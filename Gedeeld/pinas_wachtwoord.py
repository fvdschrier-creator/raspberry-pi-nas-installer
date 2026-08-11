"""
Pi NAS Suite — Centraal wachtwoordbeheer
Slaat wachtwoorden op als verborgen bestanden in C:\\PiNAS\\Logs\\
Gebruikt ook cmdkey voor Windows netwerk authenticatie.
Geen externe libraries nodig.
"""

import subprocess
import sys
import os

_LOG_MAP = os.path.join("C:\\", "PiNAS", "Logs")
_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

def _cache_pad(soort):
    os.makedirs(_LOG_MAP, exist_ok=True)
    return os.path.join(_LOG_MAP, f".ww_{soort}.dat")

def set_wachtwoord(wachtwoord, soort="samba"):
    """Sla wachtwoord op. Geeft (True, '') of (False, foutmelding)."""
    try:
        pad = _cache_pad(soort)
        # Verwijder hidden attribuut eerst zodat overschrijven werkt
        if os.path.exists(pad):
            subprocess.run(["attrib", "-H", pad],
                          capture_output=True, creationflags=_CREATE_NO_WINDOW)
        # Schrijf naar cache bestand
        with open(pad, 'w', encoding='utf-8') as f:
            f.write(wachtwoord)
        # Verberg bestand op Windows
        subprocess.run(["attrib", "+H", pad],
                      capture_output=True, creationflags=_CREATE_NO_WINDOW)
        # Ook opslaan via cmdkey voor net use authenticatie
        service = f"Pi_NAS_Suite_{soort}"
        subprocess.run(
            ["cmdkey", f"/add:{service}", "/user:pi", f"/pass:{wachtwoord}"],
            capture_output=True, creationflags=_CREATE_NO_WINDOW)
        # Ook opslaan via cmdkey voor het IP adres direct
        try:
            import configparser
            cfg = configparser.ConfigParser()
            cfg.read(r"C:\PiNAS\Beheer\picontrol.cfg")
            ip = cfg.get("pi", "ip", fallback="")
            if ip:
                subprocess.run(
                    ["cmdkey", f"/add:{ip}", "/user:pi", f"/pass:{wachtwoord}"],
                    capture_output=True, creationflags=_CREATE_NO_WINDOW)
        except Exception:
            pass
        return True, ""
    except Exception as e:
        return False, str(e)

def get_wachtwoord(soort="samba"):
    """Haal wachtwoord op. Geeft string of None."""
    try:
        pad = _cache_pad(soort)
        if os.path.exists(pad):
            with open(pad, 'r', encoding='utf-8') as f:
                ww = f.read().strip()
            return ww if ww else None
        return None
    except:
        return None

def wachtwoord_beschikbaar(soort="samba"):
    return get_wachtwoord(soort) is not None

def verwijder_wachtwoord(soort="samba"):
    try:
        pad = _cache_pad(soort)
        if os.path.exists(pad):
            os.remove(pad)
        subprocess.run(["cmdkey", f"/delete:Pi_NAS_Suite_{soort}"],
                      capture_output=True, creationflags=_CREATE_NO_WINDOW)
        return True
    except:
        return False

def keyring_beschikbaar():
    return True
