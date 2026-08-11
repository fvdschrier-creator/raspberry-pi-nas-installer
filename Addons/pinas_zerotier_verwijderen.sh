#!/usr/bin/env bash
###############################################################################
# PiNAS - VPN (ZeroTier) DE-INSTALLATIE (terug naar schoon)
#
# Verwijdert wat pinas_zerotier.sh heeft geinstalleerd:
#   - ZeroTier
#
# Raakt je NAS (Samba, Nextcloud, Apache) en Pi-hole/dnscrypt-proxy NIET
# aan - zie pinas_pihole_verwijderen.sh voor de adblock/DNS-kant.
#
# Gebruik:  sudo bash pinas_zerotier_verwijderen.sh
###############################################################################

set -Euo pipefail   # geen -e: we willen doorgaan ook als het al weg is

readonly LOGFILE="/var/log/pinas_zerotier_verwijderen.log"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
mkdir -p /var/log; touch "$LOGFILE"; chmod 600 "$LOGFILE"
exec > >(tee >(sed -r 's/\x1b\[[0-9;]*m//g' >> "$LOGFILE")) 2>&1

log()     { echo; echo -e "${BLUE}[$(date '+%F %T')]${NC} $1"; }
success() { echo -e "${GREEN}OK: $1${NC}"; }
warn()    { echo -e "${YELLOW}LET OP: $1${NC}"; }
error()   { echo -e "${RED}FOUT: $1${NC}"; }

[[ $EUID -eq 0 ]] || { error "Start met: sudo bash pinas_zerotier_verwijderen.sh"; exit 1; }

cat <<EOF

=====================================================================
  DE-INSTALLATIE - VPN (ZeroTier) terug naar schoon
=====================================================================
  Dit verwijdert ZeroTier van deze Pi.
  Je NAS en Pi-hole/dnscrypt-proxy blijven ongemoeid.
=====================================================================
EOF
read -rp ">> Typ VERWIJDER om door te gaan: " bevestig
[[ "$bevestig" == "VERWIJDER" ]] || { warn "Geannuleerd."; exit 0; }

###############################################################################
# ZeroTier
###############################################################################
log "ZeroTier verwijderen..."
if command -v zerotier-cli >/dev/null 2>&1; then
    # Netjes uit het netwerk stappen voor het verwijderen, zodat het apparaat
    # niet als "spookje" in het my.zerotier.com-dashboard blijft hangen.
    for nwid in $(zerotier-cli listnetworks 2>/dev/null | awk 'NR>1 {print $3}'); do
        zerotier-cli leave "$nwid" 2>/dev/null || true
    done
    systemctl disable --now zerotier-one 2>/dev/null || true
    apt-get remove -y zerotier-one 2>/dev/null || true
    rm -rf /var/lib/zerotier-one 2>/dev/null || true
    success "ZeroTier verwijderd."
else
    success "ZeroTier was niet aanwezig."
fi

cat <<EOF

=====================================================================
  KLAAR - ZeroTier is verwijderd.
=====================================================================
  Je NAS en Pi-hole/dnscrypt-proxy zijn niet aangeraakt.

  NIET VERGETEN:
     - Verwijder deze Pi ook uit my.zerotier.com (Members-lijst), en
       verwijder ZeroTier van je andere apparaten (Windows/iPhone/
       Android) als je de VPN helemaal niet meer wilt gebruiken.
     - Verwijder het ZeroTier-IP uit Nextcloud's trusted_domains als
       dat is toegevoegd:
       sudo -u www-data php /var/www/html/nextcloud/occ config:system:get trusted_domains

  Log: ${LOGFILE}
=====================================================================
EOF
