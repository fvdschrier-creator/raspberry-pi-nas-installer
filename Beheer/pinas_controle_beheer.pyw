#!/usr/bin/env python3
# pinas_controle_beheer.pyw - Pi NAS Suite
#
# Controles: de ENE centrale plek om te checken of de suite gezond is
# - zonder de installatiestappen van pi_nas_setup.pyw aan te raken. Zelfde
# opzet als Beheer\pinas_backup_beheer.pyw en Addons\pinas_addons_beheer.pyw
# (16 juli 2026).
#
# Ontstaan uit de reorganisatie van NAS Map Beheer: Suite testen, Diagnose
# uitvoeren en Log Bestanden Bekijken zaten eerder in NAS Map Beheer's
# "Herstel & Acties"-tab (samen met Handleiding/Distribueren/Scripts
# uploaden, die naar Onderhoud zijn verhuisd). Die tab is
# opgeheven; dit scherm is het nieuwe thuis voor de controle-acties.
# (16 juli 2026, later: hernoemd van "Controle Beheer" naar "Controles"
# omdat het naast "Onderhoud" en "Herstel & Acties" verwarrend leek.)
#
# 16 juli 2026: ook Structuurcheck en Opruimen (NAS_Map_Beheer.pyw) kregen
# hier een knop - het zijn immers ook controles. Daarmee is "Herstel &
# Acties" als los hoofdmenu-item vervallen; NAS_Map_Beheer.pyw zelf blijft
# als scherm bestaan (titel: "Structuurcheck & Opruimen"), alleen bereikbaar
# via de knop hieronder in plaats van rechtstreeks vanaf het hoofdmenu.
#
# 13 augustus 2026: Structuurcheck & Opruimen controleert de PC-kant
# (C:\PiNAS tegen pinas_versies.json). Frans vroeg na een SD-kaart-
# onderzoek via WinSCP (oude, afgebroken image van 7+ GB gevonden in
# /home/pi/Images/) om hetzelfde ook voor de Pi-kant: "Pi opruimen"
# vergelijkt /home/pi op de Pi zelf met de bestanden die de suite daar
# hoort te zetten (nas_upload.py's PI_BESTANDEN, nu de ENE bron van
# waarheid daarvoor) en laat onbekende bestanden verwijderen.
#
# Hoort thuis in: Beheer\pinas_controle_beheer.pyw

import tkinter as tk
from tkinter import messagebox, scrolledtext
import subprocess
import os
import sys
import configparser
import threading

# -- Gedeeld op het pad zetten, zodat pinas_theme en pinas_ui te vinden zijn --
_gedeeld = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Gedeeld")
if os.path.isdir(_gedeeld) and _gedeeld not in sys.path:
    sys.path.insert(0, os.path.abspath(_gedeeld))

from pinas_theme import (BG, PANEL, PANEL2, FG, DIM, OK_C, ERR_C,
                          ACCENT_PIBEHEER_2, leesbare_tekstkleur)
from pinas_ui import maak_header, maak_sectie, maak_knop
import pinas_launcher
import pinas_schijven

try:
    from version import BIJGEWERKT
except ImportError:
    BIJGEWERKT = "onbekende datum"


def _script_dir():
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def _nas_root():
    """NAS root = een niveau omhoog van Beheer/PiServer/Sync/Gedeeld/Addons."""
    d = _script_dir()
    for sub in ["Beheer", "PiServer", "Sync", "Gedeeld", "Addons"]:
        if os.path.basename(d) == sub:
            return os.path.dirname(d)
    return os.path.dirname(d)


def _c_pinas():
    return os.path.join("C:\\", "PiNAS")


_cfg = configparser.ConfigParser()
_cfg_pad = os.path.join(_nas_root(), "Beheer", "picontrol.cfg")
if not os.path.exists(_cfg_pad):
    _cfg_pad = os.path.join(_c_pinas(), "Beheer", "picontrol.cfg")
if os.path.exists(_cfg_pad):
    _cfg.read(_cfg_pad, encoding="utf-8")
PI_IP = _cfg.get("pi", "ip", fallback="UW_PI_IP_ADRES")


