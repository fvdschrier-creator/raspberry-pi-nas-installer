"""
Maakt schone publieke versie voor GitHub
Staat in: C:\\PiNAS\\Gedeeld\\
Output:   C:\\PiNAS\\Publicatie\\NAS_Public\\
Werkt automatisch vanuit elke locatie

(12 augustus 2026) Omgezet van maak_publieke_versie.bat naar Python, als
onderdeel van de .bat->.py-migratie (zie OVERDRACHT_NIEUWE_CHAT.md). Bij die
gelegenheid:
  - NAS Simulator hoort er niet meer bij - de PiServer-bestanden
    maak_simulator_map.bat, Dockerfile, sim_setup.sh, SIMULATOR_LEESMIJ.md
    en start.sh zijn uit de meegekopieerde lijst gehaald.
  - lanman_fix.bat/install_vnc_viewer.bat/nas_upload.bat/nas_diagnose.bat/
    maak_starterkit.bat/maak_publieke_versie.bat zijn hernoemd naar hun
    .py-versies.
  - Docker Desktop Installer.exe-rij uit Installatie/LEESMIJ.md gehaald
    (hoorde alleen bij de simulator) en README.md/LEESMIJ.md-tekst
    bijgewerkt (geen Docker meer, migratie-naar-Python-status bijgewerkt).
  - Anonimiseren gebeurt nu in Python zelf i.p.v. via een los PowerShell-
    commando - geen kans meer op het delayed-expansion/'!'-probleem dat op
    10 augustus 2026 het oude script brak. Zelfde vervangingspatronen.

(13 augustus 2026, verbeterpunt #2) Draait nu VERPLICHT eerst
controleer_documentatie_consistentie.py voordat de publieke versie gebouwd
wordt - bij een gevonden gat stopt dit script met een foutmelding i.p.v.
gewoon door te bouwen met een stille documentatie-inconsistentie.
"""
import os
import re
import shutil
import sys


def _script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _nas_root():
    return os.path.dirname(_script_dir())


# 13 augustus 2026 (verbeterpunt #2): documentatie-consistentiecheck is
# voorheen een los script geweest dat iemand handmatig moest ONTHOUDEN te
# draaien - op 12 augustus (laat) bleef daardoor een vergeten Docker-check
# een tijd onopgemerkt. Nu een vereiste stap vlak voor elke GitHub-push:
# deze module (de daadwerkelijke pre-push-bouwstap) importeert en draait
# de check zelf, en weigert door te gaan bij een gevonden gat.
sys.path.insert(0, _script_dir())
import controleer_documentatie_consistentie as _docconsistentie
import bijwerk_pinas_versies as _versiesbijwerker
import controleer_syntax as _syntaxcontrole


def _controleer_documentatie_of_stop(nas_root):
    print()
    print("  [Documentatie-consistentiecheck - verplicht voor een publieke build]")
    totaal_gaten = _docconsistentie.voer_controle_uit(nas_root)
    if totaal_gaten is None:
        print()
        print("  FOUT: kon de addon-lijst niet laden - zie foutmelding hierboven.")
        print("  Publieke versie NIET gebouwd.")
        sys.exit(1)
    if totaal_gaten:
        print()
        print(f"  FOUT: {totaal_gaten} documentatiegat(en) gevonden (zie hierboven) - "
              "dicht deze eerst.")
        print("  Publieke versie NIET gebouwd, er is NIETS gepusht.")
        sys.exit(1)
    print("  OK - documentatie is consistent, doorgaan met de build.")


def _controleer_syntax_of_stop(nas_root):
    # 13 augustus 2026 (verbeterpunt #4): geen handmatige py_compile/bash -n
    # meer per bestand vlak voor een push - verplichte, blokkerende stap.
    print()
    print("  [Syntaxcontrole - verplicht voor een publieke build]")
    fouten = _syntaxcontrole.controleer(nas_root)
    if fouten:
        print()
        print(f"  FOUT: {fouten} bestand(en) met een syntaxfout (zie hierboven) - "
              "dicht deze eerst.")
        print("  Publieke versie NIET gebouwd, er is NIETS gepusht.")
        sys.exit(1)
    print("  OK - alle bestanden zijn syntactisch geldig, doorgaan met de build.")


