import requests
import logging
import os
from trigger.models import InstanciaZap

logger = logging.getLogger(__name__)

# --- CREDENCIAIS DO SERVIDOR DEDICADO (HARDCODED / DEFAULT) ---
FIXED_URL = "https://servidoruazapidisparo.uazapi.com"
FIXED_ID = "wckRx6"
FIXED_TOKEN = "a2a4a60a-c343-47fc-8f09-9988106346ef"

class UazApiClient:
    def __init__(self):
        self.base_url = FIXED_URL.rstrip('/')
        
        # --- LÓGICA HÍBRIDA (Banco > Hardcode > Salva) ---
        # 1. Tenta carregar do Banco de Dados (Prioridade ao Admin)
        instancia_db = InstanciaZap.objects.first()
        
        if instancia_db and instancia_db.instancia_id:
            # Se já existe no banco (editado por você), respeita o banco
            self.instance_id = instancia_db.instancia_id
            self.token = instancia_db.token
            self.origem = "Banco de Dados (Admin)"
        else:
            # 2. Se banco vazio, usa as Fixas e SALVA para permitir edição futura
            self.instance_id = FIXED_ID
            self.token = FIXED_TOKEN
            self.origem = "Padrão Fixo (Hardcoded)"
            
            # Auto-persistência: Grava no banco para aparecer no Admin
            try:
                InstanciaZap.objects.create(
                    instancia_id=FIXED_ID,
                    token=FIXED_TOKEN,
                    nome_operador="Sistema (Config Automática)",
                    conectado=False
                )
                logger.info("[UAZAPI] Credenciais fixas salvas no banco com sucesso.")
            except Exception as e:
                logger.warning(f"[UAZAPI] Erro ao salvar credenciais padrão: {e}")

        logger.info(f"[UAZAPI] Iniciado via {self.origem}. ID: {self.instance_id}")

        # Configuração dos Headers (Compatibilidade Dupla)
        self.headers = {
            "apikey": self.token,
            "token": self.token, 
            "Content-Type": "application/json"
        }

    # =========================================================================
    # MÉTODOS DE CONEXÃO E STATUS
    # =========================================================================

    def verificar_status(self):
        """Verifica conexão e atualiza o banco local"""
        endpoint = f"{self.base_url}/instance/connectionState/{self.instance_id}"
        try:
            logger.debug(f"[UAZAPI] Verificando status: {endpoint}")
            response = requests.get(endpoint, headers=self.headers, timeout=10)
            
            # Se não existir (404), tenta criar (Auto-Cura)
            if response.status_code == 404:
                logger.warning(f"[UAZAPI] Instância {self.instance_id} não encontrada. Criando...")
                if self._criar_instancia():
                    return False # Retorna False para forçar nova verificação no front
                return False

            if response.status_code == 200:
                dados = response.json()
                state = None
                
                # Parser robusto para variações da API
                if isinstance(dados, dict):
                    if 'instance' in dados and isinstance(dados['instance'], dict):
                        state = dados['instance'].get('state')
                    elif 'state' in dados:
                        state = dados.get('state')
                
                conectado = state in ['open', 'connected']
                
                # Sincroniza status no banco visualmente
                self._atualizar_status_db(conectado)
                
                logger.info(f"[UAZAPI] Status: {state} (Conectado: {conectado})")
                return conectado
            
            if response.status_code in [401, 403]:
                logger.error(f"[UAZAPI] Erro de Permissão ({response.status_code}). Token incorreto?")

            return False
        except Exception as e:
            logger.error(f"[UAZAPI] Erro ao verificar status: {e}")
            return False

    def desconectar_instancia(self):
        """Realiza Logout (Necessário para o botão 'Sair')"""
        endpoint = f"{self.base_url}/instance/logout/{self.instance_id}"
        try:
            logger.info(f"[UAZAPI] Solicitando logout de {self.instance_id}...")
            requests.delete(endpoint, headers=self.headers, timeout=10)
            self._atualizar_status_db(False)
            return True
        except Exception as e:
            logger.error(f"[UAZAPI] Erro ao desconectar: {e}")
            return False

    def obter_qr_code(self):
        """Busca QR Code com retry e auto-criação"""
        endpoint = f"{self.base_url}/instance/connect/{self.instance_id}"
        
        try:
            logger.info(f"[UAZAPI] Buscando QR para: {self.instance_id}")
            response = requests.get(endpoint, headers=self.headers, timeout=15)
            
            # Auto-cura: Se 404, cria e tenta de novo
            if response.status_code == 404:
                logger.info("[UAZAPI] 404 detectado. Criando instância...")
                if self._criar_instancia():
                     response = requests.get(endpoint, headers=self.headers, timeout=15)
                else:
                    return {"error": True, "details": "Falha ao criar instância automaticamente."}

            if response.status_code != 200:
                 return {"error": True, "details": f"Erro API: {response.status_code} - {response.text}"}

            dados = response.json()

            # Busca o base64 em qualquer lugar do JSON
            qr_code = None
            if 'base64' in dados: qr_code = dados['base64']
            elif 'qrcode' in dados: qr_code = dados['qrcode']
            elif 'instance' in dados and isinstance(dados['instance'], dict):
                qr_code = dados['instance'].get('qrcode') or dados['instance'].get('qr')
            
            if qr_code:
                return {"qrcode": qr_code}
            
            return {
                "error": True, 
                "details": "QR não encontrado (Instância já conectada?)", 
                "raw": dados
            }

        except Exception as e:
            logger.error(f"[UAZAPI] Erro crítico QR: {e}")
            return {"error": True, "details": str(e)}

    # =========================================================================
    # MÉTODOS DE AÇÃO E HELPERS
    # =========================================================================

    def _criar_instancia(self):
        """Cria a instância na API se ela não existir"""
        endpoint = f"{self.base_url}/instance/create"
        payload = {
            "instanceName": self.instance_id,
            "token": self.token,
            "qrcode": True
        }
        try:
            requests.post(endpoint, json=payload, headers=self.headers, timeout=10)
            return True
        except Exception as e:
            logger.error(f"[UAZAPI] Erro criação: {e}")
            return False

    def enviar_texto(self, numero: str, mensagem: str):
        """Envia mensagem com Fallback para Legado"""
        endpoint = f"{self.base_url}/message/sendText/{self.instance_id}"
        payload = {
            "number": numero,
            "options": {"delay": 1200, "presence": "composing"},
            "textMessage": {"text": mensagem}
        }
        try:
            response = requests.post(endpoint, json=payload, headers=self.headers, timeout=15)
            
            # Lógica de Fallback (Restaurada)
            if response.status_code in [404, 405]:
                logger.warning("[UAZAPI] Endpoint v2 falhou, tentando v1 (Legado)...")
                return self._enviar_texto_legado(numero, mensagem)
                
            return response.json()
        except Exception as e:
            logger.error(f"[UAZAPI] Erro envio: {e}")
            return {"error": True, "details": str(e)}

    def _enviar_texto_legado(self, numero, mensagem):
        """Método de envio antigo (Preservado)"""
        endpoint = f"{self.base_url}/send/text"
        payload = {"number": numero, "text": mensagem} # Payload simplificado do legado
        try:
            return requests.post(endpoint, json=payload, headers=self.headers, timeout=15).json()
        except Exception as e:
            return {"error": True, "details": f"Erro legado: {str(e)}"}

    def _atualizar_status_db(self, status):
        """Atualiza o status no banco sem travar o processo"""
        try:
            InstanciaZap.objects.filter(instancia_id=self.instance_id).update(conectado=status)
        except:
            pass