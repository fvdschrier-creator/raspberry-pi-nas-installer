#!/usr/bin/env python3
"""
Gedeeld/controleer_documentatie_consistentie.py

Checkt of elke add-on die in Gedeeld/pinas_addon_scripts.py's ADDON_SCRIPT
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

Gedeeld/pinas_addon_scripts.py blijft de ENE bron van waarheid voor
"welke addons bestaan er" - dit script importeert die lijst rechtstreeks
(sinds 13 augustus 2026, verbeterpunt #1 - daarvoor werd _ADDON_SCRIPT met
een regex uit pinas_addons_beheer.pyw's brontekst gelezen, wat al net zo'n
losse-kopie-risico was als het probleem dat dit hele controlescript
probeert te voorkomen).

14 augustus 2026 (Frans' verbeterpunt #3 uit de "wat kan beter"-ronde):
2e, andersoortige check toegevoegd - "geregistreerde knop is ook echt
gebouwd". Aanleiding: de "Pi opruimen"-knop stond al in HELP_HOOFDSTUKKEN
(helptekst) en had een werkende `_open_pi_opruimen()`-functie, maar de
knop zelf was nooit aan het scherm toegevoegd (commit `7e2ccdd`) - Frans
zag het pas toen hij het scherm met eigen ogen bekeek. De vaste conventie
in de hele suite is dat een klik-handler `_open_xxx()` of `_start_xxx()`
heet (16 van dit soort functies, verspreid over 6 .pyw-bestanden) en
ergens als `command=`/argument aan een knop wordt doorgegeven. Een
handler die WEL gedefinieerd is maar NERGENS anders in hetzelfde bestand
voorkomt, is bijna zeker "vergeten aan een knop te hangen" - precies het
type fout van die avond. Zie `controleer_ongekoppelde_handlers()`
hieronder.

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

# Gedeeld staat er zelf al in (dit script draait normaliter vanuit die map),
# maar --root kan een andere suite-hoofdmap opgeven - zorg dat de import
# altijd de Gedeeld-map bij DIT script vindt, ongeacht cwd of --root.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pinas_addon_scripts import ADDON_SCRIPT

# Voor elke addon-sleutel (zoals in ADDON_SCRIPT) de mensleesbare naam
# zoals die in de documentatie wordt gebruikt. Dit koppelbestandje is
# bewust klein en verandert zelden (een addon-naam wijzigt niet vaak) -
# de addon-LIJST zelf komt uit pinas_addon_scripts.py, niet hiervandaan.
NAAM_MAP = {
    "nextcloud": "Nextcloud",
    "pihole": "Pi-hole",
    "zerotier": "ZeroTier",
    "vaultwarden": "Vaultwarden",
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

def laad_addon_lijst():
    """Geeft ADDON_SCRIPT terug uit Gedeeld/pinas_addon_scripts.py -
    dat blijft de ENE bron van waarheid voor welke addons bestaan."""
    if not ADDON_SCRIPT:
        print("FOUT: ADDON_SCRIPT uit pinas_addon_scripts.py is leeg.")
        return None
    return dict(ADDON_SCRIPT)  # {addon_sleutel: scriptbestandsnaam}


def zoek_addon_in_bestand(bestandspad, addon_naam):
    """True als addon_naam ergens in het bestand voorkomt (case-
    insensitive substring - simpel maar effectief genoeg om een
    volledig gemiste rij op te sporen)."""
    if not os.path.exists(bestandspad):
        return None  # bestand zelf ontbreekt - apart gemeld
    with open(bestandspad, encoding="utf-8", errors="replace") as f:
        inhoud = f.read()
    return addon_naam.lower() in inhoud.lower()


# Mappen die we NOOIT scannen voor knop-handlers: gegenereerde kopieen
# (elk .pyw-bestand daarin is een 1-op-1 kopie van het origineel elders in
# de boom en zou dus alles dubbel melden) en bytecode-cache.
_OVERSLAAN_MAPPEN = {"NAS_Public", "StarterKit", "__pycache__", ".git"}

# Vaste naamconventie in de hele suite voor een knop-klik-handler (zie de
# 14-augustus-aantekening hierboven). Bewust ALLEEN deze 2 voorvoegsels -
# functies met een andere naam zijn vaak geen knop-handler (bijv. interne
# helpers) en zouden dan valse meldingen geven.
_HANDLER_PATROON = re.compile(r"^def (_(?:open|start)_[a-z_0-9]+)\(", re.MULTILINE)


def _vind_pyw_bestanden(root):
    """Alle .pyw-bestanden onder root, met _OVERSLAAN_MAPPEN overgeslagen."""
    gevonden = []
    for dirpad, dirs, bestanden in os.walk(root):
        dirs[:] = [d for d in dirs if d not in _OVERSLAAN_MAPPEN]
        for naam in bestanden:
            if naam.lower().endswith(".pyw"):
                gevonden.append(os.path.join(dirpad, naam))
    return gevonden


def controleer_ongekoppelde_handlers(root):
    """Zoekt per .pyw-bestand naar `_open_xxx()`/`_start_xxx()`-functies
    (de vaste knop-handler-conventie in deze suite) die WEL gedefinieerd
    zijn maar verder NERGENS in datzelfde bestand voorkomen - dus
    vermoedelijk nooit aan een knop gekoppeld zijn. Simpele
    woordtelling (zelfde 'simpel maar effectief'-aanpak als de addon-
    check hierboven): de `def`-regel telt als 1 voorkomen, dus alles
    <= 1 is verdacht.

    Geeft een lijst (bestandspad, [handlernamen]) terug voor elk bestand
    met minstens 1 verdachte handler."""
    gaten = []
    for pad in sorted(_vind_pyw_bestanden(root)):
        try:
            with open(pad, encoding="utf-8", errors="replace") as f:
                inhoud = f.read()
        except OSError:
            continue
        handlers = _HANDLER_PATROON.findall(inhoud)
        if not handlers:
            continue
        verdacht = []
        for naam in handlers:
            aantal = len(re.findall(r"\b" + re.escape(naam) + r"\b", inhoud))
            if aantal <= 1:
                verdacht.append(naam)
        if verdacht:
            gaten.append((pad, verdacht))
    return gaten


def voer_controle_uit(root):
    """Voert de volledige controle uit en print het rapport. Geeft het
    aantal gevonden gaten terug (0 = alles consistent), of None als de
    addon-lijst zelf niet geladen kon worden.

    13 augustus 2026 (verbeterpunt #2): losgetrokken van main() zodat
    andere scripts (zoals maak_publieke_versie.py, vlak voor een
    GitHub-push) deze check ook rechtstreeks kunnen aanroepen en op het
    resultaat kunnen reageren, i.p.v. dat iemand moet ONTHOUDEN dit los
    te draaien."""
    addon_lijst = laad_addon_lijst()
    if addon_lijst is None:
        return None

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
    print("-" * 70)
    print("  Ongekoppelde knop-handlers (_open_xxx/_start_xxx zonder knop)")
    print("-" * 70)
    handler_gaten = controleer_ongekoppelde_handlers(root)
    if handler_gaten:
        for pad, namen in handler_gaten:
            relatief = os.path.relpath(pad, root)
            for naam in namen:
                print(f"    X  {relatief}: {naam}() gedefinieerd maar nergens "
                      f"anders in dit bestand aangeroepen (vermoedelijk geen "
                      f"knop gebouwd)")
                totaal_gaten += 1
    else:
        print("  OK, elke _open_xxx/_start_xxx-handler wordt ergens aangeroepen.")

    print()
    print("=" * 70)
    if totaal_gaten == 0:
        print("  Alles consistent - geen gaten gevonden.")
    else:
        print(f"  {totaal_gaten} gat(en) gevonden - zie hierboven.")
    print("=" * 70)
    return totaal_gaten


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

    totaal_gaten = voer_controle_uit(root)
    if totaal_gaten is None:
        sys.exit(1)
    sys.exit(1 if totaal_gaten else 0)


if __name__ == "__main__":
    main()
