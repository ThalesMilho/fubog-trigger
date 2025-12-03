from django.db import models
import uuid

# --- NOVO MODELO: Caixa das "contas" de WhatsApp ---
class InstanciaZap(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome_operador = models.CharField(max_length=100, help_text="Ex: Atendente Maria")
    numero_telefone = models.CharField(max_length=20, help_text="Apenas referência visual")
    
    # Credenciais da API
    instancia_id = models.CharField(max_length=100, help_text="ID da Instância na UazAPI")
    token = models.CharField(max_length=255, help_text="Token da Instância")
    
    conectado = models.BooleanField(default=False)
    ultima_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Instância WhatsApp"
        verbose_name_plural = "Instâncias WhatsApp"

    def __str__(self):
        return f"{self.nome_operador} ({self.numero_telefone})"

# Mdl antigo Agenda de Contatos
class Contato(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=150, default="Desconhecido") 
    telefone = models.CharField(max_length=20, unique=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} ({self.telefone})"

#Mdl antgo Log
class Disparo(models.Model):
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('ENVIADO', "Enviado"),
        ('FALHA', 'Falha'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contato = models.ForeignKey(Contato, on_delete=models.CASCADE)
    mensagem = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDENTE')
    log_api = models.JSONField(null=True, blank=True)
    data_envio = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['status']),
        ]
    def __str__(self):
        return f"Disparo para {self.contato.telefone} - {self.status}"