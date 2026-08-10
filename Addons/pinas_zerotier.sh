#!/usr/bin/env bash
###############################################################################
# PiNAS - VPN (ZeroTier) installer
#
# Installeert NAAST een bestaande PiNAS, zonder iets te breken:
#   - ZeroTier              (VPN, mesh-netwerk)    login = handmatige stap
#
# Was voorheen gebundeld met Pi-hole/dnscrypt-proxy in 1 script
# (pinas_adblock_vpn.sh) - gesplitst zodat VPN onafhankelijk van adblock/DNS
# geinstalleerd, gecontroleerd en hersteld kan worden. Zie pinas_pihole.sh
# voor adblock/versleutelde DNS.
#
# LET OP: eerder gebruikte deze suite Tailscale voor de VPN. Op de Windows-pc
# dell-3070 bleek Tailscale een niet te achterhalen, blijvende crash-loop te
# hebben (watchdog timeout on Reconfig - onderzocht t/m Process Monitor,
# oorzaak niet gevonden ondanks uitgebreid onderzoek, ook niet opgelost door
# downgrade of Defender-uitsluitingen). ZeroTier is hiervoor in de plaats
# gekomen: zelfde soort mesh-VPN, andere leverancier, getest en werkend
# bevonden op Pi, Windows, iPhone en Android (juli 2026). Gratis tot 10
# apparaten, ruim voldoende voor deze suite.
#
# Gebruik:  sudo bash pinas_zerotier.sh
###############################################################################

set -Eeuo pipefail

readonly VERSION="1.0"
readonly LOGFILE="/var/log/pinas_zerotier.log"

# Vul hier het netwerk-ID van je eigen ZeroTier-netwerk in (te vinden op
# my.zerotier.com nadat je daar een netwerk hebt aangemaakt). Zonder een
# geldig ID kan de Pi niet automatisch aansluiten.
readonly ZT_NETWORK_ID="UW_ZEROTIER_NETWERK_ID"

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
  PiNAS - VPN (ZeroTier)
  Versie ${VERSION}
=====================================================================

  Dit script installeert, NAAST je bestaande NAS:

    1. ZeroTier             - VPN om veilig thuis te komen van onderweg

  Je NAS (Samba, Nextcloud, adblock/DNS) blijft ongemoeid.

  ---------------------------------------------------------------
  BELANGRIJK OM VOORAF TE WETEN:
  ---------------------------------------------------------------
  - Dit script sluit de Pi automatisch aan bij netwerk-ID
    ${ZT_NETWORK_ID}, maar daarna moet je de Pi nog HANDMATIG
    goedkeuren op my.zerotier.com (Members -> vinkje aanzetten naast
    deze Pi). Zonder die stap krijgt de Pi geen IP-adres en werkt de
    VPN niet.
  - Op elk ANDER apparaat dat je via VPN wilt laten meedoen (Windows,
    telefoon), moet je apart de ZeroTier-app installeren, hetzelfde
    netwerk-ID invoeren, en dat apparaat ook goedkeuren.

  Duurt ongeveer 2-3 minuten, plus de handmatige goedkeuring.

  Log van deze installatie: ${LOGFILE}

=====================================================================
EOF
pauze
}

check_root() {
    [[ $EUID -eq 0 ]] || { error "Start met: sudo bash pinas_zerotier.sh"; exit 1; }
    success "Rootrechten OK."
}

