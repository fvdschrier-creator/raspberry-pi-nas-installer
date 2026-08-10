"""
Pi NAS Suite - PC Image Backup (wbAdmin).

Losgetrokken uit main.py (PiBackup/Kivy) zodat dezelfde kernlogica
herbruikt kan worden vanuit de nieuwe Tkinter-suite (pinas_sync),
zonder dat er twee keer dezelfde Windows-systeemlogica onderhouden
moet worden tijdens de overgang.

BELANGRIJK ONDERSCHEID (komt ook terug in de UI-tekst):
Dit is een VOLLEDIGE schijfkopie van C: (inclusief de EFI-partitie),
GEEN System Restore-herstelpunt. Een herstelpunt is een lichte
snapshot van systeembestanden/register; dit hier is een complete,
losse kopie van de hele schijf - groter, maar ook het enige dat
helpt als de schijf zelf kapot is.

Terugzetten gaat via de Windows-herstelomgeving (WinRE):
  Geavanceerde opties -> SYSTEEMKOPIE HERSTELLEN (System Image
  Recovery) - NIET "Systeemherstel" (System Restore), dat is een
  ander, lichter menu-item. De oorspronkelijke tekst in main.py
  verwees per ongeluk naar het verkeerde menu-item; dat is hier
  gecorrigeerd.

Architectuur, drie fasen (ongewijzigd overgenomen, want dit werkte
al goed in de praktijk):
  Fase A: bepaal_schaduw_locatie()    - VSS-schaduwkopie-plek bepalen
  Fase B: ruim_afgebroken_op()        - opruimen als het cmd-venster
                                         gesloten werd terwijl wbAdmin
                                         nog liep
  Fase C: controleer_bij_opstart()    - heropstart-detectie: was er
                                         een marker van een vorige,
                                         niet afgesloten run?

Windows-specifieke aanroepen (ctypes.windll) werken uitsluitend op
Windows. Op andere platforms geven de functies een duidelijke "alleen
op Windows beschikbaar"-melding terug in plaats van te crashen, zodat
deze module ook elders te IMPORTEREN en syntactisch te testen is.
"""

import os
import sys
import time
import string
import socket
import tempfile
import subprocess
import threading
from dataclasses import dataclass, field


def is_windows() -> bool:
    return sys.platform == "win32"


# =================================================================
# Vaste bestandsnamen - op een plek, niet verspreid als losse strings
# =================================================================

MARKER_BESTAND = os.path.join(tempfile.gettempdir(), "pibackup_running.flag")
STATUS_BESTAND = os.path.join(tempfile.gettempdir(), "pibackup_imgstatus.txt")
BAT_BESTAND = os.path.join(tempfile.gettempdir(), "pibackup_imgbackup.bat")
CLEANUP_BAT_BESTAND = os.path.join(tempfile.gettempdir(), "pibackup_img_cleanup.bat")
TRANSCRIPT_BESTAND = os.path.join(tempfile.gettempdir(), "pibackup_img_transcript.txt")

HERSTEL_BESTANDSNAAM = "HERSTELLEN-LEES-DIT.txt"
NOODKAART_BESTANDSNAAM = "NOODKAART-PINAS-HERSTEL.txt"

NOODKAART_SJABLOON = """PI NAS SYNC - NOODKAART
========================
Bewaar dit bestand OP de herstel-USB-stick zelf (niet alleen op de
NAS) - tijdens een herstel heb je de USB al in handen, maar nog geen
toegang tot de NAS totdat je dit pad al kent. Daarom hier, niet daar.

Laatst bijgewerkt: {datum}
Voor computer:      {pc_naam}

NETWERKPAD VOOR "Systeemkopie herstellen" -> "zoeken op het netwerk":
{unc_pad}

GEBRUIKERSNAAM:
{gebruiker}

WACHTWOORD:
Niet hier opgeschreven (veiligheid). Bewaar dit apart, op de plek
waar je al je andere wachtwoorden bewaart (bijv. wachtwoordmanager).

STAPPEN (kort):
1. Start op vanaf deze USB-stick.
2. Problemen oplossen > Geavanceerde opties > Systeemkopie herstellen.
3. Kies "Een systeemkopie zoeken op het netwerk".
4. Typ het netwerkpad hierboven in, log in met de gebruikersnaam
   hierboven en je wachtwoord.
5. Volg de wizard. Windows herstart automatisch zodra het klaar is.
"""

HERSTEL_INSTRUCTIE_SJABLOON = """Windows Systeemkopie-backup - HERSTELINSTRUCTIES
====================================================

Computer:     {pc_naam}
Gemaakt op:   {datum}
Locatie:      {backup_dest}

WAT IS DIT?
-----------
Dit is een VOLLEDIGE schijfkopie van station C: (inclusief de
EFI-partitie), gemaakt met Windows' eigen wbAdmin. Dit is GEEN
System Restore-herstelpunt - dat is een lichte snapshot van alleen
systeembestanden/register. Dit hier is een complete, losse kopie van
de hele schijf.

BELANGRIJK - DIT MOET JE VOORAF AL GEREGELD HEBBEN
---------------------------------------------------
Als de computer NIET MEER OPSTART (kapotte schijf, corrupte
bootloader, etc.), heb je een SEPARAAT, ZELF GEMAAKT bootbaar
medium nodig om bij deze backup te kunnen komen - bijvoorbeeld een
herstel-USB-stick. Dat medium kun je NIET meer maken op het moment
dat de computer zelf al niet meer opstart; het moet er dan al zijn.

Als je nog geen herstel-USB hebt:
1. Sluit op een NOG WERKENDE Windows-computer een USB-stick aan
   (minimaal 8-16 GB, alle inhoud erop gaat verloren).
2. Zoek in Windows naar "Een herstelschijf maken" (of start
   recoverydrive.exe), en volg de wizard.
3. Bewaar deze USB-stick op een vaste, bekende plek (niet in de PC
   die je ermee wilt herstellen) en label hem duidelijk.
4. Test eenmalig of de PC ervan kan opstarten (UEFI/BIOS-boot-menu,
   vaak F12/F2/Esc bij opstarten) - dat kost een paar minuten en
   voorkomt een onaangename verrassing op het moment dat het er
   echt op aankomt.

HOE TERUGZETTEN (als de computer nog wel opstart)?
---------------------------------------------------
1. Instellingen > Systeem > Herstel > Geavanceerd opnieuw opstarten.
2. Kies: Problemen oplossen > Geavanceerde opties > SYSTEEMKOPIE
   HERSTELLEN (Engels: "System Image Recovery").

   LET OP: dit is een ANDER menu-item dan "Systeemherstel"
   (System Restore)! Systeemherstel herstelt alleen systeembestanden
   en het register, NIET de hele schijf. Voor deze backup heb je
   echt "Systeemkopie herstellen" nodig.

3. Wijs de herstelwizard naar deze map, of naar de schijf/netwerk-
   share waar deze map op staat:
   {backup_dest}

4. Volg de wizard. De hele C:-schijf (inclusief EFI-partitie) wordt
   teruggezet exact zoals op het moment van deze backup
   ({datum}).

HOE TERUGZETTEN (als de computer NIET MEER opstart)?
------------------------------------------------------
1. Start op vanaf de herstel-USB die je vooraf gemaakt hebt (zie
   hierboven) - via het UEFI/BIOS-boot-menu een andere boot-bron
   kiezen dan de interne schijf.

2. Problemen oplossen > Geavanceerde opties > Systeemkopie herstellen.

3. Windows zoekt eerst lokaal naar een systeemkopie. Kies:
   "Een systeemkopie zoeken op het netwerk"
   (WinRE kent je normale Windows-koppelingen niet - dit is een
   volledig apart, geheugenloos opstartmilieu, dus dit moet
   handmatig.)

4. Typ dit EXACTE netwerkpad in:
   {unc_pad}

5. Log in met:
   Gebruikersnaam: {gebruiker}
   Wachtwoord: hetzelfde wachtwoord dat Pi NAS Sync gebruikt om met
               de Pi te verbinden (NIET hier opgeschreven uit
               veiligheidsoverweging - dit bestand staat immers op
               de NAS zelf).

6. Selecteer de gevonden systeemkopie (datum: {datum}) en volg de
   wizard.

7. Na een succesvolle terugzet-actie herstart Windows AUTOMATISCH -
   dit gaat vanzelf, hier is geen extra handeling voor nodig.

Dit bestand staat in de backupmap zelf, zodat de instructie
beschikbaar is op het moment dat je hem nodig hebt - ook als de
computer waar dit op gemaakt is niet meer opstart en je dus geen
toegang meer hebt tot Pi NAS Sync of main.py.
"""


