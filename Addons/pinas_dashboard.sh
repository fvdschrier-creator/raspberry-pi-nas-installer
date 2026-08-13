#!/usr/bin/env bash
###############################################################################
# PiNAS - Dashboard installer
#
# Installeert een eigen, met wachtwoord beveiligde webpagina op de Pi
# (poort 8095) die het statusoverzicht (hardware, schijfruimte, diensten),
# het addon-overzicht (installeren/openen, zelfde als Addons Beheer), en
# de Vaultwarden-certificaat- en AirPrint-profiel-download samenbrengt in
# 1 pagina - mobielvriendelijk, dus multifunctioneel voor zowel pc als
# telefoon/tablet. Bereikbaar vanaf elk apparaat, thuis en via ZeroTier
# ook onderweg.
#
# (12 augustus 2026, wens Frans) Vervangt sindsdien de losse mobiele
# statuspagina (pinas_status_pagina.sh, poort 8090) volledig - die was er
# inhoudelijk een subset van. Alles wat de statuspagina kon, kan hier nu
# ook: het "toevoegen aan beginscherm"-icoon, de Vaultwarden-root-
# certificaat-download, en het AirPrint-profiel voor de Printserver.
#
# Zesde add-on naast Nextcloud, Pi-hole, ZeroTier, Vaultwarden en
# Printserver. Zelfde installatiepatroon als die 5: wachtwoord eenmalig
# getoond, idempotent (opnieuw draaien wijzigt een bestaand wachtwoord
# niet), eigen systemd-dienst, eigen versie-afdruk voor Addons Beheer's
# "Bijgewerkt"-check. Wachtwoord kwijt? Zie
# pinas_dashboard_wachtwoord_resetten.sh.
#
# Gebruik:  sudo bash pinas_dashboard.sh
###############################################################################

set -Eeuo pipefail

readonly VERSION="2.0"
readonly LOGFILE="/var/log/pinas_dashboard.log"
readonly PORT="8095"
readonly APP_DIR="/opt/pinas-dashboard"
readonly HASH_FILE="${APP_DIR}/wachtwoord.hash"
readonly SECRET_FILE="${APP_DIR}/secret.key"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

mkdir -p /var/log; touch "$LOGFILE"; chmod 600 "$LOGFILE"
exec > >(tee >(sed -r 's/\x1b\[[0-9;]*m//g' >> "$LOGFILE")) 2>&1

log()     { echo; echo -e "${BLUE}[$(date '+%F %T')]${NC} $1"; }
success() { echo -e "${GREEN}OK: $1${NC}"; }
warn()    { echo -e "${YELLOW}LET OP: $1${NC}"; }
error()   { echo -e "${RED}FOUT: $1${NC}"; }
on_error(){ error "Afgebroken op regel $1. Log: $LOGFILE"; exit 1; }
trap 'on_error $LINENO' ERR

pauze() { echo; read -rp ">> Druk op ENTER om door te gaan... " _ || true; }

###############################################################################
# 0. Welkom + controles
###############################################################################
welkom() {
cat <<EOF

=====================================================================
  PiNAS - Dashboard
  Versie ${VERSION}
=====================================================================

  Installeert een eigen, met wachtwoord beveiligde webpagina op de Pi
  (poort ${PORT}), mobielvriendelijk en multifunctioneel voor pc EN
  telefoon/tablet:
    - Raspberry Pi hardware, schijfruimte, diensten
    - Addon-overzicht met openen/installeren (zoals Addons Beheer)
    - Vaultwarden-rootcertificaat en AirPrint-profiel downloaden

    Thuis     : http://<ip-van-de-pi>:${PORT}
    Onderweg  : via ZeroTier (als geinstalleerd)

  Tip: voeg de pagina op je telefoon toe aan het beginscherm (via het
  deel-menu van de browser) voor een eigen "app-icoon".

  Aan het einde krijg je een EENMALIG getoond wachtwoord - schrijf dat
  op. Er wordt alleen een hash van opgeslagen, nooit het wachtwoord zelf.

  Duurt ongeveer 2-3 minuten.

  Log van deze installatie: ${LOGFILE}

=====================================================================
EOF
pauze
}

check_root() {
    [[ $EUID -eq 0 ]] || { error "Start met: sudo bash pinas_dashboard.sh"; exit 1; }
    success "Rootrechten OK."
}

check_internet() {
    log "Internet controleren..."
    curl -fsSL --connect-timeout 10 https://github.com >/dev/null \
        && success "Internet OK." || { error "Geen internet."; exit 1; }
}

detect_network() {
    log "Netwerk bepalen..."
    PI_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')
    [[ -n "${PI_IP:-}" ]] || { error "Kan IP niet bepalen."; exit 1; }
    success "IP van deze Pi: $PI_IP"
}

check_poort() {
    log "Poort controleren..."
    if ss -tulpn 2>/dev/null | grep -q ":${PORT} "; then
        if ss -tulpn 2>/dev/null | grep ":${PORT} " | grep -qi python; then
            warn "Poort ${PORT} is al bezet door een eerder Dashboard - wordt overgenomen."
        else
            error "Poort ${PORT} is al bezet door iets anders. Pas PORT bovenin het script aan."; exit 1
        fi
    else
        success "Poort ${PORT} vrij."
    fi
}

