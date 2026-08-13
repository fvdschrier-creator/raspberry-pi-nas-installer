"""
Pi NAS Sync - kleuren

Pi NAS Sync leunt op het centrale suite-thema (Gedeeld/pinas_theme.py), zodat
het meekleurt met donker/licht zoals ingesteld via het Pi NAS Menu
(Beheer -> Instellingen -> Thema wisselen). Net als bij het menu is een
herstart van Pi NAS Sync nodig nadat het thema gewijzigd is.

Kan het thema niet geladen worden (bijvoorbeeld een losse Starter Kit zonder
de map Gedeeld), dan vallen we terug op de oorspronkelijke lichte palette.
Zo crasht Pi NAS Sync nooit op een ontbrekend thema - dezelfde aanpak als de
ingebouwde fallback elders in de suite.

De namen hieronder zijn die van Pi NAS Sync zelf; de waarden komen uit het
thema. Importeer met: from core.thema import *   (of from thema import *)
"""

import os as _os
import sys as _sys


def _voeg_gedeeld_toe_aan_pad():
    """Zet C:\\PiNAS\\Gedeeld op sys.path zodat pinas_theme importeerbaar is."""
    hier = _os.path.dirname(_os.path.abspath(__file__))      # ...\PiBackup\core
    kandidaten = [
        _os.path.normpath(_os.path.join(hier, "..", "..", "Gedeeld")),  # C:\PiNAS\Gedeeld
        _os.path.join("C:\\", "PiNAS", "Gedeeld"),
    ]
    for pad in kandidaten:
        if _os.path.isdir(pad) and pad not in _sys.path:
            _sys.path.insert(0, pad)


_THEMA_GELADEN = False
HUIDIG_THEMA = "fallback-licht"

try:
    _voeg_gedeeld_toe_aan_pad()
    import pinas_theme as _t   # leest zelf [ui] thema uit picontrol.cfg

    # -- Basis ----------------------------------------------------------------
    BG            = _t.BG          # hoofdachtergrond
    PANEL         = _t.PANEL       # paneel-achtergrond
    PANEL_RAND    = _t.PANEL2      # subtiele paneelrand
    TEKST         = _t.FG          # primaire tekst
    TEKST_DIM     = _t.DIM         # secundaire tekst
    # 13 augustus 2026: was _t.BLUE (= Verbinden/ACCENT_PINAS-kleur) - Pi NAS
    # Sync opent vanuit Backup Beheer, dus hoort ACCENT_PIBACKUP te tonen
    # (Frans: "de sub sub menu's moeten ook de kleur van het thema meekrijgen
    # in de titel, gebeurt nu niet").
    ACCENT        = _t.ACCENT_PIBACKUP   # header en primaire knoppen
    ACCENT_DONKER = _t.ACCENT_PIBACKUP   # actief/ingedrukt (zelfde kleur)
    GROEN         = _t.OK_C        # OK / succes
    ROOD          = _t.ERR_C       # fout / stoppen
    ORANJE        = _t.WARN        # waarschuwing

    # -- Zachte vlakken (status-/reparatiebalken, logvensters) ----------------
    BG_ZACHT      = _t.PANEL2      # lichte balken (was #eef2f7)
    LOG_BG        = _t.PANEL       # activiteit-log achtergrond (was #fafbfc)
    LOG_BG_AFW    = _t.PANEL       # afwijkingen-log achtergrond (was #fffaf5)
    ORANJE_ZACHT  = _t.PANEL2      # vlak van het oranje image-paneel (was #fff4e8)

    HUIDIG_THEMA = getattr(_t, "HUIDIG_THEMA", "?")
    _THEMA_GELADEN = True
except Exception:
    # -- Fallback: oorspronkelijke lichte palette (identiek aan voorheen) ------
    BG            = "#f4f6f9"
    PANEL         = "#ffffff"
    PANEL_RAND    = "#d6dce5"
    TEKST         = "#1c2733"
    TEKST_DIM     = "#5b6b7d"
    ACCENT        = "#1d5fd1"
    ACCENT_DONKER = "#15469e"
    GROEN         = "#1a7d3a"
    ROOD          = "#c2293a"
    ORANJE        = "#b3650f"
    BG_ZACHT      = "#eef2f7"
    LOG_BG        = "#fafbfc"
    LOG_BG_AFW    = "#fffaf5"
    ORANJE_ZACHT  = "#fff4e8"
    HUIDIG_THEMA  = "fallback-licht"

# Vaste kleuren die in beide thema's werken (staan altijd op de blauwe header
# of op een gekleurde knop, dus thema-onafhankelijk):
SUBTITEL       = "#dce8fb"   # lichtblauwe ondertitel op de blauwe header
DISABLED_TEKST = "#9aa5b1"   # grijze tekst van uitgeschakelde knoppen
KNOP_TEKST     = "white"     # tekst op gekleurde knoppen
