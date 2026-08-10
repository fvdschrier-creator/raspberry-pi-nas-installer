# pinas_vaultwarden_cert_import.ps1 - Pi NAS Suite
#
# Haalt het PiNAS root-certificaat op van de Pi en vertrouwt het eenmalig in
# Windows ("Trusted Root Certification Authorities"). Wordt elevated (UAC)
# gestart door pinas_vaultwarden_cert_vertrouwen.pyw.
#
# 19 juli 2026: dit is het ROOT-certificaat (niet meer het losse
# servercertificaat van voorheen) - dat betekent dat je dit maar EENMALIG
# hoeft te doen. Het servercertificaat wordt op de Pi automatisch jaarlijks
# vernieuwd zonder dat dit hier opnieuw hoeft.
#
# Gebruik: powershell -NoProfile -ExecutionPolicy Bypass -File pinas_vaultwarden_cert_import.ps1 -PiIp <ip>

param(
    [Parameter(Mandatory=$true)][string]$PiIp
)

$ErrorActionPreference = "Stop"
Write-Host "====================================================================="
Write-Host "  PiNAS - Vaultwarden root-certificaat vertrouwen"
Write-Host "====================================================================="
Write-Host ""

$tempCert = Join-Path $env:TEMP "pinas-ca.crt"

try {
    Write-Host "Certificaat ophalen van de Pi ($PiIp)..."
    & scp "pi@${PiIp}:/etc/pinas-ca/ca.crt" $tempCert
    if (-not (Test-Path $tempCert)) {
        throw "Certificaat niet ontvangen."
    }
    Write-Host "OK: certificaat opgehaald."
    Write-Host ""

    Write-Host "Certificaat toevoegen aan 'Trusted Root Certification Authorities'..."
    & certutil -addstore -f "ROOT" $tempCert
    if ($LASTEXITCODE -ne 0) {
        throw "certutil gaf foutcode $LASTEXITCODE."
    }
    Write-Host ""
    Write-Host "====================================================================="
    Write-Host "  KLAAR - het root-certificaat wordt nu vertrouwd door Windows."
    Write-Host "  Chrome/Edge tonen geen waarschuwing meer bij de Vaultwarden-URL."
    Write-Host "====================================================================="
}
catch {
    Write-Host ""
    Write-Host "FOUT: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Controleer of Vaultwarden op de Pi geinstalleerd is en of SSH bereikbaar is."
}
finally {
    Remove-Item -Path $tempCert -ErrorAction SilentlyContinue
    Write-Host ""
    Read-Host "Druk op ENTER om dit venster te sluiten"
}
