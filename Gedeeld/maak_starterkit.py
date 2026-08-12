"""
Pi NAS Suite - Maak Starter Kit ZIP
Staat in: C:\\PiNAS\\Gedeeld\\
Output:   C:\\PiNAS\\Publicatie\\StarterKit\\starterkit_nas.zip
Geanonimiseerd - klaar voor installatie op nieuwe pc

(12 augustus 2026) Omgezet van maak_starterkit.bat naar Python, als onderdeel
van de .bat->.py-migratie (zie OVERDRACHT_NIEUWE_CHAT.md). Bij die
gelegenheid:
  - NAS Simulator hoort er niet meer bij (niet meer gebruikt) - de
    PiServer-bestanden maak_simulator_map.bat, Dockerfile, sim_setup.sh,
    SIMULATOR_LEESMIJ.md en start.sh zijn uit de meegekopieerde lijst
    gehaald.
  - lanman_fix.bat/install_vnc_viewer.bat/nas_upload.bat/nas_diagnose.bat
    zijn hernoemd naar hun .py-versies (dezelfde migratieronde).
  - Anonimiseren gebeurt nu in Python zelf i.p.v. via een los PowerShell-
    commando - functioneel identiek (zelfde vervangingen, zelfde UTF-8-
    zonder-BOM-schrijfwijze), maar zonder de PowerShell-afhankelijkheid.
"""
import os
import re
import shutil
import sys
import tempfile
import zipfile

NAS_ROOT = r"C:\PiNAS"


def _output_map():
    return os.path.join(NAS_ROOT, "Publicatie", "StarterKit")


def _copy(bronmap, doelmap, bestand):
    bron = os.path.join(bronmap, bestand)
    if os.path.exists(bron):
        os.makedirs(doelmap, exist_ok=True)
        shutil.copy2(bron, os.path.join(doelmap, bestand))
        print(f"   OK: {os.path.relpath(bron, NAS_ROOT)}")
        return True
    print(f"   --: {os.path.relpath(bron, NAS_ROOT)} niet gevonden")
    return False


def _anonimiseer(werkmap, wachtwoord):
    """Zelfde vervangingen als de oude PowerShell-anonimisering: IP,
    wachtwoord, 'UW_WACHTWOORD'-placeholder, gebruikersnaam, ZeroTier netwerk-ID.
    Schrijft UTF-8 ZONDER BOM (anders herkent cmd.exe '@echo off' niet meer
    in de .bat-bestanden die nog in het pakket zitten)."""
    extensies = {".bat", ".py", ".sh", ".json", ".md", ".ini", ".cfg"}
    for dirpad, _dirs, bestanden in os.walk(werkmap):
        for naam in bestanden:
            if os.path.splitext(naam)[1].lower() not in extensies:
                continue
            pad = os.path.join(dirpad, naam)
            with open(pad, "rb") as f:
                data = f.read()
            if data[:3] == b"\xef\xbb\xbf":
                data = data[3:]
            try:
                tekst = data.decode("utf-8")
            except UnicodeDecodeError:
                continue

            tekst = re.sub(r"192\.168\.\d+\.\d+", "UW_PI_IP_ADRES", tekst)
            if wachtwoord:
                tekst = tekst.replace(wachtwoord, "UW_WACHTWOORD")
            tekst = tekst.replace("UW_WACHTWOORD", "UW_WACHTWOORD")
            tekst = re.sub(r"GEBRUIKER(?!hrier)[a-z]*", "GEBRUIKER", tekst)
            tekst = tekst.replace("UW_ZEROTIER_NETWERK_ID", "UW_ZEROTIER_NETWERK_ID")

            with open(pad, "w", encoding="utf-8", newline="") as f:
                f.write(tekst)
            print(f"   Schoon: {naam}")


