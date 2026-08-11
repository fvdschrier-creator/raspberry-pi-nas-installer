@echo off
setlocal enabledelayedexpansion

:: IP ophalen uit picontrol.cfg
set PI_IP=UW_PI_IP_ADRES
set CFG=%~dp0picontrol.cfg
if not exist "%CFG%" set CFG=C:\PiNAS\Beheer\picontrol.cfg
if exist "%CFG%" (
    rem /b = begin van regel, /c: = letterlijke string "ip =" (anders matcht de
    rem spatie elke regel met een '=' erin, zoals thema = ..., en pakt de lus de
    rem verkeerde waarde -> Systeemfout 67 op een niet-bestaande netwerknaam).
    for /f "tokens=3 delims= " %%A in ('findstr /i /b /c:"ip =" "%CFG%"') do set PI_IP=%%A
)

rem Controleer dat PI_IP gevuld is en geen themawaarde (eenvoudig: bevat een punt).
set "PI_IP=!PI_IP: =!"
echo !PI_IP!| findstr "." >nul
if errorlevel 1 (
    echo.
    echo FOUT: kon het Pi-IP-adres niet uit picontrol.cfg lezen.
    echo Gevonden waarde: "!PI_IP!"
    echo Controleer de [pi]-sectie in %CFG% ^(ip = UW_PI_IP_ADRES^).
    echo.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo  NAS Toegang herstellen - LanMan fix
echo ==========================================
echo.
echo Dit script herstelt de toegang tot de Pi NAS
echo als Windows de verbinding weigert met "Toegang
echo geweigerd" of "Systeemfout 5".
echo.
echo Wat dit doet:
echo   1. Past Windows LanMan beveiliging aan
echo      zodat de NAS-shares bereikbaar worden
echo   2. Schakelt onveilige gastverbindingen in
echo      (vereist voor Pi Samba-shares)
echo   3. Koppelt Y: en Z: opnieuw aan de NAS
echo.
echo Vereist: Administrator rechten (UAC-melding volgt)
echo.
echo Druk op een toets om te beginnen...
pause >nul
echo.

:: -- Administrator check -------------------------------------
net session >nul 2>&1
if errorlevel 1 (
    echo Dit script heeft Administrator rechten nodig.
    echo Rechtsklik op het script en kies "Als Administrator uitvoeren".
    pause
    exit /b 1
)

:: -- LanMan register aanpassen --------------------------------
echo Stap 1: LanMan beveiliging aanpassen...
reg add "HKLM\SYSTEM\CurrentControlSet\Services\LanmanWorkstation\Parameters" /v "AllowInsecureGuestAuth" /t REG_DWORD /d 1 /f >nul
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Lsa" /v "LmCompatibilityLevel" /t REG_DWORD /d 1 /f >nul
echo OK: Register aangepast.
echo.

:: -- Bestaande verbindingen verwijderen -----------------------
echo Stap 2: Bestaande NAS-verbindingen verwijderen...
echo.
echo LET OP: sluit eerst Sync ^& Backup ^(PiNAS Sync^) en alle Verkenner-
echo Y: of Z: open hebben staan. Een nog-geopende koppeling kan
echo voorkomen dat Windows de letter echt vrijgeeft, wat later
echo "Systeemfout 67" geeft bij het opnieuw koppelen.
echo.
echo Sluit nu Sync/Backup en Verkenner-vensters met Y: of Z:.
echo Druk daarna op een toets om door te gaan...
pause >nul

net use Y: /delete /y >nul 2>&1
net use Z: /delete /y >nul 2>&1
:: Geef Windows een moment om de koppelingen administratief
:: echt los te laten voordat we opnieuw koppelen.
timeout /t 3 /nobreak >nul

:: Forceer nogmaals, voor het geval de eerste keer niet aansloeg
net use Y: /delete /y >nul 2>&1
net use Z: /delete /y >nul 2>&1
timeout /t 2 /nobreak >nul

:: Controleer of de letters nu echt vrij zijn
net use Y: >nul 2>&1
if not errorlevel 1 (
    echo WAARSCHUWING: Y: kon niet losgekoppeld worden ^(nog in gebruik?^).
    echo Sluit alle programma's die Y: gebruiken en draai dit script opnieuw.
)
net use Z: >nul 2>&1
if not errorlevel 1 (
    echo WAARSCHUWING: Z: kon niet losgekoppeld worden ^(nog in gebruik?^).
    echo Sluit alle programma's die Z: gebruiken en draai dit script opnieuw.
)
echo OK: Verbindingen verwijderd.
echo.

:: -- Opnieuw koppelen -----------------------------------------
echo Stap 3: Y: en Z: opnieuw koppelen...
echo.
echo Voer het NAS-wachtwoord in (gebruiker: pi):
set /p NASWW=Wachtwoord: 
echo.

net use Y: \\!PI_IP!\PiNas /user:pi %NASWW% /persistent:yes
if errorlevel 1 (
    echo Eerste poging mislukt, nog een keer proberen na korte pauze...
    timeout /t 3 /nobreak >nul
    net use Y: \\!PI_IP!\PiNas /user:pi %NASWW% /persistent:yes
)
if errorlevel 1 (
    echo WAARSCHUWING: Y: koppelen mislukt.
    echo Controleer of de Pi bereikbaar is en het wachtwoord klopt.
) else (
    echo OK: Y: gekoppeld (PiNas - SSD)
)

net use Z: \\!PI_IP!\Backup /user:pi %NASWW% /persistent:yes
if errorlevel 1 (
    echo Eerste poging mislukt, nog een keer proberen na korte pauze...
    timeout /t 3 /nobreak >nul
    net use Z: \\!PI_IP!\Backup /user:pi %NASWW% /persistent:yes
)
if errorlevel 1 (
    echo WAARSCHUWING: Z: koppelen mislukt.
) else (
    echo OK: Z: gekoppeld (Backup - HDD)
)
echo.

echo ==========================================
echo  Klaar!
echo ==========================================
echo.
echo Y: en Z: zijn nu gekoppeld aan de Pi NAS.
echo.
echo Als het nog steeds niet werkt:
echo   1. Herstart Windows en probeer opnieuw
echo   2. Controleer of de Pi aan staat (ping !PI_IP!)
echo   3. Controleer het NAS-wachtwoord (Beheer - Beveiliging)
echo.
pause
