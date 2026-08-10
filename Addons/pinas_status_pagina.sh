#!/usr/bin/env bash
###############################################################################
# PiNAS - Mobiele statuspagina installer
#
# Installeert een lichte, met wachtwoord beveiligde webpagina (Flask) die op
# de Pi ZELF draait (poort 8090) en een mobielvriendelijk overzicht toont van:
#   - Raspberry Pi hardware (model, RAM, temperatuur, uptime)
#   - Diensten (Samba, Nextcloud, FileBrowser, Cockpit, Externe HDD svc,
#     Pi-hole, ZeroTier, Vaultwarden, Printserver, PiNAS Dashboard)
#   - Schijfruimte van Opslag (SSD) en Backup (HDD)
#
# Thuis bereikbaar via het lokale IP van de Pi. Onderweg bereikbaar via het
# ZeroTier-IP van de Pi (als ZeroTier is geinstalleerd - zie pinas_zerotier.sh),
# op precies dezelfde manier als Nextcloud nu al onderweg werkt. Er is GEEN
# publieke internettoegang/poort-forwarding nodig of gewenst - dit blijft
# altijd binnen je eigen netwerk/VPN (Frans, 17 juli 2026: "ook buitenshuis
# zichtbaar als dat niet te moeilijk is" - ZeroTier hergebruiken is de
# eenvoudige, veilige route, zonder de router open te zetten).
#
# LET OP - wat hier NIET op staat: de Windows-pc-specifieke onderdelen uit het
# Status-scherm (geinstalleerde software op de PC, installatiebestanden,
# sync-vergelijking PC<->Pi). Die info is inherent PC-gebonden en kan niet
# vanaf de Pi zelf bepaald worden - zie daarvoor het Status-scherm in Pi NAS
# Menu op de pc. Wat de Pi wel zelf weet (services, hardware, schijfruimte)
# staat hier zo veel mogelijk hetzelfde als in dat Status-scherm.
#
# Wachtwoord: wordt bij de EERSTE installatie automatisch gegenereerd en
# eenmalig getoond (zelfde patroon als pinas_pihole.sh) - er wordt alleen een
# hash van opgeslagen, nooit het wachtwoord zelf. Opnieuw draaien van dit
# script wijzigt een bestaand wachtwoord niet (idempotent-vriendelijk, zelfde
# opzet als de andere add-ons).
#
# Gebruik:  sudo bash pinas_status_pagina.sh
###############################################################################

set -Eeuo pipefail

readonly VERSION="1.7"
readonly LOGFILE="/var/log/pinas_status_pagina.log"
readonly PORT="8090"
readonly APP_DIR="/opt/pinas-status"
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
  PiNAS - Mobiele statuspagina
  Versie ${VERSION}
=====================================================================

  Installeert een eigen, met wachtwoord beveiligde webpagina op de Pi
  (poort ${PORT}) met een mobielvriendelijk overzicht: Pi-hardware,
  diensten en schijfruimte - te bekijken vanaf je telefoon of tablet.

    Thuis     : http://<ip-van-de-pi>:${PORT}
    Onderweg  : via ZeroTier (als geinstalleerd) - zelfde manier als
                Nextcloud nu al onderweg werkt. GEEN publieke
                internettoegang of poort-forwarding nodig.

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
    [[ $EUID -eq 0 ]] || { error "Start met: sudo bash pinas_status_pagina.sh"; exit 1; }
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
            warn "Poort ${PORT} is al bezet door een eerdere statuspagina - wordt overgenomen."
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
    read -rp ">> Typ je eigen wachtwoord voor de statuspagina, of laat leeg voor automatisch gegenereerd: " EIGEN_WACHTWOORD
    if [[ -n "$EIGEN_WACHTWOORD" ]]; then
        NIEUW_WACHTWOORD="$EIGEN_WACHTWOORD"
        log "Eigen wachtwoord instellen voor de statuspagina..."
    else
        log "Toegangswachtwoord genereren voor de statuspagina..."
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
"""PiNAS - Mobiele statuspagina.

Kleine, met wachtwoord beveiligde webpagina die op de Pi zelf draait en
een mobielvriendelijk overzicht toont van de Pi (hardware, diensten,
schijfruimte). Alleen bereikbaar op het eigen netwerk of via ZeroTier -
geen publieke internettoegang, geen poort-forwarding nodig.

Draait als systemd-dienst pinas-status.service (gebruiker 'pi', zelfde
rechten als de bestaande SSH-statuscontroles vanaf Windows). Wordt op de
Pi neergezet door pinas_status_pagina.sh - hoort NIET in de Windows-
suite-boom, dit bestand leeft alleen op de Pi zelf (/opt/pinas-status).
"""
import base64
import os
import plistlib
import shutil
import subprocess
import time
from datetime import timedelta
from pathlib import Path

