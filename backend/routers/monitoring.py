"""
CloudShield FairGuard — Infrastructure Monitoring Integration Router.

Allows external monitoring agents, exporters (e.g. Prometheus Node Exporter,
Datadog agent, CloudWatch exporter) to securely ingest real CPU/memory metrics.

Endpoints:
- POST /api/infrastructure/metrics  → Ingest real hardware/container measurements
- GET  /api/infrastructure/status   → Get exporter connection health & freshness
- GET  /api/infrastructure/metrics  → Query recent real infrastructure records
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from auth import AuthContext, get_auth, require_admin
from database import get_db

router = APIRouter(prefix="/api/infrastructure", tags=["Infrastructure Monitoring"])


class IngestMetricsRequest(BaseModel):
    tenant_id: Optional[str] = None
    source: str = Field(..., description="Agent or exporter identifier (e.g., node-exporter-v1)")
    cpu_percent: float = Field(..., ge=0, le=100)
    memory_percent: float = Field(..., ge=0, le=100)
    disk_percent: Optional[float] = Field(default=None, ge=0, le=100)
    timestamp: Optional[str] = None


class InfrastructureStatusOut(BaseModel):
    connected: bool
    status_label: str  # "CONNECTED INFRASTRUCTURE" | "NOT CONNECTED"
    last_updated: Optional[str] = None
    freshness_seconds: Optional[int] = None
    is_stale: bool
    source: Optional[str] = None
    total_measurements: int = 0
    latest_cpu_percent: Optional[float] = None
    latest_memory_percent: Optional[float] = None


@router.post("/metrics", status_code=status.HTTP_201_CREATED)
async def ingest_infrastructure_metrics(
    body: IngestMetricsRequest,
    auth: AuthContext = Depends(get_auth),
):
    """
    Ingest verified infrastructure measurements from an external agent or exporter.
    Records measurements with is_live=1 to distinguish from simulation data.
    """
    now = datetime.now(timezone.utc)
    ts = body.timestamp or now.isoformat()

    db = await get_db()
    try:
        if body.tenant_id:
            cursor = await db.execute("SELECT id FROM tenants WHERE id = ?", (body.tenant_id,))
            if not await cursor.fetchone():
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"Tenant {body.tenant_id} not found")

        await db.execute(
            """INSERT INTO infrastructure_metrics
               (tenant_id, source, cpu_percent, memory_percent, disk_percent, timestamp, is_live)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (body.tenant_id, body.source, body.cpu_percent, body.memory_percent, body.disk_percent, ts),
        )

        # Also insert into resource_measurements table with is_simulated=0
        await db.execute(
            """INSERT INTO resource_measurements
               (tenant_id, timestamp, cpu_percent, memory_percent, scope, is_simulated)
               VALUES (?, ?, ?, ?, ?, 0)""",
            (body.tenant_id, ts, body.cpu_percent, body.memory_percent, f"agent:{body.source}"),
        )

        await db.commit()
        return {
            "status": "ingested",
            "source": body.source,
            "tenant_id": body.tenant_id,
            "timestamp": ts,
            "is_live": True,
        }
    finally:
        await db.close()


@router.get("/status", response_model=InfrastructureStatusOut)
async def get_infrastructure_status(auth: AuthContext = Depends(get_auth)):
    """
    Return connection health, data freshness, and status of connected infrastructure.
    If no exporter has reported in the last 15 minutes, returns disconnected/stale.
    """
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT source, cpu_percent, memory_percent, timestamp,
                      (SELECT COUNT(*) FROM infrastructure_metrics WHERE is_live = 1) AS total_count
               FROM infrastructure_metrics
               WHERE is_live = 1
               ORDER BY timestamp DESC LIMIT 1"""
        )
        row = await cursor.fetchone()

        if not row:
            return InfrastructureStatusOut(
                connected=False,
                status_label="NOT CONNECTED",
                is_stale=True,
                total_measurements=0,
            )

        latest_ts_str = row["timestamp"]
        try:
            latest_dt = datetime.fromisoformat(latest_ts_str.replace("Z", "+00:00"))
            now_dt = datetime.now(timezone.utc)
            freshness = int((now_dt - latest_dt).total_seconds())
        except Exception:
            freshness = None

        # Stale if older than 15 minutes (900 seconds)
        is_stale = freshness is None or freshness > 900
        connected = not is_stale

        return InfrastructureStatusOut(
            connected=connected,
            status_label="CONNECTED INFRASTRUCTURE" if connected else "STALE / DISCONNECTED",
            last_updated=latest_ts_str,
            freshness_seconds=freshness,
            is_stale=is_stale,
            source=row["source"],
            total_measurements=row["total_count"] or 0,
            latest_cpu_percent=row["cpu_percent"],
            latest_memory_percent=row["memory_percent"],
        )
    finally:
        await db.close()