# -- Kleine PC-checks, zelfde soort als in NAS Map Beheer/Pi_NAS_Menu ---------
def _putty_exe():
    for p in [r"C:\Program Files\PuTTY\putty.exe",
              r"C:\Program Files (x86)\PuTTY\putty.exe"]:
        if os.path.exists(p): return p
    return None


def _tigervnc_exe():
    for p in [r"C:\Program Files\TigerVNC\vncviewer.exe",
              r"C:\Program Files (x86)\TigerVNC\vncviewer.exe"]:
        if os.path.exists(p): return p
    return None

def _winscp_exe():
    """13 augustus 2026: naast Program Files ook %LOCALAPPDATA%\\Programs
    en de App Paths-registersleutel geprobeerd - een "alleen voor mij"-
    installatie (of aangepaste map) stond niet in de vaste paden, zag
    Pi NAS Menu ook niet ("WinSCP niet gevonden" terwijl WinSCP al open
    en verbonden stond)."""
    for p in [r"C:\Program Files\WinSCP\WinSCP.exe",
              r"C:\Program Files (x86)\WinSCP\WinSCP.exe",
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "WinSCP", "WinSCP.exe")]:
        if p and os.path.exists(p): return p
    try:
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive,
                        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\WinSCP.exe") as k:
                    pad, _ = winreg.QueryValueEx(k, "")
                    if pad and os.path.exists(pad):
                        return pad
            except OSError:
                continue
    except ImportError:
        pass
    return None


HELP_HOOFDSTUKKEN = [
    ("Structuurcheck & Opruimen",
     "Opent het venster met twee tabbladen: Structuurcheck (controleert of "
     "alle verwachte bestanden er zijn en up-to-date zijn) en Opruimen "
     "(verouderde/overbodige bestanden opsporen en verwijderen). Voorheen "
     "'NAS Map Beheer' - 16 juli 2026 hierheen verhuisd, want het zijn "
     "allebei controles. Werkt op de PC-kant (C:\\PiNAS)."),
    ("Pi opruimen",
     "Zelfde soort controle als Structuurcheck & Opruimen, maar dan voor "
     "/home/pi op de Pi zelf (via SSH). Toont bestanden/mappen die de "
     "suite daar niet heeft neergezet en dus onbekend zijn, met hun "
     "grootte, en laat ze in één keer verwijderen na bevestiging."),
    ("Suite testen",
     "Draait test_suite.py: een reeks kwaliteitschecks (bestanden, syntax, "
     "Python packages, schijven, registry, Pi services, netwerk) in een "
     "apart venster. Exporteerbaar naar CSV. Gebruik dit na wijzigingen om "
     "te checken of er niets kapot is gegaan."),
    ("Diagnose uitvoeren",
     "Twee losse checks: 'PC diagnose' controleert lokale software "
     "(PuTTY/TigerVNC/WinSCP/Sync & Backup) en netwerkschijven op deze pc. "
     "'Pi diagnose' stuurt nas_diagnose.sh naar de Pi en draait het daar "
     "via SSH - handig als de Pi zelf niet lijkt te reageren zoals "
     "verwacht."),
    ("Log Bestanden Bekijken",
     "Overzicht van de belangrijkste logbestanden (Pi NAS Menu, PiNAS "
     "Sync, Externe HDD) met grootte en een Open-knop per bestand. Logs "
     "worden automatisch na 30 dagen verwijderd."),
]


def _open_structuurcheck():
    """Start NAS_Map_Beheer.pyw (Structuurcheck + Opruimen) - via de
    gedeelde launcher, zodat een dubbelklik niet twee vensters opent.
    Het scherm heet intern nog NAS_Map_Beheer.pyw; de titel/header
    tonen sinds 16 juli 2026 'Structuurcheck & Opruimen'."""
    ok, fout = pinas_launcher.open_programma(
        "NAS_Map_Beheer.pyw",
        roots=[_nas_root(), _c_pinas()],
        submappen=["Beheer"])
    if not ok:
        messagebox.showerror("Niet gevonden",
            "NAS_Map_Beheer.pyw niet gevonden.\n"
            "Zet het bestand in Beheer\\ naast pinas_controle_beheer.pyw")


