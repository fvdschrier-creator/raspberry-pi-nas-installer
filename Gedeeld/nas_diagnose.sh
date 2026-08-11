#!/bin/bash
# Raspberry Pi NAS Installer v1.0.0
# -----------------------------------------------------------------------------
# Pi NAS Diagnose - controleert alles en rapporteert fouten
# Gebruik: bash /home/pi/nas_diagnose.sh
#          bash /home/pi/nas_diagnose.sh --fix   (herstelt gevonden rechten-
#                                                  problemen meteen, i.p.v.
#                                                  alleen te melden)
# -----------------------------------------------------------------------------
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH

FIX_MODUS=0
[ "$1" = "--fix" ] && FIX_MODUS=1

R="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"
CYAN="\033[96m"; GREEN="\033[92m"; YELLOW="\033[93m"
RED="\033[91m"; BLUE="\033[94m"; WHITE="\033[97m"

# Kleurcodes uitzetten als output niet naar terminal gaat
if [ ! -t 1 ]; then
    R=""; BOLD=""; DIM=""
    CYAN=""; GREEN=""; YELLOW=""
    RED=""; BLUE=""; WHITE=""
fi

ok()   { echo -e "  ${GREEN}OK  $1${R}"; }
warn() { echo -e "  ${YELLOW}!  $1${R}"; }
err()  { echo -e "  ${RED}FOUT  $1${R}"; FOUTEN=$((FOUTEN+1)); }
info() { echo -e "  ${CYAN}i  $1${R}"; }
fixed(){ echo -e "  ${GREEN}HERSTELD  $1${R}"; FIXEN=$((FIXEN+1)); }

# Eerlijke servicestatus: een 'oneshot' die klaar is (success) is GEEN fout,
# maar een normale, voltooide eenmalige taak. Een doorlopende service die
# ingeschakeld is maar niet draait, is wel een echte waarschuwing.
check_service() {
    local svc="$1"
    local status enabled stype sresult
    status=$(systemctl is-active "$svc" 2>/dev/null)
    enabled=$(systemctl is-enabled "$svc" 2>/dev/null)
    stype=$(systemctl show -p Type --value "$svc" 2>/dev/null)
    sresult=$(systemctl show -p Result --value "$svc" 2>/dev/null)
    if [ "$status" = "active" ]; then
        ok "$svc - actief (enabled: $enabled)"
    elif [ "$stype" = "oneshot" ] && [ "$sresult" = "success" ]; then
        ok "$svc - eenmalige taak voltooid (enabled: $enabled)"
    elif [ "$enabled" = "enabled" ]; then
        warn "$svc - ingeschakeld maar NIET actief"
    else
        echo -e "  ${DIM}-  $svc - niet geinstalleerd${R}"
    fi
}
hdr()  { echo -e "\n${BLUE}${BOLD}-- $1 --${R}"; }

FOUTEN=0
FIXEN=0

echo -e "\n${CYAN}${BOLD}  Pi NAS Diagnose${R}"
echo -e "  $(date '+%Y-%m-%d %H:%M:%S')\n"

# -- Systeem -------------------------------------------------------------------
hdr "Systeem"
IP=$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^(192|10|172)' | head -1)
[ -n "$IP" ] && ok "IP-adres: $IP" || err "Geen IP-adres gevonden"
ok "Hostname: $(hostname)"
ok "Uptime: $(uptime -p 2>/dev/null || uptime)"
TEMP=$(vcgencmd measure_temp 2>/dev/null | cut -d= -f2)
[ -n "$TEMP" ] && info "CPU temp: $TEMP" || info "Temp: $(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{printf \"%.1f°C\", $1/1000}')"
FREE_RAM=$(free -h | awk '/Mem/{print $7}')
ok "RAM vrij: $FREE_RAM"

# -- Schijven ------------------------------------------------------------------
hdr "Schijven"
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT --ascii 2>/dev/null
echo ""
SDA_MOUNT=$(lsblk -rn -o MOUNTPOINT /dev/sda 2>/dev/null | head -1)
SDB_MOUNT=$(lsblk -rn -o MOUNTPOINT /dev/sdb 2>/dev/null | head -1)
[ -n "$SDA_MOUNT" ] && ok "/dev/sda gemount op $SDA_MOUNT" || warn "/dev/sda niet gemount (of niet aanwezig)"
[ -n "$SDB_MOUNT" ] && ok "/dev/sdb gemount op $SDB_MOUNT" || info "/dev/sdb niet aanwezig (backup schijf)"