###############################################################################
# 1. Software
###############################################################################
install_deps() {
    log "Benodigde software installeren (python3-flask)..."
    apt-get update -qq
    apt-get install -y python3-flask
    python3 -c "import flask, werkzeug" || { error "Flask/Werkzeug niet bruikbaar na installatie."; exit 1; }
    success "python3-flask geinstalleerd."
}

###############################################################################
# 2. Wachtwoord + sessiesleutel (alleen bij eerste installatie)
###############################################################################
maak_wachtwoord() {
    mkdir -p "$APP_DIR"
    chmod 700 "$APP_DIR"
    if [[ -f "$HASH_FILE" ]]; then
        warn "Er staat al een wachtwoord ingesteld - dat blijft ongewijzigd."
        WACHTWOORD_TONEN="(ongewijzigd - het bestaande wachtwoord blijft gelden)"
        return
    fi
    read -rp ">> Typ je eigen wachtwoord voor het Dashboard, of laat leeg voor automatisch gegenereerd: " EIGEN_WACHTWOORD
    if [[ -n "$EIGEN_WACHTWOORD" ]]; then
        NIEUW_WACHTWOORD="$EIGEN_WACHTWOORD"
        log "Eigen wachtwoord instellen voor het Dashboard..."
    else
        log "Toegangswachtwoord genereren voor het Dashboard..."
        NIEUW_WACHTWOORD=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 16 || true)
    fi
    python3 -c "
from werkzeug.security import generate_password_hash
print(generate_password_hash('${NIEUW_WACHTWOORD}'))
" > "$HASH_FILE"
    chmod 600 "$HASH_FILE"
    WACHTWOORD_TONEN="$NIEUW_WACHTWOORD"
    success "Wachtwoord ingesteld (wordt aan het eind eenmalig getoond)."
}

maak_secret() {
    if [[ -f "$SECRET_FILE" ]]; then
        return
    fi
    log "Sleutel voor beveiligde sessies genereren..."
    python3 -c "import secrets; print(secrets.token_hex(32))" > "$SECRET_FILE"
    chmod 600 "$SECRET_FILE"
    success "Sessiesleutel aangemaakt."
}

