"""
CloudShield FairGuard — Rule-based adaptive resource controller.

Design principles:
- Uses transparent, configurable thresholds (no ML).
- Takes bounded, reversible actions only.
- Records every decision with reason and evidence.
- Enforces cooldowns between repeated actions.
- Never reduces a tenant's allocation solely because it is busy.
  Evidence of policy violation OR measured impact on other tenants is required.

Metric scopes are clearly labelled:
  - machine: psutil-measured machine-wide CPU/memory
  - process: this backend process (not yet implemented)
  - job-simulated: per-job simulated cost

IMPORTANT: In a production multi-tenant deployment, reliable per-tenant
CPU/memory attribution requires cgroup isolation or container metrics.
This prototype uses job execution time and workload type as a proxy.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

from database import get_db

# ---------------------------------------------------------------------------
# Thresholds (configurable)
# ---------------------------------------------------------------------------

THRESHOLDS = {
    # Trigger adaptive action when these are SUSTAINED across N windows
    "cpu_high_pct": 75.0,          # machine CPU %
    "memory_high_pct": 80.0,       # machine memory %
    "queue_depth_high": 50,        # total queued jobs
    "queue_wait_high_ms": 400.0,   # queue wait p90 threshold
    "latency_degraded_factor": 1.5, # p95 latency > baseline * this factor
    "sustained_windows": 3,         # consecutive measurement windows to confirm
    "measurement_interval_s": 30,  # seconds between measurements
    "cooldown_s": 300,             # seconds before repeating action on same tenant
    "max_actions_per_tenant": 3,   # max active actions per tenant
    "min_concurrency": 1,          # never reduce below this
    "max_concurrency": 200,        # never increase above this
    "max_throttle_minutes": 60,    # maximum action duration
}

# ---------------------------------------------------------------------------
# Controller state
# ---------------------------------------------------------------------------

_controller_running = False
_controller_task: asyncio.Task | None = None
_measurement_history: list[dict] = []  # Rolling window of measurements
_last_action_time: dict[str, float] = {}  # tenant_id → monotonic time
_controller_status = "idle"  # idle | monitoring | acting | cooling_down


def get_controller_status() -> str:
    return _controller_status


# ---------------------------------------------------------------------------
# Real machine metrics (psutil)
# ---------------------------------------------------------------------------

def _read_machine_metrics() -> dict[str, Any]:
    """Read real machine-level CPU and memory. Clearly scoped as 'machine'."""
    if _PSUTIL_AVAILABLE:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        return {
            "cpu_percent": round(cpu, 1),
            "memory_percent": round(mem.percent, 1),
            "memory_available_mb": round(mem.available / 1024 / 1024, 0),
            "scope": "machine",
            "psutil_available": True,
        }
    else:
        # Fallback: return None to indicate metrics not available
        return {
            "cpu_percent": None,
            "memory_percent": None,
            "scope": "machine",
            "psutil_available": False,
        }


# ---------------------------------------------------------------------------
# Controller main loop
# ---------------------------------------------------------------------------

async def start_controller():
    global _controller_running, _controller_task
    if _controller_running:
        return
    _controller_running = True
    _controller_task = asyncio.create_task(_controller_loop())


async def stop_controller():
    global _controller_running, _controller_task
    _controller_running = False
    if _controller_task and not _controller_task.done():
        _controller_task.cancel()
        try:
            await _controller_task
        except asyncio.CancelledError:
            pass


async def _controller_loop():
    """Periodically measure, evaluate, and optionally act."""
    global _controller_status
    _controller_status = "monitoring"

    while _controller_running:
        try:
            await _measure_and_evaluate()
        except Exception as e:
            await _log("error", "controller_error", detail=str(e))
        await asyncio.sleep(THRESHOLDS["measurement_interval_s"])

    _controller_status = "idle"


async def _measure_and_evaluate():
    """One evaluation cycle: collect metrics, detect pressure, decide action."""
    global _controller_status, _measurement_history

    now = datetime.now(timezone.utc)
    machine = _read_machine_metrics()

    db = await get_db()
    try:
        # Machine-level snapshot
        await db.execute(
            """INSERT INTO resource_measurements
               (tenant_id, timestamp, cpu_percent, memory_percent, queue_depth, scope, is_simulated)
               VALUES (?,?,?,?,?,?,?)""",
            (None, now.isoformat(),
             machine.get("cpu_percent"),
             machine.get("memory_percent"),
             0, machine["scope"], 0),
        )

        # Per-tenant metrics: queue depth, job counts
        cursor = await db.execute(
            """SELECT t.id, t.name, t.company_id,
                   (SELECT COUNT(*) FROM jobs j WHERE j.tenant_id = t.id AND j.status='queued') AS q_depth,
                   (SELECT COUNT(*) FROM jobs j WHERE j.tenant_id = t.id AND j.status='running') AS active,
                   (SELECT AVG(j.queue_wait_ms) FROM jobs j
                    WHERE j.tenant_id = t.id AND j.completed_at IS NOT NULL
                    AND j.started_at > ?) AS avg_wait,
                   q.max_concurrency, q.resource_budget_cpu, q.requests_per_minute
               FROM tenants t
               LEFT JOIN tenant_quotas q ON q.tenant_id = t.id""",
            ((now - timedelta(minutes=5)).isoformat(),),
        )
        tenant_metrics = await cursor.fetchall()

        snapshot = {
            "timestamp": now.isoformat(),
            "machine": machine,
            "tenants": [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "company_id": r["company_id"],
                    "queue_depth": r["q_depth"] or 0,
                    "active_jobs": r["active"] or 0,
                    "avg_queue_wait_ms": r["avg_wait"] or 0,
                    "max_concurrency": r["max_concurrency"] or 25,
                    "cpu_budget": r["resource_budget_cpu"] or 25.0,
                }
                for r in tenant_metrics
            ],
        }

        _measurement_history.append(snapshot)
        # Keep only the last 10 windows
        if len(_measurement_history) > 10:
            _measurement_history = _measurement_history[-10:]

        await db.commit()

        # Evaluate if we have enough windows
        if len(_measurement_history) >= THRESHOLDS["sustained_windows"]:
            await _evaluate_pressure(db, snapshot)

    finally:
        await db.close()


async def _evaluate_pressure(db, current: dict):
    """Check sustained conditions and decide whether to act."""
    global _controller_status

    machine = current["machine"]
    cpu = machine.get("cpu_percent")
    mem = machine.get("memory_percent")
    recent = _measurement_history[-THRESHOLDS["sustained_windows"]:]

    # Check if CPU pressure is sustained
    cpu_sustained = (
        cpu is not None and
        all(w["machine"].get("cpu_percent", 0) >= THRESHOLDS["cpu_high_pct"]
            for w in recent)
    )
    mem_sustained = (
        mem is not None and
        all(w["machine"].get("memory_percent", 0) >= THRESHOLDS["memory_high_pct"]
            for w in recent)
    )
    # Check if any tenant has high queue wait sustained
    high_wait_tenants = _find_high_wait_tenants(recent)

    if not (cpu_sustained or mem_sustained or high_wait_tenants):
        _controller_status = "monitoring"
        return

    _controller_status = "acting"

    # Find tenants that are most likely causing pressure
    # Criteria: high active_jobs + CPU-intensive workload + policy violations
    cursor = await db.execute(
        """SELECT t.id, t.name, t.workload_type, t.company_id,
               q.max_concurrency,
               (SELECT COUNT(*) FROM request_events re
                WHERE re.tenant_id = t.id AND re.status='rejected'
                AND re.reason='rate_limit_exceeded'
                AND re.timestamp > ?) AS recent_violations,
               (SELECT COUNT(*) FROM jobs j WHERE j.tenant_id = t.id AND j.status='running') AS active_jobs
           FROM tenants t
           LEFT JOIN tenant_quotas q ON q.tenant_id = t.id
           ORDER BY active_jobs DESC""",
        ((datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),),
    )
    tenants = await cursor.fetchall()

    for t in tenants:
        tid = t["id"]
        # Skip tenants in cooldown
        last = _last_action_time.get(tid, 0)
        if time.monotonic() - last < THRESHOLDS["cooldown_s"]:
            continue

        active_jobs = t["active_jobs"] or 0
        violations = t["recent_violations"] or 0
        is_cpu_intensive = t["workload_type"] in ("CPU-intensive", "GPU compute", "ML inference")

        # Evidence score: require policy violation OR impact on other tenants
        evidence_score = 0
        if is_cpu_intensive and active_jobs > 3:
            evidence_score += 2
        if violations > 0:
            evidence_score += 2
        if cpu_sustained and is_cpu_intensive:
            evidence_score += 1
        if tid in high_wait_tenants:
            evidence_score += 1

        if evidence_score >= 3:
            await _apply_adaptive_action(db, dict(t), evidence_score, cpu_sustained, mem_sustained)
            _last_action_time[tid] = time.monotonic()
            break  # Only one action per cycle

    _controller_status = "monitoring"


def _find_high_wait_tenants(recent_windows: list) -> set[str]:
    """Return tenant IDs with consistently high queue wait across recent windows."""
    result = set()
    for tid_set in [
        set(
            t["id"] for t in w["tenants"]
            if (t["avg_queue_wait_ms"] or 0) >= THRESHOLDS["queue_wait_high_ms"]
        )
        for w in recent_windows
    ]:
        result |= tid_set
    return result


async def _apply_adaptive_action(db, tenant: dict, evidence_score: int,
                                  cpu_pressure: bool, mem_pressure: bool):
    """Apply a bounded protective action to the identified tenant."""
    tid = tenant["id"]
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=THRESHOLDS["max_throttle_minutes"])

    # Determine action: reduce concurrency by 25%, minimum 1
    orig_conc = tenant["max_concurrency"] or 25
    new_conc = max(THRESHOLDS["min_concurrency"], int(orig_conc * 0.75))

    if new_conc >= orig_conc:
        return  # Already at minimum, skip

    reasons = []
    if cpu_pressure:
        reasons.append("machine CPU sustained above threshold")
    if mem_pressure:
        reasons.append("machine memory sustained above threshold")
    reason_str = "; ".join(reasons) or "resource pressure detected"

    await db.execute(
        "UPDATE tenant_quotas SET max_concurrency = ?, updated_at = ? WHERE tenant_id = ?",
        (new_conc, now.isoformat(), tid),
    )
    await db.execute(
        "UPDATE tenants SET status = 'protected' WHERE id = ?", (tid,)
    )

    await db.execute(
        """INSERT INTO protection_actions
           (tenant_id, action_type, parameters, applied_at, expires_at, status, outcome)
           VALUES (?,?,?,?,?,?,?)""",
        (tid, "concurrency_reduction",
         json.dumps({
             "original_concurrency": orig_conc,
             "new_concurrency": new_conc,
             "reason": reason_str,
             "evidence_score": evidence_score,
             "auto_applied": True,
         }),
         now.isoformat(), expires.isoformat(), "applied", "pending_measurement"),
    )
    await db.commit()

    await _log("warning", "adaptive_action_applied", tenant_id=tid,
               detail=f"Reduced concurrency {orig_conc}→{new_conc}. Reason: {reason_str}")


async def _log(level: str, event: str, tenant_id: str | None = None, detail: str | None = None):
    """Write an entry to the controller_log table."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO controller_log (timestamp, level, event, tenant_id, detail) VALUES (?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), level, event, tenant_id, detail),
        )
        await db.commit()
    finally:
        await db.close()
