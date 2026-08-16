"""
Pi NAS Suite — Initiële installatie GUI
Begeleidt de gebruiker van lege SD-kaart tot werkende NAS.
Staat in: C:\\PiNAS\\Beheer\\
"""

import tkinter as tk
from tkinter import messagebox
import subprocess
import threading
import os
import sys
import time

# ── Thema laden ───────────────────────────────────────────────
_gedeeld = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Gedeeld'))
if _gedeeld not in sys.path:
    sys.path.insert(0, _gedeeld)
# __pycache__ opruimen
import shutil as _shutil
for _cp in [os.path.join(_gedeeld, '__pycache__'), os.path.join(os.path.dirname(os.path.abspath(__file__)), '__pycache__')]:
    if os.path.isdir(_cp):
        try: _shutil.rmtree(_cp)
        except: pass

try:
    from pinas_theme import *
except ImportError:
    BG="#1e2d3d"; PANEL="#2a3f55"; PANEL2="#344d63"; FG="#e2eaf2"; DIM="#8ba3be"
    OK_C="#22c55e"; ERR_C="#ef4444"; WARN="#f59e0b"; ACCENT="#1d4ed8"
    ACCENT_PICONTROL="#7c3aed"
    # 13 augustus 2026: Installatie & Herstel kreeg een eigen kleur
    # (ACCENT_PIBEHEER, zie pinas_theme.py) i.p.v. het paars dat bewust
    # gereserveerd is voor Pi NAS Menu's eigen vensterkop-branding.
    ACCENT_PIBEHEER="#c2456b"

try:
    from pinas_ui import maak_header
except ImportError:
    maak_header = None

try:
    from pinas_wachtwoord import set_wachtwoord, get_wachtwoord
except ImportError:
    def set_wachtwoord(ww, soort="samba"): return False, "module niet gevonden"
    def get_wachtwoord(soort="samba"): return None

# ── Constanten ────────────────────────────────────────────────
VENSTER_B = 620
VENSTER_H = 720
STAPPEN = 4

# ── Voortgang markers uit install.sh ─────────────────────────
MARKERS = [
    ("script(s) klaargezet",   5,  "Scripts klaargezet op Pi"),
    ("SSH ingeschakeld",        10, "SSH actief"),
    ("Bijgewerkt",              25, "Systeem bijgewerkt"),
    ("Geformatteerd",           35, "Schijf geformatteerd"),
    ("Schijf gekoppeld",        45, "Schijf gekoppeld"),
    ("Rechten service",         50, "Rechten ingesteld"),
    ("Samba ingesteld",         65, "Samba (bestandsdeling) klaar"),
    ("Cockpit ingesteld",       75, "Cockpit (webbeheer) klaar"),
    ("FileBrowser ingesteld",   85, "FileBrowser klaar"),
    ("Welkomstmenu ingesteld",  90, "Welkomstmenu ingesteld"),
    ("NAS installatie voltooid",100,"Installatie voltooid!"),
]

def _nas_root():
    return os.path.join("C:\\", "PiNAS")

def _ico():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Pi_NAS_Menu.ico")
    return p if os.path.exists(p) else None

