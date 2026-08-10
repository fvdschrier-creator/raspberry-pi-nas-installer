#!/bin/bash
# ============================================================================
# Pi NAS - iPhone Back-up
# ----------------------------------------------------------------------------
# Doel: foto's, gedeelde app-bestanden en (best effort) WhatsApp-chats van een
#       aangesloten iPhone naar de backup-HDD kopieren, als leesbare bestanden
#       (geen versleutelde blob).
#
# BELANGRIJK - de iPhone moet aan DE PI hangen (usb-poort van de Raspberry
# Pi zelf), NIET aan de Windows-pc. Dit script draait op de Pi en heeft
# rechtstreeks usb-toegang tot het toestel nodig.
#
# Draai dit OP DE PI met:   sudo bash pinas_iphone_backup.sh
#
# WAT WEL, WAT NIET (10 augustus 2026, met Frans afgesproken):
#  - Foto's/video's (camerarol): altijd, gewone bestanden, geen risico.
#  - Bestanden van apps met "bestandsdeling" (zoals je ook ziet in Verkenner
#    als je de iPhone aan een pc hangt): altijd, gewone bestanden.
#  - WhatsApp: BEST EFFORT. Vereist een volledige (tijdelijke) apparaat-
#    back-up plus een los hulpprogramma (whatsapp-chat-exporter) om daar een
#    leesbare HTML-export van chats+media uit te halen. Kwetsbaarder dan de
#    andere twee stappen (kan breken bij een WhatsApp/iOS-update, of vraagt
#    om een back-up-wachtwoord als "Codeer lokale back-up" op het toestel
#    aanstaat) - een mislukte WhatsApp-stap stopt de rest van de back-up niet.
#  - Notities: BEWUST NIET meegenomen. Apple Notities synct standaard via
#    iCloud, niet lokaal op het toestel - daar is met deze methode geen
#    leesbare kopie van te maken. (Frans, 10 augustus 2026: "zo niet dan
#    stopt dat".)
#
# VEILIG:
#  - Leest alleen van de iPhone, schrijft alleen naar de backup-HDD. Er wordt
#    niets op de iPhone zelf gewijzigd of verwijderd.
#  - De tijdelijke volledige back-up (nodig voor de WhatsApp-stap) wordt na
#    gebruik altijd opgeruimd, ook als die stap mislukt.
# ============================================================================

set -u

MOUNT="/mnt/backup"
DATUM="$(date +%F)"
BASISMAP="$MOUNT/PiNAS iPhone Backup"
RUN_MAP="$BASISMAP/iPhone_$DATUM"

R="\033[0m"; B="\033[1m"; G="\033[92m"; Y="\033[93m"; RED="\033[91m"; C="\033[96m"
ok()   { echo -e "  ${G}OK${R}  $1"; }
warn() { echo -e "  ${Y}!!${R}  $1"; }
err()  { echo -e "  ${RED}FOUT${R}  $1"; }
kop()  { echo -e "\n${C}${B}-- $1 --${R}"; }

if [ "$(id -u)" -ne 0 ]; then
    err "Draai dit script met sudo:  sudo bash pinas_iphone_backup.sh"
    exit 1
fi

echo -e "${C}${B}"
echo "============================================================"
echo "  Pi NAS - iPhone Back-up"
echo "============================================================"
echo -e "${R}"

# --- Stap 1: backup-HDD aanwezig? --------------------------------------------
kop "Stap 1: Backup-HDD controleren"
if ! mountpoint -q "$MOUNT"; then
    err "Backup-HDD ($MOUNT) is niet gekoppeld. Staat de externe HDD aan?"
    exit 1
fi
ok "Backup-HDD gevonden op $MOUNT."

# --- Stap 2: benodigde tools controleren/installeren -------------------------
kop "Stap 2: Benodigde tools"
NODIG_APT=()
command -v idevice_id      >/dev/null 2>&1 || NODIG_APT+=("libimobiledevice-utils")
command -v ifuse           >/dev/null 2>&1 || NODIG_APT+=("ifuse")
command -v ideviceinstaller >/dev/null 2>&1 || NODIG_APT+=("ideviceinstaller")
dpkg -s usbmuxd >/dev/null 2>&1 || NODIG_APT+=("usbmuxd")

if [ "${#NODIG_APT[@]}" -gt 0 ]; then
    echo "  Nog niet aanwezig: ${NODIG_APT[*]} - installeren..."
    apt-get update -qq
    apt-get install -y "${NODIG_APT[@]}"
fi
systemctl enable --now usbmuxd >/dev/null 2>&1
ok "libimobiledevice/ifuse/ideviceinstaller/usbmuxd aanwezig."

