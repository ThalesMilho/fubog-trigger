import requests
import logging
import os
from django.core.exceptions import ImproperlyConfigured
from requests.exceptions import RequestException, Timeout, ConnectionError
from typing import Dict, Any, Optional
import threading

logger = logging.getLogger(__name__)

# Custom Exceptions for WhatsApp API
class WhatsAppError(Exception):
    """Base exception for WhatsApp API errors."""
    pass

class WhatsAppAuthenticationError(WhatsAppError):
    """Raised when API credentials are invalid."""
    pass

class WhatsAppQuotaExceeded(WhatsAppError):
    """Raised when API quota is exceeded."""
    pass

class WhatsAppRateLimitError(WhatsAppError):
    """Raised when rate limit is exceeded."""
    pass

class WhatsAppUnavailableError(WhatsAppError):
    """Raised when WhatsApp service is unavailable."""
    pass

class UazApiClient:
    """
    Singleton WhatsApp API client for Windows environment.
    Thread-safe implementation with secure configuration loading.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(UazApiClient, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize client with environment configuration."""
        if self._initialized:
            return
        
        with self._lock:
            if self._initialized:
                return
            
            # Load required environment variables
            self.base_url = self._get_required_env('UAZAPI_URL').rstrip('/')
            self.instance_id = self._get_required_env('UAZAPI_INSTANCE')
            self.token = self._get_required_env('UAZAPI_TOKEN')
            
            # Validate configuration at startup
            self._validate_config()
            
            self._initialized = True
            logger.info(f"UazApiClient initialized for instance: {self.instance_id}")
    
    def _get_required_env(self, key: str) -> str:
        """Get required environment variable or raise ImproperlyConfigured."""
        value = os.getenv(key)
        if not value:
            raise ImproperlyConfigured(f"Required environment variable {key} is not set")
        return value
    
    def _validate_config(self) -> None:
        """Validate API configuration by checking connectivity."""
        try:
            health = self.check_health()
            if not health.get('healthy', False):
                logger.warning(f"API health check failed: {health.get('error', 'Unknown error')}")
        except Exception as e:
            logger.error(f"API configuration validation failed: {e}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get standardized headers for API requests."""
        return {
            "apikey": self.token,
            "token": self.token,
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def _handle_api_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response and raise appropriate exceptions."""
        try:
            data = response.json()
        except ValueError:
            data = {"error": True, "details": "Invalid JSON response"}
        
        # Map HTTP status codes to custom exceptions
        if response.status_code == 401:
            raise WhatsAppAuthenticationError("Invalid API credentials")
        elif response.status_code == 403:
            raise WhatsAppAuthenticationError("Access forbidden - check permissions")
        elif response.status_code == 429:
            raise WhatsAppRateLimitError("Rate limit exceeded")
        elif response.status_code in [500, 502, 503, 504]:
            raise WhatsAppUnavailableError(f"Service unavailable: {response.status_code}")
        elif response.status_code >= 400:
            raise WhatsAppError(f"API error: {response.status_code} - {data.get('details', 'Unknown error')}")
        
        return data
    
    def check_health(self) -> Dict[str, Any]:
        """
        Verify API connectivity and authentication.
        Returns health status and any error details.
        """
        try:
            endpoint = f"{self.base_url}/instance/status"
            response = requests.get(
                endpoint, 
                headers=self._get_headers(), 
                timeout=10
            )
            
            if response.status_code == 200:
                return {"healthy": True, "status": "connected"}
            else:
                return {"healthy": False, "error": f"HTTP {response.status_code}"}
                
        except Timeout:
            return {"healthy": False, "error": "Connection timeout"}
        except ConnectionError:
            return {"healthy": False, "error": "Connection failed"}
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    def verificar_status(self) -> bool:
        """
        Check WhatsApp connection status.
        Returns True if connected, False otherwise.
        """
        try:
            endpoint = f"{self.base_url}/instance/status"
            response = requests.get(
                endpoint, 
                headers=self._get_headers(), 
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                state = None
                
                if isinstance(data, dict):
                    state = data.get('instance', {}).get('state') or data.get('state')
                
                return state in ['open', 'connected']
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking WhatsApp status: {e}")
            return False
    
    def obter_qr_code(self) -> Dict[str, Any]:
        """
        Get QR code for WhatsApp connection.
        Returns QR code data or error information.
        """
        rotas = [
            {"method": "POST", "url": f"{self.base_url}/instance/connect"},
            {"method": "GET", "url": f"{self.base_url}/instance/connect/{self.instance_id}"},
            {"method": "POST", "url": f"{self.base_url}/instance/connect/{self.instance_id}"}
        ]
        
        headers = self._get_headers()
        last_error = ""
        
        for rota in rotas:
            try:
                if rota["method"] == "POST":
                    response = requests.post(rota["url"], json={}, headers=headers, timeout=20)
                else:
                    response = requests.get(rota["url"], headers=headers, timeout=20)
                
                if response.status_code == 200:
                    data = self._handle_api_response(response)
                    return self._parse_qr_response(data)
                
                last_error = f"HTTP {response.status_code}"
                
            except (Timeout, ConnectionError) as e:
                last_error = str(e)
                continue
            except WhatsAppError as e:
                return {"error": True, "details": str(e)}
        
        return {"error": True, "details": f"All routes failed. Last error: {last_error}"}
    
    def _parse_qr_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse QR code from API response."""
        qr = (data.get('base64') or 
              data.get('qrcode') or 
              data.get('instance', {}).get('qrcode') or 
              data.get('instance', {}).get('qr'))
        
        if qr:
            return {"qrcode": qr}
        
        return {"error": True, "details": "QR code not found", "raw": data}
    
    def enviar_texto(self, numero: str, mensagem: str) -> Dict[str, Any]:
        """
        Send text message via WhatsApp.
        Implements retry logic and proper error handling.
        """
        # Validate phone number format
        if not self._validate_phone_number(numero):
            raise ValueError(f"Invalid phone number format: {numero}")
        
        # Try modern API first, fallback to legacy
        try:
            return self._send_text_v2(numero, mensagem)
        except WhatsAppError:
            return self._send_text_legacy(numero, mensagem)
    
    def _send_text_v2(self, numero: str, mensagem: str) -> Dict[str, Any]:
        """Send text using modern API v2."""
        endpoint = f"{self.base_url}/message/sendText/{self.instance_id}"
        payload = {
            "number": numero,
            "options": {"delay": 1200},
            "textMessage": {"text": mensagem}
        }
        
        try:
            response = requests.post(
                endpoint, 
                json=payload, 
                headers=self._get_headers(), 
                timeout=15
            )
            return self._handle_api_response(response)
            
        except (Timeout, ConnectionError) as e:
            raise WhatsAppUnavailableError(f"Network error: {e}")
    
    def _send_text_legacy(self, numero: str, mensagem: str) -> Dict[str, Any]:
        """Send text using legacy API."""
        endpoint = f"{self.base_url}/send/text"
        payload = {"number": numero, "text": mensagem}
        
        try:
            response = requests.post(
                endpoint, 
                json=payload, 
                headers=self._get_headers(), 
                timeout=15
            )
            return self._handle_api_response(response)
            
        except (Timeout, ConnectionError) as e:
            raise WhatsAppUnavailableError(f"Network error: {e}")
    
    def _validate_phone_number(self, numero: str) -> bool:
        """Validate phone number format."""
        import re
        
        # Remove non-digits
        cleaned = re.sub(r'\D', '', numero)
        
        # Check if it's a valid Brazilian number (55 + DDD + number)
        if len(cleaned) < 12 or len(cleaned) > 13:
            return False
        
        # Must start with Brazil country code
        if not cleaned.startswith('55'):
            return False
        
        # DDD should be between 11 and 99 (excluding special codes)
        ddd = cleaned[2:4]
        if not (11 <= int(ddd) <= 99):
            return False
        
        return True
    
    def desconectar_instancia(self) -> bool:
        """Disconnect WhatsApp instance."""
        try:
            endpoint = f"{self.base_url}/instance/logout/{self.instance_id}"
            response = requests.delete(
                endpoint, 
                headers=self._get_headers(), 
                timeout=10
            )
            
            # Don't raise exception for logout, just return status
            return response.status_code in [200, 204]
            
        except Exception as e:
            logger.error(f"Error disconnecting instance: {e}")
            return False
