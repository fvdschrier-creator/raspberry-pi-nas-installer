"""
Pi NAS Suite - Centraal kleurenthema
Importeer in elk programma met: from pinas_theme import *

Het thema wordt bepaald door 'thema' in picontrol.cfg:
  thema = licht    (standaard)
  thema = donker

Wijzig via Pi NAS Menu -> Onderhoud -> Weergave -> Thema wisselen.
Een herstart van het programma is vereist na wijziging.

16 juli 2026, herzien: dit bestand is nu de ENIGE plek waar kleuren worden
gedefinieerd voor de hele suite (op verzoek van Frans: "1 thema voor de
hele suite, geen hardcoded kleuren"). Eerder bestond er ook nog een
"override"-mechanisme via de losse bestanden pinas_theme_donker.py /
pinas_theme_licht.py, die stilletjes voorrang kregen op de waarden
hieronder. Dat bleek het echte probleem achter een hele reeks kleur-
mismatches deze sessie: die losse bestanden waren allang niet meer
bijgewerkt (o.a. nog het oude donkere marineblauw BG="#1e2d3d" en een
feller paars) en overschreven zonder waarschuwing wat hier stond. Die
twee bestanden zijn nu omgezet naar kale re-exports van DIT bestand
("from pinas_theme import *") zodat zoiets structureel niet meer kan
gebeuren - er is nu precies 1 plek om kleuren te wijzigen.

CATEGORIE-ACCENTEN - het systeem achter de knopkleuren in de hele suite:
  ACCENT_PINAS     blauwgroen (teal) - Verbinden op het hoofdmenu, en de
                             algemene Status & Details-schermen.
  ACCENT_PIBACKUP  blauw   - alles rond Backup Beheer/Sync/PC Image Backup
                             (ook al gebruikt in pinas_image_backup.pyw).
  ACCENT_PIADDONS  amber   - Addons Beheer en de add-on-schermen erachter.
  ACCENT_PIBEHEER  roze/bes - Beheer op het hoofdmenu EN de 3 schermen
                             erachter (Installatie & Herstel, Controles,
                             Onderhoud) - elk scherm krijgt een eigen tint
                             (ACCENT_PIBEHEER/_2/_3, zie tint() hieronder)
                             i.p.v. alle 3 dezelfde kale ACCENT_PIBEHEER.
                             NIEUW, 13 augustus 2026: loste op dat Verbinden
                             en heel Beheer voorheen dezelfde ACCENT_PINAS
                             deelden en dus visueel niet te onderscheiden
                             waren (Frans: "een groen moeras").
  ACCENT_PICONTROL paars   - spaarzaam: alleen branding/vensterkop van
                             Pi NAS Menu zelf, NIET voor gewone knoppen
                             (3x identiek paars naast elkaar was té veel).
(13 augustus 2026: de labels hierboven zijn nu ook daadwerkelijk correct -
ze klopten eerder niet met de werkelijke hex-waarden, bijv. ACCENT_PINAS
heette "blauw" maar was al een tijd een blauwgroene teal.)
Elke knop/sectiekop in de suite hoort een van deze vijf te gebruiken (of
DESTRUCTIEF/WARN/ERR_C voor hun eigen specifieke betekenis) - nooit een
losse hex-code direct in een .pyw-bestand.

16 juli 2026: BTN, KV_BG en alle C_* (C_BG/C_CARD/C_DARK/C_BORDER/C_SEL/
C_TEXT/C_MUTED/C_BLUE/C_BLUE_D/C_GREEN/C_ORANGE/C_RED) verwijderd - dit
waren vestigiale RGBA-waarden (0-1 formaat, typisch Kivy) uit de oude
Kivy-versie van PiBackup en werden nergens meer geimporteerd of gebruikt.
"""

import os as _os
import configparser as _cp


def _lees_thema():
    """Bepaal thema op basis van picontrol.cfg - standaard licht."""
    _script = _os.path.abspath(__file__)
    _gedeeld = _os.path.dirname(_script)
    _picontrol = _os.path.normpath(_os.path.join(_gedeeld, "..", "Beheer", "picontrol.cfg"))
    if _os.path.exists(_picontrol):
        cfg = _cp.ConfigParser()
        try:
            cfg.read(_picontrol, encoding="utf-8")
            return cfg.get("ui", "thema", fallback="licht").strip().lower()
        except Exception:
            return "licht"
    return "licht"


