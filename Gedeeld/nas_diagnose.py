"""
Pi NAS Diagnose
Staat in: C:\\PiNAS\\Gedeeld\\
Gebruik:   python nas_diagnose.py  (of via Pi NAS Menu)

(12 augustus 2026) Omgezet van nas_diagnose.bat naar Python, als onderdeel
van de .bat->.py-migratie (zie OVERDRACHT_NIEUWE_CHAT.md). Gedrag exact
hetzelfde gehouden (zelfde menu, zelfde SCP/SSH-commando's), op één
verbetering na: het Pi-IP-adres wordt nu net als de rest van de suite uit
picontrol.cfg gelezen in plaats van een vast (in de .bat handmatig in te
vullen) adres - dat was in de oude .bat de placeholdertekst UW_PI_IP_ADRES,
dus dit script werkte alleen als je 'm zelf eerst had aangepast.
"""
import configparser
import os
import subprocess
import sys

PI_USER = "pi"
PI_DIR = "/home/pi"


def _script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _nas_root():
    return os.path.dirname(_script_dir())


def _pi_ip():
    cfg = configparser.ConfigParser()
    for pad in (
        os.path.join(_nas_root(), "Beheer", "picontrol.cfg"),
        os.path.join(_script_dir(), "picontrol.cfg"),
    ):
        if os.path.exists(pad):
            cfg.read(pad, encoding="utf-8")
            break
    return cfg.get("pi", "ip", fallback="UW_PI_IP_ADRES")


def _run(cmd):
    """Draait een commando zichtbaar (erft stdout/stderr), geeft returncode terug."""
    print()
    return subprocess.call(cmd)


def main():
    pi_ip = _pi_ip()
    nas_dir = _script_dir()
    sh_pad = os.path.join(nas_dir, "nas_diagnose.sh")
    output_pad = os.path.join(nas_dir, "nas_diagnose_output.txt")

    print()
    print(" Pi NAS Diagnose")
    print(" " + "=" * 60)
    print(f" Pi:  {PI_USER}@{pi_ip}")
    print(" " + "=" * 60)
    print()
    print(" Wat wil je doen?")
    print()
    print(" 1  Diagnose uitvoeren (eenmalig)")
    print(" 2  Diagnose installeren op Pi (herbruikbaar via SSH)")
    print(" 3  Diagnose verwijderen van Pi")
    print(" 4  Afsluiten")
    print()
    keuze = input("  Keuze (1-4): ").strip()

    if keuze == "1":
        print()
        print("  Uploaden...")
        rc = _run(["scp", sh_pad, f"{PI_USER}@{pi_ip}:{PI_DIR}/nas_diagnose.sh"])
        if rc != 0:
            print("  FOUT: Upload mislukt")
            input("Druk op Enter om af te sluiten...")
            return 1
        print()
        print(" " + "=" * 60)
        with open(output_pad, "w", encoding="utf-8") as f:
            proc = subprocess.run(
                ["ssh", f"{PI_USER}@{pi_ip}", f"sudo bash {PI_DIR}/nas_diagnose.sh"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            f.write(proc.stdout or "")
            print(proc.stdout or "")
        print(" " + "=" * 60)
        print()
        print(f"  Output opgeslagen in: {output_pad}")
        print()
        print("  Script verwijderen...")
        _run(["ssh", f"{PI_USER}@{pi_ip}", f"rm -f {PI_DIR}/nas_diagnose.sh && echo Verwijderd"])

    elif keuze == "2":
        print()
        print("  Uploaden...")
        rc = _run(["scp", sh_pad, f"{PI_USER}@{pi_ip}:{PI_DIR}/nas_diagnose.sh"])
        if rc != 0:
            print("  FOUT: Upload mislukt")
            input("Druk op Enter om af te sluiten...")
            return 1
        _run(["ssh", f"{PI_USER}@{pi_ip}",
              f"chmod 755 {PI_DIR}/nas_diagnose.sh && chown pi:pi {PI_DIR}/nas_diagnose.sh && echo OK"])
        print()
        print(" " + "=" * 60)
        print("  Geinstalleerd. Starten via SSH:")
        print("  sudo bash /home/pi/nas_diagnose.sh")
        print(" " + "=" * 60)

    elif keuze == "3":
        print()
        _run(["ssh", f"{PI_USER}@{pi_ip}", f"rm -f {PI_DIR}/nas_diagnose.sh && echo Verwijderd"])
        print("  OK: Script verwijderd.")

    print()
    input("Druk op Enter om af te sluiten...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