def _werk_versies_bij(nas_root):
    # 13 augustus 2026 (verbeterpunt #3): pinas_versies.json niet meer met
    # de hand bijwerken - dit gebeurt nu automatisch, vlak voor elke
    # publieke build, op basis van een contenthash-vergelijking met de
    # vorige keer. Nooit blokkerend (in tegenstelling tot de documentatie-
    # check): een gewijzigd bestand is geen foutsituatie.
    print()
    print("  [pinas_versies.json automatisch bijwerken]")
    _versiesbijwerker.bijwerken(nas_root)


def _copy(bronmap, doelmap, bestand, label):
    bron = os.path.join(bronmap, bestand)
    if os.path.exists(bron):
        os.makedirs(doelmap, exist_ok=True)
        shutil.copy2(bron, os.path.join(doelmap, bestand))
        print(f"   OK: {label}\\{bestand}")
        return True
    print(f"   --: {label}\\{bestand} (niet gevonden)")
    return False


LEESMIJ_INSTALLATIE = """# Installatie-map

Deze map is in de GitHub-versie bewust LEEG. Download onderstaande bestanden
zelf en zet ze in deze map, VOORDAT je Beheer_install.bat draait.

De actuele downloadlinks staan ook in Gedeeld\\download_links.ini.

| Bestand | Waarvoor | Download |
|---|---|---|
| putty-64bit-installer.msi | SSH-verbinding met de Pi | https://the.earth.li/~sgtatham/putty/latest/w64/putty-64bit-installer.msi |
| tigervnc64-installer.exe | Grafisch bureaublad van de Pi | https://github.com/TigerVNC/tigervnc/releases/latest |
| WinSCP-installer.exe | Bestanden op de Pi bekijken/beheren (optioneel) | https://sourceforge.net/projects/winscp/files/latest/download |
| python-installer.exe | Draagt de hele Windows-kant van de suite | https://www.python.org/downloads/windows/ |
| imager_latest.exe | SD-kaart voorbereiden (Stap 2 van de wizard) | https://www.raspberrypi.com/software/ |

Bestandsnaam maakt niet uit zolang die begint met de juiste naam
(python-3*.exe, putty*.msi, tigervnc*.exe, WinSCP*.exe) - dat is wat
Beheer_install.bat zoekt.
"""