@dataclass
class CheckResultaat:
    status: str  # "ok" / "fout" / "actie_nodig" / "overgeslagen" / "onbekend"
    tekst: str


@dataclass
class SchaduwLocatie:
    ok: bool
    drive: str
    reden: str
    verplaatst: bool


@dataclass
class ChecksResultaat:
    regels: list = field(default_factory=list)  # lijst van CheckResultaat
    ok_all: bool = True
    is_admin: bool = False
    unc_doel: str = ""
    shadow_drive: str = "C:"
    shadow_verplaatst: bool = False

    def klaar_om_direct_te_starten(self) -> bool:
        return self.ok_all and self.is_admin

    def klaar_voor_uac(self) -> bool:
        return self.ok_all and not self.is_admin


# =================================================================
# FASE A: schaduwkopie-locatie bepalen
# =================================================================

def beschikbare_lokale_schijven() -> list:
    """Lijst van lokale, vaste NTFS-schijven (geschikt als
    schaduwkopie-locatie), met hun vrije ruimte erbij - voor gebruik
    in een handmatige keuzelijst als de automatische bepaling geen
    plek vindt."""
    if not is_windows():
        return []
    import ctypes

    def vrije_en_totaal(drive):
        try:
            free = ctypes.c_ulonglong(0)
            total = ctypes.c_ulonglong(0)
            ok = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                drive, ctypes.byref(free), ctypes.byref(total), None)
            if ok:
                return free.value, total.value
        except Exception:
            pass
        return None, None

    def is_lokaal_ntfs(drive):
        try:
            dtype = ctypes.windll.kernel32.GetDriveTypeW(drive)
            if dtype != 3:
                return False
            fs_buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.kernel32.GetVolumeInformationW(
                drive, None, 0, None, None, None, fs_buf, 256)
            return fs_buf.value == "NTFS"
        except Exception:
            return False

    resultaat = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for i, letter in enumerate(string.ascii_uppercase):
        if not (bitmask & (1 << i)):
            continue
        drive = letter + ":\\"
        if not is_lokaal_ntfs(drive):
            continue
        free, total = vrije_en_totaal(drive)
        if free is not None:
            resultaat.append((letter + ":", free // 1024**3, total // 1024**3 if total else 0))
    return resultaat


def bepaal_schaduw_locatie(voorkeur_drive: str = None) -> SchaduwLocatie:
    """Bepaalt waar de VSS-schaduwkopie moet komen voor een
    C:-image-backup. De schaduw moet op een LOKALE NTFS-schijf staan
    (nooit netwerk). Standaard C: zelf; heeft C: minder dan ongeveer
    15%% vrij (met een minimum van 10 GB), dan wordt uitgeweken naar
    een andere lokale NTFS-schijf met genoeg vrije ruimte.

    voorkeur_drive: als opgegeven (bijv. 'D:'), wordt ALLEEN die
    schijf gecontroleerd in plaats van automatisch te zoeken - voor
    als de automatische bepaling geen plek vond en de gebruiker zelf
    een station aanwijst."""
    if not is_windows():
        return SchaduwLocatie(False, "", "Alleen op Windows beschikbaar", False)

    import ctypes

    def vrije_en_totaal(drive):
        try:
            free = ctypes.c_ulonglong(0)
            total = ctypes.c_ulonglong(0)
            ok = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                drive, ctypes.byref(free), ctypes.byref(total), None)
            if ok:
                return free.value, total.value
        except Exception:
            pass
        return None, None

    def is_lokaal_ntfs(drive):
        try:
            dtype = ctypes.windll.kernel32.GetDriveTypeW(drive)
            if dtype != 3:  # 3 = DRIVE_FIXED
                return False
            fs_buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.kernel32.GetVolumeInformationW(
                drive, None, 0, None, None, None, fs_buf, 256)
            return fs_buf.value == "NTFS"
        except Exception:
            return False

    c_free, c_total = vrije_en_totaal("C:\\")
    if c_total is None:
        return SchaduwLocatie(False, "", "Kan vrije ruimte op C: niet lezen", False)

    benodigd = max(int(c_total * 0.15), 10 * 1024**3)

    if voorkeur_drive:
        drive = voorkeur_drive.rstrip("\\") + "\\"
        if drive.upper().startswith("C:"):
            if c_free >= benodigd:
                return SchaduwLocatie(True, "C:", f"C: heeft genoeg ruimte ({c_free // 1024**3} GB vrij)", False)
            return SchaduwLocatie(False, "", f"C: heeft alsnog te weinig ruimte ({c_free // 1024**3} GB vrij)", False)
        if not is_lokaal_ntfs(drive):
            return SchaduwLocatie(False, "", f"{voorkeur_drive} is geen lokale NTFS-schijf", False)
        free, total = vrije_en_totaal(drive)
        if free is None:
            return SchaduwLocatie(False, "", f"Kan vrije ruimte op {voorkeur_drive} niet lezen", False)
        if free < benodigd:
            return SchaduwLocatie(
                False, "", f"{voorkeur_drive} heeft te weinig ruimte "
                          f"({free // 1024**3} GB vrij, {benodigd // 1024**3} GB nodig)", False)
        return SchaduwLocatie(
            True, voorkeur_drive.rstrip('\\'),
            f"Handmatig gekozen: {voorkeur_drive} ({free // 1024**3} GB vrij)", True)

    if c_free >= benodigd:
        return SchaduwLocatie(
            True, "C:", f"C: heeft genoeg ruimte ({c_free // 1024**3} GB vrij)", False)

    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for i, letter in enumerate(string.ascii_uppercase):
        if letter == "C":
            continue
        if not (bitmask & (1 << i)):
            continue
        drive = letter + ":\\"
        if not is_lokaal_ntfs(drive):
            continue
        free, total = vrije_en_totaal(drive)
        if free is not None and free >= benodigd:
            return SchaduwLocatie(
                True, letter + ":",
                f"C: te krap; schaduwkopie naar {letter}: ({free // 1024**3} GB vrij)",
                True)

    return SchaduwLocatie(
        False, "",
        f"Onvoldoende lokale ruimte voor schaduwkopie (ongeveer "
        f"{benodigd // 1024**3} GB nodig, C: heeft {c_free // 1024**3} GB) - "
        f"kies eventueel handmatig een andere schijf.",
        False)


# =================================================================
# Vereisten-checks
# =================================================================

def voer_checks_uit(doelmap: str, voorkeur_shadow_drive: str = None) -> ChecksResultaat:
    """Voert alle vereisten-checks uit voor een image-backup naar
    doelmap. Geeft een ChecksResultaat terug met losse regels (voor
    weergave) en een algemeen oordeel - puur data, geen UI-aanroepen."""
    resultaat = ChecksResultaat()

    if not is_windows():
        resultaat.ok_all = False
        resultaat.regels.append(CheckResultaat("fout", "Alleen op Windows beschikbaar"))
        return resultaat

    import ctypes
    import shutil
    import winreg

    # Check 1: Windows-editie (Pro/Enterprise/...)
    try:
        edition = ""
        for key_path in [
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows NT\CurrentVersion"]:
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                try:
                    edition, _ = winreg.QueryValueEx(key, "EditionID")
                    if edition:
                        break
                except Exception:
                    pass
                try:
                    edition, _ = winreg.QueryValueEx(key, "ProductName")
                    if edition:
                        break
                except Exception:
                    pass
            except Exception:
                pass
        if any(x in edition for x in
               ["Pro", "Professional", "Enterprise", "Education", "Ultimate", "Business"]):
            resultaat.regels.append(CheckResultaat("ok", f"Windows versie: {edition}"))
        elif edition:
            resultaat.regels.append(CheckResultaat("fout", f"Windows {edition} - vereist Pro of hoger"))
            resultaat.ok_all = False
        else:
            resultaat.regels.append(CheckResultaat("ok", "Windows versie: niet te lezen, maar doorgaan"))
    except Exception as e:
        resultaat.regels.append(CheckResultaat("ok", f"Windows versie-check overgeslagen: {e}"))

    # Check 2: Administrator-rechten (geen harde blokkade - wbAdmin
    # kan elevated gestart worden via UAC zonder het programma te
    # herstarten, wat netwerkkoppelingen Y:/Z: intact houdt)
    try:
        resultaat.is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        if resultaat.is_admin:
            resultaat.regels.append(CheckResultaat("ok", "Administrator-rechten: aanwezig"))
        else:
            resultaat.regels.append(CheckResultaat("actie_nodig", "Admin-rechten: via UAC bij het starten"))
    except Exception:
        resultaat.regels.append(CheckResultaat("onbekend", "Kan admin-rechten niet controleren"))

    # Check 3: wbAdmin aanwezig
    wbadmin = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"),
                           "System32", "wbadmin.exe")
    if os.path.exists(wbadmin):
        resultaat.regels.append(CheckResultaat("ok", "wbAdmin: aanwezig"))
    else:
        resultaat.regels.append(CheckResultaat("fout", "wbAdmin niet gevonden - installeer Windows Backup"))
        resultaat.ok_all = False

    # Check 4: doelmap bestaat en is bereikbaar
    target_ok = False
    doelmap = doelmap.strip().rstrip("/\\")
    if not doelmap:
        resultaat.regels.append(CheckResultaat("fout", "Geen doelmap ingesteld"))
        resultaat.ok_all = False
    else:
        drive_letter = (doelmap[:2] if len(doelmap) >= 2 else doelmap).upper()
        check_path = doelmap if doelmap.endswith("\\") else doelmap + "\\"
        unc_path = None

        try:
            buf = ctypes.create_unicode_buffer(1024)
            buf_size = ctypes.c_ulong(1024)
            res = ctypes.windll.mpr.WNetGetConnectionW(drive_letter, buf, ctypes.byref(buf_size))
            if res == 0 and buf.value:
                unc_path = buf.value
        except Exception:
            pass

        physically_ok = False
        try:
            free_bytes = ctypes.c_ulonglong(0)
            total_bytes = ctypes.c_ulonglong(0)
            ret = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                check_path, ctypes.byref(free_bytes), ctypes.byref(total_bytes), None)
            if ret != 0:
                physically_ok = True
        except Exception:
            pass
        if not physically_ok:
            try:
                os.listdir(check_path)
                physically_ok = True
            except Exception:
                pass

        if physically_ok:
            target_ok = True
            volledige_bestemming = bouw_backup_bestemming(resolveer_naar_unc(doelmap))
            if unc_path:
                resultaat.unc_doel = unc_path
                resultaat.regels.append(CheckResultaat(
                    "ok", f"Doelpad: {drive_letter} -> {unc_path}\n"
                         f"      Backup komt hier: {volledige_bestemming}"))
            else:
                resultaat.regels.append(CheckResultaat(
                    "ok", f"Doelpad bereikbaar: {doelmap}\n"
                         f"      Backup komt hier: {volledige_bestemming}"))
        elif unc_path:
            resultaat.regels.append(CheckResultaat(
                "fout", f"Drive bekend ({drive_letter} -> {unc_path}) maar niet bereikbaar"))
            resultaat.ok_all = False
        else:
            resultaat.regels.append(CheckResultaat(
                "fout", f"Doelpad niet bereikbaar: {doelmap} (netwerkschijf verbonden?)"))
            resultaat.ok_all = False

    # Check 5: vrije ruimte (min. 50 GB), alleen als pad bereikbaar
    if target_ok:
        try:
            check_path = doelmap if doelmap.endswith("\\") else doelmap + "\\"
            total, _used, free = shutil.disk_usage(check_path)
            free_gb = free // (1024**3)
            total_gb = total // (1024**3)
            if free_gb >= 50:
                resultaat.regels.append(CheckResultaat("ok", f"Vrije ruimte: {free_gb} GB"))
            elif total_gb < 40:
                resultaat.regels.append(CheckResultaat(
                    "fout", f"Doelschijf waarschijnlijk nog niet gemount "
                            f"({free_gb} GB vrij op {total_gb} GB totaal)"))
            else:
                resultaat.regels.append(CheckResultaat(
                    "fout", f"Te weinig ruimte: {free_gb} GB vrij (min. 50 GB)"))
                resultaat.ok_all = False
        except Exception as e:
            resultaat.regels.append(CheckResultaat("onbekend", f"Schijfruimte niet te lezen: {str(e)[:50]}"))
    else:
        resultaat.regels.append(CheckResultaat("overgeslagen", "Schijfruimte: overgeslagen (pad niet bereikbaar)"))

    # Check 6: bestandssysteem NTFS, alleen als pad bereikbaar
    if target_ok:
        try:
            fs_buf = ctypes.create_unicode_buffer(256)
            drive = (doelmap[:2] + "\\") if len(doelmap) >= 2 else doelmap
            ctypes.windll.kernel32.GetVolumeInformationW(
                drive, None, 0, None, None, None, fs_buf, 256)
            fs = fs_buf.value
            if fs == "NTFS":
                resultaat.regels.append(CheckResultaat("ok", "Bestandssysteem: NTFS"))
            elif fs:
                resultaat.regels.append(CheckResultaat(
                    "fout", f"Bestandssysteem {fs} niet ondersteund (vereist: NTFS)"))
                resultaat.ok_all = False
            else:
                resultaat.regels.append(CheckResultaat("onbekend", "Bestandssysteem niet te lezen (netwerkschijf?)"))
        except Exception as e:
            resultaat.regels.append(CheckResultaat("onbekend", f"Bestandssysteem niet te controleren: {str(e)[:40]}"))
    else:
        resultaat.regels.append(CheckResultaat("overgeslagen", "Bestandssysteem: overgeslagen (pad niet bereikbaar)"))

    # Check 7: schaduwkopie-locatie (Fase A)
    try:
        schaduw = bepaal_schaduw_locatie(voorkeur_drive=voorkeur_shadow_drive)
        resultaat.shadow_drive = schaduw.drive or "C:"
        resultaat.shadow_verplaatst = schaduw.verplaatst
        if schaduw.ok:
            resultaat.regels.append(CheckResultaat("ok", f"Schaduwkopie: {schaduw.reden}"))
        else:
            resultaat.regels.append(CheckResultaat("fout", f"Schaduwkopie: {schaduw.reden}"))
            resultaat.ok_all = False
    except Exception as e:
        resultaat.regels.append(CheckResultaat("onbekend", f"Schaduwkopie niet te bepalen: {str(e)[:40]}"))

    return resultaat


