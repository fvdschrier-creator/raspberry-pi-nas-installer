@echo off
:: Pi NAS Suite Installer v1.1.2
setlocal enabledelayedexpansion
chcp 65001 >nul

set LOG=%TEMP%\picontrol_debug.log
echo Pi NAS Install Debug Log - %DATE% %TIME% > "%LOG%"
echo. >> "%LOG%"

echo [DEBUG] Start installatie bat
echo [DEBUG] Start >> "%LOG%"

rem Administrator check
net session >nul 2>&1
if errorlevel 1 (
    echo [DEBUG] GEEN admin rechten - herstarten als elevated
    echo [DEBUG] Geen admin >> "%LOG%"
    rem 16 juli 2026: %* toegevoegd - zonder dit werden PUTTY=J/VNC=J/etc.
    rem vinkjes stilletjes weggegooid bij elke elevatie (bijna elke run,
    rem want dit script heeft vrijwel altijd admin-rechten nodig).
    powershell -NoProfile -Command "Start-Process cmd -ArgumentList '/c \"%~f0\" %*' -Verb RunAs"
    exit
)
echo [DEBUG] Admin OK
echo [DEBUG] Admin OK >> "%LOG%"

rem 16 juli 2026: welke onderdelen zijn aangevinkt in Pi_NAS_Menu.pyw? Was
rem eerder een dode doorgeefluik - de vinkjes deden niets, dit script deed
rem altijd alles. Nu gaten Stap 5/6/6a2/7 hierop (6b/6c WSL+Docker op
rem 11 augustus 2026 verwijderd, zie verderop).
set DO_PUTTY=0
set DO_VNC=0
set DO_WINSCP=0
set DO_SCHIJVEN=0
:parse_args
if "%~1"=="" goto :args_klaar
if /i "%~1"=="PUTTY=J"    set DO_PUTTY=1
if /i "%~1"=="VNC=J"      set DO_VNC=1
if /i "%~1"=="WINSCP=J"   set DO_WINSCP=1
if /i "%~1"=="SCHIJVEN=J" set DO_SCHIJVEN=1
shift
goto :parse_args
:args_klaar
:: Type detecteren
set INST_TYPE=minimaal
set BRON=%~dp0
if exist "%BRON%INSTALL_TYPE.txt" (
    set /p INST_TYPE=< "%BRON%INSTALL_TYPE.txt"
)
echo [DEBUG] Type: !INST_TYPE! >> "%LOG%"

