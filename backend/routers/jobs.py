"""
Jobs router — list job history for a tenant.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth import AuthContext, get_auth
from database import get_db
from models import JobOut

router = APIRouter(prefix="/api", tags=["Jobs"])


async def _assert_tenant_access(db, tenant_id: str, auth: AuthContext):
    cursor = await db.execute("SELECT company_id FROM tenants WHERE id = ?", (tenant_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    auth.assert_tenant_access_by_company(row["company_id"])


@router.get("/tenants/{tenant_id}/jobs", response_model=list[JobOut])
async def list_jobs(
    tenant_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    auth: AuthContext = Depends(get_auth),
):
    """List recent jobs for a tenant, ordered by created_at descending."""
    db = await get_db()
    try:
        await _assert_tenant_access(db, tenant_id, auth)
        cursor = await db.execute(
            """SELECT * FROM jobs WHERE tenant_id = ? ORDER BY created_at DESC LIMIT ?""",
            (tenant_id, limit),
        )
        rows = await cursor.fetchall()
        return [
            JobOut(
                id=r["id"], tenant_id=r["tenant_id"], status=r["status"],
                created_at=r["created_at"], started_at=r["started_at"],
                completed_at=r["completed_at"], duration_ms=r["duration_ms"],
                worker_id=r["worker_id"],
            )
            for r in rows
        ]
    finally:
        await db.close()
