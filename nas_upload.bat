@echo off
:: Pi NAS - Upload scripts naar de Pi
:: Dubbelklik om uit te voeren
:: ============================================================
setlocal enabledelayedexpansion

:: Instellingen
set PI_IP=UW_PI_IP_ADRES
set PI_USER=pi
set PI_DIR=/home/pi
set NAS_DIR=%~dp0

:: ============================================================
echo.
echo  Pi NAS - Upload scripts naar de Pi
echo  ============================================================
echo  Pi:   %PI_USER%@%PI_IP%
echo  Map:  %NAS_DIR%
echo  ============================================================
echo.

:: Controleer of scp beschikbaar is
where scp >nul 2>&1
if errorlevel 1 (
    echo  FOUT: scp niet gevonden.
    echo  Installeer OpenSSH via Windows Instellingen ^> Apps ^> Optionele functies.
    pause
    exit /b 1
)

:: Upload bestanden
set UPLOADED=0

for %%F in (
    nas_installer_cli.py
    nas_installer.py
    nas_backup.py
    nas_config.py
    pi_welkom.sh
    install.sh
    nas_start.sh
    smart_plug.py
    smart_plug_config.json
    seagate_web.py
    seagate-web.service
) do (
    if exist "%NAS_DIR%%%F" (
        echo  Uploaden: %%F
        scp "%NAS_DIR%%%F" %PI_USER%@%PI_IP%:%PI_DIR%/%%F
        if errorlevel 1 (
            echo  FOUT: %%F kon niet worden geupload
        ) else (
            echo  OK: %%F
            set /a UPLOADED+=1
        )
    ) else (
        echo  Niet gevonden, overgeslagen: %%F
    )
)

:: Rechten instellen op de Pi
echo.
echo  Rechten instellen op de Pi...
ssh %PI_USER%@%PI_IP% "sudo chown pi:pi %PI_DIR%/*.py %PI_DIR%/*.sh 2>/dev/null; sudo chmod 755 %PI_DIR%/*.py %PI_DIR%/*.sh 2>/dev/null; echo Rechten OK"

:: Ook kopiëren naar /boot/firmware/ zodat auto-update de juiste versie heeft
echo.
echo  Kopiëren naar SD-kaart (/boot/firmware/)...
ssh %PI_USER%@%PI_IP% "for f in %PI_DIR%/*.py %PI_DIR%/*.sh; do sudo cp $f /boot/firmware/ 2>/dev/null; done; echo Bootfs OK"

:: install.sh instellen in .bashrc als nog niet aanwezig
echo.
echo  install.sh instellen in .bashrc...
ssh %PI_USER%@%PI_IP% "grep -q 'install.sh' /home/pi/.bashrc || echo 'source /home/pi/install.sh' >> /home/pi/.bashrc; echo bashrc OK"

echo.
echo  ============================================================
echo  Klaar! %UPLOADED% bestand(en) geupload.
echo  ============================================================
echo.
echo  Tip: log opnieuw in via SSH om de nieuwe versie te laden.
echo  Commando: ssh %PI_USER%@%PI_IP%
echo.
pause
