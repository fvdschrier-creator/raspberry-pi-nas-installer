#!/usr/bin/env bash
###############################################################################
# PiNAS - Mobiele statuspagina DE-INSTALLATIE
#
# Stopt en verwijdert de systemd-dienst en alle bestanden in /opt/pinas-status
# (wachtwoord-hash, sessiesleutel, de webapp zelf). Er is geen losse
# gebruikersdata om te bewaren - alles hier is opnieuw te installeren met
# pinas_status_pagina.sh (met een nieuw wachtwoord).
#
# Gebruik:  sudo bash pinas_status_pagina_verwijderen.sh
###############################################################################

set -Euo pipefail

readonly LOGFILE="/var/log/pinas_status_pagina_verwijderen.log"
readonly APP_DIR="/opt/pinas-status"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
mkdir -p /var/log; touch "$LOGFILE"; chmod 600 "$LOGFILE"
exec > >(tee >(sed -r 's/\x1b\[[0-9;]*m//g' >> "$LOGFILE")) 2>&1

log()     { echo; echo -e "${BLUE}[$(date '+%F %T')]${NC} $1"; }
success() { echo -e "${GREEN}OK: $1${NC}"; }
warn()    { echo -e "${YELLOW}LET OP: $1${NC}"; }
error()   { echo -e "${RED}FOUT: $1${NC}"; }

[[ $EUID -eq 0 ]] || { error "Start met: sudo bash pinas_status_pagina_verwijderen.sh"; exit 1; }

cat <<EOF

=====================================================================
  DE-INSTALLATIE - Mobiele statuspagina
=====================================================================
  Stopt en verwijdert de statuspagina-dienst en alle bijbehorende
  bestanden (${APP_DIR}). Er is geen gebruikersdata om te bewaren -
  alleen het wachtwoord (hash) en de sessiesleutel.
=====================================================================
EOF
read -rp ">> Typ VERWIJDER om door te gaan: " bevestig
[[ "$bevestig" == "VERWIJDER" ]] || { warn "Geannuleerd."; exit 0; }

log "Dienst stoppen en uitschakelen..."
systemctl stop pinas-status 2>/dev/null || true
systemctl disable pinas-status 2>/dev/null || true
rm -f /etc/systemd/system/pinas-status.service
systemctl daemon-reload
success "Dienst gestopt en verwijderd."

log "Bestanden verwijderen..."
rm -rf "$APP_DIR"
success "Bestanden verwijderd (${APP_DIR})."

cat <<EOF

=====================================================================
  KLAAR
=====================================================================
  De mobiele statuspagina is verwijderd. Opnieuw installeren kan altijd
  met pinas_status_pagina.sh (krijgt dan een nieuw wachtwoord).

  Log: ${LOGFILE}
=====================================================================
EOF
