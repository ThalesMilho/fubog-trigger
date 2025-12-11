from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('configurar/', views.configurar, name='configurar'),
    path('sair/', views.sair, name='sair'),
    path('conectar-whatsapp/', views.conectar_whatsapp, name='conectar_whatsapp'),
    path('api/verificar-conexao/', views.verificar_conexao_api, name='verificar_conexao'),
]