@echo off
title PiNAS Sync - Installatie
cd /d "%~dp0"

echo ============================================
echo  PiNAS Sync - Eerste installatie
echo  (opvolger van Sync main.py)
echo ============================================
echo.

REM Controleer Python (3.9 of hoger)
python --version >nul 2>&1
if errorlevel 1 (
    echo FOUT: Python niet gevonden!
    echo.
    echo Download Python via:
    echo   https://www.python.org/downloads/
    echo.
    echo BELANGRIJK: vink "Add Python to PATH" aan bij installatie!
    echo.
    pause
    exit /b 1
)

echo Python gevonden:
python --version
echo.

REM Controleer minimale versie (3.9+)
python -c "import sys; exit(0 if sys.version_info >= (3,9) else 1)" >nul 2>&1
if errorlevel 1 (
    echo FOUT: Python 3.9 of hoger vereist.
    echo Download de nieuwste versie via https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Stap 1/2: Tkinter controleren...
python -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo FOUT: Tkinter ontbreekt in deze Python-installatie.
    echo.
    echo Tkinter zit standaard bij de officiele Windows-installer van
    echo python.org. Installeer Python opnieuw via python.org en zorg dat
    echo "tcl/tk and IDLE" aangevinkt blijft tijdens de installatie.
    pause
    exit /b 1
)
echo    OK: Tkinter aanwezig.

echo Stap 2/2: Klaar - geen externe pakketten nodig.
echo          (PiNAS Sync draait volledig op de standaardbibliotheek.)
echo.
echo ============================================
echo  Installatie geslaagd!
echo  Start PiNAS Sync met: start.bat
echo  (of dubbelklik pinas_sync_app.pyw)
echo ============================================
echo.
pause
