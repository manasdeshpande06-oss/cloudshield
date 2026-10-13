import urllib.request
import sys

routes = [
    '/tenant',
    '/tenant/tenants',
    '/tenant/traffic',
    '/tenant/reports',
    '/tenant/contracts',
    '/tenant/incidents',
    '/tenant/usage',
    '/tenant/profile',
]

success = True
for r in routes:
    try:
        url = f'http://localhost:3000{r}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, timeout=10)
        status = res.status
        print(f'{r}: HTTP {status}')
        if status != 200:
            success = False
    except Exception as e:
        print(f'{r}: ERROR {e}')
        success = False

if not success:
    sys.exit(1)
print("ALL TENANT ROUTES PASS!")
