"""
Gedeeld/pinas_schijven.py
Vindt de Windows-stationsletter die bij een Samba-share hoort, in plaats
van een vaste letter (Y:/Z:) aan te nemen. Nodig omdat Y:/Z: op een
willekeurige pc al door iets anders bezet kunnen zijn - Windows geeft de
netwerkschijf dan een andere letter, en alles dat vervolgens hardcoded
naar "Y:" of "Z:" zoekt vindt niets, terwijl de verbinding an sich prima
werkt.

Gebruik:
    from pinas_schijven import vind_letter, PI_IP

    opslag_letter = vind_letter("Opslag", pi_ip)   # bijv. "Y" of None
    backup_letter = vind_letter("Backup", pi_ip)   # bijv. "Z" of None
"""

import subprocess
import re


def _net_use_regels():
    """Geeft alle regels van 'net use' terug, of een lege lijst bij een
    fout - nooit een crash, want dit wordt overal aangeroepen waar een
    schijfletter nodig is."""
    try:
        r = subprocess.run(
            ["net", "use"], capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=8)
        return r.stdout.splitlines()
    except Exception:
        return []


def vind_letter(share_naam, ip=None):
    """
    Zoekt welke stationsletter nu gekoppeld is aan de share met deze naam
    (bijv. "Opslag" of "Backup"), ongeacht welke letter Windows toevallig
    toekende. Als ip is opgegeven, moet het UNC-pad ook dat IP bevatten
    (voorkomt verwarring met een share met dezelfde naam op een ander
    apparaat).

    Retourneert de letter zonder dubbele punt (bijv. "Y"), of None als de
    share niet gekoppeld is.
    """
    naam_laag = share_naam.strip().lower()
    for regel in _net_use_regels():
        # Typische 'net use'-regel:
        #   OK           Y:        \\UW_PI_IP_ADRES\Opslag         Microsoft Windows Network
        m = re.search(r"([A-Z]):\s+(\\\\[^\s]+)", regel)
        if not m:
            continue
        letter, unc = m.group(1), m.group(2)
        unc_laag = unc.lower()
        if not unc_laag.rstrip("\\").endswith("\\" + naam_laag):
            continue
        if ip and ip not in unc_laag:
            continue
        return letter
    return None


def vind_letter_of_terugval(share_naam, terugval_letter, ip=None):
    """Zelfde als vind_letter(), maar valt terug op een vaste letter
    (bijv. 'Y') als de share-naam-zoekactie niets oplevert - handig
    tijdens de overgang, of als 'net use' zelf faalt."""
    return vind_letter(share_naam, ip) or terugval_letter
