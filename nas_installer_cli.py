#!/usr/bin/env python3
# Raspberry Pi NAS Installer v1.0.0
NAS_VERSION = "1.0.0"
"""
Raspberry Pi NAS Installer — Tekstversie (CLI)
Werkt zonder scherm of desktop, via SSH of direct in terminal.
Start: sudo python3 nas_installer_cli.py
"""
import subprocess, os, sys, time, re

# ── ANSI kleuren ──────────────────────────────────────────────────────────────
R="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"
CYAN="\033[96m"; GREEN="\033[92m"; YELLOW="\033[93m"
RED="\033[91m"; BLUE="\033[94m"; MAGENTA="\033[95m"; WHITE="\033[97m"

def clr():
    os.system("clear")

def hdr(title, color=CYAN):
    w=60
    print(f"\n{color}{BOLD}{'═'*w}{R}")
    print(f"{color}{BOLD}  {title}{R}")
    print(f"{color}{BOLD}{'═'*w}{R}\n")

def subhdr(title):
    print(f"\n{BLUE}{BOLD}── {title} ──{R}\n")

def ok(msg):   print(f"  {GREEN}✔  {msg}{R}")
def warn(msg): print(f"  {YELLOW}⚠  {msg}{R}")
def err(msg):  print(f"  {RED}✗  {msg}{R}")
def info(msg): print(f"  {CYAN}ℹ  {msg}{R}")
def dim(msg):  print(f"  {DIM}{msg}{R}")

def sh(cmd):
    try:
        r=subprocess.run(cmd,shell=True,capture_output=True,text=True)
        return r.stdout.strip()
    except: return ""

def sh_rc(cmd):
    try: return subprocess.run(cmd,shell=True).returncode
    except: return 1

def run(cmd, desc=""):
    if desc: print(f"\n  {CYAN}▶  {desc}...{R}")
    proc=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT,text=True)
    for line in proc.stdout:
        s=line.rstrip()
        if s: print(f"     {DIM}{s}{R}")
    proc.wait()
    return proc.returncode==0

def ask(prompt, default="", allow_empty=False):
    d=f" [{default}]" if default else ""
    try:
        val=input(f"  {WHITE}{prompt}{d}: {R}").strip()
        return val if val else default
    except KeyboardInterrupt:
        print()
        return None  # None = terug/annuleren

def ask_pw(prompt):
    import getpass
    try:
        return getpass.getpass(f"  {WHITE}{prompt}: {R}").strip()
    except KeyboardInterrupt:
        print("\n"); main_menu(); return ""

def ask_yn(prompt, default="j"):
    opts="[J/n]" if default.lower()=="j" else "[j/N]"
    try:
        val=input(f"  {WHITE}{prompt} {opts}: {R}").strip().lower()
        if not val: return default.lower()=="j"
        return val in ("j","ja","y","yes")
    except KeyboardInterrupt:
        print()
        return False

def ask_menu(opties):
    """Toon genummerd menu, geef index terug (0-based). -1 = terug/annuleren."""
    for i,o in enumerate(opties,1):
        print(f"  {CYAN}{BOLD}{i}{R}  {o}")
    print(f"  {DIM}(Ctrl+C = terug){R}")
    print()
    while True:
        try:
            val=input(f"  {WHITE}Keuze (1-{len(opties)}): {R}").strip()
            if val.isdigit() and 1<=int(val)<=len(opties):
                return int(val)-1
            if val.lower() in ("q","terug","0",""):
                return -1
        except KeyboardInterrupt:
            print()
            return -1

def get_ip():
    for ip in sh("hostname -I").split():
        if ip.startswith(("192.","10.","172.")): return ip
    ips=sh("hostname -I").split()
    return ips[0] if ips else "niet verbonden"

def is_connected():
    return "connected" in sh("nmcli -t -f STATE general 2>/dev/null").lower()

def ssh_enabled():
    return sh("sudo systemctl is-enabled ssh 2>/dev/null").strip()=="enabled"

def get_nas_mounts():
    result=[]
    for line in sh("lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT -rn").splitlines():
        p=line.split()
        if len(p)>=4 and "/mnt/" in p[3]:
            result.append((f"/dev/{p[0]}",p[3],p[2] if len(p)>2 else "?",p[1]))
    return result

def get_samba_shares():
    shares={}
    cur=None
    for line in sh("cat /etc/samba/smb.conf 2>/dev/null").splitlines():
        line=line.strip().replace("\r","")
        if not line or line.startswith("#"): continue
        if line.startswith("[") and line.endswith("]"):
            name=line[1:-1]
            if name not in ("global","homes","printers"):
                cur=name
            else:
                cur=None
        elif cur and "=" in line and line.lower().lstrip().startswith("path"):
            shares[cur]=line.split("=",1)[1].strip()
    return shares

def suggest_device():
    used={m[0] for m in get_nas_mounts()}
    for c in "abcdefgh":
        d=f"/dev/sd{c}"
        if d not in used and sh(f"test -b {d} && echo yes")=="yes": return d
    return "/dev/sda"

def suggest_mount(dev=None):
    existing={m[1] for m in get_nas_mounts()}
    if dev:
        size_str=sh(f"lsblk -dn -o SIZE {dev} 2>/dev/null").strip()
        if size_str and ('T' in size_str or
            ('G' in size_str and float(size_str.replace('G','').strip() or '0') >= 500)):
            for s in ["",2,3]:
                mp=f"/mnt/backup{'' if not s else s}"
                if mp not in existing: return mp
        else:
            for s in ["",2,3,4,5]:
                mp=f"/mnt/opslag{'' if not s else s}"
                if mp not in existing: return mp
    for s in ["",2,3,4,5]:
        mp=f"/mnt/opslag{'' if not s else s}"
        if mp not in existing: return mp
    return "/mnt/opslag2"

def suggest_share(dev=None):
    if dev:
        size_str=sh(f"lsblk -dn -o SIZE {dev} 2>/dev/null").strip()
        if size_str and ('T' in size_str or
            ('G' in size_str and float(size_str.replace('G','').strip() or '0') >= 500)):
            return "Backup"
    return "Opslag"

def fix_dev(dev):
    """Zorg dat apparaatnaam altijd /dev/xxx is."""
    dev=dev.strip()
    if dev and not dev.startswith("/"):
        dev="/dev/"+dev
    return dev

def fs_format(dev,fs):
    if fs=="exfat":
        return [("exfatprogs installeren","sudo apt-get install -y exfatprogs"),
                ("Formatteren als exFAT",f"sudo wipefs -a {dev} && sudo mkfs.exfat {dev}")]
    elif fs=="ntfs":
        return [("ntfs-3g installeren","sudo apt-get install -y ntfs-3g"),
                ("Formatteren als NTFS",f"sudo wipefs -a {dev} && sudo mkfs.ntfs -f {dev}")]
    return [("Partitietabel wissen", f"sudo wipefs -a {dev}"),
            ("Formatteren als ext4", f"sudo mkfs.ext4 -F {dev}"),
            ("Kernel bijwerken",     f"sudo partprobe {dev} 2>/dev/null; sudo udevadm settle")]

def fs_fstab(uuid,mp,fs):
    if fs=="exfat":
        return f"UUID={uuid}  {mp}  exfat  defaults,nofail,uid=1000,gid=1000,umask=0022  0  0"
    elif fs=="ntfs":
        return f"UUID={uuid}  {mp}  ntfs-3g  defaults,nofail,uid=1000,gid=1000,umask=0022  0  0"
    return f"UUID={uuid}  {mp}  ext4  defaults,nofail  0  2"

def fix_rechten(mp=None, user=None):
    """Stel rechten in op één of alle NAS-mountpunten."""
    if user is None:
        user = sh("logname 2>/dev/null || echo pi") or "pi"
    mounts = [(mp,)] if mp else [(m[1],) for m in get_nas_mounts()]
    fixed = 0
    for (path,) in mounts:
        if os.path.exists(path):
            subprocess.run(
                f"sudo chown -R {user}:{user} {path} && sudo chmod -R 775 {path}",
                shell=True)
            fixed += 1
    return fixed

def check_rechten():
    """Geeft lijst van mountpunten waar schrijven niet mogelijk is."""
    problemen = []
    for dev, mp, fs, sz in get_nas_mounts():
        testfile = f"{mp}/.write_test_{os.getpid()}"
        try:
            r = subprocess.run(f"sudo touch {testfile} && sudo rm {testfile}",
                               shell=True, capture_output=True)
            if r.returncode != 0:
                problemen.append(mp)
        except:
            problemen.append(mp)
    return problemen
    print(f"\n  Bestandssysteem kiezen:")
    for i,( val,desc) in enumerate([
        ("ext4",  "ext4   — Beste keuze voor NAS (niet direct op Windows via USB)"),
        ("exfat", "exFAT  — Leesbaar op Linux + Windows/Mac, goed voor >4GB bestanden"),
        ("ntfs",  "NTFS   — Windows-native, ook op Linux leesbaar"),
    ],1):
        print(f"  {CYAN}{i}{R}  {desc}")
    print()
    keuze=ask("Keuze","1")
    return {"1":"ext4","2":"exfat","3":"ntfs"}.get(keuze,"ext4")

def pause():
    input(f"\n  {DIM}Druk Enter om door te gaan...{R}")

# ════════════════════════════════════════════════════════════════════════════
# STAP: NETWERK
# ════════════════════════════════════════════════════════════════════════════
def stap_netwerk():
    clr(); hdr("Netwerk — WiFi of UTP")
    ip=get_ip(); conn=is_connected()
    if conn:
        ok(f"Al verbonden — IP: {ip}")
        if not ask_yn("Toch een andere WiFi instellen?","n"): return
    print()
    info("UTP-kabel: sluit aan op router/switch — automatisch IP, geen actie nodig.")
    print()
    if ask_yn("WiFi instellen?","j"):
        print()
        subhdr("Beschikbare netwerken")
        os.system("sudo nmcli dev wifi list 2>/dev/null | head -15")
        print()
        ssid=ask("WiFi netwerknaam (SSID)")
        if not ssid: return
        pwd=ask_pw("WiFi wachtwoord (leeg = open netwerk)")
        cmd=f'sudo nmcli dev wifi connect "{ssid}"'
        if pwd: cmd+=f' password "{pwd}"'
        print()
        run(cmd+" 2>&1","Verbinden")
        time.sleep(2)
        if is_connected(): ok(f"Verbonden! IP: {get_ip()}")
        else: warn("Verbinding mislukt — controleer SSID en wachtwoord")
    pause()

# ════════════════════════════════════════════════════════════════════════════
# STAP: SSH
# ════════════════════════════════════════════════════════════════════════════
def stap_ssh():
    clr(); hdr("SSH instellen")
    ip = get_ip()

    # SSH service status
    if ssh_enabled():
        ok(f"SSH is ingeschakeld")
        info(f"Verbind via: ssh pi@{ip}")
    else:
        warn("SSH is uitgeschakeld")
        if ask_yn("SSH inschakelen?","j"):
            sh("sudo systemctl enable ssh")
            sh("sudo systemctl start ssh")
            ok(f"SSH ingeschakeld — ssh pi@{ip}")

    print()
    subhdr("SSH-sleutel (geen wachtwoord meer nodig)")

    # Controleer of er al een sleutel is
    keys = sh("cat /home/pi/.ssh/authorized_keys 2>/dev/null | wc -l")
    if keys and int(keys) > 0:
        ok(f"{keys} SSH-sleutel(s) aanwezig — wachtwoordloos inloggen werkt")
    else:
        warn("Nog geen SSH-sleutel ingesteld")
        info("Voer dit eenmalig uit op je Windows-pc (PowerShell):")
        print()
        print(f"  {CYAN}ssh-keygen -t ed25519{R}")
        print(f"  {DIM}(drie keer Enter drukken){R}")
        print()
        print(f"  {CYAN}type C:\\Users\\JOUNAAM\\.ssh\\id_ed25519.pub | ssh pi@{ip} \"mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys\"{R}")
        print()
        info("Vervang JOUNAAM door je Windows-gebruikersnaam")

    print()
    subhdr("Wachtwoordlogin")

    # Check of wachtwoordlogin nog aan staat
    pw_auth = sh("sudo grep -E '^PasswordAuthentication' /etc/ssh/sshd_config 2>/dev/null")
    if "no" in pw_auth.lower():
        ok("Wachtwoordlogin is uitgeschakeld — alleen SSH-sleutel werkt")
    else:
        info("Wachtwoordlogin is ingeschakeld (standaard)")
        warn("Tip: schakel wachtwoordlogin uit nadat je SSH-sleutel werkt.")
        warn("Dan kan niemand via wachtwoord inloggen, alleen via jouw sleutel.")
        print()
        if ask_yn("Wachtwoordlogin uitschakelen?","n"):
            # Controleer eerst of er een sleutel is
            if not keys or int(keys) == 0:
                err("Geen SSH-sleutel aanwezig — stel eerst een sleutel in!")
                err("Anders kun je niet meer inloggen na uitschakelen!")
            else:
                sh("sudo sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config")
                sh("sudo systemctl restart ssh")
                ok("Wachtwoordlogin uitgeschakeld — alleen SSH-sleutel werkt")
                warn("Bewaar je SSH-sleutel goed — zonder sleutel geen toegang meer!")
    pause()

