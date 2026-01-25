import requests
import logging
import os
from trigger.models import InstanciaZap

logger = logging.getLogger(__name__)

# --- CREDENCIAIS FIXAS (SERVIDOR DEDICADO) ---
FIXED_URL = "https://servidoruazapidisparo.uazapi.com"
FIXED_ID = "wckRx6"
FIXED_TOKEN = "a2a4a60a-c343-47fc-8f09-9988106346ef"

class UazApiClient:
    def __init__(self):
        # 1. Configuração da URL
        self.base_url = FIXED_URL.rstrip('/')
        
        # 2. Lógica Híbrida de Credenciais (Banco > Hardcode > Persistência)
        instancia_db = InstanciaZap.objects.first()
        
        if instancia_db and instancia_db.instancia_id:
            # Prioridade 1: O que estiver no banco (permite edição via Admin)
            self.instance_id = instancia_db.instancia_id
            self.token = instancia_db.token
            self.origem = "Banco de Dados (Admin)"
        else:
            # Prioridade 2: Hardcode Fixo (Setup Inicial)
            self.instance_id = FIXED_ID
            self.token = FIXED_TOKEN
            self.origem = "Hardcoded (Fixo)"
            
            # Persistência: Salva no banco para aparecer no Admin
            self._persistir_credenciais_iniciais()

        logger.info(f"[UAZAPI] Cliente iniciado via {self.origem}. ID: {self.instance_id}")

        # Headers Padrão
        self.headers = {
            "apikey": self.token,
            "token": self.token, # Redundância para compatibilidade
            "Content-Type": "application/json"
        }

    def _persistir_credenciais_iniciais(self):
        """Salva as credenciais fixas no banco de forma segura"""
        try:
            if not InstanciaZap.objects.exists():
                InstanciaZap.objects.create(
                    instancia_id=FIXED_ID,
                    token=FIXED_TOKEN,
                    nome_operador="Sistema (Config Auto)",
                    conectado=False
                )
        except Exception as e:
            logger.warning(f"[UAZAPI] Erro não-crítico ao persistir credenciais: {e}")

    # =========================================================================
    # CONEXÃO E STATUS (CORRIGIDO PARA POST)
    # =========================================================================

    def obter_qr_code(self):
        """
        Gera QR Code.
        CORREÇÃO SÊNIOR: Tenta POST e depois GET para garantir compatibilidade
        com qualquer versão do servidor dedicado.
        """
        # Endpoint padrão com ID (Formato mais seguro para dedicados)
        endpoint = f"{self.base_url}/instance/connect/{self.instance_id}"
        
        try:
            logger.info(f"[UAZAPI] Tentativa 1 (POST) em: {endpoint}")
            
            # 1. Tenta via POST (Padrão Documentação Nova)
            response = requests.post(endpoint, json={}, headers=self.headers, timeout=20)

            # 2. Se o servidor disser que a rota não existe (404) ou método errado (405)
            # Tenta via GET (Padrão Legado/Evolution V1)
            if response.status_code in [404, 405]:
                logger.warning(f"[UAZAPI] POST falhou ({response.status_code}). Tentando GET (Legado)...")
                response = requests.get(endpoint, headers=self.headers, timeout=20)

            # 3. Análise Final
            if response.status_code != 200:
                msg_erro = f"Erro API {response.status_code}: {response.text}"
                logger.error(f"[UAZAPI] Falha de conexão: {msg_erro}")
                
                # Se persistir o 404, a instância wckRx6 realmente não existe no servidor
                if response.status_code == 404:
                    return {"error": True, "details": f"Instância '{self.instance_id}' não encontrada no servidor."}
                
                return {"error": True, "details": msg_erro}

            dados = response.json()
            
            # 4. Busca o QR Code (Parser Híbrido)
            qr = dados.get('base64') or dados.get('qrcode') or \
                 dados.get('instance', {}).get('qrcode') or \
                 dados.get('instance', {}).get('qr')
                 
            if qr:
                return {"qrcode": qr}
            
            return {
                "error": True, 
                "details": "Conectado, mas QR não retornado (Verifique se já está pareado).", 
                "raw": dados
            }

        except Exception as e:
            logger.error(f"[UAZAPI] Erro crítico QR: {e}")
            return {"error": True, "details": str(e)}

    def verificar_status(self):
        """Verifica se está conectado e atualiza o banco local"""
        endpoint = f"{self.base_url}/instance/connectionState/{self.instance_id}"
        try:
            response = requests.get(endpoint, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                dados = response.json()
                state = None
                
                # Parser robusto de estado
                if isinstance(dados, dict):
                    if 'instance' in dados and isinstance(dados['instance'], dict):
                        state = dados['instance'].get('state')
                    elif 'state' in dados:
                        state = dados.get('state')
                
                conectado = state in ['open', 'connected']
                self._atualizar_status_db(conectado)
                return conectado
            
            if response.status_code == 404:
                logger.warning(f"[UAZAPI] Instância {self.instance_id} não encontrada no servidor.")
                
            return False
        except Exception as e:
            logger.error(f"[UAZAPI] Erro ao verificar status: {e}")
            return False

    def desconectar_instancia(self):
        """Realiza Logout (Necessário para o botão 'Sair' funcionar)"""
        endpoint = f"{self.base_url}/instance/logout/{self.instance_id}"
        try:
            logger.info(f"[UAZAPI] Solicitando logout...")
            requests.delete(endpoint, headers=self.headers, timeout=10)
            self._atualizar_status_db(False)
            return True
        except Exception as e:
            logger.error(f"[UAZAPI] Erro no logout: {e}")
            return False

    # =========================================================================
    # ENVIO DE MENSAGENS (COM FALLBACK LEGADO PRESERVADO)
    # =========================================================================

    def enviar_texto(self, numero: str, mensagem: str):
        """Tenta enviar via endpoint novo, com fallback para legado"""
        endpoint = f"{self.base_url}/message/sendText/{self.instance_id}"
        
        payload = {
            "number": numero,
            "options": {"delay": 1200, "presence": "composing"},
            "textMessage": {"text": mensagem}
        }
        
        try:
            # Tentativa Principal
            response = requests.post(endpoint, json=payload, headers=self.headers, timeout=15)
            
            # Se a API nova falhar (404/405), aciona seu código legado
            if response.status_code in [404, 405]:
                logger.warning("[UAZAPI] Endpoint v2 falhou. Ativando fallback legado...")
                return self._enviar_texto_legado(numero, mensagem)
                
            return response.json()
        except Exception as e:
            logger.error(f"[UAZAPI] Erro envio principal: {e}")
            # Em caso de exception, também tenta o legado por garantia
            return self._enviar_texto_legado(numero, mensagem)

    def _enviar_texto_legado(self, numero, mensagem):
        """
        SEU CÓDIGO ORIGINAL DE FALLBACK.
        Útil se a API mudar a versão dos endpoints.
        """
        endpoint = f"{self.base_url}/send/text"
        payload = {"number": numero, "text": mensagem}
        try:
            logger.info("[UAZAPI] Tentando envio via endpoint legado...")
            return requests.post(endpoint, json=payload, headers=self.headers, timeout=15).json()
        except Exception as e:
            logger.error(f"[UAZAPI] Erro no fallback legado: {e}")
            return {"error": True, "details": f"Falha total (Principal + Legado): {str(e)}"}

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _atualizar_status_db(self, status):
        """Atualiza o banco sem travar a thread"""
        try:
            InstanciaZap.objects.filter(instancia_id=self.instance_id).update(conectado=status)
        except:
            pass