"""
Pi NAS Suite - Kleurenthema (Donkere modus) - VEROUDERD, niet meer gebruikt.

16 juli 2026: dit bestand deed voorheen dienst als "override" die stilletjes
voorrang kreeg boven pinas_theme.py - en raakte daardoor uit sync (nog het
oude donkere marineblauw BG="#1e2d3d" en een feller paars, terwijl
pinas_theme.py allang was bijgewerkt naar het nieuwe "zacht zakelijk"
palet). Dat was de echte oorzaak van een reeks kleur-mismatches deze
sessie. pinas_theme.py is nu de ENIGE bron van waarheid voor kleuren in de
hele suite; dit bestand bestaat alleen nog voor het geval iets het
rechtstreeks importeert, en verwijst kaal door.

Wijzig kleuren voortaan alleen in Gedeeld\\pinas_theme.py.
"""

from pinas_theme import *  # noqa: F401,F403
