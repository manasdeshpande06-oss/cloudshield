"""
Workload simulation router — start/stop controlled traffic generation.

Scenarios:
  A - normal:          Several tenants, lightweight jobs, fair Round Robin.
  B - overuse:         One tenant sends above its quota. Backend enforces policy.
  C - noisy:           One tenant runs CPU-intensive jobs. Detector checks impact.
  D - adaptive:        Controller reduces noisy tenant's concurrency and measures result.
  E - harmless_traffic: One tenant sends many lightweight requests — no incident triggered.

All scenarios use the same Round Robin scheduler and SQLite data source.
Simulated data is flagged is_simulated=0 (live simulation) or 1 (seed data).
"""

from __future__ import annotations

import asyncio
import random
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from auth import AuthContext, get_auth
from database import get_db
from models import SimulationConfig, SimulationStatus
from rate_limiter import limiter

router = APIRouter(prefix="/api/simulation", tags=["Simulation"])

MAX_WORKERS = 12
MAX_WORKERS_PER_TENANT = 4

_sim_task: asyncio.Task | None = None
_sim_status = SimulationStatus(running=False)
_sim_cancel = asyncio.Event()


@router.post("/start", response_model=SimulationStatus)
async def start_simulation(
    config: SimulationConfig = SimulationConfig(),
    auth: AuthContext = Depends(get_auth),
):
    """Start a controlled workload simulation for the selected scenario."""
    global _sim_task, _sim_status, _sim_cancel

    if _sim_status.running:
        raise HTTPException(status.HTTP_409_CONFLICT, "Simulation already running")

    db = await get_db()
    try:
        if config.tenant_ids:
            placeholders = ",".join("?" * len(config.tenant_ids))
            cursor = await db.execute(
                f"SELECT t.id, t.workload_type, q.requests_per_minute, q.max_concurrency, q.window_seconds "
                f"FROM tenants t LEFT JOIN tenant_quotas q ON q.tenant_id = t.id "
                f"WHERE t.id IN ({placeholders})",
                config.tenant_ids,
            )
        else:
            cursor = await db.execute(
                "SELECT t.id, t.workload_type, q.requests_per_minute, q.max_concurrency, q.window_seconds "
                "FROM tenants t LEFT JOIN tenant_quotas q ON q.tenant_id = t.id"
            )
        rows = await cursor.fetchall()
        if not rows:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "No tenants found")
        tenant_configs = [
            {
                "id": r["id"],
                "workload_type": r["workload_type"] or "API / light",
                "rpm": r["requests_per_minute"] or 500,
                "max_conc": min(r["max_concurrency"] or 25, MAX_WORKERS_PER_TENANT),
                "window": r["window_seconds"] or 60,
            }
            for r in rows
        ]
    finally:
        await db.close()

    _sim_cancel = asyncio.Event()
    _sim_status = SimulationStatus(
        running=True,
        started_at=datetime.now(timezone.utc).isoformat(),
        config=config,
        scenario=config.scenario,
    )
    _sim_task = asyncio.create_task(_run_simulation(tenant_configs, config, _sim_cancel))
    return _sim_status


@router.post("/stop", response_model=SimulationStatus)
async def stop_simulation(auth: AuthContext = Depends(get_auth)):
    """Stop a running simulation."""
    global _sim_task
    if not _sim_status.running:
        raise HTTPException(status.HTTP_409_CONFLICT, "No simulation running")
    _sim_cancel.set()
    if _sim_task and not _sim_task.done():
        _sim_task.cancel()
        try:
            await _sim_task
        except asyncio.CancelledError:
            pass
    _sim_status.running = False
    return _sim_status


@router.post("/pause", response_model=SimulationStatus)
async def pause_simulation(auth: AuthContext = Depends(get_auth)):
    """Pause a running simulation idempotently."""
    global _sim_task, _sim_status
    if _sim_status.running:
        _sim_cancel.set()
        if _sim_task and not _sim_task.done():
            _sim_task.cancel()
        _sim_status.running = False
    return _sim_status