def main():
    output_map = _output_map()
    werkmap = os.path.join(tempfile.gettempdir(), "starterkit_werk")
    zip_pad = os.path.join(output_map, "starterkit_nas.zip")

    print()
    print(" Pi NAS Suite - Starter Kit bouwen")
    print(" " + "=" * 62)
    print(f" NAS root:  {NAS_ROOT}")
    print(f" Output:    {zip_pad}")
    print(" " + "=" * 62)
    print()

    if os.path.exists(werkmap):
        shutil.rmtree(werkmap)
    os.makedirs(werkmap)
    os.makedirs(output_map, exist_ok=True)

    print("  [Stap 1] Bestanden kopieren...")
    print()

    # -- Beheer ---------------------------------------------------------
    beheer_doel = os.path.join(werkmap, "Beheer")
    for bestand in (
        "Pi_NAS_Menu.pyw", "pi_nas_setup.pyw", "Pi_NAS_Menu.ico",
        "lanman_fix.py", "install_vnc_viewer.py",
        "pinas_backup_beheer.pyw", "pinas_image_backup.pyw",
    ):
        _copy(os.path.join(NAS_ROOT, "Beheer"), beheer_doel, bestand)

    # PC Image Backup's gedeelde module staat in de submap core/
    core_bron = os.path.join(NAS_ROOT, "Beheer", "core")
    if os.path.isdir(core_bron):
        core_doel = os.path.join(beheer_doel, "core")
        os.makedirs(core_doel, exist_ok=True)
        for naam in os.listdir(core_bron):
            bron = os.path.join(core_bron, naam)
            if os.path.isfile(bron):
                shutil.copy2(bron, os.path.join(core_doel, naam))
        print("   OK: Beheer\\core\\")
    else:
        print("   --: Beheer\\core niet gevonden")

    # Screenshots staan in de submap assets/
    assets_bron = os.path.join(NAS_ROOT, "Beheer", "assets")
    if os.path.isdir(assets_bron):
        assets_doel = os.path.join(beheer_doel, "assets")
        os.makedirs(assets_doel, exist_ok=True)
        for naam in os.listdir(assets_bron):
            if naam.startswith("pinas_sync_scherm") and naam.lower().endswith(".png"):
                shutil.copy2(os.path.join(assets_bron, naam), os.path.join(assets_doel, naam))
        print("   OK: Beheer\\assets\\ screenshots")
    else:
        print("   --: Beheer\\assets niet gevonden")

    # -- Publicatie -------------------------------------------------------
    publicatie_doel = os.path.join(werkmap, "Publicatie")
    for bestand in ("PiNAS_Suite_Handleiding.pdf", "build_suite_handleiding.py"):
        _copy(os.path.join(NAS_ROOT, "Publicatie"), publicatie_doel, bestand)

    # -- Sync ---------------------------------------------------------------
    sync_doel = os.path.join(werkmap, "Sync")
    os.makedirs(os.path.join(sync_doel, "core"), exist_ok=True)
    for bestand in ("pinas_sync_app.pyw", "start.bat", "requirements.txt", "install_windows.bat"):
        _copy(os.path.join(NAS_ROOT, "Sync"), sync_doel, bestand)
    for bestand in ("sync_engine.py", "bron_doel_picker.py", "thema.py", "__init__.py"):
        bron = os.path.join(NAS_ROOT, "Sync", "core", bestand)
        if os.path.exists(bron):
            shutil.copy2(bron, os.path.join(sync_doel, "core", bestand))
            print(f"   OK: Sync\\core\\{bestand}")

    # -- ArchiefBackup (hoofdmap, hoort bij Backup Beheer - geen zijproject meer) --
    archief_doel = os.path.join(werkmap, "ArchiefBackup")
    for bestand in ("archief_backup_bewaking.pyw", "start.bat"):
        _copy(os.path.join(NAS_ROOT, "ArchiefBackup"), archief_doel, bestand)

    # -- Addons (17 juli 2026 toegevoegd - stonden er nooit in) -------------
    addons_doel = os.path.join(werkmap, "Addons")
    for bestand in (
        "pinas_addons_beheer.pyw",
        "pinas_nextcloud.sh", "pinas_nextcloud_verwijderen.sh",
        "pinas_pihole.sh", "pinas_pihole_verwijderen.sh",
        "pinas_zerotier.sh", "pinas_zerotier_verwijderen.sh",
        "pinas_vaultwarden.sh", "pinas_vaultwarden_verwijderen.sh",
        "pinas_vaultwarden_cert_vertrouwen.pyw", "pinas_vaultwarden_cert_import.ps1",
        "pinas_status_pagina.sh", "pinas_status_pagina_verwijderen.sh",
        "pinas_status_pagina_wachtwoord_resetten.sh",
        "pinas_printer.sh", "pinas_printer_verwijderen.sh",
        "pinas_dashboard.sh", "pinas_dashboard_verwijderen.sh",
    ):
        _copy(os.path.join(NAS_ROOT, "Addons"), addons_doel, bestand)

    # -- PiServer -------------------------------------------------------------
    # (12 augustus 2026) Simulator-bestanden (maak_simulator_map.bat, Dockerfile,
    # sim_setup.sh, SIMULATOR_LEESMIJ.md, start.sh) bewust weggelaten - de NAS
    # Simulator wordt niet meer gebruikt.
    piserver_doel = os.path.join(werkmap, "PiServer")
    for bestand in (
        "nas_installer.py", "nas_installer_cli.py", "seagate_web.py",
        "seagate-web.service", "smart_plug.py", "smart_plug_config.json",
        "hue_diagnose.py", "pi_welkom.sh", "install.sh", "nas_start.sh",
        "README.md",
    ):
        _copy(os.path.join(NAS_ROOT, "PiServer"), piserver_doel, bestand)

    # -- Gedeeld ----------------------------------------------------------------
    gedeeld_doel = os.path.join(werkmap, "Gedeeld")
    for bestand in (
        "pinas_theme.py", "pinas_theme_donker.py", "pinas_theme_licht.py",
        "pinas_ui.py", "pinas_wachtwoord.py", "pinas_logging.py",
        "pinas_launcher.py", "pinas_pi_status.py",
        "controleer_documentatie_consistentie.py", "pinas_schijven.py",
        "pinas_versies.json", "version.py",
        "nas_upload.py", "nas_diagnose.py", "nas_diagnose.sh",
        "herstel_backup_hdd.sh", "pinas_iphone_backup.sh",
        "pinas_iphone_verkennen.sh", "test_suite.py",
        "NAS_Map_Beheer.pyw", "NAS_Map_Beheer.bat", "download_links.ini",
    ):
        _copy(os.path.join(NAS_ROOT, "Gedeeld"), gedeeld_doel, bestand)

    # Gedeeld\ScriptRunner\pi_script_draaien.bat ingetrokken (31 juli 2026,
    # Frans: niet meer los gebruikt - Addons Beheer dekt dit nu)

    # -- Beheer_install.bat in root van ZIP --------------------------------
    beheer_install_bron = os.path.join(NAS_ROOT, "Beheer", "Beheer_install.bat")
    if os.path.exists(beheer_install_bron):
        shutil.copy2(beheer_install_bron, os.path.join(werkmap, "Beheer_install.bat"))
        print("   OK: Beheer_install.bat")

    # -- Installatie (installers zelf, zodat dit ook zonder internet werkt) --
    installatie_bron = os.path.join(NAS_ROOT, "Installatie")
    if os.path.isdir(installatie_bron):
        installatie_doel = os.path.join(werkmap, "Installatie")
        shutil.copytree(installatie_bron, installatie_doel, dirs_exist_ok=True)
        print("   OK: Installatie\\ (installers - maakt het pakket groter, maar werkt dan ook zonder internet)")
    else:
        print("   --: Installatie niet gevonden")

    # -- INSTALL_TYPE.txt ------------------------------------------------------
    with open(os.path.join(werkmap, "INSTALL_TYPE.txt"), "w", encoding="utf-8") as f:
        f.write("minimaal\n")

    # -- Wachtwoord ophalen voor anonimisering ---------------------------------
    ww_cache = os.path.join(NAS_ROOT, "Logs", ".ww_samba.dat")
    huidig_ww = ""
    if os.path.exists(ww_cache):
        with open(ww_cache, "r", encoding="utf-8") as f:
            huidig_ww = f.readline().strip()

    # -- Anonimiseren ------------------------------------------------------------
    print()
    print("  [Stap 2] Anonimiseren...")
    _anonimiseer(werkmap, huidig_ww)

    # -- ZIP aanmaken --------------------------------------------------------------
    print()
    print("  [Stap 3] ZIP aanmaken...")
    if os.path.exists(zip_pad):
        os.remove(zip_pad)
    with zipfile.ZipFile(zip_pad, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpad, _dirs, bestanden in os.walk(werkmap):
            for naam in bestanden:
                volledig = os.path.join(dirpad, naam)
                relatief = os.path.relpath(volledig, werkmap)
                zf.write(volledig, relatief)

    if os.path.exists(zip_pad):
        print(f"   OK: {zip_pad}")
    else:
        print("   FOUT: ZIP aanmaken mislukt")
        input("Druk op Enter om af te sluiten...")
        return 1

    # -- Opruimen -----------------------------------------------------------------
    shutil.rmtree(werkmap, ignore_errors=True)

    print()
    print("  " + "=" * 62)
    print("  Starter Kit klaar!")
    print(f"  {zip_pad}")
    print()
    print("  Inhoud: Beheer, Addons, Publicatie, Sync, ArchiefBackup, PiServer, Gedeeld, Installatie")
    print("  Geanonimiseerd: IP, wachtwoord en ZeroTier netwerk-ID vervangen")
    print("  Installatie: uitpakken + Beheer_install.bat uitvoeren")
    print("  " + "=" * 62)
    print()
    input("Druk op Enter om af te sluiten...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
