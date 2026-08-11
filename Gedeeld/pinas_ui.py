"""
Pi NAS Suite - Gedeelde UI-bouwstenen
Importeer met: from pinas_ui import *  (of losse namen zoals hieronder)

Deze module levert de vier gedeelde bouwstenen voor de hele suite:
  1. maak_header()        - vaste kop met terug-knop en titel
  2. maak_sectie()         - vaste sectie-omkadering
  3. maak_status_label()   - een vaste manier om status te tonen
  4. maak_knop()           - knoppenhierarchie: primair / secundair / destructief

Kleuren komen altijd uit pinas_theme (licht of donker, afhankelijk van
picontrol.cfg) - pinas_ui kiest zelf geen kleuren en werkt daardoor
automatisch mee met beide thema's.

RoundedButton is hier de EENMALIGE definitie voor de hele suite. Deze
vervangt de losse kopieen die eerder in Pi_NAS_Menu.pyw (als RoundedButton)
en NAS_Map_Beheer.pyw (als _rbtn_nmb) stonden - functioneel identiek,
nu op een plek zodat een wijziging niet meer op twee plekken hoeft.
"""

import tkinter as tk
import sys as _sys
import os as _os

_gedeeld = _os.path.dirname(_os.path.abspath(__file__))
if _gedeeld not in _sys.path:
    _sys.path.insert(0, _gedeeld)

from pinas_theme import BG, PANEL, PANEL2, FG, DIM, OK_C, ERR_C, WARN, ACCENT, DESTRUCTIEF


# ---------------------------------------------------------------------------
# Logo (toegevoegd 17 juli 2026, ontwerp van Frans) - klein header-formaat
# staat in Beheer/assets/, dus vanuit Gedeeld/ een map omhoog + Beheer/assets/.
# pinas_ui.py zelf staat altijd in Gedeeld/, maar wordt vanuit heel
# verschillende mappen geimporteerd (Beheer/, Addons/, Sync/, ...) - daarom
# hier meerdere kandidaat-paden proberen i.p.v. 1 vast pad aannemen.
# ---------------------------------------------------------------------------
def _logo_pad():
    hier = _os.path.dirname(_os.path.abspath(__file__))
    kandidaten = [
        _os.path.join(hier, "..", "Beheer", "assets", "pinas_logo_header.png"),
        _os.path.join("C:\\", "PiNAS", "Beheer", "assets", "pinas_logo_header.png"),
    ]
    for k in kandidaten:
        if _os.path.exists(k):
            return k
    return None


