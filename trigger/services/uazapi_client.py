import requests
import logging
from trigger.models import InstanciaZap

logger = logging.getLogger(__name__)

class UazApiClient:
    def __init__(self):
        self.base_url = "https://free.uazapi.com"
        self.instance_id = "FubogSystem"
        
        # --- CONFIGURAÇÃO DE TOKENS ---
        
        # 1. Token da Instância (Do seu print) - Este será o PRINCIPAL agora
        self.instance_token = "a754f425-5c89-4964-b59e-a56ea087dfa6"
        
        # 2. Token Admin (Mantido apenas para fallback ou debug se necessário)
        # Corrigi um typo que tinha no anterior (UbTc -> Ub1c) baseado no seu print
        self.admin_token = "ZaW1qwTEkuq7Ub1cBUuyMiK5bNSu3nnMQ9Ih7klElc2clSRV8t"

        # Tenta carregar do banco, mas dá preferência ao hardcoded do print se o banco falhar
        instancia_db = InstanciaZap.objects.first()
        if instancia_db and instancia_db.token and len(instancia_db.token) > 10:
            # Se quiser forçar o do print, comente a linha abaixo
            # self.instance_token = instancia_db.token
            logger.info(f"[UAZAPI] Usando token definido no código: {self.instance_token[:15]}...")
        else:
            logger.info(f"[UAZAPI] Usando token fixo do código: {self.instance_token[:15]}...")

    # =========================================================================
    # MÉTODOS DE CONEXÃO (AGORA USANDO INSTANCE TOKEN)
    # =========================================================================
    
    def verificar_status(self):
        """Verifica se está conectado usando o token da instância"""
        endpoint = f"{self.base_url}/instance/connectionState/{self.instance_id}"
        
        # MUDANÇA AQUI: Usando instance_token
        headers = {"apikey": self.instance_token}
        
        try:
            logger.info(f"[UAZAPI] Verificando status da instância {self.instance_id}...")
            response = requests.get(endpoint, headers=headers, timeout=10)
            
            if response.status_code == 404:
                logger.warning("[UAZAPI] Instância não encontrada (404).")
                return False
            
            if response.status_code == 401:
                logger.error("[UAZAPI] Token da instância rejeitado (401).")
                return False

            if response.status_code == 200:
                dados = response.json()
                
                # Tenta diferentes estruturas de resposta
                estado = None
                if 'instance' in dados and isinstance(dados['instance'], dict):
                    estado = dados['instance'].get('state')
                elif 'state' in dados:
                    estado = dados.get('state')
                
                conectado = estado == 'open'
                logger.info(f"[UAZAPI] Estado: {estado} | Conectado: {conectado}")
                return conectado
            
            return False
            
        except Exception as e:
            logger.error(f"[UAZAPI] Erro ao verificar status: {e}")
            return False

    def desconectar_instancia(self):
        """Desconecta a instância (Logout)"""
        endpoint = f"{self.base_url}/instance/logout/{self.instance_id}"
        headers = {"apikey": self.instance_token}
        
        try:
            logger.info(f"[UAZAPI] Desconectando {self.instance_id}...")
            response = requests.delete(endpoint, headers=headers, timeout=10)
            return response.status_code in [200, 204]
        except Exception as e:
            logger.error(f"[UAZAPI] Erro ao desconectar: {e}")
            return False

    def obter_qr_code(self):
        """
        Busca o QR Code usando o Token da Instância.
        """
        endpoint = f"{self.base_url}/instance/connect/{self.instance_id}"
        
        # MUDANÇA AQUI: Usando instance_token
        headers = {"apikey": self.instance_token}

        try:
            logger.info(f"[UAZAPI] 🔍 Solicitando QR Code com Instance Token...")
            logger.debug(f"[UAZAPI] Endpoint: {endpoint}")
            
            response = requests.get(endpoint, headers=headers, timeout=20)
            
            logger.info(f"[UAZAPI] 📡 Status Code: {response.status_code}")
            
            # Tratamento de erros específicos
            if response.status_code == 401:
                return {
                    "error": True, 
                    "details": "Token da Instância Inválido (401). Verifique o token no painel."
                }
            
            if response.status_code == 404:
                return {
                    "error": True, 
                    "details": "Instância não encontrada (404)."
                }

            if response.status_code != 200:
                return {
                    "error": True,
                    "details": f"Erro HTTP {response.status_code}: {response.text[:100]}"
                }
            
            dados = response.json()
            
            # Busca o QR Code em vários locais possíveis do JSON
            qr_code = None
            if 'base64' in dados: qr_code = dados['base64']
            elif 'qrcode' in dados: qr_code = dados['qrcode']
            elif 'instance' in dados and isinstance(dados['instance'], dict):
                qr_code = dados['instance'].get('qrcode') or dados['instance'].get('qr')
            
            if qr_code:
                return {"qrcode": qr_code}
            else:
                # Se não veio QR code, pode ser que já esteja conectado
                return {
                    "error": True,
                    "details": "QR Code não retornado. A instância pode já estar conectada.",
                    "raw_response": dados
                }

        except Exception as e:
            logger.error(f"[UAZAPI] ❌ Erro inesperado: {e}")
            return {"error": True, "details": str(e)}

    def enviar_texto(self, numero: str, mensagem: str):
        """Envia mensagem de texto"""
        endpoint = f"{self.base_url}/message/sendText/{self.instance_id}"
        
        headers = {
            "apikey": self.instance_token, # Usa o mesmo token
            "Content-Type": "application/json"
        }
        
        payload = {
            "number": numero,
            "options": {"delay": 1200},
            "textMessage": {"text": mensagem}
        }
        
        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=15)
            return response.json()
        except Exception as e:
            logger.error(f"[UAZAPI] Erro no envio: {e}")
            return {"error": True, "details": str(e)}