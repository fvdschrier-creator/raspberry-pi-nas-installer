#!/usr/bin/env python3
"""
Gedeeld/controleer_documentatie_consistentie.py

Checkt of elke add-on die in pinas_addons_beheer.pyw's _ADDON_SCRIPT
staat, ook daadwerkelijk voorkomt in de plekken waar 'ie hoort te
staan: de Topografie, Structuurcheck (NAS_Map_Beheer.pyw) en de
Handleiding-bouwer. Meldt per addon en per bestand of die ontbreekt.

10 augustus 2026: de Functieoverzicht-bouwer (build_functieoverzicht.py)
is uit deze lijst gehaald - dat bestand bestaat niet meer, vervangen
door een compacte pagina in PiNAS_Suite_Presentatie.pptx.

Checkt BEWUST NIET op het Toegangsoverzicht (PiNAS_Toegangsoverzicht.md/
.pdf) - dat bevat echte wachtwoorden en hoort nooit in de suite-boom te
staan (5 augustus 2026), dus "niet gevonden" zou daar geen echt gat zijn.

4 augustus/5 augustus 2026 (Frans, advieslijst na de PiNAS Dashboard-
integratie): "een script dat checkt of elke addon uit _ADDON_SCRIPT ook
voorkomt in Toegangsoverzicht, Topografie, Structuurcheck en de
Handleiding, en waarschuwt bij een gat" - dit soort gaten kwam die dag
2x voor (de gemiste Printserver-rij in de PDF-generator, en de
vergeten dashboard-parsing-tak) en werden toen pas gevonden doordat
Frans het toevallig zag in een screenshot.

_ADDON_SCRIPT zelf blijft de ENE bron van waarheid voor "welke addons
bestaan er" - dit script leest die lijst uit pinas_addons_beheer.pyw
uit (in plaats van een eigen, tweede lijst te onderhouden die zelf ook
weer uit de pas zou kunnen lopen).

Gebruik:
    python3 controleer_documentatie_consistentie.py
Standaard wordt aangenomen dat dit script in C:\\PiNAS\\Gedeeld\\ staat en
de andere bestanden in hun gebruikelijke submappen (Addons, Publicatie,
Gedeeld) - met --root geef je een ander pad aan de suite-hoofdmap op.
"""
import argparse
import os
import re
import sys

# Voor elke addon-sleutel (zoals in _ADDON_SCRIPT) de mensleesbare naam
# zoals die in de documentatie wordt gebruikt. Dit koppelbestandje is
# bewust klein en verandert zelden (een addon-naam wijzigt niet vaak) -
# de addon-LIJST zelf komt uit pinas_addons_beheer.pyw, niet hiervandaan.
NAAM_MAP = {
    "nextcloud": "Nextcloud",
    "pihole": "Pi-hole",
    "zerotier": "ZeroTier",
    "vaultwarden": "Vaultwarden",
    "statuspagina": "Mobiele statuspagina",
    "printer": "Printserver",
    "dashboard": "Dashboard",
}

# (relatief pad vanaf de suite-hoofdmap, mensleesbare naam voor de melding)
TE_CONTROLEREN_BESTANDEN = [
    # 5 augustus 2026 (Frans, terecht): PiNAS_Toegangsoverzicht.md/.pdf en
    # hun builder horen NOOIT in de suite-boom te staan (bevatten echte
    # wachtwoorden, risico op lekken via Starter Kit/publieke versie) -
    # enige juiste plek is de Backup-schijf\PiNAS Toegang, buiten C:\PiNAS.
    # Dit script controleert daarom BEWUST NIET op die twee bestanden -
    # "niet gevonden in de suite-boom" is voor hen het GOEDE antwoord,
    # geen gat om te dichten.
    ("Publicatie/PiNAS_Topografie.html", "Topografie"),
    ("Beheer/NAS_Map_Beheer.pyw", "Structuurcheck (NAS_Map_Beheer.pyw)"),
    ("Publicatie/build_suite_handleiding.py", "Handleiding-bouwer"),
]

ADDONS_BEHEER_PAD = "Addons/pinas_addons_beheer.pyw"


def laad_addon_lijst(pad):
    """Leest _ADDON_SCRIPT rechtstreeks uit pinas_addons_beheer.pyw -
    dat blijft de ENE bron van waarheid voor welke addons bestaan."""
    if not os.path.exists(pad):
        print(f"FOUT: kan {pad} niet vinden - kan de addon-lijst niet lezen.")
        return None
    with open(pad, encoding="utf-8") as f:
        inhoud = f.read()
    match = re.search(r"_ADDON_SCRIPT\s*=\s*\{(.*?)\}", inhoud, re.DOTALL)
    if not match:
        print(f"FOUT: _ADDON_SCRIPT niet gevonden in {pad} - "
              "is het bestand gewijzigd/hernoemd?")
        return None
    paren = re.findall(r'"(\w+)"\s*:\s*"([\w.]+)"', match.group(1))
    return dict(paren)  # {addon_sleutel: scriptbestandsnaam}


def zoek_addon_in_bestand(bestandspad, addon_naam):
    """True als addon_naam ergens in het bestand voorkomt (case-
    insensitive substring - simpel maar effectief genoeg om een
    volledig gemiste rij op te sporen)."""
    if not os.path.exists(bestandspad):
        return None  # bestand zelf ontbreekt - apart gemeld
    with open(bestandspad, encoding="utf-8", errors="replace") as f:
        inhoud = f.read()
    return addon_naam.lower() in inhoud.lower()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None,
                         help="Pad naar de suite-hoofdmap (standaard: 1 map "
                              "boven waar dit script zelf staat, dus C:\\PiNAS "
                              "als dit script in Gedeeld\\ staat)")
    args = parser.parse_args()

    if args.root:
        root = args.root
    else:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    addons_pad = os.path.join(root, ADDONS_BEHEER_PAD)
    addon_lijst = laad_addon_lijst(addons_pad)
    if addon_lijst is None:
        sys.exit(1)

    print("=" * 70)
    print(f"  Consistentiecontrole documentatie - {len(addon_lijst)} addons gevonden")
    print(f"  Suite-hoofdmap: {root}")
    print("=" * 70)
    print()

    totaal_gaten = 0
    for sleutel in addon_lijst:
        naam = NAAM_MAP.get(sleutel, sleutel)
        regels = []
        for relatief_pad, mensleesbaar in TE_CONTROLEREN_BESTANDEN:
            volledig_pad = os.path.join(root, relatief_pad.replace("/", os.sep))
            gevonden = zoek_addon_in_bestand(volledig_pad, naam)
            if gevonden is None:
                regels.append(f"    ?  {mensleesbaar}: bestand zelf niet gevonden "
                               f"({volledig_pad})")
            elif not gevonden:
                regels.append(f"    X  ONTBREEKT in {mensleesbaar}")
                totaal_gaten += 1
        if regels:
            print(f"[{naam}] - {len(regels)} punt(en):")
            for r in regels:
                print(r)
            print()
        else:
            print(f"[{naam}] - OK, komt overal voor")

    print()
    print("=" * 70)
    if totaal_gaten == 0:
        print("  Alles consistent - geen gaten gevonden.")
    else:
        print(f"  {totaal_gaten} gat(en) gevonden - zie hierboven.")
    print("=" * 70)
    sys.exit(1 if totaal_gaten else 0)


if __name__ == "__main__":
    main()
