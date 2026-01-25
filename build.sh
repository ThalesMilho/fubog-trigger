#!/usr/bin/env bash
# Sair se houver erro
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input

# 1. Cria as tabelas vazias
python manage.py migrate

# 2. Preenche a configuração da Uazapi (NOVO)
python manage.py setup_instance

# 3. Cria o usuário Admin (que já configuramos antes)
echo "Criando superusuário automático..."
if [[ -n "$DJANGO_SUPERUSER_USERNAME" ]]; then
    python manage.py createsuperuser --noinput || true
fi