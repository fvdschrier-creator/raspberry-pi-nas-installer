#!/usr/bin/env python3
"""
Pi NAS Suite - Kleuren kiezer
Dubbelklik om te starten, of via Pi NAS Menu -> Onderhoud -> Weergave ->
"Kleuren kiezen".

Gebruiksvriendelijk alternatief voor het handmatig bewerken van
Gedeeld/pinas_theme.py: per veld een handvol vooraf gekozen kleurstalen
(geen vrije kleurenkiezer) zodat je nooit per ongeluk weer richting
donker marineblauw/camouflage/te-veel-paars terechtkomt - dat was
precies waar de suite eerder last van had.

Licht en donker zijn twee losse tabbladen: je stelt ze onafhankelijk in.
Bij "Opslaan" wordt alleen Gedeeld/pinas_theme.py bijgewerkt (de ENIGE
bron van waarheid, zie de docstring daar) - de rest van het bestand
(docstring, functies, oude naam-aliassen) blijft ongemoeid. De oude
naam-aliassen (BLUE/ACCENT/GREEN_C/GREEN/RED_C/RED/MAGENTA) worden
automatisch afgeleid van de bijbehorende accentkleur/ERR_C, zodat ze
nooit meer los raken - dat losraken was eerder dit jaar de kern van een
hele reeks kleur-mismatches.
"""
import os
import sys
import re


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


_gedeeld = os.path.join(_nas_root(), "Gedeeld")
if os.path.isdir(_gedeeld) and _gedeeld not in sys.path:
    sys.path.insert(0, _gedeeld)

from pinas_theme import (BG, PANEL, PANEL2, FG, DIM, OK_C, ERR_C, WARN, ACCENT,
                          DESTRUCTIEF, leesbare_tekstkleur)
import pinas_theme as _pt

# Vaste tekstkleur voor destructieve knoppen (zie maak_knop() in pinas_ui.py -
# stijl="destructief" gebruikt BEWUST geen leesbare_tekstkleur(), zodat de
# mini-preview hieronder exact laat zien wat de echte suite doet).
VAST_DESTRUCTIEF_TEKST = "#3d2604"


THEMA_PAD = os.path.join(_gedeeld, "pinas_theme.py")

# ---------------------------------------------------------------------------
# Welke velden zijn te kiezen, waar in de suite zie je ze terug, en welke
# kleurstalen worden aangeboden per thema. Bewust GEEN vrije kleurenkiezer -
# elke staal hieronder is zorgvuldig gekozen binnen dezelfde "zacht
# zakelijk"-familie als het huidige palet.
# ---------------------------------------------------------------------------
# Gedeeld palet van 15 frisse, verzadigde kleuren - gebruikt voor alle
# identiteits-/betekenisvelden hieronder, telkens met de eigen kleurfamilie
# vooraan. Ontstaan naar aanleiding van feedback van Frans: 6 stalen die
# allemaal een tint van dezelfde kleur zijn (bijv. 6x paars/rose bij
# Venster-branding) voelen als GEEN keuze - "een beetje meer of minder
# paars is voor mij geen verschil". Nu per veld 1 eigen kleurfamilie + de
# andere 14, gelijkmatig verspreid over het kleurenwiel (elke 24 graden),
# nog steeds "zacht zakelijk" (geen navy/camouflage/neon).
#
# 16 augustus 2026: van 10 naar 15 kleuren, en het losse met-de-hand-
# gekozen palet vervangen door een programmatisch afgeleid palet - naar
# aanleiding van Frans' vraag na het kleurenoverzicht ("een vervolg
# keuzelijst met 15 frisse kleuren"). Elke kleur is uitgerekend zodat hij
# (net als OK_C hiervoor) een contrast van minimaal 3.0:1 haalt tegen ZOWEL
# de achtergrond (BG) als het paneel (PANEL) van dat thema - dus elke kleur
# is niet alleen bruikbaar als knopachtergrond, maar ook direct als
# tekstkleur. Verzadiging vast op 0.85 (HSL) voor een consistent "fris"
# resultaat - geen enkele kleur is vager/valer dan een andere.
# Puur geel is bewust NIET als eigen slot opgenomen: in het lichte thema
# haalt zuiver geel nooit 3:1 contrast zonder zo donker te worden dat het
# alsnog als goud/olijf oogt (precies wat "amber"/"olijfgroen" hieronder
# al zijn) - dat zou de twee thema's uit elkaar laten lopen. Voor de
# statusvelden (OK_C/ERR_C/WARN/YELLOW) komt er in het donkere thema WEL
# een aparte "wit"-optie bij (zie GROEPEN hieronder) - dat was Frans'
# expliciete verzoek en wit werkt alleen in het donkere thema goed genoeg.
MASTER_LICHT = {
    "rood": "#d21121", "terracotta": "#b6440f", "amber": "#86630b",
    "olijfgroen": "#636f09", "grasgroen": "#3e760a", "smaragd": "#137b0a",
    "bosgroen": "#0a7b2e", "turkoois": "#0a7859", "cyaan": "#0b7482",
    "azuur": "#1068c6", "blauw": "#2b3bee", "indigo": "#682bee",
    "paars": "#a712e2", "fuchsia": "#bd0fa8", "roze": "#cb106b",
}
MASTER_DONKER = {
    "rood": "#f25a67", "terracotta": "#ed6324", "amber": "#b6860f",
    "olijfgroen": "#87970c", "grasgroen": "#54a00d", "smaragd": "#1aa50d",
    "bosgroen": "#0da53d", "turkoois": "#0da077", "cyaan": "#0e9caf",
    "azuur": "#3790ef", "blauw": "#7983f4", "indigo": "#9e76f4",
    "paars": "#c85ff2", "fuchsia": "#ef3edb", "roze": "#f1509e",
}

