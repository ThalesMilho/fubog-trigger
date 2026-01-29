import os
import django
import logging
from django.core.exceptions import ImproperlyConfigured
from django.db.utils import OperationalError

# Configuração de Logging (para aparecer bonito nos logs do Render)
logging.basicConfig(level=logging.INFO, format='[SETUP_ADMIN] %(message)s')
logger = logging.getLogger(__name__)

def setup_django():
    """Inicializa o ambiente Django para rodar scripts standalone."""
    try:
        # Aponta para o seu settings.py (ajuste 'core.settings' se o nome da pasta mudar)
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
        django.setup()
    except Exception as e:
        logger.error(f"Erro ao configurar Django: {e}")
        raise

def create_admin():
    setup_django()
    
    from django.contrib.auth import get_user_model
    User = get_user_model()

    # 1. Captura credenciais das variáveis de ambiente (Segurança: nunca hardcode senhas)
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

    # 2. Validação de Segurança
    if not username or not password:
        logger.warning("⚠️ Variáveis de ambiente de superusuário não definidas. Pulo a criação.")
        logger.warning("Dica: Configure DJANGO_SUPERUSER_USERNAME e DJANGO_SUPERUSER_PASSWORD no Render.")
        return

    try:
        # 3. Verifica existência (Idempotência: para não quebrar em deploys futuros)
        if User.objects.filter(username=username).exists():
            logger.info(f"✅ O usuário '{username}' já existe. Nenhuma ação necessária.")
        
        else:
            # 4. Criação Segura
            logger.info(f"🔨 Criando superusuário '{username}'...")
            User.objects.create_superuser(username=username, email=email, password=password)
            logger.info(f"🚀 Superusuário '{username}' criado com sucesso!")

    except OperationalError as e:
        logger.error("❌ Erro Operacional de Banco de Dados. O banco está acessível?")
        logger.error(f"Detalhe: {e}")
    except Exception as e:
        logger.error(f"❌ Erro inesperado ao criar superusuário: {e}")

if __name__ == '__main__':
    create_admin()