# ---------------------------------------------------------------------------
# DE paletten - enige bron van waarheid voor de hele suite (zie docstring).
# "Zacht zakelijk blauw", 16 juli 2026 herzien: iets steviger/frisser dan de
# eerste zachte versie (op verzoek van Frans), maar nadrukkelijk niet
# terug richting het oude donkere marineblauw/militaire palet.
# 13 augustus 2026 (4e ronde): in _DONKER stonden ACCENT_PINAS (blauw) en
# ACCENT_PIBACKUP (groen) verwisseld t.o.v. _LICHT (waar PINAS teal/
# blauwgroen is en PIBACKUP blauw) - Verbinden en Backup Beheer ruilden dus
# letterlijk van kleur zodra je van thema wisselde. Rechtgetrokken: PINAS
# gebruikt nu dezelfde teal als de (voorheen ongebruikte) TEAL-alias,
# PIBACKUP het blauw dat eerst per ongeluk bij PINAS stond.
# 15 augustus 2026 ("Optie B"): ACCENT_PINAS en ACCENT_PIADDONS (en hun
# aliassen TEAL/BLUE/ACCENT) waren in het donkere thema te fel/licht om
# nog voldoende contrast te geven tegen de standaard witte knoptekst
# (respectievelijk 2.49:1 en 2.26:1 - ruim onder zelfs de losse 3:1
# ondergrens voor UI-componenten). Eerder al besproken: die kleuren
# gewoon donkerder maken (Optie A) zou het "frisse" verzadigde effect
# juist weer dempen - precies de klacht van Frans ("de kleuren ogen niet
# fris, allemaal wat afgevlakte kleuren"). In plaats daarvan (Optie B):
# de kleur zelf mag fris/verzadigd blijven (zelfs iets feller dan
# hiervoor), en de KNOPTEKST wisselt automatisch naar een donkere tint
# uit dezelfde kleurfamilie zodra wit niet meer genoeg contrast geeft -
# zie leesbare_tekstkleur() hieronder, die dit voor elke kleur in de
# suite automatisch bepaalt (dus ook blijft werken als deze kleuren later
# via de kleurenkiezer worden gewijzigd).
# ---------------------------------------------------------------------------
_DONKER = dict(
    BG="#232a33", PANEL="#2b333d", PANEL2="#33404c",
    FG="#eef2f6", DIM="#9aa8b5",
    OK_C="#22c55e", ERR_C="#ef4444", WARN="#f59e0b", YELLOW="#fbbf24",
    DESTRUCTIEF="#e2875e",
    ACCENT_PINAS="#09d7bf", ACCENT_PIBACKUP="#3185e9",
    ACCENT_PIADDONS="#f9a60b", ACCENT_PICONTROL="#9480e0",
    ACCENT_PIBEHEER="#e0668a",
    BLUE="#09d7bf", GREEN_C="#3185e9", GREEN="#3185e9", RED_C="#ef4444",
    RED="#ef4444", TEAL="#09d7bf", MAGENTA="#9480e0", ACCENT="#09d7bf",
)

_LICHT = dict(
    BG="#e9edf2", PANEL="#dae2ea", PANEL2="#bed0dd",
    FG="#333c47", DIM="#6d7d8c",
    OK_C="#16a34a", ERR_C="#dc2626", WARN="#d97706", YELLOW="#c98a2a",
    DESTRUCTIEF="#d9704a",
    ACCENT_PINAS="#038787", ACCENT_PIBACKUP="#206ac9",
    ACCENT_PIADDONS="#c07c15", ACCENT_PICONTROL="#7c5cd6",
    ACCENT_PIBEHEER="#c0392b",
    BLUE="#038787", GREEN_C="#206ac9", GREEN="#206ac9", RED_C="#dc2626",
    RED="#dc2626", TEAL="#0d9488", MAGENTA="#7c5cd6", ACCENT="#038787",
)

_thema = _lees_thema()
_palet = _DONKER if _thema == "donker" else _LICHT


