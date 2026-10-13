"""
CloudShield FairGuard — Overview router.

Provides platform-wide aggregated metrics derived from the SQLite tables.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from auth import AuthContext, get_auth
from database import get_db, DEMO_MODE
from models import OverviewResponse

router = APIRouter(prefix="/api/overview", tags=["Overview"])


@router.get("", response_model=OverviewResponse)
async def get_overview(auth: AuthContext = Depends(get_auth)):
    """Return high-level platform metrics for the dashboard Overview page."""
    db = await get_db()
    try:
        # Aggregate RPM and accepted/rejected counts
        cursor = await db.execute(
            """SELECT
                 COALESCE(SUM(q.requests_per_minute), 0) AS total_rpm,
                 (SELECT COUNT(*) FROM request_events WHERE status='accepted') AS total_accepted,
                 (SELECT COUNT(*) FROM request_events WHERE status='rejected') AS total_rejected,
                 (SELECT AVG(latency_ms) FROM request_events WHERE status='accepted') AS avg_latency
               FROM tenants t
               LEFT JOIN tenant_quotas q ON q.tenant_id = t.id"""
        )
        agg = await cursor.fetchone()

        total_accepted = agg["total_accepted"] or 0
        total_rejected = agg["total_rejected"] or 0
        total_events = total_accepted + total_rejected
        success_rate = (total_accepted / max(1, total_events)) * 100

        # p95 latency approximation
        cursor2 = await db.execute(
            """SELECT latency_ms FROM request_events
               WHERE status='accepted' AND latency_ms IS NOT NULL
               ORDER BY latency_ms DESC
               LIMIT 1 OFFSET (
                 SELECT MAX(0, CAST(COUNT(*) * 0.05 AS INTEGER))
                 FROM request_events WHERE status='accepted'
               )"""
        )
        p95_row = await cursor2.fetchone()
        p95_latency = p95_row[0] if p95_row else 0

        # Active incidents
        cursor3 = await db.execute(
            "SELECT COUNT(*) FROM incidents WHERE status = 'open'"
        )
        (active_incidents,) = await cursor3.fetchone()

        # Open protection actions
        cursor4 = await db.execute(
            "SELECT COUNT(*) FROM protection_actions WHERE status = 'applied'"
        )
        (open_actions,) = await cursor4.fetchone()

        # Total queued jobs
        cursor5 = await db.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = 'queued'"
        )
        (queued_jobs,) = await cursor5.fetchone()

        # Latest machine resource measurement
        cursor6 = await db.execute(
            """SELECT cpu_percent, memory_percent FROM resource_measurements
               WHERE tenant_id IS NULL
               ORDER BY timestamp DESC LIMIT 1"""
        )
        res_row = await cursor6.fetchone()
        machine_cpu = res_row["cpu_percent"] if res_row else None
        machine_mem = res_row["memory_percent"] if res_row else None

        return OverviewResponse(
            total_requests_per_minute=int(agg["total_rpm"] or 0),
            total_accepted=total_accepted,
            total_rejected=total_rejected,
            success_rate=round(success_rate, 2),
            avg_latency_ms=round(agg["avg_latency"] or 0, 2),
            p95_latency_ms=round(p95_latency, 2),
            active_incidents=active_incidents,
            open_protection_actions=open_actions,
            machine_cpu_percent=round(machine_cpu, 1) if machine_cpu else None,
            machine_memory_percent=round(machine_mem, 1) if machine_mem else None,
            total_queued_jobs=queued_jobs,
            is_simulated=DEMO_MODE,
            controller_status="monitoring",
        )
    finally:
        await db.close()