check_netwerk_id() {
    # In de gepubliceerde/geanonimiseerde versie (GitHub, starter kit) wordt
    # het echte netwerk-ID hierboven vervangen door deze placeholder - een
    # duidelijke foutmelding hier voorkomt dat iemand per ongeluk probeert
    # aan te sluiten bij een niet-bestaand netwerk zonder te snappen waarom
    # (17 juli 2026, n.a.v. vraag Frans over publicatie van de add-ons).
    if [[ "$ZT_NETWORK_ID" == "UW_ZEROTIER_NETWERK_ID" ]]; then
        error "Vul eerst je eigen ZeroTier netwerk-ID in bovenaan dit script (ZT_NETWORK_ID)."
        echo "  Maak een netwerk aan op my.zerotier.com (gratis account, 'Sign in with"
        echo "  Google' kan ook) en kopieer het Network ID daarvandaan."
        exit 1
    fi
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

###############################################################################
# 1. ZeroTier
###############################################################################
install_zerotier() {
    if command -v zerotier-cli >/dev/null 2>&1; then
        warn "ZeroTier al aanwezig - installatie overgeslagen."
    else
        log "ZeroTier installeren..."
        curl -s https://install.zerotier.com | bash
        success "ZeroTier geinstalleerd."
    fi
}

activeer_zerotier() {
    log "Bij netwerk ${ZT_NETWORK_ID} aansluiten..."
    zerotier-cli join "$ZT_NETWORK_ID" || warn "Join-commando gaf een fout - controleer het netwerk-ID."

    echo
    warn "ZeroTier-goedkeuring kan NIET automatisch - dit doe je nu zelf."
    echo "  Ga naar my.zerotier.com, open je netwerk, en vink onder 'Members'"
    echo "  het vakje aan naast deze Pi (te herkennen aan het Device ID)."
    echo "  Zonder die goedkeuring krijgt de Pi geen IP-adres binnen het"
    echo "  ZeroTier-netwerk en werkt de VPN niet."
    pauze

    sleep 3
    ZT_IP=$(zerotier-cli listnetworks 2>/dev/null | awk -v id="$ZT_NETWORK_ID" '$0 ~ id {print $NF}')
    if [[ -n "${ZT_IP:-}" && "$ZT_IP" != "-" ]]; then
        success "ZeroTier actief, IP: ${ZT_IP}"
    else
        warn "Nog geen IP toegewezen - waarschijnlijk moet de goedkeuring in het dashboard nog verwerkt worden."
        warn "Controleer later met: sudo zerotier-cli listnetworks"
    fi
}

schrijf_versie_marker() {
    # Zie pinas_printer.sh voor de volledige uitleg.
    local marker_dir="/etc/pinas-addon-versies"
    mkdir -p "$marker_dir"
    chmod 755 "$marker_dir"
    local hash
    hash=$(sha256sum "$0" 2>/dev/null | awk '{print $1}')
    if [[ -n "$hash" ]]; then
        echo "$hash" > "${marker_dir}/zerotier.sha256"
        chmod 644 "${marker_dir}/zerotier.sha256"
    fi
}

###############################################################################
# 2. Samenvatting
###############################################################################
samenvatting() {
    local zt_ip; zt_ip=$(zerotier-cli listnetworks 2>/dev/null | awk -v id="$ZT_NETWORK_ID" '$0 ~ id {print $NF}')
    zt_ip=${zt_ip:-"onbekend (later: sudo zerotier-cli listnetworks)"}
cat <<EOF

=====================================================================
  KLAAR
=====================================================================

  ZeroTier IP van Pi    : ${zt_ip}
  ZeroTier netwerk-ID   : ${ZT_NETWORK_ID}

  ---------------------------------------------------------------
  ZEROTIER op je andere apparaten:
  ---------------------------------------------------------------
  Installeer de ZeroTier-app op elk apparaat dat toegang nodig heeft
  (Windows, iPhone, Android: zie zerotier.com/download), voer daar
  hetzelfde netwerk-ID in (${ZT_NETWORK_ID}), en keur elk apparaat
  goed op my.zerotier.com onder Members.

  Nextcloud via het ZeroTier-IP van de Pi benaderen (optioneel, alleen
  nodig als je Nextcloud via dat IP wilt bereiken i.p.v. het lokale IP):
     sudo -u www-data php /var/www/html/nextcloud/occ config:system:set trusted_domains 2 --value="${zt_ip}"

  Log: ${LOGFILE}
=====================================================================
EOF
}

###############################################################################
main() {
    welkom
    check_root
    check_netwerk_id
    check_internet
    detect_network
    install_zerotier
    activeer_zerotier
    schrijf_versie_marker
    samenvatting
}
main "$@"
