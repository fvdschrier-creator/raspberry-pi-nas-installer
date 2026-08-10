#!/usr/bin/env bash
###############################################################################
# PiNAS - Adblock (Pi-hole) + versleutelde DNS installer
#
# Installeert NAAST een bestaande PiNAS, zonder iets te breken:
#   - Pi-hole v6            (adblock DNS)          poort 53
#   - Pi-hole webinterface                          poort 8081  (80 = Nextcloud)
#   - dnscrypt-proxy        (DNS-over-HTTPS naar Cloudflare)  lokaal poort 5053
#
# Pi-hole vraagt versleuteld naar Cloudflare via dnscrypt-proxy. Poort 80
# blijft ongemoeid (Apache/Nextcloud). Detecteert bestaande installaties.
#
# Was voorheen gebundeld met ZeroTier in 1 script (pinas_adblock_vpn.sh) -
# gesplitst zodat adblock/DNS en VPN onafhankelijk van elkaar geinstalleerd,
# gecontroleerd en hersteld kunnen worden. Zie pinas_zerotier.sh voor de VPN.
#
# LET OP: eerder gebruikte deze suite cloudflared voor de versleutelde DNS.
# Cloudflare heeft de daarvoor benodigde 'proxy-dns' functie per 2 feb 2026
# definitief verwijderd. dnscrypt-proxy is de door Pi-hole zelf aanbevolen
# vervanger en wordt hier gebruikt.
#
# Gebruik:  sudo bash pinas_pihole.sh
###############################################################################

set -Eeuo pipefail

readonly VERSION="1.0"
readonly LOGFILE="/var/log/pinas_pihole.log"
readonly WEBPORT="8081"                 # Pi-hole webinterface (NIET 80)
readonly CF_PORT="5053"                 # lokale poort van dnscrypt-proxy
readonly DNSCRYPT_CFG="/etc/dnscrypt-proxy/dnscrypt-proxy.toml"

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
  PiNAS - Adblock (Pi-hole) + versleutelde DNS
  Versie ${VERSION}
=====================================================================

  Dit script installeert, NAAST je bestaande NAS:

    1. Pi-hole            - blokkeert reclame/trackers voor je hele netwerk
    2. dnscrypt-proxy      - stuurt je DNS versleuteld naar Cloudflare

  Je NAS (Samba, Nextcloud op poort 80) blijft ongemoeid.
  De Pi-hole webinterface komt op poort ${WEBPORT}.

  VPN (ZeroTier) is een apart onderdeel - zie pinas_zerotier.sh.

  ---------------------------------------------------------------
  BELANGRIJK OM VOORAF TE WETEN:
  ---------------------------------------------------------------
  - Nergens een account nodig - alles draait volledig automatisch.
  - Aan het EINDE toont het script het exacte webadres waar je Pi-hole
    kunt beheren, en het (eenmalig getoonde) wachtwoord daarvoor.

  Duurt ongeveer 3-5 minuten, grotendeels vanzelf.

  Log van deze installatie: ${LOGFILE}

=====================================================================
EOF
pauze
}

