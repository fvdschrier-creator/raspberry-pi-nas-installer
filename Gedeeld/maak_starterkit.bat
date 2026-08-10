@echo off
:: ============================================================
:: Pi NAS Suite - Maak Starter Kit ZIP
:: Staat in: C:\PiNAS\Gedeeld\
:: Output:   C:\PiNAS\Publicatie\StarterKit\starterkit_nas.zip
:: Geanonimiseerd - klaar voor installatie op nieuwe pc
:: ============================================================
setlocal

set NAS_ROOT=C:\PiNAS
set OUTPUT_MAP=%NAS_ROOT%\Publicatie\StarterKit
set WERK_MAP=%TEMP%\starterkit_werk
set ZIP_PAD=%OUTPUT_MAP%\starterkit_nas.zip

echo.
echo  Pi NAS Suite - Starter Kit bouwen
echo  ============================================================
echo  NAS root:  %NAS_ROOT%
echo  Output:    %ZIP_PAD%
echo  ============================================================
echo.

:: Controleer PowerShell beschikbaar
where powershell >nul 2>&1
if errorlevel 1 (
    echo  FOUT: PowerShell niet gevonden.
    pause & exit /b 1
)

:: Werkmap aanmaken
if exist "%WERK_MAP%" rd /s /q "%WERK_MAP%"
mkdir "%WERK_MAP%"
if not exist "%OUTPUT_MAP%" mkdir "%OUTPUT_MAP%"

echo  [Stap 1] Bestanden kopieren...

:: -- Beheer ------------------------------------------------
mkdir "%WERK_MAP%\Beheer"
for %%F in (
    Pi_NAS_Menu.pyw
    pi_nas_setup.pyw
    Pi_NAS_Menu.ico
    lanman_fix.bat
    install_vnc_viewer.bat
    pinas_backup_beheer.pyw
    pinas_image_backup.pyw
) do (
    if exist "%NAS_ROOT%\Beheer\%%F" (
        copy /Y "%NAS_ROOT%\Beheer\%%F" "%WERK_MAP%\Beheer\%%F" >nul
        echo    OK: Beheer\%%F
    ) else (
        echo    --: Beheer\%%F niet gevonden
    )
)

:: PC Image Backup's gedeelde module staat in de submap core/
if exist "%NAS_ROOT%\Beheer\core" (
    mkdir "%WERK_MAP%\Beheer\core" 2>nul
    copy /Y "%NAS_ROOT%\Beheer\core\*" "%WERK_MAP%\Beheer\core\" >nul
    echo    OK: Beheer\core\
) else (
    echo    --: Beheer\core niet gevonden
)

:: Screenshots staan in de submap assets/
if exist "%NAS_ROOT%\Beheer\assets" (
    mkdir "%WERK_MAP%\Beheer\assets" 2>nul
    copy /Y "%NAS_ROOT%\Beheer\assets\pinas_sync_scherm*.png" "%WERK_MAP%\Beheer\assets\" >nul
    echo    OK: Beheer\assets\ screenshots
) else (
    echo    --: Beheer\assets niet gevonden
)

:: -- Publicatie ---------------------------------------------
mkdir "%WERK_MAP%\Publicatie"
for %%F in (
    PiNAS_Suite_Handleiding.pdf
    build_suite_handleiding.py
) do (
    if exist "%NAS_ROOT%\Publicatie\%%F" (
        copy /Y "%NAS_ROOT%\Publicatie\%%F" "%WERK_MAP%\Publicatie\%%F" >nul
        echo    OK: Publicatie\%%F
    ) else (
        echo    --: Publicatie\%%F niet gevonden
    )
)

:: -- Sync -------------------------------------------------
mkdir "%WERK_MAP%\Sync"
mkdir "%WERK_MAP%\Sync\core"
for %%F in (pinas_sync_app.pyw start.bat requirements.txt install_windows.bat) do (
    if exist "%NAS_ROOT%\Sync\%%F" (
        copy /Y "%NAS_ROOT%\Sync\%%F" "%WERK_MAP%\Sync\%%F" >nul
        echo    OK: Sync\%%F
    ) else (
        echo    --: Sync\%%F niet gevonden
    )
)
for %%F in (sync_engine.py bron_doel_picker.py thema.py __init__.py) do (
    if exist "%NAS_ROOT%\Sync\core\%%F" (
        copy /Y "%NAS_ROOT%\Sync\core\%%F" "%WERK_MAP%\Sync\core\%%F" >nul
        echo    OK: Sync\core\%%F
    )
)