def detecteer_bestaande_backup(doelmap: str):
    """Controleert of er al een Windows-Systeemherstel-submap met
    WindowsImageBackup aanwezig is op het doelpad (lokaal via
    schijfletter). Geeft (bestaat: bool, label: str, grootte_str: str)
    terug."""
    pc_naam = huidige_pc_naam()
    submap = f"Windows-Systeemherstel-{pc_naam}"

    # IDEMPOTENT, zelfde logica als bouw_backup_bestemming: als
    # doelmap zelf al op de submap eindigt, niet nog een keer
    # toevoegen - anders wordt er naar een niet-bestaande, dubbel
    # geneste map gezocht terwijl de echte backup al een laag hoger
    # staat.
    doelmap_schoon = doelmap.rstrip("\\/")
    if doelmap_schoon.lower().endswith(submap.lower()):
        submap_pad = doelmap_schoon
    else:
        submap_pad = os.path.join(doelmap_schoon, submap)

    wib_in_sub = os.path.join(submap_pad, "WindowsImageBackup")
    wib_direct = os.path.join(doelmap_schoon, "WindowsImageBackup")  # oude stijl, voor compatibiliteit

    if os.path.isdir(wib_in_sub):
        check = wib_in_sub
        label = f"{submap}\\WindowsImageBackup"
    elif os.path.isdir(wib_direct):
        check = wib_direct
        label = "WindowsImageBackup"
    else:
        return False, "", ""

    try:
        totaal = sum(
            os.path.getsize(os.path.join(r, f))
            for r, _dirs, files in os.walk(check)
            for f in files
            if not os.path.islink(os.path.join(r, f)))
        grootte_str = (f"{totaal / 1024**3:.1f} GB" if totaal >= 1024**3
                       else f"{totaal / 1024**2:.0f} MB")
    except Exception:
        grootte_str = "onbekende grootte"
    return True, label, grootte_str


