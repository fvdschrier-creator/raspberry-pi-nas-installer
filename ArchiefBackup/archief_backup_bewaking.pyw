#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Archief Backup Bewaking - MODEL / prototype (v0.3)
============================================
Terugkerende integriteitscontrole en veilige backup-sync van
    BRON  (Z:\\ArchiefBackup)  ->  BACKUP (H:\\SpiegelBackup)

(8 augustus 2026: Fase 2 van de Qnap-rename is nu volledig - Z heet
ArchiefBackup, H heet SpiegelBackup, de quarantainemap heet
_ArchiefBackup_verwijderd. Beide kanten gebruiken nu een dynamisch
opgezochte schijfletter i.p.v. een hardcoded Z:/H:.)

Bron (Z:) is ALTIJD leidend en wordt NOOIT aangeraakt. Verwijderen gebeurt
alleen aan de backup-kant (H:), want de backup volgt de bron.

Twee gescheiden acties, controleren altijd eerst:
  1. CONTROLEREN (alleen lezen): welke bestanden ontbreken in de backup of
     wijken af? Toont ALLEEN afwijkingen. Exporteerbaar naar tekstrapport.
  2. SYNCHRONISEREN (Z leidend), met keuze uit drie modi (veiligheidsladder):
       a. Alleen aanvullen        - raakt niets aan in H (veiligst)
       b. Spiegel met quarantaine - overtollige H-bestanden -> H:\\_ArchiefBackup_verwijderd
                                     (aanbevolen, standaard)
       c. Spiegel met verwijderen - overtollige H-bestanden direct weg
                                     (extra bevestiging vereist)

Voortgang: verstreken tijd, live teller, tempo en een MEEBEWEGENDE schatting
"~nog Xm" (zoals de resterende-bereik-indicator van een auto: een inschatting
die zich met het tempo bijstelt). De scan gebruikt het onthouden totaal van de
vorige controle als verwachting.

Veiligheid:
  - Sync kan pas NA een controle.
  - Harde stop als de bron leeg/onbereikbaar is (bijv. Z: niet gemount).
  - Quarantaine staat NAAST H:\\SpiegelBackup en wordt bij scannen overgeslagen.
"""

import os
import sys
import json
import time
import shutil
import hashlib
import threading
import queue
import datetime
import configparser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

VERSIE = "1.0.0"   # als suite-module (zie version.py SUITE_VERSIE)

STANDAARD_BRON   = r"Z:\ArchiefBackup"
STANDAARD_BACKUP = r"H:\SpiegelBackup"
MIN_BRON_BESTANDEN = 50
MTIME_MARGE = 2
ETA_WARMUP = 15            # sec voordat een schatting getoond wordt
RATE_VENSTER = 12          # sec; tempo over dit recente venster
ONTHOUD_BESTAND = os.path.join(os.path.expanduser("~"), ".archief_backup_bewaking.json")

# Thema uit het centrale suite-thema (Gedeeld/pinas_theme.py), zodat deze
# module automatisch meekleurt met de rest van de Pi NAS Suite.
import os as _os2, sys as _sys2
def _voeg_gedeeld_toe_aan_pad():
    hier = _os2.path.dirname(_os2.path.abspath(__file__))
    for pad in (_os2.path.join(hier, "..", "Gedeeld"),
                _os2.path.join("C:\\", "PiNAS", "Gedeeld")):
        pad = _os2.path.abspath(pad)
        if _os2.path.isdir(pad) and pad not in _sys2.path:
            _sys2.path.insert(0, pad)
_voeg_gedeeld_toe_aan_pad()
try:
    import pinas_theme as _t
    _BG, _PANEL, _PANEL2 = _t.BG, _t.PANEL, _t.PANEL2
    _FG, _DIM = _t.FG, _t.DIM
    _OK, _ERR, _WARN, _BLUE = _t.OK_C, _t.ERR_C, _t.WARN, _t.BLUE
    _THEMA = getattr(_t, "HUIDIG_THEMA", "donker")
except Exception:
    _BG, _PANEL, _PANEL2 = "#0f172a", "#1e293b", "#334155"
    _FG, _DIM, _OK, _ERR, _WARN, _BLUE = "#e2e8f0", "#94a3b8", "#22c55e", "#ef4444", "#f59e0b", "#3b82f6"
    _THEMA = "donker"
try:
    from version import SUITE_VERSIE
except Exception:
    SUITE_VERSIE = "1.2.0"

# 8 augustus 2026: BRON was hardcoded op "Z:\Qnap_Schoon" (STANDAARD_BRON
# hierboven) - brak zodra de Backup-schijf niet op Z: gekoppeld was
# (dynamische schijfletters, zie pinas_schijven.py, zelfde patroon als
# pinas_backup_beheer.pyw's _backup_letter()). Hier hetzelfde toepassen:
# de echte gekoppelde letter opzoeken, met STANDAARD_BRON alleen als
# allerlaatste terugval wanneer pinas_schijven niet beschikbaar is.
try:
    import pinas_schijven as _schijven
except Exception:
    _schijven = None

_cfg = configparser.ConfigParser()
_cfg_pad = os.path.join(os.path.dirname(os.path.abspath(__file__)), "picontrol.cfg")
if os.path.exists(_cfg_pad):
    _cfg.read(_cfg_pad, encoding="utf-8")
_PI_IP = _cfg.get("pi", "ip", fallback="UW_PI_IP_ADRES")


def _backup_letter():
    """Geeft de werkelijke, huidige stationsletter voor de Backup-share
    terug (i.p.v. altijd 'Z' aan te nemen) - zelfde aanpak als
    pinas_backup_beheer.pyw's _backup_letter()."""
    if _schijven is None:
        return "Z"
    try:
        naam = _cfg.get("schijven", "Z", fallback="Backup") if _cfg.has_section("schijven") else "Backup"
    except Exception:
        naam = "Backup"
    try:
        letter = _schijven.vind_letter_of_terugval(naam, "Z", _PI_IP)
        return letter.rstrip(":\\") if letter else "Z"
    except Exception:
        return "Z"


