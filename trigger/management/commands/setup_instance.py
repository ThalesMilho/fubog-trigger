from django.core.management.base import BaseCommand
from trigger.models import InstanciaZap
import os

class Command(BaseCommand):
    help = 'Configura a Instância do WhatsApp automaticamente via variáveis de ambiente'

    def handle(self, *args, **options):
        # 1. Tenta pegar as variáveis do ambiente
        env_instance_id = os.getenv('UAZAPI_INSTANCE_ID')
        env_token = os.getenv('UAZAPI_TOKEN')

        # 2. Se não existirem, avisa e sai
        if not env_instance_id or not env_token:
            self.stdout.write(self.style.WARNING('Variáveis UAZAPI não encontradas. Pulei a configuração automática.'))
            return

        # 3. Cria ou Atualiza a instância no Banco de Dados
        # Usamos update_or_create para garantir que sempre haja apenas 1 configuração correta
        obj, created = InstanciaZap.objects.update_or_create(
            # Vamos buscar se já existe alguma (ou pegar a primeira)
            pk=InstanciaZap.objects.first().pk if InstanciaZap.objects.exists() else None,
            
            defaults={
                'nome_operador': 'Sistema Automático (Render)',
                'numero_telefone': 'Via Variável de Ambiente',
                'instancia_id': env_instance_id,
                'token': env_token,
                'conectado': True
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'Instância criada com sucesso! ID: {env_instance_id}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Instância atualizada com sucesso! ID: {env_instance_id}'))