# fstab NAS regels
NAS_FSTAB=$(grep "/mnt/" /etc/fstab 2>/dev/null | grep -v "^#")
if [ -n "$NAS_FSTAB" ]; then
    ok "fstab NAS regels:"
    echo "$NAS_FSTAB" | while read line; do echo -e "    ${DIM}$line${R}"; done
else
    warn "Geen NAS-regels in fstab"
fi

# -- Rechten -------------------------------------------------------------------
hdr "Rechten"
[ "$FIX_MODUS" -eq 1 ] && info "Fix-modus aan: gevonden rechten-problemen worden nu meteen hersteld"
for dir in /mnt/opslag /mnt/backup; do
    if [ -d "$dir" ]; then
        OWNER=$(stat -c '%U' "$dir" 2>/dev/null)
        PERMS=$(stat -c '%a' "$dir" 2>/dev/null)
        if [ "$OWNER" = "pi" ]; then
            ok "$dir - eigenaar: $OWNER, rechten: $PERMS"
        elif [ "$FIX_MODUS" -eq 1 ]; then
            if sudo -n chown pi:pi "$dir" 2>/dev/null; then
                fixed "$dir - eigenaar was $OWNER, nu pi"
            else
                err "$dir - eigenaar: $OWNER (verwacht: pi) - herstel met --fix mislukt (sudo?)"
            fi
        else
            err "$dir - eigenaar: $OWNER (verwacht: pi) - draai met --fix om dit te herstellen"
        fi
        if [ -d "$dir/nextcloud-data" ]; then
            NC_OWNER=$(stat -c '%U' "$dir/nextcloud-data" 2>/dev/null)
            if [ "$NC_OWNER" = "www-data" ]; then
                ok "$dir/nextcloud-data - eigenaar: $NC_OWNER"
            elif [ "$FIX_MODUS" -eq 1 ]; then
                if sudo -n chown -R www-data:www-data "$dir/nextcloud-data" 2>/dev/null; then
                    fixed "$dir/nextcloud-data - eigenaar was $NC_OWNER, nu www-data (recursief)"
                else
                    err "$dir/nextcloud-data - eigenaar: $NC_OWNER (verwacht: www-data) - herstel met --fix mislukt (sudo?)"
                fi
            else
                err "$dir/nextcloud-data - eigenaar: $NC_OWNER (verwacht: www-data) - draai met --fix om dit te herstellen"
            fi
        fi
    else
        info "$dir - map bestaat niet"
    fi
done

# Systemd rechten service
# nas-rechten is een oneshot-taak: "voltooid" is normaal, geen fout.
systemctl is-enabled nas-rechten.service &>/dev/null && ok "nas-rechten.service ingeschakeld" || warn "nas-rechten.service niet ingeschakeld"
check_service nas-rechten.service

# -- Services ------------------------------------------------------------------
hdr "Services"
for svc in ssh smbd nmbd apache2 mariadb filebrowser cockpit vncserver-x11-serviced; do
    check_service "$svc"
done

# -- Scripts -------------------------------------------------------------------
hdr "Scripts"
for f in nas_installer_cli.py nas_installer.py pi_welkom.sh install.sh; do
    PI_FILE="/home/pi/$f"
    BOOT_FILE="/boot/firmware/$f"
    if [ -f "$PI_FILE" ]; then
        PI_SIZE=$(stat -c '%s' "$PI_FILE")
        PI_DATE=$(stat -c '%y' "$PI_FILE" | cut -d' ' -f1)
        if [ -f "$BOOT_FILE" ]; then
            BOOT_DATE=$(stat -c '%y' "$BOOT_FILE" | cut -d' ' -f1)
            if diff -q "$PI_FILE" "$BOOT_FILE" &>/dev/null; then
                ok "$f - /home/pi ($PI_DATE) = /boot/firmware ($BOOT_DATE) OK"
            else
                warn "$f - /home/pi ($PI_DATE) ≠ /boot/firmware ($BOOT_DATE) - VERSCHIL!"
            fi
        else
            warn "$f - aanwezig in /home/pi maar NIET in /boot/firmware"
        fi
    else
        err "$f - ONTBREEKT in /home/pi"
    fi
done

