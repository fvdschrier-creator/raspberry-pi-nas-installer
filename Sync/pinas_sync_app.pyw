#!/usr/bin/env python3
"""
Pi NAS Suite - Sync (generieke opvolger van een oudere, NAS-specifieke sync-tool)

Twee schermen:
  1. Bron/doel kiezen: checkbox-boom + doeltoewijzing per bron
     (BronDoelKiezer uit bron_doel_picker.py)
  2. Synchroniseren: statuspaneel, reparatieknoppenbalk, besturing,
     activiteit/afwijkingen-logpanelen - hetzelfde gedrag als de
     oudere, NAS-specifieke sync-tool, maar nu volledig generiek: het
     aantal status-bolletjes en doel-stations past zich aan op wat je
     in scherm 1 hebt samengesteld, in plaats van vast op Pi/het oude
     NAS-apparaat/Z: te staan.

Gebruik: python pinas_sync_app.pyw
"""

import os
import time
import threading
import datetime
import tkinter as tk
from tkinter import ttk, messagebox

from core.sync_engine import (
    SyncEngine, SyncVoortgang, formatteer_bytes, formatteer_duur,
    test_verbinding, herstelactie_hdd_volledige_cyclus,
    herstelactie_lanmanfix, herstelactie_netuse_herkoppelen,
    controleer_systeemstatus, BestandLogger, _nas_root, drive_root,
    doel_zit_in_bron,
)
from core.bron_doel_picker import BronDoelKiezer


# =================================================================
# Kleuren - centraal via core/thema.py, dat op het suite-thema
# (Gedeeld/pinas_theme.py) leunt en meekleurt met donker/licht.
# Valt veilig terug op de oorspronkelijke lichte palette.
# =================================================================
try:
    from core.thema import (
        BG, PANEL, PANEL_RAND, TEKST, TEKST_DIM, ACCENT, ACCENT_DONKER,
        GROEN, ROOD, ORANJE, BG_ZACHT, LOG_BG, LOG_BG_AFW, ORANJE_ZACHT,
        SUBTITEL, DISABLED_TEKST, KNOP_TEKST, HUIDIG_THEMA,
    )
except ImportError:
    from thema import (
        BG, PANEL, PANEL_RAND, TEKST, TEKST_DIM, ACCENT, ACCENT_DONKER,
        GROEN, ROOD, ORANJE, BG_ZACHT, LOG_BG, LOG_BG_AFW, ORANJE_ZACHT,
        SUBTITEL, DISABLED_TEKST, KNOP_TEKST, HUIDIG_THEMA,
    )

# Suiteversie centraal uit version.py (Gedeeld staat op sys.path via het thema)
try:
    from version import BIJGEWERKT
except ImportError:
    BIJGEWERKT = "onbekende datum"

FONT_NAAM    = "Segoe UI"
FONT_NORMAAL = (FONT_NAAM, 10)
FONT_KLEIN   = (FONT_NAAM, 9)
FONT_VET     = (FONT_NAAM, 10, "bold")
FONT_TITEL   = (FONT_NAAM, 14, "bold")
FONT_MONO    = ("Consolas", 9)


class RondeKnop(tk.Button):
    """Standaardknop met consistente stijl door de hele applicatie."""
    def __init__(self, ouder, tekst, kleur=ACCENT, tekstkleur=KNOP_TEKST, **kw):
        super().__init__(
            ouder, text=tekst, font=FONT_VET, bg=kleur, fg=tekstkleur,
            activebackground=kleur, activeforeground=tekstkleur,
            relief="flat", padx=16, pady=9, cursor="hand2",
            disabledforeground=DISABLED_TEKST, **kw)


class Paneel(tk.Frame):
    """Wit paneel met subtiele rand - herbruikbare bouwsteen."""
    def __init__(self, ouder, **kw):
        super().__init__(ouder, bg=PANEL, highlightbackground=PANEL_RAND,
                         highlightthickness=1, **kw)


# =================================================================
# Scherm 1: bron/doel kiezen
# =================================================================

