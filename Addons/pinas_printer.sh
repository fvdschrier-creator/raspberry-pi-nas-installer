#!/usr/bin/env bash
###############################################################################
# pinas_printer.sh - Pi NAS Suite - Addon: Printserver (CUPS + AirPrint)
#
# Maakt van de Pi een netwerk-printserver:
#   - CUPS               (de printserver zelf)         webinterface poort 631
#   - AirPrint / IPP     (printen vanaf iPhone/iPad/Android, thuis)
#   - USB-printer delen  EN netwerkprinters toevoegen  (beide via CUPS)
#
# Toegang:
#   - Thuis          : http://<Pi-IP>:631  (beheer) en direct printen
#   - Onderweg       : via ZeroTier (zelfde als Nextcloud/statuspagina) -
#                      GEEN open poort naar internet. Je telefoon moet dan
#                      met het ZeroTier-netwerk verbonden zijn.
#
# Veilig naast de NAS: poort 631 is niet in gebruik door iets anders op de Pi
# (Samba 445, Nextcloud/Apache 80, Pi-hole-web 8081, statuspagina 8090).
#
# Idempotent-vriendelijk: nogmaals draaien is veilig (herconfigureert alleen).
#
# Gebruik: sudo bash pinas_printer.sh
###############################################################################

set -Eeuo pipefail

readonly VERSION="1.0"
readonly LOGFILE="/var/log/pinas_printer.log"
readonly CUPS_PORT="631"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

mkdir -p /var/log; touch "$LOGFILE"; chmod 600 "$LOGFILE"
exec > >(tee >(sed -r 's/\x1b\[[0-9;]*m//g' >> "$LOGFILE")) 2>&1

log()     { echo; echo -e "${BLUE}[$(date '+%F %T')]${NC} $1"; }
success() { echo -e "${GREEN}OK: $1${NC}"; }
warn()    { echo -e "${YELLOW}LET OP: $1${NC}"; }
error()   { echo -e "${RED}FOUT: $1${NC}"; }
on_error(){ error "Afgebroken op regel $1. Log: $LOGFILE"; exit 1; }
trap 'on_error $LINENO' ERR

check_root() {
    [[ $EUID -eq 0 ]] || { error "Start met: sudo bash pinas_printer.sh"; exit 1; }
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
    [[ -n "${PI_IP:-}" ]] || PI_IP="<Pi-IP>"
    success "IP van deze Pi: $PI_IP"
}

install_cups() {
    log "CUPS + AirPrint installeren (kan enkele minuten duren)..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    # cups            = de printserver
    # printer-driver-* = brede driverset (gutenprint dekt de meeste printers)
    # avahi-daemon    = maakt AirPrint/Bonjour-detectie mogelijk (telefoons)
    # cups-ipp-utils  = IPP-gereedschap (AirPrint)
    apt-get install -y cups printer-driver-gutenprint printer-driver-all \
                       avahi-daemon cups-ipp-utils >/dev/null
    success "CUPS en drivers geinstalleerd."
}

configure_cups() {
    log "CUPS configureren voor netwerktoegang (lokaal + ZeroTier)..."

    # De gebruiker 'pi' mag printers beheren (lid van groep lpadmin)
    usermod -aG lpadmin pi 2>/dev/null || true

    # CUPS standaard laat alleen localhost toe. We zetten hem open voor het
    # LOKALE netwerk en ZeroTier - NIET naar het publieke internet (dat loopt
    # via ZeroTier, geen open poort). WebInterface staat op Raspberry Pi OS/
    # Debian standaard UIT (los van --remote-admin/--remote-any/
    # --share-printers, die de webinterface NIET aanzetten) - zonder deze
    # regel kreeg je "Web Interface is Disabled" op poort 631, ook al draaide
    # CUPS zelf prima (26 juli 2026, gevonden door Frans na de eerste
    # installatie).
    cupsctl --remote-admin --remote-any --share-printers WebInterface=yes
    # 'listen' op alle interfaces zodat ZeroTier-clients er ook bij kunnen
    if ! grep -q "^Listen \*:${CUPS_PORT}" /etc/cups/cupsd.conf; then
        sed -i "s/^Listen localhost:${CUPS_PORT}/Listen *:${CUPS_PORT}/" /etc/cups/cupsd.conf || true
        grep -q "^Port ${CUPS_PORT}" /etc/cups/cupsd.conf || \
            grep -q "^Listen \*:${CUPS_PORT}" /etc/cups/cupsd.conf || \
            echo "Listen *:${CUPS_PORT}" >> /etc/cups/cupsd.conf
    fi

    systemctl enable --now cups >/dev/null 2>&1 || systemctl restart cups
    systemctl enable --now avahi-daemon >/dev/null 2>&1 || true
    systemctl restart cups
    sleep 2
    if systemctl is-active --quiet cups; then
        success "CUPS draait (webinterface: http://${PI_IP}:${CUPS_PORT})."
    else
        error "CUPS start niet. Check: journalctl -u cups"; exit 1
    fi
}

