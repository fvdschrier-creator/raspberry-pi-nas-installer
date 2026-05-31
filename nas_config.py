#!/usr/bin/env python3
# Raspberry Pi NAS Installer v1.0.0
"""
Pi NAS Configuratie Export/Import
Slaat configuratie op naar 4 locaties en kan herstellen na herinstallatie.
Start: sudo python3 /home/pi/nas_config.py
Of via NAS-installer optie
"""
import os, sys, json, subprocess, datetime, shutil

# ── Kleuren ──────────────────────────────────────────────────────────────────
R="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"
CYAN="\033[96m"; GREEN="\033[92m"; YELLOW="\033[93m"
RED="\033[91m"; BLUE="\033[94m"; WHITE="\033[97m"

CONFIG_FILE = "nas_config_export.json"
EXPORT_LOCS = [
    "/mnt/opslag",
    "/mnt/backup",
    "/boot/firmware",
    "/home/pi",
]

def sh(cmd):
    try: return subprocess.run(cmd,shell=True,capture_output=True,text=True).stdout.strip()
    except: return ""

def clr():   os.system("clear")
def ok(m):   print(f"  {GREEN}✔  {m}{R}")
def warn(m): print(f"  {YELLOW}⚠  {m}{R}")
def err(m):  print(f"  {RED}✗  {m}{R}")
def info(m): print(f"  {CYAN}ℹ  {m}{R}")
def dim(m):  print(f"  {DIM}{m}{R}")

def hdr(title, color=CYAN):
    w=60
    print(f"\n{color}{BOLD}{'═'*w}{R}")
    print(f"{color}{BOLD}  {title}{R}")
    print(f"{color}{BOLD}{'═'*w}{R}\n")

def ask_yn(prompt, default="j"):
    opts="[J/n]" if default.lower()=="j" else "[j/N]"
    try:
        val=input(f"  {WHITE}{prompt} {opts}: {R}").strip().lower()
        if not val: return default.lower()=="j"
        return val in ("j","ja","y","yes")
    except KeyboardInterrupt:
        print(); return False

def pause():
    input(f"\n  {DIM}Druk Enter om door te gaan...{R}")

# ── Export functies ───────────────────────────────────────────────────────────
def export_samba():
    """Exporteer Samba-configuratie."""
    shares={}
    conf=sh("cat /etc/samba/smb.conf 2>/dev/null")
    cur=None
    share_data={}
    for line in conf.splitlines():
        line=line.strip()
        if line.startswith("[") and line not in ("[global]","[homes]","[printers]"):
            cur=line[1:-1]; share_data[cur]={}
        elif cur and "=" in line:
            key,val=line.split("=",1)
            share_data[cur][key.strip()]=val.strip()
    # Global sectie
    global_data={}
    in_global=False
    for line in conf.splitlines():
        line=line.strip()
        if line=="[global]": in_global=True; continue
        elif line.startswith("[") and in_global: break
        elif in_global and "=" in line:
            key,val=line.split("=",1)
            global_data[key.strip()]=val.strip()
    return {"shares":share_data,"global":global_data,"raw":conf}

def export_fstab():
    """Exporteer fstab NAS-regels."""
    lines=[]
    for line in sh("cat /etc/fstab").splitlines():
        if "/mnt/" in line and not line.strip().startswith("#"):
            lines.append(line.strip())
    return lines

def export_mounts():
    """Exporteer gemounte NAS-schijven."""
    mounts=[]
    for line in sh("lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT -rn").splitlines():
        p=line.split()
        if len(p)>=4 and "/mnt/" in p[3]:
            uuid=sh(f"sudo blkid -s UUID -o value /dev/{p[0]}")
            mounts.append({
                "device": f"/dev/{p[0]}",
                "mountpoint": p[3],
                "fstype": p[2] if len(p)>2 else "ext4",
                "size": p[1],
                "uuid": uuid,
            })
    return mounts

def export_software():
    """Exporteer geïnstalleerde NAS-software."""
    return {
        "samba": sh("dpkg -l samba 2>/dev/null | grep -c '^ii'").strip()=="1",
        "cockpit": sh("dpkg -l cockpit 2>/dev/null | grep -c '^ii'").strip()=="1",
        "nextcloud": os.path.exists("/var/www/html/nextcloud"),
        "filebrowser": bool(sh("which filebrowser 2>/dev/null")),
        "desktop": sh("dpkg -l lxde-core 2>/dev/null | grep -c '^ii'").strip()=="1",
    }

