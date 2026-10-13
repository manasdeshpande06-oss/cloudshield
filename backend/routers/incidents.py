"""Incidents, protection actions, and controller log router."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth import AuthContext, get_auth
from database import get_db
from models import (
    ControllerLogOut,
    IncidentOut,
    AffectedTenantInfo,
    FairnessReceipt,
    ProtectionActionOut,
    ProtectionActionRequest,
    RollbackRequest,
)

router = APIRouter(prefix="/api", tags=["Incidents & Protection"])



def _parse_incident(r) -> IncidentOut:
    affected_raw = r["affected_tenants"]
    affected = None
    if affected_raw:
        try:
            data = json.loads(affected_raw)
            affected = [AffectedTenantInfo(**a) for a in data]
        except Exception:
            affected = None

    return IncidentOut(
        id=r["id"], tenant_id=r["tenant_id"],
        tenant_name=r["tenant_name"], company_name=r["company_name"],
        title=r["title"], description=r["description"],
        severity=r["severity"], status=r["status"],
        detected_at=r["detected_at"], resolved_at=r["resolved_at"],
        evidence=json.loads(r["evidence"]) if r["evidence"] else None,
        affected_tenants=affected,
        detection_rules=json.loads(r["detection_rules"]) if r["detection_rules"] else None,
        baseline_metrics=json.loads(r["baseline_metrics"]) if r["baseline_metrics"] else None,
        observed_metrics=json.loads(r["observed_metrics"]) if r["observed_metrics"] else None,
        is_simulated=bool(r["is_simulated"]),
    )


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

@router.get("/incidents", response_model=list[IncidentOut])
async def list_incidents(
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(get_auth),
):
    """List noisy-neighbor incidents with supporting evidence."""
    db = await get_db()
    try:
        base = """
            SELECT i.*, t.name AS tenant_name, c.name AS company_name
            FROM incidents i
            JOIN tenants t ON i.tenant_id = t.id
            JOIN companies c ON t.company_id = c.id
        """
        conditions = []
        params: list = []

        if auth.company_filter():
            # Match if tenant is suspected OR if tenant is listed in affected_tenants
            cur_t = await db.execute("SELECT id FROM tenants WHERE company_id = ?", (auth.company_filter(),))
            my_tids = [row[0] for row in await cur_t.fetchall()]
            if my_tids:
                or_terms = ["t.company_id = ?"]
                params.append(auth.company_filter())
                for tid in my_tids:
                    or_terms.append("i.affected_tenants LIKE ?")
                    params.append(f'%"{tid}"%')
                conditions.append(f"({' OR '.join(or_terms)})")
            else:
                conditions.append("t.company_id = ?")
                params.append(auth.company_filter())
        if status_filter:
            conditions.append("i.status = ?")
            params.append(status_filter)
        if severity:
            conditions.append("i.severity = ?")
            params.append(severity)

        if conditions:
            base += " WHERE " + " AND ".join(conditions)
        base += " ORDER BY i.detected_at DESC LIMIT ?"
        params.append(limit)

        cursor = await db.execute(base, params)
        rows = await cursor.fetchall()
        return [_parse_incident(r) for r in rows]
    finally:
        await db.close()


@router.get("/incidents/{incident_id}", response_model=IncidentOut)
async def get_incident(incident_id: int, auth: AuthContext = Depends(get_auth)):
    """Retrieve a single incident with full evidence, affected tenants, and actions."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT i.*, t.name AS tenant_name, c.name AS company_name
               FROM incidents i
               JOIN tenants t ON i.tenant_id = t.id
               JOIN companies c ON t.company_id = c.id
               WHERE i.id = ?""",
            (incident_id,),
        )
        r = await cursor.fetchone()
        if not r:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")

        cursor0 = await db.execute(
            "SELECT company_id FROM tenants WHERE id = ?", (r["tenant_id"],)
        )
        row0 = await cursor0.fetchone()
        
        # Check authorization: admin, suspected company, or affected tenant company
        if not auth.is_admin and auth.company_id != row0["company_id"]:
            aff_raw = r["affected_tenants"] or ""
            has_aff_access = False
            cur_my_t = await db.execute("SELECT id FROM tenants WHERE company_id = ?", (auth.company_id,))
            my_tids = [row[0] for row in await cur_my_t.fetchall()]
            for tid in my_tids:
                if tid in aff_raw:
                    has_aff_access = True
                    break
            if not has_aff_access:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized to access this incident")

        return _parse_incident(r)
    finally:
        await db.close()


@router.post("/incidents/{incident_id}/resolve", response_model=IncidentOut)
async def resolve_incident(incident_id: int, auth: AuthContext = Depends(get_auth)):
    """Mark an incident as resolved."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT i.*, t.name AS tenant_name, c.name AS company_name FROM incidents i JOIN tenants t ON i.tenant_id = t.id JOIN companies c ON t.company_id = c.id WHERE i.id = ?",
            (incident_id,),
        )
        r = await cursor.fetchone()
        if not r:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
        cursor0 = await db.execute("SELECT company_id FROM tenants WHERE id = ?", (r["tenant_id"],))
        row0 = await cursor0.fetchone()
        auth.assert_tenant_access_by_company(row0["company_id"])

        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "UPDATE incidents SET status='resolved', resolved_at=? WHERE id=?",
            (now, incident_id),
        )
        await db.commit()
        # Refresh row
        cursor2 = await db.execute(
            "SELECT i.*, t.name AS tenant_name, c.name AS company_name FROM incidents i JOIN tenants t ON i.tenant_id = t.id JOIN companies c ON t.company_id = c.id WHERE i.id = ?",
            (incident_id,),
        )
        r2 = await cursor2.fetchone()
        return _parse_incident(r2)
    finally:
        await db.close()