if ! command -v wtsexporter >/dev/null 2>&1; then
    echo "  whatsapp-chat-exporter nog niet aanwezig - installeren (voor de WhatsApp-stap)..."
    if pip3 install --break-system-packages whatsapp-chat-exporter >/dev/null 2>&1; then
        ok "whatsapp-chat-exporter geinstalleerd."
    else
        warn "whatsapp-chat-exporter kon niet worden geinstalleerd - WhatsApp-stap wordt overgeslagen."
    fi
else
    ok "whatsapp-chat-exporter al aanwezig."
fi

# --- Stap 3: iPhone zoeken ----------------------------------------------------
kop "Stap 3: iPhone zoeken"
UDID="$(idevice_id -l 2>/dev/null | head -1)"
if [ -z "$UDID" ]; then
    err "Geen iPhone gevonden. Zit 'm aan een usb-poort VAN DE PI (niet de pc), en is 'ie ontgrendeld?"
    exit 1
fi
AANTAL="$(idevice_id -l 2>/dev/null | wc -l)"
if [ "$AANTAL" -gt 1 ]; then
    warn "Meerdere Apple-toestellen gevonden - de eerste ($UDID) wordt gebruikt."
fi
ok "Toestel gevonden: $UDID"

# --- Stap 4: vertrouwen (pairing) --------------------------------------------
kop "Stap 4: Vertrouwen controleren"
if ! idevicepair -u "$UDID" validate >/dev/null 2>&1; then
    echo "  Nog niet vertrouwd - koppeling starten. Bevestig 'Vertrouw deze computer'"
    echo "  op het scherm van de iPhone zelf (ontgrendeld houden)."
    idevicepair -u "$UDID" pair >/dev/null 2>&1
    TELLER=0
    while ! idevicepair -u "$UDID" validate >/dev/null 2>&1; do
        TELLER=$((TELLER + 1))
        if [ "$TELLER" -ge 30 ]; then
            err "Geen bevestiging ontvangen (60 sec. gewacht). Ontgrendel de iPhone, tik op"
            err "'Vertrouw deze computer' zodra dat gevraagd wordt, en probeer opnieuw."
            exit 1
        fi
        sleep 2
    done
fi
ok "Toestel is vertrouwd."

mkdir -p "$RUN_MAP/Fotos" "$RUN_MAP/Bestanden"
FOTOS_OK=0; BESTANDEN_OK=0; WHATSAPP_OK=0

# --- Stap 5: foto's/video's ---------------------------------------------------
kop "Stap 5: Foto's en video's"
FOTO_MNT="$(mktemp -d)"
if timeout 20 ifuse -u "$UDID" "$FOTO_MNT" >/dev/null 2>&1 && [ -d "$FOTO_MNT/DCIM" ]; then
    rsync -a --info=progress2 "$FOTO_MNT/DCIM/" "$RUN_MAP/Fotos/" && FOTOS_OK=1
    fusermount -u "$FOTO_MNT" 2>/dev/null || umount "$FOTO_MNT" 2>/dev/null
    if [ "$FOTOS_OK" -eq 1 ]; then
        ok "Foto's/video's gekopieerd naar: $RUN_MAP/Fotos"
    else
        err "Kopieren van foto's is mislukt."
    fi
else
    err "Kon de camerarol niet koppelen (ifuse). Foto's overgeslagen."
    fusermount -u "$FOTO_MNT" 2>/dev/null || umount "$FOTO_MNT" 2>/dev/null
fi
rmdir "$FOTO_MNT" 2>/dev/null

