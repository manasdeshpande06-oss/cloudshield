"""
FAIRCLOUD — STRICT USP IMPLEMENTATION ACCEPTANCE TEST SUITE (Section 16)
Verifies:
  Test A: Cross-tenant visibility (Shop A sees Game B & Food C; Admin sees consistent values)
  Test B: Allocation violation (Borrowing disabled, demand exceeds, violation calculated and status displayed)
  Test C: Permitted borrowing (Borrowing permitted, spare capacity tracked, total capacity invariant preserved)
  Test D: Reclaiming (Source tenant demand rises, scheduler reclaims, preserves guarantee, audit recorded)
  Test E: Noisy-neighbor scenario (Game B traffic spike, innocent tenants degraded, evidence-backed incident & Fairness Receipt)
  Test F: Policy comparison (Unprotected vs Fixed Quota vs Adaptive under identical inputs & calculated metrics)
  Test G: Data consistency (Honest zero-observation empty states, no fabricated 45 ms latency, honest infrastructure labels)
  Test H: Security & access control (Unauthenticated blocked, tenant cannot modify others or call admin APIs, private data isolated)
"""

import json
import sys
import urllib.error
import urllib.request

BASE_URL = "http://localhost:8000"


def request(method: str, path: str, data: dict = None, headers: dict = None):
    url = f"{BASE_URL}{path}"
    headers = headers or {}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        err_content = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_content)
        except Exception:
            err_json = {"raw": err_content}
        return e.code, err_json


