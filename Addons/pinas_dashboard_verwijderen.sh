#!/usr/bin/env bash
###############################################################################
# PiNAS - Dashboard DE-INSTALLATIE
#
# Verwijdert de Dashboard-webapp, zijn systemd-dienst en alle bijbehorende
# bestanden (wachtwoord, sessiesleutel) volledig - 100% opgeruimd, niets
# blijft achter. Poort 8095 komt weer vrij.
#
# Gebruik:  sudo bash pinas_dashboard_verwijderen.sh
###############################################################################

set -Euo pipefail   # geen -e: we willen doorgaan ook als een onderdeel al weg is

readonly LOGFILE="/var/log/pinas_dashboard_verwijderen.log"
readonly APP_DIR="/opt/pinas-dashboard"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
mkdir -p /var/log; touch "$LOGFILE"; chmod 600 "$LOGFILE"
exec > >(tee >(sed -r 's/\x1b\[[0-9;]*m//g' >> "$LOGFILE")) 2>&1

log()     { echo; echo -e "${BLUE}[$(date '+%F %T')]${NC} $1"; }
success() { echo -e "${GREEN}OK: $1${NC}"; }
warn()    { echo -e "${YELLOW}LET OP: $1${NC}"; }
error()   { echo -e "${RED}FOUT: $1${NC}"; }

[[ $EUID -eq 0 ]] || { error "Start met: sudo bash pinas_dashboard_verwijderen.sh"; exit 1; }

cat <<EOF

=====================================================================
  DE-INSTALLATIE - PiNAS Dashboard
=====================================================================
  Verwijdert de Dashboard-webapp, de systemd-dienst, het wachtwoord en
  de sessiesleutel volledig. Niets blijft achter. Poort 8095 komt weer
  vrij. Andere add-ons (Nextcloud, Pi-hole, ZeroTier, Vaultwarden,
  Mobiele statuspagina, Printserver) worden niet aangeraakt.
=====================================================================
EOF
read -rp ">> Typ VERWIJDER om door te gaan: " bevestig
[[ "$bevestig" == "VERWIJDER" ]] || { warn "Geannuleerd."; exit 0; }

log "Dashboard-dienst stoppen en uitschakelen..."
systemctl stop pinas-dashboard 2>/dev/null || true
systemctl disable pinas-dashboard 2>/dev/null || true
success "Dienst gestopt."

log "systemd-eenheid verwijderen..."
rm -f /etc/systemd/system/pinas-dashboard.service
systemctl daemon-reload
success "systemd-eenheid verwijderd."

log "Webapp, wachtwoord en sessiesleutel verwijderen..."
rm -rf "$APP_DIR"
success "${APP_DIR} volledig verwijderd."

log "Versie-afdruk opruimen..."
rm -f /etc/pinas-addon-versies/dashboard.sha256
success "Versie-afdruk verwijderd."

cat <<EOF

=====================================================================
  KLAAR - PiNAS Dashboard is volledig verwijderd.
=====================================================================
  Poort 8095 is weer vrij. Je NAS en andere add-ons zijn niet
  aangeraakt.

  Log: ${LOGFILE}
=====================================================================
EOF
