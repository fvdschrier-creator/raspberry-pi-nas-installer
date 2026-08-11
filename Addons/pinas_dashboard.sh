#!/usr/bin/env bash
###############################################################################
# PiNAS - Dashboard installer
#
# Installeert een eigen, met wachtwoord beveiligde webpagina op de Pi
# (poort 8095) die het statusoverzicht (hardware, schijfruimte, diensten -
# zelfde als de mobiele statuspagina) EN het addon-overzicht (installeren/
# openen, zelfde als Addons Beheer) samenbrengt in 1 pagina - bereikbaar
# vanaf elk apparaat, thuis en via ZeroTier ook onderweg.
#
# Zevende add-on naast Nextcloud, Pi-hole, ZeroTier, Vaultwarden, Mobiele
# statuspagina en Printserver. Zelfde installatiepatroon als die 6:
# wachtwoord eenmalig getoond, idempotent (opnieuw draaien wijzigt een
# bestaand wachtwoord niet), eigen systemd-dienst, eigen versie-afdruk
# voor Addons Beheer's "Bijgewerkt"-check.
#
# Gebruik:  sudo bash pinas_dashboard.sh
###############################################################################

set -Eeuo pipefail

readonly VERSION="1.0"
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
  (poort ${PORT}) die status EN addons samenbrengt in 1 overzicht:
    - Raspberry Pi hardware, schijfruimte, diensten (zoals de mobiele
      statuspagina)
    - Addon-overzicht met openen/installeren (zoals Addons Beheer)

    Thuis     : http://<ip-van-de-pi>:${PORT}
    Onderweg  : via ZeroTier (als geinstalleerd)

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
onderweg), net als de mobiele statuspagina.

Hergebruikt bewust dezelfde detectielogica als pinas_status_pagina.sh en
pinas_addons_beheer.pyw - geen nieuwe checks verzonnen.

Draait als systemd-dienst pinas-dashboard.service (gebruiker pi), wordt
neergezet door pinas_dashboard.sh. Hoort NIET in de Windows-suite-boom,
dit bestand leeft alleen op de Pi zelf (/opt/pinas-dashboard).
"""
import os
import shutil
import subprocess
import time
from datetime import timedelta
from pathlib import Path

from flask import Flask, request, session, redirect, url_for, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash

APP_DIR = Path(__file__).resolve().parent
HASH_FILE = APP_DIR / "wachtwoord.hash"
SECRET_FILE = APP_DIR / "secret.key"
PORT = 8095
# Waar addon-scripts terechtkomen zodra ze via Addons Beheer of handmatig
# via SSH zijn geupload (zie _draai_script_op_pi in pinas_addons_beheer.pyw).
ADDON_SCRIPT_DIR = Path("/home/pi")

app = Flask(__name__)
app.secret_key = SECRET_FILE.read_text().strip()
app.permanent_session_lifetime = timedelta(days=30)


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
    namen = _run(["docker", "ps", "-a", "--format", "{{.Names}}"]).splitlines()
    aanwezig = "vaultwarden" in namen
    actief = False
    if aanwezig:
        actieve_namen = _run(["docker", "ps", "--format", "{{.Names}}"]).splitlines()
        actief = "vaultwarden" in actieve_namen
    return {"aanwezig": aanwezig, "actief": actief}


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
    "statuspagina": {"naam": "Mobiele statuspagina", "script": "pinas_status_pagina.sh",
                      "poort_pad": None, "poort": 8090, "https": False},
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
    if key == "statuspagina":
        return "actief" if _actief("pinas-status") else "afwezig"
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
    diensten.append(("Printserver", cups_actief, "cups" if cups_actief else None,
                      f"http://{host}:631/admin" if cups_actief else None))
    statuspagina_actief = _actief("pinas-status")
    diensten.append(("PiNAS Status (mobiel)", statuspagina_actief, "pinas-status",
                      f"http://{host}:8090" if statuspagina_actief else None))
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
        "tijd": time.strftime("%d-%m-%Y %H:%M"),
    }


def ingelogd():
    return session.get("ingelogd") is True


LOGIN_HTML = """
<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PiNAS Dashboard</title>
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
APP_EOF
    success "Webapp weggeschreven."
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