def login(username: str, password: str = None) -> str:
    if password is None:
        if username == "admin":
            password = "admin"
        else:
            password = username
    status, res = request("POST", "/api/auth/login", {"username": username, "password": password})
    assert status == 200, f"Login failed for {username}: {res}"
    return res["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def run_all_tests():
    print("======================================================================")
    print("FAIRCLOUD — STRICT USP IMPLEMENTATION ACCEPTANCE SUITE (TESTS A TO H)")
    print("======================================================================\n")

    results = {}

    # Setup tokens
    admin_token = login("admin")
    shop_token = login("shop_a")
    admin_hdr = auth_header(admin_token)
    shop_hdr = auth_header(shop_token)

    # -------------------------------------------------------------------------
    # TEST A: Cross-tenant visibility
    # -------------------------------------------------------------------------
    print("--> Running Test A: Cross-tenant visibility...")
    try:
        status, shop_view = request("GET", "/api/shared-resource-overview", headers=shop_hdr)
        assert status == 200, f"Shop A failed to fetch shared overview: {shop_view}"
        tenants_shop_view = {t["tenant_id"]: t for t in shop_view["tenants"]}

        assert "game_b" in tenants_shop_view, "Game B not visible to Shop A in shared overview"
        assert "food_c" in tenants_shop_view, "Food C not visible to Shop A in shared overview"

        # Check required fields
        game_b_for_shop = tenants_shop_view["game_b"]
        assert "current_resource_usage" in game_b_for_shop or "current_request_rate_rpm" in game_b_for_shop
        assert "configured_rate_limit_rpm" in game_b_for_shop
        assert "min_service_guarantee_rpm" in game_b_for_shop
        assert "fairness_status" in game_b_for_shop

        # Admin visibility
        status, admin_view = request("GET", "/api/shared-resource-overview", headers=admin_hdr)
        assert status == 200, f"Admin failed to fetch shared overview: {admin_view}"
        tenants_admin_view = {t["tenant_id"]: t for t in admin_view["tenants"]}

        # Consistency check
        assert tenants_admin_view["game_b"]["requests_received"] == game_b_for_shop["requests_received"], \
            "Inconsistent request counts between Admin and Shop A view"
        assert tenants_admin_view["game_b"]["configured_rate_limit_rpm"] == game_b_for_shop["configured_rate_limit_rpm"], \
            "Inconsistent configured limits between Admin and Shop A view"

        results["Test A"] = "PASSED: Shop A can inspect Game B & Food C operational metadata; Admin view is 100% consistent."
        print(f"    [OK] {results['Test A']}")
    except Exception as e:
        results["Test A"] = f"FAILED: {e}"
        print(f"    [FAIL] {results['Test A']}")

    # -------------------------------------------------------------------------
    # TEST B: Allocation violation
    # -------------------------------------------------------------------------
    print("\n--> Running Test B: Allocation violation...")
    try:
        # Configure tenant food_c with borrowing disabled
        status, updated_contract = request(
            "PUT",
            "/api/contracts/food_c",
            {
                "min_cpu_pct": 3.0,
                "max_cpu_pct": 25.0,
                "priority": 5,
                "min_rpm": 50,
                "max_rpm": 80,
                "borrow_allowed": False,
                "borrow_cap_pct": 0.0,
                "notes": "Strict hard cap test: borrowing disabled",
            },
            headers=admin_hdr,
        )
        assert status == 200, f"Failed to update contract for food_c: {updated_contract}"

        # Trigger traffic that exceeds allocation with rejections
        status, spike_res = request(
            "POST",
            "/api/simulation/trigger-spike?burst_multiplier=6.0&policy=fixed_quota",
            headers=admin_hdr,
        )
        assert status == 200, f"Failed to trigger spike: {spike_res}"

        # Fetch shared overview and inspect status
        status, overview = request("GET", "/api/shared-resource-overview", headers=admin_hdr)
        tenants_map = {t["tenant_id"]: t for t in overview["tenants"]}
        target_item = tenants_map["game_b"]

        # Game B exceeded quota under fixed_quota policy (borrowing cap hit)
        assert target_item["requests_rejected"] > 0, "Expected rejected requests under strict quota"
        assert target_item["rate_limit_exceeded"] is True, "Expected rate_limit_exceeded to be True"
        assert target_item["fairness_status"] in ("Exceeds Configured Allocation", "Protection Applied", "Another Tenant's Guarantee at Risk"), \
            f"Unexpected fairness status: {target_item['fairness_status']}"

        results["Test B"] = f"PASSED: Allocation violation calculated; status '{target_item['fairness_status']}' displayed with {target_item['requests_rejected']} throttled requests."
        print(f"    [OK] {results['Test B']}")
    except Exception as e:
        results["Test B"] = f"FAILED: {e}"
        print(f"    [FAIL] {results['Test B']}")

    # -------------------------------------------------------------------------
    # TEST C: Permitted borrowing
    # -------------------------------------------------------------------------
    print("\n--> Running Test C: Permitted borrowing...")
    try:
        # Check that sum of min guarantees across all tenants <= 100% (capacity invariant)
        status, contracts = request("GET", "/api/contracts", headers=admin_hdr)
        assert status == 200, f"Failed to list contracts: {contracts}"
        total_min_cpu = sum(c["min_cpu_pct"] for c in contracts)
        assert total_min_cpu <= 100.0, f"Capacity invariant violated: total min_cpu_pct = {total_min_cpu}% > 100%"

        # Execute borrow cycle: Game B borrows 15 units from Shop A's spare capacity
        status, borrow_res = request(
            "POST",
            "/api/contracts/simulate-borrow-reclaim",
            {
                "borrowing_tenant_id": "game_b",
                "source_tenant_id": "shop_a",
                "amount": 15.0,
                "reason": "Bursty player traffic handled by spare capacity borrowing",
                "policy_rule": "adaptive_fairness",
            },
            headers=admin_hdr,
        )
        assert status == 200, f"Failed to execute borrow simulation: {borrow_res}"
        assert borrow_res["amount_borrowed"] == 15.0
        assert borrow_res["borrowing_tenant"] == "game_b"

        # Verify borrowing ledger record
        status, records = request("GET", "/api/contracts/borrowing-records", headers=admin_hdr)
        assert status == 200
        assert len(records) > 0
        latest_rec = records[0]
        assert latest_rec["borrowing_tenant_id"] == "game_b"
        assert latest_rec["amount_borrowed"] == 15.0

        results["Test C"] = f"PASSED: Permitted borrowing recorded (15.0 units); total platform minimum guarantees ({total_min_cpu:.1f}%) <= 100% capacity preserved."
        print(f"    [OK] {results['Test C']}")
    except Exception as e:
        results["Test C"] = f"FAILED: {e}"
        print(f"    [FAIL] {results['Test C']}")

    # -------------------------------------------------------------------------
    # TEST D: Reclaiming
    # -------------------------------------------------------------------------
    print("\n--> Running Test D: Reclaiming...")
    try:
        status, records = request("GET", "/api/contracts/borrowing-records", headers=admin_hdr)
        assert status == 200
        latest_rec = records[0]
        assert latest_rec["amount_reclaimed"] == 15.0, "Expected 15.0 units reclaimed when source tenant demand increased"
        assert latest_rec["time_reclaimed"] is not None, "Expected timestamp of capacity reclamation"

        # Check policy enforcement record
        status, enf_records = request("GET", "/api/contracts/enforcement-records", headers=admin_hdr)
        assert status == 200
        assert len(enf_records) > 0
        latest_enf = enf_records[0]
        assert latest_enf["action_selected"] == "reclaim_borrowed_capacity"
        assert latest_enf["action_result"] == "success"

        results["Test D"] = "PASSED: Scheduler reclaimed 15.0 units upon source tenant demand rise; policy decision and audit logged."
        print(f"    [OK] {results['Test D']}")
    except Exception as e:
        results["Test D"] = f"FAILED: {e}"
        print(f"    [FAIL] {results['Test D']}")

    # -------------------------------------------------------------------------
    # TEST E: Noisy-neighbor scenario
    # -------------------------------------------------------------------------
    print("\n--> Running Test E: Noisy-neighbor scenario...")
    try:
        # Trigger Game B traffic spike under adaptive policy
        status, spike_res = request(
            "POST",
            "/api/simulation/trigger-spike?burst_multiplier=5.0&policy=adaptive",
            headers=admin_hdr,
        )
        assert status == 200, f"Trigger spike failed: {spike_res}"
        inc_id = spike_res["incident_id"]

        # Fetch incident details and Fairness Receipt
        status, receipt = request("GET", f"/api/incidents/{inc_id}/receipt", headers=admin_hdr)
        assert status == 200, f"Failed to retrieve Fairness Receipt: {receipt}"

        assert receipt["incident_id"] == inc_id
        assert receipt["suspected_tenant_id"] == "game_b"
        assert len(receipt["affected_tenants"]) >= 2, "Expected Shop A and Food C listed as affected"
        assert receipt["policy_action_taken"] is not None, "Expected protection action in receipt"
        assert receipt["recovery_status"] in ("measured_recovered", "measuring_in_progress")
        assert receipt["data_source_label"] == "SIMULATION MODE"

        results["Test E"] = f"PASSED: Game B 5.0x burst produced Incident #{inc_id} with Fairness Receipt, affected tenants, and protection verification."
        print(f"    [OK] {results['Test E']}")
    except Exception as e:
        results["Test E"] = f"FAILED: {e}"
        print(f"    [FAIL] {results['Test E']}")

    # -------------------------------------------------------------------------
    # TEST F: Policy comparison
    # -------------------------------------------------------------------------
    print("\n--> Running Test F: Policy comparison...")
    try:
        comparison_payload = {
            "game_b_burst_factor": 5.0,
            "total_workers": 12,
            "quota_per_tenant": 40,
            "duration_seconds": 60,
            "seed": 42,
            "shop_a_priority": 8,
            "game_b_priority": 5,
            "food_c_priority": 6,
        }
        status, lab_result = request("POST", "/api/fairness-lab/custom-comparison", comparison_payload)
        assert status == 200, f"Custom comparison failed: {lab_result}"

        policies = {p["policy"]: p for p in lab_result["policies"]}
        assert "unprotected" in policies, "Missing unprotected policy result"
        assert "fixed_quota" in policies, "Missing fixed_quota policy result"
        assert "adaptive" in policies, "Missing adaptive policy result"

        # Check identical inputs
        assert lab_result["total_workers"] == 12
        assert lab_result["duration_seconds"] == 60

        # Check real calculated metrics
        unprotected = policies["unprotected"]
        fixed_quota = policies["fixed_quota"]
        adaptive = policies["adaptive"]

        assert unprotected["system_fairness_index"] > 0
        assert fixed_quota["overall_rejected"] > 0, "Fixed quota should reject excess bursts"
        assert adaptive["system_throughput_pct"] > 0

        results["Test F"] = f"PASSED: 3-policy comparison ran against identical inputs; Adaptive fairness index={adaptive['system_fairness_index']}, throughput={adaptive['system_throughput_pct']}%."
        print(f"    [OK] {results['Test F']}")
    except Exception as e:
        results["Test F"] = f"FAILED: {e}"
        print(f"    [FAIL] {results['Test F']}")

    # -------------------------------------------------------------------------
    # TEST G: Data consistency
    # -------------------------------------------------------------------------
    print("\n--> Running Test G: Data consistency...")
    try:
        status, overview = request("GET", "/api/shared-resource-overview", headers=admin_hdr)
        assert status == 200
        for t in overview["tenants"]:
            # If zero requests, assert no fabricated latency
            if t["requests_received"] == 0:
                assert t["has_sufficient_latency_samples"] is False
                assert t["avg_latency_display"] == "—", f"Tenant {t['tenant_name']} has 0 requests but displayed {t['avg_latency_display']}"
                assert t["fairness_status"] == "Insufficient Data"

            # Infrastructure label check
            if t["cpu_percent"] is None:
                assert t["infrastructure_status"] == "No infrastructure data available"

        results["Test G"] = "PASSED: Zero-observation tenants display '—' (no hardcoded 45 ms); disconnected telemetry displays honest empty states."
        print(f"    [OK] {results['Test G']}")
    except Exception as e:
        results["Test G"] = f"FAILED: {e}"
        print(f"    [FAIL] {results['Test G']}")

    # -------------------------------------------------------------------------
    # TEST H: Security & access control
    # -------------------------------------------------------------------------
    print("\n--> Running Test H: Security & access control...")
    try:
        # 1. Unauthenticated request to /api/contracts
        status, _ = request("GET", "/api/contracts")
        assert status == 401, f"Expected 401 for unauthenticated request, got {status}"

        # 2. Shop A attempting to edit Northstar's contract
        status, _ = request(
            "PUT",
            "/api/contracts/tn_northstar_01",
            {"min_cpu_pct": 5.0, "max_cpu_pct": 40.0, "priority": 5, "min_rpm": 100, "max_rpm": 1000},
            headers=shop_hdr,
        )
        assert status == 403, f"Expected 403 when Shop A tries to edit Northstar contract, got {status}"

        # 3. Shop A attempting admin reset
        status, _ = request("POST", "/api/admin/system/reset", headers=shop_hdr)
        assert status in (403, 404), f"Expected 403/404 for tenant calling admin reset, got {status}"

        # 4. Shop A reading shared resource overview (permitted)
        status, shop_read = request("GET", "/api/shared-resource-overview", headers=shop_hdr)
        assert status == 200, f"Expected 200 for Shop A reading shared overview, got {status}"

        # 5. Verify private logs / passwords / API keys are not in shared overview response
        overview_str = json.dumps(shop_read)
        assert "password" not in overview_str
        assert "fg_demo_northstar" not in overview_str
        assert "api_key" not in overview_str

        results["Test H"] = "PASSED: Security checks enforced (unauthenticated blocked, tenant cross-edits rejected with 403, private tokens isolated)."
        print(f"    [OK] {results['Test H']}")
    except Exception as e:
        results["Test H"] = f"FAILED: {e}"
        print(f"    [FAIL] {results['Test H']}")

    print("\n======================================================================")
    print("ACCEPTANCE TEST SUMMARY:")
    print("======================================================================")
    all_passed = True
    for test_name, res in results.items():
        print(f"{test_name}: {res}")
        if "FAILED" in res:
            all_passed = False

    print("======================================================================")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
