@echo off
:: ============================================================
:: Maakt schone publieke versie voor GitHub
:: Staat in: C:\PiNAS\Gedeeld\
:: Output:   C:\PiNAS\Publicatie\NAS_Public\
:: Werkt automatisch vanuit elke locatie
:: ============================================================
setlocal enabledelayedexpansion

:: Detecteer C:\PiNAS\ als ouder van Gedeeld\
set GEDEELD=%~dp0
set GEDEELD=%GEDEELD:~0,-1%
for %%I in ("%GEDEELD%\..") do set NAS_ROOT=%%~fI

set PUBLIC_MAP=%NAS_ROOT%\Publicatie\NAS_Public

echo.
echo  Pi NAS Suite - Maak publieke versie voor GitHub
echo  ============================================================
echo  NAS root:  %NAS_ROOT%
echo  Output:    %PUBLIC_MAP%
echo  ============================================================
echo.

:: -- Eerst opschonen: NAS_Public volledig opnieuw opbouwen, zodat
:: verouderde bestanden (zoals de oude Sync main.py / Kivy-core) NIET
:: in de GitHub-release achterblijven. copy /Y overschrijft wel, maar
:: verwijdert niets - daarom hier een schone start.
if exist "%PUBLIC_MAP%" rmdir /S /Q "%PUBLIC_MAP%"
if not exist "%PUBLIC_MAP%" mkdir "%PUBLIC_MAP%"
if not exist "%PUBLIC_MAP%\PiServer" mkdir "%PUBLIC_MAP%\PiServer"
if not exist "%PUBLIC_MAP%\Sync" mkdir "%PUBLIC_MAP%\Sync"
if not exist "%PUBLIC_MAP%\Sync\core" mkdir "%PUBLIC_MAP%\Sync\core"
if not exist "%PUBLIC_MAP%\Beheer" mkdir "%PUBLIC_MAP%\Beheer"
if not exist "%PUBLIC_MAP%\Gedeeld" mkdir "%PUBLIC_MAP%\Gedeeld"
if not exist "%PUBLIC_MAP%\ArchiefBackup" mkdir "%PUBLIC_MAP%\ArchiefBackup"
if not exist "%PUBLIC_MAP%\Publicatie" mkdir "%PUBLIC_MAP%\Publicatie"
if not exist "%PUBLIC_MAP%\Addons" mkdir "%PUBLIC_MAP%\Addons"

:: -- PiServer bestanden ------------------------------------------
echo  [PiServer]
set MAP=%NAS_ROOT%\PiServer
if not exist "%PUBLIC_MAP%\PiServer" mkdir "%PUBLIC_MAP%\PiServer"
for %%F in (
    nas_installer.py
    nas_installer_cli.py
    seagate_web.py
    seagate-web.service
    smart_plug.py
    smart_plug_config.json
    hue_diagnose.py
    pi_welkom.sh
    install.sh
    nas_start.sh
    maak_simulator_map.bat
    README.md
    Dockerfile
    sim_setup.sh
    SIMULATOR_LEESMIJ.md
    start.sh
) do (
    if exist "%MAP%\%%F" (
        copy /Y "%MAP%\%%F" "%PUBLIC_MAP%\PiServer\%%F" >nul
        echo    OK: PiServer\%%F
    ) else (
        echo    --: PiServer\%%F ^(niet gevonden^)
    )
)

:: -- Sync bestanden ---------------------------------------
echo.
echo  [Sync]
set MAP=%NAS_ROOT%\Sync
if not exist "%PUBLIC_MAP%\Sync" mkdir "%PUBLIC_MAP%\Sync"
if not exist "%PUBLIC_MAP%\Sync\core" mkdir "%PUBLIC_MAP%\Sync\core"
for %%F in (
    pinas_sync_app.pyw
    start.bat
    requirements.txt
    install_windows.bat
) do (
    if exist "%MAP%\%%F" (
        copy /Y "%MAP%\%%F" "%PUBLIC_MAP%\Sync\%%F" >nul
        echo    OK: Sync\%%F
    ) else (
        echo    --: Sync\%%F ^(niet gevonden^)
    )
)
for %%F in (sync_engine.py bron_doel_picker.py thema.py __init__.py) do (
    if exist "%MAP%\core\%%F" (
        copy /Y "%MAP%\core\%%F" "%PUBLIC_MAP%\Sync\core\%%F" >nul
        echo    OK: Sync\core\%%F
    ) else (
        echo    --: Sync\core\%%F ^(niet gevonden^)
    )
)

