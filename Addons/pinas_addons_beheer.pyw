#!/usr/bin/env python3
# pinas_addons_beheer.pyw - Pi NAS Suite - Addons
#
# Addons Beheer: de ENE centrale plek om de 7 add-ons (Nextcloud, Pi-hole,
# ZeroTier, Vaultwarden, Mobiele statuspagina, Printserver, PiNAS Dashboard)
# te installeren of verwijderen.
#
# PiNAS Dashboard toegevoegd (4 augustus 2026, wens Frans): 1 webpagina op
# de Pi zelf (poort 8095) die het statusoverzicht (hardware, schijfruimte,
# diensten) EN het addon-overzicht (installeren/openen) samenbrengt -
# bereikbaar vanaf elk apparaat. Zie Addons\pinas_dashboard.sh.
# Zelfde opzet als Beheer\pinas_backup_beheer.pyw (16 juli 2026).
#
# VAULTWARDEN - 19 juli 2026, herbouwd na het iOS-connectieprobleem: gebruikt
# nu een eigen root-certificaat (kleine eigen "certificaatinstantie") i.p.v.
# een los zelf-ondertekend certificaat. Dat root-certificaat vertrouw je nog
# maar EENMALIG per apparaat; het servercertificaat wordt daarna automatisch
# elk jaar vernieuwd op de Pi zelf. Zie Addons\pinas_vaultwarden.sh.
#
# Mobiele statuspagina toegevoegd (17 juli 2026, wens Frans): een met
# wachtwoord beveiligde webpagina die op de Pi zelf draait (poort 8090) en
# een mobielvriendelijk overzicht toont - thuis en, via ZeroTier, ook
# onderweg. Zie Addons\pinas_status_pagina.sh voor de details.
#
# Printserver toegevoegd (wens Frans): CUPS + AirPrint op de Pi, zodat een
# USB-printer aan de Pi (of een netwerkprinter) gedeeld wordt met alle
# apparaten. Thuis via AirPrint/IPP direct in het print-menu van telefoon
# en pc; onderweg via ZeroTier - geen open poort naar internet. Beheer via
# de CUPS-webinterface op poort 631. Zie Addons\pinas_printer.sh.
#
# Elk add-on-blok toont sinds 16 juli 2026 ook een korte statusregel
# (Geinstalleerd / Niet geinstalleerd / Onbekend) via een eenmalige SSH-
# check bij het openen, met een "Verversen"-knop rechtsboven om opnieuw te
# checken - feedback van Frans: voordat je op Installeren drukt wil je
# weten of iets al staat. Nogmaals installeren blijft daarnaast gewoon
# veilig (de scripts zijn idempotent-vriendelijk opgezet), dit is puur een
# duidelijke vingerwijzing vooraf, geen harde blokkade.
#
# Elke knop uploadt het bijbehorende .sh-script naar de Pi en draait het
# met sudo in een zichtbaar venster (zelfde patroon als Systeem-image maken
# in Backup Beheer).
#
# 31 juli 2026 (Frans): de losse Gedeeld\ScriptRunner\pi_script_draaien.bat
# (oorspronkelijk voor handmatige installatie, vroeg in het project) wordt
# niet meer apart gebruikt en is ingetrokken - Addons Beheer hier dekt nu
# alles wat dat script deed.
#
# Hoort thuis in: Addons\pinas_addons_beheer.pyw

import tkinter as tk
from tkinter import messagebox
import subprocess
import os
import sys
import tempfile
import configparser
import threading
import hashlib
import ctypes

# -- Gedeeld op het pad zetten, zodat pinas_theme en pinas_ui te vinden zijn --
_gedeeld = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Gedeeld")
if os.path.isdir(_gedeeld) and _gedeeld not in sys.path:
    sys.path.insert(0, os.path.abspath(_gedeeld))

from pinas_theme import BG, PANEL, FG, DIM, OK_C, WARN, ACCENT_PIADDONS
from pinas_ui import maak_header, maak_sectie, maak_knop
import pinas_launcher

try:
    from version import BIJGEWERKT
except ImportError:
    BIJGEWERKT = "onbekende datum"


def _script_dir():
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def _nas_root():
    """NAS root = een niveau omhoog van Addons/Beheer/PiServer/Sync/Gedeeld."""
    d = _script_dir()
    for sub in ["Addons", "Beheer", "PiServer", "Sync", "Gedeeld"]:
        if os.path.basename(d) == sub:
            return os.path.dirname(d)
    return os.path.dirname(d)


def _c_pinas():
    return os.path.join("C:\\", "PiNAS")


# -- PI_IP uit picontrol.cfg - dat bestand staat in Beheer, niet in Addons --
_cfg = configparser.ConfigParser()
_cfg_pad = os.path.join(_nas_root(), "Beheer", "picontrol.cfg")
if not os.path.exists(_cfg_pad):
    _cfg_pad = os.path.join(_c_pinas(), "Beheer", "picontrol.cfg")
if os.path.exists(_cfg_pad):
    _cfg.read(_cfg_pad, encoding="utf-8")
PI_IP = _cfg.get("pi", "ip", fallback="UW_PI_IP_ADRES")
# 4 augustus 2026 (Frans: Dashboard/Printserver-beheer moeten ook vanaf
# onderweg te openen zijn, niet alleen thuis) - ZeroTier-adres van de Pi,
# uit picontrol.cfg als dat er ooit een keer bij komt, anders de vaste
# waarde die door de hele suite heen al gebruikt wordt.
ZT_IP = _cfg.get("pi", "zt_ip", fallback="10.90.69.2")


