# Backup do banco SQLite e dos anexos. Agende diariamente (ver deploy\agendar.ps1).
# Uso: .\deploy\backup.ps1 -Destino D:\backups\det [-Manter 30]
param([Parameter(Mandatory = $true)][string]$Destino, [int]$Manter = 30)
$raiz = Split-Path $PSScriptRoot -Parent
$carimbo = Get-Date -Format "yyyyMMdd_HHmmss"
$pasta = Join-Path $Destino $carimbo
New-Item -ItemType Directory -Force $pasta | Out-Null

$py = Join-Path $raiz ".venv\Scripts\python.exe"
$db = Join-Path $raiz "db.sqlite3"
if (Test-Path $db) {
    # Cópia consistente via API de backup do SQLite (seguro com o sistema em uso).
    & $py -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()" $db (Join-Path $pasta "db.sqlite3")
}
$anexos = if ($env:DET_MEDIA_ROOT) { $env:DET_MEDIA_ROOT } else { Join-Path $raiz "anexos_privados" }
if (Test-Path $anexos) { Copy-Item $anexos (Join-Path $pasta "anexos") -Recurse }

# Mantém só os N backups mais recentes.
Get-ChildItem $Destino -Directory | Sort-Object Name -Descending | Select-Object -Skip $Manter | Remove-Item -Recurse -Force
Write-Output "Backup em $pasta"
