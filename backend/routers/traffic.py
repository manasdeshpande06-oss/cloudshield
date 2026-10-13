"""Traffic, security events, and resource metrics router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth import AuthContext, get_auth
from database import get_db
from models import (
    RequestEventOut,
    ResourceMeasurementOut,
    SecurityEventOut,
    TrafficBucket,
)

router = APIRouter(prefix="/api", tags=["Traffic & Monitoring"])


async def _assert_tenant_access(db, tenant_id: str, auth: AuthContext):
    cursor = await db.execute("SELECT company_id FROM tenants WHERE id = ?", (tenant_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    auth.assert_tenant_access_by_company(row["company_id"])


@router.get("/tenants/{tenant_id}/traffic", response_model=list[TrafficBucket])
async def get_tenant_traffic(
    tenant_id: str,
    limit: int = Query(default=24, ge=1, le=168),
    auth: AuthContext = Depends(get_auth),
):
    """Retrieve hourly traffic buckets for a tenant."""
    db = await get_db()
    try:
        await _assert_tenant_access(db, tenant_id, auth)

        cursor = await db.execute(
            """SELECT
                 strftime('%Y-%m-%dT%H:00:00', timestamp) AS bucket,
                 COUNT(*) FILTER (WHERE status = 'accepted') AS accepted,
                 COUNT(*) FILTER (WHERE status = 'rejected') AS rejected
               FROM request_events
               WHERE tenant_id = ?
               GROUP BY bucket
               ORDER BY bucket DESC
               LIMIT ?""",
            (tenant_id, limit),
        )
        rows = await cursor.fetchall()
        return [
            TrafficBucket(time=r["bucket"], accepted=r["accepted"], rejected=r["rejected"])
            for r in reversed(rows)
        ]
    finally:
        await db.close()


@router.get("/tenants/{tenant_id}/request-events", response_model=list[RequestEventOut])
async def get_request_events(
    tenant_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    status_filter: str | None = Query(default=None, alias="status"),
    auth: AuthContext = Depends(get_auth),
):
    """Retrieve recent request events for a tenant."""
    db = await get_db()
    try:
        await _assert_tenant_access(db, tenant_id, auth)

        query = "SELECT * FROM request_events WHERE tenant_id = ?"
        params: list = [tenant_id]
        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [
            RequestEventOut(
                id=r["id"], tenant_id=r["tenant_id"], timestamp=r["timestamp"],
                status=r["status"], latency_ms=r["latency_ms"],
                reason=r["reason"], is_simulated=bool(r["is_simulated"]),
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.get("/tenants/{tenant_id}/security-events", response_model=list[SecurityEventOut])
async def get_security_events(
    tenant_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    auth: AuthContext = Depends(get_auth),
):
    """Retrieve security events scoped to a tenant."""
    db = await get_db()
    try:
        await _assert_tenant_access(db, tenant_id, auth)

        cursor = await db.execute(
            "SELECT * FROM security_events WHERE tenant_id = ? ORDER BY timestamp DESC LIMIT ?",
            (tenant_id, limit),
        )
        rows = await cursor.fetchall()
        return [
            SecurityEventOut(
                id=r["id"], tenant_id=r["tenant_id"], timestamp=r["timestamp"],
                event_type=r["event_type"], severity=r["severity"],
                description=r["description"], is_simulated=bool(r["is_simulated"]),
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.get("/security-events", response_model=list[SecurityEventOut])
async def list_all_security_events(
    limit: int = Query(default=50, ge=1, le=500),
    auth: AuthContext = Depends(get_auth),
):
    """Retrieve all security events (admin only or company-scoped)."""
    db = await get_db()
    try:
        if auth.company_filter():
            cursor = await db.execute(
                """SELECT se.* FROM security_events se
                   JOIN tenants t ON se.tenant_id = t.id
                   WHERE t.company_id = ?
                   ORDER BY se.timestamp DESC LIMIT ?""",
                (auth.company_filter(), limit),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM security_events ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [
            SecurityEventOut(
                id=r["id"], tenant_id=r["tenant_id"], timestamp=r["timestamp"],
                event_type=r["event_type"], severity=r["severity"],
                description=r["description"], is_simulated=bool(r["is_simulated"]),
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.get("/tenants/{tenant_id}/resources", response_model=list[ResourceMeasurementOut])
async def get_resource_measurements(
    tenant_id: str,
    limit: int = Query(default=24, ge=1, le=168),
    auth: AuthContext = Depends(get_auth),
):
    """Retrieve resource measurements (tenant-scoped or platform-wide)."""
    db = await get_db()
    try:
        await _assert_tenant_access(db, tenant_id, auth)

        # Include both tenant-specific and platform-wide (tenant_id IS NULL) measurements
        cursor = await db.execute(
            """SELECT * FROM resource_measurements
               WHERE tenant_id = ? OR tenant_id IS NULL
               ORDER BY timestamp DESC LIMIT ?""",
            (tenant_id, limit),
        )
        rows = await cursor.fetchall()
        return [
            ResourceMeasurementOut(
                id=r["id"], tenant_id=r["tenant_id"], timestamp=r["timestamp"],
                cpu_percent=r["cpu_percent"], memory_percent=r["memory_percent"],
                queue_depth=r["queue_depth"], is_simulated=bool(r["is_simulated"]),
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.get("/resources", response_model=list[ResourceMeasurementOut])
async def list_all_resources(
    limit: int = Query(default=24, ge=1, le=168),
    auth: AuthContext = Depends(get_auth),
):
    """Retrieve all platform resource measurements."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM resource_measurements ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [
            ResourceMeasurementOut(
                id=r["id"], tenant_id=r["tenant_id"], timestamp=r["timestamp"],
                cpu_percent=r["cpu_percent"], memory_percent=r["memory_percent"],
                queue_depth=r["queue_depth"], is_simulated=bool(r["is_simulated"]),
            )
            for r in rows
        ]
    finally:
        await db.close()
