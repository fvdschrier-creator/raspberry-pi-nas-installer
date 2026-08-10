#!/bin/bash
# ============================================================================
# Pi NAS - iPhone Doorbladeren (live, tijdelijk)
# ----------------------------------------------------------------------------
# Doel: de iPhone LIVE zichtbaar maken in Windows Verkenner terwijl hij aan
# de Pi hangt - zonder eerst een volledige back-up te hoeven draaien. Handig
# om gewoon even te kijken wat er op het toestel staat (bijv. de structuur
# onder "Op mijn iPhone").
#
# BELANGRIJK - net als bij de iPhone Back-up: de iPhone moet aan een
# usb-poort VAN DE PI hangen, niet aan deze Windows-pc.
#
# Draai dit OP DE PI met:   sudo bash pinas_iphone_verkennen.sh
#
# Maakt een TIJDELIJKE, ALLEEN-LEZEN Samba-share "iPhone" met twee mappen:
#   - Media           (camerarol, Downloads, Books - de gewone AFC-koppeling)
#   - Op mijn iPhone   (lokale opslag van de systeem-Bestanden-app)
# Blijft staan zolang dit venster open blijft (druk op ENTER om te stoppen).
# Bij stoppen (of een druk op Ctrl+C) wordt alles netjes opgeruimd: de
# koppelingen losgemaakt en de tijdelijke share-regels weer verwijderd uit
# smb.conf (met duidelijke markeringsregels, dus nooit per ongeluk iets van
# de bestaande Opslag/Backup-shares geraakt).
# ============================================================================

set -u

MARKER_START="# === PINAS_IPHONE_LIVE_START ==="
MARKER_END="# === PINAS_IPHONE_LIVE_END ==="
LIVE_ROOT="/mnt/iphone_live"
SMB_CONF="/etc/samba/smb.conf"

R="\033[0m"; B="\033[1m"; G="\033[92m"; Y="\033[93m"; RED="\033[91m"; C="\033[96m"
ok()   { echo -e "  ${G}OK${R}  $1"; }
warn() { echo -e "  ${Y}!!${R}  $1"; }
err()  { echo -e "  ${RED}FOUT${R}  $1"; }
kop()  { echo -e "\n${C}${B}-- $1 --${R}"; }

if [ "$(id -u)" -ne 0 ]; then
    err "Draai dit script met sudo:  sudo bash pinas_iphone_verkennen.sh"
    exit 1
fi

echo -e "${C}${B}"
echo "============================================================"
echo "  Pi NAS - iPhone Doorbladeren (live, tijdelijk)"
echo "============================================================"
echo -e "${R}"

# --- Opruimfunctie, wordt aan het eind ALTIJD aangeroepen --------------------
MEDIA_MNT=""
DOCS_MNT=""
opruimen() {
    kop "Opruimen"
    [ -n "$MEDIA_MNT" ] && { fusermount -u "$MEDIA_MNT" 2>/dev/null || umount "$MEDIA_MNT" 2>/dev/null; rmdir "$MEDIA_MNT" 2>/dev/null; }
    [ -n "$DOCS_MNT" ] && { fusermount -u "$DOCS_MNT" 2>/dev/null || umount "$DOCS_MNT" 2>/dev/null; rmdir "$DOCS_MNT" 2>/dev/null; }
    if grep -q "$MARKER_START" "$SMB_CONF" 2>/dev/null; then
        sed -i "/$MARKER_START/,/$MARKER_END/d" "$SMB_CONF"
        systemctl reload smbd 2>/dev/null
        ok "Tijdelijke share verwijderd uit smb.conf."
    fi
    rmdir "$LIVE_ROOT" 2>/dev/null
    echo -e "\n${G}${B}Klaar.${R} De iPhone is niet meer zichtbaar via het netwerk.\n"
}
trap opruimen EXIT INT TERM HUP

