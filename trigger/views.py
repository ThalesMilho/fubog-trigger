from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout 
from .forms import ContatoForm, MensagemForm, LoginForm
from .models import Contato, Disparo
from .services.uazapi_client import UazApiClient
import time
import random
import re

# --- VIEW 1: LOGIN (Lê do .env) ---
def configurar(request):
    # Se já está logado, vai pro dashboard
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
    Contato.objects.all().delete() # Limpa a lista ao sair
    logout(request)
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
                opcoes_tempo = list(range(10, 31))
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

                    if index < total - 1:
                        if not opcoes_tempo:
                            opcoes_tempo = list(range(10, 31))
                            random.shuffle(opcoes_tempo)
                        time.sleep(opcoes_tempo.pop())

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