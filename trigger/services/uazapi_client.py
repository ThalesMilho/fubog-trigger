import requests
import logging
import os
from trigger.models import InstanciaZap

logger = logging.getLogger(__name__)

# --- CREDENCIAIS "MASTER" (Seu porto seguro) ---
FIXED_URL = "https://servidoruazapidisparo.uazapi.com"
FIXED_ID = "wckRx6"
FIXED_TOKEN = "a2a4a60a-c343-47fc-8f09-9988106346ef"

class UazApiClient:
    def __init__(self):
        self.base_url = FIXED_URL.rstrip('/')
        
        # LÓGICA INTELIGENTE:
        # 1. Verifica se já existe algo editado no Admin (Banco de Dados)
        instancia_db = InstanciaZap.objects.first()
        
        if instancia_db and instancia_db.instancia_id:
            # Se você editou no Admin, o código RESPEITA sua edição
            self.instance_id = instancia_db.instancia_id
            self.token = instancia_db.token
            logger.info(f"[UAZAPI] Usando configuração do Admin (Banco): {self.instance_id}")
        else:
            # 2. Se o banco estiver vazio, usa o HARDCODE e SALVA no banco
            self.instance_id = FIXED_ID
            self.token = FIXED_TOKEN
            logger.info(f"[UAZAPI] Banco vazio. Usando credenciais fixas: {self.instance_id}")
            
            # AQUI ESTÁ A MÁGICA DA REVERSIBILIDADE:
            # Salvamos esses dados no banco agora. 
            # Assim, quando você abrir o Admin, eles estarão lá para você editar!
            try:
                InstanciaZap.objects.create(
                    instancia_id=FIXED_ID,
                    token=FIXED_TOKEN,
                    nome_operador="Sistema (Config Automática)",
                    conectado=False
                )
                logger.info("[UAZAPI] Credenciais fixas salvas no Admin para edição futura.")
            except Exception as e:
                logger.warning(f"[UAZAPI] Não foi possível salvar no banco (talvez lock): {e}")

        # Configuração dos Headers
        self.headers = {
            "apikey": self.token,
            "token": self.token, 
            "Content-Type": "application/json"
        }

    # =========================================================================
    # MÉTODOS ROBUSTOS (PRESERVADOS DO SEU CÓDIGO)
    # =========================================================================

    def verificar_status(self):
        endpoint = f"{self.base_url}/instance/connectionState/{self.instance_id}"
        try:
            response = requests.get(endpoint, headers=self.headers, timeout=10)
            
            # Se não existir (404), tenta criar
            if response.status_code == 404:
                self._criar_instancia()
                return False # Retorna False para forçar reload ou nova verificação

            if response.status_code == 200:
                dados = response.json()
                state = None
                if isinstance(dados, dict):
                    if 'instance' in dados and isinstance(dados['instance'], dict):
                        state = dados['instance'].get('state')
                    elif 'state' in dados:
                        state = dados.get('state')
                
                conectado = state in ['open', 'connected']
                
                # Atualiza o status no banco para ficar bonitinho no Admin
                self._atualizar_status_db(conectado)
                return conectado
            
            return False
        except Exception as e:
            logger.error(f"[UAZAPI] Erro status: {e}")
            return False

    def desconectar_instancia(self):
        """Logout para o botão 'Sair' funcionar"""
        endpoint = f"{self.base_url}/instance/logout/{self.instance_id}"
        try:
            requests.delete(endpoint, headers=self.headers, timeout=10)
            self._atualizar_status_db(False)
            return True
        except:
            return False

    def obter_qr_code(self):
        endpoint = f"{self.base_url}/instance/connect/{self.instance_id}"
        try:
            response = requests.get(endpoint, headers=self.headers, timeout=15)
            
            if response.status_code == 404:
                self._criar_instancia()
                response = requests.get(endpoint, headers=self.headers, timeout=15)

            if response.status_code != 200:
                return {"error": True, "details": f"Erro HTTP {response.status_code}"}

            dados = response.json()
            
            # Parser robusto
            qr = dados.get('base64') or dados.get('qrcode') or \
                 dados.get('instance', {}).get('qrcode') or \
                 dados.get('instance', {}).get('qr')
                 
            if qr:
                return {"qrcode": qr}
            
            return {"error": True, "details": "QR Code não encontrado (Instância já conectada?)", "raw": dados}
        except Exception as e:
            return {"error": True, "details": str(e)}

    def _criar_instancia(self):
        """Auto-Cura: Cria a instância se não existir"""
        endpoint = f"{self.base_url}/instance/create"
        payload = {
            "instanceName": self.instance_id,
            "token": self.token,
            "qrcode": True
        }
        try:
            requests.post(endpoint, json=payload, headers=self.headers, timeout=10)
        except:
            pass

    def enviar_texto(self, numero: str, mensagem: str):
        endpoint = f"{self.base_url}/message/sendText/{self.instance_id}"
        payload = {
            "number": numero,
            "options": {"delay": 1200, "presence": "composing"},
            "textMessage": {"text": mensagem}
        }
        try:
            return requests.post(endpoint, json=payload, headers=self.headers, timeout=15).json()
        except Exception as e:
            return {"error": True, "details": str(e)}

    def _atualizar_status_db(self, status):
        """Helper para manter o Admin sincronizado com a realidade"""
        try:
            InstanciaZap.objects.filter(instancia_id=self.instance_id).update(conectado=status)
        except:
            pass