# --- Stap 0: opruimen van een vorige, niet-netjes afgesloten sessie ---------
# 10 augustus 2026 (bug gevonden bij live test: tweede keer draaien bleef
# hangen op "Stap 4: iPhone koppelen"): als het vorige venster niet met ENTER
# maar bijv. met het kruisje is dichtgeklikt, kan de oude ifuse-koppeling of
# de oude tijdelijke share zijn blijven hangen. Een nieuwe ifuse-koppeling op
# een al bezet mountpunt loopt dan vast. Daarom hier eerst forceren dat alles
# leeg is, VOORDAT er iets nieuws geprobeerd wordt.
kop "Stap 0: Vorige sessie opruimen (indien nodig)"
fusermount -uz "$LIVE_ROOT/Media" 2>/dev/null
fusermount -uz "$LIVE_ROOT/Op mijn iPhone" 2>/dev/null
umount -l "$LIVE_ROOT/Media" 2>/dev/null
umount -l "$LIVE_ROOT/Op mijn iPhone" 2>/dev/null
if grep -q "$MARKER_START" "$SMB_CONF" 2>/dev/null; then
    sed -i "/$MARKER_START/,/$MARKER_END/d" "$SMB_CONF"
    systemctl reload smbd 2>/dev/null
fi
ok "Klaar voor een nieuwe koppeling."

# --- Stap 1: benodigde tools (zelfde als iPhone Back-up) ---------------------
kop "Stap 1: Benodigde tools"
NODIG_APT=()
command -v idevice_id       >/dev/null 2>&1 || NODIG_APT+=("libimobiledevice-utils")
command -v ifuse            >/dev/null 2>&1 || NODIG_APT+=("ifuse")
dpkg -s usbmuxd >/dev/null 2>&1 || NODIG_APT+=("usbmuxd")
if [ "${#NODIG_APT[@]}" -gt 0 ]; then
    apt-get update -qq
    apt-get install -y "${NODIG_APT[@]}"
fi
systemctl enable --now usbmuxd >/dev/null 2>&1
# 10 augustus 2026 (bug gevonden bij live test: inloggen op de share met het
# JUISTE NAS-wachtwoord gaf "Toegang geweigerd" - dus WEL geslaagde
# authenticatie, maar GEEN toegang, wat op een rechtenprobleem wijst i.p.v.
# een fout wachtwoord): ifuse-koppelingen zijn standaard alleen leesbaar
# door de gebruiker die ze aankoppelt - hier root, want dit script draait
# via sudo. Samba geeft bestandstoegang echter door als de ingelogde
# netwerkgebruiker (pi), die dan tegen deze root-only FUSE-koppeling
# aanloopt. "user_allow_other" in fuse.conf + "-o allow_other" bij het
# koppelen (hieronder bij Stap 4) lossen dat op.
if [ -f /etc/fuse.conf ] && ! grep -q "^user_allow_other" /etc/fuse.conf; then
    echo "user_allow_other" >> /etc/fuse.conf
fi
ok "Tools aanwezig."

# --- Stap 2: iPhone zoeken + vertrouwen --------------------------------------
kop "Stap 2: iPhone zoeken"
UDID="$(idevice_id -l 2>/dev/null | head -1)"
if [ -z "$UDID" ]; then
    err "Geen iPhone gevonden. Zit 'm aan een usb-poort VAN DE PI (niet de pc), en is 'ie ontgrendeld?"
    trap - EXIT
    exit 1
fi
ok "Toestel gevonden: $UDID"

kop "Stap 3: Vertrouwen controleren"
if ! idevicepair -u "$UDID" validate >/dev/null 2>&1; then
    echo "  Nog niet vertrouwd - bevestig 'Vertrouw deze computer' op de iPhone zelf."
    idevicepair -u "$UDID" pair >/dev/null 2>&1
    TELLER=0
    while ! idevicepair -u "$UDID" validate >/dev/null 2>&1; do
        TELLER=$((TELLER + 1))
        if [ "$TELLER" -ge 30 ]; then
            err "Geen bevestiging ontvangen (60 sec. gewacht). Probeer opnieuw."
            trap - EXIT
            exit 1
        fi
        sleep 2
    done
fi
ok "Toestel is vertrouwd."

