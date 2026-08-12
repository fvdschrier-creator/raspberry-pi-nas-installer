"""
TigerVNC Viewer installeren voor Pi NAS (Pi 5)
Staat in: C:\\PiNAS\\Beheer\\

(12 augustus 2026) Omgezet van install_vnc_viewer.bat naar Python, als
onderdeel van de .bat->.py-migratie (zie OVERDRACHT_NIEUWE_CHAT.md). Gedrag
exact hetzelfde gehouden, op één verbetering na: het voorgestelde Pi-IP komt
nu uit picontrol.cfg (net als de rest van de suite) in plaats van de vaste
placeholdertekst UW_PI_IP_ADRES die in de oude .bat stond - je kon en kunt
nog steeds een ander adres intypen, alleen is het voorstel nu al goed.
"""
import configparser
import os
import subprocess
import sys
import tempfile
import time
import webbrowser


def _nas_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pi_ip():
    cfg = configparser.ConfigParser()
    pad = os.path.join(_nas_root(), "Beheer", "picontrol.cfg")
    if os.path.exists(pad):
        cfg.read(pad, encoding="utf-8")
    return cfg.get("pi", "ip", fallback="UW_PI_IP_ADRES")


def _vnc_locatie():
    for basis in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                  os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
        pad = os.path.join(basis, "TigerVNC", "vncviewer.exe")
        if os.path.exists(pad):
            return pad
    return None


def _vraag_verbinden(vncloc, pi_ip):
    antwoord = input("  Wil je TigerVNC nu openen en verbinden met de Pi? [J/n]: ").strip().lower()
    if antwoord == "n":
        return
    ingevoerd = input(f"  IP-adres van je Pi [{pi_ip}]: ").strip()
    doel = ingevoerd or pi_ip
    subprocess.Popen([vncloc, f"{doel}:5901"])


def _handmatig():
    print()
    print("  Downloadpagina openen in browser...")
    webbrowser.open("https://github.com/TigerVNC/tigervnc/releases/latest")
    print()
    print("  " + "=" * 60)
    print("  Stappen:")
    print("  1. Download: tigervnc64-x.x.x.exe")
    print("  2. Dubbelklik en installeer")
    print("  3. Start TigerVNC Viewer via het Startmenu")
    print("  4. Typ als VNC server: <IP-van-je-Pi>:5901")
    print("  5. Voer het VNC wachtwoord in")
    print("  " + "=" * 60)


def _automatisch(pi_ip):
    print()
    print("  Nieuwste versie ophalen van GitHub...")
    ps_cmd = (
        "$r = Invoke-RestMethod 'https://api.github.com/repos/TigerVNC/tigervnc/releases/latest';"
        "$a = $r.assets | Where-Object { $_.name -like 'tigervnc64-*.exe' } | Select-Object -First 1;"
        "if ($a) { Write-Output $a.browser_download_url }"
    )
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd],
                            capture_output=True, text=True, timeout=30)
        url = (r.stdout or "").strip()
    except Exception:
        url = ""

    if not url:
        print("  Kon nieuwste versie niet ophalen - handmatig downloaden...")
        _handmatig()
        return

    print(f"  Downloaden: {url}")
    print("  Even geduld...")
    installer = os.path.join(tempfile.gettempdir(), "tigervnc_installer.exe")
    dl_cmd = f"Invoke-WebRequest -Uri '{url}' -OutFile '{installer}' -UseBasicParsing"
    subprocess.run(["powershell", "-NoProfile", "-Command", dl_cmd])

    if not os.path.exists(installer):
        print("  Download mislukt - handmatig downloaden...")
        _handmatig()
        return

    print("  Installeren...")
    subprocess.run([installer, "/silent", "/install"])
    time.sleep(15)
    try:
        os.remove(installer)
    except OSError:
        pass

    vncloc = _vnc_locatie()
    if vncloc:
        print("  OK: TigerVNC geinstalleerd.")
        print()
        _vraag_verbinden(vncloc, pi_ip)
    else:
        print("  WAARSCHUWING: Installatie mogelijk niet voltooid.")
        print("  Controleer of je Administrator rechten hebt.")


def main():
    pi_ip = _pi_ip()
    print()
    print(" Pi NAS - TigerVNC Viewer installeren")
    print(" " + "=" * 60)
    print(" TigerVNC Viewer laat je het grafische bureaublad van de")
    print(" Raspberry Pi 5 zien vanuit Windows - zonder scherm op de Pi.")
    print(" Verbinding via poort 5901.")
    print(" " + "=" * 60)
    print()

    vncloc = _vnc_locatie()
    if vncloc:
        print("  TigerVNC Viewer is al geinstalleerd!")
        print()
        _vraag_verbinden(vncloc, pi_ip)
    else:
        print("  TigerVNC Viewer is nog niet geinstalleerd.")
        print()
        print("  Keuze:")
        print("  1  Automatisch downloaden en installeren")
        print("  2  Handmatig downloaden (opent browser)")
        print("  3  Annuleren")
        print()
        keuze = input("  Keuze (1-3): ").strip()
        if keuze == "1":
            _automatisch(pi_ip)
        elif keuze == "2":
            _handmatig()
        else:
            print("  Geannuleerd.")

    print()
    print("  " + "=" * 60)
    print("  TigerVNC verbinden met Pi 5:")
    print(f"    VNC server: {pi_ip}:5901  (let op poort 5901!)")
    print("    Wachtwoord: ingesteld via vncpasswd op de Pi")
    print("  " + "=" * 60)
    print()
    input("Druk op Enter om af te sluiten...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