from flask import Flask, request, session, redirect, url_for, render_template_string, Response
from werkzeug.security import check_password_hash

APP_DIR = Path(__file__).resolve().parent
HASH_FILE = APP_DIR / "wachtwoord.hash"
SECRET_FILE = APP_DIR / "secret.key"
PORT = 8090

# 19 juli 2026: root-certificaat van Vaultwarden's eigen mini-CA (niet meer
# het losse servercertificaat van voorheen) - dit is het bestand dat je maar
# EENMALIG per apparaat hoeft te vertrouwen, zie pinas_vaultwarden.sh.
VAULTWARDEN_CA = Path("/etc/pinas-ca/ca.crt")
VAULTWARDEN_SERVER_CERT = Path("/etc/pinas-ca/server.crt")

app = Flask(__name__)
app.secret_key = SECRET_FILE.read_text().strip()
app.permanent_session_lifetime = timedelta(days=30)


# ── Icoon voor "Zet op beginscherm" (iOS + Android) ─────────────────────────
# PiNAS-logo, ingebakken als base64 zodat er geen los bestand nodig is op de
# Pi. iOS gebruikt apple-touch-icon; Android/Chrome gebruikt manifest.json
# (18 juli 2026, wens Frans).
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
        "name": "PiNAS Status",
        "short_name": "PiNAS",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#1565c0",
        "theme_color": "#1565c0",
        "icons": [
            {"src": "/icon.png", "sizes": "180x180", "type": "image/png"},
        ],
    }


# ── Status van de Pi zelf ophalen (draait er al op, geen SSH nodig) ─────────

def _run(cmd, timeout=6):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def _op_pad(commando):
    """Zoekt commando via PATH, met een fallback op bekende sbin-locaties.
    zerotier-cli staat meestal in /usr/sbin - bij een gewone gebruiker in
    een niet-interactieve SSH-sessie zit dat vaak NIET in $PATH, waardoor
    'command -v'/shutil.which ten onrechte 'afwezig' kan melden terwijl
    het programma wel degelijk geinstalleerd is (Frans, 17 juli 2026)."""
    if shutil.which(commando):
        return True
    for basis in ("/usr/sbin", "/usr/local/sbin", "/sbin", "/usr/local/bin"):
        if os.path.exists(os.path.join(basis, commando)):
            return True
    return False


def _actief(unit):
    return _run(["systemctl", "is-active", unit]) == "active"


def _ingeschakeld_of_actief(unit):
    return _actief(unit) or _run(["systemctl", "is-enabled", unit]) in ("enabled", "static")


def _commando_pad(commando):
    """Zoekt het volledige pad van een commando, met dezelfde sbin-fallback
    die hieronder al voor zerotier-cli werd gebruikt - de achtergronddienst
    draait met een beperkt PATH waar /usr/sbin vaak in ontbreekt."""
    pad = shutil.which(commando)
    if pad:
        return pad
    for basis in ("/usr/sbin", "/usr/local/sbin", "/sbin", "/usr/local/bin"):
        kandidaat = os.path.join(basis, commando)
        if os.path.exists(kandidaat):
            return kandidaat
    return commando  # laatste redmiddel: laat _run() het gewoon proberen


def _zerotier_cli_pad():
    return _commando_pad("zerotier-cli")