# --- Stap 6a: "Op mijn iPhone" (Bestanden-app, lokale opslag) ----------------
kop "Stap 6a: Op mijn iPhone"
# 10 augustus 2026 (Frans: "app bestanden is niet wat ik zocht, er is een map
# 'op mijn iphone'"): dat is de LOKALE opslag van de systeem-Bestanden-app,
# geen los geinstalleerde app - staat dus NOOIT in de "list --user"-lijst
# hierboven (die toont alleen door de gebruiker geinstalleerde apps). Het
# bundle-ID van de Bestanden-app zelf (com.apple.DocumentsApp) moet je apart,
# rechtstreeks aanroepen om bij "Op mijn iPhone" te komen.
ONMIJN_MNT="$(mktemp -d)"
# 10 augustus 2026 (Frans: "waar staat die /tmp map?"): /tmp staat op de Pi
# zelf, onbereikbaar via Verkenner. Om dat om te zeilen: bij een mislukte of
# verdacht lege koppeling de logregels meteen IN DIT SCHERM tonen, in plaats
# van er alleen naar te verwijzen.
ONMIJN_LOG="$(mktemp)"
if timeout 15 ifuse -u "$UDID" --documents com.apple.DocumentsApp "$ONMIJN_MNT" >"$ONMIJN_LOG" 2>&1; then
    if [ -n "$(ls -A "$ONMIJN_MNT" 2>/dev/null)" ]; then
        mkdir -p "$RUN_MAP/Op mijn iPhone"
        rsync -a "$ONMIJN_MNT/" "$RUN_MAP/Op mijn iPhone/" 2>/dev/null && BESTANDEN_OK=1
        ok "Op mijn iPhone gekopieerd naar: $RUN_MAP/Op mijn iPhone"
    else
        # 10 augustus 2026 (Frans, na live test: op het toestel zelf staan er
        # wel degelijk losse bestanden in "Op mijn iPhone" - dus dit is NIET
        # gewoon een lege map): de koppeling meldt succes maar toont niets.
        # Nog niet opgelost (zonder het toestel zelf te kunnen testen) - deze
        # tekst maakt in elk geval het verschil met "echt leeg" duidelijk.
        warn "'Op mijn iPhone' koppelen lukte, maar toont niets - terwijl er op"
        warn "het toestel wel bestanden in staan. Nog een onopgeloste kwestie."
        [ -s "$ONMIJN_LOG" ] && sed 's/^/  /' "$ONMIJN_LOG"
    fi
    fusermount -u "$ONMIJN_MNT" 2>/dev/null || umount "$ONMIJN_MNT" 2>/dev/null
else
    # 10 augustus 2026 (Frans, opgehelderd met pinas_iphone_diagnose.sh):
    # dit mislukt hier altijd met "InstallationLookupFailed" - Apple's
    # installation proxy behandelt de systeem-Bestanden-app (com.apple.
    # DocumentsApp) niet als een gewone geinstalleerde app met
    # UIFileSharingEnabled, dus house-arrest-toegang wordt geweigerd.
    # Bevestigd met een tweede, onafhankelijke tool (afcclient) - dezelfde
    # foutmelding, dus geen bug hier maar een echte beperking van deze
    # koppelmethode voor deze specifieke map. Foto's en Bestanden werken
    # hier niet door geraakt.
    if grep -q "InstallationLookupFailed" "$ONMIJN_LOG" 2>/dev/null; then
        warn "'Op mijn iPhone' niet toegankelijk via deze methode - bekende"
        warn "iOS-beperking (geen bug hier). Foto's en Bestanden zijn niet"
        warn "geraakt."
    else
        warn "Kon 'Op mijn iPhone' niet koppelen."
        [ -s "$ONMIJN_LOG" ] && sed 's/^/  /' "$ONMIJN_LOG"
    fi
fi
rm -f "$ONMIJN_LOG"
rmdir "$ONMIJN_MNT" 2>/dev/null

# --- Stap 6b: bestanden van overige apps met bestandsdeling -------------------
kop "Stap 6b: Bestanden van andere apps met bestandsdeling"
# 10 augustus 2026: eerste live-test gaf "ideviceinstaller: invalid option -- 'l'".
# De oude vlag-stijl ("-l -o list_user") bestaat niet meer sinds ideviceinstaller
# is herschreven naar subcommando's (zie github.com/libimobiledevice/
# ideviceinstaller, versie 1.2.0): het is nu "list --user", geen losse "-l"/"-o"
# meer. De standaarduitvoer begint bovendien met 1 kopregel
# ("CFBundleIdentifier, ...") die overgeslagen moet worden, anders wordt die
# per ongeluk als een bundle-ID behandeld.
#
# 10 augustus 2026 (Frans, na een proefbackup: "aan deze mappen heb ik niets"):
# apps waarvan de gedeelde bestanden nooit de moeite waard zijn om te
# backuppen. Lijst hieronder aanpassen (toevoegen/verwijderen) als dat
# verandert - het exacte bundle-ID staat als mapnaam onder "Bestanden" in
# een eerder gemaakte back-up.
OVERSLAAN_APPS=(
    "com.cardo.SmartSet"
    "com.duckduckgo.mobile.ios"
    "com.epson.ESCPR01"
    "com.internet.tvbrowser"
    "com.intsig.CamScannerLite"
    "com.itimeteo.webssh"
    "com.lenovo.smartconnect.ios"
    "com.microsoft.officelens"
    "com.spotify.client"
    "com.SuccessFactors.SuccessFactors"
    "it.twsweb.Nextcloud"
)
APP_RAW="$(ideviceinstaller -u "$UDID" list --user 2>>/tmp/pinas_iphone_backup.log | tail -n +2)"
APP_LIJST="$(echo "$APP_RAW" | cut -d',' -f1)"
if [ -z "$APP_LIJST" ]; then
    warn "Geen apps opgehaald - deze stap overgeslagen (zie /tmp/pinas_iphone_backup.log op de Pi)."
    echo "  Diagnose - directe aanroep (voor als dit nogmaals gebeurt):"
    ideviceinstaller -u "$UDID" list --user 2>&1 | head -5 | sed 's/^/    /'
