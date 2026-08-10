"""
Pi NAS Suite — Test Suite
Staat in: C:/PiNAS/Gedeeld/
Gebruik:   python test_suite.py  (of via Pi NAS Menu → Beheer → Geavanceerd)
"""

import os
import sys
import csv
import json
import glob
import subprocess
import threading
import importlib
import configparser
import re
import struct
import shutil
import datetime
import tkinter as tk
from tkinter import messagebox, filedialog
import pinas_schijven

# ── Pad setup ────────────────────────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_NAS_ROOT   = os.path.join("C:\\", "PiNAS")
_GEDEELD    = os.path.join(_NAS_ROOT, "Gedeeld")

sys.path.insert(0, _GEDEELD)
sys.path.insert(0, _SCRIPT_DIR)

# Pinas thema importeren indien beschikbaar
try:
    from pinas_theme import *
    _THEMA = True
except Exception:
    _THEMA = False
    BG     = "#1e1e2e"
    PANEL  = "#2a2a3e"
    PANEL2 = "#313244"
    FG     = "#cdd6f4"
    DIM    = "#6c7086"
    OK_C   = "#4ade80"
    ERR_C  = "#f87171"
    YELLOW = "#f59e0b"
    ACCENT = "#60a5fa"

# ── Kleuren ──────────────────────────────────────────────────────────────────
OK_TAG   = OK_C   if _THEMA else "#4ade80"
ERR_TAG  = ERR_C  if _THEMA else "#f87171"
WARN_TAG = YELLOW if _THEMA else "#f59e0b"
INFO_TAG = ACCENT if _THEMA else "#60a5fa"
DIM_TAG  = DIM    if _THEMA else "#6c7086"

# ── Config lezen ──────────────────────────────────────────────────────────────
def _lees_config():
    cfg = configparser.ConfigParser()
    for pad in [
        os.path.join(_NAS_ROOT, "Beheer", "picontrol.cfg"),
        os.path.join(_SCRIPT_DIR, "..", "Beheer", "picontrol.cfg"),
    ]:
        if os.path.exists(pad):
            cfg.read(pad)
            break
    return cfg

def _schijf_letter(cfg_letter_key, share_terugval, letter_terugval):
    """Zoekt de echte, huidige stationsletter via de share-naam i.p.v.
    een vaste letter aan te nemen (Y:/Z: kunnen op een andere pc al door
    iets anders bezet zijn).

    5 augustus 2026: cfg_letter_key-parameter (was: cfg.get("schijven",
    cfg_letter_key, ...) - zocht op een hardcoded letter-sleutel "Y"/"Z"
    in de config, werkte alleen toevallig omdat de terugvalwaarde
    toevallig de echte share-naam is) niet meer gebruikt voor de
    opzoeking zelf - rechtstreeks op share-naam zoeken via
    pinas_schijven, zelfde fix als vandaag al doorgevoerd in
    Pi_NAS_Menu.pyw (_letter_voor_share/_opslag_letter/_backup_letter)."""
    cfg = _lees_config()
    try:
        ip = cfg.get("pi", "ip", fallback=None)
    except Exception:
        ip = None
    return pinas_schijven.vind_letter_of_terugval(share_terugval, letter_terugval, ip)

