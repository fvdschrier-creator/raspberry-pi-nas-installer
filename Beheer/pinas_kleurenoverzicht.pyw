#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pi NAS Suite - Kleurenoverzicht
Dubbelklik om te starten, of via Pi NAS Menu -> Onderhoud -> Weergave ->
"Kleurenoverzicht (per venster)".

17 augustus 2026: opvolger van een eenmalig, met de hand gegenereerd
HTML-overzicht (op verzoek van Frans destijds: "kunnen we een tabel met
kleuren maken, van alle vensters, met knoppen, titels en tekstkleuren,
een soort boom"). Frans' vervolgvraag na dat overzicht: "doet die zich
zelf up to date maken?" - nee, dat was een momentopname, en inmiddels al
verouderd. Daarna: "is daar een los programma van te maken dat deze dat
wel doet". Dit programma is dat antwoord.

Het verschil met de oude, eenmalige versie: de kleurWAARDEN hieronder
worden NIET meer hier hardcoded, maar elke keer dat je dit programma
opent (of op "Opnieuw genereren" klikt) LIVE uitgelezen uit
Gedeeld/pinas_theme.py - de ENE bron van waarheid voor kleuren in de
hele suite (zie de docstring daar). Wijzig je een kleur via "Kleuren
kiezen", dan klopt dit overzicht bij de eerstvolgende keer openen
vanzelf weer, zonder dat iemand dit bestand met de hand hoeft bij te
werken.

Wat WEL met de hand wordt bijgehouden (net als bij GROEPEN in
pinas_kleuren_kiezer.pyw): WELK venster/welke knop WELK themaveld
gebruikt (zie VENSTERS hieronder). Dat staat nergens gestructureerd in
de suite zelf - het zijn losse .pyw-bestanden die losse constanten
importeren - en kan dus niet automatisch uit de code worden afgeleid.
Alleen de kleurWAARDE achter elke veldnaam (ACCENT_PINAS = "#038787"
e.d.) is live; welk scherm welk veld gebruikt blijft handwerk. Verandert
de suite zelf (een scherm krijgt een ander veld, of er komt een nieuw
scherm bij), dan moet VENSTERS hieronder met de hand worden bijgewerkt.
"""
import html
import os
import sys
import time
import webbrowser


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
    import pinas_theme as pt
    from pinas_theme import BG, PANEL, PANEL2, FG, DIM, OK_C, ERR_C, WARN, ACCENT_PINAS
    from pinas_ui import maak_header, maak_knop
except ImportError:
    pt = None
    BG = "#e9edf2"; PANEL = "#dae2ea"; PANEL2 = "#bed0dd"
    FG = "#333c47"; DIM = "#6d7d8c"
    OK_C = "#16a34a"; ERR_C = "#dc2626"; WARN = "#d97706"; ACCENT_PINAS = "#038787"
    maak_header = maak_knop = None

UITVOER_PAD = os.path.join(NAS_ROOT, "Publicatie", "PiNAS_Kleurenoverzicht.html")

# Vaste tekstkleur voor destructieve knoppen (zie maak_knop() in pinas_ui.py -
# stijl="destructief" gebruikt BEWUST geen leesbare_tekstkleur(), zodat dit
# overzicht exact laat zien wat de echte suite doet). Zelfde constante als in
# pinas_kleuren_kiezer.pyw - moet in sync blijven met pinas_ui.py's eigen
# "destructief"-stijl, mocht die ooit wijzigen.
VAST_DESTRUCTIEF_TEKST = "#3d2604"


# ---------------------------------------------------------------------------
# Per venster: titelbalk (bg, fg), algemene tekst (fg), knoppen
# [(label, bg-ref, fg-ref, opmerking)]. Hand-bijgehouden structuur - zie de
# docstring hierboven. fg-ref "auto" = via leesbare_tekstkleur() (LIVE
# berekend, zie auto_tekst() hieronder). fg-ref die begint met "#" =
# hardcoded letterlijke kleur (niet uit het thema, blijft dus altijd
# hetzelfde ongeacht het thema-bestand).
# ---------------------------------------------------------------------------
VENSTERS = [
    dict(groep="Hoofdmenu", naam="Pi NAS Menu — hoofdscherm",
         titelbalk=("ACCENT_PICONTROL", "#ffffff", "vaste solide balk"),
         tekst="FG",
         knoppen=[
             ("SSH / TigerVNC / WinSCP (Verbinden)", "ACCENT_PINAS", "auto", None),
             ("Backup Beheer", "ACCENT_PIBACKUP", "auto", None),
             ("Addons Beheer", "ACCENT_PIADDONS", "auto", None),
             ("Installatie & Herstel", "ACCENT_PIBEHEER", "auto", None),
             ("Controles", "ACCENT_PIBEHEER_2", "auto", None),
             ("Onderhoud", "ACCENT_PIBEHEER_3", "auto", None),
             ("Extern HDD: Aanzetten", "WARN", "auto", None),
             ("Extern HDD: Uitzetten (actief)", "ERR_C", "#333c47/#eef2f6 (FG, niet herberekend)", "let op: tekst niet automatisch herzet"),
             ("Status", "ACCENT_PINAS", "auto", None),
             ("Help / overig", "PANEL2", "FG", None),
         ]),
    dict(groep="Hoofdmenu", naam="SD-kaart wizard",
         titelbalk=("ACCENT_PICONTROL", "auto", None),
         tekst="FG / DIM",
         knoppen=[
             ("Terug / Annuleren", "PANEL2", "FG", None),
             ("Volgende →", "ACCENT_PINAS", "auto", "PANEL2 indien uitgeschakeld"),
             ("Pi Imager starten", "ACCENT_PINAS", "auto", None),
         ]),
    dict(groep="Hoofdmenu", naam="Onderhoud",
         titelbalk=("BG", "ACCENT_PIBEHEER_3", "maak_header - geen gekleurde balk"),
         tekst="FG / DIM",
         knoppen=[
             ("Help, Suite handleiding herbouwen, Topografie herbouwen, "
              "Documentatie controleren, Starter Kit bouwen, Publieke versie maken, "
              "Pi OS/Python bijwerken, Scripts uploaden, Download links, "
              "Thema wisselen, Kleuren kiezen, Kleurenoverzicht (~12x)", "PANEL2", "FG", None),
             ("Pi NAS herstarten", "DESTRUCTIEF", "auto", "wijkt af: elders vaste #3d2604"),
             ("LanMan-fix", "WARN", "auto", None),
             ("NAS wachtwoord instellen / Dashboard-wachtwoord resetten", "ACCENT_PICONTROL", "#ffffff",
              "bug: dit hoort ACCENT_PINAS (algemeen blauw) te zijn, maar dit bestand "
              "herdefinieert ACCENT lokaal naar ACCENT_PICONTROL (paars) - het paars is "
              "volgens pinas_theme.py's eigen regel juist gereserveerd voor vensterkoppen"),
         ]),
    dict(groep="Hoofdmenu", naam="Download links / NAS wachtwoord (dialoogjes)",
         titelbalk=("BG", "FG", "geen gekleurde balk, geen accent"),
         tekst="FG / DIM",
         knoppen=[
             ("Opslaan", "ACCENT_PINAS", "auto", None),
             ("Standaard herstellen / Annuleren / Later instellen", "PANEL2", "FG / DIM", None),
         ]),
    dict(groep="Hoofdmenu", naam="Status",
         titelbalk=("BG", "ACCENT_PINAS", "maak_header - geen gekleurde balk"),
         tekst="FG / DIM",
         knoppen=[
             ("Help / Vernieuwen / Uploaden naar Pi / Open (logs)", "PANEL2", "FG", None),
             ("SSH sleutel herstellen / Schijven verbinden", "WARN", "auto", None),
             ("Sync opnieuw controleren", "BG", "DIM", "oogt als link, niet als knop"),
         ]),

    dict(groep="Beheer", naam="Structuurcheck & Opruimen",
         titelbalk=("BG", "ACCENT_PIBEHEER_2", "maak_header; terugval-pad tekent wel een balk met hardcoded #9fc2e0-subtekst"),
         tekst="FG / DIM",
         knoppen=[
             ("Tabs Structuurcheck/Opruimen (inactief)", "PANEL2", "#e2eaf2 (hardcoded)", "eigen, niet-gedeelde knopklasse"),
             ("Tabs (actief) / Opnieuw controleren (2x)", "ACCENT_PINAS", "#e2eaf2 (hardcoded)", None),
             ("Verkeerd geplaatste bestanden verplaatsen", "#b45309 (hardcoded)", "#e2eaf2 (hardcoded)", "geen thema-kleur"),
             ("Dubbele/oude kopieën verwerken / Onbekend verwijderen / "
              "Geselecteerd verwijderen", "ERR_C", "#e2eaf2 (hardcoded)", None),
         ]),
    dict(groep="Beheer", naam="Controles",
         titelbalk=("BG", "ACCENT_PIBEHEER_2", "maak_header - geen gekleurde balk"),
         tekst="FG / DIM",
         knoppen=[
             ("Structuurcheck & Opruimen / Pi opruimen / Suite testen / "
              "Diagnose uitvoeren / Log Bestanden Bekijken (5x)", "PANEL2", "FG",
              "bewust neutraal sinds 15 aug (was 4x identiek ACCENT_PIBEHEER_2)"),
         ]),
    dict(groep="Beheer", naam="Controles → Diagnose",
         titelbalk=("ACCENT_PIBEHEER_2", "auto", "vaste solide balk"),
         tekst="FG / DIM",
         knoppen=[
             ("PC diagnose / Pi diagnose (SSH)", "ACCENT_PIBEHEER_2", "auto", None),
             ("Wissen / Sluiten", "PANEL2", "FG", None),
         ]),
    dict(groep="Beheer", naam="Controles → Logbestanden",
         titelbalk=("ACCENT_PIBEHEER_2", "auto", "vaste solide balk"),
         tekst="FG / DIM",
         knoppen=[("Open (per logbestand) / Sluiten", "PANEL2", "FG", None)]),
    dict(groep="Beheer", naam="Installatie & Herstel / Onderhoud-wizard (SetupApp)",
         titelbalk=("BG", "ACCENT_PIBEHEER", "maak_header - geen gekleurde balk"),
         tekst="FG / DIM (stapindicator: OK_C actief, DIM voltooid, PANEL2 nog te doen)",
         knoppen=[
             ("Terug / Annuleren / 'Pi is al bereikbaar'", "PANEL2", "FG / DIM", None),
             ("Verder → / Pi Imager starten / Wachten op Pi", "ACCENT_PIBEHEER", "auto", None),
         ]),
    dict(groep="Beheer", naam="Pi opruimen",
         titelbalk=("BG", "ACCENT_PIBEHEER_2", "maak_header - geen gekleurde balk"),
         tekst="FG / DIM",
         knoppen=[
             ("Controleren", "ACCENT_PIBEHEER_2", "auto", None),
             ("Onbekende items verwijderen", "DESTRUCTIEF", VAST_DESTRUCTIEF_TEKST, None),
         ]),
    dict(groep="Beheer", naam="Kleuren kiezen",
         titelbalk=("BG", "ACCENT_PINAS", "maak_header - geen gekleurde balk"),
         tekst="FG / DIM",
         knoppen=[
             ("Sluiten", "PANEL2", "FG", None),
             ("Tab Licht/Donker", "ACCENT_PINAS", "#ffffff (hardcoded)", "niet via leesbare_tekstkleur()"),
             ("Herladen vanaf schijf", "PANEL2", "FG", None),
             ("Opslaan", "ACCENT_PINAS", "#ffffff (hardcoded)", "niet via leesbare_tekstkleur()"),
         ]),
    dict(groep="Beheer", naam="Kleurenoverzicht (dit programma)",
         titelbalk=("BG", "ACCENT_PINAS", "maak_header - geen gekleurde balk"),
         tekst="FG / DIM",
         knoppen=[
             ("Opnieuw genereren en openen", "ACCENT_PINAS", "auto", None),
             ("Sluiten", "PANEL2", "FG", None),
         ]),

    dict(groep="Backup / Addons", naam="Backup Beheer",
         titelbalk=("BG", "ACCENT_PIBACKUP", "maak_header - geen gekleurde balk"),
         tekst="FG / DIM",
         knoppen=[
             ("Synchronisatie / PC Image Backup / iPhone Back-up / "
              "iPhone Doorbladeren / Archief Backup Bewaking (5x)", "ACCENT_PIBACKUP", "auto", None),
             ("Systeem-image maken / Backup-HDD controleren+herstellen / "
              "Rechten backup-HDD herstellen (3x)", "DESTRUCTIEF", VAST_DESTRUCTIEF_TEKST, None),
         ]),
    dict(groep="Backup / Addons", naam="PC Image Backup",
         titelbalk=("BG", "ACCENT_PIBACKUP", "maak_header - geen gekleurde balk"),
         tekst="FG(=TEKST) / DIM(=TEKST_DIM)",
         knoppen=[
             ("Herstelschijf maken + noodkaartje", "WARN", "#ffffff (hardcoded)", "geen leesbare_tekstkleur()"),
             ("Noodkaartje opslaan / Structuur controleren / doelmap "
              "kiezen / Vereisten controleren / Toon schijven (5x)", "PANEL", "FG", None),
             ("Start Image Backup (al Administrator)", "OK_C", "#ffffff (hardcoded)", "geen leesbare_tekstkleur()"),
             ("Start Image Backup als Administrator (UAC)", "WARN", "#ffffff (hardcoded)", "geen leesbare_tekstkleur()"),
         ]),
    dict(groep="Backup / Addons", naam="Addons Beheer",
         titelbalk=("BG", "ACCENT_PIADDONS", "maak_header - geen gekleurde balk"),
         tekst="FG / DIM",
         knoppen=[
             ("Installeren / Starten (7x, per addon)", "ACCENT_PIADDONS", "auto", None),
             ("Verwijderen / Stoppen (7x)", "DESTRUCTIEF", VAST_DESTRUCTIEF_TEKST, None),
             ("Certificaat vertrouwen / Beheer openen / Wachtwoord "
              "resetten e.d. (secundair)", "PANEL2", "FG", None),
         ]),
    dict(groep="Backup / Addons", naam="Vaultwarden-certificaat vertrouwen",
         titelbalk=("—", "—", "geen eigen venster - alleen kale systeemdialogen (messagebox)"),
         tekst="—",
         knoppen=[]),

    dict(groep="Sync / Archief", naam="PiNAS Sync — Bron/doel kiezen",
         titelbalk=("ACCENT_PIBACKUP", "#ffffff (hardcoded 'white')", "vaste solide balk, bewust thema-onafhankelijk"),
         tekst="DIM",
         knoppen=[("Doorgaan naar synchronisatie →", "ACCENT_PIBACKUP", "#ffffff (hardcoded)", None)]),
    dict(groep="Sync / Archief", naam="PiNAS Sync — Synchroniseren",
         titelbalk=("ACCENT_PIBACKUP", "#ffffff (hardcoded 'white')", "vaste solide balk, bewust thema-onafhankelijk"),
         tekst="DIM",
         knoppen=[
             ("Terug naar bron/doel", "ACCENT_PIBACKUP", "#ffffff (hardcoded)", None),
             ("Nu controleren / Verbinding testen / HDD uit-aan / "
              "LanManFix / station loskoppelen / tellen overslaan / "
              "alles kopiëren (7x)", "PANEL", "FG", None),
             ("Synchronisatie starten", "ACCENT_PIBACKUP", "#ffffff (hardcoded)", None),
             ("Stoppen", "ERR_C", "#ffffff (hardcoded)", None),
         ]),
    dict(groep="Sync / Archief", naam="Archief Backup Bewaking",
         titelbalk=("ACCENT_PIBACKUP", "#ffffff (hardcoded)", "vaste solide balk; subtekst #9fc2e0 (hardcoded)"),
         tekst="FG / DIM",
         knoppen=[
             ("Controleren (alleen lezen)", "ACCENT_PIBACKUP", "#ffffff (hardcoded)", None),
             ("Synchroniseren (actief)", "WARN", "#1f2937 (hardcoded)", "geen leesbare_tekstkleur()"),
             ("Synchroniseren/Rapport opslaan (uitgeschakeld)", "#3f4b5b (hardcoded)", "#eef2f7 (hardcoded)", None),
             ("Rapport opslaan (actief)", "#475569 (hardcoded)", "#ffffff (hardcoded)", "geen thema-kleur"),
             ("Map kiezen (per rij)", "PANEL2", "FG", None),
         ]),

    dict(groep="Overig", naam="Test Suite",
         titelbalk=("PANEL", "FG", "enige venster zonder accentkleur op de titel"),
         tekst="FG / DIM",
         knoppen=[
             ("Alles testen", "OK_C", "auto", None),
             ("Opnieuw / Exporteer CSV", "PANEL2", "FG", None),
         ]),
]

BEVINDINGEN = [
    "Twee verschillende titelbalk-stijlen bestaan naast elkaar: de gedeelde "
    "maak_header() tekent NOOIT een gekleurde balk (achtergrond blijft BG, "
    "alleen de titeltekst krijgt een accentkleur) - gebruikt door Onderhoud, "
    "Status, Structuurcheck &amp; Opruimen, Controles, Installatie &amp; Herstel, "
    "Pi opruimen, Kleuren kiezen, Kleurenoverzicht. Losse, handgeschreven "
    "vensters (hoofdmenu, SD-kaart wizard, Controles→Diagnose/Logbestanden, "
    "PiNAS Sync, Archief Backup Bewaking) tekenen zelf een volle gekleurde balk.",
    "leesbare_tekstkleur() (automatische contrastkeuze) wordt op meerdere "
    "plekken omzeild met een vaste witte of andere hardcoded tekstkleur: "
    "PC Image Backup (KNOP_TEKST=\"#ffffff\"), PiNAS Sync/core/thema.py "
    "(KNOP_TEKST=\"white\", SUBTITEL=\"#dce8fb\"), Archief Backup Bewaking "
    "(titel \"#ffffff\", subtekst \"#9fc2e0\", enkele knoppen), Kleuren "
    "kiezen (tabknoppen en \"Opslaan\").",
    "Losse, niet-thema hex-kleuren duiken op meerdere plekken op: "
    "Structuurcheck &amp; Opruimen se eigen knopklasse (_rbtn_nmb, met eigen "
    "hardcoded standaardkleuren) en de \"#b45309\"-knop; \"#9fc2e0\" komt "
    "onafhankelijk van elkaar voor in zowel Structuurcheck &amp; Opruimen's "
    "terugvalpad als Archief Backup Bewaking's echte titelbalk; Controles → "
    "Diagnose's uitvoerscherm (GitHub-donker-palet); Archief Backup "
    "Bewaking's UIT_BG/UIT_FG en \"#475569\".",
    "Vaultwarden-certificaat vertrouwen gebruikt helemaal geen thema - "
    "alleen kale systeemdialogen (messagebox), geen eigen venster.",
    "Pi_NAS_Menu.pyw herdefinieert lokaal ACCENT = ACCENT_PICONTROL (paars) "
    "voor de rest van dat bestand. Daardoor renderen de knoppen \"NAS "
    "wachtwoord instellen\" en \"PiNAS Dashboard - wachtwoord resetten\" op "
    "het Onderhoud-scherm in paars, terwijl pinas_theme.py's eigen "
    "documentatie zegt dat ACCENT_PICONTROL uitsluitend voor vensterkoppen "
    "bedoeld is, nooit voor knoppen.",
    "NAS_Map_Beheer.pyw heeft nog een eigen, losse Canvas-knopklasse "
    "(_rbtn_nmb) naast de gedeelde RoundedButton in pinas_ui.py - de "
    "docstring van pinas_ui.py zegt dat dit al geconsolideerd zou moeten "
    "zijn.",
    "Pi NAS Menu's \"Extern HDD: Uitzetten\"-knop wisselt van achtergrond "
    "(PANEL2 → ERR_C) maar de tekstkleur wordt niet herberekend en blijft "
    "op FG staan - mogelijk te weinig contrast zodra de knop rood wordt.",
    "Test Suite is het enige onderzochte venster waarvan de titelbalk geen "
    "accentkleur gebruikt (bg=PANEL, titel-fg=FG i.p.v. een kleur) - overal "
    "elders krijgt de titel wel een accentkleur.",
]


# ---------------------------------------------------------------------------
# Live thema-waarden - het deel dat dit programma "automatisch bijwerkend"
# maakt. Anders dan de oude, eenmalige generator staan hier GEEN kleuren
# hardcoded: alles komt bij elke aanroep vers uit Gedeeld/pinas_theme.py.
# ---------------------------------------------------------------------------
def _thema_dict(basis, is_donker):
    """basis = pt._LICHT of pt._DONKER (levend, rechtstreeks uit
    pinas_theme.py). Voegt de automatisch afgeleide ACCENT_PIBEHEER_2/_3
    toe voor DIT ene thema - pinas_theme.py zelf berekent die alleen voor
    het op dit moment ACTIEVE thema (zie _beheer_deltas/globals().update()
    daar), dus voor een overzicht dat licht EN donker naast elkaar toont
    moeten ze hier apart, voor elk thema, worden nagerekend. Gebruikt
    dezelfde delta's als pinas_theme.py's eigen _beheer_deltas-regel -
    kleine, bewuste duplicatie die in sync moet blijven met die regel,
    net als VAST_DESTRUCTIEF_TEKST hierboven."""
    d = dict(basis)
    deltas = (-18, 0.05, 18, 0.10) if is_donker else (-18, 0.06, 18, 0.13)
    d["ACCENT_PIBEHEER_2"] = pt.kleurvariant(d["ACCENT_PIBEHEER"], deltas[0], deltas[1])
    d["ACCENT_PIBEHEER_3"] = pt.kleurvariant(d["ACCENT_PIBEHEER"], deltas[2], deltas[3])
    return d


def _lees_live_paletten():
    """Herlaadt pinas_theme.py vanaf schijf (importlib.reload) zodat een
    wijziging via "Kleuren kiezen" ook zichtbaar wordt zonder dit
    programma opnieuw te hoeven starten, en geeft (LICHT, DONKER) terug."""
    import importlib
    importlib.reload(pt)
    return _thema_dict(pt._LICHT, False), _thema_dict(pt._DONKER, True)


def kleur(thema_dict, ref):
    """ref is ofwel een thema-veldnaam ('ACCENT_PINAS'), ofwel een
    letterlijke hex-code ('#xxxxxx', voor hardcoded/niet-thema-kleuren)."""
    if ref.startswith("#"):
        return ref
    return thema_dict[ref]


def auto_tekst(thema_dict, bg_ref):
    """Live tegenhanger van de vroegere, hardcoded AUTO_TEKST-tabel: roept
    leesbare_tekstkleur() rechtstreeks aan op de HUIDIGE kleur van bg_ref
    in dit thema - precies wat de suite zelf ook doet (zie maak_knop() in
    pinas_ui.py en _teken_preview() in pinas_kleuren_kiezer.pyw). Dit is
    de kern van waarom dit overzicht niet meer kan verouderen: verandert
    een achtergrondkleur, dan verandert hierdoor meteen ook de erbij
    horende automatische tekstkleur."""
    if bg_ref is None or bg_ref.startswith("#"):
        return "#ffffff"
    return pt.leesbare_tekstkleur(thema_dict[bg_ref])


def swatch(hexcode, label=None):
    veilig = html.escape(hexcode)
    tekst = html.escape(label) if label else veilig
    return (f'<span class="swatch-rij">'
            f'<span class="swatch" style="background:{veilig}"></span>'
            f'<span class="hexcode">{tekst}</span></span>')


def render_venster(v, thema_dict):
    tb_bg_ref, tb_fg_ref, tb_note = v["titelbalk"]
    out = [f'<div class="venster">', f'<h3>{html.escape(v["naam"])}</h3>']
    if tb_bg_ref == "—":
        out.append('<p class="geen">Geen eigen venster/thema van toepassing.</p>')
        out.append('</div>')
        return "\n".join(out)

    out.append('<table class="kleurtabel">')
    out.append('<tr><th>Onderdeel</th><th>Achtergrond</th><th>Tekst</th><th>Opmerking</th></tr>')

    tb_bg = kleur(thema_dict, tb_bg_ref)
    if tb_fg_ref == "auto":
        tb_fg_cell = swatch(auto_tekst(thema_dict, tb_bg_ref if not tb_bg_ref.startswith("#") else None))
    elif tb_fg_ref.startswith("#"):
        tb_fg_cell = swatch(tb_fg_ref.split(" ")[0])
    else:
        tb_fg_cell = swatch(kleur(thema_dict, tb_fg_ref), tb_fg_ref)
    out.append(f'<tr><td>Titelbalk</td><td>{swatch(tb_bg, tb_bg_ref if not tb_bg_ref.startswith("#") else None)}</td>'
               f'<td>{tb_fg_cell}</td><td class="opm">{html.escape(tb_note or "")}</td></tr>')

    tekst_refs = v["tekst"]
    if tekst_refs != "—":
        eerste = tekst_refs.split("/")[0].split("(")[0].strip()
        eerste_kleur = thema_dict.get(eerste)
        cel = swatch(eerste_kleur, tekst_refs) if eerste_kleur else html.escape(tekst_refs)
        out.append(f'<tr><td>Algemene tekst</td><td colspan="2">{cel}</td><td class="opm"></td></tr>')

    for label, bg_ref, fg_ref, opm in v["knoppen"]:
        if bg_ref == "auto":
            bg_cell = "auto"
        elif bg_ref.startswith("#"):
            bg_cell = swatch(bg_ref.split(" ")[0], bg_ref if "(" in bg_ref else None)
        else:
            bg_cell = swatch(kleur(thema_dict, bg_ref), bg_ref)

        if fg_ref == "auto":
            bg_key = bg_ref if not bg_ref.startswith("#") else None
            fg_cell = swatch(auto_tekst(thema_dict, bg_key), "auto")
        elif fg_ref.startswith("#"):
            fg_cell = swatch(fg_ref.split(" ")[0], "hardcoded" if "hardcoded" in fg_ref else None)
        elif "/" in fg_ref:
            fg_cell = html.escape(fg_ref)
        else:
            fg_cell = swatch(kleur(thema_dict, fg_ref), fg_ref)

        out.append(f'<tr><td>{html.escape(label)}</td><td>{bg_cell}</td><td>{fg_cell}</td>'
                   f'<td class="opm">{html.escape(opm or "")}</td></tr>')

    out.append('</table></div>')
    return "\n".join(out)


def render_thema(thema_naam, thema_dict):
    groepen = {}
    for v in VENSTERS:
        groepen.setdefault(v["groep"], []).append(v)
    out = [f'<div class="thema-inhoud" data-thema="{thema_naam}">']
    for groep, vensters in groepen.items():
        out.append(f'<h2>{html.escape(groep)}</h2>')
        for v in vensters:
            out.append(render_venster(v, thema_dict))
    out.append('</div>')
    return "\n".join(out)


def genereer_html():
    """Bouwt de volledige HTML-pagina met de op dit moment geldende
    kleuren (leest pinas_theme.py vers, zie _lees_live_paletten())."""
    LICHT, DONKER = _lees_live_paletten()
    gegenereerd_op = time.strftime("%d-%m-%Y %H:%M")

    return f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<title>Pi NAS Suite — Kleurenoverzicht per venster</title>
<style>
  :root {{
    --bg: #f4f6f9; --card: #ffffff; --border: #dde3ea; --text: #23303d;
    --text-dim: #667284; --accent: #206ac9;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg); color: var(--text); margin: 0; padding: 24px 32px 64px;
    line-height: 1.5;
  }}
  h1 {{ font-size: 22px; font-weight: 600; margin: 0 0 4px; }}
  .sub {{ color: var(--text-dim); font-size: 14px; margin: 0 0 4px; }}
  .stempel {{ color: var(--text-dim); font-size: 12px; margin: 0 0 20px; font-style: italic; }}
  .tabs {{ display: flex; gap: 8px; margin-bottom: 24px; }}
  .tab-btn {{
    padding: 8px 20px; border-radius: 8px; border: 1px solid var(--border);
    background: var(--card); cursor: pointer; font-size: 14px; font-weight: 600;
    color: var(--text-dim);
  }}
  .tab-btn.actief {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
  h2 {{ font-size: 15px; font-weight: 700; margin: 32px 0 10px; color: var(--text-dim);
       text-transform: uppercase; letter-spacing: 0.03em; }}
  h2:first-of-type {{ margin-top: 0; }}
  .venster {{
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
    padding: 14px 18px 18px; margin-bottom: 14px;
  }}
  .venster h3 {{ font-size: 15px; font-weight: 700; margin: 0 0 10px; }}
  .geen {{ color: var(--text-dim); font-size: 13px; font-style: italic; margin: 0; }}
  table.kleurtabel {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  table.kleurtabel th {{
    text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.03em;
    color: var(--text-dim); border-bottom: 1px solid var(--border); padding: 4px 8px 6px 0;
  }}
  table.kleurtabel td {{ padding: 6px 8px 6px 0; border-bottom: 1px solid #eef1f5; vertical-align: top; }}
  table.kleurtabel tr:last-child td {{ border-bottom: none; }}
  .swatch-rij {{ display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }}
  .swatch {{
    display: inline-block; width: 15px; height: 15px; border-radius: 4px;
    border: 1px solid rgba(0,0,0,0.15); flex-shrink: 0;
  }}
  .hexcode {{ font-family: "Cascadia Mono", Consolas, monospace; font-size: 12px; }}
  td.opm {{ color: #a05a1f; font-size: 12px; font-style: italic; max-width: 260px; }}
  .bevindingen {{
    background: #fff8ec; border: 1px solid #f0dcb2; border-radius: 10px;
    padding: 16px 20px; margin-top: 32px;
  }}
  .bevindingen h2 {{ margin-top: 0; color: #8a5a12; }}
  .bevindingen ul {{ margin: 0; padding-left: 20px; font-size: 13px; }}
  .bevindingen li {{ margin-bottom: 10px; }}
</style>
</head>
<body>

<h1>Pi NAS Suite — kleurenoverzicht per venster</h1>
<p class="sub">Per venster: titelbalk, algemene tekst en elke knop, met achtergrond- en tekstkleur.
"auto" = automatisch gekozen via leesbare_tekstkleur() (wit tenzij te weinig contrast, dan een
donkere tint uit dezelfde kleurfamilie). Cursief in de laatste kolom = bijzonderheid/afwijking.</p>
<p class="stempel">Kleurwaarden live gelezen uit Gedeeld\\pinas_theme.py bij het genereren op
{gegenereerd_op} - klik "Opnieuw genereren en openen" na een wijziging via Kleuren kiezen om deze
pagina te verversen. Welk venster welk veld gebruikt (de indeling hieronder) blijft handwerk.</p>

<div class="tabs">
  <button class="tab-btn actief" data-thema="licht" onclick="wisselThema('licht')">Licht</button>
  <button class="tab-btn" data-thema="donker" onclick="wisselThema('donker')">Donker</button>
</div>

{render_thema('licht', LICHT)}
{render_thema('donker', DONKER)}

<div class="bevindingen">
<h2>Bevindingen (niet gewijzigd, alleen gesignaleerd)</h2>
<ul>
{"".join(f"<li>{b}</li>" for b in BEVINDINGEN)}
</ul>
</div>

<script>
function wisselThema(naam) {{
  document.querySelectorAll('.thema-inhoud').forEach(function(el) {{
    el.style.display = (el.dataset.thema === naam) ? '' : 'none';
  }});
  document.querySelectorAll('.tab-btn').forEach(function(btn) {{
    btn.classList.toggle('actief', btn.dataset.thema === naam);
  }});
}}
wisselThema('licht');
</script>

</body>
</html>
"""


def genereer_en_open():
    """Schrijft de pagina naar Publicatie\\PiNAS_Kleurenoverzicht.html en
    opent hem meteen in de standaardbrowser."""
    inhoud = genereer_html()
    os.makedirs(os.path.dirname(UITVOER_PAD), exist_ok=True)
    with open(UITVOER_PAD, "w", encoding="utf-8") as f:
        f.write(inhoud)
    webbrowser.open("file://" + UITVOER_PAD.replace("\\", "/"))
    return UITVOER_PAD


# ---------------------------------------------------------------------------
# GUI - klein bedieningsvenstertje: genereert+opent meteen bij het starten,
# en biedt daarna een knop om dat opnieuw te doen (bijv. na een wijziging
# via Kleuren kiezen) zonder dit programma opnieuw te hoeven starten.
# ---------------------------------------------------------------------------
def main():
    import tkinter as tk
    from tkinter import messagebox

    win = tk.Tk()
    win.title("Kleurenoverzicht — Pi NAS Suite")
    win.configure(bg=BG)
    win.geometry("520x260")
    win.minsize(440, 220)

    KLEURENOVERZICHT_HELP = [
        ("Kleurenoverzicht", "Toont per venster van de suite welke kleur de titelbalk, de "
         "algemene tekst en elke knop hebben, voor zowel het lichte als het donkere thema. "
         "Opent automatisch in je browser."),
        ("Blijft dit up-to-date?", "Ja, de kleurWAARDEN worden elke keer dat je deze pagina "
         "genereert vers uit Gedeeld\\pinas_theme.py gelezen - wijzig je iets via Kleuren "
         "kiezen, klik dan hier op 'Opnieuw genereren en openen' om de pagina te verversen. "
         "Welk venster welk veldnaam gebruikt (de indeling van de pagina) is met de hand "
         "bijgehouden en verandert alleen als de suite zelf wijzigt."),
    ]
    if maak_header:
        maak_header(win, "Kleurenoverzicht", help_hoofdstukken=KLEURENOVERZICHT_HELP,
                    kleur=ACCENT_PINAS)
    else:
        tk.Label(win, text="Kleurenoverzicht", font=("Segoe UI", 14, "bold"),
                 bg=BG, fg=ACCENT_PINAS).pack(anchor="w", padx=16, pady=(14, 4))

    status_label = tk.Label(
        win, text="Bezig met genereren...", font=("Segoe UI", 10),
        bg=BG, fg=DIM, anchor="w", wraplength=480, justify="left")
    status_label.pack(fill="x", padx=16, pady=(4, 2))

    tk.Label(win, text="Kleurwaarden worden live uit Gedeeld\\pinas_theme.py gelezen bij elke "
                        "keer genereren - deze pagina kan dus nooit meer verouderen zoals de "
                        "eerdere, eenmalige versie.",
             font=("Segoe UI", 8), bg=BG, fg=DIM, wraplength=480,
             justify="left").pack(fill="x", padx=16, pady=(0, 10))

    knoppen = tk.Frame(win, bg=BG)
    knoppen.pack(fill="x", padx=16, pady=12, side="bottom")

    def _genereren_klik():
        try:
            pad = genereer_en_open()
            status_label.config(
                text=f"Gegenereerd en geopend in de browser.\n{pad}", fg=OK_C)
        except Exception as e:
            status_label.config(text=f"Genereren mislukt: {e}", fg=ERR_C)
            messagebox.showerror("Genereren mislukt", str(e))

    if maak_knop:
        opnieuw_knop = maak_knop(knoppen, "Opnieuw genereren en openen", _genereren_klik,
                                  stijl="primair", kleur=ACCENT_PINAS)
        opnieuw_knop.pack(side="left", padx=(0, 8))
        sluit_knop = maak_knop(knoppen, "Sluiten", win.destroy, stijl="secundair")
        sluit_knop.pack(side="left")
    else:
        tk.Button(knoppen, text="Opnieuw genereren en openen",
                  command=_genereren_klik).pack(side="left", padx=(0, 8))
        tk.Button(knoppen, text="Sluiten", command=win.destroy).pack(side="left")

    # Meteen bij het openen 1x genereren+openen - dat was expliciet de vraag
    # ("een los programma dat dat wel doet" i.p.v. zelf steeds op een knop
    # te moeten klikken).
    win.after(50, _genereren_klik)

    win.mainloop()


if __name__ == "__main__":
    main()
