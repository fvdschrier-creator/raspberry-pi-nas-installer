@echo off
setlocal

:: ============================================
::  Archief Backup Bewaking opstarten
::  (integriteitscontrole + veilige spiegel Z -> H)
:: ============================================

set "ROOT=%~dp0"
set "PYW=pythonw"
set "PY=python"

where pythonw >nul 2>&1
if %ERRORLEVEL% NEQ 0 set "PYW=%ROOT%..\..\AppData\Local\Programs\Python\Python313\pythonw.exe"
where python  >nul 2>&1
if %ERRORLEVEL% NEQ 0 set "PY=%ROOT%..\..\AppData\Local\Programs\Python\Python313\python.exe"

echo.
echo ============================================
echo  Archief Backup Bewaking opstarten...
echo ============================================
echo.

cd /d "%ROOT%"

"%PYW%" "%ROOT%archief_backup_bewaking.pyw"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Eerste poging mislukt - opnieuw met python.exe zodat een
    echo eventuele foutmelding zichtbaar blijft...
    "%PY%" "%ROOT%archief_backup_bewaking.pyw"
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo FOUT bij opstarten. Controleer of Python met Tkinter is
        echo geinstalleerd ^(python -m tkinter moet een venster tonen^).
        pause
    )
)

endlocal