# ---------------------------------------------------------------------------
# Afgeronde knop (Canvas-gebaseerd)
# ---------------------------------------------------------------------------
class RoundedButton(tk.Canvas):
    """Knop met afgeronde hoeken - uniform voor de hele Pi NAS Suite."""

    def __init__(self, parent, text, command, bg, fg=None, font=None,
                 radius=8, pady=8, padx=12, **kw):
        self._bg = bg
        self._fg = fg or "#ffffff"
        self._font = font or ("Segoe UI", 10)
        self._radius = radius
        self._pady = pady
        self._padx = padx
        self._cmd = command
        self._text = text
        self._state = "normal"

        tmp = tk.Label(parent, text=text, font=self._font)
        th = tmp.winfo_reqheight()
        tmp.destroy()
        h = th + pady * 2

        self._min_h = max(h, 32)
        super().__init__(parent, height=self._min_h, bg=parent.cget("bg"),
                          highlightthickness=0, bd=0, **kw)
        self.pack(fill="x", pady=2)

        self.bind("<Configure>", self._redraw)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))
        self._hovered = False

    def _lighten(self, hex_c, amt=30):
        h = hex_c.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return "#%02x%02x%02x" % (min(r + amt, 255), min(g + amt, 255), min(b + amt, 255))

    def _draw(self, w, h, bg):
        self.delete("all")
        r = self._radius
        self.create_arc(0, 0, 2 * r, 2 * r, start=90, extent=90, fill=bg, outline=bg)
        self.create_arc(w - 2 * r, 0, w, 2 * r, start=0, extent=90, fill=bg, outline=bg)
        self.create_arc(0, h - 2 * r, 2 * r, h, start=180, extent=90, fill=bg, outline=bg)
        self.create_arc(w - 2 * r, h - 2 * r, w, h, start=270, extent=90, fill=bg, outline=bg)
        self.create_rectangle(r, 0, w - r, h, fill=bg, outline=bg)
        self.create_rectangle(0, r, w, h - r, fill=bg, outline=bg)
        self.create_text(self._padx + r, h // 2, text=self._text,
                          font=self._font, fill=self._fg, anchor="w")

    def _redraw(self, e=None):
        w = self.winfo_width() or 200
        h = self.winfo_height() or self._min_h
        if h < 10:
            h = self._min_h
        bg = self._lighten(self._bg) if self._hovered else self._bg
        if self._state == "disabled":
            bg = PANEL2
        self._draw(w, h, bg)

    def _hover(self, on):
        if self._state == "disabled":
            return
        self._hovered = on
        self._redraw()

    def _on_click(self, e=None):
        if self._state == "disabled":
            return
        if self._cmd:
            self._cmd()

    def config(self, **kw):
        if "state" in kw:
            self._state = kw["state"]
            self._redraw()
        if "text" in kw:
            self._text = kw["text"]
            self._redraw()
        if "bg" in kw:
            self._bg = kw["bg"]
            self._redraw()

    def pack(self, **kw):
        super().pack(**kw)
        self.after(50, self._redraw)
        self.after(200, self._redraw)


# ---------------------------------------------------------------------------
# Knoppenhierarchie: primair / secundair / destructief
# ---------------------------------------------------------------------------
def maak_knop(parent, tekst, actie, stijl="primair", bold=False, kleur=None):
    """Maakt een RoundedButton in een van drie vaste stijlen.

    primair     - hoofdactie van het scherm: gevulde accentkleur, witte tekst
    secundair   - neutrale paneelkleur, gewone tekstkleur
    destructief - warme oranje vulling, donkere tekst; voor risicovolle acties
    (bewust een ANDERE tint dan ERR_C, want ERR_C betekent overal
    "fout/ontbreekt" - een destructieve knop is geen foutmelding, en zou
    anders dezelfde kleur als "iets is stuk" krijgen)

    kleur: optionele override voor de "primair"-accentkleur (16 juli 2026).
    Elk scherm gebruikt standaard de algemene ACCENT (blauw), maar Backup
    Beheer/Addons Beheer geven hier hun eigen productkleur door
    (ACCENT_PIBACKUP/ACCENT_PIADDONS) zodat het scherm in dezelfde "sfeer"
    blijft als de knop waarmee je het opende op het hoofdmenu - i.p.v. dat
    alles automatisch terugvalt op hetzelfde blauw.
    """
    kleuren = {
        "primair": (kleur or ACCENT, "#ffffff"),
        "secundair": (PANEL2, FG),
        "destructief": (DESTRUCTIEF, "#3d2604"),
    }
    bg, fg = kleuren.get(stijl, kleuren["secundair"])
    font = ("Segoe UI", 9, "bold") if bold else ("Segoe UI", 9)
    return RoundedButton(parent, text=tekst, command=actie, bg=bg, fg=fg, font=font)


