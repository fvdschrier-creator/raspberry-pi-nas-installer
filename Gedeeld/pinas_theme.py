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
# ---------------------------------------------------------------------------
_DONKER = dict(
    BG="#232a33", PANEL="#2b333d", PANEL2="#33404c",
    FG="#eef2f6", DIM="#9aa8b5",
    OK_C="#22c55e", ERR_C="#ef4444", WARN="#f59e0b", YELLOW="#fbbf24",
    DESTRUCTIEF="#e2875e",
    ACCENT_PINAS="#14b8a6", ACCENT_PIBACKUP="#3185e9",
    ACCENT_PIADDONS="#e79e15", ACCENT_PICONTROL="#9480e0",
    ACCENT_PIBEHEER="#e0668a",
    BLUE="#14b8a6", GREEN_C="#3185e9", GREEN="#3185e9", RED_C="#ef4444",
    RED="#ef4444", TEAL="#14b8a6", MAGENTA="#9480e0", ACCENT="#14b8a6",
)

_LICHT = dict(
    BG="#e9edf2", PANEL="#dae2ea", PANEL2="#bed0dd",
    FG="#333c47", DIM="#6d7d8c",
    OK_C="#16a34a", ERR_C="#dc2626", WARN="#d97706", YELLOW="#c98a2a",
    DESTRUCTIEF="#d9704a",
    ACCENT_PINAS="#038787", ACCENT_PIBACKUP="#206ac9",
    ACCENT_PIADDONS="#c07c15", ACCENT_PICONTROL="#7c5cd6",
    ACCENT_PIBEHEER="#c2456b",
    BLUE="#038787", GREEN_C="#206ac9", GREEN="#206ac9", RED_C="#dc2626",
    RED="#dc2626", TEAL="#0d9488", MAGENTA="#7c5cd6", ACCENT="#038787",
)

_thema = _lees_thema()
_palet = _DONKER if _thema == "donker" else _LICHT


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