# --- Stap 4: koppelen ----------------------------------------------------------
kop "Stap 4: iPhone koppelen"
mkdir -p "$LIVE_ROOT/Media" "$LIVE_ROOT/Op mijn iPhone"
MEDIA_MNT="$LIVE_ROOT/Media"
DOCS_MNT="$LIVE_ROOT/Op mijn iPhone"


# 10 augustus 2026: "timeout 20" alleen stuurt na 20 sec. een SIGTERM, maar
# een ifuse-proces dat vastzit in een USB/lockdownd-wachtstand reageert daar
# soms niet op en blijft hangen (leek dan alsof het script vastliep). Met
# "-k 5" wordt er, als SIGTERM niet binnen 5 sec. werkt, alsnog een harde
# SIGKILL gestuurd - dan gaat het script altijd verder, met een duidelijke
# foutmelding in plaats van eindeloos wachten.
# "-o allow_other" hoort bij de fuse.conf-wijziging hierboven bij Stap 1:
# zonder deze optie is de koppeling alleen leesbaar voor root (de gebruiker
# die 'm aanmaakt via sudo), en krijgt Samba - die bestanden opvraagt als de
# ingelogde netwerkgebruiker "pi" - een kernel-niveau toegangsweigering,
# ook al is het NAS-wachtwoord voor pi correct.
LOG="/tmp/pinas_iphone_verkennen.log"
: > "$LOG"
# 10 augustus 2026 (Frans: "waar staat die /tmp map?"): /tmp staat op de Pi
# zelf, niet op de Windows-pc - onbereikbaar via Verkenner en alleen te
# bekijken via een aparte SSH-sessie. Om dat om te zeilen: de inhoud van het
# logbestand hieronder meteen IN DIT SCHERM tonen zodra het relevant is, in
# plaats van er alleen maar naar te verwijzen.
toon_log() {
    if [ -s "$LOG" ]; then
        echo "  ---- inhoud van $LOG ----"
        sed 's/^/  /' "$LOG"
        echo "  --------------------------------"
    fi
}
if ! timeout -k 5 20 ifuse -o allow_other -u "$UDID" "$MEDIA_MNT" >>"$LOG" 2>&1; then
    err "Koppelen van de camerarol/media is mislukt."
    toon_log
    fusermount -uz "$MEDIA_MNT" 2>/dev/null
    MEDIA_MNT=""
fi
if ! timeout -k 5 20 ifuse -o allow_other -u "$UDID" --documents com.apple.DocumentsApp "$DOCS_MNT" >>"$LOG" 2>&1; then
    # 10 augustus 2026 (Frans, opgehelderd met pinas_iphone_diagnose.sh):
    # dit mislukt hier altijd met "InstallationLookupFailed" - Apple's
    # installation proxy behandelt de systeem-Bestanden-app (com.apple.
    # DocumentsApp) niet als een gewone geinstalleerde app met
    # UIFileSharingEnabled, dus house-arrest-toegang wordt geweigerd.
    # Bevestigd met een tweede, onafhankelijke tool (afcclient) - dezelfde
    # foutmelding, dus geen bug in dit script maar een echte beperking van
    # deze koppelmethode voor deze specifieke map. Media/camerarol werkt
    # hier niet door geraakt.
    if grep -q "InstallationLookupFailed" "$LOG" 2>/dev/null; then
        warn "'Op mijn iPhone' niet toegankelijk via deze methode - bekende"
        warn "iOS-beperking (geen bug hier), Media werkt gewoon door."
    else
        warn "Koppelen van 'Op mijn iPhone' is mislukt (gaat door met alleen Media)."
        toon_log
    fi
    fusermount -uz "$DOCS_MNT" 2>/dev/null
    DOCS_MNT=""
fi
if [ -z "$MEDIA_MNT" ] && [ -z "$DOCS_MNT" ]; then
    err "Niets kon gekoppeld worden - stoppen."
    exit 1
fi
ok "iPhone gekoppeld op de Pi."

