"""
NAS Toegang herstellen - LanMan fix
Staat in: C:\\PiNAS\\Beheer\\

Herstelt de toegang tot de Pi NAS als Windows de verbinding weigert met
"Toegang geweigerd" / Systeemfout 5, of met Systeemfout 1219 ("meerdere
gebruikersnamen"). Vereist Administrator-rechten - vraagt zelf om UAC als
dat nog niet het geval is.

(12 augustus 2026) Omgezet van lanman_fix.bat naar Python, als onderdeel van
de .bat->.py-migratie (zie OVERDRACHT_NIEUWE_CHAT.md). Bij die gelegenheid
meteen verbeterd t.o.v. de oude .bat:
  - Werkt nu voor alle geconfigureerde schijven (Opslag/Backup/SpiegelBackup,
    via picontrol.cfg), niet alleen hardcoded Y:/Z: - SpiegelBackup (H:)
    werd voorheen niet meegenomen.
  - Herstart ook de Workstation-service (LanmanWorkstation), niet alleen
    'net use /delete'. Op 11 augustus 2026 bleek met Frans live dat een
    SMB-sessie soms wel zichtbaar is in PowerShell's Get-SmbConnection maar
    niet in 'net use' - zo'n sessie blokkeert nieuwe verbindingen (Systeem-
    fout 1219) en is alleen met een dienstherstart echt weg te krijgen.
    Zie _herstart_smb_client_verhoogd() in Pi_NAS_Menu.pyw voor dezelfde fix.
"""
import configparser
import ctypes
import os
import subprocess
import sys
import time

_CREATE_NO_WINDOW = 0x08000000