def _haal_addon_status():
    """Eenmalige check die voor alle 7 add-ons tegelijk opvraagt of ze
    al geinstalleerd zijn - zodat je niet per ongeluk 'Installeren' klikt
    op iets dat al draait. Installeren blijft daarna gewoon veilig (de
    scripts zijn idempotent), dit is puur een duidelijke vingerwijzing
    vooraf (feedback van Frans, 16 juli 2026).

    4 augustus 2026: haalt de data nu op via de gedeelde module
    pinas_pi_status.py (1 SSH-commando, 1 parsing-logica) i.p.v. een
    eigen kopie hier - dat was voorheen apart van Pi_NAS_Menu.pyw's
    versie en liep er lichtjes uit de pas mee (bijv. Pi-hole/ZeroTier
    hadden hier alleen aanwezig/afwezig, in Pi_NAS_Menu.pyw al wel de
    preciezere actief/gestopt/afwezig). Nu 1 bron voor beide schermen.

    Geeft een dict terug met "aanwezig"/"afwezig"/"actief"/"gestopt", of
    None per sleutel als de Pi niet bereikbaar was (dan blijft de status
    'onbekend' i.p.v. een fout verzinnen)."""
    import pinas_pi_status
    leeg = {"nextcloud": None, "pihole": None, "zerotier": None, "vaultwarden": None,
            "statuspagina": None, "printer": None, "dashboard": None,
            "hash_nextcloud": None, "hash_pihole": None, "hash_zerotier": None,
            "hash_vaultwarden": None, "hash_statuspagina": None, "hash_printer": None,
            "hash_dashboard": None}
    r = pinas_pi_status.haal_pi_status(PI_IP, timeout=8)
    if not r["bereikbaar"]:
        return leeg
    resultaat = dict(leeg)
    # nextcloud/pihole/zerotier/statuspagina kennen hier bewust geen
    # actief/gestopt-onderscheid (net als voorheen, zelfde gedrag als
    # het oude losse SSH-commando had) - alleen vaultwarden/printer/
    # dashboard hebben hier al langer een Starten/Stoppen-knop en dus
    # 3 standen nodig. 'active'/'stopped' worden hier allebei "aanwezig".
    resultaat["nextcloud"] = "aanwezig" if r["nextcloud"] else "afwezig"
    for key in ("pihole", "zerotier", "statuspagina"):
        resultaat[key] = "aanwezig" if r[key] in ("active", "stopped") else "afwezig"
    for key in ("vaultwarden", "printer", "dashboard"):
        vertaald = pinas_pi_status.vertaal_naar_nederlands(r[key])
        resultaat[key] = vertaald if vertaald is not None else None
    for key in ("nextcloud", "pihole", "zerotier", "vaultwarden",
                "statuspagina", "printer", "dashboard"):
        resultaat[f"hash_{key}"] = r[f"hash_{key}"]
    return resultaat


def _status_tekst_kleur(addon_key, waarde):
    """Vertaalt de ruwe status naar (tekst, kleur) voor de statuslabel."""
    if waarde is None:
        return "Onbekend - Pi niet bereikbaar?", DIM
    if addon_key in ("vaultwarden", "printer", "dashboard"):
        if waarde == "actief":
            return "Geinstalleerd en actief", OK_C
        if waarde == "gestopt":
            return "Geinstalleerd, maar gestopt", WARN
        return "Niet geinstalleerd", DIM
    if waarde == "aanwezig":
        return "Geinstalleerd", OK_C
    return "Niet geinstalleerd", DIM


# 30 juli 2026: welk installatiescript hoort bij welke addon_key - gebruikt
# om de lokale (Windows-kant) versie te hashen en te vergelijken met de
# hash-marker die het script bij een geslaagde installatie op de Pi
# achterlaat (zie schrijf_versie_marker() in elk .sh-bestand).
_ADDON_SCRIPT = {
    "nextcloud": "pinas_nextcloud.sh",
    "pihole": "pinas_pihole.sh",
    "zerotier": "pinas_zerotier.sh",
    "vaultwarden": "pinas_vaultwarden.sh",
    "statuspagina": "pinas_status_pagina.sh",
    "printer": "pinas_printer.sh",
    "dashboard": "pinas_dashboard.sh",
}


