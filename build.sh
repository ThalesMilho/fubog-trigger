#!/usr/bin/env bash
# Sair se houver erro
set -o errexit

# Instalar dependências
pip install -r requirements.txt

# Coletar estáticos
python manage.py collectstatic --no-input

# Criar banco de dados (SQLite)
python manage.py migrate

# --- COMANDO DE SALVAÇÃO ---
# Cria o usuário admin automaticamente se ele não existir
echo "Criando superusuário automático..."
# O comando abaixo cria o usuário 'admin' com email 'admin@fubog.com'
# A senha será definida via variável ou usará um padrão se falhar
if [[ -n "$DJANGO_SUPERUSER_USERNAME" ]]; then
    python manage.py createsuperuser --noinput || true
fi