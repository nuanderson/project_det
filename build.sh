#!/usr/bin/env bash
# Build do link de teste online (Render): instala dependências e coleta os estáticos.
set -o errexit
pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --noinput
