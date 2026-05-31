#!/bin/bash
# Raspberry Pi NAS Installer v1.0.0
# ─────────────────────────────────────────────────────────────────────────────
# Pi NAS — Autonome installer / Eerste start
# Automatisch gestart via .bashrc bij eerste SSH-login
# ─────────────────────────────────────────────────────────────────────────────

export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH

# Kleuren
R="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"
CYAN="\033[96m"; GREEN="\033[92m"; YELLOW="\033[93m"
RED="\033[91m"; BLUE="\033[94m"; WHITE="\033[97m"

BOOTFS="/boot/firmware"
HOME_PI="/home/pi"
BASHRC="/home/pi/.bashrc"
MARKER="/home/pi/.nas_installed"

# ── Eerste start detectie ─────────────────────────────────────────────────────
is_eerste_start() {
    [ ! -f "$MARKER" ]
}

# ── Scripts kopiëren vanuit bootfs ────────────────────────────────────────────
kopieer_scripts() {
    local copied=0
    for f in "$BOOTFS"/*.py "$BOOTFS"/*.sh; do
        [ -f "$f" ] || continue
        local base=$(basename "$f")
        [ "$base" = "install.sh" ] && continue  # zichzelf overslaan
        cp "$f" "$HOME_PI/$base"
        chown pi:pi "$HOME_PI/$base"
        chmod 755 "$HOME_PI/$base"
        copied=$((copied+1))
    done
    echo $copied
}

# ── Welkomstmenu instellen ────────────────────────────────────────────────────
installeer_welkomstmenu() {
    # Voeg toe aan .bashrc als nog niet aanwezig
    if ! grep -q "pi_welkom.sh" "$BASHRC" 2>/dev/null; then
        echo "" >> "$BASHRC"
        echo "# Pi NAS welkomstmenu" >> "$BASHRC"
        echo "source /home/pi/pi_welkom.sh" >> "$BASHRC"
    fi
}

# ── Eerste start scherm ───────────────────────────────────────────────────────
eerste_start_scherm() {
    clear
    echo -e "\n${CYAN}${BOLD}"
    echo "  ╔══════════════════════════════════════════════╗"
    echo "  ║   🍓  Raspberry Pi NAS — Eerste installatie  ║"
    echo "  ╠══════════════════════════════════════════════╣"
    echo "  ║                                              ║"
    echo "  ║   Welkom! Scripts worden klaargezet...       ║"
    echo "  ║                                              ║"
    echo "  ╚══════════════════════════════════════════════╝"
    echo -e "${R}\n"

    # Scripts kopiëren
    echo -e "  ${CYAN}Scripts kopiëren vanuit SD-kaart...${R}"
    local n=$(kopieer_scripts)
    echo -e "  ${GREEN}✔  $n script(s) klaargezet${R}"
    echo ""

    # Welkomstmenu instellen
    installeer_welkomstmenu
    echo -e "  ${GREEN}✔  Welkomstmenu ingesteld${R}"
    echo ""

    # Keuzemenu
    echo -e "  ${WHITE}${BOLD}Wat wil je doen?${R}\n"
    echo -e "  ${CYAN}${BOLD}1${R}  🚀  Automatische installatie"
    echo -e "     ${DIM}Alles in één keer instellen: schijf, Samba, FileBrowser${R}"
    echo ""
    echo -e "  ${CYAN}${BOLD}2${R}  🔧  NAS Installer (handmatig)"
    echo -e "     ${DIM}Stap voor stap via het installatiemenu${R}"
    echo ""
    echo -e "  ${CYAN}${BOLD}3${R}  📥  Configuratie importeren"
    echo -e "     ${DIM}Herstel vanuit eerdere export (Pi-wissel/herinstallatie)${R}"
    echo ""
    echo -e "  ${CYAN}${BOLD}4${R}  💻  Gewone terminal"
    echo -e "     ${DIM}Niets installeren, direct naar commandoregel${R}"
    echo ""

    read -p "  Keuze (1-4): " keuze
    echo ""

    case $keuze in
        1) auto_install ;;
        2)
            touch "$MARKER"
            source "$HOME_PI/pi_welkom.sh"
            sudo python3 "$HOME_PI/nas_installer_cli.py"
            ;;
        3)
            touch "$MARKER"
            sudo python3 "$HOME_PI/nas_config.py"
            ;;
        4)
            touch "$MARKER"
            echo -e "  ${DIM}Typ 'menu' voor het welkomstmenu.${R}\n"
            source "$HOME_PI/pi_welkom.sh"
            return
            ;;
        *)
            touch "$MARKER"
            source "$HOME_PI/pi_welkom.sh"
            ;;
    esac
}

# ── Automatische installatie ──────────────────────────────────────────────────
auto_install() {
    clear
    echo -e "\n${GREEN}${BOLD}"
    echo "  ╔══════════════════════════════════════════════╗"
    echo "  ║   🚀  Automatische NAS installatie           ║"
    echo "  ╚══════════════════════════════════════════════╝"
    echo -e "${R}\n"

    # Netwerk
    local ip=$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^(192|10|172)' | head -1)
    if [ -n "$ip" ]; then
        echo -e "  ${GREEN}✔  Netwerk: $ip${R}"
    else
        echo -e "  ${YELLOW}Geen netwerk gevonden.${R}"
        echo -e "  WiFi instellen:\n"
        read -p "  WiFi SSID (leeg = UTP gebruiken): " WIFI_SSID
        if [ -n "$WIFI_SSID" ]; then
            read -s -p "  WiFi wachtwoord: " WIFI_PASS
            echo ""
            sudo nmcli dev wifi connect "$WIFI_SSID" password "$WIFI_PASS" 2>/dev/null
            sleep 2
            ip=$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^(192|10|172)' | head -1)
            [ -n "$ip" ] && echo -e "  ${GREEN}✔  Verbonden: $ip${R}" || echo -e "  ${YELLOW}⚠  Verbinding mislukt — ga verder met UTP${R}"
        fi
    fi
    echo ""

    # SSH
    sudo systemctl enable ssh 2>/dev/null
    sudo systemctl start ssh 2>/dev/null
    echo -e "  ${GREEN}✔  SSH ingeschakeld${R}"

    # Schijf detecteren
    echo ""
    echo -e "  ${BLUE}Beschikbare schijven:${R}"
    lsblk -o NAME,SIZE,TYPE -rn | grep disk | while read line; do
        echo -e "  ${DIM}  /dev/$line${R}"
    done
    echo ""

    # Standaard schijf bepalen
    SCHIJF=$(lsblk -o NAME,TYPE -rn | grep disk | grep -v mmcblk | head -1 | awk '{print "/dev/"$1}')
    read -p "  Schijf voor NAS [$SCHIJF]: " input
    [ -n "$input" ] && SCHIJF=$input
    echo ""

    # Mountpunt
    MOUNT="/mnt/opslag"
    read -p "  Mountpunt [$MOUNT]: " input
    [ -n "$input" ] && MOUNT=$input

    # Formatteren
    echo ""
    echo -e "  ${YELLOW}Schijf formatteren als ext4?${R}"
    echo -e "  ${DIM}(Wist alle data op $SCHIJF)${R}"
    read -p "  Formatteren? [j/N]: " FMT
    echo ""

    # NAS-instellingen
    SHARE="Opslag"
    read -p "  Naam gedeelde map [$SHARE]: " input
    [ -n "$input" ] && SHARE=$input

    NASUSER="pi"
    read -p "  Gebruikersnaam [$NASUSER]: " input
    [ -n "$input" ] && NASUSER=$input

    while true; do
        read -s -p "  Wachtwoord (min. 6 tekens): " NASPASS; echo ""
        read -s -p "  Wachtwoord (herhaal): " NASPASS2; echo ""
        [ "$NASPASS" = "$NASPASS2" ] && [ ${#NASPASS} -ge 6 ] && break
        echo -e "  ${RED}Wachtwoorden komen niet overeen of te kort.${R}"
    done
    echo ""

    # Bevestiging
    echo -e "  ${CYAN}${BOLD}Samenvatting:${R}"
    echo -e "  Schijf:    $SCHIJF"
    echo -e "  Mountpunt: $MOUNT"
    echo -e "  Formatteren: $([ "$FMT" =~ ^[jJyY] ] && echo 'ja' || echo 'nee')"
    echo -e "  Share-naam: $SHARE"
    echo -e "  Gebruiker:  $NASUSER"
    echo ""
    read -p "  Starten? [J/n]: " BEVESTIG
    [[ "$BEVESTIG" =~ ^[nN] ]] && echo -e "  ${YELLOW}Geannuleerd.${R}" && return
    echo ""

    # Uitvoeren
    echo -e "  ${CYAN}Bijwerken...${R}"
    sudo apt-get update -y -q && sudo apt-get upgrade -y -q
    echo -e "  ${GREEN}✔  Bijgewerkt${R}"

    # Schijf
    if [[ "$FMT" =~ ^[jJyY] ]]; then
        echo -e "  ${CYAN}Formatteren...${R}"
        sudo wipefs -a "$SCHIJF" 2>/dev/null
        sudo mkfs.ext4 -F "$SCHIJF"
        sudo partprobe "$SCHIJF" 2>/dev/null
        sudo udevadm settle
        echo -e "  ${GREEN}✔  Geformatteerd${R}"
    fi

    sudo mkdir -p "$MOUNT"
    UUID=$(sudo blkid -s UUID -o value "$SCHIJF")
    if [ -n "$UUID" ]; then
        FSTAB="UUID=$UUID  $MOUNT  ext4  defaults,nofail  0  2"
        grep -q "$UUID" /etc/fstab || echo "$FSTAB" | sudo tee -a /etc/fstab > /dev/null
        sudo mount -a
        sudo chown -R pi:pi "$MOUNT"
        sudo chmod -R 775 "$MOUNT"
        echo -e "  ${GREEN}✔  Schijf gekoppeld op $MOUNT${R}"
    else
        echo -e "  ${YELLOW}⚠  Geen UUID — schijf mogelijk niet herkend${R}"
    fi

    # Systemd rechten service
    cat > /tmp/nas-rechten.service << EOF
[Unit]
Description=NAS schijf rechten instellen
After=local-fs.target
Requires=local-fs.target
[Service]
Type=oneshot
ExecStart=/bin/bash -c 'chown -R pi:pi $MOUNT && chmod -R 775 $MOUNT'
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
EOF
    sudo cp /tmp/nas-rechten.service /etc/systemd/system/nas-rechten.service
    sudo systemctl daemon-reload
    sudo systemctl enable nas-rechten.service 2>/dev/null
    echo -e "  ${GREEN}✔  Rechten service ingesteld${R}"

    # Samba
    echo -e "  ${CYAN}Samba installeren...${R}"
    sudo apt-get install -y samba samba-common-bin -q
    SMB_BLOCK="
[$SHARE]
   comment = Pi NAS
   path = $MOUNT
   browseable = yes
   writable = yes
   valid users = $NASUSER
   create mask = 0664
   directory mask = 0775
   force user = $NASUSER"
    echo "$SMB_BLOCK" | sudo tee -a /etc/samba/smb.conf > /dev/null
    (echo "$NASPASS"; echo "$NASPASS") | sudo smbpasswd -a "$NASUSER" -s
    sudo systemctl restart smbd
    sudo systemctl enable smbd
    echo -e "  ${GREEN}✔  Samba ingesteld${R}"

    # Cockpit
    echo -e "  ${CYAN}Cockpit installeren...${R}"
    sudo apt-get install -y cockpit -q
    sudo systemctl enable cockpit
    sudo systemctl start cockpit
    echo -e "  ${GREEN}✔  Cockpit ingesteld${R}"

    # FileBrowser
    echo -e "  ${CYAN}FileBrowser installeren...${R}"
    curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash > /dev/null 2>&1
    cat > /tmp/filebrowser.service << EOF
[Unit]
Description=FileBrowser NAS
After=network.target
[Service]
ExecStart=/usr/local/bin/filebrowser -r /mnt -a 0.0.0.0 -p 8080 -d /home/pi/filebrowser.db
Restart=always
User=pi
[Install]
WantedBy=multi-user.target
EOF
    sudo cp /tmp/filebrowser.service /etc/systemd/system/filebrowser.service
    sudo systemctl daemon-reload
    sudo systemctl enable filebrowser
    sudo systemctl start filebrowser
    echo -e "  ${GREEN}✔  FileBrowser ingesteld${R}"

    # Welkomstmenu
    installeer_welkomstmenu
    echo -e "  ${GREEN}✔  Welkomstmenu ingesteld${R}"

    # Configuratie exporteren
    if [ -f "$HOME_PI/nas_config.py" ]; then
        sudo python3 "$HOME_PI/nas_config.py" export 2>/dev/null || true
    fi

    # Marker plaatsen
    touch "$MARKER"

    # Klaar
    local ip_now=$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^(192|10|172)' | head -1)
    echo ""
    echo -e "${GREEN}${BOLD}"
    echo "  ╔══════════════════════════════════════════════╗"
    echo "  ║   ✅  NAS installatie voltooid!              ║"
    echo "  ╠══════════════════════════════════════════════╣"
    echo -e "  ║   IP-adres:  $ip_now"
    echo -e "  ║   Windows:   \\\\\\\\$ip_now\\\\$SHARE"
    echo -e "  ║   FileBrowser: http://$ip_now:8080"
    echo -e "  ║   Cockpit:     http://$ip_now:9090"
    echo "  ╠══════════════════════════════════════════════╣"
    echo "  ║   Typ 'menu' voor het welkomstmenu           ║"
    echo "  ╚══════════════════════════════════════════════╝"
    echo -e "${R}\n"

    source "$HOME_PI/pi_welkom.sh"
}

# ── Hoofd ─────────────────────────────────────────────────────────────────────
# Alleen in interactieve sessie
if [[ $- == *i* ]]; then
    if is_eerste_start; then
        eerste_start_scherm
    fi
fi