def _relatieve_luminantie(hex_c):
    """WCAG relatieve luminantie van een hex-kleur (0.0-1.0) - basis voor
    contrast(). Zelfde formule als gebruikt bij het samenstellen van de
    kleurenkiezer-stalen (13-15 augustus 2026)."""
    h = hex_c.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

    def _kanaal(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = _kanaal(r), _kanaal(g), _kanaal(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(hex_a, hex_b):
    """WCAG-contrastverhouding tussen twee hex-kleuren (1.0-21.0)."""
    la, lb = _relatieve_luminantie(hex_a), _relatieve_luminantie(hex_b)
    lichter, donkerder = max(la, lb), min(la, lb)
    return (lichter + 0.05) / (donkerder + 0.05)


def leesbare_tekstkleur(bg_hex, donker_hex=None, minimum=3.0):
    """Kiest een leesbare tekstkleur voor een knop/label met bg_hex als
    achtergrond ("Optie B", 15 augustus 2026): wit zolang dat voldoende
    contrast geeft, anders een donkere tint UIT DEZELFDE KLEURFAMILIE
    (dus geen kaal zwart) - zodat een accentkleur zelf fris/verzadigd kan
    blijven zonder de tekst onleesbaar te maken. Werkt voor elke kleur in
    de suite, dus ook nog correct als een accentkleur later via de
    kleurenkiezer wordt gewijzigd - er hoeft dan nergens los tekstkleur-
    aangepast te worden.

    donker_hex: vaste donkere tekstkleur voor kleuren die daar al bewust
    een eigen keuze voor hebben (bijv. DESTRUCTIEF, dat al "#3d2604"
    gebruikte voordat deze functie bestond) - wordt dan gebruikt i.p.v.
    een automatisch berekende donkere familietint.
    minimum: gewenste contrastdrempel. Standaard 3.0:1 - de drempel voor
    "grote tekst"/UI-componenten (WCAG), en ook de drempel die de rest
    van de suite dit weekend al aanhield bij het beoordelen van de
    kleurenkiezer-stalen. Bewust NIET 4.5:1 (AA voor gewone lopende
    tekst): dat zou ook de al goedwerkende lichte-thema-knoppen onnodig
    van witte naar donkere tekst laten omslaan. Geef hier 4.5 expliciet
    mee voor tekst die niet vetgedrukt knoplabel-formaat is."""
    if contrast(bg_hex, "#ffffff") >= minimum:
        return "#ffffff"
    if donker_hex:
        return donker_hex
    import colorsys
    h = bg_hex.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    hue, _, sat = colorsys.rgb_to_hls(r, g, b)
    sat = min(sat, 0.55)
    for lichtheid in range(28, -1, -1):
        r2, g2, b2 = colorsys.hls_to_rgb(hue, lichtheid / 100.0, sat)
        kandidaat = f"#{round(r2*255):02x}{round(g2*255):02x}{round(b2*255):02x}"
        if contrast(bg_hex, kandidaat) >= minimum:
            return kandidaat
    return "#1a1a1a"


def tint(hex_c, amt=24):
    """Lichtere variant van een kleur (RGB-kanalen ophogen, geclipt op 255).
    Gedeelde versie van wat eerder als _licht_tint() los in Pi_NAS_Menu.pyw
    stond - hier neergezet (13 augustus 2026, kleurenherziening Beheer-
    domein) zodat elk bestand dezelfde tint-berekening gebruikt i.p.v. een
    eigen kopie te onderhouden."""
    h = hex_c.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"#{min(r+amt,255):02x}{min(g+amt,255):02x}{min(b+amt,255):02x}"


def kleurvariant(hex_c, tint_graden=0, licht_delta=0.0):
    """Draait de tint (kleurtoon) een aantal graden en verhoogt de
    lichtheid - gebruikt voor de Beheer-subtinten (ACCENT_PIBEHEER_2/_3).

    13 augustus 2026: eerst geprobeerd met alleen tint() (rechtstreeks
    lichter maken) - Frans, na een 2e screenshot: "het kleurverschil
    binnen Beheer mag iets groter, anders is het effect te gering". Alleen
    lichter maken loopt echter snel tegen een plafond (te lichter = te
    dicht bij wit = te weinig contrast met de witte knoptekst). Een kleine
    tint-draai (dezelfde kleurFAMILIE, net een andere kant op het
    kleurenwiel) geeft een veel duidelijker onderscheid bij hetzelfde
    contrastniveau."""
    import colorsys
    h = hex_c.lstrip("#")
    r, g, b = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    hh, l, s = colorsys.rgb_to_hls(r, g, b)
    hh = (hh + tint_graden / 360.0) % 1.0
    l = max(0.0, min(1.0, l + licht_delta))
    r, g, b = colorsys.hls_to_rgb(hh, l, s)
    return f"#{round(r*255):02x}{round(g*255):02x}{round(b*255):02x}"


# ACCENT_PIBEHEER_2/_3: automatisch afgeleide varianten van ACCENT_PIBEHEER
# (kleine tint-draai + iets lichter, zie kleurvariant() hierboven) - geven
# de 3 Beheer-subknoppen (Installatie & Herstel/Controles/Onderhoud) elk
# hun eigen, duidelijk te onderscheiden kleur uit dezelfde familie, zonder
# dat iemand 2 extra kleuren met de hand hoeft te kiezen/synchroniseren. Bij
# een gewijzigde ACCENT_PIBEHEER (via de kleurenkiezer) worden deze bij de
# eerstvolgende start automatisch opnieuw berekend.
_beheer_deltas = (-18, 0.06, 18, 0.13) if _thema != "donker" else (-18, 0.05, 18, 0.10)
_palet["ACCENT_PIBEHEER_2"] = kleurvariant(_palet["ACCENT_PIBEHEER"], _beheer_deltas[0], _beheer_deltas[1])
_palet["ACCENT_PIBEHEER_3"] = kleurvariant(_palet["ACCENT_PIBEHEER"], _beheer_deltas[2], _beheer_deltas[3])

globals().update(_palet)

HUIDIG_THEMA = _thema
