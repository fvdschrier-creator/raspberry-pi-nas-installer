@echo off
:: Start NAS_Map_Beheer.pyw correct
:: Werkt ook als het van een netwerkschijf gestart wordt

set SCRIPT=%~dp0NAS_Map_Beheer.pyw

:: Controleer of script bestaat
if not exist "%SCRIPT%" (
    echo NAS_Map_Beheer.pyw niet gevonden in: %~dp0
    pause
    exit /b 1
)

:: Python zoeken
set PYTHON=
for %%P in (python pythonw) do (
    %%P --version >nul 2>&1
    if not errorlevel 1 set PYTHON=%%P
)

if not defined PYTHON (
    echo Python niet gevonden. Installeer Python via https://www.python.org
    pause
    exit /b 1
)

:: Kopieer naar temp als van netwerk
net use %~d0 >nul 2>&1
if not errorlevel 1 (
    echo Netwerkschijf gedetecteerd - kopieren naar temp...
    copy "%SCRIPT%" "%TEMP%\NAS_Map_Beheer.pyw" >nul
    start "" pythonw "%TEMP%\NAS_Map_Beheer.pyw"
    exit /b
)

:: Lokaal starten
start "" pythonw "%SCRIPT%"
