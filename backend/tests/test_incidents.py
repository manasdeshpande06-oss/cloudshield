"""Tests for Noisy-Neighbor Incidents, Adaptive Actions, and Rollback."""

import pytest
from httpx import ASGITransport, AsyncClient

from database import init_db
from main import app

ADMIN = {"Authorization": "Bearer fg_admin_platform_demo_key"}


@pytest.fixture(autouse=True)
async def _seed():
    await init_db()


@pytest.mark.asyncio
async def test_list_incidents():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/incidents", headers=ADMIN)
    assert r.status_code == 200
    incidents = r.json()
    assert len(incidents) >= 1
    assert incidents[0]["id"] == 1
    assert incidents[0]["tenant_id"] == "tn_northstar_01"


@pytest.mark.asyncio
async def test_incident_detail():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/incidents/1", headers=ADMIN)
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 1
    assert "affected_tenants" in body


@pytest.mark.asyncio
async def test_apply_protection_and_rollback():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Apply action
        r_apply = await c.post(
            "/api/protection/apply",
            headers=ADMIN,
            json={
                "tenant_id": "tn_northstar_01",
                "incident_id": 1,
                "action_type": "concurrency_reduction",
                "parameters": {"reduction_percent": 25},
                "duration_minutes": 30,
            },
        )
        assert r_apply.status_code == 200
        action = r_apply.json()
        assert action["status"] == "applied"
        assert action["tenant_id"] == "tn_northstar_01"
        action_id = action["id"]

        # Rollback action
        r_roll = await c.post(
            "/api/protection/rollback",
            headers=ADMIN,
            json={"action_id": action_id, "reason": "Test rollback"},
        )
        assert r_roll.status_code == 200
        roll_body = r_roll.json()
        assert roll_body["status"] == "rolled_back"
