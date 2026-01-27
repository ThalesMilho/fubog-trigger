import os
import django
from django.contrib.auth import get_user_model
from django.conf import settings

# Configura o ambiente Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fubog_trigger.settings') # <--- TROQUE PELO NOME DA PASTA DO SEU PROJETO
django.setup()

User = get_user_model()

def create_superuser():
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
        print("Variáveis de ambiente de superusuário não encontradas. Pulando.")

if __name__ == '__main__':
    create_superuser()