def _bron_standaard():
    """Dynamische BRON-standaardwaarde op basis van de echte
    Backup-schijfletter, i.p.v. de hardcoded STANDAARD_BRON."""
    return f"{_backup_letter()}:\\ArchiefBackup"


def _spiegel_letter():
    """Geeft de werkelijke, huidige stationsletter voor de Spiegel
    Backup-share terug (i.p.v. altijd 'H' aan te nemen) - zelfde aanpak
    als _backup_letter(). Spiegel Backup is optioneel (niet elke
    installatie heeft deze schijf); als de share niet gevonden wordt,
    valt dit gewoon terug op 'H'."""
    if _schijven is None:
        return "H"
    try:
        letter = _schijven.vind_letter_of_terugval("SpiegelBackup", "H", _PI_IP)
        return letter.rstrip(":\\") if letter else "H"
    except Exception:
        return "H"


def _backup_doel_standaard():
    """Dynamische BACKUP-standaardwaarde op basis van de echte Spiegel
    Backup-schijfletter, i.p.v. de hardcoded STANDAARD_BACKUP."""
    return f"{_spiegel_letter()}:\\SpiegelBackup"

NAVY = "#2f3b47"                       # header blijft zelfde kleur in beide thema's (16 juli 2026: navy -> zacht zakelijk blauw)
GROEN, ROOD, ORANJE, BLAUW = _OK, _ERR, _WARN, _BLUE
_LOG = "#0b1220" if _THEMA == "donker" else "#f8fafc"
_HELDER = "#ffffff" if _THEMA == "donker" else _FG
THEMES = {_THEMA: dict(BG=_BG, PANEL=_PANEL, PANEL2=_PANEL2,
                       TEKST=_FG, DIM=_DIM, LOG=_LOG, HELDER=_HELDER)}
UIT_BG, UIT_FG = "#3f4b5b", "#eef2f7"


def _nl(n):
    return f"{n:,}".replace(",", ".")


# ── Kernlogica (puur, los testbaar) ──────────────────────────────────────────
def _quarantaine_root(backup):
    return os.path.join(os.path.dirname(os.path.abspath(backup)), "_ArchiefBackup_verwijderd")


def scan_boom(root, telcb=None):
    index = {}
    root = os.path.abspath(root)
    qu = os.path.abspath(_quarantaine_root(root))
    aantal = 0
    for dirpad, mappen, bestanden in os.walk(root):
        if os.path.abspath(dirpad).startswith(qu):
            mappen[:] = []
            continue
        for naam in bestanden:
            vol = os.path.join(dirpad, naam)
            try:
                st = os.stat(vol)
            except OSError:
                continue
            index[os.path.relpath(vol, root)] = (st.st_size, st.st_mtime)
            aantal += 1
            if telcb and aantal % 2000 == 0:
                telcb(aantal)
    if telcb:
        telcb(aantal)
    return index


