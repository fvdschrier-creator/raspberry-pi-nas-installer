#!/usr/bin/env python3
"""
Gedeeld/controleer_syntax.py

Controleert de syntax van ELK Python- (.py/.pyw) en bash-bestand (.sh) in
de suite-boom: `py_compile` voor Python, `bash -n` voor bash. Meldt per
kapot bestand de foutmelding.

13 augustus 2026 (verbeterpunt #4, Frans): "elke keer dat ik py_compile/
bash -n draaide, deed ik dat handmatig, per bestand, op eigen initiatief -
een simpel controlescript dat dit afdwingt zou voorkomen dat een kapot
bestand ooit gepusht wordt zonder dat iemand het toevallig test." Dit
script is dat controlescript, en draait verplicht mee in
maak_publieke_versie.py (vlak voor elke publieke build/push).

`bash -n` wordt overgeslagen (met een duidelijke melding, geen harde fout)
als er geen `bash` op het systeem staat - dit script draait in de praktijk
altijd in de Linux-sandbox (waar bash gewoon aanwezig is), maar Frans'
eigen Windows-pc heeft bewust geen bash/WSL meer (zie de Docker/WSL-
verwijdering van 12 augustus 2026) - dit script moet daar niet om
crashen als het ooit lokaal gedraaid wordt.

Gebruik:
    python3 controleer_syntax.py [--root PAD]
"""
import argparse
import os
import py_compile
import shutil
import subprocess
import sys

# Nooit meescannen: gegenereerde/gekopieerde kopie (zelfde bestanden
# worden al gecontroleerd op hun ECHTE plek), en Python's eigen cache.
OVERSLAAN_MAPNAMEN = {"NAS_Public", "__pycache__", ".git"}

PY_EXTENSIES = (".py", ".pyw")
SH_EXTENSIES = (".sh",)


def _bash_werkt_echt():
    """13 augustus 2026 (bugfix, Frans meldde dit via een screenshot van
    zijn eigen pc): shutil.which('bash') alleen is niet genoeg. Op Windows
    staat vaak nog C:\\Windows\\System32\\bash.exe op het PATH - een oude
    WSL-launcher-stub die WEL bestaat, maar bij elke aanroep meteen faalt
    ("execvpe(/bin/bash) failed: No such file or directory") zodra er geen
    WSL-distro (meer) geinstalleerd is. Frans verwijderde WSL bewust op 12
    augustus 2026, maar die stub blijft gewoon op het PATH staan. Zonder
    deze functionele test werd elk .sh-bestand als 'kapot' gemeld (20
    valse syntaxfouten) en blokkeerde dat de hele publieke build - terwijl
    de bedoeling was dat bash-controle hier gewoon stil wordt overgeslagen."""
    pad = shutil.which("bash")
    if pad is None:
        return False
    try:
        r = subprocess.run([pad, "-c", "exit 0"], capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def _vind_bestanden(root):
    for dirpad, submappen, bestanden in os.walk(root):
        submappen[:] = [d for d in submappen if d not in OVERSLAAN_MAPNAMEN]
        for naam in bestanden:
            volledig_pad = os.path.join(dirpad, naam)
            if naam.endswith(PY_EXTENSIES):
                yield "python", volledig_pad
            elif naam.endswith(SH_EXTENSIES):
                yield "bash", volledig_pad


def controleer(root):
    """Voert de controle uit en print het rapport. Geeft het aantal
    kapotte bestanden terug (0 = alles schoon)."""
    sys.dont_write_bytecode = True  # geen __pycache__-rommel in de suite-boom

    bash_beschikbaar = _bash_werkt_echt()
    python_bestanden = []
    bash_bestanden = []
    for soort, pad in _vind_bestanden(root):
        (python_bestanden if soort == "python" else bash_bestanden).append(pad)

    print("=" * 70)
    print(f"  Syntaxcontrole - {len(python_bestanden)} Python-bestand(en), "
          f"{len(bash_bestanden)} bash-bestand(en)")
    print(f"  Suite-hoofdmap: {root}")
    print("=" * 70)
    print()

    fouten = []

    for pad in sorted(python_bestanden):
        relpad = os.path.relpath(pad, root)
        try:
            py_compile.compile(pad, doraise=True)
        except py_compile.PyCompileError as e:
            fouten.append((relpad, str(e.msg).strip()))
        except (SyntaxError, ValueError) as e:
            fouten.append((relpad, str(e)))

    if bash_beschikbaar:
        for pad in sorted(bash_bestanden):
            relpad = os.path.relpath(pad, root)
            r = subprocess.run(["bash", "-n", pad], capture_output=True, text=True)
            if r.returncode != 0:
                fouten.append((relpad, r.stderr.strip()))
    else:
        print("  ?  bash niet gevonden op dit systeem - bash-syntaxcontrole overgeslagen "
              f"({len(bash_bestanden)} bestand(en) niet gecontroleerd).")
        print()

    if fouten:
        for relpad, melding in fouten:
            print(f"  X  {relpad}")
            for regel in melding.splitlines():
                print(f"       {regel}")
        print()
        print("=" * 70)
        print(f"  {len(fouten)} bestand(en) met een syntaxfout - zie hierboven.")
    else:
        print("  Alle gecontroleerde bestanden zijn syntactisch geldig.")
        print("=" * 70)

    return len(fouten)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None,
                         help="Pad naar de suite-hoofdmap (standaard: 1 map "
                              "boven waar dit script zelf staat)")
    args = parser.parse_args()
    root = args.root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fouten = controleer(root)
    sys.exit(1 if fouten else 0)


if __name__ == "__main__":
    main()
