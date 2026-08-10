#!/usr/bin/env bash
###############################################################################
# PiNAS - Vaultwarden DE-INSTALLATIE
#
# Verwijdert de Vaultwarden-container, de nginx-configuratie ervoor, en het
# root-/servercertificaat. Docker ZELF wordt nooit verwijderd (wordt ook voor
# andere dingen gebruikt) en nginx blijft staan als er nog andere sites op
# draaien.
#
# De data (/opt/pinas-vault/data - je wachtwoordkluis) wordt ALLEEN
# verwijderd als je dat expliciet bevestigt.
#
# Gebruik:  sudo bash pinas_vaultwarden_verwijderen.sh
###############################################################################

set -Euo pipefail   # geen -e: we willen doorgaan ook als een onderdeel al weg is

readonly LOGFILE="/var/log/pinas_vaultwarden_verwijderen.log"
readonly CA_DIR="/etc/pinas-ca"
readonly DATA_DIR="/opt/pinas-vault/data"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
mkdir -p /var/log; touch "$LOGFILE"; chmod 600 "$LOGFILE"
exec > >(tee >(sed -r 's/\x1b\[[0-9;]*m//g' >> "$LOGFILE")) 2>&1

log()     { echo; echo -e "${BLUE}[$(date '+%F %T')]${NC} $1"; }
success() { echo -e "${GREEN}OK: $1${NC}"; }
warn()    { echo -e "${YELLOW}LET OP: $1${NC}"; }
error()   { echo -e "${RED}FOUT: $1${NC}"; }

[[ $EUID -eq 0 ]] || { error "Start met: sudo bash pinas_vaultwarden_verwijderen.sh"; exit 1; }

cat <<EOF

=====================================================================
  DE-INSTALLATIE - Vaultwarden
=====================================================================
  Verwijdert de Vaultwarden-container, de nginx-configuratie en het
  root-/servercertificaat (dus daarna moet een herinstallatie op elk
  apparaat opnieuw vertrouwd worden).
  Docker zelf en nginx (als er nog andere sites op draaien) blijven staan.
  De data (${DATA_DIR}) blijft standaard staan.
=====================================================================
EOF
read -rp ">> Typ VERWIJDER om door te gaan: " bevestig
[[ "$bevestig" == "VERWIJDER" ]] || { warn "Geannuleerd."; exit 0; }

log "Vaultwarden-container stoppen en verwijderen..."
docker rm -f vaultwarden >/dev/null 2>&1 || true
success "Container verwijderd."

log "Geplande certificaatvernieuwing uit crontab verwijderen..."
( crontab -l 2>/dev/null | grep -v "vernieuw_certificaat.sh" ) | crontab - 2>/dev/null || true
success "Cron-taak verwijderd."

log "nginx-configuratie verwijderen..."
rm -f /etc/nginx/sites-enabled/vaultwarden.conf /etc/nginx/sites-available/vaultwarden.conf
if nginx -t >/dev/null 2>&1; then
    systemctl reload nginx 2>/dev/null || true
fi
if [[ -z "$(ls -A /etc/nginx/sites-enabled 2>/dev/null)" ]]; then
    warn "nginx heeft geen actieve sites meer - blijft geinstalleerd staan (verwijder desgewenst zelf met: apt-get remove nginx)."
else
    success "nginx-configuratie voor Vaultwarden verwijderd, andere sites blijven draaien."
fi

log "Root-/servercertificaat verwijderen..."
rm -rf "$CA_DIR"
success "Certificaten verwijderd (${CA_DIR})."

echo
if [[ -d "$DATA_DIR" ]]; then
    warn "De wachtwoordkluis-data staat nog in ${DATA_DIR}."
    read -rp ">> Ook de DATA definitief wissen? Typ dan WISDATA (anders ENTER): " wisdata
    if [[ "${wisdata:-}" == "WISDATA" ]]; then
        rm -rf "$DATA_DIR"
        success "Data definitief verwijderd."
    else
        success "Data bewaard in ${DATA_DIR} (voor een eventuele herinstallatie)."
    fi
fi

cat <<EOF

=====================================================================
  KLAAR - Vaultwarden is verwijderd.
=====================================================================
  Je NAS en eventuele andere add-ons (Nextcloud, Pi-hole, ZeroTier)
  zijn niet aangeraakt. Docker zelf staat nog gewoon geinstalleerd.

  Log: ${LOGFILE}
=====================================================================
EOF
