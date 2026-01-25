import requests
import logging
import os
from trigger.models import InstanciaZap

logger = logging.getLogger(__name__)

# --- CONFIGURAÇÃO SERVIDOR DEDICADO (HARDCODED) ---
FIXED_URL = "https://servidoruazapidisparo.uazapi.com"
FIXED_ID = "wckRx6"
FIXED_TOKEN = "a2a4a60a-c343-47fc-8f09-9988106346ef"

class UazApiClient:
    def __init__(self):
        # 1. Definição da URL (Forçada para o dedicado)
        self.base_url = FIXED_URL.rstrip('/')
        
        # 2. Definição das Credenciais (Forçadas)
        self.instance_id = FIXED_ID
        self.token = FIXED_TOKEN  # Mantive o nome 'token' que seu código usava
        
        # Mantendo compatibilidade com seu código que usa self.token
        self.headers = {
            "token": self.token,
            "apikey": self.token,
            "Content-Type": "application/json"
        }
        
        logger.info(f"[UAZAPI] Cliente iniciado (Dedicado). ID: {self.instance_id}")

    # =========================================================================
    # MÉTODOS ORIGINAIS (PRESERVADOS)
    # =========================================================================

    def verificar_status(self):
        """Verifica o status da conexão com log detalhado"""
        endpoint = f"{self.base_url}/instance/connectionState/{self.instance_id}"
        try:
            logger.debug(f"[UAZAPI] Verificando status: {endpoint}")
            response = requests.get(endpoint, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                dados = response.json()
                state = None
                # Sua lógica original de parse robusto
                if 'instance' in dados and isinstance(dados['instance'], dict):
                    state = dados['instance'].get('state')
                elif 'state' in dados:
                    state = dados.get('state')
                
                conectado = state in ['open', 'connected']
                logger.info(f"[UAZAPI] Estado: {state} -> Conectado: {conectado}")
                return conectado

            # Se 404, tenta criar (Sua lógica de auto-cura)
            if response.status_code == 404:
                logger.warning("[UAZAPI] Status 404. Tentando criar instância...")
                if self._criar_instancia():
                    return self.verificar_status() # Retry recursivo
                return False
            
            return False
        except Exception as e:
            logger.error(f"[UAZAPI] Erro ao verificar status: {e}")
            return False

    def desconectar_instancia(self):
        """Realiza logout (Mantido para o botão Sair funcionar)"""
        endpoint = f"{self.base_url}/instance/logout/{self.instance_id}"
        try:
            logger.info(f"[UAZAPI] Desconectando {self.instance_id}...")
            requests.delete(endpoint, headers=self.headers, timeout=10)
            return True
        except Exception as e:
            logger.error(f"[UAZAPI] Erro ao desconectar: {e}")
            return False

    def obter_qr_code(self):
        """Busca QR Code com suas tratativas de erro originais"""
        endpoint = f"{self.base_url}/instance/connect/{self.instance_id}"
        
        try:
            logger.info(f"[UAZAPI] Buscando QR para: {self.instance_id}")
            
            # 1. Tentativa padrão (GET)
            response = requests.get(endpoint, headers=self.headers, timeout=15)
            
            # 2. Se 404, cria e tenta de novo (Lógica sua preservada)
            if response.status_code == 404:
                logger.warning(f"[UAZAPI] Instância não encontrada. Criando...")
                if self._criar_instancia():
                     response = requests.get(endpoint, headers=self.headers, timeout=15)
                else:
                    return {"error": True, "details": "Falha ao criar instância automaticamente."}

            if response.status_code != 200:
                 return {"error": True, "details": f"Erro API: {response.status_code} - {response.text}"}

            dados = response.json()
            logger.info(f"[UAZAPI] QR obtido. Chaves: {list(dados.keys())}")

            # Seu parser original de QR Code (Preservado)
            qr_code = None
            if 'base64' in dados: qr_code = dados['base64']
            elif 'qrcode' in dados: qr_code = dados['qrcode']
            elif 'instance' in dados and isinstance(dados['instance'], dict):
                qr_code = dados['instance'].get('qrcode') or dados['instance'].get('qr')
            
            if qr_code:
                return {"qrcode": qr_code}
            
            return {"error": True, "details": "QR não encontrado no JSON (Instância já conectada?)", "raw": dados}

        except Exception as e:
            logger.error(f"[UAZAPI] Erro crítico QR: {e}")
            return {"error": True, "details": str(e)}

    def _criar_instancia(self):
        """Método interno para criar instância se não existir"""
        endpoint = f"{self.base_url}/instance/create"
        payload = {
            "instanceName": self.instance_id,
            "token": self.token,
            "qrcode": True 
        }
        try:
            logger.info(f"[UAZAPI] Criando instância: {self.instance_id}")
            response = requests.post(endpoint, json=payload, headers=self.headers, timeout=15)
            return response.status_code in [200, 201]
        except Exception as e:
            logger.error(f"[UAZAPI] Erro ao criar instância: {e}")
            return False

    def enviar_texto(self, numero: str, mensagem: str):
        """Envia mensagem (com lógica de fallback legado que você tinha)"""
        endpoint = f"{self.base_url}/message/sendText/{self.instance_id}"
        payload = {
            "number": numero,
            "options": {"delay": 1200, "presence": "composing"},
            "textMessage": {"text": mensagem}
        }
        try:
            response = requests.post(endpoint, json=payload, headers=self.headers, timeout=15)
            
            # Sua lógica de fallback (Se der erro 404/405, tenta método antigo)
            if response.status_code in [404, 405]:
                logger.warning("[UAZAPI] Endpoint padrão falhou, tentando legado...")
                return self._enviar_texto_legado(numero, mensagem)
                
            return response.json()
        except Exception as e:
            logger.error(f"[UAZAPI] Erro envio: {e}")
            return {"error": True, "details": str(e)}

    def _enviar_texto_legado(self, numero, mensagem):
        """Seu método de fallback preservado"""
        endpoint = f"{self.base_url}/send/text"
        payload = {"number": numero, "text": mensagem}
        try:
            return requests.post(endpoint, json=payload, headers=self.headers, timeout=15).json()
        except Exception as e:
            return {"error": True, "details": str(e)}