def _zerotier_ip():
    # 18 juli 2026 (Frans): echte
    # zerotier-cli geeft het IP in CIDR-notatie ("10.90.69.2/24", soms
    # meerdere adressen komma-gescheiden bij IPv4+IPv6) - de oude .count(".")
    # check pikte dat "/24" ten onrechte mee, waardoor er een kapot adres
    # ("10.90.69.2/24") werd teruggegeven i.p.v. een bruikbaar IP.
    #
    # 27 juli 2026 (Frans): pas nu aan het licht gekomen omdat de printer-
    # onderweg-functie hier echt van afhangt - zerotier-cli heeft root nodig
    # om zijn eigen authtoken.secret te lezen, en deze dienst draait als
    # gewone gebruiker 'pi' (zie systemd-unit), dus 'listnetworks' faalde
    # stilletjes en gaf altijd None terug. Zelfde 'sudo' als Frans zelf al
    # handmatig gebruikte (pi heeft NOPASSWD sudo).
    for regel in _run(["sudo", "-n", _zerotier_cli_pad(), "listnetworks"]).splitlines():
        delen = regel.split()
        if not delen:
            continue
        kandidaat = delen[-1].split(",")[0].split("/")[0]
        if kandidaat.count(".") == 3:
            return kandidaat
    return None


def _lan_ip():
    """Lokale LAN-IP van de Pi zelf (dezelfde 'ip route get'-truc als bij
    installatie in pinas_printer.sh), los van request.host - nodig omdat
    het AirPrint-profiel hieronder BEIDE adressen (thuis + onderweg)
    tegelijk moet bevatten, ongeacht vanaf welk netwerk je deze pagina nu
    toevallig bekijkt. Gebruikt _commando_pad() voor 'ip' omdat dit
    (net als zerotier-cli) vaak in /usr/sbin staat, buiten het beperkte
    PATH van de achtergronddienst (Frans, 27 juli 2026: 'Kon geen LAN- of
    ZeroTier-adres bepalen')."""
    for regel in _run([_commando_pad("ip"), "route", "get", "1.1.1.1"]).splitlines():
        delen = regel.split()
        if "src" in delen:
            return delen[delen.index("src") + 1]
    return None


def _cups_printer_namen():
    """Namen van de printers die daadwerkelijk in CUPS zijn toegevoegd
    (bijv. 'Epson_ET8550') - het AirPrint-profiel hieronder wordt hiermee
    dynamisch opgebouwd, geen handmatig/hardcoded printernaam nodig. Werkt
    ook meteen mee als je later een 2e printer toevoegt."""
    namen = []
    for regel in _run(["lpstat", "-p"]).splitlines():
        if regel.startswith("printer "):
            delen = regel.split()
            if len(delen) >= 2:
                namen.append(delen[1])
    return namen


def _vaultwarden_status():
    """Container-status + resterende geldigheid van het servercertificaat,
    zodat je op de statuspagina ruim van tevoren ziet aankomen wanneer het
    (jaarlijks, automatisch) vernieuwd wordt - geen verrassingen meer."""
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
                import datetime
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