# -- .bashrc -------------------------------------------------------------------
hdr ".bashrc"
grep -q "pi_welkom.sh" /home/pi/.bashrc && ok "pi_welkom.sh in .bashrc" || err "pi_welkom.sh ONTBREEKT in .bashrc"
grep -q "install.sh" /home/pi/.bashrc && ok "install.sh in .bashrc" || info "install.sh niet in .bashrc (optioneel)"

# Dubbele aliases
DUBBEL=$(grep -c "alias menu=" /home/pi/.bashrc 2>/dev/null)
[ "$DUBBEL" -gt 1 ] && warn "alias menu staat $DUBBEL keer in .bashrc (dubbel)" || ok "alias menu - OK"

# -- Desktop -------------------------------------------------------------------
hdr "Desktop & VNC"
dpkg -l lxde-core &>/dev/null | grep -q "^ii" && ok "Desktop (LXDE) geinstalleerd" || info "Desktop niet geinstalleerd"
dpkg -l realvnc-vnc-server &>/dev/null | grep -q "^ii" && ok "VNC geinstalleerd" || info "VNC niet geinstalleerd"

for desktop_file in /home/pi/Desktop/nas_installer.desktop /home/pi/Desktop/raspi_config.desktop; do
    if [ -f "$desktop_file" ]; then
        ok "$(basename $desktop_file) aanwezig"
        [ -x "$desktop_file" ] && ok "  uitvoerbaar OK" || warn "  NIET uitvoerbaar"
    else
        info "$(basename $desktop_file) niet aanwezig"
    fi
done

# LXDE autostart
if [ -f /home/pi/.config/lxsession/LXDE-pi/autostart ]; then
    ok "LXDE autostart aanwezig"
    cat /home/pi/.config/lxsession/LXDE-pi/autostart | while read line; do
        echo -e "    ${DIM}$line${R}"
    done
else
    info "Geen LXDE autostart ingesteld"
fi

# -- Nextcloud -----------------------------------------------------------------
hdr "Nextcloud"
if [ -d /var/www/html/nextcloud ]; then
    ok "Nextcloud geinstalleerd"
    NC_STATUS=$(sudo -n -u www-data php /var/www/html/nextcloud/occ status 2>/dev/null | grep "installed:")
    [ -n "$NC_STATUS" ] && ok "$NC_STATUS" || warn "Nextcloud status onbekend"
    NC_DATA=$(sudo -n -u www-data php /var/www/html/nextcloud/occ config:system:get datadirectory 2>/dev/null)
    [ -n "$NC_DATA" ] && ok "Data directory: $NC_DATA" || warn "Data directory onbekend"
else
    info "Nextcloud niet geinstalleerd"
fi

# -- Samba ---------------------------------------------------------------------
hdr "Samba"
if systemctl is-active smbd &>/dev/null; then
    ok "Samba actief"
    testparm -s 2>/dev/null | grep -E "^\[|path" | while read line; do
        echo -e "  ${DIM}$line${R}"
    done
elif dpkg -l samba 2>/dev/null | grep -q "^ii"; then
    ok "Samba geinstalleerd maar niet actief"
else
    info "Samba niet geinstalleerd"
fi

# -- GUI installer -------------------------------------------------------------
hdr "GUI installer"
if [ -f /home/pi/nas_installer.py ]; then
    python3 -m py_compile /home/pi/nas_installer.py 2>/dev/null && ok "nas_installer.py syntax OK" || err "nas_installer.py syntax FOUT"
    python3 - << 'PYEOF' 2>&1