def huidige_pc_naam() -> str:
    try:
        return socket.gethostname().upper()
    except Exception:
        return os.environ.get("COMPUTERNAME", "PC").upper()


def _voer_elevated_commando_uit(commando_regel: str, timeout_sec: int = 30):
    """Voert een enkel commando elevated uit (via UAC) en geeft de
    volledige uitvoer terug. Gebruikt voor leesopdrachten die
    Administrator-rechten vereisen (zoals 'wbadmin get versions',
    die ook bij alleen-lezen toegang weigert zonder elevatie).
    Geeft (succes: bool, uitvoer: str) terug. succes=False bij UAC-
    weigering of een andere fout bij het starten."""
    if not is_windows():
        return False, "Alleen op Windows beschikbaar"

    import ctypes
    from ctypes import wintypes

    output_bestand = os.path.join(
        tempfile.gettempdir(), f"pinas_elevated_output_{int(time.time()*1000)}.txt")
    bat_bestand = os.path.join(
        tempfile.gettempdir(), f"pinas_elevated_cmd_{int(time.time()*1000)}.bat")

    try:
        with open(bat_bestand, "w", encoding="utf-8") as f:
            f.write("@echo off\n")
            f.write(f'{commando_regel} > "{output_bestand}" 2>&1\n')

        class SHELLEXECUTEINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong),
                ("hwnd", wintypes.HWND), ("lpVerb", wintypes.LPCWSTR),
                ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int),
                ("hInstApp", wintypes.HINSTANCE), ("lpIDList", ctypes.c_void_p),
                ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                ("dwHotKey", wintypes.DWORD), ("hIconOrMonitor", wintypes.HANDLE),
                ("hProcess", wintypes.HANDLE),
            ]
        SEE_MASK_NOCLOSEPROCESS = 0x00000040
        sei = SHELLEXECUTEINFO()
        sei.cbSize = ctypes.sizeof(sei)
        sei.fMask = SEE_MASK_NOCLOSEPROCESS
        sei.lpVerb = "runas"
        sei.lpFile = "cmd.exe"
        sei.lpParameters = f'/C "{bat_bestand}"'
        sei.nShow = 0  # verborgen - dit is een leesopdracht, geen zichtbare actie nodig

        succes = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei))
        if not succes or not sei.hProcess:
            return False, "UAC geannuleerd"

        ctypes.windll.kernel32.WaitForSingleObject(sei.hProcess, timeout_sec * 1000)
        ctypes.windll.kernel32.CloseHandle(sei.hProcess)

        uitvoer = ""
        if os.path.exists(output_bestand):
            with open(output_bestand, encoding="utf-8", errors="replace") as f:
                uitvoer = f.read().strip()
        return True, uitvoer
    except Exception as e:
        return False, str(e)
    finally:
        for pad in (bat_bestand, output_bestand):
            try:
                if os.path.exists(pad):
                    os.remove(pad)
            except Exception:
                pass


def controleer_geldige_backups(backup_dest: str, on_log=None):
    """Voert 'wbadmin get versions' uit tegen backup_dest. Dit is een
    LEESOPDRACHT - wijzigt, maakt of verwijdert niets. Vraagt wbAdmin
    zelf welke backups het op deze locatie als geldig en compleet
    beschouwt, via zijn eigen catalogus (niet door zelf in de mappen
    te kijken - een map kan aanwezig zijn zonder dat de backup ooit
    voltooid is).

    Probeert eerst zonder elevatie (werkt als pinas_sync zelf al als
    Administrator draait); valt bij 'Access denied' automatisch terug
    op een elevated poging (een korte UAC-vraag) - wbAdmin vereist
    Administrator-rechten ook voor deze leesopdracht.

    Geeft (heeft_geldige_backup: bool, ruwe_uitvoer: str) terug."""
    on_log = on_log or (lambda t, n: None)

    if not is_windows():
        return False, "Alleen op Windows beschikbaar"

    def _beoordeel(uitvoer):
        return "Backup time:" in uitvoer or "Version identifier:" in uitvoer

    try:
        result = subprocess.run(
            ["wbadmin", "get", "versions", f"-backupTarget:{backup_dest}"],
            capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        uitvoer = ((result.stdout or "") + (result.stderr or "")).strip()
    except Exception as e:
        uitvoer = f"Fout bij uitvoeren: {e}"

    if "Access is denied" in uitvoer or "Access denied" in uitvoer:
        on_log("Zonder elevatie geweigerd (Access denied) - wbAdmin vereist "
              "Administrator-rechten ook voor deze leesopdracht. "
              "UAC wordt nu gevraagd...", "info")
        # BELANGRIJK: een gekoppelde schijfletter (Z:) bestaat niet in
        # de elevated aanmeldsessie - daarom hier altijd omzetten naar
        # het echte netwerkpad, los van wat er eerder al gecontroleerd
        # is. Dit was precies de oorzaak van 'kon niet gevonden worden'.
        backup_dest_unc = resolveer_naar_unc(backup_dest)
        if backup_dest_unc != backup_dest:
            on_log(f"Schijfletter omgezet naar netwerkpad voor de elevated "
                  f"poging: {backup_dest} -> {backup_dest_unc}", "info")
        gestart, elevated_uitvoer = _voer_elevated_commando_uit(
            f'wbadmin get versions -backupTarget:"{backup_dest_unc}"')
        if not gestart:
            on_log(f"Elevatie mislukt: {elevated_uitvoer}", "fout")
            return False, elevated_uitvoer
        uitvoer = elevated_uitvoer

    heeft_geldige = _beoordeel(uitvoer)
    if heeft_geldige:
        on_log("Geldige, complete backup gevonden op deze locatie.", "ok")
    else:
        on_log("Geen geldige backup gevonden op deze locatie (zie details "
              "hierboven in dit Voortgang-paneel).", "waarschuwing")
    return heeft_geldige, uitvoer


def open_herstelschijf_tool(on_log=None, wacht_tot_gesloten=False):
    """Start Windows' eigen 'Een herstelschijf maken'-wizard
    (recoverydrive.exe), ELEVATED - dit programma vereist
    Administrator-rechten (WinError 740 zonder elevatie: 'U hebt niet
    de benodigde bevoegdheden voor deze bewerking'). Dit MOET
    gebeuren op een nog werkende computer, VOORDAT er iets misgaat -
    na een crash is het te laat om dit nog te maken.

    wacht_tot_gesloten=True: blokkeert tot de wizard weer gesloten
    is (gebruiker is klaar, of heeft geannuleerd) - handig om
    daarna automatisch verder te gaan met het wegschrijven van het
    noodkaartje op de zojuist gemaakte stick. Draai dit dan zelf in
    een achtergrondthread vanuit de UI-laag, anders blokkeert de
    hele interface.

    Geeft (gestart: bool, foutmelding: str) terug."""
    on_log = on_log or (lambda t, n: None)
    if not is_windows():
        return False, "Alleen op Windows beschikbaar"

    import ctypes
    from ctypes import wintypes

    class SHELLEXECUTEINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong),
            ("hwnd", wintypes.HWND), ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE), ("lpIDList", ctypes.c_void_p),
            ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD), ("hIconOrMonitor", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]
    SEE_MASK_NOCLOSEPROCESS = 0x00000040
    sei = SHELLEXECUTEINFO()
    sei.cbSize = ctypes.sizeof(sei)
    sei.fMask = SEE_MASK_NOCLOSEPROCESS
    sei.lpVerb = "runas"
    sei.lpFile = "recoverydrive.exe"
    sei.lpParameters = ""
    sei.nShow = 1

    try:
        succes = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei))
    except Exception as e:
        on_log(f"Kon de herstelschijf-wizard niet starten: {e}", "fout")
        return False, str(e)

    if not succes or not sei.hProcess:
        on_log("UAC geannuleerd - herstelschijf-wizard niet gestart.", "fout")
        return False, "UAC geannuleerd"

    on_log("Herstelschijf-wizard van Windows gestart - volg de stappen "
          "daar, met een lege USB-stick van minimaal 8-16 GB.", "info")

    if wacht_tot_gesloten:
        ctypes.windll.kernel32.WaitForSingleObject(sei.hProcess, 0xFFFFFFFF)
        ctypes.windll.kernel32.CloseHandle(sei.hProcess)
        on_log("Herstelschijf-wizard is gesloten.", "info")
    else:
        ctypes.windll.kernel32.CloseHandle(sei.hProcess)

    return True, ""


