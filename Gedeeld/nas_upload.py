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


NAS_ROOT = _nas_root()

# 22 augustus 2026 (Frans, na een screenshot van "Pi opruimen" met 9
# "onbekende" items - waarvan er 3 (de oude status_pagina-scripts)
# terecht waren, maar het onderliggende probleem zat dieper: nas_installer.py
# en nas_installer_cli.py's "Scripts bijwerken vanuit SD-kaart" kopieerden
# BLIND elk .py/.sh-bestand dat op /boot/firmware/ staat naar /home/pi/
# terug - zonder enige toets tegen PI_BESTANDEN of de addon-scripts. Omdat
# de bootfs-spiegeling verderop altijd alles kopieert wat op dat moment in
# /home/pi staat, inclusief oude rommel die daar per ongeluk stond, bleef
# zo'n bestand voor altijd rondspoken: "Pi opruimen" ruimt het op in
# /home/pi, maar de volgende keer dat iemand op de Pi zelf "Scripts
# bijwerken" draait, komt het terug van /boot/firmware/.
#
# Fix: dit script schrijft nu ook een simpel manifest (1 bestandsnaam per
# regel) naar de Pi EN naar /boot/firmware/ - PI_BESTANDEN plus, net als
# pinas_pi_opruimen.pyw al doet (16 augustus 2026-bugfix aldaar), elk
# .sh-bestand dat lokaal in Addons\ staat. Bewust NIET ADDON_SCRIPT uit
# pinas_addon_scripts.py gebruikt - die bevat alleen de 6 primaire
# addon-namen, niet hun _verwijderen/_wachtwoord_resetten-varianten, en
# zou dus precies dezelfde valse "onbekend"-meldingen opleveren die deze
# fix juist moet oplossen. nas_installer.py/_cli.py toetsen "Scripts
# bijwerken" voortaan tegen dit manifest i.p.v. blind alles te kopieren -
# zie de gelijknamige fix in die 2 bestanden.
try:
    ADDON_PI_BESTANDEN = frozenset(
        f for f in os.listdir(os.path.join(NAS_ROOT, "Addons")) if f.endswith(".sh"))
except OSError:
    ADDON_PI_BESTANDEN = frozenset()

MANIFEST_BESTAND = "pinas_manifest.txt"
PI_MANIFEST = PI_BESTANDEN | ADDON_PI_BESTANDEN


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

    # 22 augustus 2026: manifest wegschrijven VOOR de bootfs-spiegeling
    # hieronder, zodat het manifest zelf meteen meekopieert naar
    # /boot/firmware/ (nodig voor een verse SD-kaart, waar nas_installer's
    # "Scripts bijwerken" nog niets in /home/pi heeft staan om uit te lezen).
    print()
    print("  Manifest bijwerken (welke scripts horen op de Pi)...")
    manifest_inhoud = "\n".join(sorted(PI_MANIFEST, key=str.lower)) + "\n"
    manifest_cmd = (
        f"cat > {PI_DIR}/{MANIFEST_BESTAND} << 'PINAS_MANIFEST_EOF'\n"
        f"{manifest_inhoud}"
        "PINAS_MANIFEST_EOF\n"
        f"chmod 644 {PI_DIR}/{MANIFEST_BESTAND} && echo Manifest OK"
    )
    r_manifest = ssh(manifest_cmd)
    if r_manifest.returncode != 0:
        print("  FOUT: manifest kon niet worden weggeschreven naar de Pi")
    else:
        print(f"  OK: {MANIFEST_BESTAND} ({len(PI_MANIFEST)} bestandsnamen)")

    print()
    print("  Rechten instellen op de Pi...")
    ssh(f"sudo chown pi:pi {PI_DIR}/*.py {PI_DIR}/*.sh 2>/dev/null; "
        f"sudo chmod 755 {PI_DIR}/*.py {PI_DIR}/*.sh 2>/dev/null; echo Rechten OK")

    print()
    print("  Kopieren naar SD-kaart (/boot/firmware/)...")
    ssh(f"for f in {PI_DIR}/*.py {PI_DIR}/*.sh {PI_DIR}/{MANIFEST_BESTAND}; do sudo cp $f /boot/firmware/ 2>/dev/null; done; echo Bootfs OK")

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