def export_system():
    """Exporteer systeem-instellingen."""
    return {
        "hostname": sh("hostname"),
        "ip": sh("hostname -I").split()[0] if sh("hostname -I") else "",
        "ssh_enabled": sh("sudo systemctl is-enabled ssh 2>/dev/null").strip()=="enabled",
        "pi_user": sh("logname 2>/dev/null || echo pi") or "pi",
    }

def export_nextcloud():
    """Exporteer Nextcloud-configuratie."""
    if not os.path.exists("/var/www/html/nextcloud"):
        return {}
    config=sh("sudo -u www-data php /var/www/html/nextcloud/occ config:system:get trusted_domains 2>/dev/null")
    data_dir=sh("sudo -u www-data php /var/www/html/nextcloud/occ config:system:get datadirectory 2>/dev/null")
    return {
        "installed": True,
        "data_dir": data_dir,
        "trusted_domains": config,
    }

def export_filebrowser():
    """Exporteer FileBrowser-configuratie."""
    svc=sh("cat /etc/systemd/system/filebrowser.service 2>/dev/null")
    rootdir=""
    port="8080"
    for line in svc.splitlines():
        if "ExecStart" in line and "-r " in line:
            import re
            m=re.search(r'-r\s+(\S+)',line)
            if m: rootdir=m.group(1)
        if "-p " in line:
            import re
            m=re.search(r'-p\s+(\d+)',line)
            if m: port=m.group(1)
    return {
        "installed": bool(sh("which filebrowser 2>/dev/null")),
        "service_enabled": sh("sudo systemctl is-enabled filebrowser 2>/dev/null") in ("enabled","static"),
        "rootdir": rootdir or "/mnt",
        "port": port,
    }

# ── Export ────────────────────────────────────────────────────────────────────
def do_export():
    clr(); hdr("Configuratie exporteren", GREEN)
    info("Configuratie wordt verzameld...")
    print()

    config = {
        "versie": "1.0",
        "datum": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "systeem": export_system(),
        "software": export_software(),
        "samba": export_samba(),
        "fstab": export_fstab(),
        "mounts": export_mounts(),
        "nextcloud": export_nextcloud(),
        "filebrowser": export_filebrowser(),
    }

    ok(f"Hostname: {config['systeem']['hostname']}")
    ok(f"IP: {config['systeem']['ip']}")
    sw=config["software"]
    installed=[k for k,v in sw.items() if v]
    ok(f"Software: {', '.join(installed) if installed else 'niets'}")
    ok(f"Schijven: {len(config['mounts'])} NAS-schijf(ven)")
    ok(f"Samba-shares: {len(config['samba']['shares'])}")
    print()

    # Opslaan naar alle locaties
    saved=0; failed=[]
    for loc in EXPORT_LOCS:
        if os.path.exists(loc):
            path=os.path.join(loc, CONFIG_FILE)
            try:
                with open(path,"w") as f:
                    json.dump(config,f,indent=2)
                ok(f"Opgeslagen: {path}")
                saved+=1
            except Exception as e:
                warn(f"Mislukt: {path} ({e})")
                failed.append(loc)
        else:
            dim(f"Map niet beschikbaar: {loc}")

    print()
    if saved>0:
        ok(f"Export geslaagd — {saved} kopie(en) opgeslagen.")
        info("Gebruik import om te herstellen na herinstallatie of Pi-wissel.")
    else:
        err("Geen enkele locatie beschikbaar — export mislukt!")
    pause()
    return config

# ── Import ────────────────────────────────────────────────────────────────────
def find_config():
    """Zoek de meest recente config op alle locaties."""
    found=[]
    for loc in EXPORT_LOCS:
        path=os.path.join(loc, CONFIG_FILE)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    cfg=json.load(f)
                found.append((path, cfg))
            except: pass
    if not found: return None, None
    # Meest recente
    found.sort(key=lambda x: x[1].get("datum",""), reverse=True)
    return found[0]

