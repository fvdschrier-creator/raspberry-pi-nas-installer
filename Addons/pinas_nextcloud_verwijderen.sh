#!/usr/bin/env bash
###############################################################################
# PiNAS - Nextcloud DE-INSTALLATIE
#
# Verwijdert Nextcloud en zijn vereisten (Apache, MariaDB, PHP).
# De data (/mnt/opslag/nextcloud-data) wordt ALLEEN verwijderd als je dat
# expliciet bevestigt - standaard blijft die staan als backup.
#
# Gebruik:  sudo bash pinas_nextcloud_verwijderen.sh
###############################################################################

set -Euo pipefail   # geen -e: we willen doorgaan ook als een onderdeel al weg is

readonly LOGFILE="/var/log/pinas_nextcloud_verwijderen.log"
readonly NC_DATA="/mnt/opslag/nextcloud-data"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
mkdir -p /var/log; touch "$LOGFILE"; chmod 600 "$LOGFILE"
exec > >(tee >(sed -r 's/\x1b\[[0-9;]*m//g' >> "$LOGFILE")) 2>&1

log()     { echo; echo -e "${BLUE}[$(date '+%F %T')]${NC} $1"; }
success() { echo -e "${GREEN}OK: $1${NC}"; }
warn()    { echo -e "${YELLOW}LET OP: $1${NC}"; }
error()   { echo -e "${RED}FOUT: $1${NC}"; }

[[ $EUID -eq 0 ]] || { error "Start met: sudo bash pinas_nextcloud_verwijderen.sh"; exit 1; }

cat <<EOF

=====================================================================
  DE-INSTALLATIE - Nextcloud
=====================================================================
  Verwijdert Nextcloud, Apache, MariaDB en PHP.
  De data (${NC_DATA}) blijft standaard staan.
=====================================================================
EOF
read -rp ">> Typ VERWIJDER om door te gaan: " bevestig
[[ "$bevestig" == "VERWIJDER" ]] || { warn "Geannuleerd."; exit 0; }

log "Services stoppen..."
systemctl stop apache2 mariadb 2>/dev/null || true
success "Services gestopt."

log "Nextcloud verwijderen..."
rm -rf /var/www/html/nextcloud 2>/dev/null || true
success "Nextcloud-bestanden verwijderd."

log "Pakketten verwijderen (Apache, MariaDB, PHP)..."
apt-get remove -y apache2 mariadb-server 'php*' libapache2-mod-php 2>/dev/null || true
apt-get autoremove -y 2>/dev/null || true
success "Pakketten verwijderd."

echo
if [[ -d "$NC_DATA" ]]; then
    warn "De data staat nog in ${NC_DATA}."
    read -rp ">> Ook de DATA definitief wissen? Typ dan WISDATA (anders ENTER): " wisdata
    if [[ "${wisdata:-}" == "WISDATA" ]]; then
        rm -rf "$NC_DATA"
        success "Data definitief verwijderd."
    else
        success "Data bewaard in ${NC_DATA} (voor een eventuele herinstallatie)."
    fi
fi

cat <<EOF

=====================================================================
  KLAAR - Nextcloud is verwijderd.
=====================================================================
  Je NAS (Samba, FileBrowser, Cockpit) en eventuele add-ons
  (Pi-hole, ZeroTier, Vault) zijn niet aangeraakt.

  Log: ${LOGFILE}
=====================================================================
EOF
