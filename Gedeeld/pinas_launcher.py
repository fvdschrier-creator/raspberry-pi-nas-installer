"""
Gedeeld/pinas_launcher.py
Centrale hulp om een suite-programma te openen zonder dat er per ongeluk
een tweede exemplaar naast een al openstaand venster verschijnt. Elk
programma had voorheen zijn eigen kopie van deze "draait het al?"-logica
(of, zoals bij Backup Beheer's Terug-knop, helemaal geen check) - dat was
precies de bron van de dubbele-hoofdmenu-bug. Nu op een plek.

Gebruik (per aanroepend bestand):
    from pinas_launcher import open_programma

    ok, fout = open_programma(
        "Pi_NAS_Menu.pyw",
        roots=[_nas_root(), _c_pinas()],
        submappen=["Beheer"],
    )
    if not ok:
        messagebox.showerror("Niet gevonden", fout)
"""

import os
import subprocess


def draait_al(bestandsnaam):
    """Kijkt via de Windows-procesli jst of bestandsnaam al voorkomt in de
    command line van een lopend pythonw/python-proces. Bij twijfel (de
    check zelf faalt) wordt False aangenomen - liever een overbodig
    tweede venster dan straks nergens meer bij kunnen."""
    try:
        uitvoer = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Process -Filter "
             "\"Name='pythonw.exe' or Name='python.exe'\").CommandLine"],
            text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW)
        return bestandsnaam in uitvoer
    except Exception:
        return False


def vind_bestand(bestandsnaam, roots, submappen):
    """Zoekt bestandsnaam in elke combinatie van roots x submappen, en
    geeft het eerste gevonden volledige pad terug (of None)."""
    for root in roots:
        if not root:
            continue
        for sub in submappen:
            pad = os.path.join(root, sub, bestandsnaam)
            if os.path.exists(pad):
                return pad
    return None


def open_programma(bestandsnaam, roots, submappen, forceer_nieuw=False):
    """
    Opent bestandsnaam via de Windows-bestandskoppeling, tenzij het al draait.

    roots: lijst van kandidaat-NAS-roots, bijv. [_nas_root(), _c_pinas()]
    submappen: lijst van mapnamen om in te zoeken, bijv. ["Beheer"]
    forceer_nieuw: negeert de "draait al"-check - voor programma's die
        bewust meerdere keren open mogen staan (bijv. NAS Map Beheer,
        waar niets op tegen is als je 'm twee keer open hebt staan).

    Retourneert (True, None) bij succes of als het al draaide,
    (False, foutmelding) als het bestand nergens gevonden kon worden.
    """
    if not forceer_nieuw and draait_al(bestandsnaam):
        return True, None

    pad = vind_bestand(bestandsnaam, roots, submappen)
    if not pad:
        return False, (f"{bestandsnaam} niet gevonden in: "
                        f"{', '.join(submappen)}")
    try:
        # 4 augustus 2026 (Frans, na herhaalde PATH-ellende): geen enkel
        # geraden Python-pad meer proberen (niet "pythonw" via PATH, niet
        # sys.executable) - os.startfile() gebruikt gewoon de Windows-
        # bestandskoppeling, exact hetzelfde mechanisme als handmatig
        # dubbelklikken op het bestand. Werkt dubbelklikken, dan werkt dit.
        os.startfile(pad)
        return True, None
    except Exception as e:
        return False, str(e)