# ════════════════════════════════════════════════════════════════════════════
# STAP: SYSTEEM BIJWERKEN
# ════════════════════════════════════════════════════════════════════════════
def stap_update():
    clr(); hdr("Systeem bijwerken")
    info("Dit kan enkele minuten duren.")
    if ask_yn("Bijwerken?","j"):
        run("sudo apt-get update -y","apt update")
        run("sudo apt-get upgrade -y","apt upgrade")
        ok("Systeem bijgewerkt")
    else:
        info("Overgeslagen")
    pause()

# ════════════════════════════════════════════════════════════════════════════
# SCHIJF: OVERZICHT
# ════════════════════════════════════════════════════════════════════════════
def schijf_overzicht():
    clr(); hdr("Schijf overzicht")
    subhdr("Alle schijven (lsblk)")
    os.system("lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT")
    print()
    subhdr("Schijfgebruik (df -h)")
    os.system("df -h | grep -E 'Filesystem|mnt|root'")
    print()
    mounts=get_nas_mounts()
    shares=get_samba_shares()
    sp={v:k for k,v in shares.items()}
    if mounts:
        subhdr("Gekoppelde NAS-schijven")
        print(f"  {'Apparaat':<12} {'Mountpunt':<18} {'FS':<8} {'Grootte':<8} {'Samba-share'}")
        print(f"  {'-'*60}")
        for dev,mp,fs,sz in mounts:
            share=sp.get(mp,"(geen)")
            print(f"  {dev:<12} {mp:<18} {fs:<8} {sz:<8} {share}")
    else:
        warn("Geen NAS-schijven gevonden onder /mnt/")
    print()
    pause()