class BronDoelScherm(tk.Frame):
    """Wikkelt BronDoelKiezer in met een koptekst en een doorgaan-
    knop. Bewust een los scherm, zodat het navigatiepatroon (scherm 1
    -> scherm 2) duidelijk blijft en de kiezer zelf herbruikbaar blijft
    voor andere toekomstige onderdelen van de suite."""

    def __init__(self, ouder, op_doorgaan, **kw):
        super().__init__(ouder, bg=BG, **kw)
        self._op_doorgaan = op_doorgaan
        self._build()

    def _build(self):
        kop = tk.Frame(self, bg="#2f3b47", height=64)
        kop.pack(fill="x")
        tk.Label(kop, text="Pi NAS Sync", font=FONT_TITEL, bg="#2f3b47", fg=KNOP_TEKST
                 ).pack(side="left", padx=18, pady=14)
        tk.Label(kop, text="Stap 1: kies bronnen en doelen",
                 font=FONT_NORMAAL, bg="#2f3b47", fg=SUBTITEL).pack(side="left", pady=14)

        toelichting = tk.Frame(self, bg=BG_ZACHT)
        toelichting.pack(fill="x")
        tk.Label(toelichting,
                text="Vink links een of meer mappen/stations/netwerkpaden aan. "
                     "Stel rechts per bron een doelmap in (vrij te kiezen, hoeft "
                     "niet dezelfde structuur te zijn). Netwerkshares, Pi-mounts (Y:/Z:) "
                     "en lokale schijven werken hier allemaal hetzelfde.",
                font=FONT_KLEIN, bg=BG_ZACHT, fg=TEKST_DIM, wraplength=1000,
                justify="left").pack(anchor="w", padx=16, pady=8)

        midden = tk.Frame(self, bg=BG)
        midden.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.kiezer = BronDoelKiezer(midden)
        self.kiezer.pack(fill="both", expand=True)

        onder = tk.Frame(self, bg=BG)
        onder.pack(fill="x", padx=12, pady=(0, 12))
        self.doorgaan_knop = RondeKnop(
            onder, "Doorgaan naar synchronisatie ->",
            command=self._doorgaan)
        self.doorgaan_knop.pack(side="right")

    def _doorgaan(self):
        taken = self.kiezer.get_taken()
        if not taken:
            messagebox.showwarning(
                "Geen taken",
                "Vink minstens een bron aan en stel een doelmap in voordat je "
                "doorgaat.")
            return

        # Harde blokkade (geen waarschuwing met doorgaan-optie): een
        # doel dat gelijk is aan, of binnen, de bron zelf ligt geeft
        # corrupte, onvoorspelbare resultaten - dit mag nooit
        # doorgaan, in tegenstelling tot de schijf-root-waarschuwing
        # hieronder die wel (bewust) doorgang toestaat.
        zelfreferentiele_taken = [
            t for t in taken if doel_zit_in_bron(t.bron_pad, t.doel_pad)]
        if zelfreferentiele_taken:
            lijst = "\n".join(f"  {t.bron_pad}  ->  {t.doel_pad}" for t in zelfreferentiele_taken)
            messagebox.showerror(
                "Doel ligt binnen de bron - niet toegestaan",
                f"Bij {len(zelfreferentiele_taken)} taak/taken ligt het doel "
                f"binnen de bron zelf:\n\n{lijst}\n\n"
                f"Dit kopieert een map naar een plek BINNEN zichzelf, wat tot "
                f"onvoorspelbare en corrupte resultaten leidt. Pas het doelpad "
                f"aan zodat het buiten de bron ligt voordat je doorgaat.")
            return

        # Veiligheidscheck: een doelpad dat EXACT een schijf-root is
        # (bijv. "Z:\\" zelf, niet "Z:\\Backup") betekent dat de
        # inhoud van de bron los op die schijf terechtkomt, zonder
        # eigen submap. Dat is bijna nooit de bedoeling - meestal is
        # dit een vergissing (bijv. via de bladerknop per ongeluk de
        # schijf-root zelf gekozen in plaats van een submap erin).
        risicovolle_taken = [
            t for t in taken
            if t.doel_pad.rstrip("\\/").lower() == drive_root(t.doel_pad).rstrip("\\/").lower()
        ]
        if risicovolle_taken:
            lijst = "\n".join(f"  {t.bron_pad}  ->  {t.doel_pad}" for t in risicovolle_taken)
            doorgaan = messagebox.askyesno(
                "Let op: doel is een hele schijf",
                f"Bij {len(risicovolle_taken)} taak/taken is het doel een complete "
                f"schijf-root, zonder eigen submap:\n\n{lijst}\n\n"
                f"De inhoud van de bron komt dan los op die schijf terecht, niet "
                f"in een eigen map. Is dit echt de bedoeling?\n\n"
                f"(Bij 'Nee' kun je het doelpad eerst aanpassen.)")
            if not doorgaan:
                return

        self._op_doorgaan(taken)


# =================================================================
# Scherm 2: synchroniseren (statuspaneel, reparatieknoppen, logs)
# =================================================================