@router.get("/incidents/{incident_id}/receipt", response_model=FairnessReceipt)
async def get_incident_receipt(incident_id: int, auth: AuthContext = Depends(get_auth)):
    """
    Generate an authoritative, explainable Fairness Receipt for an incident.
    Summarizes what happened, observed impact, causal assessment, actions taken,
    and before/after recovery measurements.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT i.*, t.name AS tenant_name, c.name AS company_name
               FROM incidents i
               JOIN tenants t ON i.tenant_id = t.id
               JOIN companies c ON t.company_id = c.id
               WHERE i.id = ?""",
            (incident_id,),
        )
        r = await cursor.fetchone()
        if not r:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")

        # Parse evidence, affected tenants, rules, baselines, observed metrics
        evidence = json.loads(r["evidence"]) if r["evidence"] else {}
        affected_tenants = json.loads(r["affected_tenants"]) if r["affected_tenants"] else []
        detection_rules = json.loads(r["detection_rules"]) if r["detection_rules"] else []
        baseline_m = json.loads(r["baseline_metrics"]) if r["baseline_metrics"] else {}
        observed_m = json.loads(r["observed_metrics"]) if r["observed_metrics"] else {}

        # Fetch protection action
        cursor_pa = await db.execute(
            "SELECT * FROM protection_actions WHERE incident_id = ? ORDER BY applied_at DESC LIMIT 1",
            (incident_id,),
        )
        pa_row = await cursor_pa.fetchone()
        action_dict = None
        recovery_status = "not_yet_measured"
        after_m = None

        if pa_row:
            action_params = json.loads(pa_row["parameters"]) if pa_row["parameters"] else {}
            has_res = "result_metrics" in pa_row.keys() and pa_row["result_metrics"]
            res_metrics = json.loads(pa_row["result_metrics"]) if has_res else None
            action_dict = {
                "action_type": pa_row["action_type"],
                "status": pa_row["status"],
                "applied_at": pa_row["applied_at"],
                "parameters": action_params,
                "outcome": pa_row["outcome"] if "outcome" in pa_row.keys() else None,
            }

            if res_metrics:
                after_m = res_metrics
                recovery_status = "measured_recovered"
            elif pa_row["status"] == "applied":
                recovery_status = "measuring_in_progress"

        # Determine causal classification based strictly on evidence
        # Observed vs Suspected cause vs Confirmed cause vs Cause undetermined
        if evidence.get("confirmed") or evidence.get("experiment_validated"):
            classification = "Confirmed cause"
        elif evidence.get("evidence_score", 0) >= 5 or "strong signal" in str(evidence.get("evidence_strength", "")).lower():
            classification = "Suspected cause"
        elif affected_tenants or detection_rules:
            classification = "Observed"
        else:
            classification = "Cause undetermined"

        # Format evidence signals
        signals = []
        if evidence.get("cpu_percent"):
            signals.append(f"CPU pressure sustained at {evidence['cpu_percent']}% across measurement windows")
        if evidence.get("p95_latency_increase_ms"):
            signals.append(f"Cross-tenant p95 latency elevation of +{evidence['p95_latency_increase_ms']}ms detected")
        if evidence.get("queue_depth_increase"):
            signals.append(f"Shared worker queue depth increased by +{evidence['queue_depth_increase']} items")
        if evidence.get("active_jobs"):
            signals.append(f"{evidence['active_jobs']} concurrent compute-heavy jobs were active on shared workers")
        for rule in detection_rules:
            signals.append(f"Triggered detection heuristic: {rule.replace('_', ' ').capitalize()}")

        summary = (
            f"At {r['detected_at'][:19]}, FairGuard observed contention on shared workers. "
            f"{r['tenant_name']} ({r['company_name']}) was identified as a {classification.lower()}. "
            f"{len(affected_tenants)} neighboring tenant(s) experienced elevated latency. "
        )
        if action_dict:
            summary += f"Platform applied {action_dict['action_type']} protection. "
            if recovery_status == "measured_recovered":
                summary += "Follow-up verification confirmed performance recovery."
            else:
                summary += "Post-action recovery is currently being monitored."
        else:
            summary += "No automated mitigation has been applied yet."

        return FairnessReceipt(
            incident_id=incident_id,
            title=r["title"],
            detected_at=r["detected_at"],
            cause_classification=classification,
            observed_workload_pattern=r["description"] or "Unusual request or compute burst",
            suspected_tenant_id=r["tenant_id"],
            suspected_tenant_name=r["tenant_name"],
            suspected_company_name=r["company_name"],
            affected_tenants=affected_tenants,
            evidence_signals=signals,
            confidence_level=evidence.get("evidence_strength", "Standard correlation"),
            policy_action_taken=action_dict,
            before_metrics=baseline_m if baseline_m else observed_m,
            after_metrics=after_m,
            recovery_status=recovery_status,
            data_source_label="SIMULATION MODE" if r["is_simulated"] == 1 else "LIVE APPLICATION DATA",
            summary_text=summary,
        )
    finally:
        await db.close()