_MASTER_VOLGORDE = ["rood", "terracotta", "amber", "olijfgroen", "grasgroen",
                     "smaragd", "bosgroen", "turkoois", "cyaan", "azuur",
                     "blauw", "indigo", "paars", "fuchsia", "roze"]


def _master(thema, eigen_eerst, plus_wit=False):
    """Geeft de 15 kleuren terug, met 'eigen_eerst' vooraan. plus_wit=True
    voegt (alleen zinvol in het donkere thema) wit toe als 16e, extra
    staal - voor statusvelden waar Frans dat expliciet vroeg."""
    m = MASTER_LICHT if thema == "licht" else MASTER_DONKER
    volgorde = [eigen_eerst] + [k for k in _MASTER_VOLGORDE if k != eigen_eerst]
    stalen = [m[k] for k in volgorde]
    if plus_wit:
        stalen.append("#ffffff")
    return stalen


GROEPEN = [
    ("Identiteit / accentkleuren", [
        ("ACCENT_PINAS", "Verbinden",
         "Verbinden op het hoofdmenu (SSH/TigerVNC/WinSCP), en de algemene "
         "Status & Details-schermen. Sinds 13 augustus 2026 NIET meer gedeeld "
         "met Beheer - dat heeft nu zijn eigen kleur (ACCENT_PIBEHEER hieronder).",
         _master("licht", "cyaan"), _master("donker", "cyaan")),
        ("ACCENT_PIBACKUP", "Backup Beheer",
         "De hoofdmenuknop zelf EN het hele venster erachter: Synchronisatie, "
         "PC Image Backup, Archief Backup Bewaking, Systeem-image maken, "
         "Backup-HDD herstellen.",
         _master("licht", "azuur"), _master("donker", "azuur")),
        ("ACCENT_PIADDONS", "Addons Beheer",
         "De hoofdmenuknop zelf EN het hele venster erachter: Nextcloud, "
         "Pi-hole, ZeroTier, Vaultwarden.",
         _master("licht", "amber"), _master("donker", "amber")),
        ("ACCENT_PIBEHEER", "Beheer",
         "NIEUW (13 augustus 2026). De hoofdmenuknop 'Beheer' EN de 3 "
         "schermen erachter: Installatie & Herstel, Controles (en "
         "Structuurcheck & Opruimen erachter), Onderhoud. Elk van die 3 "
         "knoppen/schermen krijgt automatisch een eigen, iets lichtere tint "
         "van DEZE kleur - dat stel je hier niet apart in, dat wordt bij het "
         "opstarten zelf berekend (zie tint() in pinas_theme.py).",
         _master("licht", "roze"), _master("donker", "roze")),
        ("ACCENT_PICONTROL", "Venster-branding (Pi NAS Menu)",
         "Alleen de titelbalk van het Pi NAS Menu-hoofdvenster zelf - bewust "
         "NIET gebruikt voor gewone knoppen (dat gaf eerder 3x identiek "
         "paars naast elkaar).",
         _master("licht", "indigo"), _master("donker", "indigo")),
    ]),
    ("Vensters & tekst", [
        ("BG", "Achtergrond",
         "Achtergrondkleur van alle vensters in de hele suite.",
         ["#eef2f6", "#f4f6f9", "#e9edf2", "#f0f3f7", "#eceff3", "#e6ebf0"],
         ["#232a33", "#1c232b", "#2a323c", "#1a2129", "#262e38", "#303945"]),
        ("PANEL", "Paneel",
         "Achtergrond van paneel-/sectievlakken binnen een venster.",
         ["#dde5ed", "#d7e0e9", "#e2e8ee", "#d3dde6", "#dae2ea", "#cfd9e2"],
         ["#2b333d", "#313a45", "#262e37", "#37414d", "#2e3742", "#222932"]),
        ("PANEL2", "Contrastpaneel",
         "Iets sterker contrast dan Paneel - o.a. niet-actieve tabbladen "
         "(bijv. in Structuurcheck & Opruimen).",
         ["#cbd8e3", "#c3d2df", "#d0dce6", "#bed0dd", "#c8d6e1", "#b9cbd9"],
         ["#33404c", "#3a4854", "#2e3a45", "#414f5c", "#384552", "#29343e"]),
        ("FG", "Tekst",
         "Standaard tekstkleur door de hele suite.",
         ["#232a33", "#1c222a", "#2a323c", "#1a1f26", "#262e38", "#333c47"],
         ["#eef2f6", "#f4f6f9", "#e6ebf0", "#f0f3f7", "#dfe5eb", "#f7f9fb"]),
        ("DIM", "Gedimde tekst",
         "Secundaire tekst: subtitels, uitleg-regels.",
         ["#5b6b7a", "#647585", "#52616f", "#6d7d8c", "#4d5c6a", "#748496"],
         ["#9aa8b5", "#8fa0ad", "#a5b2be", "#85949f", "#b0bcc7", "#7c8c99"]),
    ]),
    ("Status & waarschuwing", [
        # 15-16 augustus 2026: dit veld stond hiervoor vast op groentinten
        # ("blijft bewust in de groene familie") - Frans: "zou mooi zijn als
        # er ook uit een andere kleur dan groen gekozen kan worden, deze is
        # steeds niet zo contrastrijk". Terecht: uitgerekend bleken ALLE
        # oude groentinten in het LICHTE thema onder de 3:1-ondergrens te
        # zitten tegen het paneel waar de statustekst op staat. Nu net als
        # de identiteitsvelden hierboven het gedeelde 15-kleurenpalet (elke
        # kleur is al gecontroleerd op contrast tegen zowel BG als PANEL),
        # in het donkere thema aangevuld met wit (Frans: "ik zag nergens
        # geel of wit" - wit werkt alleen in het donkere thema goed genoeg,
        # zie toelichting bij MASTER_LICHT/MASTER_DONKER hierboven).
        ("OK_C", "In orde (groen, of kies zelf)",
         "Statusteksten/-bolletjes die 'in orde' betekenen (groene vinkjes, "
         "'Alles OK', 'Pi bereikbaar'). Groen staat vooraan als voor de hand "
         "liggende keuze, maar je kunt hier net als bij de andere velden ook "
         "een heel andere kleur pakken als groen voor jou niet contrastrijk "
         "genoeg oogt.",
         _master("licht", "bosgroen"), _master("donker", "bosgroen", plus_wit=True)),
        ("ERR_C", "Fout (rood)",
         "Statusteksten/-bolletjes die een fout betekenen (rode kruisjes, "
         "foutmeldingen).",
         _master("licht", "rood"), _master("donker", "rood", plus_wit=True)),
        ("WARN", "Waarschuwing / herstel (amber)",
         "Waarschuwings-/herstelknoppen - bijv. LanMan-fix, de 'Schijven "
         "verbinden'-banner.",
         _master("licht", "amber"), _master("donker", "amber", plus_wit=True)),
        ("YELLOW", "Wisselend (geel)",
         "Losse waarschuwingstekst, bijv. 'Verbinding wisselend'.",
         _master("licht", "amber"), _master("donker", "amber", plus_wit=True)),
        ("DESTRUCTIEF", "Risicovol (terracotta)",
         "Risicovolle acties - Pi NAS herstarten, Systeem-image maken, "
         "Backup-HDD controleren/herstellen.",
         _master("licht", "terracotta"), _master("donker", "terracotta")),
    ]),
]

