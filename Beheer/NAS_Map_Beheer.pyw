#!/usr/bin/env python3
# NAS_Map_Beheer - Pi NAS Suite (versie uit Gedeeld/version.py)
# Dubbelklik om te starten
import os, sys, shutil, threading, subprocess, hashlib

def _script_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except:
        return os.path.dirname(os.path.abspath(sys.argv[0]))

def _nas_root():
    d = _script_dir()
    for sub in ["Beheer","PiServer","Sync","Gedeeld"]:
        if os.path.basename(d) == sub:
            return os.path.dirname(d)
    return d

# ── Kleuren — centraal thema ─────────────────────────────────────
# Expliciet Gedeeld op sys.path zetten voordat we importeren - dit werkte
# eerder alleen "toevallig" omdat dit bestand in dezelfde map als
# pinas_theme.py stond (Gedeeld). Zodra dit bestand vanuit een andere map
# draait (bijvoorbeeld Beheer, na de mapverplaatsing), faalde de kale
# import stilzwijgend en viel dit terug op de HARDGECODEERDE DONKERE
# kleuren hieronder - vandaar dat dit scherm het thema niet overnam, ook
# na een verse herstart. Nu net zo robuust als Pi_NAS_Menu.pyw.
_gedeeld_nmb = os.path.join(_nas_root(), "Gedeeld")
if os.path.isdir(_gedeeld_nmb) and _gedeeld_nmb not in sys.path:
    sys.path.insert(0, _gedeeld_nmb)
try:
    from pinas_theme import BG,PANEL,PANEL2,FG,DIM,OK_C,ERR_C,WARN as WARN_C,BLUE,GREEN_C,RED_C,ACCENT_PINAS,ACCENT_PIBEHEER_2
except ImportError:
    BG="#1e2d3d"; PANEL="#2a3f55"; PANEL2="#344d63"
    FG="#e2eaf2"; DIM="#8ba3be"
    OK_C="#22c55e"; ERR_C="#ef4444"; WARN_C="#f59e0b"
    BLUE="#1d4ed8"; GREEN_C="#16a34a"; RED_C="#dc2626"
    ACCENT_PINAS="#1d4ed8"
    ACCENT_PIBEHEER_2="#d4577d"
try:
    from pinas_ui import maak_header
except ImportError:
    maak_header = None

# Datum van laatste wijziging centraal uit version.py (zelfde Gedeeld-map als pinas_theme)
try:
    from version import BIJGEWERKT
except ImportError:
    BIJGEWERKT = "onbekende datum"

# ── Helpers voor Diagnose / Log / Backup — zelfde als Pi NAS Menu ────────────
import configparser, tempfile, time as _time
import pinas_schijven
import datetime as _datetime

def _c_pinas():
    return os.path.join("C:\\", "PiNAS")

def pibackup_pad(bestand):
    up = os.environ.get("USERPROFILE", "")
    nas = _nas_root()
    kandidaten = [
        os.path.join(_c_pinas(), "Sync", bestand),
        os.path.join(nas, "Sync", bestand),
        os.path.join("C:\\", "bureaublad", "NAS", "NAS_Backup", "pibackup", bestand),
        os.path.join(up, "OneDrive", "Documenten", "Desktop", "NAS", "NAS_Backup", "pibackup", bestand),
        os.path.join(up, "OneDrive", "Documents", "Desktop", "NAS", "NAS_Backup", "pibackup", bestand),
    ]
    for p in kandidaten:
        if os.path.exists(p): return p
    return None

def putty_exe():
    for p in [r"C:\Program Files\PuTTY\putty.exe",
              r"C:\Program Files (x86)\PuTTY\putty.exe"]:
        if os.path.exists(p): return p
    return None

def tigervnc_exe():
    for p in [r"C:\Program Files\TigerVNC\vncviewer.exe",
              r"C:\Program Files (x86)\TigerVNC\vncviewer.exe"]:
        if os.path.exists(p): return p
    return None

def check_putty():        return putty_exe() is not None
def check_tigervnc():     return tigervnc_exe() is not None
def check_pibackup():     return pibackup_pad("pinas_sync_app.pyw") is not None

def check_schijf(letter):
    """Zelfde dubbele-poging logica als Pi NAS Menu - voorkomt valse
    'niet bereikbaar' meldingen bij een kortstondige hapering."""
    for poging in range(2):
        try:
            r = subprocess.run(["net", "use", letter + ":"],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=4)
            if r.returncode == 0:
                return True
        except Exception:
            pass
        if poging == 0:
            _time.sleep(1.5)
    return False

def nieuwste_log_bestand(prefix, fallback):
    """Zoek het nieuwste logbestand in C:\\PiNAS\\Logs dat met prefix begint."""
    try:
        lm = os.path.join("C:\\", "PiNAS", "Logs")
        kand = sorted(f for f in os.listdir(lm)
                      if f.startswith(prefix) and f.endswith(".log"))
        return kand[-1] if kand else fallback
    except Exception:
        return fallback

# PI_IP uit picontrol.cfg - zelfde configbestand als Pi NAS Menu (staat in Beheer)
_cfg = configparser.ConfigParser()
_cfg_pad = os.path.join(_script_dir(), "picontrol.cfg")
if os.path.exists(_cfg_pad):
    _cfg.read(_cfg_pad, encoding="utf-8")
PI_IP = _cfg.get("pi", "ip", fallback="UW_PI_IP_ADRES")

# 30 juli 2026: welk installatiescript hoort bij welke addon-sleutel.
# 13 augustus 2026: centraal in Gedeeld/pinas_addon_scripts.py (verbeterpunt
# #1) - i.p.v. hier en in pinas_addons_beheer.pyw/Pi_NAS_Menu.pyw apart te
# onderhouden. Zie dat bestand voor de reden.
from pinas_addon_scripts import ADDON_SCRIPT as _ADDON_SCRIPT

