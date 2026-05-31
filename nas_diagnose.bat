@echo off
:: ============================================================
:: Pi NAS Diagnose
:: ============================================================
setlocal enabledelayedexpansion

set PI_IP=UW_PI_IP_ADRES
set PI_USER=pi
set PI_DIR=/home/pi
set NAS_DIR=%~dp0

echo.
echo  Pi NAS Diagnose
echo  ============================================================
echo  Pi:  %PI_USER%@%PI_IP%
echo  ============================================================
echo.
echo  Wat wil je doen?
echo.
echo  1  Diagnose uitvoeren (eenmalig)
echo  2  Diagnose installeren op Pi (herbruikbaar via SSH)
echo  3  Diagnose verwijderen van Pi
echo  4  Afsluiten
echo.
set /p KEUZE="  Keuze (1-4): "

if "!KEUZE!" equ "1" goto :eenmalig
if "!KEUZE!" equ "2" goto :installeren
if "!KEUZE!" equ "3" goto :verwijderen
goto :einde

:eenmalig
echo.
echo  Uploaden...
scp "%NAS_DIR%nas_diagnose.sh" %PI_USER%@%PI_IP%:%PI_DIR%/nas_diagnose.sh
if errorlevel 1 ( echo  FOUT: Upload mislukt & pause & exit /b 1 )
echo.
echo  ============================================================
ssh %PI_USER%@%PI_IP% "sudo bash %PI_DIR%/nas_diagnose.sh" > "%NAS_DIR%nas_diagnose_output.txt"
type "%NAS_DIR%nas_diagnose_output.txt"
echo  ============================================================
echo.
echo  Output opgeslagen in: %NAS_DIR%nas_diagnose_output.txt
echo.
echo  Script verwijderen...
ssh %PI_USER%@%PI_IP% "rm -f %PI_DIR%/nas_diagnose.sh && echo Verwijderd"
goto :einde

:installeren
echo.
echo  Uploaden...
scp "%NAS_DIR%nas_diagnose.sh" %PI_USER%@%PI_IP%:%PI_DIR%/nas_diagnose.sh
if errorlevel 1 ( echo  FOUT: Upload mislukt & pause & exit /b 1 )
ssh %PI_USER%@%PI_IP% "chmod 755 %PI_DIR%/nas_diagnose.sh && chown pi:pi %PI_DIR%/nas_diagnose.sh && echo OK"
echo.
echo  ============================================================
echo  Geinstalleerd. Starten via SSH:
echo  sudo bash /home/pi/nas_diagnose.sh
echo  ============================================================
goto :einde

:verwijderen
echo.
ssh %PI_USER%@%PI_IP% "rm -f %PI_DIR%/nas_diagnose.sh && echo Verwijderd"
echo  OK: Script verwijderd.
goto :einde

:einde
echo.
pause
