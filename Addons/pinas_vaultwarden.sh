#!/usr/bin/env bash
###############################################################################
# PiNAS - Vaultwarden (wachtwoordkluis) installer
#
# Installeert NAAST een bestaande PiNAS, zonder iets te breken:
#   - Vaultwarden (Bitwarden-compatibel, eigen wachtwoordkluis) in Docker
#   - nginx als reverse proxy met TLS ervoor
#
# CERTIFICAAT - 19 juli 2026, herbouwd n.a.v. het iOS-connectieprobleem:
# in plaats van 1 los zelf-ondertekend certificaat (dat door Apple's "App
# Transport Security" geweigerd werd in de Bitwarden-APP, ook al werd het
# handmatig vertrouwd - Safari accepteerde het wel, de app niet) maakt dit
# script nu een EIGEN ROOT-CERTIFICAAT (kleine eigen "certificaatinstantie",
# alleen voor deze Pi) en daarmee een kort-geldig servercertificaat dat aan
# ALLE ATS-eisen voldoet:
#   - hooguit 397 dagen geldig (ATS-limiet: 398)
#   - 2048-bit RSA, SHA-256
#   - correcte keyUsage/extendedKeyUsage-velden
#   - SAN met zowel het LAN-IP als (indien aanwezig) het ZeroTier-IP
# Het ROOT-certificaat vertrouw je één keer per apparaat (PC/iPhone/Android).
# Het SERVER-certificaat wordt daarna automatisch elk jaar vernieuwd zonder
# dat er ooit opnieuw vertrouwd hoeft te worden - zie vernieuw_certificaat.sh.
#
# Gebruik:  sudo bash pinas_vaultwarden.sh
###############################################################################

set -Eeuo pipefail

readonly VERSION="2.0"
readonly LOGFILE="/var/log/pinas_vaultwarden.log"
readonly CA_DIR="/etc/pinas-ca"
readonly DATA_DIR="/opt/pinas-vault/data"
readonly HTTPS_POORT="8443"
readonly INTERN_POORT="8082"   # alleen op 127.0.0.1, niet van buiten bereikbaar

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
  PiNAS - Vaultwarden (wachtwoordkluis)
  Versie ${VERSION}
=====================================================================

  Dit script installeert, NAAST je bestaande NAS:

    1. Vaultwarden      - eigen wachtwoordkluis (Bitwarden-compatibel)
    2. Een eigen root-certificaat + geldig servercertificaat, zodat de
       Bitwarden-apps (niet alleen de browser) veilig verbinden.

  Bereikbaar op: https://<ip-van-de-pi>:${HTTPS_POORT}

  ---------------------------------------------------------------
  BELANGRIJK OM VOORAF TE WETEN:
  ---------------------------------------------------------------
  - Het root-certificaat moet je EENMALIG vertrouwen op elk apparaat
    (PC, iPhone, Android) - zie de "Certificaat vertrouwen"-knop en de
    Suite Handleiding voor telefoons.
  - Het beheerderstoken (voor het /admin-paneel) wordt aan het eind
    EENMALIG getoond - schrijf het op.
  - Duurt ongeveer 3-5 minuten.

  Log van deze installatie: ${LOGFILE}

=====================================================================
EOF
pauze
}

check_root() {
    [[ $EUID -eq 0 ]] || { error "Start met: sudo bash pinas_vaultwarden.sh"; exit 1; }
    success "Rootrechten OK."
}

check_internet() {
    log "Internet controleren..."
    curl -fsSL --connect-timeout 10 https://github.com >/dev/null \
        && success "Internet OK." || { error "Geen internet."; exit 1; }
}

check_docker() {
    log "Docker controleren..."
    command -v docker >/dev/null 2>&1 || { error "Docker niet gevonden. Installeer eerst Docker (wordt door deze suite nooit zelf verwijderd, dus als het er eerder stond hoort het er nog te staan)."; exit 1; }
    success "Docker aanwezig."
}