check_root() {
    [[ $EUID -eq 0 ]] || { error "Start met: sudo bash pinas_pihole.sh"; exit 1; }
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

check_poorten() {
    log "Poorten controleren..."
    if ss -tulpn 2>/dev/null | grep -q ":${WEBPORT} "; then
        if ss -tulpn 2>/dev/null | grep ":${WEBPORT} " | grep -qi pihole; then
            warn "Poort ${WEBPORT} is al bezet door Pi-hole zelf (van een eerdere, gedeeltelijk geslaagde poging) - dat is prima, ga door."
        else
            error "Poort ${WEBPORT} is al bezet door iets anders dan Pi-hole. Kies bovenin een andere WEBPORT."; exit 1
        fi
    else
        success "Webpoort ${WEBPORT} vrij."
    fi
    # systemd-resolved kan poort 53 blokkeren -> stub uitzetten (standaard bij Pi-hole)
    if ss -tulpn 2>/dev/null | grep -q ':53 ' && systemctl is-active --quiet systemd-resolved; then
        warn "systemd-resolved bezet poort 53 - stub wordt uitgezet (nodig voor Pi-hole)."
        mkdir -p /etc/systemd/resolved.conf.d
        printf '[Resolve]\nDNSStubListener=no\n' > /etc/systemd/resolved.conf.d/pihole.conf
        systemctl restart systemd-resolved
        success "systemd-resolved stub uit."
    else
        success "Poort 53 vrij."
    fi
}

###############################################################################
# 1. dnscrypt-proxy (versleutelde DNS-over-HTTPS naar Cloudflare)
###############################################################################
install_dnscrypt() {
    if dpkg -l dnscrypt-proxy >/dev/null 2>&1; then
        warn "dnscrypt-proxy al aanwezig - installatie overgeslagen."
    else
        log "dnscrypt-proxy installeren (versleutelde DNS)..."
        apt-get update -qq
        apt-get install -y dnscrypt-proxy
        success "dnscrypt-proxy geinstalleerd."
    fi

    log "dnscrypt-proxy instellen (lokaal op poort ${CF_PORT}, upstream Cloudflare)..."
    if [[ ! -f "${DNSCRYPT_CFG}.orig" ]]; then
        cp "$DNSCRYPT_CFG" "${DNSCRYPT_CFG}.orig" 2>/dev/null || true
    fi

    if grep -q '^listen_addresses' "$DNSCRYPT_CFG" 2>/dev/null; then
        sed -i "s|^listen_addresses.*|listen_addresses = ['127.0.0.1:${CF_PORT}']|" "$DNSCRYPT_CFG"
    else
        echo "listen_addresses = ['127.0.0.1:${CF_PORT}']" >> "$DNSCRYPT_CFG"
    fi
    if grep -q '^server_names' "$DNSCRYPT_CFG" 2>/dev/null; then
        sed -i "s|^server_names.*|server_names = ['cloudflare']|" "$DNSCRYPT_CFG"
    else
        echo "server_names = ['cloudflare']" >> "$DNSCRYPT_CFG"
    fi

    # BELANGRIJK: Debian's eigen dnscrypt-proxy.service/.socket gebruiken
    # systemd socket-activatie die HARDGECODEERD op 127.0.2.1:53 luistert,
    # los van bovenstaande config - dat botst met Pi-hole (0.0.0.0:53) en
    # blijft terugkomen bij elke restart, ook na overrides. Daarom draaien
    # we een eigen, simpele dienst die daar helemaal los van staat.
    log "Debian's ingebouwde socket-activatie uitschakelen (voorkomt poortconflict met Pi-hole)..."
    systemctl stop dnscrypt-proxy dnscrypt-proxy.socket 2>/dev/null || true
    systemctl disable dnscrypt-proxy dnscrypt-proxy.socket 2>/dev/null || true
    systemctl mask dnscrypt-proxy.socket 2>/dev/null || true

    cat > /etc/systemd/system/pinas-dnscrypt.service << SERVICE_EOF
[Unit]
Description=PiNAS eigen dnscrypt-proxy dienst (los van Debian socket-activatie)
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/sbin/dnscrypt-proxy -config ${DNSCRYPT_CFG}
Restart=on-failure
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
SERVICE_EOF

    systemctl daemon-reload
    systemctl enable --now pinas-dnscrypt.service
    sleep 2
    if systemctl is-active --quiet pinas-dnscrypt; then
        success "dnscrypt-proxy draait (versleutelde DNS via Cloudflare, eigen dienst)."
    else
        error "dnscrypt-proxy start niet. Check: journalctl -u pinas-dnscrypt"; exit 1
    fi
}

###############################################################################
# 2. Pi-hole
###############################################################################
install_pihole() {
    if command -v pihole >/dev/null 2>&1; then
        warn "Pi-hole al aanwezig - installatie overgeslagen."
        return
    fi
    log "Pi-hole installeren (onbeheerd)..."
    curl -sSL https://install.pi-hole.net -o /tmp/pihole-install.sh
    bash /tmp/pihole-install.sh --unattended
    rm -f /tmp/pihole-install.sh
    success "Pi-hole geinstalleerd."
}

configure_pihole() {
    log "Pi-hole configureren (webpoort ${WEBPORT}, upstream = dnscrypt-proxy)..."
    # Poort verzetten en upstream naar de lokale dnscrypt-proxy. De CLI-syntax
    # van v6 verschilt per versie; we proberen beide vormen, non-fataal.
    pihole-FTL --config webserver.port "${WEBPORT}o,[::]:${WEBPORT}o" 2>/dev/null \
        || pihole-FTL --config webserver.port="${WEBPORT}o" 2>/dev/null \
        || warn "Kon webpoort niet automatisch zetten (val terug op auto: waarschijnlijk 8080)."
    pihole-FTL --config dns.upstreams "[\"127.0.0.1#${CF_PORT}\"]" 2>/dev/null \
        || pihole-FTL --config dns.upstreams="[\"127.0.0.1#${CF_PORT}\"]" 2>/dev/null \
        || warn "Kon upstream niet automatisch zetten - doe dit in de webinterface (127.0.0.1#${CF_PORT})."
    systemctl restart pihole-FTL
    sleep 2
    # Detecteer op welke poort de webinterface echt luistert.
    WEB_ECHT=$(ss -tulpn 2>/dev/null | grep pihole-FTL | grep -oE ":(80|443|${WEBPORT}|8080)[^0-9]" | tr -d ': ' | head -1 || true)
    WEB_ECHT=${WEB_ECHT:-$WEBPORT}
    success "Pi-hole geconfigureerd (webinterface poort ${WEB_ECHT})."

    log "Privacyniveau instellen (domeinen + apparaten verborgen in de query-log)..."
    # Niveau 0 = alles tonen, 1 = domeinen verbergen, 2 = domeinen+apparaten
    # verbergen (gekozen als redelijke middenweg: statistieken blijven
    # bruikbaar, maar geen browsegeschiedenis per apparaat), 3 = geen logging.
    # Wijzig dit later via de webinterface: Instellingen -> Privacy.
    pihole-FTL --config misc.privacylevel 2 2>/dev/null \
        || pihole-FTL --config misc.privacylevel=2 2>/dev/null \
        || warn "Kon privacyniveau niet automatisch zetten - doe dit in de webinterface (Instellingen -> Privacy)."
    systemctl restart pihole-FTL
    sleep 1
    success "Privacyniveau ingesteld (domeinen + apparaten verborgen)."
}

set_pihole_password() {
    log "Wachtwoord voor de Pi-hole webinterface instellen..."
    PIHOLE_PASS=$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 16 || true)
    if pihole setpassword "$PIHOLE_PASS" >/dev/null 2>&1 || pihole -a -p "$PIHOLE_PASS" >/dev/null 2>&1; then
        success "Wachtwoord ingesteld."
    else
        warn "Zet wachtwoord later met: pihole setpassword"
        PIHOLE_PASS="(nog instellen: pihole setpassword)"
    fi
}

