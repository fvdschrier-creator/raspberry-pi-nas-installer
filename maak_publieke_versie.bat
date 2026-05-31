@echo off
:: ============================================================
:: Maakt schone publieke versie voor GitHub
:: ============================================================
setlocal enabledelayedexpansion

set NAS_MAP=C:\Users\UW_GEBRUIKERSNAAM\OneDrive\Documenten\Desktop\NAS
set PUBLIC_MAP=C:\Users\UW_GEBRUIKERSNAAM\OneDrive\Documenten\Desktop\NAS_Public

echo.
echo  Pi NAS - Maak publieke versie voor GitHub
echo  ============================================================
echo  Van:  %NAS_MAP%
echo  Naar: %PUBLIC_MAP%
echo  ============================================================
echo.

if not exist "%PUBLIC_MAP%" mkdir "%PUBLIC_MAP%"

set GEKOPIEERD=0
for %%F in (
    nas_installer.py
    nas_installer_cli.py
    nas_backup.py
    nas_config.py
    pi_welkom.sh
    install.sh
    nas_start.sh
    smart_plug.py
    seagate_web.py
    seagate-web.service
    nas_upload.bat
    kopieer_naar_nas.bat
    kopieer_helper.ps1
    initieel_setup.bat
    maak_publieke_versie.bat
    nas_diagnose.sh
    nas_diagnose.bat
    install_vnc_viewer.bat
    README.md
    raspberry_pi_nas_volledig.pdf
) do (
    if exist "%NAS_MAP%\%%F" (
        copy /Y "%NAS_MAP%\%%F" "%PUBLIC_MAP%\%%F" >nul
        echo  OK: %%F
        set /a GEKOPIEERD+=1
    )
)

:: Maak config template aan
echo  Aanmaken: smart_plug_config.example.json
(
echo {
echo     "type": "hue",
echo     "hue": {
echo         "bridge_ip": "UW_HUE_BRIDGE_IP",
echo         "api_key": "UW_HUE_API_KEY",
echo         "plug_id": "UW_PLUG_ID"
echo     },
echo     "tapo": {
echo         "ip": "UW_TAPO_IP",
echo         "email": "UW_TAPO_EMAIL",
echo         "password": "UW_TAPO_WACHTWOORD"
echo     },
echo     "seagate_mount": "/mnt/backup"
echo }
) > "%PUBLIC_MAP%\smart_plug_config.example.json"

:: Anonimiseer alles via één PowerShell script
echo  Anonimiseren...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$pub = '%PUBLIC_MAP%';" ^
    "Get-ChildItem $pub -Include *.bat,*.py,*.sh,*.json,*.md -Recurse | ForEach-Object {" ^
    "    $c = Get-Content $_.FullName -Raw;" ^
    "    $c = $c -replace '192\.168\.\d+\.\d+','UW_PI_IP_ADRES';" ^
    "    $c = $c -replace 'UW_HUE_API_KEY','UW_HUE_API_KEY';" ^
    "    $c = $c -replace 'UW_GEBRUIKERSNAAM','UW_GEBRUIKERSNAAM';" ^
    "    Set-Content $_.FullName $c -NoNewline;" ^
    "    Write-Host ('  SCHOON: ' + $_.Name)" ^
    "}"

echo.
echo  ============================================================
echo  !GEKOPIEERD! bestanden gekopieerd naar NAS_Public.
echo  Persoonlijke gegevens vervangen.
echo  ============================================================
echo.
echo  NAS_Public is klaar voor GitHub!
echo.
pause
