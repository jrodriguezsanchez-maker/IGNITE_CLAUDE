# Vigilante de la carga masiva: SOLO anota el avance en out\carga_noche.log y avisa cuando termina. No lanza propuesta ni Excel.
# Es independiente de cualquier sesión: se puede cerrar con Stop-Process si hace falta.
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $dir 'out\carga_noche.log'
function Anota($t) { Add-Content -Path $log -Value ("{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $t) -Encoding UTF8 }
Anota 'Vigilante iniciado (solo informa; no hace propuesta).'
$fin = (Get-Date).AddHours(10); $ultimo = Get-Date '2000-01-01'
while ((Get-Date) -lt $fin) {
    try { $s = Invoke-RestMethod -Uri 'http://localhost:8766/api/qs4/status' -TimeoutSec 15 } catch { Anota 'AVISO: el servidor no responde.'; Start-Sleep -Seconds 60; continue }
    if ($s.estado -ne 'consultando') {
        $ok = @($s.items | Where-Object { $_.estado -eq 'ok' }).Count; $err = @($s.items | Where-Object { $_.estado -eq 'error' }).Count
        Anota ("CARGA TERMINADA ({0}): {1} tablas ok, {2} con error. {3}" -f $s.estado, $ok, $err, $s.error)
        foreach ($i in ($s.items | Where-Object { $_.estado -eq 'error' })) { Anota ("  con error: {0}: {1}" -f $i.name, $i.error) }
        break
    }
    if (((Get-Date) - $ultimo).TotalMinutes -ge 5) {
        $it = $s.items | Select-Object -Last 1
        Anota ("Leyendo {0}/{1}: {2} {3} {4}" -f $s.paso, $s.total, $it.name, $it.estado, $it.fase); $ultimo = Get-Date
    }
    Start-Sleep -Seconds 30
}
Anota 'Vigilante terminado.'