class SyncScherm(tk.Frame):
    """Functioneel gelijk aan het sync-venster van de oudere,
    NAS-specifieke sync-tool, maar generiek: het aantal status-bolletjes
    en doel-stations volgt uit de taken die in scherm 1 zijn
    samengesteld, in plaats van vast op Pi/het oude NAS-apparaat/Z:
    te staan."""

    def __init__(self, ouder, taken, op_terug, **kw):
        super().__init__(ouder, bg=BG, **kw)
        self.taken = taken
        self._op_terug = op_terug

        self.bestand_logger = BestandLogger(bestandsnaam_voorvoegsel="pinas_sync")
        self.engine = None
        self.onderzoek_engine = None
        self._wacht_op_pauze_antwoord = threading.Event()
        self._pauze_antwoord = False
        self._status_was_ok = True
        self._status_storing_sinds = None
        self._herstelknoppen_bezig = False
        self._status_controle_actief = True
        self._tellen_overgeslagen = False

        # Een tijdelijke engine, alleen om doel_stations()/bron_stations()
        # op te vragen voor het statuspaneel - de echte sync-engines
        # (onderzoek + uitvoering) worden er later los van aangemaakt.
        self._referentie_engine = SyncEngine(self.taken)

        self._bouw_layout()
        self._start_statuscontrole_achtergrond()
        self._begin_onderzoek()

    def stop_achtergrondwerk(self):
        self._status_controle_actief = False

    # -- Layout ----------------------------------------------------

    def _bouw_layout(self):
        kop = tk.Frame(self, bg="#2f3b47", height=64)
        kop.pack(fill="x")
        tk.Label(kop, text="Pi NAS Sync", font=FONT_TITEL, bg="#2f3b47", fg=KNOP_TEKST
                 ).pack(side="left", padx=18, pady=14)
        tk.Label(kop, text=f"Stap 2: synchroniseren ({len(self.taken)} taak/taken)",
                 font=FONT_NORMAAL, bg="#2f3b47", fg=SUBTITEL).pack(side="left", pady=14)
        RondeKnop(kop, "<- Terug naar bron/doel", kleur=ACCENT_DONKER,
                 command=self._terug).pack(side="right", padx=18)

        self._bouw_statuspaneel()
        self._bouw_reparatiebalk()

        midden = tk.PanedWindow(self, orient="horizontal", bg=BG,
                                sashwidth=6, sashrelief="flat")
        midden.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        linker_kolom = tk.Frame(midden, bg=BG, width=380)
        midden.add(linker_kolom, minsize=320)
        self._bouw_besturingspaneel(linker_kolom)

        rechter_kolom = tk.Frame(midden, bg=BG)
        midden.add(rechter_kolom, minsize=500)
        self._bouw_activiteit_en_afwijkingen(rechter_kolom)

    def _terug(self):
        if self.engine is not None and self.engine.voortgang.fase == "synchroniseren":
            if not messagebox.askyesno(
                    "Synchronisatie loopt nog",
                    "Er loopt nog een synchronisatie. Toch teruggaan? De "
                    "synchronisatie wordt dan gestopt."):
                return
            self.engine.stop()
        self.stop_achtergrondwerk()
        self._op_terug()

    # -- Statuspaneel: past zich aan op het aantal bronnen/doelen ------

    def _bouw_statuspaneel(self):
        balk = tk.Frame(self, bg=BG_ZACHT)
        balk.pack(fill="x")
        binnenkant = tk.Frame(balk, bg=BG_ZACHT)
        binnenkant.pack(padx=16, pady=8, fill="x")

        tk.Label(binnenkant, text="Systeemstatus:", font=FONT_KLEIN,
                 bg=BG_ZACHT, fg=TEKST_DIM).pack(side="left", padx=(0, 12))

        self._status_rij = tk.Frame(binnenkant, bg=BG_ZACHT)
        self._status_rij.pack(side="left", fill="x", expand=True)
        self.status_bolletjes = {}  # gevuld bij eerste statuscontrole

        self.status_detail_label = tk.Label(
            binnenkant, text="Status wordt gecontroleerd...",
            font=FONT_KLEIN, bg=BG_ZACHT, fg=TEKST_DIM)
        self.status_detail_label.pack(side="left", padx=(8, 0))

        self.status_verversen_knop = RondeKnop(
            binnenkant, "Nu controleren", kleur=PANEL, tekstkleur=TEKST,
            highlightbackground=PANEL_RAND, highlightthickness=1,
            command=self._handmatige_statuscontrole)
        self.status_verversen_knop.pack(side="right")

    def _zorg_voor_bolletjes(self, status):
        """Bouwt de bolletjesrij eenmalig op, op basis van de eerste
        statuscontrole - daarna worden alleen de kleuren bijgewerkt."""
        if self.status_bolletjes:
            return
        namen = [b.naam for b in status.bronnen] + [d.naam for d in status.doelen]
        for naam in namen:
            cel = tk.Frame(self._status_rij, bg=BG_ZACHT)
            cel.pack(side="left", padx=(0, 16))
            bolletje = tk.Label(cel, text="\u25cf", font=(FONT_NAAM, 12),
                                 bg=BG_ZACHT, fg=TEKST_DIM)
            bolletje.pack(side="left")
            tk.Label(cel, text=naam, font=FONT_KLEIN, bg=BG_ZACHT, fg=TEKST_DIM
                     ).pack(side="left", padx=(4, 0))
            self.status_bolletjes[naam] = bolletje

    def _start_statuscontrole_achtergrond(self):
        def loop():
            while self._status_controle_actief:
                status = controleer_systeemstatus(self._referentie_engine)
                self.after(0, lambda s=status: self._toon_status(s))
                for _ in range(15):
                    if not self._status_controle_actief:
                        return
                    time.sleep(1)
        threading.Thread(target=loop, daemon=True).start()

    def _handmatige_statuscontrole(self):
        self.status_detail_label.config(text="Wordt gecontroleerd...")
        def doe():
            status = controleer_systeemstatus(self._referentie_engine)
            self.after(0, lambda: self._toon_status(status))
        threading.Thread(target=doe, daemon=True).start()

    def _toon_status(self, status):
        if not self.winfo_exists():
            return
        self._zorg_voor_bolletjes(status)

        for b in status.bronnen:
            if b.naam in self.status_bolletjes:
                kleur = TEKST_DIM if b.bereikbaar is None else (GROEN if b.bereikbaar else ROOD)
                self.status_bolletjes[b.naam].config(fg=kleur)
        for d in status.doelen:
            if d.naam in self.status_bolletjes:
                ok = d.leesbaar and d.schrijfbaar
                kleur = TEKST_DIM if d.leesbaar is None else (GROEN if ok else ROOD)
                self.status_bolletjes[d.naam].config(fg=kleur)

        tekst = status.detail_tekst()
        self.status_detail_label.config(text=tekst)

        alles_ok = status.alles_ok()
        if alles_ok:
            if not self._status_was_ok:
                duur = ""
                if self._status_storing_sinds:
                    duur = f" (storing duurde {formatteer_duur(time.time() - self._status_storing_sinds)})"
                self._log_afwijking(f"Status herstelt: alles weer in orde{duur}.", "waarschuwing")
            self._status_was_ok = True
            self._status_storing_sinds = None
        else:
            if self._status_was_ok:
                self._status_storing_sinds = time.time()
                self._log_afwijking(f"Statuscontrole: {tekst}", "waarschuwing")
            else:
                duur = time.time() - self._status_storing_sinds
                if int(duur) % 300 < 16:
                    self._log_afwijking(
                        f"Storing duurt voort ({formatteer_duur(duur)}): {tekst}", "fout")
            self._status_was_ok = False

    # -- Reparatieknoppenbalk -------------------------------------------

    def _bouw_reparatiebalk(self):
        balk = tk.Frame(self, bg=BG_ZACHT)
        balk.pack(fill="x")
        binnenkant = tk.Frame(balk, bg=BG_ZACHT)
        binnenkant.pack(padx=16, pady=(0, 8), fill="x")

        tk.Label(binnenkant, text="Handmatige reparatie:", font=FONT_KLEIN,
                 bg=BG_ZACHT, fg=TEKST_DIM).pack(side="left", padx=(0, 10))

        self.knop_test_verbinding = RondeKnop(
            binnenkant, "Verbinding testen", kleur=PANEL, tekstkleur=TEKST,
            highlightbackground=PANEL_RAND, highlightthickness=1,
            command=lambda: self._handmatige_actie(self._actie_test_verbinding))
        self.knop_test_verbinding.pack(side="left", padx=(0, 6))

        self.knop_hdd_cyclus = RondeKnop(
            binnenkant, "HDD uit/aan (volledige cyclus)", kleur=PANEL, tekstkleur=TEKST,
            highlightbackground=PANEL_RAND, highlightthickness=1,
            command=lambda: self._handmatige_actie(self._actie_hdd_cyclus))
        self.knop_hdd_cyclus.pack(side="left", padx=(0, 6))

        self.knop_lanmanfix = RondeKnop(
            binnenkant, "LanManFix uitvoeren", kleur=PANEL, tekstkleur=TEKST,
            highlightbackground=PANEL_RAND, highlightthickness=1,
            command=lambda: self._handmatige_actie(self._actie_lanmanfix))
        self.knop_lanmanfix.pack(side="left", padx=(0, 6))

        self.knop_herkoppel_z = RondeKnop(
            binnenkant, f"{self._eerste_doel_station()} loskoppelen en opnieuw koppelen",
            kleur=PANEL, tekstkleur=TEKST,
            highlightbackground=PANEL_RAND, highlightthickness=1,
            command=lambda: self._handmatige_actie(self._actie_herkoppel_z))
        self.knop_herkoppel_z.pack(side="left", padx=(0, 6))

        tk.Label(binnenkant, text=f"Logbestand: {self.bestand_logger.pad}",
                 font=FONT_KLEIN, bg=BG_ZACHT, fg=TEKST_DIM
                 ).pack(side="right")

    def _alle_reparatieknoppen(self):
        return [self.knop_test_verbinding, self.knop_hdd_cyclus,
                self.knop_lanmanfix, self.knop_herkoppel_z]

    def _handmatige_actie(self, actie_functie):
        if self._herstelknoppen_bezig:
            messagebox.showinfo("Even geduld", "Er loopt al een reparatie-actie.")
            return
        self._herstelknoppen_bezig = True
        for knop in self._alle_reparatieknoppen():
            knop.config(state="disabled")

        def doe():
            try:
                actie_functie()
            finally:
                def herstel_knoppen():
                    self._herstelknoppen_bezig = False
                    for knop in self._alle_reparatieknoppen():
                        knop.config(state="normal")
                self.after(0, herstel_knoppen)

        threading.Thread(target=doe, daemon=True).start()

    def _eerste_doel_station(self):
        stations = self._referentie_engine.doel_stations()
        return stations[0] if stations else "Z:\\"

    def _actie_test_verbinding(self):
        self._log("--- Handmatige actie: verbinding testen ---", "info")
        for station in self._referentie_engine.doel_stations():
            ok, detail, duur = test_verbinding(station)
            if ok:
                self._log(f"Verbinding in orde ({station}): {detail}", "ok")
            else:
                self._log(f"Verbinding NIET in orde ({station}): {detail}", "fout")

    def _actie_hdd_cyclus(self):
        self._log("--- Handmatige actie: HDD volledige uit/aan-cyclus ---", "info")
        gelukt, detail = herstelactie_hdd_volledige_cyclus(log_func=self._log)
        if gelukt:
            self._log("HDD-cyclus voltooid.", "ok")
        else:
            self._log(f"HDD-cyclus mislukt: {detail}", "fout")

    def _actie_lanmanfix(self):
        self._log("--- Handmatige actie: LanManFix ---", "info")
        gelukt, detail = herstelactie_lanmanfix(log_func=self._log)
        if gelukt:
            self._log("LanManFix uitgevoerd.", "ok")
        else:
            self._log(f"LanManFix mislukt: {detail}", "fout")

    def _actie_herkoppel_z(self):
        station = self._eerste_doel_station()
        self._log(f"--- Handmatige actie: {station} loskoppelen en herkoppelen ---", "info")
        gelukt, detail = herstelactie_netuse_herkoppelen(station, log_func=self._log)
        if gelukt:
            self._log(f"{station} opnieuw gekoppeld.", "ok")
        else:
            self._log(f"Herkoppelen mislukt: {detail}", "fout")

    # -- Centrale logfuncties -------------------------------------------

    def _log(self, tekst, niveau="info"):
        self.bestand_logger.schrijf(tekst, niveau)
        if hasattr(self, "activiteiten_log") and self.activiteiten_log.winfo_exists():
            self.activiteiten_log.insert("end", tekst + "\n", niveau)
            self.activiteiten_log.see("end")
        if niveau in ("fout", "waarschuwing"):
            self._toon_in_afwijkingen(tekst, niveau)

    def _log_afwijking(self, tekst, niveau="waarschuwing"):
        self.bestand_logger.schrijf(tekst, niveau)
        self._toon_in_afwijkingen(tekst, niveau)

    def _toon_in_afwijkingen(self, tekst, niveau):
        if hasattr(self, "afwijkingen_log") and self.afwijkingen_log.winfo_exists():
            tijdstip = datetime.datetime.now().strftime("%H:%M:%S")
            self.afwijkingen_log.insert("end", f"[{tijdstip}] {tekst}\n", niveau)
            self.afwijkingen_log.see("end")

    # -- Linkerkolom: besturingspaneel -----------------------------------

    def _bouw_besturingspaneel(self, ouder):
        bronnen_paneel = Paneel(ouder)
        bronnen_paneel.pack(fill="x", pady=(0, 10))
        tk.Label(bronnen_paneel, text="Bronnen en doel", font=FONT_VET,
                 bg=PANEL, fg=TEKST).pack(anchor="w", padx=14, pady=(12, 6))
        for taak in self.taken:
            tk.Label(bronnen_paneel, text=taak.bron_pad, font=FONT_KLEIN,
                     bg=PANEL, fg=TEKST, anchor="w", wraplength=340, justify="left"
                     ).pack(anchor="w", padx=14)
            tk.Label(bronnen_paneel, text=f"  -> {taak.doel_pad}",
                     font=FONT_KLEIN, bg=PANEL, fg=TEKST_DIM, anchor="w",
                     wraplength=340, justify="left"
                     ).pack(anchor="w", padx=14, pady=(0, 6))
        tk.Frame(bronnen_paneel, bg=PANEL, height=8).pack()

        self.onderzoek_paneel = Paneel(ouder)
        self.onderzoek_paneel.pack(fill="x", pady=(0, 10))
        tk.Label(self.onderzoek_paneel, text="Inventarisatie", font=FONT_VET,
                 bg=PANEL, fg=TEKST).pack(anchor="w", padx=14, pady=(12, 6))
        self.onderzoek_label = tk.Label(
            self.onderzoek_paneel, text="Bronnen worden doorzocht...",
            font=FONT_KLEIN, bg=PANEL, fg=TEKST_DIM, justify="left", wraplength=340)
        self.onderzoek_label.pack(anchor="w", padx=14, pady=(0, 6))
        self.onderzoek_balk = ttk.Progressbar(
            self.onderzoek_paneel, orient="horizontal", mode="indeterminate", length=100)
        self.onderzoek_balk.pack(fill="x", padx=14, pady=(0, 6))
        self.onderzoek_balk.start(15)
        self.sla_tellen_over_knop = RondeKnop(
            self.onderzoek_paneel, "Tellen overslaan, direct starten",
            kleur=PANEL, tekstkleur=TEKST,
            highlightbackground=PANEL_RAND, highlightthickness=1,
            command=self._sla_tellen_over)
        self.sla_tellen_over_knop.pack(fill="x", padx=14, pady=(0, 12))

        besturing_paneel = Paneel(ouder)
        besturing_paneel.pack(fill="x", pady=(0, 10))
        tk.Label(besturing_paneel, text="Besturing", font=FONT_VET,
                 bg=PANEL, fg=TEKST).pack(anchor="w", padx=14, pady=(12, 8))

        self.verwijder_wezen_var = tk.BooleanVar(value=False)
        verwijder_check = tk.Checkbutton(
            besturing_paneel, text="Ook bestanden in doel verwijderen die niet "
            "meer in de bron staan (echte sync, geen alleen-aanvullen)",
            variable=self.verwijder_wezen_var, bg=PANEL, fg=TEKST,
            activebackground=PANEL, selectcolor=PANEL, font=FONT_KLEIN,
            wraplength=340, justify="left", anchor="w")
        verwijder_check.pack(anchor="w", padx=14, pady=(0, 8))

        knoppen_rij = tk.Frame(besturing_paneel, bg=PANEL)
        knoppen_rij.pack(fill="x", padx=14, pady=(0, 12))
        self.start_knop = RondeKnop(
            knoppen_rij, "Synchronisatie starten", kleur=ACCENT, state="disabled",
            command=self._start_synchronisatie)
        self.start_knop.pack(fill="x")
        self.stop_knop = RondeKnop(
            knoppen_rij, "Stoppen", kleur=ROOD, state="disabled",
            command=self._vraag_stoppen)
        self.stop_knop.pack(fill="x", pady=(6, 0))

        voortgang_paneel = Paneel(ouder)
        voortgang_paneel.pack(fill="x", pady=(0, 10))
        tk.Label(voortgang_paneel, text="Voortgang", font=FONT_VET,
                 bg=PANEL, fg=TEKST).pack(anchor="w", padx=14, pady=(12, 6))
        self.status_label = tk.Label(
            voortgang_paneel, text="Nog niet gestart", font=FONT_NORMAAL,
            bg=PANEL, fg=TEKST_DIM, wraplength=340, justify="left")
        self.status_label.pack(anchor="w", padx=14)
        self.voortgangsbalk = ttk.Progressbar(
            voortgang_paneel, orient="horizontal", mode="determinate", length=100)
        self.voortgangsbalk.pack(fill="x", padx=14, pady=(6, 4))
        self.voortgang_detail_label = tk.Label(
            voortgang_paneel, text="", font=FONT_KLEIN, bg=PANEL, fg=TEKST_DIM,
            wraplength=340, justify="left")
        self.voortgang_detail_label.pack(anchor="w", padx=14, pady=(0, 12))

        tellers_paneel = Paneel(ouder)
        tellers_paneel.pack(fill="x")
        tk.Label(tellers_paneel, text="Tellers", font=FONT_VET,
                 bg=PANEL, fg=TEKST).pack(anchor="w", padx=14, pady=(12, 8))
        self.teller_labels = {}
        for key, titel, kleur in [
            ("al_aanwezig", "Al aanwezig", TEKST_DIM),
            ("toegevoegd", "Toegevoegd", GROEN),
            ("bijgewerkt", "Bijgewerkt", GROEN),
            ("verwijderd", "Verwijderd", ORANJE),
            ("fouten", "Fouten", ROOD),
        ]:
            rij = tk.Frame(tellers_paneel, bg=PANEL)
            rij.pack(fill="x", padx=14, pady=2)
            tk.Label(rij, text=titel, font=FONT_NORMAAL, bg=PANEL, fg=TEKST_DIM,
                     anchor="w").pack(side="left")
            waarde_label = tk.Label(rij, text="0", font=FONT_VET, bg=PANEL, fg=kleur)
            waarde_label.pack(side="right")
            self.teller_labels[key] = waarde_label
        tk.Frame(tellers_paneel, bg=PANEL, height=10).pack()

    # -- Rechterkolom: activiteitenlog en afwijkingenlog ------------------

    def _bouw_activiteit_en_afwijkingen(self, ouder):
        verdeler = tk.PanedWindow(ouder, orient="vertical", bg=BG,
                                  sashwidth=6, sashrelief="flat")
        verdeler.pack(fill="both", expand=True)

        activiteit_paneel = Paneel(verdeler)
        verdeler.add(activiteit_paneel, minsize=200)
        tk.Label(activiteit_paneel, text="Activiteit (alle bestanden, live)",
                 font=FONT_VET, bg=PANEL, fg=TEKST).pack(anchor="w", padx=14, pady=(12, 6))
        activiteit_binnen = tk.Frame(activiteit_paneel, bg=PANEL)
        activiteit_binnen.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        scroll1 = tk.Scrollbar(activiteit_binnen)
        scroll1.pack(side="right", fill="y")
        self.activiteiten_log = tk.Text(
            activiteit_binnen, bg=LOG_BG, fg=TEKST, font=FONT_MONO,
            wrap="word", relief="flat", yscrollcommand=scroll1.set,
            highlightbackground=PANEL_RAND, highlightthickness=1)
        self.activiteiten_log.pack(fill="both", expand=True)
        scroll1.config(command=self.activiteiten_log.yview)
        self.activiteiten_log.tag_config("ok", foreground=GROEN)
        self.activiteiten_log.tag_config("fout", foreground=ROOD)
        self.activiteiten_log.tag_config("waarschuwing", foreground=ORANJE)
        self.activiteiten_log.tag_config("info", foreground=TEKST_DIM)

        afwijking_paneel = Paneel(verdeler)
        verdeler.add(afwijking_paneel, minsize=140)
        afwijking_kop = tk.Frame(afwijking_paneel, bg=PANEL)
        afwijking_kop.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(afwijking_kop, text="Afwijkingen (fouten en waarschuwingen)",
                 font=FONT_VET, bg=PANEL, fg=TEKST).pack(side="left")
        RondeKnop(afwijking_kop, "Alles kopieren", kleur=PANEL, tekstkleur=TEKST,
                  highlightbackground=PANEL_RAND, highlightthickness=1,
                  command=self._kopieer_afwijkingen).pack(side="right")
        afwijking_binnen = tk.Frame(afwijking_paneel, bg=PANEL)
        afwijking_binnen.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        scroll2 = tk.Scrollbar(afwijking_binnen)
        scroll2.pack(side="right", fill="y")
        self.afwijkingen_log = tk.Text(
            afwijking_binnen, bg=LOG_BG_AFW, fg=TEKST, font=FONT_MONO,
            wrap="word", relief="flat", yscrollcommand=scroll2.set,
            highlightbackground=PANEL_RAND, highlightthickness=1)
        self.afwijkingen_log.pack(fill="both", expand=True)
        scroll2.config(command=self.afwijkingen_log.yview)
        self.afwijkingen_log.tag_config("fout", foreground=ROOD)
        self.afwijkingen_log.tag_config("waarschuwing", foreground=ORANJE)

    def _kopieer_afwijkingen(self):
        inhoud = self.afwijkingen_log.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(inhoud)

    # -- Veiligheidsnet: een achtergrondthread die crasht door een
    #    onverwachte fout mag NOOIT stilletjes verdwijnen - vooral
    #    kritiek in een .pyw-toepassing zonder consolevenster, waar
    #    een onafgevangen fout anders gewoon nergens te zien is.

    def _start_veilige_thread(self, functie, beschrijving):
        def veilig_uitvoeren():
            try:
                functie()
            except Exception as e:
                import traceback
                details = traceback.format_exc()
                self.bestand_logger.schrijf(
                    f"ONVERWACHTE FOUT in {beschrijving}: {e}\n{details}", "fout")
                self.after(0, lambda: self._toon_onverwachte_fout(beschrijving, e))
        threading.Thread(target=veilig_uitvoeren, daemon=True).start()

    def _toon_onverwachte_fout(self, beschrijving, fout):
        if not self.winfo_exists():
            return
        self._toon_in_afwijkingen(
            f"ONVERWACHTE FOUT in {beschrijving}: {fout} -- zie logbestand voor details.",
            "fout")
        messagebox.showerror(
            "Onverwachte fout",
            f"Er ging iets onverwacht mis in {beschrijving}:\n\n{fout}\n\n"
            f"Details staan in het logbestand:\n{self.bestand_logger.pad}")

    # -- Inventarisatie ---------------------------------------------------

    def _begin_onderzoek(self):
        self.onderzoek_engine = SyncEngine(
            self.taken,
            on_log=self._log,
            on_voortgang=self._onderzoek_voortgang_callback,
        )
        self._start_veilige_thread(self.onderzoek_engine.onderzoek_bronnen, "inventarisatie")

    def _sla_tellen_over(self):
        self.onderzoek_engine._stop_gevraagd = True
        self.onderzoek_balk.stop()
        self.onderzoek_balk.config(mode="determinate", value=0)
        self.onderzoek_label.config(
            text="Tellen overgeslagen - totaal aantal bestanden/bytes blijft "
                 "onbekend - de synchronisatie kan wel gewoon starten, maar "
                 "toont dan een groeiende teller in plaats van een percentage.")
        self.sla_tellen_over_knop.config(state="disabled")
        self.start_knop.config(state="normal")
        self._tellen_overgeslagen = True

    def _onderzoek_voortgang_callback(self, voortgang: SyncVoortgang):
        def doe():
            if not self.winfo_exists():
                return
            if voortgang.fase == "onderzoeken":
                self.onderzoek_label.config(
                    text=f"{voortgang.onderzocht_bestanden:,} bestanden gevonden tot nu toe "
                         f"({formatteer_bytes(voortgang.totaal_bytes)})...")
            else:
                self.onderzoek_balk.stop()
                self.onderzoek_balk.config(mode="determinate", value=100)
                self.sla_tellen_over_knop.config(state="disabled")
                if voortgang.totaal_bestanden == 0:
                    self.onderzoek_label.config(
                        text="Geen bestanden gevonden (of bron niet bereikbaar). "
                             "Test de verbinding via de reparatieknoppen hierboven.")
                    self.start_knop.config(state="disabled")
                else:
                    schatting = formatteer_duur(voortgang.totaal_bytes / (20 * 1024 * 1024))
                    self.onderzoek_label.config(
                        text=f"{voortgang.totaal_bestanden:,} bestanden, "
                             f"{formatteer_bytes(voortgang.totaal_bytes)} totaal.\n"
                             f"Ruwe schatting: {schatting}.")
                    self.start_knop.config(state="normal")
        self.after(0, doe)

    # -- Synchronisatie zelf -----------------------------------------------

    def _start_synchronisatie(self):
        if self.verwijder_wezen_var.get():
            bevestigd = messagebox.askyesno(
                "Bevestig: bestanden worden verwijderd",
                "Je hebt 'echte sync' aangezet: bestanden en lege mappen in het "
                "doel die niet meer in de bron staan worden VERWIJDERD. Dit kan "
                "niet ongedaan gemaakt worden.\n\nWeet je het zeker?")
            if not bevestigd:
                return

        self.start_knop.config(state="disabled")
        self.stop_knop.config(state="normal")
        self.voortgangsbalk.config(mode="determinate", value=0)
        self.status_label.config(text="Synchronisatie wordt gestart...", fg=TEKST)

        self.engine = SyncEngine(
            self.taken,
            on_log=self._log,
            on_voortgang=self._voortgang_callback,
            on_pauze=self._pauze_callback,
            on_klaar=self._klaar_callback,
            verwijder_wezen_bestanden=self.verwijder_wezen_var.get(),
        )
        if not self._tellen_overgeslagen:
            self.engine.voortgang.totaal_bestanden = self.onderzoek_engine.voortgang.totaal_bestanden
            self.engine.voortgang.totaal_bytes = self.onderzoek_engine.voortgang.totaal_bytes
        self.engine.voortgang.totaal_onbekend = self._tellen_overgeslagen

        self.engine_thread = None
        self._start_veilige_thread(self.engine.start, "synchronisatie")

    def _voortgang_callback(self, voortgang: SyncVoortgang):
        def doe():
            if not self.winfo_exists():
                return
            if voortgang.totaal_onbekend:
                if str(self.voortgangsbalk.cget("mode")) != "indeterminate":
                    self.voortgangsbalk.config(mode="indeterminate")
                    self.voortgangsbalk.start(20)
            elif voortgang.totaal_bestanden > 0:
                if str(self.voortgangsbalk.cget("mode")) == "indeterminate":
                    self.voortgangsbalk.stop()
                self.voortgangsbalk.config(mode="determinate")
                percentage = (voortgang.verwerkt_bestanden / voortgang.totaal_bestanden) * 100
                self.voortgangsbalk["value"] = percentage

            verstreken = time.time() - voortgang.gestart_om if voortgang.gestart_om else 0
            resterend_tekst = ""
            if (not voortgang.totaal_onbekend and voortgang.verwerkt_bestanden > 0
                    and voortgang.totaal_bestanden > 0):
                per_bestand = verstreken / voortgang.verwerkt_bestanden
                resterend = per_bestand * (voortgang.totaal_bestanden - voortgang.verwerkt_bestanden)
                resterend_tekst = f"\nNog ongeveer {formatteer_duur(resterend)}"

            if voortgang.fase == "gepauzeerd":
                status_tekst, kleur = "Gepauzeerd - verbinding wordt herstelt...", ORANJE
            elif voortgang.fase == "klaar":
                status_tekst, kleur = "Klaar", GROEN
            else:
                status_tekst, kleur = "Synchronisatie loopt", TEKST

            if voortgang.totaal_onbekend:
                aantal_tekst = f"{voortgang.verwerkt_bestanden:,} bestanden verwerkt (totaal onbekend)"
            else:
                aantal_tekst = f"{voortgang.verwerkt_bestanden:,} / {voortgang.totaal_bestanden:,} bestanden"

            self.status_label.config(
                text=f"{status_tekst}\n{aantal_tekst}{resterend_tekst}", fg=kleur)
            self.voortgang_detail_label.config(text=f"Huidig: {voortgang.huidige_bestand}")

            self.teller_labels["al_aanwezig"].config(text=f"{voortgang.al_aanwezig:,}")
            self.teller_labels["toegevoegd"].config(text=f"{voortgang.toegevoegd:,}")
            self.teller_labels["bijgewerkt"].config(text=f"{voortgang.bijgewerkt:,}")
            self.teller_labels["verwijderd"].config(text=f"{voortgang.verwijderd:,}")
            self.teller_labels["fouten"].config(text=f"{voortgang.fouten:,}")
        self.after(0, doe)

    def _pauze_callback(self, reden: str) -> bool:
        self._wacht_op_pauze_antwoord.clear()

        def toon_dialoog():
            self._log_afwijking(reden, "fout")
            antwoord = messagebox.askyesno(
                "Synchronisatie gepauzeerd",
                f"{reden}\n\nAutomatisch herstel proberen (HDD-cyclus, daarna "
                f"LanManFix)?\n\n(Bij 'Nee' stopt de synchronisatie volledig - "
                f"je kunt dan handmatig een reparatieknop hierboven gebruiken.)")
            self._pauze_antwoord = antwoord
            self._wacht_op_pauze_antwoord.set()

        self.after(0, toon_dialoog)
        self._wacht_op_pauze_antwoord.wait()
        return self._pauze_antwoord

    def _vraag_stoppen(self):
        if messagebox.askyesno("Stoppen", "Synchronisatie nu stoppen?"):
            if self.engine:
                self.engine.stop()
            self.stop_knop.config(state="disabled", text="Wordt gestopt...")

    def _klaar_callback(self, voortgang: SyncVoortgang):
        def doe():
            if not self.winfo_exists():
                return
            self.stop_knop.config(state="disabled", text="Stoppen")
            self.start_knop.config(state="normal", text="Opnieuw synchroniseren")
            if voortgang.fase == "gepauzeerd":
                self._log_afwijking(
                    "Synchronisatie definitief gepauzeerd - storing kon niet "
                    "automatisch worden opgelost. Gebruik de reparatieknoppen "
                    "of probeer het later opnieuw.", "fout")
            elif voortgang.overgeslagen_door_storing:
                self._log_afwijking(
                    f"Synchronisatie klaar, maar {len(voortgang.overgeslagen_door_storing)} "
                    f"bestand(en) zijn definitief niet gelukt.", "waarschuwing")
            else:
                self._log("Synchronisatie volledig afgerond, geen openstaande fouten.", "ok")
        self.after(0, doe)


