import requests
import logging
import json
import os
from trigger.models import InstanciaZap

logger = logging.getLogger(__name__)

# --- CREDENCIAIS MESTRE (HARDCODED) ---
# Configuradas para seu servidor dedicado
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
            self._persistir_credenciais()

        logger.info(f"[UAZAPI] Cliente iniciado via {self.origem}. ID: {self.instance_id}")

    def _persistir_credenciais(self):
        """Salva as credenciais iniciais no banco se estiver vazio"""
        try:
            if not InstanciaZap.objects.exists():
                InstanciaZap.objects.create(
                    instancia_id=FIXED_ID, 
                    token=FIXED_TOKEN,
                    nome_operador="Sistema (Auto)", 
                    conectado=False
                )
        except Exception as e:
            logger.warning(f"[UAZAPI] Erro não bloqueante ao persistir: {e}")

    # =========================================================================
    # CORE: GESTÃO DE HEADERS (A CORREÇÃO DO SNIPPET JS)
    # =========================================================================
    def _get_headers(self):
        """
        Retorna headers 'blindados'. 
        O seu snippet JS mostrou que o servidor espera a chave 'token' (minúsculo).
        Enviamos variações para garantir.
        """
        return {
            "token": self.token,         # Chave do seu snippet JS
            "apikey": self.token,        # Padrão Evolution
            "Authorization": f"Bearer {self.token}", # Padrão JWT (por garantia)
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    # =========================================================================
    # 1. CONEXÃO (QR CODE) - ESTRATÉGIA MULTI-ROTA
    # =========================================================================
    def obter_qr_code(self):
        """
        Tenta obter o QR Code testando a rota da Doc (sem ID) e a Rota Padrão (com ID).
        """
        # Endpoint 1: Padrão Doc JS (POST /instance/connect)
        endpoint_doc = f"{self.base_url}/instance/connect"
        
        # Endpoint 2: Padrão Legado/Dedicado (POST /instance/connect/{id})
        endpoint_legacy = f"{self.base_url}/instance/connect/{self.instance_id}"

        # Tenta a rota da documentação primeiro
        try:
            logger.info(f"[UAZAPI] Tentando Rota DOC: {endpoint_doc}")
            response = requests.post(endpoint_doc, json={}, headers=self._get_headers(), timeout=15)
            
            # Se der 404, o servidor não reconhece essa rota -> Tenta Legado
            if response.status_code == 404:
                logger.warning("[UAZAPI] Rota Doc falhou (404). Tentando Rota Legado...")
                return self._tentar_connect_legacy(endpoint_legacy)
            
            # Se funcionar ou der outro erro, processa
            return self._processar_resposta_qr(response)

        except Exception as e:
            logger.error(f"[UAZAPI] Erro na Rota Doc: {e}")
            # Em caso de crash, tenta legado
            return self._tentar_connect_legacy(endpoint_legacy)

    def _tentar_connect_legacy(self, endpoint):
        """Tentativa secundária com ID na URL"""
        try:
            logger.info(f"[UAZAPI] Tentando Rota Legado: {endpoint}")
            response = requests.post(endpoint, json={}, headers=self._get_headers(), timeout=15)
            return self._processar_resposta_qr(response)
        except Exception as e:
            return {"error": True, "details": f"Falha total conexão: {str(e)}"}

    def _processar_resposta_qr(self, response):
        """Extrai QR Code de qualquer resposta válida"""
        if response.status_code != 200:
             return {"error": True, "details": f"Erro API {response.status_code}: {response.text}"}

        dados = response.json()
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
    # 2. STATUS - ESTRATÉGIA MULTI-ROTA
    # =========================================================================
    def verificar_status(self):
        """Tenta verificar status em múltiplas rotas"""
        urls_to_test = [
            f"{self.base_url}/instance/status",                        # Doc JS (GET)
            f"{self.base_url}/instance/connectionState/{self.instance_id}" # Legado (GET)
        ]

        for url in urls_to_test:
            try:
                response = requests.get(url, headers=self._get_headers(), timeout=10)
                if response.status_code == 200:
                    dados = response.json()
                    state = None
                    if isinstance(dados, dict):
                        if 'instance' in dados: state = dados['instance'].get('state')
                        elif 'state' in dados: state = dados.get('state')
                    
                    conectado = state in ['open', 'connected']
                    if conectado: self._atualizar_db(True)
                    return conectado
            except:
                continue
        
        return False

    # =========================================================================
    # 3. MENSAGEM (SEU FALLBACK MANTIDO)
    # =========================================================================
    def enviar_texto(self, numero: str, mensagem: str):
        endpoint = f"{self.base_url}/message/sendText/{self.instance_id}"
        payload = {
            "number": numero, 
            "options": {"delay": 1200, "presence": "composing"},
            "textMessage": {"text": mensagem}
        }
        try:
            response = requests.post(endpoint, json=payload, headers=self._get_headers(), timeout=15)
            if response.status_code not in [200, 201]:
                logger.warning("[UAZAPI] Envio V2 falhou. Usando Legado...")
                return self._enviar_texto_legado(numero, mensagem)
            return response.json()
        except:
            return self._enviar_texto_legado(numero, mensagem)

    def _enviar_texto_legado(self, numero, mensagem):
        """Seu código original de fallback"""
        endpoint = f"{self.base_url}/send/text"
        try:
            return requests.post(endpoint, json={"number": numero, "text": mensagem}, headers=self._get_headers(), timeout=15).json()
        except Exception as e:
            return {"error": True, "details": str(e)}

    # =========================================================================
    # 4. LOGOUT E HELPERS
    # =========================================================================
    def desconectar_instancia(self):
        try:
            requests.delete(f"{self.base_url}/instance/logout/{self.instance_id}", headers=self._get_headers(), timeout=10)
            self._atualizar_db(False)
            return True
        except:
            return False

    def _atualizar_db(self, status):
        try: InstanciaZap.objects.filter(instancia_id=self.instance_id).update(conectado=status)
        except: pass