:: Bestaande installatie - status-check i.p.v. altijd vragen
:: Vergelijkt de bestaande bestanden tegen Gedeeld\pinas_versies.json
:: (dezelfde manier als Structuurcheck's VERSIE-CONTROLE): alles aanwezig
:: en actueel -> installatie overslaan, alleen instellingen/verbindingen
:: verderop in het script checken. Iets ontbreekt of is verouderd (of dit
:: is de allereerste installatie) -> bestanden bijwerken, zonder daar
:: eerst nog een keer los toestemming voor te hoeven vragen.
set INSTALLATIE_STATUS=NIEUW
if exist "C:\PiNAS\Gedeeld\pinas_versies.json" (
    for /f "delims=" %%R in ('powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "try {" ^
        "    $manifest = Get-Content 'C:\PiNAS\Gedeeld\pinas_versies.json' -Raw | ConvertFrom-Json;" ^
        "    $root = 'C:\PiNAS'; $ok = $true;" ^
        "    foreach ($prop in $manifest.PSObject.Properties) {" ^
        "        if ($prop.Name.StartsWith('_')) { continue };" ^
        "        $pad = Join-Path $root $prop.Name;" ^
        "        if (-not (Test-Path $pad)) { $ok = $false; break };" ^
        "        $verwacht = [datetime]::ParseExact($prop.Value, 'yyyy-MM-dd HH:mm', $null);" ^
        "        $echt = (Get-Item $pad).LastWriteTime;" ^
        "        if ($echt -lt $verwacht) { $ok = $false; break }" ^
        "    };" ^
        "    if ($ok) { Write-Output 'GEZOND' } else { Write-Output 'VEROUDERD' }" ^
        "} catch { Write-Output 'VEROUDERD' }"') do set INSTALLATIE_STATUS=%%R
)

if "!INSTALLATIE_STATUS!"=="GEZOND" (
    echo Bestaande installatie gevonden in C:\PiNAS\ en is actueel.
    echo Bestanden worden niet opnieuw gekopieerd - alleen instellingen en
    echo verbindingen ^(SSH-sleutel, PuTTY, schijven^) worden gecontroleerd.
    echo.
) else (
    if "!INSTALLATIE_STATUS!"=="VEROUDERD" (
        echo Bestaande installatie gevonden in C:\PiNAS\, maar niet meer helemaal actueel.
        echo Bestanden worden nu bijgewerkt.
    ) else (
        echo Geen bestaande installatie gevonden - nieuwe installatie wordt gestart.
    )
    echo.
)

:: PI_IP vragen
set PI_IP=UW_PI_IP_ADRES
set /p "PI_IP=  Pi IP-adres [UW_PI_IP_ADRES]: "
if "!PI_IP!"=="" set PI_IP=UW_PI_IP_ADRES
echo.

rem Bestaande thema-keuze bewaren (licht/donker) - picontrol.cfg wordt
rem verderop een paar keer volledig herschreven (Stap 1b, Stap 7), en
rem zonder dit te bewaren zou een eerder gekozen thema stilletjes
rem verloren gaan en terugvallen op de standaard (donker).
set BESTAAND_THEMA=
if exist "C:\PiNAS\Beheer\picontrol.cfg" (
    for /f "tokens=1,* delims==" %%A in ('findstr /i "^thema" "C:\PiNAS\Beheer\picontrol.cfg"') do (
        set "BESTAAND_THEMA=%%B"
    )
)
if defined BESTAAND_THEMA (
    for /f "tokens=* delims= " %%T in ("!BESTAAND_THEMA!") do set BESTAAND_THEMA=%%T
)


rem Stap voor stap testen
echo.
echo Stap 0: LanManFix...
reg add "HKLM\SYSTEM\CurrentControlSet\Services\LanmanWorkstation\Parameters" /v "AllowInsecureGuestAuth" /t REG_DWORD /d 1 /f >nul 2>&1
if errorlevel 1 (echo FOUT stap 0a) else (echo OK stap 0a)
reg add "HKLM\SYSTEM\CurrentControlSet\Control\Lsa" /v "LmCompatibilityLevel" /t REG_DWORD /d 1 /f >nul 2>&1
if errorlevel 1 (echo FOUT stap 0b) else (echo OK stap 0b)
echo Stap 0 >> "%LOG%"

if "!INSTALLATIE_STATUS!"=="GEZOND" goto :bestanden_actueel

echo Stap 1: Mappen aanmaken...
for %%D in ("C:\PiNAS" "C:\PiNAS\Beheer" "C:\PiNAS\Sync" "C:\PiNAS\PiServer" "C:\PiNAS\Logs" "C:\PiNAS\Gedeeld" "C:\PiNAS\ArchiefBackup") do (
    if not exist %%D mkdir %%D
)
if "!INST_TYPE!"=="schaduw" (
    for %%D in ("C:\PiNAS\Publicatie" "C:\PiNAS\Installatie") do (
        if not exist %%D mkdir %%D
    )
)
echo OK stap 1
echo Stap 1 >> "%LOG%"
echo Stap 1b: Beheer bestanden installeren...
set BRON=%~dp0
for %%F in (Pi_NAS_Menu.pyw pi_nas_setup.pyw Pi_NAS_Menu.ico lanman_fix.py install_vnc_viewer.py Beheer_install.bat pinas_backup_beheer.pyw pinas_image_backup.pyw) do (
    if exist "%BRON%Beheer\%%F" (
        xcopy "%BRON%Beheer\%%F" "C:\PiNAS\Beheer\" /Y /Q >nul 2>&1
        echo    OK: %%F
    ) else if exist "%BRON%%%F" (
        xcopy "%BRON%%%F" "C:\PiNAS\Beheer\" /Y /Q >nul 2>&1
        echo    OK: %%F
    )
)
(
echo [pi]
echo ip = !PI_IP!
echo.
echo [paden]
echo install_dir = C:\PiNAS\Beheer
echo install_type = !INST_TYPE!
if defined BESTAAND_THEMA (
echo.
echo [ui]
echo thema = !BESTAAND_THEMA!
)
) > "C:\PiNAS\Beheer\picontrol.cfg"
echo    OK: picontrol.cfg
if exist "%BRON%Beheer\core" (
    if not exist "C:\PiNAS\Beheer\core" mkdir "C:\PiNAS\Beheer\core"
    xcopy "%BRON%Beheer\core\*" "C:\PiNAS\Beheer\core\" /Y /Q >nul 2>&1
    echo    OK: core\
)
if exist "%BRON%Beheer\assets" (
    if not exist "C:\PiNAS\Beheer\assets" mkdir "C:\PiNAS\Beheer\assets"
    xcopy "%BRON%Beheer\assets\*" "C:\PiNAS\Beheer\assets\" /Y /Q >nul 2>&1
    echo    OK: assets\
)
echo Stap 1b >> "%LOG%"

echo Stap 1c: Gedeeld modules installeren...
for %%F in (pinas_theme.py pinas_theme_donker.py pinas_theme_licht.py pinas_ui.py pinas_wachtwoord.py pinas_logging.py pinas_launcher.py pinas_schijven.py pinas_versies.json version.py test_suite.py nas_upload.py nas_diagnose.py nas_diagnose.sh herstel_backup_hdd.sh maak_starterkit.py maak_publieke_versie.py download_links.ini) do (
    if exist "%BRON%Gedeeld\%%F" (
        xcopy "%BRON%Gedeeld\%%F" "C:\PiNAS\Gedeeld\" /Y /Q >nul 2>&1
        echo    OK: %%F
    ) else if exist "%BRON%%%F" (
        xcopy "%BRON%%%F" "C:\PiNAS\Gedeeld\" /Y /Q >nul 2>&1
        echo    OK: %%F
    )
)
if exist "%BRON%Gedeeld\ScriptRunner" (
    if not exist "C:\PiNAS\Gedeeld\ScriptRunner" mkdir "C:\PiNAS\Gedeeld\ScriptRunner"
    xcopy "%BRON%Gedeeld\ScriptRunner\*" "C:\PiNAS\Gedeeld\ScriptRunner\" /Y /Q >nul 2>&1
    echo    OK: ScriptRunner\
)
echo Stap 1c >> "%LOG%"

echo Stap 1d: Sync ^& Backup (PiNAS Sync) installeren...
if exist "%BRON%Sync\pinas_sync_app.pyw" (
    xcopy "%BRON%Sync\*" "C:\PiNAS\Sync\" /E /I /Y /Q >nul 2>&1
    echo OK: Sync ^& Backup geinstalleerd.
) else (
    echo INFO: Sync ^& Backup niet gevonden - later via Pi NAS Menu.
)
echo Stap 1d >> "%LOG%"

echo Stap 1e: PiNAS server scripts...
if exist "%BRON%PiServer\nas_installer.py" (
    xcopy "%BRON%PiServer\*" "C:\PiNAS\PiServer\" /E /I /Y /Q >nul 2>&1
    echo OK: PiNAS scripts geinstalleerd.
) else (
    echo INFO: PiNAS scripts niet gevonden.
)
echo Stap 1e >> "%LOG%"

echo Stap 1f: ArchiefBackup installeren...
if exist "%BRON%ArchiefBackup\archief_backup_bewaking.pyw" (
    xcopy "%BRON%ArchiefBackup\*" "C:\PiNAS\ArchiefBackup\" /E /I /Y /Q >nul 2>&1
    echo OK: ArchiefBackup geinstalleerd.
) else (
    echo INFO: ArchiefBackup niet gevonden - later via Backup Beheer.
)
echo Stap 1f >> "%LOG%"

echo Stap 1g: Publicatie installeren...
if "!INST_TYPE!"=="schaduw" (
    if exist "%BRON%Publicatie\PiNAS_Suite_Handleiding.pdf" (
        xcopy "%BRON%Publicatie\*" "C:\PiNAS\Publicatie\" /E /I /Y /Q >nul 2>&1
        echo OK: Publicatie geinstalleerd.
    ) else (
        echo INFO: Publicatie-bestanden niet gevonden.
    )
) else (
    echo INFO: overgeslagen bij minimale installatie.
)
echo Stap 1g >> "%LOG%"

:bestanden_actueel

echo Stap 2: Python controleren...
python --version > "%TEMP%\pyver.txt" 2>&1
set /p PYVER=< "%TEMP%\pyver.txt"
echo Python: !PYVER!
echo Stap 2 Python: !PYVER! >> "%LOG%"

for /f "tokens=2 delims= " %%V in ("!PYVER!") do set PYVER_NUM=%%V
for /f "tokens=1,2 delims=." %%A in ("!PYVER_NUM!") do (
    set PYVER_MAJOR=%%A
    set PYVER_MINOR=%%B
)
set PYTHON_OUDERWETS=0
if !PYVER_MAJOR! LSS 3 set PYTHON_OUDERWETS=1
if !PYVER_MAJOR! EQU 3 if !PYVER_MINOR! LSS 10 set PYTHON_OUDERWETS=1

if "!PYTHON_OUDERWETS!"=="1" (
    echo Python !PYVER_NUM! is ouder dan de vereiste 3.10 - bijwerken...
    set PYTHON_INSTALLER=
    for %%F in ("%BRON%Installatie\python-3*.exe" "%BRON%python-3*.exe") do (
        if exist "%%F" set PYTHON_INSTALLER=%%F
    )
    if defined PYTHON_INSTALLER (
        echo Python-installer gevonden in Installatie-map: !PYTHON_INSTALLER!
    ) else (
        echo Python niet lokaal gevonden - downloaden...
        powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.14.6/python-3.14.6-amd64.exe' -OutFile '%TEMP%\python_installer.exe' -UseBasicParsing" >nul 2>&1
        if exist "%TEMP%\python_installer.exe" set PYTHON_INSTALLER=%TEMP%\python_installer.exe
    )
    if defined PYTHON_INSTALLER (
        echo Python installeren - dit duurt een paar minuten...
        start /wait "" "!PYTHON_INSTALLER!" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
        echo OK: Python bijgewerkt. Herstart dit script om de nieuwe versie te gebruiken.
    ) else (
        echo WAARSCHUWING: Python-download mislukt - download handmatig via python.org
    )
) else (
    echo OK: Python-versie voldoet.
)

echo Stap 3: Python controleren (alleen standaardbibliotheek + keyring)...
:: pinas_sync en de hele suite draaien op de standaardbibliotheek (Tkinter).
:: Geen Kivy, smbprotocol of paramiko meer nodig. Alleen keyring voor
:: het wachtwoordbeheer (pinas_wachtwoord).
python -c "import tkinter" >nul 2>&1
if errorlevel 1 (echo WAARSCHUWING: Tkinter ontbreekt - herinstalleer Python via python.org met tcl/tk aangevinkt.) else (echo OK: Tkinter aanwezig.)
pip show keyring >nul 2>&1
if errorlevel 1 (pip install keyring --quiet & echo OK: keyring geinstalleerd.) else (echo OK: keyring aanwezig.)
echo Stap 3 >> "%LOG%"

echo Stap 4: SSH sleutel...
set SSH_DIR=%USERPROFILE%\.ssh
if not exist "%SSH_DIR%" mkdir "%SSH_DIR%"
set SLEUTEL_OK=0
if exist "%SSH_DIR%\id_ed25519" set SLEUTEL_OK=1
if exist "%SSH_DIR%\id_rsa" set SLEUTEL_OK=1
if !SLEUTEL_OK!==0 (
    for %%D in (X Y Z W V) do (
        if exist "%%D:\Users\%USERNAME%\.ssh\id_ed25519" (
            if not defined SLEUTEL_BRON set SLEUTEL_BRON=%%D:\Users\%USERNAME%\.ssh
        )
    )
    if defined SLEUTEL_BRON (
        copy "!SLEUTEL_BRON!\id_ed25519" "%SSH_DIR%\id_ed25519" >nul 2>&1
        echo SSH sleutel gekopieerd van !SLEUTEL_BRON!
    ) else (
        echo INFO: Geen SSH sleutel gevonden - werkt via wachtwoord.
    )
) else (
    echo SSH sleutel OK
)
ssh-keygen -R !PI_IP! >nul 2>&1
echo Stap 4 >> "%LOG%"

if not "%DO_PUTTY%"=="1" (
    echo Stap 5: PuTTY overgeslagen ^(niet aangevinkt^).
    goto :na_putty
)
echo Stap 5: PuTTY...
set PUTTY_EXE=
for %%P in ("%ProgramFiles%\PuTTY\putty.exe" "%ProgramFiles(x86)%\PuTTY\putty.exe") do (
    if exist %%P set PUTTY_EXE=%%P
)
if defined PUTTY_EXE (
    echo PuTTY OK: !PUTTY_EXE!
) else (
    set PUTTY_INSTALLER=
    for %%F in ("%BRON%Installatie\putty*.msi" "%BRON%putty*.msi") do (
        if exist "%%F" set PUTTY_INSTALLER=%%F
    )
    if not defined PUTTY_INSTALLER (
        echo PuTTY niet lokaal gevonden - downloaden...
        powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://the.earth.li/~sgtatham/putty/latest/w64/putty-64bit-installer.msi' -OutFile '%TEMP%\putty.msi' -UseBasicParsing" >nul 2>&1
        if exist "%TEMP%\putty.msi" set PUTTY_INSTALLER=%TEMP%\putty.msi
    ) else (
        echo PuTTY gevonden in Installatie-map: !PUTTY_INSTALLER!
    )
    if defined PUTTY_INSTALLER (
        msiexec /i "!PUTTY_INSTALLER!" /quiet /norestart
        timeout /t 12 /nobreak >nul
        echo OK: PuTTY geinstalleerd.
    ) else (
        echo WAARSCHUWING: PuTTY niet gevonden en download mislukt.
    )
)
echo Stap 5 >> "%LOG%"
:na_putty

if not "%DO_VNC%"=="1" (
    echo Stap 6: TigerVNC overgeslagen ^(niet aangevinkt^).
    goto :na_vnc
)
echo Stap 6: TigerVNC...
set TIGERVNC_EXE=
for %%P in ("%ProgramFiles%\TigerVNC\vncviewer.exe" "%ProgramFiles(x86)%\TigerVNC\vncviewer.exe") do (
    if exist %%P set TIGERVNC_EXE=%%P
)
if defined TIGERVNC_EXE (
    echo TigerVNC OK
) else (
    set VNC_INSTALLER=
    for %%F in ("%BRON%Installatie\tigervnc*.exe" "%BRON%tigervnc*.exe") do (
        if exist "%%F" set VNC_INSTALLER=%%F
    )
    if not defined VNC_INSTALLER (
        echo TigerVNC downloaden...
        powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://github.com/TigerVNC/tigervnc/releases/download/v1.16.2/tigervnc64-1.16.2.exe' -OutFile '%TEMP%\tigervnc.exe' -UseBasicParsing" >nul 2>&1
        if exist "%TEMP%\tigervnc.exe" set VNC_INSTALLER=%TEMP%\tigervnc.exe
    )
    if defined VNC_INSTALLER (
        "!VNC_INSTALLER!" /silent /install
        timeout /t 15 /nobreak >nul
        echo OK: TigerVNC geinstalleerd.
    ) else (
        echo WAARSCHUWING: TigerVNC niet geinstalleerd.
    )
)
echo Stap 6 >> "%LOG%"
:na_vnc

if not "%DO_WINSCP%"=="1" (
    echo Stap 6a: WinSCP overgeslagen ^(niet aangevinkt^).
    goto :na_winscp
)
echo Stap 6a: WinSCP...
set WINSCP_EXE=
for %%P in ("%ProgramFiles%\WinSCP\WinSCP.exe" "%ProgramFiles(x86)%\WinSCP\WinSCP.exe") do (
    if exist %%P set WINSCP_EXE=%%P
)
if defined WINSCP_EXE (
    echo WinSCP OK: !WINSCP_EXE!
) else (
    set WINSCP_INSTALLER=
    rem 3 patronen geprobeerd, want dit script draait in 2 contexten: vanuit
    rem de Starter Kit-root (BRON=root, Installatie is dan een subfolder) EN
    rem vanuit de al-geinstalleerde suite (BRON=Beheer\, Installatie is dan
    rem een buurmap - vandaar ook de ..\Installatie-variant hieronder).
    for %%F in ("%BRON%Installatie\WinSCP*.exe" "%BRON%..\Installatie\WinSCP*.exe" "%BRON%WinSCP*.exe") do (
        if exist "%%F" set WINSCP_INSTALLER=%%F
    )
    if not defined WINSCP_INSTALLER (
        echo WinSCP niet lokaal gevonden - downloaden...
        powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://sourceforge.net/projects/winscp/files/latest/download' -OutFile '%TEMP%\winscp.exe' -UseBasicParsing" >nul 2>&1
        if exist "%TEMP%\winscp.exe" set WINSCP_INSTALLER=%TEMP%\winscp.exe
    ) else (
        echo WinSCP gevonden in Installatie-map: !WINSCP_INSTALLER!
    )
    if defined WINSCP_INSTALLER (
        "!WINSCP_INSTALLER!" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
        timeout /t 12 /nobreak >nul
        echo OK: WinSCP geinstalleerd.
    ) else (
        echo WAARSCHUWING: WinSCP niet gevonden en download mislukt.
    )
)
echo Stap 6a >> "%LOG%"
:na_winscp

rem (11 augustus 2026) Stap 6b/6c (WSL + Docker Desktop) hier weggehaald -
rem was uitsluitend nodig voor de NAS Simulator (Docker-container die een Pi
rem nabootste), die niet meer gebruikt wordt. Zie OVERDRACHT_NIEUWE_CHAT.md
rem voor de achtergrond.

if not "%DO_SCHIJVEN%"=="1" (
    echo Stap 7: Netwerkschijven overgeslagen ^(niet aangevinkt^).
    goto :na_schijven
)
echo Stap 7: Netwerkschijven...
for /f "delims=" %%W in ('powershell -NoProfile -Command "$s=Read-Host ''NAS wachtwoord'' -AsSecureString; [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))"') do set NASWW=%%W
cmdkey /add:!PI_IP! /user:pi /pass:!NASWW! >nul
python -c "import sys; sys.path.insert(0,'C:\PiNAS\Gedeeld'); from pinas_wachtwoord import set_wachtwoord; set_wachtwoord('!NASWW!','samba')" >nul 2>&1

set OPSLAG_LETTER=
for %%L in (Y W X V U T) do (
    if not defined OPSLAG_LETTER (
        net use %%L: /delete /yes >nul 2>&1
        net use %%L: \\!PI_IP!\Opslag /user:pi !NASWW! /persistent:yes >nul 2>&1
        if not errorlevel 1 set OPSLAG_LETTER=%%L
    )
)
if defined OPSLAG_LETTER (echo Opslag OK op !OPSLAG_LETTER!:) else (echo Opslag MISLUKT - geen vrije letter gevonden)

set BACKUP_LETTER=
for %%L in (Z X W V U T) do (
    if not defined BACKUP_LETTER (
        if /i not "%%L"=="!OPSLAG_LETTER!" (
            net use %%L: /delete /yes >nul 2>&1
            net use %%L: \\!PI_IP!\Backup /user:pi !NASWW! /persistent:yes >nul 2>&1
            if not errorlevel 1 set BACKUP_LETTER=%%L
        )
    )
)
if defined BACKUP_LETTER (echo Backup OK op !BACKUP_LETTER!:) else (echo Backup MISLUKT - Externe HDD mogelijk uit, of geen vrije letter)

rem De gevonden letters vastleggen in picontrol.cfg, zodat de rest van de
rem suite (pinas_schijven.py) ze meteen kan vinden i.p.v. zelf te zoeken.
rem Herschrijft het hele bestand in een keer (i.p.v. toevoegen) zodat een
rem herinstallatie niet telkens een nieuwe [schijven]-sectie erbij plakt.
(
echo [pi]
echo ip = !PI_IP!
echo.
echo [paden]
echo install_dir = C:\PiNAS\Beheer
echo install_type = !INST_TYPE!
echo.
echo [schijven]
if defined OPSLAG_LETTER echo !OPSLAG_LETTER! = Opslag
if defined BACKUP_LETTER echo !BACKUP_LETTER! = Backup
if defined BESTAAND_THEMA (
echo.
echo [ui]
echo thema = !BESTAAND_THEMA!
)
) > "C:\PiNAS\Beheer\picontrol.cfg"
echo Stap 7 >> "%LOG%"
:na_schijven

echo Stap 8: Snelkoppeling...
powershell -NoProfile -Command "$ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Pi NAS Menu.lnk'); $s.TargetPath='pythonw.exe'; $s.Arguments='\"C:\PiNAS\Beheer\Pi_NAS_Menu.pyw\"'; $s.WorkingDirectory='C:\PiNAS\Beheer'; $s.IconLocation='C:\PiNAS\Beheer\Pi_NAS_Menu.ico'; $s.Save()" >nul 2>&1
if errorlevel 1 (echo Snelkoppeling MISLUKT) else (echo Snelkoppeling OK)
echo Stap 8 >> "%LOG%"

echo Stap 9: Klaar - gebruik de snelkoppeling op het bureaublad.
echo Stap 9 >> "%LOG%"

echo.
echo ====================================================
echo Installatie voltooid!
echo Log: %LOG%
echo ====================================================
echo.
set /p "HERSTART=  Windows herstarten? [j/N]: "
if /i "!HERSTART!"=="j" shutdown /r /t 5 /c "Pi NAS Suite installatie voltooid"
echo.
pause
