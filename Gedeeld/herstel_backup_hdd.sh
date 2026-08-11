#!/bin/bash
# ============================================================================
# Pi NAS - Backup-HDD controle en herstel
# ----------------------------------------------------------------------------
# Doel: de afgebroken-journal-fout op de backup-HDD (/mnt/backup) controleren
#       en herstellen met e2fsck, plus het cosmetische plymouth-quit opruimen.
#
# Draai dit OP DE PI met:   sudo bash herstel_backup_hdd.sh
#
# VEILIG:
#  - Werkt UITSLUITEND op de schijf met UUID UW_BACKUP_HDD_UUID... (/mnt/backup).
#    /mnt/opslag (de SSD) wordt nooit aangeraakt.
#  - e2fsck draait NOOIT op een gekoppelde schijf (dat zou data beschadigen);
#    het script controleert dat expliciet en stopt anders.
#  - Bij twijfel stopt het script en koppelt het netjes terug i.p.v. door te gaan.
# ============================================================================

set -u

UUID="UW_BACKUP_HDD_UUID"
MOUNT="/mnt/backup"

R="\033[0m"; B="\033[1m"; G="\033[92m"; Y="\033[93m"; RED="\033[91m"; C="\033[96m"
ok()   { echo -e "  ${G}OK${R}  $1"; }
warn() { echo -e "  ${Y}!!${R}  $1"; }
err()  { echo -e "  ${RED}FOUT${R}  $1"; }
kop()  { echo -e "\n${C}${B}-- $1 --${R}"; }

# --- Moet als root draaien ---------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
    err "Draai dit script met sudo:  sudo bash herstel_backup_hdd.sh"
    exit 1
fi

echo -e "${C}${B}"
echo "============================================================"
echo "  Pi NAS - Backup-HDD controle en herstel"
echo "============================================================"
echo -e "${R}"

# --- Stap 1: device vinden via UUID (nooit gokken op /dev/sdc) ---------------
kop "Stap 1: Backup-HDD opzoeken"
DEV="$(blkid -U "$UUID" 2>/dev/null)"
if [ -z "$DEV" ]; then
    err "Backup-HDD met UUID $UUID niet gevonden."
    warn "Staat de externe HDD wel aan? Zet 'm aan via het menu en probeer opnieuw."
    exit 1
fi
FSTYPE="$(blkid -o value -s TYPE "$DEV" 2>/dev/null)"
ok "Gevonden: $DEV  (filesystem: ${FSTYPE:-onbekend})"
if [ "$FSTYPE" != "ext4" ]; then
    err "Onverwacht filesystem ($FSTYPE). Voor de zekerheid stop ik hier."
    exit 1
fi

# --- Stap 2: hardware-gezondheid (fs-fout vs stervende schijf) ---------------
kop "Stap 2: Hardware-gezondheid (SMART)"
if command -v smartctl >/dev/null 2>&1; then
    HEALTH="$(smartctl -H "$DEV" 2>/dev/null | grep -i 'overall\|health\|result')"
    if [ -n "$HEALTH" ]; then
        echo "  $HEALTH"
        if echo "$HEALTH" | grep -qi "PASSED"; then
            ok "SMART meldt de schijf als gezond - de fout is waarschijnlijk alleen het bestandssysteem."
        else
            warn "SMART meldt GEEN 'PASSED'. e2fsck kan het bestandssysteem herstellen,"
            warn "maar een stervende schijf niet redden. Let hierop na afloop."
        fi
    else
        warn "Geen SMART-info beschikbaar (USB-behuizing ondersteunt het soms niet)."
    fi
else
    warn "smartctl niet geinstalleerd - SMART-check overgeslagen."
    warn "Installeren kan met: sudo apt install smartmontools"
fi

# --- Stap 3: diensten stoppen + netjes loskoppelen ---------------------------
kop "Stap 3: Loskoppelen van $MOUNT"
echo "  Diensten die de schijf vasthouden tijdelijk stoppen (smbd, apache2)..."
systemctl stop smbd 2>/dev/null
systemctl stop apache2 2>/dev/null
sync
sleep 2

if mountpoint -q "$MOUNT"; then
    umount "$MOUNT" 2>/tmp/umount.err
    if mountpoint -q "$MOUNT"; then
        err "Loskoppelen mislukt - schijf is nog in gebruik door:"
        fuser -vm "$MOUNT" 2>&1 | sed 's/^/    /' | head
        warn "Ik koppel niets en herstart de diensten. Probeer het opnieuw,"
        warn "of reboot de Pi eerst (sudo reboot) en draai dit script direct daarna."
        systemctl start apache2 2>/dev/null
        systemctl start smbd 2>/dev/null
        exit 1
    fi
