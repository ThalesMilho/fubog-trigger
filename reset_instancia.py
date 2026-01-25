import requests
import json
import time

# --- CONFIGURAÇÃO ---
BASE_URL = "https://free.uazapi.com"
# Seu Admin Token (confirmado do print)
ADMIN_TOKEN = "ZaW1qwTEkuq7Ub1cBUuyMiK5bNSu3nnMQ9Ih7klElc2clSRV8t" 
INSTANCE_NAME = "FubogSystem"

def print_step(step):
    print(f"\n👉 {step}...")

def hard_reset():
    headers = {
        "apikey": ADMIN_TOKEN,
        "Content-Type": "application/json"
    }

    print("🚨 INICIANDO HARD RESET DA INSTÂNCIA 🚨")
    print(f"Alvo: {INSTANCE_NAME}")
    print("-" * 50)

    # 1. TENTAR DELETAR (Para limpar qualquer lixo)
    print_step("1. Tentando DELETAR a instância antiga")
    try:
        url_delete = f"{BASE_URL}/instance/delete/{INSTANCE_NAME}"
        resp = requests.delete(url_delete, headers=headers)
        
        if resp.status_code == 200:
            print(f"✅ Instância deletada com sucesso! (Limpeza concluída)")
        elif resp.status_code == 404:
            print(f"ℹ️  A instância já não existia na API (Isso confirma o erro 404 anterior).")
        else:
            print(f"⚠️  Retorno inesperado ao deletar: {resp.status_code} - {resp.text}")
            
    except Exception as e:
        print(f"❌ Erro ao tentar deletar: {e}")

    time.sleep(2) # Respira fundo...

    # 2. TENTAR CRIAR (Do zero)
    print_step("2. Tentando CRIAR a instância novamente")
    try:
        url_create = f"{BASE_URL}/instance/create"
        payload = {
            "instanceName": INSTANCE_NAME,
            "description": "FUBOG Trigger System"
        }
        
        resp = requests.post(url_create, json=payload, headers=headers)
        
        if resp.status_code == 201 or resp.status_code == 200:
            data = resp.json()
            print("✅ SUCESSO! Instância recriada.")
            print("-" * 50)
            
            # Tenta pegar o token novo
            novo_token = None
            if 'hash' in data: novo_token = data['hash']
            elif 'token' in data: novo_token = data['token']
            elif 'instance' in data and 'token' in data['instance']: novo_token = data['instance']['token']
            
            if novo_token:
                print(f"🔑 NOVO TOKEN DA INSTÂNCIA: {novo_token}")
                print(f"⚠️  ATENÇÃO: Copie esse token e atualize o seu arquivo 'uazapi_client.py'!")
            else:
                print("⚠️  Criou, mas não retornou o token explicitamente. Veja o JSON:")
                print(json.dumps(data, indent=2))
                
        elif resp.status_code == 403:
            print("❌ Erro 403: Limite de instâncias atingido ou proibido.")
            print("Solução: Vá no painel da UazApi, delete a instância manualmente pelo site, e tente de novo.")
        else:
            print(f"❌ Falha ao criar: {resp.status_code}")
            print(f"Resposta: {resp.text}")

    except Exception as e:
        print(f"❌ Erro ao tentar criar: {e}")

if __name__ == "__main__":
    hard_reset()