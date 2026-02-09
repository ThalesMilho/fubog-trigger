import logging
from celery import Celery
from django.db import transaction
from django.conf import settings
from requests.exceptions import RequestException, Timeout, ConnectionError
from typing import List, Dict, Any
import uuid

from .models import Disparo, Contato, InstanciaZap
from .services.uazapi_client import (
    UazApiClient, 
    WhatsAppError, 
    WhatsAppUnavailableError,
    WhatsAppAuthenticationError,
    WhatsAppRateLimitError
)

logger = logging.getLogger(__name__)

# Configure Celery
app = Celery('fubog_trigger')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

@app.task(
    bind=True,
    name='trigger.enviar_mensagem_broadcast',
    rate_limit='10/m',  # 10 messages per minute to avoid WhatsApp bans
    autoretry_for=(RequestException, Timeout, ConnectionError, WhatsAppUnavailableError),
    retry_backoff=True,
    retry_backoff_max=300,  # 5 minutes max backoff
    retry_kwargs={'max_retries': 3},
    max_retries=3
)
def enviar_mensagem_broadcast(self, disparo_id: str) -> Dict[str, Any]:
    """
    Send individual WhatsApp message - Windows compatible implementation.
    
    Args:
        disparo_id: UUID of the dispatch record to process
    
    Returns:
        Dict with processing results
    """
    logger.info(f"Processing message dispatch {disparo_id}")
    
    try:
        # Use atomic transaction to prevent race conditions
        with transaction.atomic():
            # Lock the dispatch record to prevent concurrent processing
            disparo = Disparo.objects.select_for_update().get(id=disparo_id)
            
            # Check if already processed (idempotency)
            if disparo.status != 'PENDENTE':
                logger.info(f"Dispatch {disparo_id} already processed with status: {disparo.status}")
                return {
                    'disparo_id': disparo_id,
                    'status': disparo.status,
                    'message': 'Already processed'
                }
            
            # Mark as processing
            disparo.status = 'PROCESSANDO'
            disparo.save()
        
        # Send message via WhatsApp API
        success = _send_single_message(disparo)
        
        if success:
            return {
                'disparo_id': disparo_id,
                'status': 'ENVIADO',
                'message': 'Message sent successfully'
            }
        else:
            return {
                'disparo_id': disparo_id,
                'status': 'FALHA',
                'message': 'Failed to send message'
            }
            
    except Disparo.DoesNotExist:
        logger.error(f"Dispatch {disparo_id} not found")
        return {
            'disparo_id': disparo_id,
            'status': 'ERROR',
            'message': 'Dispatch not found'
        }
    except Exception as e:
        logger.error(f"Error processing dispatch {disparo_id}: {e}")
        
        # Mark as failed if possible
        try:
            with transaction.atomic():
                disparo = Disparo.objects.select_for_update().get(id=disparo_id)
                disparo.status = 'FALHA'
                disparo.log_api = {'error': 'Processing error', 'details': str(e)}
                disparo.save()
        except:
            pass
        
        return {
            'disparo_id': disparo_id,
            'status': 'FALHA',
            'message': str(e)
        }

@app.task(
    bind=True,
    name='trigger.send_bulk_messages',
    rate_limit='10/m',  # 10 messages per minute to avoid WhatsApp bans
    autoretry_for=(RequestException, Timeout, ConnectionError, WhatsAppUnavailableError),
    retry_backoff=True,
    retry_backoff_max=300,  # 5 minutes max backoff
    retry_kwargs={'max_retries': 3},
    max_retries=3
)
def send_bulk_messages(self, contato_ids: List[str], mensagem: str, task_id: str = None) -> Dict[str, Any]:
    """
    Bulk message sending task - Windows compatible implementation.
    Creates individual dispatch tasks for each contact.
    
    Args:
        contato_ids: List of contact UUIDs to send messages to
        mensagem: Message content to send
        task_id: Unique task identifier for tracking
    
    Returns:
        Dict with task results and statistics
    """
    if not task_id:
        task_id = str(uuid.uuid4())
    
    logger.info(f"Starting bulk message task {task_id} for {len(contato_ids)} contacts")
    
    # Initialize counters
    results = {
        'task_id': task_id,
        'total_contacts': len(contato_ids),
        'dispatched': 0,
        'failed': 0,
        'errors': []
    }
    
    # Use atomic transaction to prevent race conditions
    with transaction.atomic():
        # Lock contacts to prevent concurrent processing
        contacts = Contato.objects.filter(
            id__in=contato_ids
        ).select_for_update().order_by('criado_em')
        
        # Validate we found all contacts
        if contacts.count() != len(contato_ids):
            missing = set(contato_ids) - set(str(c.id) for c in contacts)
            results['errors'].append(f"Missing contacts: {missing}")
            results['failed'] = len(missing)
        
        # Create dispatch records and queue individual tasks
        for contato in contacts:
            try:
                # Check if message already sent to this contact (idempotency check)
                existing_disparo = Disparo.objects.filter(
                    contato=contato,
                    mensagem=mensagem,
                    status='ENVIADO'
                ).first()
                
                if existing_disparo:
                    logger.info(f"Message already sent to {contato.telefone}, skipping")
                    continue
                
                # Create pending dispatch record
                disparo = Disparo.objects.create(
                    contato=contato,
                    mensagem=mensagem,
                    status='PENDENTE',
                    task_id=task_id
                )
                
                # Dispatch individual message task
                enviar_mensagem_broadcast.delay(str(disparo.id))
                results['dispatched'] += 1
                    
            except Exception as e:
                logger.error(f"Error creating dispatch for contact {contato.id}: {e}")
                results['failed'] += 1
                results['errors'].append(f"Contact {contato.telefone}: {str(e)}")
    
    logger.info(f"Task {task_id} completed: {results['dispatched']} messages dispatched")
    return results

