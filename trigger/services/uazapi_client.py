import requests
import os
import logging
from trigger.models import InstanciaZap

logger = logging.getLogger(__name__)

class UazApiClient:
    def __init__(self):
        # Lógica de credenciais mantida (Prioridade: Banco > .env)
        instancia_db = InstanciaZap.objects.first()
        
        if instancia_db and instancia_db.instancia_id and instancia_db.token:
            self.base_url = os.getenv('UAZAPI_URL', 'https://free.uazapi.com').rstrip('/')
            self.token = instancia_db.token
            self.instance_id = instancia_db.instancia_id
        else:
            self.base_url = os.getenv('UAZAPI_URL', 'https://free.uazapi.com').rstrip('/')
            self.token = os.getenv('UAZAPI_TOKEN')
            self.instance_id = os.getenv('UAZAPI_INSTANCE', 'fubog_padrao') # Fallback nome

        self.headers = {
            "token": self.token,
            "apikey": self.token,
            "Content-Type": "application/json"
        }

    # ... (métodos enviar_texto mantidos iguais) ...

    def enviar_texto(self, numero: str, mensagem: str) -> dict:
        """Envia mensagem (mantido igual ao seu arquivo atual)"""
        endpoint = f"{self.base_url}/message/sendText/{self.instance_id}"
        payload = {
            "number": numero,
            "options": {"delay": 1200, "presence": "composing"},
            "textMessage": {"text": mensagem}
        }
        try:
            response = requests.post(endpoint, json=payload, headers=self.headers, timeout=15)
            if response.status_code in [404, 405]:
                return self._enviar_texto_legado(numero, mensagem)
            return response.json()
        except Exception as e:
            logger.error(f"Erro envio: {e}")
            return {"error": True, "details": str(e)}

    def _enviar_texto_legado(self, numero, mensagem):
        """Fallback legado (mantido)"""
        endpoint = f"{self.base_url}/send/text"
        payload = {"number": numero, "text": mensagem}
        try:
            return requests.post(endpoint, json=payload, headers=self.headers, timeout=15).json()
        except Exception as e:
            return {"error": True, "details": str(e)}

    # --- AQUI ESTÁ A MÁGICA NOVA ---

    def _criar_instancia(self):
        """Tenta criar a instância na API se ela não existir"""
        endpoint = f"{self.base_url}/instance/create"
        payload = {
            "instanceName": self.instance_id,
            "token": self.token,
            "qrcode": True 
        }
        try:
            logger.info(f"Tentando criar instância: {self.instance_id}")
            logger.debug(f"Payload: {payload}")
            response = requests.post(endpoint, json=payload, headers=self.headers, timeout=15)
            logger.debug(f"Resposta create: {response.status_code} - {response.text[:200]}")
            return response.status_code in [200, 201]
        except Exception as e:
            logger.error(f"Erro ao criar instância: {e}")
            return False

    def obter_qr_code(self):
        """
        Busca o QR Code. Se der 404, cria a instância e tenta de novo.
        Retorna dict com QR ou erro.
        """
        endpoint = f"{self.base_url}/instance/connect/{self.instance_id}"
        
        try:
            logger.info(f"Buscando QR para: {self.instance_id}")
            logger.debug(f"Endpoint (GET): {endpoint}")

            # PRIMEIRA TENTATIVA: usar o endpoint documentado POST /instance/connect
            # Alguns providers aceitam POST /instance/connect (sem instance id no path).
            try:
                post_endpoint = f"{self.base_url}/instance/connect"
                logger.info(f"Tentando POST inicial em: {post_endpoint}")
                post_resp = requests.post(post_endpoint, headers=self.headers, json={"instanceName": self.instance_id}, timeout=15)
                logger.debug(f"POST inicial response: {post_resp.status_code} - {post_resp.text[:300]}")
                # Alguns provedores retornam 409 com payload contendo a instância já existente
                if post_resp.status_code in (200, 201, 202, 409):
                    logger.info(f"POST inicial retornou {post_resp.status_code}, usando essa resposta")
                    try:
                        data = post_resp.json()
                    except Exception:
                        data = {"status_code": post_resp.status_code}
                    # Sincroniza DB se possível
                    try:
                        self._sync_instance_from_api(data)
                    except Exception as e:
                        logger.debug(f"Erro ao sincronizar após POST inicial: {e}")
                    return data
                if post_resp.status_code == 401:
                    token_preview = (self.token[:8] + '...') if self.token else 'N/A'
                    logger.error(f"POST inicial Unauthorized (401). Token prefix: {token_preview}")
                    return {"error": True, "details": "Unauthorized (401): token inválido ou sem permissão."}
            except Exception:
                logger.debug("POST inicial /instance/connect falhou; prosseguindo com GET")

            # 2. Tenta buscar o QR (GET no path com instance_id)
            response = requests.get(endpoint, headers=self.headers, timeout=15)
            logger.debug(f"GET response: {response.status_code}")

            # 2. Se der 404, a instância não existe. Vamos criar!
            if response.status_code == 404:
                logger.warning(f"Instância não encontrada (404). Tentando criar...")
                if self._criar_instancia():
                    logger.info(f"Instância criada. Buscando QR novamente...")
                    # Se criou com sucesso, tenta buscar o QR de novo
                    response = requests.get(endpoint, headers=self.headers, timeout=15)
                    logger.debug(f"GET retry response: {response.status_code}")
                else:
                    logger.error(f"Falha ao criar instância")
                    return {"error": True, "details": "Falha ao criar instância automaticamente."}

            # 3. Fallback para API que exige POST no connect (Erro 405)
            if response.status_code == 405:
                logger.info(f"Erro 405. Tentando POST em vez de GET...")
                response = requests.post(endpoint, json={}, headers=self.headers, timeout=15)
                logger.debug(f"POST response: {response.status_code}")

            # 4. Se a instância já existe (400), apenas busca o QR
            if response.status_code == 400:
                logger.info("Instância já existe (400). Tentando GET novamente...")
                response = requests.get(endpoint, headers=self.headers, timeout=15)
                logger.debug(f"GET after 400: {response.status_code}")

            if response.status_code == 200:
                dados = response.json()
                logger.info(f"QR obtido com sucesso. Chaves: {list(dados.keys())}")
                try:
                    # Tenta sincronizar com o banco local caso a API retorne id/token
                    self._sync_instance_from_api(dados)
                except Exception as e:
                    logger.debug(f"Falha ao sincronizar InstanciaZap: {e}")
                return dados

            # 401 -> token inválido ou não autorizado
            if response.status_code == 401:
                token_preview = (self.token[:8] + '...') if self.token else 'N/A'
                logger.error(f"Unauthorized (401) ao criar/consultar instância. Token prefix: {token_preview}")
                return {"error": True, "details": "Unauthorized (401): token inválido ou sem permissão."}

            # Última tentativa: usar o endpoint POST documentado /instance/connect (sem instance_id no path)
            try:
                fallback_endpoint = f"{self.base_url}/instance/connect"
                logger.info(f"Tentando fallback POST em: {fallback_endpoint}")
                fb_resp = requests.post(fallback_endpoint, headers=self.headers, json={"instanceName": self.instance_id}, timeout=15)
                logger.debug(f"Fallback POST response: {fb_resp.status_code} - {fb_resp.text[:300]}")
                if fb_resp.status_code == 200:
                    return fb_resp.json()
                if fb_resp.status_code == 401:
                    token_preview = (self.token[:8] + '...') if self.token else 'N/A'
                    logger.error(f"Fallback também retornou 401. Token prefix: {token_preview}")
                    return {"error": True, "details": "Unauthorized (401) no fallback: token inválido."}
            except Exception as ee:
                logger.debug(f"Erro no fallback POST /instance/connect: {ee}")

            logger.error(f"Erro final QR: {response.status_code} | {response.text[:500]}")
            return {"error": True, "details": f"Erro da API: {response.status_code}"}

        except Exception as e:
            logger.error(f"Erro crítico QR: {str(e)}")
            return {"error": True, "details": str(e)}

    def _sync_instance_from_api(self, dados: dict):
        """
        Se a API retornar identificadores (id, token, instanceId, instanceToken, etc),
        atualiza o registro `InstanciaZap` no banco para manter o app sincronizado.
        """
        # procura por possíveis campos que contenham id/token
        instance_id = None
        token = None

        # caminhos comuns
        if isinstance(dados, dict):
            instance_id = dados.get('id') or dados.get('instanceId') or dados.get('instance', {}).get('id')
            token = dados.get('token') or dados.get('instanceToken') or dados.get('instance', {}).get('token')

        # Alguns provedores retornam dentro de 'data' ou 'result'
        if not instance_id and isinstance(dados.get('data'), dict):
            instance_id = dados['data'].get('id') or dados['data'].get('instanceId')
            token = token or dados['data'].get('token')

        if not instance_id and isinstance(dados.get('result'), dict):
            instance_id = instance_id or dados['result'].get('id')
            token = token or dados['result'].get('token')

        # Normalize token type
        if token and not isinstance(token, str):
            try:
                token = str(token)
            except:
                token = None

        if not instance_id and not token:
            logger.debug("Nenhum id/token encontrado na resposta para sincronizar.")
            return

        # Atualiza ou cria o registro no banco
        try:
            instancia_db = InstanciaZap.objects.first()
            if instancia_db:
                if instance_id:
                    instancia_db.instancia_id = instance_id
                if token:
                    instancia_db.token = token
                instancia_db.conectado = True
                instancia_db.save()
                # Atualiza também o instance_id usado pelo cliente em memória
                if instance_id:
                    self.instance_id = instance_id
                logger.info(f"InstanciaZap atualizada: {instancia_db.instancia_id} (conectado=True)")
            else:
                InstanciaZap.objects.create(
                    nome_operador='auto-sync',
                    numero_telefone='',
                    instancia_id=instance_id or self.instance_id,
                    token=token or self.token,
                    conectado=True
                )
                logger.info("InstanciaZap criada automaticamente a partir da resposta da API.")
        except Exception as e:
            logger.error(f"Erro ao gravar InstanciaZap no banco: {e}")

    def verificar_status(self):
        """Verifica o status da conexão com mais logs"""
        # Tenta verificar usando o instance_id atual; se 404, tenta recarregar do BD e retry
        endpoint = f"{self.base_url}/instance/connectionState/{self.instance_id}"
        try:
            logger.debug(f"Verificando status: {endpoint}")
            response = requests.get(endpoint, headers=self.headers, timeout=5)
            logger.debug(f"Status response: {response.status_code}")

            if response.status_code == 200:
                dados = response.json()
                logger.debug(f"Dados status: {dados}")
                state = dados.get('instance', {}).get('state') or dados.get('state')
                conectado = state in ['open', 'connected']
                logger.info(f"Estado da instância: {state} -> {conectado}")
                return conectado

            # Se 404, pode ser que o ID que estamos usando não seja o interno da API.
            if response.status_code == 404:
                logger.warning("Status check retornou 404 — tentando recarregar instancia do BD e refazer a verificação")
                try:
                    instancia_db = InstanciaZap.objects.first()
                    if instancia_db and instancia_db.instancia_id and instancia_db.instancia_id != self.instance_id:
                        logger.debug(f"Atualizando instance_id do client: {self.instance_id} -> {instancia_db.instancia_id}")
                        self.instance_id = instancia_db.instancia_id
                        endpoint2 = f"{self.base_url}/instance/connectionState/{self.instance_id}"
                        logger.debug(f"Tentando novo endpoint de status: {endpoint2}")
                        resp2 = requests.get(endpoint2, headers=self.headers, timeout=5)
                        logger.debug(f"Retry status response: {resp2.status_code}")
                        if resp2.status_code == 200:
                            dados = resp2.json()
                            state = dados.get('instance', {}).get('state') or dados.get('state')
                            conectado = state in ['open', 'connected']
                            logger.info(f"Estado da instância (retry): {state} -> {conectado}")
                            return conectado
                except Exception as e2:
                    logger.debug(f"Erro ao re-tentar status com id recarregado: {e2}")

            logger.warning(f"Status check retornou {response.status_code}")
            return False
        except Exception as e:
            logger.error(f"Erro ao verificar status: {e}")
            return False