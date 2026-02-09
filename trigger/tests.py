import unittest
from unittest.mock import patch, MagicMock, Mock
from requests.exceptions import RequestException, Timeout, ConnectionError
import requests_mock
import uuid
from datetime import datetime, timedelta

from django.test import TestCase, TransactionTestCase
from django.core.exceptions import ImproperlyConfigured
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from .models import Contato, Disparo, InstanciaZap
from .services.uazapi_client import (
    UazApiClient, 
    WhatsAppError, 
    WhatsAppAuthenticationError,
    WhatsAppUnavailableError,
    WhatsAppRateLimitError
)
from .tasks import send_bulk_messages, _send_single_message, check_connection_status
from .views import dashboard, _handle_bulk_messages


class TestUazApiClient(TestCase):
    """Test suite for UazApiClient service."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'UAZAPI_URL': 'https://test.uazapi.com',
            'UAZAPI_INSTANCE': 'test-instance',
            'UAZAPI_TOKEN': 'test-token'
        })
        self.env_patcher.start()
        
        self.client = UazApiClient()
    
    def tearDown(self):
        """Clean up test environment."""
        self.env_patcher.stop()
    
    def test_init_with_missing_env_vars(self):
        """Test client initialization fails without required env vars."""
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(ImproperlyConfigured):
                UazApiClient()
    
    def test_get_headers(self):
        """Test headers are correctly formatted."""
        headers = self.client._get_headers()
        
        self.assertEqual(headers['apikey'], 'test-token')
        self.assertEqual(headers['token'], 'test-token')
        self.assertEqual(headers['Authorization'], 'Bearer test-token')
        self.assertEqual(headers['Content-Type'], 'application/json')
        self.assertEqual(headers['Accept'], 'application/json')
    
    @requests_mock.Mocker()
    def test_check_health_success(self, m):
        """Test health check with successful response."""
        m.get(
            f"{self.client.base_url}/instance/status",
            json={"instance": {"state": "open"}},
            status_code=200
        )
        
        result = self.client.check_health()
        
        self.assertTrue(result['healthy'])
        self.assertEqual(result['status'], 'connected')
    
    @requests_mock.Mocker()
    def test_check_health_failure(self, m):
        """Test health check with failed response."""
        m.get(
            f"{self.client.base_url}/instance/status",
            status_code=500
        )
        
        result = self.client.check_health()
        
        self.assertFalse(result['healthy'])
        self.assertEqual(result['error'], 'HTTP 500')
    
    @requests_mock.Mocker()
    def test_verificar_status_connected(self, m):
        """Test status check when connected."""
        m.get(
            f"{self.client.base_url}/instance/status",
            json={"instance": {"state": "open"}},
            status_code=200
        )
        
        result = self.client.verificar_status()
        
        self.assertTrue(result)
    
    @requests_mock.Mocker()
    def test_verificar_status_disconnected(self, m):
        """Test status check when disconnected."""
        m.get(
            f"{self.client.base_url}/instance/status",
            json={"instance": {"state": "closed"}},
            status_code=200
        )
        
        result = self.client.verificar_status()
        
        self.assertFalse(result)
    
    @requests_mock.Mocker()
    def test_obter_qr_code_success(self, m):
        """Test QR code generation success."""
        m.post(
            f"{self.client.base_url}/instance/connect",
            json={"qrcode": "base64qrdata"},
            status_code=200
        )
        
        result = self.client.obter_qr_code()
        
        self.assertFalse(result.get('error', False))
        self.assertEqual(result['qrcode'], 'base64qrdata')
    
    @requests_mock.Mocker()
    def test_obter_qr_code_auth_error(self, m):
        """Test QR code generation with auth error."""
        m.post(
            f"{self.client.base_url}/instance/connect",
            status_code=401
        )
        
        result = self.client.obter_qr_code()
        
        self.assertTrue(result.get('error', False))
        self.assertIn('Authentication', result['details'])
    
    @requests_mock.Mocker()
    def test_enviar_texto_success(self, m):
        """Test successful text message sending."""
        m.post(
            f"{self.client.base_url}/message/sendText/{self.client.instance_id}",
            json={"messageId": "msg123"},
            status_code=200
        )
        
        result = self.client.enviar_texto("5511999998888", "Test message")
        
        self.assertFalse(result.get('error', False))
        self.assertEqual(result['messageId'], 'msg123')
    
    @requests_mock.Mocker()
    def test_enviar_texto_api_error(self, m):
        """Test text message sending with API error."""
        m.post(
            f"{self.client.base_url}/message/sendText/{self.client.instance_id}",
            json={"error": True, "details": "Invalid number"},
            status_code=400
        )
        
        with self.assertRaises(WhatsAppError):
            self.client.enviar_texto("5511999998888", "Test message")
    
    @requests_mock.Mocker()
    def test_enviar_texto_auth_error(self, m):
        """Test text message sending with authentication error."""
        m.post(
            f"{self.client.base_url}/message/sendText/{self.client.instance_id}",
            status_code=401
        )
        
        with self.assertRaises(WhatsAppAuthenticationError):
            self.client.enviar_texto("5511999998888", "Test message")
    
    @requests_mock.Mocker()
    def test_enviar_texto_rate_limit(self, m):
        """Test text message sending with rate limit error."""
        m.post(
            f"{self.client.base_url}/message/sendText/{self.client.instance_id}",
            status_code=429
        )
        
        with self.assertRaises(WhatsAppRateLimitError):
            self.client.enviar_texto("5511999998888", "Test message")
    
    def test_validate_phone_number_valid(self):
        """Test valid phone number validation."""
        valid_numbers = [
            "5511999998888",
            "5521999997777",
            "5581999996666",
            "+5511999998888",
            "(11) 99999-8888"
        ]
        
        for number in valid_numbers:
            self.assertTrue(self.client._validate_phone_number(number))
    
    def test_validate_phone_number_invalid(self):
        """Test invalid phone number validation."""
        invalid_numbers = [
            "11999998888",  # Missing country code
            "551199999888",  # Too short
            "55119999988888",  # Too long
            "5510999998888",  # Invalid DDD
            "5499998888",  # Missing DDD
            "abc123"  # Non-numeric
        ]
        
        for number in invalid_numbers:
            self.assertFalse(self.client._validate_phone_number(number))


class TestCeleryTasks(TransactionTestCase):
    """Test suite for Celery tasks."""
    
    def setUp(self):
        """Set up test environment."""
        self.env_patcher = patch.dict('os.environ', {
            'UAZAPI_URL': 'https://test.uazapi.com',
            'UAZAPI_INSTANCE': 'test-instance',
            'UAZAPI_TOKEN': 'test-token'
        })
        self.env_patcher.start()
        
        # Create test contacts
        self.contacts = [
            Contato.objects.create(
                nome=f"Test Contact {i}",
                telefone=f"551199999888{i}"
            ) for i in range(5)
        ]
        
        self.mensagem = "Test message"
    
    def tearDown(self):
        """Clean up test environment."""
        self.env_patcher.stop()
    
    @patch('trigger.tasks.UazApiClient')
    def test_send_bulk_messages_success(self, mock_client_class):
        """Test successful bulk message sending."""
        # Mock successful API response
        mock_client = Mock()
        mock_client.enviar_texto.return_value = {"messageId": f"msg_{uuid.uuid4()}"}
        mock_client_class.return_value = mock_client
        
        # Get contact IDs
        contato_ids = [str(c.id) for c in self.contacts]
        
        # Execute task
        result = send_bulk_messages(contato_ids, self.mensagem)
        
        # Verify results
        self.assertEqual(result['successful'], 5)
        self.assertEqual(result['failed'], 0)
        self.assertEqual(result['skipped'], 0)
        
        # Verify database state
        dispatches = Disparo.objects.all()
        self.assertEqual(dispatches.count(), 5)
        
        for dispatch in dispatches:
            self.assertEqual(dispatch.status, 'ENVIADO')
            self.assertEqual(dispatch.mensagem, self.mensagem)
    
    @patch('trigger.tasks.UazApiClient')
    def test_send_bulk_messages_api_failure(self, mock_client_class):
        """Test bulk message sending with API failures."""
        # Mock API failure
        mock_client = Mock()
        mock_client.enviar_texto.return_value = {"error": True, "details": "API Error"}
        mock_client_class.return_value = mock_client
        
        contato_ids = [str(c.id) for c in self.contacts]
        
        result = send_bulk_messages(contato_ids, self.mensagem)
        
        self.assertEqual(result['successful'], 0)
        self.assertEqual(result['failed'], 5)
        
        # Verify database state
        dispatches = Disparo.objects.all()
        self.assertEqual(dispatches.count(), 5)
        
        for dispatch in dispatches:
            self.assertEqual(dispatch.status, 'FALHA')
    
    @patch('trigger.tasks.UazApiClient')
    def test_send_bulk_messages_with_retry_error(self, mock_client_class):
        """Test bulk message sending with retryable error."""
        # Mock retryable error
        mock_client = Mock()
        mock_client.enviar_texto.side_effect = WhatsAppUnavailableError("Service down")
        mock_client_class.return_value = mock_client
        
        contato_ids = [str(c.id) for c in self.contacts]
        
        # Task should raise exception for retry
        with self.assertRaises(WhatsAppUnavailableError):
            send_bulk_messages(contato_ids, self.mensagem)
    
    def test_send_bulk_messages_idempotency(self):
        """Test task idempotency - duplicate sends are skipped."""
        # Create existing successful dispatch
        contato = self.contacts[0]
        Disparo.objects.create(
            contato=contato,
            mensagem=self.mensagem,
            status='ENVIADO'
        )
        
        contato_ids = [str(contato.id)]
        
        # Mock client to track calls
        with patch('trigger.tasks.UazApiClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            result = send_bulk_messages(contato_ids, self.mensagem)
            
            # Should skip the already sent message
            self.assertEqual(result['skipped'], 1)
            self.assertEqual(result['successful'], 0)
            
            # API should not be called for already sent message
            mock_client.enviar_texto.assert_not_called()
    
    @patch('trigger.tasks.UazApiClient')
    def test_check_connection_status_success(self, mock_client_class):
        """Test connection status check success."""
        mock_client = Mock()
        mock_client.verificar_status.return_value = True
        mock_client_class.return_value = mock_client
        
        # Create instance
        InstanciaZap.objects.create(
            instancia_id="test-instance",
            token="test-token",
            nome_operador="Test",
            conectado=False
        )
        
        result = check_connection_status()
        
        self.assertTrue(result['connected'])
        
        # Verify database updated
        instancia = InstanciaZap.objects.first()
        self.assertTrue(instancia.conectado)
    
    @patch('trigger.tasks.UazApiClient')
    def test_check_connection_status_failure(self, mock_client_class):
        """Test connection status check failure."""
        mock_client = Mock()
        mock_client.verificar_status.return_value = False
        mock_client_class.return_value = mock_client
        
        # Create instance
        InstanciaZap.objects.create(
            instancia_id="test-instance",
            token="test-token",
            nome_operador="Test",
            conectado=True
        )
        
        result = check_connection_status()
        
        self.assertFalse(result['connected'])
        
        # Verify database updated
        instancia = InstanciaZap.objects.first()
        self.assertFalse(instancia.conectado)


class TestViews(TestCase):
    """Test suite for Django views."""
    
    def setUp(self):
        """Set up test environment."""
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        self.env_patcher = patch.dict('os.environ', {
            'UAZAPI_URL': 'https://test.uazapi.com',
            'UAZAPI_INSTANCE': 'test-instance',
            'UAZAPI_TOKEN': 'test-token'
        })
        self.env_patcher.start()
    
    def tearDown(self):
        """Clean up test environment."""
        self.env_patcher.stop()
    
    def test_dashboard_unauthenticated(self):
        """Test dashboard redirect for unauthenticated user."""
        response = self.client.get('/dashboard/')
        self.assertRedirects(response, '/configurar/')
    
    def test_dashboard_authenticated(self):
        """Test dashboard access for authenticated user."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)
    
    @patch('trigger.tasks.send_bulk_messages.delay')
    def test_bulk_message_dispatch(self, mock_task_delay):
        """Test bulk message task dispatch."""
        self.client.login(username='testuser', password='testpass123')
        
        # Create test contacts
        contacts = [
            Contato.objects.create(
                nome=f"Test {i}",
                telefone=f"551199999888{i}"
            ) for i in range(3)
        ]
        
        # Mock task
        mock_task = Mock()
        mock_task.id = str(uuid.uuid4())
        mock_task_delay.return_value = mock_task
        
        # Post request to send messages
        contato_ids = [str(c.id) for c in contacts]
        response = self.client.post('/dashboard/', {
            'btn_enviar': '1',
            'mensagem': 'Test message',
            'contatos_selecionados': contato_ids
        })
        
        # Verify task was dispatched
        mock_task_delay.assert_called_once()
        args, kwargs = mock_task_delay.call_args
        self.assertEqual(args[0], contato_ids)
        self.assertEqual(args[1], 'Test message')
        
        # Verify redirect
        self.assertRedirects(response, '/dashboard/')
        
        # Verify message
        messages = list(response.context['messages'])
        self.assertTrue(any('envio iniciado' in str(msg) for msg in messages))


