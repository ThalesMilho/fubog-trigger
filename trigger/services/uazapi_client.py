import requests
import os
import logging

logger = logging.getLogger(__name__)

class UazApiClient:
    def __init__(self):
        self.base_url = os.getenv('UAZAPI_URL', 'https://free.uazapi.com')
        self.token = os.getenv('UAZAPI_TOKEN')
        self.instance = os.getenv('UAZAPI_INSTANCE')
        
        self.headers = {
            "token": self.token,
            "apikey": self.token,
            "Content-Type": "application/json"
        }

    def enviar_texto(self, numero: str, mensagem: str) -> dict:
        """
        Envia mensagem usando o endpoint padrão /send/text
        """
        endpoint = f"{self.base_url}/send/text"
        
        payload = {
            "number": numero,
            "text": mensagem,
            # "instance": self.instance 
        }

        try:
         #   print(f"--- [DEBUG] Enviando POST para: {endpoint}")
          #  print(f"--- [DEBUG] Payload: {payload}")
            
            response = requests.post(endpoint, json=payload, headers=self.headers, timeout=15)
            
           # print(f"--- [API RESPOSTA] Status: {response.status_code} | Body: {response.text}")
            
            # Tratamento especial para o erro 405 (caso mude a versão da API do nada)
            if response.status_code == 405:
                return {"error": True, "details": "Erro 405: Endpoint incorreto na API."}

            return response.json()
            
        except Exception as e:
            logger.error(f"Erro crítico: {str(e)}")
            return {"error": True, "details": str(e)}