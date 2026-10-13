import urllib.request
import json

def check_url(url, desc):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'FairCloud-Test'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
            content = resp.read(500).decode('utf-8', errors='ignore')
            print(f"[OK] {desc} ({url}) -> HTTP {status}")
            return True
    except Exception as e:
        print(f"[FAIL] {desc} ({url}) -> {e}")
        return False

print("=== CHECKING NEXT.JS FRONTEND TENANT ROUTES ===")
routes = [
    ("/tenant", "My Overview Route"),
    ("/tenant/tenants", "My Tenants Route"),
    ("/tenant/traffic", "Traffic & Quotas Route"),
    ("/tenant/usage", "Resource Usage Route"),
    ("/tenant/contracts", "Fairness Contracts Route"),
    ("/tenant/incidents", "Incidents Route"),
    ("/tenant/profile", "Company Profile Route"),
    ("/tenant/reports", "Reports Route"),
    ("/login", "Login Route"),
]
all_fe = True
for r, d in routes:
    if not check_url(f"http://localhost:3000{r}", d):
        all_fe = False

print("\n=== CHECKING FASTAPI BACKEND ENDPOINTS ===")
be_endpoints = [
    ("/api/health", "Health Check"),
    ("/api/auth/credentials", "Demo Credentials"),
    ("/api/companies/COMP-012/tenants", "Tenant List with Aggregated Metrics"),
    ("/api/tenants/game_b/traffic", "Hourly Traffic Time-Series"),
    ("/api/shared-resource-overview", "Shared Resource Table"),
    ("/api/contracts", "Contracts Endpoint"),
    ("/api/incidents", "Incidents Endpoint"),
]
all_be = True
for ep, d in be_endpoints:
    try:
        req = urllib.request.Request(
            f"http://localhost:8000{ep}",
            headers={'Authorization': 'Bearer fg_admin_platform_demo_key', 'User-Agent': 'FairCloud-Test'}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read()
            parsed = json.loads(data)
            count = len(parsed) if isinstance(parsed, list) else (len(parsed.get('tenants', [])) if 'tenants' in parsed else 'dict')
            print(f"[OK] {d} ({ep}) -> HTTP {resp.status}, count/info: {count}")
    except Exception as e:
        print(f"[FAIL] {d} ({ep}) -> {e}")
        all_be = False

print("\nFrontend OK:", all_fe)
print("Backend OK:", all_be)