def verzamel():
    # Adres waarmee DEZE bezoeker nu verbonden is (LAN-IP thuis, ZeroTier-IP
    # onderweg) - gebruiken we hieronder om per dienst automatisch de juiste
    # link te tonen, zonder dat de gebruiker zelf hoeft te kiezen tussen
    # "thuis" en "onderweg" (Frans, 18 juli 2026).
    host = request.host.split(":")[0]
    diensten = [
        ("Samba", _actief("smbd"), None, None),
        ("Nextcloud",
         (os.path.exists("/var/www/html/nextcloud/config/config.php")
          or os.path.exists("/var/www/nextcloud/config/config.php")), None,
         f"http://{host}/nextcloud"),
        ("FileBrowser", _ingeschakeld_of_actief("filebrowser") or shutil.which("filebrowser") is not None, None,
         f"http://{host}:8080"),
        ("Cockpit", _ingeschakeld_of_actief("cockpit") or _ingeschakeld_of_actief("cockpit.socket"), None,
         f"http://{host}:9090"),
        ("Externe HDD svc", _actief("seagate-web"), None, f"http://{host}:8765"),
    ]
    pihole_aanwezig = _op_pad("pihole")
    diensten.append(("Pi-hole", pihole_aanwezig, None if pihole_aanwezig else "Niet geinstalleerd",
                      f"http://{host}:8081/admin"))
    zt_aanwezig = _op_pad("zerotier-cli")
    zt_ip = _zerotier_ip() if zt_aanwezig else None
    diensten.append(("ZeroTier", zt_aanwezig, None if zt_aanwezig else "Niet geinstalleerd",
                      "https://my.zerotier.com" if zt_aanwezig else None))
    vw = _vaultwarden_status()
    diensten.append(("Vaultwarden", vw["actief"],
                      None if vw["actief"] else ("Gestopt" if vw["aanwezig"] else "Niet geinstalleerd"),
                      f"https://{host}:8443" if vw["actief"] else None))
    # Printserver (CUPS) - actief als de cups-service draait; beheer op poort 631
    # 31 juli 2026 (Frans): link moet direct naar de admin-pagina gaan, niet naar
    # de standaard CUPS-welkomstpagina (die geen beheeropties toont).
    cups_actief = _actief("cups") or _op_pad("cupsd")
    cups_printers = _cups_printer_namen() if cups_actief else []
    diensten.append(("Printserver", cups_actief,
                      None if cups_actief else "Niet geinstalleerd",
                      f"http://{host}:631/admin" if cups_actief else None))
    # PiNAS Dashboard toegevoegd (4 augustus 2026) - status + addons in 1
    # pagina, bereikbaar via deze zelfde statuspagina.
    dashboard_actief = _actief("pinas-dashboard")
    diensten.append(("PiNAS Dashboard", dashboard_actief,
                      None if dashboard_actief else "Niet geinstalleerd",
                      f"http://{host}:8095" if dashboard_actief else None))

    model = _run(["cat", "/proc/device-tree/model"]).split("\x00")[0].strip() or "onbekend"
    ram = _run(["bash", "-c", "free -h | awk '/Mem/{print $2}'"]) or "onbekend"
    temp_ruw = _run(["vcgencmd", "measure_temp"]) if shutil.which("vcgencmd") else ""
    temp = temp_ruw.replace("temp=", "").replace("'C", " C") if temp_ruw else "onbekend"
    uptime = _run(["uptime", "-p"]) or "onbekend"

    return {
        "diensten": diensten,
        "hardware": {"model": model, "ram": ram, "temp": temp, "uptime": uptime},
        "schijven": {"Opslag (SSD)": _schijf("/mnt/opslag"), "Backup (HDD)": _schijf("/mnt/backup")},
        "zt_ip": zt_ip,
        "vw_cert_beschikbaar": VAULTWARDEN_CA.exists(),
        "vw_dagen_geldig": vw["dagen_geldig"],
        "printer_profiel_beschikbaar": len(cups_printers) > 0,
        "printer_namen": ", ".join(cups_printers),
        "tijd": time.strftime("%d-%m-%Y %H:%M"),
    }


def ingelogd():
    return session.get("ingelogd") is True


LOGIN_HTML = """
<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PiNAS Status - inloggen</title>
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="icon" href="/icon.png">
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#1565c0">
<style>
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; background:#eef1f5; margin:0;
         display:flex; align-items:center; justify-content:center; height:100vh; }
  .kaart { background:#fff; border-radius:12px; padding:28px 24px; width:100%; max-width:340px;
           box-shadow:0 2px 12px rgba(0,0,0,.12); }
  h1 { font-size:20px; color:#0d3d75; margin:0 0 18px; text-align:center; }
  input[type=password] { width:100%; box-sizing:border-box; padding:12px; font-size:16px;
           border:1px solid #ccd3da; border-radius:8px; margin-bottom:14px; }
  button { width:100%; padding:12px; font-size:16px; font-weight:600; color:#fff; background:#1565c0;
           border:none; border-radius:8px; cursor:pointer; }
  .fout { color:#c62828; font-size:14px; text-align:center; margin-bottom:12px; }
</style>
</head>
<body>
  <form class="kaart" method="post">
    <h1>&#128274; PiNAS Status</h1>
    {% if fout %}<div class="fout">{{ fout }}</div>{% endif %}
    <input type="password" name="wachtwoord" placeholder="Wachtwoord" autofocus required>
    <button type="submit">Inloggen</button>
  </form>
</body>
</html>
"""

