"""Tests for workload request submission and rate limiting."""

import pytest
from httpx import ASGITransport, AsyncClient

from database import _make_api_key, init_db
from main import app
from rate_limiter import limiter

ADMIN = {"Authorization": "Bearer fg_admin_platform_demo_key"}


@pytest.fixture(autouse=True)
async def _seed():
    await init_db()
    limiter.reset()  # Clean limiter state between tests


@pytest.mark.asyncio
async def test_submit_accepted():
    key = _make_api_key("northstar")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/workload/request", json={
            "tenant_id": "tn_northstar_01",
            "api_key": key,
            "payload": {"data": "test"},
        })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "accepted"
    assert body["tenant_id"] == "tn_northstar_01"
    assert body["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_submit_rejected_rate_limit():
    """After exhausting the quota, requests should return 429."""
    key = _make_api_key("lattice")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Set a very low quota
        await c.put(
            "/api/tenants/tn_lattice_02/quota",
            json={"requests_per_minute": 3, "max_concurrency": 30, "window_seconds": 60},
            headers=ADMIN,
        )

        # Send 3 requests (should be accepted)
        for _ in range(3):
            r = await c.post("/api/workload/request", json={
                "tenant_id": "tn_lattice_02", "api_key": key,
            })
            assert r.status_code == 200

        # 4th request should be rejected
        r = await c.post("/api/workload/request", json={
            "tenant_id": "tn_lattice_02", "api_key": key,
        })
        assert r.status_code == 429
        assert "Retry-After" in r.headers


@pytest.mark.asyncio
async def test_submit_bad_tenant():
    key = _make_api_key("northstar")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/workload/request", json={
            "tenant_id": "tn_nonexistent", "api_key": key,
        })
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_submit_bad_api_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/workload/request", json={
            "tenant_id": "tn_northstar_01", "api_key": "bad_key",
        })
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_submit_wrong_company_key():
    """An API key from one company cannot submit requests for another's tenant."""
    key = _make_api_key("meridian")  # Meridian key
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/workload/request", json={
            "tenant_id": "tn_northstar_01",  # Northstar tenant
            "api_key": key,
        })
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_events_recorded():
    """Accepted and rejected requests should be stored in request_events."""
    key = _make_api_key("meridian")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Set low quota
        await c.put(
            "/api/tenants/tn_meridian_04/quota",
            json={"requests_per_minute": 2, "max_concurrency": 30, "window_seconds": 60},
            headers=ADMIN,
        )

        # 2 accepted + 1 rejected = 3 total events
        await c.post("/api/workload/request", json={"tenant_id": "tn_meridian_04", "api_key": key})
        await c.post("/api/workload/request", json={"tenant_id": "tn_meridian_04", "api_key": key})
        await c.post("/api/workload/request", json={"tenant_id": "tn_meridian_04", "api_key": key})

        # Check recorded events (filter to non-simulated only)
        r = await c.get("/api/tenants/tn_meridian_04/request-events?limit=100", headers=ADMIN)
        assert r.status_code == 200
        events = r.json()
        live_events = [e for e in events if not e["is_simulated"]]
        assert len(live_events) == 3
        statuses = [e["status"] for e in live_events]
        assert statuses.count("accepted") == 2
        assert statuses.count("rejected") == 1