def do_import():
    clr(); hdr("Configuratie importeren", CYAN)

    path, config = find_config()
    if not config:
        err("Geen configuratie gevonden op:")
        for loc in EXPORT_LOCS:
            dim(f"  {os.path.join(loc, CONFIG_FILE)}")
        warn("Maak eerst een export via optie 1.")
        pause(); return

    ok(f"Gevonden: {path}")
    info(f"Datum export: {config.get('datum','?')}")
    info(f"Hostname: {config['systeem']['hostname']}")
    info(f"IP: {config['systeem']['ip']}")
    sw=config["software"]; installed=[k for k,v in sw.items() if v]
    info(f"Software: {', '.join(installed) if installed else 'niets'}")
    info(f"Schijven: {len(config['mounts'])} NAS-schijf(ven)")
    print()

    print(f"  {YELLOW}Wat wordt hersteld:{R}")
    print(f"  • fstab-regels voor NAS-schijven")
    print(f"  • Samba-shares (als Samba geïnstalleerd is)")
    print(f"  • FileBrowser-service (als geïnstalleerd)")
    print()
    warn("Software (Samba/Nextcloud) wordt NIET herinstalleerd — gebruik de installer daarvoor.")
    print()
    if not ask_yn("Doorgaan met import?","j"):
        info("Geannuleerd."); pause(); return

    print()
    # fstab herstellen
    hdr2("fstab herstellen")
    current_fstab=sh("cat /etc/fstab")
    added=0
    for entry in config.get("fstab",[]):
        uuid=entry.split()[0] if entry.split() else ""
        if uuid and uuid not in current_fstab:
            subprocess.run(f"echo '{entry}' | sudo tee -a /etc/fstab",shell=True)
            ok(f"Toegevoegd: {entry[:60]}")
            added+=1
        else:
            dim(f"Al aanwezig: {entry[:60]}")
    if added>0:
        subprocess.run("sudo mount -a",shell=True)
        ok("Schijven gemount")

    # Samba-shares herstellen
    hdr2("Samba-shares herstellen")
    samba_ok=sh("dpkg -l samba 2>/dev/null | grep -c '^ii'").strip()=="1"
    if samba_ok:
        conf=sh("cat /etc/samba/smb.conf")
        shares_added=0
        for share_name, share_data in config.get("samba",{}).get("shares",{}).items():
            if f"[{share_name}]" not in conf:
                blk=f"\n[{share_name}]\n"
                for k,v in share_data.items():
                    blk+=f"   {k} = {v}\n"
                subprocess.run(f"printf '{blk}' | sudo tee -a /etc/samba/smb.conf>/dev/null",shell=True)
                ok(f"Share hersteld: [{share_name}]")
                shares_added+=1
            else:
                dim(f"Share al aanwezig: [{share_name}]")
        if shares_added>0:
            subprocess.run("sudo systemctl restart smbd",shell=True)
            ok("Samba herstart")
    else:
        warn("Samba niet geïnstalleerd — shares overgeslagen")

    # FileBrowser herstellen
    hdr2("FileBrowser herstellen")
    fb_cfg=config.get("filebrowser",{})
    if fb_cfg.get("installed") and sh("which filebrowser 2>/dev/null"):
        if fb_cfg.get("service_enabled"):
            svc=f"""[Unit]
Description=FileBrowser NAS
After=network.target
[Service]
ExecStart=/usr/local/bin/filebrowser -r {fb_cfg.get('rootdir','/mnt')} -a 0.0.0.0 -p {fb_cfg.get('port','8080')} -d /home/pi/filebrowser.db
Restart=always
User=pi
[Install]
WantedBy=multi-user.target
"""
            with open("/tmp/filebrowser.service","w") as f: f.write(svc)
            subprocess.run("sudo cp /tmp/filebrowser.service /etc/systemd/system/filebrowser.service",shell=True)
            subprocess.run("sudo systemctl daemon-reload && sudo systemctl enable filebrowser",shell=True)
            ok("FileBrowser service hersteld")
    else:
        dim("FileBrowser niet beschikbaar — overgeslagen")

    # Alle kopieën synchroniseren
    hdr2("Kopieën synchroniseren")
    sync_config(config)

    print()
    ok("Import voltooid!")
    info("Herstart de Pi om alle wijzigingen toe te passen: sudo reboot")
    pause()