def _open_pi_opruimen():
    """Start pinas_pi_opruimen.pyw - via de gedeelde launcher, zoals
    _open_structuurcheck() hierboven. 13 augustus 2026."""
    ok, fout = pinas_launcher.open_programma(
        "pinas_pi_opruimen.pyw",
        roots=[_nas_root(), _c_pinas()],
        submappen=["Beheer"])
    if not ok:
        messagebox.showerror("Niet gevonden",
            "pinas_pi_opruimen.pyw niet gevonden.\n"
            "Zet het bestand in Beheer\\ naast pinas_controle_beheer.pyw")


def _start_suite_test():
    pad = os.path.join(_nas_root(), "Gedeeld", "test_suite.py")
    if not os.path.exists(pad):
        pad = os.path.join(_c_pinas(), "Gedeeld", "test_suite.py")
    if os.path.exists(pad):
        subprocess.Popen([sys.executable, pad], cwd=os.path.dirname(pad))
    else:
        messagebox.showerror("Niet gevonden",
            f"test_suite.py niet gevonden.\nVerwacht in: C:\\PiNAS\\Gedeeld\\")


def _open_diagnose(root_win):
    dwin = tk.Toplevel(root_win)
    dwin.title("Diagnose - Pi NAS Suite")
    dwin.configure(bg=BG)
    dwin.resizable(True, True)
    dwin.geometry("680x600")
    dwin.minsize(540, 400)
    dwin.update_idletasks()
    x = root_win.winfo_x() + (root_win.winfo_width() - 680) // 2
    y = root_win.winfo_y() + (root_win.winfo_height() - 600) // 2
    dwin.geometry(f"+{x}+{y}")

    # 13 augustus 2026: was hardcoded "#2f3b47" - dit dialoogscherm opent
    # vanuit Controles, dus nu ACCENT_PIBEHEER_2 zoals de rest van dat scherm.
    hdr = tk.Frame(dwin, bg=ACCENT_PIBEHEER_2, pady=10)
    hdr.pack(fill="x")
    tk.Label(hdr, text="Pi NAS Diagnose",
              font=("Segoe UI", 13, "bold"), bg=ACCENT_PIBEHEER_2, fg=leesbare_tekstkleur(ACCENT_PIBEHEER_2)).pack(side="left", padx=14)

    btn_bar = tk.Frame(dwin, bg=PANEL, pady=6)
    btn_bar.pack(fill="x")

    txt_frame = tk.Frame(dwin, bg=BG)
    txt_frame.pack(fill="both", expand=True, padx=10, pady=8)
    tekst = tk.Text(txt_frame, bg="#0d1117", fg="#c9d1d9",
                    font=("Courier New", 9), wrap="word",
                    relief="flat", insertbackground=FG,
                    selectbackground=PANEL2)
    sc = tk.Scrollbar(txt_frame, command=tekst.yview)
    tekst.configure(yscrollcommand=sc.set)
    sc.pack(side="right", fill="y")
    tekst.pack(side="left", fill="both", expand=True)

    tekst.tag_configure("ok",   foreground="#3fb950")
    tekst.tag_configure("err",  foreground="#f85149")
    tekst.tag_configure("info", foreground="#79c0ff")
    tekst.tag_configure("hdr",  foreground="#d2a8ff", font=("Courier New", 9, "bold"))

    def check(naam, ok, detail=""):
        sym = "OK " if ok else "ERR"
        tag = "ok" if ok else "err"
        tekst.insert("end", f"  {sym}  {naam}", tag)
        if detail:
            tekst.insert("end", f"  -  {detail}")
        tekst.insert("end", "\n")

    def _run_diagnose_pc():
        tekst.delete("1.0", "end")
        tekst.insert("end", "-- PC Diagnose --------------------------------\n", "hdr")
        _putty = _putty_exe()
        check("PuTTY", _putty is not None, _putty or "niet gevonden")
        _vnc = _tigervnc_exe()
        check("TigerVNC", _vnc is not None, _vnc or "niet gevonden")
        _winscp = _winscp_exe()
        check("WinSCP", _winscp is not None, _winscp or "niet gevonden (optioneel)")
        # Schijfletter dynamisch opzoeken op share-naam i.p.v. Y:/Z: aan te
        # nemen - op een andere pc kan Windows deze netwerkschijven een
        # andere letter geven als Y:/Z: daar al bezet zijn (feedback van
        # Frans, 16 juli 2026: "op een andere pc is het niet per se Y en Z").
        opslag_letter = pinas_schijven.vind_letter("Opslag", PI_IP)
        try:
            if opslag_letter:
                r = subprocess.run(["net", "use", opslag_letter + ":"], capture_output=True,
                    text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=4)
                check(f"Opslag-schijf (SSD)", r.returncode == 0, f"{opslag_letter}:")
            else:
                check("Opslag-schijf (SSD)", False, "geen gekoppelde schijfletter gevonden")
        except Exception as e:
            check("Opslag-schijf (SSD)", False, str(e))
        backup_letter = pinas_schijven.vind_letter("Backup", PI_IP)
        try:
            if backup_letter:
                r = subprocess.run(["net", "use", backup_letter + ":"], capture_output=True,
                    text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=4)
                check(f"Backup-schijf (HDD)", r.returncode == 0, f"{backup_letter}:")
            else:
                check("Backup-schijf (HDD)", False, "geen gekoppelde schijfletter gevonden")
        except Exception as e:
            check("Backup-schijf (HDD)", False, str(e))
        # Spiegel Backup (H:) is optioneel - alleen op installaties die deze
        # schijf ook echt hebben (staat dan in picontrol.cfg's [schijven]),
        # net als de Dell-installatie die deze schijf niet heeft.
        _schijven_namen = ([s.strip().lower() for s in dict(_cfg.items("schijven")).values()]
                            if _cfg.has_section("schijven") else [])
        if "spiegelbackup" in _schijven_namen:
            spiegel_letter = pinas_schijven.vind_letter("SpiegelBackup", PI_IP)
            try:
                if spiegel_letter:
                    r = subprocess.run(["net", "use", spiegel_letter + ":"], capture_output=True,
                        text=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=4)
                    check("Spiegel Backup-schijf (HDD)", r.returncode == 0, f"{spiegel_letter}:")
                else:
                    check("Spiegel Backup-schijf (HDD)", False, "geen gekoppelde schijfletter gevonden")
            except Exception as e:
                check("Spiegel Backup-schijf (HDD)", False, str(e))
        try:
            r = subprocess.run(["ping", "-n", "1", "-w", "1500", PI_IP],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            check("Pi bereikbaar (ping)", r.returncode == 0, PI_IP)
        except Exception as e:
            check("Pi bereikbaar (ping)", False, str(e))
        tekst.insert("end", "\nKlaar.\n", "info")

    def _run_diagnose_pi():
        tekst.delete("1.0", "end")
        tekst.insert("end", "-- Pi Diagnose (via SSH) -----------------------\n", "hdr")
        tekst.insert("end", "Uploaden en uitvoeren van nas_diagnose.sh...\n", "info")
        dwin.update_idletasks()

        def run():
            sh_pad = os.path.join(_nas_root(), "Gedeeld", "nas_diagnose.sh")
            if not os.path.exists(sh_pad):
                sh_pad = os.path.join(_c_pinas(), "Gedeeld", "nas_diagnose.sh")
            if not os.path.exists(sh_pad):
                tekst.after(0, lambda: tekst.insert(
                    "end", "FOUT: nas_diagnose.sh niet gevonden in Gedeeld\\\n", "err"))
                return
            try:
                r1 = subprocess.run(
                    ["scp", sh_pad, f"pi@{PI_IP}:/home/pi/nas_diagnose.sh"],
                    capture_output=True, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW, timeout=20)
                if r1.returncode != 0:
                    tekst.after(0, lambda: tekst.insert(
                        "end", f"FOUT bij uploaden:\n{r1.stderr}\n", "err"))
                    return
                r2 = subprocess.run(
                    ["ssh", "-o", "StrictHostKeyChecking=no", f"pi@{PI_IP}",
                     "sudo bash /home/pi/nas_diagnose.sh"],
                    capture_output=True, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW, timeout=60)
                tekst.after(0, lambda: tekst.insert("end", r2.stdout + r2.stderr))
                subprocess.run(
                    ["ssh", f"pi@{PI_IP}", "rm -f /home/pi/nas_diagnose.sh"],
                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
                tekst.after(0, lambda: tekst.insert("end", "\nKlaar.\n", "info"))
            except Exception as e:
                tekst.after(0, lambda: tekst.insert(
                    "end", f"\nFOUT: {e}\n", "err"))

        threading.Thread(target=run, daemon=True).start()

    tk.Button(btn_bar, text="PC diagnose", font=("Segoe UI", 9, "bold"),
              bg=ACCENT_PIBEHEER_2, fg=leesbare_tekstkleur(ACCENT_PIBEHEER_2), relief="flat", cursor="hand2",
              padx=12, pady=5, borderwidth=0,
              command=_run_diagnose_pc).pack(side="left", padx=8)
    # 15 augustus 2026: bg was hardcoded "#065f46" (losse groentint, geen
    # thema-kleur) - nu dezelfde ACCENT_PIBEHEER_2 als "PC diagnose"
    # hiernaast, dit zijn 2 gelijkwaardige acties in hetzelfde dialoogje.
    tk.Button(btn_bar, text="Pi diagnose (SSH)", font=("Segoe UI", 9, "bold"),
              bg=ACCENT_PIBEHEER_2, fg=leesbare_tekstkleur(ACCENT_PIBEHEER_2), relief="flat", cursor="hand2",
              padx=12, pady=5, borderwidth=0,
              command=_run_diagnose_pi).pack(side="left", padx=4)
    tk.Button(btn_bar, text="Wissen", font=("Segoe UI", 9),
              bg=PANEL2, fg=FG, relief="flat", cursor="hand2",
              padx=10, pady=5, borderwidth=0,
              command=lambda: tekst.delete("1.0", "end")).pack(side="right", padx=8)

    tekst.insert("end",
        "Kies een diagnose:\n"
        "  PC diagnose - controleert lokale software en schijven\n"
        "  Pi diagnose - voert nas_diagnose.sh uit op de Pi via SSH\n\n")

    tk.Button(dwin, text="Sluiten", command=dwin.destroy,
              bg=PANEL2, fg=FG, font=("Segoe UI", 9), relief="flat",
              cursor="hand2", pady=6, borderwidth=0).pack(fill="x", padx=10, pady=(0,8))


def _open_logs(root_win):
    lwin = tk.Toplevel(root_win)
    lwin.title("Logbestanden - Pi NAS Suite")
    lwin.configure(bg=BG)
    lwin.resizable(True, True)
    lwin.geometry("560x460")
    lwin.minsize(480, 360)
    lwin.update_idletasks()
    x = root_win.winfo_x() + (root_win.winfo_width() - 560) // 2
    y = root_win.winfo_y() + (root_win.winfo_height() - 460) // 2
    lwin.geometry(f"+{x}+{y}")

    hdr = tk.Frame(lwin, bg=ACCENT_PIBEHEER_2, pady=10)
    hdr.pack(fill="x")
    tk.Label(hdr, text="Logbestanden",
              font=("Segoe UI", 13, "bold"), bg=ACCENT_PIBEHEER_2, fg=leesbare_tekstkleur(ACCENT_PIBEHEER_2)).pack(side="left", padx=14)

    body = tk.Frame(lwin, bg=BG, padx=16, pady=12)
    body.pack(fill="both", expand=True)

    log_map = os.path.join("C:\\", "PiNAS", "Logs")

    def _nieuwste_log_bestand(prefix, fallback):
        try:
            kand = sorted(f for f in os.listdir(log_map)
                          if f.startswith(prefix) and f.endswith(".log"))
            return kand[-1] if kand else fallback
        except Exception:
            return fallback

    logs = [
        ("picontrol.log",  "Pi NAS Menu",    "Acties in het menu, verbindingen, fouten"),
        (_nieuwste_log_bestand("pinas_sync_", "pinas_sync.log"), "PiNAS Sync",  "Sync-sessies, gekopieerde bestanden, PC Image Backup"),
        ("seagate.log",    "Externe HDD (Pi)",   "Aan/uitzetten, mount logs"),
    ]

    tk.Label(body, text=f"Logmap:  {log_map}",
              font=("Segoe UI", 8), bg=BG, fg=DIM, anchor="w").pack(fill="x", pady=(0,10))

    for bestand, naam, beschr in logs:
        pad = os.path.join(log_map, bestand)
        bestaat = os.path.exists(pad)
        grootte = os.path.getsize(pad) if bestaat else 0
        grootte_str = (f"{grootte/1024:.1f} KB" if grootte >= 1024
                       else (f"{grootte} bytes" if grootte > 0 else "leeg"))

        rij = tk.Frame(body, bg=PANEL, pady=8, padx=10)
        rij.pack(fill="x", pady=3)

        kleur = OK_C if (bestaat and grootte > 0) else (DIM if bestaat else ERR_C)
        tk.Label(rij, text="●", font=("Segoe UI", 10),
                  bg=PANEL, fg=kleur, width=2).pack(side="left")
        info = tk.Frame(rij, bg=PANEL)
        info.pack(side="left", fill="x", expand=True)
        tk.Label(info, text=naam, font=("Segoe UI", 10, "bold"),
                  bg=PANEL, fg=FG, anchor="w").pack(fill="x")
        tk.Label(info, text=beschr + (f"  .  {grootte_str}" if bestaat else "  .  Nog niet aangemaakt"),
                  font=("Segoe UI", 8), bg=PANEL, fg=DIM, anchor="w").pack(fill="x")

        if bestaat:
            # 15 augustus 2026: bg was hardcoded "#1d4ed8" (losse blauwtint,
            # geen thema-kleur) - dit is een kleine actie per logregel, dus
            # nu neutraal PANEL2/FG zoals andere secundaire knopjes in de suite.
            tk.Button(rij, text="Open",
                      font=("Segoe UI", 9, "bold"), bg=PANEL2, fg=FG,
                      relief="flat", cursor="hand2", padx=10, pady=4,
                      borderwidth=0,
                      command=lambda p=pad: subprocess.Popen(
                          ["notepad.exe", p])).pack(side="right", padx=4)
        else:
            tk.Label(rij, text="-", font=("Segoe UI", 9),
                      bg=PANEL, fg=DIM).pack(side="right", padx=10)

    tk.Frame(body, bg=PANEL2, height=1).pack(fill="x", pady=10)
    tk.Label(body, text="Logs worden automatisch verwijderd na 30 dagen.",
              font=("Segoe UI", 8), bg=BG, fg=DIM, anchor="w").pack(fill="x")
    tk.Button(body, text="Sluiten", command=lwin.destroy,
              bg=PANEL2, fg=FG, font=("Segoe UI", 9), relief="flat",
              cursor="hand2", pady=6, borderwidth=0).pack(fill="x", pady=(8,0))


def start():
    win = tk.Tk()
    win.title("PiNAS - Controles (bijgewerkt: " + BIJGEWERKT + ")")
    win.configure(bg=BG)
    win.resizable(True, True)
    win.geometry("600x720")
    win.minsize(560, 660)

    # 13 augustus 2026: eigen kleur (ACCENT_PIBEHEER_2, Beheer-domein) i.p.v.
    # de algemene standaard - matcht nu de "Controles"-knop op het hoofdmenu.
    maak_header(win, "Controles", help_hoofdstukken=HELP_HOOFDSTUKKEN, kleur=ACCENT_PIBEHEER_2)

    # 15 augustus 2026: de 5 knoppen hieronder stonden voorheen 4x als
    # identiek gevulde "primair"-knop (allemaal ACCENT_PIBEHEER_2) plus 1x
    # neutraal - dus 4 even felle knoppen zonder enige hierarchie ("maak_knop
    # ... primair - hoofdactie van het scherm", pinas_ui.py). Dit scherm is
    # een menu van 5 gelijkwaardige functies, geen wizard met 1 hoofdactie -
    # daarom nu allemaal "secundair" (neutrale PANEL2), zelfde rustige
    # aanpak als eerder al bij Onderhoud is toegepast. De kleur van het
    # Beheer-domein blijft zichtbaar via de kopbalk hierboven.
    sectie0 = maak_sectie(win)
    achtergrond0 = sectie0.cget("bg")
    tk.Label(sectie0, text="Structuurcheck & Opruimen", font=("Segoe UI", 10, "bold"),
              bg=achtergrond0, fg=FG, anchor="w").pack(fill="x")
    tk.Label(sectie0, text="Verwachte bestanden controleren en verouderde bestanden opruimen",
              font=("Segoe UI", 8), bg=achtergrond0, fg=DIM, anchor="w").pack(fill="x", pady=(0, 8))
    maak_knop(sectie0, "Structuurcheck & Opruimen openen", _open_structuurcheck, stijl="secundair")

    # 13 augustus 2026: deze sectie zelf was per ongeluk nooit toegevoegd -
    # de knop stond wel al in HELP_HOOFDSTUKKEN en _open_pi_opruimen() was
    # al geschreven, maar de maak_sectie/maak_knop-aanroep hieronder ontbrak
    # (Frans meldde: "staat in de handleiding, maar zie het niet").
    sectie_pi = maak_sectie(win)
    achtergrond_pi = sectie_pi.cget("bg")
    tk.Label(sectie_pi, text="Pi opruimen", font=("Segoe UI", 10, "bold"),
              bg=achtergrond_pi, fg=FG, anchor="w").pack(fill="x")
    tk.Label(sectie_pi, text="Onbekende bestanden op de Pi zelf (/home/pi) opsporen en verwijderen",
              font=("Segoe UI", 8), bg=achtergrond_pi, fg=DIM, anchor="w").pack(fill="x", pady=(0, 8))
    maak_knop(sectie_pi, "Pi opruimen openen", _open_pi_opruimen, stijl="secundair")

    sectie = maak_sectie(win)
    achtergrond = sectie.cget("bg")
    tk.Label(sectie, text="Suite testen", font=("Segoe UI", 10, "bold"),
              bg=achtergrond, fg=FG, anchor="w").pack(fill="x")
    tk.Label(sectie, text="Kwaliteitschecks: bestanden, syntax, packages, schijven, registry, Pi services",
              font=("Segoe UI", 8), bg=achtergrond, fg=DIM, anchor="w").pack(fill="x", pady=(0, 8))
    maak_knop(sectie, "Suite testen (test_suite.py)", _start_suite_test, stijl="secundair")

    sectie2 = maak_sectie(win)
    achtergrond2 = sectie2.cget("bg")
    tk.Label(sectie2, text="Diagnose", font=("Segoe UI", 10, "bold"),
              bg=achtergrond2, fg=FG, anchor="w").pack(fill="x")
    tk.Label(sectie2, text="PC-diagnose (lokaal) en Pi-diagnose (via SSH)",
              font=("Segoe UI", 8), bg=achtergrond2, fg=DIM, anchor="w").pack(fill="x", pady=(0, 8))
    maak_knop(sectie2, "Diagnose uitvoeren", lambda: _open_diagnose(win), stijl="secundair")

    sectie3 = maak_sectie(win)
    achtergrond3 = sectie3.cget("bg")
    tk.Label(sectie3, text="Logbestanden", font=("Segoe UI", 10, "bold"),
              bg=achtergrond3, fg=FG, anchor="w").pack(fill="x")
    tk.Label(sectie3, text="Pi NAS Menu, PiNAS Sync en Externe HDD-logs bekijken",
              font=("Segoe UI", 8), bg=achtergrond3, fg=DIM, anchor="w").pack(fill="x", pady=(0, 8))
    maak_knop(sectie3, "Log Bestanden Bekijken", lambda: _open_logs(win), stijl="secundair")

    win.mainloop()


if __name__ == "__main__":
    start()
