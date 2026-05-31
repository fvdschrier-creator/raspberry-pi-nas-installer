@echo off
:: ============================================================
:: VNC Viewer installeren voor Pi NAS
:: ============================================================
setlocal enabledelayedexpansion

echo.
echo  Pi NAS - VNC Viewer installeren
echo  ============================================================
echo  VNC Viewer laat je de grafische omgeving van de Pi zien
echo  vanuit Windows - zonder scherm op de Pi.
echo  ============================================================
echo.

:: Controleer of VNC Viewer al geinstalleerd is
set VNCLOC=
if exist "%ProgramFiles%\RealVNC\VNC Viewer\vncviewer.exe" set VNCLOC=%ProgramFiles%\RealVNC\VNC Viewer\vncviewer.exe
if exist "%ProgramFiles(x86)%\RealVNC\VNC Viewer\vncviewer.exe" set VNCLOC=%ProgramFiles(x86)%\RealVNC\VNC Viewer\vncviewer.exe

if defined VNCLOC (
    echo  VNC Viewer is al geinstalleerd!
    echo.
    set /p OPEN="  Wil je VNC Viewer nu openen? [J/n]: "
    if /i "!OPEN!" neq "n" (
        set /p PI_IP="  IP-adres van je Pi (bijv. UW_PI_IP_ADRES): "
        if "!PI_IP!" neq "" (
            start "" "!VNCLOC!" !PI_IP!
        ) else (
            start "" "!VNCLOC!"
        )
    )
    goto :einde
)

echo  VNC Viewer is nog niet geinstalleerd.
echo.
echo  Keuze:
echo  1  Automatisch downloaden en installeren
echo  2  Handmatig downloaden (opent browser)
echo  3  Annuleren
echo.
set /p KEUZE="  Keuze (1-3): "

if "!KEUZE!" equ "2" goto :handmatig
if "!KEUZE!" equ "3" goto :geannuleerd
if "!KEUZE!" neq "1" goto :geannuleerd

:: Automatisch downloaden
echo.
echo  Downloaden via browser naar Downloads map...
echo  Installeer daarna handmatig via de wizard.
echo.

:: Open downloadpagina in browser
start "" "https://www.realvnc.com/en/connect/download/viewer/windows/"

echo  ============================================================
echo  De downloadpagina is geopend in je browser.
echo.
echo  Stappen:
echo  1. Klik op de downloadknop op de website
echo  2. Sla het bestand op
echo  3. Dubbelklik op het gedownloade bestand
echo  4. Volg de installatie-wizard
echo  5. Start VNC Viewer via het Startmenu
echo  6. Typ je Pi IP-adres in de adresbalk
echo  7. Klik op Use VNC Viewer without signing in
echo  ============================================================
goto :einde

:handmatig
echo.
echo  Downloadpagina openen in browser...
start "" "https://www.realvnc.com/en/connect/download/viewer/windows/"
echo.
echo  Download de Windows versie en installeer via de wizard.
goto :einde

:geannuleerd
echo  Geannuleerd.

:einde
echo.
echo  ============================================================
echo  Na installatie verbinden:
echo  1. Open VNC Viewer
echo  2. Typ je Pi IP-adres in de adresbalk
echo  3. Log in met Pi OS gebruikersnaam en wachtwoord
echo  ============================================================
echo.
pause
