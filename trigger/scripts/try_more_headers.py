import os
import django
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from trigger.models import InstanciaZap

inst = InstanciaZap.objects.first()
if not inst:
    print('no instance')
    raise SystemExit(1)

token = inst.token
name = inst.instancia_id
url = 'https://servidoruazapidisparo.uazapi.com/instance/connect'
headers_to_try = ['token', 'x-token', 'x-api-key', 'X-Access-Token', 'authorization']

payload = {'instanceName': name}

print('instance:', name)
for h in headers_to_try:
    hdr = h
    headers = {hdr: token, 'Content-Type': 'application/json'}
    print('\nTrying header:', hdr)
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        print('HTTP', r.status_code)
        try:
            print(r.json())
        except Exception:
            print(r.text)
    except Exception as e:
        print('error', e)

print('\ndone')
