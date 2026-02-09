#!/usr/bin/env python3
"""
🔍 Script de Diagnóstico Completo - UazAPI + Django
Autor: Engenheiro Senior FUBOG
Versão: 2.1 (Correção de Auth)
"""

import os
import sys
import django
import requests
import json
from datetime import datetime
from pathlib import Path

# Cores para terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text.center(70)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.CYAN}ℹ️  {text}{Colors.END}")

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

# Peguei do seu print:
INSTANCE_ID = "FubogSystem"
BASE_URL = "https://servidoruazapidisparo.uazapi.com"
INSTANCE_TOKEN = "a754f425-5c89-4964-b59e-a56ea087dfa6" # TOKEN DA INSTÂNCIA

# ============================================================================
# TESTE 1: API RAW (SEM DJANGO)
# ============================================================================

def test_api_raw():
    print_header("TESTE 1: API UAZAPI (CURL SIMULADO)")
    
    # 1.1: Verificar Status
    print(f"{Colors.BOLD}1.1 - Verificando Status da Instância{Colors.END}")
    print(f"      Endpoint: {BASE_URL}/instance/connectionState/{INSTANCE_ID}")
    print(f"      Token usado: {INSTANCE_TOKEN[:15]}... (Instance Token)")
    
    try:
        response = requests.get(
            f"{BASE_URL}/instance/connectionState/{INSTANCE_ID}",
            headers={"apikey": INSTANCE_TOKEN}, # Usando Token da Instância
            timeout=10
        )
        
        print(f"      Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"      Resposta: {json.dumps(data, indent=2)}")
            
            state = 'unknown'
            if 'instance' in data and isinstance(data['instance'], dict):
                state = data['instance'].get('state')
            elif 'state' in data:
                state = data.get('state')

            if state == 'open':
                print_success(f"Instância CONECTADA (state: {state})")
            elif state == 'close':
                print_warning(f"Instância ONLINE mas DESCONECTADA do Zap (state: {state})")
                print_info("Isso é bom! Significa que a API existe, só falta ler o QR Code.")
            else:
                print_warning(f"Estado retornado: {state}")
            return True # O teste passou pq a API respondeu
            
        elif response.status_code == 404:
            print_error("Erro 404: Instância não encontrada.")
            print_warning("Isso geralmente acontece se o NOME da instância estiver errado.")
            return False
        elif response.status_code == 401:
            print_error("Erro 401: Não autorizado.")
            print_warning("O Token da Instância está incorreto.")
            return False
        else:
            print_error(f"Código HTTP inesperado: {response.status_code}")
            print(f"      Body: {response.text[:300]}")
            return False

    except Exception as e:
        print_error(f"EXCEÇÃO: {e}")
        return False
    
    # 1.2: Solicitar QR Code
    # (Removi essa parte do raw para simplificar, vamos testar o QR no Django Client)

# ============================================================================
# TESTE 2: DJANGO MODELS E CLIENT
# ============================================================================

def test_django_integration():
    print_header("TESTE 2: INTEGRAÇÃO COM DJANGO")
    
    try:
        print_info("Configurando ambiente Django...")
        sys.path.append(str(Path(__file__).parent)) 
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings') 
        django.setup()
        print_success("Django setup OK")
        
        # Importa client atualizado
        from trigger.services.uazapi_client import UazApiClient
        
        client = UazApiClient()
        print(f"\n{Colors.BOLD}2.1 - Validando Tokens no Client{Colors.END}")
        print(f"      Client Instance ID: {client.instance_id}")
        
        # Verifica se o client pegou o token novo
        if client.instance_token == INSTANCE_TOKEN:
             print_success("Client está usando o Token da Instância correto (Hardcoded)")
        else:
             print_warning(f"Client usando token diferente: {client.instance_token[:10]}...")

        # Testa conexão via Client
        print(f"\n{Colors.BOLD}2.2 - Teste de Conectividade via Client{Colors.END}")
        conectado = client.verificar_status()
        
        if conectado:
            print_success("Método verificar_status() retornou TRUE (Conectado)")
        else:
            print_warning("Método verificar_status() retornou FALSE (Desconectado)")
            
        # Testa obtenção de QR Code
        print(f"\n{Colors.BOLD}2.3 - Teste de Obtenção de QR Code{Colors.END}")
        resp_qr = client.obter_qr_code()
        
        if 'error' in resp_qr:
            print_error(f"Erro ao obter QR: {resp_qr.get('details')}")
            print(f"      Dados brutos: {resp_qr}")
        elif 'qrcode' in resp_qr:
            print_success(f"QR Code obtido! Tamanho: {len(resp_qr['qrcode'])} chars")
        else:
            print_warning("QR Code não veio (talvez já conectado?)")
            print(f"      Resposta: {resp_qr}")

        return True
        
    except Exception as e:
        print_error(f"Erro no teste Django: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# MAIN
# ============================================================================

def main():
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("🔍 DIAGNÓSTICO FUBOG - VERSÃO INSTANCE TOKEN")
    print("=" * 70)
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{Colors.END}")
    
    input(f"\n{Colors.YELLOW}Pressione ENTER para testar...{Colors.END}")
    
    api_ok = test_api_raw()
    
    # Executa o teste do Django mesmo se o RAW falhar, pra gente debuggar
    django_ok = test_django_integration()
    
    print_header("RESUMO")
    if api_ok and django_ok:
        print_success("TUDO CERTO! O sistema deve funcionar.")
    else:
        print_warning("Houve falhas. Verifique as mensagens acima.")

if __name__ == "__main__":
    main()