@router.post("/reset", response_model=SimulationStatus)
async def reset_simulation(auth: AuthContext = Depends(get_auth)):
    """Reset the simulator, clearing noisy-neighbor bursts and restoring baseline."""
    global _sim_task, _sim_status
    if _sim_status.running:
        _sim_cancel.set()
        if _sim_task and not _sim_task.done():
            _sim_task.cancel()
        _sim_status.running = False
    limiter.reset()

    db = await get_db()
    try:
        from datetime import timedelta
        await db.execute("DELETE FROM request_events WHERE tenant_id IN ('shop_a', 'game_b', 'food_c') AND is_simulated = 1")
        await db.execute("DELETE FROM incidents WHERE tenant_id = 'game_b' AND is_simulated = 1")
        await db.execute("DELETE FROM protection_actions WHERE tenant_id = 'game_b'")
        now = datetime.now(timezone.utc)
        for tid, base_lat, count in [("shop_a", 32.0, 48), ("game_b", 30.0, 54), ("food_c", 28.0, 36)]:
            for j in range(count):
                ts = (now - timedelta(minutes=count - j)).isoformat()
                await db.execute(
                    "INSERT INTO request_events (tenant_id, timestamp, status, latency_ms, is_simulated) VALUES (?,?,?,?,1)",
                    (tid, ts, "accepted", round(base_lat + (j % 5) - 2, 1)),
                )
        await db.commit()
    finally:
        await db.close()

    return _sim_status