schrijf_versie_marker() {
    # Zie pinas_printer.sh voor de volledige uitleg - zelfde mechanisme,
    # 1 marker-bestand per add-on, zodat Addons Beheer kan zien of de Pi
    # nog de nieuwste versie van dit script draait.
    local marker_dir="/etc/pinas-addon-versies"
    mkdir -p "$marker_dir"
    chmod 755 "$marker_dir"
    local hash
    hash=$(sha256sum "$0" 2>/dev/null | awk '{print $1}')
    if [[ -n "$hash" ]]; then
        echo "$hash" > "${marker_dir}/pihole.sha256"
        chmod 644 "${marker_dir}/pihole.sha256"
    fi
}

###############################################################################
# 3. Samenvatting
###############################################################################
samenvatting() {
cat <<EOF

=====================================================================
  KLAAR
=====================================================================

  Pi-hole webinterface : http://${PI_IP}:${WEB_ECHT:-$WEBPORT}/admin
  Pi-hole wachtwoord   : ${PIHOLE_PASS:-al eerder ingesteld}
  (schrijf dit op - het wordt niet opnieuw getoond)

  Nextcloud blijft op   : http://${PI_IP}/nextcloud   (ongemoeid)
  Versleutelde DNS      : dnscrypt-proxy -> Cloudflare (poort ${CF_PORT})
  Privacyniveau         : domeinen + apparaten verborgen in de query-log
                          (wijzigen: Instellingen -> Privacy in de webinterface)

  ---------------------------------------------------------------
  NOG DOEN - in je Deco-app (voor adblock op je HELE netwerk):
  ---------------------------------------------------------------
  Deco-app -> Meer -> Geavanceerd -> DHCP-server:
     Primaire DNS  : ${PI_IP}     (de Pi-hole)
     Secundaire DNS: 1.1.1.1      (fallback: internet blijft werken
                                   als de Pi even uit staat)
  Sla op en herstart je wifi (of wacht tot apparaten opnieuw verbinden).

  Let op: door de fallback lekt soms een reclame door als de Pi
  niet reageert. Dat is de prijs voor 'huis ligt nooit plat'.

  ---------------------------------------------------------------
  Wil je ook via VPN bij je Pi kunnen (thuis en onderweg)?
  Draai dan apart: sudo bash pinas_zerotier.sh
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
    check_poorten
    install_dnscrypt
    install_pihole
    configure_pihole
    set_pihole_password
    schrijf_versie_marker
    samenvatting
}
main "$@"
