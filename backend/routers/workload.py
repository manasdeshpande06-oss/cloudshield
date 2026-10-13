"""Workload router — receive requests, enforce rate limits, record events."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from database import get_db
from models import WorkloadRequest, WorkloadResponse
from rate_limiter import limiter

router = APIRouter(prefix="/api/workload", tags=["Workload"])


@router.post("/request", response_model=WorkloadResponse)
async def submit_workload_request(body: WorkloadRequest):
    """Receive a workload request, identify the tenant via demo credentials,
    enforce the sliding-window rate limit, and record the outcome.

    Returns HTTP 429 when the tenant's quota is exceeded.
    """
    db = await get_db()
    try:
        # 1. Verify tenant exists
        cursor = await db.execute(
            "SELECT t.id, t.company_id FROM tenants t WHERE t.id = ?",
            (body.tenant_id,),
        )
        tenant_row = await cursor.fetchone()
        if not tenant_row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")

        # 2. Verify API key belongs to the tenant's company
        cursor2 = await db.execute(
            "SELECT id FROM companies WHERE api_key = ? AND id = ?",
            (body.api_key, tenant_row["company_id"]),
        )
        company_row = await cursor2.fetchone()
        if not company_row:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key for this tenant")

        # 3. Fetch quota
        cursor3 = await db.execute(
            "SELECT * FROM tenant_quotas WHERE tenant_id = ?",
            (body.tenant_id,),
        )
        quota_row = await cursor3.fetchone()
        max_rpm = quota_row["requests_per_minute"] if quota_row else 500
        window_sec = quota_row["window_seconds"] if quota_row else 60

        # 4. Check rate limit
        now = datetime.now(timezone.utc)
        start = time.perf_counter()
        allowed, retry_after = limiter.allow(body.tenant_id, max_rpm, window_sec)
        latency_ms = (time.perf_counter() - start) * 1000

        if not allowed:
            # Record rejected event
            await db.execute(
                """INSERT INTO request_events
                   (tenant_id, timestamp, status, latency_ms, reason, is_simulated)
                   VALUES (?,?,?,?,?,?)""",
                (body.tenant_id, now.isoformat(), "rejected", latency_ms, "rate_limit_exceeded", 0),
            )
            await db.commit()

            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail=WorkloadResponse(
                    status="rejected",
                    tenant_id=body.tenant_id,
                    latency_ms=round(latency_ms, 3),
                    message=f"Rate limit exceeded ({max_rpm} requests per {window_sec}s window)",
                    retry_after_seconds=round(retry_after, 2),
                ).model_dump(),
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

        # 5. Simulate work latency (real measurement of processing overhead)
        # In a real system this is where the workload would execute.
        work_start = time.perf_counter()
        # --- placeholder: no real work in this prototype ---
        work_latency_ms = (time.perf_counter() - work_start) * 1000
        total_latency = latency_ms + work_latency_ms

        # 6. Record accepted event
        await db.execute(
            """INSERT INTO request_events
               (tenant_id, timestamp, status, latency_ms, is_simulated)
               VALUES (?,?,?,?,?)""",
            (body.tenant_id, now.isoformat(), "accepted", round(total_latency, 3), 0),
        )
        await db.commit()

        return WorkloadResponse(
            status="accepted",
            tenant_id=body.tenant_id,
            latency_ms=round(total_latency, 3),
            message="Request processed",
        )
    finally:
        await db.close()
