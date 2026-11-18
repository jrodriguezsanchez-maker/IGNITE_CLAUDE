# Espera a que no haya ninguna lectura de SAP en marcha; entonces reinicia el servidor (puerto 8766), repite la propuesta en bloque de PP y regenera el Excel.
# Anota todo en out\reinicio_servidor.log. No corta nunca una lectura: solo actúa cuando el estado deja de ser «consultando».
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $dir 'out\reinicio_servidor.log'
function Anota($t) { Add-Content -Path $log -Value ("{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $t) -Encoding UTF8 }
Anota 'Esperando a que termine la lectura en curso...'
$fin = (Get-Date).AddHours(3)
while ((Get-Date) -lt $fin) {
    $estado = try { (Invoke-RestMethod -Uri 'http://localhost:8766/api/qs4/status' -TimeoutSec 10).estado } catch { 'sin respuesta' }
    if ($estado -ne 'consultando') { break }
    Start-Sleep -Seconds 20
}
if ($estado -eq 'consultando') { Anota 'Se agotó la espera: sigue habiendo una lectura. No se reinicia nada.'; return }
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'server.py' -and $_.CommandLine -match '8766' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 2
$p = Start-Process -FilePath 'python' -ArgumentList 'front\server.py', '--port', '8766' -WorkingDirectory $dir -WindowStyle Minimized -PassThru
Start-Sleep -Seconds 18
Anota ("Servidor reiniciado (PID {0}); estado previo: {1}." -f $p.Id, $estado)
try {
    $r = Invoke-RestMethod -Method Post -Uri 'http://localhost:8766/api/auto' -ContentType 'application/json' -Body '{"confirmado":true,"stream":"PP"}' -TimeoutSec 900
    Anota ("Propuesta en bloque: {0}" -f ($r | ConvertTo-Json -Compress))
    $x = Invoke-RestMethod -Uri 'http://localhost:8766/api/excel' -TimeoutSec 900
    Anota ("Excel: {0} | filas {1} | verificado {2}" -f $x.ruta, $x.filas, $x.verificacion.solo_sheet2_y_table2)
} catch { Anota ("ERROR: {0}" -f $_.Exception.Message) }
Anota 'Terminado.'