# ── Verwachte bestanden ───────────────────────────────────────────────────────
# 8 augustus 2026: VERWACHT was hier een eigen, handmatig bijgehouden lijst
# die naast Gedeeld/pinas_versies.json synchroon gehouden moest worden - twee
# plekken voor dezelfde informatie, en dat liep die dag ook echt uit de pas
# (zie de build_topografie.py-opschoning eerder die dag). VERWACHT wordt nu
# rechtstreeks afgeleid uit pinas_versies.json, dat daarmee de ENE bron van
# waarheid is voor "welke bestanden horen in de suite te bestaan". Nieuwe
# bestanden hoef je dus alleen nog in pinas_versies.json te registreren
# (zie ook de "Geen ongeregistreerde scripts"-check hieronder, die er juist
# voor waarschuwt als dat vergeten is).
def _lees_verwacht():
    pad = os.path.join(_GEDEELD, "pinas_versies.json")
    try:
        with open(pad, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    resultaat = []
    for sleutel in data:
        if sleutel.startswith("_"):
            continue  # _uitleg e.d., geen bestandssleutel
        # pinas_versies.json-sleutels zijn altijd Windows-stijl ("Map\sub\bestand"),
        # ongeacht het besturingssysteem waarop dit draait - os.path.join
        # bouwt het bestand-deel weer platformeigen op (net als de oude
        # hardcoded lijst deed met os.path.join("core", "bestand.py")).
        delen = sleutel.split("\\")
        if len(delen) >= 2:
            resultaat.append((delen[0], os.path.join(*delen[1:])))
    return resultaat

VERWACHT = _lees_verwacht()

# ── Checks ────────────────────────────────────────────────────────────────────
class Check:
    def __init__(self, categorie, naam, functie, optioneel=False):
        self.categorie = categorie
        self.naam      = naam
        self.functie   = functie
        self.optioneel = optioneel
        self.status    = "?"      # OK / FOUT / WARN / INFO
        self.detail    = ""
        self.tijdstip  = ""

    def uitvoeren(self):
        try:
            status, detail = self.functie()
            self.status = status
            self.detail = detail
        except Exception as e:
            self.status = "FOUT"
            self.detail = f"Uitzondering: {e}"
        self.tijdstip = datetime.datetime.now().strftime("%H:%M:%S")
        return self.status, self.detail


def _check_bestandsstructuur():
    """Bundelt de aanwezigheidscheck van alle verwachte bestanden tot 1
    regel. De uitgebreide versie (misplaatst/dubbel/verouderd-detectie,
    per bestand) zit al in Structuurcheck (NAS Map Beheer) - die hoeft
    hier niet nog eens overgedaan te worden, alleen een korte samenvatting
    zodat je weet of er iets mist."""
    ontbrekend = []
    for map_, bestand in VERWACHT:
        pad = os.path.join(_NAS_ROOT, map_, bestand)
        if not os.path.exists(pad):
            ontbrekend.append(f"{map_}\\{bestand}")
    if not ontbrekend:
        return "OK", f"Alle {len(VERWACHT)} verwachte bestanden aanwezig - zie Structuurcheck voor details"
    return "FOUT", (f"{len(ontbrekend)} van {len(VERWACHT)} bestanden ontbreken "
                    f"(zie Structuurcheck voor welke, en om te repareren): " + ", ".join(ontbrekend[:5])
                    + (", ..." if len(ontbrekend) > 5 else ""))

def _check_ongeregistreerd():
    """De OMGEKEERDE richting van _check_bestandsstructuur: niet 'staat
    alles wat verwacht wordt er ook echt' maar 'staat alles wat er staat
    ook geregistreerd in pinas_versies.json (en dus in VERWACHT)'. Dit is
    precies het gat waar PiServer/nas_installer_cli.py op 8 augustus 2026
    doorheen glipte - dat bestand bestond allang, maar stond nergens
    geregistreerd en werd daarom nooit gecontroleerd. WARN i.p.v. FOUT:
    een net aangemaakt bestand dat je nog aan het bewerken bent is geen
    acute fout, maar wel iets om niet te vergeten."""
    bekend = {os.path.join(m, b) for (m, b) in VERWACHT}
    ongeregistreerd = []
    for ext in ("py", "pyw", "bat", "sh", "ps1"):
        for pad in glob.glob(os.path.join(_NAS_ROOT, "**", f"*.{ext}"), recursive=True):
            if any(x in pad for x in ("NAS_Public", "NAS_Simulator", "__pycache__", "Logs")):
                continue
            rel = os.path.relpath(pad, _NAS_ROOT)
            if rel not in bekend:
                ongeregistreerd.append(rel)
    if not ongeregistreerd:
        return "OK", "Alle scripts staan geregistreerd in pinas_versies.json"
    ongeregistreerd.sort()
    return ("WARN", f"{len(ongeregistreerd)} bestand(en) niet geregistreerd in "
                     f"pinas_versies.json: " + ", ".join(ongeregistreerd[:10])
                     + (", ..." if len(ongeregistreerd) > 10 else ""))

def _check_syntax(map_, bestand):
    pad = os.path.join(_NAS_ROOT, map_, bestand)
    if not os.path.exists(pad):
        return "FOUT", f"Bestand niet gevonden: {pad}"
    try:
        import py_compile
        py_compile.compile(pad, doraise=True)
        return "OK", f"Syntax OK — {bestand}"
    except py_compile.PyCompileError as e:
        return "FOUT", f"Syntaxfout: {e}"

def _alle_py_bestanden():
    """Vindt automatisch alle .py/.pyw in de hele suite-boom i.p.v. een
    handmatig bijgehouden lijst (zie toelichting hierboven bij VERWACHT
    en _check_ongeregistreerd - 8 augustus 2026). Zelfde uitsluitingen
    als _scan_script_hygiene/_scan_code_kwaliteit hieronder."""
    gevonden = []
    for ext in ("py", "pyw"):
        for pad in glob.glob(os.path.join(_NAS_ROOT, "**", f"*.{ext}"), recursive=True):
            if "NAS_Public" in pad or "NAS_Simulator" in pad or "__pycache__" in pad:
                continue
            rel = os.path.relpath(pad, _NAS_ROOT)
            deel = rel.split(os.sep, 1)
            if len(deel) == 2:
                gevonden.append((deel[0], deel[1]))
            else:
                gevonden.append((".", deel[0]))
    return sorted(set(gevonden))

def _check_bom(map_, bestand):
    pad = os.path.join(_NAS_ROOT, map_, bestand)
    if not os.path.exists(pad):
        return "WARN", f"Niet gevonden: {pad}"
    with open(pad, "rb") as f:
        begin = f.read(3)
    if begin.startswith(b"\xef\xbb\xbf"):
        return "FOUT", f"BOM aanwezig in {bestand} — verwijder met: open(pad,'rb').read()[3:]"
    return "OK", f"Geen BOM — {bestand}"


def _scan_script_hygiene():
    """Scan ALLE scripts in de suite op BOM en juiste regeleindes.
    .bat moet CRLF zijn (cmd-regel), .sh moet LF zijn (anders breekt het op de Pi).
    De publieke spiegel (NAS_Public) wordt overgeslagen: die wordt opnieuw gebouwd."""
    import glob as _glob
    bom_fout, le_fout, ascii_fout = [], [], []
    for ext in ("bat", "sh", "ps1", "pyw", "py", "ini"):
        for pad in _glob.glob(os.path.join(_NAS_ROOT, "**", f"*.{ext}"), recursive=True):
            if "NAS_Public" in pad or "NAS_Simulator" in pad:
                continue  # gegenereerde mappen: worden opnieuw gebouwd uit de bron
            try:
                with open(pad, "rb") as fh:
                    d = fh.read()
            except Exception:
                continue
            rel = os.path.relpath(pad, _NAS_ROOT)
            if d[:3] == b"\xef\xbb\xbf":
                bom_fout.append(rel)
            crlf = d.count(b"\r\n")
            lf = d.count(b"\n") - crlf
            if ext == "bat" and lf > 0:
                le_fout.append(f"{rel} (.bat hoort CRLF, heeft {lf} losse LF)")
            if ext == "sh" and crlf > 0:
                le_fout.append(f"{rel} (.sh hoort LF, heeft {crlf} CRLF)")
            # Niet-ASCII alleen voor cmd/PowerShell-scripts: daar geeft de
            # Windows-codepage problemen. .py/.pyw mogen UTF-8 (emoji, NL-tekens).
            if ext in ("bat", "ps1"):
                niet_ascii = sum(1 for b in d if b > 127)
                if niet_ascii > 0:
                    ascii_fout.append(f"{rel} ({niet_ascii} niet-ASCII bytes)")
    return bom_fout, le_fout, ascii_fout

def _scan_code_kwaliteit():
    """Zoekt klassen verborgen gebreken die handmatig testen vaak mist:
    - dode self._methode-verwijzingen in de .pyw's: een knop die een niet-
      bestaande methode aanroept crasht pas bij het klikken. Alleen project-
      eigen methodes (leidende underscore); Tkinter-overerving (after, configure,
      geometry, ...) heeft die niet en wordt dus niet als 'dood' gezien.
    - losse '&' in echo-regels van .bat: cmd ziet dat als commando-scheider
      ("'Backup' is not recognized"); ge-escapete ^& en && blijven met rust.
    - 'pause >nul' zonder zichtbare uitleg ervoor: lijkt vast te lopen.
    NAS_Public/NAS_Simulator worden overgeslagen (gegenereerd uit de bron)."""
    import glob as _glob
    dood, echo_amp, pauze = [], [], []
    base = _NAS_ROOT
    for pad in _glob.glob(os.path.join(base, "**", "*.pyw"), recursive=True):
        if "NAS_Public" in pad or "NAS_Simulator" in pad:
            continue
        try:
            src = open(pad, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        rel = os.path.relpath(pad, base)
        bekend = (set(re.findall(r'def\s+(_\w+)\s*\(', src))
                  | set(re.findall(r'self\.(_\w+)\s*=', src)))
        for c in sorted(set(re.findall(r'self\.(_\w+)\s*\(', src))):
            if c not in bekend:
                dood.append(f"{rel}: self.{c}()")
    for pad in _glob.glob(os.path.join(base, "**", "*.bat"), recursive=True):
        if "NAS_Public" in pad or "NAS_Simulator" in pad:
            continue
        try:
            lines = open(pad, encoding="utf-8", errors="replace").read().splitlines()
        except Exception:
            continue
        rel = os.path.relpath(pad, base)
        for i, l in enumerate(lines, 1):
            st = l.strip()
            if st.lower().startswith("echo ") and re.search(r'(?<![\^&])&(?!&)', st):
                echo_amp.append(f"{rel}:{i}")
        for i, l in enumerate(lines):
            if re.match(r'\s*pause\s*>\s*nul', l, re.I):
                prev = lines[i-1] if i > 0 else ""
                if not re.search(r'toets|door te gaan|druk', prev, re.I):
                    pauze.append(f"{rel}:{i+1}")
    return dood, echo_amp, pauze

def _check_python_versie():
    v = sys.version_info
    if v >= (3, 10):
        return "OK", f"Python {v.major}.{v.minor}.{v.micro}"
    return "FOUT", f"Python {v.major}.{v.minor} — minimaal 3.10 vereist"

def _check_documentatie_consistentie():
    """Hergebruikt Gedeeld/controleer_documentatie_consistentie.py (dat
    blijft de ENE plek met de addon-controlelogica - hier alleen
    aanroepen, niet dupliceren) zodat 'Test Suite draaien' voortaan ook
    deze controle meeneemt i.p.v. een los, handmatig te onthouden
    scriptje (8 augustus 2026 advieslijst)."""
    try:
        import controleer_documentatie_consistentie as _cdc
    except Exception as e:
        return "WARN", f"Kon controleer_documentatie_consistentie.py niet laden: {e}"
    addons_pad = os.path.join(_NAS_ROOT, _cdc.ADDONS_BEHEER_PAD)
    addon_lijst = _cdc.laad_addon_lijst(addons_pad)
    if addon_lijst is None:
        return "FOUT", "Kon addon-lijst niet lezen uit pinas_addons_beheer.pyw"
    gaten = []
    for sleutel in addon_lijst:
        naam = _cdc.NAAM_MAP.get(sleutel, sleutel)
        for relatief_pad, mensleesbaar in _cdc.TE_CONTROLEREN_BESTANDEN:
            volledig_pad = os.path.join(_NAS_ROOT, relatief_pad.replace("/", os.sep))
            gevonden = _cdc.zoek_addon_in_bestand(volledig_pad, naam)
            if gevonden is None:
                gaten.append(f"{mensleesbaar}: bestand zelf niet gevonden")
            elif not gevonden:
                gaten.append(f"{naam} ontbreekt in {mensleesbaar}")
    if not gaten:
        return "OK", f"Alle {len(addon_lijst)} addons consistent in Topografie/Structuurcheck/Handleiding"
    return "FOUT", "; ".join(gaten[:10]) + (", ..." if len(gaten) > 10 else "")

def _check_topografie_reconciliatie():
    """Leest de al-gegenereerde PiNAS_Topografie.html (niet build_topografie.py
    zelf importeren - dat script schrijft bij import onvoorwaardelijk het
    HTML-bestand, wat ongewenst is als bijwerking van een testrun) en
    checkt de reconciliatie-zin die build_topografie.py daar zelf al in
    zet (matrix vs. pinas_versies.json)."""
    pad = os.path.join(_NAS_ROOT, "Publicatie", "PiNAS_Topografie.html")
    if not os.path.exists(pad):
        return "WARN", f"Niet gevonden: {pad} (nog nooit gegenereerd?)"
    try:
        with open(pad, encoding="utf-8") as f:
            html = f.read()
    except Exception as e:
        return "FOUT", f"Kon {pad} niet lezen: {e}"
    i = html.find("Vergelijking met Structuurcheck")
    if i == -1:
        return "WARN", "Reconciliatie-tekst niet gevonden in PiNAS_Topografie.html — draai build_topografie.py opnieuw"
    stukje = html[i:i + 400]
    if "komt NIET overeen" in stukje:
        return "FOUT", "Topografie-matrix komt niet overeen met pinas_versies.json — draai build_topografie.py en bekijk de afwijking"
    if "komt overeen" in stukje:
        return "OK", "Topografie-matrix komt overeen met pinas_versies.json"
    return "WARN", "Kon reconciliatie-status niet bepalen uit PiNAS_Topografie.html"

def _check_package(naam):
    def _check():
        # Eerst importeren proberen
        try:
            importlib.import_module(naam)
            return "OK", f"{naam} geïnstalleerd"
        except ImportError:
            pass
        # Daarna pip show proberen (werkt ook als package in andere Python zit)
        r = subprocess.run(
            ["pip", "show", naam],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW)
        if r.returncode == 0:
            versie = ""
            for regel in r.stdout.splitlines():
                if regel.startswith("Version:"):
                    versie = regel.split(":",1)[1].strip()
            return "OK", f"{naam} geïnstalleerd via pip (versie {versie})"
        return "FOUT", f"{naam} niet gevonden — pip install {naam}"
    return _check

def _check_putty():
    for p in [
        r"C:\Program Files\PuTTY\putty.exe",
        r"C:\Program Files (x86)\PuTTY\putty.exe",
    ]:
        if os.path.exists(p):
            return "OK", p
    return "FOUT", "PuTTY niet gevonden"

def _check_tigervnc():
    for p in [
        r"C:\Program Files\TigerVNC\vncviewer.exe",
        r"C:\Program Files (x86)\TigerVNC\vncviewer.exe",
    ]:
        if os.path.exists(p):
            return "OK", p
    return "WARN", "TigerVNC niet gevonden (optioneel)"

def _check_docker():
    for p in [
        r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
        r"C:\Program Files\Docker Desktop\Docker Desktop.exe",
    ]:
        if os.path.exists(p):
            return "OK", p
    return "WARN", "Docker Desktop niet gevonden (optioneel — alleen voor simulator)"

def _check_schijf(letter):
    def _check():
        pad = letter + ":\\"
        if not os.path.exists(pad):
            return "FOUT", f"{letter}: niet gekoppeld"
        try:
            t, u, v = shutil.disk_usage(pad)
            pct = int(v / t * 100) if t > 0 else 0
            status = "OK" if pct > 10 else "WARN"
            return status, f"{letter}: — {v//(1024**3)} GB vrij van {t//(1024**3)} GB ({pct}% vrij)"
        except Exception as e:
            return "FOUT", str(e)
    return _check

def _check_schijf_schrijfbaar(letter):
    def _check():
        pad = letter + ":\\"
        if not os.path.exists(pad):
            return "FOUT", f"{letter}: niet beschikbaar"
        # Let op: tempfile.mkstemp() faalt op Samba-netwerkschijven met
        # "[Errno 22] Invalid argument" door de low-level vlaggen die het
        # gebruikt, ook als de schijf gewoon schrijfbaar is. Een doodgewone
        # open()/write/remove werkt wel (net als 'touch' op de Pi).
        testpad = os.path.join(pad, f"pinas_schrijftest_{os.getpid()}.tmp")
        try:
            with open(testpad, "w") as f:
                f.write("ok")
            return "OK", f"{letter}: is schrijfbaar"
        except OSError as e:
            # 6 augustus 2026 (Frans: "geeft een error, vlgs mij is dat
            # niet helemaal correct... schijf backup staat gewoon uit"):
            # os.path.exists() hierboven geeft True omdat de netwerkletter
            # blijvend geregistreerd staat (net use .../persistent:yes),
            # ook als de Pi/HDD daadwerkelijk uit staat - schrijven faalt
            # dan met deze cryptische Errno 22 i.p.v. iets duidelijks.
            if getattr(e, "errno", None) == 22:
                return "FOUT", f"{letter}: niet bereikbaar (Pi/schijf mogelijk uitgeschakeld of niet gemount)"
            return "FOUT", f"{letter}: niet schrijfbaar — {e}"
        except Exception as e:
            return "FOUT", f"{letter}: niet schrijfbaar — {e}"
        finally:
            try:
                if os.path.exists(testpad):
                    os.remove(testpad)
            except Exception:
                pass
    return _check

def _check_config():
    cfg = _lees_config()
    try:
        ip = cfg.get("pi", "ip")
        if not ip or ip.strip() == "UW_PI_IP_ADRES":
            return "FOUT", "IP niet ingesteld (UW_PI_IP_ADRES)"
        # Controleer dat het echt een IP-adres is en niet bv. een themawaarde
        # (zoals 'donker' bij de eerdere findstr-parsefout in lanman_fix.bat).
        if not re.match(r'^\d{1,3}(\.\d{1,3}){3}$', ip.strip()):
            return "FOUT", f"IP ongeldig: '{ip}' (verwacht bv. UW_PI_IP_ADRES)"
        return "OK", f"IP: {ip}"
    except Exception:
        return "FOUT", "picontrol.cfg niet gevonden of ongeldig"

def _check_wachtwoord():
    try:
        sys.path.insert(0, _GEDEELD)
        from pinas_wachtwoord import get_wachtwoord
        ww = get_wachtwoord("samba")
        if ww:
            return "OK", f"Wachtwoord opgeslagen ({len(ww)} tekens)"
        return "FOUT", "Geen wachtwoord gevonden — stel in via Beheer → Beveiliging"
    except Exception as e:
        return "FOUT", f"Fout bij ophalen wachtwoord: {e}"

def _check_logs_map():
    pad = os.path.join(_NAS_ROOT, "Logs")
    if not os.path.exists(pad):
        return "FOUT", f"Map ontbreekt: {pad}"
    testpad = os.path.join(pad, ".pinas_test")
    try:
        with open(testpad, "w") as f: f.write("test")
        os.remove(testpad)
        return "OK", f"{pad} — aanwezig en schrijfbaar"
    except Exception as e:
        return "FOUT", f"{pad} — niet schrijfbaar: {e}"

def _check_lanman():
    try:
        r = subprocess.run(
            ["reg", "query",
             r"HKLM\SYSTEM\CurrentControlSet\Services\LanmanWorkstation\Parameters",
             "/v", "AllowInsecureGuestAuth"],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW)
        if "0x1" in r.stdout:
            return "OK", "AllowInsecureGuestAuth = 1"
        return "FOUT", "AllowInsecureGuestAuth niet correct — voer LanManFix uit"
    except Exception as e:
        return "FOUT", str(e)

def _check_lmcompat():
    try:
        r = subprocess.run(
            ["reg", "query",
             r"HKLM\SYSTEM\CurrentControlSet\Control\Lsa",
             "/v", "LmCompatibilityLevel"],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW)
        if "0x1" in r.stdout:
            return "OK", "LmCompatibilityLevel = 1"
        return "WARN", "LmCompatibilityLevel niet gevonden of 0 — kan problemen geven"
    except Exception as e:
        return "FOUT", str(e)

def _check_ping():
    cfg = _lees_config()
    try:
        ip = cfg.get("pi", "ip")
    except Exception:
        return "FOUT", "Geen IP in config"
    r = subprocess.run(
        ["ping", "-n", "1", "-w", "2000", ip],
        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    if r.returncode == 0:
        return "OK", f"Pi bereikbaar op {ip}"
    return "FOUT", f"Pi niet bereikbaar op {ip}"

def _check_ssh():
    cfg = _lees_config()
    try:
        ip = cfg.get("pi", "ip")
    except Exception:
        return "FOUT", "Geen IP in config"
    r = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
         "-o", "BatchMode=yes", f"pi@{ip}", "echo OK"],
        capture_output=True, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
    if r.returncode == 0 and "OK" in r.stdout:
        return "OK", f"SSH verbinding OK naar {ip}"
    return "FOUT", f"SSH mislukt — {r.stderr.strip()[:80]}"

def _check_pi_service(service):
    def _check():
        cfg = _lees_config()
        try:
            ip = cfg.get("pi", "ip")
        except Exception:
            return "FOUT", "Geen IP in config"
        r = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
             "-o", "BatchMode=yes", f"pi@{ip}",
             f"systemctl is-active {service} 2>/dev/null"],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        status = r.stdout.strip()
        if status == "active":
            return "OK", f"{service} — actief"
        elif status == "inactive":
            return "WARN", f"{service} — inactief"
        else:
            return "FOUT", f"{service} — {status or 'niet gevonden'}"
    return _check

def _check_pi_mount(mountpunt, optioneel=False):
    def _check():
        cfg = _lees_config()
        try:
            ip = cfg.get("pi", "ip")
        except Exception:
            return "FOUT", "Geen IP in config"
        r = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
             "-o", "BatchMode=yes", f"pi@{ip}",
             f"mountpoint -q {mountpunt} && echo GEMOUNT || echo NIET"],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
        if "GEMOUNT" in r.stdout:
            return "OK", f"{mountpunt} gemount op Pi"
        if optioneel:
            return "WARN", f"{mountpunt} niet gemount (optioneel — externe HDD uit?)"
        return "FOUT", f"{mountpunt} niet gemount op Pi"
    return _check