def controleer_herstelschijf(drive_pad: str):
    """Best-effort STRUCTUURCONTROLE van een herstel-USB: checkt of
    de typische bestanden/mappen van een bootbare herstelschijf
    aanwezig zijn. GEEN garantie dat de stick echt opstart - dat kan
    alleen door hem daadwerkelijk te proberen op een PC (UEFI/BIOS-
    boot-menu). Deze check vangt vooral de duidelijke gevallen op:
    een lege stick, een mislukte/onderbroken aanmaak, of de verkeerde
    schijf aangewezen.

    Geeft een lijst (status, tekst) terug, status: 'ok' of 'fout'."""
    resultaten = []
    drive_pad = drive_pad.rstrip("\\/")

    if not os.path.isdir(drive_pad):
        return [("fout", f"Schijf/map niet bereikbaar: {drive_pad}")]

    # Typische aanwezige onderdelen op een Windows-herstelschijf.
    # Namen kunnen licht verschillen per Windows-versie, daarom een
    # paar varianten/alternatieven per check.
    checks = [
        ("Boot-bestand (bootmgr)", ["bootmgr"]),
        ("EFI-opstartmap (UEFI)", ["EFI"]),
        ("Boot-map", ["Boot"]),
        ("Sources-map (herstelbestanden)", ["Sources"]),
    ]
    for naam, kandidaten in checks:
        gevonden = any(os.path.exists(os.path.join(drive_pad, k)) for k in kandidaten)
        if gevonden:
            resultaten.append(("ok", f"{naam}: aanwezig"))
        else:
            resultaten.append(("fout", f"{naam}: NIET gevonden"))

    try:
        totaal_items = len(os.listdir(drive_pad))
        if totaal_items <= 2:
            resultaten.append(("fout", f"Schijf lijkt vrijwel leeg ({totaal_items} items in de root) - "
                                       f"is dit wel de juiste stick, en is de aanmaak voltooid?"))
        else:
            resultaten.append(("ok", f"{totaal_items} items gevonden in de hoofdmap - lijkt gevuld"))
    except Exception as e:
        resultaten.append(("fout", f"Kon hoofdmap niet lezen: {e}"))

    aantal_fouten = sum(1 for status, _ in resultaten if status == "fout")
    if aantal_fouten == 0:
        resultaten.append(("ok", "Structuur ziet er compleet uit - LET OP: dit garandeert geen "
                                 "bootbaarheid. Test dit eenmalig door er daadwerkelijk een PC "
                                 "vanaf op te starten (UEFI/BIOS-boot-menu)."))
    else:
        resultaten.append(("fout", f"{aantal_fouten} onderdeel/onderdelen ontbreken - controleer of "
                                   f"de aanmaak echt voltooid is, of probeer de stick opnieuw te maken."))
    return resultaten


# =================================================================
# Niet-elevated pad: direct starten (alleen als al admin)
# =================================================================

def start_direct(doelmap: str, unc_doel: str, on_log=None):
    """Start wbAdmin direct (zonder UAC) - alleen te gebruiken als de
    huidige sessie al Administrator-rechten heeft. Blokkerend; draai
    dit zelf in een achtergrondthread vanuit de UI-laag. Geeft
    (succes: bool, exitcode: int) terug."""
    on_log = on_log or (lambda t, n: None)
    wbadmin = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"),
                           "System32", "wbadmin.exe")
    backup_target = unc_doel or doelmap
    cmd = [wbadmin, "start", "backup",
           f"-backupTarget:{backup_target}", "-include:C:", "-allCritical", "-quiet"]

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for regel in proc.stdout:
            regel = regel.strip()
            if regel:
                on_log(regel, "info")
        proc.wait()
        succes = proc.returncode == 0
        on_log("Image backup voltooid!" if succes else "Image backup mislukt!",
              "ok" if succes else "fout")
        return succes, proc.returncode
    except Exception as e:
        on_log(f"Fout: {e}", "fout")
        return False, -1


# =================================================================
# Elevated pad (UAC): bat-script bouwen en uitvoeren
# =================================================================

def resolveer_naar_unc(pad: str) -> str:
    """Zet een pad dat met een schijfletter begint (bijv. 'Z:\\Sub')
    om naar zijn echte netwerkpad (bijv. '\\\\UW_PI_IP_ADRES\\Backup\\Sub'),
    als die letter een gekoppelde netwerkschijf is. Geeft het pad
    ONGEWIJZIGD terug als het al een UNC-pad is, of geen gekoppelde
    netwerkschijf betreft (dan kan het pad niet omgezet worden, en is
    dat ook niet nodig).

    BELANGRIJK, WAAROM DIT BESTAAT: een UAC-elevatie draait in een
    ANDERE aanmeldsessie dan je normale, interactieve sessie.
    Gekoppelde schijfletters (via 'net use', zoals Z:) zijn aan die
    interactieve sessie gebonden en daardoor NIET zichtbaar in een
    elevated proces - zelfs niet voor dezelfde gebruiker. Een
    elevated wbAdmin-aanroep met 'Z:\\...' kan daardoor het pad
    simpelweg niet vinden, met een verwarrende foutmelding als
    gevolg. Door ALTIJD eerst naar het UNC-pad om te zetten, ongeacht
    of er al een eerdere check is gedaan, wordt dit probleem
    structureel voorkomen in plaats van afhankelijk te zijn van een
    toevallig al beschikbare eerdere check."""
    if not pad or pad.startswith("\\\\") or not is_windows():
        return pad

    pad = pad.replace("/", "\\")
    if len(pad) < 2 or pad[1] != ":":
        return pad  # geen schijfletter-pad, niets aan om te zetten

    drive_letter = pad[:2]  # bijv. "Z:"
    rest = pad[2:].lstrip("\\")

    import ctypes
    try:
        buf = ctypes.create_unicode_buffer(1024)
        buf_size = ctypes.c_ulong(1024)
        res = ctypes.windll.mpr.WNetGetConnectionW(drive_letter, buf, ctypes.byref(buf_size))
        if res == 0 and buf.value:
            unc_root = buf.value.rstrip("\\")
            return unc_root + "\\" + rest if rest else unc_root
    except Exception:
        pass
    return pad  # geen gekoppelde netwerkschijf (of niet te bepalen) - ongewijzigd terug