README = """# Pi NAS Suite

Een complete thuisserver-oplossing op basis van een Raspberry Pi 5 - bestanden opslaan,
automatisch backuppen, en volledig beheren vanuit Windows, zonder technische kennis.

![Architectuur](Publicatie/PiNAS_Suite_Architectuur.png)

**[Bekijk de presentatie](Publicatie/PiNAS_Suite_Presentatie_Preview.pdf)** - een uitgebreide
walkthrough met screenshots van installatie tot dagelijks gebruik (PDF, direct
leesbaar in de browser). Origineel (bewerkbaar): [PiNAS_Suite_Presentatie.pptx](Publicatie/PiNAS_Suite_Presentatie.pptx).

**[Volledige handleiding](Publicatie/PiNAS_Suite_Handleiding.pdf)** - alle vensters,
knoppen en instellingen in detail.

## Wat is dit?

De suite bestaat uit drie delen die samenwerken:

| Onderdeel | Wat doet het? | Op welk apparaat? |
|---|---|---|
| Pi NAS Menu | Verbinden, uploaden, diagnose, beheer | Windows PC |
| PiNAS Sync | Synchroniseren en PC Images backuppen | Windows PC |
| Pi NAS Server | Bestanden opslaan, Nextcloud, FileBrowser, Cockpit | Raspberry Pi 5 |

Onderdelen: Samba (netwerkschijven), Nextcloud (eigen cloud), FileBrowser (webbeheer),
Cockpit (Pi-beheer via browser), en optionele add-ons (Pi-hole, ZeroTier, Vaultwarden,
printserver, dashboard).

## Snel starten - van 0 naar werkend

1. **Bron kiezen**: pak deze repository uit (of download als ZIP)
2. **Beheer_install.bat draaien** (staat los in de root) - zet de hele suite neer op
   `C:\\PiNAS`, installeert de Windows-onderdelen en maakt een bureaubladsnelkoppeling.
   Dit bestand opent zelf niets - open daarna zelf de nieuwe snelkoppeling.
3. **Pi NAS Menu -> Installatie & Herstel** - de wizard (4 stappen: Gegevens, SD-kaart,
   Pi instellen, Windows klaarzetten) doet de rest automatisch.

Zie de `Installatie/`-map: die bevat een LEESMIJ met downloadlinks voor de installers
die je zelf even moet ophalen (PuTTY, TigerVNC, WinSCP (optioneel), Python,
Raspberry Pi Imager - te groot om in deze repository mee te nemen).

Volledige uitleg, inclusief een beslisboom voor "wat als ik al iets heb staan":
zie de [handleiding](Publicatie/PiNAS_Suite_Handleiding.pdf), hoofdstuk 2.

## Mapstructuur

| Map | Inhoud |
|---|---|
| `Beheer/` | Pi NAS Menu, installer, Backup Beheer |
| `Sync/` | PiNAS Sync (synchronisatieprogramma) |
| `ArchiefBackup/` | Archief Backup Bewaking |
| `Addons/` | Nextcloud, Pi-hole, ZeroTier, Vaultwarden en meer |
| `PiServer/` | Server-scripts die op de Pi zelf draaien |
| `Gedeeld/` | Gedeelde hulpmodules |
| `Publicatie/` | Handleiding en presentatie |
| `Installatie/` | LEESMIJ + downloadlinks voor installers |

## Bekende beperkingen & roadmap

Dit is een solo-onderhouden project - vooral gericht op functionaliteit en
documentatie. Een paar dingen om te weten voordat je begint:

- De meeste Windows-scripts zijn inmiddels van .bat naar Python omgezet. Een
  klein aantal blijft bewust .bat: bootstrap-installers (Beheer_install.bat)
  moeten werken voordat Python zelf geinstalleerd is, en python_bijwerken.bat
  werkt de Python-installatie zelf bij.
- Nog geen geautomatiseerde CI-pipeline - tests draaien lokaal via
  `test_suite.py`, niet automatisch bij elke commit.
- "Op mijn iPhone" (de Bestanden-app) is niet doorbladerbaar via de
  iPhone-functies - een vaste iOS/libimobiledevice-beperking, geen bug
  (zie hoofdstuk over iPhone Back-up in de handleiding).
- Issues en bijdragen zijn welkom, maar dit is een nevenproject - reactietijd
  kan wisselen.

## Licentie

MIT License - vrij te gebruiken, aanpassen en verspreiden. Vermeld de oorsprong als je
het deelt.
"""


