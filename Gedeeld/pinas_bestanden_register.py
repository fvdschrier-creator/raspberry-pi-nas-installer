#!/usr/bin/env python3
"""
Gedeeld/pinas_bestanden_register.py

DE centrale lijst van elk bestand dat bij de Pi NAS Suite hoort. De ENE
bron van waarheid voor drie dingen die voorheen elk hun eigen, losse
kopie van (een deel van) deze lijst bijhielden:

  1. Beheer\\NAS_Map_Beheer.pyw (Structuurcheck) - "welke bestanden hoort
     de suite te hebben, en wat is de korte uitleg erbij".
  2. Gedeeld\\maak_publieke_versie.py - "welke bestanden horen mee naar
     de publieke GitHub-versie".
  3. Gedeeld\\maak_starterkit.py - "welke bestanden horen mee in de
     Starter Kit ZIP".

14 augustus 2026: aangemaakt na een reeks losse bugs deze sessie die
allemaal dezelfde oorzaak hadden - een bestand stond wel in de ene lijst
maar niet in een andere, en dat viel pas op toen Frans het toevallig
tegenkwam:
  - WinSCP-installer ontbrak in Topografie (build_topografie.py, niet dit
    register - zie de docstring daar voor waarom Topografie een aparte,
    genuanceerdere structuur blijft).
  - pinas_controle_beheer.pyw / NAS_Map_Beheer.pyw / pinas_kleuren_kiezer.pyw
    ontbraken volledig in de publieke GitHub-versie EN de Starter Kit,
    terwijl Pi_NAS_Menu.pyw's "Controles"-knop er wel naartoe verwees.
  - Gedeeld\\pinas_versies_hashes.json ontbrak in Structuurcheck's lijst
    en werd daardoor steeds als "onbekend bestand" gemeld.
  - Bij het opstellen van dit register kwam een 4e, tot dan toe ONONTDEKTE
    bug aan het licht: Gedeeld\\pinas_addon_scripts.py (een harde,
    top-level import in zowel Pi_NAS_Menu.pyw als
    Addons\\pinas_addons_beheer.pyw) stond wel in de publieke GitHub-versie
    maar NIET in de Starter Kit - een verse Starter Kit-installatie zou
    dus meteen gecrasht zijn bij het opstarten van het hoofdmenu zelf.
    Nu vanzelf gefixt doordat beide bouwscripts uit hetzelfde register
    lezen i.p.v. 2 losse, uit elkaar gegroeide lijsten te onderhouden.

BESTANDEN is een platte lijst van (map, bestand, beschrijving, github,
starterkit)-tuples:
  map          - submap (PiServer/Sync/Beheer/Gedeeld/Publicatie/
                 Installatie/Addons/ArchiefBackup)
  bestand      - bestandsnaam, relatief aan 'map'. Submap-bestanden
                 gebruiken '/' als scheidingsteken (bijv. "core/thema.py")
                 - voor_structuurcheck() zet dit om naar os.path.join(),
                 zodat dit register platform-onafhankelijk blijft.
  beschrijving - mensleesbare uitleg, gebruikt door Structuurcheck.
  github       - True als dit bestand hoort in de publieke GitHub-versie
                 (maak_publieke_versie.py).
  starterkit   - True als dit bestand hoort in de Starter Kit ZIP
                 (maak_starterkit.py). Meestal gelijk aan 'github', met
                 een paar bewuste uitzonderingen (zie de losse
                 aantekeningen hieronder bij die regels): build-/
                 publicatietooling die een verse installatie niet nodig
                 heeft (bijv. maak_publieke_versie.py zelf, de
                 marketingpresentatie) staat wel op GitHub maar niet in
                 de Starter Kit.

BEWUST NIET in dit register:
  - Bestanden met een wisselende naam (bijv. "python-3*.exe" - het
    versienummer verandert bij elke download). Die blijven met een
    joker-patroon herkend, apart geregeld in NAS_Map_Beheer.pyw zelf
    (installatie_patronen), want dat is geen statische bestandsnaam.
  - Gedeeld\\pinas_versies.json zelf hoeft geen aparte "hoort dit bestand
    er wel/niet" registratie te hebben t.o.v. dit bestand - dat is een
    apart mechanisme (datums, niet een statische ja/nee-lijst) en wordt
    zelf ook gewoon als 1 regel HIERONDER meegenomen.
  - build_topografie.py's MENU_RIJEN/FUNCTIE_RIJEN-structuur (welk
    bestand bij welk MENU-ITEM hoort) - dat is genuanceerder dan een
    platte publiek/privé-vlag en blijft in dat bestand zelf staan, zie
    de docstring daar. Topografie's reconciliatiecheck vergelijkt nog
    steeds tegen pinas_versies.json, niet tegen dit register.
"""

