import requests
import logging
import os
from trigger.models import InstanciaZap

logger = logging.getLogger(__name__)

class UazApiClient:
    def __init__(self):
        # 1. Configuração da URL (Lê do ambiente ou usa padrão)
        self.base_url = os.getenv('UAZAPI_URL', "https://free.uazapi.com").rstrip('/')
        
        # 2. Inicializa variáveis
        self.instance_id = None
        self.instance_token = None

        # 3. Carregamento de Credenciais (Prioridade: Banco de Dados > Ambiente > Padrão)
        instancia_db = InstanciaZap.objects.first()
        
        if instancia_db and instancia_db.instancia_id:
            # CENÁRIO IDEAL: Lê o que a automação gravou no banco
            self.instance_id = instancia_db.instancia_id
            self.instance_token = instancia_db.token
            logger.info(f"[UAZAPI] Iniciado com credenciais do Banco: ID={self.instance_id}")
        else:
            # FALLBACK: Se o banco estiver vazio, tenta ler variáveis diretas (segurança)
            self.instance_id = os.getenv('UAZAPI_INSTANCE_ID', 'fubog_default')
            self.instance_token = os.getenv('UAZAPI_TOKEN', '')
            logger.warning(f"[UAZAPI] Banco vazio! Usando fallback de ambiente: ID={self.instance_id}")

    # =========================================================================
    # MÉTODOS INTERNOS (Novos)
    # =========================================================================
    
    def _get_headers(self):
        """Gera os headers dinamicamente para garantir o token atual"""
        return {
            "apikey": self.instance_token,
            "token": self.instance_token, # Alguns endpoints usam 'token'
            "Content-Type": "application/json"
        }

    def _criar_instancia(self):
        """
        Auto-Cura: Tenta criar a instância na API se ela não existir (Erro 404).
        Isso é crucial para o primeiro uso.
        """
        endpoint = f"{self.base_url}/instance/create"
        payload = {
            "instanceName": self.instance_id,
            "token": self.instance_token,
            "qrcode": True
        }
        try:
            logger.info(f"[UAZAPI] 🚑 Tentando AUTO-CRIAR instância: {self.instance_id}...")
            response = requests.post(endpoint, json=payload, headers=self._get_headers(), timeout=10)
            
            if response.status_code in [200, 201]:
                logger.info("[UAZAPI] ✅ Instância criada com sucesso!")
                return True
            elif response.status_code == 403:
                logger.warning("[UAZAPI] Instância já existe (403).")
                return True
            else:
                logger.error(f"[UAZAPI] Falha ao criar instância: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"[UAZAPI] Erro de conexão ao criar: {e}")
            return False

    # =========================================================================
    # MÉTODOS PÚBLICOS (Sua lógica original preservada e melhorada)
    # =========================================================================
    
    def verificar_status(self):
        """Verifica se está conectado"""
        if not self.instance_id: return False

        endpoint = f"{self.base_url}/instance/connectionState/{self.instance_id}"
        
        try:
            logger.debug(f"[UAZAPI] Checando status: {endpoint}")
            response = requests.get(endpoint, headers=self._get_headers(), timeout=10)
            
            # SE NÃO EXISTE (404), TENTA CRIAR
            if response.status_code == 404:
                logger.warning("[UAZAPI] Status 404. Tentando criar instância e verificar de novo...")
                if self._criar_instancia():
                    # Retry recursivo (uma única vez)
                    return self.verificar_status()
                return False
            
            if response.status_code == 401:
                logger.error("[UAZAPI] Erro 401: Token inválido. Verifique UAZAPI_TOKEN no Render.")
                return False

            if response.status_code == 200:
                dados = response.json()
                # Lógica original de parse preservada
                estado = None
                if 'instance' in dados and isinstance(dados['instance'], dict):
                    estado = dados['instance'].get('state')
                elif 'state' in dados:
                    estado = dados.get('state')
                
                conectado = estado in ['open', 'connected']
                return conectado
            
            return False
            
        except Exception as e:
            logger.error(f"[UAZAPI] Erro ao verificar status: {e}")
            return False

    def obter_qr_code(self):
        """Busca o QR Code com lógica de fallback"""
        if not self.instance_id: 
            return {"error": True, "details": "ID da instância não configurado no banco."}

        endpoint = f"{self.base_url}/instance/connect/{self.instance_id}"

        try:
            logger.info(f"[UAZAPI] 🔍 Buscando QR Code para: {self.instance_id}")
            response = requests.get(endpoint, headers=self._get_headers(), timeout=20)
            
            # SE NÃO EXISTE (404), TENTA CRIAR
            if response.status_code == 404:
                logger.info("[UAZAPI] 404 ao pedir QR. Iniciando auto-criação...")
                self._criar_instancia()
                # Tenta pedir de novo após criar
                response = requests.get(endpoint, headers=self._get_headers(), timeout=20)

            if response.status_code != 200:
                return {"error": True, "details": f"Erro API: {response.status_code} - {response.text[:50]}"}
            
            dados = response.json()
            
            # Lógica original de busca do base64 (Preservada)
            qr_code = None
            if 'base64' in dados: qr_code = dados['base64']
            elif 'qrcode' in dados: qr_code = dados['qrcode']
            elif 'instance' in dados and isinstance(dados['instance'], dict):
                qr_code = dados['instance'].get('qrcode') or dados['instance'].get('qr')
            
            if qr_code:
                return {"qrcode": qr_code}
            else:
                return {
                    "error": True, 
                    "details": "Instância já conectada ou API não retornou QR.",
                    "raw": dados
                }

        except Exception as e:
            logger.error(f"[UAZAPI] Erro crítico QR: {e}")
            return {"error": True, "details": str(e)}

    def desconectar_instancia(self):
        endpoint = f"{self.base_url}/instance/logout/{self.instance_id}"
        try:
            requests.delete(endpoint, headers=self._get_headers(), timeout=10)
            return True
        except:
            return False

    def enviar_texto(self, numero: str, mensagem: str):
        endpoint = f"{self.base_url}/message/sendText/{self.instance_id}"
        
        payload = {
            "number": numero,
            "options": {"delay": 1200},
            "textMessage": {"text": mensagem}
        }
        
        try:
            response = requests.post(endpoint, json=payload, headers=self._get_headers(), timeout=15)
            return response.json()
        except Exception as e:
            logger.error(f"[UAZAPI] Erro envio: {e}")
            return {"error": True, "details": str(e)}