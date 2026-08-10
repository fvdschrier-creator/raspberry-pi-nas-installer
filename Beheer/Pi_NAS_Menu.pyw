#!/usr/bin/env python3
# Pi NAS Menu - datum uit Gedeeld/version.py (BIJGEWERKT)
# Twee lagen: Dagelijks beheer + Setup wizard
import tkinter as tk
from tkinter import messagebox
import subprocess, os, sys, base64, tempfile, threading, configparser, time, shutil, hashlib
import urllib.request

# ── Kleuren — centraal thema ──────────────────────────────────────────────────
import sys as _sys, os as _os
_gedeeld = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'Gedeeld')
if _os.path.isdir(_gedeeld) and _gedeeld not in _sys.path:
    _sys.path.insert(0, _os.path.abspath(_gedeeld))
from pinas_theme import *
from pinas_ui import maak_header, maak_knop
import pinas_launcher
import pinas_schijven
ACCENT = ACCENT_PICONTROL   # paars — Pi NAS Menu, alleen als vensterkop-branding

def _licht_tint(hex_c, amt=70):
    """16 juli 2026: lichtere variant van een thema-kleur berekenen (voor
    ondertitel-tekst op een gekleurde vensterkop) - i.p.v. een losse
    hardcoded hex ernaast. Verandert automatisch mee als het thema wijzigt."""
    h = hex_c.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"#{min(r+amt,255):02x}{min(g+amt,255):02x}{min(b+amt,255):02x}"

ACCENT_LICHT = _licht_tint(ACCENT_PICONTROL)   # ondertitel-tint op vensterkoppen

# ── Pad detectie — autonoom, pc-onafhankelijk ─────────────────────────────────
def _zoek_pad(*delen):
    """Combineer paden en retourneer bestaand pad of None."""
    p = os.path.join(*delen)
    return p if os.path.exists(p) else None

def _script_dir():
    return os.path.dirname(os.path.abspath(sys.argv[0]))

def _nas_root():
    """NAS root = een niveau omhoog van Beheer."""
    return os.path.dirname(_script_dir())

def _c_pinas():
    return os.path.join("C:\\", "PiNAS")

# 30 juli 2026: welk installatiescript hoort bij welke addon-sleutel - zelfde
# mapping als in pinas_addons_beheer.pyw, hier herhaald omdat dit een apart
# proces/bestand is. Gebruikt om te waarschuwen als het lokale bestand in
# Addons\ afwijkt van wat er als laatst-geinstalleerd op de Pi bekend staat.
_ADDON_SCRIPT = {
    "nextcloud": "pinas_nextcloud.sh",
    "pihole": "pinas_pihole.sh",
    "zerotier": "pinas_zerotier.sh",
    "vaultwarden": "pinas_vaultwarden.sh",
    "statuspagina": "pinas_status_pagina.sh",
    "printer": "pinas_printer.sh",
}

def _lokale_addon_hash(addon_key):
    """SHA256 van het huidige lokale Addons\\<script>.sh, om te vergelijken
    met de versie-marker die het script bij een geslaagde installatie op
    de Pi achterlaat. None als het lokale bestand niet gevonden is."""
    naam = _ADDON_SCRIPT.get(addon_key)
    if not naam:
        return None
    for basis in (_nas_root(), _c_pinas()):
        pad = os.path.join(basis, "Addons", naam)
        if os.path.exists(pad):
            try:
                with open(pad, "rb") as f:
                    return hashlib.sha256(f.read()).hexdigest()
            except Exception:
                return None
    return None

def pibackup_pad(bestand):
    up = os.environ.get("USERPROFILE", "")
    nas = _nas_root()
    kandidaten = [
        os.path.join(_c_pinas(), "Sync", bestand),
        os.path.join(nas, "Sync", bestand),
        os.path.join("C:\\", "bureaublad", "NAS", "NAS_Backup", "pibackup", bestand),
        os.path.join(up, "OneDrive", "Documenten", "Desktop", "NAS", "NAS_Backup", "pibackup", bestand),
        os.path.join(up, "OneDrive", "Documents", "Desktop", "NAS", "NAS_Backup", "pibackup", bestand),
    ]
    for p in kandidaten:
        if os.path.exists(p): return p
    return None

def bat_pad(naam):
    """Zoek bat bestand in scriptmap en nas_root."""
    for basis in [_script_dir(), _nas_root(),
                  os.path.join(_nas_root(), "Gedeeld"),
                  os.path.join(_nas_root(), "Beheer")]:
        p = os.path.join(basis, naam)
        if os.path.exists(p): return p
    return None

def putty_exe():
    for p in [r"C:\Program Files\PuTTY\putty.exe",
              r"C:\Program Files (x86)\PuTTY\putty.exe"]:
        if os.path.exists(p): return p
    return None

def tigervnc_exe():
    for p in [r"C:\Program Files\TigerVNC\vncviewer.exe",
              r"C:\Program Files (x86)\TigerVNC\vncviewer.exe"]:
        if os.path.exists(p): return p
    return None

def ppk_pad():
    return os.path.join(os.environ.get("USERPROFILE", ""), ".ssh", "id_ed25519.ppk")

def _puttygen_exe():
    for p in [r"C:\Program Files\PuTTY\puttygen.exe",
              r"C:\Program Files (x86)\PuTTY\puttygen.exe"]:
        if os.path.exists(p): return p
    return None

def zorg_voor_ppk():
    """Als de OpenSSH-sleutel (id_ed25519) wel bestaat maar de .ppk niet,
    is de sleutel ooit aangemaakt zonder 'm om te zetten naar PuTTY's
    eigen PPK-formaat. De commandoregel-conversie van puttygen bleek op
    sommige Windows-installaties niet te werken (ook met de juiste
    documentatie-syntax) - daarom opent dit de GUI van puttygen, die wel
    betrouwbaar werkt, met duidelijke instructies voor de gebruiker."""
    ppk = ppk_pad()
    if os.path.exists(ppk):
        return True
    openssh_sleutel = os.path.join(os.environ.get("USERPROFILE", ""), ".ssh", "id_ed25519")
    puttygen = _puttygen_exe()
    if not os.path.exists(openssh_sleutel) or not puttygen:
        return False
    messagebox.showinfo(
        "SSH sleutel omzetten",
        "PuTTYgen wordt geopend om je SSH-sleutel om te zetten naar het "
        "juiste formaat:\n\n"
        "1. Klik op 'Conversions' -> 'Import key'\n"
        f"2. Kies dit bestand: {openssh_sleutel}\n"
        "3. Klik op 'Save private key'\n"
        "4. Kies 'Ja' als gevraagd wordt zonder wachtwoordzin op te slaan\n"
        f"5. Sla op als: {ppk}\n\n"
        "Klik daarna hier op OK, en probeer de verbinding opnieuw.")
    try:
        subprocess.Popen([puttygen])
    except Exception:
        pass
    return os.path.exists(ppk)

# ── Status checks ─────────────────────────────────────────────────────────────
def check_putty():      return putty_exe() is not None
def check_ssh_sleutel(): return zorg_voor_ppk() or os.path.exists(ppk_pad())

def check_ssh():
    """Echte verbindingstest (niet alleen of het sleutelbestand bestaat) -
    probeert daadwerkelijk in te loggen op de Pi via plink (komt mee met
    PuTTY, zelfde map als putty.exe)."""
    ppk = ppk_pad()
    exe = putty_exe()
    if not exe or not os.path.exists(ppk):
        return False
    plink = os.path.join(os.path.dirname(exe), "plink.exe")
    if not os.path.exists(plink):
        return False
    try:
        r = subprocess.run(
            [plink, "-batch", "-ssh", "-i", ppk, f"pi@{PI_IP}", "echo ok"],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=8)
        return "ok" in (r.stdout or "").strip()
    except Exception:
        return False
def check_tigervnc():   return tigervnc_exe() is not None
def check_pibackup():   return pibackup_pad("pinas_sync_app.pyw") is not None

def nieuwste_log_bestand(prefix, fallback):
    """Zoek het nieuwste logbestand in C:\\PiNAS\\Logs dat met prefix begint.
    pinas_sync schrijft logs met een tijdstempel (pinas_sync_JJJJMMDD_*.log),
    dus we pakken de meest recente i.p.v. een vaste bestandsnaam."""
    try:
        lm = os.path.join("C:\\", "PiNAS", "Logs")
        kand = sorted(f for f in os.listdir(lm)
                      if f.startswith(prefix) and f.endswith(".log"))
        return kand[-1] if kand else fallback
    except Exception:
        return fallback

def check_simulator_map():
    """Controleer of NAS_Simulator map bestaat in C:/PiNAS/NAS_Simulator."""
    nas_sim = os.path.join("C:\\", "PiNAS", "NAS_Simulator")
    if os.path.isdir(nas_sim):
        return True
    # Fallback: bureaublad (legacy)
    bureau = os.path.join(os.environ.get("USERPROFILE",""), "Desktop", "NAS_Simulator")
    return os.path.isdir(bureau)

def check_docker_desktop():
    lad = os.environ.get("LOCALAPPDATA", "")
    for p in [r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
              os.path.join(lad, "Docker", "Docker Desktop.exe")]:
        if os.path.exists(p): return True
    return False