# (map, bestand, beschrijving, github, starterkit)
BESTANDEN = [
    # -- PiServer (Pi-kant installatiescripts) -------------------------------
    ("PiServer", "nas_installer.py", "NAS Installer", True, True),
    ("PiServer", "nas_installer_cli.py", "CLI", True, True),
    ("PiServer", "seagate_web.py", "Seagate service", True, True),
    ("PiServer", "seagate-web.service", "Seagate systemd", True, True),
    ("PiServer", "smart_plug.py", "Smart plug", True, True),
    ("PiServer", "smart_plug_config.json", "Smart plug configuratie", True, True),
    ("PiServer", "hue_diagnose.py", "Hue Bridge diagnose", True, True),
    ("PiServer", "pi_welkom.sh", "Pi welkom script", True, True),
    ("PiServer", "install.sh", "Pi installatie script", True, True),
    ("PiServer", "nas_start.sh", "Desktop-snelkoppelingen wrapper (pkexec) op de Pi", True, True),
    ("PiServer", "README.md", "PiServer leesmij", True, True),

    # -- Sync (PiNAS Sync) ----------------------------------------------------
    ("Sync", "pinas_sync_app.pyw", "Sync & Backup hoofdprogramma", True, True),
    ("Sync", "start.bat", "Sync & Backup start", True, True),
    ("Sync", "core/sync_engine.py", "sync-engine", True, True),
    ("Sync", "core/bron_doel_picker.py", "bron/doel-kiezer", True, True),
    ("Sync", "core/thema.py", "kleuren/thema", True, True),
    ("Sync", "core/__init__.py", "core package", True, True),
    ("Sync", "requirements.txt", "afhankelijkheden (geen externe)", True, True),
    ("Sync", "install_windows.bat", "Windows installatie", True, True),

    # -- Beheer -----------------------------------------------------------------
    ("Beheer", "Pi_NAS_Menu.pyw", "Menu", True, True),
    ("Beheer", "pi_nas_setup.pyw", "Herstel/installatie wizard", True, True),
    ("Beheer", "Pi_NAS_Menu.ico", "Icoon", True, True),
    ("Beheer", "Beheer_install.bat", "Installer", True, True),
    ("Beheer", "lanman_fix.py", "LanManFix", True, True),
    ("Beheer", "install_vnc_viewer.py", "TigerVNC installer", True, True),
    # Draait BEWUST alleen op Frans' eigen pc (nooit publiceren) - zie de
    # eigen docstring in Beheer\pinas_opruimen.pyw.
    ("Beheer", "pinas_opruimen.pyw",
     "Ruimt FUSE-opruimlijst + __pycache__ op (buiten de sandbox te draaien)", False, False),
    ("Beheer", "python_bijwerken.bat", "Python bijwerken naar laatste versie", False, False),
    ("Beheer", "pinas_backup_beheer.pyw", "Backup Beheer - centrale backup-acties", True, True),
    ("Beheer", "pinas_image_backup.pyw", "PC Image Backup (los van Sync)", True, True),
    # Bevat Frans' eigen Pi-IP/thema - persoonlijke configuratie, nooit
    # publiceren (elke installatie krijgt zijn eigen exemplaar via de
    # installatiewizard).
    ("Beheer", "picontrol.cfg", "Configuratie (Pi-IP, thema)", False, False),
    ("Beheer", "core/image_backup.py", "PC Image Backup logica", True, True),
    ("Beheer", "core/__init__.py", "core package (Beheer)", True, True),
    # Logo's blijven bewust intern (alleen de 3 handleiding-screenshots
    # hieronder gaan mee) - geen productbranding-bestanden op GitHub nodig.
    ("Beheer", "assets/pinas_logo.png", "Logo (PNG, algemeen gebruik)", False, False),
    ("Beheer", "assets/pinas_logo.svg", "Logo (SVG, bron/vector)", False, False),
    ("Beheer", "assets/pinas_logo_header.png", "Logo voor vensterkoppen", False, False),
    ("Beheer", "assets/pinas_logo_hoofdmenu.png", "Logo voor het hoofdmenu-scherm", False, False),
    ("Beheer", "assets/pinas_logo_icoon.png", "Logo als icoon-formaat", False, False),
    ("Beheer", "assets/pinas_sync_scherm1.png", "Screenshot handleiding 1", True, True),
    ("Beheer", "assets/pinas_sync_scherm2.png", "Screenshot handleiding 2", True, True),
    ("Beheer", "assets/pinas_sync_scherm3.png", "Screenshot handleiding 3", True, True),
    ("Beheer", "NAS_Map_Beheer.pyw", "Structuurcheck & Opruimen (bereikbaar via Controles)", True, True),
    ("Beheer", "NAS_Map_Beheer.bat", "Map beheer launcher", True, True),
    ("Beheer", "pinas_controle_beheer.pyw", "Controles - Suite testen, Diagnose, Logs", True, True),
    ("Beheer", "pinas_kleuren_kiezer.pyw", "Kleuren kiezen - thema aanpassen via kleurstalen", True, True),
    ("Beheer", "pinas_pi_opruimen.pyw",
     "Pi opruimen - onbekende bestanden in /home/pi opsporen en verwijderen", True, True),

    # -- Gedeeld ------------------------------------------------------------------
    ("Gedeeld", "nas_upload.py", "Upload naar Pi", True, True),
    ("Gedeeld", "nas_diagnose.py", "Diagnose", True, True),
    ("Gedeeld", "nas_diagnose.sh", "Diagnose Pi-kant", True, True),
    ("Gedeeld", "pinas_theme.py", "Centraal thema", True, True),
    ("Gedeeld", "pinas_theme_donker.py", "Thema override - donker", True, True),
    ("Gedeeld", "pinas_theme_licht.py", "Thema override - licht", True, True),
    ("Gedeeld", "pinas_ui.py", "Gedeelde UI-bouwstenen", True, True),
    ("Gedeeld", "pinas_wachtwoord.py", "Wachtwoordbeheer", True, True),
    ("Gedeeld", "pinas_logging.py", "Centrale logging", True, True),
    ("Gedeeld", "pinas_launcher.py", "Gedeelde launcher-helper (voorkomt dubbele vensters)", True, True),
    ("Gedeeld", "pinas_pi_status.py",
     "Gedeelde Pi-statuscheck (1 SSH-commando voor Status + Addons Beheer)", True, True),
    # 14 augustus 2026: was starterkit=False - een HARDE, top-level import
    # in zowel Pi_NAS_Menu.pyw als pinas_addons_beheer.pyw (allebei wel in
    # de Starter Kit). Zonder dit bestand crasht een verse Starter Kit-
    # installatie meteen bij het opstarten van het hoofdmenu. Nooit
    # opgemerkt omdat niemand een Starter Kit-installatie helemaal
    # opnieuw getest heeft sinds dit bestand op 13 augustus is ontstaan.
    ("Gedeeld", "pinas_addon_scripts.py",
     "Gedeelde addon-sleutel -> scriptbestandsnaam-mapping", True, True),
    ("Gedeeld", "controleer_documentatie_consistentie.py",
     "Checkt of elke addon in Toegangsoverzicht/Topografie/Structuurcheck/Handleiding voorkomt", True, True),
    ("Gedeeld", "pinas_schijven.py",
     "Gedeelde schijfletter-resolver (share-naam i.p.v. vaste letter)", True, True),
    ("Gedeeld", "pinas_versies.json", "Versie-manifest (laatst geleverde datum per bestand)", True, True),
    # Build-/onderhoudstooling - een verse installatie hoeft niet zelf een
    # publieke GitHub-versie of Starter Kit te kunnen bouwen, dus bewust
    # NIET in de Starter Kit zelf (wel op GitHub, voor wie aan de suite
    # zelf verder wil bouwen).
    ("Gedeeld", "bijwerk_pinas_versies.py",
     "Werkt pinas_versies.json automatisch bij via contenthash-vergelijking", True, False),
    ("Gedeeld", "pinas_versies_hashes.json",
     "Hash-cache voor bijwerk_pinas_versies.py - lokaal, wijzigt bij elke run, wordt niet gepubliceerd",
     False, False),
    ("Gedeeld", "controleer_syntax.py",
     "py_compile/bash -n over de hele boom, verplicht voor een publieke build", True, False),
    ("Gedeeld", "opruimen_lijst.json",
     "Opruimlijst voor pinas_opruimen.pyw (FUSE kon niet verwijderen)", False, False),
    ("Gedeeld", "maak_publieke_versie.py", "Publieke versie maker", True, False),
    ("Gedeeld", "maak_starterkit.py", "Starter Kit maker", True, False),
    ("Gedeeld", "pinas_bestanden_register.py",
     "DE centrale bestandenlijst - bron voor Structuurcheck, publieke build en Starter Kit", True, True),
    # Gaat in de publieke versie naar Installatie\ (niet Gedeeld\) - blijft
    # daarom een losse, hardgecodeerde kopieerregel in
    # maak_publieke_versie.py zelf; deze entry is puur voor Structuurcheck.
    ("Gedeeld", "download_links.ini", "Download-links tools", True, True),
    ("Gedeeld", "herstel_backup_hdd.sh", "Backup-HDD herstelscript (Pi-kant)", True, True),
    ("Gedeeld", "pinas_iphone_backup.sh",
     "iPhone Back-up script (Pi-kant): foto's, bestanden, WhatsApp", True, True),
    ("Gedeeld", "pinas_iphone_verkennen.sh",
     "iPhone Doorbladeren script (Pi-kant): live, alleen-lezen Samba-share", True, True),
    ("Gedeeld", "version.py", "Centraal versienummer", True, True),
    ("Gedeeld", "test_suite.py", "Suite test", True, True),
    ("Gedeeld", "CONVENTIES.md", "Vaste conventies - lees dit eerst (9 augustus 2026)", False, False),

    # -- Publicatie ---------------------------------------------------------------
    ("Publicatie", "PiNAS_Suite_Handleiding.pdf", "Suite handleiding", True, True),
    ("Publicatie", "build_suite_handleiding.py", "Suite handleiding builder", True, True),
    ("Publicatie", "Publicatie_Gids.md", "Publicatiegids", False, False),
    ("Publicatie", "Publicatie_Gids.pdf", "Publicatiegids (PDF)", False, False),
    ("Publicatie", "PiNAS_Topografie.html", "Suite-topografie (menu x mappen matrix)", False, False),
    ("Publicatie", "build_topografie.py", "Topografie builder (16 juli 2026)", False, False),
    # Marketing-/publiciteitsmateriaal - hoort bij de GitHub-repo (laat
    # zien wat de suite is/kan), een Starter Kit-gebruiker heeft dat al
    # gezien en hoeft het niet mee te installeren.
    ("Publicatie", "PiNAS_Suite_Presentatie.pptx",
     "Presentatie voor bekendheid/publiciteit - installatie tot gebruik (9 augustus 2026)", True, False),
    ("Publicatie", "PiNAS_Suite_Architectuur.png",
     "Architectuurplaatje (5 lagen) voor de GitHub README (9 augustus 2026)", True, False),
    ("Publicatie", "PiNAS_Suite_Presentatie_Preview.pdf",
     "PDF-export van de presentatie, voor GitHub's ingebouwde viewer (9 augustus 2026)", True, False),

    # -- Installatie (installers zelf) -------------------------------------------
    # Nooit publiceren (te groot voor GitHub/bandbreedte) - de publieke
    # versie zet in plaats daarvan een gegenereerde LEESMIJ.md +
    # download_links.ini neer (zie maak_publieke_versie.py). Let op: Python
    # zelf staat hier NIET met een vaste naam (bevat een versienummer dat
    # elke download kan wijzigen) - zie de docstring in NAS_Map_Beheer.pyw.
    ("Installatie", "imager_2.0.7.exe", "Pi Imager", False, False),
    ("Installatie", "tigervnc64-1.16.2.exe", "TigerVNC", False, False),
    ("Installatie", "putty-64bit-0.84-installer.msi", "PuTTY", False, False),
    ("Installatie", "WinSCP-6.5.6-Setup.exe", "WinSCP", False, False),

    # -- Addons (Pi-hole, ZeroTier, Nextcloud, Vaultwarden, enz.) ----------------
    ("Addons", "pinas_pihole.sh", "Pi-hole installatie", True, True),
    ("Addons", "pinas_pihole_verwijderen.sh", "Pi-hole verwijderen", True, True),
    ("Addons", "pinas_zerotier.sh", "ZeroTier installatie", True, True),
    ("Addons", "pinas_zerotier_verwijderen.sh", "ZeroTier verwijderen", True, True),
    ("Addons", "pinas_nextcloud.sh", "Nextcloud installatie", True, True),
    ("Addons", "pinas_nextcloud_verwijderen.sh", "Nextcloud verwijderen", True, True),
    ("Addons", "pinas_vaultwarden.sh",
     "Vaultwarden installatie (root-CA + servercertificaat)", True, True),
    ("Addons", "pinas_vaultwarden_verwijderen.sh", "Vaultwarden verwijderen", True, True),
    ("Addons", "pinas_vaultwarden_cert_vertrouwen.pyw",
     "Vaultwarden - root-certificaat vertrouwen (Windows)", True, True),
    ("Addons", "pinas_vaultwarden_cert_import.ps1",
     "Vaultwarden - certificaat-import (elevated)", True, True),
    ("Addons", "pinas_printer.sh", "Printserver (CUPS+AirPrint) installatie", True, True),
    ("Addons", "pinas_printer_verwijderen.sh", "Printserver verwijderen", True, True),
    ("Addons", "pinas_dashboard.sh", "PiNAS Dashboard installatie", True, True),
    ("Addons", "pinas_dashboard_verwijderen.sh", "PiNAS Dashboard verwijderen", True, True),
    ("Addons", "pinas_dashboard_wachtwoord_resetten.sh",
     "PiNAS Dashboard - wachtwoord resetten", True, True),
    ("Addons", "pinas_addons_beheer.pyw", "Addons Beheer - hub-scherm", True, True),

    # -- ArchiefBackup (hoort bij Backup Beheer, geen zijproject meer) ----------
    ("ArchiefBackup", "archief_backup_bewaking.pyw",
     "Archief Backup Bewaking hoofdprogramma", True, True),
    ("ArchiefBackup", "start.bat", "Archief Backup Bewaking launcher", True, True),
]