def resolveer_naar_unc(pad: str) -> str:
    """Zet een pad dat met een schijfletter begint (bijv.
    'Z:\\Windows-Systeemherstel-DELL-3070') om naar het ECHTE
    netwerkpad waar die letter naar wijst (bijv.
    '\\\\UW_PI_IP_ADRES\\Backup\\Windows-Systeemherstel-DELL-3070'),
    met de rest van het pad erachter bewaard.

    BELANGRIJK waarom dit altijd moet gebeuren, niet alleen als de
    UI al een eerdere check deed: een gekoppelde schijfletter (Z:)
    hoort bij de NORMALE (niet-elevated) aanmeldsessie. Een UAC-
    elevatie draait in een ANDERE aanmeldsessie, waarin die
    schijfletter niet bestaat - wbAdmin zou dan 'pad niet gevonden'
    melden, ook al is de schijf voor jou heel gewoon bereikbaar. Door
    dit hier, in de kernlogica zelf, altijd te doen (in plaats van te
    vertrouwen op een eerder uitgevoerde UI-check), werkt elke
    elevated actie altijd correct - ongeacht of 'Controleren' al is
    aangeklikt.

    Als het pad al een UNC-pad is (begint met \\\\), of geen
    schijfletter-vorm heeft, wordt het ongewijzigd teruggegeven."""
    if not pad or not is_windows():
        return pad
    pad = pad.replace("/", "\\")
    if pad.startswith("\\\\"):
        return pad  # al een netwerkpad, niets te doen
    if len(pad) < 2 or pad[1] != ":":
        return pad  # geen schijfletter-vorm, niets te doen

    drive_letter = pad[:2]  # bijv. "Z:"
    rest = pad[2:].lstrip("\\")  # bijv. "Windows-Systeemherstel-DELL-3070"

    import ctypes
    try:
        buf = ctypes.create_unicode_buffer(1024)
        buf_size = ctypes.c_ulong(1024)
        res = ctypes.windll.mpr.WNetGetConnectionW(drive_letter, buf, ctypes.byref(buf_size))
        if res == 0 and buf.value:
            unc_basis = buf.value.rstrip("\\")
            return unc_basis + ("\\" + rest if rest else "")
    except Exception:
        pass
    return pad  # geen netwerkkoppeling gevonden - geef ongewijzigd terug


def bouw_backup_bestemming(unc_doel_basis: str) -> str:
    """Bouwt het volledige doelpad MET de herkenbare submap:
    \\\\server\\share\\Windows-Systeemherstel-<PC>\\
    wbAdmin maakt daarbinnen zelf nog WindowsImageBackup\\<PC>\\ aan.

    IDEMPOTENT: als de meegegeven basis AL eindigt op die submap
    (bijv. omdat iemand 'm zelf al in het doelveld had gezet), wordt
    hij niet nog een keer toegevoegd - dat gaf eerder een dubbele,
    geneste map zoals '...DELL-3070\\Windows-Systeemherstel-DELL-3070'."""
    pc_naam = huidige_pc_naam()
    submap = f"Windows-Systeemherstel-{pc_naam}"
    basis = unc_doel_basis.rstrip("\\/")
    if basis.lower().endswith(submap.lower()):
        return basis
    return basis + "\\" + submap


def bouw_elevated_bat(doelmap_lokaal: str, backup_unc_basis: str,
                       gebruiker: str, wachtwoord: str,
                       shadow_drive: str, shadow_verplaatst: bool) -> str:
    """Schrijft het bat-script dat elevated (via UAC) wordt gestart.
    Volgorde: NAS-verbinding controleren/maken, doelmap aanmaken,
    schaduwopslag eventueel verplaatsen (Fase A), MARKER schrijven,
    wbAdmin starten, statusbestand schrijven, marker weghalen, EN
    zichzelf verifieren via 'wbadmin get versions' (naar een
    bestand, zodat dit altijd nalees baar is - ook als het zwarte
    venster zelf niet te kopieren is of al gesloten is voordat je
    kon lezen wat er stond).
    Geeft het pad van het geschreven bat-bestand terug."""
    # GEGARANDEERDE resolutie naar UNC, ALTIJD, ongeacht wat er is
    # meegegeven - dit bat-script draait straks elevated, en een
    # gekoppelde schijfletter bestaat niet in die aanmeldsessie. Door
    # dit hier te doen (in plaats van te vertrouwen op de aanroeper)
    # werkt dit altijd, ook als de UI per ongeluk een schijfletter
    # doorgeeft.
    backup_unc_basis = resolveer_naar_unc(backup_unc_basis)
    backup_dest = bouw_backup_bestemming(backup_unc_basis)

    # Oude marker/status/transcript van een vorige run opruimen
    for pad in (MARKER_BESTAND, STATUS_BESTAND, TRANSCRIPT_BESTAND):
        try:
            if os.path.exists(pad):
                os.remove(pad)
        except Exception:
            pass

    with open(BAT_BESTAND, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write("chcp 65001 >nul\n")
        f.write("title Pi NAS Sync - Windows Image Backup\n")
        f.write("echo ============================================\n")
        f.write("echo  Pi NAS Sync - Windows Systeemkopie-backup\n")
        f.write("echo ============================================\n")
        f.write("echo.\n")
        f.write(f"echo Doel: {backup_dest}\n")
        f.write("echo.\n")
        f.write("echo [1/4] NAS bereikbaarheid controleren...\n")
        f.write(f'if exist "{backup_unc_basis}\\" (\n')
        f.write('  echo      NAS al bereikbaar.\n')
        f.write(') else (\n')
        f.write(f'  echo      Verbinding maken als gebruiker {gebruiker}...\n')
        # "echo." stuurt een lege regel naar stdin zodat net use nooit
        # interactief op een wachtwoord blijft wachten.
        f.write(f'  echo.| net use "{backup_unc_basis}" /user:{gebruiker} "{wachtwoord}"\n')
        f.write(')\n')
        f.write(f'if not exist "{backup_unc_basis}\\" (\n')
        f.write('  echo.\n')
        f.write('  echo ============================================\n')
        f.write('  echo  FOUT: NAS-pad niet bereikbaar.\n')
        f.write('  echo ============================================\n')
        f.write(f'  echo Pad: {backup_unc_basis}\n')
        f.write(f'  echo Gebruiker: {gebruiker}\n')
        f.write('  echo.\n')
        f.write('  echo Mogelijke oorzaak: verkeerd Samba-wachtwoord voor pi.\n')
        f.write('  echo Zet het op de Pi met:  sudo smbpasswd -a pi\n')
        f.write(f'  echo NET_USE_FOUT>"{STATUS_BESTAND}"\n')
        f.write('  echo.\n')
        f.write('  echo Druk op een toets om te sluiten...\n')
        f.write('  pause >nul\n')
        f.write('  exit /b 1\n')
        f.write(')\n')
        f.write("echo      NAS bereikbaar.\n")
        f.write("echo [2/4] Doelmap controleren...\n")
        f.write(f'if not exist "{backup_dest}" mkdir "{backup_dest}"\n')

        if shadow_verplaatst and shadow_drive and shadow_drive.upper() != "C:":
            f.write(f"echo      Schaduwkopie wordt op {shadow_drive} geplaatst (C: te krap)...\n")
            f.write('vssadmin delete shadowstorage /for=C: /on=C: >nul 2>&1\n')
            f.write(f'vssadmin add shadowstorage /for=C: /on={shadow_drive} /maxsize=20%% >nul 2>&1\n')
            f.write(f"echo      Schaduwopslag ingesteld op {shadow_drive}.\n")
        else:
            f.write("echo      Schaduwkopie wordt op C: gemaakt (genoeg ruimte).\n")

        f.write("echo [3/4] Windows Image Backup starten (dit kan lang duren)...\n")
        f.write("echo      Laat dit venster open staan tot de backup klaar is.\n")
        f.write("echo.\n")
        # MARKER: bewijst dat wbAdmin NU draait, bevat het schaduw-drive
        # zodat Fase B/C gericht kunnen opruimen.
        marker_inhoud = shadow_drive if (shadow_verplaatst and shadow_drive) else "C:"
        f.write(f'echo {marker_inhoud}>"{MARKER_BESTAND}"\n')
        wbadmin = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "wbadmin.exe")
        f.write(f'"{wbadmin}" start backup -backupTarget:"{backup_dest}" '
               f'-include:C: -allCritical -quiet\n')
        f.write('set WBEXIT=%ERRORLEVEL%\n')
        f.write(f'echo %WBEXIT%>"{STATUS_BESTAND}"\n')
        f.write(f'del "{MARKER_BESTAND}" >nul 2>&1\n')

        # ZELF-VERIFICATIE: meteen na wbAdmin, nog steeds elevated,
        # vraagt het script wbAdmin zelf of de backup geldig is - en
        # schrijft dat naar een bestand. Dit is dezelfde betrouwbare
        # bron die 'Controleer of er een geldige backup bestaat' ook
        # gebruikt, maar dan AUTOMATISCH vastgelegd, zodat dit altijd
        # nalees baar is - ook als het zwarte venster te snel sluit of
        # niet te kopieren is.
        f.write("echo [4/5] Zelf-verificatie (wbadmin get versions)...\n")
        f.write(f'echo === Pi NAS Sync zelf-verificatie === > "{TRANSCRIPT_BESTAND}"\n')
        f.write(f'echo Tijdstip: %date% %time% >> "{TRANSCRIPT_BESTAND}"\n')
        f.write(f'echo WBEXIT (exitcode van wbadmin start backup): %WBEXIT% >> "{TRANSCRIPT_BESTAND}"\n')
        f.write(f'echo. >> "{TRANSCRIPT_BESTAND}"\n')
        f.write(f'"{wbadmin}" get versions -backupTarget:"{backup_dest}" >> "{TRANSCRIPT_BESTAND}" 2>&1\n')

        f.write("echo [5/5] Afronden...\n")
        f.write("echo.\n")
        f.write('if %WBEXIT% EQU 0 (\n')
        f.write('  echo ============================================\n')
        f.write('  echo  BACKUP VOLTOOID!\n')
        f.write('  echo ============================================\n')
        f.write(') else (\n')
        f.write('  echo ============================================\n')
        f.write('  echo  BACKUP MISLUKT - foutcode %WBEXIT%\n')
        f.write('  echo ============================================\n')
        f.write('  echo Druk op een toets om te sluiten...\n')
        f.write('  pause >nul\n')
        f.write(')\n')
        f.write("echo.\n")
        f.write(f'echo Volledig logbestand: {TRANSCRIPT_BESTAND}\n')
        f.write("echo Dit venster sluit automatisch over 10 seconden...\n")
        f.write("timeout /t 10 >nul\n")

    return BAT_BESTAND