def _lokale_hash(addon_key):
    """SHA256 van het huidige lokale installatiescript (C:\\PiNAS\\Addons\\...),
    om te vergelijken met wat er als laatst-geinstalleerd op de Pi bekend
    staat. Geeft None als het lokale bestand niet gevonden kan worden."""
    naam = _ADDON_SCRIPT.get(addon_key)
    if not naam:
        return None
    pad = os.path.join(_script_dir(), naam)
    if not os.path.exists(pad):
        return None
    try:
        with open(pad, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return None


def _bijgewerkt_tekst(addon_key, geinstalleerd_status, resultaat):
    """(tekst, kleur) voor een klein 'Bijgewerkt'-label onder de hoofdstatus -
    alleen betekenisvol als de add-on echt geinstalleerd is; anders leeg."""
    if geinstalleerd_status not in ("aanwezig", "actief", "gestopt"):
        return "", DIM
    pi_hash = resultaat.get(f"hash_{addon_key}") if resultaat else None
    if pi_hash is None:
        return "Bijgewerkt: onbekend (Pi niet bereikbaar)", DIM
    if pi_hash == "geen":
        return "Bijgewerkt: onbekend (nog geen versie-afdruk - eenmaal opnieuw installeren maakt dit zichtbaar)", DIM
    lokaal_hash = _lokale_hash(addon_key)
    if lokaal_hash is None:
        return "", DIM
    if pi_hash == lokaal_hash:
        return "Bijgewerkt: ja", OK_C
    return "Bijgewerkt: nee - lokaal bestand wijkt af, opnieuw installeren aangeraden", WARN


HELP_HOOFDSTUKKEN = [
    ("Nextcloud",
     "Je eigen prive-cloud op de Pi: bestanden, foto's, muziek en "
     "documenten, bereikbaar als een eigen Dropbox/Google Drive - maar "
     "alles blijft bij jou thuis. Installeren zet Nextcloud op; "
     "verwijderen haalt het er weer af (je data in Nextcloud zelf blijft "
     "daarbij standaard staan, zie de handleiding)."),
    ("Pi-hole",
     "Blokkeert reclame en trackers voor je hele netwerk via versleutelde "
     "DNS (dnscrypt-proxy). Elk apparaat dat via de Pi surft profiteert "
     "hiervan automatisch, zonder per-apparaat instellingen."),
    ("ZeroTier",
     "Een VPN waarmee je van onderweg veilig thuiskomt op je eigen "
     "netwerk - Samba-schijven, SSH en Nextcloud allemaal bereikbaar via "
     "dit ene VPN-IP, ook op je telefoon."),
    ("Vaultwarden",
     "Je eigen wachtwoordkluis (Bitwarden-compatibel) op de Pi - al je "
     "wachtwoorden op een plek, versleuteld, bij jou thuis in plaats van "
     "bij een extern bedrijf. Gebruikt een EIGEN ROOT-CERTIFICAAT (een "
     "kleine eigen 'certificaatinstantie', alleen voor deze Pi): dat "
     "root-certificaat vertrouw je met de knop 'Certificaat vertrouwen' "
     "eenmalig op elk apparaat (PC, iPhone, Android) - het eigenlijke "
     "servercertificaat wordt daarna automatisch elk jaar vernieuwd op "
     "de Pi zelf, zonder dat je ooit opnieuw hoeft te vertrouwen. Als "
     "ZeroTier al geinstalleerd is op het moment van installeren, wordt "
     "het ZeroTier-adres automatisch in hetzelfde certificaat opgenomen "
     "- dan werkt de kluis ook onderweg zonder certificaatwaarschuwing. "
     "Telefoon/tablet: het root-certificaat download je via de mobiele "
     "statuspagina en moet je daar zelf eenmalig vertrouwen (installeren "
     "als profiel + 'Certificaatvertrouwen' aanzetten op iPhone; als "
     "CA-certificaat installeren op Android) - zie de Suite Handleiding "
     "voor de exacte stappen."),
    ("Mobiele statuspagina",
     "Een met wachtwoord beveiligde webpagina die op de Pi zelf draait "
     "(poort 8090) met een mobielvriendelijk overzicht: diensten, "
     "hardware (temperatuur, RAM, uptime) en schijfruimte. Thuis "
     "bereikbaar via het IP van de Pi; onderweg via het ZeroTier-IP "
     "(als ZeroTier geinstalleerd is) - net als Nextcloud nu al onderweg "
     "werkt. Bij 'Diensten' staat per actieve dienst (Nextcloud, "
     "FileBrowser, Cockpit, Vaultwarden, Pi-hole, Externe HDD svc) een "
     "directe 'Openen'-link - die kiest automatisch het juiste adres: "
     "lokaal thuis, ZeroTier-adres onderweg (18 juli 2026). Het "
     "wachtwoord wordt bij installatie eenmalig getoond in het venster "
     "- schrijf het op, of typ bij installatie/resetten je eigen "
     "wachtwoord in i.p.v. het automatisch gegenereerde. Voeg de pagina "
     "op je telefoon toe aan het beginscherm voor een eigen 'app-icoon'. "
     "Wachtwoord kwijt? Gebruik de knop 'Wachtwoord resetten' - maakt "
     "een nieuw wachtwoord aan zonder dat je de hele pagina opnieuw "
     "hoeft te installeren."),
    ("Printserver",
     "Maakt van de Pi een netwerk-printserver met CUPS + AirPrint. Een "
     "USB-printer die aan de Pi hangt (of een bestaande netwerkprinter) "
     "wordt zo door alle apparaten te gebruiken. Thuis verschijnt de "
     "printer vanzelf in het print-menu van je iPhone/iPad (AirPrint) of "
     "Android (IPP/Mopria); onderweg werkt printen via ZeroTier, net als "
     "Nextcloud - er is bewust GEEN open poort naar internet. De printer "
     "voeg je eenmalig toe via de CUPS-webinterface op http://<Pi-IP>:631 "
     "(inloggen als gebruiker pi met je Pi-wachtwoord): Administration -> "
     "Add Printer -> kies je USB- of netwerkprinter en vink 'Share This "
     "Printer' aan. Zie de Suite Handleiding voor de stappen. De status "
     "hierboven toont 'Geinstalleerd en actief' of 'Geinstalleerd, maar "
     "gestopt' - staat de dienst gestopt, gebruik dan de knop 'Starten' "
     "om 'm weer aan te zetten (en aan te zetten bij een volgende reboot "
     "van de Pi), zonder opnieuw te hoeven installeren.\n\n"
     "TIP - printen op iPhone/iPad onderweg ZONDER wifi (bevestigd "
     "werkend, 27 juli 2026): (1) voeg dezelfde printer nog een keer toe "
     "met een naam die eindigt op '_onderweg', (2) installeer het "
     "AirPrint-profiel via de mobiele statuspagina, (3) koppel de printer "
     "EEN KEER met de gratis Epson Smart Panel-app (Wi-Fi Direct/QR-code, "
     "thuis op wifi) - zonder deze koppeling bleek printen zonder wifi "
     "consequent te mislukken. Zie de Suite Handleiding voor de volledige "
     "uitleg."),
    ("Installeren / Verwijderen - hoe werkt dat?",
     "Elke knop uploadt het bijbehorende script naar de Pi en draait het "
     "daar met sudo, in een apart venster dat je de voortgang laat zien "
     "(en eventuele vragen kan stellen - beantwoord die in dat venster). "
     "Gaat er iets mis? Gewoon opnieuw installeren is veilig."),
]



def _draai_script_op_pi(script_naam, mooie_naam):
    """Upload een .sh-bestand uit Addons\\ naar de Pi en draai het met
    sudo, in een zichtbaar venster - zelfde patroon als Systeem-image
    maken in Backup Beheer en de losse Script-runner in Gedeeld."""
    script_pad = os.path.join(_script_dir(), script_naam)
    if not os.path.exists(script_pad):
        messagebox.showerror("Niet gevonden",
            f"{script_naam} niet gevonden in:\n{_script_dir()}")
        return

    akkoord = messagebox.askyesno(
        mooie_naam,
        f"Dit uploadt {script_naam} naar de Pi ({PI_IP}) en draait het "
        "met sudo. Volg het venster dat opent voor de voortgang en "
        "beantwoord eventuele vragen daarin.\n\nDoorgaan?")
    if not akkoord:
        return

    bat = os.path.join(tempfile.gettempdir(), f"pinas_addon_{script_naam}.bat")
    regels = [
        "@echo off",
        f"echo {mooie_naam} - dit venster laat de voortgang zien.",
        "echo.",
        "echo Stap 1: uploaden...",
        f'scp "{script_pad}" pi@{PI_IP}:/home/pi/{script_naam}',
        "if errorlevel 1 (",
        "    echo FOUT: uploaden mislukt.",
        "    pause",
        "    exit /b 1",
        ")",
        "echo OK: geupload.",
        "echo.",
        "echo Stap 2: uitvoeren (met sudo, live uitvoer)...",
        "echo Beantwoord eventuele vragen hieronder in dit venster.",
        f'ssh -t pi@{PI_IP} "export TERM=xterm; chmod +x /home/pi/{script_naam} '
        f'&& sudo -E /home/pi/{script_naam}"',
        "echo.",
        "echo Klaar. Dit venster mag gesloten worden.",
        "pause",
    ]
    with open(bat, "w", newline="") as f:
        f.write("\r\n".join(regels) + "\r\n")
    subprocess.Popen('start cmd /k "' + bat + '"', shell=True)


def _open_cert_vertrouwen():
    ok, fout = pinas_launcher.open_programma(
        "pinas_vaultwarden_cert_vertrouwen.pyw",
        roots=[_nas_root(), _c_pinas()], submappen=["Addons"])
    if not ok:
        messagebox.showerror("Niet gevonden", fout)



def _start_dienst_op_pi(dienst_systemd, mooie_naam):
    """Start (en enable, zodat 'm ook na een Pi-reboot vanzelf meestart) een
    systemd-dienst op de Pi via SSH - voor als een add-on wel geinstalleerd
    is maar (nog) niet draait. Los van _draai_script_op_pi omdat dit geen
    installatiescript uploadt, alleen een korte systemctl-opdracht draait
    (26 juli 2026, toegevoegd na Frans's melding dat de Printserver uit
    stond en nergens via het menu gestart kon worden).

    Geeft True terug als de gebruiker heeft bevestigd (en het commando dus
    is gestart), False als geannuleerd - zodat de aanroeper daarna kan
    beslissen om automatisch te verversen (4 augustus 2026, Frans wilde
    niet apart op "Verversen" hoeven klikken na Starten/Stoppen)."""
    akkoord = messagebox.askyesno(
        mooie_naam,
        f"Dit start de {dienst_systemd}-dienst op de Pi ({PI_IP}) en zet 'm "
        "aan bij opstarten (enable).\n\nDoorgaan?")
    if not akkoord:
        return False

    bat = os.path.join(tempfile.gettempdir(), f"pinas_addon_start_{dienst_systemd}.bat")
    regels = [
        "@echo off",
        f"echo {mooie_naam} - dienst starten...",
        "echo.",
        f'ssh -t pi@{PI_IP} "sudo systemctl enable --now {dienst_systemd}"',
        "echo.",
        "echo Klaar. Dit venster mag gesloten worden.",
        "pause",
    ]
    with open(bat, "w", newline="") as f:
        f.write("\r\n".join(regels) + "\r\n")
    subprocess.Popen('start cmd /k "' + bat + '"', shell=True)
    return True


def _stop_dienst_op_pi(dienst_systemd, mooie_naam):
    """Stopt een systemd-dienst op de Pi via SSH - spiegelbeeld van
    _start_dienst_op_pi (4 augustus 2026, Frans: wil het Dashboard ook
    kunnen uitzetten, en de actief/niet-actief status duidelijk zien voor
    de veiligheid). Zet de dienst NIET uit bij opstarten (disable) - dat
    blijft een losse, bewuste stap, dit is alleen 'nu even uit'.

    Geeft True terug als de gebruiker heeft bevestigd, False als
    geannuleerd - zelfde reden als bij _start_dienst_op_pi."""
    eenheden = dienst_systemd if isinstance(dienst_systemd, list) else [dienst_systemd]
    eenheden_tekst = " ".join(eenheden)
    akkoord = messagebox.askyesno(
        mooie_naam,
        f"Dit stopt {eenheden_tekst} op de Pi ({PI_IP}).\n\n"
        "Start bij een volgende herstart van de Pi weer vanzelf op "
        "(blijft 'enabled') - dit is alleen 'nu even uit'.\n\nDoorgaan?")
    if not akkoord:
        return False

    bat = os.path.join(tempfile.gettempdir(), f"pinas_addon_stop_{eenheden[0]}.bat")
    regels = [
        "@echo off",
        f"echo {mooie_naam} - dienst stoppen...",
        "echo.",
        f'ssh -t pi@{PI_IP} "sudo systemctl stop {eenheden_tekst}"',
        "echo.",
        "echo Klaar. Dit venster mag gesloten worden.",
        "pause",
    ]
    with open(bat, "w", newline="") as f:
        f.write("\r\n".join(regels) + "\r\n")
    subprocess.Popen('start cmd /k "' + bat + '"', shell=True)
    return True


def _open_thuis_of_onderweg(poort, pad, titel):
    """Vraagt thuis of onderweg, en opent het bijbehorende adres in de
    standaardbrowser (4 augustus 2026, Frans: Openen werkte alleen thuis -
    de dienst zelf draait al op 0.0.0.0 dus is altijd ook via ZeroTier
    bereikbaar zonder verdere serverconfiguratie, alleen deze knop
    gebruikte tot nu toe altijd het lokale adres, ook onderweg)."""
    import webbrowser
    thuis = messagebox.askyesno(
        titel,
        "Ben je nu thuis, op je eigen netwerk?\n\n"
        "Ja = lokaal adres\nNee = ZeroTier-adres (onderweg)")
    ip = PI_IP if thuis else ZT_IP
    webbrowser.open(f"http://{ip}:{poort}{pad}")


def _open_cups_beheer():
    """Opent de CUPS-webinterface (printserver-beheer) in de standaardbrowser."""
    _open_thuis_of_onderweg(631, "", "Printserver - beheer openen")

def _open_dashboard():
    """Opent het PiNAS Dashboard in de standaardbrowser."""
    _open_thuis_of_onderweg(8095, "", "PiNAS Dashboard openen")


def check_zerotier_windows_dienst():
    """Vraagt via PowerShell de status van de LOKALE ZeroTier One-Windows-
    dienst op deze pc op - geeft 'actief', 'gestopt', 'afwezig' of
    'onbekend' terug. Verplaatst vanuit Pi_NAS_Menu.pyw naar hier
    (4 augustus 2026, Frans: wil dit consistent met de andere diensten
    behandeld zien, i.p.v. een aparte rij in het Status-scherm). Let op:
    dit is de dienst op DEZE pc, geen SSH-check naar de Pi."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Service -Name '*ZeroTier*' -ErrorAction SilentlyContinue "
             "| Select-Object -First 1).Status"],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW)
        status = r.stdout.strip()
        if status == "Running":
            return "actief"
        if status == "Stopped":
            return "gestopt"
        if status == "":
            return "afwezig"
        return "onbekend"
    except Exception:
        return "onbekend"


def _verhoogd_ps1_draaien(ps1_pad):
    """Draait een .ps1-bestand verhoogd (UAC) via Windows' eigen
    ShellExecuteW-elevatiemechanisme - rechtstreeks, geen geneste
    PowerShell-in-PowerShell-Start-Process-constructie meer.

    4 augustus 2026 (Frans): de oude aanpak (powershell -Command
    "Start-Process powershell -Verb RunAs -ArgumentList '...'") werkte wel
    als je het commando handmatig in een PowerShell-venster plakte, maar
    NIET via de knop in het menu - vier geneste lagen aanhalingstekens
    (Python-lijst -> Windows-commandoregel -> PowerShell -Command ->
    Start-Process -ArgumentList -> bestandspad) is precies het soort
    constructie die stilletjes verkeerd geciteerd raakt zonder
    foutmelding. ShellExecuteW is de directe, door Windows zelf
    aangeboden manier om iets verhoogd te starten - maar 1 laag."""
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", "powershell.exe",
        f'-NoProfile -ExecutionPolicy Bypass -File "{ps1_pad}"',
        None, 1)


def _start_zerotier_windows(mooie_naam):
    """Start de lokale ZeroTier-dienst - vraagt Windows-beheerdersbeves-
    tiging (UAC). Zelfde True/False-teruggave als _start_dienst_op_pi,
    voor de _actie_en_ververs()-koppeling."""
    akkoord = messagebox.askyesno(
        mooie_naam,
        "Dit start de lokale ZeroTier-dienst op DEZE pc - Windows vraagt "
        "hiervoor om een beheerdersbevestiging (UAC-scherm).\n\nDoorgaan?")
    if not akkoord:
        return False
    ps1_pad = os.path.join(tempfile.gettempdir(), "pinas_zerotier_start.ps1")
    with open(ps1_pad, "w", encoding="utf-8") as f:
        f.write("Get-Service -Name '*ZeroTier*' -ErrorAction SilentlyContinue "
                "| Start-Service\n")
    _verhoogd_ps1_draaien(ps1_pad)
    return True


def _stop_zerotier_windows(mooie_naam):
    """Stopt de lokale ZeroTier-dienst - spiegelbeeld van _start_zerotier_windows."""
    akkoord = messagebox.askyesno(
        mooie_naam,
        "Dit stopt de lokale ZeroTier-dienst op DEZE pc - Windows vraagt "
        "hiervoor om een beheerdersbevestiging (UAC-scherm). Zolang de "
        "dienst uit staat, is de Pi vanaf dit apparaat niet via ZeroTier "
        "bereikbaar.\n\nDoorgaan?")
    if not akkoord:
        return False
    ps1_pad = os.path.join(tempfile.gettempdir(), "pinas_zerotier_stop.ps1")
    with open(ps1_pad, "w", encoding="utf-8") as f:
        f.write("Get-Service -Name '*ZeroTier*' -ErrorAction SilentlyContinue "
                "| Stop-Service -Force\n")
    _verhoogd_ps1_draaien(ps1_pad)
    return True


def _bouw_addon_item(win, titel, subtekst, acties, status_labels, addon_key, bijgewerkt_labels=None,
                      aan_uit_knoppen=None):
    """acties: lijst van (knoptekst, functie, stijl) - 1 tot 2 hoofdknoppen
    (Installeren/Verwijderen), plus optioneel 1 of 2 extra knoppen eronder.

    status_labels: dict waarin het statuslabel voor addon_key wordt
    opgeslagen, zodat _ververs_status() het later kan bijwerken zonder
    het hele venster opnieuw te tekenen.

    bijgewerkt_labels: zelfde patroon, voor het kleine 'Bijgewerkt: ja/nee'-
    label dat laat zien of de Pi nog de nieuwste versie van dit
    installatiescript heeft gedraaid (30 juli 2026).

    aan_uit_knoppen: zelfde patroon (4 augustus 2026, Frans: wil in 1
    oogopslag zien of een dienst draait EN de niet-toepasselijke knop
    (Starten als 'ie al draait, Stoppen als 'ie al staat) grijs/inactief
    zien in plaats van dit uit het statuslabel erboven te moeten afleiden).
    Alleen gebruikt als acties precies 2 extra knoppen heeft (Starten +
    Stoppen, in die volgorde) - _ververs_status() zet daarna per addon de
    juiste knop aan/uit op basis van de echte Pi-status."""
    sectie = maak_sectie(win)
    achtergrond = sectie.cget("bg")

    kop_rij = tk.Frame(sectie, bg=achtergrond)
    kop_rij.pack(fill="x")
    tk.Label(kop_rij, text=titel, font=("Segoe UI", 10, "bold"),
              bg=achtergrond, fg=FG, anchor="w").pack(side="left")
    status_lbl = tk.Label(kop_rij, text="●  bezig met controleren...",
                           font=("Segoe UI", 8, "bold"), bg=achtergrond, fg=DIM)
    status_lbl.pack(side="right")
    status_labels[addon_key] = status_lbl

    tk.Label(sectie, text=subtekst, font=("Segoe UI", 8),
              bg=achtergrond, fg=DIM, anchor="w").pack(fill="x", pady=(0, 2))

    if bijgewerkt_labels is not None:
        bijgewerkt_lbl = tk.Label(sectie, text="", font=("Segoe UI", 8),
                                    bg=achtergrond, fg=DIM, anchor="w")
        bijgewerkt_lbl.pack(fill="x", pady=(0, 8))
        bijgewerkt_labels[addon_key] = bijgewerkt_lbl
    else:
        tk.Frame(sectie, bg=achtergrond, height=6).pack(fill="x")

    # 18 juli 2026 (Frans: knoppen vielen van het venster af bij 3 stuks
    # naast elkaar): Installeren/Verwijderen op de eerste rij. 4 augustus
    # 2026: omgezet naar een grid met 2 gelijke kolommen (i.p.v. naast
    # elkaar "packen") zodat een knoppenrij eronder er precies onder
    # uitgelijnd kan worden.
    knop_rij = tk.Frame(sectie, bg=achtergrond)
    knop_rij.pack(fill="x")
    knop_rij.columnconfigure(0, weight=1)
    knop_rij.columnconfigure(1, weight=1)
    # 4 augustus 2026 (Frans, echte crash gevonden en met een losse test
    # bevestigd): maak_knop() verpakt een nieuwe knop intern altijd meteen
    # met pack(). Zodra de EERSTE knop hier al met grid() staat, crasht het
    # AANMAKEN van de tweede knop meteen (de interne pack() botst dan al
    # met de grid-buur) - dus nooit knoppen om-en-om maken+gridden. Eerst
    # ALLE knoppen van deze rij aanmaken, dan ALLEMAAL pack_forget(), en
    # pas daarna allemaal grid() - alleen die volgorde is veilig.
    gemaakte_hoofdknoppen = [
        maak_knop(knop_rij, tekst, actie, stijl=stijl, kleur=ACCENT_PIADDONS)
        for tekst, actie, stijl in acties[:2]
    ]
    for knop in gemaakte_hoofdknoppen:
        knop.pack_forget()
    for col, knop in enumerate(gemaakte_hoofdknoppen):
        knop.grid(row=0, column=col, sticky="ew", padx=(0, 8) if col == 0 else (0, 0))

    # 4 augustus 2026: als de HOOFDknoppen zelf al Starten/Stoppen zijn
    # (geen Installeren/Verwijderen - bijv. de lokale ZeroTier-dienst, die
    # niets te installeren heeft), moet de aan/uit-koppeling ook hier al
    # gebeuren, niet alleen bij de latere "extra"-knoppenrij hieronder.
    if (aan_uit_knoppen is not None and len(acties) >= 2
            and acties[0][0] == "Starten" and acties[1][0] == "Stoppen"):
        aan_uit_knoppen[addon_key] = {"openen": None,
                                       "starten": gemaakte_hoofdknoppen[0],
                                       "stoppen": gemaakte_hoofdknoppen[1]}

    extra_acties = acties[2:]
    starten_stoppen = (len(extra_acties) >= 2
                        and extra_acties[-2][0] == "Starten" and extra_acties[-1][0] == "Stoppen")
    # 4 augustus 2026 (Frans): een "Open(en)"-knop die er direct voor staat
    # (Openen (8095), Beheer openen (631)) hoort er ook bij op dezelfde
    # regel, niet los erboven - en telt mee in de aan/uit-status (alleen
    # klikbaar als de dienst ook echt actief is, i.p.v. altijd klikbaar).
    open_erbij = (starten_stoppen and len(extra_acties) >= 3
                  and "open" in extra_acties[-3][0].lower())
    groep = extra_acties[-3:] if open_erbij else (extra_acties[-2:] if starten_stoppen else [])
    losse_extras = extra_acties[:-len(groep)] if groep else extra_acties

    for tekst, actie, stijl in losse_extras:
        extra_rij = tk.Frame(sectie, bg=achtergrond)
        extra_rij.pack(fill="x", pady=(6, 0))
        knop = maak_knop(extra_rij, tekst, actie, stijl=stijl, kleur=ACCENT_PIADDONS)
        knop.pack(side="left", padx=(0, 8))

    if groep:
        # Openen/Starten/Stoppen samen exact zo breed als de Verwijderen-
        # knop erboven, op 1 regel - in een sub-frame dat zelf in kolom 1
        # van dezelfde 2-koloms-grid als knop_rij zit; kolom 0 (onder
        # Installeren) blijft leeg.
        extra_rij = tk.Frame(sectie, bg=achtergrond)
        extra_rij.pack(fill="x", pady=(6, 0))
        extra_rij.columnconfigure(0, weight=1)
        extra_rij.columnconfigure(1, weight=1)
        tk.Frame(extra_rij, bg=achtergrond).grid(row=0, column=0, sticky="ew")
        sub = tk.Frame(extra_rij, bg=achtergrond)
        sub.grid(row=0, column=1, sticky="ew")
        for kol in range(len(groep)):
            sub.columnconfigure(kol, weight=1)
        # Eerst ALLE knoppen van deze regel maken, dan ALLEMAAL
        # pack_forget(), dan pas allemaal grid() - zie uitleg hierboven bij
        # de hoofdknoppen-rij, zelfde reden.
        knoppen_gemaakt = [
            maak_knop(sub, tekst, actie, stijl=stijl, kleur=ACCENT_PIADDONS)
            for tekst, actie, stijl in groep
        ]
        for knop in knoppen_gemaakt:
            knop.pack_forget()
        for i, knop in enumerate(knoppen_gemaakt):
            knop.grid(row=0, column=i, sticky="ew", padx=(0, 6) if i < len(knoppen_gemaakt) - 1 else (0, 0))
        if aan_uit_knoppen is not None:
            if open_erbij:
                aan_uit_knoppen[addon_key] = {"openen": knoppen_gemaakt[0],
                                               "starten": knoppen_gemaakt[1], "stoppen": knoppen_gemaakt[2]}
            else:
                aan_uit_knoppen[addon_key] = {"openen": None,
                                               "starten": knoppen_gemaakt[0], "stoppen": knoppen_gemaakt[1]}


def start():
    win = tk.Tk()
    win.title("PiNAS - Addons Beheer (bijgewerkt: " + BIJGEWERKT + ")")
    win.configure(bg=BG)
    win.resizable(True, True)
    # 18 juli 2026: breedte 640->700 (Frans: knoppen vielen van het venster
    # af). Hoogte 800 (740->480 minsize) nu de inhoud scrollbaar is - zie
    # ook de wijziging in _bouw_addon_item() die de 3e knop sowieso op een
    # eigen rij zet, ongeacht vensterbreedte.
    win.geometry("700x800")
    win.minsize(620, 480)

    hdr = maak_header(win, "Addons Beheer",
                       help_hoofdstukken=HELP_HOOFDSTUKKEN, kleur=ACCENT_PIADDONS)

    # Scrollbaar body - zelfde opzet als Onderhoud/Status in Pi_NAS_Menu.pyw.
    # Dit venster is zijn eigen Tk-proces (los van het hoofdmenu), dus een
    body_container = tk.Frame(win, bg=BG)
    body_container.pack(fill="both", expand=True)
    _canvas = tk.Canvas(body_container, bg=BG, highlightthickness=0)
    _scroll = tk.Scrollbar(body_container, orient="vertical", command=_canvas.yview)
    _canvas.configure(yscrollcommand=_scroll.set)
    _scroll.pack(side="right", fill="y")
    _canvas.pack(side="left", fill="both", expand=True)
    body = tk.Frame(_canvas, bg=BG)
    _body_canvas_win = _canvas.create_window((0, 0), window=body, anchor="nw")
    body.bind("<Configure>", lambda e: _canvas.configure(scrollregion=_canvas.bbox("all")))
    _canvas.bind("<Configure>", lambda e: _canvas.itemconfig(_body_canvas_win, width=e.width))
    # 6 augustus 2026 (Frans: muiswiel-scroll van het ene venster bleef
    # "vasthouden" als een ander suite-venster tegelijk open stond) - de
    # eerdere aanname "geen ander venster om rekening mee te houden" klopte
    # niet, Addons Beheer kan prima naast Onderhoud/Status/Help open staan.
    # Zelfde Enter/Leave-scoped patroon als al bewezen in pinas_kleuren_
    # kiezer.pyw: alleen actief zolang de muis boven DIT venster hangt.
    def _wiel_aan(e):
        _canvas.bind_all("<MouseWheel>", lambda ev: _canvas.yview_scroll(
            int(-1 * (ev.delta / 120)), "units"))
    def _wiel_uit(e):
        _canvas.unbind_all("<MouseWheel>")
    _canvas.bind("<Enter>", _wiel_aan)
    _canvas.bind("<Leave>", _wiel_uit)

    status_labels = {}
    bijgewerkt_labels = {}
    aan_uit_knoppen = {}

    def _ververs_status():
        for lbl in status_labels.values():
            lbl.config(text="●  bezig met controleren...", fg=DIM)
        for lbl in bijgewerkt_labels.values():
            lbl.config(text="", fg=DIM)

        def _werk():
            resultaat = _haal_addon_status()
            def _toepassen():
                for key, lbl in status_labels.items():
                    tekst, kleur = _status_tekst_kleur(key, resultaat.get(key))
                    lbl.config(text="●  " + tekst, fg=kleur)
                    if key in bijgewerkt_labels:
                        b_tekst, b_kleur = _bijgewerkt_tekst(key, resultaat.get(key), resultaat)
                        bijgewerkt_labels[key].config(text=b_tekst, fg=b_kleur)
                    if key in aan_uit_knoppen:
                        waarde = resultaat.get(key)
                        openen_knop = aan_uit_knoppen[key]["openen"]
                        starten_knop = aan_uit_knoppen[key]["starten"]
                        stoppen_knop = aan_uit_knoppen[key]["stoppen"]
                        if waarde == "actief":
                            if openen_knop is not None:
                                openen_knop.config(state="normal")
                            starten_knop.config(state="disabled")
                            stoppen_knop.config(state="normal")
                        elif waarde == "gestopt":
                            if openen_knop is not None:
                                openen_knop.config(state="disabled")
                            starten_knop.config(state="normal")
                            stoppen_knop.config(state="disabled")
                        else:
                            # afwezig (niet geinstalleerd) of onbekend (Pi
                            # niet bereikbaar) - geen van drieen zinvol
                            if openen_knop is not None:
                                openen_knop.config(state="disabled")
                            starten_knop.config(state="disabled")
                            stoppen_knop.config(state="disabled")
            win.after(0, _toepassen)
        threading.Thread(target=_werk, daemon=True).start()

    ververs_knop = tk.Label(hdr, text="↻  Status verversen", font=("Segoe UI", 9),
                             bg=BG, fg=ACCENT_PIADDONS, cursor="hand2")
    ververs_knop.pack(side="right", padx=(0, 12))
    def _actie_en_ververs(functie, addon_key):
        """Voert een Starten/Stoppen-actie uit en ververst de status
        automatisch - Frans (4 augustus 2026) wilde niet apart op
        'Verversen' hoeven klikken. Alleen verversen als de gebruiker
        echt heeft bevestigd (functie geeft dan True terug).

        Zelfde polijst als bij de lokale ZeroTier-dienst (4 augustus
        2026): meteen bij het klikken al "bezig..." tonen + knoppen
        uitschakelen (voorkomt dubbel klikken), en meerdere keren
        verversen (2/5/9 sec) i.p.v. 1 vaste gok - SSH+sudo kan, net als
        een UAC-scherm, even op een reactie moeten wachten."""
        if functie():
            lbl = status_labels.get(addon_key)
            if lbl:
                lbl.config(text="\u25cf  bezig...", fg=DIM)
            knoppen = aan_uit_knoppen.get(addon_key)
            if knoppen:
                knoppen["starten"].config(state="disabled")
                knoppen["stoppen"].config(state="disabled")
                if knoppen.get("openen") is not None:
                    knoppen["openen"].config(state="disabled")
            for _vertraging in (2000, 5000, 9000):
                win.after(_vertraging, _ververs_status)

    _bouw_addon_item(
        body, "Nextcloud", "Eigen prive-cloud: bestanden, foto's, muziek, documenten",
        [("Installeren", lambda: _draai_script_op_pi("pinas_nextcloud.sh", "Nextcloud installeren"), "primair"),
         ("Verwijderen", lambda: _draai_script_op_pi("pinas_nextcloud_verwijderen.sh", "Nextcloud verwijderen"), "destructief")],
        status_labels, "nextcloud", bijgewerkt_labels)

    _bouw_addon_item(
        body, "Pi-hole", "Adblock + versleutelde DNS voor je hele netwerk",
        [("Installeren", lambda: _draai_script_op_pi("pinas_pihole.sh", "Pi-hole installeren"), "primair"),
         ("Verwijderen", lambda: _draai_script_op_pi("pinas_pihole_verwijderen.sh", "Pi-hole verwijderen"), "destructief")],
        status_labels, "pihole", bijgewerkt_labels)

    _bouw_addon_item(
        body, "ZeroTier (Pi)", "VPN - veilig thuis komen van onderweg",
        [("Installeren", lambda: _draai_script_op_pi("pinas_zerotier.sh", "ZeroTier installeren"), "primair"),
         ("Verwijderen", lambda: _draai_script_op_pi("pinas_zerotier_verwijderen.sh", "ZeroTier verwijderen"), "destructief")],
        status_labels, "zerotier", bijgewerkt_labels)

    # 4 augustus 2026 (Frans): ZeroTier-dienst op DEZE pc, consistent
    # behandeld met de andere diensten hierboven (Starten/Stoppen-knoppen)
    # i.p.v. de aparte rij die eerst in het Status-scherm stond. BEWUST
    # met een eigen, LOSSE status_labels/aan_uit_knoppen-dict, niet de
    # gedeelde: dit is een lokale Windows-dienst-check (PowerShell), geen
    # SSH-check naar de Pi - zou anders door _ververs_status() elke keer
    # verkeerd overschreven worden met "Onbekend - Pi niet bereikbaar".
    windows_status_labels = {}
    windows_aan_uit_knoppen = {}
    _bouw_addon_item(
        body, "ZeroTier - lokale dienst (deze pc)",
        "De ZeroTier-VPN-dienst op DEZE Windows-pc zelf - moet actief zijn "
        "om de Pi via ZeroTier te kunnen bereiken (los van de ZeroTier-"
        "addon hierboven, die over de Pi-kant gaat)",
        [("Starten", lambda: _actie_en_ververs_lokaal(
            lambda: _start_zerotier_windows("ZeroTier-dienst starten")), "primair"),
         ("Stoppen", lambda: _actie_en_ververs_lokaal(
            lambda: _stop_zerotier_windows("ZeroTier-dienst stoppen")), "destructief")],
        windows_status_labels, "windows_zerotier", None, windows_aan_uit_knoppen)

    def _ververs_windows_zerotier():
        """Eigen, lokale verversing voor de ZeroTier-Windows-dienst-rij -
        los van _ververs_status() (die is voor de SSH/Pi-kant-diensten).
        Via een achtergrondthread, net als de rest van dit venster, zodat
        de PowerShell-aanroep het scherm niet even laat vastlopen."""
        lbl = windows_status_labels.get("windows_zerotier")
        if lbl is None:
            return
        lbl.config(text="\u25cf  bezig met controleren...", fg=DIM)

        def _werk():
            status = check_zerotier_windows_dienst()
            def _toepassen():
                knoppen = windows_aan_uit_knoppen.get("windows_zerotier")
                tekst = {"actief": "Actief", "gestopt": "Gestopt",
                         "afwezig": "Niet gevonden", "onbekend": "Onbekend"}[status]
                kleur = {"actief": OK_C, "gestopt": WARN, "afwezig": DIM, "onbekend": DIM}[status]
                lbl.config(text="\u25cf  " + tekst, fg=kleur)
                if knoppen:
                    starten_knop, stoppen_knop = knoppen["starten"], knoppen["stoppen"]
                    if status == "actief":
                        starten_knop.config(state="disabled"); stoppen_knop.config(state="normal")
                    elif status == "gestopt":
                        starten_knop.config(state="normal"); stoppen_knop.config(state="disabled")
                    else:
                        starten_knop.config(state="disabled"); stoppen_knop.config(state="disabled")
            win.after(0, _toepassen)
        threading.Thread(target=_werk, daemon=True).start()

    def _actie_en_ververs_lokaal(functie):
        """Zelfde patroon als _actie_en_ververs, maar voor de lokale
        ZeroTier-Windows-dienst. 4 augustus 2026 (Frans: knop bleef oranje
        staan na een geslaagde start, en klikte daardoor 2x): 1 vaste
        vertraging is altijd gokken, want hoelang jij nodig hebt om het
        UAC-scherm te bevestigen is onvoorspelbaar. Nu meteen bij het
        klikken al "bezig..." tonen (voorkomt dubbel klikken) EN
        meerdere keren verversen (2/5/9/15 sec) i.p.v. 1x - vangt zowel
        een snelle als een tragere UAC-bevestiging op."""
        if functie():
            lbl = windows_status_labels.get("windows_zerotier")
            knoppen = windows_aan_uit_knoppen.get("windows_zerotier")
            if lbl:
                lbl.config(text="\u25cf  bezig - bevestig het UAC-scherm...", fg=DIM)
            if knoppen:
                knoppen["starten"].config(state="disabled")
                knoppen["stoppen"].config(state="disabled")
            for _vertraging in (2000, 5000, 9000, 15000):
                win.after(_vertraging, _ververs_windows_zerotier)

    win.after(0, _ververs_windows_zerotier)
    ververs_knop.bind("<Button-1>", lambda e: (_ververs_status(), _ververs_windows_zerotier()))

    _bouw_addon_item(
        body, "Vaultwarden", "Eigen wachtwoordkluis (Bitwarden-compatibel)",
        [("Installeren", lambda: _draai_script_op_pi("pinas_vaultwarden.sh", "Vaultwarden installeren"), "primair"),
         ("Verwijderen", lambda: _draai_script_op_pi("pinas_vaultwarden_verwijderen.sh", "Vaultwarden verwijderen"), "destructief"),
         ("Certificaat vertrouwen", _open_cert_vertrouwen, "secundair")],
        status_labels, "vaultwarden", bijgewerkt_labels)

    _bouw_addon_item(
        body, "Mobiele statuspagina", "Statusoverzicht op je telefoon - thuis en onderweg (via ZeroTier)",
        [("Installeren", lambda: _draai_script_op_pi("pinas_status_pagina.sh", "Mobiele statuspagina installeren"), "primair"),
         ("Verwijderen", lambda: _draai_script_op_pi("pinas_status_pagina_verwijderen.sh", "Mobiele statuspagina verwijderen"), "destructief"),
         ("Wachtwoord resetten", lambda: _draai_script_op_pi("pinas_status_pagina_wachtwoord_resetten.sh", "Wachtwoord resetten"), "secundair")],
        status_labels, "statuspagina", bijgewerkt_labels)

    _bouw_addon_item(
        body, "Printserver", "Print via de Pi - USB- of netwerkprinter delen (AirPrint, ook onderweg via ZeroTier)",
        [("Installeren", lambda: _draai_script_op_pi("pinas_printer.sh", "Printserver installeren"), "primair"),
         ("Verwijderen", lambda: _draai_script_op_pi("pinas_printer_verwijderen.sh", "Printserver verwijderen"), "destructief"),
         ("Beheer openen (631)", _open_cups_beheer, "secundair"),
         ("Starten", lambda: _actie_en_ververs(lambda: _start_dienst_op_pi("cups", "Printserver starten"), "printer"), "primair"),
         ("Stoppen", lambda: _actie_en_ververs(lambda: _stop_dienst_op_pi(["cups", "cups.socket"], "Printserver stoppen"), "printer"), "destructief")],
        status_labels, "printer", bijgewerkt_labels, aan_uit_knoppen)

    _bouw_addon_item(
        body, "PiNAS Dashboard", "Status + addons in 1 pagina - bereikbaar vanaf elk apparaat (thuis en onderweg via ZeroTier)",
        [("Installeren", lambda: _draai_script_op_pi("pinas_dashboard.sh", "Dashboard installeren"), "primair"),
         ("Verwijderen", lambda: _draai_script_op_pi("pinas_dashboard_verwijderen.sh", "Dashboard verwijderen"), "destructief"),
         ("Openen (8095)", _open_dashboard, "secundair"),
         ("Starten", lambda: _actie_en_ververs(lambda: _start_dienst_op_pi("pinas-dashboard", "Dashboard starten"), "dashboard"), "primair"),
         ("Stoppen", lambda: _actie_en_ververs(lambda: _stop_dienst_op_pi("pinas-dashboard", "Dashboard stoppen"), "dashboard"), "destructief")],
        status_labels, "dashboard", bijgewerkt_labels, aan_uit_knoppen)

    _ververs_status()
    win.mainloop()


if __name__ == "__main__":
    start()
