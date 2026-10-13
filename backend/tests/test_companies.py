"""Tests for company and tenant API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from database import init_db
from main import app

ADMIN = {"Authorization": "Bearer fg_admin_platform_demo_key"}


@pytest.fixture(autouse=True)
async def _seed():
    await init_db()


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "timestamp" in body


@pytest.mark.asyncio
async def test_list_companies():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/companies", headers=ADMIN)
    assert r.status_code == 200
    companies = r.json()
    assert len(companies) in (10, 13)
    assert all("tenant_count" in c for c in companies)


@pytest.mark.asyncio
async def test_get_company_detail():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/companies/COMP-001", headers=ADMIN)
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Northstar Analytics"
    assert body["tenant_count"] == 3


@pytest.mark.asyncio
async def test_get_company_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/companies/COMP-999", headers=ADMIN)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_tenants_by_company():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/companies/COMP-001/tenants", headers=ADMIN)
    assert r.status_code == 200
    tenants = r.json()
    assert len(tenants) == 3
    assert all(t["company_id"] == "COMP-001" for t in tenants)


@pytest.mark.asyncio
async def test_get_tenant_with_metrics():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/tenants/tn_northstar_01", headers=ADMIN)
    assert r.status_code == 200
    body = r.json()
    assert body["tenant"]["id"] == "tn_northstar_01"
    assert body["quota"]["requests_per_minute"] == 1000
    assert "accepted_count" in body


@pytest.mark.asyncio
async def test_get_tenant_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/tenants/tn_nonexistent", headers=ADMIN)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_quota():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.put(
            "/api/tenants/tn_northstar_01/quota",
            json={"requests_per_minute": 2000, "max_concurrency": 50, "window_seconds": 60},
            headers=ADMIN,
        )
    assert r.status_code == 200
    body = r.json()
    assert body["requests_per_minute"] == 2000
    assert body["max_concurrency"] == 50


@pytest.mark.asyncio
async def test_auth_invalid_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/companies", headers={"Authorization": "Bearer bad_key"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_company_scoped_key_cannot_see_other_company():
    """A company-scoped API key should not access another company's tenants."""
    from database import _make_api_key
    northstar_key = _make_api_key("northstar")
    headers = {"Authorization": f"Bearer {northstar_key}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Northstar is COMP-001, try to access COMP-002 (Meridian)
        r = await c.get("/api/companies/COMP-002/tenants", headers=headers)
    assert r.status_code == 403
