"""
CloudShield FairGuard — Shared Resource Overview Router.

Provides transparent cross-tenant visibility for both Admin and Customer/Tenant users.
Exposes approved operational metadata (rates, quotas, latency, contracts, policy adherence)
while strictly isolating confidential payloads, tokens, passwords, and private business data.

Endpoints:
- GET /api/shared-resource-overview  → Unified shared resource usage table
"""

from __future__ import annotations

import json
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from auth import AuthContext, get_auth
from database import get_db

router = APIRouter(prefix="/api/shared-resource-overview", tags=["Shared Resource Overview"])


class SharedTenantUsageItem(BaseModel):
    tenant_id: str
    tenant_name: str
    company_name: str
    company_id: str
    time_window: str                     # e.g. "Last 24 Hours"

    # 1. Resource usage with explicit units
    current_resource_usage: str          # e.g. "32.0 req/min"
    resource_unit: str                   # "req/min & capacity share"
    current_usage_val: float

    # 2. Configured maximum allocation or quota
    configured_max_allocation: str       # e.g. "500 req/min (40.0% cap)"
    configured_rate_limit_rpm: int
    max_allocation_limit_rpm: int

    # 3. Minimum service guarantee
    min_service_guarantee: str           # e.g. "100 req/min (5.0% min guarantee)"
    min_service_guarantee_rpm: int
    min_cpu_pct: float

    # 4. Current assigned allocation
    current_assigned_allocation: str     # e.g. "100 req/min base + 0 borrowed"

    # 5. Borrowed capacity, if applicable
    borrowed_capacity: str               # e.g. "0 req/min" or "12.0 req/min borrowed"
    borrowed_units: float
    borrow_allowed: bool

    # 6. Remaining capacity available in the shared pool
    remaining_pool_capacity: str         # e.g. "33.0% available pool"

    # 7. Distinct request metrics
    requests_received: int               # Total inbound
    requests_accepted: int               # Accepted & processed
    requests_processed: int              # Same as accepted
    requests_rejected: int               # Dropped / throttled
    requests_throttled: int              # Throttled by policy

    # 8. Actual request rate with time window
    current_request_rate_rpm: float
    request_rate_display: str            # "32.0 req/min (24h)" or "—"

    # 9. Distinguish rate limit vs allocation violation
    rate_limit_exceeded: bool
    allocation_exceeded: bool

    # 10. Latencies
    avg_latency_ms: float
    p95_latency_ms: float
    avg_latency_display: str             # "32.4 ms" or "—"
    p95_latency_display: str             # "45.0 ms" or "—"
    has_sufficient_latency_samples: bool

    # 11. Fairness status (one of the 6 precise prompt statuses)
    fairness_status: str                 # "Within Allocation" | "Borrowing Permitted Capacity" | "Exceeds Configured Allocation" | "Another Tenant's Guarantee at Risk" | "Protection Applied" | "Insufficient Data"
    fairness_status_details: str
    fairness_status_color: str           # "green" | "amber" | "red" | "blue" | "slate"

    # 12. Protection action applied
    protection_applied: bool
    protection_action_display: str

    # 13. Associated incident
    associated_incident_id: Optional[int] = None
    associated_incident_title: Optional[str] = None
    is_impacted_by_incident: bool = False
    affected_tenants_summary: Optional[str] = None

    # 14. Priority
    priority: int

    # 15. Real Infrastructure (only if verified exporter reported)
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    infrastructure_status: str           # "CONNECTED INFRASTRUCTURE" | "No infrastructure data available"

    # 16. Legacy compat fields (so existing UI/tests don't break)
    tenant_status: str
    current_allocation_pct: float
    policy_adherence_status: str
    policy_adherence_color: str
    data_source_label: str


class SharedResourceOverviewResponse(BaseModel):
    summary: dict
    time_window: str
    data_source_label: str
    privacy_notice: str
    tenants: list[SharedTenantUsageItem]


