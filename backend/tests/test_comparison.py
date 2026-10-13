"""Tests for Multi-Tenant Resource Visibility and Comparison."""

import pytest
from httpx import ASGITransport, AsyncClient

from database import init_db
from main import app

ADMIN = {"Authorization": "Bearer fg_admin_platform_demo_key"}


@pytest.fixture(autouse=True)
async def _seed():
    await init_db()


@pytest.mark.asyncio
async def test_company_tenant_comparison():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/companies/comparison", headers=ADMIN)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) in (25, 28)
    # Verify expected visibility columns
    row0 = rows[0]
    assert "tenant_id" in row0
    assert "company_name" in row0
    assert "workload_type" in row0
    assert "quota_rpm" in row0
    assert "max_concurrency" in row0
    assert "cpu_scope" in row0


@pytest.mark.asyncio
async def test_update_tenant_quota():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.put(
            "/api/tenants/tn_northstar_01/quota",
            headers=ADMIN,
            json={
                "requests_per_minute": 1500,
                "max_concurrency": 35,
                "queue_limit": 120,
                "resource_budget_cpu": 30.0,
                "resource_budget_memory": 30.0,
                "window_seconds": 60,
            },
        )
    assert r.status_code == 200
    q = r.json()
    assert q["requests_per_minute"] == 1500
    assert q["max_concurrency"] == 35