STATUS_HTML = """
<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PiNAS Status</title>
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="icon" href="/icon.png">
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#1565c0">
<style>
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; background:#eef1f5; margin:0; color:#26313d; }
  header { background:#1565c0; color:#fff; padding:16px 18px; display:flex;
           justify-content:space-between; align-items:center; }
  header h1 { font-size:18px; margin:0; }
  header a { color:#dbe9ff; font-size:13px; text-decoration:none; margin-left:14px; }
  main { padding:14px; max-width:480px; margin:0 auto; }
  .kaart { background:#fff; border-radius:10px; padding:14px 16px; margin-bottom:14px;
           box-shadow:0 1px 4px rgba(0,0,0,.08); }
  .kaart h2 { font-size:14px; color:#0d3d75; margin:0 0 10px; text-transform:uppercase; letter-spacing:.03em; }
  .rij { display:flex; justify-content:space-between; align-items:center; padding:6px 0;
         border-bottom:1px solid #f0f2f5; font-size:14px; }
  .rij:last-child { border-bottom:none; }
  .stip { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:8px; }
  .groen { background:#2e7d32; } .rood { background:#c62828; } .grijs { background:#9e9e9e; }
  .waarde { color:#5b6b7a; }
  .balk { background:#eceff2; border-radius:6px; height:6px; margin-top:6px; overflow:hidden; }
  .balk-vulling { background:#1565c0; height:100%; }
  footer { text-align:center; color:#8896a3; font-size:12px; padding:10px 0 24px; }
</style>
</head>
<body>
<header>
  <h1>&#128241; PiNAS Status</h1>
  <div><a href="{{ url_for('status') }}">&#8635; Vernieuwen</a><a href="{{ url_for('logout') }}">Uitloggen</a></div>
</header>
<main>

  <div class="kaart">
    <h2>Diensten</h2>
    {% for naam, ok, opmerking, url in data.diensten %}
    <div class="rij">
      <span><span class="stip {{ 'groen' if ok else ('grijs' if opmerking else 'rood') }}"></span>{{ naam }}</span>
      {% if ok and url %}
      <a class="waarde" href="{{ url }}" target="_blank" rel="noopener"
         style="color:#1565c0; text-decoration:none; font-weight:600;">Openen &rarr;</a>
      {% else %}
      <span class="waarde">{{ opmerking if opmerking else ('Actief' if ok else 'Inactief') }}</span>
      {% endif %}
    </div>
    {% endfor %}
  </div>

  <div class="kaart">
    <h2>Raspberry Pi - hardware</h2>
    <div class="rij"><span>Model</span><span class="waarde">{{ data.hardware.model }}</span></div>
    <div class="rij"><span>RAM geheugen</span><span class="waarde">{{ data.hardware.ram }}</span></div>
    <div class="rij"><span>CPU temperatuur</span><span class="waarde">{{ data.hardware.temp }}</span></div>
    <div class="rij"><span>Uptime</span><span class="waarde">{{ data.hardware.uptime }}</span></div>
  </div>

  <div class="kaart">
    <h2>Schijven</h2>
    {% for naam, info in data.schijven.items() %}
      {% if info %}
      <div class="rij"><span>{{ naam }}</span><span class="waarde">{{ info.vrij }} vrij van {{ info.grootte }}</span></div>
      <div class="balk"><div class="balk-vulling" style="width:{{ info.percentage }};"></div></div>
      {% else %}
      <div class="rij"><span>{{ naam }}</span><span class="waarde"><span class="stip rood"></span>niet gekoppeld</span></div>
      {% endif %}
    {% endfor %}
  </div>

  <div class="kaart">
    <h2>Bereikbaarheid</h2>
    <div class="rij"><span>Thuis (LAN)</span><span class="waarde">{{ request.host.split(':')[0] }}</span></div>
    {% if data.zt_ip %}
    <div class="rij"><span>Onderweg (ZeroTier)</span>
      <a class="waarde" href="http://{{ data.zt_ip }}:8090" target="_blank" rel="noopener"
         style="color:#1565c0; text-decoration:none; font-weight:600;">{{ data.zt_ip }}:8090 &rarr;</a>
    </div>
    {% endif %}
  </div>

  {% if data.vw_cert_beschikbaar %}
  <div class="kaart">
    <details>
      <summary style="cursor:pointer; font-size:14px; color:#0d3d75; font-weight:600;">Vaultwarden - root-certificaat</summary>
      <div style="margin-top:10px; font-size:13px; color:#5b6b7a; line-height:1.5;">
        Dit certificaat hoef je maar <b>eenmalig per apparaat</b> te vertrouwen -
        het onderliggende servercertificaat wordt daarna automatisch elk jaar
        vernieuwd, zonder dat je dit opnieuw hoeft te doen.
        {% if data.vw_dagen_geldig is not none %}
        <br>Huidig servercertificaat nog geldig: <b>{{ data.vw_dagen_geldig }} dagen</b>.
        {% endif %}
      </div>
      <a href="{{ url_for('vaultwarden_ca') }}" download="pinas-ca.crt"
         style="display:inline-block; margin-top:10px; padding:10px 14px; background:#1565c0;
                color:#fff; text-decoration:none; border-radius:8px; font-weight:600; font-size:13px;">
        &#8681; Root-certificaat downloaden
      </a>
    </details>
  </div>
  {% endif %}

  {% if data.printer_profiel_beschikbaar %}
  <div class="kaart">
    <details>
      <summary style="cursor:pointer; font-size:14px; color:#0d3d75; font-weight:600;">Printserver - AirPrint (thuis en onderweg)</summary>
      <div style="margin-top:10px; font-size:13px; color:#5b6b7a; line-height:1.5;">
        Thuis verschijnt de printer ({{ data.printer_namen }}) vanzelf in het
        print-menu - geen verdere actie nodig.
        <br><br>
        <b>Onderweg zonder wifi, via ZeroTier: bevestigd werkend</b> (27
        juli 2026) - MITS je deze twee dingen EENMALIG, VOORAF, THUIS hebt
        gedaan:
        <ol style="margin:6px 0 0 18px; padding:0;">
          <li>Een 2e wachtrij in CUPS voor dezelfde printer, met een naam
          die eindigt op <code>_onderweg</code> (bijv.
          <code>Epson_ET8550_onderweg</code>).</li>
          <li>De gratis <b>Epson Smart Panel</b>-app geinstalleerd en de
          printer er EEN KEER mee gekoppeld (via Wi-Fi Direct/QR-code op
          het display van de printer, terwijl je gewoon thuis op wifi
          zit).</li>
        </ol>
        <br>
        Zonder de Smart Panel-koppeling bleek printen zonder wifi
        consequent te mislukken ("Geen AirPrint-printers gevonden"), ook
        met een verder correct profiel - de koppeling lijkt iets in iOS te
        "ontgrendelen". De precieze technische reden hiervoor is niet met
        zekerheid vastgesteld, alleen het herhaalde verband tussen wel/niet
        gekoppeld en wel/niet werkend printen.
        <br><br>
        Download het profiel hieronder rechtstreeks in Safari op je
        iPhone/iPad (Instellingen -> Profiel gedownload -> Installeren;
        de gele "Niet geverifieerd"-waarschuwing is normaal). Werkt het
        onverhoopt toch niet, dan is <b>Epson Connect</b> (Email Print of
        Remote Print via de Epson iPrint-app) het alternatief - Epson's
        eigen clouddienst, werkt via gewoon internet, los van deze suite.
      </div>
      <a href="{{ url_for('printer_airprint_profiel') }}"
         style="display:inline-block; margin-top:10px; padding:10px 14px; background:#1565c0;
                color:#fff; text-decoration:none; border-radius:8px; font-weight:600; font-size:13px;">
        &#8681; AirPrint-profiel downloaden
      </a>
    </details>
  </div>
  {% endif %}

  <footer>Bijgewerkt: {{ data.tijd }}</footer>
</main>
</body>
</html>
"""


