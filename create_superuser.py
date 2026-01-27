import os
import django
from django.contrib.auth import get_user_model
from django.conf import settings

# Garanta que está apontando para o settings correto (core ou fubog_trigger)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings') 
django.setup()

User = get_user_model()

def create_superuser():
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

    if username and password:
        # Tenta pegar o usuário, ou cria se não existir
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': email, 'is_staff': True, 'is_superuser': True}
        )
        
        # Independente se foi criado agora ou já existia, FORÇA a nova senha
        user.set_password(password)
        user.save()
        
        if created:
            print(f"Superusuário {username} criado com sucesso!")
        else:
            print(f"Superusuário {username} já existia. Senha ATUALIZADA com sucesso!")
    else:
        print("Variáveis de ambiente não encontradas.")

if __name__ == '__main__':
    create_superuser()