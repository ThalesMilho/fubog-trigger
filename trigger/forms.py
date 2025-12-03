from django import forms
from django.core.validators import RegexValidator 
from .models import Contato

# 1. LOGIN 
class LoginForm(forms.Form):
    username = forms.CharField(
        label='Usuário',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg', 
            'placeholder': 'Usuário do sistema',
            'autofocus': 'autofocus'
        })
    )
    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Sua senha'
        })
    )

# 2. CONFIGURAÇÃO 
class ConfiguracaoForm(forms.Form):
    numero_disparador = forms.CharField(
        label='Número Conectado (WhatsApp)',
        validators=[
            RegexValidator(
                regex=r'^\d{10,13}$',
                message="Digite apenas números (com DDD). Ex: 62999999999"
            )
        ],
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg text-center', 
            'placeholder': 'Ex: 62999999999 (Somente números)',
        })
    )
    
    token_api = forms.CharField(
        label='Token / Senha da API',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Cole o token aqui'
        })
    )

# 3. MENSAGEM
class MensagemForm(forms.Form):
    mensagem = forms.CharField(
        label='Mensagem da Campanha', 
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 4,
            'placeholder': 'Olá, lembramos do seu retorno...'
        })
    )
    confirmacao = forms.BooleanField(
        required=True,
        label="Confirmar envio em massa",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

# 4. CONTATO
class ContatoForm(forms.ModelForm):
    class Meta:
        model = Contato
        fields = ['telefone']
        widgets = {
            'telefone': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Ex: 62999999999'
            })
        }