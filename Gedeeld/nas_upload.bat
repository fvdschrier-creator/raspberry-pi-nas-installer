@echo off
:: Pi NAS - Upload scripts naar de Pi
:: Staat in: C:\PiNAS\Gedeeld\
:: Haalt elk bestand op uit de juiste submap
:: ============================================================
setlocal

set PI_IP=UW_PI_IP_ADRES
set PI_USER=pi
set PI_DIR=/home/pi
set SSH_OPT=-o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=10

for %%I in ("%~dp0..") do set NAS_ROOT=%%~fI

echo.
echo  Pi NAS - Upload scripts naar de Pi
echo  ============================================================
echo  Pi:       %PI_USER%@%PI_IP%
echo  NAS root: %NAS_ROOT%
echo  ============================================================
echo.

where scp >nul 2>&1
if errorlevel 1 (
    echo  FOUT: scp niet gevonden.
    pause
    exit /b 1
)

set UPLOADED=0
set OVERGESLAGEN=0

echo  [PiServer]
call :upload "%NAS_ROOT%\PiServer\nas_installer.py"        nas_installer.py
call :upload "%NAS_ROOT%\PiServer\nas_installer_cli.py"    nas_installer_cli.py
call :upload "%NAS_ROOT%\PiServer\seagate_web.py"          seagate_web.py
call :upload "%NAS_ROOT%\PiServer\seagate-web.service"     seagate-web.service
call :upload "%NAS_ROOT%\PiServer\smart_plug.py"           smart_plug.py
call :upload "%NAS_ROOT%\PiServer\smart_plug_config.json"  smart_plug_config.json
call :upload "%NAS_ROOT%\PiServer\hue_diagnose.py"         hue_diagnose.py
call :upload "%NAS_ROOT%\PiServer\pi_welkom.sh"            pi_welkom.sh
call :upload "%NAS_ROOT%\PiServer\install.sh"              install.sh
call :upload "%NAS_ROOT%\PiServer\nas_start.sh"            nas_start.sh

echo.
echo  [Gedeeld]
call :upload "%NAS_ROOT%\Gedeeld\nas_diagnose.sh"       nas_diagnose.sh
call :upload "%NAS_ROOT%\Gedeeld\herstel_backup_hdd.sh" herstel_backup_hdd.sh
call :upload "%NAS_ROOT%\Gedeeld\pinas_theme.py"        pinas_theme.py
call :upload "%NAS_ROOT%\Gedeeld\pinas_wachtwoord.py"   pinas_wachtwoord.py
call :upload "%NAS_ROOT%\Gedeeld\pinas_logging.py"      pinas_logging.py
call :upload "%NAS_ROOT%\Gedeeld\version.py"             version.py

echo.
echo  Rechten instellen op de Pi...
ssh %SSH_OPT% %PI_USER%@%PI_IP% "sudo chown pi:pi %PI_DIR%/*.py %PI_DIR%/*.sh 2>/dev/null; sudo chmod 755 %PI_DIR%/*.py %PI_DIR%/*.sh 2>/dev/null; echo Rechten OK"

echo.
echo  Kopieren naar SD-kaart (/boot/firmware/)...
ssh %SSH_OPT% %PI_USER%@%PI_IP% "for f in %PI_DIR%/*.py %PI_DIR%/*.sh; do sudo cp $f /boot/firmware/ 2>/dev/null; done; echo Bootfs OK"

echo.
echo  install.sh instellen in .bashrc...
ssh %SSH_OPT% %PI_USER%@%PI_IP% "grep -q 'install.sh' /home/pi/.bashrc || echo 'source /home/pi/install.sh' >> /home/pi/.bashrc; echo bashrc OK"

echo.
echo  Services herstarten op de Pi...
ssh %SSH_OPT% -t %PI_USER%@%PI_IP% "sudo systemctl restart seagate-web && echo seagate-web: herstart OK || echo seagate-web: herstart MISLUKT"

echo.
echo  ============================================================
echo  Klaar! %UPLOADED% bestand(en) geupload, %OVERGESLAGEN% overgeslagen.
echo  ============================================================
echo.
pause
goto :eof

:upload
    if exist %1 (
        echo  Uploaden: %2
        scp %1 %PI_USER%@%PI_IP%:%PI_DIR%/%2
        if errorlevel 1 (
            echo  FOUT: %2 kon niet worden geupload
        ) else (
            echo  OK: %2
            set /a UPLOADED+=1
        )
    ) else (
        echo  Niet gevonden, overgeslagen: %2
        set /a OVERGESLAGEN+=1
    )
    goto :eof
