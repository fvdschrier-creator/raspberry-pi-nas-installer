#!/usr/bin/env python3
"""
Pi NAS Suite - Pi opruimen
Dubbelklik om te starten, of via Pi NAS Menu -> Beheer -> Controles ->
"Pi opruimen".

13 augustus 2026 (Frans, na het SD-kaart-onderzoek via WinSCP): een oude,
afgebroken Systeem-image (7+ GB) bleek per ongeluk in /home/pi/Images/ te
staan i.p.v. op de backup-HDD waar hij hoort - restant van een quote-bug
die dezelfde dag (17 juli 2026) al gefixt was. Frans' vervolgvraag: "weten
we wat er wel moet staan op de SD-kaart en wat niet, en kunnen we dat
controleren en schoonmaken?"

Vergelijkt /home/pi/ op de Pi (via SSH, dezelfde sleutel als PuTTY/WinSCP -
geen wachtwoord nodig) met PI_BESTANDEN uit nas_upload.py - dat blijft de
ENE bron van waarheid voor "welke bestanden hoort de suite daar te
zetten", niet hier dupliceren. Standaard Linux/desktop-mappen en dotfiles
(Desktop, Documents, .bashrc, .ssh, enzovoort) worden genegeerd - alleen
echt onverklaarde bestanden/mappen worden als opruim-kandidaat getoond,
met hun grootte, zodat je zelf kunt inschatten of het de moeite waard is.
"""
import configparser
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox


def _script_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return os.path.dirname(os.path.abspath(sys.argv[0]))


def _nas_root():
    d = _script_dir()
    for sub in ["Beheer", "PiServer", "Sync", "Gedeeld"]:
        if os.path.basename(d) == sub:
            return os.path.dirname(d)
    return d


NAS_ROOT = _nas_root()
_gedeeld = os.path.join(NAS_ROOT, "Gedeeld")
if os.path.isdir(_gedeeld) and _gedeeld not in sys.path:
    sys.path.insert(0, _gedeeld)

try:
    from pinas_theme import BG, PANEL, PANEL2, FG, DIM, OK_C, ERR_C, WARN, ACCENT_PIBEHEER_2
    from pinas_ui import maak_header, maak_sectie, maak_knop
except ImportError:
    BG = "#232a33"; PANEL = "#2b333d"; PANEL2 = "#33404c"
    FG = "#eef2f6"; DIM = "#9aa8b5"
    OK_C = "#22c55e"; ERR_C = "#ef4444"; WARN = "#f59e0b"; ACCENT_PIBEHEER_2 = "#e47bba"
    maak_header = maak_sectie = maak_knop = None

try:
    from nas_upload import PI_BESTANDEN
except ImportError:
    PI_BESTANDEN = frozenset()

_cfg = configparser.ConfigParser()
_cfg_pad = os.path.join(NAS_ROOT, "Beheer", "picontrol.cfg")
if os.path.exists(_cfg_pad):
    _cfg.read(_cfg_pad, encoding="utf-8")
PI_IP = _cfg.get("pi", "ip", fallback="UW_PI_IP_ADRES")
PI_USER = "pi"

# Standaard Raspberry Pi OS/desktopmap-namen - horen gewoon bij een
# normale Linux-thuismap, nooit als "onbekend" melden. Verborgen
# bestanden/mappen (beginnen met ".") worden apart al genegeerd (zie
# _controleer() - "du -a" laat ze wel zien, maar we filteren ze eruit).
GENEGEERD_NAMEN = {
    "Desktop", "Documents", "Downloads", "Music", "Pictures",
    "Public", "Templates", "Videos", "bin",
}

SSH_OPT = ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=8"]


def _ssh_run(cmd, timeout=25):
    return subprocess.run(
        ["ssh"] + SSH_OPT + [f"{PI_USER}@{PI_IP}", cmd],
        capture_output=True, text=True, timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW)