# ---------------------------------------------------------------------------
# Protection actions
# ---------------------------------------------------------------------------

@router.get("/protection-actions", response_model=list[ProtectionActionOut])
async def list_protection_actions(
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(get_auth),
):
    """List protection actions, optionally filtered by tenant."""
    db = await get_db()
    try:
        if tenant_id:
            cursor0 = await db.execute("SELECT company_id FROM tenants WHERE id = ?", (tenant_id,))
            row0 = await cursor0.fetchone()
            if not row0:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
            auth.assert_tenant_access_by_company(row0["company_id"])
            cursor = await db.execute(
                "SELECT * FROM protection_actions WHERE tenant_id = ? ORDER BY applied_at DESC LIMIT ?",
                (tenant_id, limit),
            )
        elif auth.company_filter():
            cursor = await db.execute(
                """SELECT pa.* FROM protection_actions pa
                   JOIN tenants t ON pa.tenant_id = t.id
                   WHERE t.company_id = ? ORDER BY pa.applied_at DESC LIMIT ?""",
                (auth.company_filter(), limit),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM protection_actions ORDER BY applied_at DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [
            ProtectionActionOut(
                id=r["id"], incident_id=r["incident_id"], tenant_id=r["tenant_id"],
                action_type=r["action_type"],
                parameters=json.loads(r["parameters"]) if r["parameters"] else None,
                applied_at=r["applied_at"], rolled_back_at=r["rolled_back_at"],
                expires_at=r["expires_at"] if "expires_at" in r.keys() else None,
                result_metrics=json.loads(r["result_metrics"]) if r.get("result_metrics") else None,
                outcome=r["outcome"] if "outcome" in r.keys() else None,
                status=r["status"],
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.post("/protection/apply", response_model=ProtectionActionOut)
async def apply_protection(body: ProtectionActionRequest, auth: AuthContext = Depends(get_auth)):
    """Apply a bounded concurrency-control or rate-limit action to a tenant."""
    db = await get_db()
    try:
        cursor0 = await db.execute("SELECT company_id FROM tenants WHERE id = ?", (body.tenant_id,))
        row0 = await cursor0.fetchone()
        if not row0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
        auth.assert_tenant_access_by_company(row0["company_id"])

        now = datetime.now(timezone.utc)
        expires = now + __import__("datetime").timedelta(minutes=body.duration_minutes)

        # Apply the action
        if body.action_type == "concurrency_reduction":
            pct = body.parameters.get("reduction_percent", 25)
            cursor_q = await db.execute("SELECT * FROM tenant_quotas WHERE tenant_id = ?", (body.tenant_id,))
            quota = await cursor_q.fetchone()
            if quota:
                original = quota["max_concurrency"]
                new_conc = max(1, int(original * (1 - pct / 100)))
                await db.execute(
                    "UPDATE tenant_quotas SET max_concurrency = ?, updated_at = ? WHERE tenant_id = ?",
                    (new_conc, now.isoformat(), body.tenant_id),
                )
                body.parameters["original_concurrency"] = original
                body.parameters["new_concurrency"] = new_conc
                body.parameters["auto_applied"] = False

        elif body.action_type == "rate_limit_override":
            new_rpm = body.parameters.get("new_rpm")
            if new_rpm and isinstance(new_rpm, int):
                cursor_q = await db.execute("SELECT * FROM tenant_quotas WHERE tenant_id = ?", (body.tenant_id,))
                quota = await cursor_q.fetchone()
                if quota:
                    body.parameters["original_rpm"] = quota["requests_per_minute"]
                    await db.execute(
                        "UPDATE tenant_quotas SET requests_per_minute = ?, updated_at = ? WHERE tenant_id = ?",
                        (new_rpm, now.isoformat(), body.tenant_id),
                    )

        elif body.action_type == "defer_background":
            # Defer: set status to "deferred" on queued background jobs
            await db.execute(
                "UPDATE jobs SET status='deferred' WHERE tenant_id = ? AND status='queued' AND job_type IN ('batch_export','etl_job','report_gen','batch_inference')",
                (body.tenant_id,),
            )

        # Update tenant status
        await db.execute("UPDATE tenants SET status = 'protected' WHERE id = ?", (body.tenant_id,))

        cursor = await db.execute(
            """INSERT INTO protection_actions
               (incident_id, tenant_id, action_type, parameters, applied_at, expires_at, status, outcome)
               VALUES (?,?,?,?,?,?,?,?)""",
            (body.incident_id, body.tenant_id, body.action_type,
             json.dumps(body.parameters), now.isoformat(), expires.isoformat(),
             "applied", "pending_measurement"),
        )
        action_id = cursor.lastrowid

        await db.execute(
            """INSERT INTO security_events (tenant_id, timestamp, event_type, severity, description, is_simulated)
               VALUES (?,?,?,?,?,?)""",
            (body.tenant_id, now.isoformat(), f"protection_{body.action_type}",
             "warning", f"Protection action applied: {body.action_type}", 0),
        )
        await db.commit()

        return ProtectionActionOut(
            id=action_id, incident_id=body.incident_id,
            tenant_id=body.tenant_id, action_type=body.action_type,
            parameters=body.parameters, applied_at=now.isoformat(),
            expires_at=expires.isoformat(),
            rolled_back_at=None, outcome="pending_measurement", status="applied",
        )
    finally:
        await db.close()


@router.post("/protection/rollback", response_model=ProtectionActionOut)
async def rollback_protection(body: RollbackRequest, auth: AuthContext = Depends(get_auth)):
    """Roll back a previously applied protection action."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM protection_actions WHERE id = ?", (body.action_id,))
        action = await cursor.fetchone()
        if not action:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Action not found")
        if action["status"] != "applied":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Cannot roll back action in status '{action['status']}'",
            )

        cursor0 = await db.execute("SELECT company_id FROM tenants WHERE id = ?", (action["tenant_id"],))
        row0 = await cursor0.fetchone()
        auth.assert_tenant_access_by_company(row0["company_id"])

        now = datetime.now(timezone.utc).isoformat()
        params = json.loads(action["parameters"]) if action["parameters"] else {}

        if action["action_type"] == "concurrency_reduction":
            original = params.get("original_concurrency")
            if original:
                await db.execute(
                    "UPDATE tenant_quotas SET max_concurrency = ?, updated_at = ? WHERE tenant_id = ?",
                    (original, now, action["tenant_id"]),
                )
        elif action["action_type"] == "rate_limit_override":
            original_rpm = params.get("original_rpm")
            if original_rpm:
                await db.execute(
                    "UPDATE tenant_quotas SET requests_per_minute = ?, updated_at = ? WHERE tenant_id = ?",
                    (original_rpm, now, action["tenant_id"]),
                )
        elif action["action_type"] == "defer_background":
            # Re-queue deferred jobs
            await db.execute(
                "UPDATE jobs SET status='queued' WHERE tenant_id = ? AND status='deferred'",
                (action["tenant_id"],),
            )

        await db.execute("UPDATE tenants SET status = 'healthy' WHERE id = ?", (action["tenant_id"],))
        await db.execute(
            "UPDATE protection_actions SET status = 'rolled_back', rolled_back_at = ?, outcome = 'rolled_back' WHERE id = ?",
            (now, body.action_id),
        )
        await db.execute(
            """INSERT INTO security_events (tenant_id, timestamp, event_type, severity, description, is_simulated)
               VALUES (?,?,?,?,?,?)""",
            (action["tenant_id"], now, f"rollback_{action['action_type']}",
             "info", f"Protection action rolled back: {action['action_type']}", 0),
        )
        await db.commit()

        return ProtectionActionOut(
            id=body.action_id, incident_id=action["incident_id"],
            tenant_id=action["tenant_id"], action_type=action["action_type"],
            parameters=params, applied_at=action["applied_at"],
            rolled_back_at=now, outcome="rolled_back", status="rolled_back",
        )
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Controller log
# ---------------------------------------------------------------------------

@router.get("/controller/log", response_model=list[ControllerLogOut])
async def get_controller_log(
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(get_auth),
):
    """Return the adaptive resource controller audit log."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM controller_log ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [
            ControllerLogOut(
                id=r["id"], timestamp=r["timestamp"],
                level=r["level"], event=r["event"],
                tenant_id=r["tenant_id"], detail=r["detail"],
            )
            for r in rows
        ]
    finally:
        await db.close()
