#!/bin/bash
# Raspberry Pi NAS Installer v1.0.0
# ─────────────────────────────────────────────────────────────────────────────
# Pi Welkomstmenu — start automatisch bij inloggen
# ─────────────────────────────────────────────────────────────────────────────

# PATH veiligstellen — voorkomt 'command not found' fouten
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH

# Kleuren
R="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"
CYAN="\033[96m"; GREEN="\033[92m"; YELLOW="\033[93m"
RED="\033[91m"; BLUE="\033[94m"; WHITE="\033[97m"

# ── Helpers ───────────────────────────────────────────────────────────────────
pi_ip() {
    hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^(192|10|172)' | head -1
}

fb_running() {
    pgrep -x filebrowser &>/dev/null && echo "aan" || echo "uit"
}

samba_running() {
    systemctl is-active smbd &>/dev/null && echo "aan" || echo "uit"
}

update_beschikbaar() {
    # Kijk of er nieuwe/andere bestanden in bootfs staan
    local count=0
    for f in /boot/firmware/*.py /boot/firmware/*.sh; do
        [ -f "$f" ] || continue
        local base=$(basename "$f")
        local dest="/home/pi/$base"
        if [ ! -f "$dest" ] || ! diff -q "$f" "$dest" &>/dev/null; then
            count=$((count+1))
        fi
    done
    echo $count
}

# ── Welkomstscherm ────────────────────────────────────────────────────────────
pi_welkom_toon() {
    clear
    local ip=$(pi_ip)
    local fb=$(fb_running)
    local smb=$(samba_running)
    local updates=$(update_beschikbaar)

    echo -e "\n${CYAN}${BOLD}  🍓  Raspberry Pi NAS — piNAS${R}"
    echo -e "  ${DIM}$(date '+%A %d %B %Y  %H:%M')${R}"
    echo -e "  ${DIM}──────────────────────────────────────${R}\n"

    # Status
    echo -e "  ${BLUE}Status:${R}"
    if [ -n "$ip" ]; then
        echo -e "  📡  IP-adres    ${GREEN}${BOLD}$ip${R}"
    else
        echo -e "  📡  IP-adres    ${YELLOW}niet verbonden${R}"
    fi
    echo -e "  💾  Samba       $([ "$smb" = "aan" ] && echo "${GREEN}aan${R}" || echo "${YELLOW}uit${R}")"
    echo -e "  🌐  FileBrowser $([ "$fb" = "aan" ] && echo "${GREEN}aan  →  http://$ip:8080${R}" || echo "${YELLOW}uit${R}")"

    # Schijf
    local mount=$(df -h /mnt/opslag 2>/dev/null | tail -1)
    if [ -n "$mount" ]; then
        local used=$(echo $mount | awk '{print $3}')
        local avail=$(echo $mount | awk '{print $4}')
        local pct=$(echo $mount | awk '{print $5}')
        echo -e "  💽  Opslag      ${GREEN}${used} gebruikt, ${avail} vrij (${pct})${R}"
    else
        echo -e "  💽  Opslag      ${YELLOW}niet gemount${R}"
    fi

    # Update beschikbaar?
    if [ "$updates" -gt 0 ]; then
        echo -e "\n  ${YELLOW}${BOLD}  ⬆  $updates nieuw(e) script(s) beschikbaar in /boot/firmware/${R}"
    fi

    echo -e "\n  ${DIM}──────────────────────────────────────${R}\n"

    # Menu
    echo -e "  ${WHITE}${BOLD}Wat wil je doen?${R}\n"
    # Backup status
    local backup_info=""
    if [ -f /home/pi/backup_status.json ] 2>/dev/null; then
        backup_info=$(python3 -c "
import json,datetime
try:
    d=json.load(open('/home/pi/backup_status.json'))
    l=d.get('laatste',{})
    if l:
        dt=datetime.datetime.strptime(l['datum'],'%Y-%m-%d %H:%M:%S')
        age=(datetime.datetime.now()-dt).days
        warn=' ⚠  '+str(age)+' dagen geleden!' if age>=7 else ' ('+str(age)+' dagen geleden)'
        print(l['datum']+warn)
except: pass
" 2>/dev/null)
    fi

    echo -e "  ${CYAN}${BOLD}1${R}  🔧  NAS Installer"
    echo -e "     ${DIM}Schijven beheren, Samba/Nextcloud installeren${R}"
    echo -e ""
    if [ "$fb" = "aan" ]; then
        echo -e "  ${CYAN}${BOLD}2${R}  🌐  FileBrowser stoppen"
        echo -e "     ${GREEN}Actief op http://$ip:8080${R}"
    else
        echo -e "  ${CYAN}${BOLD}2${R}  🌐  FileBrowser starten"
        echo -e "     ${DIM}Start de webinterface voor bestandsbeheer${R}"
    fi
    echo -e ""
    echo -e "  ${CYAN}${BOLD}3${R}  💾  Backup"
    if [ -n "$backup_info" ]; then
        echo -e "     Laatste: ${YELLOW}$backup_info${R}"
    else
        echo -e "     ${YELLOW}Nog geen backup gemaakt${R}"
    fi
    echo -e ""
    echo -e "  ${CYAN}${BOLD}4${R}  📊  Status & diagnose"
    echo -e "     ${DIM}Schijfgebruik, netwerk, services bekijken${R}"
    echo -e ""
    if [ "$updates" -gt 0 ]; then
        echo -e "  ${YELLOW}${BOLD}5${R}  ⬆  Scripts bijwerken vanuit SD-kaart"
        echo -e "     ${YELLOW}$updates bestand(en) in /boot/firmware/ zijn nieuwer${R}"
        echo -e ""
    else
        echo -e "  ${CYAN}${BOLD}5${R}  ⬆  Scripts bijwerken vanuit SD-kaart"
        echo -e "     ${DIM}Kopieer nieuwe scripts van /boot/firmware/ naar /home/pi/${R}"
        echo -e ""
    fi
    echo -e "  ${CYAN}${BOLD}6${R}  🚪  Pi afsluiten"
    echo -e "     ${DIM}Netjes afsluiten (wacht daarna 30 sec voor schijf uit)${R}"
    echo -e ""
    echo -e "  ${CYAN}${BOLD}7${R}  💻  Gewone terminal"
    echo -e "     ${DIM}Direct naar de commandoregel${R}"
    echo -e ""
    # Seagate status bepalen
    SEAGATE_STATUS=$(seagate_status)
    if [ "$SEAGATE_STATUS" = "aan" ]; then
        echo -e "  ${CYAN}${BOLD}8${R}  🔌  Seagate uitzetten  ${GREEN}(nu: aan)${R}"
    else
        echo -e "  ${CYAN}${BOLD}8${R}  🔌  Seagate aanzetten  ${DIM}(nu: uit)${R}"
    fi
    echo -e ""
    echo -e "  ${CYAN}${BOLD}9${R}  🔒  Uitloggen / sessie vergrendelen"
    echo -e "     ${DIM}SSH sessie beëindigen en VNC vergrendelen${R}"
    echo -e ""
    echo -e "  ${DIM}Of typ een commando en druk Enter.${R}\n"
}

# ── Menu afhandeling ──────────────────────────────────────────────────────────

# ── Smart Plug / Seagate functies ───────────────────────────────────────
PLUG_CONFIG="/home/pi/smart_plug_config.json"

seagate_aan() {
    if [ ! -f "$PLUG_CONFIG" ]; then
        echo -e "  ${YELLOW}Smart plug niet geconfigureerd. Gebruik NAS installer → Beheer${R}"
        return 1
    fi
    echo -e "  ${CYAN}Seagate aanzetten...${R}"
    python3 /home/pi/smart_plug.py aan 2>/dev/null
    MOUNT=$(python3 -c "import json; c=json.load(open('$PLUG_CONFIG')); print(c.get('seagate_mount','/mnt/backup'))" 2>/dev/null || echo "/mnt/backup")
    if mountpoint -q "$MOUNT"; then
        echo -e "  ${GREEN}OK  Seagate aan en gemount op $MOUNT${R}"
    else
        echo -e "  ${YELLOW}!   Seagate aan maar nog niet gemount - wacht even en probeer opnieuw${R}"
    fi
}

seagate_uit() {
    if [ ! -f "$PLUG_CONFIG" ]; then
        echo -e "  ${YELLOW}Smart plug niet geconfigureerd.${R}"
        return 1
    fi
    echo -e "  ${CYAN}Seagate uitzetten...${R}"
    python3 /home/pi/smart_plug.py uit 2>/dev/null
    echo -e "  ${GREEN}OK  Seagate uitgezet${R}"
}

seagate_status() {
    if [ ! -f "$PLUG_CONFIG" ]; then echo "onbekend"; return; fi
    python3 -c "
import sys; sys.path.insert(0,'/home/pi')
try:
    from smart_plug import plug_status
    s = plug_status()
    print('aan' if s else 'uit' if s is not None else 'onbekend')
except: print('onbekend')
" 2>/dev/null
}

pi_welkom_keuze() {
    while true; do
        pi_welkom_toon
        read -p "  Keuze (1-9): " keuze
        echo ""

        case $keuze in
            1)
                # Start GUI als desktop beschikbaar is, anders CLI
                if python3 -c "import tkinter" 2>/dev/null && [ -n "$DISPLAY" ]; then
                    echo -e "  ${CYAN}GUI-installer starten...${R}\n"
                    sudo python3 /home/pi/nas_installer.py
                    EXIT_CODE=$?
                    if [ $EXIT_CODE -ne 0 ]; then
                        echo -e "\n  ${YELLOW}⚠  GUI-installer gestopt (exitcode $EXIT_CODE).${R}"
                        echo -e "  ${CYAN}Tekstversie beschikbaar als alternatief.${R}"
                        read -p "  Tekstversie starten? [J/n]: " fallback
                        if [[ ! "$fallback" =~ ^[nN] ]]; then
                            sudo python3 /home/pi/nas_installer_cli.py
                        fi
                    fi
                else
                    echo -e "  ${CYAN}NAS Installer starten...${R}\n"
                    sudo python3 /home/pi/nas_installer_cli.py
                fi
                ;;
            2)
                local ip=$(pi_ip)
                local fb=$(fb_running)
                if [ "$fb" = "aan" ]; then
                    echo -e "  ${CYAN}FileBrowser stoppen...${R}"
                    sudo systemctl stop filebrowser 2>/dev/null || pkill filebrowser
                    sleep 1
                    echo -e "  ${GREEN}✔  FileBrowser gestopt.${R}"
                else
                    echo -e "  ${CYAN}FileBrowser starten...${R}"
                    if systemctl is-enabled filebrowser &>/dev/null; then
                        sudo systemctl start filebrowser
                        sleep 1
                        echo -e "  ${GREEN}✔  Gestart op http://$ip:8080${R}"
                        echo -e "  ${DIM}Gebruikersnaam: admin${R}"
                    else
                        echo -e "  ${YELLOW}FileBrowser niet als service ingesteld.${R}"
                        echo -e "  Installeer via NAS Installer → optie 4 FileBrowser${R}"
                    fi
                fi
                read -p "  Druk Enter om terug te gaan..." dummy
                ;;
            3)
                echo -e "  ${CYAN}Backup starten...${R}\n"
                sudo python3 /home/pi/nas_backup.py
                ;;
            4)
                clear
                echo -e "\n${CYAN}${BOLD}  📊 Status & diagnose${R}\n"
                echo -e "  ${BLUE}── Schijven ──${R}"
                lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT
                echo ""
                echo -e "  ${BLUE}── Schijfgebruik ──${R}"
                df -h | grep -E "Filesystem|mnt|/$"
                echo ""
                echo -e "  ${BLUE}── Services ──${R}"
                for svc in smbd nmbd cockpit filebrowser; do
                    status=$(systemctl is-active $svc 2>/dev/null)
                    if [ "$status" = "active" ]; then
                        echo -e "  ${GREEN}✔  $svc${R}"
                    else
                        echo -e "  ${DIM}✗  $svc (niet actief)${R}"
                    fi
                done
                echo ""
                echo -e "  ${BLUE}── Netwerk ──${R}"
                echo -e "  IP: $(pi_ip)"
                echo -e "  Hostname: $(hostname)"
                echo ""
                read -p "  Druk Enter om terug te gaan..." dummy
                ;;
            5)
                clear
                echo -e "\n${CYAN}${BOLD}  ⬆  Scripts bijwerken vanuit SD-kaart (/boot/firmware/)${R}\n"
                local copied=0
                local skipped=0
                for f in /boot/firmware/*.py /boot/firmware/*.sh; do
                    [ -f "$f" ] || continue
                    local base=$(basename "$f")
                    local dest="/home/pi/$base"
                    if [ ! -f "$dest" ]; then
                        cp "$f" "$dest" && chmod +x "$dest" 2>/dev/null
                        echo -e "  ${GREEN}✔  Nieuw: $base${R}"
                        copied=$((copied+1))
                    elif ! diff -q "$f" "$dest" &>/dev/null; then
                        cp "$f" "$dest" && chmod +x "$dest" 2>/dev/null
                        echo -e "  ${GREEN}✔  Bijgewerkt: $base${R}"
                        copied=$((copied+1))
                    else
                        echo -e "  ${DIM}✓  Ongewijzigd: $base${R}"
                        skipped=$((skipped+1))
                    fi
                done
                echo ""
                if [ $copied -gt 0 ]; then
                    echo -e "  ${GREEN}${BOLD}$copied bestand(en) bijgewerkt.${R}"
                else
                    echo -e "  ${GREEN}Alles al up-to-date.${R}"
                fi
                read -p "  Druk Enter om terug te gaan..." dummy
                ;;
            6)
                echo -e "  ${YELLOW}Pi wordt afgesloten...${R}"
                echo -e "  ${DIM}Wacht ~30 seconden na het afsluiten voor je de schijf uitzet.${R}\n"
                read -p "  Zeker weten? [j/N]: " confirm
                if [[ "$confirm" =~ ^[jJyY] ]]; then
                    sudo shutdown -h now
                else
                    echo -e "  ${DIM}Geannuleerd.${R}"
                fi
                ;;
            7|"")
                echo -e "  ${DIM}Typ 'menu' om het welkomstmenu opnieuw te tonen.${R}\n"
                return
                ;;
            8)
                if [ "$(seagate_status 2>/dev/null)" = "aan" ]; then
                    seagate_uit
                else
                    seagate_aan
                fi
                read -p "  Druk Enter om terug te gaan..." dummy
                PI_WELKOM_GETOOND=
                ;;
            9)
                echo -e "  ${YELLOW}Uitloggen...${R}"
                # VNC vergrendelen als beschikbaar
                if command -v xdg-screensaver &>/dev/null && [ -n "$DISPLAY" ]; then
                    xdg-screensaver lock 2>/dev/null
                    echo -e "  ${GREEN}VNC sessie vergrendeld.${R}"
                elif command -v lxlock &>/dev/null; then
                    lxlock 2>/dev/null
                    echo -e "  ${GREEN}Scherm vergrendeld.${R}"
                fi
                # SSH sessie beëindigen
                echo -e "  ${DIM}SSH sessie beëindigd. Tot ziens!${R}\n"
                export PI_WELKOM_GETOOND=
                kill -HUP $PPID 2>/dev/null || exit 0
                ;;
            *)
                # Onbekende invoer — gewoon als commando uitvoeren
                eval "$keuze"
                read -p "  Druk Enter om terug te gaan..." dummy
                ;;
        esac
    done
}

# ── Automatisch bijwerken vanuit bootfs ──────────────────────────────────────
auto_update_scripts() {
    local copied=0
    for f in /boot/firmware/*.py /boot/firmware/*.sh; do
        [ -f "$f" ] || continue
        local base=$(basename "$f")
        local dest="/home/pi/$base"
        if [ ! -f "$dest" ] || ! diff -q "$f" "$dest" &>/dev/null; then
            cp "$f" "$dest"
            chown pi:pi "$dest"
            chmod 755 "$dest"
            echo -e "  ${GREEN}✔  Bijgewerkt: $base${R}"
            copied=$((copied+1))
        fi
    done
    if [ $copied -gt 0 ]; then
        echo -e "  ${CYAN}$copied script(s) automatisch bijgewerkt vanuit SD-kaart.${R}"
        echo -e "  ${DIM}Herlaad met: source /home/pi/pi_welkom.sh${R}\n"
        sleep 2
    fi
}

# ── Aliases instellen ─────────────────────────────────────────────────────────
alias nas='sudo python3 /home/pi/nas_installer_cli.py'
alias fb='filebrowser -r /mnt/opslag -a 0.0.0.0 -p 8080 -d /home/pi/filebrowser.db'
alias menu='pi_welkom_keuze'
alias backup='sudo python3 /home/pi/nas_backup.py'
alias update-scripts='for f in /boot/firmware/*.py /boot/firmware/*.sh; do [ -f "$f" ] && cp "$f" /home/pi/ && chown pi:pi /home/pi/$(basename $f) && chmod 755 /home/pi/$(basename $f) && echo "Gekopieerd: $(basename $f)"; done'

# ── Automatisch tonen bij inloggen (alleen interactieve sessie) ───────────────
if [[ $- == *i* ]] && [ -z "$PI_WELKOM_GETOOND" ]; then
    export PI_WELKOM_GETOOND=1
    auto_update_scripts    # ← automatisch bijwerken vóór menu
    pi_welkom_keuze
fi