def sha256(pad, blok=1024 * 1024):
    h = hashlib.sha256()
    with open(pad, "rb") as f:
        for stuk in iter(lambda: f.read(blok), b""):
            h.update(stuk)
    return h.hexdigest()


def vergelijk(bron_idx, backup_idx, deepcheck, bron_root, backup_root):
    ontbreekt, verschilt, extra = [], [], []
    for rel, (bg, bm) in bron_idx.items():
        if rel not in backup_idx:
            ontbreekt.append(rel)
        else:
            hg, hm = backup_idx[rel]
            if (bg != hg) or (abs(bm - hm) > MTIME_MARGE):
                verschilt.append(rel)
            elif deepcheck:
                try:
                    if sha256(os.path.join(bron_root, rel)) != sha256(os.path.join(backup_root, rel)):
                        verschilt.append(rel)
                except OSError:
                    verschilt.append(rel)
    for rel in backup_idx:
        if rel not in bron_idx:
            extra.append(rel)
    return ontbreekt, verschilt, extra


def duur(seconden):
    m, s = divmod(int(seconden), 60)
    h, m = divmod(m, 60)
    return (f"{h}u{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s" if m else f"{s}s")


def mensgrootte(b):
    """Bytes naar leesbare grootte (2.71 TB)."""
    b = float(b)
    for e in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024 or e == "TB":
            return f"{b:.2f} {e}" if e not in ("B", "KB") else f"{int(b)} {e}"
        b /= 1024


