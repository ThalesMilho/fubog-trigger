import requests
import logging
import json
from trigger.models import InstanciaZap

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. AMBIENTE: PRODUÇÃO (CHEFE/DEDICADO)
# ==============================================================================
PROD_CONFIG = {
    "base_url": "https://servidoruazapidisparo.uazapi.com",
    "instance_id": "wckRx6",
    "token": "a2a4a60a-c343-47fc-8f09-9988106346ef",
    "nome": "PRODUÇÃO"
}

# ==============================================================================
# 2. AMBIENTE: TESTE (FREE UAZAPI) - Use este agora!
# ==============================================================================
TEST_CONFIG = {
    "base_url": "https://free.uazapi.com",
    "instance_id": "76OfvM",
    "token": "f407e517-f415-49a9-95be-22346b5bb149",
    "nome": "TESTE (Free)"
}

# 🔴 SELETOR DE AMBIENTE 🔴
# Mantenha TEST_CONFIG para os testes de hoje. Mude para PROD_CONFIG amanhã.
ACTIVE_CONFIG = TEST_CONFIG

class UazApiClient:
    def __init__(self):
        # 1. Sincronização Passiva (Não toca na API, só no Banco Local)
        self._sincronizar_banco_local()
        
        # 2. Carregamento
        instancia_db = InstanciaZap.objects.first()
        self.instance_id = instancia_db.instancia_id
        self.token = instancia_db.token
        
        # Limpeza de URL
        self.base_url = ACTIVE_CONFIG["base_url"].rstrip('/')
        
        logger.info(f"╔══════════════════════════════════════════════════╗")
        logger.info(f"║ [UAZAPI] INICIADO | MODO: {ACTIVE_CONFIG['nome']:<10}             ║")
        logger.info(f"║ ID: {self.instance_id:<36} ║")
        logger.info(f"╚══════════════════════════════════════════════════╝")

    # =========================================================================
    # GESTÃO DE ESTADO (BANCO DE DADOS)
    # =========================================================================
    
    def _sincronizar_banco_local(self):
        """
        Alinha o banco de dados com a configuração ativa.
        IMPORTANTE: Não faz chamadas de rede para evitar resetar a instância na API.
        """
        try:
            instancia_db = InstanciaZap.objects.first()
            
            # Se não existe, cria
            if not instancia_db:
                InstanciaZap.objects.create(
                    instancia_id=ACTIVE_CONFIG["instance_id"],
                    token=ACTIVE_CONFIG["token"],
                    nome_operador=f"Sistema ({ACTIVE_CONFIG['nome']})",
                    conectado=False
                )
                return

            # Se está diferente (Troca de Ambiente), atualiza
            if (instancia_db.instancia_id != ACTIVE_CONFIG["instance_id"] or 
                instancia_db.token != ACTIVE_CONFIG["token"]):
                
                logger.warning(f"[UAZAPI] ♻️ Trocando ambiente: {instancia_db.instancia_id} -> {ACTIVE_CONFIG['instance_id']}")
                instancia_db.instancia_id = ACTIVE_CONFIG["instance_id"]
                instancia_db.token = ACTIVE_CONFIG["token"]
                instancia_db.nome_operador = f"Sistema ({ACTIVE_CONFIG['nome']})"
                instancia_db.conectado = False
                instancia_db.save()
                
        except Exception as e:
            logger.error(f"[UAZAPI] Erro DB: {e}")

    def _atualizar_status_db(self, status: bool):
        try:
            InstanciaZap.objects.filter(instancia_id=self.instance_id).update(conectado=status)
        except: pass

    # =========================================================================
    # CORE: HEADERS (Omni-Channel)
    # =========================================================================

    def _get_headers(self):
        """Headers completos para garantir aceitação."""
        return {
            "apikey": self.token,            
            "token": self.token,             
            "Authorization": f"Bearer {self.token}", 
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    # =========================================================================
    # 1. VERIFICAR STATUS (BASEADO NO SEU SNIPPET JS)
    # =========================================================================

    def verificar_status(self):
        """
        Implementação exata do seu snippet JS.
        GET /instance/status (Sem ID na URL)
        """
        # A URL exata que você mandou
        endpoint = f"{self.base_url}/instance/status"
        
        try:
            # logger.debug(f"[UAZAPI] Checando status em: {endpoint}")
            response = requests.get(endpoint, headers=self._get_headers(), timeout=10)
            
            if response.status_code == 200:
                dados = response.json()
                
                # A doc diz que retorna "instance: { state: '...' }" ou direto "state"
                state = None
                if isinstance(dados, dict):
                    state = dados.get('instance', {}).get('state') or dados.get('state')
                
                # Lista de estados considerados "Conectado"
                conectado = state in ['open', 'connected']
                
                # Log para entendermos o que a API está devolvendo
                if conectado:
                    # logger.info(f"[UAZAPI] Status: CONECTADO ({state})")
                    self._atualizar_status_db(True)
                else:
                    # logger.info(f"[UAZAPI] Status: Desconectado ({state})")
                    pass
                    
                return conectado
            
            # Se der 401, o token está errado (instância sumiu ou mudou)
            if response.status_code in [401, 403]:
                logger.error(f"[UAZAPI] Status Check: Credenciais Inválidas ({response.status_code}).")
                return False

            return False
            
        except Exception as e:
            logger.error(f"[UAZAPI] Erro Status: {e}")
            return False

    # =========================================================================
    # 2. CONEXÃO (ROTEAMENTO INTELIGENTE)
    # =========================================================================

    def obter_qr_code(self):
        """Tenta rotas em ordem de modernidade"""
        rotas = [
            # 1. POST /connect (Doc Nova / JS)
            {"method": "POST", "url": f"{self.base_url}/instance/connect"},
            # 2. GET /connect/{id} (Legado Robusto)
            {"method": "GET",  "url": f"{self.base_url}/instance/connect/{self.instance_id}"},
            # 3. POST /connect/{id} (Híbrido)
            {"method": "POST", "url": f"{self.base_url}/instance/connect/{self.instance_id}"}
        ]

        headers = self._get_headers()
        last_error = ""

        for r in rotas:
            try:
                if r["method"] == "POST":
                    resp = requests.post(r["url"], json={}, headers=headers, timeout=20)
                else:
                    resp = requests.get(r["url"], headers=headers, timeout=20)

                if resp.status_code == 200:
                    logger.info(f"[UAZAPI] Conexão iniciada via {r['url']}")
                    return self._parser_qr(resp.json())
                
                if resp.status_code in [401, 403]:
                    return {"error": True, "details": "Token rejeitado. Instância existe?"}

                last_error = f"{resp.status_code}"
            except Exception as e:
                last_error = str(e)
                continue

        return {"error": True, "details": f"Falha ao obter QR. Código: {last_error}"}

    def _parser_qr(self, dados):
        qr = dados.get('base64') or dados.get('qrcode') or \
             dados.get('instance', {}).get('qrcode') or \
             dados.get('instance', {}).get('qr')
        if qr: return {"qrcode": qr}
        return {"error": True, "details": "QR não retornado (Instância já pareada?).", "raw": dados}

    # =========================================================================
    # 3. ENVIO E LOGOUT
    # =========================================================================

    def enviar_texto(self, numero: str, mensagem: str):
        # Tenta V2
        endpoint = f"{self.base_url}/message/sendText/{self.instance_id}"
        payload = {"number": numero, "options": {"delay": 1200}, "textMessage": {"text": mensagem}}
        
        try:
            r = requests.post(endpoint, json=payload, headers=self._get_headers(), timeout=15)
            if r.status_code in [200, 201]: return r.json()
        except: pass

        # Fallback V1
        return self._enviar_legado(numero, mensagem)

    def _enviar_legado(self, numero, mensagem):
        try:
            url = f"{self.base_url}/send/text"
            return requests.post(url, json={"number": numero, "text": mensagem}, headers=self._get_headers(), timeout=15).json()
        except Exception as e: return {"error": True, "details": str(e)}

    def desconectar_instancia(self):
        """Só deleta se o usuário pedir explicitamente"""
        try:
            requests.delete(f"{self.base_url}/instance/logout/{self.instance_id}", headers=self._get_headers(), timeout=10)
            self._atualizar_status_db(False)
            return True
        except: return False