def _controleer():
    """Haalt op wat er nu in /home/pi staat (niet-verborgen items, met
    grootte) en vergelijkt met PI_BESTANDEN. Geeft (onbekend, ontbrekend)
    terug - allebei lijsten. Gooit een Exception als SSH niet lukt."""
    r = _ssh_run("du -sh /home/pi/* 2>/dev/null")
    if r.returncode != 0 and not r.stdout.strip():
        raise RuntimeError(r.stderr.strip() or "Geen verbinding met de Pi (SSH mislukt)")

    aanwezig = {}
    for regel in r.stdout.strip().splitlines():
        deel = regel.split("\t")
        if len(deel) < 2:
            continue
        grootte, pad = deel[0], deel[-1]
        naam = os.path.basename(pad.rstrip("/"))
        if naam:
            aanwezig[naam] = grootte

    onbekend = [(naam, grootte) for naam, grootte in aanwezig.items()
                if naam not in PI_BESTANDEN and naam not in GENEGEERD_NAMEN]
    ontbrekend = [naam for naam in sorted(PI_BESTANDEN, key=str.lower) if naam not in aanwezig]
    return onbekend, ontbrekend


PI_OPRUIMEN_HELP = [
    ("Pi opruimen", "Vergelijkt /home/pi/ op de Pi met de bestanden die de suite daar hoort "
     "te zetten (zie Onderhoud -> Geavanceerd -> Scripts uploaden). Standaard Linux-mappen "
     "(Desktop, Documents, enzovoort) en verborgen bestanden worden genegeerd - alles wat "
     "overblijft is onverklaard, vaak resten van een oude, afgebroken actie."),
    ("Verwijderen", "Verwijdert de getoonde onbekende bestanden/mappen definitief van de Pi "
     "via SSH (rm -rf) - vraagt eerst 1x bevestiging met de volledige lijst zichtbaar. Dit "
     "kan niet ongedaan worden gemaakt."),
]