def _lokale_addon_hash(root_dir, addon_key):
    """SHA256 van het huidige lokale Addons\\<script>.sh. None als het
    lokale bestand niet gevonden is."""
    naam = _ADDON_SCRIPT.get(addon_key)
    if not naam:
        return None
    pad = os.path.join(root_dir, "Addons", naam)
    if not os.path.exists(pad):
        return None
    try:
        with open(pad, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return None

def _schijf_naam(letter, terugval):
    try:
        if _cfg.has_section("schijven"):
            return _cfg.get("schijven", letter, fallback=terugval)
    except Exception:
        pass
    return terugval

def check_share(share_naam, terugval_letter):
    letter = pinas_schijven.vind_letter_of_terugval(share_naam, terugval_letter, PI_IP)
    return check_schijf(letter), letter

def _rbtn_nmb(parent, tekst, cmd, kleur, fg="#e2eaf2", bold=False):
    """Afgeronde Canvas-knop voor NAS Map Beheer."""
    import tkinter as tk
    font = ("Segoe UI", 10, "bold") if bold else ("Segoe UI", 10)
    radius = 8
    padx = 14
    pady_inner = 9

    # Hoogte bepalen
    tmp = tk.Label(parent, text=tekst, font=font)
    th = tmp.winfo_reqheight()
    tmp.destroy()
    min_h = max(th + pady_inner * 2, 34)

    def lighten(h, amt=25):
        h = h.lstrip("#")
        r,g,b2 = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        return f"#{min(r+amt,255):02x}{min(g+amt,255):02x}{min(b2+amt,255):02x}"

    c = tk.Canvas(parent, height=min_h, bg=parent.cget("bg"),
                  highlightthickness=0, bd=0)
    c.pack(fill="x", pady=2)

    state = {"hovered": False, "disabled": False}

    def draw(w=None, h=None):
        w = w or c.winfo_width() or 200
        h = h or c.winfo_height() or min_h
        if h < 10: h = min_h
        bg = lighten(kleur) if state["hovered"] and not state["disabled"] else kleur
        if state["disabled"]:
            bg = "#344d63"
        c.delete("all")
        r = radius
        c.create_arc(0,0,2*r,2*r, start=90, extent=90, fill=bg, outline=bg)
        c.create_arc(w-2*r,0,w,2*r, start=0, extent=90, fill=bg, outline=bg)
        c.create_arc(0,h-2*r,2*r,h, start=180, extent=90, fill=bg, outline=bg)
        c.create_arc(w-2*r,h-2*r,w,h, start=270, extent=90, fill=bg, outline=bg)
        c.create_rectangle(r,0,w-r,h, fill=bg, outline=bg)
        c.create_rectangle(0,r,w,h-r, fill=bg, outline=bg)
        txt_fg = "#6b7280" if state["disabled"] else fg
        c.create_text(padx+r, h//2, text=tekst, font=font, fill=txt_fg, anchor="w")

    def on_configure(e): draw(e.width, e.height)
    def on_enter(e):
        if not state["disabled"]:
            state["hovered"] = True; draw()
    def on_leave(e):
        state["hovered"] = False; draw()
    def on_click(e):
        if not state["disabled"] and cmd: cmd()

    c.bind("<Configure>", on_configure)
    c.bind("<Enter>", on_enter)
    c.bind("<Leave>", on_leave)
    c.bind("<Button-1>", on_click)

    c.after(50, draw)
    c.after(200, draw)

    def config(**kw):
        if "state" in kw:
            state["disabled"] = (kw["state"] == "disabled")
            draw()
    c.config_rbtn = config
    return c

# ── EEN gedeelde lijst van onnodige bestanden - gebruikt door zowel
# Structuurcheck's melding als Opruimen's daadwerkelijke verwijderknop.
#
# 6 augustus 2026 (Frans: "constatering tot zover wel misschien correct,
# maar ruimt niet op"): dit waren voorheen TWEE losse lijsten (een simpele
# in de Structuurcheck-tab, een rijkere met redenen in de Opruimen-tab) -
# ruim uit elkaar gegroeid (de Opruimen-lijst had zelfs nog oude "_v7"-
# bestandsnamen uit 12 juli terwijl de infographic allang (16 juli) hele-
# maal geschrapt was). Nu 1 bron: (map, bestand, sleutel, reden). bestand
# mag None zijn voor een sectiekopje (alleen getoond in Opruimen).
def _vind_pycache_mappen(root_dir):
    """Zoekt ALLE __pycache__-mappen, hoe diep genest ook, onder Sync/
    PiServer/Beheer/Gedeeld. EEN functie voor zowel Structuurcheck's
    melding als Opruimen's verwijderknop (6 augustus 2026, Frans: "ik heb
    met het handje nog steeds Beheer\\core\\__pycache__ moeten opruimen"
    - Opruimen had een VASTE lijst submappen die geneste mappen zoals
    Beheer\\core\\ miste, terwijl Structuurcheck's melding al wel
    recursief zocht en dus WEL liet zien wat Opruimen niet kon
    verwijderen - exact dezelfde soort 2-lijsten-bug als bij
    ONNODIGE_BESTANDEN hierboven, nu voor __pycache__. Recursief zoeken
    dekt élke toekomstige geneste map vanzelf, geen aparte regel meer
    nodig per submap zoals "Sync/core" dat eerder was."""
    gevonden = []
    for submap in ["Sync", "PiServer", "Beheer", "Gedeeld"]:
        basis = os.path.join(root_dir, submap)
        if not os.path.isdir(basis):
            continue
        for dirpath, dirnames, _ in os.walk(basis):
            for d in dirnames:
                if d == "__pycache__":
                    gevonden.append(os.path.join(dirpath, d))
    return gevonden

ONNODIGE_BESTANDEN = [
    # 6 augustus 2026 (Frans: "die oude dingen die al lang weg zijn mogen
    # er ook uit... het moet nu een actueel ding worden"): historische
    # opruim-items van 12/16 juli verwijderd - waren allang van iedereens
    # schijf verdwenen en maakten deze lijst zelf tot rommel. Alleen nog
    # de actuele, net-ontdekte Node.js-resten staan hier - dat blijven ze
    # ook (Node.js komt niet terug), tot Frans ze zelf opruimt.
    ("Publicatie", None, None,
     "Publicatie - Functieoverzicht is 6 augustus 2026 van Node.js/docx naar Python/PDF omgezet"),
    ("Publicatie", "build_functieoverzicht.js", "funcjs", "Functieoverzicht nu Python/PDF (build_functieoverzicht.py)"),
    ("Publicatie", "PiNAS_Functieoverzicht.docx", "funcdocx", "Functieoverzicht nu Python/PDF"),
    ("Publicatie", "package.json", "pkgjson", "npm niet meer nodig sinds Functieoverzicht op Python draait"),
    ("Publicatie", "package-lock.json", "pkglockjson", "npm niet meer nodig sinds Functieoverzicht op Python draait"),
    # 10 augustus 2026 (Frans: "functieoverzicht kan vervallen als je een
    # korte versie op een pagina kunt opnemen in de presentatie"): het
    # Functieoverzicht-eindproduct zelf is nu ook vervangen - een compacte
    # versie staat als losse pagina in PiNAS_Suite_Presentatie.pptx. Deze
    # twee bestanden zijn dus zelf nu ook "oude Node.js-achtige resten"
    # geworden, net als de rij hierboven.
    ("Publicatie", "build_functieoverzicht.py", "funcpy", "Functieoverzicht vervangen door een pagina in de presentatie (10 augustus 2026)"),
    ("Publicatie", "PiNAS_Functieoverzicht.pdf", "funcpdf", "Functieoverzicht vervangen door een pagina in de presentatie (10 augustus 2026)"),
    # 10 augustus 2026: eenmalig hulpmiddel om de "Op mijn iPhone"-kwestie
    # uit te zoeken - vraag is beantwoord (InstallationLookupFailed, een
    # vaste iOS-beperking, geen bug), dus dit mag weg. Bewust nooit in
    # pinas_versies.json/Structuurcheck/Topografie opgenomen geweest, want
    # het was altijd al bedoeld als wegwerpscript.
    ("Gedeeld", "pinas_iphone_diagnose.sh", "iphonediagsh", "Onderzoek 'Op mijn iPhone' afgerond - InstallationLookupFailed is een vaste iOS-beperking"),
    ("Gedeeld", "pinas_iphone_diagnose.bat", "iphonediagbat", "Onderzoek 'Op mijn iPhone' afgerond - InstallationLookupFailed is een vaste iOS-beperking"),
    # 10 augustus 2026 (Frans: "dit bestand is ook niet meer nodig denk ik"):
    # de losse Sync-handleiding is inhoudelijk overgenomen in hoofdstuk 5 van
    # PiNAS_Suite_Handleiding.pdf - dit bestand is dus dubbel geworden.
    ("Sync", "HANDLEIDING_pinas_sync.md", "syncmd", "Inhoud zit al in hoofdstuk 5 van PiNAS_Suite_Handleiding.pdf (10 augustus 2026)"),
]

def main():
    import tkinter as gui
    from tkinter import messagebox
    from tkinter import scrolledtext
    import subprocess, sys, os, threading

    root_dir = _nas_root()

    # Alle bekende hoofdmappen van de suite - gebruikt om een bestand te
    # kunnen terugvinden als het niet op zijn juiste plek staat, zodat
    # Structuurcheck kan zeggen WAAR het wel staat i.p.v. alleen ONTBREEKT.
    # ArchiefBackup (voorheen QnapCheck, hernoemd 8 augustus 2026) is
    # hoofdniveau geworden (hoort bij Backup Beheer, geen zijproject meer) -
    # de oude naam QnapCheck en de nog oudere Zijprojecten\QnapCheck-plek
    # blijven nog in deze lijst zodat bestanden die daar nog staan (bijv. op
    # een installatie die deze hernoeming nog niet heeft) gevonden en
    # verplaatst kunnen worden.
    ALLE_MAPPEN = ["PiServer", "Sync", "Beheer", "Gedeeld", "ArchiefBackup", "Addons", "Publicatie",
                   "Installatie", "QnapCheck", os.path.join("Zijprojecten", "QnapCheck")]

    win = gui.Tk()
    win.title(f"Structuurcheck & Opruimen — Pi NAS Suite (bijgewerkt: {BIJGEWERKT})")
    win.configure(bg=BG)
    win.resizable(True, True)
    win.geometry("780x860")
    win.minsize(680, 700)

    # Header - 5 augustus 2026 (Frans: alle headers consistent, geen
    # Terug-knop, wel een Help-knop overal) - omgezet naar de gedeelde
    # maak_header() i.p.v. een eigen, hardcoded #2f3b47-kleur (die
    # nergens anders in de suite voorkwam).
    STRUCTUURCHECK_HELP = [
        ("Structuurcheck", "Vergelijkt de bestanden die op schijf staan met de lijst verwachte "
         "bestanden (pinas_versies.json). Laat per bestand zien: aanwezig/ontbreekt, of de datum "
         "op schijf overeenkomt met de laatst geleverde versie, en of een bestand op de verkeerde "
         "plek staat (met een 'Verplaats'-knop om dat in 1 klik recht te zetten)."),
        ("Onnodige bestanden", "__pycache__-mappen en andere bestanden die nergens in de suite "
         "bekend zijn - kandidaten om op te ruimen, worden nooit automatisch verwijderd zonder "
         "jouw bevestiging."),
        ("Opruimen", "Aparte tab naast Structuurcheck - verwijdert de hierboven gevonden onnodige "
         "bestanden, pas na een expliciete keuze per bestand."),
    ]
    if maak_header:
        # 13 augustus 2026: eigen kleur (ACCENT_PIBEHEER_2) - dit scherm
        # opent via Beheer -> Controles -> Structuurcheck & Opruimen, dus
        # matcht nu de Controles-tint i.p.v. de algemene ACCENT_PINAS.
        maak_header(win, "Structuurcheck & Opruimen", subtekst=f"Map: {root_dir}",
                    help_hoofdstukken=STRUCTUURCHECK_HELP, kleur=ACCENT_PIBEHEER_2)
    else:
        hdr = gui.Frame(win, bg=ACCENT_PIBEHEER_2, pady=14)
        hdr.pack(fill="x")
        gui.Label(hdr, text="Structuurcheck & Opruimen",
                  font=("Segoe UI",16,"bold"), bg=ACCENT_PIBEHEER_2, fg="#ffffff").pack()
        gui.Label(hdr, text=f"Map: {root_dir}",
                  font=("Segoe UI",9), bg=ACCENT_PIBEHEER_2, fg="#9fc2e0").pack()

    # Tab knoppen
    tab_frame = gui.Frame(win, bg=PANEL2)
    tab_frame.pack(fill="x")
    tab_container = gui.Frame(win, bg=BG)
    tab_container.pack(fill="both", expand=True)

    tabs = {}
    tab_btns = {}

    def toon_tab(naam):
        for n,f in tabs.items(): f.pack_forget()
        for n,b in tab_btns.items():
            b.config(bg=BLUE if n==naam else PANEL2)
        tabs[naam].pack(fill="both", expand=True)

    for naam in ["Structuurcheck", "Opruimen"]:
        b = gui.Button(tab_frame, text=naam,
                       font=("Segoe UI",9), bg=PANEL2, fg=FG,
                       relief="flat", cursor="hand2", padx=16, pady=8,
                       borderwidth=0, highlightthickness=0,
                       command=lambda n=naam: toon_tab(n))
        b.pack(side="left")
        tab_btns[naam] = b

    # Footer
    footer = gui.Frame(win, bg=PANEL, pady=8)
    footer.pack(fill="x", side="bottom")
    gui.Label(footer, text=f"Structuurcheck & Opruimen — Pi NAS Suite (bijgewerkt: {BIJGEWERKT})  |  Autonoom pad detectie",
              font=("Segoe UI",8), bg=PANEL, fg=DIM).pack(side="right", padx=12)

    # ════════════════════════════════════════════════════════════
    # TAB 1: STRUCTUURCHECK
    # ════════════════════════════════════════════════════════════
    f1 = gui.Frame(tab_container, bg=BG)
    tabs["Structuurcheck"] = f1

    gui.Label(f1, text="Controle mappenstructuur en verplichte bestanden",
              font=("Segoe UI",9), bg=BG, fg=DIM).pack(pady=(10,6), padx=16, anchor="w")

    check_text = scrolledtext.ScrolledText(
        f1, font=("Consolas",9), bg=PANEL, fg=FG,
        relief="flat", height=28, wrap="word")
    check_text.pack(fill="both", expand=True, padx=12, pady=(0,8))
    for tag, kleur in [("ok",OK_C),("fout",ERR_C),("warn",WARN_C)]:
        check_text.tag_config(tag, foreground=kleur)
    check_text.tag_config("kop", foreground="#60a5fa",
                          font=("Consolas",9,"bold"))

    def schrijf(tekst, tag=""):
        check_text.config(state="normal")
        check_text.insert("end", tekst+"\n", tag)
        check_text.see("end")
        check_text.config(state="disabled")

    def check_alles():
        check_text.config(state="normal")
        check_text.delete("1.0","end")
        check_text.config(state="disabled")
        fouten = 0
        schrijf(f"NAS root: {root_dir}\n", "kop")
        schrijf("MAPPENSTRUCTUUR", "kop")
        for naam, beschr in [
            ("PiServer",        "Server installer"),
            ("Sync",     "Backup programma"),
            ("Beheer",    "Menu dashboard"),
            ("Gedeeld",      "Hulpscripts + centrale modules"),
            ("ArchiefBackup","Archief Backup Bewaking - hoort bij Backup Beheer, geen zijproject"),
            ("Addons",       "Add-ons: Pi-hole, ZeroTier, Nextcloud, Vaultwarden - hoofdmap"),
            ("Publicatie",   "Handleiding, Topografie, Presentatie, GitHub publieke versie"),
            ("Installatie",  "Installers"),
            ("Logs",         "Logbestanden (automatisch aangemaakt)"),
        ]:
            pad = os.path.join(root_dir, naam)
            if os.path.isdir(pad):
                schrijf(f"  v  {naam:15} {beschr}", "ok")
            else:
                schrijf(f"  x  {naam:15} ONTBREEKT", "fout")
                fouten += 1

        schrijf("\nVERPLICHTE BESTANDEN", "kop")
        # 14 augustus 2026: deze hand-getypte lijst (~130 regels) is
        # vervangen door Gedeeld\pinas_bestanden_register.py - de ENE bron
        # van waarheid, ook gebruikt door maak_publieke_versie.py en
        # maak_starterkit.py (die eerder allebei hun eigen kopie van een
        # deel van deze lijst bijhielden, en daardoor meerdere keren uit
        # de pas liepen: WinSCP-installer, de Controles-schermen,
        # pinas_versies_hashes.json ontbraken op verschillende plekken -
        # zie de docstring in dat register voor de volledige lijst gaten
        # die dit oploste). Zijprojecten\AdblockVPN (16 juli 2026, door
        # Frans zelf verwijderd) en PiNAS_Toegangsoverzicht (bevat echte
        # wachtwoorden, hoort nooit in de suite-boom) staan bewust NIET
        # in het register.
        try:
            import pinas_bestanden_register as _reg
            checks = _reg.voor_structuurcheck()
        except ImportError:
            schrijf("  x  Gedeeld\\pinas_bestanden_register.py niet gevonden - "
                     "bestandscontrole kan niet doorgaan", "fout")
            checks = []
        misplaatst = []  # (huidig_pad, juiste_pad, weergavenaam) - te verplaatsen
        dubbel = []       # (extra_pad, weergavenaam) - overbodige kopie, te verwijderen

        # Bestandsnamen die vaker dan eens in de lijst voorkomen (zoals
        # __init__.py, dat zowel in Sync\core als Beheer\core hoort te
        # bestaan als twee onafhankelijke lege markeerbestanden) mogen NOOIT
        # als "verkeerd geplaatst" of "dubbel" worden aangemerkt - anders
        # denkt de check dat het ene __init__.py "verhuisd" of "verwijderd"
        # moet worden t.o.v. het andere, wat onzin is: het zijn geen kopieen
        # van elkaar, gewoon toevallig dezelfde naam op meerdere plekken.
        naam_telling = {}
        for _, _bestand, _ in checks:
            naam_telling[_bestand] = naam_telling.get(_bestand, 0) + 1
        vaker_dan_eens = {naam for naam, n in naam_telling.items() if n > 1}

        # Voor sommige van die dubbel-voorkomende namen maakt de INHOUD wel
        # degelijk uit - start.bat in Sync is een heel ander bestand dan
        # start.bat in ArchiefBackup. Alleen op naam controleren zou een bestand
        # met de juiste naam maar verkeerde inhoud (bijv. de ArchiefBackup-
        # launcher die per ongeluk in Sync\ staat) ten onrechte goedkeuren.
        # Voor deze paren wordt de inhoud gecontroleerd op een herkenbare
        # tekst; bij een mismatch wordt gezocht welke andere plek WEL past,
        # en dat bestand als verkeerd geplaatst aangemerkt.
        INHOUD_HANDTEKENING = {
            ("Sync", "start.bat"): "pinas_sync_app.pyw",
            ("ArchiefBackup", "start.bat"): "archief_backup_bewaking.pyw",
        }

        def _lees_stukje(pad, lengte=4000):
            try:
                with open(pad, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read(lengte)
            except Exception:
                return ""

        inhoud_gecontroleerd = set()  # (map_, bestand) die hieronder al zijn afgehandeld

        for map_, bestand, beschr in checks:
            if (map_, bestand) not in INHOUD_HANDTEKENING:
                continue
            inhoud_gecontroleerd.add((map_, bestand))
            volledig_juist = f"{map_}\\{bestand}"
            juiste_pad = os.path.join(root_dir, map_, bestand)
            verwachte_tekst = INHOUD_HANDTEKENING[(map_, bestand)]
            if not os.path.exists(juiste_pad):
                schrijf(f"  x  {volledig_juist:52} ONTBREEKT (hier zelf aanmaken - "
                         f"dit is een eigen kopie, geen gedeeld bestand)", "fout")
                fouten += 1
                continue
            inhoud = _lees_stukje(juiste_pad)
            if verwachte_tekst in inhoud:
                schrijf(f"  v  {volledig_juist:52} {beschr}", "ok")
                continue
            # Naam klopt, inhoud niet - zoek uit welk ander bestand dit
            # eigenlijk is.
            gevonden_elders = None
            for (andere_map, andere_bestand), andere_tekst in INHOUD_HANDTEKENING.items():
                if (andere_map, andere_bestand) == (map_, bestand):
                    continue
                if andere_bestand != bestand:
                    continue
                if andere_tekst in inhoud:
                    gevonden_elders = (andere_map, andere_bestand)
                    break
            if gevonden_elders:
                andere_map, andere_bestand = gevonden_elders
                juiste_pad_elders = os.path.join(root_dir, andere_map, andere_bestand)
                volledig_elders = f"{andere_map}\\{andere_bestand}"
                schrijf(f"  !  {volledig_juist:52} bevat de INHOUD van {volledig_elders} - "
                         f"hoort daar, niet hier", "warn")
                if not os.path.exists(juiste_pad_elders):
                    misplaatst.append((juiste_pad, juiste_pad_elders,
                                        f"{volledig_juist} (verkeerde inhoud)  ->  {volledig_elders}"))
                else:
                    schrijf(f"     ({volledig_elders} bestaat daar zelf ook al - "
                             f"controleer handmatig welke klopt)", "warn")
                fouten += 1
            else:
                schrijf(f"  ?  {volledig_juist:52} bestaat, maar de inhoud klopt niet met "
                         f"wat hier verwacht wordt", "warn")

        for map_, bestand, beschr in checks:
            if (map_, bestand) in inhoud_gecontroleerd:
                continue
            volledig_juist = f"{map_}\\{bestand}"
            juiste_pad = os.path.join(root_dir, map_, bestand)
            if os.path.exists(juiste_pad):
                schrijf(f"  v  {volledig_juist:52} {beschr}", "ok")
                if bestand not in vaker_dan_eens:
                    # Ook checken of er, naast de juiste plek, ELDERS nog
                    # een extra kopie rondslingert - en zo ja, kijken welke
                    # van de twee nieuwer is (op wijzigingsdatum), zodat een
                    # per ongeluk oudere versie op de juiste plek niet een
                    # nieuwere kopie ergens anders laat overschrijven.
                    for andere_map in ALLE_MAPPEN:
                        if andere_map == map_:
                            continue
                        extra_pad = os.path.join(root_dir, andere_map, bestand)
                        if os.path.exists(extra_pad):
                            volledig_extra = f"{andere_map}\\{bestand}"
                            tijd_juist = os.path.getmtime(juiste_pad)
                            tijd_extra = os.path.getmtime(extra_pad)
                            if tijd_extra > tijd_juist:
                                schrijf(f"     (LET OP: {volledig_extra} is NIEUWER dan de "
                                         f"versie hierboven - klik hieronder om te vervangen)", "warn")
                                dubbel.append(("vervang", extra_pad, juiste_pad, volledig_extra, volledig_juist))
                            else:
                                schrijf(f"     (dubbel: oudere/gelijke kopie staat ook nog "
                                         f"in {volledig_extra} - kan weg)", "warn")
                                dubbel.append(("verwijder", extra_pad, None, volledig_extra, None))
                continue
            if bestand in vaker_dan_eens:
                schrijf(f"  x  {volledig_juist:52} ONTBREEKT (hier zelf aanmaken - "
                         f"dit is een eigen kopie, geen gedeeld bestand)", "fout")
                fouten += 1
                continue
            # Niet op de juiste plek - zoek het overal anders binnen de suite
            gevonden_pad = None
            gevonden_in = None
            for andere_map in ALLE_MAPPEN:
                if andere_map == map_:
                    continue
                kandidaat = os.path.join(root_dir, andere_map, bestand)
                if os.path.exists(kandidaat):
                    gevonden_pad = kandidaat
                    gevonden_in = andere_map
                    break
            if gevonden_pad:
                volledig_fout = f"{gevonden_in}\\{bestand}"
                schrijf(f"  !  {volledig_fout:52} staat hier, hoort in {volledig_juist}", "warn")
                misplaatst.append((gevonden_pad, juiste_pad, f"{volledig_fout}  ->  {volledig_juist}"))
            else:
                schrijf(f"  x  {volledig_juist:52} ONTBREEKT (nergens gevonden)", "fout")
                fouten += 1

        # Python-installer: bestandsnaam bevat een versienummer dat bij elke
        # "Onderhoud -> Windows onderdelen" download kan wijzigen, dus wordt
        # met een joker-patroon herkend i.p.v. een vaste naam (zelfde patroon
        # als het Status-scherm gebruikt: python-3*.exe). De gevonden
        # bestandsnaam wordt hieronder ook toegevoegd aan bekend_per_map,
        # zodat de "onbekende bestanden"-scan verderop deze niet ten
        # onrechte als vreemd bestand aanmerkt.
        import glob as _glob
        installatie_patronen = [
            ("python-3*.exe", "Python installer (versie kan afwijken)"),
        ]
        _installatie_pad = os.path.join(root_dir, "Installatie")
        installatie_gevonden_namen = set()
        for patroon, beschr in installatie_patronen:
            treffers = _glob.glob(os.path.join(_installatie_pad, patroon))
            if treffers:
                for t in treffers:
                    naam = os.path.basename(t)
                    installatie_gevonden_namen.add(naam)
                    volledig = "Installatie\\" + naam
                    schrijf(f"  v  {volledig:52} {beschr}", "ok")
            else:
                volledig = "Installatie\\" + patroon
                schrijf(f"  ?  {volledig:52} niet aanwezig - "
                         f"wordt gedownload bij installatie/bijwerken", "")

        schrijf("\nONNODIGE BESTANDEN", "kop")
        n_overbodig = 0
        for map_, bestand, _sleutel, _reden in ONNODIGE_BESTANDEN:
            if bestand is None:
                continue  # sectiekopje, alleen voor Opruimen-tab
            pad = os.path.join(root_dir, map_, bestand)
            if os.path.exists(pad):
                schrijf(f"  !  {map_:12} {bestand} - kan weg", "warn")
                n_overbodig += 1
        # node_modules (Publicatie) - npm-afhankelijkheden, niet meer nodig
        # sinds Functieoverzicht op Python/PDF draait (6 augustus 2026).
        _node_modules_pad = os.path.join(root_dir, "Publicatie", "node_modules")
        if os.path.isdir(_node_modules_pad):
            schrijf(f"  !  {'Publicatie':12} node_modules\\ - kan weg", "warn")
            n_overbodig += 1
        # __pycache__ mappen opsporen - gedeelde functie, zie boven
        for pycache_pad in _vind_pycache_mappen(root_dir):
            rel = os.path.relpath(pycache_pad, root_dir)
            schrijf(f"  !  {rel} - kan weg", "warn")
            n_overbodig += 1
        if n_overbodig == 0:
            schrijf("  v  Geen onnodige bestanden", "ok")

        schrijf("\nONBEKENDE BESTANDEN (nergens in de suite bekend)", "kop")
        # Nu gebaseerd op een echt volledige lijst (opgebouwd vanuit een
        # verse export van de hele mappenstructuur) - eerdere versie gaf te
        # veel valse meldingen omdat de lijst toen nog onvolledig was.
        # Tijdelijke bestanden (bijv. een open LibreOffice/Office-document)
        # worden ook genegeerd - dat zijn geen suite-bestanden, gewoon een
        # spoor van een geopend document.
        bekend_per_map = {}
        for map_, bestand, _ in checks:
            bekend_per_map.setdefault(map_, set()).add(bestand)
        for map_, bestand, _sleutel, _reden in ONNODIGE_BESTANDEN:
            if bestand is not None:
                bekend_per_map.setdefault(map_, set()).add(bestand)
        # De werkelijk gevonden Python/Node.js installer-bestandsnamen (via de
        # joker-patronen hierboven) horen ook bij "bekend" - anders zou de
        # "onbekende bestanden"-scan hieronder ze alsnog als vreemd bestand
        # aanmerken (ze staan niet letterlijk in checks/overbodig, want hun
        # naam bevat een versienummer dat kan wijzigen). Per-map toegevoegd
        # (alleen bij "Installatie"), niet globaal - zie 5 augustus 2026-fix
        # hieronder bij de eigenlijke controle.
        for naam in installatie_gevonden_namen:
            bekend_per_map.setdefault("Installatie", set()).add(naam)

        def _is_tijdelijk(naam):
            return (naam.startswith(".~lock.") or naam.startswith("~$")
                    or naam.endswith("#") or naam.endswith(".tmp"))

        onbekend = []  # (pad, weergave)
        for map_ in ["PiServer", "Sync", "Beheer", "Gedeeld", "ArchiefBackup", "Addons", "Publicatie",
                     "Installatie", "QnapCheck", os.path.join("Zijprojecten", "QnapCheck")]:
            mappad = os.path.join(root_dir, map_)
            if not os.path.isdir(mappad):
                continue
            bekend = bekend_per_map.get(map_, set())
            try:
                for naam in os.listdir(mappad):
                    volledig_pad = os.path.join(mappad, naam)
                    if os.path.isdir(volledig_pad):
                        continue  # submappen (zoals core\, assets\) laten we hier met rust
                    # 5 augustus 2026 (Frans: Beheer_install.bat stond
                    # verkeerd in Publicatie, maar Structuurcheck zag het
                    # niet) - "naam in alle_bekende_namen" verwijderd: dat
                    # controleerde of een bestand OOIT ergens bekend is,
                    # niet of het bekend is IN DEZE map. Een bestand dat
                    # ergens anders hoort te staan werd daardoor stil
                    # overgeslagen i.p.v. als verkeerd geplaatst gemeld.
                    if naam in bekend or _is_tijdelijk(naam):
                        continue
                    volledig_naam = f"{map_}\\{naam}"
                    schrijf(f"  ?  {volledig_naam:52} hoort nergens bij - kandidaat voor opruimen", "warn")
                    onbekend.append((volledig_pad, volledig_naam))
            except Exception:
                pass
        if not onbekend:
            schrijf("  v  Geen onbekende bestanden", "ok")

        schrijf("\nVERSIE-CONTROLE (datum laatst geleverde versie)", "kop")
        verouderd = []  # (pad, weergave, geleverd_op, huidige_datum)
        mist_in_versies = []
        mist_in_checks = []
        versies_pad = os.path.join(root_dir, "Gedeeld", "pinas_versies.json")
        if os.path.exists(versies_pad):
            try:
                import json as _json
                with open(versies_pad, "r", encoding="utf-8") as f:
                    versies = _json.load(f)
            except Exception:
                versies = {}
            for relpad, geleverd_str in versies.items():
                if relpad.startswith("_"):
                    continue  # het "_uitleg"-veld overslaan
                volledig_pad = os.path.join(root_dir, relpad)
                if not os.path.exists(volledig_pad):
                    continue  # ontbrekende bestanden zijn al gemeld hierboven
                try:
                    import datetime as _dt
                    geleverd_op = _dt.datetime.strptime(geleverd_str, "%Y-%m-%d %H:%M")
                    huidig_tijdstip = _dt.datetime.fromtimestamp(os.path.getmtime(volledig_pad))
                    if huidig_tijdstip < geleverd_op:
                        schrijf(f"  !  {relpad:52} verouderd - laatste versie is van "
                                 f"{geleverd_op}, dit bestand is van {huidig_tijdstip}", "warn")
                        verouderd.append((volledig_pad, relpad, geleverd_str, str(huidig_tijdstip)))
                except Exception:
                    continue
            if not verouderd:
                schrijf("  v  Alle bestanden zijn de laatst geleverde versie", "ok")

            # 27 juli 2026 (Frans): losstaande check die pinas_versies.json
            # vergelijkt met de eigen bekende-bestandenlijst hierboven -
            # voorkomt dat een bestand er stilletjes niet in terechtkomt
            # (kwam al 2x eerder voor: nas_installer_cli.py en de
            # printserver-scripts eerst gemist).
            schrijf("\nVERSIE-MANIFEST vs. BEKENDE BESTANDEN", "kop")
            bekende_sleutels = {f"{m}\\{n}" for (m, n, _) in checks}
            versie_sleutels = {k for k in versies.keys() if not k.startswith("_")}
            # pinas_versies_hashes.json hoort BEWUST niet in pinas_versies.json
            # (zie entry hierboven) - anders zou deze uitzondering hier zelf
            # weer als "geen entry"-waarschuwing verschijnen.
            _GEEN_VERSIE_ENTRY_VERWACHT = {"Gedeeld\\pinas_versies_hashes.json"}
            mist_in_versies = sorted(bekende_sleutels - versie_sleutels - _GEEN_VERSIE_ENTRY_VERWACHT)
            mist_in_checks = sorted(versie_sleutels - bekende_sleutels)
            if mist_in_versies:
                for s in mist_in_versies:
                    schrijf(f"  ?  {s:52} bekend bestand, maar GEEN entry in pinas_versies.json", "warn")
            if mist_in_checks:
                for s in mist_in_checks:
                    schrijf(f"  ?  {s:52} staat in pinas_versies.json, maar onbekend hierboven (typo/hernoemd?)", "warn")
            if not mist_in_versies and not mist_in_checks:
                schrijf("  v  Versie-manifest en bekende-bestandenlijst komen overeen", "ok")
        else:
            schrijf("  ?  pinas_versies.json niet gevonden - versiecontrole overgeslagen", "warn")

        # 30 juli 2026 (Frans): "ik wil een niet te missen signaal, en
        # misschien moet Structuurcheck dit ook meenemen" - vergelijkt de
        # SHA256-versie-marker die elk add-on-script bij een geslaagde
        # installatie op de Pi achterlaat (schrijf_versie_marker()) met het
        # huidige lokale bestand in Addons\. De PRIMAIRE garantie hiervoor
        # is de waarschuwing bovenaan Status & details (die zie je toch al
        # standaard) - dit hier is de aanvullende, bewuste controle.
        schrijf("\nADD-ON VERSIES OP DE PI", "kop")
        addon_verouderd = []
        try:
            addon_cmd = (
                "for k in nextcloud pihole zerotier vaultwarden printer; do "
                "  if [ -f /etc/pinas-addon-versies/$k.sha256 ]; then "
                "    echo \"hash_$k:$(cat /etc/pinas-addon-versies/$k.sha256 2>/dev/null)\"; "
                "  else echo \"hash_$k:geen\"; fi; "
                "done"
            )
            r = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=4", "-o", "BatchMode=yes",
                 f"pi@{PI_IP}", addon_cmd],
                capture_output=True, text=True, timeout=8,
                creationflags=subprocess.CREATE_NO_WINDOW)
            pi_hashes = {}
            for regel in r.stdout.strip().splitlines():
                if regel.startswith("hash_"):
                    sleutel, _, waarde = regel.partition(":")
                    pi_hashes[sleutel[len("hash_"):]] = waarde.strip()
            if not pi_hashes:
                schrijf("  ?  Pi niet bereikbaar - add-on-versies niet gecontroleerd", "warn")
            else:
                for key, mooie_naam in [
                    ("nextcloud", "Nextcloud"), ("pihole", "Pi-hole"),
                    ("zerotier", "ZeroTier"), ("vaultwarden", "Vaultwarden"),
                    ("printer", "Printserver"),
                ]:
                    pi_hash = pi_hashes.get(key)
                    lokaal_pad = os.path.join(root_dir, "Addons", _ADDON_SCRIPT[key])
                    if not os.path.exists(lokaal_pad):
                        continue   # add-on-script niet lokaal aanwezig, niets te vergelijken
                    if pi_hash in (None, "geen"):
                        schrijf(f"  ?  {mooie_naam:24} nog nooit geinstalleerd op de Pi met deze versie-check "
                                 f"(of nog niet opnieuw geinstalleerd sinds deze functie is toegevoegd)", "warn")
                        continue
                    lokaal_hash = _lokale_addon_hash(root_dir, key)
                    if lokaal_hash and lokaal_hash == pi_hash:
                        schrijf(f"  v  {mooie_naam:24} Pi draait de nieuwste versie", "ok")
                    elif lokaal_hash:
                        schrijf(f"  !  {mooie_naam:24} Pi draait een ANDERE versie dan het lokale bestand - "
                                 f"opnieuw installeren via Addons Beheer", "warn")
                        addon_verouderd.append(mooie_naam)
        except Exception:
            schrijf("  ?  Pi niet bereikbaar - add-on-versies niet gecontroleerd", "warn")

        schrijf(f"\n{'─'*60}", "kop")
        alles_schoon = (fouten == 0 and n_overbodig == 0 and not misplaatst
                        and not dubbel and not onbekend and not verouderd
                        and not mist_in_versies and not mist_in_checks
                        and not addon_verouderd)
        if alles_schoon:
            schrijf(f"v  Alles OK ({len(checks)} bestanden) - niets te doen", "ok")
        else:
            if fouten == 0:
                schrijf(f"v  Alle {len(checks)} verwachte bestanden zijn aanwezig", "ok")
            else:
                schrijf(f"x  {fouten} bestand(en) ontbreken", "fout")
        if n_overbodig > 0:
            schrijf(f"!  {n_overbodig} onnodige bestand(en) - gebruik tabblad Opruimen", "warn")
        if misplaatst:
            schrijf(f"!  {len(misplaatst)} bestand(en) staan op de verkeerde plek - "
                     f"klik hieronder om te verplaatsen", "warn")
        if dubbel:
            schrijf(f"!  {len(dubbel)} dubbele/verouderde kopie(en) gevonden - klik hieronder om te verwerken", "warn")
        if onbekend:
            schrijf(f"!  {len(onbekend)} onbekend bestand(en) gevonden - klik hieronder om te verwijderen", "warn")
        if verouderd:
            schrijf(f"!  {len(verouderd)} bestand(en) zijn een verouderde versie - "
                     f"nog niet overgezet vanuit het chatgesprek", "warn")
        if mist_in_versies or mist_in_checks:
            schrijf(f"!  {len(mist_in_versies) + len(mist_in_checks)} verschil(len) tussen "
                     f"pinas_versies.json en de bekende-bestandenlijst - zie hierboven", "warn")
        if addon_verouderd:
            schrijf(f"!  {len(addon_verouderd)} add-on(s) verouderd op de Pi: {', '.join(addon_verouderd)} - "
                     f"zie ADD-ON VERSIES OP DE PI hierboven", "warn")

        verplaats_knop.pack_forget()
        if misplaatst:
            verplaats_knop.pack(fill="x", pady=(6,0))
        _huidige_misplaatst["lijst"] = misplaatst

        verwijder_dubbel_knop.pack_forget()
        if dubbel:
            verwijder_dubbel_knop.pack(fill="x", pady=(6,0))
        _huidige_dubbel["lijst"] = dubbel

        verwijder_onbekend_knop.pack_forget()
        if onbekend:
            verwijder_onbekend_knop.pack(fill="x", pady=(6,0))
        _huidige_onbekend["lijst"] = onbekend

    def verwijder_onbekende():
        lijst = _huidige_onbekend["lijst"]
        if not lijst:
            return
        namen = "\n".join(f"  - {weergave}" for _, weergave in lijst)
        if not messagebox.askyesno("Verwijderen bevestigen",
                f"{len(lijst)} onbekend bestand(en) verwijderen?\n\n{namen}\n\n"
                f"Deze staan niet in de bekende lijst van de suite (verwacht of "
                f"al-bekend-overbodig) - weet je zeker dat ze weg mogen?"):
            return
        for pad, weergave in lijst:
            try:
                os.remove(pad)
                schrijf(f"  v  Verwijderd: {weergave}", "ok")
            except Exception as e:
                schrijf(f"  x  Mislukt: {weergave} - {e}", "fout")
        win.after(300, check_alles)

    def verplaats_misplaatste():
        lijst = _huidige_misplaatst["lijst"]
        if not lijst:
            return
        namen = "\n".join(f"  - {weergave}" for _, _, weergave in lijst)
        if not messagebox.askyesno("Verplaatsen bevestigen",
                f"{len(lijst)} bestand(en) verplaatsen naar de juiste map?\n\n{namen}"):
            return
        for huidig_pad, juiste_pad, weergave in lijst:
            try:
                os.makedirs(os.path.dirname(juiste_pad), exist_ok=True)
                shutil.move(huidig_pad, juiste_pad)
                schrijf(f"  v  Verplaatst: {weergave}", "ok")
            except Exception as e:
                schrijf(f"  x  Mislukt: {weergave} - {e}", "fout")
        win.after(300, check_alles)

    def verwijder_dubbele():
        lijst = _huidige_dubbel["lijst"]
        if not lijst:
            return
        regels = []
        for actie, extra_pad, juiste_pad, volledig_extra, volledig_juist in lijst:
            if actie == "vervang":
                regels.append(f"  - VERVANG {volledig_juist} door nieuwere versie uit {volledig_extra}")
            else:
                regels.append(f"  - VERWIJDER dubbele kopie {volledig_extra}")
        namen = "\n".join(regels)
        if not messagebox.askyesno("Bevestigen",
                f"{len(lijst)} actie(s) uitvoeren?\n\n{namen}"):
            return
        for actie, extra_pad, juiste_pad, volledig_extra, volledig_juist in lijst:
            try:
                if actie == "vervang":
                    os.remove(juiste_pad)
                    shutil.move(extra_pad, juiste_pad)
                    schrijf(f"  v  Vervangen: {volledig_juist} <- {volledig_extra}", "ok")
                else:
                    os.remove(extra_pad)
                    schrijf(f"  v  Verwijderd: {volledig_extra}", "ok")
            except Exception as e:
                schrijf(f"  x  Mislukt: {volledig_extra} - {e}", "fout")
        win.after(300, check_alles)


    _huidige_misplaatst = {"lijst": []}
    verplaats_knop = _rbtn_nmb(f1, "Verkeerd geplaatste bestanden verplaatsen naar juiste map",
                                verplaats_misplaatste, "#b45309", bold=True)
    verplaats_knop.pack_forget()

    _huidige_dubbel = {"lijst": []}
    verwijder_dubbel_knop = _rbtn_nmb(f1, "Dubbele/verouderde kopieen verwerken",
                                        verwijder_dubbele, RED_C, bold=True)
    verwijder_dubbel_knop.pack_forget()

    _huidige_onbekend = {"lijst": []}
    verwijder_onbekend_knop = _rbtn_nmb(f1, "Onbekende bestanden verwijderen",
                                          verwijder_onbekende, RED_C, bold=True)
    verwijder_onbekend_knop.pack_forget()

    _rbtn_nmb(f1, "Opnieuw controleren", check_alles, BLUE)

    # ════════════════════════════════════════════════════════════
    # TAB 2: OPRUIMEN
    # ════════════════════════════════════════════════════════════
    f2 = gui.Frame(tab_container, bg=BG)
    tabs["Opruimen"] = f2

    gui.Label(f2, text="Bestanden en mappen die niet meer nodig zijn - vink aan en verwijder",
              font=("Segoe UI",9), bg=BG, fg=DIM).pack(pady=(10,6), padx=16, anchor="w")

    sf = gui.Frame(f2, bg=BG)
    sf.pack(fill="both", expand=True, padx=12)
    cv = gui.Canvas(sf, bg=BG, highlightthickness=0)
    sb = gui.Scrollbar(sf, orient="vertical", command=cv.yview)
    cv.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    cv.pack(side="left", fill="both", expand=True)
    inner = gui.Frame(cv, bg=BG)
    cv.create_window((0,0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))

    opruim_vars = {}

    # 9 augustus 2026 (Frans: "als je opruimen gedaan hebt blijft deze rode
    # balk staan, lijkt me niet correct"): de hele itemlijst hieronder werd
    # maar EEN keer opgebouwd, bij het openen van het venster. Na op
    # "Geselecteerde bestanden verwijderen" te klikken werden de bestanden
    # echt verwijderd, maar de vinkjes/statusteksten ("aanwezig") en de
    # rode knop zelf bleven er ongewijzigd bijstaan - alsof er niets gebeurd
    # was. Nu zit alles in een functie die opnieuw aangeroepen kan worden:
    # na het verwijderen (en via een eigen "Opnieuw controleren"-knop,
    # net als tab 1) wordt de lijst vers opgebouwd, zodat net verwijderde
    # items meteen als "niet gevonden" / uitgeschakeld getoond worden.
    def _bouw_opruim_items():
        for w in inner.winfo_children():
            w.destroy()
        opruim_vars.clear()

        # 6 augustus 2026: eigen, losse lijst vervangen door de gedeelde
        # ONNODIGE_BESTANDEN (zie boven in dit bestand) - dit was de directe
        # oorzaak van "Structuurcheck meldt het wel, Opruimen doet er niets
        # mee": deze lijst had zelfs nog oude "_v7"-bestandsnamen uit 12 juli
        # staan, terwijl de infographic al sinds 16 juli helemaal geschrapt is.
        overbodig_items = list(ONNODIGE_BESTANDEN)

        # ArchiefBackup was tot 8 augustus 2026 een hoofdmap genaamd QnapCheck
        # (hernoemd - het oude NAS-apparaat bestaat niet meer, de naam was
        # verwarrend). Beide oude locaties - de vroegere hoofdmap QnapCheck en
        # de nog oudere Zijprojecten\QnapCheck - horen niet meer te bestaan
        # zodra alle bestanden eruit verplaatst zijn. Los opgenomen (niet in
        # overbodig_items) omdat dit hele MAPPEN zijn, geen losse bestanden -
        # zelfde patroon als de __pycache__-mappen hieronder.
        for _oude_naam, _oude_pad in (
            ("qnapcheckold", os.path.join(root_dir, "Zijprojecten", "QnapCheck")),
            ("qnapcheckhoofdmap", os.path.join(root_dir, "QnapCheck")),
        ):
            if os.path.isdir(_oude_pad):
                _resterend = os.listdir(_oude_pad)
                if _resterend:
                    reden = (f"Verouderde map - nog {len(_resterend)} bestand(en) erin, "
                             f"gebruik Structuurcheck's verplaats-knop om ze naar ArchiefBackup te "
                             f"krijgen; daarna is deze map leeg en kan hij hier verwijderd worden")
                else:
                    reden = "Verouderde, lege map - heet nu ArchiefBackup, dit mag weg"
                overbodig_items.append(("__map__", _oude_pad, _oude_naam, reden))

        # __pycache__ mappen dynamisch toevoegen - gedeelde functie, zie boven
        # in dit bestand (6 augustus 2026: was een vaste lijst die geneste
        # mappen zoals Beheer\core\ miste, terwijl Structuurcheck's melding
        # ze wel al toonde - vandaar dat Frans ze met de hand moest opruimen).
        for pycache_pad in _vind_pycache_mappen(root_dir):
            rel = os.path.relpath(pycache_pad, root_dir)
            sleutel = f"cache_{rel.replace(os.sep, '_')}"
            overbodig_items.append(
                ("__pycache__", pycache_pad, sleutel,
                 f"Python cache in {os.path.dirname(rel) or '.'} — veilig te verwijderen"))

        # node_modules (Publicatie) - 6 augustus 2026 (Frans: "map node blijft
        # staan???"): npm-afhankelijkheden voor de oude, vervangen Node.js-
        # versie van Functieoverzicht - niet meer nodig. Nieuw maptype
        # __map_niet_leeg__ i.p.v. __map__: node_modules is NOOIT leeg (dat is
        # juist de bedoeling van zo'n map), __map__'s "moet leeg zijn"-regel
        # zou 'm dus altijd blokkeren.
        _node_modules_pad = os.path.join(root_dir, "Publicatie", "node_modules")
        if os.path.isdir(_node_modules_pad):
            overbodig_items.append(
                ("__map_niet_leeg__", _node_modules_pad, "nodemodules",
                 "npm-afhankelijkheden - niet meer nodig sinds Functieoverzicht "
                 "op Python/PDF draait (kan groot zijn, mag altijd in 1 keer weg)"))

        for map_, bestand, key, reden in overbodig_items:
            if bestand is None:
                gui.Frame(inner, bg=PANEL2, height=1).pack(fill="x", pady=(10,4))
                gui.Label(inner, text=reden, font=("Segoe UI",9,"bold"),
                          bg=BG, fg="#60a5fa").pack(anchor="w", padx=4)
                continue

            if map_ in ("__pycache__", "__map__", "__map_niet_leeg__"):
                pad = bestand  # bestand is hier het volledige pad
                bestaat = os.path.isdir(pad)
                label = os.path.relpath(pad, root_dir)
                # Bij __map__ (hele map verwijderen, niet alleen __pycache__)
                # mag dat ALLEEN als de map leeg is - anders zou een vinkje +
                # verwijderen ook nog niet-verplaatste bestanden meenemen.
                # __map_niet_leeg__ (bijv. node_modules) is bewust een andere
                # tak: zo'n map is per definitie nooit leeg, dus geen restrictie.
                nog_niet_leeg = (map_ == "__map__" and bestaat and os.listdir(pad))
                if nog_niet_leeg:
                    bestaat = False  # forceert uitgeschakeld vinkje hieronder
            else:
                pad = os.path.join(root_dir, map_, bestand)
                bestaat = os.path.exists(pad)
                label = f"{map_}\\{bestand}"
                nog_niet_leeg = False

            var = gui.BooleanVar(master=win, value=bestaat)
            var.set(bestaat)  # expliciet, voor de zekerheid (6 augustus 2026:
                               # Frans meldde aangevinkte items die bij het
                               # verwijderen toch als "niet geselecteerd" golden)
            opruim_vars[key] = (var, pad)

            rij = gui.Frame(inner, bg=BG)
            rij.pack(fill="x", pady=2, padx=4)
            gui.Checkbutton(rij, text=label, variable=var,
                            font=("Segoe UI",9), bg=BG, fg=FG,
                            selectcolor=PANEL2, activebackground=BG,
                            state="normal" if bestaat else "disabled",
                            anchor="w").pack(side="left")
            if nog_niet_leeg:
                statustekst, statuskleur = "nog niet leeg", WARN_C
            elif bestaat:
                statustekst, statuskleur = "aanwezig", ERR_C
            else:
                statustekst, statuskleur = "niet gevonden", DIM
            gui.Label(rij, text=statustekst, font=("Segoe UI",8), bg=BG,
                      fg=statuskleur).pack(side="right")
            gui.Label(inner, text=f"    {reden}",
                      font=("Segoe UI",8), bg=BG, fg=DIM).pack(anchor="w", padx=4)

    _bouw_opruim_items()

    opruim_log = scrolledtext.ScrolledText(
        f2, font=("Consolas",9), bg=PANEL, fg=FG,
        relief="flat", height=6, wrap="word")
    opruim_log.pack(fill="x", padx=12, pady=(8,4))
    opruim_log.tag_config("ok",   foreground=OK_C)
    opruim_log.tag_config("fout", foreground=ERR_C)

    def opruimen():
        aangevinkt = [(k, p) for k, (v, p) in opruim_vars.items() if v.get()]
        te_doen = [(k, p) for k, p in aangevinkt
                   if os.path.exists(p) or os.path.isdir(p)]
        if not te_doen:
            if not aangevinkt:
                messagebox.showinfo("Opruimen",
                    f"Niets aangevinkt (van de {len(opruim_vars)} items in de lijst).\n\n"
                    "Zet eerst een vinkje bij wat je wilt verwijderen.")
            else:
                messagebox.showinfo("Opruimen",
                    f"{len(aangevinkt)} item(s) waren aangevinkt, maar geen van "
                    "allemaal bestaat nog op schijf - waarschijnlijk al eerder "
                    "verwijderd. Klik op 'Opnieuw controleren'.")
            return
        namen = "\n".join(f"  - {os.path.basename(p)}" for _,p in te_doen)
        if not messagebox.askyesno("Bevestigen",
                f"{len(te_doen)} item(s) verwijderen?\n\n{namen}"):
            return
        opruim_log.config(state="normal")
        opruim_log.delete("1.0","end")
        for key, pad in te_doen:
            try:
                if os.path.isdir(pad): shutil.rmtree(pad)
                else: os.remove(pad)
                opruim_log.insert("end", f"v  {os.path.basename(pad)}\n", "ok")
            except Exception as e:
                opruim_log.insert("end", f"x  {os.path.basename(pad)} - {e}\n", "fout")
        opruim_log.insert("end","Klaar!\n","ok")
        opruim_log.config(state="disabled")
        # 9 augustus 2026: itemlijst hierboven ook verversen, niet alleen
        # tab 1 (check_alles) - anders bleven net verwijderde items hier
        # aangevinkt en "aanwezig" staan, en de rode knop leek dus nog
        # iets te doen te hebben terwijl alles al weg was.
        win.after(500, _bouw_opruim_items)
        win.after(500, check_alles)

    _rbtn_nmb(f2, "Geselecteerde bestanden verwijderen", opruimen, RED_C, bold=True)
    _rbtn_nmb(f2, "Opnieuw controleren", _bouw_opruim_items, BLUE)

    # Start - open op gevraagd tabblad indien meegegeven via commandoregel.
    # Herstel & Acties-tab is 16 juli 2026 opgeheven: Handleiding/Scripts
    # uploaden/Distribueren zijn verhuisd naar Onderhoud, Suite
    # testen/Diagnose/Log Bestanden Bekijken naar het nieuwe
    # pinas_controle_beheer.pyw. Alleen Structuurcheck en Opruimen resten hier.
    _start_tab = "Structuurcheck"
    if len(sys.argv) > 1 and sys.argv[1] in tabs:
        _start_tab = sys.argv[1]
    toon_tab(_start_tab)
    win.after(300, check_alles)
    win.mainloop()

if __name__ == "__main__":
    main()