class TestModels(TestCase):
    """Test suite for Django models."""
    
    def test_contato_model(self):
        """Test Contato model creation and string representation."""
        contato = Contato.objects.create(
            nome="Test Contact",
            telefone="5511999998888"
        )
        
        self.assertEqual(str(contato), "Test Contact (5511999998888)")
        self.assertIsNotNone(contato.criado_em)
        self.assertIsNotNone(contato.id)
    
    def test_disparo_model(self):
        """Test Disparo model creation and string representation."""
        contato = Contato.objects.create(
            nome="Test Contact",
            telefone="5511999998888"
        )
        
        disparo = Disparo.objects.create(
            contato=contato,
            mensagem="Test message",
            status='PENDENTE'
        )
        
        self.assertEqual(str(disparo), "Disparo para 5511999998888 - PENDENTE")
        self.assertEqual(disparo.status, 'PENDENTE')
        self.assertEqual(disparo.contato, contato)
    
    def test_instancia_zap_model(self):
        """Test InstanciaZap model creation and string representation."""
        instancia = InstanciaZap.objects.create(
            nome_operador="Test Operator",
            numero_telefone="5511999998888",
            instancia_id="test-instance",
            token="test-token",
            conectado=True
        )
        
        self.assertEqual(str(instancia), "Test Operator (5511999998888)")
        self.assertTrue(instancia.conectado)
        self.assertEqual(instancia.instancia_id, "test-instance")


if __name__ == '__main__':
    unittest.main()