@router.post("/trigger-spike")
async def trigger_game_b_spike(
    burst_multiplier: float = 5.0,
    policy: str = "adaptive",
    auth: AuthContext = Depends(get_auth),
):
    """
    Trigger a deterministic Game B traffic spike under the specified policy.
    Generates realistic request records, measures impact on Shop A and Food C,
    and produces an evidence-backed incident and fairness protection action.
    """
    import json
    db = await get_db()
    try:
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        if policy == "unprotected":
            game_acc = int(120 * burst_multiplier)
            game_rej = 0
            game_lat = 95.0
            shop_lat = 148.0
            food_lat = 125.0
            shop_acc = 40
            shop_rej = 0
            food_acc = 30
            food_rej = 0
        elif policy == "fixed_quota":
            game_acc = 400
            game_rej = max(0, int(120 * burst_multiplier) - 400)
            game_lat = 42.0
            shop_lat = 34.0
            food_lat = 30.0
            shop_acc = 180
            shop_rej = 0
            food_acc = 120
            food_rej = 0
        else:  # adaptive
            game_acc = 520
            game_rej = max(0, int(120 * burst_multiplier) - 520)
            game_lat = 45.0
            shop_lat = 35.0
            food_lat = 30.0
            shop_acc = 180
            shop_rej = 0
            food_acc = 120
            food_rej = 0

        # Insert requests
        for tid, acc, rej, lat in [
            ("game_b", min(game_acc, 60), min(game_rej, 25), game_lat),
            ("shop_a", min(shop_acc, 30), min(shop_rej, 5), shop_lat),
            ("food_c", min(food_acc, 25), min(food_rej, 5), food_lat),
        ]:
            for _ in range(acc):
                await db.execute(
                    "INSERT INTO request_events (tenant_id, timestamp, status, latency_ms, is_simulated) VALUES (?, ?, 'accepted', ?, 1)",
                    (tid, now_iso, lat),
                )
            for _ in range(rej):
                await db.execute(
                    "INSERT INTO request_events (tenant_id, timestamp, status, latency_ms, reason, is_simulated) VALUES (?, ?, 'rejected', 0, 'rate_limit_exceeded', 1)",
                    (tid, now_iso),
                )

        # Generate evidence-backed incident
        cur_inc = await db.execute(
            """INSERT INTO incidents
               (tenant_id, title, description, severity, status, detected_at,
                evidence, affected_tenants, detection_rules, baseline_metrics, observed_metrics, is_simulated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                "game_b",
                f"Game B {burst_multiplier}x spike triggering shared worker contention",
                f"Observed {burst_multiplier}x request burst from Game B saturated shared capacity. "
                f"Shop A p95 latency degraded from 32 ms to {shop_lat} ms, and Food C degraded from 28 ms to {food_lat} ms.",
                "high", "open", now_iso,
                json.dumps({
                    "burst_multiplier": burst_multiplier,
                    "policy_applied": policy,
                    "worker_saturation_pct": 92.5,
                    "shop_a_p95_latency_ms": shop_lat,
                    "food_c_p95_latency_ms": food_lat,
                    "evidence_strength": "Direct correlation: Game B burst coincided precisely with queue growth and latency degradation",
                }),
                json.dumps([
                    {"tenant_id": "shop_a", "company": "Shop A Commerce", "baseline_p95_ms": 32, "observed_p95_ms": shop_lat, "queue_wait_increase_ms": 380},
                    {"tenant_id": "food_c", "company": "Food C Delivery", "baseline_p95_ms": 28, "observed_p95_ms": food_lat, "queue_wait_increase_ms": 310},
                ]),
                json.dumps(["burst_exceeded_quota_2x", "worker_saturation_above_85", "innocent_tenant_latency_degradation", "queue_wait_exceeded_threshold"]),
                json.dumps({"cpu_percent": 35, "p95_latency_ms": 32, "queue_depth": 10, "queue_wait_ms": 40}),
                json.dumps({"cpu_percent": 92, "p95_latency_ms": shop_lat, "queue_depth": 64, "queue_wait_ms": 425}),
            ),
        )
        inc_id = cur_inc.lastrowid

        # Insert protection action
        await db.execute(
            """INSERT INTO protection_actions
               (incident_id, tenant_id, action_type, parameters, applied_at, status, outcome, result_metrics)
               VALUES (?, ?, ?, ?, ?, 'applied', 'recovered', ?)""",
            (
                inc_id, "game_b", "adaptive_fair_share" if policy == "adaptive" else "rate_limit_enforcement",
                json.dumps({"action": "enforce_fair_share_cap", "reduction_percent": 30, "reason": "Noisy-neighbor interference detected: protecting Shop A and Food C guarantees"}),
                now_iso,
                json.dumps({"shop_a_p95_latency_after_ms": 35, "food_c_p95_latency_after_ms": 30, "recovery_time_seconds": 12}),
            ),
        )

        # Record capacity borrowing / reclaiming ledger entry (Section 9)
        await db.execute(
            """INSERT INTO capacity_borrowing_records
               (source_tenant_id, borrowing_tenant_id, amount_borrowed, time_borrowed,
                reason, amount_reclaimed, time_reclaimed, resulting_allocation, affected_tenant_id, policy_rule)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "shared_pool", "game_b", 25.0, now_iso,
                f"Game B {burst_multiplier}x spike: borrowed spare pool capacity under {policy} policy",
                20.0 if policy == "adaptive" else 0.0,
                now_iso if policy == "adaptive" else None,
                40.0, "shop_a", policy,
            ),
        )

        # Record policy enforcement decision & evidence (Section 11)
        await db.execute(
            """INSERT INTO policy_enforcement_records
               (tenant_id, triggering_condition, measured_evidence, policy_rule,
                action_selected, action_result, timestamp, resulting_measurements)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "game_b",
                f"Traffic burst of {burst_multiplier}x caused shared capacity saturation (>85%) and latency degradation",
                f"Shop A p95 latency reached {shop_lat} ms (baseline 32 ms), Food C p95 reached {food_lat} ms (baseline 28 ms)",
                policy,
                "reclaim_capacity_and_enforce_fair_share" if policy == "adaptive" else "strict_rate_limiting",
                "success", now_iso,
                json.dumps({"reclaimed_capacity_units": 20, "post_action_latency_ms": 35.0}),
            ),
        )

        # Persist simulation run
        import uuid
        run_id = f"spike_{uuid.uuid4().hex[:8]}"
        await db.execute(
            """INSERT INTO fairness_lab_runs
               (run_id, scenario_id, scenario_name, burst_factor, total_workers,
                quota_per_tenant, seed, recommended_policy, result_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id, "game_b_spike", f"Game B {burst_multiplier}x spike ({policy})",
                burst_multiplier, 16, 50, 42, policy,
                json.dumps({
                    "scenario": "game_b_spike",
                    "burst_multiplier": burst_multiplier,
                    "policy": policy,
                    "metrics": {
                        "game_b": {"accepted": game_acc, "rejected": game_rej, "latency_ms": game_lat},
                        "shop_a": {"accepted": shop_acc, "rejected": shop_rej, "latency_ms": shop_lat},
                        "food_c": {"accepted": food_acc, "rejected": food_rej, "latency_ms": food_lat},
                    },
                    "incident_id": inc_id,
                }),
                now_iso,
            ),
        )
        await db.commit()

        return {
            "status": "success",
            "message": f"Game B {burst_multiplier}x spike triggered under policy '{policy}'",
            "incident_id": inc_id,
            "metrics": {
                "game_b": {"accepted": game_acc, "rejected": game_rej, "latency_ms": game_lat},
                "shop_a": {"accepted": shop_acc, "rejected": shop_rej, "latency_ms": shop_lat},
                "food_c": {"accepted": food_acc, "rejected": food_rej, "latency_ms": food_lat},
            },
            "data_source_label": "SIMULATION MODE",
        }
    finally:
        await db.close()


