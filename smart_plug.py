#!/usr/bin/env python3
# Raspberry Pi NAS Installer v1.0.0
"""
Pi NAS Smart Plug Controller
Ondersteunt: Philips Hue Smart plug en TP-Link Tapo P100/P110
Configuratie: /home/pi/smart_plug_config.json
"""
import os, json, time, subprocess

CONFIG_FILE = "/home/pi/smart_plug_config.json"

def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except:
        return None

def save_config(cfg):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=2)
        return True
    except:
        return False

# ── Hue ──────────────────────────────────────────────────────────────────────
def hue_set(aan: bool) -> bool:
    try:
        cfg = load_config()
        if not cfg or cfg.get("type") != "hue": return False
        h = cfg["hue"]
        import urllib.request
        data = json.dumps({"on": aan}).encode()
        req = urllib.request.Request(
            f"http://{h['bridge_ip']}/api/{h['api_key']}/lights/{h['plug_id']}/state",
            data=data, method="PUT")
        urllib.request.urlopen(req, timeout=3)
        return True
    except: return False

def hue_status() -> bool:
    try:
        cfg = load_config()
        if not cfg or cfg.get("type") != "hue": return None
        h = cfg["hue"]
        import urllib.request
        r = urllib.request.urlopen(
            f"http://{h['bridge_ip']}/api/{h['api_key']}/lights/{h['plug_id']}", timeout=3)
        d = json.loads(r.read())
        return d["state"]["on"]
    except: return None

def hue_detect(bridge_ip: str, api_key: str) -> list:
    """Detecteer alle Hue pluggen op de bridge."""
    try:
        import urllib.request
        r = urllib.request.urlopen(f"http://{bridge_ip}/api/{api_key}/lights", timeout=3)
        lights = json.loads(r.read())
        plugs = [(id, d["name"]) for id, d in lights.items()
                 if "plug" in d.get("type","").lower() or "plug" in d.get("productname","").lower()]
        return plugs
    except: return []

# ── Tapo ─────────────────────────────────────────────────────────────────────
def tapo_set(aan: bool) -> bool:
    try:
        cfg = load_config()
        if not cfg or cfg.get("type") != "tapo": return False
        t = cfg["tapo"]
        # Controleer of plugp100 geinstalleerd is
        result = subprocess.run(
            ["python3", "-c",
             f"from plugp100.api.plug_device import PlugDevice; "
             f"from plugp100.credentials import AuthCredential; "
             f"import asyncio; "
             f"async def run(): "
             f"  c = AuthCredential('{t['email']}', '{t['password']}'); "
             f"  d = PlugDevice('{t['ip']}', 80, c); "
             f"  await d.login(); "
             f"  await d.{'turn_on' if aan else 'turn_off'}(); "
             f"asyncio.run(run())"],
            capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except: return False

def tapo_install() -> bool:
    """Installeer plugp100 library."""
    r = subprocess.run(
        ["pip3", "install", "plugp100", "--break-system-packages"],
        capture_output=True, text=True)
    return r.returncode == 0

# ── Universele interface ──────────────────────────────────────────────────────
def plug_aan() -> bool:
    cfg = load_config()
    if not cfg: return False
    if cfg.get("type") == "hue": return hue_set(True)
    if cfg.get("type") == "tapo": return tapo_set(True)
    return False

def plug_uit() -> bool:
    cfg = load_config()
    if not cfg: return False
    if cfg.get("type") == "hue": return hue_set(False)
    if cfg.get("type") == "tapo": return tapo_set(False)
    return False

def plug_status() -> bool:
    cfg = load_config()
    if not cfg: return None
    if cfg.get("type") == "hue": return hue_status()
    return None

def seagate_aan(mount="/mnt/backup") -> bool:
    """Seagate aanzetten en mounten."""
    plug_aan()
    time.sleep(5)
    subprocess.run("sudo mount -a", shell=True)
    return os.path.ismount(mount)

def seagate_uit(mount="/mnt/backup") -> bool:
    """Seagate unmounten en uitzetten."""
    subprocess.run(f"sudo umount {mount} 2>/dev/null", shell=True)
    time.sleep(1)
    return plug_uit()

def is_geconfigureerd() -> bool:
    return os.path.exists(CONFIG_FILE) and load_config() is not None

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Gebruik: smart_plug.py [aan|uit|status]")
        sys.exit(1)
    cmd = sys.argv[1].lower()
    if cmd == "aan":
        print("Seagate aanzetten...")
        ok = seagate_aan()
        print("OK - gemount" if ok else "FOUT - niet gemount")
    elif cmd == "uit":
        print("Seagate uitzetten...")
        ok = seagate_uit()
        print("OK" if ok else "FOUT")
    elif cmd == "status":
        s = plug_status()
        print(f"Stekker: {'aan' if s else 'uit' if s is not None else 'onbekend'}")
        print(f"Seagate gemount: {'ja' if os.path.ismount('/mnt/backup') else 'nee'}")
