@echo off
:: ============================================================
:: Eenmalige setup — kopieert ALLE NAS-bestanden naar NAS-map
:: Gebruik dit bij eerste installatie of na toevoeging van
:: nieuwe bestanden door Claude
:: ============================================================
setlocal enabledelayedexpansion

set NAS_MAP=C:\Users\UW_GEBRUIKERSNAAM\OneDrive\Documenten\Desktop\NAS
set DOWNLOADS=%USERPROFILE%\Downloads

echo.
echo  Pi NAS - Initiële setup NAS-map
echo  ============================================================
echo  Kopieert alle NAS-bestanden naar: %NAS_MAP%
echo  ============================================================
echo.

if not exist "%NAS_MAP%" mkdir "%NAS_MAP%"

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
    smart_plug_config.json
    seagate_web.py
    seagate-web.service
    nas_upload.bat
    kopieer_naar_nas.bat
    kopieer_helper.ps1
    nas_diagnose.sh
    nas_diagnose.bat
    install_vnc_viewer.bat
    initieel_setup.bat
    README.md
    raspberry_pi_nas_volledig.pdf
) do (
    if exist "%DOWNLOADS%\%%F" (
        copy /Y "%DOWNLOADS%\%%F" "%NAS_MAP%\%%F" >nul
        echo  OK: %%F
        set /a GEKOPIEERD+=1
    ) else (
        echo  SKIP: %%F niet in Downloads
    )
)

echo.
echo  ============================================================
echo  !GEKOPIEERD! bestand(en) gekopieerd naar NAS-map.
echo  Download ontbrekende bestanden uit het gesprek met Claude
echo  en voer dit script opnieuw uit.
echo  ============================================================
echo.
pause
