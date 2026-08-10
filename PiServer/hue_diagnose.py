#!/usr/bin/env python3
"""
Hue diagnose — controleert of de geconfigureerde plug_id in
smart_plug_config.json daadwerkelijk bij de juiste Hue-stekker
hoort. Draai dit op de Pi met: python3 hue_diagnose.py

Als het geconfigureerde bridge_ip niet meer werkt (DHCP-wissel),
wordt automatisch gezocht naar het huidige IP via meethue.com/SSDP
en de config bijgewerkt — net als smart_plug.py nu zelf ook doet.
"""
import json, urllib.request, sys, os

CONFIG_FILE = "/home/pi/smart_plug_config.json"

# Hergebruik de auto-discovery uit smart_plug.py als dat bestand
# beschikbaar is (zelfde map), anders gewone foutmelding.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from smart_plug import hue_discover_bridge_ip, _hue_bridge_reageert
    _HAS_DISCOVERY = True
except Exception:
    _HAS_DISCOVERY = False

def main():
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
    except Exception as e:
        print(f"FOUT: kon {CONFIG_FILE} niet lezen: {e}")
        sys.exit(1)

    if cfg.get("type") != "hue":
        print(f"Config-type is '{cfg.get('type')}', niet 'hue'. Dit script is alleen voor Hue.")
        sys.exit(1)

    h = cfg.get("hue", {})
    bridge_ip = h.get("bridge_ip")
    api_key   = h.get("api_key")
    plug_id   = h.get("plug_id")

    if not bridge_ip or not api_key:
        print("FOUT: bridge_ip of api_key ontbreekt in de config.")
        sys.exit(1)

    print(f"Bridge IP (geconfigureerd):        {bridge_ip}")
    print(f"Geconfigureerd plug_id: {plug_id}")
    print()

    # Check of het geconfigureerde IP nog werkt; zo niet, automatisch
    # opnieuw zoeken (net als smart_plug.py bij elke aan/uit-actie doet).
    actief_ip = bridge_ip
    if _HAS_DISCOVERY and not _hue_bridge_reageert(bridge_ip):
        print(f"Bridge reageert niet meer op {bridge_ip} — automatisch zoeken...")
        gevonden = hue_discover_bridge_ip()
        if gevonden:
            print(f"Nieuw IP gevonden: {gevonden}")
            if gevonden != bridge_ip:
                cfg["hue"]["bridge_ip"] = gevonden
                with open(CONFIG_FILE, "w") as f:
                    json.dump(cfg, f, indent=2)
                print(f"Config bijgewerkt naar bridge_ip = {gevonden}")
            actief_ip = gevonden
        else:
            print("FOUT: kon geen Hue Bridge vinden via auto-discovery.")
            sys.exit(1)
        print()

    try:
        r = urllib.request.urlopen(f"http://{actief_ip}/api/{api_key}/lights", timeout=5)
        lights = json.loads(r.read())
    except Exception as e:
        print(f"FOUT: kon Hue Bridge niet bereiken op {actief_ip}: {e}")
        sys.exit(1)

    print("Alle apparaten op deze Hue Bridge:")
    print("-" * 60)
    for id, d in lights.items():
        naam   = d.get("name", "?")
        status = d.get("state", {}).get("on")
        status_txt = "AAN" if status else "UIT" if status is False else "onbekend"
        merker = "  <-- DIT IS GECONFIGUREERD" if id == str(plug_id) else ""
        print(f"  ID {id:>3}  |  {naam:<25}  |  {status_txt}{merker}")
    print("-" * 60)

    if str(plug_id) not in lights:
        print()
        print(f"!! WAARSCHUWING: plug_id '{plug_id}' bestaat niet (meer) op deze Bridge.")
        print("   Dit verklaart waarom de status altijd verkeerd/onbekend is.")
    else:
        d = lights[str(plug_id)]
        naam = d.get("name", "?")
        status = d.get("state", {}).get("on")
        print()
        print(f"Geconfigureerd apparaat is: '{naam}' — huidige status: "
              f"{'AAN' if status else 'UIT'}")
        print()
        print("Is dit niet de Seagate/HDD-stekker? Pas dan 'plug_id' in")
        print(f"{CONFIG_FILE} aan naar het juiste ID uit de lijst hierboven.")

if __name__ == "__main__":
    main()