@app.route("/login", methods=["GET", "POST"])
def login():
    fout = None
    if request.method == "POST":
        ingevoerd = request.form.get("wachtwoord", "")
        try:
            juist_hash = HASH_FILE.read_text().strip()
        except FileNotFoundError:
            juist_hash = None
        if juist_hash and check_password_hash(juist_hash, ingevoerd):
            session.permanent = True
            session["ingelogd"] = True
            return redirect(url_for("status"))
        time.sleep(1.5)  # simpele afremming tegen snel gokken
        fout = "Onjuist wachtwoord."
    return render_template_string(LOGIN_HTML, fout=fout)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def status():
    if not ingelogd():
        return redirect(url_for("login"))
    return Response(render_template_string(STATUS_HTML, data=verzamel()),
                     headers={"Cache-Control": "no-store"})


def _airprint_entries_voor(naam, lan_ip, zt_ip):
    """Kiest per printernaam BEWUST een enkel adres, in plaats van beide
    tegelijk onder dezelfde naam - dat bleek in de praktijk niet
    betrouwbaar te werken op iOS (Frans, 26 juli 2026: de printer
    verscheen wel in de lijst, maar printen zelf lukte niet zodra wifi
    uit stond - waarschijnlijk omdat iOS van 2 adressen onder 1 naam er
    intern maar 1 onthoudt, niet allebei als terugval probeert).
    Voeg in CUPS een 2e wachtrij toe voor dezelfde fysieke printer met een
    naam die eindigt op '_onderweg' of '_zerotier' (bijv.
    Epson_ET8550_onderweg) - die koppelt aan het ZeroTier-adres. Elke
    andere naam krijgt het lokale (thuis-)adres."""
    is_onderweg = naam.lower().endswith(("_onderweg", "_zerotier"))
    ip = zt_ip if is_onderweg else lan_ip
    if not ip:
        return []
    return [{"IPAddress": ip, "Port": 631, "ResourcePath": f"printers/{naam}"}]


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


