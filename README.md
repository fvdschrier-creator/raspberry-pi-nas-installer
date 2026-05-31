# Raspberry Pi NAS Installer v1.0.0

Een complete NAS-server oplossing voor de Raspberry Pi 4/5 met installer, 
beheer en documentatie. Geschikt voor thuisgebruik.

## Wat is dit?

Dit pakket zet een Raspberry Pi om tot een volwaardige NAS (Network Attached Storage) 
server met:

- **Samba** — netwerkschijf voor Windows, Mac, iPhone, Android
- **Nextcloud** — eigen cloud met automatische foto-backup
- **FileBrowser** — webbeheer voor bestanden
- **Cockpit** — webbeheer voor de Pi zelf
- **CLI-installer** — tekstmenu via SSH
- **GUI-installer** — grafische interface via VNC
- **Philips Hue / TP-Link Tapo** — slimme stekker voor Seagate aan/uitzetten

## Benodigdheden

- Raspberry Pi 4 of 5 (minimaal 2GB RAM, aanbevolen 4GB/8GB)
- Raspberry Pi OS Lite (64-bit)
- SD-kaart 16GB of groter
- Externe SSD of HDD
- Windows-pc voor installatie

## Werkwijze Windows batch-scripts

| Script | Wanneer gebruiken |
|---|---|
| `initieel_setup.bat` | **Eenmalig** bij eerste installatie of nieuwe bestanden van Claude |
| `kopieer_naar_nas.bat` | Bij updates — kopieert nieuwere versies naar NAS-map en Pi |
| `nas_upload.bat` | Alleen uploaden naar Pi zonder kopieer stap |

**Eerste keer:**
1. Download alle bestanden van Claude naar Downloads
2. Dubbelklik `initieel_setup.bat` → alles naar NAS-map
3. Dubbelklik `nas_upload.bat` → alles naar Pi

**Bij updates:**
1. Download nieuwe bestanden van Claude naar Downloads
2. Dubbelklik `kopieer_naar_nas.bat` → nieuwere versies naar NAS-map + Pi

> **Let op:** Nieuwe bestanden van Claude eerst toevoegen via `initieel_setup.bat`.
> `kopieer_naar_nas.bat` werkt alleen bestanden bij die al in de NAS-map staan.

## Installatie

1. Flash Raspberry Pi OS Lite via [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
2. Stel WiFi, gebruikersnaam en wachtwoord in via Imager
3. Kopieer alle bestanden naar de SD-kaart boot-partitie
4. Start de Pi op — het installatiemenu verschijnt automatisch
5. Kies optie 1 "Volledige initiële setup"

## Bestanden

| Bestand | Functie |
|---|---|
| `nas_installer_cli.py` | CLI-installer via SSH |
| `nas_installer.py` | GUI-installer via VNC |
| `nas_backup.py` | Backup systeem |
| `nas_config.py` | Configuratie export/import |
| `smart_plug.py` | Slimme stekker controller (Hue/Tapo) |
| `pi_welkom.sh` | Welkomstmenu bij SSH-login |
| `install.sh` | Eerste-start installer |
| `nas_upload.bat` | Upload scripts naar Pi (Windows) |
| `kopieer_naar_nas.bat` | Kopieer downloads naar NAS-map (Windows) |
| `kopieer_helper.ps1` | PowerShell helper voor kopieer bat |
| `nas_diagnose.bat` | Diagnose uitvoeren (Windows) |
| `nas_diagnose.sh` | Diagnose script (Pi) |
| `install_vnc_viewer.bat` | VNC Viewer installeren (Windows) |
| `smart_plug_config.json` | Smart plug configuratie (aanpassen!) |
| `raspberry_pi_nas_volledig.pdf` | Volledige handleiding |

## Snelstart

SSH verbinden:
```
ssh pi@[IP-ADRES]
```

NAS installer starten:
```
nas
```

## Smart plug (optioneel)

Sluit de Seagate aan op een Philips Hue Smart plug of TP-Link Tapo P100/P110.
Configureer via: NAS installer → Beheer → Smart plug instellen.

Configuratie opslaan in `smart_plug_config.json`:
```json
{
    "type": "hue",
    "hue": {
        "bridge_ip": "192.168.1.x",
        "api_key": "JOUW_API_KEY",
        "plug_id": "7"
    }
}
```

## Licentie

MIT License — vrij te gebruiken, aanpassen en verspreiden.
Vermeld de oorsprong als je het deelt.

## Documentatie

Zie `raspberry_pi_nas_volledig.pdf` voor de volledige handleiding.
