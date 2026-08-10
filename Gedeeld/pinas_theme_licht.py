"""
Pi NAS Suite - Kleurenthema (Lichte modus) - VEROUDERD, niet meer gebruikt.

16 juli 2026: dit bestand deed voorheen dienst als "override" die stilletjes
voorrang kreeg boven pinas_theme.py - en raakte daardoor uit sync (nog het
oude palet, terwijl pinas_theme.py al was bijgewerkt). Dat was de echte
oorzaak van een reeks kleur-mismatches. pinas_theme.py is nu de ENIGE bron
van waarheid voor kleuren in de hele suite; dit bestand bestaat alleen nog
voor het geval iets het rechtstreeks importeert, en verwijst kaal door.

Wijzig kleuren voortaan alleen in Gedeeld\\pinas_theme.py.
"""

from pinas_theme import *  # noqa: F401,F403