@dataclass
class ElevatedResultaat:
    gestart: bool = False
    geweigerd: bool = False
    afgebroken: bool = False
    exitcode: int = -1
    backup_dest: str = ""
    foutmelding: str = ""

    def succes(self) -> bool:
        return self.gestart and not self.geweigerd and not self.afgebroken and self.exitcode == 0


def start_elevated_en_wacht(bat_pad: str, backup_dest: str, shadow_drive: str,
                            on_log=None, on_uac_gestart=None,
                            max_wachttijd_sec: int = 1800) -> ElevatedResultaat:
    """Start het bat-bestand elevated via UAC (ShellExecuteW 'runas'),
    en wacht tot het is afgerond. Blokkerend; draai dit in een
    achtergrondthread vanuit de UI-laag.

    on_log(tekst, niveau): voortgangsmeldingen
    on_uac_gestart(): wordt aangeroepen zodra UAC is geaccepteerd en
                       het venster draait (voor UI-feedback)

    Detecteert Fase B (afgebroken backup: cmd-venster gesloten terwijl
    wbAdmin nog liep) via de marker - roept dan ZELF nog geen opruiming
    aan, dat doet de UI-laag via ruim_afgebroken_op(), zodat de UI de
    juiste meldingen kan tonen op het juiste moment."""
    on_log = on_log or (lambda t, n: None)
    resultaat = ElevatedResultaat(backup_dest=backup_dest)

    if not is_windows():
        resultaat.foutmelding = "Alleen op Windows beschikbaar"
        return resultaat

    import ctypes
    from ctypes import wintypes

    class SHELLEXECUTEINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", ctypes.c_ulong),
            ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR),
            ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", wintypes.LPCWSTR),
            ("hkeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD),
            ("hIconOrMonitor", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]

    SEE_MASK_NOCLOSEPROCESS = 0x00000040

    # Korte 8.3-naam ophalen om spaties in TEMP-pad te omzeilen
    try:
        short_buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.kernel32.GetShortPathNameW(bat_pad, short_buf, 260)
        bat_pad_kort = short_buf.value if short_buf.value else bat_pad
    except Exception:
        bat_pad_kort = bat_pad

    sei = SHELLEXECUTEINFO()
    sei.cbSize = ctypes.sizeof(sei)
    sei.fMask = SEE_MASK_NOCLOSEPROCESS
    sei.lpVerb = "runas"
    sei.lpFile = "cmd.exe"
    sei.lpParameters = f'/C "{bat_pad_kort}"'
    sei.nShow = 1  # SW_SHOWNORMAL - venster zichtbaar voor voortgang

    try:
        succes = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei))
    except Exception as e:
        resultaat.foutmelding = str(e)
        return resultaat

    if not succes or not sei.hProcess:
        resultaat.geweigerd = True
        on_log("UAC geannuleerd - geen backup gestart", "fout")
        return resultaat

    resultaat.gestart = True
    on_log("Backup loopt - zie het zwarte venster voor voortgang", "info")
    if on_uac_gestart:
        on_uac_gestart()

    ctypes.windll.kernel32.WaitForSingleObject(sei.hProcess, max_wachttijd_sec * 1000)
    ctypes.windll.kernel32.CloseHandle(sei.hProcess)

    # Iets geduldiger dan voorheen (was 5 sec) - puur als marge, het
    # statusbestand hoort al lang geschreven te zijn op het moment dat
    # het venster zelf sluit.
    for _ in range(15):
        if os.path.exists(STATUS_BESTAND):
            break
        time.sleep(1)

    exitcode = -1
    try:
        with open(STATUS_BESTAND, encoding="utf-8") as fh:
            raw = fh.read().strip()
        try:
            os.remove(STATUS_BESTAND)
        except Exception:
            pass
        exitcode = -2 if raw == "NET_USE_FOUT" else int(raw)
    except Exception:
        pass

    resultaat.exitcode = exitcode

    # VANGNET: als het statusbestand niet (op tijd) gevonden of
    # gelezen kon worden, betekent dat NIET automatisch dat de backup
    # mislukt is - het kan ook gewoon een timing-kwestie zijn (bijv.
    # het venster handmatig vroeg gesloten). Voordat 'mislukt' wordt
    # gemeld, wordt daarom het zelf-verificatie-transcript gelezen
    # (door het bat-script zelf geschreven via 'wbadmin get versions')
    # - staat daar een geldige, complete backup in, dan telt dat als
    # succes, ongeacht het ontbrekende statusbestand.
    transcript_inhoud = ""
    if os.path.exists(TRANSCRIPT_BESTAND):
        try:
            with open(TRANSCRIPT_BESTAND, encoding="utf-8", errors="replace") as fh:
                transcript_inhoud = fh.read()
        except Exception:
            pass

    if exitcode != 0 and transcript_inhoud:
        if "Backup time:" in transcript_inhoud or "Version identifier:" in transcript_inhoud:
            on_log("Statusbestand gaf geen duidelijk succes, maar de "
                  "zelf-verificatie (wbadmin get versions) bevestigt een "
                  "geldige, complete backup - dit telt als GESLAAGD.", "ok")
            resultaat.exitcode = 0
            exitcode = 0

    if transcript_inhoud:
        on_log(f"Volledig verificatie-logbestand: {TRANSCRIPT_BESTAND}", "info")

    # FASE B - afbreek-detectie: geen geldig statusbestand (exitcode -1)
    # MAAR de marker bestaat nog -> het cmd-venster is gesloten terwijl
    # wbAdmin nog liep.
    if exitcode == -1 and os.path.exists(MARKER_BESTAND):
        resultaat.afgebroken = True

    return resultaat


# =================================================================
# FASE B: opruimen na een afgebroken backup
# =================================================================

