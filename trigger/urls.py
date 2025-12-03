from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('configurar/', views.configurar, name='configurar'),
    path('sair/', views.sair, name='sair'),
]