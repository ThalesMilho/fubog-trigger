#!/usr/bin/env python
"""
Script de teste para validar o fluxo QR Code
Executa: python test_qr_flow.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

import logging
from trigger.services.uazapi_client import UazApiClient
from trigger.models import InstanciaZap

# Configurar logs para debug
logging.basicConfig(
    level=logging.DEBUG,
    format='%(name)s - %(levelname)s - %(message)s'
)

def test_instancia_exists():
    """Testa se há instância no BD"""
    print("\n" + "="*60)
    print("1️⃣  TESTE: Verificar Instância no BD")
    print("="*60)
    
    instancia = InstanciaZap.objects.first()
    if not instancia:
        print("❌ ERRO: Nenhuma instância no BD")
        print("   Solução: Acesse admin e crie uma instância em InstanciaZap")
        return False
    
    print(f"✅ Instância encontrada:")
    print(f"   Nome: {instancia.nome_operador}")
    print(f"   Telefone: {instancia.numero_telefone}")
    print(f"   Instance ID: {instancia.instancia_id}")
    print(f"   Token: {instancia.token[:20]}...")
    print(f"   Conectado: {instancia.conectado}")
    return True

def test_client_init():
    """Testa inicialização do cliente"""
    print("\n" + "="*60)
    print("2️⃣  TESTE: Inicializar Cliente UazAPI")
    print("="*60)
    
    try:
        client = UazApiClient()
        print(f"✅ Cliente inicializado:")
        print(f"   Base URL: {client.base_url}")
        print(f"   Instance ID: {client.instance_id}")
        print(f"   Token: {client.token[:20]}..." if client.token else "   Token: VAZIO ❌")
        return client
    except Exception as e:
        print(f"❌ Erro ao inicializar: {e}")
        return None

def test_obter_qr(client):
    """Testa obtenção de QR Code"""
    print("\n" + "="*60)
    print("3️⃣  TESTE: Obter QR Code")
    print("="*60)
    
    try:
        resultado = client.obter_qr_code()
        
        if resultado.get('error'):
            print(f"❌ Erro da API: {resultado.get('details')}")
            print("\n   Possíveis causas:")
            print("   1. Token inválido")
            print("   2. Instance ID incorreto")
            print("   3. API offline")
            print("   4. Sem acesso à internet")
            return False
        
        chaves = list(resultado.keys())
        print(f"✅ QR obtido com sucesso!")
        print(f"   Chaves na resposta: {chaves}")
        
        # Procurar pelo base64
        for chave in ['base64', 'qrcode', 'qr']:
            if chave in resultado:
                tamanho = len(resultado[chave])
                print(f"   ✅ Encontrado '{chave}': {tamanho} caracteres")
                if resultado[chave].startswith('data:image'):
                    print(f"      Tipo: Data URI (pronto para usar no HTML)")
                return True
        
        print(f"   ⚠️  Nenhuma chave de QR encontrada")
        print(f"      Resposta completa: {resultado}")
        return False
        
    except Exception as e:
        print(f"❌ Erro crítico: {e}")
        return False

def test_verificar_status(client):
    """Testa verificação de status"""
    print("\n" + "="*60)
    print("4️⃣  TESTE: Verificar Status de Conexão")
    print("="*60)
    
    try:
        conectado = client.verificar_status()
        
        if conectado:
            print(f"✅ INSTÂNCIA CONECTADA!")
            print(f"   WhatsApp está pronto para usar")
        else:
            print(f"⏳ Instância ainda não conectada")
            print(f"   Próximo passo: Escanear o QR Code")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao verificar: {e}")
        return False

def main():
    print("\n")
    print("╔" + "═"*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  🧪 TESTE DE FLUXO QR CODE - WHATSAPP  ".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "═"*58 + "╝")
    
    # Teste 1
    if not test_instancia_exists():
        print("\n❌ ABORTADO: Instância não configurada")
        return
    
    # Teste 2
    client = test_client_init()
    if not client:
        print("\n❌ ABORTADO: Erro ao inicializar cliente")
        return
    
    # Teste 3
    qr_ok = test_obter_qr(client)
    
    # Teste 4
    test_verificar_status(client)
    
    # Resumo final
    print("\n" + "="*60)
    print("📋 RESUMO")
    print("="*60)
    
    if qr_ok:
        print("✅ Seu sistema está PRONTO para uso!")
        print("\nPróximos passos:")
        print("1. Acesse: http://localhost:8000/conectar-whatsapp/")
        print("2. Veja o QR Code")
        print("3. Abra WhatsApp > Aparelhos Conectados > Conectar")
        print("4. Escaneie o código")
        print("5. Aguarde a página atualizar automaticamente")
    else:
        print("❌ Há problemas a corrigir:")
        print("\nVerifique no painel Django (logs) qual é o erro exato")
        print("Consulte DEBUG_GUIA.md para soluções")

if __name__ == '__main__':
    main()