detect_network() {
    log "Netwerk bepalen..."
    PI_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')
    [[ -n "${PI_IP:-}" ]] || { error "Kan IP niet bepalen."; exit 1; }
    success "LAN-IP van deze Pi: $PI_IP"

    ZT_IP=""
    if command -v zerotier-cli >/dev/null 2>&1 || [[ -x /usr/sbin/zerotier-cli ]]; then
        ZT_IP=$(zerotier-cli listnetworks 2>/dev/null | awk '{print $NF}' | cut -d',' -f1 | cut -d'/' -f1 \
                | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | head -1 || true)
        if [[ -n "$ZT_IP" ]]; then
            success "ZeroTier-IP gevonden, wordt meegenomen in het certificaat: $ZT_IP"
        else
            warn "ZeroTier is geinstalleerd maar heeft nog geen IP - certificaat dekt dan alleen het LAN-IP. Herinstalleer dit script later als je onderweg toegang wilt."
        fi
    else
        warn "ZeroTier niet geinstalleerd - certificaat dekt alleen het LAN-IP (thuis-toegang)."
    fi
}

###############################################################################
# 1. Root-certificaat (eenmalig - blijft bestaan bij herinstallatie)
###############################################################################
maak_root_ca() {
    mkdir -p "$CA_DIR"
    # De map zelf moet doorzoekbaar zijn voor de "pi"-gebruiker (chmod 755,
    # niet 700) - anders kan scp/de statuspagina (die als "pi" draaien) het
    # publieke ca.crt niet ophalen, ook al is het bestand zelf leesbaar.
    # De PRIVATE sleutels blijven apart op chmod 600 (alleen root), dus dit
    # is veilig: alleen de map-doorgang wordt opengezet, geen sleutels
    # (19 juli 2026, bug gevonden: "scp: No such file or directory" omdat
    # pi de map niet in kon).
    chmod 755 "$CA_DIR"
    if [[ -f "${CA_DIR}/ca.crt" && -f "${CA_DIR}/ca.key" ]]; then
        warn "Root-certificaat bestaat al - wordt hergebruikt (dus geen nieuwe vertrouwen-stap nodig op je apparaten)."
        chmod 600 "${CA_DIR}/ca.key"
        chmod 644 "${CA_DIR}/ca.crt"
        return
    fi
    log "Eigen root-certificaat aanmaken (eenmalig, geldig 10 jaar)..."
    openssl genrsa -out "${CA_DIR}/ca.key" 4096
    openssl req -x509 -new -nodes -key "${CA_DIR}/ca.key" -sha256 -days 3650 \
        -subj "/CN=PiNAS Lokale CA" -out "${CA_DIR}/ca.crt"
    chmod 600 "${CA_DIR}/ca.key"
    chmod 644 "${CA_DIR}/ca.crt"
    success "Root-certificaat aangemaakt: ${CA_DIR}/ca.crt"
}

###############################################################################
# 2. Servercertificaat (ATS-compliant: max 397 dagen, 2048-bit, SHA-256)
###############################################################################
maak_server_cert() {
    log "Servercertificaat aanmaken (max. 397 dagen geldig, voldoet aan Apple ATS-eisen)..."

    {
        echo "basicConstraints=CA:FALSE"
        echo "keyUsage=digitalSignature,keyEncipherment"
        echo "extendedKeyUsage=serverAuth"
        echo "subjectAltName=@alt_names"
        echo
        echo "[alt_names]"
        echo "IP.1 = ${PI_IP}"
        [[ -n "$ZT_IP" ]] && echo "IP.2 = ${ZT_IP}"
    } > "${CA_DIR}/server_ext.cnf"

    openssl genrsa -out "${CA_DIR}/server.key" 2048
    openssl req -new -key "${CA_DIR}/server.key" -out "${CA_DIR}/server.csr" -subj "/CN=${PI_IP}"
    openssl x509 -req -in "${CA_DIR}/server.csr" \
        -CA "${CA_DIR}/ca.crt" -CAkey "${CA_DIR}/ca.key" -CAcreateserial \
        -out "${CA_DIR}/server.crt" -days 397 -sha256 -extfile "${CA_DIR}/server_ext.cnf"
    rm -f "${CA_DIR}/server.csr"
    chmod 600 "${CA_DIR}/server.key"
    chmod 644 "${CA_DIR}/server.crt"
    success "Servercertificaat aangemaakt (geldig tot: $(openssl x509 -enddate -noout -in "${CA_DIR}/server.crt" | cut -d= -f2))."
}