def _nas_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _herstart_verhoogd():
    """Start dit script opnieuw met Administrator-rechten (UAC-melding)."""
    params = " ".join(f'"{a}"' for a in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{os.path.abspath(__file__)}" {params}', None, 1)


def _pi_ip(cfg):
    return cfg.get("pi", "ip", fallback="UW_PI_IP_ADRES")


def _schijf_config(cfg):
    """Schijfletter -> Samba-share, zelfde logica/valt terug op Y/Z als
    Pi_NAS_Menu.pyw's _schijf_config()."""
    paren = {}
    try:
        if cfg.has_section("schijven"):
            for letter, share in cfg.items("schijven"):
                L = letter.strip().upper().rstrip(":")
                if L and share.strip():
                    paren[L] = share.strip()
    except Exception:
        pass
    if not paren:
        paren = {"Y": "Opslag", "Z": "Backup"}
    return paren


def _nas_wachtwoord():
    sys.path.insert(0, os.path.join(_nas_root(), "Gedeeld"))
    try:
        from pinas_wachtwoord import get_wachtwoord, set_wachtwoord
    except Exception:
        return None
    ww = get_wachtwoord("samba")
    if ww:
        return ww
    ww = input("Wachtwoord voor gebruiker 'pi' (wordt onthouden): ").strip()
    if ww:
        try:
            set_wachtwoord(ww, "samba")
        except Exception:
            pass
    return ww or None


def main():
    if not _is_admin():
        print()
        print("Dit script heeft Administrator-rechten nodig - UAC-melding volgt...")
        _herstart_verhoogd()
        return 0

    cfg_pad = os.path.join(_nas_root(), "Beheer", "picontrol.cfg")
    cfg = configparser.ConfigParser()
    if os.path.exists(cfg_pad):
        cfg.read(cfg_pad, encoding="utf-8")
    pi_ip = _pi_ip(cfg)
    paren = _schijf_config(cfg)

    print()
    print("=" * 60)
    print(" NAS Toegang herstellen - LanMan fix")
    print("=" * 60)
    print()
    print("Dit script herstelt de toegang tot de Pi NAS als Windows de")
    print("verbinding weigert met \"Toegang geweigerd\", Systeemfout 5, of")
    print("Systeemfout 1219 (\"meerdere gebruikersnamen\").")
    print()
    print("Wat dit doet:")
    print("  1. Past Windows LanMan-beveiliging aan zodat de NAS-shares")
    print("     bereikbaar worden")
    print("  2. Schakelt onveilige gastverbindingen in (vereist voor Pi")
    print("     Samba-shares)")
    print("  3. Herstart de Workstation-service (breekt ALLE bestaande")
    print("     SMB-verbindingen af, ook onzichtbare)")
    letters = ", ".join(f"{l}:" for l in paren)
    print(f"  4. Koppelt {letters} opnieuw aan de NAS")
    print()
    input("Druk op Enter om te beginnen...")
    print()

    # -- Stap 1: LanMan-register aanpassen --------------------------------
    print("Stap 1: LanMan-beveiliging aanpassen...")
    subprocess.run(["reg", "add",
                     r"HKLM\SYSTEM\CurrentControlSet\Services\LanmanWorkstation\Parameters",
                     "/v", "AllowInsecureGuestAuth", "/t", "REG_DWORD", "/d", "1", "/f"],
                    capture_output=True, creationflags=_CREATE_NO_WINDOW)
    subprocess.run(["reg", "add", r"HKLM\SYSTEM\CurrentControlSet\Control\Lsa",
                     "/v", "LmCompatibilityLevel", "/t", "REG_DWORD", "/d", "1", "/f"],
                    capture_output=True, creationflags=_CREATE_NO_WINDOW)
    print("OK: Register aangepast.")
    print()

    # -- Stap 2: Workstation-service herstarten ----------------------------
    # (11 augustus 2026) Vervangt de losse 'net use /delete'-pogingen van de
    # oude .bat: een herstart van de SMB-cliëntdienst breekt ECHT alles af,
    # ook een sessie die 'net use' zelf niet laat zien.
    print("Stap 2: Workstation-service herstarten (sluit alle NAS-verbindingen)...")
    print()
    print("LET OP: sluit eerst Sync & Backup (PiNAS Sync) en alle Verkenner-")
    print(f"vensters met {letters} open staan.")
    input("Druk daarna op Enter om door te gaan...")
    subprocess.run(["net", "stop", "lanmanworkstation", "/y"],
                    capture_output=True, creationflags=_CREATE_NO_WINDOW)
    subprocess.run(["net", "start", "lanmanworkstation"],
                    capture_output=True, creationflags=_CREATE_NO_WINDOW)
    time.sleep(2)
    print("OK: Verbindingen verwijderd.")
    print()

    # -- Stap 3: opnieuw koppelen -------------------------------------------
    print("Stap 3: schijven opnieuw koppelen...")
    print()
    nasww = _nas_wachtwoord()
    if not nasww:
        print("FOUT: geen NAS-wachtwoord beschikbaar - kan niet koppelen.")
        print()
        input("Druk op Enter om af te sluiten...")
        return 1

    for letter, share in paren.items():
        doel = f"\\\\{pi_ip}\\{share}"
        gelukt = False
        for poging in (1, 2):
            r = subprocess.run(
                ["net", "use", f"{letter}:", doel, "/user:pi", nasww, "/persistent:yes"],
                capture_output=True, text=True, creationflags=_CREATE_NO_WINDOW)
            if r.returncode == 0:
                gelukt = True
                break
            if poging == 1:
                print(f"Eerste poging voor {letter}: mislukt, nog een keer proberen na korte pauze...")
                time.sleep(3)
        if gelukt:
            print(f"OK: {letter}: gekoppeld ({share})")
        else:
            print(f"WAARSCHUWING: {letter}: koppelen mislukt.")
            print("Controleer of de Pi bereikbaar is en het wachtwoord klopt.")
    print()

    print("=" * 60)
    print(" Klaar!")
    print("=" * 60)
    print()
    print(f"{letters} zijn nu gekoppeld aan de Pi NAS.")
    print()
    print("Als het nog steeds niet werkt:")
    print("  1. Herstart Windows en probeer opnieuw")
    print(f"  2. Controleer of de Pi aan staat (ping {pi_ip})")
    print("  3. Controleer het NAS-wachtwoord (Beheer - Beveiliging)")
    print()
    input("Druk op Enter om af te sluiten...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
