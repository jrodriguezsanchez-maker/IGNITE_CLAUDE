# Reinicia el servidor de la herramienta (puerto 8766) SOLO cuando no hay ninguna lectura de SAP en marcha.
# Sirve para cargar cambios de código sin cortar una lectura larga. Espera hasta 8 horas.
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$fin = (Get-Date).AddHours(8)
while ((Get-Date) -lt $fin) {
    try {
        $estado = (Invoke-RestMethod -Uri 'http://localhost:8766/api/qs4/status' -TimeoutSec 10).estado
    } catch { $estado = 'sin respuesta' }
    if ($estado -ne 'consultando') {
        Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'server.py' -and $_.CommandLine -match '8766' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
        Start-Sleep -Seconds 2
        Start-Process -FilePath 'python' -ArgumentList 'front\server.py', '--port', '8766' -WorkingDirectory $dir -WindowStyle Minimized
        Add-Content -Path (Join-Path $dir 'out\reinicio_servidor.log') -Value ("{0}  servidor reiniciado (estado previo: {1})" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $estado)
        break
    }
    Start-Sleep -Seconds 30
}
