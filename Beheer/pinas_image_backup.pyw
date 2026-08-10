#!/usr/bin/env python3
"""
Pi NAS Suite - PC Image Backup (volledige systeemkopie)

Losstaand programma, losgekoppeld van PiNAS Sync op verzoek van Frans
(12 juli 2026): PC Image Backup hoorde conceptueel niet bij synchronisatie
en stond op een plek waar je het niet meteen zou verwachten. De logica
(core/image_backup.py) was al UI-onafhankelijk opgezet, dus dit is vooral
een verplaatsing van het scherm zelf - de backup-logica is ongewijzigd
overgenomen uit pinas_sync_app.pyw's ImageBackupScherm.

Hoort thuis in: Beheer\\pinas_image_backup.pyw, met Beheer\\core\\image_backup.py

Gebruik: python pinas_image_backup.pyw
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import messagebox

# -- Gedeeld op het pad zetten voor pinas_theme en pinas_ui --------------
_gedeeld = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Gedeeld")
if os.path.isdir(_gedeeld) and _gedeeld not in sys.path:
    sys.path.insert(0, os.path.abspath(_gedeeld))

from pinas_theme import BG, PANEL, PANEL2, FG, DIM, OK_C, ERR_C, WARN, ACCENT_PIBACKUP
from pinas_ui import maak_header, maak_sectie

from core import image_backup as ib

try:
    from version import BIJGEWERKT
except ImportError:
    BIJGEWERKT = "onbekende datum"

try:
    import pinas_schijven
except ImportError:
    pinas_schijven = None


def _backup_letter():
    """Geeft de werkelijke, huidige stationsletter voor de Backup-share
    terug (i.p.v. altijd 'Z' aan te nemen als standaard-doelmap) - zelfde
    aanpak als elders in de suite (9 augustus 2026)."""
    if pinas_schijven is None:
        return "Z"
    try:
        return pinas_schijven.vind_letter_of_terugval("Backup", "Z")
    except Exception:
        return "Z"

# -- Kleuren-aliassen - zelfde namen als de oorspronkelijke ImageBackupScherm
# in pinas_sync_app.pyw, nu gevoed door pinas_theme in plaats van core.thema,
# zodat dit scherm automatisch meekleurt met het licht/donker-thema net als
# de rest van de suite. De logica hieronder is verder ongewijzigd overgenomen.
TEKST = FG
TEKST_DIM = DIM
GROEN = OK_C
ROOD = ERR_C
ORANJE = WARN
BG_ZACHT = PANEL2
ORANJE_ZACHT = PANEL2
LOG_BG = PANEL
PANEL_RAND = PANEL2
KNOP_TEKST = "#ffffff"
DISABLED_TEKST = DIM
ACCENT = ACCENT_PIBACKUP

FONT_NAAM    = "Segoe UI"
FONT_NORMAAL = (FONT_NAAM, 10)
FONT_KLEIN   = (FONT_NAAM, 9)
FONT_VET     = (FONT_NAAM, 10, "bold")
FONT_TITEL   = (FONT_NAAM, 14, "bold")
FONT_MONO    = ("Consolas", 9)


class RondeKnop(tk.Button):
    """Standaardknop met consistente stijl - zelfde als in pinas_sync_app.pyw."""
    def __init__(self, ouder, tekst, kleur=ACCENT, tekstkleur=KNOP_TEKST, **kw):
        super().__init__(
            ouder, text=tekst, font=FONT_VET, bg=kleur, fg=tekstkleur,
            activebackground=kleur, activeforeground=tekstkleur,
            relief="flat", padx=16, pady=9, cursor="hand2",
            disabledforeground=DISABLED_TEKST, **kw)


class Paneel(tk.Frame):
    """Paneel met subtiele rand - herbruikbare bouwsteen."""
    def __init__(self, ouder, **kw):
        super().__init__(ouder, bg=PANEL, highlightbackground=PANEL_RAND,
                         highlightthickness=1, **kw)


class ImageBackupVenster(tk.Tk):
    """PC Image Backup als eigen, zelfstandig venster (was eerder scherm 3
    binnen PiNAS Sync). Terug-knop sluit dit venster - Backup Beheer blijft
    intussen gewoon open op de achtergrond."""

    def __init__(self):
        super().__init__()
        self.title(f"PiNAS - PC Image Backup (bijgewerkt: {BIJGEWERKT})")
        self.geometry("1180x860")
        self.configure(bg=BG)
        self.minsize(1000, 700)

        self._checks_resultaat = None
        self._achtergrond_actief = True
        # 5 augustus 2026 (Frans: Terug-knop overal weg): _terug() stopte
        # ook het achtergrondwerk, niet alleen het venster sluiten - dat
        # gedrag blijft nu gekoppeld aan het sluiten via de X-knop, i.p.v.
        # verloren te gaan met de Terug-knop.
        self.protocol("WM_DELETE_WINDOW", self._terug)

        maak_header(self, "PC Image Backup",
                    subtekst="Volledige systeemkopie", kleur=ACCENT_PIBACKUP)
        self._build()

        # Fase C (heropstart-detectie): eenmalig bij opstarten van dit
        # programma - zelfde reden als voorheen in PiNasSyncVenster: als dit
        # bij elk bezoek opnieuw zou draaien, zou een ECHT lopende backup
        # door een mislukte detectie ten onrechte kunnen worden afgebroken.
        # Nu is dit sowieso enkel, want dit programma heeft maar dit scherm.
        self._opstart_log_bestand = os.path.join(
            os.environ.get("TEMP", "."), "pinas_image_backup_opstart.log")
        ib.controleer_bij_opstart(on_log=self._log_opstart_controle)

    def _log_opstart_controle(self, tekst, niveau):
        try:
            with open(self._opstart_log_bestand, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] [{niveau}] {tekst}\n")
        except Exception:
            pass

    def stop_achtergrondwerk(self):
        self._achtergrond_actief = False

    def _terug(self):
        self.stop_achtergrondwerk()
        self.destroy()

    def _build(self):
        uitleg = tk.Frame(self, bg=BG_ZACHT)
        uitleg.pack(fill="x")
        tk.Label(uitleg,
                text="Dit maakt een VOLLEDIGE kopie van station C: (inclusief de "
                     "EFI-partitie) - GEEN System Restore-herstelpunt. Terugzetten "
                     "gaat via de Windows-herstelomgeving: Geavanceerde opties -> "
                     "SYSTEEMKOPIE HERSTELLEN (niet 'Systeemherstel' - dat is een "
                     "ander, lichter menu-item dat alleen systeembestanden herstelt). "
                     "Na een succesvolle backup wordt een leesbaar instructiebestand "
                     "in de backupmap zelf gezet, zodat de uitleg er nog is op het "
                     "moment dat je hem echt nodig hebt.",
                font=FONT_KLEIN, bg=BG_ZACHT, fg=TEKST_DIM, wraplength=1000,
                justify="left").pack(anchor="w", padx=16, pady=8)

        midden = tk.PanedWindow(self, orient="horizontal", bg=BG,
                                sashwidth=6, sashrelief="flat")
        midden.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        links = tk.Frame(midden, bg=BG, width=420)
        midden.add(links, minsize=360)
        self._bouw_linkerkolom(links)

        rechts = tk.Frame(midden, bg=BG)
        midden.add(rechts, minsize=400)
        self._bouw_logpaneel(rechts)

    def _bouw_linkerkolom(self, ouder):
        voorbereiding_paneel = tk.Frame(
            ouder, bg=ORANJE_ZACHT, highlightbackground=ORANJE, highlightthickness=1)
        voorbereiding_paneel.pack(fill="x", pady=(0, 10))
        tk.Label(voorbereiding_paneel, text="VOORBEREIDING - eenmalig, voor er iets misgaat",
                 font=FONT_VET, bg=ORANJE_ZACHT, fg=ORANJE).pack(anchor="w", padx=14, pady=(12, 4))
        tk.Label(voorbereiding_paneel,
                text="Als de PC niet meer opstart, heb je een ZELF GEMAAKTE "
                     "herstel-USB nodig om bij deze backup te kunnen - die kun "
                     "je dan niet meer maken. Maak deze nu, op een werkende PC, "
                     "en test eenmalig of er vanaf gestart kan worden.",
                font=FONT_KLEIN, bg=ORANJE_ZACHT, fg=TEKST, wraplength=380,
                justify="left").pack(anchor="w", padx=14, pady=(0, 8))
        RondeKnop(voorbereiding_paneel, "Herstelschijf maken + noodkaartje erop",
                 kleur=ORANJE, command=self._maak_herstelschijf_en_kaartje).pack(
                     fill="x", padx=14, pady=(0, 8))

        tk.Label(voorbereiding_paneel,
                text="Start de Windows-wizard voor een herstel-USB. Zodra je die "
                     "wizard afrondt (of sluit), wordt automatisch gevraagd waar "
                     "de stick staat, zodat het noodkaartje (netwerkpad + "
                     "gebruikersnaam) er meteen op gezet kan worden - voordat je "
                     "het kan vergeten.",
                font=FONT_KLEIN, bg=ORANJE_ZACHT, fg=TEKST_DIM, wraplength=380,
                justify="left").pack(anchor="w", padx=14, pady=(0, 6))
        RondeKnop(voorbereiding_paneel, "Alleen noodkaartje opslaan (stick al gemaakt)",
                 kleur=PANEL, tekstkleur=TEKST,
                 highlightbackground=PANEL_RAND, highlightthickness=1,
                 command=self._sla_noodkaartje_op).pack(fill="x", padx=14, pady=(0, 8))
        RondeKnop(voorbereiding_paneel, "Structuur van de herstelschijf controleren",
                 kleur=PANEL, tekstkleur=TEKST,
                 highlightbackground=PANEL_RAND, highlightthickness=1,
                 command=self._controleer_herstelschijf).pack(fill="x", padx=14, pady=(0, 12))

        doel_paneel = Paneel(ouder)
        doel_paneel.pack(fill="x", pady=(0, 10))
        tk.Label(doel_paneel, text="Doelmap", font=FONT_VET,
                 bg=PANEL, fg=TEKST).pack(anchor="w", padx=14, pady=(12, 6))
        doel_rij = tk.Frame(doel_paneel, bg=PANEL)
        doel_rij.pack(fill="x", padx=14, pady=(0, 6))
        self.doel_var = tk.StringVar(value=f"{_backup_letter()}:\\")
        tk.Entry(doel_rij, textvariable=self.doel_var, font=FONT_NORMAAL
                ).pack(side="left", fill="x", expand=True)
        RondeKnop(doel_rij, "...", kleur=PANEL, tekstkleur=TEKST,
                 highlightbackground=PANEL_RAND, highlightthickness=1,
                 command=self._kies_doelmap).pack(side="left", padx=(6, 0))
        tk.Frame(doel_paneel, bg=PANEL, height=8).pack()

        checks_paneel = Paneel(ouder)
        checks_paneel.pack(fill="both", expand=True, pady=(0, 10))
        kop_rij = tk.Frame(checks_paneel, bg=PANEL)
        kop_rij.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(kop_rij, text="Vereisten", font=FONT_VET,
                 bg=PANEL, fg=TEKST).pack(side="left")
        RondeKnop(kop_rij, "Controleren", kleur=PANEL, tekstkleur=TEKST,
                 highlightbackground=PANEL_RAND, highlightthickness=1,
                 command=self._doe_checks).pack(side="right")

        self.checks_lijst = tk.Frame(checks_paneel, bg=PANEL)
        self.checks_lijst.pack(fill="both", expand=True, padx=14, pady=(0, 6))
        self._checks_leeg_label = tk.Label(
            self.checks_lijst, text="Klik op 'Controleren' om te beginnen.",
            font=FONT_KLEIN, bg=PANEL, fg=TEKST_DIM)
        self._checks_leeg_label.pack(anchor="w")

        self.status_label = tk.Label(
            checks_paneel, text="", font=FONT_NORMAAL, bg=PANEL, fg=TEKST_DIM,
            wraplength=380, justify="left")
        self.status_label.pack(anchor="w", padx=14, pady=(0, 6))

        schaduw_rij = tk.Frame(checks_paneel, bg=PANEL)
        schaduw_rij.pack(fill="x", padx=14, pady=(0, 12))
        tk.Label(schaduw_rij, text="Schaduwkopie-station (optioneel - alleen "
                 "invullen als de check hierboven 'onvoldoende ruimte' meldt):",
                 font=FONT_KLEIN, bg=PANEL, fg=TEKST_DIM, wraplength=380,
                 justify="left").pack(anchor="w")
        schaduw_invoer_rij = tk.Frame(schaduw_rij, bg=PANEL)
        schaduw_invoer_rij.pack(fill="x", pady=(4, 0))
        self.schaduw_override_var = tk.StringVar(value="")
        tk.Entry(schaduw_invoer_rij, textvariable=self.schaduw_override_var,
                font=FONT_NORMAAL, width=8).pack(side="left")
        RondeKnop(schaduw_invoer_rij, "Toon beschikbare schijven", kleur=PANEL,
                 tekstkleur=TEKST, highlightbackground=PANEL_RAND, highlightthickness=1,
                 command=self._toon_beschikbare_schaduwschijven).pack(side="left", padx=(6, 0))

        controle_paneel = Paneel(ouder)
        controle_paneel.pack(fill="x", pady=(0, 10))
        tk.Label(controle_paneel, text="Bestaande backup controleren", font=FONT_VET,
                 bg=PANEL, fg=TEKST).pack(anchor="w", padx=14, pady=(12, 4))
        tk.Label(controle_paneel,
                text="Leesopdracht (wbadmin get versions) - wijzigt niets. Vraagt "
                     "wbAdmin zelf of er op deze doelmap een GELDIGE, complete "
                     "backup staat (een map met bestanden is geen garantie).",
                font=FONT_KLEIN, bg=PANEL, fg=TEKST_DIM, wraplength=380,
                justify="left").pack(anchor="w", padx=14, pady=(0, 6))
        RondeKnop(controle_paneel, "Controleer of er een geldige backup bestaat",
                 kleur=PANEL, tekstkleur=TEKST,
                 highlightbackground=PANEL_RAND, highlightthickness=1,
                 command=self._controleer_bestaande_backup).pack(
                     fill="x", padx=14, pady=(0, 12))

        knoppen_paneel = Paneel(ouder)
        knoppen_paneel.pack(fill="x")
        tk.Label(knoppen_paneel, text="Starten", font=FONT_VET,
                 bg=PANEL, fg=TEKST).pack(anchor="w", padx=14, pady=(12, 8))
        self.start_direct_knop = RondeKnop(
            knoppen_paneel, "Start Image Backup (al Administrator)",
            kleur=GROEN, state="disabled", command=self._start_direct)
        self.start_direct_knop.pack(fill="x", padx=14)
        self.start_uac_knop = RondeKnop(
            knoppen_paneel, "Start Image Backup als Administrator (UAC)",
            kleur=ORANJE, state="disabled", command=self._start_elevated)
        self.start_uac_knop.pack(fill="x", padx=14, pady=(8, 14))

    def _bouw_logpaneel(self, ouder):
        log_paneel = Paneel(ouder)
        log_paneel.pack(fill="both", expand=True)
        tk.Label(log_paneel, text="Voortgang", font=FONT_VET,
                 bg=PANEL, fg=TEKST).pack(anchor="w", padx=14, pady=(12, 6))
        binnen = tk.Frame(log_paneel, bg=PANEL)
        binnen.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        scroll = tk.Scrollbar(binnen)
        scroll.pack(side="right", fill="y")
        self.log_tekst = tk.Text(
            binnen, bg=LOG_BG, fg=TEKST, font=FONT_MONO, wrap="word",
            relief="flat", yscrollcommand=scroll.set,
            highlightbackground=PANEL_RAND, highlightthickness=1)
        self.log_tekst.pack(fill="both", expand=True)
        scroll.config(command=self.log_tekst.yview)
        self.log_tekst.tag_config("ok", foreground=GROEN)
        self.log_tekst.tag_config("fout", foreground=ROOD)
        self.log_tekst.tag_config("waarschuwing", foreground=ORANJE)
        self.log_tekst.tag_config("info", foreground=TEKST_DIM)

    def _log(self, tekst, niveau="info"):
        def doe():
            if not self.winfo_exists():
                return
            self.log_tekst.insert("end", tekst + "\n", niveau)
            self.log_tekst.see("end")
        self.after(0, doe)

    def _kies_doelmap(self):
        from tkinter import filedialog
        gekozen = filedialog.askdirectory(title="Kies de doelmap voor de systeemkopie")
        if gekozen:
            self.doel_var.set(gekozen)

    def _controleer_herstelschijf(self):
        from tkinter import filedialog
        gekozen = filedialog.askdirectory(
            title="Kies de herstel-USB-stick om de structuur van te controleren")
        if not gekozen:
            return

        self._log(f"--- Structuurcontrole herstelschijf: {gekozen} ---", "info")
        resultaten = ib.controleer_herstelschijf(gekozen)
        for status, tekst in resultaten:
            self._log(tekst, "ok" if status == "ok" else "fout")

        fouten = [t for s, t in resultaten if s == "fout"]
        if fouten:
            messagebox.showwarning(
                "Mogelijk probleem gevonden",
                "Een of meer onderdelen ontbreken of zien er niet goed uit:\n\n"
                + "\n".join(fouten) +
                "\n\nDit garandeert overigens nooit 100% dat een complete "
                "stick wel bootbaar is, of een incomplete dat niet is - de "
                "enige echte test is er een PC vanaf laten opstarten.")
        else:
            messagebox.showinfo(
                "Structuur ziet er goed uit",
                "Alle typische onderdelen van een herstelschijf zijn gevonden.\n\n"
                "Let op: dit garandeert geen bootbaarheid. Test dit eenmalig "
                "door er echt een PC vanaf op te starten (UEFI/BIOS-boot-menu, "
                "vaak F12/F2/Esc).")

    def _maak_herstelschijf_en_kaartje(self):
        # Beide acties gebruiken VSS (schaduwkopieen). wbAdmin houdt
        # tijdens een backup een schaduwkopie actief vast; de
        # herstelschijf-wizard wil zelf OOK een schaduwkopie maken om
        # systeembestanden te kopieren - dat kan botsen. Waarschuw
        # hiervoor in plaats van de gebruiker te laten gokken naar een
        # onduidelijke fout.
        if os.path.exists(ib.MARKER_BESTAND):
            loopt, zeker = ib.wbadmin_draait()
            if loopt or not zeker:
                doorgaan = messagebox.askyesno(
                    "Mogelijk conflict met lopende backup",
                    "Er lijkt een image-backup te draaien (of dat is onzeker). "
                    "Zowel de backup als de herstelschijf-wizard gebruiken "
                    "schaduwkopieen (VSS) - die kunnen elkaar in de weg "
                    "zitten, waardoor de wizard niet goed werkt.\n\n"
                    "Aanbevolen: wacht tot de backup klaar is.\n\n"
                    "Toch nu doorgaan?")
                if not doorgaan:
                    return

        # BEWUSTE KEUZE: recoverydrive.exe niet meer programmatisch
        # starten. Dat bleek herhaaldelijk te falen met WinError 740
        # (elevatie geweigerd), zelfs met de juiste 'runas'-aanroep -
        # dit programma heeft zijn eigen ingebouwde auto-elevatie via
        # zijn manifest, en die combinatie met ShellExecuteEx blijkt
        # onbetrouwbaar genoeg om niet op te vertrouwen. Zelf openen
        # via het Windows-zoekvenster werkt altijd, zonder die
        # complexiteit - dus dat is nu de weg.
        self._log("--- Herstelschijf maken: handmatig te openen ---", "info")
        doorgegaan = messagebox.askokcancel(
            "Herstelschijf zelf openen",
            "Open nu zelf de Windows-wizard (dit is betrouwbaarder dan "
            "automatisch starten vanuit dit programma):\n\n"
            "1. Druk op de Windows-toets\n"
            "2. Typ: herstelschijf\n"
            "3. Klik op 'Een herstelschijf maken' (met het schildje "
            "erbij - dat geeft zelf de UAC-vraag)\n"
            "4. Doorloop de wizard met je USB-stick\n\n"
            "Klik hier op OK zodra je KLAAR bent met de wizard (of "
            "Annuleren als je het niet nu wil doen) - daarna helpt dit "
            "programma je verder met het noodkaartje.")
        if not doorgegaan:
            self._log("Herstelschijf-wizard niet gestart (geannuleerd).", "info")
            return
        self._na_herstelschijf_wizard()

    def _na_herstelschijf_wizard(self):
        doorgaan = messagebox.askyesno(
            "Herstelschijf-wizard gesloten",
            "Is de herstel-USB-stick succesvol aangemaakt?\n\n"
            "Bij 'Ja' kun je nu aanwijzen waar de stick staat, zodat het "
            "noodkaartje er meteen op gezet wordt.")
        if doorgaan:
            self._sla_noodkaartje_op()

    def _sla_noodkaartje_op(self):
        from tkinter import filedialog
        doelmap_lokaal = self.doel_var.get().strip()
        if not doelmap_lokaal:
            messagebox.showwarning(
                "Geen doelmap", "Vul eerst de doelmap in (boven) zodat ik weet "
                "welk netwerkpad er op het kaartje moet komen.")
            return

        unc_basis = (self._checks_resultaat.unc_doel
                    if self._checks_resultaat else "") or doelmap_lokaal
        unc_pad = ib.bouw_backup_bestemming(unc_basis)

        gekozen = filedialog.askdirectory(
            title="Kies de USB-stick (de zojuist gemaakte herstelschijf) waar het noodkaartje op moet komen")
        if not gekozen:
            return

        gestart = ib.schrijf_noodkaartje(gekozen, unc_pad, gebruiker="pi", on_log=self._log)
        if gestart:
            messagebox.showinfo(
                "Noodkaartje opgeslagen",
                f"Geschreven naar:\n{gekozen}\\{ib.NOODKAART_BESTANDSNAAM}\n\n"
                f"Bewaar dit op de herstel-USB-stick zelf.")

    # -- Bestaande backup controleren (leesopdracht, wbadmin get versions) --

    def _controleer_bestaande_backup(self):
        doelmap = self.doel_var.get().strip()
        if not doelmap:
            messagebox.showwarning("Geen doelmap", "Vul eerst een doelmap in.")
            return

        unc_doel = self._checks_resultaat.unc_doel if self._checks_resultaat else None
        backup_basis = unc_doel or doelmap
        backup_dest = ib.bouw_backup_bestemming(backup_basis)

        self._log(f"--- Controleren op geldige backup: {backup_dest} ---", "info")
        self.status_label.config(text="Wordt gecontroleerd (wbadmin get versions)...", fg=TEKST_DIM)

        def doe():
            heeft_geldige, ruwe_uitvoer = ib.controleer_geldige_backups(backup_dest, on_log=self._log)
            self.after(0, lambda: self._toon_backup_controle(heeft_geldige, ruwe_uitvoer, backup_dest))

        threading.Thread(target=doe, daemon=True).start()

    def _toon_backup_controle(self, heeft_geldige, ruwe_uitvoer, backup_dest):
        if not self.winfo_exists():
            return
        for regel in ruwe_uitvoer.splitlines():
            self._log(regel, "ok" if heeft_geldige else "waarschuwing")

        if heeft_geldige:
            self.status_label.config(
                text=f"Geldige, complete backup gevonden op: {backup_dest}", fg=GROEN)
        else:
            self.status_label.config(
                text=f"GEEN geldige backup gevonden op: {backup_dest} (zie details hierboven in 'Voortgang')",
                fg=ROOD)

    # -- Vereisten-checks --------------------------------------------------

    def _doe_checks(self):
        doelmap = self.doel_var.get().strip()
        override = self.schaduw_override_var.get().strip() or None
        self.status_label.config(text="Vereisten worden gecontroleerd...", fg=TEKST_DIM)

        def doe():
            resultaat = ib.voer_checks_uit(doelmap, voorkeur_shadow_drive=override)
            self.after(0, lambda: self._toon_checks(resultaat))

        threading.Thread(target=doe, daemon=True).start()

    def _toon_beschikbare_schaduwschijven(self):
        def doe():
            schijven = ib.beschikbare_lokale_schijven()
            self.after(0, lambda: self._toon_schaduwschijven_resultaat(schijven))
        threading.Thread(target=doe, daemon=True).start()

    def _toon_schaduwschijven_resultaat(self, schijven):
        if not schijven:
            messagebox.showinfo("Geen schijven gevonden",
                                "Geen lokale NTFS-schijven gevonden (of niet op Windows).")
            return
        regels = "\n".join(f"  {letter}  -  {vrij} GB vrij van {totaal} GB totaal"
                           for letter, vrij, totaal in schijven)
        messagebox.showinfo(
            "Beschikbare lokale schijven",
            f"{regels}\n\nTyp de letter (bijv. 'D:') in het veld hiernaast en klik "
            f"opnieuw op 'Controleren' om die schijf te gebruiken voor de schaduwkopie.")

    def _toon_checks(self, resultaat):
        if not self.winfo_exists():
            return
        self._checks_resultaat = resultaat
        for widget in self.checks_lijst.winfo_children():
            widget.destroy()

        kleuren = {"ok": GROEN, "fout": ROOD, "actie_nodig": ORANJE,
                  "overgeslagen": TEKST_DIM, "onbekend": ORANJE}
        symbolen = {"ok": "[OK]", "fout": "[!!]", "actie_nodig": "[>>]",
                   "overgeslagen": "[--]", "onbekend": "[??]"}
        for regel in resultaat.regels:
            rij = tk.Frame(self.checks_lijst, bg=PANEL)
            rij.pack(fill="x", anchor="w")
            kleur = kleuren.get(regel.status, TEKST_DIM)
            tk.Label(rij, text=symbolen.get(regel.status, "[?]"), font=FONT_MONO,
                     bg=PANEL, fg=kleur, width=5, anchor="w").pack(side="left")
            tk.Label(rij, text=regel.tekst, font=FONT_KLEIN, bg=PANEL, fg=kleur,
                     anchor="w", wraplength=320, justify="left").pack(
                         side="left", fill="x", expand=True)

        if resultaat.klaar_om_direct_te_starten():
            self.status_label.config(text="Alle checks geslaagd - klaar om te starten.", fg=GROEN)
            self.start_direct_knop.config(state="normal")
            self.start_uac_knop.config(state="disabled")
        elif resultaat.klaar_voor_uac():
            self.status_label.config(text="Geen admin-rechten - gebruik de oranje UAC-knop.", fg=ORANJE)
            self.start_direct_knop.config(state="disabled")
            self.start_uac_knop.config(state="normal")
        else:
            self.status_label.config(text="Niet alle vereisten zijn voldaan - zie rood hierboven.", fg=ROOD)
            self.start_direct_knop.config(state="disabled")
            self.start_uac_knop.config(state="disabled")

    # -- Starten: direct (al admin) ---------------------------------------

    def _start_direct(self):
        if not self._checks_resultaat:
            return
        doelmap = self.doel_var.get().strip()
        self.start_direct_knop.config(state="disabled")
        self._log("--- Image backup gestart (direct, al Administrator) ---", "info")

        def doe():
            succes, exitcode = ib.start_direct(
                doelmap, self._checks_resultaat.unc_doel, on_log=self._log)
            if succes:
                backup_basis = self._checks_resultaat.unc_doel or doelmap
                backup_dest = ib.bouw_backup_bestemming(backup_basis)
                ib.schrijf_herstel_instructie(
                    backup_dest, unc_pad=backup_dest, gebruiker="pi", on_log=self._log)
            self.after(0, lambda: self.start_direct_knop.config(state="normal"))

        threading.Thread(target=doe, daemon=True).start()

    # -- Starten: elevated via UAC -----------------------------------------

    def _start_elevated(self):
        if not self._checks_resultaat:
            return
        doelmap_lokaal = self.doel_var.get().strip()
        backup_basis = self._checks_resultaat.unc_doel or doelmap_lokaal

        # Vergrendeling: niet starten als er al een marker bestaat EN
        # wbAdmin daadwerkelijk draait - dat zou een echt lopende
        # backup verstoren (precies het soort situatie dat eerder een
        # lopende backup per ongeluk liet stoppen).
        if os.path.exists(ib.MARKER_BESTAND):
            loopt, zeker = ib.wbadmin_draait()
            if loopt:
                messagebox.showwarning(
                    "Er loopt al een backup",
                    "Er lijkt al een image-backup te draaien (wbadmin.exe is "
                    "actief). Wacht tot die klaar is voordat je een nieuwe "
                    "start - anders verstoren ze elkaar.")
                return
            if not zeker:
                doorgaan = messagebox.askyesno(
                    "Onzeker of er al een backup loopt",
                    "Er staat een marker van een eerdere poging, maar ik kan "
                    "niet met zekerheid vaststellen of wbAdmin nog draait "
                    "(tasklist-controle mislukt). Controleer dit liever zelf "
                    "even in Taakbeheer voordat je doorgaat.\n\n"
                    "Toch doorgaan met een nieuwe backup starten?")
                if not doorgaan:
                    return

        bestaat, label, grootte = ib.detecteer_bestaande_backup(doelmap_lokaal)
        if bestaat:
            doorgaan = messagebox.askyesno(
                "Bestaande backup gevonden",
                f"Er staat al een backup op:\n{doelmap_lokaal}\\{label}\n"
                f"Grootte: {grootte}\n\n"
                f"wbAdmin overschrijft de bestaande backup.\nWil je doorgaan?")
            if not doorgaan:
                return

        self.start_uac_knop.config(state="disabled", text="UAC gevraagd...")
        self._log("--- Image backup gestart (UAC) ---", "info")

        gebruiker = "pi"
        wachtwoord = ""  # in de praktijk overgenomen uit het verbindingsscherm van de suite

        bat_pad = ib.bouw_elevated_bat(
            doelmap_lokaal=doelmap_lokaal,
            backup_unc_basis=backup_basis,
            gebruiker=gebruiker,
            wachtwoord=wachtwoord,
            shadow_drive=self._checks_resultaat.shadow_drive,
            shadow_verplaatst=self._checks_resultaat.shadow_verplaatst)
        backup_dest = ib.bouw_backup_bestemming(backup_basis)

        def on_uac_gestart():
            self.after(0, lambda: self.start_uac_knop.config(text="Backup loopt..."))

        def doe():
            resultaat = ib.start_elevated_en_wacht(
                bat_pad, backup_dest, self._checks_resultaat.shadow_drive,
                on_log=self._log, on_uac_gestart=on_uac_gestart)
            self.after(0, lambda: self._na_elevated(resultaat))

        threading.Thread(target=doe, daemon=True).start()

    def _na_elevated(self, resultaat):
        self.start_uac_knop.config(state="normal", text="Start Image Backup als Administrator (UAC)")
        if resultaat.geweigerd:
            self._log("UAC geannuleerd - geen backup gestart.", "fout")
            self.status_label.config(text="UAC geannuleerd.", fg=ROOD)
            return
        if resultaat.afgebroken:
            self._log("Backup afgebroken (venster gesloten tijdens wbAdmin) - wordt opgeruimd...", "waarschuwing")
            ib.ruim_afgebroken_op(self._checks_resultaat.shadow_drive, resultaat.backup_dest, on_log=self._log)
            self.status_label.config(text="Backup afgebroken - automatisch opgeruimd.", fg=ORANJE)
            return
        if resultaat.succes():
            self._log(f"Backup voltooid: {resultaat.backup_dest}", "ok")
            self.status_label.config(text=f"Backup voltooid: {resultaat.backup_dest}", fg=GROEN)
            ib.schrijf_herstel_instructie(
                resultaat.backup_dest, unc_pad=resultaat.backup_dest,
                gebruiker="pi", on_log=self._log)
        elif resultaat.exitcode == -2:
            self._log("Verbinding mislukt - controleer gebruikersnaam/wachtwoord.", "fout")
            self.status_label.config(text="Verbinding mislukt.", fg=ROOD)
        else:
            self._log(f"Backup mislukt (exitcode {resultaat.exitcode}).", "fout")
            self.status_label.config(text=f"Backup mislukt (exitcode {resultaat.exitcode}).", fg=ROOD)


if __name__ == "__main__":
    app = ImageBackupVenster()
    app.mainloop()