###############################################################################
# 3. De webapp zelf
###############################################################################
maak_app() {
    log "Webapp wegschrijven (${APP_DIR}/app.py)..."
    cat > "${APP_DIR}/app.py" << 'APP_EOF'
#!/usr/bin/env python3
"""PiNAS - Dashboard.

Combineert het statusoverzicht (Pi-hardware, schijfruimte, diensten) en
het addon-overzicht (installeren/openen) in 1 webpagina, rechtstreeks op
de Pi zelf - bereikbaar vanaf elk apparaat (thuis en, via ZeroTier, ook
onderweg).

Hergebruikt bewust dezelfde detectielogica als pinas_addons_beheer.pyw -
geen nieuwe checks verzonnen.

(12 augustus 2026, wens Frans) Neemt sindsdien ALLES over van de losse
mobiele statuspagina (pinas_status_pagina.sh, poort 8090), die daarmee is
komen te vervallen - de statuspagina was er inhoudelijk een subset van
(zelfde hardware/schijven/diensten-overzicht), met alleen een paar
mobiel-specifieke extra's die hier nu ook zitten: het "toevoegen aan
beginscherm"-icoon/manifest, de Vaultwarden-rootcertificaat-download, en
het AirPrint-profiel voor de Printserver. 1 pagina, multifunctioneel voor
zowel pc als telefoon/tablet.

Draait als systemd-dienst pinas-dashboard.service (gebruiker pi), wordt
neergezet door pinas_dashboard.sh. Hoort NIET in de Windows-suite-boom,
dit bestand leeft alleen op de Pi zelf (/opt/pinas-dashboard).
"""
import base64
import datetime
import os
import plistlib
import shutil
import subprocess
import time
from datetime import timedelta
from pathlib import Path

from flask import Flask, request, session, redirect, url_for, render_template_string, Response
from werkzeug.security import generate_password_hash, check_password_hash

APP_DIR = Path(__file__).resolve().parent
HASH_FILE = APP_DIR / "wachtwoord.hash"
SECRET_FILE = APP_DIR / "secret.key"
PORT = 8095
# Waar addon-scripts terechtkomen zodra ze via Addons Beheer of handmatig
# via SSH zijn geupload (zie _draai_script_op_pi in pinas_addons_beheer.pyw).
ADDON_SCRIPT_DIR = Path("/home/pi")

# 19 juli 2026: root-certificaat van Vaultwarden's eigen mini-CA - dit is
# het bestand dat je maar EENMALIG per apparaat hoeft te vertrouwen, zie
# pinas_vaultwarden.sh. (Overgenomen van pinas_status_pagina.sh, 12
# augustus 2026.)
VAULTWARDEN_CA = Path("/etc/pinas-ca/ca.crt")
VAULTWARDEN_SERVER_CERT = Path("/etc/pinas-ca/server.crt")

app = Flask(__name__)
app.secret_key = SECRET_FILE.read_text().strip()
app.permanent_session_lifetime = timedelta(days=30)


# ── Icoon voor "Zet op beginscherm" (iOS + Android) ─────────────────────────
# PiNAS-logo, ingebakken als base64 zodat er geen los bestand nodig is op de
# Pi. iOS gebruikt apple-touch-icon; Android/Chrome gebruikt manifest.json.
# (12 augustus 2026, overgenomen van pinas_status_pagina.sh - was daar 18
# juli 2026 toegevoegd, wens Frans.)
ICOON_PNG_B64 = (
    "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"
    "RK5CYII="
)


@app.route("/apple-touch-icon.png")
@app.route("/apple-touch-icon-precomposed.png")
@app.route("/icon.png")
@app.route("/favicon.ico")
def icoon():
    return Response(base64.b64decode(ICOON_PNG_B64), mimetype="image/png")


@app.route("/manifest.json")
def manifest():
    return {
        "name": "PiNAS Dashboard",
        "short_name": "PiNAS",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#1565c0",
        "theme_color": "#1565c0",
        "icons": [
            {"src": "/icon.png", "sizes": "180x180", "type": "image/png"},
        ],
    }


# -- Hergebruikte hulpfuncties (letterlijk overgenomen uit  -----------------
# -- pinas_status_pagina.sh's app.py, zelfde gedrag) -------------------------
def _run(cmd, timeout=6):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def _op_pad(commando):
    if shutil.which(commando):
        return True
    for basis in ("/usr/sbin", "/usr/local/sbin", "/sbin", "/usr/local/bin"):
        if os.path.exists(os.path.join(basis, commando)):
            return True
    return False


def _commando_pad(commando):
    """Zoekt het volledige pad van een commando (zerotier-cli/ip staan vaak
    in /usr/sbin, buiten het beperkte PATH van de achtergronddienst)."""
    pad = shutil.which(commando)
    if pad:
        return pad
    for basis in ("/usr/sbin", "/usr/local/sbin", "/sbin", "/usr/local/bin"):
        kandidaat = os.path.join(basis, commando)
        if os.path.exists(kandidaat):
            return kandidaat
    return commando


def _zerotier_cli_pad():
    return _commando_pad("zerotier-cli")


def _zerotier_ip():
    for regel in _run(["sudo", "-n", _zerotier_cli_pad(), "listnetworks"]).splitlines():
        delen = regel.split()
        if not delen:
            continue
        kandidaat = delen[-1].split(",")[0].split("/")[0]
        if kandidaat.count(".") == 3:
            return kandidaat
    return None


def _lan_ip():
    """Lokale LAN-IP van de Pi zelf, los van request.host - nodig omdat het
    AirPrint-profiel BEIDE adressen (thuis + onderweg) tegelijk moet
    bevatten, ongeacht vanaf welk netwerk je deze pagina nu toevallig
    bekijkt."""
    for regel in _run([_commando_pad("ip"), "route", "get", "1.1.1.1"]).splitlines():
        delen = regel.split()
        if "src" in delen:
            return delen[delen.index("src") + 1]
    return None


def _actief(unit):
    return _run(["systemctl", "is-active", unit]) == "active"


def _ingeschakeld_of_actief(unit):
    return _actief(unit) or _run(["systemctl", "is-enabled", unit]) in ("enabled", "static")


def _cups_printer_namen():
    namen = []
    for regel in _run(["lpstat", "-p"]).splitlines():
        if regel.startswith("printer "):
            delen = regel.split()
            if len(delen) >= 2:
                namen.append(delen[1])
    return namen


def _vaultwarden_status():
    """Container-status + resterende geldigheid van het servercertificaat
    (overgenomen van pinas_status_pagina.sh, 12 augustus 2026), zodat je
    hier ook ruim van tevoren ziet aankomen wanneer het (jaarlijks,
    automatisch) vernieuwd wordt."""
    namen = _run(["docker", "ps", "-a", "--format", "{{.Names}}"]).splitlines()
    aanwezig = "vaultwarden" in namen
    actief = False
    if aanwezig:
        actieve_namen = _run(["docker", "ps", "--format", "{{.Names}}"]).splitlines()
        actief = "vaultwarden" in actieve_namen

    dagen_geldig = None
    if VAULTWARDEN_SERVER_CERT.exists():
        einddatum = _run(["openssl", "x509", "-enddate", "-noout",
                           "-in", str(VAULTWARDEN_SERVER_CERT)])
        if einddatum.startswith("notAfter="):
            try:
                eind = datetime.datetime.strptime(
                    einddatum.split("=", 1)[1].strip(), "%b %d %H:%M:%S %Y %Z")
                dagen_geldig = (eind - datetime.datetime.utcnow()).days
            except Exception:
                dagen_geldig = None

    return {"aanwezig": aanwezig, "actief": actief, "dagen_geldig": dagen_geldig}


def _schijf(pad):
    if not os.path.ismount(pad):
        return None
    regels = _run(["df", "-h", pad]).splitlines()
    if len(regels) < 2:
        return None
    delen = regels[1].split()
    if len(delen) < 5:
        return None
    return {"grootte": delen[1], "gebruikt": delen[2], "vrij": delen[3], "percentage": delen[4]}


# -- Addons: zelfde 6, zelfde scriptnamen als _ADDON_SCRIPT in --------------
# -- pinas_addons_beheer.pyw - bewust dezelfde bron, niet opnieuw verzonnen --
ADDONS = {
    "nextcloud":    {"naam": "Nextcloud",           "script": "pinas_nextcloud.sh",
                      "poort_pad": "/nextcloud", "poort": 80, "https": False},
    "pihole":       {"naam": "Pi-hole",             "script": "pinas_pihole.sh",
                      "poort_pad": "/admin", "poort": 8081, "https": False},
    "zerotier":     {"naam": "ZeroTier",            "script": "pinas_zerotier.sh",
                      "poort_pad": None, "poort": None, "https": False},
    "vaultwarden":  {"naam": "Vaultwarden",         "script": "pinas_vaultwarden.sh",
                      "poort_pad": None, "poort": 8443, "https": True},
    "printer":      {"naam": "Printserver (CUPS)",  "script": "pinas_printer.sh",
                      "poort_pad": "/admin", "poort": 631, "https": False},
}


def _addon_geinstalleerd(key):
    """Zelfde detectielogica als _haal_addon_status() in pinas_addons_beheer.pyw,
    nu lokaal uitgevoerd (geen SSH nodig, we draaien al op de Pi)."""
    if key == "pihole":
        return "actief" if _op_pad("pihole") else "afwezig"
    if key == "zerotier":
        aanwezig = (_op_pad("zerotier-cli")
                    or os.path.exists("/usr/sbin/zerotier-cli")
                    or os.path.exists("/usr/local/bin/zerotier-cli"))
        return "actief" if aanwezig else "afwezig"
    if key == "nextcloud":
        aanwezig = (os.path.exists("/var/www/html/nextcloud/config/config.php")
                    or os.path.exists("/var/www/nextcloud/config/config.php"))
        return "actief" if aanwezig else "afwezig"
    if key == "vaultwarden":
        namen = _run(["docker", "ps", "-a", "--format", "{{.Names}}"])
        if "vaultwarden" not in namen.splitlines():
            return "afwezig"
        actief = _run(["docker", "ps", "--format", "{{.Names}}"])
        return "actief" if "vaultwarden" in actief.splitlines() else "gestopt"
    if key == "printer":
        aanwezig = (_run(["systemctl", "cat", "cups"]) != "" or _op_pad("cupsd"))
        if not aanwezig:
            return "afwezig"
        return "actief" if _actief("cups") else "gestopt"
    return "afwezig"


def _addon_url(key, host):
    info = ADDONS[key]
    if info["poort"] is None:
        return None
    schema = "https" if info["https"] else "http"
    pad = info["poort_pad"] or ""
    return f"{schema}://{host}:{info['poort']}{pad}"


def verzamel_addons(host):
    resultaat = []
    for key, info in ADDONS.items():
        status = _addon_geinstalleerd(key)
        script_lokaal = (ADDON_SCRIPT_DIR / info["script"]).exists()
        resultaat.append({
            "key": key,
            "naam": info["naam"],
            "status": status,
            "url": _addon_url(key, host) if status == "actief" else None,
            "script": info["script"],
            "script_lokaal_aanwezig": script_lokaal,
        })
    return resultaat


def verzamel_status(host):
    # (naam, actief, systemd-eenheid-voor-herstarten-of-None, url-of-None)
    # systemd-eenheid = None betekent: geen "Herstarten/Logs"-knop (geen
    # nette 1-op-1 systemd-eenheid, bijv. Nextcloud/Vaultwarden draaien
    # via apache/docker, niet via 1 losse unit die je zomaar herstart)
    diensten = [
        ("Samba", _actief("smbd"), "smbd", None),
        ("Nextcloud",
         (os.path.exists("/var/www/html/nextcloud/config/config.php")
          or os.path.exists("/var/www/nextcloud/config/config.php")),
         None, f"http://{host}/nextcloud"),
        ("FileBrowser", _ingeschakeld_of_actief("filebrowser"), "filebrowser", f"http://{host}:8080"),
        ("Cockpit", _ingeschakeld_of_actief("cockpit") or _ingeschakeld_of_actief("cockpit.socket"),
         "cockpit", f"http://{host}:9090"),
        ("Externe HDD svc", _actief("seagate-web"), "seagate-web", f"http://{host}:8765"),
    ]
    pihole_aanwezig = _op_pad("pihole")
    diensten.append(("Pi-hole", pihole_aanwezig, "pihole-FTL" if pihole_aanwezig else None,
                      f"http://{host}:8081/admin" if pihole_aanwezig else None))
    zt_aanwezig = _op_pad("zerotier-cli")
    diensten.append(("ZeroTier", zt_aanwezig, "zerotier-one" if zt_aanwezig else None,
                      "https://my.zerotier.com" if zt_aanwezig else None))
    vw = _vaultwarden_status()
    diensten.append(("Vaultwarden", vw["actief"], "__docker_vaultwarden__" if vw["aanwezig"] else None,
                      f"https://{host}:8443" if vw["actief"] else None))
    cups_actief = _actief("cups") or _op_pad("cupsd")
    cups_printers = _cups_printer_namen() if cups_actief else []
    diensten.append(("Printserver", cups_actief, "cups" if cups_actief else None,
                      f"http://{host}:631/admin" if cups_actief else None))
    diensten.append(("PiNAS Dashboard (dit scherm)", True, "pinas-dashboard", None))

    model = _run(["cat", "/proc/device-tree/model"]).split("\x00")[0].strip() or "onbekend"
    ram = _run(["bash", "-c", "free -h | awk '/Mem/{print $2}'"]) or "onbekend"
    sd_grootte = _run(["bash", "-c", "lsblk -no SIZE /dev/mmcblk0 2>/dev/null | head -1"]) or "onbekend"
    temp_ruw = _run(["vcgencmd", "measure_temp"]) if shutil.which("vcgencmd") else ""
    temp = temp_ruw.replace("temp=", "").replace("'C", " C") if temp_ruw else "onbekend"
    uptime = _run(["uptime", "-p"]) or "onbekend"

    return {
        "diensten": diensten,
        "model": model, "ram": ram, "sd_grootte": sd_grootte, "temp": temp, "uptime": uptime,
        "schijven": {"Opslag (SSD)": _schijf("/mnt/opslag"), "Backup (HDD)": _schijf("/mnt/backup")},
        # (12 augustus 2026) Overgenomen van pinas_status_pagina.sh: ZeroTier-
        # adres voor de Bereikbaarheid-kaart, Vaultwarden-certificaatstatus
        # voor de downloadkaart, en CUPS-printernamen voor het AirPrint-
        # profiel.
        "zt_ip": _zerotier_ip() if zt_aanwezig else None,
        "vw_cert_beschikbaar": VAULTWARDEN_CA.exists(),
        "vw_dagen_geldig": vw["dagen_geldig"],
        "printer_profiel_beschikbaar": len(cups_printers) > 0,
        "printer_namen": ", ".join(cups_printers),
        "tijd": time.strftime("%d-%m-%Y %H:%M"),
    }


def ingelogd():
    return session.get("ingelogd") is True


LOGIN_HTML = """
<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PiNAS Dashboard</title>
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="icon" href="/icon.png">
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#1565c0">
<style>
body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#eef1f5;margin:0;
     display:flex;align-items:center;justify-content:center;height:100vh}
.kaart{background:#fff;border-radius:12px;padding:28px 24px;width:100%;max-width:340px;
       box-shadow:0 2px 12px rgba(0,0,0,.12)}
h1{font-size:18px;color:#0d3d75;margin:0 0 6px;text-align:center}
p.sub{font-size:12px;color:#c0392b;text-align:center;margin:0 0 18px}
input[type=password]{width:100%;box-sizing:border-box;padding:12px;font-size:16px;
       border:1px solid #ccd3da;border-radius:8px;margin-bottom:14px}
button{width:100%;padding:12px;font-size:15px;background:#1565c0;color:#fff;border:0;
       border-radius:8px}
.fout{color:#c0392b;font-size:13px;text-align:center;margin-bottom:10px}
</style></head><body>
<div class="kaart">
  <h1>PiNAS Dashboard</h1>
  {% if fout %}<p class="fout">{{ fout }}</p>{% endif %}
  <form method="post">
    <input type="password" name="ww" placeholder="Wachtwoord" autofocus>
    <button type="submit">Inloggen</button>
  </form>
</div></body></html>
"""

DASHBOARD_HTML = """
<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PiNAS Dashboard</title>
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="icon" href="/icon.png">
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#1565c0">
<style>
body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#eef1f5;margin:0;
     padding:16px;color:#222}
h2{font-size:14px;color:#5f6b7a;text-transform:uppercase;letter-spacing:.04em;
   margin:22px 0 8px}
.kaart{background:#fff;border-radius:10px;padding:12px 16px;margin-bottom:8px;
       box-shadow:0 1px 4px rgba(0,0,0,.08);display:flex;align-items:center;
       justify-content:space-between;flex-wrap:wrap;gap:8px}
.naam{font-weight:600;font-size:15px}
.status{font-size:12px;padding:3px 10px;border-radius:12px}
.st-actief{background:#e3f6ea;color:#1a7d42}
.st-gestopt{background:#fdeee0;color:#b5620a}
.st-afwezig{background:#f0f1f3;color:#6b7280}
a.knop, button.knop{font-size:13px;padding:7px 14px;border-radius:7px;border:1px solid #1565c0;
      background:#fff;color:#1565c0;text-decoration:none;cursor:pointer}
.commando{font-family:monospace;font-size:12px;background:#f4f5f7;padding:8px 10px;
          border-radius:6px;margin-top:6px;width:100%;word-break:break-all;display:none}
.top{display:flex;justify-content:space-between;align-items:center}
.uitloggen{font-size:12px;color:#5f6b7a;text-decoration:none}
table.info{width:100%;font-size:13px;border-collapse:collapse}
table.info td{padding:4px 0}
table.info td.w{color:#5f6b7a;width:45%}
</style>
<script>
function toonCommando(id){
  var el = document.getElementById(id);
  el.style.display = el.style.display === 'block' ? 'none' : 'block';
}
</script>
</head><body>
<div class="top">
  <div style="font-size:16px;font-weight:600">PiNAS Dashboard</div>
  <a class="uitloggen" href="{{ url_for('uitloggen') }}">Uitloggen</a>
</div>

<h2>Raspberry Pi - hardware</h2>
<div class="kaart"><table class="info">
  <tr><td class="w">Model</td><td>{{ status.model }}</td></tr>
  <tr><td class="w">RAM</td><td>{{ status.ram }}</td></tr>
  <tr><td class="w">SD-kaart</td><td>{{ status.sd_grootte }}</td></tr>
  <tr><td class="w">CPU-temperatuur</td><td>{{ status.temp }}</td></tr>
  <tr><td class="w">Uptime</td><td>{{ status.uptime }}</td></tr>
</table></div>

<h2>Schijfruimte</h2>
{% for naam, s in status.schijven.items() %}
<div class="kaart">
  <span class="naam">{{ naam }}</span>
  <span style="font-size:13px;color:#5f6b7a">
    {% if s %}{{ s.vrij }} vrij van {{ s.grootte }} ({{ s.percentage }} in gebruik){% else %}niet gekoppeld{% endif %}
  </span>
</div>
{% endfor %}

<h2>Raspberry Pi - diensten</h2>
{% for naam, ok, unit, url in status.diensten %}
<div class="kaart">
  <span class="naam">{{ naam }}</span>
  <div style="display:flex;gap:8px;align-items:center">
    <span class="status {{ 'st-actief' if ok else 'st-afwezig' }}">{{ 'Actief' if ok else 'Niet actief' }}</span>
    {% if url and ok %}<a class="knop" href="{{ url }}" target="_blank">Openen</a>{% endif %}
  </div>
</div>
{% endfor %}

<h2>Bereikbaarheid</h2>
<div class="kaart">
  <span class="naam">Thuis (LAN)</span>
  <span style="font-size:13px;color:#5f6b7a">{{ host }}</span>
</div>
{% if status.zt_ip %}
<div class="kaart">
  <span class="naam">Onderweg (ZeroTier)</span>
  <a class="knop" href="http://{{ status.zt_ip }}:8095" target="_blank">{{ status.zt_ip }}:8095</a>
</div>
{% endif %}

{% if status.vw_cert_beschikbaar %}
<div class="kaart" style="display:block">
  <details>
    <summary style="cursor:pointer;font-weight:600;font-size:14px;color:#0d3d75">Vaultwarden - root-certificaat</summary>
    <div style="margin-top:10px;font-size:13px;color:#5f6b7a;line-height:1.5">
      Dit certificaat hoef je maar <b>eenmalig per apparaat</b> te vertrouwen - het
      onderliggende servercertificaat wordt daarna automatisch elk jaar vernieuwd,
      zonder dat je dit opnieuw hoeft te doen.
      {% if status.vw_dagen_geldig is not none %}
      <br>Huidig servercertificaat nog geldig: <b>{{ status.vw_dagen_geldig }} dagen</b>.
      {% endif %}
    </div>
    <a class="knop" style="display:inline-block;margin-top:10px" href="{{ url_for('vaultwarden_ca') }}"
       download="pinas-ca.crt">&#8681; Root-certificaat downloaden</a>
  </details>
</div>
{% endif %}

{% if status.printer_profiel_beschikbaar %}
<div class="kaart" style="display:block">
  <details>
    <summary style="cursor:pointer;font-weight:600;font-size:14px;color:#0d3d75">Printserver - AirPrint (thuis en onderweg)</summary>
    <div style="margin-top:10px;font-size:13px;color:#5f6b7a;line-height:1.5">
      Thuis verschijnt de printer ({{ status.printer_namen }}) vanzelf in het
      print-menu - geen verdere actie nodig. Onderweg zonder wifi via ZeroTier:
      zie de Suite Handleiding voor de volledige opzet (2e wachtrij in CUPS +
      Epson Smart Panel-koppeling).
    </div>
    <a class="knop" style="display:inline-block;margin-top:10px"
       href="{{ url_for('printer_airprint_profiel') }}">&#8681; AirPrint-profiel downloaden</a>
  </details>
</div>
{% endif %}

<h2>Addons</h2>
{% for a in addons %}
<div class="kaart">
  <div>
    <div class="naam">{{ a.naam }}</div>
    {% if not a.script_lokaal_aanwezig %}
    <div style="font-size:11px;color:#b5620a">script niet gevonden op {{ addon_dir }} - hier nog niet installeerbaar</div>
    {% endif %}
    <div class="commando" id="cmd-{{ a.key }}">ssh pi@{{ host }} 'sudo bash /home/pi/{{ a.script }}'</div>
  </div>
  <div style="display:flex;gap:8px;align-items:center">
    <span class="status st-{{ a.status }}">
      {{ {'actief':'Geinstalleerd','gestopt':'Gestopt','afwezig':'Niet geinstalleerd'}[a.status] }}
    </span>
    {% if a.url %}<a class="knop" href="{{ a.url }}" target="_blank">Openen</a>{% endif %}
    {% if a.status != 'actief' %}
    <button class="knop" onclick="toonCommando('cmd-{{ a.key }}')">Installeren</button>
    {% endif %}
  </div>
</div>
{% endfor %}
<p style="font-size:11px;color:#9aa1ab;margin-top:20px">
  "Installeren" bij Addons toont het commando dat je zelf via SSH draait
  (de scripts vragen om bevestiging tijdens het draaien). Bijgewerkt: {{ status.tijd }}.
</p>
</body></html>
"""


@app.route("/", methods=["GET"])
def dashboard():
    if not ingelogd():
        return redirect(url_for("login"))
    host = request.host.split(":")[0]
    return render_template_string(
        DASHBOARD_HTML,
        status=verzamel_status(host),
        addons=verzamel_addons(host),
        addon_dir=str(ADDON_SCRIPT_DIR),
        host=host,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    fout = None
    if request.method == "POST":
        ww = request.form.get("ww", "")
        opgeslagen_hash = HASH_FILE.read_text().strip()
        if check_password_hash(opgeslagen_hash, ww):
            session.permanent = True
            session["ingelogd"] = True
            return redirect(url_for("dashboard"))
        fout = "Onjuist wachtwoord."
    return render_template_string(LOGIN_HTML, fout=fout)


@app.route("/uitloggen")
def uitloggen():
    session.clear()
    return redirect(url_for("login"))


# -- Vaultwarden-certificaat en AirPrint-profiel (overgenomen van --------
# -- pinas_status_pagina.sh, 12 augustus 2026) ----------------------------
@app.route("/vaultwarden-ca.crt")
def vaultwarden_ca():
    if not ingelogd():
        return redirect(url_for("login"))
    if not VAULTWARDEN_CA.exists():
        return "Certificaat niet gevonden - is Vaultwarden geinstalleerd?", 404
    return Response(
        VAULTWARDEN_CA.read_bytes(),
        mimetype="application/x-x509-ca-cert",
        headers={"Content-Disposition": 'attachment; filename="pinas-ca.crt"'})


def _airprint_entries_voor(naam, lan_ip, zt_ip):
    """Kiest per printernaam BEWUST een enkel adres i.p.v. beide tegelijk
    onder dezelfde naam - werkte niet betrouwbaar op iOS. Voeg in CUPS een
    2e wachtrij toe voor dezelfde fysieke printer met een naam die eindigt
    op '_onderweg' of '_zerotier' - die koppelt aan het ZeroTier-adres.
    Elke andere naam krijgt het lokale (thuis-)adres."""
    is_onderweg = naam.lower().endswith(("_onderweg", "_zerotier"))
    ip = zt_ip if is_onderweg else lan_ip
    if not ip:
        return []
    return [{"IPAddress": ip, "Port": 631, "ResourcePath": f"printers/{naam}"}]


# Vaste PayloadUUID's (niet elke keer opnieuw gegenereerd!) - eigen UUID's
# t.o.v. pinas_status_pagina.sh, zodat een download hier geen bestaand
# statuspagina-profiel op een toestel overschrijft (die twee kunnen naast
# elkaar hebben bestaan tijdens de overgang).
_AIRPRINT_PROFIEL_UUID = "6C9F0A2E-6C7E-4C0F-9C6E-6B6E7E3F9A11"
_AIRPRINT_PAYLOAD_UUID = "3B7C1E9D-2A4F-4E8B-9D3C-1F5A8E2C7B44"


@app.route("/pinas-printer-airprint.mobileconfig")
def printer_airprint_profiel():
    geen_cache = {"Cache-Control": "no-store"}
    if not ingelogd():
        return redirect(url_for("login"))
    printers = _cups_printer_namen()
    if not printers:
        return Response(
            "Geen printer gevonden in CUPS - voeg eerst een printer toe "
            "via http://<Pi-IP>:631 (Administration -> Add Printer).",
            status=404, headers=geen_cache)

    lan_ip = _lan_ip()
    zt_ip = _zerotier_ip()
    entries = []
    for naam in printers:
        entries.extend(_airprint_entries_voor(naam, lan_ip, zt_ip))
    if not entries:
        return Response("Kon geen LAN- of ZeroTier-adres bepalen voor de Pi.",
                         status=404, headers=geen_cache)

    profiel = {
        "PayloadContent": [{
            "AirPrint": entries,
            "PayloadDescription": "Voegt de PiNAS-printer(s) toe aan AirPrint - "
                                   "thuis via het lokale netwerk, onderweg via ZeroTier.",
            "PayloadDisplayName": "PiNAS Printserver",
            "PayloadIdentifier": "nl.pinas.airprint.printserver",
            "PayloadOrganization": "PiNAS",
            "PayloadType": "com.apple.airprint",
            "PayloadUUID": _AIRPRINT_PAYLOAD_UUID,
            "PayloadVersion": 1,
        }],
        "PayloadDescription": "PiNAS Printserver toevoegen aan AirPrint (thuis en onderweg via ZeroTier).",
        "PayloadDisplayName": "PiNAS Printserver - AirPrint",
        "PayloadIdentifier": "nl.pinas.airprint.profile",
        "PayloadOrganization": "PiNAS",
        "PayloadRemovalDisallowed": False,
        "PayloadType": "Configuration",
        "PayloadUUID": _AIRPRINT_PROFIEL_UUID,
        "PayloadVersion": 1,
    }
    return Response(
        plistlib.dumps(profiel, fmt=plistlib.FMT_XML),
        mimetype="application/x-apple-aspen-config",
        headers={"Content-Disposition": 'inline; filename="PiNAS_Printserver_AirPrint.mobileconfig"',
                 "Cache-Control": "no-store"})


if __name__ == "__main__":
    if not HASH_FILE.exists() or not SECRET_FILE.exists():
        raise SystemExit("Wachtwoord/sessiesleutel ontbreekt - draai eerst pinas_dashboard.sh")
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
APP_EOF

    # 13 augustus 2026 (verbeterpunt #8/#6, Frans): dit bestand is 700+
    # regels met de hele webapp verstopt in een heredoc - lastig te
    # linten/testen, en het ingebedde base64-icoon is al eens bijna
    # gecorrumpeerd door handmatig overtypen. Bewust GEEN structuurwijziging
    # (het 1-bestand-plak-en-klaar-patroon is precies waarom de rest van de
    # suite dit ook zo doet) - wel 2 harde controles vlak na het wegschrijven,
    # zodat een kapotte heredoc/icoon hier meteen opvalt i.p.v. pas bij een
    # falende systemd-dienst verderop.
    log "Weggeschreven app.py controleren..."
    if ! python3 -m py_compile "${APP_DIR}/app.py"; then
        error "app.py bevat een Python-syntaxfout - de heredoc is waarschijnlijk kapot."
        exit 1
    fi
    if ! python3 - "${APP_DIR}/app.py" <<'ICOONCHECK_EOF'
import re, base64, sys
pad = sys.argv[1]
inhoud = open(pad, encoding="utf-8").read()
match = re.search(r'ICOON_PNG_B64\s*=\s*\((.*?)\)', inhoud, re.DOTALL)
if not match:
    print("FOUT: ICOON_PNG_B64 niet gevonden in app.py.")
    sys.exit(1)
b64 = "".join(re.findall(r'"([^"]*)"', match.group(1)))
try:
    ruwe_bytes = base64.b64decode(b64, validate=True)
except Exception as e:
    print(f"FOUT: ICOON_PNG_B64 is geen geldige base64 ({e}).")
    sys.exit(1)
if not ruwe_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
    print("FOUT: ICOON_PNG_B64 decodeert niet naar een geldige PNG (PNG-magic-bytes ontbreken).")
    sys.exit(1)
print(f"OK: icoon decodeert naar een geldige PNG ({len(ruwe_bytes)} bytes).")
ICOONCHECK_EOF
    then
        error "Het ingebedde beginscherm-icoon in app.py is corrupt - opnieuw genereren/plakken nodig."
        exit 1
    fi
    rm -f "${APP_DIR}/app.py.pyc" 2>/dev/null || true
    find "${APP_DIR}" -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    success "Webapp weggeschreven en gecontroleerd (syntax + icoon geldig)."
}

###############################################################################
# 4. systemd-dienst
###############################################################################
maak_service() {
    log "Achtergronddienst instellen (systemd)..."
    cat > /etc/systemd/system/pinas-dashboard.service << 'SERVICE_EOF'
[Unit]
Description=PiNAS Dashboard
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 /opt/pinas-dashboard/app.py
WorkingDirectory=/opt/pinas-dashboard
Restart=on-failure
RestartSec=5
User=pi
Group=pi

[Install]
WantedBy=multi-user.target
SERVICE_EOF

    chown -R pi:pi "$APP_DIR"
    chmod 700 "$APP_DIR"
    chmod 600 "$HASH_FILE" "$SECRET_FILE"
    chmod 644 "${APP_DIR}/app.py"

    systemctl daemon-reload
    systemctl enable --now pinas-dashboard.service
    systemctl restart pinas-dashboard.service
    sleep 2
    if systemctl is-active --quiet pinas-dashboard; then
        success "Dashboard draait (poort ${PORT})."
    else
        error "Dashboard start niet. Check: journalctl -u pinas-dashboard"; exit 1
    fi
}

###############################################################################
# 5. Samenvatting
###############################################################################
samenvatting() {
    local zt_ip
    zt_ip=$(command -v zerotier-cli >/dev/null 2>&1 && zerotier-cli listnetworks 2>/dev/null \
            | awk '{print $NF}' | cut -d',' -f1 | cut -d'/' -f1 \
            | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | head -1 || true)
cat <<EOF

=====================================================================
  KLAAR - PiNAS Dashboard draait
=====================================================================

  Thuis (LAN)   : http://${PI_IP}:${PORT}
EOF
if [[ -n "${zt_ip:-}" ]]; then
cat <<EOF
  Onderweg (ZT) : http://${zt_ip}:${PORT}
EOF
else
cat <<EOF
  Onderweg      : installeer eerst ZeroTier (pinas_zerotier.sh) voor
                  toegang van onderweg
EOF
fi
cat <<EOF

  Wachtwoord    : ${WACHTWOORD_TONEN}
  (schrijf dit op - het wordt niet opnieuw getoond)

  Tip: open de link op je telefoon en voeg de pagina toe aan je
  beginscherm (browser-deelmenu -> "Zet op beginscherm") voor een
  eigen app-icoon, zonder dat er een echte app voor nodig is.

  Log: ${LOGFILE}
=====================================================================
EOF
}

###############################################################################
schrijf_versie_marker() {
    local marker_dir="/etc/pinas-addon-versies"
    mkdir -p "$marker_dir"
    chmod 755 "$marker_dir"
    local hash
    hash=$(sha256sum "$0" 2>/dev/null | awk '{print $1}')
    if [[ -n "$hash" ]]; then
        echo "$hash" > "${marker_dir}/dashboard.sha256"
        chmod 644 "${marker_dir}/dashboard.sha256"
    fi
}

main() {
    welkom
    check_root
    check_internet
    detect_network
    check_poort
    install_deps
    maak_wachtwoord
    maak_secret
    maak_app
    maak_service
    schrijf_versie_marker
    samenvatting
}
main "$@"
