import asyncio
import sys
import os

# Ensure backend directory is in sys.path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from database import init_db
from main import app
from httpx import ASGITransport, AsyncClient

ADMIN = {'Authorization': 'Bearer fg_admin_platform_demo_key'}

async def main():
    await init_db()
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as c:
        # 1. Health
        r = await c.get('/api/health')
        assert r.status_code == 200, f'Health failed: {r.text}'
        print('[OK] Health check passed')

        # 2. Company tenants with metrics
        r = await c.get('/api/companies/COMP-012/tenants', headers=ADMIN)
        assert r.status_code == 200, f'Tenants failed: {r.text}'
        tenants = r.json()
        assert len(tenants) >= 1
        t = tenants[0]
        print(f'[OK] COMP-012 tenant: {t["name"]}')
        print(f'     Accepted: {t["accepted_count"]}, Throttled: {t["rejected_count"]}, Avg Latency: {t["avg_latency_ms"]} ms, Quota: {t["quota_rpm"]} rpm')
        assert t["accepted_count"] > 0, "Expected accepted_count > 0"
        assert t["avg_latency_ms"] > 0, "Expected avg_latency_ms > 0"

        # 3. Traffic endpoint
        r = await c.get(f'/api/tenants/{t["id"]}/traffic', headers=ADMIN)
        assert r.status_code == 200, f'Traffic failed: {r.text}'
        tf = r.json()
        print(f'[OK] Traffic buckets: {len(tf)} buckets. First bucket: {tf[0] if tf else None}')
        if tf:
            assert 'T' in tf[0]['time'], f'Expected ISO timestamp, got {tf[0]["time"]}'

        # 4. Shared overview
        r = await c.get('/api/shared-resource-overview', headers=ADMIN)
        assert r.status_code == 200, f'Overview failed: {r.text}'
        ov = r.json()
        print(f'[OK] Shared overview: {len(ov["tenants"])} tenants')
        assert len(ov["tenants"]) >= 13

        # 5. Contracts
        r = await c.get('/api/contracts', headers=ADMIN)
        assert r.status_code == 200, f'Contracts failed: {r.text}'
        contracts = r.json()
        print(f'[OK] Fairness contracts: {len(contracts)} contracts')

        # 6. Incidents
        r = await c.get('/api/incidents', headers=ADMIN)
        assert r.status_code == 200, f'Incidents failed: {r.text}'
        incidents = r.json()
        print(f'[OK] Incidents: {len(incidents)} incidents')

    print('\nALL FASTAPI BACKEND IN-PROCESS CHECKS PASSED 100%!')

if __name__ == '__main__':
    asyncio.run(main())
