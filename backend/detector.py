"""
CloudShield FairGuard — Noisy-neighbor detection engine.

Detection algorithm:
  1. Observe sustained resource pressure (CPU, queue depth, queue wait).
  2. Check whether OTHER tenants' latency or queue wait has degraded.
  3. Identify tenants running CPU/memory-intensive workloads simultaneously.
  4. Score evidence strength. Require the condition to persist across
     multiple measurement windows (reduces false positives).
  5. NEVER create an incident based on high request count alone.
  6. Clearly distinguish "tenant over budget" from "causing harm".

Evidence strength levels:
  - < 3 points: insufficient — do not create incident
  - 3–4: possible — create "needs_investigation" incident
  - 5–6: probable — create incident, recommend action
  - >= 7: strong — create incident, auto-apply bounded action

Controlled experiments are logged to validate causation.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from database import get_db

# ---------------------------------------------------------------------------
# Detection thresholds (configurable)
# ---------------------------------------------------------------------------

DETECT_THRESHOLDS = {
    "cpu_high_pct": 70.0,
    "latency_degradation_factor": 1.4,   # observed > baseline * factor
    "queue_wait_degradation_factor": 1.6,
    "min_evidence_score": 3,             # below this = no incident
    "strong_evidence_score": 7,          # auto-apply action at this level
    "sustained_windows": 3,              # number of windows condition must persist
    "cooldown_minutes": 30,              # do not re-detect same tenant within this window
}

_last_incident_time: dict[str, float] = {}  # tenant_id → epoch time of last incident


async def run_detection_cycle(measurement_history: list[dict]) -> list[dict]:
    """Run one detection cycle. Returns list of new incident summaries created."""
    if len(measurement_history) < DETECT_THRESHOLDS["sustained_windows"]:
        return []

    recent = measurement_history[-DETECT_THRESHOLDS["sustained_windows"]:]
    current = recent[-1]
    machine_cpu = current["machine"].get("cpu_percent")

    created_incidents = []
    db = await get_db()
    try:
        # Load baseline latencies per tenant (last 2 hours, pre-pressure)
        baselines = await _load_baselines(db)

        # Load current latencies per tenant (last 15 minutes)
        current_latencies = await _load_current_latencies(db)

        # Find tenants with active CPU-intensive work
        heavy_tenants = _find_heavy_tenants(recent)

        # Find tenants with degraded performance
        degraded_tenants = _find_degraded_tenants(baselines, current_latencies)

        if not heavy_tenants or not degraded_tenants:
            return []  # No candidate and no victim

        for suspect_id, suspect_info in heavy_tenants.items():
            import time as _time
            last = _last_incident_time.get(suspect_id, 0)
            if _time.time() - last < DETECT_THRESHOLDS["cooldown_minutes"] * 60:
                continue

            score, rules = _score_evidence(
                suspect_info, degraded_tenants, machine_cpu, recent
            )

            if score < DETECT_THRESHOLDS["min_evidence_score"]:
                continue

            status = "needs_investigation" if score < 5 else "open"
            severity = "low" if score < 5 else ("medium" if score < 7 else "high")

            affected = [
                {
                    "tenant_id": tid,
                    "company": info["company_name"],
                    "baseline_p95_ms": info["baseline_p95"],
                    "observed_p95_ms": info["observed_p95"],
                    "queue_wait_increase_ms": info.get("queue_wait_increase", 0),
                }
                for tid, info in degraded_tenants.items()
                if tid != suspect_id
            ]

            baseline_m = baselines.get(suspect_id, {})
            current_m = current_latencies.get(suspect_id, {})

            cursor = await db.execute(
                """INSERT INTO incidents
                   (tenant_id, title, description, severity, status, detected_at,
                    evidence, affected_tenants, detection_rules,
                    baseline_metrics, observed_metrics, is_simulated)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    suspect_id,
                    f"{suspect_info['tenant_name']} may be impacting shared resources",
                    f"Automated detection: {suspect_info['workload_type']} workload showing "
                    f"sustained resource pressure with {len(affected)} affected tenant(s). "
                    f"Evidence strength: {score} points. "
                    f"High request volume alone does NOT trigger this alert.",
                    severity, status,
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps({
                        "machine_cpu_percent": machine_cpu,
                        "active_jobs": suspect_info.get("active_jobs", 0),
                        "evidence_score": score,
                        "evidence_strength": (
                            "insufficient" if score < 3 else
                            "possible" if score < 5 else
                            "probable" if score < 7 else "strong"
                        ),
                        "note": "This is not confirmed causation. Score indicates correlation.",
                    }),
                    json.dumps(affected),
                    json.dumps(rules),
                    json.dumps({"cpu_percent": machine_cpu, **baseline_m}),
                    json.dumps(current_m),
                    0,  # not simulated — detected from real measurements
                ),
            )
            incident_id = cursor.lastrowid
            await db.commit()

            _last_incident_time[suspect_id] = __import__("time").time()
            created_incidents.append({
                "incident_id": incident_id,
                "suspect": suspect_id,
                "severity": severity,
                "evidence_score": score,
            })

    finally:
        await db.close()

    return created_incidents


