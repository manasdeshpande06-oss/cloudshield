"""Tenants router — list, detail, metrics, quota configuration, and resource visibility."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from auth import AuthContext, get_auth
from database import get_db
from models import TenantMetrics, TenantOut, TenantQuota, TenantQuotaOut
from rate_limiter import limiter

router = APIRouter(prefix="/api", tags=["Tenants"])


async def _get_tenant_row(db, tenant_id: str):
    """Return the tenant row or raise 404."""
    cursor = await db.execute(
        "SELECT t.*, c.name AS company_name FROM tenants t JOIN companies c ON t.company_id = c.id WHERE t.id = ?",
        (tenant_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    return row


@router.get("/tenants", response_model=list[TenantOut])
async def list_all_tenants(
    auth: AuthContext = Depends(get_auth),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=100),
    q: str | None = Query(None),
    workload_type: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    sortBy: str = Query("name"),
    sortDir: str = Query("asc"),
    response: Response = None,
):
    """List all tenants (admin) or company-scoped tenants, with filtering and sorting."""
    db = await get_db()
    try:
        conditions = []
        params: list = []
        if auth.company_filter():
            conditions.append("t.company_id = ?")
            params.append(auth.company_filter())
        if q:
            conditions.append("(t.name LIKE ? OR t.id LIKE ? OR c.name LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        if workload_type:
            conditions.append("t.workload_type = ?")
            params.append(workload_type)
        if status_filter:
            conditions.append("t.status = ?")
            params.append(status_filter)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        count_cursor = await db.execute(
            f"SELECT COUNT(*) FROM tenants t JOIN companies c ON t.company_id = c.id {where}",
            tuple(params),
        )
        (total_count,) = await count_cursor.fetchone()
        if response is not None:
            response.headers["X-Total-Count"] = str(total_count)

        allowed_sort = {"name", "workload_type", "status", "created_at"}
        sort_col = f"t.{sortBy}" if sortBy in allowed_sort else "t.name"
        direction = "ASC" if sortDir.lower() == "asc" else "DESC"
        offset = (page - 1) * pageSize

        cursor = await db.execute(
            f"""SELECT t.*, c.name AS company_name,
                   COALESCE(q.requests_per_minute, 500) AS quota_rpm,
                   (SELECT COUNT(*) FROM request_events re WHERE re.tenant_id = t.id AND re.status='accepted') AS accepted_count,
                   (SELECT COUNT(*) FROM request_events re WHERE re.tenant_id = t.id AND re.status='rejected') AS rejected_count,
                   (SELECT AVG(re.latency_ms) FROM request_events re WHERE re.tenant_id = t.id AND re.status='accepted') AS avg_latency,
                   (SELECT re.latency_ms FROM request_events re
                    WHERE re.tenant_id = t.id AND re.status='accepted' AND re.latency_ms IS NOT NULL
                    ORDER BY re.latency_ms DESC LIMIT 1) AS p95_latency
                FROM tenants t
                JOIN companies c ON t.company_id = c.id
                LEFT JOIN tenant_quotas q ON q.tenant_id = t.id
                {where} ORDER BY {sort_col} {direction} LIMIT ? OFFSET ?""",
            tuple(params) + (pageSize, offset),
        )
        rows = await cursor.fetchall()
        return [
            TenantOut(
                id=r["id"], company_id=r["company_id"], company_name=r["company_name"],
                name=r["name"], workload_type=r["workload_type"],
                status=r["status"], created_at=r["created_at"],
                accepted_count=r["accepted_count"] or 0,
                rejected_count=r["rejected_count"] or 0,
                avg_latency_ms=round(r["avg_latency"] or 0.0, 1),
                p95_latency_ms=round(r["p95_latency"] or 0.0, 1),
                quota_rpm=r["quota_rpm"] or 500,
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.get("/companies/{company_id}/tenants", response_model=list[TenantOut])
async def list_tenants_by_company(
    company_id: str,
    auth: AuthContext = Depends(get_auth),
):
    """List all tenants belonging to a company."""
    auth.assert_company_access(company_id)
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT t.*, c.name AS company_name,
                   COALESCE(q.requests_per_minute, 500) AS quota_rpm,
                   (SELECT COUNT(*) FROM request_events re WHERE re.tenant_id = t.id AND re.status='accepted') AS accepted_count,
                   (SELECT COUNT(*) FROM request_events re WHERE re.tenant_id = t.id AND re.status='rejected') AS rejected_count,
                   (SELECT AVG(re.latency_ms) FROM request_events re WHERE re.tenant_id = t.id AND re.status='accepted') AS avg_latency,
                   (SELECT re.latency_ms FROM request_events re
                    WHERE re.tenant_id = t.id AND re.status='accepted' AND re.latency_ms IS NOT NULL
                    ORDER BY re.latency_ms DESC LIMIT 1) AS p95_latency
               FROM tenants t
               JOIN companies c ON t.company_id = c.id
               LEFT JOIN tenant_quotas q ON q.tenant_id = t.id
               WHERE t.company_id = ? ORDER BY t.name""",
            (company_id,),
        )
        rows = await cursor.fetchall()
        return [
            TenantOut(
                id=r["id"], company_id=r["company_id"], company_name=r["company_name"],
                name=r["name"], workload_type=r["workload_type"],
                status=r["status"], created_at=r["created_at"],
                accepted_count=r["accepted_count"] or 0,
                rejected_count=r["rejected_count"] or 0,
                avg_latency_ms=round(r["avg_latency"] or 0.0, 1),
                p95_latency_ms=round(r["p95_latency"] or 0.0, 1),
                quota_rpm=r["quota_rpm"] or 500,
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.get("/tenants/{tenant_id}", response_model=TenantMetrics)
async def get_tenant(tenant_id: str, auth: AuthContext = Depends(get_auth)):
    """Retrieve an individual tenant with full current metrics."""
    db = await get_db()
    try:
        row = await _get_tenant_row(db, tenant_id)
        auth.assert_tenant_access_by_company(row["company_id"])

        tenant = TenantOut(
            id=row["id"], company_id=row["company_id"], company_name=row["company_name"],
            name=row["name"], workload_type=row["workload_type"],
            status=row["status"], created_at=row["created_at"],
        )

        # Quota
        cursor_q = await db.execute("SELECT * FROM tenant_quotas WHERE tenant_id = ?", (tenant_id,))
        qrow = await cursor_q.fetchone()
        now_iso = datetime.now(timezone.utc).isoformat()
        if qrow:
            quota = TenantQuotaOut(
                tenant_id=qrow["tenant_id"],
                requests_per_minute=qrow["requests_per_minute"],
                max_concurrency=qrow["max_concurrency"],
                queue_limit=qrow["queue_limit"] if "queue_limit" in qrow.keys() else 100,
                resource_budget_cpu=qrow["resource_budget_cpu"] if "resource_budget_cpu" in qrow.keys() else 25.0,
                resource_budget_memory=qrow["resource_budget_memory"] if "resource_budget_memory" in qrow.keys() else 25.0,
                window_seconds=qrow["window_seconds"],
                updated_at=qrow["updated_at"],
            )
        else:
            quota = TenantQuotaOut(
                tenant_id=tenant_id, requests_per_minute=500, max_concurrency=25,
                queue_limit=100, resource_budget_cpu=25.0, resource_budget_memory=25.0,
                window_seconds=60, updated_at=now_iso,
            )

        # Live rate-limiter count
        current_rpm = limiter.current_count(tenant_id, quota.window_seconds)

        # Request event aggregates
        cursor_r = await db.execute(
            """SELECT
                 COUNT(*) FILTER (WHERE status='accepted') AS accepted,
                 COUNT(*) FILTER (WHERE status='rejected') AS rejected,
                 AVG(latency_ms) FILTER (WHERE status='accepted') AS avg_lat,
                 COUNT(*) FILTER (WHERE status='rejected' AND reason='rate_limit_exceeded') AS quota_violations,
                 (SELECT latency_ms FROM request_events
                  WHERE tenant_id = ? AND status='accepted' AND latency_ms IS NOT NULL
                  ORDER BY latency_ms DESC
                  LIMIT 1 OFFSET (
                    SELECT MAX(0, CAST(COUNT(*)*0.05 AS INTEGER))
                    FROM request_events WHERE tenant_id = ? AND status='accepted'
                  )) AS p95_lat
               FROM request_events WHERE tenant_id = ?""",
            (tenant_id, tenant_id, tenant_id),
        )
        stats = await cursor_r.fetchone()

        # Job counts
        cursor_j = await db.execute(
            "SELECT status, COUNT(*) AS cnt FROM jobs WHERE tenant_id = ? GROUP BY status",
            (tenant_id,),
        )
        job_counts = {r["status"]: r["cnt"] for r in await cursor_j.fetchall()}

        # Latest per-tenant resource measurement
        cursor_m = await db.execute(
            """SELECT cpu_percent, memory_percent, queue_depth, queue_wait_ms, scope
               FROM resource_measurements
               WHERE tenant_id = ?
               ORDER BY timestamp DESC LIMIT 1""",
            (tenant_id,),
        )
        mrow = await cursor_m.fetchone()

        cpu_pct = mrow["cpu_percent"] if mrow else None
        mem_pct = mrow["memory_percent"] if mrow else None
        cpu_scope = mrow["scope"] if mrow else "not_measured"
        queue_depth = mrow["queue_depth"] if mrow else 0
        queue_wait = mrow["queue_wait_ms"] if mrow else 0

        # Active protection action
        cursor_p = await db.execute(
            "SELECT action_type FROM protection_actions WHERE tenant_id = ? AND status='applied' ORDER BY applied_at DESC LIMIT 1",
            (tenant_id,),
        )
        prow = await cursor_p.fetchone()

        accepted = stats["accepted"] if stats else 0
        rpm_quota = quota.requests_per_minute
        est_rpm = current_rpm or round((accepted / max(1, 24 * 60)), 1)
        quota_util = round(est_rpm / max(1, rpm_quota) * 100, 1)
        cpu_budget_util = round(cpu_pct / quota.resource_budget_cpu * 100, 1) if cpu_pct else None

        return TenantMetrics(
            tenant=tenant,
            quota=quota,
            requests_per_minute=current_rpm,
            accepted_count=accepted,
            rejected_count=stats["rejected"] if stats else 0,
            avg_latency_ms=round(stats["avg_lat"] or 0, 2),
            p95_latency_ms=round(stats["p95_lat"] or 0, 2),
            active_jobs=job_counts.get("running", 0),
            queued_jobs=job_counts.get("queued", 0),
            completed_jobs=job_counts.get("completed", 0),
            failed_jobs=job_counts.get("failed", 0),
            cpu_percent=round(cpu_pct, 1) if cpu_pct else None,
            memory_percent=round(mem_pct, 1) if mem_pct else None,
            cpu_scope=cpu_scope,
            memory_scope=cpu_scope,
            queue_depth=queue_depth or 0,
            queue_wait_ms=round(queue_wait or 0, 1),
            quota_utilization_pct=quota_util,
            cpu_budget_utilization_pct=cpu_budget_util,
            quota_violations=stats["quota_violations"] if stats else 0,
            resource_violations=0,
            active_protection=prow["action_type"] if prow else None,
        )
    finally:
        await db.close()


@router.put("/tenants/{tenant_id}/quota", response_model=TenantQuotaOut)
async def update_quota(
    tenant_id: str,
    body: TenantQuota,
    auth: AuthContext = Depends(get_auth),
):
    """Configure a tenant's quota, concurrency, queue limits, and resource budgets."""
    db = await get_db()
    try:
        row = await _get_tenant_row(db, tenant_id)
        auth.assert_tenant_access_by_company(row["company_id"])

        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            """INSERT INTO tenant_quotas
               (tenant_id, requests_per_minute, max_concurrency, queue_limit,
                resource_budget_cpu, resource_budget_memory, window_seconds, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(tenant_id) DO UPDATE SET
                 requests_per_minute = excluded.requests_per_minute,
                 max_concurrency = excluded.max_concurrency,
                 queue_limit = excluded.queue_limit,
                 resource_budget_cpu = excluded.resource_budget_cpu,
                 resource_budget_memory = excluded.resource_budget_memory,
                 window_seconds = excluded.window_seconds,
                 updated_at = excluded.updated_at""",
            (tenant_id, body.requests_per_minute, body.max_concurrency, body.queue_limit,
             body.resource_budget_cpu, body.resource_budget_memory, body.window_seconds, now),
        )
        await db.commit()
        return TenantQuotaOut(
            tenant_id=tenant_id,
            requests_per_minute=body.requests_per_minute,
            max_concurrency=body.max_concurrency,
            queue_limit=body.queue_limit,
            resource_budget_cpu=body.resource_budget_cpu,
            resource_budget_memory=body.resource_budget_memory,
            window_seconds=body.window_seconds,
            updated_at=now,
        )
    finally:
        await db.close()