# ══════════════════════════════════════════════════════════════
class SetupApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pi NAS Suite — Installatie")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(560, 500)
        self.geometry(f"{VENSTER_B}x{VENSTER_H}")
        try:
            ico = _ico()
            if ico: self.iconbitmap(ico)
        except: pass
        self.update_idletasks()
        x = (self.winfo_screenwidth() - VENSTER_B) // 2
        y = (self.winfo_screenheight() - VENSTER_H) // 2
        self.geometry(f"+{x}+{y}")

        self.pi_ip   = tk.StringVar(value="UW_PI_IP_ADRES")
        self.pi_ww   = tk.StringVar()
        self.huidige_stap = 0
        self._ping_actief = False
        self._ssh_thread  = None

        self._bouw_ui()
        self._ga_naar_stap(1)

    # ── UI opbouw ─────────────────────────────────────────────
    INSTALLATIE_HELP = [
        ("Stap 1 - Jouw gegevens", "Pi IP-adres invullen, NAS-wachtwoord instellen (opgeslagen in "
         "Windows Credential Manager). Al een wachtwoord bekend? Veld leeg laten om het te behouden."),
        ("Stap 2 - SD-kaart voorbereiden", "Checklist voor Raspberry Pi Imager. Daarna wacht de "
         "wizard automatisch (ping + SSH-controle) tot de Pi online is - of klik 'Ik weet zeker "
         "dat de Pi al bereikbaar is' om dit over te slaan bij een bestaande Pi."),
        ("Stap 3 - Pi configureren", "Volledig automatisch: uploadt de PiServer-scripts en draait "
         "install.sh - dat installeert Samba, Cockpit en FileBrowser op de Pi. Duurt 5-15 minuten."),
        ("Stap 4 - Windows afronden", "Volledig automatisch: LanManFix, inloggegevens opslaan, de "
         "Opslag- en Backup-schijf koppelen, een snelkoppeling aanmaken, en Pi NAS Menu starten."),
        ("Nieuwe installatie versus reparatie", "Deze wizard werkt voor beide - bij een bestaande "
         "Pi kun je Stap 2 overslaan, en install.sh is veilig opnieuw te draaien zonder iets kapot "
         "te maken."),
    ]

    def _bouw_ui(self):
        # Header - 5 augustus 2026 (Frans: "Installatie en herstel wijkt
        # helemaal af, moet dezelfde header-opmaak volgen als bijv. Addons
        # Beheer", en overal een Help-knop) - omgezet naar de gedeelde
        # maak_header() i.p.v. eigen, losse code (die bg=PANEL gebruikte,
        # wat nergens anders voorkomt). Eigen Help-inhoud (geen Terug-
        # knop, wel Help) omdat dit een apart proces is zonder toegang tot
        # Pi_NAS_Menu.pyw's _open_help().
        if maak_header:
            # 13 augustus 2026: eigen kleur (ACCENT_PIBEHEER) i.p.v.
            # ACCENT_PICONTROL - dat laatste is gereserveerd voor Pi NAS
            # Menu's eigen vensterkop-branding, niet voor sub-schermen.
            maak_header(self, "Pi NAS Suite - Installatie",
                        subtekst="Volg de stappen om jouw NAS in te stellen",
                        help_hoofdstukken=self.INSTALLATIE_HELP, kleur=ACCENT_PIBEHEER)
        else:
            hdr = tk.Frame(self, bg=PANEL, pady=12)
            hdr.pack(fill="x")
            tk.Label(hdr, text="Pi NAS Suite — Installatie",
                     font=("Segoe UI", 14, "bold"), bg=PANEL, fg=FG).pack()
            tk.Label(hdr, text="Volg de stappen om jouw NAS in te stellen",
                     font=("Segoe UI", 9), bg=PANEL, fg=DIM).pack()

        # Stappen indicator
        self.stap_frame = tk.Frame(self, bg=BG, pady=8)
        self.stap_frame.pack(fill="x", padx=20)
        self.stap_labels = []
        namen = ["1  Gegevens", "2  SD-kaart", "3  Pi instellen", "4  Windows klaar"]
        for i, naam in enumerate(namen):
            lbl = tk.Label(self.stap_frame, text=naam,
                          font=("Segoe UI", 8), bg=BG, fg=DIM, padx=8)
            lbl.pack(side="left")
            self.stap_labels.append(lbl)

        tk.Frame(self, bg=PANEL2, height=1).pack(fill="x")

        # Inhoud frame (echt scrollbaar - canvas + scrollbar)
        inhoud_wrap = tk.Frame(self, bg=BG)
        inhoud_wrap.pack(fill="both", expand=True, padx=24, pady=16)
        inhoud_canvas = tk.Canvas(inhoud_wrap, bg=BG, highlightthickness=0)
        inhoud_scroll = tk.Scrollbar(inhoud_wrap, orient="vertical",
                                      command=inhoud_canvas.yview)
        inhoud_canvas.configure(yscrollcommand=inhoud_scroll.set)
        inhoud_scroll.pack(side="right", fill="y")
        inhoud_canvas.pack(side="left", fill="both", expand=True)
        self.inhoud = tk.Frame(inhoud_canvas, bg=BG)
        inhoud_venster = inhoud_canvas.create_window((0, 0), window=self.inhoud, anchor="nw")

        def _op_configure(event):
            inhoud_canvas.configure(scrollregion=inhoud_canvas.bbox("all"))
        self.inhoud.bind("<Configure>", _op_configure)

        def _canvas_breedte(event):
            inhoud_canvas.itemconfig(inhoud_venster, width=event.width)
        inhoud_canvas.bind("<Configure>", _canvas_breedte)

        # 6 augustus 2026 (Frans: muiswiel-scroll van het ene venster bleef
        # "vasthouden" als een ander suite-venster tegelijk open stond) -
        # Enter/Leave-scoped i.p.v. een permanente bind_all, zelfde bewezen
        # patroon als pinas_kleuren_kiezer.pyw: alleen actief zolang de
        # muis boven DIT venster hangt.
        def _muiswiel(event):
            inhoud_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        def _wiel_aan(e):
            inhoud_canvas.bind_all("<MouseWheel>", _muiswiel)
        def _wiel_uit(e):
            inhoud_canvas.unbind_all("<MouseWheel>")
        inhoud_canvas.bind("<Enter>", _wiel_aan)
        inhoud_canvas.bind("<Leave>", _wiel_uit)

        # Footer knoppen
        tk.Frame(self, bg=PANEL2, height=1).pack(fill="x")
        ftr = tk.Frame(self, bg=PANEL, pady=10)
        ftr.pack(fill="x")
        self.btn_terug = tk.Button(ftr, text="◀  Terug",
                font=("Segoe UI", 10), bg=PANEL2, fg=FG, relief="flat",
                cursor="hand2", padx=14, pady=6, borderwidth=0,
                command=self._terug)
        self.btn_terug.pack(side="left", padx=16)
        self.btn_verder = tk.Button(ftr, text="Verder  ▶",
                font=("Segoe UI", 10, "bold"), bg=ACCENT_PIBEHEER, fg=leesbare_tekstkleur(ACCENT_PIBEHEER), relief="flat",
                cursor="hand2", padx=14, pady=6, borderwidth=0,
                command=self._verder)
        self.btn_verder.pack(side="right", padx=16)

    def _clear(self):
        for w in self.inhoud.winfo_children():
            w.destroy()

    def _stap_indicator(self, actief):
        for i, lbl in enumerate(self.stap_labels):
            if i + 1 == actief:
                lbl.config(fg=OK_C, font=("Segoe UI", 8, "bold"))
            elif i + 1 < actief:
                lbl.config(fg=DIM, font=("Segoe UI", 8))
            else:
                lbl.config(fg=PANEL2, font=("Segoe UI", 8))

    def _kop(self, tekst, sub=""):
        tk.Label(self.inhoud, text=tekst,
                 font=("Segoe UI", 13, "bold"), bg=BG, fg=FG,
                 anchor="w").pack(fill="x", pady=(0,2))
        if sub:
            tk.Label(self.inhoud, text=sub,
                     font=("Segoe UI", 9), bg=BG, fg=DIM,
                     anchor="w", wraplength=560, justify="left").pack(fill="x", pady=(0,10))

    def _lbl(self, tekst, kleur=None):
        tk.Label(self.inhoud, text=tekst,
                 font=("Segoe UI", 9), bg=BG, fg=kleur or FG,
                 anchor="w", wraplength=560, justify="left").pack(fill="x", pady=2)

    def _invoer(self, label, var, ww=False, breedte=30):
        rij = tk.Frame(self.inhoud, bg=BG)
        rij.pack(fill="x", pady=4)
        tk.Label(rij, text=label, font=("Segoe UI", 9),
                 bg=BG, fg=FG, width=18, anchor="w").pack(side="left")
        e = tk.Entry(rij, textvariable=var, font=("Segoe UI", 10),
                     bg=PANEL2, fg=FG, insertbackground=FG,
                     show="*" if ww else "", width=breedte, relief="flat")
        e.pack(side="left")
        return e

    def _sep(self):
        tk.Frame(self.inhoud, bg=PANEL2, height=1).pack(fill="x", pady=10)

    # ── Navigatie ─────────────────────────────────────────────
    def _ga_naar_stap(self, stap):
        self.huidige_stap = stap
        self._stap_indicator(stap)
        self._clear()
        if stap == 1:
            self.btn_terug.config(state="normal", text="✕  Annuleren", command=self.destroy)
        else:
            self.btn_terug.config(state="normal", text="◀  Terug", command=self._terug)
        self.btn_verder.config(state="normal", text="Verder  ▶")
        {1: self._stap1, 2: self._stap2, 3: self._stap3, 4: self._stap4}[stap]()

    def _verder(self):
        if self.huidige_stap == 1:
            if not self._valideer_stap1(): return
        if self.huidige_stap < STAPPEN:
            self._ga_naar_stap(self.huidige_stap + 1)

    def _terug(self):
        self._ga_naar_stap(self.huidige_stap - 1)

    # ══════════════════════════════════════════════════════════
    # STAP 1 — Gegevens
    # ══════════════════════════════════════════════════════════
    def _stap1(self):
        self._kop("Stap 1 — Jouw gegevens",
                  "Vul het IP-adres van jouw Pi en het gewenste NAS wachtwoord in. "
                  "Dit wachtwoord gebruik je voor de Opslag-/Backup-netwerkschijven en SSH.")

        self._invoer("Pi IP-adres:", self.pi_ip)
        self._sep()
        self._lbl("NAS wachtwoord — wordt opgeslagen in Windows Credential Manager:", DIM)
        self.pi_ww2 = tk.StringVar()
        self._invoer("Nieuw wachtwoord:", self.pi_ww, ww=True)
        self._invoer("Bevestig wachtwoord:", self.pi_ww2, ww=True)

        # Toon bestaand wachtwoord als al ingesteld
        bestaand = get_wachtwoord("samba")
        if bestaand:
            self._lbl(f"✔  Wachtwoord al ingesteld — laat leeg om te bewaren", OK_C)

        self._sep()
        self._lbl("💡  Tip: noteer het IP-adres en wachtwoord voor jezelf.", WARN)

    def _valideer_stap1(self):
        ip = self.pi_ip.get().strip()
        if not ip:
            messagebox.showerror("Fout", "Vul een IP-adres in.")
            return False
        ww  = self.pi_ww.get()
        ww2 = self.pi_ww2.get() if hasattr(self, 'pi_ww2') else ww
        if ww:
            if ww != ww2:
                messagebox.showerror("Fout", "Wachtwoorden komen niet overeen.")
                return False
            if len(ww) < 4:
                messagebox.showerror("Fout", "Wachtwoord minimaal 4 tekens.")
                return False
            ok, fout = set_wachtwoord(ww, "samba")
            if not ok:
                messagebox.showerror("Fout", f"Wachtwoord opslaan mislukt:\n{fout}")
                return False
        elif not get_wachtwoord("samba"):
            messagebox.showerror("Fout", "Stel eerst een wachtwoord in.")
            return False
        return True

    # ══════════════════════════════════════════════════════════
    # STAP 2 — SD-kaart
    # ══════════════════════════════════════════════════════════
    def _stap2(self):
        self._kop("Stap 2 — SD-kaart voorbereiden",
                  "Gebruik Raspberry Pi Imager om de SD-kaart voor te bereiden. "
                  "Daarna stopt de Pi Imager en wacht dit venster tot de Pi bereikbaar is.")

        self._lbl("Checklist voor Pi Imager:", DIM)
        for item in [
            "✦  Kies: Raspberry Pi 5",
            "✦  Kies: Raspberry Pi OS Lite (64-bit)",
            "✦  Kies jouw SD-kaart",
            "✦  Klik op het tandwiel ⚙ en stel in:",
            "     • Hostname: piNAS",
            "     • SSH inschakelen",
            "     • Gebruiker: pi  /  Wachtwoord: jouw NAS wachtwoord",
            "✦  Schrijf de SD-kaart",
            "✦  Stop de SD-kaart in de Pi en zet hem aan",
        ]:
            tk.Label(self.inhoud, text=item, font=("Segoe UI", 9),
                     bg=BG, fg=FG, anchor="w").pack(fill="x", pady=1)

        self._sep()

        # Knoppen
        btn_frame = tk.Frame(self.inhoud, bg=BG)
        btn_frame.pack(fill="x", pady=4)
        # 15 augustus 2026: bg was hardcoded "#0c4a6e" (losse blauwtint,
        # geen thema-kleur) - nu ACCENT_PIBEHEER zoals de rest van dit scherm
        # (kopbalk en de "Verder"-knop verderop).
        tk.Button(btn_frame, text="🖥  Pi Imager starten",
                  font=("Segoe UI", 10, "bold"), bg=ACCENT_PIBEHEER, fg=leesbare_tekstkleur(ACCENT_PIBEHEER),
                  relief="flat", cursor="hand2", padx=14, pady=8, borderwidth=0,
                  command=self._start_imager).pack(side="left")

        self._sep()

        # Ping status
        self.ping_status_var = tk.StringVar(value="⏳  Wachtend — zet de Pi aan en klik 'Wachten op Pi'...")
        self.ping_lbl = tk.Label(self.inhoud, textvariable=self.ping_status_var,
                                  font=("Segoe UI", 9), bg=BG, fg=WARN,
                                  anchor="w", wraplength=560)
        self.ping_lbl.pack(fill="x")

        tk.Button(self.inhoud, text="📡  Wachten op Pi (automatische pingloop)",
                  font=("Segoe UI", 10), bg=ACCENT_PIBEHEER, fg=leesbare_tekstkleur(ACCENT_PIBEHEER),
                  relief="flat", cursor="hand2", padx=14, pady=8, borderwidth=0,
                  command=self._start_pingloop).pack(fill="x", pady=(8,0))

        tk.Button(self.inhoud,
                  text="✔  Ik weet zeker dat de Pi al bereikbaar is - toch doorgaan",
                  font=("Segoe UI", 9), bg=PANEL2, fg=DIM,
                  relief="flat", cursor="hand2", padx=14, pady=6, borderwidth=0,
                  command=self._forceer_verder).pack(fill="x", pady=(6,0))

        self.btn_verder.config(state="disabled")

    def _start_imager(self):
        nas = _nas_root()
        kandidaten = [
            os.path.join(nas, "Installatie", "imager_2.0.7.exe"),
            os.path.join(nas, "Installatie", "imager_latest.exe"),
            r"C:\Program Files\Raspberry Pi Imager\rpi-imager.exe",
        ]
        for pad in kandidaten:
            if os.path.exists(pad):
                subprocess.Popen([pad])
                return
        messagebox.showinfo("Pi Imager",
            "Pi Imager niet gevonden.\n\n"
            "Download via: https://www.raspberrypi.com/software/\n"
            "Of installeer via Setup → Stap 0 in Pi NAS Menu.")

    def _start_pingloop(self):
        if self._ping_actief:
            return
        self._ping_actief = True
        self.ping_lbl.config(fg=WARN)
        threading.Thread(target=self._ping_loop, daemon=True).start()

    def _ping_loop(self):
        ip = self.pi_ip.get().strip()
        poging = 0
        while self._ping_actief:
            poging += 1
            self.after(0, lambda p=poging: self.ping_status_var.set(
                f"📡  Ping poging {p} naar {ip}... (eerste opstart duurt 1-3 min)"))
            r = subprocess.run(["ping", "-n", "1", "-w", "1000", ip],
                               capture_output=True)
            if r.returncode == 0:
                self._wacht_op_ssh(ip)
                return
            time.sleep(2)

    def _wacht_op_ssh(self, ip):
        """Ping reageert vaak al voordat sshd echt klaar is - vooral bij een
        verse installatie regenereert de Pi dan nog SSH host-keys en herstart
        sshd daarna. Test daarom actief of SSH al bruikbaar is voordat we
        'klaar' melden, in plaats van alleen op ping te vertrouwen."""
        pogingen = 0
        while self._ping_actief and pogingen < 30:
            pogingen += 1
            self.after(0, lambda p=pogingen: self.ping_status_var.set(
                f"🔑  Pi reageert, SSH wordt klaargezet... (controle {p}/30)"))
            klaar = False
            try:
                r = subprocess.run(
                    ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=4",
                     "-o", "BatchMode=yes", f"pi@{ip}", "echo klaar"],
                    capture_output=True, text=True, timeout=8,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                # BatchMode=yes weigert altijd interactief wachtwoord - een
                # "Permission denied" betekent dus dat sshd al gewoon
                # antwoordt en klaar is, ook al is er nog geen sleutel
                # uitgewisseld (dat lost de latere upload-stap zelf op).
                klaar = (r.returncode == 0 and "klaar" in r.stdout) or \
                        ("permission denied" in r.stderr.lower())
            except subprocess.TimeoutExpired:
                pass
            except Exception:
                pass
            if klaar:
                self._ping_actief = False
                self.after(0, self._pi_gevonden)
                return
            time.sleep(3)
        if self._ping_actief:
            self._ping_actief = False
            self.after(0, lambda: self.ping_status_var.set(
                "⚠  Pi reageert op ping maar SSH komt niet tot stand. Wacht nog even "
                "en klik opnieuw op 'Wachten op Pi', of controleer handmatig via SSH."))
            self.after(0, lambda: self.ping_lbl.config(fg=WARN))

    def _forceer_verder(self):
        self._ping_actief = False
        self.ping_status_var.set("✔  Handmatig bevestigd - doorgaan zonder automatische controle.")
        self.ping_lbl.config(fg=OK_C)
        self.btn_verder.config(state="normal")

    def _pi_gevonden(self):
        self.ping_status_var.set(f"✔  Pi bereikbaar op {self.pi_ip.get().strip()}!")
        self.ping_lbl.config(fg=OK_C)
        self.btn_verder.config(state="normal")
        messagebox.showinfo("Pi gevonden!",
            f"De Pi is bereikbaar op {self.pi_ip.get().strip()}.\n\n"
            "Klik 'Verder' om de Pi te configureren.")

    # ══════════════════════════════════════════════════════════
    # STAP 3 — Pi configureren
    # ══════════════════════════════════════════════════════════
    def _stap3(self):
        self._kop("Stap 3 — Pi configureren",
                  "De Pi wordt nu automatisch geconfigureerd. "
                  "Dit duurt 5-15 minuten afhankelijk van internetsnelheid.")

        # Voortgangsbalk
        balk_frame = tk.Frame(self.inhoud, bg=PANEL2, relief="flat", bd=1)
        balk_frame.pack(fill="x", pady=(0,4))
        self.balk_binnen = tk.Frame(balk_frame, bg=ACCENT_PIBEHEER, height=20, width=0)
        self.balk_binnen.pack(side="left")
        self.balk_breedte = 0

        self.balk_pct = tk.Label(self.inhoud, text="0%",
                                  font=("Segoe UI", 9), bg=BG, fg=DIM)
        self.balk_pct.pack(anchor="e")

        self.status_lbl = tk.Label(self.inhoud, text="⏳  Verbinden met Pi...",
                                    font=("Segoe UI", 10, "bold"), bg=BG, fg=WARN,
                                    anchor="w")
        self.status_lbl.pack(fill="x", pady=4)

        self._sep()

        # Log sectie
        log_hdr = tk.Frame(self.inhoud, bg=BG)
        log_hdr.pack(fill="x")
        tk.Label(log_hdr, text="Technisch log", font=("Segoe UI", 9, "bold"),
                 bg=BG, fg=DIM).pack(side="left")
        self.log_toon_var = tk.BooleanVar(value=False)
        tk.Checkbutton(log_hdr, text="Toon details", variable=self.log_toon_var,
                       bg=BG, fg=DIM, selectcolor=PANEL2,
                       command=self._toggle_log,
                       font=("Segoe UI", 8)).pack(side="right")

        self.log_frame = tk.Frame(self.inhoud, bg=BG)
        self.log_txt = tk.Text(self.log_frame, height=10,
                                font=("Consolas", 8), bg=PANEL, fg=DIM,
                                relief="flat", state="disabled", wrap="word")
        scroll = tk.Scrollbar(self.log_frame, command=self.log_txt.yview)
        self.log_txt.config(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log_txt.pack(fill="both", expand=True)

        self.btn_verder.config(state="disabled")
        threading.Thread(target=self._configureer_pi, daemon=True).start()

    def _toggle_log(self):
        if self.log_toon_var.get():
            self.log_frame.pack(fill="both", expand=True, pady=4)
        else:
            self.log_frame.pack_forget()

    def _log(self, tekst):
        def _do():
            self.log_txt.config(state="normal")
            self.log_txt.insert("end", tekst + "\n")
            self.log_txt.see("end")
            self.log_txt.config(state="disabled")
        self.after(0, _do)

    def _balk(self, pct, tekst=""):
        def _do():
            breedte = int((VENSTER_B - 48) * pct / 100)
            self.balk_binnen.config(width=breedte)
            self.balk_pct.config(text=f"{pct}%")
            if tekst:
                self.status_lbl.config(text=f"✔  {tekst}", fg=OK_C)
        self.after(0, _do)

    def _configureer_pi(self):
        ip = self.pi_ip.get().strip()
        ww = get_wachtwoord("samba") or ""
        nas = _nas_root()

        # Stap A: upload scripts
        self.after(0, lambda: self.status_lbl.config(
            text="⏳  Scripts uploaden naar Pi...", fg=WARN))
        self._log(f"Verbinden met {ip}...")

        scripts = [
            os.path.join(nas, "PiServer", "nas_installer.py"),
            os.path.join(nas, "PiServer", "nas_installer_cli.py"),
            os.path.join(nas, "PiServer", "seagate_web.py"),
            os.path.join(nas, "PiServer", "seagate-web.service"),
            os.path.join(nas, "PiServer", "smart_plug.py"),
            os.path.join(nas, "PiServer", "pi_welkom.sh"),
            os.path.join(nas, "PiServer", "install.sh"),
            os.path.join(nas, "PiServer", "nas_start.sh"),
            os.path.join(nas, "Gedeeld", "nas_diagnose.sh"),
        ]

        for script in scripts:
            if os.path.exists(script):
                naam = os.path.basename(script)
                self._log(f"Uploaden: {naam}")
                r = subprocess.run(
                    ["scp", "-o", "StrictHostKeyChecking=no",
                     script, f"pi@{ip}:/home/pi/{naam}"],
                    capture_output=True, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                if r.returncode == 0:
                    self._log(f"  OK: {naam}")
                else:
                    self._log(f"  FOUT: {naam} — {r.stderr.strip()}")

        self._balk(5, "Scripts geüpload")

        # Rechten instellen
        r = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no",
             "-o", "ConnectTimeout=10", f"pi@{ip}",
             "chmod 755 /home/pi/*.py /home/pi/*.sh 2>/dev/null; "
             "sudo cp /home/pi/*.py /home/pi/*.sh /boot/firmware/ 2>/dev/null; "
             "echo OK"],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
        self._log(f"Rechten: {r.stdout.strip()}")

        # Stap B: SSH verbinden en install.sh activeren
        self.after(0, lambda: self.status_lbl.config(
            text="⏳  Pi configureren — even geduld...", fg=WARN))

        # Activeer install.sh via .bashrc en voer het uit
        r = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no",
             "-o", "ConnectTimeout=10", f"pi@{ip}",
             "grep -q 'install.sh' /home/pi/.bashrc || "
             "echo 'source /home/pi/install.sh' >> /home/pi/.bashrc; echo bashrc_ok"],
            capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
        self._log(f"Bashrc: {r.stdout.strip()}")

        # Voer install.sh direct uit en vang output op
        self._log("install.sh starten...")
        self.after(0, lambda: self.status_lbl.config(
            text="⏳  Installatie bezig op Pi (5-15 min)...", fg=WARN))

        try:
            proc = subprocess.Popen(
                ["ssh", "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=30",
                 "-o", "ServerAliveInterval=10",
                 f"pi@{ip}",
                 "sudo bash /home/pi/install.sh 2>&1 || "
                 "sudo bash -c 'source /home/pi/install.sh'"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, creationflags=subprocess.CREATE_NO_WINDOW)

            for regel in proc.stdout:
                regel = regel.rstrip()
                # Strip ANSI kleurcodes
                import re
                schoon = re.sub(r'\033\[[0-9;]*m', '', regel).strip()
                if schoon:
                    self._log(schoon)
                    # Check markers
                    for marker, pct, beschr in MARKERS:
                        if marker in schoon:
                            self._balk(pct, beschr)
                            break

            proc.wait()

        except Exception as e:
            self._log(f"FOUT: {e}")
            self.after(0, lambda: self.status_lbl.config(
                text=f"⚠  Fout: {e}", fg=ERR_C))
            return

        # Klaar
        self._balk(100, "Pi configuratie voltooid!")
        self.after(0, lambda: self.btn_verder.config(state="normal"))
        self.after(0, lambda: messagebox.showinfo(
            "Pi klaar!",
            "De Pi is volledig geconfigureerd!\n\n"
            "Let op: net geinstalleerde services worden pas actief na een "
            "herstart van de Pi. Staat een service straks nog op 'niet "
            "actief', herstart dan de Pi (Onderhoud -> Pi NAS "
            "herstarten) - dat is normaal, geen fout.\n\n"
            "Klik 'Verder' om Windows af te ronden."))

    # ══════════════════════════════════════════════════════════
    # STAP 4 — Windows afronden
    # ══════════════════════════════════════════════════════════
    def _stap4(self):
        self._kop("Stap 4 — Windows afronden",
                  "Bijna klaar! De netwerkschijven worden nu gekoppeld "
                  "en Pi NAS Menu wordt gestart.")

        ip = self.pi_ip.get().strip()
        ww = get_wachtwoord("samba") or ""

        self.stap4_status = []
        self.stap4_labels = {}

        items = [
            ("lanman",   "LanManFix toepassen"),
            ("cmdkey",   "Inloggegevens opslaan"),
            ("y_schijf", "Opslag-schijf koppelen (SSD)"),
            ("z_schijf", "Backup-schijf koppelen (Seagate)"),
            ("snelkoppeling", "Snelkoppeling aanmaken"),
        ]

        for key, naam in items:
            rij = tk.Frame(self.inhoud, bg=BG)
            rij.pack(fill="x", pady=3)
            lbl_status = tk.Label(rij, text="⏳", font=("Segoe UI", 10),
                                   bg=BG, fg=DIM, width=3)
            lbl_status.pack(side="left")
            tk.Label(rij, text=naam, font=("Segoe UI", 9),
                     bg=BG, fg=FG, anchor="w").pack(side="left", fill="x", expand=True)
            self.stap4_labels[key] = lbl_status

        self._sep()
        self.stap4_resultaat = tk.Label(self.inhoud, text="",
                                         font=("Segoe UI", 10, "bold"),
                                         bg=BG, fg=WARN, wraplength=560)
        self.stap4_resultaat.pack(fill="x")

        self.btn_verder.config(state="disabled", text="Pi NAS Menu starten")
        threading.Thread(target=lambda: self._windows_afronden(ip, ww), daemon=True).start()

    def _stap4_update(self, key, ok, tekst=""):
        def _do():
            lbl = self.stap4_labels.get(key)
            if lbl:
                lbl.config(text="✔" if ok else "✘", fg=OK_C if ok else ERR_C)
        self.after(0, _do)

    def _kies_vrije_letter(self, voorkeur, ip, share):
        """Kiest een stationsletter: de voorkeursletter als die vrij is
        (of al naar dezelfde Pi+share wijst), anders de eerstvolgende
        vrije letter. Pakt NOOIT een letter af die al iets ANDERS in
        gebruik heeft.

        5 augustus 2026 (Frans, staande regel: geen hardcoded Y:/Z:):
        deze wizard koppelde tot nu toe altijd hardcoded aan Y:/Z:, ook
        als die al door iets anders bezet waren op de nieuwe pc. Nu
        dynamisch, net als de rest van de suite al eerder vandaag kreeg."""
        kandidaten = [voorkeur] + [c for c in "DEFGHIJKLMNOPQRSTUVWX" if c != voorkeur]
        doel = f"\\\\{ip}\\{share}".lower()
        for letter in kandidaten:
            if not os.path.exists(f"{letter}:\\"):
                return letter
            r = subprocess.run(["net", "use", f"{letter}:"], capture_output=True,
                                text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if doel in (r.stdout or "").lower():
                return letter  # was al aan dezelfde share gekoppeld
        return voorkeur  # alle 24 letters bezet - onwaarschijnlijk, laatste redmiddel

    def _onthoud_schijfletter(self, letter, share):
        """Slaat de gekozen letter op in picontrol.cfg's [schijven]-sectie
        - zelfde bestand/formaat als Pi_NAS_Menu.pyw's _schijf_config()
        leest, zodat de rest van de suite deze letter automatisch
        terugvindt in plaats van zelf weer Y:/Z: aan te nemen."""
        import configparser
        cfg_pad = os.path.join(os.path.dirname(os.path.abspath(__file__)), "picontrol.cfg")
        cfg = configparser.ConfigParser()
        if os.path.exists(cfg_pad):
            cfg.read(cfg_pad)
        if not cfg.has_section("schijven"):
            cfg.add_section("schijven")
        for bestaande_letter, bestaande_share in list(cfg.items("schijven")):
            if bestaande_share.strip().lower() == share.strip().lower():
                cfg.remove_option("schijven", bestaande_letter)
        cfg.set("schijven", letter, share)
        try:
            with open(cfg_pad, "w", encoding="utf-8") as f:
                cfg.write(f)
        except Exception:
            pass  # Niet kunnen opslaan is niet fataal voor deze installatie

    def _windows_afronden(self, ip, ww):
        # LanManFix
        subprocess.run(["reg", "add",
            r"HKLM\SYSTEM\CurrentControlSet\Services\LanmanWorkstation\Parameters",
            "/v", "AllowInsecureGuestAuth", "/t", "REG_DWORD", "/d", "1", "/f"],
            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        self._stap4_update("lanman", True)
        time.sleep(0.5)

        # cmdkey
        subprocess.run(["cmdkey", f"/add:{ip}", "/user:pi", f"/pass:{ww}"],
                       capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        self._stap4_update("cmdkey", True)
        time.sleep(0.5)

        # Opslag-schijf - letter dynamisch gekozen, NIET hardcoded Y:
        # (5 augustus 2026: sharenaam bevestigd door Frans via Verkenner
        # - "Opslag", niet "PiNas" zoals hier eerder stond)
        opslag_letter = self._kies_vrije_letter("Y", ip, "Opslag")
        subprocess.run(["net", "use", f"{opslag_letter}:", "/delete", "/yes"],
                       capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        r = subprocess.run(
            ["net", "use", f"{opslag_letter}:", f"\\\\{ip}\\Opslag", f"/user:pi", ww, "/persistent:yes"],
            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        self._stap4_update("y_schijf", r.returncode == 0)
        if r.returncode == 0:
            self._onthoud_schijfletter(opslag_letter, "Opslag")
        time.sleep(0.5)

        # Backup-schijf - letter dynamisch gekozen, NIET hardcoded Z:
        backup_letter = self._kies_vrije_letter("Z", ip, "Backup")
        subprocess.run(["net", "use", f"{backup_letter}:", "/delete", "/yes"],
                       capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        r = subprocess.run(
            ["net", "use", f"{backup_letter}:", f"\\\\{ip}\\Backup", f"/user:pi", ww, "/persistent:yes"],
            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        self._stap4_update("z_schijf", r.returncode == 0)
        if r.returncode == 0:
            self._onthoud_schijfletter(backup_letter, "Backup")
        time.sleep(0.5)

        # Snelkoppeling
        nas = _nas_root()
        menu_pad = os.path.join(nas, "Beheer", "Pi_NAS_Menu.pyw")
        ico_pad  = os.path.join(nas, "Beheer", "Pi_NAS_Menu.ico")
        snelkoppeling = os.path.join(os.environ.get("USERPROFILE",""), "Desktop", "Pi NAS Menu.lnk")
        werk_dir = os.path.join(nas, "Beheer")
        ps = (
            "$ws=New-Object -ComObject WScript.Shell; "
            + "$s=$ws.CreateShortcut('" + snelkoppeling + "'); "
            + "$s.TargetPath='pythonw.exe'; "
            + "$s.Arguments='\"" + menu_pad + "\"'; "
            + "$s.WorkingDirectory='" + werk_dir + "'; "
            + "$s.IconLocation='" + ico_pad + "'; "
            + "$s.Save()"
        )
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        self._stap4_update("snelkoppeling", r.returncode == 0)

        # Klaar
        self.after(0, lambda: self.stap4_resultaat.config(
            text="✅  Alles klaar! Klik 'Pi NAS Menu starten' om te beginnen.",
            fg=OK_C))
        self.after(0, lambda: self.btn_verder.config(
            state="normal", command=self._start_menu))

    def _start_menu(self):
        try:
            import pinas_launcher
            pinas_launcher.open_programma(
                "Pi_NAS_Menu.pyw", roots=[_nas_root()], submappen=["Beheer"])
        except ImportError:
            # Terugval als pinas_launcher.py (nog) niet aanwezig is
            nas = _nas_root()
            menu = os.path.join(nas, "Beheer", "Pi_NAS_Menu.pyw")
            if os.path.exists(menu):
                subprocess.Popen(["pythonw", menu])
        self.destroy()

# ── Start ──────────────────────────────────────────────────────
if __name__ == "__main__":
    app = SetupApp()
    app.mainloop()
