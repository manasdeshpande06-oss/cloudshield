"""Companies router — list, detail, and tenant comparison views."""

from __future__ import annotations

import json
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from auth import AuthContext, get_auth
from database import get_db
from models import CompanyDetail, CompanyOut, TenantComparisonRow

router = APIRouter(prefix="/api/companies", tags=["Companies"])


@router.get("", response_model=list[CompanyOut])
async def list_companies(
    auth: AuthContext = Depends(get_auth),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=100),
    q: str | None = Query(None),
    response: Response = None,
):
    """List companies visible to the caller, with optional search."""
    db = await get_db()
    try:
        conditions = []
        params: list = []
        if auth.company_filter():
            conditions.append("c.id = ?")
            params.append(auth.company_filter())
        if q:
            conditions.append("c.name LIKE ?")
            params.append(f"%{q}%")

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        count_cursor = await db.execute(f"SELECT COUNT(*) FROM companies c {where}", tuple(params))
        (total_count,) = await count_cursor.fetchone()
        if response is not None:
            response.headers["X-Total-Count"] = str(total_count)

        offset = (page - 1) * pageSize
        cursor = await db.execute(
            f"""SELECT c.*,
                    (SELECT COUNT(*) FROM tenants t WHERE t.company_id = c.id) AS tenant_count
                FROM companies c {where} ORDER BY c.name LIMIT ? OFFSET ?""",
            tuple(params) + (pageSize, offset),
        )
        rows = await cursor.fetchall()
        return [
            CompanyOut(
                id=r["id"], name=r["name"], slug=r["slug"],
                registered_at=r["registered_at"], status=r["status"],
                tenant_count=r["tenant_count"],
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.get("/comparison", response_model=list[TenantComparisonRow])
async def company_tenant_comparison(
    auth: AuthContext = Depends(get_auth),
    company_id: str | None = Query(None),
    workload_type: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
):
    """Cross-company/tenant resource comparison for the admin dashboard.

    Returns one row per tenant with all relevant metrics for comparison.
    Company-scoped users see only their own tenants.
    """
    db = await get_db()
    try:
        conditions = []
        params: list = []

        if auth.company_filter():
            conditions.append("t.company_id = ?")
            params.append(auth.company_filter())
        elif company_id:
            conditions.append("t.company_id = ?")
            params.append(company_id)

        if workload_type:
            conditions.append("t.workload_type = ?")
            params.append(workload_type)
        if status_filter:
            conditions.append("t.status = ?")
            params.append(status_filter)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cursor = await db.execute(
            f"""SELECT t.id, t.name, t.company_id, t.workload_type, t.status,
                    c.name AS company_name,
                    q.requests_per_minute, q.max_concurrency, q.queue_limit,
                    q.resource_budget_cpu, q.resource_budget_memory,
                    -- Request counts
                    (SELECT COUNT(*) FROM request_events re WHERE re.tenant_id = t.id AND re.status='accepted') AS accepted_count,
                    (SELECT COUNT(*) FROM request_events re WHERE re.tenant_id = t.id AND re.status='rejected') AS rejected_count,
                    (SELECT AVG(re.latency_ms) FROM request_events re WHERE re.tenant_id = t.id AND re.status='accepted') AS avg_latency,
                    -- p95 latency approximation
                    (SELECT re.latency_ms FROM request_events re
                     WHERE re.tenant_id = t.id AND re.status='accepted' AND re.latency_ms IS NOT NULL
                     ORDER BY re.latency_ms DESC
                     LIMIT 1
                    ) AS p95_latency,
                    -- Job counts
                    (SELECT COUNT(*) FROM jobs j WHERE j.tenant_id = t.id AND j.status='running') AS active_jobs,
                    (SELECT COUNT(*) FROM jobs j WHERE j.tenant_id = t.id AND j.status='queued') AS queued_jobs,
                    -- Latest resource measurement (job-level preferred)
                    (SELECT rm.cpu_percent FROM resource_measurements rm
                     WHERE rm.tenant_id = t.id ORDER BY rm.timestamp DESC LIMIT 1) AS cpu_percent,
                    (SELECT rm.memory_percent FROM resource_measurements rm
                     WHERE rm.tenant_id = t.id ORDER BY rm.timestamp DESC LIMIT 1) AS memory_percent,
                    (SELECT rm.scope FROM resource_measurements rm
                     WHERE rm.tenant_id = t.id ORDER BY rm.timestamp DESC LIMIT 1) AS cpu_scope,
                    (SELECT rm.queue_depth FROM resource_measurements rm
                     WHERE rm.tenant_id = t.id ORDER BY rm.timestamp DESC LIMIT 1) AS queue_depth,
                    (SELECT rm.queue_wait_ms FROM resource_measurements rm
                     WHERE rm.tenant_id = t.id ORDER BY rm.timestamp DESC LIMIT 1) AS queue_wait_ms,
                    -- Quota violations (rejected requests = policy enforced)
                    (SELECT COUNT(*) FROM request_events re
                     WHERE re.tenant_id = t.id AND re.status='rejected' AND re.reason='rate_limit_exceeded') AS quota_violations,
                    -- Open incidents
                    (SELECT COUNT(*) FROM incidents i WHERE i.tenant_id = t.id AND i.status='open') AS open_incidents,
                    -- Active protection
                    (SELECT pa.action_type FROM protection_actions pa
                     WHERE pa.tenant_id = t.id AND pa.status='applied'
                     ORDER BY pa.applied_at DESC LIMIT 1) AS active_protection
                FROM tenants t
                JOIN companies c ON t.company_id = c.id
                LEFT JOIN tenant_quotas q ON q.tenant_id = t.id
                {where}
                ORDER BY c.name, t.name""",
            tuple(params),
        )
        rows = await cursor.fetchall()

        result = []
        for r in rows:
            rpm = r["requests_per_minute"] or 500
            accepted = r["accepted_count"] or 0
            rejected = r["rejected_count"] or 0
            # Estimate current RPM from total / hours available
            estimated_rpm = round((accepted + rejected) / max(1, 24 * 60), 1)
            quota_util = round(estimated_rpm / max(1, rpm) * 100, 1)
            cpu_budget_util = None
            if r["cpu_percent"] is not None and r["resource_budget_cpu"]:
                cpu_budget_util = round(r["cpu_percent"] / r["resource_budget_cpu"] * 100, 1)

            result.append(TenantComparisonRow(
                tenant_id=r["id"],
                tenant_name=r["name"],
                company_id=r["company_id"],
                company_name=r["company_name"],
                workload_type=r["workload_type"],
                status=r["status"],
                requests_per_minute=estimated_rpm,
                quota_rpm=rpm,
                quota_utilization_pct=quota_util,
                accepted_count=accepted,
                rejected_count=rejected,
                avg_latency_ms=round(r["avg_latency"] or 0, 2),
                p95_latency_ms=round(r["p95_latency"] or 0, 2),
                active_jobs=r["active_jobs"] or 0,
                queued_jobs=r["queued_jobs"] or 0,
                queue_depth=r["queue_depth"] or 0,
                queue_wait_ms=round(r["queue_wait_ms"] or 0, 1),
                max_concurrency=r["max_concurrency"] or 25,
                queue_limit=r["queue_limit"] or 100,
                resource_budget_cpu=r["resource_budget_cpu"] or 25.0,
                resource_budget_memory=r["resource_budget_memory"] or 25.0,
                cpu_percent=round(r["cpu_percent"], 1) if r["cpu_percent"] else None,
                memory_percent=round(r["memory_percent"], 1) if r["memory_percent"] else None,
                cpu_scope=r["cpu_scope"] or "not_measured",
                quota_violations=r["quota_violations"] or 0,
                resource_violations=0,  # set by controller in future
                active_protection=r["active_protection"],
                open_incidents=r["open_incidents"] or 0,
            ))
        return result
    finally:
        await db.close()


@router.get("/{company_id}", response_model=CompanyDetail)
async def get_company(company_id: str, auth: AuthContext = Depends(get_auth)):
    """Retrieve a company's details with aggregate metrics."""
    auth.assert_company_access(company_id)
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT c.*,
                   (SELECT COUNT(*) FROM tenants t WHERE t.company_id = c.id) AS tenant_count,
                   (SELECT COALESCE(SUM(q.resource_budget_cpu), 0) FROM tenant_quotas q
                    JOIN tenants t ON q.tenant_id = t.id WHERE t.company_id = c.id) AS total_cpu_budget,
                   (SELECT COALESCE(SUM(q.resource_budget_memory), 0) FROM tenant_quotas q
                    JOIN tenants t ON q.tenant_id = t.id WHERE t.company_id = c.id) AS total_mem_budget
               FROM companies c WHERE c.id = ?""",
            (company_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")

        cursor2 = await db.execute(
            """SELECT
                 COALESCE(SUM(q.requests_per_minute), 0) AS total_rpm,
                 (SELECT COUNT(*) FROM request_events re
                  JOIN tenants t2 ON re.tenant_id = t2.id
                  WHERE t2.company_id = ? AND re.status = 'accepted') AS total_accepted,
                 (SELECT COUNT(*) FROM request_events re
                  JOIN tenants t2 ON re.tenant_id = t2.id
                  WHERE t2.company_id = ? AND re.status = 'rejected') AS total_rejected,
                 (SELECT AVG(latency_ms) FROM request_events re
                  JOIN tenants t2 ON re.tenant_id = t2.id
                  WHERE t2.company_id = ? AND re.status = 'accepted') AS avg_latency,
                 (SELECT COUNT(*) FROM incidents i
                  JOIN tenants t3 ON i.tenant_id = t3.id
                  WHERE t3.company_id = ? AND i.status = 'open') AS active_incidents
               FROM tenants t
               LEFT JOIN tenant_quotas q ON q.tenant_id = t.id
               WHERE t.company_id = ?""",
            (company_id, company_id, company_id, company_id, company_id),
        )
        agg = await cursor2.fetchone()

        return CompanyDetail(
            id=row["id"], name=row["name"], slug=row["slug"],
            registered_at=row["registered_at"], status=row["status"],
            tenant_count=row["tenant_count"],
            total_requests_per_minute=int(agg["total_rpm"] or 0),
            total_accepted=agg["total_accepted"] or 0,
            total_rejected=agg["total_rejected"] or 0,
            avg_latency_ms=round(agg["avg_latency"] or 0, 2),
            active_incidents=agg["active_incidents"] or 0,
            total_cpu_budget=round(row["total_cpu_budget"] or 0, 1),
            total_mem_budget=round(row["total_mem_budget"] or 0, 1),
        )
    finally:
        await db.close()
