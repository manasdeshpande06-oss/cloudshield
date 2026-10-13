"""
CloudShield FairGuard — Audit Logging Router.

Records and exposes platform administrative events:
- Rate limit and quota adjustments
- Fairness contract updates
- Protection policy applications and rollbacks
- Simulator configuration and runs
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from auth import AuthContext, require_admin, get_auth
from database import get_db

router = APIRouter(prefix="/api/audit", tags=["Audit Log"])


class AuditLogOut(BaseModel):
    id: int
    actor: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Optional[dict[str, Any]] = None
    timestamp: str


async def record_audit_event(
    actor: str,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """Helper to log administrative actions into the audit_logs table."""
    now = datetime.now(timezone.utc).isoformat()
    detail_str = json.dumps(details) if details else None
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO audit_logs (actor, action, resource_type, resource_id, details, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (actor, action, resource_type, resource_id, detail_str, now),
        )
        await db.commit()
    finally:
        await db.close()


@router.get("", response_model=list[AuditLogOut])
async def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(require_admin),
):
    """List audit events. Platform administrators only."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?""",
            (limit,),
        )
        rows = await cursor.fetchall()

        events = []
        for r in rows:
            parsed_details = None
            if r["details"]:
                try:
                    parsed_details = json.loads(r["details"])
                except Exception:
                    parsed_details = {"raw": r["details"]}
            events.append(
                AuditLogOut(
                    id=r["id"],
                    actor=r["actor"],
                    action=r["action"],
                    resource_type=r["resource_type"],
                    resource_id=r["resource_id"],
                    details=parsed_details,
                    timestamp=r["timestamp"],
                )
            )
        return events
    finally:
        await db.close()