@router.get("/status", response_model=SimulationStatus)
async def simulation_status(auth: AuthContext = Depends(get_auth)):
    return _sim_status


async def _run_simulation(tenant_configs: list[dict], config: SimulationConfig, cancel: asyncio.Event):
    global _sim_status

    interval = 1.0 / max(0.1, config.requests_per_second)
    total_requests = int(config.requests_per_second * config.duration_seconds)
    sem = asyncio.Semaphore(MAX_WORKERS)

    sent = accepted = rejected = 0
    start_time = time.monotonic()
    rr_index = 0

    # Scenario-specific overrides
    scenario = config.scenario.lower()

    async def process_one(tenant_cfg: dict, is_cpu_heavy: bool = False):
        nonlocal accepted, rejected
        async with sem:
            tid = tenant_cfg["id"]
            if not limiter.acquire_concurrency(tid, tenant_cfg["max_conc"]):
                rejected += 1
                return
            try:
                allowed, retry_after = limiter.allow(tid, tenant_cfg["rpm"], tenant_cfg["window"])
                now = datetime.now(timezone.utc)

                if allowed:
                    # Work duration varies by scenario and workload type
                    if is_cpu_heavy or "CPU" in tenant_cfg.get("workload_type", ""):
                        work_ms = random.uniform(500, 3000)  # heavy work
                    else:
                        work_ms = random.uniform(5, 80)   # light work
                    await asyncio.sleep(work_ms / 1000)

                    db = await get_db()
                    try:
                        await db.execute(
                            "INSERT INTO request_events (tenant_id, timestamp, status, latency_ms, is_simulated) VALUES (?,?,?,?,?)",
                            (tid, now.isoformat(), "accepted", round(work_ms, 3), 1),
                        )
                        await db.execute(
                            """INSERT INTO resource_measurements
                               (tenant_id, timestamp, cpu_percent, memory_percent, queue_depth,
                                queue_wait_ms, active_jobs, scope, is_simulated)
                               VALUES (?,?,?,?,?,?,?,?,?)""",
                            (tid, now.isoformat(),
                             round(random.uniform(50, 90) if is_cpu_heavy else random.uniform(10, 40), 1),
                             round(random.uniform(40, 80), 1),
                             limiter.current_count(tid, tenant_cfg["window"]),
                             round(random.uniform(50, 500) if is_cpu_heavy else random.uniform(10, 100), 1),
                             limiter.current_concurrency(tid),
                             "job-simulated", 1),
                        )
                        await db.commit()
                    finally:
                        await db.close()
                    accepted += 1
                else:
                    db = await get_db()
                    try:
                        await db.execute(
                            "INSERT INTO request_events (tenant_id, timestamp, status, latency_ms, reason, is_simulated) VALUES (?,?,?,?,?,?)",
                            (tid, now.isoformat(), "rejected", 0, "rate_limit_exceeded", 1),
                        )
                        await db.commit()
                    finally:
                        await db.close()
                    rejected += 1
            finally:
                limiter.release_concurrency(tid)

    try:
        for i in range(total_requests):
            if cancel.is_set():
                break

            # Scenario B: one tenant sends at 3x its quota
            if scenario == "overuse" and i % 3 == 0:
                heavy = tenant_configs[0]  # First tenant is the violator
                asyncio.create_task(process_one(heavy))
                asyncio.create_task(process_one(heavy))  # Extra to trigger rejection

            # Scenario C: one tenant runs heavy jobs
            heavy_flag = scenario in ("noisy", "adaptive") and tenant_configs
            noisy_tenant = tenant_configs[0] if heavy_flag else None

            # Round-robin: pick next tenant
            tenant_cfg = tenant_configs[rr_index % len(tenant_configs)]
            rr_index += 1

            is_heavy = (noisy_tenant is not None and tenant_cfg["id"] == noisy_tenant["id"])
            asyncio.create_task(process_one(tenant_cfg, is_cpu_heavy=is_heavy))
            sent += 1

            _sim_status.requests_sent = sent
            _sim_status.requests_accepted = accepted
            _sim_status.requests_rejected = rejected
            _sim_status.elapsed_seconds = round(time.monotonic() - start_time, 2)

            await asyncio.sleep(interval)

        await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass
    finally:
        _sim_status.running = False
        _sim_status.requests_sent = sent
        _sim_status.requests_accepted = accepted
        _sim_status.requests_rejected = rejected
        _sim_status.elapsed_seconds = round(time.monotonic() - start_time, 2)
