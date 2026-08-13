"""
Pi NAS - Upload scripts naar de Pi
Staat in: C:\\PiNAS\\Gedeeld\\
Haalt elk bestand op uit de juiste submap en zet het via scp op de Pi.

(12 augustus 2026) Omgezet van nas_upload.bat naar Python, als onderdeel van
de .bat->.py-migratie (zie OVERDRACHT_NIEUWE_CHAT.md). Gedrag exact hetzelfde
gehouden (zelfde bestandenlijst, zelfde scp/ssh-commando's), op één
verbetering na: het Pi-IP komt nu uit picontrol.cfg in plaats van de vaste
UW_PI_IP_ADRES die in de oude .bat stond.
"""
import configparser
import os
import shutil
import subprocess
import sys

PI_USER = "pi"
PI_DIR = "/home/pi"
SSH_OPT = ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10"]

# 13 augustus 2026: losgetrokken uit main() zodat dit de ENE bron van
# waarheid wordt voor "welke bestanden hoort de suite in /home/pi te
# zetten" - pinas_pi_opruimen.pyw hergebruikt deze set om te bepalen wat
# op de Pi WEL verwacht wordt (i.p.v. een eigen, losse kopie van deze
# lijst bij te houden die uit elkaar kan groeien - zelfde reden als bij
# ADDON_SCRIPT eerder deze sessie).
PISERVER_BESTANDEN = (
    "nas_installer.py", "nas_installer_cli.py", "seagate_web.py",
    "seagate-web.service", "smart_plug.py", "smart_plug_config.json",
    "hue_diagnose.py", "pi_welkom.sh", "install.sh", "nas_start.sh",
)
GEDEELD_BESTANDEN = (
    "nas_diagnose.sh", "herstel_backup_hdd.sh", "pinas_theme.py",
    "pinas_wachtwoord.py", "pinas_logging.py", "version.py",
)
PI_BESTANDEN = frozenset(PISERVER_BESTANDEN + GEDEELD_BESTANDEN)


def _script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _nas_root():
    return os.path.dirname(_script_dir())


def _pi_ip():
    cfg = configparser.ConfigParser()
    pad = os.path.join(_nas_root(), "Beheer", "picontrol.cfg")
    if os.path.exists(pad):
        cfg.read(pad, encoding="utf-8")
    return cfg.get("pi", "ip", fallback="UW_PI_IP_ADRES")


def main():
    pi_ip = _pi_ip()
    nas_root = _nas_root()

    print()
    print(" Pi NAS - Upload scripts naar de Pi")
    print(" " + "=" * 62)
    print(f" Pi:       {PI_USER}@{pi_ip}")
    print(f" NAS root: {nas_root}")
    print(" " + "=" * 62)
    print()

    if not shutil.which("scp"):
        print("  FOUT: scp niet gevonden.")
        input("Druk op Enter om af te sluiten...")
        return 1

    geupload = 0
    overgeslagen = 0

    def upload(bronpad, doelnaam):
        nonlocal geupload, overgeslagen
        if os.path.exists(bronpad):
            print(f"  Uploaden: {doelnaam}")
            r = subprocess.run(["scp", bronpad, f"{PI_USER}@{pi_ip}:{PI_DIR}/{doelnaam}"])
            if r.returncode != 0:
                print(f"  FOUT: {doelnaam} kon niet worden geupload")
            else:
                print(f"  OK: {doelnaam}")
                geupload += 1
        else:
            print(f"  Niet gevonden, overgeslagen: {doelnaam}")
            overgeslagen += 1

    print("  [PiServer]")
    piserver = os.path.join(nas_root, "PiServer")
    for bestand in PISERVER_BESTANDEN:
        upload(os.path.join(piserver, bestand), bestand)

    print()
    print("  [Gedeeld]")
    gedeeld = os.path.join(nas_root, "Gedeeld")
    for bestand in GEDEELD_BESTANDEN:
        upload(os.path.join(gedeeld, bestand), bestand)

    def ssh(cmd, tty=False):
        basis = ["ssh"] + (["-t"] if tty else []) + SSH_OPT + [f"{PI_USER}@{pi_ip}", cmd]
        return subprocess.run(basis)

    print()
    print("  Rechten instellen op de Pi...")
    ssh(f"sudo chown pi:pi {PI_DIR}/*.py {PI_DIR}/*.sh 2>/dev/null; "
        f"sudo chmod 755 {PI_DIR}/*.py {PI_DIR}/*.sh 2>/dev/null; echo Rechten OK")

    print()
    print("  Kopieren naar SD-kaart (/boot/firmware/)...")
    ssh(f"for f in {PI_DIR}/*.py {PI_DIR}/*.sh; do sudo cp $f /boot/firmware/ 2>/dev/null; done; echo Bootfs OK")

    print()
    print("  install.sh instellen in .bashrc...")
    ssh("grep -q 'install.sh' /home/pi/.bashrc || echo 'source /home/pi/install.sh' >> /home/pi/.bashrc; echo bashrc OK")

    print()
    print("  Services herstarten op de Pi...")
    ssh("sudo systemctl restart seagate-web && echo seagate-web: herstart OK || echo seagate-web: herstart MISLUKT",
        tty=True)

    print()
    print("  " + "=" * 62)
    print(f"  Klaar! {geupload} bestand(en) geupload, {overgeslagen} overgeslagen.")
    print("  " + "=" * 62)
    print()
    input("Druk op Enter om af te sluiten...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