###############################################################################
# 3. Automatische vernieuwing (cron, geen herhaalde vertrouwen-stap nodig)
###############################################################################
maak_vernieuw_taak() {
    log "Automatische jaarlijkse vernieuwing instellen..."
    cat > "${CA_DIR}/vernieuw_certificaat.sh" << VERNIEUW_EOF
#!/usr/bin/env bash
# Vernieuwt alleen het SERVERcertificaat (met dezelfde, al vertrouwde
# root-CA) als het over minder dan 30 dagen verloopt. Geen enkele actie
# nodig op je apparaten - het root-certificaat blijft hetzelfde.
set -Eeuo pipefail
CA_DIR="${CA_DIR}"
if openssl x509 -checkend \$((30*86400)) -noout -in "\${CA_DIR}/server.crt" >/dev/null 2>&1; then
    exit 0
fi
openssl genrsa -out "\${CA_DIR}/server.key" 2048
openssl req -new -key "\${CA_DIR}/server.key" -out "\${CA_DIR}/server.csr" -subj "/CN=${PI_IP}"
openssl x509 -req -in "\${CA_DIR}/server.csr" \\
    -CA "\${CA_DIR}/ca.crt" -CAkey "\${CA_DIR}/ca.key" -CAcreateserial \\
    -out "\${CA_DIR}/server.crt" -days 397 -sha256 -extfile "\${CA_DIR}/server_ext.cnf"
rm -f "\${CA_DIR}/server.csr"
chmod 600 "\${CA_DIR}/server.key"; chmod 644 "\${CA_DIR}/server.crt"
systemctl reload nginx 2>/dev/null || true
VERNIEUW_EOF
    chmod 700 "${CA_DIR}/vernieuw_certificaat.sh"
    # crontab -l geeft foutcode 1 als er nog helemaal geen crontab bestaat
    # (nieuwe Pi) - met "|| true" laten we dat niet de installatie
    # afbreken. En dit is root's EIGEN crontab (via "crontab -", niet
    # /etc/crontab), dus zonder gebruikersveld in de regel zelf - "root "
    # ervoor zou cron laten proberen een programma genaamd 'root' te
    # starten (19 juli 2026, bug gevonden na een mislukte installatie).
    ( crontab -l 2>/dev/null | grep -v "vernieuw_certificaat.sh" || true; \
      echo "0 3 * * 0 ${CA_DIR}/vernieuw_certificaat.sh" ) | crontab -
    success "Vernieuwing ingepland (elke zondag 03:00, vernieuwt alleen als er <30 dagen resttijd is)."
}

###############################################################################
# 4. Vaultwarden zelf (Docker)
###############################################################################
install_vaultwarden() {
    mkdir -p "$DATA_DIR"
    if docker ps -a --format '{{.Names}}' | grep -qx vaultwarden; then
        warn "Vaultwarden-container bestaat al - wordt herstart met de huidige instellingen."
        docker rm -f vaultwarden >/dev/null 2>&1 || true
    fi

    log "Beheerderstoken genereren..."
    ADMIN_TOKEN=$(openssl rand -base64 32)

    log "Nieuwste Vaultwarden-image ophalen..."
    # 10 augustus 2026: zonder expliciete "docker pull" hergebruikt
    # "docker run" gewoon de al lokaal aanwezige "latest"-image, ook als
    # die maanden oud is - terwijl de Bitwarden-browserextensie zichzelf
    # via de Chrome Web Store steeds automatisch bijwerkt. Dat gat tussen
    # een oude server-versie en een nieuwe extensie-versie gaf een
    # "eeuwig laden"-crash in de extensie (WASM-decodeerfout), terwijl de
    # webkluis wel gewoon werkte. Vanaf nu haalt elke (her)installatie
    # dus altijd eerst de nieuwste image op.
    docker pull vaultwarden/server:latest
    success "Nieuwste image binnengehaald."

    log "Vaultwarden-container starten..."
    # SIGNUPS_ALLOWED=true: deze server is toch nooit vanaf het open
    # internet bereikbaar (alleen LAN + ZeroTier-VPN), dus het risico van
    # open registratie is hier laag - en het voorkomt gedoe bij een eerste
    # account aanmaken. SIGNUPS_VERIFY=false is VERPLICHT zonder eigen
    # e-mailserver (SMTP): zonder deze regel probeert de nieuwste
    # Bitwarden-app een verificatiemail-stap te doen die nooit aankomt,
    # met "Token is invalid" als gevolg (19 juli 2026, bug gevonden na een
    # mislukte account-aanmaak-poging).
    docker run -d --name vaultwarden --restart unless-stopped \
        -e WEBSOCKET_ENABLED=true \
        -e SIGNUPS_ALLOWED=true \
        -e SIGNUPS_VERIFY=false \
        -e ADMIN_TOKEN="${ADMIN_TOKEN}" \
        -v "${DATA_DIR}:/data" \
        -p "127.0.0.1:${INTERN_POORT}:80" \
        vaultwarden/server:latest
    success "Vaultwarden-container draait (alleen lokaal bereikbaar, nginx regelt de buitenkant)."
}