:: -- ArchiefBackup bestanden (hoofdmap, hoort bij Backup Beheer) --------------
echo.
echo  [ArchiefBackup]
set MAP=%NAS_ROOT%\ArchiefBackup
if not exist "%PUBLIC_MAP%\ArchiefBackup" mkdir "%PUBLIC_MAP%\ArchiefBackup"
for %%F in (
    archief_backup_bewaking.pyw
    start.bat
) do (
    if exist "%MAP%\%%F" (
        copy /Y "%MAP%\%%F" "%PUBLIC_MAP%\ArchiefBackup\%%F" >nul
        echo    OK: ArchiefBackup\%%F
    ) else (
        echo    --: ArchiefBackup\%%F ^(niet gevonden^)
    )
)

:: -- Addons bestanden (17 juli 2026 toegevoegd - stonden er nooit in) -----
echo.
echo  [Addons]
set MAP=%NAS_ROOT%\Addons
if not exist "%PUBLIC_MAP%\Addons" mkdir "%PUBLIC_MAP%\Addons"
for %%F in (
    pinas_addons_beheer.pyw
    pinas_nextcloud.sh
    pinas_nextcloud_verwijderen.sh
    pinas_pihole.sh
    pinas_pihole_verwijderen.sh
    pinas_zerotier.sh
    pinas_zerotier_verwijderen.sh
    pinas_vaultwarden.sh
    pinas_vaultwarden_verwijderen.sh
    pinas_vaultwarden_cert_vertrouwen.pyw
    pinas_vaultwarden_cert_import.ps1
    pinas_status_pagina.sh
    pinas_status_pagina_verwijderen.sh
    pinas_status_pagina_wachtwoord_resetten.sh
    pinas_printer.sh
    pinas_printer_verwijderen.sh
    pinas_dashboard.sh
    pinas_dashboard_verwijderen.sh
) do (
    if exist "%MAP%\%%F" (
        copy /Y "%MAP%\%%F" "%PUBLIC_MAP%\Addons\%%F" >nul
        echo    OK: Addons\%%F
    ) else (
        echo    --: Addons\%%F ^(niet gevonden^)
    )
)

:: -- Beheer bestanden --------------------------------------
echo.
echo  [Beheer]
set MAP=%NAS_ROOT%\Beheer
for %%F in (
    Pi_NAS_Menu.pyw
    pi_nas_setup.pyw
    Pi_NAS_Menu.ico
    Beheer_install.bat
    lanman_fix.bat
    install_vnc_viewer.bat
    pinas_backup_beheer.pyw
    pinas_image_backup.pyw
) do (
    if exist "%MAP%\%%F" (
        copy /Y "%MAP%\%%F" "%PUBLIC_MAP%\Beheer\%%F" >nul
        echo    OK: Beheer\%%F
    ) else (
        echo    --: Beheer\%%F ^(niet gevonden^)
    )
)

:: PC Image Backup's gedeelde module staat in de submap core/
if exist "%MAP%\core" (
    mkdir "%PUBLIC_MAP%\Beheer\core" 2>nul
    copy /Y "%MAP%\core\*" "%PUBLIC_MAP%\Beheer\core\" >nul
    echo    OK: Beheer\core\
) else (
    echo    --: Beheer\core ^(niet gevonden^)
)

:: Screenshots staan in de submap assets/
if exist "%MAP%\assets" (
    mkdir "%PUBLIC_MAP%\Beheer\assets" 2>nul
    copy /Y "%MAP%\assets\pinas_sync_scherm*.png" "%PUBLIC_MAP%\Beheer\assets\" >nul
    echo    OK: Beheer\assets\ screenshots
) else (
    echo    --: Beheer\assets ^(niet gevonden^)
)

