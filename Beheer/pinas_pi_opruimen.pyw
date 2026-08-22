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

22 augustus 2026 (Frans, na een screenshot met 9 "onbekende" items waarvan
hij bij een aantal niet zeker was of ze wel weg mochten - "het mag niets
weggooien wat niet weg mag"): "Onbekende items verwijderen" verwijderde tot
nu toe altijd ALLES uit de lijst in 1x, geen individuele keuze - bij twijfel
over ook maar 1 item kon de knop dus niet veilig gebruikt worden voor de
rest. Elk item heeft nu een eigen vinkje (zelfde patroon als Structuurcheck/
Opruimen in NAS_Map_Beheer.pyw), STANDAARD UIT - bewust anders dan daar,
want die lijst is een curated, vooraf bekende set (ONNODIGE_BESTANDEN),
terwijl deze lijst per definitie "alles wat de suite niet herkent" is en dus
ook iets kan bevatten dat wél nodig is. Alleen aangevinkte items worden
verwijderd, zowel in de bevestiging als in het daadwerkelijke rm-commando.
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

# 16 augustus 2026 (bugfix, Frans meldde dit via een screenshot - "Pi
# opruimen" gaf 18 "onbekende" items, waarvan er 7 gewoon actief in
# gebruik zijnde addon-scripts bleken: pinas_dashboard.sh,
# pinas_nextcloud.sh, pinas_pihole.sh, pinas_printer.sh,
# pinas_vaultwarden.sh, pinas_vaultwarden_verwijderen.sh,
# pinas_zerotier.sh). Oorzaak: PI_BESTANDEN (uit nas_upload.py) is de
# lijst van bestanden die "Scripts uploaden naar Pi" wegzet, maar addon-
# scripts worden apart, per addon, vanuit Addons\ geupload door
# Addons Beheer (zie _draai_script_op_pi() in pinas_addons_beheer.pyw,
# dat elk .sh-bestand uit Addons\ 1-op-1 als /home/pi/<bestandsnaam>
# neerzet) - die route stond hier nergens geregistreerd. In plaats van
# zelf een tweede, losse kopie van "welke addon-scripts bestaan er" bij
# te houden (dezelfde valkuil als eerder bij ADDON_SCRIPT, zie
# pinas_addon_scripts.py) wordt hier gewoon elk .sh-bestand dat lokaal
# in Addons\ staat als "hoort er te mogen zijn" behandeld - blijft
# vanzelf kloppen als er een addon bijkomt.
try:
    ADDON_PI_BESTANDEN = frozenset(
        f for f in os.listdir(os.path.join(NAS_ROOT, "Addons")) if f.endswith(".sh"))
except OSError:
    ADDON_PI_BESTANDEN = frozenset()

# Overige bestanden/mappen die door iets anders dan de suite zelf op de
# Pi worden gezet, maar wel degelijk verwacht/in gebruik zijn:
# - filebrowser.db: database van FileBrowser, een los te installeren
#   dienst via de PiServer-installer (nas_installer.py), niet via
#   Addons Beheer - staat daarom niet in PI_BESTANDEN of Addons\.
# - pinas_manifest.txt: 22 augustus 2026, door nas_upload.py weggeschreven
#   (whitelist voor nas_installer.py/_cli.py's "Scripts bijwerken vanuit
#   SD-kaart" - zie de fix daar) - geen bestand dat de suite zelf ooit
#   naar hier upload, dus stond hier nog niet. Zonder deze regel zou
#   "Onbekende items verwijderen" het manifest zelf meepakken en
#   daarmee precies de fix van vandaag weer ongedaan maken.
PI_OVERIGE_BEKEND = {"filebrowser.db", "pinas_manifest.txt"}

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
# "logs": de eigen, zelf-opruimende maplog van pinas_logging.py (zie
# GEDEELD_BESTANDEN hierboven) - verwijdert zelf bestanden ouder dan 30
# dagen, hoort dus niet als opruim-kandidaat getoond te worden.
GENEGEERD_NAMEN = {
    "Desktop", "Documents", "Downloads", "Music", "Pictures",
    "Public", "Templates", "Videos", "bin", "logs",
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

    bekend = PI_BESTANDEN | ADDON_PI_BESTANDEN | PI_OVERIGE_BEKEND
    onbekend = [(naam, grootte) for naam, grootte in aanwezig.items()
                if naam not in bekend and naam not in GENEGEERD_NAMEN]
    ontbrekend = [naam for naam in sorted(PI_BESTANDEN, key=str.lower) if naam not in aanwezig]
    return onbekend, ontbrekend


PI_OPRUIMEN_HELP = [
    ("Pi opruimen", "Vergelijkt /home/pi/ op de Pi met de bestanden die de suite daar hoort "
     "te zetten: de vaste kernbestanden (Onderhoud -> Geavanceerd -> Scripts uploaden), elk "
     "addon-script uit Addons\\ (Nextcloud, Pi-hole, ZeroTier, Vaultwarden, Printserver, "
     "Dashboard, incl. hun 'verwijderen'/'wachtwoord resetten'-varianten) en een paar bekende "
     "bestanden van los geinstalleerde diensten (bijv. filebrowser.db). Standaard Linux-mappen "
     "(Desktop, Documents, enzovoort), de zelf-opruimende logmap en verborgen bestanden worden "
     "genegeerd - alles wat overblijft is onverklaard, vaak resten van een oude, afgebroken of "
     "inmiddels vervangen actie."),
    ("Verwijderen", "Elk onbekend item heeft een eigen vinkje, standaard UIT - vink aan wat "
     "je echt kwijt wilt. Verwijdert alleen de aangevinkte bestanden/mappen definitief van de "
     "Pi via SSH (rm -rf), na 1x bevestiging met alleen de aangevinkte items zichtbaar. Dit "
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
    cv = tk.Canvas(lijst_frame, bg=PANEL2, highlightthickness=0,
                    yscrollcommand=scrollbar.set)
    cv.pack(side="left", fill="both", expand=True)
    scrollbar.config(command=cv.yview)
    inner = tk.Frame(cv, bg=PANEL2)
    cv.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))

    knoppen = tk.Frame(win, bg=BG)
    knoppen.pack(fill="x", padx=16, pady=12)

    _staat = {"onbekend": [], "bezig": False}
    onbekend_vars = {}  # naam -> (BooleanVar, grootte)

    def _leeg(tekst, tag=None):
        for w in inner.winfo_children():
            w.destroy()
        kleur = {"warn": WARN, "ok": OK_C, "dim": DIM}.get(tag, FG)
        tk.Label(inner, text=tekst, font=("Segoe UI", 9), bg=PANEL2, fg=kleur,
                 anchor="w", justify="left").pack(anchor="w", padx=8, pady=8)

    # 22 augustus 2026: elk onbekend item krijgt een eigen vinkje (STANDAARD
    # UIT - zie de docstring bovenaan dit bestand voor waarom dat hier
    # bewust anders is dan bij Structuurcheck/Opruimen). Alleen aangevinkte
    # items komen in de bevestiging EN in het daadwerkelijke rm-commando
    # terecht - "het mag niets weggooien wat niet weg mag" (Frans).
    def _bouw_lijst(onbekend, ontbrekend):
        for w in inner.winfo_children():
            w.destroy()
        onbekend_vars.clear()

        if onbekend:
            tk.Label(inner, text=f"ONBEKEND ({len(onbekend)}) - vink aan wat je wilt "
                                  f"verwijderen (standaard niets aangevinkt):",
                      font=("Segoe UI", 9, "bold"), bg=PANEL2, fg=WARN,
                      anchor="w").pack(anchor="w", padx=8, pady=(8, 4))
            for naam, grootte in sorted(onbekend, key=lambda x: x[0].lower()):
                var = tk.BooleanVar(master=win, value=False)
                onbekend_vars[naam] = (var, grootte)
                rij = tk.Frame(inner, bg=PANEL2)
                rij.pack(fill="x", padx=8, pady=1)
                tk.Checkbutton(rij, text=naam, variable=var, font=("Segoe UI", 9),
                                bg=PANEL2, fg=FG, selectcolor=PANEL,
                                activebackground=PANEL2, anchor="w").pack(side="left")
                tk.Label(rij, text=grootte, font=("Segoe UI", 8), bg=PANEL2, fg=DIM,
                          width=8, anchor="e").pack(side="right")
        else:
            tk.Label(inner, text="Geen onbekende bestanden/mappen gevonden.",
                      font=("Segoe UI", 9), bg=PANEL2, fg=OK_C,
                      anchor="w").pack(anchor="w", padx=8, pady=8)

        if ontbrekend:
            tk.Frame(inner, bg=PANEL, height=1).pack(fill="x", padx=8, pady=(10, 4))
            tk.Label(inner, text=f"ONTBREEKT ({len(ontbrekend)}) - hoort er wel te staan:",
                      font=("Segoe UI", 9, "bold"), bg=PANEL2, fg=WARN,
                      anchor="w").pack(anchor="w", padx=8, pady=(4, 2))
            for naam in ontbrekend:
                tk.Label(inner, text=f"  {naam}", font=("Segoe UI", 9), bg=PANEL2, fg=FG,
                          anchor="w").pack(anchor="w", padx=8)
            tk.Label(inner, text="  Tip: Onderhoud -> Geavanceerd -> Scripts uploaden naar Pi.",
                      font=("Segoe UI", 8), bg=PANEL2, fg=DIM,
                      anchor="w").pack(anchor="w", padx=8, pady=(2, 8))

    def _controleren_klik():
        if _staat["bezig"]:
            return
        _staat["bezig"] = True
        status_label.config(text="Bezig met controleren via SSH...", fg=DIM)
        verwijder_knop.config(state="disabled")
        controleer_knop.config(state="disabled")
        _leeg("Even geduld...", "dim")

        def _werk():
            try:
                onbekend, ontbrekend = _controleer()

                def _klaar():
                    _staat["onbekend"] = onbekend
                    _staat["bezig"] = False
                    controleer_knop.config(state="normal")
                    _bouw_lijst(onbekend, ontbrekend)
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
                    _leeg(f"Kon niet verbinden met de Pi:\n\n{e}", "warn")
                win.after(0, _mislukt)

        threading.Thread(target=_werk, daemon=True).start()

    def _verwijderen_klik():
        geselecteerd = [(naam, grootte) for naam, (var, grootte) in onbekend_vars.items()
                         if var.get()]
        if not geselecteerd:
            messagebox.showinfo("Opruimen",
                f"Niets aangevinkt (van de {len(onbekend_vars)} onbekende item(s)).\n\n"
                "Zet eerst een vinkje bij wat je wilt verwijderen.")
            return
        namen = "\n".join(f"  - {n} ({g})" for n, g in geselecteerd)
        if not messagebox.askyesno(
                "Verwijderen bevestigen",
                f"{len(geselecteerd)} van de {len(onbekend_vars)} onbekende item(s) definitief "
                f"verwijderen van de Pi?\n\n{namen}\n\n"
                "Dit kan niet ongedaan worden gemaakt."):
            return
        paden = " ".join(f"'/home/pi/{n}'" for n, _g in geselecteerd)
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
            messagebox.showinfo("Opruimen - klaar", f"{len(geselecteerd)} item(s) verwijderd.")
            _controleren_klik()
        else:
            messagebox.showerror("Opruimen mislukt", r.stderr.strip() or "Onbekende fout")

    if maak_knop:
        controleer_knop = maak_knop(knoppen, "Controleren", _controleren_klik,
                                     stijl="primair", kleur=ACCENT_PIBEHEER_2)
        controleer_knop.pack(side="left", padx=(0, 8))
        verwijder_knop = maak_knop(knoppen, "Aangevinkte items verwijderen",
                                    _verwijderen_klik, stijl="destructief")
        verwijder_knop.pack(side="left")
    else:
        controleer_knop = tk.Button(knoppen, text="Controleren", command=_controleren_klik)
        controleer_knop.pack(side="left", padx=(0, 8))
        verwijder_knop = tk.Button(knoppen, text="Aangevinkte items verwijderen", command=_verwijderen_klik)
        verwijder_knop.pack(side="left")
    verwijder_knop.config(state="disabled")

    win.after(200, _controleren_klik)
    win.mainloop()


if __name__ == "__main__":
    main()
