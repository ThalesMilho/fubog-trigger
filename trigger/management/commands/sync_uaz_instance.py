import json
import logging
import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from trigger.models import InstanciaZap

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = (
        "Verifica token da InstanciaZap contra a API Uaz e opcionalmente persiste id/token retornados.\n"
        "Útil para diagnosticar 401/404 e sincronizar a instância com o que a API espera."
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Salvar id/token retornados no DB')
        parser.add_argument('--instance', type=str, help='UUID da InstanciaZap (campo `id`)')
        parser.add_argument('--base-url', type=str, default='https://servidoruazapidisparo.uazapi.com', help='Base URL da API')

    def handle(self, *args, **options):
        inst = None
        if options.get('instance'):
            inst = InstanciaZap.objects.filter(id=options['instance']).first()
        else:
            inst = InstanciaZap.objects.first()

        if not inst:
            self.stderr.write('Nenhuma InstanciaZap encontrada no DB')
            return

        token = inst.token
        instance_name = inst.instancia_id
        base_url = options.get('base_url')

        self.stdout.write('Testando InstanciaZap:')
        self.stdout.write(f'  DB id: {inst.id}')
        self.stdout.write(f'  nome_operador: {inst.nome_operador}')
        self.stdout.write(f'  instancia_id (db): {instance_name}')
        self.stdout.write(f'  token (prefix): {token[:12]}...')
        self.stdout.write('\nRealizando POST para /instance/connect (modo de teste)')

        url = f"{base_url.rstrip('/')}/instance/connect"
        payload_base = {'instanceName': instance_name}

        # Try multiple header/body variants to detect which form the API accepts
        variants = [
            ('x-access-token header', {'x-access-token': token, 'Content-Type': 'application/json'}, payload_base),
            ('Authorization: Bearer header', {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}, payload_base),
            ('token in JSON body', {'Content-Type': 'application/json'}, {**payload_base, 'token': token}),
            ('token header', {'token': token, 'Content-Type': 'application/json'}, payload_base),
            ('x-token header', {'x-token': token, 'Content-Type': 'application/json'}, payload_base),
            ('x-api-key header', {'x-api-key': token, 'Content-Type': 'application/json'}, payload_base),
        ]

        success_resp = None
        for title, headers, payload in variants:
            self.stdout.write(f'\n-- Tentativa: {title}')
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=15)
            except Exception as e:
                self.stderr.write(f'Erro ao conectar na API: {e}')
                continue

            self.stdout.write(f'Status HTTP: {resp.status_code}')
            try:
                body = resp.json()
                pretty = json.dumps(body, indent=2, ensure_ascii=False)
                self.stdout.write('Resposta JSON:')
                self.stdout.write(pretty)
            except Exception:
                self.stdout.write('Resposta (não-JSON):')
                self.stdout.write(resp.text)

            if resp.status_code == 200:
                success_resp = (resp, title)
                break

        if not success_resp:
            self.stderr.write('\nA requisição não foi bem-sucedida em nenhum formato. Verifique token/instancia no painel UazAPI e que o token corresponde à instância.')
            return

        resp, used_variant = success_resp
        self.stdout.write(f'\nSucesso usando: {used_variant}')

        # Tentar extrair id/token retornados pela API
        data = None
        try:
            data = resp.json()
        except Exception:
            data = None

        instance_data = None
        if isinstance(data, dict):
            # A API às vezes coloca em 'instance' ou 'data' ou direto no body
            instance_data = data.get('instance') or data.get('data') or data

        new_id = None
        new_token = None
        if isinstance(instance_data, dict):
            new_id = instance_data.get('id') or instance_data.get('instanceId')
            new_token = instance_data.get('token')

        if not new_id and not new_token:
            self.stdout.write('\nNenhum id/token extraído da resposta — talvez a resposta contenha forma diferente.')
            return

        self.stdout.write('\nExtraído da API:')
        if new_id:
            self.stdout.write(f'  instance.id: {new_id}')
        if new_token:
            self.stdout.write(f'  token (prefix): {new_token[:12]}...')

        if options.get('apply'):
            self.stdout.write('\nAplicando atualização no DB...')
            with transaction.atomic():
                if new_id:
                    inst.instancia_id = new_id
                if new_token:
                    inst.token = new_token
                inst.save()
            self.stdout.write(self.style.SUCCESS('InstanciaZap atualizada com sucesso'))
        else:
            self.stdout.write('\nExecução em modo dry-run. Use --apply para salvar as alterações no DB')
