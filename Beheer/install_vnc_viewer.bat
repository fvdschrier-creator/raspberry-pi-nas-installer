@echo off
:: ============================================================
:: TigerVNC Viewer installeren voor Pi NAS (Pi 5)
:: ============================================================
setlocal enabledelayedexpansion

echo.
echo  Pi NAS - TigerVNC Viewer installeren
echo  ============================================================
echo  TigerVNC Viewer laat je het grafische bureaublad van de
echo  Raspberry Pi 5 zien vanuit Windows - zonder scherm op de Pi.
echo  Verbinding via poort 5901.
echo  ============================================================
echo.

:: Controleer of TigerVNC al geinstalleerd is
set VNCLOC=
for %%P in (
    "%ProgramFiles%\TigerVNC\vncviewer.exe"
    "%ProgramFiles(x86)%\TigerVNC\vncviewer.exe"
) do (
    if exist %%P set VNCLOC=%%P
)

if defined VNCLOC (
    echo  TigerVNC Viewer is al geinstalleerd!
    echo.
    set /p OPEN="  Wil je TigerVNC nu openen en verbinden met de Pi? [J/n]: "
    if /i "!OPEN!" neq "n" (
        set PI_IP=UW_PI_IP_ADRES
        set /p PI_IP="  IP-adres van je Pi [UW_PI_IP_ADRES]: "
        start "" "!VNCLOC!" !PI_IP!:5901
    )
    goto :einde
)

echo  TigerVNC Viewer is nog niet geinstalleerd.
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

:: Automatisch downloaden via PowerShell
echo.
echo  Nieuwste versie ophalen van GitHub...

:: Haal de nieuwste release URL op
powershell -NoProfile -Command ^
    "$r = Invoke-RestMethod 'https://api.github.com/repos/TigerVNC/tigervnc/releases/latest';" ^
    "$a = $r.assets | Where-Object { $_.name -like 'tigervnc64-*.exe' } | Select-Object -First 1;" ^
    "if ($a) { $a.browser_download_url | Out-File '%TEMP%\tigervnc_url.txt' -Encoding ASCII -NoNewline }" ^
    >nul 2>&1

set TIGERVNC_URL=
if exist "%TEMP%\tigervnc_url.txt" (
    set /p TIGERVNC_URL=< "%TEMP%\tigervnc_url.txt"
    del "%TEMP%\tigervnc_url.txt" >nul 2>&1
)

if defined TIGERVNC_URL (
    echo  Downloaden: !TIGERVNC_URL!
    echo  Even geduld...
    powershell -NoProfile -Command ^
        "Invoke-WebRequest -Uri '!TIGERVNC_URL!' -OutFile '%TEMP%\tigervnc_installer.exe' -UseBasicParsing"
    if exist "%TEMP%\tigervnc_installer.exe" (
        echo  Installeren...
        "%TEMP%\tigervnc_installer.exe" /silent /install
        timeout /t 15 /nobreak >nul
        del "%TEMP%\tigervnc_installer.exe" >nul 2>&1
        :: Controleer of installatie gelukt is
        set VNCLOC=
        for %%P in (
            "%ProgramFiles%\TigerVNC\vncviewer.exe"
            "%ProgramFiles(x86)%\TigerVNC\vncviewer.exe"
        ) do (
            if exist %%P set VNCLOC=%%P
        )
        if defined VNCLOC (
            echo  OK: TigerVNC geinstalleerd.
            echo.
            set /p OPEN="  Nu verbinden met de Pi? [J/n]: "
            if /i "!OPEN!" neq "n" (
                start "" "!VNCLOC!" UW_PI_IP_ADRES:5901
            )
        ) else (
            echo  WAARSCHUWING: Installatie mogelijk niet voltooid.
            echo  Controleer of je Administrator rechten hebt.
        )
    ) else (
        echo  Download mislukt - handmatig downloaden...
        goto :handmatig
    )
) else (
    echo  Kon nieuwste versie niet ophalen - handmatig downloaden...
    goto :handmatig
)
goto :einde

:handmatig
echo.
echo  Downloadpagina openen in browser...
start "" "https://github.com/TigerVNC/tigervnc/releases/latest"
echo.
echo  ============================================================
echo  Stappen:
echo  1. Download: tigervnc64-x.x.x.exe
echo  2. Dubbelklik en installeer
echo  3. Start TigerVNC Viewer via het Startmenu
echo  4. Typ als VNC server: UW_PI_IP_ADRES:5901
echo  5. Voer het VNC wachtwoord in
echo  ============================================================
goto :einde

:geannuleerd
echo  Geannuleerd.

:einde
echo.
echo  ============================================================
echo  TigerVNC verbinden met Pi 5:
echo    VNC server: UW_PI_IP_ADRES:5901  (let op poort 5901!)
echo    Wachtwoord: ingesteld via vncpasswd op de Pi
echo  ============================================================
echo.
pause