def voor_structuurcheck():
    """(map, bestand, beschrijving)-tuples met bestand in os.path.join()-
    vorm - drop-in vervanging voor NAS_Map_Beheer.pyw's hand-getypte
    'checks'-lijst."""
    import os
    return [(map_, os.path.join(*bestand.split("/")), beschr)
            for map_, bestand, beschr, _gh, _sk in BESTANDEN]


def publieke_bestanden(map_, doel="github"):
    """Platte (geen submap) bestandsnamen voor 'map_' die naar 'doel'
    ("github" of "starterkit") horen te gaan - gebruikt door
    maak_publieke_versie.py/maak_starterkit.py voor hun eenvoudige
    kopieerlussen. Submap-bestanden (core/, assets/) staan bewust NIET
    in deze functie - die volgen geen platte kopieerlijst (assets/ is
    een selectieve glob, core/ ligt in een aparte submap) en blijven met
    de hand geregeld in de bouwscripts zelf, vlak bij die speciale
    kopieerstappen."""
    if doel not in ("github", "starterkit"):
        raise ValueError(f"doel moet 'github' of 'starterkit' zijn, kreeg: {doel!r}")
    kolom = 3 if doel == "github" else 4
    return tuple(b[1] for b in BESTANDEN
                 if b[0] == map_ and b[kolom] and "/" not in b[1])