# ════════════════════════════════════════════════════════════════════════════
# SCHIJF: KOPPELEN
# ════════════════════════════════════════════════════════════════════════════
def update_rechten_service():
    """Maak/update systemd service die rechten instelt na reboot."""
    import glob as _glob
    mounts = [m[1] for m in get_nas_mounts()]
    if not mounts: return
    user = sh("logname 2>/dev/null || echo pi") or "pi"
    paths = " ".join(mounts)
    # Basis: chown pi op alle NAS-schijven
    cmd = f"chown -R {user}:{user} {paths} && chmod -R 775 {paths}"
    # Nextcloud datamap uitsluiten — die heeft www-data nodig
    for mp in mounts:
        for nc in _glob.glob(f"{mp}/nextcloud-data"):
            if os.path.exists(nc):
                cmd += f" && chown -R www-data:www-data {nc} && chmod -R 755 {nc}"
    svc = f"""[Unit]
Description=NAS schijf rechten instellen
After=local-fs.target
Requires=local-fs.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c '{cmd}'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""
    with open("/tmp/nas-rechten.service", "w") as f:
        f.write(svc)
    subprocess.run("sudo cp /tmp/nas-rechten.service /etc/systemd/system/nas-rechten.service",
                   shell=True)
    subprocess.run("sudo systemctl daemon-reload", shell=True)
    subprocess.run("sudo systemctl enable nas-rechten.service", shell=True)
    subprocess.run("sudo systemctl start nas-rechten.service", shell=True)


def schijf_koppel():
    clr(); hdr("Schijf koppelen")

    # Toon beschikbare schijven met grootte en status
    print(f"  {BLUE}Beschikbare schijven:{R}")
    schijven=sh("lsblk -dn -o NAME,SIZE,TYPE 2>/dev/null | grep disk")
    grote_vrij=False
    for regel in schijven.splitlines():
        parts=regel.split()
        if len(parts)>=2:
            dev_naam=f"/dev/{parts[0]}"; sz=parts[1]
            mount=sh(f"lsblk -dn -o MOUNTPOINT {dev_naam} 2>/dev/null").strip()
            status=f"→ {mount}" if mount else "→ vrij"
            kleur=GREEN if not mount else DIM
            print(f"  {kleur}{dev_naam}  {sz}  {status}{R}")
            if not mount and ('T' in sz or ('G' in sz and float(sz.replace('G','').strip() or '0') >= 500)):
                grote_vrij=True
    print()

    # Waarschuwing als geen grote schijf vrij
    if not grote_vrij:
        if os.path.exists("/home/pi/smart_plug_config.json"):
            warn("Geen grote schijf gevonden!")
            warn("Zet de Seagate aan via: nas → Beheer → Smart plug → Testen")
            warn("Daarna opnieuw proberen.")
        else:
            warn("Geen grote schijf gevonden!")
            warn("Controleer of de Seagate aangesloten en ingeschakeld is.")
        print()
        if not ask_yn("Toch doorgaan?","n"): return

    info("Druk Ctrl+C om te annuleren en terug te gaan.")
    dev_raw=ask("Schijf (bijv. /dev/sda)", suggest_device())
    if dev_raw is None: return
    dev=fix_dev(dev_raw)
    mp_raw=ask("Mountpunt", suggest_mount(dev))
    if mp_raw is None: return
    mp=mp_raw
    share_default=suggest_share(dev)
    user=sh("logname 2>/dev/null || echo pi")

    do_fmt=ask_yn("Schijf formatteren? (wist alle data!)",  "n")
    fs="ext4"
    if do_fmt:
        warn("ALLE DATA op de schijf wordt gewist!")
        if not ask_yn("Zeker weten?","n"):
            info("Geannuleerd"); pause(); return
        fs=kies_fs()

    add_samba=ask_yn("Samba-share aanmaken voor deze schijf?","j")
    share_name=ask("Samba share-naam", share_default) if add_samba else ""
    samba_user=ask("Samba gebruikersnaam","pi") if add_samba else user

    print()
    if do_fmt:
        for desc,cmd in fs_format(dev,fs):
            run(cmd,desc)

    run(f"sudo mkdir -p {mp}","Mountpunt aanmaken")

    uuid=sh(f"sudo blkid -s UUID -o value {dev}")
    if not uuid:
        err("Geen UUID gevonden — de schijf heeft nog geen bestandssysteem.")
        warn(f"Formatteer eerst: kies in het menu 'Schijf beheer' → 'Formatteren' → {dev}")
        warn("Of ga terug en kies 'Ja' bij de formatteeroptie.")
        pause(); return
    ok(f"UUID: {uuid}")

    fstab=sh("cat /etc/fstab")
    if uuid not in fstab:
        entry=fs_fstab(uuid,mp,fs)+"\n"
        subprocess.run(f"echo '{entry}' | sudo tee -a /etc/fstab",shell=True)
        ok(f"fstab bijgewerkt ({fs})")
    else:
        info("UUID al aanwezig in fstab")

    if sh_rc("sudo mount -a")==0:
        ok(f"Gemount op {mp}")
    else:
        err("Mount mislukt — controleer de fstab-regel")
        pause(); return

    subprocess.run(f"sudo chown -R {user}:{user} {mp} && sudo chmod -R 775 {mp}",shell=True)
    ok(f"Eigenaarschap: {user}")

    if add_samba:
        smbd=sh("sudo systemctl is-enabled smbd 2>/dev/null")
        if smbd in ("enabled","static"):
            conf=sh("cat /etc/samba/smb.conf")
            if f"[{share_name}]" not in conf:
                blk=(f"\n[{share_name}]\n   comment = Pi Opslag\n   path = {mp}\n"
                     f"   browseable = yes\n   writable = yes\n"
                     f"   valid users = {samba_user}\n   force user = {samba_user}\n")
                subprocess.run(f"printf '{blk}' | sudo tee -a /etc/samba/smb.conf > /dev/null",shell=True)
                subprocess.run("sudo systemctl restart smbd",shell=True)
                ok(f"Samba-share [{share_name}] aangemaakt")
            else:
                info(f"Share [{share_name}] bestaat al")
        else:
            info("Samba niet geïnstalleerd — share overgeslagen")

    print()
    ok(f"Schijf succesvol gekoppeld!")
    update_rechten_service()
    info(f"Mountpunt: {mp}")
    if add_samba: info(f"Windows: \\\\{get_ip()}\\{share_name}")
    pause()

# ════════════════════════════════════════════════════════════════════════════
# SCHIJF: WISSELEN
# ════════════════════════════════════════════════════════════════════════════
def schijf_wissel():
    clr(); hdr("Schijf wisselen")
    mounts=get_nas_mounts()
    if not mounts:
        warn("Geen NAS-schijven gevonden om te vervangen")
        pause(); return

    print("  Huidige NAS-schijven:")
    for i,(dev,mp,fs,sz) in enumerate(mounts,1):
        print(f"  {CYAN}{i}{R}  {mp}  ({dev}, {sz}, {fs})")
    print()
    keuze=int(ask("Welke vervangen? (nummer)","1"))-1
    if not 0<=keuze<len(mounts):
        warn("Ongeldige keuze"); pause(); return
    _,mp,_,_=mounts[keuze]

    print()
    print("  Beschikbare schijven:")
    os.system("lsblk -o NAME,SIZE,TYPE -rn | grep disk | sed 's/^/    /'")
    print()
    new_dev=fix_dev(ask("Nieuwe schijf (bijv. /dev/sda)", suggest_device()))
    do_fmt=ask_yn(f"Nieuwe schijf {new_dev} formatteren? (wist alle data!)", "n")
    fs="ext4"
    if do_fmt:
        warn("ALLE DATA op de nieuwe schijf wordt gewist!")
        if not ask_yn("Zeker weten?","n"):
            info("Geannuleerd"); pause(); return
        fs=kies_fs()

    warn(f"NAS-software blijft geïnstalleerd. Alleen {mp} wordt opnieuw gekoppeld.")
    warn("Nextcloud-data staat op de OUDE schijf en gaat NIET mee.")
    if not ask_yn("Doorgaan?","j"):
        info("Geannuleerd"); pause(); return

    print()
    for svc in ["smbd","apache2","mariadb"]:
        if sh(f"sudo systemctl is-active {svc}")=="active":
            subprocess.run(f"sudo systemctl stop {svc}",shell=True)
            ok(f"{svc} gestopt")

    subprocess.run(f"sudo umount {mp} 2>/dev/null",shell=True)
    ok(f"Ge-unmount: {mp}")

    if do_fmt:
        for desc,cmd in fs_format(new_dev,fs):
            run(cmd,desc)

    uuid=sh(f"sudo blkid -s UUID -o value {new_dev}")
    if not uuid:
        err("Geen UUID gevonden"); pause(); return
    ok(f"UUID: {uuid}")

    lines=[l for l in sh("cat /etc/fstab").splitlines()
           if mp not in l or l.strip().startswith("#")]
    lines.append(fs_fstab(uuid,mp,fs))
    new_fstab="\n".join(lines)+"\n"
    subprocess.run(f"sudo bash -c \"printf '%s' '{new_fstab}' > /etc/fstab\"",shell=True)
    ok("fstab bijgewerkt")

    subprocess.run(f"sudo mkdir -p {mp}",shell=True)
    if sh_rc("sudo mount -a")==0:
        ok("Gemount!")
    else:
        err("Mount mislukt"); pause(); return

    user=sh("logname 2>/dev/null || echo pi")
    subprocess.run(f"sudo chown -R {user}:{user} {mp} && sudo chmod -R 775 {mp}",shell=True)
    ok(f"Eigenaarschap: {user}")

    for svc in ["smbd","apache2","mariadb"]:
        if sh(f"sudo systemctl is-enabled {svc} 2>/dev/null") in ("enabled","static"):
            subprocess.run(f"sudo systemctl start {svc}",shell=True)
            ok(f"{svc} herstart")

    print()
    ok("Schijf succesvol gewisseld!")
    update_rechten_service()
    ok("Samba werkt direct.")
    warn("Nextcloud: data staat op de oude schijf.")
    pause()

# ════════════════════════════════════════════════════════════════════════════
# SCHIJF: VERWIJDEREN
# ════════════════════════════════════════════════════════════════════════════
def schijf_verwijder():
    clr(); hdr("Schijf verwijderen")
    mounts=get_nas_mounts()
    if not mounts:
        warn("Geen NAS-schijven gevonden")
        pause(); return

    shares=get_samba_shares()
    sp={v:k for k,v in shares.items()}

    print("  Gekoppelde NAS-schijven:")
    for i,(dev,mp,fs,sz) in enumerate(mounts,1):
        share=sp.get(mp,"(geen)")
        print(f"  {CYAN}{i}{R}  {mp}  ({dev}, {sz})  Samba: {share}")
    print()
    keuze=int(ask("Welke verwijderen? (nummer)","1"))-1
    if not 0<=keuze<len(mounts):
        warn("Ongeldige keuze"); pause(); return
    dev,mp,fs,sz=mounts[keuze]
    share=sp.get(mp)

    print()
    info(f"Wordt verwijderd:")
    dim(f"• fstab-regel voor {mp}")
    dim(f"• Unmount van {mp}")
    if share: dim(f"• Samba-share [{share}]")
    dim(f"• Data op de schijf blijft BEWAARD")
    print()
    if not ask_yn("Doorgaan?","j"):
        info("Geannuleerd"); pause(); return

    if share:
        conf=sh("cat /etc/samba/smb.conf")
        lines=conf.splitlines(); new=[]; skip=False
        for line in lines:
            if line.strip()==f"[{share}]": skip=True
            elif skip and line.strip().startswith("["): skip=False
            if not skip: new.append(line)
        subprocess.run(f"printf '%s\\n' "+(" ".join(f"'{l}'" for l in new))+
                       " | sudo tee /etc/samba/smb.conf > /dev/null",shell=True)
        subprocess.run("sudo systemctl restart smbd 2>/dev/null",shell=True)
        ok(f"Samba-share [{share}] verwijderd")

    lines=[l for l in sh("cat /etc/fstab").splitlines()
           if mp not in l or l.strip().startswith("#")]
    subprocess.run(f"sudo bash -c \"printf '%s\\n' > /etc/fstab\"",shell=True)
    for l in lines:
        subprocess.run(f"echo '{l}' | sudo tee -a /etc/fstab > /dev/null",shell=True)
    ok("fstab bijgewerkt")

    subprocess.run(f"sudo umount {mp} 2>/dev/null",shell=True)
    ok(f"Ge-unmount")
    ok("Schijf verwijderd — data onaangeroerd")
    update_rechten_service()
    pause()

# ════════════════════════════════════════════════════════════════════════════
# SCHIJF: FORMATTEREN
# ════════════════════════════════════════════════════════════════════════════
def schijf_rechten():
    clr(); hdr("Rechten herstellen", BLUE)
    user = sh("logname 2>/dev/null || echo pi") or "pi"
    mounts = get_nas_mounts()
    if not mounts:
        warn("Geen NAS-schijven gevonden.")
        pause(); return

    print("  Gevonden NAS-schijven:")
    for dev,mp,fs,sz in mounts:
        # Test schrijfrechten
        testfile = f"{mp}/.write_test"
        r = subprocess.run(f"sudo touch {testfile} && sudo rm {testfile}",
                           shell=True, capture_output=True)
        status = f"{GREEN}✔ OK{R}" if r.returncode==0 else f"{RED}✗ Schrijven mislukt{R}"
        print(f"  {mp:<20} {status}")
    print()

    if not ask_yn("Rechten herstellen op alle NAS-schijven?", "j"):
        info("Geannuleerd."); pause(); return

    print()
    for dev,mp,fs,sz in mounts:
        subprocess.run(
            f"sudo chown -R {user}:{user} {mp} && sudo chmod -R 775 {mp}",
            shell=True)
        ok(f"Rechten hersteld op {mp} (eigenaar: {user})")

    print()
    ok("Klaar — probeer nu opnieuw te schrijven via Windows Verkenner.")
    pause()


def schijf_format():
    clr(); hdr("Schijf formatteren")
    print("  Beschikbare schijven:")
    os.system("lsblk -o NAME,SIZE,TYPE,FSTYPE -rn | sed 's/^/    /'")
    print()
    warn("WAARSCHUWING: formatteren wist ALLE data op de schijf permanent!")
    warn("Zorg dat de schijf NIET gemount is.")
    print()
    info("Druk Ctrl+C om te annuleren.")
    dev_raw=ask("Schijf (bijv. /dev/sda)")
    if dev_raw is None: return
    dev=fix_dev(dev_raw)
    if not dev: pause(); return
    fs=kies_fs()
    print()
    warn(f"ALLE DATA op {dev} wordt gewist als {fs}!")
    if not ask_yn("Eerste bevestiging — zeker weten?","n"):
        info("Geannuleerd"); pause(); return
    if not ask_yn("Tweede bevestiging — echt zeker?","n"):
        info("Geannuleerd"); pause(); return
    print()
    for desc,cmd in fs_format(dev,fs):
        run(cmd,desc)
    ok(f"{dev} geformatteerd als {fs}")
    pause()

# ════════════════════════════════════════════════════════════════════════════
# SCHIJF MENU
# ════════════════════════════════════════════════════════════════════════════
def schijf_menu():
    while True:
        clr(); hdr("Schijf beheer", BLUE)
        idx=ask_menu([
            "📋  Overzicht — toon gekoppelde schijven",
            "💾  Koppelen — eerste of extra schijf",
            "🔄  Wisselen — testschijf → definitieve schijf",
            "🗑   Verwijderen — schijf netjes ontkoppelen",
            "🔧  Formatteren — schijf leegmaken",
            "🔑  Rechten herstellen — fix schrijfproblemen",
            "← Terug naar hoofdmenu",
        ])
        if   idx==0: schijf_overzicht()
        elif idx==1: schijf_koppel()
        elif idx==2: schijf_wissel()
        elif idx==3: schijf_verwijder()
        elif idx==4: schijf_format()
        elif idx==5: schijf_rechten()
        elif idx==6 or idx==-1: return

# ════════════════════════════════════════════════════════════════════════════
# NAS SOFTWARE INSTALLEREN
# ════════════════════════════════════════════════════════════════════════════
def nas_config():
    """Vraag NAS-instellingen op, geef dict terug."""
    clr(); hdr("NAS-instellingen")

    # Detecteer wat al geïnstalleerd is
    samba_ok=sh("dpkg -l samba 2>/dev/null | grep -c '^ii'").strip()=="1"
    nc_ok=os.path.exists("/var/www/html/nextcloud")
    if samba_ok or nc_ok:
        already=[]
        if samba_ok: already.append("Samba")
        if nc_ok: already.append("Nextcloud")
        warn(f"Al geïnstalleerd: {', '.join(already)}")
        warn("Opnieuw installeren overschrijft de huidige configuratie.")
        print()
        if not ask_yn("Toch doorgaan met installatie?","n"):
            info("Geannuleerd — terug naar hoofdmenu.")
            pause(); return None

    print(f"  Methode kiezen:")
    idx=ask_menu([
        "Methode A — Samba + Cockpit (aanbevolen, ~20 min)",
        "Methode B — Nextcloud (eigen cloud, ~45 min)",
        "Beide methoden (~65 min)",
    ])
    method=["A","B","AB"][idx]

    cfg={"method":method}

    mounts=get_nas_mounts()
    mp=mounts[0][1] if mounts else ask("Mountpunt opslag","/mnt/opslag")
    cfg["mp"]=mp

    if method in ("A","AB"):
        print()
        subhdr("Samba instellingen")
        cfg["share"]=ask("Naam gedeelde map","Opslag")
        cfg["user"]=ask("Gebruikersnaam","pi")
        while True:
            cfg["passwd"]=ask_pw("Wachtwoord")
            cfg["passwd2"]=ask_pw("Wachtwoord (herhaal)")
            if not cfg["passwd"]:
                warn("Wachtwoord mag niet leeg zijn"); continue
            if cfg["passwd"]!=cfg["passwd2"]:
                warn("Wachtwoorden komen niet overeen"); continue
            if len(cfg["passwd"])<6:
                warn("Minimaal 6 tekens"); continue
            break

    if method in ("B","AB"):
        print()
        subhdr("Nextcloud instellingen")
        cfg["nc_admin"]=ask("Beheerder gebruikersnaam","admin")
        cfg["nc_pass"]=ask_pw("Beheerder wachtwoord")
        cfg["nc_db"]=ask_pw("Database wachtwoord (intern)")

    return cfg

def nas_install(cfg):
    clr(); hdr("NAS-software installeren", GREEN)
    method=cfg["method"]; mp=cfg["mp"]; ip=get_ip()

    if method in ("A","AB"):
        share=cfg["share"]; user=cfg["user"]; passwd=cfg["passwd"]
        print(f"\n{GREEN}{BOLD}── Methode A: Samba + Cockpit ──{R}\n")
        run("sudo apt-get update -y","apt update")
        run("sudo apt-get install -y samba samba-common-bin","Samba installeren")
        subprocess.run(f"sudo chown -R {user}:{user} {mp} && sudo chmod -R 775 {mp}",shell=True)
        ok(f"Rechten ingesteld")
        subprocess.run(f"(echo '{passwd}';echo '{passwd}')|sudo smbpasswd -a {user} -s",shell=True)
        ok(f"Samba-gebruiker aangemaakt")
        smb=(f"\n[{share}]\n   comment = Pi NAS\n   path = {mp}\n"
             f"   browseable = yes\n   writable = yes\n"
             f"   valid users = {user}\n   create mask = 0664\n"
             f"   directory mask = 0775\n   force user = {user}\n")
        subprocess.run(f"printf '{smb}' | sudo tee -a /etc/samba/smb.conf > /dev/null",shell=True)
        subprocess.run("sudo systemctl restart smbd && sudo systemctl enable smbd",shell=True)
        ok("Samba gestart")
        run("sudo apt-get install -y cockpit","Cockpit installeren")
        subprocess.run("sudo systemctl enable cockpit && sudo systemctl start cockpit",shell=True)
        ok("Cockpit gestart")
        print()
        ok(f"Windows Verkenner: \\\\{ip}\\{share}")
        ok(f"Cockpit: http://{ip}:9090")

    if method in ("B","AB"):
        nc_admin=cfg["nc_admin"]; nc_pass=cfg["nc_pass"]; nc_db=cfg["nc_db"]
        nc_data=f"{mp}/nextcloud-data"
        print(f"\n{GREEN}{BOLD}── Methode B: Nextcloud ──{R}\n")
        run("sudo apt-get install -y apache2 mariadb-server php php-mysql php-gd "
            "php-curl php-zip php-xml php-mbstring php-intl php-imagick "
            "php-bcmath php-gmp libapache2-mod-php unzip wget","Vereisten installeren")
        subprocess.run("sudo systemctl start mariadb && sudo systemctl enable mariadb",shell=True)
        sql=(f"CREATE DATABASE IF NOT EXISTS nextcloud CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"
             f"CREATE USER IF NOT EXISTS 'ncuser'@'localhost' IDENTIFIED BY '{nc_db}';"
             f"GRANT ALL PRIVILEGES ON nextcloud.* TO 'ncuser'@'localhost';FLUSH PRIVILEGES;")
        subprocess.run(f'sudo mysql -u root -e "{sql}"',shell=True)
        ok("Database aangemaakt")
        run("cd /tmp && sudo wget -q -O latest.zip "
            "https://download.nextcloud.com/server/releases/latest.zip","Nextcloud downloaden")
        run("cd /tmp && sudo unzip -q latest.zip","Uitpakken")
        run("sudo mv /tmp/nextcloud /var/www/html/ && "
            "sudo chown -R www-data:www-data /var/www/html/nextcloud","Plaatsen")
        subprocess.run(f"sudo mkdir -p {nc_data} && sudo chown -R www-data:www-data {nc_data}",shell=True)
        run("sudo a2enmod rewrite headers env dir mime && sudo systemctl restart apache2","Apache")
        run(f"sudo -u www-data php /var/www/html/nextcloud/occ maintenance:install "
            f"--database mysql --database-name nextcloud --database-user ncuser "
            f"--database-pass '{nc_db}' --admin-user '{nc_admin}' "
            f"--admin-pass '{nc_pass}' --data-dir '{nc_data}'","Nextcloud initialiseren")
        subprocess.run(f"sudo -u www-data php /var/www/html/nextcloud/occ "
                       f"config:system:set trusted_domains 1 --value={ip}",shell=True)
        # Voorbeeldbestanden verwijderen
        run("sudo rm -rf /var/www/html/nextcloud/core/skeleton/*",
            "Voorbeeldbestanden verwijderen")
        run(f"sudo find {nc_data} -name '*.md' -o -name '*.pdf' -o -name 'Nextcloud*' "
            f"2>/dev/null | sudo xargs rm -f 2>/dev/null; "
            f"sudo -u www-data php /var/www/html/nextcloud/occ files:scan {nc_admin} --quiet 2>/dev/null",
            "Bestandsindex bijwerken")
        ok(f"Nextcloud: http://{ip}/nextcloud")

    print()
    hdr("✅  Installatie voltooid!", GREEN)
    ok(f"IP-adres Pi: {ip}")
    print()

    if method in ("A","AB"):
        print(f"  {BLUE}{BOLD}── Inloggen via Windows ──{R}")
        print(f"  1. Open Windows Verkenner")
        print(f"  2. Klik in de adresbalk en typ:  {YELLOW}\\\\{ip}\\{cfg['share']}{R}")
        print(f"  3. Druk Enter")
        print(f"  4. Gebruikersnaam: {YELLOW}{cfg['user']}{R}")
        print(f"  5. Wachtwoord: {YELLOW}het wachtwoord dat je zojuist hebt ingesteld{R}")
        print(f"  6. Vink 'Inloggegevens onthouden' aan")
        print()
        print(f"  {BLUE}{BOLD}── Inloggen via iPhone (Bestanden-app) ──{R}")
        print(f"  1. Open de Bestanden-app")
        print(f"  2. Tik rechtsonder op Bladeren")
        print(f"  3. Tik ··· rechtsboven → Verbinding maken met server")
        print(f"  4. Typ:  {YELLOW}smb://{ip}{R}")
        print(f"  5. Gebruiker: {YELLOW}{cfg['user']}{R}  Wachtwoord: je Samba-wachtwoord")
        print()
        print(f"  {BLUE}{BOLD}── Inloggen via Android (Solid Explorer) ──{R}")
        print(f"  1. Installeer Solid Explorer (gratis, Play Store)")
        print(f"  2. Tik + → Netwerk → SMB/LAN")
        print(f"  3. Server: {YELLOW}{ip}{R}   Share: {YELLOW}{cfg['share']}{R}")
        print(f"  4. Gebruiker: {YELLOW}{cfg['user']}{R}  Wachtwoord: je Samba-wachtwoord")
        print()
        print(f"  {BLUE}{BOLD}── Cockpit (webbeheer + afsluiten) ──{R}")
        print(f"  Browser op PC of telefoon: {YELLOW}http://{ip}:9090{R}")
        print(f"  Inloggen met Pi OS gebruiker: {YELLOW}pi{R} en je Pi-wachtwoord")
        print(f"  (Let op: dit is het Pi OS-wachtwoord, NIET het Samba-wachtwoord)")
        print()

    if method in ("B","AB"):
        nc_admin=cfg.get("nc_admin","admin")
        print(f"  {BLUE}{BOLD}── Inloggen Nextcloud ──{R}")
        print(f"  Browser: {YELLOW}http://{ip}/nextcloud{R}")
        print(f"  Gebruikersnaam: {YELLOW}{nc_admin}{R}")
        print(f"  Wachtwoord: het Nextcloud-wachtwoord dat je hebt ingesteld")
        print()
        print(f"  App installeren:")
        print(f"  Android/iPhone: zoek 'Nextcloud' in Play Store / App Store (gratis)")
        print(f"  Serveradres invullen: {YELLOW}http://{ip}/nextcloud{R}")
        print()

    print(f"  {BLUE}{BOLD}── Pi afsluiten ──{R}")
    print(f"  Via terminal:  {YELLOW}sudo shutdown -h now{R}")
    print(f"  Via Cockpit:   {YELLOW}http://{ip}:9090{R} → klik op systeemnaam → Afsluiten")
    print(f"  Wacht daarna ~30 seconden voor je de schijfbehuizing uitzet!")
    print()
    warn("Noteer je gegevens:")
    print(f"  IP-adres:          {YELLOW}{ip}{R}")
    if method in ("A","AB"):
        print(f"  Samba gebruiker:   {YELLOW}{cfg['user']}{R}")
        print(f"  Windows pad:       {YELLOW}\\\\{ip}\\{cfg['share']}{R}")
    if method in ("B","AB"):
        print(f"  Nextcloud:         {YELLOW}http://{ip}/nextcloud{R}")
        print(f"  NC gebruiker:      {YELLOW}{cfg.get('nc_admin','admin')}{R}")
    print()
    pause()

# ════════════════════════════════════════════════════════════════════════════
# INITIËLE SETUP — ALLES IN ÉÉN
# ════════════════════════════════════════════════════════════════════════════
def initiele_setup():
    clr(); hdr("🚀  Initiële setup — alles in één", GREEN)
    info("Regelt: netwerk · SSH · update · schijf · NAS-software")
    print()

    # Gevonden schijven tonen
    print("  Gevonden schijven:")
    os.system("lsblk -o NAME,SIZE,TYPE -rn | grep disk | sed 's/^/    /'")
    print()

    # Netwerk
    if not is_connected():
        subhdr("Netwerk instellen")
        os.system("sudo nmcli dev wifi list 2>/dev/null | head -10")
        print()
        ssid=ask("WiFi netwerknaam (SSID, leeg = UTP gebruiken)")
        if ssid:
            pwd=ask_pw("WiFi wachtwoord")
            cmd=f'sudo nmcli dev wifi connect "{ssid}"'
            if pwd: cmd+=f' password "{pwd}"'
            run(cmd+" 2>&1","Verbinden")
            time.sleep(2)
            if is_connected(): ok(f"Verbonden: {get_ip()}")
            else: warn("Verbinding mislukt — verder met UTP of controleer gegevens")
    else:
        ok(f"Netwerk: {get_ip()}")

    # SSH
    subhdr("SSH")
    if not ssh_enabled():
        sh("sudo systemctl enable ssh && sudo systemctl start ssh")
    ok(f"SSH actief — ssh pi@{get_ip()}")

    # Update
    subhdr("Systeem bijwerken")
    if ask_yn("Bijwerken? (aanbevolen maar langzaam)","j"):
        run("sudo apt-get update -y && sudo apt-get upgrade -y","Bijwerken")
        ok("Bijgewerkt")
    else:
        info("Overgeslagen")

    # Schijf
    subhdr("Schijf instellen")
    print("  Beschikbare schijven:")
    os.system("lsblk -o NAME,SIZE,TYPE -rn | grep disk | sed 's/^/    /'")
    print()
    dev=fix_dev(ask("Schijf", suggest_device()))
    mp =ask("Mountpunt", "/mnt/opslag")
    user=sh("logname 2>/dev/null || echo pi")

    if ask_yn(f"Schijf {dev} formatteren als ext4? (wist alle data!)", "n"):
        if ask_yn("Zeker weten?","n"):
            run(f"sudo wipefs -a {dev}","Partitietabel wissen")
            run(f"sudo mkfs.ext4 -F {dev}","Formatteren als ext4")
            run(f"sudo partprobe {dev} 2>/dev/null; sudo udevadm settle","Kernel bijwerken")

    run(f"sudo mkdir -p {mp}","Mountpunt aanmaken")
    uuid=sh(f"sudo blkid -s UUID -o value {dev}")
    if uuid:
        fstab=sh("cat /etc/fstab")
        if uuid not in fstab:
            entry=f"UUID={uuid}  {mp}  ext4  defaults,nofail  0  2\n"
            subprocess.run(f"echo '{entry}' | sudo tee -a /etc/fstab",shell=True)
        subprocess.run("sudo mount -a",shell=True)
        subprocess.run(f"sudo chown -R {user}:{user} {mp} && sudo chmod -R 775 {mp}",shell=True)
        ok(f"Schijf gekoppeld op {mp}")
        update_rechten_service()
    else:
        warn("Geen UUID — schijf niet gevonden, verder zonder schijf")

    # NAS software
    subhdr("NAS-software")
    cfg=nas_config()
    cfg["mp"]=mp
    nas_install(cfg)
# DIAGNOSE
# ════════════════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════════════════
# FILEBROWSER
# ════════════════════════════════════════════════════════════════════════════
def cockpit_menu():
    clr(); hdr("Cockpit — webbeheer Raspberry Pi", "#ed8936")
    ip=get_ip()
    ck_actief=sh("systemctl is-active cockpit 2>/dev/null")=="active"
    ck_installed=bool(sh("which cockpit 2>/dev/null") or sh("dpkg -l cockpit 2>/dev/null | grep '^ii'"))
    svc_enabled=sh("systemctl is-enabled cockpit 2>/dev/null")=="enabled"

    if ck_installed:
        if ck_actief:
            ok(f"Cockpit is actief op: http://{ip}:9090")
        else:
            warn("Cockpit is momenteel niet actief")
        info(f"Login met Pi OS gebruikersnaam en wachtwoord")
    else:
        warn("Cockpit is niet geïnstalleerd")
    print()

    idx=ask_menu([
        "Cockpit installeren",
        "Cockpit starten",
        "Cockpit stoppen",
        "Cockpit inschakelen bij opstarten",
        "Cockpit uitschakelen bij opstarten",
        "← Terug",
    ])

    if idx==0:
        clr(); hdr("Cockpit installeren", "#ed8936")
        if ck_installed:
            ok("Cockpit is al geïnstalleerd")
        else:
            run("sudo apt-get install -y cockpit", "Cockpit installeren")
        run("sudo systemctl enable --now cockpit.socket", "Cockpit inschakelen")
        ok(f"Cockpit beschikbaar op: http://{ip}:9090")
        info(f"Login met Pi OS gebruikersnaam: pi")
    elif idx==1:
        if not ck_installed: warn("Cockpit niet geïnstalleerd."); pause(); return
        run("sudo systemctl start cockpit","Cockpit starten")
        ok(f"Cockpit actief op: http://{ip}:9090")
    elif idx==2:
        run("sudo systemctl stop cockpit","Cockpit stoppen")
        ok("Cockpit gestopt")
    elif idx==3:
        run("sudo systemctl enable cockpit.socket","Cockpit inschakelen bij opstarten")
        ok("Cockpit wordt automatisch gestart bij opstarten")
    elif idx==4:
        run("sudo systemctl disable cockpit.socket","Cockpit uitschakelen bij opstarten")
        ok("Cockpit start niet meer automatisch")
    if idx != 5 and idx != -1: pause()


def filebrowser_menu():
    clr(); hdr("FileBrowser — webbeheer bestanden", MAGENTA)
    ip=get_ip()
    fb_actief=sh("systemctl is-active filebrowser 2>/dev/null")=="active" or \
               bool(sh("pgrep -x filebrowser 2>/dev/null"))
    svc_enabled=sh("systemctl is-enabled filebrowser 2>/dev/null") in ("enabled","static")
    mp=sh("grep -o 'r /mnt[^ ]*' /etc/systemd/system/filebrowser.service 2>/dev/null | head -1 | cut -c3-") or "/mnt/opslag"

    if fb_actief:
        ok(f"FileBrowser is actief op: http://{ip}:8080")
    else:
        warn("FileBrowser is momenteel niet actief")
    info(f"Bestandsmap: {mp}")
    print()

    idx=ask_menu([
        "FileBrowser installeren en als service instellen",
        "FileBrowser starten (eenmalig, stopt bij afsluiten)",
        "FileBrowser stoppen",
        "FileBrowser inschakelen bij opstarten",
        "FileBrowser uitschakelen bij opstarten",
        "Wachtwoord resetten (naar willekeurig wachtwoord)",
        "← Terug",
    ])

    if idx==0:
        clr(); hdr("FileBrowser installeren", MAGENTA)
        if sh("which filebrowser"):
            ok("FileBrowser is al geïnstalleerd")
        else:
            run("curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash",
                "FileBrowser downloaden en installeren")

        mp_in=ask("Bestandsmap (wat je via browser ziet)", mp)
        port=ask("Poort","8080")

        svc=f"""[Unit]