# Oude naam-aliassen: worden bij Opslaan automatisch afgeleid van hun
# "echte" veld hierboven, zodat ze nooit meer los kunnen raken (dat was
# eerder dit jaar de kern van een hele reeks kleur-mismatches).
ALIAS_AFGELEID = {
    "BLUE": "ACCENT_PINAS", "ACCENT": "ACCENT_PINAS",
    "GREEN_C": "ACCENT_PIBACKUP", "GREEN": "ACCENT_PIBACKUP",
    "RED_C": "ERR_C", "RED": "ERR_C",
    "MAGENTA": "ACCENT_PICONTROL",
}


def _alle_velden():
    for _, velden in GROEPEN:
        for v in velden:
            yield v


# Snelle opzoektabel key -> (label, beschrijving, presets_licht, presets_donker),
# gebruikt door de klikbare mini-preview (zie _open_kleurkeuze() in main())
# om bij een klik meteen de juiste vervolg-keuzelijst te tonen.
VELD_BIJ_KEY = {key: (label, beschrijving, pl, pd)
                for key, label, beschrijving, pl, pd in _alle_velden()}


def _huidige_waarden(thema):
    """Leest de huidige waarden rechtstreeks uit pinas_theme (de bron)."""
    bron = _pt._DONKER if thema == "donker" else _pt._LICHT
    return {key: bron.get(key, "#888888") for key, *_ in _alle_velden()}


