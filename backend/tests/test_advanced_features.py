"""
Tests for FairCloud advanced features:
- Authentication (JWT login, register, role checks)
- Shared resource overview (accessible to both admin and tenants)
- Fairness Receipt generation and evidence classification
- Real infrastructure metrics ingestion and freshness
- Contract feasibility validation (sum of minimum guarantees <= capacity)
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from database import PLATFORM_ADMIN_KEY, init_db
from main import app


@pytest_asyncio.fixture(autouse=True)
async def ensure_db():
    await init_db()


@pytest.mark.asyncio
async def test_jwt_login_admin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Valid admin login
        res = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": PLATFORM_ADMIN_KEY},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == "admin"
        assert "access_token" in data
        token = data["access_token"]

        # Call authenticated me endpoint
        me_res = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_res.status_code == 200
        assert me_res.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_jwt_login_tenant():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Get demo credentials to find tenant
        creds_res = await client.get("/api/auth/credentials")
        assert creds_res.status_code == 200
        tenant_creds = [c for c in creds_res.json()["demo_credentials"] if c["role"] == "tenant"][0]

        # Log in as tenant
        res = await client.post(
            "/api/auth/login",
            json={"username": tenant_creds["username"], "password": tenant_creds["password"]},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == "tenant"
        token = data["access_token"]

        # Tenant can access own overview
        me_res = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_res.status_code == 200
        assert me_res.json()["role"] == "tenant"


@pytest.mark.asyncio
async def test_tenant_self_registration():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/auth/register",
            json={
                "company_name": "Test Acme Cloud Inc",
                "initial_tenant_name": "Acme Core Worker",
                "workload_type": "API / light",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == "tenant"
        assert data["company_name"] == "Test Acme Cloud Inc"
        assert "access_token" in data


@pytest.mark.asyncio
async def test_shared_resource_overview():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Get token
        login_res = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": PLATFORM_ADMIN_KEY},
        )
        token = login_res.json()["access_token"]

        res = await client.get(
            "/api/shared-resource-overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "tenants" in data
        assert len(data["tenants"]) > 0
        first = data["tenants"][0]
        # Verify required operational fields
        assert "tenant_id" in first
        assert "configured_rate_limit_rpm" in first
        assert "requests_received" in first
        assert "requests_accepted" in first
        assert "requests_rejected" in first
        assert "min_service_guarantee_rpm" in first
        assert "policy_adherence_status" in first
        assert "data_source_label" in first
        # Verify private keys/passwords are NOT present
        assert "api_key" not in first
        assert "password" not in first


@pytest.mark.asyncio
async def test_fairness_receipt():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Admin login
        login_res = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": PLATFORM_ADMIN_KEY},
        )
        token = login_res.json()["access_token"]

        # Get seeded incident #1 receipt
        res = await client.get(
            "/api/incidents/1/receipt",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        receipt = res.json()
        assert receipt["incident_id"] == 1
        assert receipt["cause_classification"] in [
            "Observed", "Suspected cause", "Confirmed cause", "Cause undetermined"
        ]
        assert "affected_tenants" in receipt
        assert "evidence_signals" in receipt
        assert "summary_text" in receipt
        assert receipt["data_source_label"] in ["LIVE APPLICATION DATA", "SIMULATION MODE"]


@pytest.mark.asyncio
async def test_infrastructure_monitoring_ingest_and_status():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login_res = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": PLATFORM_ADMIN_KEY},
        )
        token = login_res.json()["access_token"]

        # Ingest live metrics
        ingest_res = await client.post(
            "/api/infrastructure/metrics",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "source": "prometheus-node-exporter",
                "cpu_percent": 45.2,
                "memory_percent": 61.8,
            },
        )
        assert ingest_res.status_code == 201

        # Check status
        status_res = await client.get(
            "/api/infrastructure/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["connected"] is True
        assert status_data["status_label"] == "CONNECTED INFRASTRUCTURE"
        assert status_data["latest_cpu_percent"] == 45.2


@pytest.mark.asyncio
async def test_contract_feasibility_validation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login_res = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": PLATFORM_ADMIN_KEY},
        )
        token = login_res.json()["access_token"]

        # Attempt to set min_cpu_pct to 99% when others already consume > 10%
        res = await client.put(
            "/api/contracts/tn_northstar_01",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "min_cpu_pct": 75.0,
                "max_cpu_pct": 80.0,
                "priority": 10,
                "min_rpm": 500,
                "max_rpm": 1000,
            },

        )
        # Should reject because sum of minimum guarantees exceeds 100% capacity
        assert res.status_code == 400
        assert "Infeasible contract" in res.json()["detail"]


@pytest.mark.asyncio
async def test_custom_fairness_lab():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/fairness-lab/custom-comparison",
            json={
                "game_b_burst_factor": 6.0,
                "total_workers": 16,
                "quota_per_tenant": 50,
                "seed": 42,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["policies"]) == 3
        # Check reproducibility with identical seed
        res2 = await client.post(
            "/api/fairness-lab/custom-comparison",
            json={
                "game_b_burst_factor": 6.0,
                "total_workers": 16,
                "quota_per_tenant": 50,
                "seed": 42,
            },
        )
        assert res2.status_code == 200
        assert data["policies"][0]["overall_accepted"] == res2.json()["policies"][0]["overall_accepted"]


@pytest.mark.asyncio
async def test_affected_tenant_incident_access_and_isolation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Log in as Shop A
        shop_a_login = await client.post(
            "/api/auth/login",
            json={"username": "shop_a", "password": "shop_a"},
        )
        assert shop_a_login.status_code == 200
        shop_a_token = shop_a_login.json()["access_token"]
        shop_a_headers = {"Authorization": f"Bearer {shop_a_token}"}

        # 2. Trigger a comparison that generates an incident where Game B causes interference affecting Shop A
        sim_res = await client.post(
            "/api/fairness-lab/custom-comparison",
            json={
                "game_b_burst_factor": 5.0,
                "total_workers": 16,
                "quota_per_tenant": 50,
                "seed": 101,
            },
        )
        assert sim_res.status_code == 200

        # 3. Shop A (affected tenant) can access the incident and its Fairness Receipt via incidents endpoint
        inc_list_res = await client.get("/api/incidents", headers=shop_a_headers)
        assert inc_list_res.status_code == 200
        incidents = inc_list_res.json()
        assert len(incidents) >= 1
        inc_id = incidents[0]["id"]

        inc_res = await client.get(f"/api/incidents/{inc_id}", headers=shop_a_headers)
        assert inc_res.status_code == 200
        inc_data = inc_res.json()
        assert "shop_a" in str(inc_data.get("affected_tenants", ""))

        receipt_res = await client.get(f"/api/incidents/{inc_id}/receipt", headers=shop_a_headers)
        assert receipt_res.status_code == 200
        receipt = receipt_res.json()
        assert receipt["incident_id"] == inc_id
        assert "affected_tenants" in receipt
        assert "summary_text" in receipt

        # 4. Shop A CANNOT modify Game B's contract (tenant isolation enforces 403 Forbidden)
        tamper_res = await client.put(
            "/api/contracts/game_b",
            headers=shop_a_headers,
            json={
                "min_cpu_pct": 2.0,
                "max_cpu_pct": 40.0,
                "priority": 2,
            },
        )
        assert tamper_res.status_code == 403


@pytest.mark.asyncio
async def test_simulation_spike_pause_reset_and_results():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Pause simulation
        pause_res = await client.post("/api/simulation/pause")
        assert pause_res.status_code == 200
        assert pause_res.json()["running"] is False

        # Reset simulation
        reset_res = await client.post("/api/simulation/reset")
        assert reset_res.status_code == 200
        assert reset_res.json()["running"] is False

        # Trigger Game B spike
        spike_res = await client.post(
            "/api/simulation/trigger-spike?burst_multiplier=5.0&policy=adaptive",
        )
        assert spike_res.status_code == 200
        spike_data = spike_res.json()
        assert spike_data["status"] in ("success", "spike_completed")
        assert spike_data.get("incident_id") is not None
        assert "game_b" in spike_data["metrics"]

        # Verify persisted fairness lab results
        results_res = await client.get("/api/fairness-lab/results")
        assert results_res.status_code == 200
        runs = results_res.json()
        assert isinstance(runs, list)
        assert len(runs) >= 1


@pytest.mark.asyncio
async def test_fairness_contracts_validation_and_persistence():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_login = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": PLATFORM_ADMIN_KEY},
        )
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 1. Valid contract update with feasible min_cpu_pct (2.5%)
        valid_res = await client.put(
            "/api/contracts/shop_a",
            headers=admin_headers,
            json={
                "min_cpu_pct": 2.5,
                "max_cpu_pct": 50.0,
                "priority": 8,
                "min_rpm": 150,
                "max_rpm": 800,
                "borrow_allowed": True,
                "borrow_cap_pct": 20.0,
            },
        )
        assert valid_res.status_code == 200

        # Verify contract is retrievable
        list_res = await client.get("/api/contracts", headers=admin_headers)
        assert list_res.status_code == 200
        contracts = list_res.json()
        shop_contract = next((c for c in contracts if c["tenant_id"] == "shop_a"), None)
        assert shop_contract is not None
        assert shop_contract["min_cpu_pct"] == 2.5
        assert shop_contract["max_cpu_pct"] == 50.0

        # 2. Infeasible contract validation (min > max)
        invalid_res = await client.put(
            "/api/contracts/shop_a",
            headers=admin_headers,
            json={
                "min_cpu_pct": 60.0,
                "max_cpu_pct": 40.0,
                "priority": 5,
            },
        )
        assert invalid_res.status_code in (400, 422)