:: -- ArchiefBackup (hoofdmap, hoort bij Backup Beheer - geen zijproject meer) --
mkdir "%WERK_MAP%\ArchiefBackup"
for %%F in (archief_backup_bewaking.pyw start.bat) do (
    if exist "%NAS_ROOT%\ArchiefBackup\%%F" (
        copy /Y "%NAS_ROOT%\ArchiefBackup\%%F" "%WERK_MAP%\ArchiefBackup\%%F" >nul
        echo    OK: ArchiefBackup\%%F
    ) else (
        echo    --: ArchiefBackup\%%F niet gevonden
    )
)

:: -- Addons (17 juli 2026 toegevoegd - stonden er nooit in) ---------------
mkdir "%WERK_MAP%\Addons"
for %%F in (
    pinas_addons_beheer.pyw
    pinas_nextcloud.sh
    pinas_nextcloud_verwijderen.sh
    pinas_pihole.sh
    pinas_pihole_verwijderen.sh
    pinas_zerotier.sh
    pinas_zerotier_verwijderen.sh
    pinas_vaultwarden.sh
    pinas_vaultwarden_verwijderen.sh
    pinas_vaultwarden_cert_vertrouwen.pyw
    pinas_vaultwarden_cert_import.ps1
    pinas_status_pagina.sh
    pinas_status_pagina_verwijderen.sh
    pinas_status_pagina_wachtwoord_resetten.sh
    pinas_printer.sh
    pinas_printer_verwijderen.sh
    pinas_dashboard.sh
    pinas_dashboard_verwijderen.sh
) do (
    if exist "%NAS_ROOT%\Addons\%%F" (
        copy /Y "%NAS_ROOT%\Addons\%%F" "%WERK_MAP%\Addons\%%F" >nul
        echo    OK: Addons\%%F
    ) else (
        echo    --: Addons\%%F niet gevonden
    )
)

:: -- PiServer ----------------------------------------------------
mkdir "%WERK_MAP%\PiServer"
for %%F in (
    nas_installer.py
    nas_installer_cli.py
    seagate_web.py
    seagate-web.service
    smart_plug.py
    smart_plug_config.json
    hue_diagnose.py
    pi_welkom.sh
    install.sh
    nas_start.sh
    maak_simulator_map.bat
    README.md
    Dockerfile
    sim_setup.sh
    SIMULATOR_LEESMIJ.md
    start.sh
) do (
    if exist "%NAS_ROOT%\PiServer\%%F" (
        copy /Y "%NAS_ROOT%\PiServer\%%F" "%WERK_MAP%\PiServer\%%F" >nul
        echo    OK: PiServer\%%F
    ) else (
        echo    --: PiServer\%%F niet gevonden
    )
)

:: -- Gedeeld --------------------------------------------------
mkdir "%WERK_MAP%\Gedeeld"
for %%F in (
    pinas_theme.py
    pinas_theme_donker.py
    pinas_theme_licht.py
    pinas_ui.py
    pinas_wachtwoord.py
    pinas_logging.py
    pinas_launcher.py
    pinas_pi_status.py
    controleer_documentatie_consistentie.py
    pinas_schijven.py
    pinas_versies.json
    version.py
    nas_upload.bat
    nas_diagnose.bat
    nas_diagnose.sh
    herstel_backup_hdd.sh
    pinas_iphone_backup.sh
    pinas_iphone_verkennen.sh
    test_suite.py
    NAS_Map_Beheer.pyw
    NAS_Map_Beheer.bat
    download_links.ini
) do (
    if exist "%NAS_ROOT%\Gedeeld\%%F" (
        copy /Y "%NAS_ROOT%\Gedeeld\%%F" "%WERK_MAP%\Gedeeld\%%F" >nul
        echo    OK: Gedeeld\%%F
    ) else (
        echo    --: Gedeeld\%%F niet gevonden
    )
)

:: Gedeeld\ScriptRunner\pi_script_draaien.bat ingetrokken (31 juli 2026,
:: Frans: niet meer los gebruikt - Addons Beheer dekt dit nu)