def _check_pi_bestand(bestand):
    def _check():
        cfg = _lees_config()
        try:
            ip = cfg.get("pi", "ip")
        except Exception:
            return "FOUT", "Geen IP in config"
        try:
            r = subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=8",
                 "-o", "BatchMode=yes", f"pi@{ip}",
                 f"test -f {bestand} && echo AANWEZIG || echo ONTBREEKT"],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
            if "AANWEZIG" in r.stdout:
                return "OK", f"{bestand} aanwezig op Pi"
            return "FOUT", f"{bestand} ontbreekt op Pi"
        except subprocess.TimeoutExpired:
            return "WARN", f"SSH timeout bij check {bestand}"
        except Exception as e:
            return "FOUT", str(e)
    return _check

def _check_pi_syntax(bestand):
    def _check():
        cfg = _lees_config()
        try:
            ip = cfg.get("pi", "ip")
        except Exception:
            return "FOUT", "Geen IP in config"
        r = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
             "-o", "BatchMode=yes", f"pi@{ip}",
             f"python3 -m py_compile {bestand} 2>&1 && echo OK || echo FOUT"],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        if r.stdout.strip().endswith("OK"):
            return "OK", f"{bestand} — syntax OK op Pi"
        return "FOUT", f"{bestand} — syntaxfout op Pi: {r.stdout.strip()[:80]}"
    return _check


