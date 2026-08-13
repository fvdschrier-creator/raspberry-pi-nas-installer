#!/usr/bin/env python3
"""
Gedeeld/bijwerk_pinas_versies.py

Werkt Gedeeld/pinas_versies.json automatisch bij: voor elk bestand dat al
een entry heeft, wordt de huidige SHA256-inhoud vergeleken met de hash van
de vorige keer dat dit script draaide. Is de inhoud gewijzigd, dan wordt
de datum voor dat bestand naar VANDAAG 00:01 gezet - precies de regel die
tot nu toe elke sessie met de hand moest gebeuren (verbeterpunt #3, 13
augustus 2026: "deze sessie moesten tijdstempels van gewijzigde bestanden
er zeker 15x met de hand in bijgewerkt worden - foutgevoelig, schaalt
niet").

Waarom contenthash i.p.v. bestandstijd (mtime)? C:\\PiNAS zelf is GEEN
git-repository (dat is alleen de /tmp-kloon tijdens een push) - er is dus
geen "git diff sinds laatste commit" beschikbaar als signaal. mtime alleen
is onbetrouwbaar zodra bestanden gekopieerd/gesynchroniseerd worden (bijv.
rsync met -t behoudt mtime, maar een handmatige kopieerslag in Verkenner
niet altijd) - een eigen hash-cache (Gedeeld/pinas_versies_hashes.json)
is de robuustere bron van waarheid en werkt ongeacht hoe een bestand hier
terecht is gekomen.

Eerste keer draaien (geen cache aanwezig): legt alleen de baseline vast
(hash van elk bestand dat nu in pinas_versies.json staat) en verandert
GEEN datums - er is dan nog niets om "gewijzigd sinds" mee te vergelijken.

Nieuwe bestanden die nog GEEN entry in pinas_versies.json hebben, worden
BEWUST niet automatisch toegevoegd (dat blijft een bewuste, kleine
mensenkeuze - welke naam/mensleesbare rij hoort erbij). NAS_Map_Beheer.pyw
Structuurcheck meldt zulke ontbrekende entries al apart ("bekend bestand,
maar GEEN entry in pinas_versies.json").

Gebruik:
    python3 bijwerk_pinas_versies.py [--root PAD] [--stil]
Wordt ook automatisch aangeroepen door maak_publieke_versie.py, vlak voor
elke publieke build/push - zie daar.
"""
import argparse
import datetime
import hashlib
import json
import os
import sys

VERSIES_BESTAND = "pinas_versies.json"
HASHES_BESTAND = "pinas_versies_hashes.json"


def _script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _volledig_pad(root, relpad):
    """pinas_versies.json gebruikt altijd backslash als scheidingsteken
    (Windows-conventie, ongeacht het platform waar dit script draait) -
    expliciet splitsen i.p.v. os.path.join(root, relpad) direct, want die
    laatste behandelt een backslash op Linux als een gewoon teken in de
    bestandsnaam i.p.v. als padscheiding."""
    return os.path.join(root, *relpad.split("\\"))


def _sha256(pad):
    try:
        with open(pad, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return None


def _laad_json(pad):
    if not os.path.exists(pad):
        return {}
    try:
        with open(pad, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _schrijf_json(pad, data):
    with open(pad, "w", encoding="utf-8", newline="") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")


def bijwerken(root, stil=False):
    """Voert de hash-vergelijking + eventuele datum-bijwerking uit. Geeft
    (bijgewerkte_paden, is_eerste_keer) terug."""
    gedeeld = os.path.join(root, "Gedeeld")
    versies_pad = os.path.join(gedeeld, VERSIES_BESTAND)
    hashes_pad = os.path.join(gedeeld, HASHES_BESTAND)

    versies = _laad_json(versies_pad)
    if not versies:
        if not stil:
            print(f"FOUT: kan {versies_pad} niet lezen of is leeg.")
        return [], False

    is_eerste_keer = not os.path.exists(hashes_pad)
    oude_hashes = _laad_json(hashes_pad)
    nieuwe_hashes = dict(oude_hashes)

    vandaag = datetime.date.today().strftime("%Y-%m-%d 00:01")
    bijgewerkt = []

    for relpad in versies:
        if relpad.startswith("_"):
            continue  # "_uitleg"-veld
        volledig_pad = _volledig_pad(root, relpad)
        if not os.path.exists(volledig_pad):
            continue  # ontbrekend bestand - Structuurcheck meldt dit al apart
        huidige_hash = _sha256(volledig_pad)
        if huidige_hash is None:
            continue
        nieuwe_hashes[relpad] = huidige_hash
        if is_eerste_keer:
            continue  # baseline vastleggen, nog niets te vergelijken
        vorige_hash = oude_hashes.get(relpad)
        if vorige_hash is not None and vorige_hash != huidige_hash:
            versies[relpad] = vandaag
            bijgewerkt.append(relpad)

    if bijgewerkt:
        _schrijf_json(versies_pad, versies)
        # pinas_versies.json staat zelf ook als entry in pinas_versies.json
        # (het bevat zijn eigen laatst-geleverde-datum) - de hash die
        # hierboven is vastgelegd, is van VOOR deze schrijfactie, dus
        # meteen weer verouderd. Zonder deze correctie zou de VOLGENDE run
        # dit bestand elke keer opnieuw als "gewijzigd" zien (oneindige
        # lus van steeds zichzelf bijwerken).
        for relpad in nieuwe_hashes:
            if os.path.abspath(_volledig_pad(root, relpad)) == os.path.abspath(versies_pad):
                nieuwe_hashes[relpad] = _sha256(versies_pad)

    _schrijf_json(hashes_pad, nieuwe_hashes)

    if not stil:
        if is_eerste_keer:
            print(f"  Eerste keer: baseline vastgelegd voor {len(nieuwe_hashes)} bestanden "
                  f"in {HASHES_BESTAND} - geen datums aangepast.")
        elif bijgewerkt:
            print(f"  {len(bijgewerkt)} bestand(en) gewijzigd sinds vorige keer - "
                  f"datum bijgewerkt naar {vandaag.split()[0]}:")
            for p in bijgewerkt:
                print(f"    - {p}")
        else:
            print("  Geen wijzigingen t.o.v. de vorige keer - pinas_versies.json ongewijzigd.")

    return bijgewerkt, is_eerste_keer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None,
                         help="Pad naar de suite-hoofdmap (standaard: 1 map "
                              "boven waar dit script zelf staat)")
    parser.add_argument("--stil", action="store_true",
                         help="Geen uitvoer, alleen de exitcode/return telt")
    args = parser.parse_args()

    root = args.root or os.path.dirname(_script_dir())
    if not args.stil:
        print("=" * 70)
        print("  pinas_versies.json automatisch bijwerken (contenthash-vergelijking)")
        print(f"  Suite-hoofdmap: {root}")
        print("=" * 70)
    bijwerken(root, stil=args.stil)
    if not args.stil:
        print("=" * 70)


if __name__ == "__main__":
    sys.exit(main())