Description=FileBrowser NAS
After=network.target mnt-opslag.mount

[Service]
ExecStart=/usr/local/bin/filebrowser -r {mp_in} -a 0.0.0.0 -p {port} -d /home/pi/filebrowser.db
Restart=always
User=pi
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
        with open("/tmp/filebrowser.service","w") as f: f.write(svc)
        sh("sudo cp /tmp/filebrowser.service /etc/systemd/system/filebrowser.service")
        sh("sudo systemctl daemon-reload")
        sh("sudo systemctl enable filebrowser")
        sh("sudo systemctl start filebrowser")
        import time; time.sleep(2)
        ok(f"FileBrowser geïnstalleerd en actief op http://{ip}:{port}")
        print()
        info("Eerste keer inloggen:")
        info("  Gebruikersnaam: admin")
        info("  Wachtwoord:     zie uitvoer hierboven (willekeurig gegenereerd)")
        info("  Wijzig het wachtwoord direct na inloggen!")

    elif idx==1:
        mp_in=ask("Bestandsmap", mp)
        print(f"\n  {CYAN}FileBrowser starten op http://{ip}:8080{R}")
        print(f"  {DIM}Stop met Ctrl+C{R}\n")
        os.system(f"filebrowser -r {mp_in} -a 0.0.0.0 -p 8080 -d /home/pi/filebrowser.db")

    elif idx==2:
        sh("sudo systemctl stop filebrowser 2>/dev/null")
        sh("pkill filebrowser 2>/dev/null")
        ok("FileBrowser gestopt")

    elif idx==3:
        sh("sudo systemctl enable filebrowser")
        sh("sudo systemctl start filebrowser")
        ok(f"FileBrowser ingeschakeld en gestart op http://{ip}:8080")

    elif idx==4:
        sh("sudo systemctl disable filebrowser")
        sh("sudo systemctl stop filebrowser")
        ok("FileBrowser uitgeschakeld")

    elif idx==5:
        sh("sudo systemctl stop filebrowser 2>/dev/null")
        sh("rm -f /home/pi/filebrowser.db")
        sh("sudo systemctl start filebrowser 2>/dev/null || "
           "filebrowser -r /mnt/opslag -d /home/pi/filebrowser.db &")
        import time; time.sleep(1)
        out=sh("journalctl -u filebrowser -n 5 --no-pager 2>/dev/null || "
               "cat /tmp/fb.log 2>/dev/null")
        ok("Database gereset — nieuw willekeurig wachtwoord gegenereerd")
        info("Bekijk het nieuwe wachtwoord in de service-log:")
        print(f"  {CYAN}sudo journalctl -u filebrowser -n 10 --no-pager{R}")

    elif idx==6 or idx==-1:
        return

    if idx not in (1,6):
        pause()


