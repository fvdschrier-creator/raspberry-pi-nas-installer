# Pi NAS Installer Simulator

Test de NAS installer op je Windows PC — geen Raspberry Pi nodig.

## Eenmalig installeren

1. Download **Docker Desktop** via https://www.docker.com/products/docker-desktop
2. Installeer Docker Desktop — klik door de wizard
3. **Herstart je PC** na installatie
4. Start Docker Desktop en wacht tot het groen is

## Simulator starten

1. Kopieer alle bestanden uit deze map naar één map op je PC
2. Dubbelklik **start_simulator.bat**
3. Eerste keer: even wachten (~3 minuten) terwijl de omgeving gebouwd wordt
4. VNC Viewer opent automatisch met de installer
5. **Wachtwoord:** `raspberry`

## Wat werkt in de simulator

✅ Volledige GUI installer met alle menu's  
✅ Welkomscherm met status  
✅ Schijf beheer (nep schijven van 100MB en 200MB)  
✅ Beheer pagina  
✅ Cockpit en FileBrowser pagina's  
✅ CLI installer  

## Wat niet werkt

❌ Echte software installeren (Samba/Nextcloud)  
❌ Echte schijven koppelen  
❌ Smart plug / Seagate aansturing  
❌ Netwerk instellingen  

## Simulator stoppen

Druk **Enter** in het zwarte venster — de simulator stopt automatisch.

## Bestanden die je nodig hebt

Zet deze bestanden in dezelfde map als start_simulator.bat:
- `Dockerfile`
- `start.sh`
- `sim_setup.sh`
- `nas_installer.py`
- `nas_installer_cli.py`
- `pi_welkom.sh`
- `smart_plug.py`
