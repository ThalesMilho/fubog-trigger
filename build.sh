#!/usr/bin/env bash
# Sair se houver erro
set -o errexit

pip install -r requirements.txt

# Coletar estáticos
python manage.py collectstatic --no-input

# Aplicar migrações
python manage.py migrate