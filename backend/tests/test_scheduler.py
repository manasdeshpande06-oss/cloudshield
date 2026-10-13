"""Tests for Fair Round-Robin Scheduler router and decisions."""

import pytest
from httpx import ASGITransport, AsyncClient

from database import init_db
from main import app

ADMIN = {"Authorization": "Bearer fg_admin_platform_demo_key"}


@pytest.fixture(autouse=True)
async def _seed():
    await init_db()


@pytest.mark.asyncio
async def test_scheduler_status():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/scheduler/status", headers=ADMIN)
    assert r.status_code == 200
    data = r.json()
    assert "max_workers" in data
    assert "queued_jobs_total" in data
    assert data["max_workers"] == 12


@pytest.mark.asyncio
async def test_scheduler_enqueue_job():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/scheduler/enqueue",
            headers=ADMIN,
            params={
                "tenant_id": "tn_northstar_01",
                "job_type": "cpu_heavy",
                "priority": 5,
            },
        )
    assert r.status_code == 202
    body = r.json()
    assert "job_id" in body
    assert body["status"] == "queued"


@pytest.mark.asyncio
async def test_scheduler_history():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Enqueue job and run step
        await c.post(
            "/api/scheduler/enqueue",
            headers=ADMIN,
            params={
                "tenant_id": "tn_meridian_04",
                "job_type": "api_light",
            },
        )
        await c.post("/api/scheduler/step", headers=ADMIN)
        r = await c.get("/api/scheduler/history", headers=ADMIN)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