# ════════════════════════════════════════════════════════════════════════════
# SCRIPTS BIJWERKEN VANUIT BOOTFS
# ════════════════════════════════════════════════════════════════════════════
def update_scripts():
    clr(); hdr("Scripts bijwerken vanuit SD-kaart", CYAN)
    info("Kopieert nieuwe of gewijzigde scripts van /boot/firmware/ naar /home/pi/")
    print()

    bootfs="/boot/firmware"
    gevonden=[]
    for ext in ("*.py","*.sh"):
        import glob
        gevonden+=glob.glob(f"{bootfs}/{ext}")

    if not gevonden:
        warn("Geen .py of .sh bestanden gevonden in /boot/firmware/")
        pause(); return

    copied=0; skipped=0
    for src_path in sorted(gevonden):
        base=os.path.basename(src_path)
        dest=f"/home/pi/{base}"
        if not os.path.exists(dest):
            sh(f"sudo cp '{src_path}' '{dest}' && sudo chown pi:pi '{dest}'")
            ok(f"Nieuw gekopieerd:  {base}")
            copied+=1
        elif sh(f"diff -q '{src_path}' '{dest}' 2>/dev/null"):
            sh(f"sudo cp '{src_path}' '{dest}' && sudo chown pi:pi '{dest}'")
            ok(f"Bijgewerkt:        {base}")
            copied+=1
        else:
            dim(f"Ongewijzigd:       {base}")
            skipped+=1

    print()
    if copied>0:
        ok(f"{copied} bestand(en) bijgewerkt.")
        info("Herstart 'nas' om de nieuwe versie te gebruiken.")
    else:
        ok("Alles is al up-to-date — niets gekopieerd.")
    pause()


# ════════════════════════════════════════════════════════════════════════════
# DESKTOP INSTALLEREN / VERWIJDEREN
# ════════════════════════════════════════════════════════════════════════════

def create_desktop_shortcuts():
    """Maak desktop snelkoppelingen aan als ze nog niet bestaan."""
    import os
    shortcuts = {
        "/home/pi/Desktop/nas_installer.desktop": """[Desktop Entry]
Version=1.0
Type=Application
Name=NAS Installer
Exec=sudo python3 /home/pi/nas_installer.py
Icon=preferences-system
Terminal=true
Categories=System;
""",
        "/home/pi/Desktop/raspi_config.desktop": """[Desktop Entry]
Version=1.0
Type=Application
Name=Raspi Config
Exec=sudo raspi-config
Icon=preferences-desktop
Terminal=true
Categories=System;
""",
        }
    os.makedirs("/home/pi/Desktop", exist_ok=True)
    created = 0
    for path, content in shortcuts.items():
        if os.path.exists(path):
            # Controleer of inhoud klopt
            with open(path) as f:
                existing = f.read()
            if content.strip() == existing.strip():
                dim(f"Snelkoppeling al aanwezig: {os.path.basename(path)}")
                continue
        with open(path, "w") as f:
            f.write(content)
        sh(f"chmod +x {path}")
        sh(f"chown pi:pi {path}")
        sh(f"gio set {path} metadata::trusted true 2>/dev/null")
        ok(f"Snelkoppeling aangemaakt: {os.path.basename(path).replace('.desktop','')}")
        created += 1
    if created > 0:
        ok(f"{created} snelkoppeling(en) aangemaakt op het bureaublad.")

def desktop_menu():
    clr(); hdr("Desktop installeren / verwijderen", MAGENTA)

    # Controleer huidige status
    desktop_installed = sh("dpkg -l lxde-core 2>/dev/null | grep -c '^ii'")
    has_desktop = desktop_installed.strip() == "1"
    vnc_installed = bool(sh("which wayvnc 2>/dev/null || which vncserver 2>/dev/null || dpkg -l realvnc-vnc-server 2>/dev/null | grep -c '^ii'"))
    vnc_active = sh("sudo systemctl is-active vncserver-x11-serviced 2>/dev/null || sudo systemctl is-active wayvnc 2>/dev/null").strip() == "active"
    ip = get_ip()

    if has_desktop:
        ok("Desktop (LXDE) is geïnstalleerd")
        tk_ok = sh("python3 -c 'import tkinter' 2>/dev/null; echo $?").strip() == "0"
        if tk_ok: ok("Tkinter is beschikbaar — grafische installer werkt")
        else: warn("Tkinter ontbreekt nog")
    else:
        info("Desktop (LXDE) is NIET geïnstalleerd — Lite modus")

    if vnc_installed:
        ok(f"VNC is geïnstalleerd — {'actief op '+ip+':5900' if vnc_active else 'niet actief'}")
    else:
        info("VNC is niet geïnstalleerd")

    disk = sh("df -h / | tail -1")
    avail = sh("df -BG / | tail -1 | awk '{print $4}'").replace("G","").strip()
    print()
    info(f"SD-kaart: {disk}")
    if avail and int(avail) < 2:
        warn("Minder dan 2GB vrij — installatie kan mislukken!")
    print()

    idx=ask_menu([
        "🖥️  Desktop installeren (LXDE + Tkinter) — ~500MB, ~10 min",
        "🗑   Desktop verwijderen — terug naar Lite",
        "📺  VNC installeren — grafische omgeving via Windows/tablet",
        "▶   VNC inschakelen",
        "⏹   VNC uitschakelen",
        "🗑   VNC verwijderen",
        "← Terug",
    ])

    if idx==0:
        if has_desktop: info("Desktop is al geïnstalleerd."); pause(); return
        warn("Pi gebruikt daarna ~300-400MB extra RAM.")
        warn("Aanbevolen voor Pi 5 — op Pi 4 merkbaar trager.")
        if not ask_yn("Desktop installeren?","j"): info("Geannuleerd."); pause(); return
        run("sudo apt-get update -y","Pakketlijst bijwerken")
        run("sudo apt-get install -y xorg lxde-core lightdm","Desktop installeren")
        run("sudo apt-get install -y python3-tk","Tkinter installeren")
        run("sudo systemctl set-default graphical.target","Automatisch opstarten instellen")
        ok("Desktop geïnstalleerd!")
        create_desktop_shortcuts()
        if ask_yn("Pi nu herstarten?","j"): sh("sudo reboot")

    elif idx==1:
        if not has_desktop: info("Desktop al verwijderd."); pause(); return
        warn("Pi start daarna op in tekstmodus. NAS blijft werken.")
        if not ask_yn("Desktop verwijderen?","n"): info("Geannuleerd."); pause(); return
        run("sudo apt-get remove -y lxde-core lxde lightdm xorg","Desktop verwijderen")
        run("sudo apt-get autoremove -y","Opruimen")
        run("sudo systemctl set-default multi-user.target","Tekstmodus instellen")
        ok("Desktop verwijderd.")
        if ask_yn("Pi nu herstarten?","j"): sh("sudo reboot")

    elif idx==2:
        if not has_desktop:
            warn("Desktop moet eerst geïnstalleerd zijn voor VNC.")
            pause(); return
        print()
        info("VNC laat je de grafische omgeving van de Pi zien op je Windows-pc.")
        info("Gebruik VNC Viewer (gratis): https://www.realvnc.com/en/connect/download/viewer/")
        info(f"Verbindingsadres: {ip}:5900")
        print()
        if not ask_yn("VNC installeren?","j"): info("Geannuleerd."); pause(); return
        run("sudo apt-get update -y","Pakketlijst bijwerken")
        run("sudo apt-get install -y realvnc-vnc-server","RealVNC installeren")
        run("sudo systemctl enable vncserver-x11-serviced","VNC inschakelen bij opstarten")
        run("sudo systemctl start vncserver-x11-serviced","VNC starten")
        print()
        ok("VNC geïnstalleerd en actief!")
        ok(f"Verbind via VNC Viewer: {ip}:5900")
        info("Inloggen met Pi OS gebruikersnaam en wachtwoord")
        info("VNC Viewer downloaden: https://www.realvnc.com/en/connect/download/viewer/")

    elif idx==3:
        sh("sudo systemctl start vncserver-x11-serviced 2>/dev/null || sudo systemctl start wayvnc 2>/dev/null")
        ok(f"VNC gestart — verbind via {ip}:5900")

    elif idx==4:
        sh("sudo systemctl stop vncserver-x11-serviced 2>/dev/null || sudo systemctl stop wayvnc 2>/dev/null")
        ok("VNC gestopt")

    elif idx==5:
        if not ask_yn("VNC verwijderen?","n"): info("Geannuleerd."); pause(); return
        run("sudo systemctl stop vncserver-x11-serviced 2>/dev/null","VNC stoppen")
        run("sudo systemctl disable vncserver-x11-serviced 2>/dev/null","VNC uitschakelen")
        run("sudo apt-get remove -y realvnc-vnc-server","VNC verwijderen")
        run("sudo apt-get autoremove -y","Opruimen")
        ok("VNC verwijderd")

    elif idx==6 or idx==-1:
        return

    pause()


# ════════════════════════════════════════════════════════════════════════════
# DEÏNSTALLEREN
# ════════════════════════════════════════════════════════════════════════════
def deinstall_menu():
    clr(); hdr("Software deïnstalleren", RED)

    # Status tonen
    samba_ok  = sh("dpkg -l samba 2>/dev/null | grep -c '^ii'").strip()=="1"
    nc_ok     = os.path.exists("/var/www/html/nextcloud")
    fb_ok     = bool(sh("which filebrowser 2>/dev/null"))
    ck_ok     = sh("dpkg -l cockpit 2>/dev/null | grep -c '^ii'").strip()=="1"
    desk_ok   = sh("dpkg -l lxde-core 2>/dev/null | grep -c '^ii'").strip()=="1"

    print(f"  {BLUE}Geïnstalleerde software:{R}")
    for naam,status in [("Samba",samba_ok),("Nextcloud",nc_ok),
                         ("FileBrowser",fb_ok),("Cockpit",ck_ok),
                         ("Desktop (LXDE)",desk_ok)]:
        kleur=GREEN if status else DIM
        symbool="✔" if status else "✗"
        print(f"  {kleur}{symbool}  {naam}{R}")
    print()

    idx=ask_menu([
        "Samba verwijderen",
        "Nextcloud verwijderen",
        "FileBrowser verwijderen",
        "Cockpit verwijderen",
        "Desktop (LXDE) verwijderen",
        "Samba shares verwijderen (data blijft bewaard)",
        f"{RED}Alles verwijderen — volledige software reset{R}",
        "← Terug",
    ])

    if idx==7 or idx==-1: return

    if idx==6:
        warn("DIT VERWIJDERT: Samba, Nextcloud, FileBrowser, Cockpit en Desktop.")
        warn("Data op de schijven blijft bewaard.")
        warn("Pi OS blijft intact — Pi blijft werken.")
        print()
        if not ask_yn("Zeker weten?","n"): info("Geannuleerd."); pause(); return
        if not ask_yn("Tweede bevestiging — echt alles verwijderen?","n"): info("Geannuleerd."); pause(); return
        _deinstall_samba()
        _deinstall_nextcloud()
        _deinstall_filebrowser()
        _deinstall_cockpit()
        _deinstall_desktop()
        print()
        ok("Alles verwijderd — Pi OS is schoon.")
        info("Data op externe schijven is onaangeroerd.")
        info("Voor een complete reset: flash de SD-kaart opnieuw via Raspberry Pi Imager.")
        pause(); return

    if idx==0:
        if not samba_ok: warn("Samba is niet geïnstalleerd."); pause(); return
        if not ask_yn("Samba verwijderen?","n"): info("Geannuleerd."); pause(); return
        _deinstall_samba()
    elif idx==1:
        if not nc_ok: warn("Nextcloud is niet geïnstalleerd."); pause(); return
        if not ask_yn("Nextcloud verwijderen?","n"): info("Geannuleerd."); pause(); return
        _deinstall_nextcloud()
    elif idx==2:
        if not fb_ok: warn("FileBrowser is niet geïnstalleerd."); pause(); return
        if not ask_yn("FileBrowser verwijderen?","n"): info("Geannuleerd."); pause(); return
        _deinstall_filebrowser()
    elif idx==3:
        if not ck_ok: warn("Cockpit is niet geïnstalleerd."); pause(); return
        if not ask_yn("Cockpit verwijderen?","n"): info("Geannuleerd."); pause(); return
        _deinstall_cockpit()
    elif idx==4:
        if not desk_ok: warn("Desktop is niet geïnstalleerd."); pause(); return
        if not ask_yn("Desktop verwijderen?","n"): info("Geannuleerd."); pause(); return
        _deinstall_desktop()
    elif idx==5:
        _deinstall_shares()

    pause()


def _deinstall_shares():
    shares = get_samba_shares()
    if not shares:
        warn("Geen shares gevonden."); pause(); return

    print(f"\n  {BLUE}Huidige shares:{R}\n")
    for naam,pad in shares.items():
        print(f"  {CYAN}[{naam}]{R}  →  {pad}")
    print()
    warn("Shares worden verwijderd uit de configuratie.")
    warn("Mappen en data op de schijven blijven BEWAARD.")
    print()
    if not ask_yn("Alle shares verwijderen?","n"): info("Geannuleerd."); pause(); return

    # Verwijder alle custom shares uit smb.conf
    conf = sh("cat /etc/samba/smb.conf")
    lines = conf.splitlines()
    new = []; skip = False
    system_sections = ["global","homes","printers","print$"]
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1].lower()
            skip = section not in system_sections
        if not skip:
            new.append(line)
    with open("/tmp/smb_new.conf","w") as f: f.write("\n".join(new))
    sh("sudo cp /tmp/smb_new.conf /etc/samba/smb.conf")
    subprocess.run("sudo systemctl restart smbd",shell=True)
    ok("Alle shares verwijderd — data bewaard")
    info("Gebruik Beheer → Standaard aanmaken om shares opnieuw aan te maken.")
    pause()


