# Registra no Agendador de Tarefas do Windows: alertas por e-mail (08:00) e backup (22:00).
# Execute uma vez, em PowerShell como administrador: .\deploy\agendar.ps1 -DestinoBackup D:\backups\det
param([Parameter(Mandatory = $true)][string]$DestinoBackup)
$raiz = Split-Path $PSScriptRoot -Parent
$py = Join-Path $raiz ".venv\Scripts\python.exe"

$alertas = New-ScheduledTaskAction -Execute $py -Argument "manage.py enviar_alertas" -WorkingDirectory $raiz
Register-ScheduledTask -TaskName "DET - Alertas" -Action $alertas -Trigger (New-ScheduledTaskTrigger -Daily -At 8:00) -Force | Out-Null

$backup = New-ScheduledTaskAction -Execute "powershell.exe" -WorkingDirectory $raiz `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$raiz\deploy\backup.ps1`" -Destino `"$DestinoBackup`""
Register-ScheduledTask -TaskName "DET - Backup" -Action $backup -Trigger (New-ScheduledTaskTrigger -Daily -At 22:00) -Force | Out-Null
Write-Output "Tarefas 'DET - Alertas' e 'DET - Backup' registradas."