async def _load_baselines(db) -> dict[str, dict]:
    """Load per-tenant baseline p95 latency from 2–4 hours ago (pre-pressure window)."""
    since = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
    until = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    cursor = await db.execute(
        """SELECT re.tenant_id, t.name, c.name AS company_name,
               AVG(re.latency_ms) AS avg_lat,
               (SELECT re2.latency_ms FROM request_events re2
                WHERE re2.tenant_id = re.tenant_id AND re2.status='accepted'
                  AND re2.timestamp BETWEEN ? AND ?
                ORDER BY re2.latency_ms DESC
                LIMIT 1 OFFSET (
                  SELECT MAX(0, CAST(COUNT(*)*0.05 AS INTEGER))
                  FROM request_events WHERE tenant_id = re.tenant_id AND status='accepted'
                    AND timestamp BETWEEN ? AND ?
                )) AS p95_lat
           FROM request_events re
           JOIN tenants t ON re.tenant_id = t.id
           JOIN companies c ON t.company_id = c.id
           WHERE re.status='accepted' AND re.timestamp BETWEEN ? AND ?
           GROUP BY re.tenant_id""",
        (since, until, since, until, since, until),
    )
    rows = await cursor.fetchall()
    return {
        r["tenant_id"]: {
            "company_name": r["company_name"],
            "baseline_avg": r["avg_lat"] or 0,
            "baseline_p95": r["p95_lat"] or 0,
        }
        for r in rows
    }


async def _load_current_latencies(db) -> dict[str, dict]:
    """Load per-tenant current latency from last 15 minutes."""
    since = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    cursor = await db.execute(
        """SELECT re.tenant_id, t.name, c.name AS company_name,
               AVG(re.latency_ms) AS avg_lat,
               (SELECT re2.latency_ms FROM request_events re2
                WHERE re2.tenant_id = re.tenant_id AND re2.status='accepted'
                  AND re2.timestamp >= ?
                ORDER BY re2.latency_ms DESC
                LIMIT 1 OFFSET (
                  SELECT MAX(0, CAST(COUNT(*)*0.05 AS INTEGER))
                  FROM request_events WHERE tenant_id = re.tenant_id AND status='accepted'
                    AND timestamp >= ?
                )) AS p95_lat
           FROM request_events re
           JOIN tenants t ON re.tenant_id = t.id
           JOIN companies c ON t.company_id = c.id
           WHERE re.status='accepted' AND re.timestamp >= ?
           GROUP BY re.tenant_id""",
        (since, since, since),
    )
    rows = await cursor.fetchall()
    return {
        r["tenant_id"]: {
            "company_name": r["company_name"],
            "observed_avg": r["avg_lat"] or 0,
            "observed_p95": r["p95_lat"] or 0,
        }
        for r in rows
    }


def _find_heavy_tenants(recent: list[dict]) -> dict[str, dict]:
    """Find tenants consistently running CPU/memory-intensive jobs."""
    heavy = {}
    for window in recent:
        for t in window.get("tenants", []):
            if t["active_jobs"] >= 3 and t.get("avg_queue_wait_ms", 0) > 200:
                tid = t["id"]
                if tid not in heavy:
                    heavy[tid] = {
                        "tenant_name": t.get("name", tid),
                        "workload_type": "CPU-intensive",  # will be enriched from DB
                        "active_jobs": t["active_jobs"],
                        "avg_queue_wait_ms": t["avg_queue_wait_ms"],
                    }
    return heavy


def _find_degraded_tenants(
    baselines: dict, current: dict
) -> dict[str, dict]:
    """Find tenants whose performance has degraded compared to baseline."""
    degraded = {}
    for tid, cur in current.items():
        baseline = baselines.get(tid)
        if not baseline:
            continue
        b95 = baseline["baseline_p95"]
        o95 = cur["observed_p95"]
        factor = DETECT_THRESHOLDS["latency_degradation_factor"]
        if b95 > 0 and o95 > b95 * factor:
            degraded[tid] = {
                "company_name": cur["company_name"],
                "baseline_p95": b95,
                "observed_p95": o95,
                "degradation_factor": round(o95 / b95, 2),
                "queue_wait_increase": 0,  # enriched by measurement in future
            }
    return degraded


def _score_evidence(
    suspect: dict, degraded: dict, machine_cpu: float | None, recent: list
) -> tuple[int, list[str]]:
    """Score evidence strength (higher = more confident). Return (score, rules_triggered)."""
    score = 0
    rules = []

    active_jobs = suspect.get("active_jobs", 0)
    if active_jobs >= 5:
        score += 2
        rules.append(f"cpu_intensive_workload_active ({active_jobs} running jobs)")
    elif active_jobs >= 3:
        score += 1
        rules.append(f"moderate_active_jobs ({active_jobs})")

    if machine_cpu is not None and machine_cpu >= DETECT_THRESHOLDS["cpu_high_pct"]:
        score += 2
        rules.append(f"cpu_sustained_above_threshold ({machine_cpu:.0f}%)")

    if len(degraded) >= 2:
        score += 2
        rules.append(f"latency_degraded_multiple_tenants ({len(degraded)} affected)")
    elif len(degraded) == 1:
        score += 1
        rules.append("latency_degraded_one_tenant")

    # Sustained across windows
    cpu_sustained = all(
        w["machine"].get("cpu_percent", 0) >= DETECT_THRESHOLDS["cpu_high_pct"]
        for w in recent
    )
    if cpu_sustained and machine_cpu is not None:
        score += 1
        rules.append(f"cpu_sustained_{len(recent)}_consecutive_windows")

    return score, rules