def _deinstall_samba():
    print()
    run("sudo systemctl stop smbd nmbd 2>/dev/null","Samba stoppen")
    run("sudo apt-get remove -y samba samba-common-bin","Samba verwijderen")
    run("sudo apt-get autoremove -y","Opruimen")
    ok("Samba verwijderd")
    info("Shares zijn weg — data op de schijf blijft bewaard.")

def _deinstall_nextcloud():
    print()
    run("sudo systemctl stop apache2 mariadb 2>/dev/null","Services stoppen")
    run("sudo rm -rf /var/www/html/nextcloud","Nextcloud verwijderen")
    run("sudo apt-get remove -y apache2 mariadb-server php* libapache2-mod-php","Pakketten verwijderen")
    run("sudo apt-get autoremove -y","Opruimen")
    ok("Nextcloud verwijderd")
    warn("Nextcloud-DATA op /mnt/opslag/nextcloud-data is BEWAARD.")
    info("Wil je de data ook verwijderen: sudo rm -rf /mnt/opslag/nextcloud-data")

def _deinstall_filebrowser():
    print()
    sh("sudo systemctl stop filebrowser 2>/dev/null")
    sh("sudo systemctl disable filebrowser 2>/dev/null")
    sh("sudo rm -f /etc/systemd/system/filebrowser.service")
    sh("sudo rm -f /usr/local/bin/filebrowser")
    sh("sudo systemctl daemon-reload")
    ok("FileBrowser verwijderd")

def _deinstall_cockpit():
    print()
    run("sudo systemctl stop cockpit 2>/dev/null","Cockpit stoppen")
    run("sudo apt-get remove -y cockpit","Cockpit verwijderen")
    run("sudo apt-get autoremove -y","Opruimen")
    ok("Cockpit verwijderd")

def _deinstall_desktop():
    print()
    run("sudo apt-get remove -y lxde-core lxde lightdm xorg","Desktop verwijderen")
    run("sudo apt-get autoremove -y","Opruimen")
    run("sudo systemctl set-default multi-user.target","Tekstmodus instellen")
    ok("Desktop verwijderd — Pi start op in tekstmodus")
    if ask_yn("Pi nu herstarten?","j"):
        sh("sudo reboot")


# ════════════════════════════════════════════════════════════════════════════
# BEHEER
# ════════════════════════════════════════════════════════════════════════════
def beheer_menu():
    while True:
        clr(); hdr("🛠  Beheer", CYAN)
        ip = get_ip()
        # Toon gemounte schijven
        mounts = get_nas_mounts()
        print(f"  {BLUE}Gemounte schijven:{R}")
        for dev,mp,fs,sz in mounts:
            used = sh(f"df -h {mp} 2>/dev/null | tail -1 | awk '{{print $3\"/\"$2\" gebruikt (\"$5\")\"}}'")
            print(f"  {GREEN}  {mp:<20} {dev:<10} {used}{R}")
        print()

        idx = ask_menu([
            "📁  Mappen beheren — aanmaken, verwijderen op SSD en Seagate",
            "🔗  Samba shares beheren — toevoegen, verwijderen, pad wijzigen",
            "☁   Nextcloud opslag — mappen koppelen aan Nextcloud",
            "👤  Gebruikers beheren — Samba en Nextcloud gebruikers",
            "💽  Schijfruimte overzicht",
            "🔌  Smart plug instellen — Hue of Tapo voor Seagate",
            "← Terug",
        ])
        if idx==0: beheer_mappen()
        elif idx==1: beheer_shares()
        elif idx==2: beheer_nextcloud_opslag()
        elif idx==3: beheer_gebruikers()
        elif idx==4: beheer_schijfruimte()
        elif idx==5: smart_plug_setup()
        elif idx==6 or idx==-1: return


def beheer_mappen():
    while True:
        clr(); hdr("📁  Mappen beheren", CYAN)
        # Toon huidige mappen op alle NAS-schijven
        mounts = get_nas_mounts()
        print(f"  {BLUE}Mappen op NAS-schijven:{R}\n")
        alle_mappen = []
        for dev,mp,fs,sz in mounts:
            print(f"  {CYAN}{mp}{R} ({dev}):")
            dirs = sh(f"find {mp} -maxdepth 1 -mindepth 1 -type d 2>/dev/null | sort")
            for d in dirs.splitlines():
                if d and 'lost+found' not in d and 'nextcloud-data' not in d:
                    grootte = sh(f"du -sh {d} 2>/dev/null | awk '{{print $1}}'")
                    naam = os.path.basename(d)
                    print(f"    {DIM}{naam:<30} {grootte}{R}")
                    alle_mappen.append(d)
            print()

        idx = ask_menu([
            "➕  Map aanmaken",
            "🗑   Map verwijderen",
            "← Terug",
        ])
        if idx==-1 or idx==2: return

        if idx==0:
            print(f"\n  {BLUE}Beschikbare locaties:{R}")
            for i,(dev,mp,fs,sz) in enumerate(mounts,1):
                print(f"  {CYAN}{i}{R}  {mp}  ({sz})")
            print(f"  {DIM}(Leeg = op alle schijven aanmaken){R}")
            print()
            keuze = ask("Kies locatie (nummer of Enter voor alle)")
            if keuze and keuze.isdigit() and 1<=int(keuze)<=len(mounts):
                gekozen = [mounts[int(keuze)-1][1]]
            elif not keuze:
                gekozen = [m[1] for m in mounts]
                info(f"Map wordt aangemaakt op: {', '.join(gekozen)}")
            else:
                warn("Ongeldig nummer."); pause(); continue

            naam = ask("Naam van de nieuwe map")
            if not naam: continue

            user = sh("logname 2>/dev/null || echo pi") or "pi"
            aangemaakt=[]; bestond_al=[]
            for mp in gekozen:
                pad = f"{mp}/{naam}"
                if os.path.exists(pad):
                    warn(f"Bestaat al: {pad}")
                    bestond_al.append(pad)
                else:
                    sh(f"sudo mkdir -p '{pad}' && sudo chown {user}:{user} '{pad}' && sudo chmod 775 '{pad}'")
                    ok(f"Aangemaakt: {pad}")
                    aangemaakt.append(pad)

            if not aangemaakt:
                warn("Alle mappen bestonden al — niets aangemaakt.")
                pause(); continue

            if ask_yn(f"Samba-share aanmaken voor {naam}?","j"):
                share_naam = ask(f"Share naam", naam)
                for pad in aangemaakt:
                    blk=(f"\n[{share_naam}]\n   comment={share_naam}\n   path={pad}\n"
                         f"   browseable=yes\n   writable=yes\n"
                         f"   valid users={user}\n   force user={user}\n")
                    subprocess.run(f"printf '{blk}' | sudo tee -a /etc/samba/smb.conf>/dev/null",shell=True)
                subprocess.run("sudo systemctl restart smbd",shell=True)
                ok(f"Samba-share [{share_naam}] aangemaakt")
                info(f"Windows: \\\\{get_ip()}\\{share_naam}")
            pause()

        elif idx==1:
            if not alle_mappen: warn("Geen mappen gevonden."); pause(); continue
            print(f"\n  {BLUE}Kies map om te verwijderen:{R}")
            for i,d in enumerate(alle_mappen,1):
                grootte = sh(f"du -sh {d} 2>/dev/null | awk '{{print $1}}'")
                print(f"  {CYAN}{i}{R}  {d}  ({grootte})")
            print()
            keuze = ask("Nummer (leeg = annuleren)")
            if not keuze or not keuze.isdigit() or int(keuze) > len(alle_mappen): continue
            pad = alle_mappen[int(keuze)-1]
            warn(f"Map verwijderen: {pad}")
            warn("DATA IN DEZE MAP WORDT PERMANENT GEWIST!")
            if not ask_yn("Zeker weten?","n"): continue
            sh(f"sudo rm -rf '{pad}'")
            ok(f"Map verwijderd: {pad}")
            # Samba share ook verwijderen?
            shares = get_samba_shares()
            sp = {v:k for k,v in shares.items()}
            share = sp.get(pad)
            if share and ask_yn(f"Samba-share [{share}] ook verwijderen?","j"):
                conf = sh("cat /etc/samba/smb.conf"); lines = conf.splitlines()
                new = []; skip = False
                for line in lines:
                    if line.strip()==f"[{share}]": skip=True
                    elif skip and line.strip().startswith("["): skip=False
                    if not skip: new.append(line)
                subprocess.run(f"printf '%s\\n' " + " ".join(f"'{l}'" for l in new) +
                               " | sudo tee /etc/samba/smb.conf>/dev/null",shell=True)
                subprocess.run("sudo systemctl restart smbd",shell=True)
                ok(f"Share [{share}] verwijderd")
            pause()


def beheer_shares():
    # Standaard NAS-structuur
    STANDAARD = [
        ("Opslag",    "/mnt/opslag",            "SSD — tijdelijke opslag"),
        ("Fotos",     "/mnt/backup/fotos",       "Seagate — foto's iPhone/Android"),
        ("Bestanden", "/mnt/backup/bestanden",   "Seagate — PC en overige bestanden"),
        ("Music",     "/mnt/backup/music",       "Seagate — muziek"),
    ]

    while True:
        clr(); hdr("🔗  Samba shares beheren", CYAN)
        shares = get_samba_shares()
        ip = get_ip()

        # Huidige shares tonen
        if shares:
            print(f"  {BLUE}Huidige shares:{R}\n")
            for naam,pad in shares.items():
                exists = os.path.exists(pad)
                kleur = GREEN if exists else RED
                status = "OK" if exists else "MAP ONTBREEKT"
                print(f"  {kleur}[{naam}]{R}  →  {pad}  {kleur}({status}){R}")
                print(f"    {DIM}Windows: \\\\{ip}\\{naam}{R}")
            print()

        # Standaard structuur tonen
        print(f"  {BLUE}Aanbevolen standaard NAS-structuur:{R}\n")
        bestaande_paden=[p.rstrip('/') for p in shares.values()]
        bestaande_namen=[n.lower() for n in shares.keys()]
        ontbreekt = []
        for naam, pad, beschr in STANDAARD:
            share_bestaat = naam.lower() in bestaande_namen or pad.rstrip('/') in bestaande_paden
            if share_bestaat:
                print(f"  {GREEN}OK  [{naam}]{R}  →  {pad}  {DIM}({beschr}){R}")
            else:
                print(f"  {YELLOW}!   [{naam}]{R}  →  {pad}  {DIM}({beschr}){R}")
                ontbreekt.append((naam, pad, beschr))
        print()

        if ontbreekt:
            info(f"{len(ontbreekt)} standaard share(s) ontbreekt/ontbreken.")
        else:
            ok("Alle standaard shares zijn aanwezig.")
        print()

        idx = ask_menu([
            f"✅  Standaard shares aanmaken ({len(ontbreekt)} ontbrekende)",
            "➕  Eigen share toevoegen",
            "🗑   Share verwijderen",
            "✏   Share pad wijzigen",
            "← Terug",
        ])
        if idx==-1 or idx==4: return

        if idx==0:
            if not ontbreekt:
                ok("Alle standaard shares zijn al aanwezig."); pause(); continue
            user = sh("logname 2>/dev/null || echo pi") or "pi"
            for naam, pad, beschr in ontbreekt:
                if not os.path.exists(pad):
                    sh(f"sudo mkdir -p \'{pad}\' && sudo chown {user}:{user} \'{pad}\' && sudo chmod 775 \'{pad}\'")
                    ok(f"Map aangemaakt: {pad}")
                blk=(f"\n[{naam}]\n   comment={beschr}\n   path={pad}\n"
                     f"   browseable=yes\n   writable=yes\n"
                     f"   valid users={user}\n   force user={user}\n")
                subprocess.run(f"printf \'{blk}\' | sudo tee -a /etc/samba/smb.conf>/dev/null",shell=True)
                ok(f"Share [{naam}] aangemaakt → {pad}")
                info(f"Windows: \\\\{ip}\\{naam}")
            subprocess.run("sudo systemctl restart smbd",shell=True)
            ok("Samba herstart — alle shares actief")
            pause()

        elif idx==1:
            naam = ask("Share naam (bijv. Videos)")
            if not naam: continue
            print(f"\n  {BLUE}Beschikbare mappen:{R}")
            mounts = get_nas_mounts()
            for i,(dev,mp,fs,sz) in enumerate(mounts,1):
                print(f"  {CYAN}{i}{R}  {mp}  ({sz})")
                dirs = sh(f"find {mp} -maxdepth 1 -mindepth 1 -type d 2>/dev/null | grep -v lost+found | sort")
                for d in dirs.splitlines():
                    print(f"     {DIM}{os.path.basename(d)}{R}")
            pad = ask(f"Volledig pad")
            if not pad: continue
            user = sh("logname 2>/dev/null || echo pi") or "pi"
            if not os.path.exists(pad):
                if ask_yn(f"Map aanmaken?","j"):
                    sh(f"sudo mkdir -p \'{pad}\' && sudo chown {user}:{user} \'{pad}\' && sudo chmod 775 \'{pad}\'")
                else: continue
            blk=(f"\n[{naam}]\n   comment={naam}\n   path={pad}\n"
                 f"   browseable=yes\n   writable=yes\n"
                 f"   valid users={user}\n   force user={user}\n")
            subprocess.run(f"printf \'{blk}\' | sudo tee -a /etc/samba/smb.conf>/dev/null",shell=True)
            subprocess.run("sudo systemctl restart smbd",shell=True)
            ok(f"Share [{naam}] aangemaakt → {pad}")
            info(f"Windows: \\\\{ip}\\{naam}")
            pause()

        elif idx==2:
            if not shares: warn("Geen shares."); pause(); continue
            share_namen = list(shares.keys())
            for i,n in enumerate(share_namen,1):
                print(f"  {CYAN}{i}{R}  [{n}]  →  {shares[n]}")
            keuze = ask("Nummer")
            if not keuze or not keuze.isdigit() or int(keuze) > len(share_namen): continue
            naam = share_namen[int(keuze)-1]
            if not ask_yn(f"Share [{naam}] verwijderen?","n"): continue
            conf = sh("cat /etc/samba/smb.conf"); lines = conf.splitlines()
            new = []; skip = False
            for line in lines:
                if line.strip()==f"[{naam}]": skip=True
                elif skip and line.strip().startswith("["): skip=False
                if not skip: new.append(line)
            with open("/tmp/smb_new.conf","w") as f_out: f_out.write("\n".join(new))
            sh("sudo cp /tmp/smb_new.conf /etc/samba/smb.conf")
            subprocess.run("sudo systemctl restart smbd",shell=True)
            ok(f"Share [{naam}] verwijderd")
            pause()

        elif idx==3:
            if not shares: warn("Geen shares."); pause(); continue
            share_namen = list(shares.keys())
            for i,n in enumerate(share_namen,1):
                print(f"  {CYAN}{i}{R}  [{n}]  →  {shares[n]}")
            keuze = ask("Nummer")
            if not keuze or not keuze.isdigit() or int(keuze) > len(share_namen): continue
            naam = share_namen[int(keuze)-1]
            nieuw_pad = ask(f"Nieuw pad voor [{naam}]", shares[naam])
            if not nieuw_pad: continue
            user = sh("logname 2>/dev/null || echo pi") or "pi"
            if not os.path.exists(nieuw_pad):
                if ask_yn(f"Map aanmaken?","j"):
                    sh(f"sudo mkdir -p \'{nieuw_pad}\' && sudo chown {user}:{user} \'{nieuw_pad}\' && sudo chmod 775 \'{nieuw_pad}\'")
            conf = sh("cat /etc/samba/smb.conf")
            conf = conf.replace(f"path = {shares[naam]}", f"path = {nieuw_pad}")
            with open("/tmp/smb_new.conf","w") as f_out: f_out.write(conf)
            sh("sudo cp /tmp/smb_new.conf /etc/samba/smb.conf")
            subprocess.run("sudo systemctl restart smbd",shell=True)
            ok(f"Share [{naam}] pad gewijzigd naar {nieuw_pad}")
            pause()