fi
ok "$MOUNT is losgekoppeld - veilig om te controleren."

# --- Stap 4: bestandssysteem controleren/herstellen --------------------------
kop "Stap 4: Bestandssysteem controleren (e2fsck)"
echo "  Eerst de veilige automatische modus (-p, herstelt alleen wat veilig is)..."
e2fsck -p "$DEV"
RC=$?
echo "  (e2fsck exitcode: $RC)"
case $RC in
    0) ok "Schoon - geen fouten gevonden." ;;
    1) ok "Kleine fouten automatisch hersteld." ;;
    2) warn "Fouten hersteld - een reboot wordt aangeraden na afloop." ;;
    *)
        warn "De veilige modus kon het niet alleen af (code $RC)."
        echo ""
        echo "  Een VOLLEDIGE reparatie (e2fsck -f -y) kan dit oplossen, maar kan"
        echo "  losse/kapotte bestanden naar de map 'lost+found' verplaatsen."
        read -r -p "  Volledige reparatie nu draaien? [j/N]: " ANT
        if [[ "$ANT" =~ ^[jJyY] ]]; then
            echo "  Volledige reparatie (kan op 7TB even duren)..."
            e2fsck -f -y "$DEV"
            RC2=$?
            echo "  (volledige reparatie exitcode: $RC2)"
            if [ "$RC2" -ge 8 ]; then
                err "Ernstige fout tijdens reparatie (code $RC2). Schijf NIET teruggekoppeld."
                warn "Dit wijst mogelijk op een hardwareprobleem. Koppel niets terug; meld de code."
                exit 1
            fi
            ok "Volledige reparatie afgerond."
        else
            warn "Overgeslagen. De schijf blijft LOSGEKOPPELD zodat er niets op geschreven wordt."
            warn "Koppel pas terug als het bestandssysteem hersteld is."
            exit 1
        fi
        ;;
esac

# --- Stap 5: terugkoppelen + rechten + diensten ------------------------------
kop "Stap 5: Terugkoppelen"
mount -a
if mountpoint -q "$MOUNT"; then
    ok "$MOUNT is weer gekoppeld."
else
    err "Terugkoppelen mislukt! Controleer 'sudo mount -a' handmatig."
    systemctl start apache2 2>/dev/null
    systemctl start smbd 2>/dev/null
    exit 1
fi
echo "  Rechten herstellen en diensten herstarten..."
systemctl start nas-rechten 2>/dev/null
systemctl start apache2 2>/dev/null
systemctl start smbd 2>/dev/null
ok "Diensten herstart (smbd, apache2, nas-rechten)."

# --- Stap 6: verifieren ------------------------------------------------------
kop "Stap 6: Controle achteraf"
TESTF="$MOUNT/.hdd_schrijftest_$$"
if touch "$TESTF" 2>/dev/null && rm -f "$TESTF" 2>/dev/null; then
    ok "Schrijftest geslaagd - de schijf is lees- en schrijfbaar."
else
    err "Schrijftest MISLUKT - schijf mogelijk read-only of hardwareprobleem."
fi
DEVBASE="$(basename "$DEV")"
echo "  Recente fouten voor $DEVBASE in dmesg:"
NEW="$(dmesg 2>/dev/null | grep -i "$DEVBASE" | grep -i 'error\|aborted journal' | tail -3)"
if [ -n "$NEW" ]; then
    echo "$NEW" | sed 's/^/    /'
    warn "Er staan nog fout-regels (kunnen van VOOR de reparatie zijn)."
    warn "Geef de schijf zo nodig een volledige uit/aan-cyclus en draai daarna nogmaals de diagnose."
else
    ok "Geen nieuwe schijf-fouten in dmesg."
fi

# --- Extra (cosmetisch): plymouth-quit opruimen ------------------------------
kop "Extra: plymouth-quit (cosmetisch rood kruisje)"
echo "  Op een headless NAS heeft plymouth-quit geen opstartscherm om af te sluiten;"
echo "  het 'mislukt' daarom zonder dat er iets stuk is. We maskeren het zodat het"
echo "  niet meer rood meldt. (Terugdraaien kan met: sudo systemctl unmask plymouth-quit.service)"
if systemctl mask plymouth-quit.service >/dev/null 2>&1; then
    ok "plymouth-quit.service gemaskeerd - geen rode melding meer."
else
    warn "Kon plymouth-quit niet maskeren (negeerbaar, puur cosmetisch)."
fi

echo -e "\n${G}${B}Klaar.${R} Backup-HDD gecontroleerd/hersteld en diensten draaien weer."
echo -e "Draai eventueel de Pi-diagnose opnieuw om te bevestigen dat alles groen is.\n"