def _anonimiseer(public_map, wachtwoord, zelf_naam):
    """Zelfde vervangingen als de oude PowerShell-anonimisering: IP,
    wachtwoord, 'Test1234'-placeholder, gebruikersnaam, backup-HDD UUID
    (twee patronen) en ZeroTier netwerk-ID. Slaat zichzelf over (net als de
    oude .bat deed voor maak_publieke_versie.bat) zodat de redactie-
    patronen niet door zichzelf vervangen worden."""
    extensies = {".bat", ".py", ".pyw", ".sh", ".json", ".md", ".ini", ".cfg"}
    for dirpad, _dirs, bestanden in os.walk(public_map):
        for naam in bestanden:
            if naam == zelf_naam:
                continue
            if os.path.splitext(naam)[1].lower() not in extensies:
                continue
            pad = os.path.join(dirpad, naam)
            try:
                # (12 augustus 2026) Binair lezen en newline="" schrijven,
                # NIET tekst-mode "r" (die vertaalt \r\n stilzwijgend naar
                # \n bij het lezen) - anders verandert elk Windows-bestand
                # (CRLF) hier in LF, wat een reuzendiff geeft in git voor
                # bestanden waar verder niets aan gewijzigd is.
                with open(pad, "rb") as f:
                    tekst = f.read().decode("utf-8")
            except UnicodeDecodeError:
                continue

            tekst = re.sub(r"192\.168\.\d+\.\d+", "UW_PI_IP_ADRES", tekst)
            if wachtwoord:
                tekst = tekst.replace(wachtwoord, "UW_WACHTWOORD")
            tekst = tekst.replace("Test1234", "UW_WACHTWOORD")
            tekst = re.sub(r"fvdsc(?!hrier)[a-z]*", "GEBRUIKER", tekst)
            tekst = tekst.replace("f838cf2d-6221-4452-b9df-a0ab36913586", "UW_BACKUP_HDD_UUID")
            tekst = tekst.replace("f838cf2d", "UW_BACKUP_HDD_UUID")
            tekst = tekst.replace("166359304e3cacb3", "UW_ZEROTIER_NETWERK_ID")

            with open(pad, "w", encoding="utf-8", newline="") as f:
                f.write(tekst)
            print(f"   SCHOON: {naam}")