def _muiswiel_op_focus(win, canvas):
    """Bindt het muiswiel aan canvas, en herbindt het automatisch zodra
    win weer focus krijgt.

    6 augustus 2026 (Frans: klikte in Status terwijl Help nog open stond,
    maar Help bleef scrollen i.p.v. Status): bind_all("<MouseWheel>") is
    GLOBAAL voor de hele toepassing - zonder dit blijft het venster dat
    het laatst bind_all aanriep de scroll 'vasthouden', ook als je in een
    ANDER, nog open venster klikt. <FocusIn> herbindt de globale handler
    naar het venster dat je daadwerkelijk hebt aangeklikt, zodat scrollen
    altijd het venster onder je aandacht raakt - werkt met willekeurig
    veel tegelijk open vensters, niet alleen 2."""
    def _scroll(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    canvas.bind_all("<MouseWheel>", _scroll)
    win.bind("<FocusIn>", lambda e: canvas.bind_all("<MouseWheel>", _scroll))
    return _scroll

def check_zerotier_windows_dienst():
    """Vraagt via PowerShell de status van de lokale ZeroTier One-Windows-
    dienst op - geeft 'actief', 'gestopt', 'afwezig' of 'onbekend' terug.

    4 augustus 2026 (Frans): liep tegenaan dat deze dienst uit stond
    (Dashboard/Bitwarden werkten toen niet via ZeroTier, onbekend/stil
    probleem totdat handmatig via services.msc aangezet) - wil dit in Pi
    NAS Menu kunnen zien EN meteen kunnen starten, i.p.v. zelf steeds naar
    services.msc te moeten."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Service -Name '*ZeroTier*' -ErrorAction SilentlyContinue "
             "| Select-Object -First 1).Status"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW)
        status = r.stdout.strip()
        if status == "Running":
            return "actief"
        if status == "Stopped":
            return "gestopt"
        if status == "":
            return "afwezig"
        return "onbekend"
    except Exception:
        return "onbekend"

def start_zerotier_windows_dienst():
    """Start de lokale ZeroTier-Windows-dienst - vraagt een Windows-
    beheerdersbevestiging (UAC), want een dienst starten kan niet zonder.
    Schrijft een klein .ps1-bestand weg en start dat verhoogd, i.p.v. de
    verhoogde aanroep zelf met geneste aanhalingstekens te proberen (dat
    is foutgevoelig)."""
    ps1_pad = os.path.join(tempfile.gettempdir(), "pinas_zerotier_start.ps1")
    with open(ps1_pad, "w", encoding="utf-8") as f:
        f.write("Get-Service -Name '*ZeroTier*' -ErrorAction SilentlyContinue "
                "| Start-Service\n")
    subprocess.Popen(
        ["powershell", "-NoProfile", "-Command",
         "Start-Process powershell -Verb RunAs -ArgumentList "
         f"'-NoProfile -ExecutionPolicy Bypass -File \"{ps1_pad}\"'"],
        creationflags=subprocess.CREATE_NO_WINDOW)

def stop_zerotier_windows_dienst():
    """Stopt de lokale ZeroTier-Windows-dienst - spiegelbeeld van
    start_zerotier_windows_dienst (4 augustus 2026, Frans: wil 'm net als
    handmatig via services.msc ook vanuit Pi NAS Menu kunnen uit- EN
    aanzetten)."""
    ps1_pad = os.path.join(tempfile.gettempdir(), "pinas_zerotier_stop.ps1")
    with open(ps1_pad, "w", encoding="utf-8") as f:
        f.write("Get-Service -Name '*ZeroTier*' -ErrorAction SilentlyContinue "
                "| Stop-Service -Force\n")
    subprocess.Popen(
        ["powershell", "-NoProfile", "-Command",
         "Start-Process powershell -Verb RunAs -ArgumentList "
         f"'-NoProfile -ExecutionPolicy Bypass -File \"{ps1_pad}\"'"],
        creationflags=subprocess.CREATE_NO_WINDOW)

def check_schijf(letter):
    """Controleert of schijfletter Y:/Z: bereikbaar is via 'net use'.

    Voorheen gaf één korte poging (timeout=3 sec) met een bare except
    al een definitief 'False' terug bij de geringste vertraging — een
    kortstondige netwerk- of Pi-hapering werd dan ten onrechte gemeld
    als een echt Y:/Z:-probleem, wat de LanManFix-knop liet verschijnen
    voor iets dat zichzelf al had opgelost. Nu: twee pogingen met een
    ruimere timeout, pas na BEIDE mislukte pogingen wordt 'niet
    bereikbaar' aangenomen.
    """
    for poging in range(2):
        try:
            r = subprocess.run(["net", "use", letter + ":"],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=4)
            # Exitcode 0 = de schijfletter is gekoppeld. Dit is taal-onafhankelijk;
            # zoeken naar "OK"/"verbonden" in de uitvoer faalde op Nederlandse
            # Windows (andere bewoording), waardoor de LanManFix-knop oranje bleef
            # terwijl Z: wel degelijk gekoppeld was.
            if r.returncode == 0:
                return True
        except Exception:
            pass
        if poging == 0:
            time.sleep(1.5)  # korte adempauze voor de tweede poging
    return False


def check_share(share_naam, terugval_letter, ip=None):
    """Zelfde als check_schijf(), maar zoekt eerst zelf de juiste
    stationsletter op via de share-naam ("Opslag"/"Backup") in plaats
    van een vaste letter aan te nemen. Y:/Z: kunnen op een andere pc
    namelijk al door iets anders bezet zijn, waardoor Windows de
    netwerkschijven een andere letter geeft - deze functie vindt dan
    nog steeds de juiste, in plaats van "niet bereikbaar" te melden
    terwijl de verbinding an sich prima werkt."""
    letter = pinas_schijven.vind_letter_of_terugval(share_naam, terugval_letter, ip)
    return check_schijf(letter)


def _opruim_losse_verbindingen(share_namen):
    """Verwijdert ALLE bestaande 'net use'-verbindingen (met of zonder
    stationsletter) die naar een share met een van de gegeven namen
    wijzen, ongeacht via welk IP-adres (lokaal netwerk of via ZeroTier).

    Nodig omdat _verbind_schijven() voorheen alleen de eigen letters
    (Y:/Z:) opruimde. Een losse testverbinding zoals \\\\10.90.69.2\\Opslag
    (bijv. na het uitproberen van de VPN) bleef dan liggen en gaf de
    Windows-fout 'meerdere verbindingen met een server die meerdere
    gebruikersnamen gebruikt' zodra de vaste Y:/Z:-koppeling naar het
    lokale IP opnieuw werd opgezet."""
    try:
        r = subprocess.run(["net", "use"], capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=8)
    except Exception:
        return
    for regel in (r.stdout or "").splitlines():
        regel = regel.strip()
        if "\\\\" not in regel:
            continue
        # Pak het UNC-pad uit de regel, ongeacht of ervoor een status/letter
        # staat (bv. "OK  Y:  \\UW_PI_IP_ADRES\Opslag  Microsoft...").
        idx = regel.find("\\\\")
        rest = regel[idx:]
        pad = rest.split()[0] if rest.split() else ""
        if not pad:
            continue
        share_hier = pad.rsplit("\\", 1)[-1]
        if share_hier in share_namen:
            try:
                subprocess.run(["net", "use", pad, "/delete", "/y"],
                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=8)
            except Exception:
                pass


def _schijf_config():
    """Schijfletter -> Samba-share. Leest [schijven] uit de config en valt
    terug op de standaard Y:->Opslag, Z:->Backup. Zo werkt de knop ook als
    iemand andere letters/namen gebruikt."""
    paren = {}
    try:
        if _cfg.has_section("schijven"):
            for letter, share in _cfg.items("schijven"):
                L = letter.strip().upper().rstrip(":")
                if L and share.strip():
                    paren[L] = share.strip()
    except Exception:
        pass
    if not paren:
        paren = {"Y": "Opslag", "Z": "Backup"}
    return paren


def _onthoud_schijfletter(share, letter):
    """Slaat een gevonden/gebruikte stationsletter voor deze share op in
    picontrol.cfg's [schijven]-sectie, zodat de volgende keer dezelfde
    letter gebruikt wordt in plaats van steeds opnieuw te moeten zoeken
    of te falen op een bezette standaardletter."""
    try:
        if not _cfg.has_section("schijven"):
            _cfg.add_section("schijven")
        # Verwijder een eventuele oude letter die naar dezelfde share
        # wees, zodat er niet twee regels voor dezelfde share overblijven.
        for bestaande_letter, bestaande_share in list(_cfg.items("schijven")):
            if bestaande_share.strip().lower() == share.strip().lower():
                _cfg.remove_option("schijven", bestaande_letter)
        _cfg.set("schijven", letter, share)
        with open(_cfg_pad, "w", encoding="utf-8") as f:
            _cfg.write(f)
    except Exception:
        pass  # Niet kunnen opslaan is niet fataal - werkt deze sessie nog wel


def _letter_voor_share(share_naam, terugval):
    """Geeft de stationsletter voor een share ('Opslag'/'Backup') terug
    op basis van _schijf_config() - GEEN hardcoded Y/Z aannemen.

    4 augustus 2026 (Frans, staande regel): 'we werken niet met hardcoded
    items in de programmatuur' - Opslag/Backup zijn de vaste namen, de
    letter is een lokaal detail dat per pc kan verschillen. Overal waar
    het programma zelf een 'net use'-commando bouwt (i.p.v. alleen een
    tekst tonen) moet deze functie gebruikt worden, nooit een letterlijke
    "Y:"/"Z:" in de code."""
    for letter, share in _schijf_config().items():
        if share.strip().lower() == share_naam.strip().lower():
            return letter
    return terugval


def _opslag_letter():
    return _letter_voor_share("Opslag", "Y")


def _backup_letter():
    return _letter_voor_share("Backup", "Z")


def _spiegel_letter():
    return _letter_voor_share("SpiegelBackup", "H")


def _heeft_spiegel_backup():
    """True als deze installatie een Spiegel Backup-schijf heeft
    (H:\\SpiegelBackup aan de Pi, zie Fase 2 van de Qnap-rename, 8
    augustus 2026) - staat in picontrol.cfg's [schijven]-sectie. Niet
    elke installatie (bijv. de Dell) heeft deze schijf, dus dit is
    BEWUST optioneel en nooit een vaste aanname."""
    return "spiegelbackup" in [s.strip().lower() for s in _schijf_config().values()]

# ── Configuratie ──────────────────────────────────────────────────────────────
_cfg = configparser.ConfigParser()
_cfg_pad = os.path.join(_script_dir(), "picontrol.cfg")
if os.path.exists(_cfg_pad):
    _cfg.read(_cfg_pad, encoding="utf-8")

PI_IP = _cfg.get("pi", "ip", fallback="UW_PI_IP_ADRES")
# 4 augustus 2026 (Frans: wil in de Status ook de ZeroTier-adressen zien,
# niet alleen lokaal) - zelfde patroon als pinas_addons_beheer.pyw's ZT_IP.
ZT_IP = _cfg.get("pi", "zt_ip", fallback="10.90.69.2")
SEAGATE_URL = f"http://{PI_IP}:8765"

# ── Gedeeld pad + cache opruimen bij elke start ──────────────────────────────
_gedeeld_pad = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'Gedeeld'))
if _gedeeld_pad not in _sys.path:
    _sys.path.insert(0, _gedeeld_pad)
# __pycache__ altijd opruimen zodat nieuwe modules direct actief zijn
for _cache_map in [
    _os.path.join(_gedeeld_pad, '__pycache__'),
    _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '__pycache__'),
]:
    if _os.path.isdir(_cache_map):
        import shutil as _shutil
        try: _shutil.rmtree(_cache_map)
        except: pass

# ── Wachtwoord — uit Windows Credential Manager ───────────────────────────────
try:
    from pinas_wachtwoord import get_wachtwoord, set_wachtwoord, wachtwoord_beschikbaar
    _WACHTWOORD_MODULE = True
except ImportError:
    _WACHTWOORD_MODULE = False
    def get_wachtwoord(soort="samba"): return None
    def set_wachtwoord(ww, soort="samba"): return False
    def wachtwoord_beschikbaar(soort="samba"): return False

# ── Versie ────────────────────────────────────────────────────────────────────
try:
    from version import BIJGEWERKT, GITHUB_VERSIE
except ImportError:
    BIJGEWERKT    = "onbekende datum"
    GITHUB_VERSIE = "1.1.0"

# ── Logging ───────────────────────────────────────────────────────────────────
try:
    from pinas_logging import get_logger, get_log_pad
    log = get_logger("picontrol")
except ImportError:
    import logging as _logging
    log = _logging.getLogger("picontrol")
    log.addHandler(_logging.NullHandler())
    def get_log_pad(naam="picontrol"):
        return _os.path.join("C:\\", "PiNAS", "Logs", f"{naam}.log")

def _get_nas_wachtwoord():
    """Haal Samba wachtwoord op — eerst Credential Manager, dan bestandsfallback."""
    # Poging 1: via pinas_wachtwoord module (gebruikt keyring = Credential Manager)
    ww = get_wachtwoord("samba")
    if ww:
        return ww
    # Poging 2: direct via keyring voor het Pi IP-adres
    try:
        import keyring as _kr
        for service in [f"TERMSRV/{PI_IP}", PI_IP, f"\\\\{PI_IP}"]:
            ww = _kr.get_password(service, "pi")
            if ww:
                return ww
    except Exception:
        pass
    # Poging 3: fallback uit oude config (migreer naar Credential Manager)
    ww_cfg = _cfg.get("pi", "wachtwoord", fallback="")
    if ww_cfg and ww_cfg not in ("UW_WACHTWOORD", ""):
        set_wachtwoord(ww_cfg, "samba")
        return ww_cfg
    return ""

# ── SSH helpers ───────────────────────────────────────────────────────────────
SSH_VEREISTEN = {
    "docker": {"check": "which docker", "naam": "Docker (op Pi)",
        "uitleg": "Docker is niet geinstalleerd op de Pi.\n\nInstalleer via Beheer → Pi services → Docker op Pi."},
    "vncserver": {"check": "which vncserver", "naam": "TigerVNC (op Pi)",
        "uitleg": "TigerVNC server is niet geinstalleerd op de Pi.\n\nInstalleer via Beheer → Pi services."},
}

def ssh_voer_uit(cmd, vereiste=None, root=None):
    if vereiste and vereiste in SSH_VEREISTEN:
        v = SSH_VEREISTEN[vereiste]
        def check():
            try:
                r = subprocess.run(
                    ["ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no",
                     f"pi@{PI_IP}", v["check"]],
                    capture_output=True, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW, timeout=8)
                output = (r.stdout + r.stderr).strip()
            except: output = ""
            niet_gevonden = not output or "not found" in output.lower() or output == ""
            if niet_gevonden:
                if root: root.after(0, lambda: _toon_niet_geinstalleerd(v, vereiste, root))
            else:
                _run_ssh(cmd)
        threading.Thread(target=check, daemon=True).start()
        return
    _run_ssh(cmd)

def _run_ssh(cmd):
    bat = os.path.join(tempfile.gettempdir(), "picontrol_ssh.bat")
    with open(bat, "w") as f:
        f.write(f"@echo off\r\nssh pi@{PI_IP} \"{cmd}\"\r\npause\r\n")
    subprocess.Popen(["cmd", "/c", bat], creationflags=subprocess.CREATE_NEW_CONSOLE)

def _toon_niet_geinstalleerd(v, vereiste, root):
    win = tk.Toplevel(root)
    win.title(f"{v['naam']} niet gevonden")
    win.configure(bg=BG); win.resizable(False, False)
    win.geometry("440x260"); win.grab_set()
    win.update_idletasks()
    x = root.winfo_x() + (root.winfo_width() - 440)//2
    y = root.winfo_y() + (root.winfo_height() - 260)//2
    win.geometry(f"+{x}+{y}")
    tk.Frame(win, bg=ERR_C, pady=10).pack(fill="x")
    tk.Label(win.winfo_children()[-1], text=f"⚠  {v['naam']} niet gevonden",
             font=("Segoe UI", 11, "bold"), bg=ERR_C, fg="#ffffff").pack()
    body = tk.Frame(win, bg=BG, padx=20, pady=14)
    body.pack(fill="both", expand=True)
    tk.Label(body, text=v["uitleg"], font=("Segoe UI", 9), bg=BG, fg=FG,
             justify="left", wraplength=380).pack(fill="x", pady=(0,12))
    if vereiste == "docker":
        def install_docker():
            win.destroy()
            cmds = ("curl -fsSL https://get.docker.com | sudo sh; "
                    "sudo usermod -aG docker pi; "
                    "sudo systemctl enable docker; sudo systemctl start docker; "
                    "echo === Docker klaar ===; docker --version")
            bat = os.path.join(tempfile.gettempdir(), "docker_install.bat")
            with open(bat, "w") as f:
                f.write(f"@echo off\r\necho Docker installeren (~2 min)...\r\n"
                        f"ssh pi@{PI_IP} \"{cmds}\"\r\npause\r\n")
            subprocess.Popen(["cmd", "/c", bat], creationflags=subprocess.CREATE_NEW_CONSOLE)
        tk.Button(body, text="🐳  Docker installeren via SSH", command=install_docker,
                  bg=ACCENT_PINAS, fg="#ffffff", font=("Segoe UI", 10, "bold"), relief="flat",
                  cursor="hand2", pady=8, borderwidth=0).pack(fill="x", pady=(0,6))
    tk.Button(body, text="Sluiten", command=win.destroy,
              bg=PANEL2, fg=FG, font=("Segoe UI", 9), relief="flat",
              cursor="hand2", pady=7, borderwidth=0).pack(fill="x")

def run_bat(naam):
    """Start een .bat bestand in een zichtbaar CMD venster."""
    pad = bat_pad(naam)
    if not pad:
        messagebox.showerror("Bestand niet gevonden",
            f"{naam} kon niet worden gevonden.\n\n"
            f"Gezocht in C:\\PiNAS\\Gedeeld\\ en C:\\PiNAS\\Beheer\\\n\n"
            "Tip: controleer de mappenstructuur via Controles → Structuurcheck & Opruimen")
        return
    # Start CMD venster zichtbaar zodat gebruiker output en fouten kan zien
    subprocess.Popen(
        f'start cmd /k "{pad}"',
        shell=True,
        cwd=os.path.dirname(pad)
    )

def open_powershell():
    subprocess.Popen(["powershell", "-NoExit", "-Command", f"ssh pi@{PI_IP}"],
                     creationflags=subprocess.CREATE_NEW_CONSOLE)

def open_putty():
    exe = putty_exe()
    ppk = ppk_pad()
    if not exe:
        messagebox.showerror("PuTTY niet gevonden",
        "PuTTY is niet geïnstalleerd op deze PC.\n\n"
        "Wat te doen:\n"
        "  1. Ga naar Beheer → Windows onderdelen\n"
        "  2. Klik op 'PuTTY + SSH sleutel instellen'")
        return
    if not os.path.exists(ppk):
        if not zorg_voor_ppk():
            return  # zorg_voor_ppk() heeft de gebruiker al zelf geinstrueerd
    if not os.path.exists(ppk):
        # Gebruiker heeft de omzetting nog niet (kunnen) voltooien
        return
    subprocess.Popen([exe, "-ssh", f"pi@{PI_IP}", "-i", ppk])

def open_tigervnc():
    exe = tigervnc_exe()
    if not exe:
        messagebox.showerror("TigerVNC niet gevonden",
        "TigerVNC is niet geïnstalleerd op deze PC.\n\n"
        "Wat te doen:\n"
        "  1. Ga naar Beheer → Windows onderdelen\n"
        "  2. Klik op 'TigerVNC Viewer installeren'")
        return
    subprocess.Popen([exe, f"{PI_IP}:5901"])

# ── ICO ───────────────────────────────────────────────────────────────────────
ICO_B64 = "AAABAAQAEBAAAAAAIADnAAAARgAAACAgAAAAACAALgEAAC0BAAAwMAAAAAAgAJ4BAABbAgAAAAAAAAAAIAAsCAAA+QMAAIlQTkcNChoKAAAADUlIRFIAAAAQAAAAEAgGAAAAH/P/YQAAAK5JREFUeJxjZGBgYJCz6vrPQAZ4dKyMkZFczTDARIlmBgYGBhZkjlN2AU6FL8TqGCReNcH5+6ZOIN4FL8TqUGhkgBoGbKo4DdGqPslwrdUcIfDrNhYDCBiCrpmBAS0M0CWJASgGlHYX41S4pCaEIaZlDZzfXdrLwMBAZCAuqQlBoZEB0YEoybiI4fn/OIQA1KuoLsDjf2yaGRioEIgUJ2XKDXh0rIyRXM2PjpUxAgCYhjdeC3PqXQAAAABJRU5ErkJggg=="

def _logo_hoofdmenu_pad():
    """Logo (17 juli 2026, ontwerp Frans) voor de hero-header van het
    hoofdmenu - groter formaat dan de kleine header-variant die de
    secundaire vensters via pinas_ui.maak_header() gebruiken."""
    for p in [os.path.join(_script_dir(), "assets", "pinas_logo_hoofdmenu.png"),
              os.path.join(_nas_root(), "Beheer", "assets", "pinas_logo_hoofdmenu.png")]:
        if os.path.exists(p):
            return p
    return None


def _ico_pad():
    # Probeer eerst echt ico bestand
    for p in [os.path.join(_script_dir(), "Pi_NAS_Menu.ico"),
              os.path.join(_nas_root(), "Beheer", "Pi_NAS_Menu.ico")]:
        if os.path.exists(p) and os.path.getsize(p) > 100:
            return p
    tmp = os.path.join(tempfile.gettempdir(), "pi_nas_menu.ico")
    if not os.path.exists(tmp):
        with open(tmp, "wb") as f: f.write(base64.b64decode(ICO_B64))
    return tmp

# ═══════════════════════════════════════════════════════════════════════════════
#  MENU KLASSE
# ═══════════════════════════════════════════════════════════════════════════════
# ── Threading lock voor status updates ───────────────────────────────────────
import threading as _threading
_status_lock = _threading.Lock()

class Menu(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Pi NAS Menu — Pi NAS Suite (bijgewerkt: {BIJGEWERKT})")
        try: self.iconbitmap(_ico_pad())
        except: pass
        self.configure(bg=BG)
        self.resizable(True, True)
        # 18 juli 2026: van 700 naar 520 nu de inhoud scrollbaar is - het
        # venster hoeft niet meer minimaal 700px hoog te zijn, dat was precies
        # het probleem bij een lagere schermresolutie.
        self.minsize(580, 520)
        self._bouw()
        self.after(500, self._seagate_status_update)
        self.after(1000, self._start_ping)
        self.after(2000, self._ververs_pi_status)
        self.after(3000, self._auto_koppel_schijven)  # Y:/Z: koppelen bij opstarten
        # 31 juli 2026 (Frans): de Pi-scripts-synccheck liep tot nu toe NOOIT
        # vanzelf mee bij opstarten - alleen als je zelf het Status-scherm
        # opende en op "Sync opnieuw controleren" klikte, of na een upload.
        # Daardoor kon een verouderd Pi-script dagenlang onopgemerkt blijven.
        # Nu automatisch bij elke start, met een echte pop-up (zie
        # _start_sync_check) als er iets geupload moet worden - in plaats
        # van alleen een gekleurd statusregeltje dat je zelf moet opmerken.
        self.after(4000, self._start_sync_check)
        self.after(8000, self._check_suite_update)    # GitHub versiecheck
        # 4 augustus 2026 (Frans: hele programma liep vast): de ZeroTier-
        # Windows-check gebruikt PowerShell, wat 1-3 sec kan duren om op te
        # starten - die MOET via een achtergrondthread, nooit rechtstreeks
        # tijdens het opbouwen van een scherm (dat bevriest anders de HELE
        # Tkinter-app, alle vensters, want er is maar 1 hoofdthread).
        self._zt_windows_status = "onbekend"
        self.after(1500, self._start_zt_windows_check)
        self.after(100, self._redraw_all_buttons)    # knoppen hertekenen na render

    def _herstel_hoofd_muiswiel(self):
        """Geeft de muiswiel-scroll terug aan het hoofdvenster nadat een
        onderliggend scrollbaar venster (Onderhoud, Status) gesloten is - zie
        de uitleg bij het opzetten van de canvas in _bouw() hieronder."""
        try:
            if self._hoofd_scroll_canvas.winfo_exists():
                self._hoofd_scroll_canvas.bind_all("<MouseWheel>", self._hoofd_muiswiel)
        except (tk.TclError, AttributeError):
            pass

    def _bouw(self):
        # ── Header ────────────────────────────────────────────────────────────
        # Logo (17 juli 2026, ontwerp Frans) bevat de "PiNAS"-tekst al zelf -
        # de losse "Pi NAS"-tekstlabel die hier eerder apart onder/boven het
        # logo stond gaf daardoor 2x dezelfde naam onder elkaar. Nu: logo
        # links, volledig (icoon + naam), met IP/verbinding ernaast.
        hdr = tk.Frame(self, bg=ACCENT_PICONTROL, pady=14, padx=18)
        hdr.pack(fill="x")
        _logo_pad = _logo_hoofdmenu_pad()
        if _logo_pad:
            try:
                self._logo_img = tk.PhotoImage(file=_logo_pad)  # referentie vasthouden
                tk.Label(hdr, image=self._logo_img, bg=ACCENT_PICONTROL).pack(
                    side="left", padx=(0, 16))
            except Exception:
                pass
        info_kolom = tk.Frame(hdr, bg=ACCENT_PICONTROL)
        info_kolom.pack(side="left")
        tk.Label(info_kolom, text=PI_IP, font=("Segoe UI", 10),
                 bg=ACCENT_PICONTROL, fg=ACCENT_LICHT).pack(anchor="w")
        self.lbl_ping = tk.Label(info_kolom, text="● Verbinding controleren...",
                                  font=("Segoe UI", 10), bg=ACCENT_PICONTROL, fg=YELLOW)
        self.lbl_ping.pack(anchor="w")

        # ── Eén kolom (scrollbaar - 18 juli 2026, wens Frans: bij een lagere
        # schermresolutie paste niet alles op het scherm). Zelfde canvas +
        # scrollbar-opzet als Onderhoud/Status.
        #
        # Muiswiel: bind_all i.p.v. bind, anders werkt het muiswiel alleen
        # boven kale canvas-ruimte, niet boven de knoppen/labels erin (zelfde
        # reden als bij Onderhoud/Status hieronder). bind_all is GLOBAAL voor
        # de hele toepassing - Onderhoud en Status zetten bij het openen hun
        # eigen bind_all (nemen de scroll dus tijdelijk over, verwacht
        # gedrag). Belangrijk: dit hoofdvenster blijft de hele sessie open,
        # dus na het sluiten van zo'n venster moet het muiswiel HIER weer
        # worden hersteld - dat gebeurt via _herstel_hoofd_muiswiel(),
        # aangeroepen vanuit het <Destroy>-event van die vensters. (Eerdere
        # poging met Enter/Leave-scoped bind_all leek slimmer, maar de Leave
        # op dit canvas vuurt zodra Onderhoud/Status erboven opent, en
        # unbind_all("<MouseWheel>") is ook globaal - dat brak dus juist het
        # muiswiel in het net geopende venster. Vandaar deze aanpak.)
        body_container = tk.Frame(self, bg=BG)
        body_container.pack(fill="both", expand=True)
        canvas = tk.Canvas(body_container, bg=BG, highlightthickness=0)
        scroll = tk.Scrollbar(body_container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(canvas, bg=BG, padx=16, pady=16)
        _body_canvas_win = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(_body_canvas_win, width=e.width))

        self._hoofd_scroll_canvas = canvas
        # 6 augustus 2026: _muiswiel_op_focus herbindt het muiswiel ook
        # zodra dit hoofdvenster weer focus krijgt (zie functie zelf) -
        # lost op dat een ander, nog open venster de scroll bleef
        # vasthouden. self._hoofd_muiswiel blijft bestaan voor de
        # bestaande _herstel_hoofd_muiswiel()-restore-on-close-logica.
        self._hoofd_muiswiel = _muiswiel_op_focus(self, canvas)

        # STATUS SAMENVATTING
        self.status_samen_frame = tk.Frame(body, bg=BG)
        self.status_samen_frame.pack(fill="x", pady=(0,8))
        self._sep(body)

        # VERBINDEN
        self._sectie(body, "VERBINDEN")
        self._btn(body, "⌨  SSH via PowerShell", open_powershell, ACCENT_PINAS)
        self._btn(body, "🖥  SSH via PuTTY", open_putty, ACCENT_PINAS)
        self._btn(body, "🖼  TigerVNC bureaublad", open_tigervnc, ACCENT_PINAS)
        self._sep(body)
        # 16 juli 2026: vaste knop "Schijven verbinden" hier weggehaald op
        # verzoek van Frans - die staat al als blauwe balk boven in beeld en
        # als knop in Status & details, allebei ALLEEN zichtbaar als Y:/Z:
        # niet in orde zijn (zelfde patroon als de scripts-uploaden melding).

        # EXTERNE HDD
        self._sectie(body, "EXTERNE HDD")
        self.lbl_seagate = tk.Label(body, text="● Status ophalen...",
                                     font=("Segoe UI", 9), bg=BG, fg=YELLOW, anchor="w")
        self.lbl_seagate.pack(fill="x", pady=(2,6))
        f_sea = tk.Frame(body, bg=BG)
        f_sea.pack(fill="x", pady=4)
        self.btn_aan = tk.Button(f_sea, text="🔌  Aanzetten", command=self._seagate_aan,
                                  bg=WARN, fg="#ffffff", font=("Segoe UI", 10),
                                  relief="flat", cursor="hand2", padx=10, pady=8,
                                  borderwidth=0, highlightthickness=0)
        self.btn_aan.pack(side="left", fill="x", expand=True, padx=(0,4))
        self.btn_uit = tk.Button(f_sea, text="⏹  Uitzetten", command=self._seagate_uit,
                                  bg=PANEL2, fg=FG, font=("Segoe UI", 10),
                                  relief="flat", cursor="hand2", padx=10, pady=8,
                                  borderwidth=0, highlightthickness=0, state="disabled")
        self.btn_uit.pack(side="left", fill="x", expand=True)
        self._sep(body)

        # BACKUP - 16 juli 2026: van vlakke PANEL2-grijs naar de eigen
        # productkleur (ACCENT_PIBACKUP, groen) - Frans vroeg om frissere
        # kleuren i.p.v. alle hoofdmenu-knoppen in dezelfde grijsblauwe tint.
        self._sectie(body, "BACKUP")
        self._btn(body, "🗂  Backup Beheer", self._open_backup_overzicht, ACCENT_PIBACKUP)
        self._sep(body)

        # ADDONS - eigen productkleur (ACCENT_PIADDONS, amber) - 16 juli 2026
        # herzien: eerst ACCENT_PINAS (blauw, zelfde als de rest), maar Frans
        # wilde dat Addons net als Backup zijn eigen "sfeer" heeft, dus nu een
        # eigen categorie i.p.v. hetzelfde blauw als alle andere knoppen.
        self._sectie(body, "ADDONS")
        self._btn(body, "🧩  Addons Beheer", self._open_addons_beheer, ACCENT_PIADDONS)
        self._sep(body)

        # BEHEER - 16 juli 2026: Herstel & Acties en Onderhoud
        # gepromoveerd van footer naar hoofdscherm; Controles is nieuw.
        # Status verhuisde de andere kant op, naar de footer - zie hieronder.
        # 16 juli 2026 (vervolg): Structuurcheck + Opruimen verhuisd naar
        # Controles (het waren toch controles) - daarmee viel NAS Map Beheer
        # weg als los hoofdmenu-item. "Installatie & Herstel" (voorheen in
        # de footer) staat nu op zijn plek.
        # 16 juli 2026 (kleuren herzien): eerst ACCENT_PICONTROL (paars) voor
        # deze 3 knoppen, maar 3x identiek paars naast elkaar bleek precies
        # het probleem waar Frans op wees. ACCENT_PICONTROL is nu gereserveerd
        # voor de vensterkoppen zelf (branding, 1x per venster) - gewone
        # knoppen als deze gebruiken ACCENT_PINAS, de "kern"-kleur voor
        # algemeen suite-beheer (zelfde categorie als Verbinden hierboven).
        self._sectie(body, "BEHEER")
        self._btn(body, "🔧  Installatie & Herstel", self._open_installatie, ACCENT_PINAS)
        self._btn(body, "🧪  Controles", self._open_controle_beheer, ACCENT_PINAS)
        self._btn(body, "🔧  Onderhoud", self._open_setup, ACCENT_PINAS)
        self._sep(body)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = tk.Frame(self, bg=PANEL, pady=10)
        footer.pack(fill="x")
        tk.Button(footer, text="❓  Help", command=self._open_help,
                  bg=PANEL2, fg=FG, font=("Segoe UI", 9), relief="flat",
                  cursor="hand2", padx=14, pady=6,
                  borderwidth=0, highlightthickness=0).pack(side="left", padx=10)
        tk.Button(footer, text="📊  Status", command=self._open_status,
                  bg=ACCENT_PINAS, fg="#ffffff", font=("Segoe UI", 9, "bold"), relief="flat",
                  cursor="hand2", padx=12, pady=4,
                  borderwidth=0, highlightthickness=0).pack(side="left", padx=4)
        # Setup status bolletje
        self.lbl_setup_status = tk.Label(footer, text="●",
                  font=("Segoe UI", 10), bg=PANEL, fg=DIM)
        self.lbl_setup_status.pack(side="left", padx=2)
        tk.Label(footer, text=f"Pi NAS Menu  ·  Pi 5  ·  bijgewerkt: {BIJGEWERKT}",
                 font=("Segoe UI", 9), bg=PANEL, fg=DIM).pack(side="right", padx=10)

        # Initieel status dashboard vullen
        self._bouw_pc_status()
        self._ververs_pc_checks()   # eerste echte check in de achtergrond
        self._bouw_pi_status_leeg()
        # Controleer wachtwoord bij opstarten
        self.after(2000, self._check_wachtwoord_bij_start)
        # Pi sync check parallel starten na 3 sec (ping heeft dan al gedraaid)
        self.after(3000, self._start_sync_check)

    # ── Status samenvatting (compact, hoofdvenster) ───────────────────────────
    def _bouw_pc_status(self):
        """Bouwt/werkt de compacte statussamenvatting in het hoofdvenster bij.

        Voorheen werden bij elke aanroep (elke 20 sec, plus na elke
        achtergrondcheck) ALLE widgets vernietigd en opnieuw aangemaakt.
        Dat gaf zichtbaar knipperen. Nu worden de vaste rijen (PC-status,
        Pi-status, Simulator, Sync) één keer aangemaakt en bij volgende
        aanroepen alleen hun tekst/kleur bijgewerkt — geen destroy/rebuild
        meer voor onderdelen die toch blijven bestaan. Alleen de
        conditionele elementen (Nextcloud-rij, upload-knop, herstel-knop)
        worden nog steeds aan/afgebroken, omdat die soms wel en soms niet
        zichtbaar moeten zijn.
        """
        # PC checks: lees uit de cache die de achtergrondthread vult.
        # Zo bevriest het hoofdvenster NOOIT op een trage/ontbrekende Z:.
        checks = getattr(self, '_pc_checks', None)
        pc_bezig = checks is None
        if pc_bezig:
            # Nog geen resultaat binnen: toon 'controleren...' i.p.v. stil hangen.
            pc_items = []
            pc_ok = False
            pc_deels = True          # geel = bezig
            y_ok = z_ok = False
            h_ok = False
            docker_ok = False
        else:
            pc_items = [checks.get('putty', False), checks.get('vnc', False),
                        checks.get('pibackup', False),
                        checks.get('y', False), checks.get('z', False)]
            pc_ok = all(pc_items)
            pc_deels = any(pc_items) and not pc_ok
            y_ok = checks.get('y', False)
            z_ok = checks.get('z', False)
            # Spiegel Backup (H:) is optioneel (niet elke installatie heeft
            # 'm) en telt BEWUST niet mee in pc_ok/pc_items - een tijdelijk
            # ontkoppelde spiegel-van-de-backup mag de hoofdstatus niet rood
            # laten lijken, dat is minder kritiek dan Opslag/Backup zelf.
            h_ok = checks.get('h', False)
            docker_ok = checks.get('docker', False)
        schijf_ok = y_ok and z_ok

        # Pi status (gebruik laatste bekende staat)
        pi_ok = getattr(self, '_pi_status_ok', None)

        eerste_keer = not hasattr(self, '_status_rij_widgets')
        if eerste_keer:
            self._status_rij_widgets = {}

        def _status_rij(key, parent, tekst, ok, deels=False, cmd=None, uitleg=None):
            kleur = OK_C if ok and not deels else (WARN if deels else ERR_C)
            cursor = "hand2" if (cmd or uitleg) else ""

            def _actie(e=None):
                if cmd:
                    cmd()
                elif uitleg:
                    s = "✅ OK" if ok and not deels else ("⚠ Gedeeltelijk" if deels else "❌ Probleem")
                    messagebox.showinfo(tekst.split(" —")[0].strip(), f"{s}\n\n{uitleg}")

            if key in self._status_rij_widgets:
                # Bestaande rij — alleen bijwerken, niet opnieuw aanmaken.
                w = self._status_rij_widgets[key]
                w['rij'].config(cursor=cursor)
                w['bol'].config(fg=kleur)
                w['lbl'].config(text=tekst)
                # Klik-handler vervangen (cmd/uitleg kunnen per aanroep wijzigen)
                w['rij'].unbind("<Button-1>")
                w['lbl'].unbind("<Button-1>")
                if cmd or uitleg:
                    w['rij'].bind("<Button-1>", _actie)
                    w['lbl'].bind("<Button-1>", _actie)
                return

            # Eerste keer — widgets aanmaken en onthouden.
            rij = tk.Frame(parent, bg=BG, cursor=cursor)
            rij.pack(fill="x", pady=3)
            bol = tk.Label(rij, text="●", font=("Segoe UI", 11),
                     bg=BG, fg=kleur, width=2)
            bol.pack(side="left")
            lbl = tk.Label(rij, text=tekst, font=("Segoe UI", 10),
                     bg=BG, fg=FG, anchor="w")
            lbl.pack(side="left", fill="x", expand=True)
            if uitleg:
                tk.Label(rij, text="ℹ", font=("Segoe UI", 9),
                         bg=BG, fg=DIM).pack(side="right", padx=4)
            if cmd or uitleg:
                rij.bind("<Button-1>", _actie)
                lbl.bind("<Button-1>", _actie)
            self._status_rij_widgets[key] = {'rij': rij, 'bol': bol, 'lbl': lbl}

        _status_rij("pc",
                    self.status_samen_frame,
                    "PC — software & schijven  (controleren…)" if pc_bezig
                        else "PC — software & schijven",
                    pc_ok, pc_deels, self._open_status,
                    uitleg=("Bezig met controleren van PuTTY, TigerVNC, Sync & Backup en Opslag/Backup…"
                            if pc_bezig else
                            "PuTTY, TigerVNC, Sync & Backup en de Opslag/Backup-schijven zijn beschikbaar."
                            if pc_ok else
                            "Eén of meer onderdelen ontbreken.\n\n"
                            "Klik voor details → controleer via Beheer → Windows onderdelen."))
        if _heeft_spiegel_backup():
            _status_rij("h",
                        self.status_samen_frame,
                        f"Spiegel Backup — {_spiegel_letter()}: (controleren…)" if pc_bezig
                            else f"Spiegel Backup — {_spiegel_letter()}:",
                        h_ok, False, self._open_status,
                        uitleg=("Bezig met controleren van de Spiegel Backup-schijf (backup van de backup)…"
                                if pc_bezig else
                                "Spiegel Backup is verbonden."
                                if h_ok else
                                f"Spiegel Backup ({_spiegel_letter()}:) is niet verbonden - vaak omdat de schijf (nog) niet "
                                "aan de Pi hangt. Klik 'Schijven verbinden' als de schijf wel aan staat."))
        _status_rij("pi",
                    self.status_samen_frame,
                    "Raspberry Pi — services",
                    pi_ok is True,
                    pi_ok is None,
                    self._open_status,
                    uitleg=("Samba, Nextcloud, FileBrowser en Cockpit zijn actief op de Pi."
                            if pi_ok is True else
                            "Pi niet bereikbaar of services nog niet gecheckt.\n\n"
                            "Controleer of de Pi aan staat en verbonden is met het netwerk."
                            if pi_ok is None else
                            "Eén of meer Pi services draaien niet.\n\n"
                            "Klik voor details → gebruik Diagnose voor meer informatie."))

        # Pi scripts sync status
        sync = getattr(self, '_pi_sync_status', 'onbekend')
        sync_tekst = {
            'ok':       "Pi scripts — up-to-date",
            'oranje':   "Pi scripts — verschil gevonden",
            'rood':     "Pi scripts — upload nodig (lokaal nieuwer)",
            'bezig':    "Pi scripts — bezig met controleren...",
            'onbekend': "Pi scripts — onbekend",
        }.get(sync, "Pi scripts — onbekend")
        sync_kleur = {
            'ok':       OK_C,
            'oranje':   YELLOW,
            'rood':     ERR_C,
            'bezig':    DIM,
            'onbekend': DIM,
        }.get(sync, DIM)

        details = getattr(self, '_pi_sync_details', [])
        def _toon_sync_info(e=None, d=details):
            if sync == 'ok':
                messagebox.showinfo("Pi scripts — sync",
                    "✅ Alle scripts zijn up-to-date.\n\n"
                    "Alle 16 bestanden die nas_upload.bat naar de Pi zet zijn "
                    "gecheckt (MD5-vergelijking lokaal vs Pi).\n\n"
                    "Let op - dit dekt NIET de Addons-scripts (Mobiele "
                    "statuspagina, Pi-hole, Nextcloud, ZeroTier, Vaultwarden): die "
                    "gebruiken nas_upload.bat niet en worden hier dus ook niet "
                    "gecheckt. Addons Beheer uploadt de laatste lokale versie "
                    "automatisch elke keer dat je op 'Installeren' klikt - "
                    "daar hoef je dus niets los voor te doen.")
            elif d:
                messagebox.showinfo("Pi scripts — upload nodig",
                    "❌ Lokale versies zijn nieuwer dan de Pi:\n\n" +
                    "\n".join(f"  • {x}" for x in d) +
                    "\n\nWat te doen:\n"
                    "  Klik op 'Uploaden naar Pi' in het hoofdvenster\n"
                    "  of ga naar Beheer → Geavanceerd → Uploaden naar Pi.\n\n"
                    "(Deze lijst gaat alleen over de 16 bestanden die "
                    "nas_upload.bat beheert. Addons-scripts staan hier nooit "
                    "bij - die worden los geupload zodra je op 'Installeren' "
                    "klikt in Addons Beheer.)")
            elif sync == 'bezig':
                messagebox.showinfo("Pi scripts — bezig",
                    "⏳ De controle loopt nog (SSH-verbinding + MD5-vergelijking "
                    "van 16 bestanden) - dit duurt meestal een paar seconden.\n\n"
                    "Blijft dit lang zo staan, dan is de Pi vermoedelijk niet "
                    "bereikbaar via SSH. Controleer via Diagnose uitvoeren.")
            else:
                messagebox.showinfo("Pi scripts — onbekend",
                    "⚪ Sync status kon niet bepaald worden.\n\n"
                    "Mogelijke oorzaken:\n"
                    "  • Pi is niet bereikbaar via SSH (time-out)\n"
                    "  • SSH sleutel werkt niet\n\n"
                    "Tip: controleer de Pi verbinding via Diagnose uitvoeren, of "
                    "klik op 'Sync opnieuw controleren' in het Status-scherm.")

        if "sync" in self._status_rij_widgets:
            w = self._status_rij_widgets["sync"]
            w['bol'].config(fg=sync_kleur)
            w['lbl'].config(text=sync_tekst)
            w['rij'].config(cursor="hand2")
            w['rij'].unbind("<Button-1>"); w['lbl'].unbind("<Button-1>")
            w['rij'].bind("<Button-1>", _toon_sync_info)
            w['lbl'].bind("<Button-1>", _toon_sync_info)
        else:
            rij_sync = tk.Frame(self.status_samen_frame, bg=BG, cursor="hand2")
            rij_sync.pack(fill="x", pady=3)
            bol_sync = tk.Label(rij_sync, text="●", font=("Segoe UI", 11),
                     bg=BG, fg=sync_kleur, width=2)
            bol_sync.pack(side="left")
            lbl_sync = tk.Label(rij_sync, text=sync_tekst, font=("Segoe UI", 10),
                     bg=BG, fg=FG, anchor="w")
            lbl_sync.pack(side="left", fill="x", expand=True)
            rij_sync.bind("<Button-1>", _toon_sync_info)
            lbl_sync.bind("<Button-1>", _toon_sync_info)
            self._status_rij_widgets["sync"] = {'rij': rij_sync, 'bol': bol_sync, 'lbl': lbl_sync}

        # Upload-knop: conditioneel zichtbaar — alleen aan/afbreken bij wijziging.
        upload_moet_tonen = sync in ('oranje', 'rood')
        upload_was_getoond = getattr(self, '_upload_btn_getoond', False)
        if upload_moet_tonen != upload_was_getoond:
            if hasattr(self, '_upload_btn') and self._upload_btn.winfo_exists():
                self._upload_btn.destroy()
            if upload_moet_tonen:
                _upload_btn = tk.Button(self.status_samen_frame,
                          text="⬆  Upload naar Pi — scripts bijwerken",
                          font=("Segoe UI", 9, "bold"),
                          bg=ACCENT_PINAS, fg="#ffffff",
                          relief="flat", cursor="hand2",
                          borderwidth=0, pady=5)

                def _doe_upload(btn=_upload_btn):
                    btn.destroy()
                    self._upload_btn_getoond = False
                    # Direct groen — upload werkt alles bij
                    self._pi_sync_status = 'ok'
                    self._pi_sync_details = []
                    self._bouw_pc_status()
                    self._upload_naar_pi()

                _upload_btn.configure(command=_doe_upload)
                _upload_btn.pack(fill="x", pady=(8,0))
                self._upload_btn = _upload_btn
            self._upload_btn_getoond = upload_moet_tonen

        # Herstel-knop bij schijfproblemen — idem, conditioneel. Z: telt
        # alleen mee als de HDD niet bewust uitstaat (4 augustus 2026,
        # Frans: knop verscheen ook meteen na het bewust uitzetten van de
        # HDD, alsof dat een fout was die "hersteld" moest worden).
        hdd_bewust_uit = getattr(self, '_extern_hdd_aan', True) is False
        herstel_moet_tonen = (not y_ok or (not z_ok and not hdd_bewust_uit)
                               or (_heeft_spiegel_backup() and not h_ok))
        herstel_was_getoond = getattr(self, '_herstel_btn_getoond', False)
        if herstel_moet_tonen != herstel_was_getoond:
            if hasattr(self, '_herstel_btn') and self._herstel_btn.winfo_exists():
                self._herstel_btn.destroy()
            if herstel_moet_tonen:
                btn_herstel = tk.Button(
                    self.status_samen_frame,
                    text="🔌  Schijven verbinden",
                    font=("Segoe UI", 9, "bold"),
                    bg=WARN, fg="#ffffff",
                    relief="flat", cursor="hand2",
                    borderwidth=0, pady=5,
                    command=self._verbind_schijven)
                btn_herstel.pack(fill="x", pady=(4,0))
                self._herstel_btn = btn_herstel
            self._herstel_btn_getoond = herstel_moet_tonen

        # Setup bolletje bijwerken
        setup_ok = pc_ok and docker_ok
        self.lbl_setup_status.config(
            fg=OK_C if setup_ok else (WARN if pc_deels else ERR_C))

        # Volgende ronde: draai de (trage) checks in de achtergrond en
        # ververs daarna. Nooit blokkerend op de tekenthread.
        self.after(20000, self._ververs_pc_checks)

    def _ververs_pc_checks(self):
        """Draait de PC-checks (net use Y:/Z:, PuTTY, VNC, Sync, Docker) in een
        achtergrondthread en werkt daarna het statuspaneel bij. Zo bevriest het
        venster niet als Z: traag is of ontbreekt."""
        if getattr(self, '_pc_checks_bezig', False):
            return
        self._pc_checks_bezig = True

        def _werk():
            resultaat = {}
            try:
                resultaat['putty']    = check_putty()
                resultaat['vnc']      = check_tigervnc()
                resultaat['pibackup'] = check_pibackup()
                resultaat['docker']   = check_docker_desktop()
                resultaat['y']        = check_share("Opslag", _opslag_letter(), PI_IP)
                resultaat['z']        = check_share("Backup", _backup_letter(), PI_IP)
                if _heeft_spiegel_backup():
                    resultaat['h'] = check_share("SpiegelBackup", _spiegel_letter(), PI_IP)
            except Exception:
                pass

            def _klaar():
                self._pc_checks = resultaat
                self._pc_checks_bezig = False
                try:
                    self._bouw_pc_status()
                except tk.TclError:
                    pass
            try:
                self.after(0, _klaar)
            except Exception:
                self._pc_checks_bezig = False

        threading.Thread(target=_werk, daemon=True).start()

    def _verbind_schijven(self):
        """Koppelt de NAS-netwerkschijven schoon opnieuw: eerst een eventuele
        kapotte koppeling weg (net use /delete), dan een verse koppeling ZONDER
        /persistent (die veroorzaakt juist de 'onthouden maar dode' koppelingen).
        Gebruikt het opgeslagen NAS-wachtwoord; geen register/UAC nodig. Draait
        in de achtergrond zodat het venster niet bevriest."""
        if getattr(self, '_verbind_bezig', False):
            return
        paren = _schijf_config()
        ww = _get_nas_wachtwoord()
        if not ww:
            from tkinter import simpledialog
            ww = simpledialog.askstring(
                "NAS-wachtwoord",
                "Wachtwoord voor gebruiker 'pi' (wordt onthouden):",
                show="*", parent=self)
            if not ww:
                return
            try:
                set_wachtwoord(ww, "samba")
            except Exception:
                pass
        self._verbind_bezig = True
        letters = ", ".join(f"{l}:" for l in paren)
        try:
            self.lbl_ping.config(text=f"● Schijven verbinden ({letters})…", fg=WARN)
        except Exception:
            pass

        def _werk():
            resultaat = {}
            # Eerst ALLE losse verbindingen naar dezelfde shares opruimen,
            # ongeacht IP (lokaal of ZeroTier) - voorkomt het 'meerdere
            # gebruikersnamen'-conflict als er nog een losse testverbinding
            # openstaat naast de vaste Y:/Z:-koppeling.
            _opruim_losse_verbindingen(set(paren.values()))
            for letter, share in paren.items():
                try:
                    subprocess.run(["net", "use", f"{letter}:", "/delete", "/y"],
                        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
                        timeout=8)
                except Exception:
                    pass
                args = ["net", "use", f"{letter}:", f"\\\\{PI_IP}\\{share}", "/user:pi", ww]
                try:
                    r = subprocess.run(args, capture_output=True, text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
                    ok = (r.returncode == 0)
                    melding = (r.stderr or r.stdout or "").strip()
                except Exception as e:
                    ok = False
                    melding = str(e)

                # De letter kan bezet zijn door iets anders dat geen PiNAS-
                # verbinding is (dus niet opgeruimd door _opruim_losse_
                # verbindingen hierboven) - probeer dan automatisch een
                # vrije letter, en onthoud die in picontrol.cfg zodat
                # latere checks/verbindingen dezelfde letter blijven
                # gebruiken in plaats van het steeds opnieuw te ontdekken.
                gebruikte_letter = letter
                if not ok:
                    for alt in ["W", "V", "U", "T", "X"]:
                        if alt == letter or alt in paren:
                            continue
                        alt_args = ["net", "use", f"{alt}:", f"\\\\{PI_IP}\\{share}", "/user:pi", ww]
                        try:
                            r2 = subprocess.run(alt_args, capture_output=True, text=True,
                                creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
                            if r2.returncode == 0:
                                ok = True
                                melding = ""
                                gebruikte_letter = alt
                                _onthoud_schijfletter(share, alt)
                                break
                        except Exception:
                            continue

                resultaat[gebruikte_letter] = (ok, melding)

            def _klaar():
                self._verbind_bezig = False
                gelukt = [l for l, (ok, _) in resultaat.items() if ok]
                mislukt = {l: m for l, (ok, m) in resultaat.items() if not ok}
                if not mislukt:
                    messagebox.showinfo(
                        "Schijven verbonden",
                        "Verbonden: " + ", ".join(f"{l}:" for l in gelukt) +
                        "\n\nZe zijn nu zichtbaar in Verkenner.")
                else:
                    tekst = ("Verbonden: " +
                             (", ".join(f"{l}:" for l in gelukt) or "geen") + "\n\n"
                             "Niet gelukt:\n" +
                             "\n".join(f"  {l}:  {m}" for l, m in mislukt.items()) +
                             "\n\nControleer of de Pi aan staat en de HDD gemount is.")
                    messagebox.showwarning("Schijven verbinden", tekst)
                self._ververs_pc_checks()   # oranje balk / status direct bijwerken

            try:
                self.after(0, _klaar)
            except Exception:
                self._verbind_bezig = False

        threading.Thread(target=_werk, daemon=True).start()

    def _bouw_pi_status_leeg(self):
        self._pi_statussen = []
        self._pi_status_ok = None
        self._sp_status = "onbekend"
        self._pihole_status = "onbekend"
        self._zerotier_status = "onbekend"
        self._vw_status = "onbekend"
        self._printer_status = "onbekend"
        self._dashboard_status = "onbekend"
        self._addon_verouderd = []

    def _bouw_pi_status(self, statussen):
        # Sla Pi status op voor samenvatting in hoofdvenster
        self._pi_statussen = statussen
        self._pi_status_ok = all(ok for _, ok in statussen) if statussen else None
        # Ververs samenvatting in hoofdvenster
        self._bouw_pc_status()
        # Ververs status venster als open
        if hasattr(self, '_status_win') and self._status_win and self._status_win.winfo_exists():
            self._vul_status_venster()

    def _ververs_pi_status(self):
        def check():
            resultaten = []
            # 4 augustus 2026: SSH-commando + parsing verhuisd naar de
            # gedeelde module pinas_pi_status.py - dit was voorheen een
            # eigen kopie, apart van pinas_addons_beheer.pyw's versie,
            # en die twee liepen uit de pas (zie de Dashboard-status-bug
            # van vandaag). Nu 1 bron voor beide schermen.
            import pinas_pi_status
            try:
                r = pinas_pi_status.haal_pi_status(PI_IP)
                svc_map = {}
                addon_hashes = {}
                if r["bereikbaar"]:
                    svc_map = {
                        "smbd": r["smbd"], "nextcloud": r["nextcloud"],
                        "filebrowser": r["filebrowser"], "cockpit": r["cockpit"],
                        "seagate-web": r["seagate-web"],
                        "backup_mount": r["backup_mount"],
                    }
                    for k in ("nextcloud", "pihole", "zerotier", "vaultwarden",
                              "statuspagina", "printer", "dashboard"):
                        addon_hashes[k] = r[f"hash_{k}"]
                sp_status = r["statuspagina"] if r["bereikbaar"] else "onbekend"
                pihole_status = r["pihole"] if r["bereikbaar"] else "onbekend"
                zerotier_status = r["zerotier"] if r["bereikbaar"] else "onbekend"
                vw_status = r["vaultwarden"] if r["bereikbaar"] else "onbekend"
                printer_status = r["printer"] if r["bereikbaar"] else "onbekend"
                dashboard_status = r["dashboard"] if r["bereikbaar"] else "onbekend"
                # "unknown" (de neutrale waarde van de gedeelde module als
                # de Pi wel bereikbaar was maar deze ene regel niet in de
                # uitvoer stond) -> "onbekend", zelfde Nederlandse label
                # als voorheen.
                if sp_status == "unknown": sp_status = "onbekend"
                if pihole_status == "unknown": pihole_status = "onbekend"
                if zerotier_status == "unknown": zerotier_status = "onbekend"
                if vw_status == "unknown": vw_status = "onbekend"
                if printer_status == "unknown": printer_status = "onbekend"
                if dashboard_status == "unknown": dashboard_status = "onbekend"
                if svc_map:
                    for svc_key, naam in [
                        ("smbd",        "Samba"),
                        ("nextcloud",   "Nextcloud"),
                        ("filebrowser", "FileBrowser"),
                        ("cockpit",     "Cockpit"),
                        ("seagate-web", "Externe HDD svc"),
                        ("backup_mount","Backup-schijf gemount"),
                    ]:
                        resultaten.append((naam, svc_map.get(svc_key, False)))
                # Geen bruikbare SSH-output -> resultaten blijft leeg = 'onbekend'
            except Exception:
                resultaten = []   # SSH mislukt: status ONBEKEND, niet "alles uit"
                addon_hashes = {}
                sp_status = "onbekend"
                pihole_status = "onbekend"
                zerotier_status = "onbekend"
                vw_status = "onbekend"
                printer_status = "onbekend"
                dashboard_status = "onbekend"

            # Welke add-ons zijn geinstalleerd EN wijken af van het lokale
            # bestand? Alleen dan is een waarschuwing zinvol - een add-on
            # die niet geinstalleerd is, hoeft ook niet bijgewerkt te
            # worden (30 juli 2026).
            addon_geinstalleerd = {
                "nextcloud": svc_map.get("nextcloud", False),
                "pihole": pihole_status in ("active", "stopped"),
                "zerotier": zerotier_status in ("active", "stopped"),
                "vaultwarden": vw_status in ("active", "stopped"),
                "statuspagina": sp_status in ("active", "stopped"),
                "printer": printer_status in ("active", "stopped"),
                "dashboard": dashboard_status in ("active", "stopped"),
            }
            verouderd = []
            for key, naam in [
                ("nextcloud", "Nextcloud"), ("pihole", "Pi-hole"),
                ("zerotier", "ZeroTier"), ("vaultwarden", "Vaultwarden"),
                ("statuspagina", "Mobiele statuspagina"), ("printer", "Printserver"),
                ("dashboard", "PiNAS Dashboard"),
            ]:
                if not addon_geinstalleerd.get(key):
                    continue
                pi_hash = addon_hashes.get(key)
                if pi_hash in (None, "geen"):
                    continue   # onbekend/nog nooit geinstalleerd met deze functie - geen valse waarschuwing
                lokaal_hash = _lokale_addon_hash(key)
                if lokaal_hash and pi_hash != lokaal_hash:
                    verouderd.append(naam)

            self._sp_status = sp_status
            self._pihole_status = pihole_status
            self._zerotier_status = zerotier_status
            self._vw_status = vw_status
            self._printer_status = printer_status
            self._dashboard_status = dashboard_status
            self._addon_verouderd = verouderd
            self.after(0, lambda: self._bouw_pi_status(resultaten))
        threading.Thread(target=check, daemon=True).start()
        self.after(60000, self._ververs_pi_status)

    # -- Sync --────────────────────────────────────────────────────────────
    def _run_simulator_bat(self, naam):
        """Zoek simulator bat in PiNAS map — autonoom."""
        nas_root = _nas_root()
        up = os.environ.get("USERPROFILE", "")
        kandidaten = [
            os.path.join(_script_dir(), naam),
            os.path.join(nas_root, "PiServer", naam),
            os.path.join(nas_root, "Gedeeld", naam),
            os.path.join("C:\\", "PiNAS", "PiServer", naam),
            os.path.join(up, "OneDrive", "Documenten", "Desktop", "NAS", "PiServer", naam),
            os.path.join(up, "OneDrive", "Documents", "Desktop", "NAS", "PiServer", naam),
            bat_pad(naam),
        ]
        gevonden = [p for p in kandidaten if p and os.path.exists(p)]
        if gevonden:
            subprocess.Popen(["cmd", "/c", gevonden[0]],
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            msg = (f"{naam} niet gevonden.\n\n"
                   f"Gezocht in:\n" +
                   "\n".join(f"  {p}" for p in kandidaten if p))
            messagebox.showerror("Niet gevonden", msg)

    # ── Setup venster ─────────────────────────────────────────────────────────

    def _open_sdcard_wizard(self, parent=None):
        """Stap-voor-stap wizard: SD-kaart maken en Pi opstarten."""
        wiz = tk.Toplevel(self)
        wiz.title("SD-kaart wizard — Pi NAS Suite")
        wiz.configure(bg=BG)
        wiz.resizable(False, False)
        wiz.geometry("520x500")
        try: wiz.iconbitmap(_ico_pad())
        except: pass
        if parent:
            wiz.transient(parent)
        wiz.grab_set()
        wiz.update_idletasks()
        x = self.winfo_x() + (self.winfo_width()  - 520) // 2
        y = self.winfo_y() + (self.winfo_height() - 500) // 2
        wiz.geometry(f"+{x}+{y}")

        stop_ping = threading.Event()
        huidige_stap = [1]

        # ── Header ────────────────────────────────────────────
        hdr = tk.Frame(wiz, bg=ACCENT_PICONTROL, pady=12)
        hdr.pack(fill="x")
        lbl_stap  = tk.Label(hdr, text="Stap 1 van 4",
                             font=("Segoe UI", 10, "bold"), bg=ACCENT_PICONTROL, fg="#ffffff")
        lbl_stap.pack()
        lbl_titel = tk.Label(hdr, text="",
                             font=("Segoe UI", 9), bg=ACCENT_PICONTROL, fg=ACCENT_LICHT)
        lbl_titel.pack()

        # ── Content ───────────────────────────────────────────
        content = tk.Frame(wiz, bg=BG, padx=20, pady=16)
        content.pack(fill="both", expand=True)

        # ── Navigatie ─────────────────────────────────────────
        nav = tk.Frame(wiz, bg=PANEL, pady=10)
        nav.pack(fill="x", side="bottom")
        btn_terug = tk.Button(nav, text="Terug",
                              bg=PANEL2, fg=FG, font=("Segoe UI", 9),
                              relief="flat", cursor="hand2", pady=7,
                              borderwidth=0, state="disabled")
        btn_terug.pack(side="left", padx=10)
        btn_stop = tk.Button(nav, text="Annuleren",
                             bg=PANEL2, fg=FG, font=("Segoe UI", 9),
                             relief="flat", cursor="hand2", pady=7,
                             borderwidth=0,
                             command=lambda: [stop_ping.set(), wiz.destroy()])
        btn_stop.pack(side="left", padx=4)
        btn_next = tk.Button(nav, text="Volgende →",
                             bg=BLUE, fg="#ffffff", font=("Segoe UI", 10, "bold"),
                             relief="flat", cursor="hand2", pady=7,
                             borderwidth=0)
        btn_next.pack(side="right", padx=10)

        def wis():
            for w in content.winfo_children():
                w.destroy()

        def lbl(tekst, bold=False, kleur=None):
            kleur = kleur or FG
            f = ("Segoe UI", 9, "bold") if bold else ("Segoe UI", 9)
            tk.Label(content, text=tekst, font=f, bg=BG,
                     fg=kleur, anchor="w").pack(fill="x", pady=1)

        def stap1():
            huidige_stap[0] = 1
            lbl_stap.config(text="Stap 1 van 4")
            lbl_titel.config(text="Voorbereiding")
            wis()
            btn_terug.config(state="disabled")
            btn_next.config(text="Volgende →", state="normal",
                           bg=BLUE, command=stap2)
            lbl("SD-kaart voorbereiden", bold=True)
            tk.Frame(content, bg=PANEL2, height=1).pack(fill="x", pady=6)
            for t in [
                "1.  Stop een lege SD-kaart (minimaal 16 GB) in je pc.",
                "2.  Aanbevolen: Raspberry Pi 5 met minimaal 32 GB A1/A2 kaart.",
                "",
                "Pi Imager is meegeleverd in de installatie map.",
                "Klik Volgende als de SD-kaart in de pc zit.",
            ]:
                lbl(t, kleur=DIM if not t else FG)

        def stap2():
            huidige_stap[0] = 2
            lbl_stap.config(text="Stap 2 van 4")
            lbl_titel.config(text="SD-kaart flashen")
            wis()
            btn_terug.config(state="normal", command=stap1)
            btn_next.config(text="SD-kaart is klaar →", state="disabled",
                           bg=PANEL2)

            lbl("Pi Imager instellen en flashen", bold=True)
            tk.Frame(content, bg=PANEL2, height=1).pack(fill="x", pady=6)

            # Imager starten knop
            def start_imager():
                imager = next((p for p in [
                    os.path.join(_nas_root(), "Installatie", "imager_2.0.7.exe"),
                    os.path.join(_script_dir(), "imager_2.0.7.exe"),
                    os.path.join("C:\\", "PiNAS", "Installatie", "imager_2.0.7.exe"),
                ] if os.path.exists(p)), None)
                if imager:
                    subprocess.Popen([imager])
                else:
                    import webbrowser
                    webbrowser.open("https://www.raspberrypi.com/software/")
                    messagebox.showinfo("Pi Imager",
                        "Pi Imager niet gevonden.\n"
                        "Browser geopend voor download.")

            tk.Button(content, text="▶  Pi Imager starten",
                      command=start_imager,
                      bg=ACCENT_PINAS, fg="#ffffff", font=("Segoe UI", 10, "bold"),
                      relief="flat", cursor="hand2", pady=8,
                      borderwidth=0).pack(fill="x", pady=(0,10))

            lbl("Stel het volgende in via Instellingen bewerken:", bold=True)

            checks_def = [
                ("Raspberry Pi OS (64-bit) gekozen", True),
                ("Hostname: piNAS ingesteld", True),
                ("SSH inschakelen aangevinkt", True),
                ("Gebruikersnaam: pi", True),
                ("Wachtwoord ingesteld (onthoud dit!)", True),
                ("WiFi ingesteld (optioneel)", False),
                ("SD-kaart geflasht en uitgeworpen", True),
            ]
            chk_vars = []

            def update_next(*_):
                verplicht = [v for v, (_, vp) in zip(chk_vars, checks_def) if vp]
                if all(v.get() for v in verplicht):
                    btn_next.config(state="normal", bg=BLUE)
                else:
                    btn_next.config(state="disabled", bg=PANEL2)

            for tekst, verplicht in checks_def:
                var = tk.BooleanVar(master=wiz)
                var.trace_add("write", update_next)
                chk_vars.append(var)
                rij = tk.Frame(content, bg=BG)
                rij.pack(fill="x", pady=1)
                tk.Checkbutton(rij, text=tekst, variable=var,
                               font=("Segoe UI", 9), bg=BG, fg=FG,
                               selectcolor=PANEL2, activebackground=BG,
                               anchor="w").pack(side="left")
                if verplicht:
                    tk.Label(rij, text=" *", font=("Segoe UI", 9, "bold"),
                             bg=BG, fg=ERR_C).pack(side="left")

            btn_next.config(command=stap3)

        def stap3():
            huidige_stap[0] = 3
            lbl_stap.config(text="Stap 3 van 4")
            lbl_titel.config(text="Pi opstarten")
            wis()
            btn_terug.config(state="normal", command=stap2)
            btn_next.config(text="Pi is aangezet →", state="normal",
                           bg=BLUE, command=stap4)
            lbl("SD-kaart in de Pi en Pi aanzetten", bold=True)
            tk.Frame(content, bg=PANEL2, height=1).pack(fill="x", pady=6)
            for t in [
                "1.  Verwijder de SD-kaart uit de pc.",
                "2.  Stop de SD-kaart in de Raspberry Pi.",
                "3.  Sluit netwerkkabel aan (aanbevolen).",
                "4.  Sluit voeding aan — Pi start automatisch op.",
                "",
                "Wacht tot de groene LED op de Pi knippert.",
                "De eerste opstart duurt circa 60-90 seconden.",
                "",
                "Klik Volgende als de Pi aangezet is.",
            ]:
                lbl(t, kleur=DIM if not t else FG)

        def stap4():
            huidige_stap[0] = 4
            lbl_stap.config(text="Stap 4 van 4")
            lbl_titel.config(text="Wachten op Pi...")
            wis()
            btn_terug.config(state="disabled")
            btn_next.config(state="disabled", text="Wachten...", bg=PANEL2)

            lbl("Verbinding maken met de Pi", bold=True)
            tk.Frame(content, bg=PANEL2, height=1).pack(fill="x", pady=6)

            lbl_status = tk.Label(content,
                                  text=f"Pingen naar {PI_IP}...",
                                  font=("Segoe UI", 10), bg=BG, fg=YELLOW)
            lbl_status.pack(anchor="w", pady=4)

            lbl_poging = tk.Label(content, text="Poging 1...",
                                  font=("Segoe UI", 9), bg=BG, fg=DIM)
            lbl_poging.pack(anchor="w")

            # Voortgangsbalk
            pb_outer = tk.Frame(content, bg=PANEL2, height=6)
            pb_outer.pack(fill="x", pady=8)
            pb_bar = tk.Frame(pb_outer, bg=BLUE, height=6, width=0)
            pb_bar.place(x=0, y=0)

            tk.Label(content,
                     text="De eerste opstart duurt 1-3 minuten.\n"
                          "Even geduld — de Pi wordt automatisch gedetecteerd.",
                     font=("Segoe UI", 9), bg=BG, fg=DIM,
                     justify="left").pack(anchor="w", pady=(4,0))

            pogingen = [0]

            def ping_loop():
                if stop_ping.is_set():
                    return
                pogingen[0] += 1
                lbl_poging.config(text=f"Poging {pogingen[0]}...")

                # Animeer balk (cyclisch)
                breedte = int(pb_outer.winfo_width() * ((pogingen[0] % 15 + 1) / 15))
                pb_bar.config(width=breedte)

                try:
                    r = subprocess.run(
                        ["ping", "-n", "1", "-w", "2000", PI_IP],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW)
                    bereikbaar = r.returncode == 0
                except:
                    bereikbaar = False

                if bereikbaar:
                    stop_ping.set()
                    lbl_status.config(
                        text=f"●  Pi bereikbaar op {PI_IP}!", fg=OK_C)
                    lbl_poging.config(
                        text="Verbinding geslaagd!", fg=OK_C)
                    pb_bar.config(bg=OK_C, width=pb_outer.winfo_width())
                    btn_stop.config(state="disabled")
                    btn_next.config(
                        state="normal",
                        text="Doorgaan naar Pi instellen →",
                        bg=GREEN_C,
                        command=lambda: [
                            wiz.destroy(),
                            messagebox.showinfo(
                                "Pi bereikbaar!",
                                f"De Pi is bereikbaar op {PI_IP}.\n\n"
                                "Volgende stap:\n"
                                "  Beheer → Pi services → NAS installer uploaden\n"
                                "  Dan via SSH de installer starten.")])
                else:
                    wiz.after(3000, ping_loop)

            wiz.after(1500, ping_loop)

        stap1()

    def _rbtn(self, parent, tekst, cmd, kleur=None, bold=False):
        """Afgeronde knop voor setup/help vensters."""
        k = kleur or PANEL2
        fg = FG if k in (PANEL, PANEL2) else "#ffffff"
        f = ("Segoe UI", 9, "bold") if bold else ("Segoe UI", 9)
        b = RoundedButton(parent, text=tekst, command=cmd, bg=k, fg=fg, font=f)
        return b

    def _open_installatie(self):
        """Start de installatie wizard pi_nas_setup.pyw - via de gedeelde
        launcher, zodat een dubbelklik niet twee vensters opent."""
        ok, fout = pinas_launcher.open_programma(
            "pi_nas_setup.pyw", roots=[_nas_root()], submappen=["Beheer"])
        if not ok:
            messagebox.showerror("Niet gevonden",
                "pi_nas_setup.pyw niet gevonden in C:\\PiNAS\\Beheer\\\n\n"
                "Download de Starter Kit voor een nieuwe installatie.")

    def _open_setup(self):
        win = tk.Toplevel(self)
        win.title(f"Onderhoud — Pi NAS Suite (bijgewerkt: {BIJGEWERKT})")
        win.configure(bg=BG)
        win.resizable(True, True)
        # 6 augustus 2026 (Frans: "vensters niet op de juiste breedte...
        # alleen het scherm vullen van boven naar beneden, alleen als dat
        # mogelijk is"): vaste breedte blijft 620 (ongewijzigd), maar de
        # hoogte was een vaste 1040px die op veel schermen simpelweg niet
        # past - nu begrensd tot wat het scherm daadwerkelijk toelaat.
        win.update_idletasks()
        _breedte, _gewenste_hoogte = 620, 1040
        _hoogte = min(_gewenste_hoogte, win.winfo_screenheight() - 80)
        win.geometry(f"{_breedte}x{_hoogte}")
        win.minsize(560, 760)
        try: win.iconbitmap(_ico_pad())
        except: pass
        # Geen grab_set() hier - dat blokkeerde het netjes sluiten van vensters
        # die je vanuit Beheer opent (Diagnose, Log Bestanden Bekijken).
        win.update_idletasks()
        _x = self.winfo_x() + (self.winfo_width() - _breedte) // 2
        _y = 20
        win.geometry(f"+{_x}+{_y}")

        # Header - 5 augustus 2026 (Frans: headers niet consequent tussen
        # vensters, icoon ontbrak, en overal een Help-knop) - omgezet naar
        # de gedeelde maak_header() i.p.v. eigen, losse code. Was 1 van 4
        # bijna-identieke kopieën in dit bestand die de al-bestaande
        # gedeelde functie nooit gebruikten.
        hdr = maak_header(win, "Onderhoud", subtekst="Beheer en onderhoud van bestaande installatie",
                    kleur=ACCENT_PICONTROL)
        # Hergebruikt de bestaande, uitgebreide _open_help() (zelfde als
        # het hoofdmenu) - GEEN aparte, dubbele help-inhoud voor dit
        # scherm, want dit draait in hetzelfde proces/dezelfde klasse.
        # In hdr.rij pakken (de titelregel zelf), niet in hdr (dat bevat
        # ook de subtekst-regel eronder) - anders belandt de knop onder
        # de subtekst i.p.v. ernaast (5 augustus 2026, Frans gemeld).
        help_knop = maak_knop(hdr.rij, "?  Help", self._open_help, stijl="secundair")
        help_knop.pack_forget()
        help_knop.pack(side="right")

        # Scrollbaar body
        canvas = tk.Canvas(win, bg=BG, highlightthickness=0)
        scroll = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        frame = tk.Frame(canvas, bg=BG, padx=20, pady=14)
        self._beheer_canvas_win = canvas.create_window((0,0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(
            self._beheer_canvas_win, width=e.width - 4))
        # bind_all i.p.v. bind - anders werkt het muiswiel alleen boven kale
        # canvas-ruimte, niet boven de knoppen/labels erin (16 juli 2026,
        # zelfde fix als in Status & details hieronder).
        # 6 augustus 2026: _muiswiel_op_focus herbindt ook bij <FocusIn> -
        # zie functie zelf (lost op dat een ander open venster de scroll
        # bleef vasthouden ondanks dat dit venster is aangeklikt).
        _muiswiel_op_focus(win, canvas)
        # 18 juli 2026: bind_all is GLOBAAL - zonder dit geeft dit venster de
        # muiswiel-scroll bij sluiten niet terug aan het hoofdmenu (dat blijft
        # de hele sessie open en heeft zijn eigen scrollbare inhoud).
        win.bind("<Destroy>", lambda e: self._herstel_hoofd_muiswiel() if e.widget is win else None)

        def sectie(tekst, kleur):
            f = tk.Frame(frame, bg=kleur, pady=7, padx=12)
            f.pack(fill="x", pady=(10,4))
            tk.Label(f, text=tekst, font=("Segoe UI", 10, "bold"),
                     bg=kleur, fg="#ffffff").pack(anchor="w")

        self._beheer_marks = {}

        def check_item(tekst, key, var):
            rij = tk.Frame(frame, bg=BG)
            rij.pack(fill="x", pady=3)
            tk.Checkbutton(rij, text=f"  {tekst}", variable=var,
                           font=("Segoe UI", 9), bg=BG, fg=FG,
                           selectcolor=PANEL2, activebackground=BG,
                           anchor="w").pack(side="left", fill="x", expand=True)
            mark = tk.Label(rij, text="⏳", font=("Segoe UI", 9), bg=BG, fg=DIM)
            mark.pack(side="right")
            self._beheer_marks[key] = mark

        def _zet_mark(key, ok):
            m = self._beheer_marks.get(key)
            if m is not None:
                try:
                    if m.winfo_exists():
                        m.config(text="✅" if ok else "❌",
                                 fg=OK_C if ok else ERR_C)
                except tk.TclError:
                    pass

        vars_ = {}

        # ── Pi services ──────────────────────────────────────────────────────
        sectie("🖥  Pi services", ACCENT_PINAS)
        tk.Label(frame, text="Installeer of herstel services op de Pi.",
                 font=("Segoe UI", 8), bg=BG, fg=DIM, wraplength=480).pack(anchor="w", pady=(2,4))

        # Items direct opbouwen met placeholder; de echte status wordt zo
        # dadelijk in een achtergrondthread opgehaald (venster bevriest niet).
        for key, naam, svc_naam in [
            ("server",      "Samba (bestandsdeling)",  "smbd"),
            ("filebrowser", "FileBrowser",             "filebrowser"),
            ("cockpit",     "Cockpit",                 "cockpit"),
            ("seagate_svc", "Externe HDD service",     "seagate-web"),
        ]:
            vars_[key] = tk.BooleanVar(value=False)
            check_item(naam, key, vars_[key])

        # ── Windows onderdelen ───────────────────────────────────────────────
        sectie("💻  Windows onderdelen", ACCENT_PINAS)
        for key, naam in [
            ("putty",     "PuTTY"),
            ("vnc",       "TigerVNC Viewer"),
            ("docker_pc", "Docker Desktop"),
            ("pibackup",  "Sync & Backup"),
            ("schijven",  "Netwerkschijven (Opslag + Backup)"),
            # Node.js is hier verwijderd (6 augustus 2026, Frans: "als dat
            # eruit kan, kun je dat gelijk opruimen") - was ALLEEN nodig
            # voor de oude Functieoverzicht-docx-build, die nu op Python/
            # ReportLab (PDF) draait. Ook uit Beheer_install.bat gehaald.
        ]:
            vars_[key] = tk.BooleanVar(value=False)
            check_item(naam, key, vars_[key])

        # ── Alle status-checks in EEN achtergrondthread ──────────────────────
        # Deze checks (SSH naar de Pi, net use voor de schijven) kunnen traag
        # zijn; op de hoofdthread zouden ze het venster laten bevriezen. Daarom
        # draaien ze hier apart en werken ze de vinkjes daarna bij.
        def _beheer_status_worker():
            svc = {}
            _cmd = (
                "st=$(systemctl is-active smbd 2>/dev/null); echo smbd:$st; "
                "if [ -f /var/www/html/nextcloud/config/config.php ] || "
                "   [ -f /var/www/nextcloud/config/config.php ]; "
                "then echo nextcloud:active; else echo nextcloud:inactive; fi; "
                "st=$(systemctl is-active filebrowser 2>/dev/null); "
                "en=$(systemctl is-enabled filebrowser 2>/dev/null); "
                "if [ \"$st\" = \"active\" ] || [ \"$en\" = \"enabled\" ] || "
                "   command -v filebrowser >/dev/null 2>&1; "
                "then echo filebrowser:active; else echo filebrowser:$st; fi; "
                "st=$(systemctl is-active cockpit 2>/dev/null); "
                "en=$(systemctl is-enabled cockpit 2>/dev/null); "
                "if [ \"$st\" = \"active\" ] || [ \"$en\" = \"enabled\" ] || [ \"$en\" = \"static\" ]; "
                "then echo cockpit:active; else echo cockpit:$st; fi; "
                "st=$(systemctl is-active seagate-web 2>/dev/null); echo seagate-web:$st"
            )
            try:
                r = subprocess.run(
                    ["ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no",
                     "-o", "BatchMode=yes", f"pi@{PI_IP}", _cmd],
                    capture_output=True, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
                for regel in r.stdout.strip().splitlines():
                    if ":" in regel:
                        s, _, st = regel.partition(":")
                        svc[s.strip()] = (st.strip() == "active")
            except Exception:
                pass
            resultaat = {
                "server":      svc.get("smbd", False),
                "nextcloud":   svc.get("nextcloud", False),
                "filebrowser": svc.get("filebrowser", False),
                "cockpit":     svc.get("cockpit", False),
                "seagate_svc": svc.get("seagate-web", False),
            }
            try:
                resultaat["putty"]     = check_putty()
                resultaat["vnc"]       = check_tigervnc()
                resultaat["docker_pc"] = check_docker_desktop()
                resultaat["pibackup"]  = check_pibackup()
                resultaat["schijven"]  = (check_share("Opslag", _opslag_letter(), PI_IP)
                                           and check_share("Backup", _backup_letter(), PI_IP))
            except Exception:
                pass
            try:
                win.after(0, lambda: [_zet_mark(k, v) for k, v in resultaat.items()])
            except Exception:
                pass

        threading.Thread(target=_beheer_status_worker, daemon=True).start()

        # ── Uitvoeren knop ───────────────────────────────────────────────────
        tk.Frame(frame, bg=PANEL2, height=1).pack(fill="x", pady=12)

        def installeer():
            keuzes = {k: v.get() for k, v in vars_.items()}
            if not any(keuzes.values()):
                messagebox.showinfo("Beheer", "Geen onderdelen geselecteerd.")
                return
            win.destroy()
            self._voer_setup_uit(keuzes)

        self._rbtn(frame, "⚙️  Uitvoeren", installeer, ACCENT_PINAS, bold=True)

        # ── Publicatie / Distributie ─────────────────────────────────────────
        # Verhuisd hierheen vanuit NAS Map Beheer's opgeheven "Herstel &
        # Acties"-tab (16 juli 2026). 16 juli 2026: op verzoek van Frans
        # gesplitst in Publicatie (de 3 documentatie-builders) en Distributie
        # (Starter Kit + publieke versie); Scripts uploaden verhuisde naar
        # Geavanceerd, bij de andere Pi-onderhoudsacties.
        tk.Frame(frame, bg=PANEL2, height=1).pack(fill="x", pady=(14,6))
        tk.Label(frame, text="Publicatie", font=("Segoe UI", 9, "bold"),
                 bg=BG, fg=ACCENT_PINAS).pack(anchor="w", pady=(4,2))

        def _distributie_zoekpad(bestand, submappen):
            nas = _nas_root()
            for sub in submappen:
                p = os.path.join(nas, sub, bestand) if sub else os.path.join(nas, bestand)
                if os.path.exists(p):
                    return p
            return None

        # 16 juli 2026: elke actie eindigt nu met een duidelijke "Gereed"/
        # "Mislukt" regel in het cmd-venster (&& / ||), zodat je nooit meer
        # gokt of een snel klaar script wel iets deed. Het venster blijft
        # open (cmd /k) - zelf sluiten als je klaar bent met kijken.
        _KLAAR = (
            '&& (echo. & echo ============================== '
            '& echo  Gereed! & echo ==============================) '
            '|| (echo. & echo ============================== '
            '& echo  Mislukt - zie foutmelding hierboven & echo ==============================)'
        )

        def _bat_actie(bestand, submappen=("Gedeeld","Beheer","PiServer","")):
            pad = _distributie_zoekpad(bestand, submappen)
            if not pad:
                messagebox.showerror("Niet gevonden", f"{bestand} niet gevonden.")
                return
            subprocess.Popen(f'start cmd /k "{pad}" {_KLAAR}',
                              shell=True, cwd=os.path.dirname(pad))

        def _console_python():
            """Geeft het pad naar python.exe (NIET pythonw.exe) terug.

            5 augustus 2026 (Frans: Publicatie-knoppen toonden alleen
            'Gereed!' en verder niets - geen enkele regel van het script
            zelf): Pi_NAS_Menu.pyw draait zelf via pythonw.exe (het is
            een .pyw-bestand), dus sys.executable wijst daar ook naar.
            pythonw.exe onderdrukt ALLE stdout/stderr van elk script dat
            het start - ook als dat binnen een zichtbaar cmd-venster
            gebeurt, blijft het scherm dan gewoon leeg terwijl het
            script prima doorloopt. python.exe (zonder de w) doet dat
            niet. Beide staan altijd naast elkaar in dezelfde map."""
            kandidaat = sys.executable.replace("pythonw.exe", "python.exe")
            if os.path.exists(kandidaat):
                return kandidaat
            return sys.executable  # laatste redmiddel, beter dan crashen

        def _python_actie(bestand, submappen=("Publicatie","Beheer","Gedeeld","")):
            """5 augustus 2026 (Frans: knop opende een cmd-venster met
            alleen een kaal promptje, niets werd uitgevoerd): de oude
            aanpak bouwde 1 lange shell=True-commandoregel met GENESTE
            aanhalingstekens (interpreterpad + scriptpad allebei apart
            gequote binnen een 'start cmd /k "..."'-wikkel). cmd.exe's
            eigen quote-stripping bij /k is berucht onvoorspelbaar zodra
            er meer dan 1 gequote deel in zit - zelfde klasse fout als de
            ZeroTier-elevatie eerder vandaag. Nu net zo robuust: een echt
            .bat-bestand wegschrijven en dat starten via een simpele
            argv-lijst (geen shell=True, geen handmatig quoten nodig -
            subprocess doet dat zelf correct)."""
            pad = _distributie_zoekpad(bestand, submappen)
            if not pad:
                messagebox.showerror("Niet gevonden", f"{bestand} niet gevonden.")
                return
            bat_naam = f"pinas_actie_{os.path.splitext(bestand)[0]}.bat"
            bat_pad = os.path.join(tempfile.gettempdir(), bat_naam)
            regels = [
                "@echo off",
                f'"{_console_python()}" "{pad}"',
                "if errorlevel 1 (",
                "    echo.",
                "    echo ==============================",
                "    echo  Mislukt - zie foutmelding hierboven",
                "    echo ==============================",
                ") else (",
                "    echo.",
                "    echo ==============================",
                "    echo  Gereed!",
                "    echo ==============================",
                ")",
                "pause",
            ]
            with open(bat_pad, "w", encoding="utf-8") as f:
                f.write("\r\n".join(regels) + "\r\n")
            subprocess.Popen(["cmd", "/c", "start", "cmd", "/k", bat_pad],
                              cwd=os.path.dirname(pad))

        def _open_publicatie_bestand(bestand):
            """16 juli 2026: opent een gebouwd document met het standaard-
            Windows-programma (PDF-lezer / Word / browser) - zodat je na het
            herbouwen niet zelf naar de Publicatie-map hoeft te navigeren."""
            pad = os.path.join(_nas_root(), "Publicatie", bestand)
            if not os.path.exists(pad):
                messagebox.showinfo(
                    "Nog niet gebouwd",
                    f"{bestand} bestaat nog niet in Publicatie.\n\n"
                    f"Klik eerst op de knop ernaast om het te (her)bouwen.")
                return
            try:
                os.startfile(pad)
            except Exception as e:
                messagebox.showerror("Kon niet openen",
                    f"{bestand} kon niet worden geopend:\n{e}")

        def _herbouw_rij(label, bouw_cmd, open_bestand, kleur):
            """Rij met de herbouw-knop (breed) en een smalle Open-knop
            ernaast, zodat je het resultaat meteen kunt bekijken zonder zelf
            naar Publicatie te hoeven bladeren."""
            rij = tk.Frame(frame, bg=BG)
            rij.pack(fill="x", pady=2)
            hoofd = RoundedButton(rij, text=label, command=bouw_cmd,
                                   bg=kleur, fg="#ffffff")
            hoofd.pack(side="left", fill="x", expand=True, padx=(0,6))
            openknop = RoundedButton(rij, text="📂 Open", command=lambda: _open_publicatie_bestand(open_bestand),
                                      bg=PANEL2, fg=FG, width=76)
            openknop.pack(side="left")

        _herbouw_rij("📄  Suite handleiding herbouwen (PDF)",
                     lambda: _python_actie("build_suite_handleiding.py"),
                     "PiNAS_Suite_Handleiding.pdf", ACCENT_PINAS)
        # Functieoverzicht herbouwen-knop verwijderd (10 augustus 2026, Frans:
        # "functieoverzicht kan vervallen als je een korte versie op een
        # pagina kunt opnemen in de presentatie") - build_functieoverzicht.py
        # en PiNAS_Functieoverzicht.pdf bestaan niet meer, vervangen door een
        # pagina in PiNAS_Suite_Presentatie.pptx (die je met PowerPoint zelf
        # bewerkt, geen herbouw-knop voor nodig).
        _herbouw_rij("🗺  Topografie herbouwen (build_topografie.py)",
                     lambda: _python_actie("build_topografie.py"),
                     "PiNAS_Topografie.html", ACCENT_PINAS)

        # 5 augustus 2026 (Frans: "waarom zou ik dat niet vanuit de suite
        # starten?" - terechte vraag): consistentiecontrole-script kreeg
        # alsnog een knop i.p.v. alleen via de opdrachtregel bruikbaar te
        # zijn. Geen "Open"-knop erbij nodig zoals bij de herbouw-knoppen
        # hierboven - dit produceert geen document, de uitvoer verschijnt
        # gewoon live in het cmd-venster dat _python_actie al opent.
        RoundedButton(frame, text="🔍  Documentatie consistentie controleren",
                      command=lambda: _python_actie("controleer_documentatie_consistentie.py"),
                      bg=ACCENT_PINAS, fg="#ffffff").pack(fill="x", pady=2)

        tk.Frame(frame, bg=PANEL2, height=1).pack(fill="x", pady=(14,6))
        tk.Label(frame, text="Distributie", font=("Segoe UI", 9, "bold"),
                 bg=BG, fg=ACCENT_PINAS).pack(anchor="w", pady=(4,2))
        self._rbtn(frame, "📦  Starter Kit ZIP bouwen (maak_starterkit.bat)",
                   lambda: _bat_actie("maak_starterkit.bat"), ACCENT_PINAS)
        self._rbtn(frame, "🌐  Publieke versie maken voor GitHub (maak_publieke_versie.bat)",
                   lambda: _bat_actie("maak_publieke_versie.bat"), ACCENT_PINAS)

        # ── Geavanceerd ──────────────────────────────────────────────────────
        tk.Frame(frame, bg=PANEL2, height=1).pack(fill="x", pady=(14,6))
        tk.Label(frame, text="Geavanceerd", font=("Segoe UI", 9, "bold"),
                 bg=BG, fg=ACCENT_PINAS).pack(anchor="w", pady=(4,2))
        self._rbtn(frame, "🔄  Pi OS bijwerken (apt update + upgrade)", self._pi_update, ACCENT_PINAS)
        self._rbtn(frame, "🐍  Python bijwerken naar laatste versie (Windows)",
                   lambda: _bat_actie("python_bijwerken.bat"), ACCENT_PINAS)
        self._rbtn(frame, "♻  Pi NAS herstarten (sudo reboot)",
                   self._herstart_pi, DESTRUCTIEF)
        self._rbtn(frame, "🔓  LanMan-fix — alleen bij 'Toegang geweigerd' / Systeemfout 5",
                   self._herstel_verbinding, WARN)
        self._rbtn(frame, "⬆  Scripts uploaden naar Pi (nas_upload.bat)",
                   lambda: _bat_actie("nas_upload.bat"), ACCENT_PINAS)
        tk.Frame(frame, bg=PANEL2, height=1).pack(fill="x", pady=(10,6))
        self._rbtn(frame, "🔗  Download links beheren", self._open_download_links, ACCENT_PINAS)
        tk.Frame(frame, bg=PANEL2, height=1).pack(fill="x", pady=(10,6))
        tk.Label(frame, text="Weergave", font=("Segoe UI", 9, "bold"),
                 bg=BG, fg=ACCENT_PINAS).pack(anchor="w", pady=(4,2))
        huidig = getattr(__import__("pinas_theme"), "HUIDIG_THEMA", "donker")
        thema_tekst = f"🎨  Thema wisselen  (nu: {huidig}) — herstart vereist"
        self._rbtn(frame, thema_tekst, self._wissel_thema, PANEL2)
        self._rbtn(frame, "🌈  Kleuren kiezen (aanpassen)", self._open_kleuren_kiezer, ACCENT_PINAS)
        tk.Frame(frame, bg=PANEL2, height=1).pack(fill="x", pady=(10,6))
        tk.Label(frame, text="Beveiliging", font=("Segoe UI", 8, "bold"),
                 bg=BG, fg=DIM).pack(anchor="w")
        self._rbtn(frame, "🔑  NAS wachtwoord instellen / wijzigen",
                   lambda: self._wachtwoord_instellen(), ACCENT)
        self._rbtn(frame, "📱  Mobiele statuspagina - wachtwoord resetten",
                   self._reset_statuspagina_wachtwoord, ACCENT)

    def _open_kleuren_kiezer(self):
        """Opent Kleuren kiezen - los venster om pinas_theme.py aan te passen
        via kleurstalen i.p.v. het bestand met de hand te bewerken."""
        ok, fout = pinas_launcher.open_programma(
            "pinas_kleuren_kiezer.pyw", roots=[_nas_root()], submappen=["Beheer"])
        if not ok:
            messagebox.showerror("Niet gevonden",
                "pinas_kleuren_kiezer.pyw niet gevonden in C:\\PiNAS\\Beheer\\\n\n"
                f"Technische details: {fout}")

    def _wissel_thema(self):
        """Wissel tussen donker en licht thema — sla op in picontrol.cfg."""
        try:
            import pinas_theme as _pt
            huidig = getattr(_pt, "HUIDIG_THEMA", "donker")
        except Exception:
            huidig = "donker"
        nieuw_thema = "licht" if huidig == "donker" else "donker"

        # Schrijf naar picontrol.cfg
        cfg_pad = os.path.join(_nas_root(), "Beheer", "picontrol.cfg")
        import configparser as _cp
        cfg = _cp.ConfigParser()
        if os.path.exists(cfg_pad):
            cfg.read(cfg_pad, encoding="utf-8")
        if not cfg.has_section("ui"):
            cfg.add_section("ui")
        cfg.set("ui", "thema", nieuw_thema)
        with open(cfg_pad, "w", encoding="utf-8") as f:
            cfg.write(f)

        messagebox.showinfo(
            "Thema gewijzigd",
            f"Thema gewijzigd naar: {nieuw_thema}\n\n"
            "Herstart Pi NAS Menu om het nieuwe thema toe te passen.")

    def _pi_update(self):
        """Voert apt update + upgrade uit op de Pi in een zichtbaar CMD venster."""
        import tempfile
        bat = os.path.join(tempfile.gettempdir(), "pi_update.bat")
        cmd_pi = "sudo apt update && sudo apt upgrade -y && sudo apt autoremove -y"
        regels_bat = [
            "@echo off",
            "echo Pi OS bijwerken op de Raspberry Pi...",
            "echo Dit kan enkele minuten duren.",
            "echo.",
            "ssh -t pi@" + PI_IP + ' "' + cmd_pi + '"',
            "echo.",
            "echo === Klaar ===",
            "pause",
        ]
        with open(bat, "w", newline="") as f_bat:
            f_bat.write("\r\n".join(regels_bat) + "\r\n")
        subprocess.Popen('start cmd /k "' + bat + '"', shell=True)

    def _reset_statuspagina_wachtwoord(self):
        """Wachtwoord van de mobiele statuspagina resetten - zelfde script
        als de knop in Addons Beheer, hier ook beschikbaar onder
        Beveiliging (Frans, 17 juli 2026: wachtwoord-acties horen bij
        elkaar), zodat je niet apart naar Addons Beheer hoeft als je
        alleen het wachtwoord kwijt bent."""
        script_naam = "pinas_status_pagina_wachtwoord_resetten.sh"
        script_pad = os.path.join(_nas_root(), "Addons", script_naam)
        if not os.path.exists(script_pad):
            script_pad = os.path.join(_c_pinas(), "Addons", script_naam)
        if not os.path.exists(script_pad):
            messagebox.showerror("Niet gevonden",
                f"{script_naam} niet gevonden.\n\nInstalleer eerst de mobiele "
                "statuspagina via Addons Beheer als dat nog niet is gebeurd.")
            return

        akkoord = messagebox.askyesno(
            "Mobiele statuspagina - wachtwoord resetten",
            "Dit maakt een NIEUW wachtwoord aan voor de mobiele statuspagina "
            "(poort 8090). Het oude wachtwoord werkt daarna niet meer.\n\n"
            "Vereist dat de statuspagina al geinstalleerd is (via Addons "
            "Beheer). Volg het venster dat opent voor het nieuwe wachtwoord.\n\n"
            "Doorgaan?")
        if not akkoord:
            return

        bat = os.path.join(tempfile.gettempdir(), "pinas_statuspagina_ww_reset.bat")
        regels = [
            "@echo off",
            "echo Mobiele statuspagina - wachtwoord resetten...",
            "echo.",
            "echo Stap 1: script uploaden...",
            f'scp "{script_pad}" pi@{PI_IP}:/home/pi/{script_naam}',
            "if errorlevel 1 (",
            "    echo FOUT: uploaden mislukt.",
            "    pause",
            "    exit /b 1",
            ")",
            "echo OK: geupload.",
            "echo.",
            "echo Stap 2: uitvoeren (met sudo)...",
            f'ssh -t pi@{PI_IP} "export TERM=xterm; chmod +x /home/pi/{script_naam} '
            f'&& sudo -E /home/pi/{script_naam}"',
            "echo.",
            "echo Klaar. Dit venster mag gesloten worden.",
            "pause",
        ]
        with open(bat, "w", newline="") as f:
            f.write("\r\n".join(regels) + "\r\n")
        subprocess.Popen('start cmd /k "' + bat + '"', shell=True)

    def _herstart_pi(self):
        """Herstart de Pi (sudo reboot) via SSH, met bevestiging. De
        SSH-verbinding valt direct weg zodra de Pi herstart - dat is
        normaal en geen fout."""
        akkoord = messagebox.askyesno(
            "Pi NAS herstarten",
            "Weet je zeker dat je de Pi NAS wilt herstarten?\n\n"
            "Alle actieve verbindingen (Opslag, Backup, Nextcloud, FileBrowser) "
            "vallen kort weg. Na ongeveer 30-60 seconden is de Pi weer "
            "bereikbaar.\n\n"
            "Doorgaan?")
        if not akkoord:
            return
        bat = os.path.join(tempfile.gettempdir(), "pinas_herstart.bat")
        regels = [
            "@echo off",
            "echo Pi NAS wordt herstart...",
            'ssh -o ConnectTimeout=5 pi@' + PI_IP + ' "sudo reboot"',
            "echo.",
            "echo De verbinding valt nu weg - dat is normaal.",
            "echo Wacht ongeveer 30-60 seconden en klik dan in het hoofdvenster op 'Nu controleren'.",
            "pause",
        ]
        with open(bat, "w", newline="") as f:
            f.write("\r\n".join(regels) + "\r\n")
        subprocess.Popen('start cmd /k "' + bat + '"', shell=True)

    def _open_builder(self):
        """Start maak_starterkit.bat autonoom."""
        nas = _nas_root()
        script = _script_dir()
        for pad in [
            os.path.join(nas, "Gedeeld", "maak_starterkit.bat"),
            os.path.join(script, "maak_starterkit.bat"),
            os.path.join(nas, "Beheer", "maak_starterkit.bat"),
        ]:
            if os.path.exists(pad):
                subprocess.Popen(["cmd", "/c", pad],
                                 creationflags=subprocess.CREATE_NEW_CONSOLE)
                return
        messagebox.showerror("Niet gevonden",
            "maak_starterkit.bat niet gevonden.\n"
            "Zet het bestand in C:\\PiNAS\\Gedeeld\\")

    def _open_download_links(self):
        """Venster voor beheren van download links. Omhuld met een zichtbare
        foutmelding: gaat er iets mis, dan zie je de exacte reden in plaats van
        een venster dat stil niet opent."""
        try:
            self._open_download_links_impl()
        except Exception:
            import traceback
            messagebox.showerror(
                "Download links - er ging iets mis",
                "Het venster kon niet (volledig) openen.\n\n"
                "Technische details:\n" + traceback.format_exc())

    def _open_download_links_impl(self):
        import configparser as _cp

        # Zoek download_links.ini
        gedeeld = os.path.join(_nas_root(), "Gedeeld")
        ini_pad = os.path.join(gedeeld, "download_links.ini")

        # Laad huidige links. interpolation=None is essentieel: de URLs bevatten
        # %-tekens (bv. Docker ...%20Desktop%20Installer.exe). Met de standaard-
        # interpolatie crasht configparser daarop (InterpolationSyntaxError),
        # waardoor het venster wel "klikbaar" is maar niet opent.
        cfg = _cp.ConfigParser(interpolation=None)
        if os.path.exists(ini_pad):
            # utf-8-sig: verdraagt en verwijdert een eventuele UTF-8 BOM aan het
            # begin van het bestand. Zonder dit ziet configparser de eerste
            # [sectie]-kop niet en weigert het hele bestand (MissingSectionHeaderError).
            cfg.read(ini_pad, encoding="utf-8-sig")

        win = tk.Toplevel(self)
        win.title("Download links — Pi NAS Suite")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.geometry("640x560")
        win.grab_set()

        tk.Label(win, text="🔗  Download links",
                 font=("Segoe UI", 13, "bold"), bg=BG, fg=FG).pack(pady=(14,2))
        tk.Label(win,
                 text="Links worden gebruikt door Beheer_install.bat als installers "
                      "niet lokaal aanwezig zijn. Pas aan als een link veranderd is.",
                 font=("Segoe UI", 9), bg=BG, fg=DIM, justify="center").pack(pady=(0,10))

        # Onderbalk (knoppen + foutregel) EERST onderaan vastzetten, anders
        # verdringt de uitklappende canvas (expand=True) de Opslaan-knop.
        knop_frame = tk.Frame(win, bg=BG)
        knop_frame.pack(side="bottom", pady=10)
        fout_lbl = tk.Label(win, text="", font=("Segoe UI", 9), bg=BG, fg=ERR_C)
        fout_lbl.pack(side="bottom", pady=(8,0))

        canvas = tk.Canvas(win, bg=BG, highlightthickness=0)
        scroll = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True, padx=(12,0))
        frame = tk.Frame(canvas, bg=BG, padx=8, pady=8)
        canvas.create_window((0,0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        # 6 augustus 2026 (Frans: "help schermen niet scrolbaar met de muis,
        # dat moeten eigenlijk alle schermen zijn") - ontbrak hier, andere
        # vensters (Onderhoud/Status) hadden dit al. _muiswiel_op_focus
        # herbindt ook bij <FocusIn> (zelfde dag, zelfde reden).
        _muiswiel_op_focus(win, canvas)
        def _canvas_resize(e):
            items = canvas.find_all()
            if items:
                canvas.itemconfig(items[0], width=e.width)
        canvas.bind("<Configure>", _canvas_resize)

        invoer_velden = {}

        secties = [
            ("TigerVNC",  "TigerVNC Viewer"),
            ("Docker",    "Docker Desktop"),
            ("PiImager",  "Raspberry Pi Imager"),
            ("PuTTY",     "PuTTY SSH client"),
            ("Python",    "Python"),
        ]

        standaard_urls = {
            "TigerVNC":  "https://github.com/TigerVNC/tigervnc/releases/download/v1.16.2/tigervnc64-1.16.2.exe",
            "Docker":    "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe",
            "PiImager":  "https://downloads.raspberrypi.org/imager/imager_latest.exe",
            "PuTTY":     "https://the.earth.li/~sgtatham/putty/latest/w64/putty-64bit-installer.msi",
            "Python":    "https://www.python.org/ftp/python/3.14.6/python-3.14.6-amd64.exe",
        }

        for sectie, naam in secties:
            tk.Frame(frame, bg=PANEL2, height=1).pack(fill="x", pady=(8,4))
            tk.Label(frame, text=naam, font=("Segoe UI", 10, "bold"),
                     bg=BG, fg=ACCENT_PINAS).pack(anchor="w")

            # Omschrijving
            omschr = cfg.get(sectie, "omschrijving", fallback="") if cfg.has_section(sectie) else ""
            if omschr:
                tk.Label(frame, text=omschr, font=("Segoe UI", 8),
                         bg=BG, fg=DIM).pack(anchor="w")

            # Versie
            versie_rij = tk.Frame(frame, bg=BG)
            versie_rij.pack(fill="x", pady=2)
            tk.Label(versie_rij, text="Versie:", font=("Segoe UI", 9),
                     bg=BG, fg=FG, width=10, anchor="w").pack(side="left")
            versie_var = tk.StringVar(value=cfg.get(sectie, "versie", fallback="latest") if cfg.has_section(sectie) else "latest")
            tk.Entry(versie_rij, textvariable=versie_var, font=("Segoe UI", 9),
                     bg=PANEL2, fg=FG, insertbackground=FG, width=20).pack(side="left")

            # URL
            url_rij = tk.Frame(frame, bg=BG)
            url_rij.pack(fill="x", pady=2)
            tk.Label(url_rij, text="URL:", font=("Segoe UI", 9),
                     bg=BG, fg=FG, width=10, anchor="w").pack(side="left")
            huidig_url = cfg.get(sectie, "url", fallback=standaard_urls.get(sectie, "")) if cfg.has_section(sectie) else standaard_urls.get(sectie, "")
            url_var = tk.StringVar(value=huidig_url)
            tk.Entry(url_rij, textvariable=url_var, font=("Segoe UI", 8),
                     bg=PANEL2, fg=FG, insertbackground=FG).pack(side="left", fill="x", expand=True)

            invoer_velden[sectie] = {"url": url_var, "versie": versie_var}

        def opslaan():
            # interpolation=None: laat %-tekens in de URLs ongemoeid bij opslaan.
            nieuw_cfg = _cp.ConfigParser(interpolation=None)
            omschr_map = {
                "TigerVNC":  "TigerVNC Viewer — grafisch bureaublad naar de Pi",
                "Docker":    "Docker Desktop — voor de NAS simulator",
                "PiImager":  "Raspberry Pi Imager — SD-kaart voorbereiden",
                "PuTTY":     "PuTTY — SSH client voor verbinding met Pi",
            }
            bestand_map = {
                "TigerVNC": "tigervnc64-installer.exe",
                "Docker":   "Docker Desktop Installer.exe",
                "PiImager": "imager_latest.exe",
                "PuTTY":    "putty-installer.msi",
            }
            for sectie, velden in invoer_velden.items():
                url = velden["url"].get().strip()
                versie = velden["versie"].get().strip()
                if not url:
                    fout_lbl.config(text=f"URL voor {sectie} mag niet leeg zijn.")
                    return
                nieuw_cfg[sectie] = {
                    "url":         url,
                    "versie":      versie or "latest",
                    "bestand":     bestand_map.get(sectie, "installer.exe"),
                    "omschrijving": omschr_map.get(sectie, ""),
                }
            try:
                os.makedirs(gedeeld, exist_ok=True)
                with open(ini_pad, "w", encoding="utf-8") as f:
                    nieuw_cfg.write(f)
                win.destroy()
                messagebox.showinfo("Download links", f"Links opgeslagen in:\n{ini_pad}")
            except Exception as e:
                fout_lbl.config(text=f"Opslaan mislukt: {e}")

        def herstel_standaard():
            for sectie, velden in invoer_velden.items():
                velden["url"].set(standaard_urls.get(sectie, ""))
                velden["versie"].set("latest")
            fout_lbl.config(text="Standaard links hersteld — klik Opslaan om te bevestigen.")

        tk.Button(knop_frame, text="💾  Opslaan", font=("Segoe UI", 10, "bold"),
                  bg=ACCENT_PINAS, fg="#ffffff", relief="flat", padx=16, pady=6,
                  cursor="hand2", command=opslaan).pack(side="left", padx=6)
        tk.Button(knop_frame, text="↩  Standaard herstellen", font=("Segoe UI", 9),
                  bg=PANEL2, fg=FG, relief="flat", padx=12, pady=6,
                  cursor="hand2", command=herstel_standaard).pack(side="left", padx=6)
        tk.Button(knop_frame, text="Annuleren", font=("Segoe UI", 9),
                  bg=PANEL2, fg=FG, relief="flat", padx=12, pady=6,
                  cursor="hand2", command=win.destroy).pack(side="left", padx=6)

    def _check_wachtwoord_bij_start(self):
        """Waarschuw eenmalig als wachtwoord nog niet ingesteld is."""
        if not wachtwoord_beschikbaar("samba"):
            antwoord = messagebox.askyesno(
                "NAS Wachtwoord niet ingesteld",
                "Het Samba wachtwoord is nog niet ingesteld.\n\n"
                "Zonder wachtwoord kunnen de Opslag- en Backup-schijven niet worden gekoppeld.\n\n"
                "Wil je het wachtwoord nu instellen?",
                icon="warning"
            )
            if antwoord:
                self._wachtwoord_instellen(toon_huidig=False)

    def _wachtwoord_instellen(self, toon_huidig=True):
        """Dialoog voor instellen of wijzigen van NAS wachtwoord in Credential Manager."""
        win = tk.Toplevel(self)
        win.title("NAS wachtwoord — Pi NAS Suite")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="NAS Wachtwoord", font=("Segoe UI", 13, "bold"),
                 bg=BG, fg=FG).pack(padx=20, pady=(16,4))
        tk.Label(win,
                 text="Dit wachtwoord wordt opgeslagen in Windows Credential Manager.\n"
                      "Het wordt gebruikt voor de Opslag-/Backup-schijven (Samba) en SSH verbindingen.",
                 font=("Segoe UI", 9), bg=BG, fg=DIM, justify="center").pack(padx=20, pady=(0,10))

        frame = tk.Frame(win, bg=BG)
        frame.pack(fill="x", padx=20, pady=4)

        if toon_huidig:
            huidig = get_wachtwoord("samba") or "(niet ingesteld)"
            tk.Label(frame, text="Huidig:", font=("Segoe UI", 9), bg=BG, fg=DIM,
                     width=14, anchor="w").grid(row=0, column=0, pady=3)
            tk.Label(frame, text="●" * len(huidig) if huidig != "(niet ingesteld)" else huidig,
                     font=("Segoe UI", 9), bg=BG,
                     fg=OK_C if huidig != "(niet ingesteld)" else ERR_C).grid(row=0, column=1, sticky="w")

        tk.Label(frame, text="Nieuw wachtwoord:", font=("Segoe UI", 9), bg=BG, fg=FG,
                 width=14, anchor="w").grid(row=1, column=0, pady=3)
        invoer_nieuw = tk.Entry(frame, show="*", font=("Segoe UI", 10),
                                bg=PANEL2, fg=FG, insertbackground=FG, width=22)
        invoer_nieuw.grid(row=1, column=1, sticky="w")

        tk.Label(frame, text="Bevestigen:", font=("Segoe UI", 9), bg=BG, fg=FG,
                 width=14, anchor="w").grid(row=2, column=0, pady=3)
        invoer_bevestig = tk.Entry(frame, show="*", font=("Segoe UI", 10),
                                   bg=PANEL2, fg=FG, insertbackground=FG, width=22)
        invoer_bevestig.grid(row=2, column=1, sticky="w")



        fout_lbl = tk.Label(win, text="", font=("Segoe UI", 9), bg=BG, fg=ERR_C)
        fout_lbl.pack(pady=(4,0))

        def opslaan():
            nieuw = invoer_nieuw.get().strip()
            bevestig = invoer_bevestig.get().strip()
            if not nieuw and not vnc:
                fout_lbl.config(text="Vul minimaal één wachtwoord in.")
                return
            if nieuw and nieuw != bevestig:
                fout_lbl.config(text="Wachtwoorden komen niet overeen.")
                return

            gelukt = []
            if nieuw:
                ok, fout = set_wachtwoord(nieuw, "samba")
                if ok:
                    gelukt.append("Samba/SSH wachtwoord opgeslagen")
                else:
                    fout_lbl.config(text=f"Opslaan mislukt: {fout}")
                    return


            win.destroy()
            messagebox.showinfo("Wachtwoord", "\n".join(gelukt) +
                                "\n\nOpgeslagen in Windows Credential Manager.")

        knop_frame = tk.Frame(win, bg=BG)
        knop_frame.pack(pady=12)
        tk.Button(knop_frame, text="Opslaan", font=("Segoe UI", 10, "bold"),
                  bg=ACCENT_PINAS, fg="#ffffff", relief="flat", padx=16, pady=6,
                  cursor="hand2", command=opslaan).pack(side="left", padx=6)
        tk.Button(knop_frame, text="Later instellen", font=("Segoe UI", 10),
                  bg=PANEL2, fg=DIM, relief="flat", padx=16, pady=6,
                  cursor="hand2", command=win.destroy).pack(side="left", padx=6)

        invoer_nieuw.focus_set()
        win.bind("<Return>", lambda e: opslaan())

    def _open_test_suite(self):
        """Start Test Suite als apart proces."""
        kandidaten = [
            os.path.join(_c_pinas(), "Gedeeld", "test_suite.py"),
            os.path.join(_nas_root(), "Gedeeld", "test_suite.py"),
            os.path.join(_script_dir(), "..", "Gedeeld", "test_suite.py"),
        ]
        pad = next((p for p in kandidaten if os.path.exists(p)), None)
        if pad:
            subprocess.Popen(
                [sys.executable, pad],
                creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            messagebox.showerror("Test Suite niet gevonden",
                "test_suite.py niet gevonden.\n\n"
                f"Verwacht in:\n{os.path.join(_c_pinas(), 'Gedeeld', 'test_suite.py')}")

    def _open_backup_overzicht(self):
        """Start pinas_backup_beheer.pyw - via de gedeelde launcher, zodat
        een dubbelklik niet twee vensters naast elkaar opent."""
        ok, fout = pinas_launcher.open_programma(
            "pinas_backup_beheer.pyw",
            roots=[_script_dir(), _nas_root()],
            submappen=["", "Beheer"])
        if not ok:
            messagebox.showerror("Niet gevonden",
                "pinas_backup_beheer.pyw niet gevonden.\n"
                "Zet het bestand in Beheer\\ naast Pi_NAS_Menu.pyw")

    def _open_controle_beheer(self):
        """Start pinas_controle_beheer.pyw - via de gedeelde launcher, zodat
        een dubbelklik niet twee vensters naast elkaar opent."""
        ok, fout = pinas_launcher.open_programma(
            "pinas_controle_beheer.pyw",
            roots=[_script_dir(), _nas_root()],
            submappen=["", "Beheer"])
        if not ok:
            messagebox.showerror("Niet gevonden",
                "pinas_controle_beheer.pyw niet gevonden.\n"
                "Zet het bestand in Beheer\\ naast Pi_NAS_Menu.pyw")

    def _open_addons_beheer(self):
        """Start pinas_addons_beheer.pyw - via de gedeelde launcher, zodat
        een dubbelklik niet twee vensters naast elkaar opent."""
        ok, fout = pinas_launcher.open_programma(
            "pinas_addons_beheer.pyw",
            roots=[_script_dir(), _nas_root()],
            submappen=["", "Addons"])
        if not ok:
            messagebox.showerror("Niet gevonden",
                "pinas_addons_beheer.pyw niet gevonden.\n"
                "Zet het bestand in Addons\\ naast Pi_NAS_Menu.pyw")

    def _voer_setup_uit(self, keuzes):
        install_dir = _script_dir()
        nas_root = _nas_root()
        installer = None
        for p in [os.path.join(install_dir, "Beheer_install.bat"),
                  os.path.join(nas_root, "Beheer", "Beheer_install.bat")]:
            if os.path.exists(p):
                installer = p
                break

        # seagate_svc en server zijn PURE Pi-kant installaties -- horen
        # niet bij het Windows-side .bat-script, die heeft daar geen
        # logica voor (was eerder een dood vinkje: aanvinken deed niets).
        if keuzes.get("seagate_svc"):
            self._installeer_seagate_service_remote()

        args = []
        if keuzes.get("putty"): args += ["PUTTY=J"]
        if keuzes.get("vnc"):        args += ["VNC=J"]
        if keuzes.get("docker_pc"):
            args += ["DOCKER=J"]
            # Simulator map direct aanmaken na Docker installatie
            self.after(5000, lambda: self._run_simulator_bat("maak_simulator_map.bat"))
        if keuzes.get("pibackup"):   args += ["PIBACKUP=J"]
        if keuzes.get("schijven"):   args += ["SCHIJVEN=J"]
        if keuzes.get("server"):     args += ["SERVER=J"]

        # Alleen de .bat starten als er ook echt iets voor DIE installer
        # te doen is -- anders een leeg cmd-venster openen voor niets.
        if args:
            if not installer:
                messagebox.showerror("Setup",
                    "Beheer_install.bat niet gevonden.\nZorg dat alle bestanden aanwezig zijn.")
                return
            subprocess.Popen(["cmd", "/k", installer] + args,
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
        elif not keuzes.get("seagate_svc"):
            messagebox.showinfo("Setup", "Geen onderdelen geselecteerd.")

    def _installeer_seagate_service_remote(self):
        """Installeert/herstart de seagate-web systemd-service op de Pi
        rechtstreeks via SSH -- geen handmatig inloggen meer nodig.
        Toont een live-logvenster en meldt alleen succes als de service
        na installatie ECHT 'active' is volgens systemctl, niet eerder."""
        win = tk.Toplevel(self)
        win.title("Externe HDD service — Pi NAS Suite")
        win.configure(bg=BG)
        win.geometry("620x420")
        try: win.iconbitmap(_ico_pad())
        except: pass

        tk.Label(win, text="Externe HDD service (seagate-web) installeren op de Pi",
                 font=("Segoe UI", 11, "bold"), bg=BG, fg=FG).pack(pady=(12,4), padx=12, anchor="w")

        log_frame = tk.Frame(win, bg=PANEL)
        log_frame.pack(fill="both", expand=True, padx=12, pady=8)
        log_txt = tk.Text(log_frame, bg=PANEL, fg=FG, font=("Consolas", 9),
                           wrap="word", relief="flat")
        log_txt.pack(fill="both", expand=True, padx=6, pady=6)
        log_txt.tag_config("ok",   foreground=OK_C)
        log_txt.tag_config("err",  foreground=ERR_C)
        log_txt.tag_config("info", foreground=DIM)

        def log(tekst, tag=None):
            def doe():
                log_txt.insert("end", tekst + "\n", tag or "")
                log_txt.see("end")
            self.after(0, doe)

        def run():
            log("Verbinden met de Pi via SSH...", "info")

            # 1. Check of seagate_web.py al op de Pi staat; zo niet, eerst
            #    uploaden vanuit de lokale PiNAS-map.
            check = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=no",
                 "-o", "BatchMode=yes", f"pi@{PI_IP}",
                 "test -f /home/pi/seagate_web.py && echo JA || echo NEE"],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)

            if "JA" not in check.stdout:
                log("seagate_web.py ontbreekt op de Pi -- wordt geupload...", "info")
                lokaal_pad = None
                for kandidaat in [
                    os.path.join("C:\\", "PiNAS", "PiServer", "seagate_web.py"),
                    os.path.join(_nas_root(), "PiServer", "seagate_web.py"),
                    os.path.join(_script_dir(), "seagate_web.py"),
                ]:
                    if os.path.exists(kandidaat):
                        lokaal_pad = kandidaat
                        break
                if not lokaal_pad:
                    log("FOUT: seagate_web.py niet gevonden in PiNAS-map op deze PC.", "err")
                    log("Zorg dat dit bestand in C:\\PiNAS\\PiServer\\ staat en probeer opnieuw.", "err")
                    return
                up = subprocess.run(
                    ["scp", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=15",
                     lokaal_pad, f"pi@{PI_IP}:/home/pi/seagate_web.py"],
                    capture_output=True, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
                if up.returncode != 0:
                    log(f"FOUT: upload van seagate_web.py mislukt.\n{up.stderr.strip()}", "err")
                    return
                log("OK: seagate_web.py geupload.", "ok")

            # 2. Het .service-bestand aanmaken en installeren -- inline,
            #    niet afhankelijk van een bestand dat al zou moeten bestaan.
            log("Service-bestand aanmaken en installeren...", "info")
            svc_inhoud = (
                "[Unit]\\n"
                "Description=Pi NAS Seagate Web Controller\\n"
                "After=network.target\\n\\n"
                "[Service]\\n"
                "ExecStart=/usr/bin/python3 /home/pi/seagate_web.py\\n"
                "Restart=always\\n"
                "RestartSec=3\\n"
                "User=pi\\n\\n"
                "[Install]\\n"
                "WantedBy=multi-user.target\\n"
            )
            install_cmd = (
                f"printf '{svc_inhoud}' > /tmp/seagate-web.service && "
                "sudo cp /tmp/seagate-web.service /etc/systemd/system/seagate-web.service && "
                "sudo systemctl daemon-reload && "
                "sudo systemctl enable --now seagate-web && "
                "sleep 2 && "
                "systemctl is-active seagate-web"
            )
            r = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no",
                 "-o", "BatchMode=yes", f"pi@{PI_IP}", install_cmd],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)

            # 3. Echte verificatie -- alleen "active" in de laatste regel
            #    telt als daadwerkelijk succes, niets anders.
            laatste_regel = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
            if laatste_regel == "active":
                log("", None)
                log(f"OK: Externe HDD service is actief op http://{PI_IP}:8765", "ok")
                self.after(0, self._ververs_pi_status)
            else:
                log("", None)
                log("FOUT: service is NIET actief na installatie.", "err")
                if r.stderr.strip():
                    log(r.stderr.strip(), "err")
                detail = subprocess.run(
                    ["ssh", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=no",
                     "-o", "BatchMode=yes", f"pi@{PI_IP}",
                     "systemctl status seagate-web --no-pager -l 2>&1 | tail -n 12"],
                    capture_output=True, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
                if detail.stdout.strip():
                    log(detail.stdout.strip(), "err")

        threading.Thread(target=run, daemon=True).start()

    def _open_help(self):
        win = tk.Toplevel(self)
        win.title("Help — Pi NAS Suite")
        win.configure(bg=BG); win.resizable(False, False)
        win.geometry("560x820")
        win.resizable(True, True)
        try: win.iconbitmap(_ico_pad())
        except: pass
        win.update_idletasks()
        x = self.winfo_x() + (self.winfo_width()  - 520) // 2
        y = self.winfo_y() + (self.winfo_height() - 700) // 2
        win.geometry(f"+{x}+{y}")

        canvas = tk.Canvas(win, bg=BG, highlightthickness=0)
        scroll = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        frame = tk.Frame(canvas, bg=BG)
        canvas.create_window((0,0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        # 6 augustus 2026 (Frans: "help schermen niet scrolbaar met de muis,
        # dat moeten eigenlijk alle schermen zijn") - ontbrak hier. Later
        # zelfde dag: bind_all bleek GLOBAAL, dus Help hield de scroll vast
        # ook als je in Status klikte terwijl Help nog open stond -
        # _muiswiel_op_focus herbindt nu bij <FocusIn> per venster.
        _muiswiel_op_focus(win, canvas)

        def h(tekst):
            tk.Label(frame, text=tekst, font=("Segoe UI", 11, "bold"),
                     bg=BG, fg=ACCENT_PINAS, anchor="w").pack(fill="x", padx=16, pady=(12,2))
            tk.Frame(frame, bg=PANEL2, height=1).pack(fill="x", padx=16)

        def item(knop, uitleg):
            f = tk.Frame(frame, bg=BG)
            f.pack(fill="x", padx=16, pady=3)
            tk.Label(f, text=knop, font=("Segoe UI", 9, "bold"),
                     bg=BG, fg=FG, anchor="w", width=26).pack(side="left")
            tk.Label(f, text=uitleg, font=("Segoe UI", 9), bg=BG, fg=DIM,
                     anchor="w", wraplength=270, justify="left").pack(side="left")

        tk.Label(frame, text="Pi NAS Suite — Help",
                 font=("Segoe UI", 14, "bold"), bg=BG, fg=FG).pack(pady=(16,4))

        h("STATUS — DEZE PC")
        item("PC — software & schijven",
             "Compacte samenvatting in hoofdvenster. Groen = alles OK, oranje = deels, rood = probleem. "
             "Klik op de regel of open 'Status & details' voor volledig overzicht.")
        item("Status & details",
             "Volledig statusvenster. Toont: software (PuTTY/TigerVNC/Docker/Sync & Backup), "
             "schijven Opslag/Backup met vrije ruimte, Pi services, Pi hardware (model/RAM/SD/temperatuur), "
             "download links en logbestanden. Vernieuwen knop voor actuele data.")
        item("PuTTY",          "PuTTY SSH client — aanwezig als groen bolletje in Status venster.")
        item("TigerVNC",       "TigerVNC Viewer — aanwezig als groen bolletje in Status venster.")
        item("Docker Desktop", "Docker Desktop — aanwezig als groen bolletje in Status venster.")
        item("Sync & Backup", "PiNAS Sync (Sync & Backup) - aanwezig als groen bolletje in Status venster.")
        item("Opslag-schijf",      f"SSD gekoppeld via Samba (\\\\{PI_IP}\\Opslag), letter {_opslag_letter()}: op deze pc. Zichtbaar in Status venster.")
        item("Backup-schijf",      f"Externe HDD gekoppeld via Samba (\\\\{PI_IP}\\Backup), letter {_backup_letter()}: op deze pc. Zichtbaar in Status venster.")
        if _heeft_spiegel_backup():
            item("Spiegel Backup-schijf", f"Extra HDD aan de Pi (USB), backup van de Backup-schijf. Gekoppeld via Samba (\\\\{PI_IP}\\SpiegelBackup), letter {_spiegel_letter()}: op deze pc. Optioneel - alleen aanwezig als deze schijf aan de Pi hangt. Zichtbaar in Status venster.")

        h("STATUS — RASPBERRY PI")
        item("Raspberry Pi — services",
             "Compacte samenvatting in hoofdvenster. Groen = alle services actief. "
             "Open 'Status & details' voor details per service en Pi hardware info.")
        item("Samba",             "Bestandsshares actief — Opslag en Backup bereikbaar via Windows Verkenner.")
        item("Nextcloud",         "Eigen cloud — bereikbaar via browser op http://[Pi IP]/nextcloud. "
                                  "Klik op de Nextcloud URL in het hoofdvenster om direct te openen.")
        item("FileBrowser",       "Eenvoudig bestandsbeheer via browser op poort 8080.")
        item("Cockpit",           "Pi beheerpaneel via browser op poort 9090.")
        item("Externe HDD svc",   "Webservice voor HDD aan/uit via smart plug, poort 8765.")

        h("VERBINDEN")
        item("SSH via PowerShell", "Directe SSH verbinding. Geen extra software nodig.")
        item("SSH via PuTTY",      "SSH via PuTTY met PPK sleutel.")
        item("TigerVNC bureaublad","Grafisch bureaublad Pi op je scherm (poort 5901).")
        item("Schijven verbinden", "Koppelt de NAS-netwerkschijven (Opslag/Backup) schoon opnieuw als er een verdwenen is, bijvoorbeeld na de HDD uit/aan te zetten. Gebruikt het opgeslagen NAS-wachtwoord; ze zijn daarna direct zichtbaar in Verkenner. Geen vaste knop meer - verschijnt als blauwe balk bovenin zodra het nodig is, en staat ook in Status & details.")

        h("EXTERNE HDD")
        item("Aanzetten / Uitzetten", f"Externe HDD via smart plug. Na aanzetten: wacht ~15 sec op mount. Status toont 'gemount' als de Backup-schijf ({_backup_letter()}:) beschikbaar is.")

        h("BACKUP")
        item("Backup Beheer", "Centrale plek voor alle backup-acties: Synchronisatie, PC Image Backup, "
                               "Archief Backup Bewaking, Systeem-image maken (SD-kaart) en Backup-HDD "
                               "controleren/herstellen (e2fsck). Elke actie opent het bijbehorende "
                               "programma apart - niets wordt samengevoegd of automatisch na elkaar gestart.")

        h("ADDONS")
        item("Addons Beheer", "Centrale plek voor de 7 add-ons: Nextcloud, Pi-hole, ZeroTier, "
                               "Vaultwarden, de mobiele statuspagina, de Printserver en het "
                               "PiNAS Dashboard. Per add-on Installeren/Verwijderen.")

        h("SIMULATOR")
        # NAS Simulator map en Nextcloud-status verhuisd naar Status & details,
        # niet meer als losse regel op het hoofdscherm.
        item("Simulator starten",     "Start NAS simulator in Docker (localhost:5901). Knop in Beheer → Geavanceerd.")

        h("BEHEER")
        # 16 juli 2026: Herstel & Acties en Onderhoud gepromoveerd
        # naar het hoofdscherm; Controles is nieuw. NAS Map Beheer's
        # oude "Herstel & Acties"-tab is opgeheven: Structuurcheck en
        # Opruimen zijn verhuisd naar Controles (het waren toch controles),
        # de rest zat al eerder in Onderhoud. "Installatie & Herstel" heeft
        # de vrijgekomen plek op het hoofdmenu overgenomen.
        #
        # 5 augustus 2026 (Frans: "we hebben een top-down benadering nodig,
        # nieuwe installatie is een beetje ondergeschoven"): 3 wegen bestaan
        # al, maar stonden verspreid zonder ooit als geheel benoemd te zijn.
        # Dit item eerst, als hoogste-niveau-oriëntatie - verwijst naar de
        # al bestaande, gedetailleerde items hieronder i.p.v. ze te
        # herhalen (Frans: "we willen niets dubbel hebben").
        item("De 3 wegen: wachtwoord, reparatie, of nieuwe installatie",
             "Al aanwezig, hier op een rij:\n"
             "1. Wachtwoord kwijt/wijzigen - Onderhoud -> Beveiliging -> 'NAS wachtwoord'.\n"
             "2. Iets kapot op een BESTAANDE installatie - gerichte reparatietools: Onderhoud -> "
             "'Pi services' (Samba/FileBrowser/Cockpit herstellen), 'Windows onderdelen' (PuTTY/"
             "TigerVNC/schijven herstellen), Geavanceerd -> LanMan-fix, of 'Schijven verbinden' "
             "op het hoofdmenu.\n"
             "3. Volledig NIEUWE installatie (nieuwe Pi/pc) - zie 'De installatiereis' hieronder.")
        # 5 augustus 2026 (Frans: "dit ontdek ik zelf nu pas, moet overal
        # heel duidelijk zijn"): losse items voor Installatie & Herstel en
        # Distributie beschreven ieder hun eigen onderdeel, maar nergens
        # stond de VOLLEDIGE reis met verplicht/optioneel helder bij elkaar.
        # Dit item eerst, als overzicht, voordat de losse items volgen.
        # Zelfde dag, later: bleek een hele stap te ontbreken - Beheer_
        # install.bat (de bootstrap-installer voor een pc waar de suite nog
        # NIET op staat) was nog nooit gezien/gedocumenteerd. Nu als
        # beslisboom i.p.v. alleen een lineaire lijst, want het startpunt
        # bepaalt welke stap je nodig hebt.
        # 9 augustus 2026 (Frans: "de help hoeft hiervoor alleen naar de
        # handleiding te verwijzen") - dit item dupliceerde tot nu toe de
        # volledige tekst uit de Handleiding (inclusief beslisboom). Op
        # Frans' expliciete verzoek ingekort tot een korte samenvatting +
        # verwijzing, om dubbele tekst (en het risico dat de twee uit de
        # pas gaan lopen) te vermijden. De volledige, uitgewerkte reis met
        # beslisboom, de 4 wizardstappen in detail, en de 2 extra
        # verduidelijkingen (Pi Menu werkt zonder draaiende Pi; de
        # SD-kaart wordt geschreven via het externe programma Raspberry
        # Pi Imager, niet door Beheer_install.bat/Starter Kit) staan in de
        # Suite Handleiding, hoofdstuk 3.5.
        item("De installatiereis (van 0 naar werkend)",
             "Startpunt bepaalt de eerste stap: compleet nieuwe pc, suite staat er nog niet op? -> "
             "eerst Beheer_install.bat draaien (in de root van Starter Kit/GitHub). Suite staat al op "
             "deze pc? -> ga direct naar Installatie & Herstel (de verplichte wizard, 4 stappen).\n\n"
             "Voor de volledige reis - inclusief beslisboom, alle 4 wizardstappen in detail, en wat "
             "wel/niet automatisch gaat - zie de Suite Handleiding, hoofdstuk 3.5 "
             "('Installatie & Herstel, Controles, Onderhoud'), te openen via Onderhoud -> Publicatie.")
        item("Installatie & Herstel", "Start pi_nas_setup.pyw - begeleidt bij een nieuwe installatie, "
                                   "het voltooien van een gekopieerde installatie, of het herstellen van "
                                   "een kapotte, in 4 stappen (Gegevens, SD-kaart, Pi configureren, Windows "
                                   "afronden). Stap 3 installeert automatisch al Samba/Cockpit/FileBrowser "
                                   "op de Pi - dat hoef je er niet nog eens los bij te doen.")
        item("Controles",         "Structuurcheck (verwachte bestanden controleren), Opruimen (verouderde "
                                   "bestanden verwijderen), Suite testen, Diagnose uitvoeren (PC + Pi via "
                                   "SSH) en Log Bestanden Bekijken - allemaal op 1 plek, los van de "
                                   "installatiewizard.")
        item("Onderhoud",         "Pi services en Windows onderdelen installeren/herstellen, plus "
                                   "Publicatie (handleiding/topografie herbouwen), "
                                   "Distributie (Starter Kit, publieke versie), Geavanceerd, en Weergave "
                                   "(thema wisselen, kleuren kiezen via stalen).")

        h("ONDERHOUD")
        item("Pi services",       "Installeert of herstelt Samba, FileBrowser, Cockpit en Externe HDD service. "
                                  "Selecteer onderdelen en klik Uitvoeren. Bij een NIEUWE installatie doet "
                                  "Installatie & Herstel dit al automatisch - deze knop is voor een latere "
                                  "reparatie of als je er destijds bewust iets van hebt overgeslagen.")
        item("Windows onderdelen","Installeert PuTTY, TigerVNC, Docker, Sync & Backup en koppelt "
                                  "de Opslag-/Backup-schijven.")
        item("Publicatie",        "Suite handleiding en Topografie herbouwen, en de documentatie-consistentie controleren. Het functieoverzicht staat sinds 10 augustus 2026 als losse pagina in de presentatie, niet meer hier.")
        item("Distributie",       "Starter Kit ZIP bouwen: verpakt de suite geanonimiseerd (zonder jouw "
                                   "IP/wachtwoorden) in 1 ZIP-bestand voor een NIEUWE pc - doet zelf niets "
                                   "op een Pi of pc. Op de nieuwe plek gebruik je daarna 'Installatie & "
                                   "Herstel' om het pakket daadwerkelijk in te vullen en te installeren. "
                                   "'Publieke versie maken' is hetzelfde, maar voor GitHub.")
        item("Geavanceerd",       "Pi OS bijwerken, Python bijwerken, Pi NAS herstarten, LanMan-fix, Scripts "
                                  "uploaden naar Pi en Download links beheren.")
        item("Pi OS bijwerken",    "Onder Geavanceerd. Voert apt update + apt upgrade uit op de Pi via SSH. "
                                   "Opent een CMD venster met live output. Duurt 1-5 minuten.")
        item("Python bijwerken",  "Onder Geavanceerd. Installeert de nieuwste Python naast je huidige versie "
                                  "op Windows (python_bijwerken.bat). Nodig voor Suite testen/de Publicatie-"
                                  "builders. Vervangt niets - zet alleen PATH naar de nieuwe versie.")
        item("Pi NAS herstarten",    "Onder Geavanceerd. Herstart de Pi (sudo reboot) via SSH, met "
             "bevestiging. De verbinding valt kort weg zodra de Pi herstart - dat is normaal. Na "
             "30-60 sec weer bereikbaar.")
        item("NAS wachtwoord",    "Wijzigt Samba wachtwoord op Pi én in Windows Credential Manager tegelijk. "
                                  "Staat onder Beveiliging in Onderhoud.")

        h("CONTROLE")
        item("Structuurcheck",    "Controleert of alle verwachte bestanden er zijn en up-to-date zijn. "
                                  "Staat in Controles.")
        item("Conventies",        "Vaste regels van de suite op één plek: ASCII-only in .bat/.ps1, "
                                  "dry-run vóór destructieve acties, pinas_versies.json als ene bron "
                                  "van waarheid, waarom Toegang apart staat, enzovoort. Staat in "
                                  "Gedeeld\\CONVENTIES.md (9 augustus 2026).")
        item("Opruimen",          "Verouderde/overbodige bestanden opsporen en verwijderen. Staat in "
                                  "Controles.")
        item("Suite testen",      "84 kwaliteitschecks: bestanden, syntax (hele boom), documentatie-"
                                  "consistentie, packages, schijven, registry, Pi services, GUI-rooktest "
                                  "(elk venster met een mainloop() daadwerkelijk laten opstarten). "
                                  "Exporteerbaar naar CSV. Staat in Controles.")
        item("Diagnose uitvoeren","PC diagnose (lokale software/schijven) en Pi diagnose (nas_diagnose.sh "
                                  "via SSH). Staat in Controles.")
        item("Log Bestanden Bekijken", "Pi NAS Menu, PiNAS Sync en Externe HDD-logs. Staat in Controles.")

        h("TOOLS")
        item("Status",     "Gedetailleerd statusvenster: PC software, schijven, Pi services "
                                     "(Samba/Nextcloud/FileBrowser/Cockpit), hardware (model/RAM/temperatuur/uptime), "
                                     "Pi scripts sync met upload knop, en logbestanden. Knop in de footer.")

        h("VEELVOORKOMENDE PROBLEMEN")
        item("Pi niet bereikbaar",        f"Pi aan? Zelfde netwerk? Probeer: ping {PI_IP}")
        item("Opslag/Backup verdwenen",           f"Klik op de blauwe balk 'Schijven verbinden' die bovenin verschijnt zodra Opslag ({_opslag_letter()}:) of Backup ({_backup_letter()}:) niet in orde is (of op dezelfde knop in Status & details). Dat koppelt de netwerkschijven schoon opnieuw. Werkt dat niet met 'Toegang geweigerd' of Systeemfout 5, gebruik dan LanMan-fix in Onderhoud.")
        item("TigerVNC mislukt",          "SSH → vncserver -kill :1 → vncserver :1 -geometry 1920x1080 -depth 24 -localhost no")
        item("Externe HDD niet gemount",  "Wacht 15-20 sec na aanzetten. Status wordt automatisch bijgewerkt.")
        item("Sync & Backup niet gevonden", "Beheer -> Windows onderdelen -> Sync & Backup installeren.")

        tk.Button(frame, text="Sluiten", command=win.destroy,
                  bg=PANEL2, fg=FG, font=("Segoe UI", 10), relief="flat",
                  cursor="hand2", pady=8, borderwidth=0).pack(pady=16, padx=16, fill="x")

    # ── ZeroTier-Windows-dienst (alleen voor het grijs maken van 10.90.x-
    # links in Status - Starten/Stoppen zelf zit in Addons Beheer) ─────────
    def _start_zt_windows_check(self):
        """Vraagt via een achtergrondthread de lokale ZeroTier-dienst-status
        op en cachet 'm in self._zt_windows_status - NOOIT rechtstreeks
        aanroepen tijdens het opbouwen van een scherm (PowerShell-opstart
        duurt 1-3 sec en zou anders de hele Tkinter-app bevriezen, zie
        4 augustus 2026-fix)."""
        def _werk():
            status = check_zerotier_windows_dienst()
            def _toepassen():
                self._zt_windows_status = status
                # Alleen het Status-venster herbouwen als het nu open staat
                # en de status is veranderd - voorkomt onnodig herbouwen.
                if hasattr(self, '_status_win') and self._status_win:
                    try:
                        if self._status_win.winfo_exists():
                            self._vul_status_venster()
                    except Exception:
                        pass
            self.after(0, _toepassen)
        threading.Thread(target=_werk, daemon=True).start()

    # ── Externe HDD ───────────────────────────────────────────────────────────────
    def _seagate_status_update(self):
        def fetch():
            try:
                r = urllib.request.urlopen(f"{SEAGATE_URL}/status", timeout=3)
                data = json.loads(r.read())
                aan = data.get("aan", False)
                gemount = data.get("gemount", False)
            except:
                aan = None
                gemount = False
            self.after(0, lambda: self._seagate_update_ui(aan, gemount))
        threading.Thread(target=fetch, daemon=True).start()
        self.after(10000, self._seagate_status_update)

    def _seagate_update_ui(self, aan, gemount=False):
        # 4 augustus 2026 (Frans): "Schijven verbinden" verscheen ook als de
        # HDD gewoon bewust uitstond (geen fout, een keuze) - de herstel-
        # logica moet dit onderscheid kunnen maken, dus bewaren als attribuut.
        self._extern_hdd_aan = aan
        if aan is None:
            self.lbl_seagate.config(text="● Externe HDD — onbekend", fg=DIM)
            self.btn_aan.config(state="normal", bg=WARN)
            self.btn_uit.config(state="disabled", bg=PANEL2)
        elif aan:
            lbl = "● Externe HDD AAN — gemount" if gemount else "● Externe HDD AAN — niet gemount!"
            kleur = OK_C if gemount else YELLOW
            self.lbl_seagate.config(text=lbl, fg=kleur)
            self.btn_aan.config(state="disabled", bg=PANEL2)
            self.btn_uit.config(state="normal", bg=RED_C)
        else:
            self.lbl_seagate.config(text="● Externe HDD UIT", fg=ERR_C)
            self.btn_aan.config(state="normal", bg=WARN)
            self.btn_uit.config(state="disabled", bg=PANEL2)

    def _seagate_aan(self):
        log.info("Externe HDD aanzetten gestart")
        try:
            urllib.request.urlopen(f"{SEAGATE_URL}/actie/aan", timeout=5)
            # Toon wacht-status terwijl plug opstart en mount -a loopt (~15 sec)
            self.lbl_seagate.config(text="⏳ Externe HDD — wachten op mount...", fg=DIM)
            self.btn_aan.config(state="disabled", bg=PANEL2)
            self.btn_uit.config(state="disabled", bg=PANEL2)
            # Na 18 sec: Z: koppelen in Windows en status verversen
            self.after(18000, self._koppel_backup_en_ververs)
        except:
            messagebox.showerror("Externe HDD — aanzetten mislukt",
            "De externe HDD kon niet worden aangezet.\n\n"
            "Mogelijke oorzaken:\n"
            "  • Smart plug niet bereikbaar (controleer stroom en netwerk)\n"
            "  • IP-adres van de Pi klopt niet (check picontrol.cfg)\n"
            "  • seagate-web service draait niet op de Pi\n\n"
            "Tip: probeer de Pi diagnose via Tools → Diagnose uitvoeren")

    def _open_status(self):
        """Open het volledige status venster."""
        # Hergebruik bestaand venster als open
        if hasattr(self, '_status_win') and self._status_win:
            try:
                if self._status_win.winfo_exists():
                    self._status_win.lift()
                    return
            except: pass

        win = tk.Toplevel(self)
        self._status_win = win
        win.title("Status — Pi NAS Suite")
        win.configure(bg=BG)
        win.resizable(True, True)
        # 6 augustus 2026 (Frans, zelfde reden als Onderhoud): 1250px vaste
        # hoogte past op veel schermen niet - nu schermbewust begrensd.
        win.update_idletasks()
        _breedte, _gewenste_hoogte = 740, 1250
        _hoogte = min(_gewenste_hoogte, win.winfo_screenheight() - 80)
        win.geometry(f"{_breedte}x{_hoogte}")
        win.minsize(600, 700)
        try: win.iconbitmap(_ico_pad())
        except: pass
        win.update_idletasks()
        _x = self.winfo_x() + self.winfo_width() + 10
        _y = 20
        win.geometry(f"+{_x}+{_y}")

        # Header - 5 augustus 2026 (Frans: headers niet consequent, overal
        # een Help-knop) - omgezet naar de gedeelde maak_header(), zelfde
        # reden als Onderhoud. Hergebruikt _open_help(), geen dubbele inhoud.
        hdr = maak_header(win, "Status", subtekst=f"bijgewerkt: {BIJGEWERKT}",
                           kleur=ACCENT_PICONTROL)
        # In hdr.rij pakken (de titelregel zelf), niet in hdr - zelfde
        # reden als Onderhoud (5 augustus 2026, Frans gemeld: Vernieuwen
        # en Help liever op de regel van "Status" zelf).
        help_knop = maak_knop(hdr.rij, "?  Help", self._open_help, stijl="secundair")
        help_knop.pack_forget()
        help_knop.pack(side="right")
        vernieuw_knop = maak_knop(hdr.rij, "↻  Vernieuwen",
                  lambda: (self._vul_status_venster(), self._start_zt_windows_check()),
                  stijl="secundair")
        vernieuw_knop.pack_forget()
        vernieuw_knop.pack(side="right", padx=10)

        # Scrollbaar body
        canvas = tk.Canvas(win, bg=BG, highlightthickness=0)
        scroll = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._status_frame = tk.Frame(canvas, bg=BG, padx=16, pady=12)
        self._status_canvas_win = canvas.create_window((0,0), window=self._status_frame, anchor="nw")
        self._status_frame.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(
            self._status_canvas_win, width=e.width - 4))
        # Muiswiel - 6 augustus 2026: _muiswiel_op_focus herbindt ook bij
        # <FocusIn>, dus dit was het venster waar Frans naartoe klikte
        # terwijl Help open bleef scrollen.
        _muiswiel_op_focus(win, canvas)
        # 18 juli 2026: bind_all is GLOBAAL - zonder dit geeft dit venster de
        # muiswiel-scroll bij sluiten niet terug aan het hoofdmenu.
        win.bind("<Destroy>", lambda e: self._herstel_hoofd_muiswiel() if e.widget is win else None)

        self._vul_status_venster()

    def _vul_status_venster(self):
        """Vult het status venster met actuele data."""
        if not hasattr(self, '_status_frame'): return
        try:
            if not self._status_frame.winfo_exists(): return
        except: return

        for w in self._status_frame.winfo_children(): w.destroy()
        frame = self._status_frame

        # ── WAARSCHUWING: add-on(s) verouderd op de Pi ──────────────────────
        # Niet te missen, bovenaan, ongeacht of je hier speciaal voor komt -
        # dit scherm open je toch al standaard (Frans, 30 juli 2026: "ik
        # vergeet dit soort dingen over een half jaar, ik wil hier een niet
        # te missen signaal, geen scherm dat ik apart moet onthouden open te
        # doen").
        verouderd = getattr(self, '_addon_verouderd', [])
        if verouderd:
            waarschuw = tk.Frame(frame, bg=WARN, pady=8, padx=12)
            waarschuw.pack(fill="x", pady=(0, 10))
            tk.Label(waarschuw,
                     text="⚠  Add-on(s) verouderd op de Pi - lokaal bestand is gewijzigd, "
                          "maar nog niet geupload/geinstalleerd:",
                     font=("Segoe UI", 9, "bold"), bg=WARN, fg="#ffffff",
                     anchor="w", justify="left", wraplength=520).pack(fill="x")
            tk.Label(waarschuw, text="  " + ", ".join(verouderd),
                     font=("Segoe UI", 9, "bold"), bg=WARN, fg="#ffffff",
                     anchor="w").pack(fill="x")
            tk.Label(waarschuw,
                     text="Open Addons Beheer en klik daar op 'Installeren' bij elk "
                          "hierboven genoemd item.",
                     font=("Segoe UI", 8), bg=WARN, fg="#ffffff",
                     anchor="w").pack(fill="x", pady=(2, 0))

        def sectie_kop(tekst, kleur=ACCENT_PINAS):
            f = tk.Frame(frame, bg=kleur, pady=6, padx=12)
            f.pack(fill="x", pady=(10,4))
            tk.Label(f, text=tekst, font=("Segoe UI", 10, "bold"),
                     bg=kleur, fg="#ffffff").pack(anchor="w")

        def status_rij(parent, naam, ok, waarde="", deels=False, na=False):
            # na ("niet van toepassing") - neutraal grijs, voor optionele
            # add-ons die (nog) niet geinstalleerd zijn. Bewust ANDERS dan
            # rood: niet geinstalleerd is geen fout, alleen een keuze -
            # rood blijft gereserveerd voor "hoort te draaien maar doet het niet".
            if na:
                kleur = DIM
            else:
                kleur = OK_C if (ok and not deels) else (WARN if deels else ERR_C)
            symbool = "●"
            rij = tk.Frame(parent, bg=BG)
            rij.pack(fill="x", pady=1)
            tk.Label(rij, text=symbool, font=("Segoe UI", 10),
                     bg=BG, fg=kleur, width=2).pack(side="left")
            tk.Label(rij, text=naam, font=("Segoe UI", 9),
                     bg=BG, fg=FG, width=22, anchor="w").pack(side="left")
            tk.Label(rij, text=waarde or ("OK" if ok else "Ontbreekt"),
                     font=("Segoe UI", 9), bg=BG,
                     fg=kleur).pack(side="left", fill="x", expand=True)

        def info_rij(parent, naam, waarde, kleur=None):
            rij = tk.Frame(parent, bg=BG)
            rij.pack(fill="x", pady=1)
            tk.Label(rij, text="  " + naam, font=("Segoe UI", 9),
                     bg=BG, fg=FG, width=24, anchor="w").pack(side="left")
            tk.Label(rij, text=waarde, font=("Segoe UI", 9),
                     bg=BG, fg=kleur or FG).pack(side="left")

        # ── DEZE PC ──────────────────────────────────────────────────────────
        sectie_kop("💻  Deze PC — software", ACCENT_PINAS)
        _putty = putty_exe()
        status_rij(frame, "PuTTY",         check_putty(),
                   f"OK  {_putty}" if _putty else "Niet gevonden")
        _vnc = tigervnc_exe()
        status_rij(frame, "TigerVNC",      check_tigervnc(),
                   f"OK  {_vnc}" if _vnc else "Niet gevonden")
        _docker = check_docker_desktop()
        status_rij(frame, "Docker Desktop", _docker,
                   "OK" if _docker else "Niet gevonden")

        # ZeroTier-Windows-dienst (starten/stoppen) verhuisd naar Addons
        # Beheer (4 augustus 2026, Frans: wil dit consistent met de andere
        # diensten daar, niet apart hier in Status).

        _pyv = _sys.version_info
        _py_ok = _pyv >= (3, 10)
        status_rij(frame, "Python", _py_ok,
                   f"{_pyv.major}.{_pyv.minor}.{_pyv.micro}"
                   + ("" if _py_ok else "  (minimaal 3.10 vereist)"))
        _pb = pibackup_pad("pinas_sync_app.pyw")
        status_rij(frame, "Sync & Backup", check_pibackup(),
                   f"OK  {_pb}" if _pb else "Niet gevonden")
        sim_ok = check_simulator_map()
        status_rij(frame, "NAS Simulator",   sim_ok,
                   r"C:\PiNAS\NAS_Simulator" + "\\" if sim_ok else "Map ontbreekt", deels=not sim_ok)

        # Wachtwoord
        try:
            from pinas_wachtwoord import wachtwoord_beschikbaar
            ww_ok = wachtwoord_beschikbaar("samba")
        except:
            ww_ok = False
        status_rij(frame, "Samba wachtwoord", ww_ok,
                   "Opgeslagen in Credential Manager" if ww_ok else "Niet ingesteld")



        sectie_kop("🗄  Deze PC — schijven", ACCENT_PINAS)
        _naam_opslag = "Opslag"
        _naam_backup = "Backup"
        _letter_opslag = _opslag_letter()
        _letter_backup = _backup_letter()
        y_ok = check_share(_naam_opslag, _letter_opslag, PI_IP)
        z_ok = check_share(_naam_backup, _letter_backup, PI_IP)
        status_rij(frame, f"Opslag ({_letter_opslag}:, SSD)",  y_ok)
        status_rij(frame, f"Backup ({_letter_backup}:, HDD)",  z_ok)
        # Spiegel Backup (H:) is optioneel - alleen tonen op installaties
        # die deze schijf ook echt hebben (staat dan in picontrol.cfg).
        _heeft_h = _heeft_spiegel_backup()
        h_ok = False
        if _heeft_h:
            _letter_spiegel = _spiegel_letter()
            h_ok = check_share("SpiegelBackup", _letter_spiegel, PI_IP)
            status_rij(frame, f"Spiegel Backup ({_letter_spiegel}:, HDD)", h_ok)
        ssh_ok = check_ssh()
        status_rij(frame, "SSH-verbinding met de Pi", ssh_ok)
        if not ssh_ok:
            tk.Button(frame, text="🔑  SSH sleutel herstellen",
                      font=("Segoe UI", 9, "bold"), bg=WARN, fg="#ffffff",
                      relief="flat", cursor="hand2", borderwidth=0, pady=5,
                      command=zorg_voor_ppk).pack(fill="x", pady=(4,2))
        hdd_bewust_uit = getattr(self, '_extern_hdd_aan', True) is False
        if not y_ok or (not z_ok and not hdd_bewust_uit) or (_heeft_h and not h_ok):
            tk.Button(frame, text="🔌  Schijven verbinden",
                      font=("Segoe UI", 9, "bold"), bg=WARN, fg="#ffffff",
                      relief="flat", cursor="hand2", borderwidth=0, pady=5,
                      command=self._verbind_schijven).pack(fill="x", pady=(4,2))

        # Schijfruimte
        _schijfruimte_lijst = [(_letter_opslag, "Opslag"), (_letter_backup, "Backup")]
        if _heeft_h:
            _schijfruimte_lijst.append((_letter_spiegel, "Spiegel Backup"))
        for letter, naam in _schijfruimte_lijst:
            try:
                import shutil
                pad = letter + ":\\"
                if os.path.exists(pad):
                    t, u, v = shutil.disk_usage(pad)
                    info_rij(frame, f"{naam} ({letter}:) ruimte",
                             f"{v//(1024**3):.0f} GB vrij van {t//(1024**3):.0f} GB")
            except: pass

        sectie_kop("🔗  Snelle links — services (geen wachtwoorden)", ACCENT_PINAS)
        import webbrowser as _wb2

        def link_rij(parent, naam, url):
            rij = tk.Frame(parent, bg=BG)
            rij.pack(fill="x", pady=1)
            tk.Label(rij, text="🔗", font=("Segoe UI", 9),
                     bg=BG, fg=ACCENT_PINAS, width=2).pack(side="left")
            lbl = tk.Label(rij, text=f"{naam} — {url}",
                     font=("Segoe UI", 9), bg=BG, fg=ACCENT_PINAS,
                     cursor="hand2", anchor="w")
            lbl.pack(side="left", fill="x", expand=True)
            lbl.bind("<Button-1>", lambda e, u=url: _wb2.open(u))
            rij.bind("<Button-1>", lambda e, u=url: _wb2.open(u))

        def open_pad_rij(parent, naam, pad, uitleg=""):
            rij = tk.Frame(parent, bg=BG)
            rij.pack(fill="x", pady=1)
            tk.Label(rij, text="📂", font=("Segoe UI", 9),
                     bg=BG, fg=ACCENT_PINAS, width=2).pack(side="left")
            lbl = tk.Label(rij, text=f"{naam} — {pad}",
                     font=("Segoe UI", 9), bg=BG, fg=ACCENT_PINAS,
                     cursor="hand2", anchor="w")
            lbl.pack(side="left", fill="x", expand=True)
            def _open(e=None, p=pad):
                try: os.startfile(p)
                except Exception: pass
            lbl.bind("<Button-1>", _open)
            rij.bind("<Button-1>", _open)

        def na_rij(parent, naam, tekst):
            """Grijze, niet-klikbare regel voor een optionele add-on die (nog)
            niet actief is - i.p.v. de link gewoon weg te laten."""
            rij = tk.Frame(parent, bg=BG)
            rij.pack(fill="x", pady=1)
            tk.Label(rij, text="○", font=("Segoe UI", 9),
                     bg=BG, fg=DIM, width=2).pack(side="left")
            tk.Label(rij, text=f"{naam} — {tekst}",
                     font=("Segoe UI", 9), bg=BG, fg=DIM, anchor="w").pack(
                     side="left", fill="x", expand=True)

        def _status_naar_items(status, naam, maak_url):
            """Bouwt (lokaal_item, zt_item) uit dezelfde status - zelfde
            na/link-patroon voor beide, alleen het adres verschilt (4
            augustus 2026, Frans wil ook de ZeroTier-adressen in Status
            zien, niet alleen lokaal)."""
            if status == 'active':
                return (("link", naam, maak_url(PI_IP)),
                        ("link", f"{naam} (ZeroTier)", maak_url(ZT_IP)))
            if status == 'stopped':
                tekst = "geinstalleerd, maar gestopt"
            elif status == 'absent':
                tekst = "n.v.t. (niet geinstalleerd)"
            else:
                tekst = "onbekend - Pi niet bereikbaar?"
            return (("na", naam, tekst), ("na", f"{naam} (ZeroTier)", tekst))

        sp_status_snel = getattr(self, '_sp_status', 'onbekend')
        sp_item, sp_item_zt = _status_naar_items(
            sp_status_snel, "PiNAS Status (mobiel)", lambda ip: f"http://{ip}:8090")

        pihole_status_snel = getattr(self, '_pihole_status', 'onbekend')
        pihole_item, pihole_item_zt = _status_naar_items(
            pihole_status_snel, "Pi-hole", lambda ip: f"http://{ip}:8081/admin")

        # ZeroTier dashboard zelf is een externe website (my.zerotier.com),
        # geen adres op de Pi - dus geen ZT-variant hiervan nodig.
        zerotier_status_snel = getattr(self, '_zerotier_status', 'onbekend')
        if zerotier_status_snel == 'active':
            zerotier_item = ("link", "ZeroTier dashboard", "https://my.zerotier.com")
        elif zerotier_status_snel == 'stopped':
            zerotier_item = ("na", "ZeroTier dashboard", "geinstalleerd, maar gestopt")
        elif zerotier_status_snel == 'absent':
            zerotier_item = ("na", "ZeroTier dashboard", "n.v.t. (niet geinstalleerd)")
        else:
            zerotier_item = ("na", "ZeroTier dashboard", "onbekend - Pi niet bereikbaar?")

        vw_status_snel = getattr(self, '_vw_status', 'onbekend')
        vw_item, vw_item_zt = _status_naar_items(
            vw_status_snel, "Vaultwarden", lambda ip: f"https://{ip}:8443")

        printer_status_snel = getattr(self, '_printer_status', 'onbekend')
        printer_item, printer_item_zt = _status_naar_items(
            printer_status_snel, "Printserver (CUPS)", lambda ip: f"http://{ip}:631/admin")

        dashboard_status_snel = getattr(self, '_dashboard_status', 'onbekend')
        dashboard_item, dashboard_item_zt = _status_naar_items(
            dashboard_status_snel, "PiNAS Dashboard", lambda ip: f"http://{ip}:8095")

        link_items = [
            ("link", "Nextcloud",    f"http://{PI_IP}/nextcloud"),
            ("link", "Nextcloud (ZeroTier)", f"http://{ZT_IP}/nextcloud"),
            ("link", "FileBrowser",  f"http://{PI_IP}:8080"),
            ("link", "FileBrowser (ZeroTier)", f"http://{ZT_IP}:8080"),
            ("link", "Cockpit",      f"http://{PI_IP}:9090"),
            ("link", "Cockpit (ZeroTier)", f"http://{ZT_IP}:9090"),
            pihole_item, pihole_item_zt,
            sp_item, sp_item_zt,
            ("pad",  f"Opslag ({_opslag_letter()}:, SSD)", fr"\\{PI_IP}\Opslag"),
            ("pad",  f"Opslag ({_opslag_letter()}:, SSD, ZeroTier)", fr"\\{ZT_IP}\Opslag"),
            ("pad",  f"Backup ({_backup_letter()}:, HDD)", fr"\\{PI_IP}\Backup"),
            ("pad",  f"Backup ({_backup_letter()}:, HDD, ZeroTier)", fr"\\{ZT_IP}\Backup"),
            zerotier_item,
            vw_item, vw_item_zt,
            printer_item, printer_item_zt,
            dashboard_item, dashboard_item_zt,
        ]
        # Spiegel Backup (H:) is optioneel - alleen op installaties die
        # deze schijf hebben (Fase 2 van de Qnap-rename, 8 augustus 2026).
        if _heeft_spiegel_backup():
            link_items.extend([
                ("pad", f"Spiegel Backup ({_spiegel_letter()}:, HDD)", fr"\\{PI_IP}\SpiegelBackup"),
                ("pad", f"Spiegel Backup ({_spiegel_letter()}:, HDD, ZeroTier)", fr"\\{ZT_IP}\SpiegelBackup"),
            ])
        # 4 augustus 2026 (Frans): als de lokale ZeroTier-Windows-dienst uit
        # staat, zijn alle 10.90.x-adressen sowieso onbereikbaar vanaf deze
        # pc - dan moeten ze grijs/niet-klikbaar worden i.p.v. een link te
        # tonen die toch alleen maar vastloopt. Gebruikt de GECACHETE status
        # (zie _start_zt_windows_check) - NOOIT hier rechtstreeks aanroepen,
        # dat bevriest de hele app (PowerShell-opstart duurt 1-3 sec).
        #
        # 6 augustus 2026 (Frans: "verschil overeenkomst en dubbel komt niet
        # eenduidig over... dit moet slimmer kunnen"): alleen nog overschrijven
        # als het item ANDERS EEN WERKENDE LINK zou zijn geweest (typ=="link").
        # Was een dienst al om een andere reden grijs (bijv. Printserver
        # "geinstalleerd, maar gestopt"), dan blijft die eigen, specifiekere
        # reden staan - de ZeroTier-tekst overschreef dat voorheen blind,
        # wat de indruk wekte dat ALLEEN ZeroTier de reden was, terwijl de
        # dienst zelf ook al uit stond.
        if getattr(self, '_zt_windows_status', 'onbekend') != "actief":
            link_items = [
                ("na", naam, "ZeroTier-dienst (Windows) staat uit")
                if (typ in ("link", "pad") and naam.rstrip().endswith("ZeroTier)"))
                else (typ, naam, waarde)
                for (typ, naam, waarde) in link_items
            ]
        import math as _math
        splits = _math.ceil(len(link_items) / 2)
        cols_frame = tk.Frame(frame, bg=BG)
        cols_frame.pack(fill="x")
        col1 = tk.Frame(cols_frame, bg=BG)
        col2 = tk.Frame(cols_frame, bg=BG)
        col1.pack(side="left", fill="both", expand=True, padx=(0, 6))
        col2.pack(side="left", fill="both", expand=True, padx=(6, 0))
        for i, (typ, naam, waarde) in enumerate(link_items):
            doel = col1 if i < splits else col2
            if typ == "link":
                link_rij(doel, naam, waarde)
            elif typ == "na":
                na_rij(doel, naam, waarde)
            else:
                open_pad_rij(doel, naam, waarde)

        sectie_kop("📦  Download links", ACCENT_PINAS)
        ini_pad = os.path.join(_nas_root(), "Gedeeld", "download_links.ini")
        if os.path.exists(ini_pad):
            status_rij(frame, "download_links.ini", True, ini_pad)
        else:
            status_rij(frame, "download_links.ini", False, "Niet gevonden in Gedeeld\\")
        # 16 juli 2026: expliciete toelichting - "Lokaal aanwezig" zegt hier
        # alleen dat het installatiebestand in Installatie\ staat, NIET dat
        # het programma zelf al (bijgewerkt) geinstalleerd is. Zie Windows
        # onderdelen hierboven voor de echte installatiestatus.
        tk.Label(frame, text="'Lokaal aanwezig' = installatiebestand staat klaar in "
                            "Installatie\\ - zegt niets over of het al geinstalleerd is.",
                 font=("Segoe UI", 8), bg=BG, fg=DIM, wraplength=480,
                 justify="left").pack(anchor="w", pady=(2,4))
        for naam, bestand in [
            ("TigerVNC installer-bestand", "tigervnc*.exe"),
            ("Docker installer-bestand",   "Docker Desktop Installer.exe"),
            ("Python installer-bestand",   "python-3*.exe"),
        ]:
            import glob
            inst_map = os.path.join(_nas_root(), "Installatie")
            gevonden = glob.glob(os.path.join(inst_map, bestand))
            if gevonden:
                info_rij(frame, naam, "Lokaal aanwezig", OK_C)
            else:
                info_rij(frame, naam, "Wordt gedownload bij installatie", DIM)

        # ── RASPBERRY PI ─────────────────────────────────────────────────────
        # 6 augustus 2026 (Frans: "ik zou 3 kolommen willen: geinstalleerd,
        # lokaal, zerotier (actief, niet actief - als niet geinstalleerd is
        # het lokaal en bij zerotier natuurlijk niet actief)"): 1 gedeelde
        # rij-functie i.p.v. de losse if/elif-blokken per dienst hieronder -
        # de cascade (niet geinstalleerd -> automatisch beide kolommen
        # "niet actief") zit hier ingebouwd, niet per dienst herhaald.
        def dienst_rij(parent, naam, status, zt_relevant=True):
            """status: 'active'/'stopped'/'absent'/'onbekend', of een bool
            (True->'active', False->'absent' - voor diensten zonder eigen
            gestopt-detectie zoals Samba/Nextcloud/FileBrowser/Cockpit/
            Externe HDD svc). zt_relevant=False voor diensten zonder eigen
            ZeroTier-toegangspad (Externe HDD svc, ZeroTier zelf)."""
            if isinstance(status, bool):
                status = "active" if status else "absent"
            geinstalleerd = status in ("active", "stopped")
            lokaal_actief = (status == "active")
            zt_windows_actief = (getattr(self, '_zt_windows_status', 'onbekend') == "actief")
            zerotier_actief = zt_relevant and lokaal_actief and zt_windows_actief

            rij = tk.Frame(parent, bg=BG)
            rij.pack(fill="x", pady=1)
            tk.Label(rij, text=naam, font=("Segoe UI", 9),
                     bg=BG, fg=FG, width=22, anchor="w").pack(side="left")
            tk.Label(rij, text=("Ja" if geinstalleerd else "Nee"), font=("Segoe UI", 9),
                     bg=BG, fg=(OK_C if geinstalleerd else DIM), width=13, anchor="w").pack(side="left")
            tk.Label(rij, text=("Actief" if lokaal_actief else "Niet actief"), font=("Segoe UI", 9),
                     bg=BG, fg=(OK_C if lokaal_actief else DIM), width=13, anchor="w").pack(side="left")
            if zt_relevant:
                tk.Label(rij, text=("Actief" if zerotier_actief else "Niet actief"), font=("Segoe UI", 9),
                         bg=BG, fg=(OK_C if zerotier_actief else DIM), width=13, anchor="w").pack(side="left")
            else:
                tk.Label(rij, text="n.v.t.", font=("Segoe UI", 9),
                         bg=BG, fg=DIM, width=13, anchor="w").pack(side="left")

        sectie_kop("🖥  Raspberry Pi — services", ACCENT_PINAS)
        _kop = tk.Frame(frame, bg=BG)
        _kop.pack(fill="x", pady=(2,4))
        tk.Label(_kop, text="", font=("Segoe UI", 8, "bold"), bg=BG, fg=DIM, width=22, anchor="w").pack(side="left")
        tk.Label(_kop, text="Geïnstalleerd", font=("Segoe UI", 8, "bold"), bg=BG, fg=DIM, width=13, anchor="w").pack(side="left")
        tk.Label(_kop, text="Lokaal", font=("Segoe UI", 8, "bold"), bg=BG, fg=DIM, width=13, anchor="w").pack(side="left")
        tk.Label(_kop, text="ZeroTier", font=("Segoe UI", 8, "bold"), bg=BG, fg=DIM, width=13, anchor="w").pack(side="left")

        pi_statussen = getattr(self, '_pi_statussen', [])
        # Externe HDD svc: intern-only, geen eigen ZeroTier-toegangspad
        # (zelfde vaste uitzondering als elders in de suite).
        _geen_zt = {"Externe HDD svc", "Backup-schijf gemount"}
        if pi_statussen:
            for naam, ok in pi_statussen:
                dienst_rij(frame, naam, ok, zt_relevant=(naam not in _geen_zt))
        else:
            tk.Label(frame, text="  ○  Services ophalen...",
                     font=("Segoe UI", 9), bg=BG, fg=DIM).pack(anchor="w", pady=4)

        pihole_status = getattr(self, '_pihole_status', 'onbekend')
        dienst_rij(frame, "Pi-hole", pihole_status)

        # ZeroTier (Pi) zelf: geen zinnig "via ZeroTier bereikbaar"-concept
        # (je kunt niet via ZeroTier bij de ZeroTier-dienst die de
        # verbinding zelf moet leggen) - vandaar zt_relevant=False.
        zerotier_status = getattr(self, '_zerotier_status', 'onbekend')
        dienst_rij(frame, "ZeroTier (Pi)", zerotier_status, zt_relevant=False)

        vw_status = getattr(self, '_vw_status', 'onbekend')
        dienst_rij(frame, "Vaultwarden", vw_status)

        sp_status = getattr(self, '_sp_status', 'onbekend')
        dienst_rij(frame, "PiNAS Status (mobiel)", sp_status)

        dashboard_status = getattr(self, '_dashboard_status', 'onbekend')
        dienst_rij(frame, "PiNAS Dashboard", dashboard_status)

        # Pi bereikbaarheid
        ping_tekst = self.lbl_ping.cget("text")
        ping_ok = "bereikbaar" in ping_tekst and "niet" not in ping_tekst
        status_rij(frame, "Pi bereikbaar", ping_ok, PI_IP)

        # Pi hardware — via SSH ophalen
        sectie_kop("⚙️  Raspberry Pi — hardware", ACCENT_PINAS)
        hw_frame = tk.Frame(frame, bg=BG)
        hw_frame.pack(fill="x")
        hw_lbl = tk.Label(hw_frame, text="  Ophalen via SSH...",
                          font=("Segoe UI", 9), bg=BG, fg=DIM, anchor="w")
        hw_lbl.pack(fill="x")

        def haal_hardware():
            try:
                cmd = (
                    "echo MODEL:$(strings /proc/device-tree/model 2>/dev/null | head -1); "
                    "echo RAM:$(free -h | awk '/Mem/{print $2}'); "
                    "echo SDCARD:$(df -h / | awk 'NR==2{print $2}'); "
                    "echo TEMP:$(vcgencmd measure_temp 2>/dev/null || echo n/a); "
                    "echo UPTIME:$(uptime -p 2>/dev/null)"
                )
                r = subprocess.run(
                        ["ssh",
                         "-o", "ConnectTimeout=8",
                         "-o", "StrictHostKeyChecking=no",
                         f"pi@{PI_IP}", cmd],
                        capture_output=True, text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
                data = {}
                for regel in r.stdout.splitlines():
                    if ":" in regel:
                        k, _, v = regel.partition(":")
                        data[k.strip()] = v.strip()
                self.after(0, lambda: _toon_hardware(data))
            except Exception as e:
                self.after(0, lambda: hw_lbl.config(
                    text=f"  SSH niet beschikbaar: {e}", fg=ERR_C))

        def _toon_hardware(data):
            try:
                if not hw_frame.winfo_exists(): return
                hw_lbl.destroy()
                for k, label in [
                    ("MODEL",  "Model"),
                    ("RAM",    "RAM geheugen"),
                    ("SDCARD", "SD-kaart grootte"),
                    ("TEMP",   "CPU temperatuur"),
                    ("UPTIME", "Uptime"),
                ]:
                    v = data.get(k, "n/a")
                    if v:
                        kleur = ERR_C if (k == "TEMP" and "temp=" in v and
                                          float(v.replace("temp=","").replace("'C","")) > 70
                                          ) else FG
                        info_rij(hw_frame, label, v, kleur)
            except: pass

        threading.Thread(target=haal_hardware, daemon=True).start()

        # ── PI SCRIPTS SYNC ──────────────────────────────────────────────────
        sectie_kop("📡  Pi scripts — sync", ACCENT_PINAS)
        sync = getattr(self, '_pi_sync_status', 'onbekend')
        sync_kleur = {
            'ok':       OK_C,
            'oranje':   WARN,
            'rood':     ERR_C,
            'onbekend': DIM,
        }.get(sync, DIM)
        sync_tekst = {
            'ok':       "Alle scripts up-to-date",
            'oranje':   "Verschil gevonden — controleer details",
            'rood':     "Upload nodig — lokaal nieuwer dan Pi",
            'onbekend': "Onbekend — Pi niet bereikbaar of nog niet gecontroleerd",
        }.get(sync, "Onbekend")

        sync_rij = tk.Frame(frame, bg=BG)
        sync_rij.pack(fill="x", pady=2)
        tk.Label(sync_rij, text="●", font=("Segoe UI", 10),
                 bg=BG, fg=sync_kleur, width=2).pack(side="left")
        tk.Label(sync_rij, text="Sync status", font=("Segoe UI", 9),
                 bg=BG, fg=FG, width=22, anchor="w").pack(side="left")
        tk.Label(sync_rij, text=sync_tekst, font=("Segoe UI", 9),
                 bg=BG, fg=sync_kleur).pack(side="left", fill="x", expand=True)

        # Details per bestand
        details = getattr(self, '_pi_sync_details', [])
        if details:
            regel_items = details
            def _regel_widget(parent, regel):
                kleur = ERR_C if "ROOD" in regel or "upload" in regel.lower() else (
                        WARN if "ORANJE" in regel or "verschil" in regel.lower() else DIM)
                tk.Label(parent, text=f"    {regel}",
                         font=("Segoe UI", 8), bg=BG, fg=kleur, anchor="w").pack(
                         fill="x", padx=4)
        elif sync == 'ok':
            regel_items = [
                "nas_installer.py", "nas_installer_cli.py", "seagate_web.py",
                "pi_welkom.sh", "install.sh", "nas_diagnose.sh"
            ]
            def _regel_widget(parent, b):
                tk.Label(parent, text=f"    ✓  {b}",
                         font=("Segoe UI", 8), bg=BG, fg=OK_C, anchor="w").pack(
                         fill="x", padx=4)
        else:
            regel_items = []
            _regel_widget = None

        if regel_items:
            splits2 = _math.ceil(len(regel_items) / 2)
            scols_frame = tk.Frame(frame, bg=BG)
            scols_frame.pack(fill="x")
            scol1 = tk.Frame(scols_frame, bg=BG)
            scol2 = tk.Frame(scols_frame, bg=BG)
            scol1.pack(side="left", fill="both", expand=True, padx=(0, 6))
            scol2.pack(side="left", fill="both", expand=True, padx=(6, 0))
            for i, regel in enumerate(regel_items):
                _regel_widget(scol1 if i < splits2 else scol2, regel)

        # Upload knop altijd zichtbaar in status venster
        def _doe_upload_en_herlaad():
            self._upload_naar_pi()

        tk.Button(frame, text="⬆  Uploaden naar Pi",
                  font=("Segoe UI", 9), bg=PANEL2, fg=FG,
                  relief="flat", cursor="hand2", borderwidth=0, pady=5,
                  command=_doe_upload_en_herlaad).pack(fill="x", pady=(6, 2))
        tk.Button(frame, text="↻  Sync opnieuw controleren",
                  font=("Segoe UI", 8), bg=BG, fg=DIM,
                  relief="flat", cursor="hand2", borderwidth=0, pady=3,
                  command=lambda: [self._start_sync_check(),
                                   self.after(6000, self._vul_status_venster)]
                  ).pack(fill="x", pady=(0, 4))

        # ── LOGS ─────────────────────────────────────────────────────────────
        sectie_kop("📋  Logbestanden", ACCENT_PINAS)
        log_map = os.path.join("C:\\", "PiNAS", "Logs")
        logs = [
            ("picontrol.log",  "Pi NAS Menu"),
            (nieuwste_log_bestand("pinas_sync_", "pinas_sync.log"), "PiNAS Sync"),
            ("seagate.log",    "Externe HDD (Pi)"),
        ]
        for bestand, naam in logs:
            pad = os.path.join(log_map, bestand)
            if os.path.exists(pad):
                grootte = os.path.getsize(pad)
                grootte_str = f"{grootte/1024:.1f} KB" if grootte > 0 else "leeg"
                rij = tk.Frame(frame, bg=BG)
                rij.pack(fill="x", pady=1)
                tk.Label(rij, text="●", font=("Segoe UI", 10),
                         bg=BG, fg=OK_C, width=2).pack(side="left")
                tk.Label(rij, text=naam, font=("Segoe UI", 9),
                         bg=BG, fg=FG, width=22, anchor="w").pack(side="left")
                tk.Label(rij, text=grootte_str, font=("Segoe UI", 9),
                         bg=BG, fg=DIM).pack(side="left")
                tk.Button(rij, text="Open",
                          font=("Segoe UI", 8), bg=PANEL2, fg=FG,
                          relief="flat", cursor="hand2", padx=6, pady=2,
                          borderwidth=0,
                          command=lambda p=pad: subprocess.Popen(
                              ["notepad.exe", p])).pack(side="right", padx=4)
            else:
                info_rij(frame, naam, "Nog geen log", DIM)

    def _herstel_verbinding(self):
        """Roept lanman_fix.bat aan als zichtbaar CMD venster met admin rechten."""
        pad = bat_pad("lanman_fix.bat")
        if pad:
            def wacht_en_ververs():
                import time
                proc = subprocess.Popen(
                    ["powershell", "-Command",
                     f"Start-Process cmd -ArgumentList '/c \"{pad}\"' -Verb RunAs -Wait"],
                    creationflags=subprocess.CREATE_NO_WINDOW)
                proc.wait()
                time.sleep(1)
                self.after(0, self._bouw_pc_status)
            import threading
            threading.Thread(target=wacht_en_ververs, daemon=True).start()
        else:
            messagebox.showerror("Herstel verbinding — bestand ontbreekt",
                "lanman_fix.bat niet gevonden.\n\n"
                "Verwacht in: C:\\PiNAS\\Beheer\\lanman_fix.bat\n\n"
                "Wat te doen:\n"
                "  Download de Starter Kit opnieuw of kopieer\n"
                "  lanman_fix.bat naar C:\\PiNAS\\Beheer\\")


    def _redraw_all_buttons(self):
        """Herteken alle RoundedButtons na initieel renderen."""
        def redraw_recursive(widget):
            if isinstance(widget, RoundedButton):
                widget._redraw()
            for child in widget.winfo_children():
                redraw_recursive(child)
        redraw_recursive(self)
        self.after(300, lambda: redraw_recursive(self))

    def _check_suite_update(self):
        """Checkt via GitHub of er een nieuwere versie van de Suite beschikbaar is."""
        import threading, urllib.request

        def _check():
            try:
                url = ("https://raw.githubusercontent.com/"
                       "fvdschrier-creator/raspberry-pi-nas-installer/"
                       "main/version.py")
                with urllib.request.urlopen(url, timeout=6) as r:
                    tekst = r.read().decode("utf-8")
                # Zoek GITHUB_VERSIE = "x.x.x" in de raw tekst - dit is het
                # publieke releasenummer, los van de interne BIJGEWERKT-datum
                for regel in tekst.splitlines():
                    if "GITHUB_VERSIE" in regel and "=" in regel:
                        github_versie = regel.split("=")[1].strip().strip('"').strip("'")
                        lokaal = GITHUB_VERSIE
                        if github_versie != lokaal:
                            self.after(0, lambda gv=github_versie: _meld(gv))
                        return
            except Exception:
                pass  # Geen melding bij fout — stil falen

        def _meld(github_versie):
            bericht = (
                "Er is een nieuwe versie van de Pi NAS Suite beschikbaar!\n\n"
                "  Huidige versie:     v" + GITHUB_VERSIE + "\n"
                "  Nieuwste versie:    v" + github_versie + "\n\n"
                "Wil je de GitHub pagina openen om de update te downloaden?"
            )
            ant = messagebox.askyesno(
                "Suite update beschikbaar",
                bericht,
                icon="info"
            )
            if ant:
                import webbrowser
                webbrowser.open(
                    "https://github.com/fvdschrier-creator/"
                    "raspberry-pi-nas-installer/releases"
                )

        threading.Thread(target=_check, daemon=True).start()

    def _auto_koppel_schijven(self):
        """Bij opstarten: Opslag en Backup koppelen als ze ontbreken (op
        hun geconfigureerde letter, niet hardcoded Y:/Z:)."""
        import threading
        def koppel():
            import time
            for letter, share in _schijf_config().items():
                if not check_share(share, letter, PI_IP):
                    subprocess.Popen(
                        ["net", "use", f"{letter}:", f"\\\\{PI_IP}\\{share}",
                         "/user:pi", _get_nas_wachtwoord(), "/persistent:yes"],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
            time.sleep(2)
            self.after(0, self._bouw_pc_status)
        threading.Thread(target=koppel, daemon=True).start()

    def _koppel_backup_en_ververs(self):
        """Na mount: Backup-schijf koppelen in Windows en status verversen."""
        letter = _backup_letter()
        try:
            # Eerst oude verbinding verwijderen (kan al bestaan)
            subprocess.Popen(
                ["net", "use", f"{letter}:", "/delete", "/yes"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except: pass
        try:
            # Backup-schijf opnieuw koppelen
            subprocess.Popen(
                ["net", "use", f"{letter}:", f"\\\\{PI_IP}\\Backup",
                 "/user:pi", _get_nas_wachtwoord(), "/persistent:yes"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except: pass
        _onthoud_schijfletter("Backup", letter)
        self._seagate_status_update()

    def _seagate_uit(self):
        # 6 augustus 2026 (Frans: "kan niet zijn hdd backup gemount als hij
        # niet actief is?? - Backup-schijf gemount toonde nog 'actief'
        # terwijl Externe HDD al UIT was"): root cause gevonden - deze
        # functie haalde de stroom eraf (/actie/uit) zonder EERST /mnt/
        # backup op de Pi netjes te umounten. Linux' mounttabel bleef dan
        # "gemount" zeggen terwijl de schijf er niet meer was (spookmount).
        # Nu: eerst umount via SSH, PAS DAARNA de stroom eraf. In een
        # thread (vaste regel: elke nieuwe subprocess/netwerk-aanroep
        # threaden, nooit blokkerend in een knop-handler).
        def werk():
            try:
                subprocess.run(
                    ["ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no",
                     "-o", "BatchMode=yes", f"pi@{PI_IP}", "sudo umount /mnt/backup 2>/dev/null; true"],
                    capture_output=True, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
            except Exception:
                pass  # Pi niet bereikbaar voor umount - stroom toch uitzetten,
                      # anders kan de HDD helemaal nooit meer uit via de app
            try:
                urllib.request.urlopen(f"{SEAGATE_URL}/actie/uit", timeout=5)
                letter = _backup_letter()
                subprocess.Popen(
                    ["net", "use", f"{letter}:", "/delete", "/yes"],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            except Exception:
                self.after(0, lambda: messagebox.showerror(
                    "Externe HDD — uitzetten mislukt",
                    "De externe HDD kon niet worden uitgezet.\n\n"
                    "Mogelijke oorzaken:\n"
                    "  • Smart plug niet bereikbaar\n"
                    f"  • Backup-schijf ({_backup_letter()}:) nog in gebruik door een ander programma\n\n"
                    f"Tip: sluit alle bestanden op de Backup-schijf ({_backup_letter()}:) en probeer opnieuw"))
        threading.Thread(target=werk, daemon=True).start()

    # ── Ping ──────────────────────────────────────────────────────────────────
    def _start_ping(self):
        self._ping_history = getattr(self, '_ping_history', [])
        def ping():
            try:
                r = subprocess.run(["ping", "-n", "1", "-w", "1500", PI_IP],
                                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                ok = r.returncode == 0
            except: ok = False
            if not ok:
                self.after(3000, self._ping_herpoging)
            else:
                self.after(0, lambda: self._ping_result(True))
        threading.Thread(target=ping, daemon=True).start()
        self.after(15000, self._start_ping)

    def _ping_herpoging(self):
        """Tweede poging — pas na twee mislukkingen op rood zetten."""
        def ping():
            try:
                r = subprocess.run(["ping", "-n", "1", "-w", "2000", PI_IP],
                                   capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                ok = r.returncode == 0
            except: ok = False
            self.after(0, lambda: self._ping_result(ok, herpoging=True))
        threading.Thread(target=ping, daemon=True).start()

    def _ping_result(self, bereikbaar, herpoging=False):
        hist = getattr(self, '_ping_history', [])
        hist.append(bereikbaar)
        if len(hist) > 6:
            hist = hist[-6:]
        self._ping_history = hist
        was_bereikbaar = getattr(self, '_pi_bereikbaar', None)
        self._pi_bereikbaar = bereikbaar

        if bereikbaar:
            self.lbl_ping.config(text=f"● Pi bereikbaar  ({PI_IP})", fg=OK_C)
            # Kwam de Pi terug uit onbereikbaar? Verifieer services en scripts
            # meteen opnieuw, zodat een verouderde 'onbekend' snel wordt
            # bijgewerkt naar de echte, actuele status.
            if was_bereikbaar is False:
                self.after(1500, self._ververs_pi_status)
                self.after(2500, self._start_sync_check)
        elif herpoging:
            laatste = hist[-3:] if len(hist) >= 3 else hist
            if all(not x for x in laatste):
                self.lbl_ping.config(text=f"● Pi niet bereikbaar  ({PI_IP})", fg=ERR_C)
                # Pi onbereikbaar: alles wat de Pi vereist (services, scripts,
                # Nextcloud) kan NIET bekend zijn. Zet die op 'onbekend' i.p.v.
                # het laatst bekende groen te laten staan (valse geruststelling).
                self._pi_status_ok = None
                self._pi_statussen = []
                self._pi_sync_status = 'onbekend'
                self._bouw_pc_status()
            else:
                self.lbl_ping.config(text=f"● Verbinding wisselend  ({PI_IP})", fg=YELLOW)
        else:
            self.lbl_ping.config(text=f"● Verbinding wisselend  ({PI_IP})", fg=YELLOW)

    # ── Uploaden naar de Pi (canoniek - alle upload-knoppen via deze methode) ──
    def _upload_naar_pi(self):
        """Zet alle lokale scripts op de Pi via nas_upload.bat en controleer
        daarna de sync opnieuw. Een plek voor elke upload-knop, zodat upload
        overal hetzelfde doet (lokaal is de bron)."""
        run_bat("nas_upload.bat")
        self.after(5000, self._start_sync_check)

    # ── Pi scripts sync check ──────────────────────────────────────────────────
    def _start_sync_check(self):
        """MD5 hash vergelijking Pi scripts vs lokaal — onafhankelijk van tijdstempel."""
        import threading, hashlib

        # 16 juli 2026: uitgebreid naar ALLE bestanden die nas_upload.bat
        # daadwerkelijk uploadt (was eerder maar 8 van de 16 - o.a.
        # pinas_theme.py stond er niet bij, waardoor een achterstand in
        # net dat bestand geen signaal gaf, terwijl uploaden het wel
        # meenam. Nu 1-op-1 met nas_upload.bat.
        PI_SCRIPTS = [
            ("nas_installer.py",      os.path.join(_nas_root(), "PiServer", "nas_installer.py")),
            ("nas_installer_cli.py",  os.path.join(_nas_root(), "PiServer", "nas_installer_cli.py")),
            ("seagate_web.py",        os.path.join(_nas_root(), "PiServer", "seagate_web.py")),
            ("seagate-web.service",   os.path.join(_nas_root(), "PiServer", "seagate-web.service")),
            ("smart_plug.py",         os.path.join(_nas_root(), "PiServer", "smart_plug.py")),
            ("smart_plug_config.json",os.path.join(_nas_root(), "PiServer", "smart_plug_config.json")),
            ("hue_diagnose.py",       os.path.join(_nas_root(), "PiServer", "hue_diagnose.py")),
            ("pi_welkom.sh",          os.path.join(_nas_root(), "PiServer", "pi_welkom.sh")),
            ("install.sh",            os.path.join(_nas_root(), "PiServer", "install.sh")),
            ("nas_start.sh",          os.path.join(_nas_root(), "PiServer", "nas_start.sh")),
            ("nas_diagnose.sh",       os.path.join(_nas_root(), "Gedeeld", "nas_diagnose.sh")),
            ("herstel_backup_hdd.sh", os.path.join(_nas_root(), "Gedeeld", "herstel_backup_hdd.sh")),
            ("pinas_theme.py",        os.path.join(_nas_root(), "Gedeeld", "pinas_theme.py")),
            ("pinas_wachtwoord.py",   os.path.join(_nas_root(), "Gedeeld", "pinas_wachtwoord.py")),
            ("pinas_logging.py",      os.path.join(_nas_root(), "Gedeeld", "pinas_logging.py")),
            ("version.py",            os.path.join(_nas_root(), "Gedeeld", "version.py")),
        ]

        def md5_lokaal(pad):
            try:
                h = hashlib.md5()
                with open(pad, "rb") as f:
                    for blok in iter(lambda: f.read(65536), b""):
                        h.update(blok)
                return h.hexdigest()
            except Exception:
                return None

        def check():
            try:
                # Één SSH aanroep — md5sum van alle Pi-scripts tegelijk
                pi_bestanden = " ".join(f"/home/pi/{naam}" for naam, _ in PI_SCRIPTS)
                r = subprocess.run(
                    ["ssh", "-o", "StrictHostKeyChecking=no",
                     "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                     f"pi@{PI_IP}",
                     f"md5sum {pi_bestanden} 2>/dev/null"],
                    capture_output=True, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=8)

                # 5 augustus 2026 (Frans: "scripts onbekend" terwijl SSH
                # Diagnose prima werkte): r.returncode != 0 hoorde hier niet
                # bij te staan - md5sum geeft AL een niet-nul exitcode zodra
                # ook maar 1 van de 16 bestanden ontbreekt op de Pi, ook als
                # de andere 15 gewoon prima matchen. Dat gooide dan de hele,
                # verderop al goed werkende per-bestand-vergelijking (die
                # "X ontbreekt op Pi" al netjes apart afhandelt) meteen weg
                # en toonde in plaats daarvan een misleidende SSH-foutmelding.
                # Alleen ECHT geen bruikbare uitvoer (SSH zelf mislukt/time-
                # out) betekent nu nog 'onbekend'.
                if not r.stdout.strip():
                    self._pi_sync_status = 'onbekend'
                    self.after(0, self._bouw_pc_status)
                    return

                # Pi hashes parsen: "hash  /home/pi/naam"
                pi_hashes = {}
                for regel in r.stdout.strip().splitlines():
                    delen = regel.strip().split(None, 1)
                    if len(delen) == 2:
                        pi_hash = delen[0]
                        naam = os.path.basename(delen[1].strip())
                        pi_hashes[naam] = pi_hash

                # Vergelijken met lokale MD5 hashes
                status = 'ok'
                details = []
                for naam, lokaal_pad in PI_SCRIPTS:
                    if not os.path.exists(lokaal_pad):
                        continue
                    lok_hash = md5_lokaal(lokaal_pad)
                    if naam not in pi_hashes:
                        status = 'rood'
                        details.append(f"{naam}: ontbreekt op Pi")
                        continue
                    if lok_hash and lok_hash != pi_hashes[naam]:
                        # Inhoud verschilt. In de Pi NAS Suite is LOKAAL altijd
                        # de bron: je ontwikkelt lokaal en uploadt naar de Pi.
                        # Dus is een verschil = upload nodig. We vergelijken
                        # GEEN tijdstempels meer: dat wees na het uitpakken van
                        # een zip ten onrechte "Pi nieuwer" aan en suggereerde
                        # de verkeerde richting (terughalen i.p.v. uploaden).
                        status = 'rood'
                        details.append(f"{naam}: lokaal verschilt - upload nodig")

                self._pi_sync_status = status
                self._pi_sync_details = details
                self.after(0, self._bouw_pc_status)

                # 31 juli 2026 (Frans): naast het statusregeltje ook een ECHTE
                # pop-up, want een gekleurd regeltje wordt te makkelijk gemist.
                # Toont 1x per unieke situatie (niet elke 5 minuten opnieuw
                # dezelfde pop-up als er niets veranderd is).
                vorig_gemeld = getattr(self, '_pi_sync_laatst_gemeld', None)
                if status == 'rood' and details != vorig_gemeld:
                    self._pi_sync_laatst_gemeld = list(details)
                    def _toon_popup(details=details):
                        messagebox.showwarning(
                            "Pi scripts — upload nodig",
                            "Lokale scriptwijzigingen zijn nog niet naar de Pi "
                            "geupload:\n\n" +
                            "\n".join(f"  • {x}" for x in details) +
                            "\n\nGebruik 'Uploaden naar Pi' (hoofdscherm of "
                            "Beheer → Geavanceerd) om dit bij te werken.\n\n"
                            "Let op: dit controleert alleen of het bestand in "
                            "/home/pi/ op de Pi overeenkomt met lokaal. Heeft "
                            "een script na het uploaden nog een aparte "
                            "installatie-/herstartstap nodig (bijv. een "
                            "systemd-dienst herladen), dan moet die stap zelf "
                            "nog herhaald worden - dat ziet deze controle niet.")
                    self.after(0, _toon_popup)
                elif status != 'rood':
                    self._pi_sync_laatst_gemeld = None

            except subprocess.TimeoutExpired:
                self._pi_sync_status = 'onbekend'
                self.after(0, self._bouw_pc_status)
            except Exception:
                self._pi_sync_status = 'onbekend'
                self.after(0, self._bouw_pc_status)

            # Herhaal elke 5 minuten
            self.after(300000, self._start_sync_check)

        self._pi_sync_status = 'bezig'
        self.after(0, self._bouw_pc_status)
        threading.Thread(target=check, daemon=True).start()


    # ── Elevated run ──────────────────────────────────────────────────────────
    def _run_elevated(self, naam):
        pad = bat_pad(naam)
        if not pad:
            messagebox.showerror("Niet gevonden", f"{naam} niet gevonden.")
            return
        import ctypes
        cmd_arg = '/c "' + pad + '"'
        ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", cmd_arg, None, 1)

    # ── Widget helpers ────────────────────────────────────────────────────────
    def _sectie(self, parent, tekst):
        tk.Label(parent, text=tekst, font=("Segoe UI", 9, "bold"),
                 bg=BG, fg=DIM, anchor="w").pack(fill="x", pady=(14,4))

    def _sep(self, parent):
        tk.Frame(parent, bg=PANEL2, height=1).pack(fill="x", pady=10)

    def _btn(self, parent, tekst, cmd, kleur):
        # Knoppen op een neutrale paneelkleur (PANEL/PANEL2) gebruiken de
        # thema-tekstkleur; knoppen met een duidelijke accentkleur (blauw/
        # groen/oranje/etc.) blijven altijd wit voor leesbaarheid in elk thema.
        fg = FG if kleur in (PANEL, PANEL2) else "#ffffff"
        btn = RoundedButton(parent, text=tekst, command=cmd, bg=kleur, fg=fg)
        return btn


import json

# ── Afgeronde knop (Canvas-gebaseerd) ─────────────────────────────────────────
class RoundedButton(tk.Canvas):
    """Knop met afgeronde hoeken — uniform voor hele Pi NAS Menu."""
    def __init__(self, parent, text, command, bg, fg=None, font=None,
                 radius=8, pady=8, padx=12, width=0, **kw):
        self._bg     = bg
        self._fg     = fg or "#ffffff"   # standaard wit — knop heeft altijd een gekleurde achtergrond
        self._font   = font or ("Segoe UI", 10)
        self._radius = radius
        self._pady   = pady
        self._padx   = padx
        self._cmd    = command
        self._text   = text
        self._state  = "normal"

        # Bereken hoogte op basis van font
        tmp = tk.Label(parent, text=text, font=self._font)
        th  = tmp.winfo_reqheight()
        tmp.destroy()
        h = th + pady * 2

        self._min_h = max(h, 32)
        super().__init__(parent, height=self._min_h, bg=parent.cget("bg"),
                         highlightthickness=0, bd=0, **kw)
        self.pack(fill="x", pady=2)

        self.bind("<Configure>", self._redraw)
        self.bind("<Button-1>",  self._on_click)
        self.bind("<Enter>",     lambda e: self._hover(True))
        self.bind("<Leave>",     lambda e: self._hover(False))
        self._hovered = False

    def _lighten(self, hex_c, amt=30):
        h = hex_c.lstrip("#")
        r,g,b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        return f"#{min(r+amt,255):02x}{min(g+amt,255):02x}{min(b+amt,255):02x}"

    def _draw(self, w, h, bg):
        self.delete("all")
        r = self._radius
        # Afgeronde rechthoek
        self.create_arc(0,   0,   2*r, 2*r, start=90,  extent=90, fill=bg, outline=bg)
        self.create_arc(w-2*r, 0, w, 2*r,   start=0,   extent=90, fill=bg, outline=bg)
        self.create_arc(0, h-2*r, 2*r, h,   start=180, extent=90, fill=bg, outline=bg)
        self.create_arc(w-2*r, h-2*r, w, h, start=270, extent=90, fill=bg, outline=bg)
        self.create_rectangle(r, 0, w-r, h,   fill=bg, outline=bg)
        self.create_rectangle(0, r, w,   h-r, fill=bg, outline=bg)
        # Tekst links uitgelijnd
        self.create_text(self._padx + r, h//2, text=self._text,
                         font=self._font, fill=self._fg, anchor="w")

    def _redraw(self, e=None):
        w = self.winfo_width() or 200
        h = self.winfo_height() or self._min_h
        if h < 10: h = self._min_h
        bg = self._lighten(self._bg) if self._hovered else self._bg
        if self._state == "disabled":
            bg = PANEL2
        self._draw(w, h, bg)

    def _hover(self, on):
        if self._state == "disabled": return
        self._hovered = on
        self._redraw()

    def _on_click(self, e=None):
        if self._state == "disabled": return
        if self._cmd: self._cmd()

    def config(self, **kw):
        if "state" in kw:
            self._state = kw["state"]
            self._redraw()
        if "text" in kw:
            self._text = kw["text"]
            self._redraw()
        if "bg" in kw:
            self._bg = kw["bg"]
            self._redraw()

    def pack(self, **kw):
        super().pack(**kw)
        self.after(50, self._redraw)
        self.after(200, self._redraw)

if __name__ == "__main__":
    app = Menu()
    app.mainloop()
