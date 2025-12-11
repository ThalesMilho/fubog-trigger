import os
import json
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()

from trigger.models import InstanciaZap

inst = InstanciaZap.objects.first()
if not inst:
    print('Nenhuma InstanciaZap no DB')
    raise SystemExit(1)

token = inst.token
instance_name = inst.instancia_id
base_url = 'https://free.uazapi.com'
url = f"{base_url.rstrip('/')}/instance/connect"

print('Using instance (db):', instance_name)
print('Will try 3 header/body variants (token masked).\n')

variants = []
# Variant 1: x-access-token header (existing)
variants.append(('x-access-token header', {'x-access-token': token, 'Content-Type': 'application/json'}, {'instanceName': instance_name}))
# Variant 2: Authorization: Bearer <token>
variants.append(('Authorization Bearer header', {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}, {'instanceName': instance_name}))
# Variant 3: token in JSON body
variants.append(('token in JSON body', {'Content-Type': 'application/json'}, {'instanceName': instance_name, 'token': token}))

for title, headers, payload in variants:
    print('---')
    print(title)
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
    except Exception as e:
        print('Request error:', e)
        continue
    print('HTTP', r.status_code)
    try:
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    except Exception:
        print(r.text)

print('\nDone')