# 13 augustus 2026 (verbeterpunt #5, Frans): "de anonimisering leunt op mijn
# handmatige grep-controle voor de push, geen ingebouwde garantie - een
# publieke repo, dit zou ik het eerst dichttimmeren." Elk patroon hieronder
# is het SPIEGELBEELD van een vervanging in _anonimiseer() hierboven (plus
# een generieke GitHub-token-check, die _anonimiseer() zelf niet had) - komt
# een van deze patronen NA het anonimiseren nog voor, dan is er iets
# misgegaan (nieuw vervangingspatroon vergeten, wachtwoord elders in een
# andere vorm, etc.) en moet de build hard stoppen i.p.v. gewoon doorgaan.
_GEHEIM_PATRONEN = (
    ("privé-IP-adres", re.compile(r"192\.168\.\d+\.\d+")),
    ("'Test1234'-placeholder (had UW_WACHTWOORD moeten worden)", re.compile(r"Test1234")),
    ("gebruikersnaam 'fvdsc...' (had GEBRUIKER moeten worden)", re.compile(r"fvdsc(?!hrier)[a-z]*")),
    ("backup-HDD UUID", re.compile(r"f838cf2d(-6221-4452-b9df-a0ab36913586)?")),
    ("ZeroTier netwerk-ID", re.compile(r"166359304e3cacb3")),
    # Klassiek formaat (ghp_/gho_/ghu_/ghs_/ghr_...) EN het nieuwere
    # fijnmazige formaat (github_pat_...) - alleen het eerste dekken was
    # een blinde vlek: precies het formaat van de PAT's die in deze suite
    # zelf gebruikt zijn (zie OVERDRACHT_NIEUWE_CHAT.md).
    ("GitHub Personal Access Token (klassiek)", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("GitHub Personal Access Token (fijnmazig)", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
)


def _controleer_geen_geheimen(public_map, wachtwoord, zelf_naam):
    """Doorzoekt de AL geanonimiseerde public_map nogmaals op alles wat
    _anonimiseer() had moeten weghalen (plus GitHub-tokens). Geeft een lijst
    (relpad, omschrijving, voorbeeldregel) terug - leeg = schoon."""
    extensies = {".bat", ".py", ".pyw", ".sh", ".json", ".md", ".ini", ".cfg"}
    treffers = []
    for dirpad, _dirs, bestanden in os.walk(public_map):
        for naam in bestanden:
            if naam == zelf_naam:
                continue  # bevat de patronen zelf als broncode, geen lek
            if os.path.splitext(naam)[1].lower() not in extensies:
                continue
            pad = os.path.join(dirpad, naam)
            try:
                with open(pad, "rb") as f:
                    tekst = f.read().decode("utf-8")
            except UnicodeDecodeError:
                continue
            for omschrijving, patroon in _GEHEIM_PATRONEN:
                match = patroon.search(tekst)
                if match:
                    relpad = os.path.relpath(pad, public_map)
                    treffers.append((relpad, omschrijving, match.group(0)))
            if wachtwoord and wachtwoord in tekst:
                relpad = os.path.relpath(pad, public_map)
                treffers.append((relpad, "het Samba-wachtwoord zelf", "(verborgen)"))
    return treffers


def _controleer_geheimen_of_stop(public_map, wachtwoord, zelf_naam):
    print()
    print("  [Controle op resterende geheimen - verplicht na het anonimiseren]")
    treffers = _controleer_geen_geheimen(public_map, wachtwoord, zelf_naam)
    if treffers:
        print(f"  FOUT: {len(treffers)} verdachte treffer(s) gevonden NA anonimiseren:")
        for relpad, omschrijving, voorbeeld in treffers:
            print(f"    X  {relpad}: {omschrijving} ({voorbeeld!r})")
        print()
        print(f"  De publieke versie staat nog in {public_map} voor onderzoek,")
        print("  maar is NIET geverifieerd als schoon - NIET pushen naar GitHub.")
        sys.exit(1)
    print("  OK - geen resterende geheimen gevonden.")


def main():
    nas_root = _nas_root()
    public_map = os.path.join(nas_root, "Publicatie", "NAS_Public")

    print()
    print(" Pi NAS Suite - Maak publieke versie voor GitHub")
    print(" " + "=" * 62)
    print(f" NAS root:  {nas_root}")
    print(f" Output:    {public_map}")
    print(" " + "=" * 62)

    _controleer_syntax_of_stop(nas_root)
    _werk_versies_bij(nas_root)
    _controleer_documentatie_of_stop(nas_root)
    print()

    # Eerst opschonen: NAS_Public volledig opnieuw opbouwen, zodat verouderde
    # bestanden niet in de GitHub-release achterblijven.
    if os.path.exists(public_map):
        shutil.rmtree(public_map)
    for submap in ("", "PiServer", "Sync", os.path.join("Sync", "core"), "Beheer",
                   "Gedeeld", "ArchiefBackup", "Publicatie", "Addons"):
        os.makedirs(os.path.join(public_map, submap), exist_ok=True)

    # -- PiServer ------------------------------------------------------------
    # (12 augustus 2026) Simulator-bestanden bewust weggelaten - niet meer gebruikt.
    print("  [PiServer]")
    piserver_doel = os.path.join(public_map, "PiServer")
    for bestand in (
        "nas_installer.py", "nas_installer_cli.py", "seagate_web.py",
        "seagate-web.service", "smart_plug.py", "smart_plug_config.json",
        "hue_diagnose.py", "pi_welkom.sh", "install.sh", "nas_start.sh",
        "README.md",
    ):
        _copy(os.path.join(nas_root, "PiServer"), piserver_doel, bestand, "PiServer")

    # -- Sync ------------------------------------------------------------------
    print()
    print("  [Sync]")
    sync_doel = os.path.join(public_map, "Sync")
    for bestand in ("pinas_sync_app.pyw", "start.bat", "requirements.txt", "install_windows.bat"):
        _copy(os.path.join(nas_root, "Sync"), sync_doel, bestand, "Sync")
    for bestand in ("sync_engine.py", "bron_doel_picker.py", "thema.py", "__init__.py"):
        _copy(os.path.join(nas_root, "Sync", "core"), os.path.join(sync_doel, "core"), bestand, "Sync\\core")

    # -- ArchiefBackup (hoofdmap, hoort bij Backup Beheer) --------------------
    print()
    print("  [ArchiefBackup]")
    archief_doel = os.path.join(public_map, "ArchiefBackup")
    for bestand in ("archief_backup_bewaking.pyw", "start.bat"):
        _copy(os.path.join(nas_root, "ArchiefBackup"), archief_doel, bestand, "ArchiefBackup")

    # -- Addons (17 juli 2026 toegevoegd - stonden er nooit in) ----------------
    print()
    print("  [Addons]")
    addons_doel = os.path.join(public_map, "Addons")
    for bestand in (
        "pinas_addons_beheer.pyw",
        "pinas_nextcloud.sh", "pinas_nextcloud_verwijderen.sh",
        "pinas_pihole.sh", "pinas_pihole_verwijderen.sh",
        "pinas_zerotier.sh", "pinas_zerotier_verwijderen.sh",
        "pinas_vaultwarden.sh", "pinas_vaultwarden_verwijderen.sh",
        "pinas_vaultwarden_cert_vertrouwen.pyw", "pinas_vaultwarden_cert_import.ps1",
        "pinas_printer.sh", "pinas_printer_verwijderen.sh",
        "pinas_dashboard.sh", "pinas_dashboard_verwijderen.sh",
        "pinas_dashboard_wachtwoord_resetten.sh",
    ):
        _copy(os.path.join(nas_root, "Addons"), addons_doel, bestand, "Addons")

    # -- Beheer ------------------------------------------------------------------
    print()
    print("  [Beheer]")
    beheer_bron = os.path.join(nas_root, "Beheer")
    beheer_doel = os.path.join(public_map, "Beheer")
    for bestand in (
        "Pi_NAS_Menu.pyw", "pi_nas_setup.pyw", "Pi_NAS_Menu.ico",
        "Beheer_install.bat", "lanman_fix.py", "install_vnc_viewer.py",
        "pinas_backup_beheer.pyw", "pinas_image_backup.pyw",
    ):
        _copy(beheer_bron, beheer_doel, bestand, "Beheer")

    # PC Image Backup's gedeelde module staat in de submap core/
    core_bron = os.path.join(beheer_bron, "core")
    if os.path.isdir(core_bron):
        core_doel = os.path.join(beheer_doel, "core")
        os.makedirs(core_doel, exist_ok=True)
        for naam in os.listdir(core_bron):
            bron = os.path.join(core_bron, naam)
            if os.path.isfile(bron):
                shutil.copy2(bron, os.path.join(core_doel, naam))
        print("   OK: Beheer\\core\\")
    else:
        print("   --: Beheer\\core (niet gevonden)")

    # Screenshots staan in de submap assets/
    assets_bron = os.path.join(beheer_bron, "assets")
    if os.path.isdir(assets_bron):
        assets_doel = os.path.join(beheer_doel, "assets")
        os.makedirs(assets_doel, exist_ok=True)
        for naam in os.listdir(assets_bron):
            if naam.startswith("pinas_sync_scherm") and naam.lower().endswith(".png"):
                shutil.copy2(os.path.join(assets_bron, naam), os.path.join(assets_doel, naam))
        print("   OK: Beheer\\assets\\ screenshots")
    else:
        print("   --: Beheer\\assets (niet gevonden)")

    # -- Publicatie (Handleiding, verhuisd hierheen) --------------------------
    print()
    print("  [Publicatie]")
    publicatie_doel = os.path.join(public_map, "Publicatie")
    for bestand in (
        "PiNAS_Suite_Handleiding.pdf", "build_suite_handleiding.py",
        "PiNAS_Suite_Presentatie.pptx", "PiNAS_Suite_Presentatie_Preview.pdf",
        "PiNAS_Suite_Architectuur.png",
    ):
        _copy(os.path.join(nas_root, "Publicatie"), publicatie_doel, bestand, "Publicatie")

    # -- Gedeeld ------------------------------------------------------------------
    print()
    print("  [Gedeeld]")
    gedeeld_bron = os.path.join(nas_root, "Gedeeld")
    gedeeld_doel = os.path.join(public_map, "Gedeeld")
    for bestand in (
        "pinas_theme.py", "pinas_theme_donker.py", "pinas_theme_licht.py",
        "pinas_ui.py", "pinas_wachtwoord.py", "pinas_logging.py",
        "pinas_launcher.py", "pinas_pi_status.py", "pinas_addon_scripts.py",
        "controleer_documentatie_consistentie.py", "pinas_schijven.py",
        "pinas_versies.json", "version.py",
        "nas_upload.py", "nas_diagnose.py", "nas_diagnose.sh",
        "herstel_backup_hdd.sh", "pinas_iphone_backup.sh",
        "pinas_iphone_verkennen.sh", "test_suite.py",
        "maak_publieke_versie.py", "maak_starterkit.py",
        "bijwerk_pinas_versies.py", "controleer_syntax.py",
    ):
        _copy(gedeeld_bron, gedeeld_doel, bestand, "Gedeeld")
    # Gedeeld\ScriptRunner\pi_script_draaien.bat ingetrokken (31 juli 2026,
    # Frans: niet meer los gebruikt - Addons Beheer dekt dit nu)

    # -- Installatie ---------------------------------------------------------------
    # (9 augustus 2026, Frans) De installers zelf horen niet in de publieke
    # repo (te groot / bandbreedte-kosten). De map blijft leeg met een
    # LEESMIJ + download_links.ini. (12 augustus 2026: Docker-rij verwijderd,
    # hoorde alleen bij de niet meer gebruikte simulator.)
    print()
    print("  [Installatie]")
    installatie_doel = os.path.join(public_map, "Installatie")
    os.makedirs(installatie_doel, exist_ok=True)
    with open(os.path.join(installatie_doel, "LEESMIJ.md"), "w", encoding="utf-8", newline="") as f:
        f.write(LEESMIJ_INSTALLATIE.replace("\n", "\r\n"))
    download_links_bron = os.path.join(gedeeld_bron, "download_links.ini")
    if os.path.exists(download_links_bron):
        shutil.copy2(download_links_bron, os.path.join(installatie_doel, "download_links.ini"))
    print("   OK: Installatie\\LEESMIJ.md (installers zelf NIET meegenomen - te groot voor GitHub)")

    # -- README.md in de root -----------------------------------------------------
    print()
    print("  [README]")
    with open(os.path.join(public_map, "README.md"), "w", encoding="utf-8", newline="") as f:
        f.write(README.replace("\n", "\r\n"))
    print("   OK: README.md")

    # -- Beheer_install.bat in root ------------------------------------------------
    beheer_install_bron = os.path.join(beheer_bron, "Beheer_install.bat")
    if os.path.exists(beheer_install_bron):
        shutil.copy2(beheer_install_bron, os.path.join(public_map, "Beheer_install.bat"))
        print("   OK: Beheer_install.bat (root)")
    with open(os.path.join(public_map, "INSTALL_TYPE.txt"), "w", encoding="utf-8", newline="") as f:
        f.write("minimaal\r\n")

    # -- Wachtwoord ophalen uit cache -----------------------------------------------
    print()
    print("  [Wachtwoord ophalen voor anonimisering]")
    ww_cache = os.path.join(nas_root, "Logs", ".ww_samba.dat")
    huidig_ww = ""
    if os.path.exists(ww_cache):
        with open(ww_cache, "r", encoding="utf-8") as f:
            huidig_ww = f.readline().strip()
        print("   Wachtwoord gevonden voor anonimisering")
    else:
        print("   Geen wachtwoordcache gevonden (alleen IP wordt geanonimiseerd)")

    # -- Anonimiseren ------------------------------------------------------------------
    print()
    print("  [Anonimiseren]")
    _anonimiseer(public_map, huidig_ww, zelf_naam="maak_publieke_versie.py")

    _controleer_geheimen_of_stop(public_map, huidig_ww, zelf_naam="maak_publieke_versie.py")

    print()
    print("  " + "=" * 62)
    print("  Klaar! Publieke versie staat in:")
    print(f"  {public_map}")
    print()
    print("  Structuur: PiServer\\, Sync\\, ArchiefBackup\\, Beheer\\, Addons\\, Publicatie\\, Gedeeld\\, Installatie\\")
    print("  Geanonimiseerd + geverifieerd: IP, wachtwoord, gebruikersnaam, backup-HDD UUID, ZeroTier")
    print("  netwerk-ID en GitHub-tokens - geen handmatige controle meer nodig voor de push.")
    print("  " + "=" * 62)
    print()
    input("Druk op Enter om af te sluiten...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