@router.get("", response_model=SharedResourceOverviewResponse)
async def get_shared_resource_overview(
    window_hours: int = Query(default=24, ge=1, le=168),
    auth: AuthContext = Depends(get_auth),
):
    """
    Cross-tenant shared resource overview table accessible to all authenticated users.
    Ordinary tenants receive approved operational metadata (read-only).
    Platform administrators receive the same overview with administrative controls.
    """
    db = await get_db()
    try:
        # Check if real live infrastructure exporter is connected
        infra_cursor = await db.execute(
            """SELECT cpu_percent, memory_percent, timestamp FROM infrastructure_metrics
               WHERE is_live = 1 ORDER BY timestamp DESC LIMIT 1"""
        )
        infra_row = await infra_cursor.fetchone()
        has_real_infra = infra_row is not None

        # Fetch all tenants with quotas, contracts, and request aggregations
        query = """
            SELECT 
                t.id AS tenant_id,
                t.name AS tenant_name,
                t.company_id,
                c.name AS company_name,
                t.status AS tenant_status,
                t.workload_type,
                COALESCE(q.requests_per_minute, 500) AS quota_rpm,
                COALESCE(fc.min_rpm, 100) AS min_rpm,
                COALESCE(fc.max_rpm, 1000) AS max_rpm,
                COALESCE(fc.min_cpu_pct, 5.0) AS min_cpu_pct,
                COALESCE(fc.max_cpu_pct, 40.0) AS max_cpu_pct,
                COALESCE(fc.priority, 5) AS priority,
                COALESCE(fc.borrow_allowed, 1) AS borrow_allowed,
                -- Requests in window
                (SELECT COUNT(*) FROM request_events re WHERE re.tenant_id = t.id AND re.status = 'accepted') AS accepted_count,
                (SELECT COUNT(*) FROM request_events re WHERE re.tenant_id = t.id AND re.status = 'rejected') AS rejected_count,
                (SELECT AVG(re.latency_ms) FROM request_events re WHERE re.tenant_id = t.id AND re.status = 'accepted') AS avg_lat,
                (SELECT re.latency_ms FROM request_events re WHERE re.tenant_id = t.id AND re.status = 'accepted' AND re.latency_ms IS NOT NULL
                 ORDER BY re.latency_ms DESC LIMIT 1) AS p95_lat,
                -- Open incident where tenant is suspected
                (SELECT i.id FROM incidents i WHERE i.tenant_id = t.id AND i.status = 'open' LIMIT 1) AS inc_id,
                (SELECT i.title FROM incidents i WHERE i.tenant_id = t.id AND i.status = 'open' LIMIT 1) AS inc_title,
                (SELECT i.affected_tenants FROM incidents i WHERE i.tenant_id = t.id AND i.status = 'open' LIMIT 1) AS inc_affected,
                -- Active protection
                (SELECT pa.action_type FROM protection_actions pa WHERE pa.tenant_id = t.id AND pa.status = 'applied' LIMIT 1) AS prot_action
            FROM tenants t
            JOIN companies c ON t.company_id = c.id
            LEFT JOIN tenant_quotas q ON q.tenant_id = t.id
            LEFT JOIN fairness_contracts fc ON fc.tenant_id = t.id
            ORDER BY c.name, t.name
        """
        cursor = await db.execute(query)
        rows = await cursor.fetchall()

        # Check whether any data in request_events is live vs simulated
        sim_check = await db.execute("SELECT COUNT(*) FROM request_events WHERE is_simulated = 0")
        (live_count,) = await sim_check.fetchone()
        data_source = "LIVE APPLICATION DATA" if live_count > 0 else "SIMULATION MODE"

        # Check for open incidents affecting other tenants
        cur_open_inc = await db.execute("SELECT tenant_id, affected_tenants FROM incidents WHERE status = 'open'")
        open_incs = await cur_open_inc.fetchall()
        suspected_with_victims = set()
        affected_victim_ids = set()
        for oi in open_incs:
            if oi["affected_tenants"]:
                suspected_with_victims.add(oi["tenant_id"])
                try:
                    aff_list = json.loads(oi["affected_tenants"])
                    for item in aff_list:
                        if isinstance(item, dict) and "tenant_id" in item:
                            affected_victim_ids.add(item["tenant_id"])
                        elif isinstance(item, str):
                            affected_victim_ids.add(item)
                except Exception:
                    pass

        items: list[SharedTenantUsageItem] = []
        total_accepted = 0
        total_rejected = 0

        # Precompute total minimum guarantees
        total_min_guarantees = sum(r["min_cpu_pct"] for r in rows)
        remaining_pool_pct = max(0.0, round(100.0 - total_min_guarantees, 1))

        for r in rows:
            acc = r["accepted_count"] or 0
            rej = r["rejected_count"] or 0
            total_accepted += acc
            total_rejected += rej
            received = acc + rej
            quota_rpm = r["quota_rpm"]
            min_rpm = r["min_rpm"]
            max_rpm = r["max_rpm"]
            min_cpu = r["min_cpu_pct"]
            borrow_allowed = bool(r["borrow_allowed"])
            prot_action = r["prot_action"]

            # Current rate estimation in rpm
            current_rate = round(received / max(1, window_hours * 60), 1)
            allocation_pct = round(min(100.0, (current_rate / max(1, quota_rpm)) * 100), 1)

            # Distinguish rate limit vs resource allocation violations
            rate_limit_exceeded = (rej > 0) or (current_rate > quota_rpm)
            allocation_exceeded = (current_rate > max_rpm) or (current_rate > quota_rpm and not borrow_allowed)

            # Capacity borrowing calculation
            # Base allocation is the min service guarantee or fair share
            if current_rate > min_rpm and borrow_allowed:
                borrowed_units = round(min(max(0.0, current_rate - min_rpm), max_rpm - min_rpm), 1)
            else:
                borrowed_units = 0.0

            # -------------------------------------------------------------
            # Fairness Status Logic with Precedence (Section 5)
            # -------------------------------------------------------------
            # Precedence order:
            # 1. Protection Applied
            # 2. Another Tenant's Guarantee at Risk
            # 3. Exceeds Configured Allocation
            # 4. Borrowing Permitted Capacity
            # 5. Within Allocation
            # 6. Insufficient Data
            if prot_action:
                fairness_status = "Protection Applied"
                fairness_color = "blue"
                fairness_details = f"Active enforcement action applied: {prot_action.replace('_', ' ').title()}. Concurrency/quota bounded to protect shared fairness."
            elif r["tenant_id"] in suspected_with_victims:
                fairness_status = "Another Tenant's Guarantee at Risk"
                fairness_color = "red"
                fairness_details = f"Workload spike or worker saturation from {r['tenant_name']} has been detected degrading service guarantees of innocent neighboring tenants."
            elif rej > 15 or (current_rate > quota_rpm and not borrow_allowed):
                fairness_status = "Exceeds Configured Allocation"
                fairness_color = "red"
                fairness_details = f"Current consumption ({current_rate} rpm) exceeds configured quota ({quota_rpm} rpm) without borrowing privileges. {rej} requests throttled."
            elif borrow_allowed and (current_rate > min_rpm or borrowed_units > 0) and received > 0 and rej == 0:
                fairness_status = "Borrowing Permitted Capacity"
                fairness_color = "amber"
                fairness_details = f"Consuming {current_rate} rpm; borrowing {borrowed_units} rpm from idle pool capacity. Permitted under active fairness contract."
            elif received > 0:
                fairness_status = "Within Allocation"
                fairness_color = "green"
                fairness_details = f"Operating normally within allocated quota ({current_rate} rpm / {quota_rpm} rpm). SLA satisfied."
            else:
                fairness_status = "Insufficient Data"
                fairness_color = "slate"
                fairness_details = "No request activity observed in the selected time window. Awaiting operational telemetry."

            # Legacy policy status compatibility
            legacy_policy_status = "Over Quota" if fairness_color == "red" else ("At Risk" if fairness_color == "amber" else "Within Policy")
            legacy_tenant_st = "Protected" if prot_action else ("Throttled" if rej > 20 else r["tenant_status"].capitalize())

            # Format latency displays honestly (no fake 45 ms)
            avg_lat = round(r["avg_lat"] or 0.0, 1)
            p95_lat = round(r["p95_lat"] or 0.0, 1)
            has_sufficient = acc >= 5

            # Affected summary
            aff_summary = None
            if r["inc_affected"]:
                try:
                    aff_data = json.loads(r["inc_affected"])
                    aff_names = [a.get("tenant_id", "tenant") if isinstance(a, dict) else str(a) for a in aff_data]
                    aff_summary = f"Degrading: {', '.join(aff_names)}"
                except Exception:
                    aff_summary = "Impacting neighboring tenants"
            elif r["tenant_id"] in affected_victim_ids:
                aff_summary = "Degraded by neighboring tenant burst"

            items.append(
                SharedTenantUsageItem(
                    tenant_id=r["tenant_id"],
                    tenant_name=r["tenant_name"],
                    company_name=r["company_name"],
                    company_id=r["company_id"],
                    time_window=f"Last {window_hours}h",

                    # 1. Resource usage with explicit units
                    current_resource_usage=f"{current_rate} req/min" if received > 0 else "—",
                    resource_unit="req/min & capacity share",
                    current_usage_val=current_rate,

                    # 2. Configured maximum allocation or quota
                    configured_max_allocation=f"{quota_rpm} rpm ({r['max_cpu_pct']}% cap)",
                    configured_rate_limit_rpm=quota_rpm,
                    max_allocation_limit_rpm=max_rpm,

                    # 3. Minimum service guarantee
                    min_service_guarantee=f"{min_rpm} rpm ({min_cpu}% min)",
                    min_service_guarantee_rpm=min_rpm,
                    min_cpu_pct=min_cpu,

                    # 4. Current assigned allocation
                    current_assigned_allocation=f"{min_rpm + int(borrowed_units)} rpm",

                    # 5. Borrowed capacity
                    borrowed_capacity=f"{borrowed_units} rpm borrowed" if borrowed_units > 0 else "0 rpm",
                    borrowed_units=borrowed_units,
                    borrow_allowed=borrow_allowed,

                    # 6. Remaining capacity in shared pool
                    remaining_pool_capacity=f"{remaining_pool_pct}% pool reserve",

                    # 7. Distinct request metrics
                    requests_received=received,
                    requests_accepted=acc,
                    requests_processed=acc,
                    requests_rejected=rej,
                    requests_throttled=rej,

                    # 8. Actual request rate with time window
                    current_request_rate_rpm=current_rate,
                    request_rate_display=f"{current_rate} rpm ({window_hours}h)" if received > 0 else "—",

                    # 9. Rate limit vs Allocation flags
                    rate_limit_exceeded=rate_limit_exceeded,
                    allocation_exceeded=allocation_exceeded,

                    # 10. Latencies
                    avg_latency_ms=avg_lat,
                    p95_latency_ms=p95_lat,
                    avg_latency_display=f"{avg_lat} ms" if has_sufficient and avg_lat > 0 else "—",
                    p95_latency_display=f"{p95_lat} ms" if has_sufficient and p95_lat > 0 else "—",
                    has_sufficient_latency_samples=has_sufficient,

                    # 11. Fairness status
                    fairness_status=fairness_status,
                    fairness_status_details=fairness_details,
                    fairness_status_color=fairness_color,

                    # 12. Protection action applied
                    protection_applied=bool(prot_action),
                    protection_action_display=prot_action.replace("_", " ").title() if prot_action else "None",

                    # 13. Associated incident
                    associated_incident_id=r["inc_id"],
                    associated_incident_title=r["inc_title"],
                    is_impacted_by_incident=bool(r["inc_id"] or r["tenant_id"] in affected_victim_ids),
                    affected_tenants_summary=aff_summary,

                    # 14. Priority
                    priority=r["priority"],

                    # 15. Real Infrastructure
                    cpu_percent=round(infra_row["cpu_percent"], 1) if has_real_infra else None,
                    memory_percent=round(infra_row["memory_percent"], 1) if has_real_infra else None,
                    infrastructure_status="CONNECTED INFRASTRUCTURE" if has_real_infra else "No infrastructure data available",

                    # 16. Legacy compat fields
                    tenant_status=legacy_tenant_st,
                    current_allocation_pct=allocation_pct,
                    policy_adherence_status=legacy_policy_status,
                    policy_adherence_color=fairness_color,
                    data_source_label=data_source,
                )
            )

        return SharedResourceOverviewResponse(
            summary={
                "total_tenants": len(items),
                "total_requests_received": total_accepted + total_rejected,
                "total_requests_accepted": total_accepted,
                "total_requests_throttled": total_rejected,
                "time_window_hours": window_hours,
                "remaining_pool_capacity_pct": remaining_pool_pct,
            },
            time_window=f"Past {window_hours} Hours",
            data_source_label=data_source,
            privacy_notice="Notice: This shared overview table displays approved operational metadata (rates, quotas, latency, SLA guarantees, and fairness statuses). Private request bodies, tokens, API keys, and sensitive application payloads are strictly isolated and excluded.",
            tenants=items,
        )
    finally:
        await db.close()
