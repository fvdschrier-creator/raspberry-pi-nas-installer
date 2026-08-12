"""
Gedeeld/pinas_pi_status.py

Centrale, ENIGE plek voor de SSH-statuscheck van alle Pi-diensten en de
op-de-Pi-geinstalleerde addon-versie-hashes.

4 augustus 2026 (Frans, staande regel): Pi_NAS_Menu.pyw en
pinas_addons_beheer.pyw hadden allebei hun EIGEN kopie van bijna
hetzelfde SSH-commando en bijna dezelfde parsing-logica - apart
onderhouden, licht uit elkaar gegroeid (bijv. Pi-hole/ZeroTier kregen in
Pi_NAS_Menu.pyw ooit een preciezere 3-standen-detectie, die nooit is
overgenomen in pinas_addons_beheer.pyw). Dat was de directe oorzaak van
de Dashboard-status-bug van vandaag: een nieuwe dienst moest op 2 plekken
apart worden toegevoegd, en dat gebeurde niet consistent.

Gebruik (per aanroepend bestand):
    import pinas_pi_status

    resultaat = pinas_pi_status.haal_pi_status(PI_IP)
    if resultaat["bereikbaar"]:
        ...

Geeft ENGELSE waarden terug ("active"/"stopped"/"absent"/"unknown" voor
de 3-standen-diensten, True/False voor de simpele aan/uit-diensten) -
wie dit aanroept vertaalt zelf naar de eigen weergaaltaal (bijv.
Nederlands in pinas_addons_beheer.pyw) indien nodig. Zie
vertaal_naar_nederlands() onderaan voor een kant-en-klare vertaler.

Bewust GEEN wijziging aan het gedrag van de bestaande schermen - dit
bestand verplaatst alleen de databron naar 1 plek, de callers bepalen
zelf nog steeds wat ze ermee tonen.
"""
import subprocess

# De volledige combi-SSH-opdracht - dit is de ENIGE plek waar deze tekst
# nog hoort te staan. Nieuwe/gewijzigde diensten hier toevoegen, dan
# zien BEIDE schermen het vanzelf.
_SSH_COMMANDO = (
    # Samba
    "st=$(systemctl is-active smbd 2>/dev/null); echo smbd:$st; "
    # Nextcloud - via config.php (draait via Apache, geen eigen service)
    "if [ -f /var/www/html/nextcloud/config/config.php ] || "
    "   [ -f /var/www/nextcloud/config/config.php ]; "
    "then echo nextcloud:active; else echo nextcloud:inactive; fi; "
    # FileBrowser - service of binair
    "st=$(systemctl is-active filebrowser 2>/dev/null); "
    "en=$(systemctl is-enabled filebrowser 2>/dev/null); "
    "if [ \"$st\" = \"active\" ] || [ \"$en\" = \"enabled\" ] || "
    "   command -v filebrowser >/dev/null 2>&1; "
    "then echo filebrowser:active; else echo filebrowser:$st; fi; "
    # Cockpit - is-enabled als fallback (socket-based, zelden "active")
    "st=$(systemctl is-active cockpit 2>/dev/null); "
    "en=$(systemctl is-enabled cockpit 2>/dev/null); "
    "if [ \"$st\" = \"active\" ] || [ \"$en\" = \"enabled\" ] || [ \"$en\" = \"static\" ]; "
    "then echo cockpit:active; else echo cockpit:$st; fi; "
    # Externe HDD service
    "st=$(systemctl is-active seagate-web 2>/dev/null); echo seagate-web:$st; "
    # 6 augustus 2026 (Frans: "in status geeft hij wel actief [voor Externe
    # HDD svc], maar hij is niet gemount - dat geeft status niet aan"):
    # seagate-web is de systemd-DIENST die de smart plug bedient - die kan
    # actief zijn terwijl de Backup-schijf zelf (nog) niet gemount is
    # (bijv. vlak na aanzetten, of als de HDD om een andere reden niet
    # mount). Aparte, eigen check op de daadwerkelijke mount.
    # 6 augustus 2026 (Frans: "kan niet zijn hdd backup gemount als hij
    # niet actief is?? - screenshot toonde Externe HDD UIT terwijl
    # Backup-schijf gemount toch 'actief' liet zien): mountpoint -q
    # controleert alleen of Linux DENKT dat er iets gemount is - als de
    # smart plug de stroom eraf haalt zonder eerst netjes umount te doen
    # (bijv. buiten de eigen Uitzetten-knop om), blijft het mountpunt in
    # Linux' ogen "gemount" staan terwijl de schijf er niet meer is (een
    # spookmount). Nu ook een echte I/O-poging (timeout 3 ls) - die faalt
    # snel en duidelijk als het apparaat weg is, in tegenstelling tot
    # mountpoint -q die daar niets van merkt.
    "if mountpoint -q /mnt/backup 2>/dev/null && timeout 3 ls /mnt/backup >/dev/null 2>&1; then "
    "echo backup_mount:active; "
    "else echo backup_mount:inactive; fi; "
    # Pi-hole - via 'systemctl cat' (bestaat de unit uberhaupt), niet
    # 'command -v': dat faalde eerder ten onrechte in een niet-
    # interactieve SSH-sessie omdat /usr/sbin niet in het PATH van een
    # gewone gebruiker zit.
    "if systemctl cat pihole-FTL >/dev/null 2>&1; then "
    "  st=$(systemctl is-active pihole-FTL 2>/dev/null); "
    "  if [ \"$st\" = \"active\" ]; then echo pihole:active; else echo pihole:stopped; fi; "
    "else echo pihole:absent; fi; "
    # ZeroTier (Pi-kant)
    "if systemctl cat zerotier-one >/dev/null 2>&1; then "
    "  st=$(systemctl is-active zerotier-one 2>/dev/null); "
    "  if [ \"$st\" = \"active\" ]; then echo zerotier:active; else echo zerotier:stopped; fi; "
    "else echo zerotier:absent; fi; "
    # Vaultwarden - draait in Docker, geen systemd-unit
    "if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx vaultwarden; then "
    "  if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx vaultwarden; "
    "  then echo vaultwarden:active; else echo vaultwarden:stopped; fi; "
    "else echo vaultwarden:absent; fi; "
    # Printserver (CUPS)
    "if systemctl cat cups >/dev/null 2>&1; then "
    "  st=$(systemctl is-active cups 2>/dev/null); "
    "  if [ \"$st\" = \"active\" ]; then echo printer:active; else echo printer:stopped; fi; "
    "else echo printer:absent; fi; "
    # PiNAS Dashboard
    "if systemctl cat pinas-dashboard >/dev/null 2>&1; then "
    "  st=$(systemctl is-active pinas-dashboard 2>/dev/null); "
    "  if [ \"$st\" = \"active\" ]; then echo dashboard:active; else echo dashboard:stopped; fi; "
    "else echo dashboard:absent; fi; "
    # Versie-afdruk van elke add-on (zie schrijf_versie_marker() in elk
    # .sh-script) - om te kunnen waarschuwen als een lokaal bijgewerkt
    # bestand nog niet naar de Pi geupload/geinstalleerd is.
    "for k in nextcloud pihole zerotier vaultwarden printer dashboard; do "
    "  if [ -f /etc/pinas-addon-versies/$k.sha256 ]; then "
    "    echo \"hash_$k:$(cat /etc/pinas-addon-versies/$k.sha256 2>/dev/null)\"; "
    "  else echo \"hash_$k:geen\"; fi; "
    "done"
)

