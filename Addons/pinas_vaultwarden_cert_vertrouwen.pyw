#!/usr/bin/env python3
# pinas_vaultwarden_cert_vertrouwen.pyw - Pi NAS Suite
#
# Haalt het PiNAS root-certificaat op van de Pi (via SSH/scp) en vertrouwt
# het eenmalig in Windows via een elevated (UAC) PowerShell-script
# (pinas_vaultwarden_cert_import.ps1, moet in dezelfde map staan).
#
# 19 juli 2026: dit vertrouwt het ROOT-certificaat, niet meer een los
# servercertificaat - dus dit hoeft maar EENMALIG per pc, ook na een
# jaarlijkse automatische vernieuwing van het servercertificaat op de Pi.
#
# Hoort thuis in: Addons\pinas_vaultwarden_cert_vertrouwen.pyw

import ctypes
import os
import sys
import configparser
import tkinter as tk
from tkinter import messagebox


def _script_dir():
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def _nas_root():
    d = _script_dir()
    for sub in ["Addons", "Beheer", "PiServer", "Sync", "Gedeeld"]:
        if os.path.basename(d) == sub:
            return os.path.dirname(d)
    return os.path.dirname(d)


def _pi_ip():
    cfg = configparser.ConfigParser()
    for kandidaat in (os.path.join(_nas_root(), "Beheer", "picontrol.cfg"),
                       os.path.join("C:\\", "PiNAS", "Beheer", "picontrol.cfg")):
        if os.path.exists(kandidaat):
            cfg.read(kandidaat, encoding="utf-8")
            break
    return cfg.get("pi", "ip", fallback="UW_PI_IP_ADRES")


def start():
    root = tk.Tk()
    root.withdraw()

    ps1_pad = os.path.join(_script_dir(), "pinas_vaultwarden_cert_import.ps1")
    if not os.path.exists(ps1_pad):
        messagebox.showerror("Niet gevonden", f"pinas_vaultwarden_cert_import.ps1 niet gevonden in:\n{_script_dir()}")
        return

    pi_ip = _pi_ip()
    akkoord = messagebox.askyesno(
        "Certificaat vertrouwen",
        "Dit haalt het PiNAS root-certificaat op van de Pi "
        f"({pi_ip}) en vertrouwt het eenmalig in Windows. Er wordt "
        "om Administrator-rechten gevraagd (UAC). Volg het venster "
        "dat opent voor de voortgang.\n\nDoorgaan?")
    if not akkoord:
        return

    parameters = f'-NoProfile -ExecutionPolicy Bypass -File "{ps1_pad}" -PiIp {pi_ip}'
    resultaat = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", "powershell.exe", parameters, None, 1)
    # ShellExecuteW geeft een waarde > 32 terug bij succes, <= 32 bij een fout
    # (bijv. UAC geannuleerd door de gebruiker).
    if resultaat <= 32:
        messagebox.showinfo("Geannuleerd", "UAC-verzoek geannuleerd - er is niets gewijzigd.")


if __name__ == "__main__":
    start()