def hdr2(title):
    print(f"\n  {BLUE}{BOLD}── {title} ──{R}\n")

# ── Synchroniseren ────────────────────────────────────────────────────────────
def do_sync():
    """Synchroniseer alle kopieën — herstel ontbrekende."""
    clr(); hdr("Kopieën synchroniseren", BLUE)
    path, config = find_config()
    if not config:
        warn("Geen configuratie gevonden. Maak eerst een export.")
        pause(); return
    ok(f"Bron gevonden: {path}")
    ok(f"Datum: {config.get('datum','?')}")
    print()
    sync_config(config)
    pause()

def sync_config(config):
    """Sla config op naar alle beschikbare locaties."""
    synced=0
    for loc in EXPORT_LOCS:
        if os.path.exists(loc):
            path=os.path.join(loc, CONFIG_FILE)
            try:
                with open(path,"w") as f:
                    json.dump(config,f,indent=2)
                ok(f"Gesynchroniseerd: {path}")
                synced+=1
            except Exception as e:
                warn(f"Mislukt: {path} ({e})")
        else:
            dim(f"Niet beschikbaar: {loc}")
    return synced

# ── Status ────────────────────────────────────────────────────────────────────
def do_status():
    clr(); hdr("Configuratie status", BLUE)

    path, config = find_config()
    if config:
        ok(f"Meest recente export: {config.get('datum','?')}")
        ok(f"Gevonden op: {path}")
        print()
        # Controleer alle locaties
        print(f"  {BLUE}Kopieën:{R}")
        for loc in EXPORT_LOCS:
            p=os.path.join(loc, CONFIG_FILE)
            if os.path.exists(p):
                try:
                    with open(p) as f: c=json.load(f)
                    datum=c.get("datum","?")
                    # Vergelijk met meest recente
                    if datum==config.get("datum"):
                        print(f"  {GREEN}✔{R}  {p}  ({datum})")
                    else:
                        print(f"  {YELLOW}⚠{R}  {p}  ({datum}) — VEROUDERD")
                except:
                    print(f"  {RED}✗{R}  {p}  — BESCHADIGD")
            else:
                if os.path.exists(loc):
                    print(f"  {YELLOW}✗{R}  {p}  — ONTBREEKT")
                else:
                    print(f"  {DIM}─{R}  {p}  — map niet beschikbaar")
    else:
        warn("Geen configuratie gevonden — nog geen export gemaakt.")

    pause()

# ── Hoofdmenu ─────────────────────────────────────────────────────────────────
def config_menu():
    while True:
        clr(); hdr("Configuratie export/import", CYAN)

        path, config = find_config()
        if config:
            print(f"  {GREEN}Laatste export: {config.get('datum','?')}{R}")
        else:
            print(f"  {YELLOW}Nog geen export gemaakt{R}")
        print()

        print(f"  {CYAN}{BOLD}1{R}  Exporteren — sla huidige configuratie op (4 locaties)")
        print(f"     {DIM}Samba, schijven, FileBrowser, Nextcloud, software{R}\n")
        print(f"  {CYAN}{BOLD}2{R}  Importeren — herstel configuratie na herinstallatie of Pi-wissel")
        print(f"     {DIM}Herstelt fstab, Samba-shares, FileBrowser-service{R}\n")
        print(f"  {CYAN}{BOLD}3{R}  Synchroniseren — herstel ontbrekende of verouderde kopieën")
        print(f"     {DIM}Zorgt dat alle 4 locaties up-to-date zijn{R}\n")
        print(f"  {CYAN}{BOLD}4{R}  Status — bekijk alle kopieën en hun leeftijd\n")
        print(f"  {CYAN}{BOLD}5{R}  ← Terug\n")

        try: keuze=input(f"  {WHITE}Keuze (1-5): {R}").strip()
        except KeyboardInterrupt: return

        if   keuze=="1": do_export()
        elif keuze=="2": do_import()
        elif keuze=="3": do_sync()
        elif keuze=="4": do_status()
        elif keuze in ("5",""): return


if __name__=="__main__":
    if os.geteuid()!=0:
        print(f"\n{RED}⚠  Start met: sudo python3 /home/pi/nas_config.py{R}\n")
        sys.exit(1)
    config_menu()
