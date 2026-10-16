#!/usr/bin/env bash
# Início do link de teste online (Render). O disco do plano gratuito é temporário:
# a cada início o banco é recriado e a demonstração é repopulada.
set -o errexit
python manage.py migrate --noinput
if [ "${DET_PERMITIR_DEMO:-}" = "True" ] || [ "${DET_PERMITIR_DEMO:-}" = "true" ]; then
  python manage.py popular_demo
fi
# O Render termina o HTTPS e repassa X-Forwarded-Proto; o waitress só o respeita se o proxy for declarado confiável.
exec python -m waitress --host=0.0.0.0 --port="${PORT:-10000}" \
  --trusted-proxy='*' --trusted-proxy-headers='x-forwarded-proto x-forwarded-for' \
  config.wsgi:application
