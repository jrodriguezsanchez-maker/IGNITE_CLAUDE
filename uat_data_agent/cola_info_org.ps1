# Registros info por organización de compras (QS4, solo lectura): EINE por EKORG + EINA. De la más pequeña a la más grande.
# Salta las organizaciones ya leídas. Anota todo en out\carga_info_org.log. No reinicia el servidor.
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $dir 'out\carga_info_org.log'
$base = 'http://localhost:8766'
function Anota($t) { for ($k = 0; $k -lt 5; $k++) { try { Add-Content -Path $log -Value ("{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $t) -Encoding UTF8 -ErrorAction Stop; return } catch { Start-Sleep -Milliseconds 500 } } }
function Estado { try { (Invoke-RestMethod -Uri "$base/api/qs4/status" -TimeoutSec 15).estado } catch { 'sin respuesta' } }
$orgs = 'FI01', 'CI01', 'SN01', 'DZ01', 'GH01', 'SE01', 'FR01', 'DE01', 'NG01', 'BE01', 'IT01', 'ES01'
Anota 'COLA INFO ORG iniciada'
foreach ($ek in $orgs) {
    while ((Estado) -eq 'consultando') { Start-Sleep -Seconds 20 }
    $eina = Join-Path $dir ('data/raw/EINA__O' + $ek + '.txt')
    if (Test-Path -LiteralPath $eina) { Anota "[$ek] ya leida, se salta."; continue }
    $body = @{ extra = 'info_org'; ekorg = $ek; confirmado = $true; autocurar = $true; forzar = $true } | ConvertTo-Json -Compress
    try { $r = Invoke-RestMethod -Method Post -Uri "$base/api/qs4/run" -ContentType 'application/json' -Body $body -TimeoutSec 60 }
    catch { Anota "[$ek] no se pudo lanzar: $($_.Exception.Message)"; continue }
    Anota "[$ek] lanzada"
    Start-Sleep -Seconds 20
    $ultimo = Get-Date '2000-01-01'
    while ((Estado) -eq 'consultando') {
        if (((Get-Date) - $ultimo).TotalMinutes -ge 5) {
            try { $s = Invoke-RestMethod -Uri "$base/api/qs4/status" -TimeoutSec 15; $it = $s.items | Select-Object -Last 1; Anota ("  [{0}] {1}/{2}: {3} {4}" -f $ek, $s.paso, $s.total, $it.name, $it.fase) } catch {}
            $ultimo = Get-Date
        }
        Start-Sleep -Seconds 20
    }
    try {
        $s = Invoke-RestMethod -Uri "$base/api/qs4/status" -TimeoutSec 30
        $ok = @($s.items | Where-Object { $_.estado -eq 'ok' }).Count; $err = @($s.items | Where-Object { $_.estado -eq 'error' }).Count
        Anota ("[{0}] TERMINADO ({1}): {2} tablas ok, {3} con error." -f $ek, $s.estado, $ok, $err)
        foreach ($i in ($s.items | Where-Object { $_.estado -eq 'error' })) { Anota ("    error: {0}: {1}" -f $i.name, $i.error) }
    } catch { Anota "[$ek] no pude leer el resultado final." }
}
Anota 'COLA INFO ORG terminada.'