schrijf_versie_marker() {
    # Legt een SHA256-afdruk van DIT script neer op de Pi, zodat Addons
    # Beheer (Windows-kant) straks kan zien of de Pi nog de nieuwste versie
    # draait, of dat het lokale bestand in C:\PiNAS\Addons ondertussen is
    # bijgewerkt en opnieuw geinstalleerd moet worden (30 juli 2026, wens
    # Frans: "waarom geeft de suite nergens aan dat dit een wijziging is").
    # Map moet 755 zijn (niet 700) - anders kan de mobiele-statuspagina/
    # Addons Beheer-check (die als gebruiker 'pi' leest, niet als root) de
    # marker niet lezen, zelfde les als eerder bij Vaultwarden's CA_DIR.
    local marker_dir="/etc/pinas-addon-versies"
    mkdir -p "$marker_dir"
    chmod 755 "$marker_dir"
    local hash
    hash=$(sha256sum "$0" 2>/dev/null | awk '{print $1}')
    if [[ -n "$hash" ]]; then
        echo "$hash" > "${marker_dir}/printer.sha256"
        chmod 644 "${marker_dir}/printer.sha256"
    fi
}

print_summary() {
cat <<EOF

=====================================================================
  PRINTSERVER KLAAR
=====================================================================
  Beheer (browser)  : http://${PI_IP}:${CUPS_PORT}
     Log in als gebruiker 'pi' met je Pi-wachtwoord voor beheer.

  PRINTER TOEVOEGEN (eenmalig):
    1. Open http://${PI_IP}:${CUPS_PORT} in je browser.
    2. Ga naar 'Administration' -> 'Add Printer'.
    3. Netwerkprinter: kies de regel met '(driverless)' erbij onder
       'Discovered Network Printers' (dit is IPP Everywhere). Staat het
       Connection-veld verkeerd ingevuld, typ dan zelf het IP-adres van
       de PRINTER zelf (niet van de Pi) in als ipp://<printer-IP>/ipp/print.
    4. Naam: bijv. 'Epson_ET8550'. Vink 'Share This Printer' aan.
    5. Bij merk/model: kies 'Generic' -> 'IPP Everywhere' voor de beste
       compatibiliteit.
    6. WIL JE OOK ONDERWEG PRINTEN VIA ZEROTIER: herhaal stap 2-5 nog
       een keer voor DEZELFDE fysieke printer, met een naam die eindigt
       op '_onderweg' (bijv. 'Epson_ET8550_onderweg'). Dit is nodig omdat
       1 naam met 2 adressen niet betrouwbaar bleek op iOS.

  PRINTEN VANAF TELEFOON (AirPrint/IPP):
    - THUIS: de printer verschijnt vanzelf in het print-menu van je
      iPhone/iPad (AirPrint) of Android (IPP/Mopria).
    - ONDERWEG (ZONDER wifi, via ZeroTier): bevestigd werkend (27 juli
      2026), maar vereist EENMALIG, VOORAF, THUIS twee dingen:
        a) De 'Epson_ET8550_onderweg'-wachtrij hierboven aangemaakt.
        b) Installeer de gratis Epson Smart Panel-app en koppel de
           printer er EEN KEER mee (via Wi-Fi Direct/QR-code op het
           display van de printer, terwijl je gewoon thuis op wifi zit).
      Download daarna het AirPrint-profiel via de mobiele statuspagina
      (Addons Beheer -> Mobiele statuspagina moet geinstalleerd zijn) en
      installeer het op je iPhone/iPad. Zonder de Smart Panel-koppeling
      bleek printen zonder wifi consequent te mislukken ("Geen
      AirPrint-printers gevonden"), ook met een correct profiel - de
      koppeling lijkt iets in iOS te "ontgrendelen". De precieze
      technische reden is niet met zekerheid vastgesteld, alleen het
      herhaalde verband tussen wel/niet gekoppeld en wel/niet werkend.
    - ALTERNATIEF, buiten de suite om: Epson Connect (Email Print /
      Remote Print via de Epson iPrint-app) - Epson's eigen clouddienst,
      werkt via gewoon internet, los van ZeroTier/de Pi.
      Er is BEWUST geen open poort naar internet - dat is veiliger.

  Log: ${LOGFILE}
=====================================================================
EOF
}

main() {
    echo "PiNAS Printserver installer v${VERSION}"
    check_root
    check_internet
    detect_network
    install_cups
    configure_cups
    schrijf_versie_marker
    print_summary
}
main "$@"
