import os
import django
from django.contrib.auth import get_user_model
from django.conf import settings

# CORREÇÃO AQUI: Mudamos de 'fubog_trigger.settings' para 'core.settings'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

User = get_user_model()

def create_superuser():
    # ... (o resto do código continua igual)
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

    if username and email and password:
        if not User.objects.filter(username=username).exists():
            print(f"Criando superusuário: {username}")
            User.objects.create_superuser(username=username, email=email, password=password)
            print("Superusuário criado com sucesso!")
        else:
            print("Superusuário já existe. Pulando criação.")
    else:
        print("Variáveis de ambiente não encontradas.")

if __name__ == '__main__':
    create_superuser()