#!/usr/bin/env bash
###############################################################################
# PiNAS - PiNAS Dashboard: wachtwoord opnieuw instellen
#
# Voor als je het wachtwoord van PiNAS Dashboard kwijt bent. Maakt een NIEUW
# wachtwoord aan (het oude werkt daarna niet meer) en herstart de dienst.
# Het Dashboard zelf hoeft NIET opnieuw geinstalleerd te worden.
#
# (12 augustus 2026) Nieuw als onderdeel van het samenvoegen van de mobiele
# statuspagina in PiNAS Dashboard - vervangt
# pinas_status_pagina_wachtwoord_resetten.sh, zelfde opzet.
#
# Gebruik:  sudo bash pinas_dashboard_wachtwoord_resetten.sh
###############################################################################

set -Eeuo pipefail

readonly LOGFILE="/var/log/pinas_dashboard_wachtwoord.log"
readonly APP_DIR="/opt/pinas-dashboard"
readonly HASH_FILE="${APP_DIR}/wachtwoord.hash"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

mkdir -p /var/log; touch "$LOGFILE"; chmod 600 "$LOGFILE"
exec > >(tee >(sed -r 's/\x1b\[[0-9;]*m//g' >> "$LOGFILE")) 2>&1

log()     { echo; echo -e "${BLUE}[$(date '+%F %T')]${NC} $1"; }
success() { echo -e "${GREEN}OK: $1${NC}"; }
warn()    { echo -e "${YELLOW}LET OP: $1${NC}"; }
error()   { echo -e "${RED}FOUT: $1${NC}"; }
on_error(){ error "Afgebroken op regel $1. Log: $LOGFILE"; exit 1; }
trap 'on_error $LINENO' ERR

[[ $EUID -eq 0 ]] || { error "Start met: sudo bash pinas_dashboard_wachtwoord_resetten.sh"; exit 1; }

if [[ ! -d "$APP_DIR" ]]; then
    error "PiNAS Dashboard is niet geinstalleerd (${APP_DIR} ontbreekt). Installeer eerst pinas_dashboard.sh."
    exit 1
fi

python3 -c "import flask, werkzeug" 2>/dev/null \
    || { error "python3-flask ontbreekt. Installeer eerst pinas_dashboard.sh."; exit 1; }

cat <<EOF

=====================================================================
  Wachtwoord opnieuw instellen - PiNAS Dashboard
=====================================================================
  Dit maakt een NIEUW wachtwoord aan. Het oude wachtwoord werkt daarna
  niet meer - je hoeft verder nergens iets aan te passen.
=====================================================================
EOF
read -rp ">> Doorgaan? (j/n): " akkoord
[[ "${akkoord,,}" == "j" ]] || { warn "Geannuleerd."; exit 0; }

echo
read -rp ">> Typ je eigen wachtwoord, of laat leeg voor automatisch gegenereerd: " EIGEN_WACHTWOORD
if [[ -n "$EIGEN_WACHTWOORD" ]]; then
    NIEUW_WACHTWOORD="$EIGEN_WACHTWOORD"
    log "Eigen wachtwoord instellen..."
else
    log "Nieuw wachtwoord genereren..."
    NIEUW_WACHTWOORD=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 16 || true)
fi
python3 -c "
from werkzeug.security import generate_password_hash
print(generate_password_hash('${NIEUW_WACHTWOORD}'))
" > "$HASH_FILE"
chmod 600 "$HASH_FILE"
chown pi:pi "$HASH_FILE"
success "Nieuw wachtwoord ingesteld."

log "Dienst herstarten..."
systemctl restart pinas-dashboard 2>/dev/null || true
sleep 2
if systemctl is-active --quiet pinas-dashboard; then
    success "Dashboard draait weer."
else
    warn "Dienst lijkt niet (meer) te draaien - controleer: journalctl -u pinas-dashboard"
fi

cat <<EOF

=====================================================================
  KLAAR
=====================================================================
  Nieuw wachtwoord : ${NIEUW_WACHTWOORD}
  (schrijf dit op - het wordt niet opnieuw getoond)

  Log: ${LOGFILE}
=====================================================================
EOF
