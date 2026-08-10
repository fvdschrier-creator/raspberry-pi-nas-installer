#!/usr/bin/env python3
# pinas_backup_beheer.pyw - Pi NAS Suite
#
# Backup Beheer: de ENE centrale plek voor alle backup-gerelateerde acties.
# Vervangt het eerdere pinas_backup_overzicht.pyw en neemt drie acties over
# die voorheen los in andere schermen stonden (Frans, 12 juli 2026):
#   - Synchronisatie was een losse knop in het hoofdmenu
#   - PC Image Backup zat ingebakken in PiNAS Sync (nu een eigen programma)
#   - Archief Backup Bewaking en Systeem-image (SD-kaart) zaten in NAS Map Beheer
#   - Backup-HDD controleren/herstellen zat in Onderhoud
#
# Pure navigatie/uitvoering per actie, geen samengevoegde uitvoering: elke
# knop doet precies een ding. Geen "alles-in-1"-knop - dat risico (bijv.
# per ongeluk een zware SD-kaart-image naast een routine-sync starten) is
# bewust vermeden.
#
# Hoort thuis in: Beheer\pinas_backup_beheer.pyw

import tkinter as tk
from tkinter import messagebox
import subprocess
import os
import sys
import tempfile
import datetime
import configparser
import threading
import time

# -- Gedeeld op het pad zetten, zodat pinas_theme en pinas_ui te vinden zijn --
_gedeeld = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Gedeeld")
if os.path.isdir(_gedeeld) and _gedeeld not in sys.path:
    sys.path.insert(0, os.path.abspath(_gedeeld))

from pinas_theme import BG, PANEL, FG, DIM, ACCENT_PIBACKUP
from pinas_ui import maak_header, maak_sectie, maak_knop, maak_status_label, maak_status_legenda
import pinas_launcher
import pinas_schijven

try:
    from version import BIJGEWERKT
except ImportError:
    BIJGEWERKT = "onbekende datum"


def _script_dir():
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def _nas_root():
    """NAS root = een niveau omhoog van Beheer/PiServer/Sync/Gedeeld."""
    d = _script_dir()
    for sub in ["Beheer", "PiServer", "Sync", "Gedeeld"]:
        if os.path.basename(d) == sub:
            return os.path.dirname(d)
    return os.path.dirname(d)


def _c_pinas():
    return os.path.join("C:\\", "PiNAS")


def _pad(*delen):
    """Probeert eerst de root gevonden via de mapnaam van het script,
    en anders C:\\PiNAS als vaste terugval."""
    for root in [_nas_root(), _c_pinas()]:
        p = os.path.join(root, *delen)
        if os.path.exists(p):
            return p
    return None


# -- PI_IP uit picontrol.cfg, zelfde bestand als Pi NAS Menu / NAS Map Beheer --
_cfg = configparser.ConfigParser()
_cfg_pad = os.path.join(_script_dir(), "picontrol.cfg")
if os.path.exists(_cfg_pad):
    _cfg.read(_cfg_pad, encoding="utf-8")
PI_IP = _cfg.get("pi", "ip", fallback="UW_PI_IP_ADRES")


def _backup_letter():
    """Geeft de werkelijke, huidige stationsletter voor de Backup-share
    terug (i.p.v. altijd 'Z' aan te nemen), voor gebruik in teksten."""
    try:
        naam = _cfg.get("schijven", "Z", fallback="Backup") if _cfg.has_section("schijven") else "Backup"
    except Exception:
        naam = "Backup"
    return pinas_schijven.vind_letter_of_terugval(naam, "Z", PI_IP)


def _spiegel_letter():
    """Geeft de werkelijke, huidige stationsletter voor de Spiegel
    Backup-share terug (i.p.v. altijd 'H' aan te nemen), voor gebruik in
    teksten - zelfde aanpak als _backup_letter(). 9 augustus 2026:
    toegevoegd omdat de helpteksten hieronder nog een hardcoded "(H:)"
    hadden staan terwijl de rest van de suite al lang dynamisch was."""
    return pinas_schijven.vind_letter_of_terugval("SpiegelBackup", "H", PI_IP)


