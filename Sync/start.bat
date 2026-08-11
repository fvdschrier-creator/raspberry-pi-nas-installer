@echo off
setlocal

:: ============================================
::  PiNAS Sync opstarten
::  (opvolger van Sync main.py - Tkinter)
:: ============================================

set "ROOT=%~dp0"
set "PYW=%ROOT%..\..\AppData\Local\Programs\Python\Python313\pythonw.exe"
set "PY=%ROOT%..\..\AppData\Local\Programs\Python\Python313\python.exe"

:: Python via PATH heeft voorrang als beschikbaar
where pythonw >nul 2>&1
if %ERRORLEVEL% EQU 0 set "PYW=pythonw"
where python  >nul 2>&1
if %ERRORLEVEL% EQU 0 set "PY=python"

:: OPMERKING: bewust GEEN Administrator-herstart.
:: Windows isoleert netwerkschijven (Y:, Z:, ...) per gebruikerssessie;
:: een verhoogd proces ziet die koppelingen niet meer.
:: PC Image Backup vraagt zelf gericht om elevatie voor alleen die ene actie.

echo.
echo ============================================
echo  PiNAS Sync opstarten...
echo ============================================
echo.

cd /d "%ROOT%"

:: pythonw start zonder zwart consolevenster (het is een .pyw)
"%PYW%" "%ROOT%pinas_sync_app.pyw"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Eerste poging mislukt - opnieuw proberen met python.exe zodat
    echo een eventuele foutmelding zichtbaar blijft...
    "%PY%" "%ROOT%pinas_sync_app.pyw"
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo FOUT bij opstarten. Controleer of Python met Tkinter is
        echo geinstalleerd ^(python -m tkinter moet een venster tonen^).
        pause
    )
)

endlocal