else
    while IFS= read -r BUNDLE; do
        [ -z "$BUNDLE" ] && continue
        OVERSLAAN=0
        for X in "${OVERSLAAN_APPS[@]}"; do
            if [ "$BUNDLE" = "$X" ]; then
                OVERSLAAN=1
                break
            fi
        done
        [ "$OVERSLAAN" -eq 1 ] && continue
        APP_MNT="$(mktemp -d)"
        if timeout 15 ifuse -u "$UDID" --documents "$BUNDLE" "$APP_MNT" >/dev/null 2>&1; then
            if [ -n "$(ls -A "$APP_MNT" 2>/dev/null)" ]; then
                DOEL="$RUN_MAP/Bestanden/$BUNDLE"
                mkdir -p "$DOEL"
                rsync -a "$APP_MNT/" "$DOEL/" 2>/dev/null && BESTANDEN_OK=1
            fi
            fusermount -u "$APP_MNT" 2>/dev/null || umount "$APP_MNT" 2>/dev/null
        fi
        rmdir "$APP_MNT" 2>/dev/null
    done <<< "$APP_LIJST"
    if [ "$BESTANDEN_OK" -eq 1 ]; then
        ok "Gedeelde app-bestanden gekopieerd naar: $RUN_MAP/Bestanden"
    else
        warn "Geen apps met bruikbare bestandsdeling gevonden (kan normaal zijn)."
    fi
fi

# --- Stap 7: WhatsApp (best effort) ------------------------------------------
kop "Stap 7: WhatsApp (best effort)"
if ! command -v wtsexporter >/dev/null 2>&1; then
    warn "whatsapp-chat-exporter niet beschikbaar - WhatsApp-stap overgeslagen."
elif ! ideviceinstaller -u "$UDID" list --user 2>/dev/null | grep -q "net.whatsapp.WhatsApp"; then
    warn "WhatsApp niet gevonden op dit toestel - overgeslagen."
else
    TIJDELIJK="$(mktemp -d)"
    echo "  Volledige (tijdelijke) apparaat-back-up maken - dit kan lang duren..."
    if timeout 3600 idevicebackup2 -u "$UDID" backup --full "$TIJDELIJK" >/tmp/pinas_iphone_backup.log 2>&1; then
        mkdir -p "$RUN_MAP/WhatsApp"
        if wtsexporter -i -b "$TIJDELIJK/$UDID" -o "$RUN_MAP/WhatsApp" >>/tmp/pinas_iphone_backup.log 2>&1; then
            WHATSAPP_OK=1
            ok "WhatsApp-export gemaakt in: $RUN_MAP/WhatsApp"
        else
            err "WhatsApp-export mislukt (zie /tmp/pinas_iphone_backup.log op de Pi)."
            echo "  Mogelijke oorzaak: 'Codeer lokale back-up' staat aan op de iPhone -"
            echo "  zie Instellingen > Algemeen > Overdragen of iPhone resetten op het toestel."
        fi
    else
        err "Volledige back-up (nodig voor WhatsApp) is mislukt of vroegtijdig gestopt."
        echo "  Mogelijke oorzaak: 'Codeer lokale back-up' staat aan op de iPhone en vraagt"
        echo "  om een wachtwoord dat dit script niet kent."
    fi
    rm -rf "$TIJDELIJK"
fi

# --- Stap 8: rechten -----------------------------------------------------------
kop "Stap 8: Rechten"
chown -R pi:pi "$BASISMAP" 2>/dev/null
chmod -R u+rwX,g+rX "$BASISMAP" 2>/dev/null
ok "Rechten gezet."

# --- Samenvatting --------------------------------------------------------------
echo -e "\n${C}${B}============================================================${R}"
echo -e "${C}${B}  Klaar${R}"
echo -e "${C}${B}============================================================${R}"
[ "$FOTOS_OK" -eq 1 ]     && ok "Foto's/video's: gelukt"     || err "Foto's/video's: niet gelukt"
[ "$BESTANDEN_OK" -eq 1 ] && ok "App-bestanden: gelukt"      || warn "App-bestanden: niets gevonden/overgeslagen"
[ "$WHATSAPP_OK" -eq 1 ]  && ok "WhatsApp: gelukt"           || warn "WhatsApp: niet gelukt/overgeslagen (best effort)"
echo -e "\nAlles staat in: $RUN_MAP\n"