def _vervang_dict_blok(tekst, dict_naam, waarden):
    """Vervangt KEY=\"...\" paren binnen het dict(...)-blok van dict_naam.
    Laat al het andere (docstring, commentaar, overige velden) met rust."""
    patroon_blok = re.compile(
        r"(" + re.escape(dict_naam) + r"\s*=\s*dict\(\n)(.*?)(\n\)\n)",
        re.DOTALL)
    m = patroon_blok.search(tekst)
    if not m:
        raise ValueError(f"{dict_naam} blok niet gevonden in pinas_theme.py")
    kop, inhoud, staart = m.group(1), m.group(2), m.group(3)
    nieuwe_inhoud = inhoud
    for key, waarde in waarden.items():
        key_patroon = re.compile(r"(\b" + re.escape(key) + r"\s*=\s*)\"([^\"]*)\"")
        nieuwe_inhoud, _n = key_patroon.subn(
            lambda mm, w=waarde: mm.group(1) + '"' + w + '"',
            nieuwe_inhoud, count=1)
    return tekst[:m.start()] + kop + nieuwe_inhoud + staart + tekst[m.end():]


def opslaan(licht_waarden, donker_waarden):
    """Schrijft beide thema's in een keer weg naar pinas_theme.py."""
    with open(THEMA_PAD, "r", encoding="utf-8") as f:
        tekst = f.read()

    for thema, waarden in [("_LICHT", dict(licht_waarden)),
                            ("_DONKER", dict(donker_waarden))]:
        # Afgeleide alias-velden meesturen zodat ze nooit los raken.
        for alias, bron_key in ALIAS_AFGELEID.items():
            waarden[alias] = waarden[bron_key]
        tekst = _vervang_dict_blok(tekst, thema, waarden)

    with open(THEMA_PAD, "w", encoding="utf-8") as f:
        f.write(tekst)


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
def main():
    import tkinter as tk
    from tkinter import messagebox
    sys.path.insert(0, _gedeeld)
    from pinas_ui import RoundedButton, maak_knop, maak_header

    win = tk.Tk()
    win.title("Kleuren kiezen - Pi NAS Suite")
    win.configure(bg=BG)
    win.geometry("860x780")
    win.minsize(720, 600)

    state = {"licht": _huidige_waarden("licht"), "donker": _huidige_waarden("donker")}
    huidig_tab = {"naam": "licht"}

    # ── Header ───────────────────────────────────────────────────────────
    # 5 augustus 2026 (Frans: alle headers consistent - icoon, Help-knop
    # overal) - omgezet naar de gedeelde maak_header() i.p.v. eigen, losse
    # code zonder icoon/Help. Eigen, nieuwe Help-inhoud (apart proces).
    KLEUREN_HELP = [
        ("Kleuren kiezen", "Klik een kleurstaal aan per veld om het te wijzigen. Licht en donker "
         "staan los van elkaar - wissel via de tabbladen. Niets wordt opgeslagen tot je op "
         "'Opslaan' klikt."),
        ("Herladen vanaf schijf", "Verwerpt eventuele niet-opgeslagen wijzigingen en laadt de "
         "kleuren opnieuw zoals ze nu in pinas_theme.py staan."),
        ("Opslaan", "Schrijft de gekozen kleuren terug naar pinas_theme.py - geldt daarna voor "
         "de hele suite. Een herstart van openstaande vensters is nodig om het overal te zien."),
    ]
    hdr = maak_header(win, "Kleuren kiezen", help_hoofdstukken=KLEUREN_HELP)
    sluit_knop = maak_knop(hdr.rij, "Sluiten", win.destroy, stijl="secundair")
    sluit_knop.pack_forget()
    sluit_knop.pack(side="right")
    tk.Label(win, text="Klik een kleurstaal aan per veld. Licht en donker staan los van "
                        "elkaar - wissel via de tabbladen hieronder. Niets wordt "
                        "opgeslagen tot je op 'Opslaan' klikt.",
              font=("Segoe UI", 9), bg=BG, fg=DIM, wraplength=800,
              justify="left").pack(fill="x", padx=16, pady=(0, 6))
    tk.Frame(win, bg=PANEL2, height=1).pack(fill="x", padx=16)

    # ── Tabbladen ────────────────────────────────────────────────────────
    tab_frame = tk.Frame(win, bg=BG)
    tab_frame.pack(fill="x", padx=16, pady=(8, 0))
    tab_btns = {}

    def wissel_tab(naam):
        huidig_tab["naam"] = naam
        for n, b in tab_btns.items():
            b.config(bg=ACCENT if n == naam else PANEL2)
        bouw_inhoud()

    for naam in ["licht", "donker"]:
        b = RoundedButton(tab_frame, text=naam.capitalize(),
                           command=lambda n=naam: wissel_tab(n),
                           bg=(ACCENT if naam == "licht" else PANEL2), fg="#ffffff",
                           font=("Segoe UI", 9, "bold"))
        b.pack(side="left", padx=(0, 6))
        tab_btns[naam] = b

    # ── Vast voorbeeldpaneel (15 augustus 2026) ─────────────────────────
    # Stond eerst bovenaan IN de scrollbare veldenlijst (inner, hieronder) -
    # dus zodra je naar een veld verderop in de lijst scrolt, scrolt het
    # levende voorbeeld gewoon mee weg. Frans: "kun je dit in zijn geheel
    # vastzetten, is handiger bij het scrollen". Nu een eigen vast frame,
    # gepakt VOOR het scrollbare canvas (sf) - blijft dus altijd zichtbaar,
    # ongeacht hoever je in de veldenlijst naar beneden scrolt.
    preview_kader = tk.Frame(win, bg=BG)
    preview_kader.pack(fill="x", padx=16, pady=(10, 0))

    # ── Scrollbaar canvas voor de veldenlijst ───────────────────────────
    sf = tk.Frame(win, bg=BG)
    sf.pack(fill="both", expand=True, padx=12, pady=(8, 4))
    cv = tk.Canvas(sf, bg=BG, highlightthickness=0)
    sb = tk.Scrollbar(sf, orient="vertical", command=cv.yview)
    cv.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    cv.pack(side="left", fill="both", expand=True)
    inner = tk.Frame(cv, bg=BG)
    cv.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))

    # Muiswiel-scrollen: alleen actief zolang de muis boven dit venster
    # hangt (bind_all/unbind_all bij Enter/Leave), zodat het geen andere
    # open suite-vensters beinvloedt.
    def _op_muiswiel(e):
        cv.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def _wiel_aan(e):
        cv.bind_all("<MouseWheel>", _op_muiswiel)

    def _wiel_uit(e):
        cv.unbind_all("<MouseWheel>")

    cv.bind("<Enter>", _wiel_aan)
    cv.bind("<Leave>", _wiel_uit)

    def _maak_swatch(parent, hex_kleur, geselecteerd, on_click):
        rand_kleur = FG if geselecteerd else PANEL2
        dikte = 3 if geselecteerd else 1
        kader = tk.Frame(parent, bg=rand_kleur)
        kader.pack(side="left", padx=4, pady=2)
        vlak = tk.Frame(kader, bg=hex_kleur, width=30, height=30, cursor="hand2")
        vlak.pack(padx=dikte, pady=dikte)
        vlak.pack_propagate(False)
        vlak.bind("<Button-1>", lambda e: on_click())
        return kader

    # ── Klikbare mini-preview + vervolg-keuzelijst (16 augustus 2026) ─────
    # Frans, na het kleurenoverzicht: "kunnen we niets maken dat kleuren
    # laat kiezen op basis van deze html pagina, in een soort vervolg
    # keuze lijst, maar dan met 15 frisse kleuren". Elk klikbaar onderdeel
    # hieronder komt EXACT overeen met de 15 kleurvelden uit GROEPEN - een
    # klik opent een klein venster naast de muis met de 15(+wit)-kleuren
    # voor precies dat veld; een keuze past meteen toe en sluit het
    # venstertje. De grote veldenlijst hieronder blijft ook gewoon werken -
    # dit is een snellere, contextuele route ernaast, geen vervanging.
    def _open_kleurkeuze(key, x=None, y=None):
        thema = huidig_tab["naam"]
        if key not in VELD_BIJ_KEY:
            return
        label, beschrijving, presets_licht, presets_donker = VELD_BIJ_KEY[key]
        presets = presets_licht if thema == "licht" else presets_donker
        huidige_waarde = state[thema].get(key)
        toon_stalen = list(presets)
        if huidige_waarde not in toon_stalen:
            toon_stalen = [huidige_waarde] + toon_stalen

        popup = tk.Toplevel(win)
        popup.title(f"{label} - {thema}")
        popup.configure(bg=PANEL)
        popup.transient(win)
        popup.resizable(False, False)
        breedte, hoogte = 300, 90 + 40 * (-(-len(toon_stalen) // 5))
        if x is None or y is None:
            x, y = win.winfo_pointerx(), win.winfo_pointery()
        x = max(0, min(x, popup.winfo_screenwidth() - breedte - 20))
        y = max(0, min(y, popup.winfo_screenheight() - hoogte - 40))
        popup.geometry(f"{breedte}x{hoogte}+{x}+{y}")

        tk.Label(popup, text=f"{label}  ({key})", font=("Segoe UI", 10, "bold"),
                  bg=PANEL, fg=FG, anchor="w", wraplength=breedte - 20,
                  justify="left").pack(fill="x", padx=10, pady=(10, 2))
        tk.Label(popup, text=beschrijving, font=("Segoe UI", 8), bg=PANEL, fg=DIM,
                  anchor="w", wraplength=breedte - 20, justify="left"
                  ).pack(fill="x", padx=10, pady=(0, 6))

        for start in range(0, len(toon_stalen), 5):
            rij = tk.Frame(popup, bg=PANEL)
            rij.pack(padx=10)
            for hex_kleur in toon_stalen[start:start + 5]:
                def _kies(h=hex_kleur):
                    state[thema][key] = h
                    popup.destroy()
                    bouw_inhoud()
                _maak_swatch(rij, hex_kleur, hex_kleur == huidige_waarde, _kies)

        RoundedButton(popup, text="Sluiten", command=popup.destroy,
                      bg=PANEL2, fg=FG, font=("Segoe UI", 8)).pack(pady=(6, 10))
        popup.bind("<Escape>", lambda e: popup.destroy())
        popup.after(50, popup.focus_set)

    def _klikbaar(widget, key):
        """Maakt een preview-onderdeel klikbaar: wijst de muiscursor aan en
        opent bij een klik de vervolg-keuzelijst van 'key'."""
        widget.configure(cursor="hand2")
        widget.bind("<Button-1>", lambda e: _open_kleurkeuze(key, e.x_root, e.y_root))
        return widget

    def _teken_preview(parent, waarden):
        """Levend voorbeeld met de op dit moment (nog niet opgeslagen) gekozen
        kleuren - klik op een titelbalk, knop, statustekst of achtergrond om
        die kleur direct te wijzigen (zie _open_kleurkeuze hierboven)."""
        kader = tk.Frame(parent, bg=waarden["PANEL"], bd=0)
        kader.pack(fill="x", pady=(0, 4))
        _klikbaar(kader, "PANEL")
        binnen = tk.Frame(kader, bg=waarden["PANEL"])
        binnen.pack(fill="x", padx=12, pady=12)
        _klikbaar(binnen, "PANEL")

        titelbalk = tk.Frame(binnen, bg=waarden["ACCENT_PICONTROL"])
        titelbalk.pack(fill="x")
        _klikbaar(titelbalk, "ACCENT_PICONTROL")
        titel_lbl = tk.Label(
            titelbalk, text="Pi NAS Menu (voorbeeld titelbalk)",
            font=("Segoe UI", 9, "bold"), bg=waarden["ACCENT_PICONTROL"],
            fg=leesbare_tekstkleur(waarden["ACCENT_PICONTROL"]))
        titel_lbl.pack(anchor="w", padx=8, pady=4)
        _klikbaar(titel_lbl, "ACCENT_PICONTROL")

        knoppenrij = tk.Frame(binnen, bg=waarden["PANEL"])
        knoppenrij.pack(fill="x", pady=(8, 4))
        for tekst, key in [("Verbinden", "ACCENT_PINAS"),
                            ("Backup Beheer", "ACCENT_PIBACKUP"),
                            ("Addons Beheer", "ACCENT_PIADDONS"),
                            ("Beheer", "ACCENT_PIBEHEER"),
                            ("Pi NAS herstarten", "DESTRUCTIEF")]:
            # Destructieve knoppen krijgen in de echte suite een VASTE
            # tekstkleur (maak_knop(), geen leesbare_tekstkleur) - de
            # preview volgt exact diezelfde regel.
            fg = VAST_DESTRUCTIEF_TEKST if key == "DESTRUCTIEF" else leesbare_tekstkleur(waarden[key])
            lbl = tk.Label(knoppenrij, text=tekst, font=("Segoe UI", 8, "bold"),
                            bg=waarden[key], fg=fg, padx=8, pady=4)
            lbl.pack(side="left", padx=(0, 6))
            _klikbaar(lbl, key)
        annuleer = tk.Label(knoppenrij, text="Annuleren", font=("Segoe UI", 8, "bold"),
                              bg=waarden["PANEL2"], fg=waarden["FG"], padx=8, pady=4)
        annuleer.pack(side="left", padx=(0, 6))
        _klikbaar(annuleer, "PANEL2")

        statusrij = tk.Frame(binnen, bg=waarden["PANEL"])
        statusrij.pack(fill="x", pady=(6, 0))
        for tekst, key in [("● in orde", "OK_C"), ("● fout", "ERR_C"),
                           ("● waarschuwing", "WARN"), ("● wisselend", "YELLOW")]:
            lbl = tk.Label(statusrij, text=tekst, font=("Segoe UI", 9),
                            bg=waarden["PANEL"], fg=waarden[key])
            lbl.pack(side="left", padx=(0, 14))
            _klikbaar(lbl, key)

        tekstvb = tk.Frame(binnen, bg=waarden["BG"])
        tekstvb.pack(fill="x", pady=(8, 0))
        _klikbaar(tekstvb, "BG")
        hoofdtekst = tk.Label(tekstvb, text="Voorbeeldtekst op de achtergrondkleur",
                                font=("Segoe UI", 9), bg=waarden["BG"], fg=waarden["FG"])
        hoofdtekst.pack(anchor="w", padx=8, pady=(6, 0))
        _klikbaar(hoofdtekst, "FG")
        dimtekst = tk.Label(tekstvb, text="Gedimde hulptekst eronder",
                              font=("Segoe UI", 8), bg=waarden["BG"], fg=waarden["DIM"])
        dimtekst.pack(anchor="w", padx=8, pady=(0, 6))
        _klikbaar(dimtekst, "DIM")

        tk.Label(parent, text="Tip: klik op de titelbalk, een knop, statustekst of "
                  "achtergrond hierboven om die kleur direct te wijzigen.",
                  font=("Segoe UI", 8), bg=BG, fg=DIM, wraplength=800,
                  justify="left").pack(anchor="w", pady=(0, 12))

    def bouw_inhoud():
        for w in inner.winfo_children():
            w.destroy()
        for w in preview_kader.winfo_children():
            w.destroy()
        thema = huidig_tab["naam"]
        waarden = state[thema]

        # Vast voorbeeldpaneel (zie preview_kader hierboven) - niet meer in
        # inner, dus blijft staan ongeacht scrollpositie.
        _teken_preview(preview_kader, waarden)

        for groepnaam, velden in GROEPEN:
            tk.Label(inner, text=groepnaam, font=("Segoe UI", 10, "bold"),
                      bg=BG, fg=ACCENT).pack(anchor="w", pady=(6, 4))
            for key, label, beschrijving, presets_licht, presets_donker in velden:
                presets = presets_licht if thema == "licht" else presets_donker
                rij = tk.Frame(inner, bg=BG)
                rij.pack(fill="x", pady=(2, 8))
                tk.Label(rij, text=f"{label}  ({key})", font=("Segoe UI", 9, "bold"),
                          bg=BG, fg=FG, anchor="w").pack(fill="x")
                tk.Label(rij, text=beschrijving, font=("Segoe UI", 8),
                          bg=BG, fg=DIM, anchor="w", wraplength=760,
                          justify="left").pack(fill="x", pady=(0, 4))
                stalen_rij = tk.Frame(rij, bg=BG)
                stalen_rij.pack(anchor="w")
                huidige_waarde = waarden.get(key)
                # Zorg dat de huidige (mogelijk niet-standaard) waarde ook
                # zichtbaar is, ook als hij niet in de standaardstalen zit.
                toon_stalen = list(presets)
                if huidige_waarde not in toon_stalen:
                    toon_stalen = [huidige_waarde] + toon_stalen
                for hex_kleur in toon_stalen:
                    def _kies(k=key, h=hex_kleur, t=thema):
                        state[t][k] = h
                        bouw_inhoud()
                    _maak_swatch(stalen_rij, hex_kleur, hex_kleur == huidige_waarde, _kies)
            tk.Frame(inner, bg=PANEL2, height=1).pack(fill="x", pady=(4, 8))

    bouw_inhoud()

    # ── Onderbalk: Opslaan / Herladen ────────────────────────────────────
    onder = tk.Frame(win, bg=BG)
    onder.pack(fill="x", padx=16, pady=(4, 14))

    def _herladen():
        if not messagebox.askyesno(
                "Herladen",
                "Alle nog niet opgeslagen keuzes ongedaan maken en opnieuw "
                "laden vanaf schijf?"):
            return
        state["licht"] = _huidige_waarden("licht")
        state["donker"] = _huidige_waarden("donker")
        bouw_inhoud()

    def _opslaan():
        try:
            opslaan(state["licht"], state["donker"])
        except Exception as e:
            messagebox.showerror("Opslaan mislukt", str(e))
            return
        messagebox.showinfo(
            "Opgeslagen",
            "Kleuren opgeslagen in Gedeeld\\pinas_theme.py.\n\n"
            "Herstart de suite-programma's (hoofdmenu en eventuele open "
            "vensters) om de wijziging te zien.")

    RoundedButton(onder, text="Herladen vanaf schijf", command=_herladen,
                  bg=PANEL2, fg=FG, font=("Segoe UI", 9)).pack(side="left")
    RoundedButton(onder, text="Opslaan", command=_opslaan,
                  bg=ACCENT, fg="#ffffff", font=("Segoe UI", 9, "bold")).pack(side="right")

    win.mainloop()


if __name__ == "__main__":
    main()
