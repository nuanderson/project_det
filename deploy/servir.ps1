# Sobe o sistema com waitress (Windows). Defina as variáveis DET_* antes (ver .env.example).
# Uso: .\deploy\servir.ps1 [-Porta 8000]
param([int]$Porta = 8000)
$raiz = Split-Path $PSScriptRoot -Parent
Set-Location $raiz
$py = Join-Path $raiz ".venv\Scripts\python.exe"
& $py manage.py migrate --noinput
& $py manage.py collectstatic --noinput
& $py -m waitress --listen="0.0.0.0:$Porta" config.wsgi:application