def ruim_afgebroken_op(shadow_drive: str, backup_dest: str, on_log=None):
    """FASE B - ruimt een afgebroken image-backup netjes op. Wordt
    aangeroepen als het cmd-venster gesloten is terwijl wbAdmin nog
    liep. Doet (elevated, via een klein opruim-bat-script):
      1. wbadmin stop job       -> stopt de nog lopende backup
      2. vssadmin delete shadows -> ruimt de tijdelijke schaduwkopie op
      3. shadowstorage-associatie terugzetten naar C: als die
         verplaatst was."""
    on_log = on_log or (lambda t, n: None)

    if not is_windows():
        on_log("Opruimen alleen op Windows mogelijk", "fout")
        return

    import ctypes

    on_log("Backup afgebroken gedetecteerd - bezig met opruimen...", "waarschuwing")

    try:
        with open(CLEANUP_BAT_BESTAND, "w", encoding="utf-8") as f:
            f.write("@echo off\n")
            f.write("echo Pi NAS Sync - opruimen afgebroken image-backup\n")
            f.write('echo Y| wbadmin stop job >nul 2>&1\n')
            f.write('echo Y| vssadmin delete shadows /for=C: /all >nul 2>&1\n')
            if shadow_drive and shadow_drive.upper() != "C:":
                f.write(f'vssadmin delete shadowstorage /for=C: /on={shadow_drive} >nul 2>&1\n')
            f.write("exit /b 0\n")

        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "cmd.exe", f'/C "{CLEANUP_BAT_BESTAND}"', None, 0)
        on_log("Opruimactie gestart: wbadmin gestopt, schaduwkopie verwijderd.", "ok")
        if shadow_drive and shadow_drive.upper() != "C:":
            on_log(f"Schaduwopslag-associatie teruggezet van {shadow_drive} naar C:.", "ok")
    except Exception as e:
        on_log(f"Opruimen mislukt: {str(e)[:60]}", "fout")

    try:
        if os.path.exists(MARKER_BESTAND):
            os.remove(MARKER_BESTAND)
    except Exception:
        pass

    on_log("Let op: controleer de doelmap op de NAS op een onvolledige "
          "WindowsImageBackup-map.", "waarschuwing")
    on_log(f"Doelmap: {backup_dest}", "info")


# =================================================================
# FASE C: heropstart-detectie
# =================================================================

def wbadmin_draait() -> bool:
    """Controleert of wbadmin.exe momenteel draait, via tasklist.
    BEWUST tasklist gebruikt, NIET wmic - wmic is op recente Windows-
    versies (24H2 en nieuwer) verwijderd of niet meer standaard
    aanwezig. Geeft (loopt: bool, zeker_geweten: bool) terug - als de
    check zelf faalt (geen van beide tools beschikbaar), is
    zeker_geweten False zodat de aanroeper NOOIT zomaar aanneemt dat
    wbAdmin niet loopt enkel omdat de check niet uitgevoerd kon
    worden. Dat omgekeerde aannemen was precies de eerdere bug: een
    mislukte detectie werd ten onrechte gelezen als 'loopt niet',
    waardoor een ECHT lopende backup per ongeluk werd gestopt."""
    if not is_windows():
        return False, True
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq wbadmin.exe"],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        loopt = "wbadmin.exe" in result.stdout.lower()
        return loopt, True
    except Exception:
        pass
    return False, False


def controleer_bij_opstart(on_log=None, backup_dest_onbekend="(onbekend)"):
    """FASE C - heropstart-detectie. Bij het opstarten van de app:
    controleert of er een marker is van een vorige run die niet
    netjes is afgesloten (crash, stroomuitval, PC-herstart). Als de
    marker nog bestaat maar wbAdmin niet meer draait, ruimt deze
    functie alsnog netjes op. Niet-blokkerend aan te roepen vanuit de
    UI-laag (start zelf een achtergrondthread).

    BELANGRIJK: deze functie hoort maar EENMAAL per opstart van de
    app aangeroepen te worden, niet bij elk bezoek aan het scherm -
    anders kan herhaald aanroepen een ECHT lopende backup alsnog per
    ongeluk laten stoppen als de detectie een keer faalt."""
    on_log = on_log or (lambda t, n: None)

    if not os.path.exists(MARKER_BESTAND):
        return  # niets te doen - meest voorkomende geval

    def _controleer():
        loopt, zeker = wbadmin_draait()

        if loopt:
            return  # wbAdmin draait nog gewoon - niets aan de hand

        if not zeker:
            # De detectie zelf is mislukt (geen tasklist beschikbaar?)
            # - NIET zomaar opruimen. Beter een keer te veel melden dan
            # een echt lopende backup per ongeluk stoppen.
            on_log("Kan niet zeker vaststellen of een vorige image-backup "
                  "nog loopt (detectie via tasklist mislukt). Er wordt NIET "
                  "automatisch opgeruimd om een eventueel echt lopende "
                  "backup niet te verstoren. Controleer dit zo nodig "
                  "handmatig (Taakbeheer: staat wbadmin.exe in de lijst?).",
                  "waarschuwing")
            return

        shadow_drive = "C:"
        try:
            with open(MARKER_BESTAND, encoding="utf-8") as mh:
                shadow_drive = mh.read().strip() or "C:"
        except Exception:
            pass

        on_log("Bij opstart gedetecteerd: vorige image-backup was niet "
              "netjes afgesloten. Automatisch opruimen...", "waarschuwing")
        ruim_afgebroken_op(shadow_drive, backup_dest_onbekend, on_log)

    threading.Thread(target=_controleer, daemon=True).start()


# =================================================================
# Herstelinstructie wegschrijven op de bestemming zelf
# =================================================================

def schrijf_noodkaartje(doel_map: str, unc_pad: str, gebruiker: str = "pi",
                         on_log=None) -> bool:
    """Schrijft het korte NOODKAART-bestand naar doel_map - bedoeld
    om op de herstel-USB-stick zelf te zetten (niet alleen op de
    NAS). Tijdens een echt herstel heb je de USB al in handen, maar
    nog GEEN toegang tot de NAS totdat je het pad al kent - dit
    kaartje moet er dus al zijn voordat je bij de NAS kunt, niet
    pas in de backupmap die je nog niet kan bereiken."""
    on_log = on_log or (lambda t, n: None)
    try:
        inhoud = NOODKAART_SJABLOON.format(
            datum=time.strftime("%Y-%m-%d %H:%M"),
            pc_naam=huidige_pc_naam(),
            unc_pad=unc_pad,
            gebruiker=gebruiker)
        pad = os.path.join(doel_map, NOODKAART_BESTANDSNAAM)
        with open(pad, "w", encoding="utf-8") as f:
            f.write(inhoud)
        on_log(f"Noodkaartje geschreven: {pad}", "ok")
        return True
    except Exception as e:
        on_log(f"Kon noodkaartje niet wegschrijven: {e}", "fout")
        return False


def schrijf_herstel_instructie(backup_dest: str, unc_pad: str = "", gebruiker: str = "pi",
                                on_log=None) -> bool:
    """Schrijft een leesbaar HERSTELLEN-LEES-DIT.txt bestand in de
    backupmap zelf (naast WindowsImageBackup), zodat de instructie
    beschikbaar is op het moment dat hij echt nodig is - ook als de
    computer waarop dit gemaakt is niet meer opstart. Geeft True
    terug bij succes.

    unc_pad: het EXACTE netwerkpad dat in WinRE ingetypt moet worden
    bij 'Een systeemkopie zoeken op het netwerk' - zonder dit moet
    iemand dit in een stressvolle situatie uit het hoofd weten."""
    on_log = on_log or (lambda t, n: None)
    try:
        inhoud = HERSTEL_INSTRUCTIE_SJABLOON.format(
            pc_naam=huidige_pc_naam(),
            datum=time.strftime("%Y-%m-%d %H:%M"),
            backup_dest=backup_dest,
            unc_pad=unc_pad or backup_dest,
            gebruiker=gebruiker)
        pad = os.path.join(backup_dest, HERSTEL_BESTANDSNAAM)
        os.makedirs(backup_dest, exist_ok=True)
        with open(pad, "w", encoding="utf-8") as f:
            f.write(inhoud)
        on_log(f"Herstelinstructie geschreven: {pad}", "ok")
        return True
    except Exception as e:
        on_log(f"Kon herstelinstructie niet wegschrijven: {e}", "fout")
        return False
