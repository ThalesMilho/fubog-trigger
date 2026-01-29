from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout 
from django.http import JsonResponse
from .forms import ContatoForm, MensagemForm, LoginForm
from .models import Contato, Disparo, InstanciaZap
from .services.uazapi_client import UazApiClient
import time
import random
import re
import logging

logger = logging.getLogger(__name__)

# --- VIEW 1: LOGIN (Lê do .env) ---
def configurar(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = LoginForm(request.POST or None)

    if request.method == 'POST':
        if form.is_valid():
            username_form = form.cleaned_data['username']
            password_form = form.cleaned_data['password']

            # Autentica usando usuários do Django Admin
            user = authenticate(request, username=username_form, password=password_form)

            if user is not None:
                login(request, user)
                return redirect('dashboard')
            else:
                messages.error(request, "Usuário ou senha incorretos.")
        else:
            messages.error(request, "Preencha os campos corretamente.")

    return render(request, 'trigger/setup.html', {'form': form})

# --- VIEW 2: SAIR ---
def sair(request):
    client = UazApiClient() # Inicializa o cliente da API
    
    # 1. Tenta desconectar a sessão do WhatsApp na API
    client.desconectar_instancia() 

    # 2. Limpa o registro local de conexão (opcional, mas bom)
    instancia = InstanciaZap.objects.first()
    if instancia:
        instancia.conectado = False
        instancia.save()

    # 3. Limpa a lista de contatos (já existia)
    Contato.objects.all().delete() 
    
    # 4. Desloga o usuário do Django
    logout(request)
    
    messages.info(request, "Sessão encerrada e WhatsApp desconectado.")
    return redirect('configurar')

# --- VIEW 3: DASHBOARD ---
def dashboard(request):
    if not request.user.is_authenticated:
        return redirect('configurar')
    
    client = UazApiClient()
    
    # Nome para exibir na tela
    numero_atual = request.user.username.upper()
    
    if request.method == 'POST':
        # --- SALVAR ---
        if 'btn_salvar' in request.POST:
            form_contato = ContatoForm(request.POST)
            if form_contato.is_valid():
                try:
                    novo = form_contato.save(commit=False)
                    num_limpo = re.sub(r'\D', '', novo.telefone)
                    if not num_limpo.startswith('55'): num_limpo = f"55{num_limpo}"
                    novo.telefone = num_limpo
                    novo.nome = f"Paciente {num_limpo[-4:]}"
                    novo.save()
                    messages.success(request, f"Número {num_limpo} salvo!")
                except:
                    messages.error(request, "Número já existe.")
            else:
                messages.error(request, "Erro no número.")
            return redirect('dashboard')

        # --- LIMPAR ---
        elif 'btn_limpar' in request.POST:
            Contato.objects.all().delete()
            messages.warning(request, "Lista limpa.")
            return redirect('dashboard')

        # --- DISPARAR ---
        elif 'btn_enviar' in request.POST:
            form_msg = MensagemForm(request.POST)
            if form_msg.is_valid():
                texto = form_msg.cleaned_data['mensagem']
                contatos = Contato.objects.all().order_by('criado_em')
                
                if not contatos.exists():
                    messages.warning(request, "Lista vazia.")
                    return redirect('dashboard')

                sucessos = 0
                total = contatos.count()
                opcoes_tempo = list(range(8, 21))
                random.shuffle(opcoes_tempo)

                for index, contato in enumerate(contatos):
                    disparo = Disparo.objects.create(
                        contato=contato, mensagem=texto, status='PENDENTE'
                    )
                    
                    resposta = client.enviar_texto(contato.telefone, texto)
                    
                    if 'error' in resposta:
                        disparo.status = 'FALHA'
                    else:
                        disparo.status = 'ENVIADO'
                        sucessos += 1
                    
                    disparo.log_api = resposta
                    disparo.save()

                    # Lógica Senior: Humanização do Delay
                    # Gera um tempo aleatório entre 1.0 e 5.0 segundos
                    tempo_espera = random.uniform(1, 5) 

                    print(f"⏳ Aguardando {tempo_espera:.2f} segundos...") # Log para debug
                    time.sleep(tempo_espera)

                messages.success(request, f"Fim! {sucessos}/{total} entregues.")
                return redirect('dashboard')

    else:
        form_contato = ContatoForm()
        form_msg = MensagemForm()

    lista_contatos = Contato.objects.all().order_by('criado_em')

    return render(request, 'trigger/index.html', {
        'form_contato': form_contato,
        'form_msg': form_msg,
        'lista_contatos': lista_contatos,
        'numero_atual': numero_atual 
    })

# --- VIEW 4: CONEXÃO WHATSAPP ---
# Em trigger/views.py

# Cole isso no trigger/views.py, substituindo a função conectar_whatsapp antiga

def conectar_whatsapp(request):
    client = UazApiClient()
    
    # 1. Verifica se forçaram a reconexão pela URL (?force=true)
    forcar = request.GET.get('force') == 'true'
    
    # 2. Se não forçado e já estiver conectado, manda pro painel
    if not forcar and client.verificar_status():
        # Sincroniza o banco local
        InstanciaZap.objects.update_or_create(
            instancia_id=client.instance_id,
            defaults={'conectado': True}
        )
        messages.success(request, "WhatsApp já está conectado!")
        return redirect('dashboard')

    # 3. Pede o QR Code
    resultado = client.obter_qr_code()
    
    qr_code_img = None
    erro_qr = None
    
    # Lógica para extrair a imagem Base64 do JSON da Uazapi
    if 'qrcode' in resultado:
        qr_code_img = resultado['qrcode']
    elif 'base64' in resultado:
        qr_code_img = resultado['base64']
    elif 'instance' in resultado and isinstance(resultado['instance'], dict):
        # Às vezes vem aninhado em instance > qrcode
        qr_code_img = resultado['instance'].get('qrcode')
    
    # Tratamento de erro
    if 'error' in resultado and resultado['error']:
        erro_qr = resultado.get('details', 'Erro de comunicação com a API')

    # 4. Formatação Final da Imagem para o HTML
    if qr_code_img and not qr_code_img.startswith('data:'):
        qr_code_img = f"data:image/png;base64,{qr_code_img}"

    # Renderiza usando o template que você já tem
    return render(request, 'trigger/conexao.html', {
        'qr_code': qr_code_img,
        'instancia_nome': client.instance_id,
        'erro_qr': erro_qr
    })

# --- VIEW 5: VERIFICAR STATUS VIA AJAX (para polling) ---
def verificar_conexao_api(request):
    """
    Endpoint AJAX para verificar se a instância foi conectada.
    Retorna JSON com status de conexão e atualiza BD se conectado.
    """
    client = UazApiClient()
    conectado = client.verificar_status()
    
    if conectado:
        # Atualiza o BD para marcar como conectado
        instancia = InstanciaZap.objects.first()
        if instancia:
            instancia.conectado = True
            instancia.save()
            logger.info(f"Instância {instancia.nome_operador} marcada como conectada")
    
    return JsonResponse({
        'conectado': conectado,
        'instancia_id': client.instance_id
    })

def verificar_status_conexao(request):
    """
    View para verificar o status da conexão com a UazAPI.
    Retorna um JSON com o status da conexão.
    """
    try:
        # Simulação de chamada à UazAPI
        client = UazApiClient()
        status_uazapi = client.verificar_status()  # Exemplo: retorna 'open' ou 'closed'

        # Traduz o status da API para um booleano
        esta_conectado = status_uazapi == 'open'

        return JsonResponse({
            'conectado': esta_conectado,
            'status': status_uazapi
        })
    except Exception as e:
        logger.error(f"Erro ao verificar status da conexão: {e}")
        return JsonResponse({'conectado': False, 'error': str(e)}, status=500)