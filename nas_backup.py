#!/usr/bin/env python3
# Raspberry Pi NAS Installer v1.0.0
"""
Pi NAS Backup Script
rsync van /mnt/opslag naar /mnt/backup
Start: sudo python3 /home/pi/nas_backup.py
Of via welkomstmenu optie 5
"""
import os, sys, subprocess, time, datetime, json

# ── Kleuren ──────────────────────────────────────────────────────────────────
R="\033[0m"; BOLD="\033[1m"; DIM="\033[2m"
CYAN="\033[96m"; GREEN="\033[92m"; YELLOW="\033[93m"
RED="\033[91m"; BLUE="\033[94m"; WHITE="\033[97m"
MAGENTA="\033[95m"

SRC        = "/mnt/opslag"
DST        = "/mnt/backup"
LOG_FILE   = "/home/pi/backup.log"
STATUS_FILE= "/home/pi/backup_status.json"
CONFIG_FILE= "/home/pi/backup_config.json"
WARN_DAYS  = 7

def load_config():
    """Laad backup-configuratie, gebruik standaardwaarden als niet aanwezig."""
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
            return cfg.get("src", SRC), cfg.get("dst", DST)
    except:
        return SRC, DST

def save_config(src, dst):
    """Sla backup-configuratie op."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump({"src": src, "dst": dst}, f, indent=2)
        return True
    except:
        return False

def clr():   os.system("clear")
def ok(m):   print(f"  {GREEN}✔  {m}{R}")
def warn(m): print(f"  {YELLOW}⚠  {m}{R}")
def err(m):  print(f"  {RED}✗  {m}{R}")
def info(m): print(f"  {CYAN}ℹ  {m}{R}")
def dim(m):  print(f"  {DIM}{m}{R}")

PLUG_CONFIG = "/home/pi/smart_plug_config.json"

def seagate_plug_aan():
    try:
        sys.path.insert(0, '/home/pi')
        from smart_plug import seagate_aan as _aan
        if _aan(): ok("Seagate aangezet en gemount"); return True
        warn("Seagate aanzetten mislukt"); return False
    except: return False

def seagate_plug_uit():
    try:
        sys.path.insert(0, '/home/pi')
        from smart_plug import seagate_uit as _uit
        if _uit(): ok("Seagate uitgezet"); return True
        return False
    except: return False
    try:
        r=subprocess.run(cmd,shell=True,capture_output=True,text=True)
        return r.stdout.strip()
    except: return ""

def ask_yn(prompt, default="j"):
    opts="[J/n]" if default.lower()=="j" else "[j/N]"
    try:
        val=input(f"  {WHITE}{prompt} {opts}: {R}").strip().lower()
        if not val: return default.lower()=="j"
        return val in ("j","ja","y","yes")
    except (KeyboardInterrupt, EOFError):
        print(); return False

def pause():
    try: input(f"\n  {DIM}Druk Enter om door te gaan...{R}")
    except KeyboardInterrupt: print()

def hdr(title, color=CYAN):
    w=60
    print(f"\n{color}{BOLD}{'═'*w}{R}")
    print(f"{color}{BOLD}  {title}{R}")
    print(f"{color}{BOLD}{'═'*w}{R}\n")

def format_size(bytes_val):
    for unit in ['B','KB','MB','GB','TB']:
        if bytes_val < 1024: return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"

def format_duration(seconds):
    if seconds < 60: return f"{int(seconds)} seconden"
    if seconds < 3600: return f"{int(seconds//60)} minuten {int(seconds%60)} sec"
    return f"{int(seconds//3600)} uur {int((seconds%3600)//60)} min"

# ── Status laden/opslaan ──────────────────────────────────────────────────────
def load_status():
    try:
        with open(STATUS_FILE) as f:
            return json.load(f)
    except: return {}

def save_status(data):
    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except: pass

def log_backup(status, duration, files_copied, size_copied, error=None):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "datum":        now,
        "status":       status,
        "duur":         format_duration(duration),
        "bestanden":    files_copied,
        "grootte":      format_size(size_copied),
        "fout":         error or ""
    }
    # JSON status
    data = load_status()
    if "geschiedenis" not in data:
        data["geschiedenis"] = []
    data["laatste"] = entry
    data["geschiedenis"].insert(0, entry)
    data["geschiedenis"] = data["geschiedenis"][:20]  # max 20 bewaren
    save_status(data)
    # Tekstlog
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(f"\n[{now}] {status.upper()}\n")
            f.write(f"  Duur: {entry['duur']}\n")
            f.write(f"  Bestanden: {files_copied}\n")
            f.write(f"  Grootte: {entry['grootte']}\n")
            if error: f.write(f"  Fout: {error}\n")
    except: pass

# ── Controles ─────────────────────────────────────────────────────────────────
def check_mounted(path):
    return sh(f"mountpoint -q {path} && echo yes") == "yes"

def get_disk_info(path):
    out = sh(f"df -B1 {path} 2>/dev/null | tail -1")
    if not out: return None
    parts = out.split()
    if len(parts) < 4: return None
    return {
        "total": int(parts[1]),
        "used":  int(parts[2]),
        "avail": int(parts[3]),
        "pct":   parts[4]
    }

def count_source():
    """Tel bestanden en grootte in bronmap."""
    out = sh(f"du -sb {SRC} 2>/dev/null | cut -f1")
    size = int(out) if out.isdigit() else 0
    count = sh(f"find {SRC} -type f 2>/dev/null | wc -l")
    files = int(count) if count.isdigit() else 0
    return files, size

# ── Backup uitvoeren ──────────────────────────────────────────────────────────
def run_backup():
    clr()
    hdr("💾  Backup starten", GREEN)
    SRC, DST = load_config()

    # Controle 1: bronmap
    if not check_mounted(SRC):
        err(f"Bronmap {SRC} is niet gemount!")
        warn("Start de NAS-installer en koppel de SSD eerst.")
        pause(); return

    # Controle 2: backup-schijf
    if not check_mounted(DST):
        warn(f"Backup-schijf {DST} is niet gemount.")
        # Probeer via Hue stekker aan te zetten
        if os.path.exists(PLUG_CONFIG):
            info("Seagate aanzetten via Hue stekker...")
            seagate_plug_aan()
        info("Automatisch mounten...")
        os.system("sudo mount -a")
        time.sleep(3)
        if not check_mounted(DST):
            err(f"Mount mislukt — {DST} niet beschikbaar.")
            warn("Controleer of de Seagate aangesloten en ingeschakeld is.")
            print()
            if not ask_yn("Opnieuw proberen?", "j"):
                pause(); return
            os.system("sudo mount -a")
            time.sleep(3)
            if not check_mounted(DST):
                err("Nog steeds niet gemount — backup geannuleerd.")
                pause(); return
        ok(f"{DST} gemount!")

    # Info tonen
    src_info = get_disk_info(SRC)
    dst_info = get_disk_info(DST)

    print(f"  {BLUE}── Bron: {SRC} ──{R}")
    if src_info:
        print(f"  Gebruikt: {format_size(src_info['used'])} van {format_size(src_info['total'])}")

    print(f"\n  {BLUE}── Doel: {DST} ──{R}")
    if dst_info:
        print(f"  Beschikbaar: {format_size(dst_info['avail'])} van {format_size(dst_info['total'])}")
        # Waarschuwing als backup-schijf bijna vol
        pct = int(dst_info['pct'].replace('%',''))
        if pct > 90:
            warn(f"Backup-schijf is {dst_info['pct']} vol!")

    # Controleer of er genoeg ruimte is
    if src_info and dst_info:
        if src_info['used'] > dst_info['avail']:
            err("Niet genoeg ruimte op backup-schijf!")
            err(f"Nodig: {format_size(src_info['used'])}  Beschikbaar: {format_size(dst_info['avail'])}")
            pause(); return

    # Bestanden tellen
    print(f"\n  {CYAN}Bestanden tellen...{R}", end="", flush=True)
    files, size = count_source()
    print(f"\r  Klaar.{' '*20}")
    info(f"Te kopiëren: {files:,} bestanden ({format_size(size)})")
    info(f"Alleen nieuwe en gewijzigde bestanden worden gekopieerd (rsync)")

    # Laatste backup tonen
    status = load_status()
    if "laatste" in status:
        l = status["laatste"]
        print(f"\n  Laatste backup: {YELLOW}{l['datum']}{R}  ({l['status']}  {l['bestanden']} bestanden)")

    print()
    if not ask_yn("Backup starten?", "j"):
        info("Geannuleerd.")
        pause(); return

    # Backup uitvoeren
    print(f"\n  {CYAN}Backup bezig...{R}")
    print(f"  {DIM}Dit kan even duren afhankelijk van de hoeveelheid data.{R}\n")

    start = time.time()
    files_copied = 0
    size_copied  = 0

    cmd = [
        "sudo", "rsync",
        "-av",                    # archive + verbose
        "--progress",             # voortgang per bestand
        "--stats",                # eindstatistieken
        "--human-readable",       # leesbare groottes
        "--delete",               # verwijder op doel wat niet meer in bron zit
        "--exclude=lost+found",   # systeemmappen overslaan
        f"{SRC}/",
        f"{DST}/nas-backup/"
    ]

    # Doelmap aanmaken
    os.makedirs(f"{DST}/nas-backup", exist_ok=True)

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True)

        stats_lines = []
        for line in proc.stdout:
            line = line.rstrip()
            if not line: continue
            # Statistieken bewaren
            if any(k in line for k in ["Number of files", "Total file size",
                                        "Total transferred", "Literal data"]):
                stats_lines.append(line)
                # Bestanden tellen
                if "Number of regular files transferred" in line:
                    try:
                        files_copied = int(line.split(":")[-1].strip().replace(",",""))
                    except: pass
                if "Total transferred file size" in line:
                    try:
                        parts = line.split(":")[-1].strip().split()
                        val = float(parts[0].replace(",",""))
                        unit = parts[1] if len(parts)>1 else "B"
                        multipliers={"B":1,"K":1024,"M":1024**2,"G":1024**3,"T":1024**4}
                        for k,v in multipliers.items():
                            if unit.upper().startswith(k):
                                size_copied=int(val*v); break
                    except: pass
            # Voortgang tonen (niet te veel)
            elif line.startswith("sending") or "to-check" in line:
                print(f"  {DIM}{line[:70]}{R}", end="\r", flush=True)
            elif not line.startswith(" ") and "/" in line:
                print(f"  {DIM}→ {line[:65]}{R}", end="\r", flush=True)

        proc.wait()
        duration = time.time() - start
        print(" " * 75, end="\r")  # regel leegmaken

        if proc.returncode == 0:
            # Succes
            print(f"\n{GREEN}{BOLD}{'═'*60}{R}")
            print(f"{GREEN}{BOLD}  ✅  BACKUP GESLAAGD!{R}")
            print(f"{GREEN}{BOLD}{'═'*60}{R}\n")
            ok(f"Duur:              {format_duration(duration)}")
            ok(f"Bestanden:         {files_copied:,}")
            ok(f"Gekopieerd:        {format_size(size_copied)}")
            if dst_info:
                dst_after = get_disk_info(DST)
                if dst_after:
                    ok(f"Vrije ruimte:      {format_size(dst_after['avail'])}")
            print()
            info(f"Backup staat in:   {DST}/nas-backup/")
            log_backup("geslaagd", duration, files_copied, size_copied)
            # Seagate uitzetten via Hue als geconfigureerd
            if os.path.exists(PLUG_CONFIG):
                print()
                if ask_yn("Seagate uitzetten?","j"):
                    os.system(f"sudo umount {DST} 2>/dev/null")
                    seagate_plug_uit()
        else:
            err(f"Backup mislukt (exitcode {proc.returncode})")
            log_backup("mislukt", duration, files_copied, size_copied,
                       f"exitcode {proc.returncode}")

    except KeyboardInterrupt:
        duration = time.time() - start
        print(f"\n\n  {YELLOW}Backup onderbroken na {format_duration(duration)}{R}")
        log_backup("onderbroken", duration, files_copied, size_copied, "handmatig onderbroken")

    pause()

# ── Laatste backup tonen ──────────────────────────────────────────────────────
def toon_laatste():
    clr()
    hdr("📋  Backup geschiedenis", BLUE)
    data = load_status()
    if not data or "geschiedenis" not in data:
        warn("Nog geen backups uitgevoerd.")
        pause(); return

    print(f"  {'Datum':<22} {'Status':<12} {'Duur':<18} {'Bestanden':<12} {'Grootte'}")
    print(f"  {'-'*80}")
    for entry in data["geschiedenis"]:
        status_col = GREEN if entry['status']=='geslaagd' else \
                     YELLOW if entry['status']=='onderbroken' else RED
        print(f"  {entry['datum']:<22} "
              f"{status_col}{entry['status']:<12}{R} "
              f"{entry['duur']:<18} "
              f"{str(entry['bestanden']):<12} "
              f"{entry['grootte']}")
    pause()

# ── Backup log bekijken ───────────────────────────────────────────────────────
def toon_log():
    clr()
    hdr("📄  Backup log", BLUE)
    if not os.path.exists(LOG_FILE):
        warn("Nog geen logbestand — nog geen backups uitgevoerd.")
        pause(); return
    os.system(f"tail -50 {LOG_FILE}")
    pause()

# ── Schijfruimte overzicht ────────────────────────────────────────────────────
def toon_ruimte():
    clr()
    hdr("💽  Schijfruimte overzicht", BLUE)
    SRC, DST = load_config()

    for label, path in [(f"Bron ({SRC})", SRC),
                         (f"Doel ({DST})", DST)]:
        print(f"  {BLUE}{BOLD}{label}{R}")
        if check_mounted(path):
            info = get_disk_info(path)
            if info:
                pct = int(info['pct'].replace('%',''))
                bar_filled = int(pct / 5)
                bar = "█" * bar_filled + "░" * (20 - bar_filled)
                color = GREEN if pct < 70 else YELLOW if pct < 90 else RED
                print(f"  [{color}{bar}{R}] {pct}%")
                print(f"  Gebruikt:    {format_size(info['used'])}")
                print(f"  Beschikbaar: {format_size(info['avail'])}")
                print(f"  Totaal:      {format_size(info['total'])}")
        else:
            print(f"  {YELLOW}Niet gemount{R}")
        print()

    # Backup leeftijd
    data = load_status()
    if "laatste" in data:
        l = data["laatste"]
        try:
            last_dt = datetime.datetime.strptime(l['datum'], "%Y-%m-%d %H:%M:%S")
            age = (datetime.datetime.now() - last_dt).days
            if age >= WARN_DAYS:
                warn(f"Laatste backup is {age} dagen geleden — maak een nieuwe backup!")
            else:
                ok(f"Laatste backup: {l['datum']} ({age} dagen geleden)")
        except: pass
    else:
        warn("Nog geen backup gemaakt!")

    pause()

# ── Backup status voor welkomstmenu ──────────────────────────────────────────
def status_regel():
    """Geeft één regel terug voor in het welkomstmenu."""
    data = load_status()
    if "laatste" not in data:
        return f"\033[93mNog geen backup gemaakt\033[0m"
    l = data["laatste"]
    try:
        last_dt = datetime.datetime.strptime(l['datum'], "%Y-%m-%d %H:%M:%S")
        age = (datetime.datetime.now() - last_dt).days
        if age >= WARN_DAYS:
            return f"\033[93m{l['datum']}  ⚠  {age} dagen geleden!\033[0m"
        return f"\033[92m{l['datum']}  ({age} dagen geleden)\033[0m"
    except:
        return l['datum']

# ── Hoofdmenu ─────────────────────────────────────────────────────────────────
def backup_config_menu():
    clr(); hdr("⚙️  Backup configuratie", MAGENTA)
    src, dst = load_config()

    print(f"  {BLUE}Huidige instelling:{R}")
    info(f"Bron (wat gebackupt wordt): {src}")
    info(f"Doel (waar naartoe):        {dst}")
    print()
    print(f"  {BLUE}Beschikbare mappen onder /mnt/:{R}")
    mounts = sh("df -h | grep /mnt/ | awk '{print $6, $4}'")
    if mounts:
        for line in mounts.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                print(f"  {GREEN}✔{R}  {parts[0]:<25} {parts[1]} vrij")
    else:
        warn("Geen mappen gevonden — zijn de schijven gemount?")
    print()
    print(f"  {CYAN}1{R}  Bron aanpassen (nu: {src})")
    print(f"  {CYAN}2{R}  Doel aanpassen  (nu: {dst})")
    print(f"  {CYAN}3{R}  Standaard herstellen (/mnt/opslag → /mnt/backup)")
    print(f"  {CYAN}4{R}  ← Terug\n")

    try: keuze = input(f"  {WHITE}Keuze (1-4): {R}").strip()
    except KeyboardInterrupt: print(); return

    if keuze == "1":
        try:
            nieuwe = input(f"  {WHITE}Nieuwe bron [{src}]: {R}").strip()
        except KeyboardInterrupt: print(); return
        if nieuwe and os.path.isabs(nieuwe):
            save_config(nieuwe, dst)
            ok(f"Bron ingesteld: {nieuwe}")
        elif nieuwe:
            warn(f"Ongeldig pad: {nieuwe} — moet beginnen met /")
        else: info("Ongewijzigd.")
    elif keuze == "2":
        try:
            nieuwe = input(f"  {WHITE}Nieuw doel [{dst}]: {R}").strip()
        except KeyboardInterrupt: print(); return
        if nieuwe and os.path.isabs(nieuwe):
            save_config(src, nieuwe)
            ok(f"Doel ingesteld: {nieuwe}")
        elif nieuwe:
            warn(f"Ongeldig pad: {nieuwe} — moet beginnen met /")
        else: info("Ongewijzigd.")
    elif keuze == "3":
        save_config("/mnt/opslag", "/mnt/backup")
        ok("Standaard hersteld: /mnt/opslag → /mnt/backup")
    pause()


def backup_menu():
    while True:
        clr(); hdr("💾  Backup beheer", MAGENTA)
        src, dst = load_config()
        src_ok = check_mounted(src)
        dst_ok = check_mounted(dst)

        print(f"  {BLUE}Configuratie:{R}")
        print(f"  Bron: {src:<28} "
              f"{'✅ Gemount' if src_ok else RED+'❌ Niet gemount'+R}")
        print(f"  Doel: {dst:<28} "
              f"{'✅ Gemount' if dst_ok else YELLOW+'⚠  Niet gemount (schijf aanzetten)'+R}")
        data = load_status()
        if "laatste" in data:
            print(f"  Laatste backup:  {status_regel()}")
        else:
            print(f"  Laatste backup:  {YELLOW}Nog geen backup gemaakt{R}")
        print()

        print(f"  {CYAN}{BOLD}1{R}  💾  Backup starten")
        print(f"     {DIM}Van {src} naar {dst}{R}\n")
        print(f"  {CYAN}{BOLD}2{R}  ⚙️  Configuratie — bron en doel aanpassen\n")
        print(f"  {CYAN}{BOLD}3{R}  📋  Backup geschiedenis\n")
        print(f"  {CYAN}{BOLD}4{R}  📄  Backup log bekijken\n")
        print(f"  {CYAN}{BOLD}5{R}  💽  Schijfruimte overzicht\n")
        print(f"  {CYAN}{BOLD}6{R}  ← Terug\n")

        try: keuze = input(f"  {WHITE}Keuze (1-6): {R}").strip()
        except KeyboardInterrupt: print(); return

        if   keuze=="1": run_backup()
        elif keuze=="2": backup_config_menu()
        elif keuze=="3": toon_laatste()
        elif keuze=="4": toon_log()
        elif keuze=="5": toon_ruimte()
        elif keuze in ("6",""): return


if __name__=="__main__":
    if os.geteuid()!=0:
        print(f"\n{RED}⚠  Start met: sudo python3 /home/pi/nas_backup.py{R}\n")
        sys.exit(1)
    backup_menu()
