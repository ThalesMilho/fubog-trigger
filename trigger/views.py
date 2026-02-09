import logging
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout 
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.db import transaction
import re

from .forms import ContatoForm, MensagemForm, LoginForm
from .models import Contato, Disparo, InstanciaZap
from .services.uazapi_client import UazApiClient, WhatsAppError
from .tasks import send_bulk_messages, check_connection_status

logger = logging.getLogger(__name__)

# --- VIEW 1: LOGIN ---
def configurar(request):
    """Handle user authentication."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = LoginForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                return redirect('dashboard')
            else:
                messages.error(request, "Usuário ou senha incorretos.")
        else:
            messages.error(request, "Preencha os campos corretamente.")

    return render(request, 'trigger/setup.html', {'form': form})

# --- VIEW 2: LOGOUT ---
def sair(request):
    """Handle user logout and WhatsApp disconnection."""
    try:
        # Disconnect WhatsApp instance
        client = UazApiClient()
        client.desconectar_instancia()
        
        # Update local database
        with transaction.atomic():
            instancia = InstanciaZap.objects.select_for_update().first()
            if instancia:
                instancia.conectado = False
                instancia.save()

        # Clear contacts
        Contato.objects.all().delete()
        
        # Logout user
        logout(request)
        
        messages.info(request, "Sessão encerrada e WhatsApp desconectado.")
        
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        messages.error(request, "Erro ao encerrar sessão.")
    
    return redirect('configurar')

# --- VIEW 3: DASHBOARD ---
def dashboard(request):
    """Main dashboard view - now async for bulk messaging."""
    if not request.user.is_authenticated:
        return redirect('dashboard')
    
    client = UazApiClient()
    numero_atual = request.user.username.upper()
    
    if request.method == 'POST':
        # --- SAVE CONTACT ---
        if 'btn_salvar' in request.POST:
            return _handle_save_contact(request)
        
        # --- CLEAR CONTACTS ---
        elif 'btn_limpar' in request.POST:
            return _handle_clear_contacts(request)
        
        # --- SEND BULK MESSAGES ---
        elif 'btn_enviar' in request.POST:
            return _handle_bulk_messages(request)

    # GET request - show dashboard
    form_contato = ContatoForm()
    form_msg = MensagemForm()
    lista_contatos = Contato.objects.all().order_by('criado_em')

    return render(request, 'trigger/index.html', {
        'form_contato': form_contato,
        'form_msg': form_msg,
        'lista_contatos': lista_contatos,
        'numero_atual': numero_atual 
    })

def _handle_save_contact(request) -> redirect:
    """Handle contact saving with validation."""
    form_contato = ContatoForm(request.POST)
    
    if not form_contato.is_valid():
        messages.error(request, "Erro no número.")
        return redirect('dashboard')
    
    try:
        novo = form_contato.save(commit=False)
        
        # Clean and validate phone number
        num_limpo = re.sub(r'\D', '', novo.telefone)
        if not num_limpo.startswith('55'):
            num_limpo = f"55{num_limpo}"
        
        # Validate phone number format
        client = UazApiClient()
        if not client._validate_phone_number(num_limpo):
            messages.error(request, "Formato de telefone inválido.")
            return redirect('dashboard')
        
        novo.telefone = num_limpo
        novo.nome = f"Paciente {num_limpo[-4:]}"
        novo.save()
        
        messages.success(request, f"Número {num_limpo} salvo!")
        
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.error(f"Error saving contact: {e}")
        messages.error(request, "Número já existe ou erro ao salvar.")
    
    return redirect('dashboard')

def _handle_clear_contacts(request) -> redirect:
    """Handle contact list clearing."""
    try:
        with transaction.atomic():
            count = Contato.objects.count()
            Contato.objects.all().delete()
            messages.warning(request, f"Lista limpa. {count} contatos removidos.")
    except Exception as e:
        logger.error(f"Error clearing contacts: {e}")
        messages.error(request, "Erro ao limpar lista.")
    
    return redirect('dashboard')

def _handle_bulk_messages(request) -> redirect:
    """
    Handle bulk message sending - now async via Celery.
    View only creates the task and returns immediately.
    """
    form_msg = MensagemForm(request.POST)
    
    if not form_msg.is_valid():
        messages.error(request, "Erro na mensagem.")
        return redirect('dashboard')
    
    texto = form_msg.cleaned_data['mensagem']
    contatos_ids = request.POST.getlist('contatos_selecionados')
    
    # Validate inputs
    if not contatos_ids:
        messages.warning(request, "Nenhum contato selecionado.")
        return redirect('dashboard')
    
    if len(contatos_ids) > 100:
        messages.error(request, "Limite de 100 contatos por envio.")
        return redirect('dashboard')
    
    try:
        # Create dispatch records atomically
        with transaction.atomic():
            contacts = Contato.objects.filter(id__in=contatos_ids)
            
            # Validate all contacts exist
            if contacts.count() != len(contatos_ids):
                missing = set(contatos_ids) - set(str(c.id) for c in contacts)
                messages.error(request, f"Contatos não encontrados: {missing}")
                return redirect('dashboard')
            
            # Create pending dispatch records
            dispatches = []
            for contato in contacts:
                disparo = Disparo(
                    contato=contato,
                    mensagem=texto,
                    status='PENDENTE'
                )
                dispatches.append(disparo)
            
            Disparo.objects.bulk_create(dispatches)
        
        # Dispatch async task
        task = send_bulk_messages.delay(contatos_ids, texto)
        
        messages.success(
            request, 
            f"Envio iniciado! Task ID: {task.id}. "
            f"Processando {len(contatos_ids)} mensagens."
        )
        
        logger.info(f"Bulk message task {task.id} started for {len(contatos_ids)} contacts")
        
    except Exception as e:
        logger.error(f"Error starting bulk message task: {e}")
        messages.error(request, "Erro ao iniciar envio em massa.")
    
    return redirect('dashboard')

# --- VIEW 4: WHATSAPP CONNECTION ---
def conectar_whatsapp(request):
    """Handle WhatsApp connection via QR code."""
    client = UazApiClient()
    
    # Check for forced reconnection
    force_reconnect = request.GET.get('force') == 'true'
    
    # If not forced and already connected, redirect to dashboard
    if not force_reconnect and client.verificar_status():
        # Sync database
        with transaction.atomic():
            InstanciaZap.objects.update_or_create(
                instancia_id=client.instance_id,
                defaults={'conectado': True}
            )
        
        messages.success(request, "WhatsApp já está conectado!")
        return redirect('dashboard')
    
    # Get QR code
    try:
        resultado = client.obter_qr_code()
        
        qr_code_img = None
        erro_qr = None
        
        # Extract QR code from response
        if 'qrcode' in resultado:
            qr_code_img = resultado['qrcode']
        elif 'base64' in resultado:
            qr_code_img = resultado['base64']
        elif 'instance' in resultado and isinstance(resultado['instance'], dict):
            qr_code_img = resultado['instance'].get('qrcode')
        
        # Handle errors
        if 'error' in resultado and resultado['error']:
            erro_qr = resultado.get('details', 'Erro de comunicação com a API')
        
        # Format QR code for HTML
        if qr_code_img and not qr_code_img.startswith('data:'):
            qr_code_img = f"data:image/png;base64,{qr_code_img}"
        
        return render(request, 'trigger/conexao.html', {
            'qr_code': qr_code_img,
            'instancia_nome': client.instance_id,
            'erro_qr': erro_qr
        })
        
    except WhatsAppError as e:
        logger.error(f"WhatsApp API error: {e}")
        messages.error(request, f"Erro na API WhatsApp: {e}")
        return redirect('dashboard')
    
    except Exception as e:
        logger.error(f"Unexpected error getting QR code: {e}")
        messages.error(request, "Erro ao obter QR Code.")
        return redirect('dashboard')

# --- VIEW 5: AJAX STATUS CHECK ---
def verificar_conexao_api(request):
    """
    AJAX endpoint to check WhatsApp connection status.
    Returns JSON with connection status and updates database.
    """
    try:
        client = UazApiClient()
        conectado = client.verificar_status()
        
        if conectado:
            # Update database atomically
            with transaction.atomic():
                instancia = InstanciaZap.objects.select_for_update().first()
                if instancia:
                    instancia.conectado = True
                    instancia.save()
                    logger.info(f"Instância {instancia.nome_operador} marcada como conectada")
        
        return JsonResponse({
            'conectado': conectado,
            'instancia_id': client.instance_id
        })
        
    except Exception as e:
        logger.error(f"Error checking connection status: {e}")
        return JsonResponse({
            'conectado': False, 
            'error': str(e)
        }, status=500)

def verificar_status_conexao(request):
    """
    View to check WhatsApp connection status.
    Returns JSON with detailed status information.
    """
    try:
        client = UazApiClient()
        
        # Get real-time status from API
        status_uazapi = client.verificar_status()
        
        # Check health
        health = client.check_health()
        
        return JsonResponse({
            'conectado': status_uazapi,
            'health': health,
            'instancia_id': client.instance_id
        })
        
    except Exception as e:
        logger.error(f"Error verifying connection status: {e}")
        return JsonResponse({
            'conectado': False, 
            'error': str(e)
        }, status=500)

# --- VIEW 6: TASK STATUS ---
def task_status(request, task_id: str):
    """
    Check status of async bulk message task.
    """
    try:
        from celery.result import AsyncResult
        
        result = AsyncResult(task_id)
        
        # Get task statistics
        if result.ready():
            if result.successful():
                data = result.get()
                return JsonResponse({
                    'status': 'completed',
                    'result': data
                })
            else:
                return JsonResponse({
                    'status': 'failed',
                    'error': str(result.info)
                })
        else:
            return JsonResponse({
                'status': 'pending',
                'progress': 'Processing...'
            })
            
    except Exception as e:
        logger.error(f"Error checking task status: {e}")
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)
