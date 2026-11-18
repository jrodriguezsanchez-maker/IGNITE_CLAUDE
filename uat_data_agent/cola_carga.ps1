# Cola de cargas masivas desde QS4: QM -> WM -> LOG (solo plantas L), una detrás de otra y solo lo que falta.
# Con recuperación automática si SAP se cuelga. Anota todo en out\carga_noche.log. No corta nunca una lectura en marcha.
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $dir 'out\carga_noche.log'
$base = 'http://localhost:8766'
function Anota($t) { Add-Content -Path $log -Value ("{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $t) -Encoding UTF8 }
function Estado { try { (Invoke-RestMethod -Uri "$base/api/qs4/status" -TimeoutSec 15).estado } catch { 'sin respuesta' } }
function EsperaLibre($max) {
    $fin = (Get-Date).AddMinutes($max); $ultimo = Get-Date '2000-01-01'
    while ((Get-Date) -lt $fin) {
        $e = Estado
        if ($e -ne 'consultando') { return $e }
        if (((Get-Date) - $ultimo).TotalMinutes -ge 10) {
            try { $s = Invoke-RestMethod -Uri "$base/api/qs4/status" -TimeoutSec 15; $it = $s.items | Select-Object -Last 1; Anota ("  leyendo {0}/{1}: {2} {3}" -f $s.paso, $s.total, $it.name, $it.fase) } catch {}
            $ultimo = Get-Date
        }
        Start-Sleep -Seconds 30
    }
    return 'consultando'
}
Anota 'COLA iniciada: QM, WM y LOG (plantas L). Espera a que acabe la lectura en curso.'
foreach ($stream in 'QM', 'WM', 'LOG') {
    if ((EsperaLibre 600) -eq 'consultando') { Anota "[$stream] hay una lectura que dura más de 10 h; se abandona la cola."; break }
    try { $pl = Invoke-RestMethod -Uri "$base/api/plantas?stream=$stream" -TimeoutSec 60 } catch { Anota "[$stream] no pude leer la lista de plantas: $($_.Exception.Message)"; continue }
    $pend = @($pl.plantas | Where-Object { $_.faltan -gt 0 -and ($stream -ne 'LOG' -or $_.planta -like 'L*') } | ForEach-Object { $_.planta })
    if (-not $pend.Count) { Anota "[$stream] nada pendiente."; continue }
    Anota ("[{0}] lanzando {1} plantas: {2}" -f $stream, $pend.Count, ($pend -join ', '))
    $body = @{ id = $pl.ejemplo; plants = $pend; stream = $stream; masivo = $true; confirmado = $true; refrescar = @(); vendor = ''; autocurar = $true } | ConvertTo-Json -Compress
    try { Invoke-RestMethod -Method Post -Uri "$base/api/qs4/run" -ContentType 'application/json' -Body $body -TimeoutSec 60 | Out-Null } catch { Anota "[$stream] no se pudo lanzar: $($_.Exception.Message)"; continue }
    Start-Sleep -Seconds 20
    $e = EsperaLibre 600
    try { $s = Invoke-RestMethod -Uri "$base/api/qs4/status" -TimeoutSec 30; $ok = @($s.items | Where-Object { $_.estado -eq 'ok' }).Count; $vac = @($s.items | Where-Object { $_.estado -eq 'sin resultados' }).Count; $err = @($s.items | Where-Object { $_.estado -eq 'error' }).Count
        Anota ("[{0}] TERMINADO ({1}): {2} tablas ok, {3} sin resultados, {4} con error." -f $stream, $e, $ok, $vac, $err)
        foreach ($i in ($s.items | Where-Object { $_.estado -eq 'error' } | Select-Object -First 10)) { Anota ("    error: {0}: {1}" -f $i.name, $i.error) } } catch { Anota "[$stream] no pude leer el resultado final." }
}
Anota 'COLA terminada.'
