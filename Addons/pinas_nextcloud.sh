#!/usr/bin/env bash
###############################################################################
# PiNAS - Nextcloud installer
#
# Installeert NAAST een bestaande PiNAS, zonder iets te breken:
#   - Apache + MariaDB + PHP     (Nextcloud's vereisten)
#   - Nextcloud zelf             bereikbaar via http://<pi-ip>/nextcloud
#
# Was voorheen ONDERDEEL van nas_installer.py's GUI ("Methode B"), vast
# gekoppeld aan Tkinter-invoervelden - geextraheerd tot een zelfstandig
# script, zelfde stijl als de andere add-ons (Pi-hole, ZeroTier, Vault).
#
# Data komt op de Opslag-schijf (/mnt/opslag/nextcloud-data), niet op de
# SD-kaart - overleeft dus een systeem-herinstallatie.
#
# Gebruik:  sudo bash pinas_nextcloud.sh
###############################################################################

set -Eeuo pipefail

readonly VERSION="1.0"
readonly LOGFILE="/var/log/pinas_nextcloud.log"
readonly MOUNTPOINT="/mnt/opslag"
readonly NC_DATA="${MOUNTPOINT}/nextcloud-data"

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
  PiNAS - Nextcloud
  Versie ${VERSION}
=====================================================================

  Dit script installeert, NAAST je bestaande NAS:

    1. Apache + MariaDB + PHP  - Nextcloud's vereisten
    2. Nextcloud zelf          - je eigen cloudopslag

  Bereikbaar op: http://<ip-van-de-pi>/nextcloud
  Data komt op de Opslag-schijf (${NC_DATA}), niet op de SD-kaart.

  ---------------------------------------------------------------
  BELANGRIJK OM VOORAF TE WETEN:
  ---------------------------------------------------------------
  - Je kiest zelf een gebruikersnaam voor de Nextcloud-beheerder.
  - Het beheerderswachtwoord wordt automatisch gegenereerd en aan
    het eind EENMALIG getoond - schrijf het op.
  - Duurt ongeveer 5-10 minuten.

  Log van deze installatie: ${LOGFILE}

=====================================================================
EOF
pauze
}

check_root() {
    [[ $EUID -eq 0 ]] || { error "Start met: sudo bash pinas_nextcloud.sh"; exit 1; }
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

check_mountpoint() {
    log "Opslag-schijf controleren (${MOUNTPOINT})..."
    if mountpoint -q "$MOUNTPOINT" 2>/dev/null || [[ -d "$MOUNTPOINT" ]]; then
        success "Opslag gevonden op ${MOUNTPOINT}."
    else
        error "Opslag-schijf niet gevonden op ${MOUNTPOINT}. Zorg dat de NAS-basisinstallatie eerst klaar is."
        exit 1
    fi
}

vraag_gebruikersnaam() {
    echo
    read -rp ">> Gewenste Nextcloud-beheerdersnaam [admin]: " NC_ADMIN
    NC_ADMIN=${NC_ADMIN:-admin}
    success "Beheerdersnaam: ${NC_ADMIN}"
}

###############################################################################
# 1. Vereisten (Apache, MariaDB, PHP)
###############################################################################
install_vereisten() {
    log "Vereisten installeren (Apache, MariaDB, PHP)..."
    apt-get update -qq
    apt-get install -y apache2 mariadb-server php php-mysql php-gd \
        php-curl php-zip php-xml php-mbstring php-intl php-imagick php-bcmath php-gmp \
        libapache2-mod-php unzip wget
    success "Vereisten geinstalleerd."

    # Bekende MariaDB-opstartfout na een onnette afsluiting - een oude
    # tc.log kan de eerste start blokkeren. Verwijderen is veilig (wordt
    # opnieuw aangemaakt) en voorkomt deze bekende valkuil.
    rm -f /var/lib/mysql/tc.log 2>/dev/null || true

    systemctl start mariadb && systemctl enable mariadb
    success "MariaDB draait."
}

###############################################################################
# 2. Database
###############################################################################
setup_database() {
    log "Database aanmaken..."
    NC_DB_PASS=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 20 || true)
    mysql -u root -e "CREATE DATABASE IF NOT EXISTS nextcloud CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci; \
        CREATE USER IF NOT EXISTS 'ncuser'@'localhost' IDENTIFIED BY '${NC_DB_PASS}'; \
        GRANT ALL PRIVILEGES ON nextcloud.* TO 'ncuser'@'localhost'; FLUSH PRIVILEGES;"
    success "Database 'nextcloud' aangemaakt."
}