def _check_gui_opstart(relatief_pad, mensleesbare_naam, wachttijd=4):
    """5 augustus 2026 (Frans's advieslijst na de PiNAS Dashboard-sessie):
    'test_suite.py uitbreiden met een echte GUI-rooktest - een Tkinter-
    venster daadwerkelijk laten opstarten en checken of het niet direct
    crasht. Vangt pack/grid-conflicten en NameErrors af voor levering,
    niet erna.'

    py_compile (zie _check_syntax hierboven) checkt alleen of het
    bestand SYNTACTISCH geldig Python is - dat ving het pack/grid-
    conflict en de ERR_C-typefout van vandaag geen van beide op, want
    beide fouten gebeurden pas TIJDENS het daadwerkelijk opbouwen van
    het venster (een TclError uit Tkinter zelf, resp. een NameError die
    pas afgaat als die regel code echt wordt uitgevoerd).

    Aanpak: start het bestand als een ECHT, apart proces (exact zoals
    Frans het handmatig deed om de foutmeldingen van vandaag te vinden -
    'python pinas_addons_beheer.pyw' in cmd), wacht een paar seconden,
    en kijk of het proces nog leeft. Een geslaagd venster blijft hangen
    in zijn mainloop() (dus nog actief); een crash sluit het proces
    vrijwel meteen af met een foutmelding op stderr.

    Dit opent kort een echt, zichtbaar venster op het scherm - dat is
    bewust, er is geen headless Tkinter-modus op Windows."""
    def _check():
        pad = os.path.join(_NAS_ROOT, relatief_pad)
        if not os.path.exists(pad):
            return "FOUT", f"{relatief_pad} niet gevonden op {pad}"
        try:
            proces = subprocess.Popen(
                [sys.executable, pad],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                cwd=os.path.dirname(pad),
                creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            return "FOUT", f"{mensleesbare_naam} kon niet gestart worden: {e}"

        import time as _time
        _time.sleep(wachttijd)
        nog_actief = proces.poll() is None

        # Altijd netjes opruimen, ongeacht het resultaat - geen vensters
        # laten rondslingeren na een testrun.
        stderr_tekst = ""
        if nog_actief:
            try:
                proces.terminate()
                proces.wait(timeout=3)
            except Exception:
                try:
                    proces.kill()
                except Exception:
                    pass
        else:
            try:
                _, stderr_tekst = proces.communicate(timeout=2)
            except Exception:
                stderr_tekst = ""

        if nog_actief:
            return "OK", f"{mensleesbare_naam} — venster startte en bleef actief"
        laatste_regels = (stderr_tekst or "").strip().splitlines()
        detail = laatste_regels[-1] if laatste_regels else "geen foutuitvoer (onbekende reden)"
        return "FOUT", f"{mensleesbare_naam} — venster sloot/crashte binnen {wachttijd}s: {detail}"
    return _check


def bouw_checks():
    """Bouw de volledige lijst van checks."""
    checks = []

    # ── Configuratie ─────────────────────────────────────────────────────────
    checks.append(Check("⚙ Configuratie", "picontrol.cfg — IP ingesteld", _check_config))
    checks.append(Check("⚙ Configuratie", "NAS wachtwoord opgeslagen", _check_wachtwoord))
    checks.append(Check("⚙ Configuratie", "Logs map aanwezig en schrijfbaar", _check_logs_map))

    # ── Bestanden aanwezig (samenvatting - details zitten in Structuurcheck) ──
    checks.append(Check("📁 Bestanden", f"Alle {len(VERWACHT)} verwachte bestanden", _check_bestandsstructuur))
    checks.append(Check("📁 Bestanden", "Geen ongeregistreerde scripts", _check_ongeregistreerd))

    # ── Syntax checks ─────────────────────────────────────────────────────────
    # 8 augustus 2026: was een vaste lijst van 18 bestanden die je er zelf
    # bij moest zetten - daardoor stond PiServer/nas_installer_cli.py er
    # niet in en viel een echte syntaxfout niet op. Nu: automatisch ALLE
    # .py/.pyw in de boom (zelfde uitsluitingen als de hygiene-scan).
    for map_, bestand in _alle_py_bestanden():
        checks.append(Check(
            "🔍 Syntax",
            f"{map_}\\{bestand}",
            lambda m=map_, b=bestand: _check_syntax(m, b)
        ))

    # ── BOM + regeleinde checks (hele suite, automatisch) ─────────────────────
    _bom_fout, _le_fout, _ascii_fout = _scan_script_hygiene()
    checks.append(Check(
        "🔤 BOM check",
        "Alle scripts (.bat/.sh/.ps1/.py/.pyw/.ini)",
        lambda: ("OK", "Geen BOM in scripts")
                if not _bom_fout else ("FOUT", "BOM in: " + ", ".join(_bom_fout))
    ))
    checks.append(Check(
        "↵ Regeleindes",
        ".bat = CRLF, .sh = LF",
        lambda: ("OK", "Regeleindes correct (.bat CRLF, .sh LF)")
                if not _le_fout else ("FOUT", "; ".join(_le_fout))
    ))
    checks.append(Check(
        "🔠 ASCII (.bat/.ps1)",
        "Geen niet-ASCII tekens in cmd/PowerShell-scripts",
        lambda: ("OK", "Alle .bat/.ps1 zijn puur ASCII")
                if not _ascii_fout else ("FOUT", "Niet-ASCII in: " + "; ".join(_ascii_fout))
    ))

    # ── Code-integriteit (verborgen gebreken) ────────────────────────────────
    _dood, _echo_amp, _pauze = _scan_code_kwaliteit()
    checks.append(Check(
        "🔗 Code-integriteit",
        "Geen dode self.-methodeverwijzingen",
        lambda: ("OK", "Alle aangeroepen methodes bestaan")
                if not _dood else ("FOUT", "Dode verwijzing: " + "; ".join(_dood))
    ))
    checks.append(Check(
        "🔗 Code-integriteit",
        ".bat echo zonder losse & (commando-scheider)",
        lambda: ("OK", "Geen ongeescapete & in echo-regels")
                if not _echo_amp else ("FOUT", "Losse & in: " + "; ".join(_echo_amp))
    ))
    checks.append(Check(
        "🔗 Code-integriteit",
        ".bat pauzes met zichtbare uitleg",
        lambda: ("OK", "Alle pause >nul hebben uitleg ervoor")
                if not _pauze else ("FOUT", "Onzichtbare pauze in: " + "; ".join(_pauze))
    ))

    # ── Documentatie (8 augustus 2026: hiervóór losse, handmatig te
    # onthouden scripts/reconciliatietelling - nu meegenomen in de gewone
    # testrun zodat je ze niet apart hoeft te draaien) ────────────────────────
    checks.append(Check("📄 Documentatie", "Addons consistent in alle documentatie",
                        _check_documentatie_consistentie))
    checks.append(Check("📄 Documentatie", "Topografie komt overeen met pinas_versies.json",
                        _check_topografie_reconciliatie))

    # ── Python omgeving ───────────────────────────────────────────────────────
    checks.append(Check("🐍 Python", "Python versie ≥ 3.10", _check_python_versie))
    # pinas_sync en de rest van de suite draaien op de standaardbibliotheek;
    # alleen keyring is nog een externe afhankelijkheid (pinas_wachtwoord).
    for pkg in ["keyring"]:
        checks.append(Check("🐍 Python", f"Package: {pkg}", _check_package(pkg)))

    # ── Windows software ──────────────────────────────────────────────────────
    checks.append(Check("💻 Windows software", "PuTTY",       _check_putty))
    checks.append(Check("💻 Windows software", "TigerVNC",    _check_tigervnc,  optioneel=True))
    checks.append(Check("💻 Windows software", "Docker Desktop", _check_docker, optioneel=True))

    # ── Schijven ──────────────────────────────────────────────────────────────
    _y_letter = _schijf_letter("Y", "Opslag", "Y")
    _z_letter = _schijf_letter("Z", "Backup", "Z")
    checks.append(Check("💾 Schijven", f"{_y_letter}: beschikbaar en schijfruimte", _check_schijf(_y_letter)))
    checks.append(Check("💾 Schijven", f"{_z_letter}: beschikbaar en schijfruimte", _check_schijf(_z_letter), optioneel=True))
    checks.append(Check("💾 Schijven", f"{_y_letter}: schrijfbaar", _check_schijf_schrijfbaar(_y_letter)))
    checks.append(Check("💾 Schijven", f"{_z_letter}: schrijfbaar", _check_schijf_schrijfbaar(_z_letter), optioneel=True))

    # ── Registry ──────────────────────────────────────────────────────────────
    checks.append(Check("🔑 Registry", "LanMan — AllowInsecureGuestAuth", _check_lanman))
    checks.append(Check("🔑 Registry", "LanMan — LmCompatibilityLevel",   _check_lmcompat))

    # ── Netwerk / Pi ──────────────────────────────────────────────────────────
    checks.append(Check("🌐 Netwerk", "Pi bereikbaar (ping)",   _check_ping))
    checks.append(Check("🌐 Netwerk", "SSH verbinding mogelijk", _check_ssh))

    # ── Pi services (via SSH) ─────────────────────────────────────────────────
    for svc in ["smbd", "nmbd", "apache2", "mariadb", "filebrowser"]:
        checks.append(Check("🖥 Pi services", f"{svc} actief", _check_pi_service(svc)))
    checks.append(Check("🖥 Pi services", "seagate-web actief",
                        _check_pi_service("seagate-web"), optioneel=True))
    checks.append(Check("🖥 Pi services", "pinas-status actief (mobiele statuspagina, optioneel)",
                        _check_pi_service("pinas-status"), optioneel=True))

    # ── Pi bestanden ──────────────────────────────────────────────────────────
    checks.append(Check("📂 Pi bestanden", "nas_installer.py aanwezig",
                        _check_pi_bestand("/home/pi/nas_installer.py")))
    checks.append(Check("📂 Pi bestanden", "nas_installer.py syntax OK",
                        _check_pi_syntax("/home/pi/nas_installer.py")))
    checks.append(Check("📂 Pi bestanden", "/mnt/opslag gemount",
                        _check_pi_mount("/mnt/opslag")))
    checks.append(Check("📂 Pi bestanden", "/mnt/backup gemount (optioneel)",
                        _check_pi_mount("/mnt/backup", optioneel=True), optioneel=True))

    # ── GUI-rooktest ─────────────────────────────────────────────────────────
    # 5 augustus 2026 (Frans's advieslijst): een echt venster laten opstarten
    # en checken of het niet direct crasht - vangt pack/grid-conflicten en
    # NameErrors af voor levering, niet erna. Optioneel gemarkeerd: opent
    # kort een zichtbaar venster, dus bewust niet stilletjes bij elke run
    # (de gebruiker kan deze twee expliciet aan/uit laten staan als losse
    # sectie in het overzicht).
    checks.append(Check("🖼 GUI-rooktest", "Pi NAS Menu opent zonder te crashen",
                        _check_gui_opstart(os.path.join("Beheer", "Pi_NAS_Menu.pyw"),
                                            "Pi NAS Menu"), optioneel=True))
    checks.append(Check("🖼 GUI-rooktest", "Addons Beheer opent zonder te crashen",
                        _check_gui_opstart(os.path.join("Addons", "pinas_addons_beheer.pyw"),
                                            "Addons Beheer"), optioneel=True))
    # 9 augustus 2026 (Frans: "backup opstarten wordt niet gesmoked, komt
    # dat doordat dat een los programma is?") - nee, dat was geen bewuste
    # architecturale keuze: op 5 augustus zijn hier alleen de twee vensters
    # aan toegevoegd waar op dat moment een crash in gevonden was. Backup
    # Beheer is qua opzet identiek (ook een los .pyw-proces) en hoort hier
    # net zo goed bij.
    checks.append(Check("🖼 GUI-rooktest", "Backup Beheer opent zonder te crashen",
                        _check_gui_opstart(os.path.join("Beheer", "pinas_backup_beheer.pyw"),
                                            "Backup Beheer"), optioneel=True))
    # 9 augustus 2026: en dan meteen de rest van de vensters die een echte
    # mainloop() hebben - niet alleen de "belangrijkste", want je weet
    # vooraf nooit welk venster de volgende keer de bug heeft (zie de
    # Structuurcheck-inspringfout die dezelfde dag gevonden werd - dat
    # venster stond toen ook nog niet in dit lijstje).
    checks.append(Check("🖼 GUI-rooktest", "Structuurcheck & Opruimen opent zonder te crashen",
                        _check_gui_opstart(os.path.join("Beheer", "NAS_Map_Beheer.pyw"),
                                            "Structuurcheck & Opruimen"), optioneel=True))
    checks.append(Check("🖼 GUI-rooktest", "PiNAS Sync opent zonder te crashen",
                        _check_gui_opstart(os.path.join("Sync", "pinas_sync_app.pyw"),
                                            "PiNAS Sync"), optioneel=True))
    checks.append(Check("🖼 GUI-rooktest", "Archief Backup Bewaking opent zonder te crashen",
                        _check_gui_opstart(os.path.join("ArchiefBackup", "archief_backup_bewaking.pyw"),
                                            "Archief Backup Bewaking"), optioneel=True))
    checks.append(Check("🖼 GUI-rooktest", "PC Image Backup opent zonder te crashen",
                        _check_gui_opstart(os.path.join("Beheer", "pinas_image_backup.pyw"),
                                            "PC Image Backup"), optioneel=True))
    checks.append(Check("🖼 GUI-rooktest", "Controles opent zonder te crashen",
                        _check_gui_opstart(os.path.join("Beheer", "pinas_controle_beheer.pyw"),
                                            "Controles"), optioneel=True))
    checks.append(Check("🖼 GUI-rooktest", "Kleuren kiezen opent zonder te crashen",
                        _check_gui_opstart(os.path.join("Beheer", "pinas_kleuren_kiezer.pyw"),
                                            "Kleuren kiezen"), optioneel=True))
    checks.append(Check("🖼 GUI-rooktest", "Setup wizard opent zonder te crashen",
                        _check_gui_opstart(os.path.join("Beheer", "pi_nas_setup.pyw"),
                                            "Setup wizard"), optioneel=True))

    return checks


# ── GUI ───────────────────────────────────────────────────────────────────────
class TestSuiteVenster(tk.Toplevel):
    def __init__(self, master=None):
        if master is None:
            self._root_eigenaar = True
            master = tk.Tk()
            master.withdraw()
        else:
            self._root_eigenaar = False

        super().__init__(master)
        self._master = master
        self.title("Pi NAS Suite — Test Suite")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.geometry("820x680")
        self.minsize(700, 500)

        self.checks = bouw_checks()
        self._resultaten = []
        self._bezig = False

        self._bouw_ui()
        self.protocol("WM_DELETE_WINDOW", self._sluiten)

        # Centreer
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - 820) // 2
        y = (self.winfo_screenheight() - 680) // 2
        self.geometry(f"+{x}+{y}")

    def _bouw_ui(self):
        # Header
        hdr = tk.Frame(self, bg=PANEL, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🧪  Pi NAS Suite — Test Suite",
                 font=("Segoe UI", 14, "bold"), bg=PANEL, fg=FG).pack(side="left", padx=14)
        self._lbl_samenvatting = tk.Label(hdr, text="",
                 font=("Segoe UI", 9), bg=PANEL, fg=DIM)
        self._lbl_samenvatting.pack(side="right", padx=14)

        # Voortgangsbalk
        pb_frame = tk.Frame(self, bg=BG, pady=6, padx=14)
        pb_frame.pack(fill="x")
        self._lbl_voortgang = tk.Label(pb_frame, text="Nog niet gestart",
                 font=("Segoe UI", 9), bg=BG, fg=DIM, anchor="w")
        self._lbl_voortgang.pack(fill="x")
        self._canvas_pb = tk.Canvas(pb_frame, bg=PANEL2, height=8,
                                     highlightthickness=0)
        self._canvas_pb.pack(fill="x", pady=2)
        self._pb_balk = None

        # Knoppenbalk
        btn_bar = tk.Frame(self, bg=PANEL, pady=6)
        btn_bar.pack(fill="x")
        self._btn_start = tk.Button(btn_bar, text="▶  Alles testen",
                  font=("Segoe UI", 10, "bold"), bg="#16a34a", fg=FG,
                  relief="flat", cursor="hand2", padx=16, pady=6,
                  borderwidth=0, command=self._start_tests)
        self._btn_start.pack(side="left", padx=8)

        tk.Button(btn_bar, text="🔄  Opnieuw",
                  font=("Segoe UI", 9), bg=PANEL2, fg=FG,
                  relief="flat", cursor="hand2", padx=12, pady=6,
                  borderwidth=0, command=self._reset).pack(side="left", padx=4)

        tk.Button(btn_bar, text="📊  Exporteer CSV",
                  font=("Segoe UI", 9), bg="#0c4a6e", fg=FG,
                  relief="flat", cursor="hand2", padx=12, pady=6,
                  borderwidth=0, command=self._exporteer_csv).pack(side="right", padx=8)

        # Filter knoppen
        filter_frame = tk.Frame(self, bg=BG, padx=14, pady=4)
        filter_frame.pack(fill="x")
        tk.Label(filter_frame, text="Toon:",
                 font=("Segoe UI", 8), bg=BG, fg=DIM).pack(side="left")
        self._filter = tk.StringVar(value="ALLES")
        for label, waarde in [("Alles","ALLES"), ("Fouten","FOUT"),
                               ("Waarschuwingen","WARN"), ("OK","OK")]:
            tk.Radiobutton(filter_frame, text=label, variable=self._filter,
                          value=waarde, font=("Segoe UI", 8),
                          bg=BG, fg=FG, selectcolor=PANEL2,
                          activebackground=BG,
                          command=self._ververs_lijst).pack(side="left", padx=6)

        # Resultatenlijst
        lijst_frame = tk.Frame(self, bg=BG)
        lijst_frame.pack(fill="both", expand=True, padx=10, pady=4)

        self._tekst = tk.Text(lijst_frame, bg="#0d1117", fg=FG,
                              font=("Courier New", 9), wrap="none",
                              relief="flat", state="disabled",
                              insertbackground=FG)
        sb_v = tk.Scrollbar(lijst_frame, command=self._tekst.yview)
        sb_h = tk.Scrollbar(lijst_frame, orient="horizontal",
                            command=self._tekst.xview)
        self._tekst.configure(yscrollcommand=sb_v.set,
                              xscrollcommand=sb_h.set)
        sb_v.pack(side="right", fill="y")
        sb_h.pack(side="bottom", fill="x")
        self._tekst.pack(side="left", fill="both", expand=True)

        # Tags
        self._tekst.tag_configure("OK",   foreground="#4ade80")
        self._tekst.tag_configure("FOUT", foreground="#f87171",
                                  font=("Courier New", 9, "bold"))
        self._tekst.tag_configure("WARN", foreground="#f59e0b")
        self._tekst.tag_configure("INFO", foreground="#60a5fa")
        self._tekst.tag_configure("CAT",  foreground="#818cf8",
                                  font=("Courier New", 9, "bold"))
        self._tekst.tag_configure("DIM",  foreground="#6c7086")

        # Statusbalk
        self._lbl_status = tk.Label(self, text="Klaar om te testen",
                 font=("Segoe UI", 8), bg=PANEL2, fg=DIM, anchor="w",
                 pady=4, padx=10)
        self._lbl_status.pack(fill="x", side="bottom")

        self._toon_intro()

    def _toon_intro(self):
        self._tekst.configure(state="normal")
        self._tekst.delete("1.0", "end")
        self._tekst.insert("end",
            f"Pi NAS Suite — Test Suite\n"
            f"{'─' * 60}\n"
            f"Aantal checks: {len(self.checks)}\n"
            f"NAS root:      {_NAS_ROOT}\n\n"
            f"Klik 'Alles testen' om te beginnen.\n",
            "DIM")
        self._tekst.configure(state="disabled")

    def _start_tests(self):
        if self._bezig:
            return
        self._bezig = True
        self._btn_start.configure(state="disabled", bg=PANEL2,
                                   text="⏳  Bezig...")
        self._lbl_status.configure(text="Tests uitvoeren...")
        self._resultaten = []

        for check in self.checks:
            check.status = "?"
            check.detail = ""

        threading.Thread(target=self._voer_tests_uit, daemon=True).start()

    def _voer_tests_uit(self):
        totaal = len(self.checks)
        for i, check in enumerate(self.checks):
            self.after(0, lambda c=check, n=i: self._update_voortgang(c, n, totaal))
            check.uitvoeren()
            self._resultaten.append(check)
            self.after(0, lambda c=check: self._voeg_resultaat_toe(c))

        self.after(0, self._tests_klaar)

    def _update_voortgang(self, check, n, totaal):
        pct = int(n / totaal * 100)
        self._lbl_voortgang.configure(
            text=f"[{n}/{totaal}]  {check.naam}")
        self._canvas_pb.update_idletasks()
        breedte = self._canvas_pb.winfo_width()
        if self._pb_balk:
            self._canvas_pb.delete(self._pb_balk)
        self._pb_balk = self._canvas_pb.create_rectangle(
            0, 0, int(breedte * n / totaal), 8,
            fill=ACCENT, outline="")

    def _voeg_resultaat_toe(self, check):
        self._tekst.configure(state="normal")

        # Categoriekop als eerste van categorie
        cat_checks = [c for c in self.checks if c.categorie == check.categorie]
        if cat_checks[0] is check:
            self._tekst.insert("end",
                f"\n{check.categorie}\n{'─' * 50}\n", "CAT")

        # Status symbool
        sym = {"OK": "✓", "FOUT": "✗", "WARN": "!", "INFO": "i"}.get(
            check.status, "?")
        tag = check.status if check.status in ("OK","FOUT","WARN") else "INFO"

        # Naam + status
        naam_pad = f"  {sym}  {check.naam:<45}"
        self._tekst.insert("end", naam_pad, tag)

        # Detail
        if check.detail:
            detail = check.detail[:60]
            self._tekst.insert("end", f"  {detail}", "DIM")
        self._tekst.insert("end", "\n")

        self._tekst.see("end")
        self._tekst.configure(state="disabled")

    def _tests_klaar(self):
        self._bezig = False
        self._btn_start.configure(state="normal", bg="#16a34a",
                                   text="▶  Alles testen")

        # Samenvatting
        ok   = sum(1 for c in self.checks if c.status == "OK")
        fout = sum(1 for c in self.checks if c.status == "FOUT")
        warn = sum(1 for c in self.checks if c.status == "WARN")
        totaal = len(self.checks)

        kleur = "#4ade80" if fout == 0 else "#f87171"
        self._lbl_samenvatting.configure(
            text=f"✓ {ok}  ✗ {fout}  ! {warn}  van {totaal}",
            fg=kleur)

        self._lbl_voortgang.configure(text=f"Klaar — {totaal} checks uitgevoerd")
        if self._pb_balk:
            self._canvas_pb.delete(self._pb_balk)
        breedte = self._canvas_pb.winfo_width()
        self._canvas_pb.create_rectangle(
            0, 0, breedte, 8,
            fill="#4ade80" if fout == 0 else "#f87171", outline="")

        # Samenvatting onderaan
        self._tekst.configure(state="normal")
        self._tekst.insert("end",
            f"\n{'═' * 60}\n"
            f"  SAMENVATTING: {ok} OK  ·  {fout} FOUTEN  ·  {warn} WAARSCHUWINGEN\n"
            f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{'═' * 60}\n",
            "FOUT" if fout > 0 else "OK")
        self._tekst.see("end")
        self._tekst.configure(state="disabled")

        status_txt = f"✓ {ok} OK  ·  ✗ {fout} fouten  ·  ! {warn} waarschuwingen"
        self._lbl_status.configure(text=status_txt,
                                    fg=kleur)

    def _ververs_lijst(self):
        """Herfilter de resultaten op basis van geselecteerde filter."""
        if not self._resultaten:
            return
        filter_val = self._filter.get()
        self._tekst.configure(state="normal")
        self._tekst.delete("1.0", "end")

        huidige_cat = None
        for check in self._resultaten:
            if filter_val != "ALLES" and check.status != filter_val:
                continue
            if check.categorie != huidige_cat:
                huidige_cat = check.categorie
                self._tekst.insert("end",
                    f"\n{check.categorie}\n{'─' * 50}\n", "CAT")
            sym = {"OK": "✓", "FOUT": "✗", "WARN": "!", "INFO": "i"}.get(
                check.status, "?")
            tag = check.status if check.status in ("OK","FOUT","WARN") else "INFO"
            naam_pad = f"  {sym}  {check.naam:<45}"
            self._tekst.insert("end", naam_pad, tag)
            if check.detail:
                self._tekst.insert("end", f"  {check.detail[:60]}", "DIM")
            self._tekst.insert("end", "\n")

        self._tekst.configure(state="disabled")

    def _reset(self):
        for check in self.checks:
            check.status = "?"
            check.detail = ""
        self._resultaten = []
        self._lbl_samenvatting.configure(text="")
        self._lbl_voortgang.configure(text="Nog niet gestart")
        if self._pb_balk:
            self._canvas_pb.delete(self._pb_balk)
        self._pb_balk = None
        self._btn_start.configure(state="normal")
        self._filter.set("ALLES")
        self._toon_intro()

    def _exporteer_csv(self):
        if not self._resultaten:
            messagebox.showinfo("Export", "Eerst tests uitvoeren.")
            return
        pad = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV bestanden", "*.csv"), ("Alle bestanden", "*.*")],
            initialfile=f"pinas_test_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            title="Exporteer testresultaten")
        if not pad:
            return
        try:
            with open(pad, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["Categorie", "Check", "Status", "Detail",
                            "Optioneel", "Tijdstip"])
                for c in self._resultaten:
                    w.writerow([c.categorie, c.naam, c.status,
                                c.detail, "Ja" if c.optioneel else "Nee",
                                c.tijdstip])
            self._lbl_status.configure(
                text=f"CSV geëxporteerd: {pad}", fg="#4ade80")
        except Exception as e:
            messagebox.showerror("Export fout", str(e))

    def _sluiten(self):
        self.destroy()
        if self._root_eigenaar:
            self._master.destroy()


# ── Integratie met Pi NAS Menu ────────────────────────────────────────────────
def open_test_venster(master=None):
    """Aanroepen vanuit Pi_NAS_Menu.pyw."""
    v = TestSuiteVenster(master)
    if master is None:
        v._master.mainloop()
    return v


# ── Standalone ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    open_test_venster()