def beheer_nextcloud_opslag():
    clr(); hdr("☁   Nextcloud externe opslag", CYAN)
    if not os.path.exists("/var/www/html/nextcloud"):
        warn("Nextcloud is niet geïnstalleerd."); pause(); return

    # Toon huidige externe opslag
    huidige = sh("sudo -u www-data php /var/www/html/nextcloud/occ files_external:list 2>/dev/null")
    if huidige and "No mounts" not in huidige:
        print(f"  {BLUE}Huidige externe opslag:{R}")
        print(huidige)
        print()
    else:
        info("Nog geen externe opslag gekoppeld.")
        print()

    # Zorg dat External Storage app actief is
    sh("sudo -u www-data php /var/www/html/nextcloud/occ app:enable files_external 2>/dev/null")

    mounts = get_nas_mounts()
    idx = ask_menu([
        "➕  Map koppelen aan Nextcloud",
        "🗑   Koppeling verwijderen",
        "← Terug",
    ])
    if idx==-1 or idx==2: return

    if idx==0:
        nc_user = sh("sudo -u www-data php /var/www/html/nextcloud/occ user:list 2>/dev/null | head -5")
        info(f"Nextcloud gebruikers: {nc_user}")
        gebruiker = ask("Nextcloud gebruiker (bijv. admin)", "admin")
        map_naam = ask("Naam in Nextcloud (bijv. Fotos)")
        if not map_naam: return

        print(f"\n  {BLUE}Beschikbare paden:{R}")
        paden = []
        for dev,mp,fs,sz in mounts:
            dirs = sh(f"find {mp} -maxdepth 2 -mindepth 1 -type d 2>/dev/null | grep -v lost+found | grep -v nextcloud-data | sort")
            for d in dirs.splitlines():
                if d: paden.append(d); print(f"  {CYAN}{len(paden)}{R}  {d}")
        print()
        pad = ask("Volledig pad of nummer")
        if not pad: return
        if pad.isdigit() and int(pad) <= len(paden):
            pad = paden[int(pad)-1]

        if not os.path.exists(pad):
            if ask_yn(f"Map aanmaken?","j"):
                sh(f"sudo mkdir -p '{pad}' && sudo chown -R www-data:www-data '{pad}' && sudo chmod -R 755 '{pad}'")
            else: return
        else:
            sh(f"sudo chown -R www-data:www-data '{pad}' && sudo chmod -R 755 '{pad}'")

        r = sh(f"sudo -u www-data php /var/www/html/nextcloud/occ files_external:create "
               f"'{map_naam}' local null::null -c datadir='{pad}' --apply-to-user {gebruiker} 2>&1")
        if "created" in r.lower() or not r.strip():
            ok(f"Nextcloud map '{map_naam}' gekoppeld aan {pad}")
            sh("sudo -u www-data php /var/www/html/nextcloud/occ files:scan --all -q 2>/dev/null")
            ok("Bestanden gesynchroniseerd")
        else:
            warn(f"Resultaat: {r}")
        pause()

    elif idx==1:
        mounts_list = sh("sudo -u www-data php /var/www/html/nextcloud/occ files_external:list 2>/dev/null")
        if not mounts_list or "No mounts" in mounts_list:
            warn("Geen externe opslag gevonden."); pause(); return
        print(mounts_list)
        mount_id = ask("ID van de koppeling om te verwijderen")
        if not mount_id: return
        r = sh(f"sudo -u www-data php /var/www/html/nextcloud/occ files_external:delete {mount_id} 2>&1")
        ok(f"Koppeling {mount_id} verwijderd") if not r or "deleted" in r.lower() else warn(r)
        pause()


def beheer_gebruikers():
    while True:
        clr(); hdr("👤  Gebruikers beheren", CYAN)

        idx = ask_menu([
            "👤  Samba gebruiker toevoegen/wachtwoord wijzigen",
            "🗑   Samba gebruiker verwijderen",
            "👤  Nextcloud gebruiker aanmaken",
            "🗑   Nextcloud gebruiker verwijderen",
            "📋  Overzicht gebruikers",
            "← Terug",
        ])
        if idx==-1 or idx==5: return

        if idx==0:
            user = ask("Gebruikersnaam", "pi")
            if not user: continue
            print(f"\n  {YELLOW}Voer wachtwoord in voor {user}:{R}")
            r = subprocess.run(f"sudo smbpasswd -a {user}", shell=True)
            ok(f"Samba gebruiker {user} bijgewerkt") if r.returncode==0 else err("Mislukt")
            pause()

        elif idx==1:
            user = ask("Gebruikersnaam")
            if not user: continue
            if not ask_yn(f"Samba gebruiker {user} verwijderen?","n"): continue
            sh(f"sudo smbpasswd -x {user}")
            ok(f"Samba gebruiker {user} verwijderd")
            pause()

        elif idx==2:
            if not os.path.exists("/var/www/html/nextcloud"):
                warn("Nextcloud niet geïnstalleerd."); pause(); continue
            user = ask("Gebruikersnaam")
            if not user: continue
            r = sh(f"sudo -u www-data php /var/www/html/nextcloud/occ user:add {user} --display-name='{user}' 2>&1")
            ok(f"Nextcloud gebruiker {user} aangemaakt") if "created" in r.lower() else warn(r)
            pause()

        elif idx==3:
            if not os.path.exists("/var/www/html/nextcloud"):
                warn("Nextcloud niet geïnstalleerd."); pause(); continue
            users = sh("sudo -u www-data php /var/www/html/nextcloud/occ user:list 2>/dev/null")
            print(f"\n{users}\n")
            user = ask("Gebruikersnaam om te verwijderen")
            if not user: continue
            if not ask_yn(f"Nextcloud gebruiker {user} verwijderen?","n"): continue
            sh(f"sudo -u www-data php /var/www/html/nextcloud/occ user:delete {user}")
            ok(f"Nextcloud gebruiker {user} verwijderd")
            pause()

        elif idx==4:
            print(f"\n  {BLUE}Samba gebruikers:{R}")
            print(sh("sudo pdbedit -L 2>/dev/null | awk -F: '{print $1}'") or "  Geen")
            if os.path.exists("/var/www/html/nextcloud"):
                print(f"\n  {BLUE}Nextcloud gebruikers:{R}")
                print(sh("sudo -u www-data php /var/www/html/nextcloud/occ user:list 2>/dev/null") or "  Geen")
            pause()


def smart_plug_setup():
    clr(); hdr("🔌  Smart plug instellen", CYAN)
    CONFIG = "/home/pi/smart_plug_config.json"

    # Huidige configuratie tonen
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG) as f: cfg = json.load(f)
            t = cfg.get("type","niet geconfigureerd")
            ok(f"Huidige instelling: {t}")
            if t == "hue":
                info(f"Bridge: {cfg['hue'].get('bridge_ip','?')}")
                info(f"Plug ID: {cfg['hue'].get('plug_id','?')}")
            elif t == "tapo":
                info(f"Tapo IP: {cfg['tapo'].get('ip','?')}")
        except: warn("Configuratie onleesbaar")
    else:
        warn("Nog niet geconfigureerd")
    print()

    idx = ask_menu([
        "🔵  Philips Hue Smart plug instellen",
        "🟢  TP-Link Tapo P100/P110 instellen",
        "📋  Geen smart plug — handmatig beheer",
        "🔌  Testen (aan/uit)",
        "← Terug",
    ])
    if idx==-1 or idx==4: return

    if idx==0:
        # Auto-detecteer Hue bridge
        info("Hue Bridge zoeken...")
        result = sh("curl -s https://discovery.meethue.com 2>/dev/null")
        bridge_ip = ""
        try:
            import json as _json
            bridges = _json.loads(result)
            if bridges:
                bridge_ip = bridges[0].get("internalipaddress","")
                ok(f"Bridge gevonden: {bridge_ip}")
        except: pass
        if not bridge_ip:
            bridge_ip = ask("Bridge IP-adres")
        if not bridge_ip: return

        # API key
        info("Druk op de knop op de Hue Bridge en druk dan Enter...")
        input()
        result2 = sh(f"curl -s -X POST http://{bridge_ip}/api -d '{{\"devicetype\":\"nas_pi\"}}'")
        api_key = ""
        try:
            resp = json.loads(result2)
            if resp and "success" in resp[0]:
                api_key = resp[0]["success"]["username"]
                ok(f"API key verkregen: {api_key[:20]}...")
        except: pass
        if not api_key:
            api_key = ask("API key (handmatig)")
        if not api_key: return

        # Detecteer pluggen
        import urllib.request
        try:
            r = urllib.request.urlopen(f"http://{bridge_ip}/api/{api_key}/lights", timeout=3)
            lights = json.loads(r.read())
            plugs = [(id, d["name"]) for id, d in lights.items()
                     if "plug" in d.get("type","").lower() or
                        "plug" in d.get("productname","").lower() or
                        "On/Off" in d.get("type","")]
            if plugs:
                print(f"\n  {BLUE}Gevonden pluggen:{R}")
                for pid, naam in plugs:
                    print(f"  {CYAN}{pid}{R}  {naam}")
                plug_id = ask("Plug ID", plugs[0][0])
            else:
                plug_id = ask("Plug ID (niet automatisch gevonden)")
        except:
            plug_id = ask("Plug ID")
        if not plug_id: return

        cfg = {
            "type": "hue",
            "hue": {"bridge_ip": bridge_ip, "api_key": api_key, "plug_id": plug_id},
            "tapo": {"ip": "", "email": "", "password": ""},
            "seagate_mount": "/mnt/backup"
        }
        with open(CONFIG, 'w') as f: json.dump(cfg, f, indent=2)
        ok("Hue configuratie opgeslagen")

    elif idx==1:
        info("Tapo P100/P110 instellen")
        info("Installeer eerst de library:")
        print(f"  {DIM}pip3 install plugp100 --break-system-packages{R}")
        tapo_ip = ask("Tapo IP-adres (te vinden in TP-Link Tapo app)")
        email = ask("Tapo account e-mail")
        pwd = ask("Tapo account wachtwoord")
        if not tapo_ip or not email or not pwd: return

        # Installeer library
        run("pip3 install plugp100 --break-system-packages", "plugp100 installeren")

        cfg = {
            "type": "tapo",
            "hue": {"bridge_ip": "", "api_key": "", "plug_id": ""},
            "tapo": {"ip": tapo_ip, "email": email, "password": pwd},
            "seagate_mount": "/mnt/backup"
        }
        with open(CONFIG, 'w') as f: json.dump(cfg, f, indent=2)
        ok("Tapo configuratie opgeslagen")

    elif idx==2:
        cfg = {"type": "none", "seagate_mount": "/mnt/backup"}
        with open(CONFIG, 'w') as f: json.dump(cfg, f, indent=2)
        ok("Ingesteld op handmatig beheer — geen smart plug")

    elif idx==3:
        info("Seagate Web Controller — bereikbaar via browser op elk apparaat")
        info(f"URL: http://{get_ip()}:8765")
        idx2=ask_menu([
            "▶  Starten (eenmalig)",
            "⚙️  Installeren als service (start automatisch)",
            "⏹  Stoppen",
            "🗑  Service verwijderen",
            "← Terug",
        ])
        if idx2==0:
            subprocess.Popen(["sudo","python3","/home/pi/seagate_web.py"])
            ok(f"Web controller gestart op http://{get_ip()}:8765")
        elif idx2==1:
            run("sudo cp /home/pi/seagate-web.service /etc/systemd/system/","Service installeren")
            run("sudo systemctl daemon-reload","Daemon herladen")
            run("sudo systemctl enable --now seagate-web","Service inschakelen")
            ok(f"Web controller actief op http://{get_ip()}:8765")
        elif idx2==2:
            sh("sudo systemctl stop seagate-web 2>/dev/null")
            ok("Web controller gestopt")
        elif idx2==3:
            sh("sudo systemctl stop seagate-web 2>/dev/null")
            sh("sudo systemctl disable seagate-web 2>/dev/null")
            sh("sudo rm -f /etc/systemd/system/seagate-web.service")
            sh("sudo systemctl daemon-reload")
            ok("Service verwijderd")
        pause()

    elif idx==4:
        info("Seagate aanzetten...")
        r = sh("python3 /home/pi/smart_plug.py aan")
        print(f"  {r}")
        if ask_yn("Seagate uitzetten?","j"):
            r = sh("python3 /home/pi/smart_plug.py uit")
            print(f"  {r}")
        pause()