:: -- Beheer_install.bat in root van ZIP --------------------
if exist "%NAS_ROOT%\Beheer\Beheer_install.bat" (
    copy /Y "%NAS_ROOT%\Beheer\Beheer_install.bat" "%WERK_MAP%\Beheer_install.bat" >nul
    echo    OK: Beheer_install.bat
)

:: -- Installatie (installers zelf, zodat dit ook zonder internet werkt) --
if exist "%NAS_ROOT%\Installatie" (
    mkdir "%WERK_MAP%\Installatie" 2>nul
    xcopy "%NAS_ROOT%\Installatie\*" "%WERK_MAP%\Installatie\" /E /I /Y /Q >nul 2>&1
    echo    OK: Installatie\ (installers - maakt het pakket groter, maar werkt dan ook zonder internet)
) else (
    echo    --: Installatie niet gevonden
)

:: -- INSTALL_TYPE.txt -----------------------------------------
echo minimaal> "%WERK_MAP%\INSTALL_TYPE.txt"

:: -- Wachtwoord ophalen voor anonimisering -------------------
set WW_CACHE=%NAS_ROOT%\Logs\.ww_samba.dat
set HUIDIG_WW=
if exist "%WW_CACHE%" (
    set /p HUIDIG_WW=< "%WW_CACHE%"
)

:: -- Anonimiseren ---------------------------------------------
:: BELANGRIJK: Set-Content -Encoding UTF8 voegt ALTIJD een BOM toe
:: (EF BB BF), wat .bat-bestanden breekt in cmd.exe ("@echo off"
:: wordt dan niet herkend). Daarom schrijven we hier handmatig met
:: .NET UTF8Encoding(false) = UTF-8 ZONDER BOM.
echo.
echo  [Stap 2] Anonimiseren...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$pub = '%WERK_MAP%';" ^
    "$ww = '%HUIDIG_WW%';" ^
    "$enc = New-Object System.Text.UTF8Encoding($false);" ^
    "Get-ChildItem $pub -Include *.bat,*.py,*.sh,*.json,*.md,*.ini,*.cfg -Recurse | ForEach-Object {" ^
    "    $bytes = [System.IO.File]::ReadAllBytes($_.FullName);" ^
    "    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {" ^
    "        $bytes = $bytes[3..($bytes.Length-1)]" ^
    "    };" ^
    "    $c = [System.Text.Encoding]::UTF8.GetString($bytes);" ^
    "    if ($c -eq $null) { return };" ^
    "    $c = $c -replace '192\.168\.\d+\.\d+', 'UW_PI_IP_ADRES';" ^
    "    if ($ww -ne '') { $c = $c -replace [regex]::Escape($ww), 'UW_WACHTWOORD' };" ^
    "    $c = $c -replace 'UW_WACHTWOORD', 'UW_WACHTWOORD';" ^
    "    $c = $c -replace 'GEBRUIKER(?!hrier)[a-z]*', 'GEBRUIKER';" ^
    "    $c = $c -replace 'UW_ZEROTIER_NETWERK_ID', 'UW_ZEROTIER_NETWERK_ID';" ^
    "    [System.IO.File]::WriteAllText($_.FullName, $c, $enc);" ^
    "    Write-Host ('   Schoon: ' + $_.Name)" ^
    "}"

:: -- ZIP aanmaken ---------------------------------------------
echo.
echo  [Stap 3] ZIP aanmaken...
if exist "%ZIP_PAD%" del /f "%ZIP_PAD%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Compress-Archive -Path '%WERK_MAP%\*' -DestinationPath '%ZIP_PAD%' -Force"

if exist "%ZIP_PAD%" (
    echo    OK: %ZIP_PAD%
) else (
    echo    FOUT: ZIP aanmaken mislukt
    pause & exit /b 1
)

:: -- Opruimen -------------------------------------------------
rd /s /q "%WERK_MAP%"

echo.
echo  ============================================================
echo  Starter Kit klaar!
echo  %ZIP_PAD%
echo.
echo  Inhoud: Beheer, Addons, Publicatie, Sync, ArchiefBackup, PiServer, Gedeeld, Installatie
echo  Geanonimiseerd: IP, wachtwoord en ZeroTier netwerk-ID vervangen
echo  Installatie: uitpakken + Beheer_install.bat uitvoeren
echo  ============================================================
echo.
pause