# =================================================================
# Hoofdvenster - schakelt tussen scherm 1 en scherm 2
# (PC Image Backup is verhuisd naar het losstaande pinas_image_backup.pyw)
# =================================================================

class PiNasSyncVenster(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Pi NAS Sync — Pi NAS Suite (bijgewerkt: {BIJGEWERKT})")
        self.geometry("1180x860")
        self.configure(bg=BG)
        self.minsize(1000, 700)

        self._huidig_scherm = None
        self._toon_bron_doel_scherm()

    def _wissel_scherm(self, nieuw_scherm_widget):
        if self._huidig_scherm is not None:
            if isinstance(self._huidig_scherm, SyncScherm):
                self._huidig_scherm.stop_achtergrondwerk()
            self._huidig_scherm.destroy()
        self._huidig_scherm = nieuw_scherm_widget
        self._huidig_scherm.pack(fill="both", expand=True)

    def _toon_bron_doel_scherm(self):
        scherm = BronDoelScherm(self, op_doorgaan=self._toon_sync_scherm)
        self._wissel_scherm(scherm)

    def _toon_sync_scherm(self, taken):
        scherm = SyncScherm(self, taken, op_terug=self._toon_bron_doel_scherm)
        self._wissel_scherm(scherm)


if __name__ == "__main__":
    app = PiNasSyncVenster()
    app.mainloop()