def beheer_schijfruimte():
    clr(); hdr("💽  Schijfruimte overzicht", CYAN)
    mounts = get_nas_mounts()
    if not mounts:
        warn("Geen NAS-schijven gemount."); pause(); return

    for dev,mp,fs,sz in mounts:
        print(f"\n  {CYAN}{BOLD}{mp}{R}  ({dev}  {fs}  {sz})")
        df = sh(f"df -h {mp} 2>/dev/null | tail -1")
        if df:
            parts = df.split()
            if len(parts)>=5:
                used_pct = parts[4].replace('%','')
                color = RED if int(used_pct)>85 else YELLOW if int(used_pct)>60 else GREEN
                print(f"  Gebruikt: {color}{parts[2]} ({parts[4]}){R}  Vrij: {GREEN}{parts[3]}{R}  Totaal: {parts[1]}")
        # Top 5 grootste mappen
        print(f"\n  {DIM}Grootste mappen:{R}")
        top = sh(f"du -sh {mp}/* 2>/dev/null | sort -rh | head -5")
        for line in top.splitlines():
            if 'lost+found' not in line:
                print(f"    {DIM}{line}{R}")

    print()
    info(f"SD-kaart: {sh('df -h / | tail -1 | awk \"{print $3\\\"/\\\"$2\\\" gebruikt (\\\"$5\\\")\\\"}')} ")
    pause()


def diagnose():
    while True:
        clr(); hdr("Diagnose", MAGENTA)
        idx=ask_menu([
            "lsblk — schijfoverzicht",
            "df -h — schijfgebruik",
            "cat /etc/fstab — mountconfiguratie",
            "Actieve mounts",
            "Schijftemperatuur (hddtemp)",
            "Samba status",
            "Netwerk status",
            "← Terug",
        ])
        clr()
        if   idx==0: os.system("lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT")
        elif idx==1: os.system("df -h")
        elif idx==2: os.system("cat /etc/fstab")
        elif idx==3: os.system("mount | grep /mnt/")
        elif idx==4: os.system("sudo hddtemp /dev/sda 2>&1 || echo 'sudo apt install hddtemp'")
        elif idx==5: os.system("sudo systemctl status smbd --no-pager")
        elif idx==6: os.system("nmcli general && echo && ip addr show | grep inet")
        elif idx==7 or idx==-1: return
        print(); pause()

# ════════════════════════════════════════════════════════════════════════════
# HOOFDMENU
# ════════════════════════════════════════════════════════════════════════════

def show_help():
    clr(); hdr("❓  NAS Installer — Help", CYAN)
    secties = [
        ("1  🚀  Initiële setup",
         ["Alles in één keer: netwerk, SSH, update, schijf koppelen en NAS-software installeren.",
          "Ideaal voor een verse Pi. Stelt alles automatisch in met minimale vragen."]),
        ("2  💾  Schijf beheer",
         ["Koppelen    — toont alle schijven met grootte en status · waarschuwing als Seagate uit staat",
          "            Zet Seagate EERST aan via Beheer → Smart plug voordat je koppelt",
          "Wisselen    — testschijf vervangen door definitieve schijf",
          "Verwijderen — schijfkoppeling netjes verwijderen (data blijft bewaard)",
          "Formatteren — schijf wissen en nieuw bestandssysteem aanmaken",
          "Diagnose    — lsblk, df, fstab en mount-overzicht"]),
        ("3  ⚙️   NAS-software",
         ["Methode A: Samba + Cockpit — netwerkschijf voor Windows/iPhone/Android",
          "Methode B: Nextcloud — eigen cloud met apps en foto-back-up",
          "Beide: volledige installatie van A en B"]),
        ("4  🌐  FileBrowser",
         ["Webbeheer voor bestanden via browser op http://[IP]:8080",
          "Installeren, starten, stoppen",
          "Inschakelen bij opstarten — start automatisch na reboot",
          "Uitschakelen bij opstarten — start niet meer automatisch",
          "Wachtwoord resetten"]),
        ("5  ⚙️   Cockpit",
         ["Webbeheer voor de Pi via browser op http://[IP]:9090",
          "CPU, geheugen, schijven, services en updates beheren",
          "Installeren, starten, stoppen",
          "Inschakelen/uitschakelen bij opstarten",
          "Login met Pi OS gebruikersnaam en wachtwoord"]),
        ("5  🖥️   Desktop & VNC",
         ["Desktop installeren (LXDE + Tkinter) voor grafische installer",
          "VNC installeren voor grafische omgeving via Windows (RealVNC Viewer)",
          "VNC starten, stoppen, verwijderen"]),
        ("6  💾  Configuratie export/import",
         ["Exporteer alle instellingen naar 4 locaties (SSD, 8TB, bootfs, /home/pi)",
          "Importeer na herinstallatie of bij Pi-wissel",
          "Synchroniseer alle kopieën"]),
        ("7  🗑   Deïnstalleren",
         ["Verwijder Samba, Nextcloud, FileBrowser, Cockpit of Desktop afzonderlijk",
          "Samba shares verwijderen — alleen share-definities, data blijft bewaard",
          "Of verwijder alles — Pi OS blijft intact, data op schijven blijft bewaard"]),
        ("8  🛠   Beheer",
         ["Standaard NAS-structuur aanmaken: Opslag (SSD), Fotos, Bestanden, Music (Seagate)",
          "Toont welke mappen/shares al bestaan en welke ontbreken",
          "Eigen map/share toevoegen of verwijderen",
          "Nextcloud externe opslag koppelen en verwijderen",
          "Samba- en Nextcloud-gebruikers beheren",
          "Schijfruimte overzicht per schijf"]),
        ("9  🌐  Netwerk",  ["WiFi instellen via nmcli"]),
        ("10  🔑  SSH",
         ["SSH inschakelen, SSH-sleutel controleren",
          "Wachtwoordlogin uitschakelen (na sleutel instellen)"]),
        ("11  🔄  Systeem bijwerken", ["apt update + upgrade"]),
        ("12  ⬆   Scripts bijwerken",
         ["Kopieert nieuwe scripts van /boot/firmware/ naar /home/pi/",
          "Bootfs wordt ook bijgewerkt zodat auto-update correct werkt"]),
        ("13  🔬  Diagnose",
         ["lsblk, df, fstab, mounts, temperatuur, Samba-status"]),
        ("14  ❓  Help", ["Dit overzicht"]),
        ("15  🚪  Afsluiten", ["Sluit de installer af"]),
    ]
    for titel, regels in secties:
        print(f"  {CYAN}{BOLD}{titel}{R}")
        for r in regels:
            print(f"    {DIM}• {r}{R}")
        print()
    print(f"  {YELLOW}Tip: Ctrl+C annuleert altijd en gaat terug naar het menu.{R}")
    print(f"  {YELLOW}Tip: Enter zonder invoer bevestigt de standaardkeuze [tussen haken].{R}")
    pause()

def main_menu():
    while True:
        clr()
        # Status balk
        ip=get_ip(); conn=is_connected(); ssh_ok=ssh_enabled()
        print(f"\n  {CYAN}{BOLD}🍓 Raspberry Pi NAS Installer  v{NAS_VERSION}{R}")
        print(f"  {DIM}{'─'*40}{R}")
        conn_str=f"{GREEN}✔ Verbonden ({ip}){R}" if conn else f"{YELLOW}✗ Niet verbonden{R}"
        ssh_str =f"{GREEN}✔ Aan{R}" if ssh_ok else f"{YELLOW}✗ Uit{R}"
        print(f"  Netwerk: {conn_str}   SSH: {ssh_str}")
        drives=sh("lsblk -o NAME,SIZE -rn | grep -E '^sd' | head -3")
        if drives:
            drive_txt=" · ".join(f"/dev/{l.split()[0]}({l.split()[1]})" for l in drives.splitlines())
            print(f"  Schijven: {YELLOW}{drive_txt}{R}")
        # Rechtencheck
        problemen = check_rechten()
        if problemen:
            print(f"  {RED}⚠  Schrijfrechten onjuist op: {', '.join(problemen)}{R}")
            print(f"  {YELLOW}   Kies Schijf beheer → Rechten herstellen om dit op te lossen.{R}")
        print()

        idx=ask_menu([
            f"{GREEN}{BOLD}🚀  Volledige initiële setup (alles in één){R}",
            "💾  Schijf beheer",
            "⚙️   NAS-software installeren of herinstalleren",
            "🌐  FileBrowser",
            "⚙️   Cockpit — webbeheer Pi",
            "🖥️   Desktop installeren / verwijderen",
            "💾  Configuratie export/import",
            f"{RED}🗑   Software deïnstalleren{R}",
            "🛠   Beheer — mappen, shares, Nextcloud, gebruikers",
            "🌐  Netwerk instellen (WiFi)",
            "🔑  SSH instellen",
            "🔄  Systeem bijwerken",
            "⬆   Scripts bijwerken vanuit SD-kaart",
            "🔬  Diagnose",
            "❓  Help",
            "🚪  Afsluiten",
        ])
        if   idx==0: initiele_setup()
        elif idx==1: schijf_menu()
        elif idx==2:
            cfg=nas_config()
            if cfg: nas_install(cfg)
        elif idx==3: filebrowser_menu()
        elif idx==4: cockpit_menu()
        elif idx==5: desktop_menu()
        elif idx==6:
            try:
                import importlib.util
                spec=importlib.util.spec_from_file_location("nas_config_mod","/home/pi/nas_config.py")
                mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
                mod.config_menu()
            except Exception as e:
                err(f"nas_config.py niet gevonden: {e}")
                info("Kopieer nas_config.py naar /home/pi/ via het upload-script.")
                pause()
        elif idx==7: deinstall_menu()
        elif idx==8: beheer_menu()
        elif idx==9: stap_netwerk()
        elif idx==10: stap_ssh()
        elif idx==11: stap_update()
        elif idx==12: update_scripts()
        elif idx==13: diagnose()
        elif idx==14: show_help()
        elif idx==15 or idx==-1:
            clr()
            print(f"\n  {GREEN}Tot ziens!{R}\n")
            sys.exit(0)

# ────────────────────────────────────────────────────────────────────────────
if __name__=="__main__":
    if os.geteuid()!=0:
        print(f"\n{RED}⚠  Start met: sudo python3 nas_installer_cli.py{R}\n")
        sys.exit(1)
    try:
        main_menu()
    except KeyboardInterrupt:
        print(f"\n\n  {YELLOW}Onderbroken. Tot ziens!{R}\n")
        sys.exit(0)
