"""
Gedeeld/pinas_addon_scripts.py

Centrale, ENIGE plek voor de addon-sleutel -> scriptbestandsnaam-mapping
(bijv. "dashboard" -> "pinas_dashboard.sh").

13 augustus 2026 (Frans, verbeterpunt #1 uit een eerlijke lijst met
verbeterpunten): deze dict stond apart onderhouden in 3 bestanden
(Addons/pinas_addons_beheer.pyw, Beheer/Pi_NAS_Menu.pyw,
Beheer/NAS_Map_Beheer.pyw) - met bekende historische inconsistenties.
Zelfde probleem, zelfde aanpak als Gedeeld/pinas_pi_status.py (4 augustus
2026) al toepaste voor de SSH-statuschecks: 1 gedeelde bron i.p.v. 3 losse
kopieen die uit elkaar groeien.

Concreet gat dat deze centralisatie meteen oploste: Pi_NAS_Menu.pyw en
NAS_Map_Beheer.pyw misten de "dashboard"-regel (die stond alleen in
pinas_addons_beheer.pyw). Gevolg in Pi_NAS_Menu.pyw:
_lokale_addon_hash("dashboard") gaf altijd None terug (ADDON_SCRIPT.get()
vond de sleutel niet), waardoor de "Pi draait een andere versie dan het
lokale bestand"-waarschuwing voor de Dashboard-add-on nooit kon afgaan,
ook al leest de rest van die functie (regel ~1453) dashboard wel degelijk
mee. Met de centrale lijst hieronder werkt die check nu ook voor Dashboard.

Gebruik (per aanroepend bestand, nadat Gedeeld op sys.path staat):
    import pinas_addon_scripts
    naam = pinas_addon_scripts.ADDON_SCRIPT.get(addon_key)

Nieuwe addon toevoegen? 1x hier toevoegen, alle 3 aanroepers (en
Gedeeld/controleer_documentatie_consistentie.py) zien het vanzelf.
"""

ADDON_SCRIPT = {
    "nextcloud": "pinas_nextcloud.sh",
    "pihole": "pinas_pihole.sh",
    "zerotier": "pinas_zerotier.sh",
    "vaultwarden": "pinas_vaultwarden.sh",
    "printer": "pinas_printer.sh",
    "dashboard": "pinas_dashboard.sh",
}