def main():
    win = tk.Tk()
    win.title("Pi opruimen — Pi NAS Suite")
    win.configure(bg=BG)
    win.geometry("640x540")
    win.minsize(520, 420)

    if maak_header:
        maak_header(win, "Pi opruimen", subtekst=f"Pi: {PI_USER}@{PI_IP}",
                    help_hoofdstukken=PI_OPRUIMEN_HELP, kleur=ACCENT_PIBEHEER_2)
    else:
        tk.Label(win, text="Pi opruimen", font=("Segoe UI", 14, "bold"),
                 bg=BG, fg=ACCENT_PIBEHEER_2).pack(anchor="w", padx=16, pady=(14, 4))

    status_label = tk.Label(win, text="Nog niet gecontroleerd.", font=("Segoe UI", 10),
                             bg=BG, fg=DIM, anchor="w")
    status_label.pack(fill="x", padx=16, pady=(4, 2))

    lijst_frame = tk.Frame(win, bg=PANEL2)
    lijst_frame.pack(fill="both", expand=True, padx=16, pady=8)
    scrollbar = tk.Scrollbar(lijst_frame)
    scrollbar.pack(side="right", fill="y")
    tekstvak = tk.Text(lijst_frame, font=("Consolas", 9), bg=PANEL2, fg=FG,
                        relief="flat", wrap="word", yscrollcommand=scrollbar.set)
    tekstvak.pack(fill="both", expand=True)
    scrollbar.config(command=tekstvak.yview)
    tekstvak.tag_configure("warn", foreground=WARN)
    tekstvak.tag_configure("ok", foreground=OK_C)
    tekstvak.tag_configure("dim", foreground=DIM)
    tekstvak.config(state="disabled")

    knoppen = tk.Frame(win, bg=BG)
    knoppen.pack(fill="x", padx=16, pady=12)

    _staat = {"onbekend": [], "bezig": False}

    def _toon(regels):
        tekstvak.config(state="normal")
        tekstvak.delete("1.0", "end")
        for tekst, tag in regels:
            tekstvak.insert("end", tekst, tag)
        tekstvak.config(state="disabled")

    def _controleren_klik():
        if _staat["bezig"]:
            return
        _staat["bezig"] = True
        status_label.config(text="Bezig met controleren via SSH...", fg=DIM)
        verwijder_knop.config(state="disabled")
        controleer_knop.config(state="disabled")
        _toon([("Even geduld...\n", "dim")])

        def _werk():
            try:
                onbekend, ontbrekend = _controleer()

                def _klaar():
                    _staat["onbekend"] = onbekend
                    _staat["bezig"] = False
                    controleer_knop.config(state="normal")
                    regels = []
                    if onbekend:
                        regels.append((f"ONBEKEND ({len(onbekend)}) - kandidaat om op te ruimen:\n", "warn"))
                        for naam, grootte in sorted(onbekend, key=lambda x: x[0].lower()):
                            regels.append((f"  {grootte:>7}  {naam}\n", None))
                        regels.append(("\n", None))
                    else:
                        regels.append(("Geen onbekende bestanden/mappen gevonden.\n\n", "ok"))
                    if ontbrekend:
                        regels.append((f"ONTBREEKT ({len(ontbrekend)}) - hoort er wel te staan:\n", "warn"))
                        for naam in ontbrekend:
                            regels.append((f"  {naam}\n", None))
                        regels.append(("\n  Tip: Onderhoud -> Geavanceerd -> Scripts uploaden naar Pi.\n", "dim"))
                    _toon(regels)
                    if onbekend:
                        status_label.config(text=f"{len(onbekend)} onbekend item(s) gevonden.", fg=WARN)
                        verwijder_knop.config(state="normal")
                    else:
                        status_label.config(text="Alles in orde.", fg=OK_C)
                        verwijder_knop.config(state="disabled")
                win.after(0, _klaar)
            except Exception as e:
                def _mislukt():
                    _staat["bezig"] = False
                    controleer_knop.config(state="normal")
                    status_label.config(text=f"Controle mislukt: {e}", fg=ERR_C)
                    _toon([(f"Kon niet verbinden met de Pi:\n\n{e}", "warn")])
                win.after(0, _mislukt)

        threading.Thread(target=_werk, daemon=True).start()

    def _verwijderen_klik():
        onbekend = _staat["onbekend"]
        if not onbekend:
            return
        namen = "\n".join(f"  - {n} ({g})" for n, g in onbekend)
        if not messagebox.askyesno(
                "Verwijderen bevestigen",
                f"{len(onbekend)} item(s) definitief verwijderen van de Pi?\n\n{namen}\n\n"
                "Dit kan niet ongedaan worden gemaakt."):
            return
        paden = " ".join(f"'/home/pi/{n}'" for n, _g in onbekend)
        # 13 augustus 2026 (bugfix, Frans meldde dit via een screenshot):
        # zonder sudo faalde dit stil-gedeeltelijk op alles wat een
        # root-eigen achtergronddienst (bijv. de seagate-/smart_plug-
        # logging) in een map had achtergelaten - "rm: cannot remove
        # ...: Permission denied" per bestand DIEP in zo'n map, terwijl
        # alleen de map zelf (bijv. "logs") in het kandidatenlijstje
        # stond. pi heeft nergens leesrechten-probleem (du -sh werkte
        # allang), maar wel schrijfrechten-probleem om root-eigen
        # bestanden te verwijderen. sudo hier is consistent met de rest
        # van de suite (nas_upload.py doet hetzelfde via SSH zonder tty).
        try:
            r = _ssh_run(f"sudo rm -rf {paden} && echo OK")
        except Exception as e:
            messagebox.showerror("Opruimen mislukt", str(e))
            return
        if r.returncode == 0 and "OK" in r.stdout:
            messagebox.showinfo("Opruimen - klaar", f"{len(onbekend)} item(s) verwijderd.")
            _controleren_klik()
        else:
            messagebox.showerror("Opruimen mislukt", r.stderr.strip() or "Onbekende fout")

    if maak_knop:
        controleer_knop = maak_knop(knoppen, "Controleren", _controleren_klik,
                                     stijl="primair", kleur=ACCENT_PIBEHEER_2)
        controleer_knop.pack(side="left", padx=(0, 8))
        verwijder_knop = maak_knop(knoppen, "Onbekende items verwijderen",
                                    _verwijderen_klik, stijl="destructief")
        verwijder_knop.pack(side="left")
    else:
        controleer_knop = tk.Button(knoppen, text="Controleren", command=_controleren_klik)
        controleer_knop.pack(side="left", padx=(0, 8))
        verwijder_knop = tk.Button(knoppen, text="Onbekende items verwijderen", command=_verwijderen_klik)
        verwijder_knop.pack(side="left")
    verwijder_knop.config(state="disabled")

    win.after(200, _controleren_klik)
    win.mainloop()


if __name__ == "__main__":
    main()
