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
  ACCENT_PINAS     blauw   - kern/algemeen: Verbinden, Installatie & Herstel,
                             Onderhoud, Publicatie/Distributie-acties.
  ACCENT_PIBACKUP  groen   - alles rond Backup Beheer/Sync/PC Image Backup
                             (ook al gebruikt in pinas_image_backup.pyw).
  ACCENT_PIADDONS  amber   - Addons Beheer en de add-on-schermen erachter.
  ACCENT_PICONTROL paars   - spaarzaam: alleen branding/vensterkoppen van
                             Pi NAS Menu zelf, NIET meer voor gewone knoppen
                             (3x identiek paars naast elkaar was té veel).
Elke knop/sectiekop in de suite hoort een van deze vier te gebruiken (of
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
# ---------------------------------------------------------------------------
_DONKER = dict(
    BG="#232a33", PANEL="#2b333d", PANEL2="#33404c",
    FG="#eef2f6", DIM="#9aa8b5",
    OK_C="#22c55e", ERR_C="#ef4444", WARN="#f59e0b", YELLOW="#fbbf24",
    DESTRUCTIEF="#e2875e",
    ACCENT_PINAS="#4f8fdb", ACCENT_PIBACKUP="#2fb787",
    ACCENT_PIADDONS="#dba53f", ACCENT_PICONTROL="#9480e0",
    BLUE="#4f8fdb", GREEN_C="#2fb787", GREEN="#2fb787", RED_C="#ef4444",
    RED="#ef4444", TEAL="#14b8a6", MAGENTA="#9480e0", ACCENT="#4f8fdb",
)

_LICHT = dict(
    BG="#e9edf2", PANEL="#dae2ea", PANEL2="#bed0dd",
    FG="#333c47", DIM="#6d7d8c",
    OK_C="#16a34a", ERR_C="#dc2626", WARN="#d97706", YELLOW="#c98a2a",
    DESTRUCTIEF="#d9704a",
    ACCENT_PINAS="#0f8a8a", ACCENT_PIBACKUP="#3573c4",
    ACCENT_PIADDONS="#c98a2a", ACCENT_PICONTROL="#7c5cd6",
    BLUE="#0f8a8a", GREEN_C="#3573c4", GREEN="#3573c4", RED_C="#dc2626",
    RED="#dc2626", TEAL="#0d9488", MAGENTA="#7c5cd6", ACCENT="#0f8a8a",
)

_thema = _lees_thema()
_palet = _DONKER if _thema == "donker" else _LICHT

globals().update(_palet)

HUIDIG_THEMA = _thema