def _send_single_message(disparo: Disparo) -> bool:
    """
    Send a single WhatsApp message with proper error handling.
    
    Args:
        disparo: Disparo instance to process
    
    Returns:
        True if successful, False otherwise
    """
    client = UazApiClient()
    
    try:
        # Send message via API
        response = client.enviar_texto(disparo.contato.telefone, disparo.mensagem)
        
        # Check for API errors in response
        if 'error' in response:
            with transaction.atomic():
                disparo.status = 'FALHA'
                disparo.log_api = response
                disparo.save()
            
            logger.error(f"API error for {disparo.contato.telefone}: {response}")
            return False
        
        # Mark as successful
        with transaction.atomic():
            disparo.status = 'ENVIADO'
            disparo.log_api = response
            disparo.data_envio = timezone.now()
            disparo.save()
        
        logger.info(f"Message sent successfully to {disparo.contato.telefone}")
        return True
        
    except WhatsAppAuthenticationError as e:
        # Critical error - don't retry
        with transaction.atomic():
            disparo.status = 'FALHA'
            disparo.log_api = {'error': 'Authentication failed', 'details': str(e)}
            disparo.save()
        
        logger.error(f"Authentication error for {disparo.contato.telefone}: {e}")
        # Don't retry auth errors
        raise
        
    except WhatsAppRateLimitError as e:
        # Rate limit - will be retried by Celery
        with transaction.atomic():
            disparo.status = 'FALHA'
            disparo.log_api = {'error': 'Rate limited', 'details': str(e)}
            disparo.save()
        
        logger.warning(f"Rate limited for {disparo.contato.telefone}: {e}")
        raise  # Celery will retry
        
    except WhatsAppUnavailableError as e:
        # Service unavailable - will be retried
        with transaction.atomic():
            disparo.status = 'FALHA'
            disparo.log_api = {'error': 'Service unavailable', 'details': str(e)}
            disparo.save()
        
        logger.warning(f"Service unavailable for {disparo.contato.telefone}: {e}")
        raise  # Celery will retry
        
    except Exception as e:
        # Unexpected error
        with transaction.atomic():
            disparo.status = 'FALHA'
            disparo.log_api = {'error': 'Unexpected error', 'details': str(e)}
            disparo.save()
        
        logger.error(f"Unexpected error for {disparo.contato.telefone}: {e}")
        return False

@app.task(
    bind=True,
    name='trigger.check_connection_status',
    rate_limit='1/m'  # Check status once per minute max
)
def check_connection_status(self) -> Dict[str, Any]:
    """
    Periodic task to check WhatsApp connection status
    and update database accordingly.
    """
    try:
        client = UazApiClient()
        is_connected = client.verificar_status()
        
        # Update database atomically
        with transaction.atomic():
            instancia = InstanciaZap.objects.select_for_update().first()
            if instancia:
                instancia.conectado = is_connected
                instancia.save()
        
        logger.info(f"Connection status updated: {is_connected}")
        return {'connected': is_connected, 'timestamp': timezone.now().isoformat()}
        
    except Exception as e:
        logger.error(f"Error checking connection status: {e}")
        return {'connected': False, 'error': str(e)}

@app.task(
    bind=True,
    name='trigger.cleanup_old_disparos'
)
def cleanup_old_disparos(self, days_old: int = 30) -> Dict[str, Any]:
    """
    Cleanup old dispatch records to maintain database performance.
    """
    from django.utils import timezone
    
    try:
        cutoff_date = timezone.now() - timezone.timedelta(days=days_old)
        
        with transaction.atomic():
            old_count = Disparo.objects.filter(
                criado_em__lt=cutoff_date
            ).count()
            
            Disparo.objects.filter(
                criado_em__lt=cutoff_date
            ).delete()
        
        logger.info(f"Cleaned up {old_count} old dispatch records")
        return {'deleted_count': old_count, 'cutoff_date': cutoff_date.isoformat()}
        
    except Exception as e:
        logger.error(f"Error cleaning up old dispatches: {e}")
        return {'deleted_count': 0, 'error': str(e)}

# Helper function for timezone import
def timezone():
    """Import timezone lazily to avoid circular imports."""
    from django.utils import timezone
    return timezone
