#!/usr/bin/env bash
###############################################################################
# PiNAS - Adblock (Pi-hole) + versleutelde DNS DE-INSTALLATIE (terug naar schoon)
#
# Verwijdert wat pinas_pihole.sh heeft geinstalleerd:
#   - Pi-hole
#   - dnscrypt-proxy (+ config)
#   - IP forwarding / systemd-resolved aanpassingen
#
# Raakt je NAS (Samba, Nextcloud, Apache) en ZeroTier NIET aan - zie
# pinas_zerotier_verwijderen.sh voor de VPN-kant.
#
# Gebruik:  sudo bash pinas_pihole_verwijderen.sh
###############################################################################

set -Euo pipefail   # geen -e: we willen doorgaan ook als een onderdeel al weg is

readonly LOGFILE="/var/log/pinas_pihole_verwijderen.log"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
mkdir -p /var/log; touch "$LOGFILE"; chmod 600 "$LOGFILE"
exec > >(tee >(sed -r 's/\x1b\[[0-9;]*m//g' >> "$LOGFILE")) 2>&1

log()     { echo; echo -e "${BLUE}[$(date '+%F %T')]${NC} $1"; }
success() { echo -e "${GREEN}OK: $1${NC}"; }
warn()    { echo -e "${YELLOW}LET OP: $1${NC}"; }
error()   { echo -e "${RED}FOUT: $1${NC}"; }

[[ $EUID -eq 0 ]] || { error "Start met: sudo bash pinas_pihole_verwijderen.sh"; exit 1; }

cat <<EOF

=====================================================================
  DE-INSTALLATIE - Adblock (Pi-hole) + versleutelde DNS terug naar schoon
=====================================================================
  Dit verwijdert Pi-hole en dnscrypt-proxy.
  Je NAS (Samba, Nextcloud, Apache poort 80) en ZeroTier blijven ongemoeid.
=====================================================================
EOF
read -rp ">> Typ VERWIJDER om door te gaan: " bevestig
[[ "$bevestig" == "VERWIJDER" ]] || { warn "Geannuleerd."; exit 0; }

###############################################################################
# Pi-hole
###############################################################################
log "Pi-hole verwijderen..."
if command -v pihole >/dev/null 2>&1; then
    # De officiele uninstaller draait interactief; we forceren via 'yes'.
    if [[ -x /etc/.pihole/automated\ install/uninstall.sh ]]; then
        yes | bash "/etc/.pihole/automated install/uninstall.sh" 2>/dev/null || true
    fi
    # Voor de zekerheid resten opruimen
    systemctl disable --now pihole-FTL 2>/dev/null || true
    apt-get remove -y pihole-ftl 2>/dev/null || true
    rm -rf /etc/pihole /etc/.pihole /opt/pihole /var/log/pihole 2>/dev/null || true
    rm -f /usr/local/bin/pihole /etc/bash_completion.d/pihole 2>/dev/null || true
    success "Pi-hole verwijderd."
else
    success "Pi-hole was niet aanwezig."
fi

###############################################################################
# dnscrypt-proxy
###############################################################################
log "dnscrypt-proxy verwijderen..."
systemctl stop pinas-dnscrypt 2>/dev/null || true
systemctl disable pinas-dnscrypt 2>/dev/null || true
rm -f /etc/systemd/system/pinas-dnscrypt.service 2>/dev/null || true
systemctl unmask dnscrypt-proxy.socket 2>/dev/null || true
systemctl daemon-reload 2>/dev/null || true
if dpkg -l dnscrypt-proxy >/dev/null 2>&1; then
    apt-get remove -y dnscrypt-proxy 2>/dev/null || true
    apt-get purge -y dnscrypt-proxy 2>/dev/null || true
    rm -rf /etc/dnscrypt-proxy 2>/dev/null || true
    success "dnscrypt-proxy verwijderd."
else
    success "dnscrypt-proxy was niet aanwezig."
fi

# Restje van een oudere cloudflared-poging (gebruikt voor DNS-over-HTTPS,
# vervangen door dnscrypt-proxy nadat Cloudflare die functie per 2 feb 2026
# heeft verwijderd). Niet gerelateerd aan ZeroTier of Cloudflare Tunnel.
if [[ -f /etc/systemd/system/cloudflared.service ]] || command -v cloudflared >/dev/null 2>&1; then
    log "Restje van eerdere cloudflared-poging opruimen..."
    systemctl disable --now cloudflared 2>/dev/null || true
    rm -f /etc/systemd/system/cloudflared.service /usr/local/bin/cloudflared 2>/dev/null || true
    systemctl daemon-reload 2>/dev/null || true
    id -u cloudflared >/dev/null 2>&1 && userdel cloudflared 2>/dev/null || true
    success "Oude cloudflared-restanten verwijderd."
fi

###############################################################################
# systemd-resolved herstellen
###############################################################################
log "systemd-resolved herstellen (DNS-stub terug aan)..."
if [[ -f /etc/systemd/resolved.conf.d/pihole.conf ]]; then
    rm -f /etc/systemd/resolved.conf.d/pihole.conf
    systemctl restart systemd-resolved 2>/dev/null || true
    success "systemd-resolved teruggezet."
else
    success "Geen systemd-resolved-aanpassing gevonden."
fi

cat <<EOF

=====================================================================
  KLAAR - Pi-hole en dnscrypt-proxy zijn verwijderd.
=====================================================================
  Je NAS (Samba, Nextcloud, Apache) en ZeroTier zijn niet aangeraakt.

  NIET VERGETEN:
     - In de Deco-app: zet de DHCP DNS terug op 'automatisch' (of je
       oude waarde), anders wijzen je apparaten nog naar de verdwenen
       Pi-hole.

  Log: ${LOGFILE}
=====================================================================
EOF
