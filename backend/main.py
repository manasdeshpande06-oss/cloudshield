"""
CloudShield FairGuard — FastAPI application entry point.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone

import time
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from database import init_db, get_db
from routers import companies, experiments, incidents, jobs, simulation, tenants, traffic, workload
from routers import overview, scheduler as scheduler_router
from routers import auth_router
from routers import contracts as contracts_router
from routers import fairness_lab as fairness_lab_router
from routers import monitoring as monitoring_router
from routers import shared_overview as shared_overview_router
from routers import audit as audit_router


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that records live API requests into SQLite for traceability.
    Excludes private request bodies, passwords, and tokens.
    Adds X-Request-ID and X-Processing-Time-Ms response headers.
    """
    async def dispatch(self, request: Request, call_next):
        req_id = f"req_{uuid.uuid4().hex[:12]}"
        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Processing-Time-Ms"] = f"{duration_ms:.2f}"

        path = request.url.path
        if path.startswith("/api") and path not in ("/api/health", "/docs", "/openapi.json"):
            tenant_id = request.headers.get("X-Tenant-ID")
            status_code = response.status_code
            throttled = 1 if status_code == 429 else 0
            policy_applied = "RateLimit" if throttled else "Standard"

            try:
                db = await get_db()
                try:
                    await db.execute(
                        """INSERT INTO api_request_logs
                           (request_id, tenant_id, endpoint, method, status_code, duration_ms, throttled, policy_applied, timestamp, is_simulated)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                        (
                            req_id,
                            tenant_id,
                            path,
                            request.method,
                            status_code,
                            round(duration_ms, 2),
                            throttled,
                            policy_applied,
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                    await db.commit()
                finally:
                    await db.close()
            except Exception:
                pass  # do not fail response if request logging has an issue

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise the database (idempotent) on startup."""
    await init_db()
    yield


app = FastAPI(
    title="CloudShield FairGuard API",
    version="0.3.0",
    description=(
        "Multi-tenant resource management: fair scheduling, "
        "adaptive protection, noisy-neighbor detection, and fairness contracts."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

# Register routers
app.include_router(auth_router.router)
app.include_router(companies.router)
app.include_router(tenants.router)
app.include_router(traffic.router)
app.include_router(workload.router)
app.include_router(simulation.router)
app.include_router(incidents.router)
app.include_router(experiments.router)
app.include_router(jobs.router)
app.include_router(overview.router)
app.include_router(scheduler_router.router)
app.include_router(contracts_router.router)
app.include_router(fairness_lab_router.router)
app.include_router(monitoring_router.router)
app.include_router(shared_overview_router.router)
app.include_router(audit_router.router)



@app.get("/api/health", tags=["Health"])
async def health():
    """Liveness check."""
    return {
        "status": "ok",
        "version": "0.3.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