def _open_sync():
    if pinas_launcher.draait_al("pinas_sync_app.pyw"):
        return
    pad = _pad("Sync", "start.bat")
    if pad:
        subprocess.Popen(["cmd", "/c", pad], creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        messagebox.showerror("Niet gevonden",
            "PiNAS Sync is niet gevonden.\n\nVerwacht in: C:\\PiNAS\\Sync\\start.bat")


def _open_image_backup():
    ok, fout = pinas_launcher.open_programma(
        "pinas_image_backup.pyw", roots=[_nas_root(), _c_pinas()], submappen=["Beheer"])
    if not ok:
        messagebox.showerror("Niet gevonden", fout)


def _open_archief_bewaking():
    if pinas_launcher.draait_al("archief_backup_bewaking.pyw"):
        return
    nas = _nas_root()
    kandidaten = []
    # ArchiefBackup is de huidige (Fase 1, 8 augustus 2026) mapnaam.
    # QnapCheck/Zijprojecten\QnapCheck blijven als terugval staan zolang
    # niet elke installatie (o.a. de Dell) al gemigreerd is.
    for basis in [os.path.join(nas, "ArchiefBackup"),
                  os.path.join(_c_pinas(), "ArchiefBackup"),
                  os.path.join(nas, "QnapCheck"),
                  os.path.join(_c_pinas(), "QnapCheck"),
                  os.path.join(nas, "Zijprojecten", "QnapCheck"),
                  os.path.join(_c_pinas(), "Zijprojecten", "QnapCheck")]:
        kandidaten.append(os.path.join(basis, "start.bat"))
        kandidaten.append(os.path.join(basis, "archief_backup_bewaking.pyw"))
        kandidaten.append(os.path.join(basis, "qnap_backup_check.pyw"))
    for pad in kandidaten:
        if os.path.exists(pad):
            if pad.endswith(".bat"):
                subprocess.Popen(["cmd", "/c", pad], creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                for exe in ["pythonw.exe", "pythonw", "python.exe", "python"]:
                    try:
                        subprocess.Popen([exe, pad])
                        return
                    except FileNotFoundError:
                        continue
            return
    messagebox.showerror("Niet gevonden",
        "Archief Backup Bewaking niet gevonden in C:\\PiNAS\\ArchiefBackup\\")


def _maak_systeem_image():
    """Maakt een gecomprimeerde image van de actieve Pi SD-kaart (dd + gzip)
    op de backup-HDD. Terugzetten gaat niet via een knop - zie handleiding
    hoofdstuk 3.7 (Windows/Win32DiskImager of Linux/Zorin met dd)."""
    akkoord = messagebox.askyesno(
        "Systeem-image maken",
        "Dit maakt een volledige, gecomprimeerde kopie van de Pi "
        "SD-kaart (dd + gzip) en zet die op de backup-HDD:\n\n"
        f"{_backup_letter()}:\\PiNAS Images\\pinas_sd_<datum>.img.gz\n\n"
        "Belangrijk:\n"
        "  - Dit draait terwijl de Pi doorwerkt; kan tientallen "
        "minuten duren, afhankelijk van de kaartgrootte.\n"
        f"  - De externe HDD ({_backup_letter()}:) moet aanstaan.\n"
        "  - Voor terugzetten: zie de handleiding hoofdstuk 3.7 - "
        "er is geen knop voor terugzetten, dat kan niet veilig "
        "vanaf de draaiende kaart zelf.\n\n"
        "Doorgaan?")
    if not akkoord:
        return

    datum = datetime.date.today().strftime("%Y-%m-%d")
    bestand = f"pinas_sd_{datum}.img.gz"
    # LET OP: het pad bevat een spatie ("PiNAS Images"). De aanhalingstekens
    # daaromheen moeten hier met \" (backslash-quote) geschreven worden, NIET
    # met kale " - dit hele commando zit namelijk al zelf tussen dubbele
    # aanhalingstekens (die het geheel als 1 argument voor ssh.exe afbakenen,
    # verderop bij 'ssh -t ... "..."'). Kale " erin zou die buitenste
    # aanhaling voortijdig laten "sluiten" bij het inlezen door cmd.exe/
    # ssh.exe, waardoor "/mnt/backup/PiNAS Images/..." bij de spatie in twee
    # losse stukken uiteenvalt. Dat gaf precies deze fout op de Pi (17 juli
    # 2026, gemeld door Frans): "tee: /mnt/backup/PiNAS: Is a directory" -
    # tee kreeg "/mnt/backup/PiNAS" en "Images/<bestand>" als twee aparte
    # argumenten in plaats van 1 pad met spatie, dd/gzip bleven overigens
    # gewoon lopen (vandaar de voortgangsregel), maar er kwam geen bruikbaar
    # bestand op de juiste plek terecht. Met \" blijft het pad met spatie nu
    # heel: cmd.exe/ssh.exe geven de \" door als een letterlijke " naar de
    # Pi, waar bash 'm weer normaal als aanhalingsteken om het pad leest.
    # Voorheen heette deze map gewoon "PiNAS", maar die naam is vrijgemaakt
    # voor het Toegangsoverzicht (Z:\PiNAS Toegang) - zie pinas_versies.json
    # (16 juli 2026).
    remote_cmd = (
        'mkdir -p \\"/mnt/backup/PiNAS Images\\" && '
        "sudo dd if=/dev/mmcblk0 bs=4M status=progress | gzip | "
        f'sudo tee \\"/mnt/backup/PiNAS Images/{bestand}\\" > /dev/null && '
        f'echo === Klaar: \\"/mnt/backup/PiNAS Images/{bestand}\\" ==='
    )
    bat = os.path.join(tempfile.gettempdir(), "pinas_systeem_image.bat")
    regels = [
        "@echo off",
        "echo Systeem-image maken - dit kan lang duren, laat dit venster open staan.",
        "echo.",
        'ssh -t pi@' + PI_IP + ' "' + remote_cmd + '"',
        "echo.",
        "echo === Klaar. Zie de handleiding hoofdstuk 3.7 voor terugzetten. ===",
        "pause",
    ]
    with open(bat, "w", newline="") as f:
        f.write("\r\n".join(regels) + "\r\n")
    subprocess.Popen('start cmd /k "' + bat + '"', shell=True)


def _open_iphone_backup():
    """iPhone Back-up via pinas_iphone_backup.sh op de Pi.

    BELANGRIJK: de iPhone moet aan een usb-poort VAN DE PI hangen, niet aan
    deze Windows-pc - het script draait op de Pi en heeft rechtstreeks
    usb-toegang tot het toestel nodig (10 augustus 2026, met Frans
    afgesproken samen met de scope: foto's + gedeelde app-bestanden altijd,
    WhatsApp best effort, Notities bewust NIET meegenomen - zie de
    Handleiding voor de reden)."""
    nas = _nas_root()
    script = _script_dir()
    kandidaten = [
        os.path.join(nas, "Gedeeld", "pinas_iphone_backup.sh"),
        os.path.join(nas, "PiServer", "pinas_iphone_backup.sh"),
        os.path.join(script, "pinas_iphone_backup.sh"),
    ]
    sh_pad = next((p for p in kandidaten if os.path.exists(p)), None)
    if not sh_pad:
        messagebox.showerror("Niet gevonden",
            "pinas_iphone_backup.sh niet gevonden.\n"
            "Zet het bestand in C:\\PiNAS\\Gedeeld\\")
        return

    akkoord = messagebox.askyesno(
        "iPhone Back-up",
        "BELANGRIJK: hang de iPhone aan een usb-poort VAN DE PI zelf, "
        "NIET aan deze Windows-pc. Dit script draait op de Pi en heeft "
        "daar rechtstreeks usb-toegang voor nodig.\n\n"
        "Kopieert naar de backup-HDD:\n"
        f"{_backup_letter()}:\\PiNAS iPhone Backup\\iPhone_<datum>\\\n\n"
        "Wat wordt meegenomen:\n"
        "  - Foto's en video's (camerarol)\n"
        "  - Bestanden van apps met bestandsdeling\n"
        "  - WhatsApp-chats (best effort, kan mislukken - de rest van de "
        "back-up gaat dan gewoon door)\n"
        "  - Notities NIET (zit standaard in iCloud, niet leesbaar te "
        "krijgen via deze weg)\n\n"
        "Eerste keer? Ontgrendel de iPhone en tik op 'Vertrouw deze "
        "computer' zodra dat gevraagd wordt.\n\n"
        "Doorgaan?")
    if not akkoord:
        return

    bat = os.path.join(tempfile.gettempdir(), "pinas_iphone_backup.bat")
    regels = [
        "@echo off",
        "echo iPhone Back-up - script naar de Pi kopieren...",
        'scp -o StrictHostKeyChecking=no "' + sh_pad + '" pi@' + PI_IP + ":/tmp/pinas_iphone_backup.sh",
        "if errorlevel 1 (",
        "  echo.",
        "  echo FOUT: kon het script niet naar de Pi kopieren.",
        "  echo Controleer of de Pi bereikbaar is.",
        "  pause",
        "  exit /b 1",
        ")",
        "echo.",
        "echo Verbinden en back-up starten. Hou de iPhone in de gaten voor",
        "echo een eventuele 'Vertrouw deze computer'-vraag.",
        "echo.",
        'ssh -t pi@' + PI_IP + ' "sudo bash /tmp/pinas_iphone_backup.sh; rm -f /tmp/pinas_iphone_backup.sh"',
        "echo.",
        "echo === Klaar. Dit venster mag gesloten worden. ===",
        "pause",
    ]
    with open(bat, "w", newline="") as f:
        f.write("\r\n".join(regels) + "\r\n")
    subprocess.Popen('start cmd /k "' + bat + '"', shell=True)


def _open_iphone_verkennen():
    """iPhone Doorbladeren via pinas_iphone_verkennen.sh op de Pi.

    Maakt de iPhone LIVE en ALLEEN-LEZEN zichtbaar zolang het venster open
    blijft - geen back-up, puur even kijken. BELANGRIJK: iPhone aan de Pi,
    niet aan de pc (10 augustus 2026, met Frans afgesproken).

    10 augustus 2026 (bug gevonden bij live test: rechtstreeks \\\\ip\\iPhone
    intypen in Verkenner deed soms niets - geen foutmelding, geen inlogscherm,
    gewoon stilte): wordt nu net als Opslag/Backup automatisch als
    schijfletter gekoppeld via 'net use' (_iphone_koppelen_en_opruimen), in
    plaats van de gebruiker het pad zelf te laten intypen."""
    nas = _nas_root()
    script = _script_dir()
    kandidaten = [
        os.path.join(nas, "Gedeeld", "pinas_iphone_verkennen.sh"),
        os.path.join(nas, "PiServer", "pinas_iphone_verkennen.sh"),
        os.path.join(script, "pinas_iphone_verkennen.sh"),
    ]
    sh_pad = next((p for p in kandidaten if os.path.exists(p)), None)
    if not sh_pad:
        messagebox.showerror("Niet gevonden",
            "pinas_iphone_verkennen.sh niet gevonden.\n"
            "Zet het bestand in C:\\PiNAS\\Gedeeld\\")
        return

    akkoord = messagebox.askyesno(
        "iPhone Doorbladeren",
        "BELANGRIJK: hang de iPhone aan een usb-poort VAN DE PI zelf, "
        "NIET aan deze Windows-pc.\n\n"
        "Maakt de iPhone tijdelijk en ALLEEN-LEZEN zichtbaar - net als de "
        "Opslag/Backup-schijven wordt hij automatisch als schijfletter "
        "gekoppeld en geopend in Verkenner, zolang dit venster open blijft. "
        "Geen back-up - puur om te bekijken wat er op het toestel staat.\n\n"
        "Eerste keer? Ontgrendel de iPhone en tik op 'Vertrouw deze "
        "computer' zodra dat gevraagd wordt.\n\n"
        "Doorgaan?")
    if not akkoord:
        return

    bat = os.path.join(tempfile.gettempdir(), "pinas_iphone_verkennen.bat")
    regels = [
        "@echo off",
        "echo iPhone Doorbladeren - script naar de Pi kopieren...",
        'scp -o StrictHostKeyChecking=no "' + sh_pad + '" pi@' + PI_IP + ":/tmp/pinas_iphone_verkennen.sh",
        "if errorlevel 1 (",
        "  echo.",
        "  echo FOUT: kon het script niet naar de Pi kopieren.",
        "  echo Controleer of de Pi bereikbaar is.",
        "  pause",
        "  exit /b 1",
        ")",
        "echo.",
        "echo Verbinden. Hou de iPhone in de gaten voor een eventuele",
        "echo 'Vertrouw deze computer'-vraag. Zodra de iPhone zichtbaar is,",
        "echo opent Verkenner vanzelf. Laat dit venster open staan zolang",
        "echo je de iPhone wilt bekijken - druk daarna op ENTER IN DIT",
        "echo VENSTER om weer op te ruimen.",
        "echo.",
        'ssh -t pi@' + PI_IP + ' "sudo bash /tmp/pinas_iphone_verkennen.sh; rm -f /tmp/pinas_iphone_verkennen.sh"',
        "echo.",
        "echo === Klaar. Dit venster mag gesloten worden. ===",
        "pause",
    ]
    with open(bat, "w", newline="") as f:
        f.write("\r\n".join(regels) + "\r\n")

    # 10 augustus 2026 (bug gevonden bij live test: rechtstreeks \\ip\iPhone
    # intypen in Verkenner deed soms helemaal niets - geen foutmelding, geen
    # inlogscherm, gewoon stilte; Frans stelde toen zelf voor: waarom niet
    # gewoon als schijfletter koppelen, zoals Opslag/Backup dat al doen?).
    # Dat gebeurt nu hier: een aparte achtergrond-thread wacht tot de
    # tijdelijke share op de Pi actief is, koppelt 'm dan met 'net use' aan
    # een vrije letter (hergebruikt de tijdens Installatie opgeslagen
    # inloggegevens via cmdkey - dus geen inlogscherm) en opent Verkenner
    # vanzelf. Zodra dit cmd-venster wordt gesloten (ENTER of het kruisje)
    # wordt de letter ook weer losgekoppeld - precies zo tijdelijk als de
    # share zelf op de Pi.
    proc = subprocess.Popen(["cmd", "/k", bat], creationflags=subprocess.CREATE_NEW_CONSOLE)
    threading.Thread(target=_iphone_koppelen_en_opruimen, args=(proc,), daemon=True).start()


def _iphone_vrije_letter():
    """Eerstvolgende vrije stationsletter voor de tijdelijke iPhone-koppeling
    (nooit een letter die al iets anders in gebruik heeft)."""
    for letter in "IJKLMNOPQRSTUVWX":
        if not os.path.exists(letter + ":\\"):
            return letter
    return None


def _iphone_koppelen_en_opruimen(proc):
    """Draait in een achtergrond-thread zolang het iPhone Doorbladeren-
    venster open staat: koppelt de tijdelijke share aan een schijfletter
    zodra hij actief is (tot 90 sec. wachten - het kan even duren als de
    iPhone eerst 'Vertrouw deze computer' moet bevestigen), opent Verkenner,
    en koppelt weer los zodra het venster sluit."""
    letter = _iphone_vrije_letter()
    if not letter:
        proc.wait()
        return
    doel = r"\\" + PI_IP + r"\iPhone"
    gekoppeld = False
    venster_nog_open = True
    for _ in range(45):
        if proc.poll() is not None:
            venster_nog_open = False
            break  # venster al gesloten voordat de share actief werd
        r = subprocess.run(["net", "use", letter + ":", doel],
                            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if r.returncode == 0:
            gekoppeld = True
            try:
                os.startfile(letter + ":\\")
            except Exception:
                pass
            break
        time.sleep(2)
    if not gekoppeld and venster_nog_open:
        # Terugval: 'net use' is binnen 90 sec. niet gelukt (bijv. cmdkey
        # ontbreekt op deze pc). Probeer het rechtstreekse pad alsnog te
        # openen - dan kan Windows zelf om een wachtwoord vragen in plaats
        # van dat er niets gebeurt.
        try:
            os.startfile(doel)
        except Exception:
            pass
    proc.wait()
    if gekoppeld:
        subprocess.run(["net", "use", letter + ":", "/delete", "/yes"],
                        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)


def _herstel_backup_hdd():
    """Backup-HDD controleren/herstellen via e2fsck op de Pi.

    Draait INTERACTIEF in een eigen venster (ssh -t): de tool stelt zo
    nodig een ja/nee-vraag voor de volledige reparatie, en e2fsck op een
    volle 7TB-schijf kan lang duren. Daarom een echt SSH-venster i.p.v.
    opgevangen uitvoer met timeout (die zou de vraag niet kunnen
    beantwoorden en bij een lange controle afbreken)."""
    nas = _nas_root()
    script = _script_dir()
    kandidaten = [
        os.path.join(nas, "Gedeeld", "herstel_backup_hdd.sh"),
        os.path.join(nas, "PiServer", "herstel_backup_hdd.sh"),
        os.path.join(script, "herstel_backup_hdd.sh"),
    ]
    sh_pad = next((p for p in kandidaten if os.path.exists(p)), None)
    if not sh_pad:
        messagebox.showerror("Niet gevonden",
            "herstel_backup_hdd.sh niet gevonden.\n"
            "Zet het bestand in C:\\PiNAS\\Gedeeld\\")
        return

    akkoord = messagebox.askyesno(
        "Backup-HDD controleren / herstellen",
        "Dit controleert en herstelt het bestandssysteem van de "
        f"backup-HDD ({_backup_letter()}:) op de Pi met e2fsck.\n\n"
        "Belangrijk:\n"
        "  - De schijf wordt tijdelijk losgekoppeld; sluit eerst lopende "
        "backups of synchronisaties.\n"
        "  - Op een volle schijf kan dit lang duren (tot tientallen minuten).\n"
        "  - Beantwoord eventuele vragen in het venster dat opent.\n\n"
        "Doorgaan?")
    if not akkoord:
        return

    bat = os.path.join(tempfile.gettempdir(), "pinas_herstel_hdd.bat")
    regels = [
        "@echo off",
        "echo Backup-HDD herstel - script naar de Pi kopieren...",
        'scp -o StrictHostKeyChecking=no "' + sh_pad + '" pi@' + PI_IP + ":/tmp/herstel_backup_hdd.sh",
        "if errorlevel 1 (",
        "  echo.",
        "  echo FOUT: kon het script niet naar de Pi kopieren.",
        "  echo Controleer of de Pi bereikbaar is.",
        "  pause",
        "  exit /b 1",
        ")",
        "echo.",
        "echo Verbinden en herstel starten. Beantwoord vragen in dit venster.",
        "echo.",
        'ssh -t pi@' + PI_IP + ' "sudo bash /tmp/herstel_backup_hdd.sh; rm -f /tmp/herstel_backup_hdd.sh"',
        "echo.",
        "echo === Klaar. Dit venster mag gesloten worden. ===",
        "pause",
    ]
    with open(bat, "w", newline="") as f:
        f.write("\r\n".join(regels) + "\r\n")
    subprocess.Popen('start cmd /k "' + bat + '"', shell=True)


HELP_HOOFDSTUKKEN = [
    ("Synchronisatie",
     "Kopieert je bestanden (documenten, foto's, enzovoort) van deze pc naar "
     "de NAS - je dagelijkse, gewone backup. Opent PiNAS Sync, een apart "
     "programma. Gebruik dit regelmatig, dit is de backup die je het vaakst "
     "nodig hebt."),
    ("PC Image Backup",
     "Maakt een VOLLEDIGE kopie van de Windows-schijf (C:) van DEZE pc, met "
     "wbAdmin (een ingebouwd Windows-onderdeel). Dit is geen bestanden-backup "
     "maar een systeemkopie: als deze pc's schijf crasht, kun je Windows "
     "inclusief alle programma's en instellingen in een keer terugzetten. "
     "Duurt langer dan een gewone synchronisatie en gebruik je minder vaak "
     "(bijv. maandelijks of na een grote Windows-update)."),
    ("iPhone Back-up",
     "BELANGRIJK: hang de iPhone aan een usb-poort VAN DE PI, niet aan deze "
     "Windows-pc - dit draait op de Pi zelf en heeft daar rechtstreeks "
     "usb-toegang voor nodig. Kopieert foto's/video's en bestanden van apps "
     "met bestandsdeling altijd; WhatsApp-chats als 'best effort' extra "
     "stap (kan mislukken zonder de rest van de back-up te breken). "
     "Notities worden bewust NIET meegenomen - die zitten standaard in "
     "iCloud, niet leesbaar te krijgen via deze weg. Komt op de backup-HDD "
     f"te staan in 'PiNAS iPhone Backup\\iPhone_<datum>'. Eerste keer: "
     "ontgrendel de iPhone en tik op 'Vertrouw deze computer' zodra dat "
     "gevraagd wordt."),
    ("iPhone Doorbladeren",
     "BELANGRIJK: hang de iPhone aan een usb-poort VAN DE PI, niet aan deze "
     "Windows-pc. Maakt de iPhone tijdelijk en ALLEEN-LEZEN zichtbaar - "
     "camerarol en 'Op mijn iPhone' - en koppelt hem automatisch aan een "
     "vrije schijfletter (net als Opslag/Backup), die vanzelf in Verkenner "
     "opent zodra hij actief is. Geen back-up, puur om te bekijken wat er "
     "op het toestel staat. Druk in het venster op ENTER om te stoppen; "
     "dan verdwijnt zowel de schijfletter als de share weer, en wordt "
     "alles netjes losgekoppeld."),
    ("Archief Backup Bewaking",
     "Controleert de Archief Backup (op de Backup-schijf) en maakt daar een "
     f"extra, veilige Spiegel Backup van op een tweede schijf ({_spiegel_letter()}:). Dit is dus "
     "een backup VAN de backup - voor het geval de Backup-schijf zelf een "
     "keer stuk gaat, heb je nog een kopie op een andere schijf."),
    ("Systeem-image maken (SD-kaart)",
     "Maakt een volledige, gecomprimeerde kopie van de SD-kaart van de "
     "Raspberry Pi zelf (niet van deze Windows-pc!). Dat is dus een backup "
     "van de hele Pi: het besturingssysteem EN alles wat er op geinstalleerd "
     "is (Nextcloud, Pi-hole, ZeroTier, Vaultwarden, enzovoort) - de complete "
     "Pi in een keer. Als de SD-kaart van de Pi kapot gaat, kun je hiermee de "
     "Pi helemaal opnieuw opzetten zonder alles handmatig te herinstalleren. "
     "Komt op de backup-HDD te staan in de map 'PiNAS Images'. Draait op de "
     "achtergrond terwijl de Pi doorwerkt, maar kan tientallen minuten duren. "
     "Terugzetten gaat niet met een knop in dit scherm - zie de handleiding "
     "hoofdstuk 3.7 (Win32DiskImager of dd vanaf een andere pc/Linux)."),
    ("Backup-HDD controleren/herstellen",
     f"Draait een bestandssysteem-controle (e2fsck) op de backup-HDD ({_backup_letter()}:) "
     "zelf - dus niet op de inhoud, maar op de schijf als geheel. Gebruik dit "
     "als de backup-HDD raar doet (fouten geeft, niet meer bereikbaar is, "
     "traag is) om te checken of de schijf zelf technisch in orde is."),
]


def _bouw_item(win, titel, subtekst, actie, stijl, status):
    sectie = maak_sectie(win)
    achtergrond = sectie.cget("bg")

    rij = tk.Frame(sectie, bg=achtergrond)
    rij.pack(fill="x")

    tekst_kolom = tk.Frame(rij, bg=achtergrond)
    tekst_kolom.pack(side="left", fill="x", expand=True)
    tk.Label(tekst_kolom, text=titel, font=("Segoe UI", 10, "bold"),
              bg=achtergrond, fg=FG, anchor="w").pack(fill="x")
    tk.Label(tekst_kolom, text=subtekst, font=("Segoe UI", 8),
              bg=achtergrond, fg=DIM, anchor="w").pack(fill="x")

    knop_kolom = tk.Frame(rij, bg=achtergrond)
    knop_kolom.pack(side="right")

    if status:
        maak_status_label(knop_kolom, status=status).pack(side="left", padx=(0, 12))

    maak_knop(knop_kolom, "Openen", actie, stijl=stijl, kleur=ACCENT_PIBACKUP)


def start():
    win = tk.Tk()
    win.title("PiNAS - Backup Beheer (bijgewerkt: " + BIJGEWERKT + ")")
    win.configure(bg=BG)
    win.resizable(True, True)
    win.geometry("640x620")
    win.minsize(600, 560)

    maak_header(win, "Backup Beheer",
                help_hoofdstukken=HELP_HOOFDSTUKKEN, kleur=ACCENT_PIBACKUP)

    _bouw_item(win, "Synchronisatie", "Bestanden kopieren naar de NAS",
               _open_sync, "primair", None)
    _bouw_item(win, "PC Image Backup", "Volledige kopie van C: (wbAdmin)",
               _open_image_backup, "primair", None)
    _bouw_item(win, "iPhone Back-up", "Foto's, bestanden en WhatsApp (iPhone MOET aan de Pi hangen)",
               _open_iphone_backup, "primair", None)
    _bouw_item(win, "iPhone Doorbladeren", "Live, alleen-lezen in Verkenner - geen back-up (iPhone MOET aan de Pi hangen)",
               _open_iphone_verkennen, "primair", None)
    _bouw_item(win, "Archief Backup Bewaking", f"Controle en veilige Spiegel Backup {_backup_letter()} naar H",
               _open_archief_bewaking, "primair", "ok")
    _bouw_item(win, "Systeem-image maken (SD-kaart)", "Volledige Pi SD-kaart backuppen",
               _maak_systeem_image, "destructief", None)
    _bouw_item(win, "Backup-HDD controleren/herstellen", f"e2fsck op de backup-HDD ({_backup_letter()}:)",
               _herstel_backup_hdd, "destructief", None)

    legenda_frame = tk.Frame(win, bg=BG)
    legenda_frame.pack(fill="x", padx=16, pady=(8, 14))
    maak_status_legenda(legenda_frame).pack(anchor="w")

    win.mainloop()


if __name__ == "__main__":
    start()