# --- Stap 5: tijdelijke, alleen-lezen Samba-share ----------------------------
kop "Stap 5: Tijdelijk zichtbaar maken op het netwerk"
# Vindt de bestaande gebruiker van de Opslag-share (meestal "pi"), zodat dit
# met hetzelfde NAS-wachtwoord werkt - geen aparte inlog nodig.
# 10 augustus 2026 (bug gevonden bij live test: het venster liet "gebruiker:
# users=pi" zien in plaats van "pi", en inloggen op de share lukte daardoor
# niet): de oude "print $NF" (laatste veld, gesplitst op spaties) ging ervan
# uit dat smb.conf altijd "valid users = pi" met spaties om het '='-teken
# gebruikt. Op deze Pi staat het zonder spaties ("valid users=pi"), waardoor
# awk het hele "users=pi" als één veld zag. Nu expliciet op '=' splitsen en
# de waarde trimmen - werkt met of zonder spaties eromheen.
NASUSER="$(awk -F'=' '/^\[Opslag\]/{f=1} f&&/valid users/{v=$2; gsub(/^[ \t]+|[ \t]+$/,"",v); print v; exit}' "$SMB_CONF")"
[ -z "$NASUSER" ] && NASUSER="pi"

if grep -q "$MARKER_START" "$SMB_CONF" 2>/dev/null; then
    sed -i "/$MARKER_START/,/$MARKER_END/d" "$SMB_CONF"
fi
{
    echo "$MARKER_START"
    echo "[iPhone]"
    echo "   comment = iPhone (tijdelijk, alleen zolang aangesloten en dit venster open staat)"
    echo "   path = $LIVE_ROOT"
    echo "   browseable = yes"
    echo "   writable = no"
    echo "   valid users = $NASUSER"
    echo "$MARKER_END"
} >> "$SMB_CONF"

if ! testparm -s "$SMB_CONF" >/dev/null 2>&1; then
    err "smb.conf is ongeldig na toevoegen - share weer verwijderd, niets zichtbaar gemaakt."
    sed -i "/$MARKER_START/,/$MARKER_END/d" "$SMB_CONF"
    exit 1
fi
systemctl reload smbd
ok "Tijdelijke share 'iPhone' actief (gebruiker: $NASUSER, hetzelfde NAS-wachtwoord)."

PI_IP="$(hostname -I | awk '{print $1}')"
# 10 augustus 2026 (bug gevonden bij live test: Verkenner gaf "kan
# \UW_PI_IP_ADRES\iPhone niet vinden" - één backslash i.p.v. twee, dus
# geen geldig UNC-pad): dit pad ging eerst door bash's eigen dubbele-
# aanhalingstekens-parsing (die \\ al naar 1 \ terugbrengt) en DAARNA nog
# een keer door echo -e's eigen escape-interpretatie (die de resterende
# \\ opnieuw naar 1 \ terugbrengt) - twee keer halveren = 1 backslash
# over in plaats van 2. Fix: het pad met gewone (niet -e) echo printen,
# zodat het maar 1 keer verwerkt wordt.
echo -e "\n${G}${B}Nu open in Windows Verkenner:${R}"
echo "  \\\\${PI_IP}\\iPhone"
echo ""
echo "Alleen-lezen - je kunt bekijken en kopieren, niet wijzigen of verwijderen op de iPhone."
echo ""
# 10 augustus 2026 (gebruikersvraag na live test): Windows toont soms een eigen
# inlogscherm met gebruiker "$NASUSER" zodra je dit UNC-pad voor het eerst rechtstreeks
# opent (in plaats van via een al gekoppelde schijfletter). Dat is normaal gedrag van
# Windows, geen storing - vandaar deze regel als toelichting vooraf.
echo "Vraagt Windows om een wachtwoord? Gebruikersnaam \"$NASUSER\" laten staan en"
echo "je NAS-wachtwoord invullen (hetzelfde als voor Opslag/Backup). Vink \"Onthoud"
echo "mijn gegevens\" aan, dan wordt dit niet meer gevraagd."
echo ""
read -r -p "Druk op ENTER om te stoppen en op te ruimen... " _