# ── GUI ──────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Archief Backup Bewaking \u2014 Pi NAS Suite v{SUITE_VERSIE}")
        self.geometry("900x730")
        self.thema = _THEMA
        self.q = queue.Queue()
        self._laatste = None
        self._bezig = False
        self._t0 = None
        self._themed = []
        # voortgang / ETA
        self._prog_fase = None      # 'scan' of 'sync'
        self._prog_label = ""       # 'gescand' / 'verwerkt'
        self._prog_n = 0
        self._prog_verwacht = None  # verwacht totaal (int of None)
        self._prog_samples = []     # [(t, n)]
        self._onthoud = self._laad_onthoud()
        self._bouw_ui()
        self._pas_thema_toe()
        self.after(100, self._verwerk_queue)
        self._tik()

    # ---- onthouden totalen ----
    def _laad_onthoud(self):
        try:
            with open(ONTHOUD_BESTAND, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _bewaar_onthoud(self):
        try:
            with open(ONTHOUD_BESTAND, "w", encoding="utf-8") as f:
                json.dump(self._onthoud, f)
        except OSError:
            pass

    def _reg(self, w, rol):
        self._themed.append((w, rol)); return w

    # ---- UI ----
    def _bouw_ui(self):
        self.configure(bg=THEMES[self.thema]["BG"])
        hdr = tk.Frame(self, bg=NAVY, pady=12); hdr.pack(fill="x")
        tk.Label(hdr, text="\U0001f9ea  Archief Backup Bewaking",
                 font=("Segoe UI", 15, "bold"), bg=NAVY, fg="#ffffff").pack(side="left", padx=16)
        tk.Label(hdr, text=f"Bron ({_backup_letter()}:) is leidend \u00b7 backup = {_spiegel_letter()}:",
                 font=("Segoe UI", 9), bg=NAVY, fg="#9fc2e0").pack(side="left")
        body = self._reg(tk.Frame(self), "BG"); body.pack(fill="both", expand=True)
        pad = self._reg(tk.Frame(body), "BG"); pad.pack(fill="x", padx=16, pady=(10, 4))
        self.var_bron   = tk.StringVar(value=_bron_standaard())
        self.var_backup = tk.StringVar(value=_backup_doel_standaard())
        self._padrij(pad, "Bron (leidend):", self.var_bron, 0)
        self._padrij(pad, f"Backup ({_spiegel_letter()}:):", self.var_backup, 1)

        opt = self._reg(tk.Frame(body), "BG"); opt.pack(fill="x", padx=16, pady=(2, 4))
        self.var_deep = tk.BooleanVar(value=False)
        cb = tk.Checkbutton(opt, text="Diepe controle (SHA256) - traag, alleen bij twijfel",
                            variable=self.var_deep, font=("Segoe UI", 9))
        self._reg(cb, "check"); cb.pack(anchor="w")

        mf = self._reg(tk.LabelFrame(body, text=" Bij synchroniseren ",
                                     font=("Segoe UI", 9, "bold")), "labelframe")
        mf.pack(fill="x", padx=16, pady=(2, 6))
        self.var_modus = tk.StringVar(value="quarantaine")
        _h = _spiegel_letter()
        for waarde, tekst in (
            ("aanvullen",   f"Alleen aanvullen  -  kopieert ontbrekende/gewijzigde bestanden naar {_h}, verwijdert niets uit {_h} (veiligst)"),
            ("quarantaine", f"Spiegel met quarantaine  -  kopieert naar {_h} en verplaatst overtollige {_h}-bestanden naar _ArchiefBackup_verwijderd (aanbevolen)"),
            ("verwijderen", f"Spiegel met verwijderen  -  kopieert naar {_h} en verwijdert overtollige {_h}-bestanden direct (extra bevestiging)"),
        ):
            rb = tk.Radiobutton(mf, text=tekst, variable=self.var_modus, value=waarde,
                                font=("Segoe UI", 9), anchor="w")
            self._reg(rb, "check"); rb.pack(fill="x", padx=6, pady=1)

        kn = self._reg(tk.Frame(body), "BG"); kn.pack(fill="x", padx=16, pady=4)
        self.btn_check = tk.Button(kn, text="\U0001f50d  Controleren (alleen lezen)",
                                   command=self._start_controle, bg=BLAUW, fg="#ffffff",
                                   font=("Segoe UI", 10, "bold"), relief="flat",
                                   padx=14, pady=8, cursor="hand2")
        self.btn_check.pack(side="left")
        self.btn_sync = tk.Button(kn, text="\u21bb  Synchroniseren",
                                  command=self._start_sync, font=("Segoe UI", 10, "bold"),
                                  relief="flat", padx=14, pady=8, cursor="hand2", state="disabled")
        self.btn_sync.pack(side="left", padx=(10, 0))
        self.btn_export = tk.Button(kn, text="\U0001f4be  Rapport opslaan",
                                    command=self._export, font=("Segoe UI", 10),
                                    relief="flat", padx=12, pady=8, cursor="hand2", state="disabled")
        self.btn_export.pack(side="right")
        self._knop_uit(self.btn_sync)
        self._knop_uit(self.btn_export)

        self.progress = ttk.Progressbar(body, mode="indeterminate")
        self.progress.pack(fill="x", padx=16, pady=(2, 2))

        strook = self._reg(tk.Frame(body), "BG"); strook.pack(fill="x", padx=16)
        self.lbl_sam = self._reg(tk.Label(strook, text="Nog geen controle gedraaid.",
                                          font=("Segoe UI", 10), anchor="w"), "sam")
        self.lbl_sam.pack(side="left")
        self.lbl_tijd = self._reg(tk.Label(strook, text="", font=("Consolas", 9), anchor="e"), "dim")
        self.lbl_tijd.pack(side="right")

        wrap = self._reg(tk.Frame(body), "BG"); wrap.pack(fill="both", expand=True, padx=16, pady=8)
        self.txt = tk.Text(wrap, font=("Consolas", 9), relief="flat", wrap="none")
        self._reg(self.txt, "log"); self.txt.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(wrap, command=self.txt.yview); sb.pack(side="right", fill="y")
        self.txt.config(yscrollcommand=sb.set)
        for tag, kleur in (("ok", GROEN), ("fout", ROOD), ("waarsch", ORANJE), ("kop", BLAUW)):
            self.txt.tag_config(tag, foreground=kleur)

    def _padrij(self, parent, label, var, rij):
        self._reg(tk.Label(parent, text=label, width=14, anchor="w",
                           font=("Segoe UI", 9)), "tekst").grid(row=rij, column=0, sticky="w", pady=2)
        self._reg(tk.Entry(parent, textvariable=var, relief="flat", width=68),
                  "entry").grid(row=rij, column=1, sticky="we", padx=6)
        self._reg(tk.Button(parent, text="...", command=lambda v=var: self._kies_map(v),
                            relief="flat", cursor="hand2"), "knop2").grid(row=rij, column=2)
        parent.columnconfigure(1, weight=1)

    def _kies_map(self, var):
        m = filedialog.askdirectory(initialdir=var.get() or "/")
        if m:
            var.set(os.path.normpath(m))

    # ---- knop aan/uit-uiterlijk ----
    def _knop_uit(self, btn):
        btn.config(state="disabled", bg=UIT_BG, fg=UIT_FG)

    def _knop_aan(self, btn, bg, fg):
        btn.config(state="normal", bg=bg, fg=fg)

    # ---- Thema ----
    def _pas_thema_toe(self):
        t = THEMES[self.thema]
        self.configure(bg=t["BG"])
        for w, rol in self._themed:
            try:
                if rol == "BG":
                    w.config(bg=t["BG"])
                elif rol == "tekst":
                    w.config(bg=t["BG"], fg=t["TEKST"])
                elif rol in ("dim", "sam"):
                    w.config(bg=t["BG"], fg=t["DIM"] if rol == "dim" else t["TEKST"])
                elif rol == "entry":
                    w.config(bg=t["PANEL"], fg=t["TEKST"], insertbackground=t["TEKST"])
                elif rol == "knop2":
                    w.config(bg=t["PANEL2"], fg=t["TEKST"])
                elif rol == "check":
                    # radiobutton/checkbox-tekst: helder (wit in donker thema)
                    w.config(bg=t["BG"], fg=t["HELDER"], selectcolor=t["PANEL"],
                             activebackground=t["BG"], activeforeground=t["HELDER"])
                elif rol == "labelframe":
                    w.config(bg=t["BG"], fg=t["DIM"])
                elif rol == "log":
                    w.config(bg=t["LOG"], fg=t["TEKST"], insertbackground=t["TEKST"])
            except tk.TclError:
                pass

    # ---- tijd + ETA-tik ----
    def _tik(self):
        if self._bezig and self._t0:
            el = time.time() - self._t0
            stukjes = [f"verstreken: {duur(el)}"]
            if self._prog_fase:
                n = self._prog_n
                verwacht = self._prog_verwacht
                # tempo over recent venster
                tempo = None
                s = self._prog_samples
                if len(s) >= 2 and (s[-1][0] - s[0][0]) > 0:
                    tempo = (s[-1][1] - s[0][1]) / (s[-1][0] - s[0][0])
                tel = f"{self._prog_label}: {_nl(n)}"
                if verwacht:
                    tel += f" / ~{_nl(verwacht)}"
                stukjes = [tel]
                if tempo and tempo > 0:
                    stukjes.append(f"~{_nl(int(tempo))}/s")
                # ETA: alleen na warmup en met tempo
                if tempo and tempo > 0 and el > ETA_WARMUP and verwacht and n < verwacht:
                    eta = (verwacht - n) / tempo
                    stukjes.append(f"~nog {duur(eta)}")
                else:
                    stukjes.append(f"{duur(el)}")
            self.lbl_tijd.config(text="   \u00b7   ".join(stukjes))
        self.after(1000, self._tik)

    def _prog(self, fase, label, n, verwacht):
        self.q.put(("prog", fase, label, n, verwacht))

    # ---- logging/queue ----
    def log(self, tekst, tag=None):
        self.q.put(("log", tekst, tag))

    def _verwerk_queue(self):
        try:
            while True:
                soort, *rest = self.q.get_nowait()
                if soort == "log":
                    tekst, tag = rest
                    self.txt.insert("end", tekst + "\n", tag or "")
                    self.txt.see("end")
                elif soort == "prog":
                    fase, label, n, verwacht = rest
                    self._prog_fase, self._prog_label = fase, label
                    self._prog_n, self._prog_verwacht = n, verwacht
                    if fase == "sync":
                        try:
                            self.progress.config(value=n)
                        except tk.TclError:
                            pass
                    now = time.time()
                    self._prog_samples.append((now, n))
                    self._prog_samples = [(t, c) for (t, c) in self._prog_samples
                                          if now - t <= RATE_VENSTER] or self._prog_samples[-1:]
                elif soort == "klaar":
                    self._op_klaar(*rest)
        except queue.Empty:
            pass
        self.after(100, self._verwerk_queue)

    def _reset_prog(self):
        self._prog_fase = None; self._prog_n = 0
        self._prog_verwacht = None; self._prog_samples = []

    # ---- Controle ----
    def _start_controle(self):
        if self._bezig:
            return
        self.txt.delete("1.0", "end")
        self._bezig = True; self._t0 = time.time(); self._reset_prog()
        self.btn_check.config(state="disabled")
        self._knop_uit(self.btn_sync); self._knop_uit(self.btn_export)
        try:
            self.progress.config(mode="indeterminate", value=0)
        except tk.TclError:
            pass
        self.progress.start(12); self.lbl_sam.config(text="Bezig met controleren...")
        threading.Thread(target=self._controle_worker, daemon=True).start()

    def _controle_worker(self):
        bron = self.var_bron.get().strip(); backup = self.var_backup.get().strip()
        try:
            self.log("=== CONTROLE (alleen lezen) ===", "kop")
            self.log(f"Bron:   {bron}"); self.log(f"Backup: {backup}")
            fout = self._veiligheid(bron, backup, voor_sync=False)
            if fout:
                self.log("STOP: " + fout, "fout"); self.q.put(("klaar", None, fout)); return

            self.log("Bron scannen...")
            verw_b = self._onthoud.get("bron")
            bron_idx = scan_boom(bron, lambda n: self._prog("scan", "gescand (bron)", n, verw_b))
            self.log(f"   {_nl(len(bron_idx))} bestanden in bron.")
            if len(bron_idx) < MIN_BRON_BESTANDEN:
                fout = (f"Bron heeft maar {len(bron_idx)} bestanden (< {MIN_BRON_BESTANDEN}). "
                        "Mogelijk niet gemount. Gestopt.")
                self.log("STOP: " + fout, "fout"); self.q.put(("klaar", None, fout)); return

            self.log("Backup scannen...")
            verw_h = self._onthoud.get("backup")
            backup_idx = (scan_boom(backup, lambda n: self._prog("scan", "gescand (backup)", n, verw_h))
                          if os.path.isdir(backup) else {})
            self.log(f"   {_nl(len(backup_idx))} bestanden in backup.")

            self.log("Vergelijken...")
            ontbreekt, verschilt, extra = vergelijk(bron_idx, backup_idx, self.var_deep.get(), bron, backup)
            bron_bytes = sum(sz for sz, _ in bron_idx.values())
            backup_bytes = sum(sz for sz, _ in backup_idx.values())
            self._rapport(bron_idx, backup_idx, ontbreekt, verschilt, extra, bron_bytes, backup_bytes)

            # onthoud totalen voor de ETA van de volgende keer
            self._onthoud["bron"] = len(bron_idx)
            self._onthoud["backup"] = len(backup_idx)
            self._bewaar_onthoud()

            self.q.put(("klaar", dict(bron=bron, backup=backup, ontbreekt=ontbreekt,
                                      verschilt=verschilt, extra=extra, totaal=len(bron_idx),
                                      totaal_backup=len(backup_idx), bron_bytes=bron_bytes,
                                      backup_bytes=backup_bytes, seconden=time.time() - self._t0), None))
        except Exception as e:
            self.log(f"FOUT: {e}", "fout"); self.q.put(("klaar", None, str(e)))

    def _rapport(self, bron_idx, backup_idx, ontbreekt, verschilt, extra, bron_bytes, backup_bytes):
        self.log(""); self.log("--- RAPPORT (alleen afwijkingen) ---", "kop")
        in_orde = len(bron_idx) - len(ontbreekt) - len(verschilt)
        self.log(f"In orde: {_nl(in_orde)} van {_nl(len(bron_idx))} bestanden.", "ok")
        for titel, lijst, tag, teken in (
                ("ONTBREEKT in backup", ontbreekt, "fout", "+"),
                ("WIJKT AF (grootte/datum)", verschilt, "waarsch", "~"),
                ("EXTRA in backup (niet meer in bron)", extra, None, "-")):
            if lijst:
                self.log(f"\n{titel} ({len(lijst)}):", tag)
                for r in lijst[:200]:
                    self.log(f"   {teken} {r}", tag)
                if len(lijst) > 200:
                    self.log(f"   ... en nog {len(lijst) - 200} meer", tag)
        if not (ontbreekt or verschilt or extra):
            self.log("\nBackup is volledig gelijk aan de bron. Niets te doen.", "ok")

        # ---- EINDCONTROLE: onafhankelijke totaal-vergelijking Z vs H ----
        self.log(""); self.log("--- EINDCONTROLE (totalen Z vs H) ---", "kop")
        self.log(f"Bron   ({_backup_letter()}): {mensgrootte(bron_bytes)}  \u00b7  {_nl(len(bron_idx))} bestanden")
        self.log(f"Backup ({_spiegel_letter()}): {mensgrootte(backup_bytes)}  \u00b7  {_nl(len(backup_idx))} bestanden")
        if ontbreekt or verschilt:
            self.log("\u26a0 Backup mist of wijkt af van de bron - synchroniseren aanbevolen.", "waarsch")
        elif bron_bytes != backup_bytes or len(bron_idx) != len(backup_idx):
            # bron zit volledig in backup, maar totalen verschillen -> backup heeft extra's
            self.log(f"\u2713 Backup bevat alles uit de bron. ({_spiegel_letter()} is groter door extra bestanden.)", "ok")
        else:
            self.log(f"\u2713 {_backup_letter()} en {_spiegel_letter()} zijn exact gelijk in grootte en aantal.", "ok")

    def _op_klaar(self, res, fout):
        self._bezig = False; self.progress.stop()
        try:
            self.progress.config(mode="indeterminate", value=0)
        except tk.TclError:
            pass
        self._reset_prog()
        self.btn_check.config(state="normal")
        if self._t0:
            self.lbl_tijd.config(text=f"klaar in {duur(time.time() - self._t0)}")
        if fout:
            self.lbl_sam.config(text="Gestopt: " + fout); self._laatste = None; return
        if res is None:
            return
        if "ontbreekt" in res:
            self._laatste = res
            self._knop_aan(self.btn_export, "#475569", "#ffffff")
            o, v, e = len(res["ontbreekt"]), len(res["verschilt"]), len(res["extra"])
            if o or v or e:
                self.lbl_sam.config(text=f"Afwijkingen: {o} ontbreken, {v} wijken af, {e} extra.")
                self._knop_aan(self.btn_sync, ORANJE, "#1f2937")
            else:
                self.lbl_sam.config(text="Backup compleet en gelijk. Geen sync nodig.")
                self._knop_uit(self.btn_sync)

    # ---- Sync ----
    def _start_sync(self):
        r = self._laatste
        if not r:
            messagebox.showinfo("Eerst controleren", "Draai eerst een controle."); return
        modus = self.var_modus.get()
        o, v, e = len(r["ontbreekt"]), len(r["verschilt"]), len(r["extra"])
        _h = _spiegel_letter()
        if modus == "aanvullen":
            wat = f"Naar {_h} kopieren/bijwerken: {o + v}\nOvertollige {_h}-bestanden blijven staan ({e})"
        elif modus == "quarantaine":
            wat = f"Naar {_h} kopieren/bijwerken: {o + v}\nNaar quarantaine: {e}  ({_h}:\\_ArchiefBackup_verwijderd\\<datum-tijd>)"
        else:
            wat = f"Naar {_h} kopieren/bijwerken: {o + v}\nDEFINITIEF VERWIJDEREN uit {_h}: {e}"
        if not messagebox.askyesno("Synchroniseren bevestigen",
                                    f"Modus: {modus}\n\n{wat}\n\nBron ({_backup_letter()}:) wordt niet aangeraakt. Doorgaan?"):
            return
        if modus == "verwijderen" and e:
            if not messagebox.askyesno("Definitief verwijderen",
                                       f"{e} bestanden worden PERMANENT uit {_h} verwijderd "
                                       "(niet naar quarantaine). Zeker weten?"):
                return
        self._bezig = True; self._t0 = time.time(); self._reset_prog()
        self.btn_check.config(state="disabled"); self._knop_uit(self.btn_sync)
        # bepaalde voortgangsbalk: totaal is bekend bij sync
        o2, v2, e2 = len(r["ontbreekt"]), len(r["verschilt"]), len(r["extra"])
        tot = o2 + v2 + (e2 if modus in ("quarantaine", "verwijderen") else 0)
        self.progress.stop()
        self.progress.config(mode="determinate", maximum=max(tot, 1), value=0)
        self.lbl_sam.config(text="Bezig met synchroniseren...")
        threading.Thread(target=self._sync_worker, args=(r, modus), daemon=True).start()

    def _sync_worker(self, r, modus):
        bron, backup = r["bron"], r["backup"]
        try:
            self.log(""); self.log(f"=== SYNCHRONISEREN (modus: {modus}) ===", "kop")
            fout = self._veiligheid(bron, backup, voor_sync=True)
            if fout:
                self.log("STOP: " + fout, "fout"); self.q.put(("klaar", None, fout)); return
            kopielijst = r["ontbreekt"] + r["verschilt"]
            extra = r["extra"] if modus in ("quarantaine", "verwijderen") else []
            totaal = len(kopielijst) + len(extra)
            self._gedaan = 0
            self._sync_fouten = []   # mislukte bestanden verzamelen

            def stap():
                self._gedaan += 1
                if self._gedaan % 100 == 0 or self._gedaan == totaal:
                    self._prog("sync", "verwerkt", self._gedaan, totaal)

            gekop = self._kopieer(bron, backup, kopielijst, stap)
            weg = 0
            if modus == "quarantaine":
                weg = self._quarantaine(backup, extra, stap)
            elif modus == "verwijderen":
                weg = self._verwijder(backup, extra, stap)
            self.log("")
            fouten = getattr(self, "_sync_fouten", [])
            kleur = "waarsch" if fouten else "ok"
            self.log(f"Klaar. {gekop} gekopieerd/bijgewerkt, {weg} verwijderd/gequarantaineerd, "
                     f"{len(fouten)} mislukt, in {duur(time.time() - self._t0)}.", kleur)
            if fouten:
                self.log(f"\n\u26a0 {len(fouten)} bestand(en) MISLUKT:", "fout")
                for rel in fouten[:100]:
                    self.log(f"   ! {rel}", "fout")
                if len(fouten) > 100:
                    self.log(f"   ... en nog {len(fouten) - 100} meer", "fout")
                self.log("Deze verschijnen bij de volgende controle weer als ontbrekend/afwijkend.", "waarsch")
            self.log("Draai opnieuw 'Controleren' om te bevestigen (eindcontrole vergelijkt dan de totalen).")
            self.q.put(("klaar", None, None))
        except Exception as e:
            self.log(f"FOUT tijdens sync: {e}", "fout"); self.q.put(("klaar", None, str(e)))

    def _kopieer(self, bron, backup, lijst, stap=None):
        n = 0
        for rel in lijst:
            try:
                dst = os.path.join(backup, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(os.path.join(bron, rel), dst); n += 1
                self.log(f"   \u2713 gekopieerd: {rel}", "ok")
            except OSError as e:
                self.log(f"   ! kopie mislukt: {rel} ({e})", "fout")
                self._sync_fouten.append(rel)
            if stap:
                stap()
        return n

    def _quarantaine(self, backup, lijst, stap=None):
        if not lijst:
            return 0
        stempel = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        qbasis = os.path.join(_quarantaine_root(backup), stempel)
        n = 0
        for rel in lijst:
            try:
                dst = os.path.join(qbasis, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(os.path.join(backup, rel), dst); n += 1
            except OSError as e:
                self.log(f"   ! quarantaine mislukt: {rel} ({e})", "fout")
                self._sync_fouten.append(rel)
            if stap:
                stap()
        if n:
            self.log(f"   {n} naar quarantaine: {qbasis}", "waarsch")
        return n

    def _verwijder(self, backup, lijst, stap=None):
        n = 0
        for rel in lijst:
            try:
                os.remove(os.path.join(backup, rel)); n += 1
            except OSError as e:
                self.log(f"   ! verwijderen mislukt: {rel} ({e})", "fout")
                self._sync_fouten.append(rel)
            if stap:
                stap()
        if n:
            self.log(f"   {n} definitief verwijderd uit {_spiegel_letter()}.", "waarsch")
        return n

    # ---- Export ----
    def _export(self):
        r = self._laatste
        if not r:
            return
        pad = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Tekst", "*.txt"), ("CSV", "*.csv")],
            initialfile=f"archief_controle_{datetime.datetime.now():%Y-%m-%d_%H-%M}.txt")
        if not pad:
            return
        try:
            with open(pad, "w", encoding="utf-8") as f:
                f.write(f"Archief Backup Bewaking - rapport {datetime.datetime.now():%Y-%m-%d %H:%M}\n")
                f.write(f"Bron:   {r['bron']}\nBackup: {r['backup']}\n")
                f.write(f"Totaal bron: {r['totaal']} bestanden, {mensgrootte(r.get('bron_bytes',0))}\n")
                f.write(f"Totaal backup: {r['totaal_backup']} bestanden, {mensgrootte(r.get('backup_bytes',0))}\n")
                f.write(f"Controle-duur: {duur(r['seconden'])}\n\n")
                for titel, sleutel in (("ONTBREEKT in backup", "ontbreekt"),
                                       ("WIJKT AF", "verschilt"),
                                       ("EXTRA in backup", "extra")):
                    f.write(f"== {titel} ({len(r[sleutel])}) ==\n")
                    for rel in r[sleutel]:
                        f.write(rel + "\n")
                    f.write("\n")
            self.log(f"Rapport opgeslagen: {pad}", "ok")
        except OSError as e:
            messagebox.showerror("Opslaan mislukt", str(e))

    # ---- Veiligheid ----
    def _veiligheid(self, bron, backup, voor_sync):
        if not bron or not os.path.isdir(bron):
            return f"Bronmap bestaat niet: {bron}"
        try:
            if not any(os.scandir(bron)):
                return "Bron is leeg - mogelijk niet gemount. Backup NIET aangeraakt."
        except OSError as e:
            return f"Bron niet leesbaar: {e}"
        if voor_sync:
            if not backup:
                return "Geen backup-pad opgegeven."
            os.makedirs(backup, exist_ok=True)
        return None


if __name__ == "__main__":
    App().mainloop()
