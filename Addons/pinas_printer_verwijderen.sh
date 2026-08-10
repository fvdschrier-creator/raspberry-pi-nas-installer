#!/usr/bin/env bash
###############################################################################
# pinas_printer_verwijderen.sh - Pi NAS Suite - Addon: Printserver VERWIJDEREN
#
# Verwijdert wat pinas_printer.sh installeerde:
#   - CUPS (printserver) + drivers
#   - AirPrint/IPP-configuratie
#
# Raakt de NAS (Samba, Nextcloud, andere add-ons) NIET aan.
# Avahi-daemon wordt NIET verwijderd (kan door andere diensten gebruikt
# worden) - alleen CUPS zelf.
#
# Gebruik: sudo bash pinas_printer_verwijderen.sh
###############################################################################

set -Euo pipefail

readonly LOGFILE="/var/log/pinas_printer_verwijderen.log"
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
mkdir -p /var/log; touch "$LOGFILE"; chmod 600 "$LOGFILE"
exec > >(tee >(sed -r 's/\x1b\[[0-9;]*m//g' >> "$LOGFILE")) 2>&1

log()     { echo; echo -e "${BLUE}[$(date '+%F %T')]${NC} $1"; }
success() { echo -e "${GREEN}OK: $1${NC}"; }
warn()    { echo -e "${YELLOW}LET OP: $1${NC}"; }
error()   { echo -e "${RED}FOUT: $1${NC}"; }

[[ $EUID -eq 0 ]] || { error "Start met: sudo bash pinas_printer_verwijderen.sh"; exit 1; }

cat <<EOF

=====================================================================
  PRINTSERVER VERWIJDEREN
=====================================================================
  Dit verwijdert CUPS (de printserver) en de printerdrivers.
  Je NAS en andere add-ons blijven ongemoeid.
=====================================================================
EOF
read -rp ">> Typ VERWIJDER om door te gaan: " bevestig
[[ "$bevestig" == "VERWIJDER" ]] || { warn "Geannuleerd."; exit 0; }

log "CUPS stoppen en verwijderen..."
systemctl disable --now cups 2>/dev/null || true
systemctl disable --now cups-browsed 2>/dev/null || true

export DEBIAN_FRONTEND=noninteractive
apt-get remove -y cups cups-daemon cups-client printer-driver-gutenprint \
                  printer-driver-all cups-ipp-utils 2>/dev/null || true
apt-get autoremove -y 2>/dev/null || true

# CUPS-configuratie en printer-definities opruimen
rm -rf /etc/cups 2>/dev/null || true

success "CUPS verwijderd."

log "Gebruiker 'pi' uit groep lpadmin halen (opruimen)..."
gpasswd -d pi lpadmin 2>/dev/null || true
success "Opgeruimd."

cat <<EOF

=====================================================================
  KLAAR - printserver verwijderd.
=====================================================================
  Avahi (netwerkdetectie) is bewust NIET verwijderd - andere diensten
  kunnen die gebruiken. Wil je die ook weg, doe dat handmatig:
     sudo apt-get remove avahi-daemon

  Log: ${LOGFILE}
=====================================================================
EOF