# Diensten met een simpele aan/uit-status (True/False) i.p.v. 3 standen.
_BOOLEAN_DIENSTEN = ("smbd", "nextcloud", "filebrowser", "cockpit",
                      "seagate-web", "backup_mount")

# Diensten met 3-standen-status ("active"/"stopped"/"absent").
_DRIESTANDEN_DIENSTEN = ("pihole", "zerotier", "vaultwarden",
                         "printer", "dashboard")

_ADDON_SLEUTELS = ("nextcloud", "pihole", "zerotier", "vaultwarden",
                    "printer", "dashboard")


def _lege_resultaat():
    resultaat = {"bereikbaar": False}
    for k in _BOOLEAN_DIENSTEN:
        resultaat[k] = False
    for k in _DRIESTANDEN_DIENSTEN:
        resultaat[k] = "unknown"
    for k in _ADDON_SLEUTELS:
        resultaat[f"hash_{k}"] = None
    return resultaat


def haal_pi_status(pi_ip, timeout=15):
    """Voert de combi-SSH-check 1x uit en geeft 1 dict terug met de
    status van alle Pi-diensten + addon-versie-hashes. Bij een
    onbereikbare Pi (SSH mislukt of geen bruikbare uitvoer) blijft
    resultaat["bereikbaar"] False en alle overige waarden op hun
    neutrale standaardwaarde (False/"unknown"/None) - NOOIT een gok
    doen bij een mislukte verbinding."""
    resultaat = _lege_resultaat()
    try:
        r = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=6", "-o", "StrictHostKeyChecking=no",
             "-o", "BatchMode=yes", f"pi@{pi_ip}", _SSH_COMMANDO],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=timeout)
        if not r.stdout.strip():
            return resultaat
        resultaat["bereikbaar"] = True
        for regel in r.stdout.strip().splitlines():
            if ":" not in regel:
                continue
            svc, _, st = regel.partition(":")
            svc, st = svc.strip(), st.strip()
            if svc.startswith("hash_"):
                if svc in resultaat:
                    resultaat[svc] = st
            elif svc in _BOOLEAN_DIENSTEN:
                resultaat[svc] = (st == "active")
            elif svc in _DRIESTANDEN_DIENSTEN:
                resultaat[svc] = st
    except Exception:
        pass
    return resultaat


_NL_VERTALING = {"active": "actief", "stopped": "gestopt",
                  "absent": "afwezig", "unknown": None}


def vertaal_naar_nederlands(waarde):
    """Zet een Engelse 3-standen-waarde ('active'/'stopped'/'absent') om
    naar de Nederlandse ('actief'/'gestopt'/'afwezig') die
    pinas_addons_beheer.pyw intern gebruikt. 'unknown' wordt None (zelfde
    betekenis als de oude 'Pi niet bereikbaar'-None-waarde)."""
    return _NL_VERTALING.get(waarde, waarde)