###############################################################################
# 5. nginx reverse proxy met TLS
###############################################################################
install_nginx() {
    if ! command -v nginx >/dev/null 2>&1; then
        log "nginx installeren..."
        apt-get update -qq
        apt-get install -y nginx
        success "nginx geinstalleerd."
    else
        success "nginx al aanwezig."
    fi
}

configureer_nginx() {
    log "nginx configureren voor Vaultwarden (poort ${HTTPS_POORT})..."
    cat > /etc/nginx/sites-available/vaultwarden.conf << NGINX_EOF
server {
    listen ${HTTPS_POORT} ssl;
    listen [::]:${HTTPS_POORT} ssl;
    server_name _;

    ssl_certificate     ${CA_DIR}/server.crt;
    ssl_certificate_key ${CA_DIR}/server.key;
    ssl_protocols TLSv1.2 TLSv1.3;

    client_max_body_size 128M;

    location / {
        proxy_pass http://127.0.0.1:${INTERN_POORT};
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /notifications/hub {
        proxy_pass http://127.0.0.1:${INTERN_POORT}/notifications/hub;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
    }
}
NGINX_EOF
    ln -sf /etc/nginx/sites-available/vaultwarden.conf /etc/nginx/sites-enabled/vaultwarden.conf

    # nginx's standaard site luistert op poort 80 - dat botst met Apache
    # (Nextcloud draait daar al op). Onze Vaultwarden-site gebruikt alleen
    # 8443, dus de standaard site kan gewoon weg (19 juli 2026, bug
    # gevonden na een mislukte installatie: "port 80 is already in use").
    rm -f /etc/nginx/sites-enabled/default

    nginx -t
    systemctl restart nginx
    sleep 1
    if ! systemctl is-active --quiet nginx; then
        error "nginx start niet. Check: sudo systemctl status nginx --no-pager"
        journalctl -u nginx --no-pager -n 20 || true
        exit 1
    fi
    success "nginx draait met het nieuwe certificaat."
}

schrijf_versie_marker() {
    # Zie pinas_printer.sh voor de volledige uitleg.
    local marker_dir="/etc/pinas-addon-versies"
    mkdir -p "$marker_dir"
    chmod 755 "$marker_dir"
    local hash
    hash=$(sha256sum "$0" 2>/dev/null | awk '{print $1}')
    if [[ -n "$hash" ]]; then
        echo "$hash" > "${marker_dir}/vaultwarden.sha256"
        chmod 644 "${marker_dir}/vaultwarden.sha256"
    fi
}

###############################################################################
# 6. Samenvatting
###############################################################################
samenvatting() {
cat <<EOF

=====================================================================
  KLAAR - Vaultwarden draait
=====================================================================

  Open Vaultwarden op   : https://${PI_IP}:${HTTPS_POORT}
EOF
if [[ -n "$ZT_IP" ]]; then
cat <<EOF
  Onderweg (ZeroTier)   : https://${ZT_IP}:${HTTPS_POORT}
EOF
fi
cat <<EOF
  Beheerderspaneel      : https://${PI_IP}:${HTTPS_POORT}/admin
  Beheerderstoken       : ${ADMIN_TOKEN}
  (schrijf dit token op - het wordt niet opnieuw getoond)

  ---------------------------------------------------------------
  VOLGENDE STAP - certificaat vertrouwen:
  ---------------------------------------------------------------
  Gebruik de knop "Certificaat vertrouwen" in Addons Beheer voor
  Windows. Voor iPhone/Android: zie de Suite Handleiding - het
  root-certificaat is te downloaden via de mobiele statuspagina.

  Log: ${LOGFILE}
=====================================================================
EOF
}

###############################################################################
main() {
    welkom
    check_root
    check_internet
    check_docker
    detect_network
    maak_root_ca
    maak_server_cert
    maak_vernieuw_taak
    install_vaultwarden
    install_nginx
    configureer_nginx
    schrijf_versie_marker
    samenvatting
}
main "$@"
