@echo off
:: ============================================================
:: Maakt NAS_Simulator map met alle benodigde bestanden
:: Werkt automatisch vanuit elke map - geen pad instellen nodig
:: ============================================================
setlocal enabledelayedexpansion

:: Automatisch eigen map detecteren
set NAS_MAP=%~dp0
set NAS_MAP=%NAS_MAP:~0,-1%

:: NAS_Simulator staat naast de huidige map
for %%I in ("%NAS_MAP%\..") do set PARENT=%%~fI
set SIM_MAP=%PARENT%\NAS_Simulator

echo.
echo  Pi NAS Simulator map aanmaken
echo  ============================================================
echo  Van:  %NAS_MAP%
echo  Naar: %SIM_MAP%
echo  ============================================================
echo.

if not exist "%SIM_MAP%" mkdir "%SIM_MAP%"

set GEKOPIEERD=0

:: Simulator bestanden
for %%F in (
    start_simulator.bat
    Dockerfile
    start.sh
    sim_setup.sh
    SIMULATOR_LEESMIJ.md
) do (
    if exist "%NAS_MAP%\%%F" (
        copy /Y "%NAS_MAP%\%%F" "%SIM_MAP%\%%F" >nul
        echo  OK: %%F
        set /a GEKOPIEERD+=1
    ) else (
        echo  SKIP: %%F niet gevonden
    )
)

:: Laatste installer versies meekopieren
for %%F in (
    nas_installer.py
    nas_installer_cli.py
    smart_plug.py
    smart_plug_config.json
) do (
    if exist "%NAS_MAP%\%%F" (
        copy /Y "%NAS_MAP%\%%F" "%SIM_MAP%\%%F" >nul
        echo  OK: %%F (laatste versie^)
        set /a GEKOPIEERD+=1
    )
)

echo.
echo  ============================================================
echo  !GEKOPIEERD! bestanden gekopieerd naar NAS_Simulator.
echo  Simulator starten: dubbelklik start_simulator.bat in:
echo  %SIM_MAP%
echo  ============================================================
echo.
pause
