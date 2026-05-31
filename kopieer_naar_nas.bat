@echo off
:: ============================================================
:: Kopieert nieuwe NAS-bestanden van Downloads naar NAS-map
:: Configuratie: pas NAS_MAP aan naar jouw locatie
:: ============================================================
setlocal enabledelayedexpansion

:: ── CONFIGURATIE ─────────────────────────────────────────────
set NAS_MAP=C:\Users\UW_GEBRUIKERSNAAM\OneDrive\Documenten\Desktop\NAS
:: ─────────────────────────────────────────────────────────────

set DOWNLOADS=%USERPROFILE%\Downloads
set OLD_MAP=%DOWNLOADS%\Download Old NAS

if not exist "%OLD_MAP%" mkdir "%OLD_MAP%"

echo.
echo  Kopieer NAS-downloads naar NAS-map
echo  ============================================================
echo  NAS-map: %NAS_MAP%
echo  ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%NAS_MAP%\kopieer_helper.ps1" -NasMap "%NAS_MAP%" -Downloads "%DOWNLOADS%" -OldMap "%OLD_MAP%"

echo.
set /p UPLOAD="  Nu uploaden naar Pi? [J/n]: "
if /i "!UPLOAD!" neq "n" (
    call "%NAS_MAP%\nas_upload.bat"
)

echo.
echo  Backup naar Y:\NAS...
if exist "Y:\NAS\" (
    xcopy /Y /E /I "%NAS_MAP%\*.*" "Y:\NAS\" >nul 2>&1
    echo  OK: Gekopieerd naar Y:\NAS
) else (
    echo  SKIP: Y:\NAS niet beschikbaar
)
echo.
pause