# ---------------------------------------------------------------------------
# Vaste kop voor elk scherm
# ---------------------------------------------------------------------------
def maak_header(venster, titel, terug_actie=None, subtekst=None, help_hoofdstukken=None, kleur=None):
    """Bouwt de vaste kopbalk: [terug-knop] + titel (+ optionele subtekst).

    terug_actie: functie zonder argumenten die het venster afsluit en het
    hoofdmenu opent. Blijft weg als terug_actie None is (bijvoorbeeld in
    het hoofdmenu zelf).

    help_hoofdstukken: optionele lijst van (kop, tekst) tuples - als
    meegegeven verschijnt rechts in de kopbalk een "?  Help"-knopje dat
    toon_help_venster() opent (zie hieronder). Ontstaan in Backup Beheer
    (16 juli 2026), hier gedeeld zodat elk scherm dit kan gebruiken.

    kleur: optionele override voor de titelkleur (16 juli 2026) - zelfde
    idee als bij maak_knop(): laat een scherm zijn eigen productkleur
    doorgeven i.p.v. altijd de algemene ACCENT (blauw), zodat titel en
    primaire knoppen samen dezelfde "sfeer" vormen.
    """
    hdr = tk.Frame(venster, bg=BG)
    hdr.pack(fill="x", padx=16, pady=(14, 6))

    rij = tk.Frame(hdr, bg=BG)
    rij.pack(fill="x")

    if terug_actie is not None:
        terug = RoundedButton(rij, text="<  Hoofdmenu", command=terug_actie,
                               bg=PANEL2, fg=FG, font=("Segoe UI", 9))
        terug.pack(side="left", padx=(0, 12))

    logo_pad = _logo_pad()
    if logo_pad:
        try:
            logo_img = tk.PhotoImage(file=logo_pad)
            # Referentie vasthouden op het frame zelf - anders ruimt Tkinter's
            # garbage collection de PhotoImage op en verdwijnt het logo weer
            # zodra deze functie klaar is (geen andere Python-referentie over).
            hdr.logo_img = logo_img
            tk.Label(rij, image=logo_img, bg=BG).pack(side="left", padx=(0, 8))
        except Exception:
            pass

    tk.Label(rij, text=titel, font=("Segoe UI", 14, "bold"),
              bg=BG, fg=(kleur or ACCENT)).pack(side="left")

    if help_hoofdstukken:
        help_knop = RoundedButton(
            rij, text="?  Help", bg=PANEL2, fg=FG, font=("Segoe UI", 9),
            command=lambda: toon_help_venster(venster, titel, help_hoofdstukken))
        help_knop.pack(side="right")

    if subtekst:
        tk.Label(hdr, text=subtekst, font=("Segoe UI", 9),
                  bg=BG, fg=DIM, anchor="w").pack(fill="x", pady=(2, 0))

    tk.Frame(venster, bg=PANEL2, height=1).pack(fill="x")
    # 5 augustus 2026 (Frans: extra knoppen zoals Help/Vernieuwen die een
    # aanroeper zelf toevoegt, belandden onder de subtekst i.p.v. op
    # dezelfde regel als de titel) - rij (de titelregel zelf) ook
    # toegankelijk maken als hdr.rij, zodat aanroepers daar extra knoppen
    # in kunnen pakken i.p.v. per ongeluk in de buitenste hdr-frame (die
    # de titelregel EN de subtekst-regel eronder bevat).
    hdr.rij = rij
    return hdr


# ---------------------------------------------------------------------------
# Sectie-omkadering
# ---------------------------------------------------------------------------
def maak_sectie(parent, titel=None):
    """Geeft een frame terug met vaste paneelkleur en binnenmarge,
    optioneel met een klein kopje linksboven."""
    buiten = tk.Frame(parent, bg=BG)
    buiten.pack(fill="x", padx=16, pady=6)

    kader = tk.Frame(buiten, bg=PANEL)
    kader.pack(fill="x")

    binnen = tk.Frame(kader, bg=PANEL)
    binnen.pack(fill="both", expand=True, padx=14, pady=12)

    if titel:
        tk.Label(binnen, text=titel, font=("Segoe UI", 9, "bold"),
                  bg=PANEL, fg=DIM, anchor="w").pack(fill="x", pady=(0, 8))

    return binnen


# ---------------------------------------------------------------------------
# Status-indicator: EEN vorm voor de hele suite
# ---------------------------------------------------------------------------
_STATUS_KLEUR = {
    "ok": OK_C,
    "waarschuwing": WARN,
    "fout": ERR_C,
    "onbekend": DIM,
}

_STATUS_TEKST = {
    "ok": "in orde",
    "waarschuwing": "let op",
    "fout": "fout",
    "onbekend": "onbekend",
}