:: -- Publicatie bestanden (Handleiding, verhuisd hierheen) ----------------
echo.
echo  [Publicatie]
set MAP=%NAS_ROOT%\Publicatie
if not exist "%PUBLIC_MAP%\Publicatie" mkdir "%PUBLIC_MAP%\Publicatie"
:: 9 augustus 2026 (Frans: "presentatie is te groot om te tonen via
:: GitHub" - de .pptx zelf heeft geen inline preview op GitHub) -
:: PiNAS_Suite_Presentatie_Preview.pdf is een PDF-export van dezelfde
:: slides, puur zodat GitHub's ingebouwde PDF-viewer 'm direct in de
:: browser kan tonen. De .pptx zelf blijft ongewijzigd (voor wie het
:: wil bewerken/downloaden). LET OP: deze PDF wordt NIET automatisch
:: hier gegenereerd (vereist LibreOffice/soffice, niet onderdeel van
:: de suite's Windows-toolchain) - bij een nieuwe versie van de
:: presentatie moet deze PDF-preview apart opnieuw gemaakt worden.
for %%F in (
    PiNAS_Suite_Handleiding.pdf
    build_suite_handleiding.py
    PiNAS_Suite_Presentatie.pptx
    PiNAS_Suite_Presentatie_Preview.pdf
    PiNAS_Suite_Architectuur.png
) do (
    if exist "%MAP%\%%F" (
        copy /Y "%MAP%\%%F" "%PUBLIC_MAP%\Publicatie\%%F" >nul
        echo    OK: Publicatie\%%F
    ) else (
        echo    --: Publicatie\%%F ^(niet gevonden^)
    )
)

:: -- Gedeeld bestanden ----------------------------------------
echo.
echo  [Gedeeld]
set MAP=%NAS_ROOT%\Gedeeld
if not exist "%PUBLIC_MAP%\Gedeeld" mkdir "%PUBLIC_MAP%\Gedeeld"
for %%F in (
    pinas_theme.py
    pinas_theme_donker.py
    pinas_theme_licht.py
    pinas_ui.py
    pinas_wachtwoord.py
    pinas_logging.py
    pinas_launcher.py
    pinas_pi_status.py
    controleer_documentatie_consistentie.py
    pinas_schijven.py
    pinas_versies.json
    version.py
    nas_upload.bat
    nas_diagnose.bat
    nas_diagnose.sh
    herstel_backup_hdd.sh
    pinas_iphone_backup.sh
    pinas_iphone_verkennen.sh
    test_suite.py
    maak_publieke_versie.bat
    maak_starterkit.bat
) do (
    if exist "%MAP%\%%F" (
        copy /Y "%MAP%\%%F" "%PUBLIC_MAP%\Gedeeld\%%F" >nul
        echo    OK: Gedeeld\%%F
    ) else (
        echo    --: Gedeeld\%%F ^(niet gevonden^)
    )
)
:: Gedeeld\ScriptRunner\pi_script_draaien.bat ingetrokken (31 juli 2026,
:: Frans: niet meer los gebruikt - Addons Beheer dekt dit nu)

:: -- Installatie -------------------------------------------------
:: 9 augustus 2026 (Frans: "gratis houden, installatie map weg laten
:: en een readme toevoegen dat je deze zelf in installatie map moet
:: plaatsen") - de installers zelf (vooral Docker Desktop Installer.exe,
:: 631MB) horen niet in de publieke GitHub-repo: dat bestand alleen al
:: is te groot voor gewone GitHub-upload (limiet 25MB via de web-
:: interface, 100MB hard via git) en Git LFS is niet gratis genoeg om
:: dit blijvend te dragen (bandbreedte-kosten bij elke download). De
:: map blijft WEL leeg aanwezig met een LEESMIJ + de bestaande
:: download_links.ini (single source of truth, al gebruikt door
:: "Download links beheren" in Onderhoud), zodat de gebruiker exact
:: weet wat te downloaden en waar neer te zetten. In de Starter Kit
:: (maak_starterkit.bat) blijven de installers wel gewoon meegaan -
:: dat pakket is niet voor GitHub bedoeld en heeft geen groottelimiet.
echo  [Installatie]
mkdir "%PUBLIC_MAP%\Installatie" 2>nul
(
echo # Installatie-map
echo.
echo Deze map is in de GitHub-versie bewust LEEG. De installers zelf zijn te
echo groot voor een publieke GitHub-repository ^(Docker Desktop Installer.exe
echo alleen al is 631MB^). Download onderstaande bestanden zelf en zet ze in
echo deze map, VOORDAT je Beheer_install.bat draait.
echo.
echo De actuele downloadlinks staan ook in Gedeeld\download_links.ini.
echo.
echo ^| Bestand ^| Waarvoor ^| Download ^|
echo ^|---^|---^|---^|
echo ^| Docker Desktop Installer.exe ^| NAS-simulator ^| https://desktop.docker.com/win/main/amd64/Docker%%20Desktop%%20Installer.exe ^|
echo ^| putty-64bit-installer.msi ^| SSH-verbinding met de Pi ^| https://the.earth.li/~sgtatham/putty/latest/w64/putty-64bit-installer.msi ^|
echo ^| tigervnc64-installer.exe ^| Grafisch bureaublad van de Pi ^| https://github.com/TigerVNC/tigervnc/releases/latest ^|
echo ^| python-installer.exe ^| Draagt de hele Windows-kant van de suite ^| https://www.python.org/downloads/windows/ ^|
echo ^| imager_latest.exe ^| SD-kaart voorbereiden ^(Stap 2 van de wizard^) ^| https://www.raspberrypi.com/software/ ^|
echo.
echo Bestandsnaam maakt niet uit zolang die begint met de juiste naam
echo ^(python-3*.exe, putty*.msi, tigervnc*.exe, Docker*.exe^) - dat is wat
echo Beheer_install.bat zoekt.
) > "%PUBLIC_MAP%\Installatie\LEESMIJ.md"
if exist "%NAS_ROOT%\Gedeeld\download_links.ini" (
    copy /Y "%NAS_ROOT%\Gedeeld\download_links.ini" "%PUBLIC_MAP%\Installatie\download_links.ini" >nul
)
echo    OK: Installatie\LEESMIJ.md ^(installers zelf NIET meegenomen - te groot voor GitHub^)

:: -- README.md in de root ---------------------------------------
:: 9 augustus 2026 (Frans: "ik kan een readme toevoegen, kan dat ook
:: de presentatie zijn?") - een .pptx kan GitHub's README niet
:: vervangen (moet markdown/tekst zijn), dus README.md verwijst ernaar
:: en de presentatie zelf gaat gewoon mee de repo in (Publicatie\).
echo.
echo  [README]
(
echo # Pi NAS Suite
echo.
echo Een complete thuisserver-oplossing op basis van een Raspberry Pi 5 - bestanden opslaan,
echo automatisch backuppen, en volledig beheren vanuit Windows, zonder technische kennis.
echo.
echo ^^!^[Architectuur^]^(Publicatie/PiNAS_Suite_Architectuur.png^)
echo.
echo **[Bekijk de presentatie]^(Publicatie/PiNAS_Suite_Presentatie_Preview.pdf^)** - een uitgebreide
echo walkthrough met screenshots van installatie tot dagelijks gebruik ^(PDF, direct
echo leesbaar in de browser^). Origineel ^(bewerkbaar^): [PiNAS_Suite_Presentatie.pptx]^(Publicatie/PiNAS_Suite_Presentatie.pptx^).
echo.
echo **[Volledige handleiding]^(Publicatie/PiNAS_Suite_Handleiding.pdf^)** - alle vensters,
echo knoppen en instellingen in detail.
echo.
echo ## Wat is dit?
echo.
echo De suite bestaat uit drie delen die samenwerken:
echo.
echo ^| Onderdeel ^| Wat doet het? ^| Op welk apparaat? ^|
echo ^|---^|---^|---^|
echo ^| Pi NAS Menu ^| Verbinden, uploaden, diagnose, beheer ^| Windows PC ^|
echo ^| PiNAS Sync ^| Synchroniseren en PC Images backuppen ^| Windows PC ^|
echo ^| Pi NAS Server ^| Bestanden opslaan, Nextcloud, FileBrowser, Cockpit ^| Raspberry Pi 5 ^|
echo.
echo Onderdelen: Samba ^(netwerkschijven^), Nextcloud ^(eigen cloud^), FileBrowser ^(webbeheer^),
echo Cockpit ^(Pi-beheer via browser^), en optionele add-ons ^(Pi-hole, ZeroTier, Vaultwarden,
echo printserver, statuspagina, dashboard^).
echo.
echo ## Snel starten - van 0 naar werkend
echo.
echo 1. **Bron kiezen**: pak deze repository uit ^(of download als ZIP^)
echo 2. **Beheer_install.bat draaien** ^(staat los in de root^) - zet de hele suite neer op
echo    `C:\PiNAS`, installeert de Windows-onderdelen en maakt een bureaubladsnelkoppeling.
echo    Dit bestand opent zelf niets - open daarna zelf de nieuwe snelkoppeling.
echo 3. **Pi NAS Menu -^> Installatie ^& Herstel** - de wizard ^(4 stappen: Gegevens, SD-kaart,
echo    Pi instellen, Windows klaarzetten^) doet de rest automatisch.
echo.
echo Zie de `Installatie/`-map: die bevat een LEESMIJ met downloadlinks voor de installers
echo die je zelf even moet ophalen ^(Docker, PuTTY, TigerVNC, Python, Raspberry Pi Imager -
echo te groot om in deze repository mee te nemen^).
echo.
echo Volledige uitleg, inclusief een beslisboom voor "wat als ik al iets heb staan":
echo zie de [handleiding]^(Publicatie/PiNAS_Suite_Handleiding.pdf^), hoofdstuk 2.
echo.
echo ## Mapstructuur
echo.
echo ^| Map ^| Inhoud ^|
echo ^|---^|---^|
echo ^| `Beheer/` ^| Pi NAS Menu, installer, Backup Beheer ^|
echo ^| `Sync/` ^| PiNAS Sync ^(synchronisatieprogramma^) ^|
echo ^| `ArchiefBackup/` ^| Archief Backup Bewaking ^|
echo ^| `Addons/` ^| Nextcloud, Pi-hole, ZeroTier, Vaultwarden en meer ^|
echo ^| `PiServer/` ^| Server-scripts die op de Pi zelf draaien ^|
echo ^| `Gedeeld/` ^| Gedeelde hulpmodules ^|
echo ^| `Publicatie/` ^| Handleiding en presentatie ^|
echo ^| `Installatie/` ^| LEESMIJ + downloadlinks voor installers ^|
echo.
echo ## Bekende beperkingen ^& roadmap
echo.
echo Dit is een solo-onderhouden project - vooral gericht op functionaliteit en
echo documentatie. Een paar dingen om te weten voordat je begint:
echo.
echo - De Windows-installatiekant draait nu op .bat-scripts; migratie naar Python
echo   staat op de planning voor meer robuustheid.
echo - Nog geen geautomatiseerde CI-pipeline - tests draaien lokaal via
echo   `test_suite.py`, niet automatisch bij elke commit.
echo - "Op mijn iPhone" ^(de Bestanden-app^) is niet doorbladerbaar via de
echo   iPhone-functies - een vaste iOS/libimobiledevice-beperking, geen bug
echo   ^(zie hoofdstuk over iPhone Back-up in de handleiding^).
echo - Issues en bijdragen zijn welkom, maar dit is een nevenproject - reactietijd
echo   kan wisselen.
echo.
echo ## Licentie
echo.
echo MIT License - vrij te gebruiken, aanpassen en verspreiden. Vermeld de oorsprong als je
echo het deelt.
) > "%PUBLIC_MAP%\README.md"
echo    OK: README.md

:: -- Beheer_install.bat in root ---------------------------
if exist "%NAS_ROOT%\Beheer\Beheer_install.bat" (
    copy /Y "%NAS_ROOT%\Beheer\Beheer_install.bat" "%PUBLIC_MAP%\Beheer_install.bat" >nul
    echo    OK: Beheer_install.bat ^(root^)
)
echo minimaal> "%PUBLIC_MAP%\INSTALL_TYPE.txt"

:: -- Wachtwoord ophalen uit cache -----------------------------
echo.
echo  [Wachtwoord ophalen voor anonimisering]
set WW_CACHE=%NAS_ROOT%\Logs\.ww_samba.dat
set HUIDIG_WW=
if exist "%WW_CACHE%" (
    set /p HUIDIG_WW=< "%WW_CACHE%"
    echo    Wachtwoord gevonden voor anonimisering
) else (
    echo    Geen wachtwoordcache gevonden ^(alleen IP wordt geanonimiseerd^)
)

:: -- Anonimiseren ---------------------------------------------
echo.
echo  [Anonimiseren]
:: 10 augustus 2026 (bug gevonden na een live-run: PowerShell-blok brak af
:: met "Missing closing '}'"): het regex-patroon 'fvdsc(?!hrier)[a-z]*'
:: hieronder bevat een kale '!' (negative lookahead). Met
:: enabledelayedexpansion AAN (zie setlocal bovenaan dit bestand) scant
:: cmd de hele samengevoegde powershell-opdracht op '!...!'-paren, vindt
:: geen sluitende '!' en gooit alles ertussen weg - vandaar het afgekapte
:: commando in de foutmelding. Delayed expansion is verder nergens in dit
:: script nodig (geen enkel !VAR!-gebruik), dus hier lokaal uitzetten is
:: veilig en lost het op zonder de regex zelf aan te passen.
::
:: 10 augustus 2026 (2e bug, zelfde live-run): dit bestand kopieert en
:: anonimiseert ZICHZELF ook mee (het staat in de Gedeeld\-lijst hierboven).
:: De patronen hieronder (zoals 'fvdsc(?!hrier)[a-z]*' en 'Test1234') zijn
:: geen echte gebruikersgegevens maar de redactie-patronen zelf - die mogen
:: dus niet door zichzelf vervangen worden, anders werkt de gekopieerde
:: versie in NAS_Public niet meer bij een volgende run. Vandaar de
:: uitzondering hieronder die maak_publieke_versie.bat overslaat.
setlocal disabledelayedexpansion
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$pub = '%PUBLIC_MAP%';" ^
    "$ww = '%HUIDIG_WW%';" ^
    "Get-ChildItem $pub -Include *.bat,*.py,*.pyw,*.sh,*.json,*.md,*.ini,*.cfg -Recurse | ForEach-Object {" ^
    "    if ($_.Name -eq 'maak_publieke_versie.bat') { return };" ^
    "    $c = Get-Content $_.FullName -Raw -Encoding UTF8;" ^
    "    if ($c -eq $null) { return };" ^
    "    $c = $c -replace '192\.168\.\d+\.\d+', 'UW_PI_IP_ADRES';" ^
    "    if ($ww -ne '') { $c = $c -replace [regex]::Escape($ww), 'UW_WACHTWOORD' };" ^
    "    $c = $c -replace 'Test1234', 'UW_WACHTWOORD';" ^
    "    $c = $c -replace 'fvdsc(?!hrier)[a-z]*', 'GEBRUIKER';" ^
    "    $c = $c -replace 'f838cf2d-6221-4452-b9df-a0ab36913586', 'UW_BACKUP_HDD_UUID';" ^
    "    $c = $c -replace 'f838cf2d', 'UW_BACKUP_HDD_UUID';" ^
    "    $c = $c -replace '166359304e3cacb3', 'UW_ZEROTIER_NETWERK_ID';" ^
    "    Set-Content $_.FullName $c -NoNewline -Encoding UTF8;" ^
    "    Write-Host ('   SCHOON: ' + $_.Name)" ^
    "}"
endlocal

echo.
echo  ============================================================
echo  Klaar! Publieke versie staat in:
echo  %PUBLIC_MAP%
echo.
echo  Structuur: PiServer\, Sync\, ArchiefBackup\, Beheer\, Addons\, Publicatie\, Gedeeld\, Installatie\
echo  Geanonimiseerd: IP, wachtwoord, gebruikersnaam, backup-HDD UUID en ZeroTier netwerk-ID
echo  Controleer de inhoud voor upload naar GitHub.
echo  ============================================================
echo.
pause