import sys; sys.argv=['x']
src = open('/home/pi/nas_installer.py').read()
src = src.replace("NASInstaller().mainloop()", "pass")
src = src.replace("if __name__==\"__main__\":", "if False:")
src = src.replace('if __name__ == "__main__":', "if False:")
try:
    exec(compile(src, 'nas_installer.py', 'exec'))
    shares = get_samba_shares()
    print(f"OK  get_samba_shares: {list(shares.keys())}")
    mounts = get_nas_mounts()
    print(f"OK  get_nas_mounts: {[m[1] for m in mounts]}")
    # Test beheer pagina logica
    STANDAARD=[
        ("Opslag",    "/mnt/opslag",           "SSD"),
        ("Fotos",     "/mnt/backup/fotos",      "Seagate fotos"),
        ("Bestanden", "/mnt/backup/bestanden",  "Seagate bestanden"),
        ("Music",     "/mnt/backup/music",      "Seagate muziek"),
    ]
    bestaande_paden=[p.rstrip('/') for p in shares.values()]
    bestaande_namen=[n.lower() for n in shares.keys()]
    for naam,pad,beschr in STANDAARD:
        bestaat = naam.lower() in bestaande_namen or pad.rstrip('/') in bestaande_paden
        print(f"{'OK' if bestaat else '! '}  [{naam}] -> {pad} ({'aanwezig' if bestaat else 'ontbreekt'})")
    # Tkinter test alleen als display beschikbaar (niet via SSH zonder X11)
    import os as _os
    if _os.environ.get("DISPLAY"):
        import tkinter as tk
        try:
            root = tk.Tk()
            root.withdraw()
            f = tk.Frame(root, bg="#1e1e2e")
            for naam,pad,beschr in STANDAARD:
                r = tk.Frame(f, bg="#313244")
                tk.Label(r, text="OK", font=("Segoe UI",9,"bold"), bg="#313244", fg="#a6e3a1", width=3)
                tk.Label(r, text=f"[{naam}]", font=("Segoe UI",9,"bold"), bg="#313244", width=12)
                tk.Label(r, text=pad, font=("Courier",8), bg="#313244")
                tk.Label(r, text=beschr, font=("Segoe UI",8), bg="#313244")
                print(f"OK  Tkinter rij [{naam}] aangemaakt")
            root.destroy()
            print("OK  Tkinter beheer pagina render test geslaagd")
        except Exception as te:
            print(f"FOUT  Tkinter fout bij rij: {te}")
            import traceback; traceback.print_exc()
    else:
        print("OK  Tkinter test overgeslagen (geen display)")
except Exception as e:
    import traceback
    print(f"FOUT  {e}")
    traceback.print_exc()
PYEOF
else
    err "nas_installer.py niet gevonden"
fi

# -- Opruimen / SD-kaart ------------------------------------------------------
hdr "Opruimen / SD-kaart"
echo "  Schijfruimte:"
df -h / /boot/firmware 2>/dev/null | sed 's/^/    /'
echo ""
echo "  Grootste mappen in /home/pi (top 8):"
du -h --max-depth=2 /home/pi/ 2>/dev/null | sort -rh | head -n 8 | sed 's/^/    /'
echo ""
# Scripts horen BEWUST in twee plekken te staan: /home/pi (draait) en
# /boot/firmware (overleeft een herinstallatie). Dat is geen fout. We
# waarschuwen alleen als de twee kopieen VAN ELKAAR VERSCHILLEN (uit sync).
UITSYNC=0
for n in seagate_web.py smart_plug.py nas_installer.py nas_installer_cli.py pinas_theme.py pi_welkom.sh install.sh; do
    H="/home/pi/$n"; B="/boot/firmware/$n"
    if [ -f "$H" ] && [ -f "$B" ]; then
        if ! sudo cmp -s "$H" "$B" 2>/dev/null && ! cmp -s "$H" "$B" 2>/dev/null; then
            warn "script uit sync (home != /boot/firmware): $n"
            UITSYNC=$((UITSYNC+1))
        fi
    fi
done
[ "$UITSYNC" -eq 0 ] && ok "scripts in sync (home en /boot/firmware gelijk)"
SDFOUT=$(dmesg 2>/dev/null | grep -i -E 'mmc[0-9].*error|i/o error|EXT4-fs error' | tail -n 3)
if [ -n "$SDFOUT" ]; then
    warn "mogelijke SD-/schijf-fouten in dmesg (laatste 3):"
    echo "$SDFOUT" | sed 's/^/    /'
else
    ok "geen SD-/schijf-fouten in dmesg"
fi

# -- Samenvatting --------------------------------------------------------------
echo -e "\n${CYAN}${BOLD}======================================================${R}"
if [ "$FIXEN" -gt 0 ]; then
    echo -e "  ${GREEN}${BOLD}HERSTELD  $FIXEN probleem/problemen automatisch verholpen${R}"
fi
if [ $FOUTEN -eq 0 ]; then
    echo -e "  ${GREEN}${BOLD}OK  Alles OK - geen fouten gevonden${R}"
else
    echo -e "  ${RED}${BOLD}FOUT  $FOUTEN fout(en) gevonden - zie bovenstaande meldingen${R}"
    [ "$FIX_MODUS" -eq 0 ] && echo -e "  ${DIM}Sommige hiervan zijn mogelijk automatisch te herstellen: bash nas_diagnose.sh --fix${R}"
fi
echo -e "${CYAN}${BOLD}======================================================${R}\n"