# Vaste PayloadUUID's (niet elke keer opnieuw gegenereerd!) - dit is de
# "identiteit" van het profiel voor iOS. Blijven deze twee waarden gelijk,
# dan VERVANGT een latere her-download (bijv. na het toevoegen van een 2e
# printer) het bestaande profiel automatisch, in plaats van een dubbel
# profiel aan te maken (26 juli 2026).
_AIRPRINT_PROFIEL_UUID = "0BE828EB-E31A-4C19-9DBA-5FED525FDD99"
_AIRPRINT_PAYLOAD_UUID = "9447D4BE-1271-4C16-9CD2-A3D54CCC40EE"


@app.route("/pinas-printer-airprint.mobileconfig")
def printer_airprint_profiel():
    # Cache-Control: no-store hieronder overal expliciet - Safari op iOS kan
    # anders een oude foutmelding van deze pagina blijven tonen na een
    # scriptupdate, ook al draait de dienst allang de nieuwe versie
    # (Frans, 27 juli 2026: zag dezelfde foutmelding na een bevestigde
    # herinstallatie/herstart).
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
        raise SystemExit("Wachtwoord/sessiesleutel ontbreekt - draai eerst pinas_status_pagina.sh")
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
APP_EOF
    success "Webapp weggeschreven."
}

###############################################################################
# 4. systemd-dienst
###############################################################################
maak_service() {
    log "Achtergronddienst instellen (systemd)..."
    cat > /etc/systemd/system/pinas-status.service << 'SERVICE_EOF'
[Unit]
Description=PiNAS mobiele statuspagina
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 /opt/pinas-status/app.py
WorkingDirectory=/opt/pinas-status
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
    systemctl enable --now pinas-status.service
    systemctl restart pinas-status.service
    sleep 2
    if systemctl is-active --quiet pinas-status; then
        success "Statuspagina draait (poort ${PORT})."
    else
        error "Statuspagina start niet. Check: journalctl -u pinas-status"; exit 1
    fi
}

###############################################################################
# 5. Samenvatting
###############################################################################
samenvatting() {
    local zt_ip
    # zelfde CIDR-fix als hierboven bij _zerotier_ip()
    zt_ip=$(command -v zerotier-cli >/dev/null 2>&1 && zerotier-cli listnetworks 2>/dev/null \
            | awk '{print $NF}' | cut -d',' -f1 | cut -d'/' -f1 \
            | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | head -1 || true)
cat <<EOF

=====================================================================
  KLAAR - Mobiele statuspagina draait
=====================================================================

  Thuis (LAN)   : http://${PI_IP}:${PORT}
EOF
if [[ -n "${zt_ip:-}" ]]; then
cat <<EOF
  Onderweg (ZT) : http://${zt_ip}:${PORT}   (ZeroTier moet aanstaan op je telefoon)
EOF
else
cat <<EOF
  Onderweg      : installeer eerst ZeroTier (pinas_zerotier.sh) voor
                  toegang van onderweg - je krijgt dan een eigen IP
                  te zien via: sudo zerotier-cli listnetworks
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
    # Zie pinas_printer.sh voor de volledige uitleg.
    local marker_dir="/etc/pinas-addon-versies"
    mkdir -p "$marker_dir"
    chmod 755 "$marker_dir"
    local hash
    hash=$(sha256sum "$0" 2>/dev/null | awk '{print $1}')
    if [[ -n "$hash" ]]; then
        echo "$hash" > "${marker_dir}/statuspagina.sha256"
        chmod 644 "${marker_dir}/statuspagina.sha256"
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