_BOL = "\u25cf"  # gevulde bol - zelfde teken als al gebruikt in NAS Map Beheer


def maak_status_label(parent, status="onbekend", tekst=None):
    """Bolletje + tekst, altijd in dezelfde volgorde en stijl.
    status: "ok" / "waarschuwing" / "fout" / "onbekend" """
    kleur = _STATUS_KLEUR.get(status, DIM)
    label_tekst = tekst or _STATUS_TEKST.get(status, status)
    achtergrond = parent.cget("bg")

    rij = tk.Frame(parent, bg=achtergrond)
    tk.Label(rij, text=_BOL, font=("Segoe UI", 9), bg=achtergrond,
              fg=kleur).pack(side="left", padx=(0, 6))
    tk.Label(rij, text=label_tekst, font=("Segoe UI", 9), bg=achtergrond,
              fg=kleur).pack(side="left")
    return rij


def maak_status_legenda(parent):
    """De vaste legenda: in orde / let op / fout / onbekend, in die volgorde."""
    achtergrond = parent.cget("bg")
    rij = tk.Frame(parent, bg=achtergrond)
    for status in ["ok", "waarschuwing", "fout", "onbekend"]:
        item = maak_status_label(rij, status=status)
        item.pack(side="left", padx=(0, 16))
    return rij


# ---------------------------------------------------------------------------
# Help-venster: EEN vorm voor de hele suite (16 juli 2026)
# ---------------------------------------------------------------------------
# Ontstaan uit Backup Beheer, waar het niet meer duidelijk was wat elke
# knop precies deed ("over een half jaar weet ik dit ook niet meer"). Hier
# als gedeelde bouwsteen neergezet zodat andere schermen dit later ook
# kunnen gebruiken zonder het opnieuw te bouwen.
def toon_help_venster(ouder, titel, hoofdstukken):
    """Opent een los, schuifbaar tekstvenster met uitleg per functie.

    hoofdstukken: lijst van (kop, tekst) tuples. Elke kop wordt vetgedrukt
    getoond, gevolgd door de bijbehorende uitleg in gewone taal.
    """
    from tkinter import scrolledtext

    win = tk.Toplevel(ouder)
    win.title(f"Help - {titel}")
    win.configure(bg=BG)
    win.geometry("620x560")
    win.minsize(480, 400)

    tk.Label(win, text=f"Help - {titel}", font=("Segoe UI", 13, "bold"),
              bg=BG, fg=ACCENT).pack(anchor="w", padx=16, pady=(14, 4))
    tk.Frame(win, bg=PANEL2, height=1).pack(fill="x", padx=16)

    tekstvak = scrolledtext.ScrolledText(
        win, font=("Segoe UI", 10), bg=PANEL, fg=FG,
        relief="flat", wrap="word", padx=12, pady=10)
    tekstvak.pack(fill="both", expand=True, padx=16, pady=12)

    tekstvak.tag_config("kop", font=("Segoe UI", 11, "bold"), foreground=ACCENT,
                         spacing1=6, spacing3=6)
    tekstvak.tag_config("tekst", font=("Segoe UI", 10), foreground=FG, spacing3=14)

    for kop, tekst in hoofdstukken:
        tekstvak.insert("end", kop + "\n", "kop")
        tekstvak.insert("end", tekst.strip() + "\n", "tekst")

    tekstvak.config(state="disabled")

    sluit = RoundedButton(win, text="Sluiten", command=win.destroy,
                           bg=PANEL2, fg=FG, font=("Segoe UI", 9))
    sluit.pack(padx=16, pady=(0, 14), anchor="e")

    win.transient(ouder)
    win.focus_set()
    return win


def maak_help_knop(parent, ouder, titel, hoofdstukken):
    """Klein rond '?'-knopje dat toon_help_venster opent - te gebruiken
    naast de titel in maak_header() of ergens los in een scherm."""
    return RoundedButton(parent, text="?  Help", bg=PANEL2, fg=FG,
                          font=("Segoe UI", 9),
                          command=lambda: toon_help_venster(ouder, titel, hoofdstukken))
