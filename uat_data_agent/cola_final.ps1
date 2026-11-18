# Cola final de cargas desde QS4 (solo lectura), para dejarlo todo listo:
#  1) espera a que acabe la lectura en marcha (no la corta nunca)  2) reinicia el servidor para cargar el código nuevo
#  3) proveedores internos "P + planta" de los traslados entre sociedades  4) QM, LOG y WM: solo lo que falte, con recuperación automática si SAP se cuelga.
# Anota todo en out\carga_final.log.
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $dir 'out\carga_final.log'
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
function Resultado($nombre) {
    try { $s = Invoke-RestMethod -Uri "$base/api/qs4/status" -TimeoutSec 30
        $ok = @($s.items | Where-Object { $_.estado -eq 'ok' }).Count; $vac = @($s.items | Where-Object { $_.estado -eq 'sin resultados' -or $_.estado -eq 'omitida' }).Count; $err = @($s.items | Where-Object { $_.estado -eq 'error' }).Count
        Anota ("[{0}] TERMINADO ({1}): {2} tablas ok, {3} sin resultados, {4} con error." -f $nombre, $s.estado, $ok, $vac, $err)
        foreach ($i in ($s.items | Where-Object { $_.estado -eq 'error' } | Select-Object -First 10)) { Anota ("    error: {0}: {1}" -f $i.name, $i.error) } } catch { Anota "[$nombre] no pude leer el resultado final." }
}
function Lanza($nombre, $body) {
    try { Invoke-RestMethod -Method Post -Uri "$base/api/qs4/run" -ContentType 'application/json' -Body $body -TimeoutSec 60 | Out-Null } catch { Anota "[$nombre] no se pudo lanzar: $($_.Exception.Message)"; return $false }
    Start-Sleep -Seconds 20
    $e = EsperaLibre 600
    Resultado $nombre
    return $true
}
Anota 'COLA FINAL iniciada. Espera a que acabe la lectura en curso.'
[void](EsperaLibre 120)
if ((Estado) -eq 'sin respuesta') { Anota 'El servidor no responde: arráncalo con iniciar_uat.bat y relanza la cola.'; exit }

if ((Estado) -eq 'sin respuesta') { Anota 'El servidor no responde: arráncalo con iniciar_uat.bat y relanza la cola.'; exit }
Anota 'Servidor activo (sin reinicio).'

# --- proveedores internos "P + planta" (ZINT / ZINR) ---
try {
    $cs = Invoke-RestMethod -Uri "$base/api/cases" -TimeoutSec 60
    $ej = ($cs | Where-Object { $_.stream -eq 'LOG' } | Select-Object -First 1).id
    $pls = @($cs | Where-Object { $_.flow -in 'ZINT', 'ZINR' } | ForEach-Object { $_.plants } | Where-Object { $_ } | Sort-Object -Unique)
    $ven = ($pls | ForEach-Object { "P$_" }) -join ','
    Anota ("[PROVEEDORES P+planta] {0} proveedores: {1}" -f $pls.Count, $ven)
    $body = @{ id = $ej; plants = @(); stream = 'LOG'; masivo = $false; confirmado = $true; refrescar = @(); vendor = $ven; autocurar = $true } | ConvertTo-Json -Compress
    Lanza 'PROVEEDORES P+planta' $body | Out-Null
} catch { Anota "[PROVEEDORES P+planta] fallo: $($_.Exception.Message)" }

# --- QM, LOG y WM: solo lo que falte ---
foreach ($stream in 'QM', 'LOG', 'WM') {
    if ((EsperaLibre 600) -eq 'consultando') { Anota "[$stream] hay una lectura que dura más de 10 h; se abandona la cola."; break }
    try { $pl = Invoke-RestMethod -Uri "$base/api/plantas?stream=$stream" -TimeoutSec 60 } catch { Anota "[$stream] no pude leer la lista de plantas: $($_.Exception.Message)"; continue }
    $pend = @($pl.plantas | Where-Object { $_.faltan -gt 0 } | ForEach-Object { $_.planta })
    if (-not $pend.Count) { Anota "[$stream] nada pendiente."; continue }
    Anota ("[{0}] lanzando {1} plantas: {2}" -f $stream, $pend.Count, ($pend -join ', '))
    $body = @{ id = $pl.ejemplo; plants = $pend; stream = $stream; masivo = $true; confirmado = $true; refrescar = @(); vendor = ''; autocurar = $true } | ConvertTo-Json -Compress
    Lanza $stream $body | Out-Null
}
Anota 'COLA FINAL terminada.'


