from django.contrib import admin
from .models import Contato, Disparo, InstanciaZap

# Registro da Instância
@admin.register(InstanciaZap)
class InstanciaZapAdmin(admin.ModelAdmin):
    list_display = ('nome_operador', 'numero_telefone', 'conectado', 'instancia_id')
    search_fields = ('nome_operador', 'numero_telefone')

# Registro dos Contatos
@admin.register(Contato)
class ContatoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'telefone', 'criado_em')
    search_fields = ('nome', 'telefone')

# Logs DISPAROS
@admin.register(Disparo)
class DisparoAdmin(admin.ModelAdmin):
    list_display = ('contato', 'status', 'data_envio', 'criado_em')
    list_filter = ('status', 'criado_em')
    search_fields = ('contato__nome', 'contato__telefone', 'mensagem')
    readonly_fields = ('id', 'log_api', 'criado_em')