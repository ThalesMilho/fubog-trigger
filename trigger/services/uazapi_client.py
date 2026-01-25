import requests
import logging
import os
from trigger.models import InstanciaZap

logger = logging.getLogger(__name__)

# --- CREDENCIAIS FIXAS (SERVIDOR DEDICADO) ---
# Seus dados de produção
FIXED_URL = "https://servidoruazapidisparo.uazapi.com"
FIXED_ID = "wckRx6"
FIXED_TOKEN = "a2a4a60a-c343-47fc-8f09-9988106346ef"

class UazApiClient:
    def __init__(self):
        # 1. Configuração da URL Base
        self.base_url = FIXED_URL.rstrip('/')
        
        # 2. Gestão de Credenciais (Híbrido: Banco > Hardcode)
        instancia_db = InstanciaZap.objects.first()
        
        if instancia_db and instancia_db.instancia_id:
            # Prioridade 1: O que estiver editado no Admin
            self.instance_id = instancia_db.instancia_id
            self.token = instancia_db.token
            self.origem = "Banco de Dados (Admin)"
        else:
            # Prioridade 2: Hardcoded (Setup Inicial)
            self.instance_id = FIXED_ID
            self.token = FIXED_TOKEN
            self.origem = "Hardcoded (Fixo)"
            # Persistência: Salva no banco para aparecer no Admin
            self._persistir_credenciais()

        logger.info(f"[UAZAPI] Cliente iniciado via {self.origem}. ID: {self.instance_id}")

        # Headers de Autenticação (Chave Mestra)
        self.headers = {
            "apikey": self.token,
            "token": self.token, # Redundância para compatibilidade
            "Content-Type": "application/json"
        }

    def _persistir_credenciais(self):
        """Salva as credenciais iniciais no banco"""
        try:
            if not InstanciaZap.objects.exists():
                InstanciaZap.objects.create(
                    instancia_id=FIXED_ID, token=FIXED_TOKEN,
                    nome_operador="Sistema", conectado=False
                )
        except Exception as e:
            logger.warning(f"[UAZAPI] Erro ao persistir credenciais: {e}")

    # =========================================================================
    # 1. CONEXÃO (QR CODE) - ESTRATÉGIA DUPLA ROBUSTA
    # =========================================================================

    def obter_qr_code(self):
        """
        Gera QR Code.
        Estratégia 1: POST /instance/connect (Documentação JS)
        Estratégia 2: POST /instance/connect/{id} (Fallback Padrão)
        """
        # TENTATIVA 1: Padrão da sua Documentação (Sem ID na URL)
        endpoint_v1 = f"{self.base_url}/instance/connect"
        
        try:
            logger.info(f"[UAZAPI] Solicitando QR (Tentativa 1): {endpoint_v1}")
            response = requests.post(endpoint_v1, json={}, headers=self.headers, timeout=20)

            # Se der 404, significa que a rota sem ID não existe neste servidor.
            # Acionamos o Fallback.
            if response.status_code == 404:
                logger.warning("[UAZAPI] Rota V1 deu 404. Tentando rota com ID...")
                return self._obter_qr_code_com_id()

            if response.status_code != 200:
                return {"error": True, "details": f"Erro API {response.status_code}: {response.text}"}

            return self._processar_resposta_qr(response.json())

        except Exception as e:
            logger.error(f"[UAZAPI] Erro na Tentativa 1: {e}")
            # Em caso de erro de rede, tenta a segunda rota por garantia
            return self._obter_qr_code_com_id()

    def _obter_qr_code_com_id(self):
        """Método auxiliar de Fallback (Com ID na URL)"""
        endpoint_v2 = f"{self.base_url}/instance/connect/{self.instance_id}"
        try:
            logger.info(f"[UAZAPI] Solicitando QR (Tentativa 2): {endpoint_v2}")
            response = requests.post(endpoint_v2, json={}, headers=self.headers, timeout=20)
            
            if response.status_code != 200:
                return {"error": True, "details": f"Erro Fallback {response.status_code}: {response.text}"}
            
            return self._processar_resposta_qr(response.json())
        except Exception as e:
            return {"error": True, "details": f"Falha total na conexão: {str(e)}"}

    def _processar_resposta_qr(self, dados):
        """Parser unificado para extrair o QR Code do JSON"""
        qr = dados.get('base64') or dados.get('qrcode') or \
             dados.get('instance', {}).get('qrcode') or \
             dados.get('instance', {}).get('qr')
             
        if qr:
            return {"qrcode": qr}
        
        return {
            "error": True, 
            "details": "Conectado. QR não retornado (Instância já ativa?).", 
            "raw": dados
        }

    # =========================================================================
    # 2. STATUS - ESTRATÉGIA DUPLA
    # =========================================================================

    def verificar_status(self):
        """
        Verifica status tentando endpoint sem ID primeiro, depois com ID.
        """
        # Tenta endpoint da doc (sem ID)
        endpoint = f"{self.base_url}/instance/status"
        if self._check_status_endpoint(endpoint):
            return True
            
        # Tenta endpoint padrão (com ID)
        endpoint_fallback = f"{self.base_url}/instance/connectionState/{self.instance_id}"
        if self._check_status_endpoint(endpoint_fallback):
            return True
            
        return False

    def _check_status_endpoint(self, endpoint):
        """Helper para testar um endpoint de status"""
        try:
            response = requests.get(endpoint, headers=self.headers, timeout=10)
            if response.status_code == 200:
                dados = response.json()
                state = None
                if isinstance(dados, dict):
                    if 'instance' in dados: state = dados['instance'].get('state')
                    elif 'state' in dados: state = dados.get('state')
                
                conectado = state in ['open', 'connected']
                if conectado:
                    self._atualizar_db(True)
                return conectado
        except:
            pass
        return False

    # =========================================================================
    # 3. LOGOUT
    # =========================================================================

    def desconectar_instancia(self):
        """Tenta logout com e sem ID"""
        endpoints = [
            f"{self.base_url}/instance/logout/{self.instance_id}",
            f"{self.base_url}/instance/logout"
        ]
        
        for ep in endpoints:
            try:
                requests.delete(ep, headers=self.headers, timeout=10)
                self._atualizar_db(False)
                return True
            except:
                continue
        return False

    # =========================================================================
    # 4. ENVIO DE MENSAGENS (COM SEU FALLBACK LEGADO PRESERVADO)
    # =========================================================================

    def enviar_texto(self, numero: str, mensagem: str):
        """
        Envia mensagem.
        Tenta endpoint V2 (com ID). Se falhar, usa o método legado.
        """
        endpoint = f"{self.base_url}/message/sendText/{self.instance_id}"
        
        payload = {
            "number": numero, 
            "options": {"delay": 1200, "presence": "composing"},
            "textMessage": {"text": mensagem}
        }
        
        try:
            response = requests.post(endpoint, json=payload, headers=self.headers, timeout=15)
            
            # Se a API nova falhar (404/405), vai para o legado imediatamente
            if response.status_code in [404, 405]:
                logger.warning("[UAZAPI] Envio V2 falhou. Usando método Legado...")
                return self._enviar_texto_legado(numero, mensagem)
                
            return response.json()
        except Exception as e:
            logger.error(f"[UAZAPI] Erro envio: {e}")
            return self._enviar_texto_legado(numero, mensagem)

    def _enviar_texto_legado(self, numero, mensagem):
        """
        SEU CÓDIGO ORIGINAL PRESERVADO.
        Endpoint: /send/text
        """
        endpoint = f"{self.base_url}/send/text"
        try:
            payload = {"number": numero, "text": mensagem}
            return requests.post(endpoint, json=payload, headers=self.headers, timeout=15).json()
        except Exception as e:
            return {"error": True, "details": str(e)}

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _atualizar_db(self, status):
        try: InstanciaZap.objects.filter(instancia_id=self.instance_id).update(conectado=status)
        except: pass