###############################################################################
# 3. Nextcloud zelf
###############################################################################
install_nextcloud() {
    if [[ -d /var/www/html/nextcloud ]]; then
        warn "Nextcloud staat er al - installatie overgeslagen (gebruik pinas_nextcloud_verwijderen.sh om opnieuw te beginnen)."
        return
    fi
    log "Nextcloud downloaden..."
    cd /tmp && wget -q -O latest.zip https://download.nextcloud.com/server/releases/latest.zip
    success "Gedownload."

    log "Uitpakken en plaatsen..."
    unzip -q latest.zip
    mv nextcloud /var/www/html/
    chown -R www-data:www-data /var/www/html/nextcloud
    rm -f /tmp/latest.zip
    success "Geplaatst in /var/www/html/nextcloud."

    log "Datamap aanmaken op de Opslag-schijf (${NC_DATA})..."
    mkdir -p "$NC_DATA"
    chown -R www-data:www-data "$NC_DATA"
    success "Datamap klaar."

    log "Apache instellen..."
    a2enmod rewrite headers env dir mime
    systemctl restart apache2
    success "Apache klaar."

    log "Nextcloud initialiseren (dit duurt even)..."
    NC_ADMIN_PASS=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 16 || true)
    sudo -u www-data php /var/www/html/nextcloud/occ maintenance:install \
        --database mysql --database-name nextcloud --database-user ncuser \
        --database-pass "${NC_DB_PASS}" --admin-user "${NC_ADMIN}" \
        --admin-pass "${NC_ADMIN_PASS}" --data-dir "${NC_DATA}"
    success "Nextcloud geinitialiseerd."

    log "Nog wat opruimen en instellen..."
    sudo -u www-data php /var/www/html/nextcloud/occ config:system:set trusted_domains 1 --value="${PI_IP}"
    rm -rf /var/www/html/nextcloud/core/skeleton/*
    sudo -u www-data php /var/www/html/nextcloud/occ files:scan "${NC_ADMIN}" --quiet 2>/dev/null || true
    success "Klaar."
}

schrijf_versie_marker() {
    # Zie pinas_printer.sh voor de volledige uitleg.
    local marker_dir="/etc/pinas-addon-versies"
    mkdir -p "$marker_dir"
    chmod 755 "$marker_dir"
    local hash
    hash=$(sha256sum "$0" 2>/dev/null | awk '{print $1}')
    if [[ -n "$hash" ]]; then
        echo "$hash" > "${marker_dir}/nextcloud.sha256"
        chmod 644 "${marker_dir}/nextcloud.sha256"
    fi
}

###############################################################################
# 4. Samenvatting
###############################################################################
samenvatting() {
cat <<EOF

=====================================================================
  KLAAR - Nextcloud draait
=====================================================================

  Open Nextcloud op: http://${PI_IP}/nextcloud

  Beheerdersnaam    : ${NC_ADMIN}
  Beheerderswachtwoord: ${NC_ADMIN_PASS:-al eerder ingesteld}
  (schrijf dit op - het wordt niet opnieuw getoond)

  Data staat in     : ${NC_DATA} (op de Opslag-schijf, niet de SD-kaart)

  ---------------------------------------------------------------
  Wil je Nextcloud ook via VPN kunnen bereiken (thuis en onderweg)?
  Draai dan apart: sudo bash pinas_zerotier.sh (als dat nog niet is
  gedaan), en voeg daarna het ZeroTier-IP toe aan trusted_domains:
     sudo -u www-data php /var/www/html/nextcloud/occ config:system:set trusted_domains 2 --value=<zerotier-ip>
  ---------------------------------------------------------------

  Log: ${LOGFILE}
=====================================================================
EOF
}

###############################################################################
main() {
    welkom
    check_root
    check_internet
    detect_network
    check_mountpoint
    vraag_gebruikersnaam
    install_vereisten
    setup_database
    install_nextcloud
    schrijf_versie_marker
    samenvatting
}
main "$@"
