#!/usr/bin/env python3
# Raspberry Pi NAS Installer v1.0.0
"""
Pi NAS Smart Plug Controller
Ondersteunt: Philips Hue Smart plug en TP-Link Tapo P100/P110
Configuratie: /home/pi/smart_plug_config.json
"""
import os, json, time, subprocess, logging

CONFIG_FILE = "/home/pi/smart_plug_config.json"

# Eigen logger - schrijft naar /home/pi/logs/smart_plug.log zodat stille
# fouten (config ontbreekt, plug onbereikbaar, verkeerd wachtwoord, etc.)
# voor het eerst echt zichtbaar worden. Voorheen gaven alle except-blokken
# alleen "False" terug zonder enige aanwijzing waarom.
def _setup_logging():
    log_map = "/home/pi/logs"
    try:
        os.makedirs(log_map, exist_ok=True)
    except Exception:
        pass
    logger = logging.getLogger("smart_plug")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s [%(levelname)-7s] %(message)s",
                                datefmt="%Y-%m-%d %H:%M:%S")
        try:
            fh = logging.FileHandler(f"{log_map}/smart_plug.log", encoding="utf-8")
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        except PermissionError:
            import sys
            sys.stderr.write(
                f"WAARSCHUWING: kan niet schrijven naar {log_map}/smart_plug.log "
                f"(verkeerd bestandseigendom, bv. van eerdere sudo-run).\n"
                f"Fix: sudo chown pi:pi {log_map}/smart_plug.log\n")
        except Exception:
            pass
    return logger

log = _setup_logging()

def load_config():
    if not os.path.exists(CONFIG_FILE):
        log.error(f"Config-bestand ontbreekt: {CONFIG_FILE}")
        return None
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        if not cfg.get("type"):
            log.error("Config-bestand mist 'type' veld (hue/tapo)")
        return cfg
    except Exception as e:
        log.error(f"Config-bestand kon niet gelezen worden: {e}")
        return None

def save_config(cfg):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=2)
        return True
    except Exception as e:
        log.error(f"Config opslaan mislukt: {e}")
        return False

# -- Hue ----------------------------------------------------------------------

def hue_discover_bridge_ip(api_key=None, timeout=5):
    """Zoekt het huidige IP van de Hue Bridge op, los van DHCP-wissels.

    Gebruikt eerst Philips' officiele discovery-service (meethue.com),
    die altijd het actuele lokale IP teruggeeft. Als dat niet werkt
    (geen internet, dienst onbereikbaar), valt terug op een lokale
    netwerkscan via SSDP (UPnP-discovery die de Bridge zelf uitstuurt).

    Geeft het gevonden IP terug, of None als niets gevonden is.
    """
    import urllib.request

    # Methode 1: Philips' officiele discovery-endpoint
    try:
        r = urllib.request.urlopen(
            "https://discovery.meethue.com/", timeout=timeout)
        data = json.loads(r.read())
        if data:
            ip = data[0].get("internalipaddress")
            if ip:
                log.info(f"Bridge gevonden via meethue.com discovery: {ip}")
                return ip
    except Exception as e:
        log.warning(f"meethue.com discovery mislukt: {e}")

    # Methode 2: lokale SSDP-discovery (werkt ook zonder internet)
    try:
        import socket
        msg = (
            "M-SEARCH * HTTP/1.1\r\n"
            "HOST: 239.255.255.250:1900\r\n"
            'MAN: "ssdp:discover"\r\n'
            "MX: 3\r\n"
            "ST: urn:schemas-upnp-org:device:basic:1\r\n\r\n"
        ).encode()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)
        sock.sendto(msg, ("239.255.255.250", 1900))
        start = time.time()
        while time.time() - start < timeout:
            try:
                resp, addr = sock.recvfrom(4096)
                text = resp.decode(errors="ignore")
                if "IpBridge" in text or "hue" in text.lower():
                    log.info(f"Bridge gevonden via SSDP: {addr[0]}")
                    sock.close()
                    return addr[0]
            except socket.timeout:
                break
        sock.close()
    except Exception as e:
        log.warning(f"SSDP discovery mislukt: {e}")

    log.error("Hue Bridge niet gevonden via discovery (meethue.com en SSDP)")
    return None


def _hue_bridge_reageert(ip, timeout=3):
    """Snelle check: reageert dit IP op de Hue API (zonder auth nodig)?"""
    try:
        import urllib.request
        urllib.request.urlopen(f"http://{ip}/api/0/config", timeout=timeout)
        return True
    except Exception:
        # Een 4xx/JSON-foutrespons betekent ook dat de Bridge wel
        # reageert (alleen de auth/route klopt niet) - dat is genoeg
        # bevestiging dat dit IP een actieve Hue Bridge is.
        return False


def _hue_zelfherstel_ip(cfg):
    """Als het opgeslagen bridge_ip niet meer reageert, zoek het nieuwe
    IP op via discovery en sla dat automatisch op in de config - zodat
    een volgende DHCP-wissel niet meer handmatig gefixt hoeft te worden.
    Geeft het (eventueel bijgewerkte) IP terug, of None bij falen.
    """
    h = cfg.get("hue", {})
    huidig_ip = h.get("bridge_ip")

    if huidig_ip and _hue_bridge_reageert(huidig_ip):
        return huidig_ip  # nog steeds correct, niets te doen

    log.warning(f"bridge_ip '{huidig_ip}' reageert niet meer - "
                f"start automatische herdetectie...")
    nieuw_ip = hue_discover_bridge_ip()
    if not nieuw_ip:
        log.error("Automatische herdetectie van de Hue Bridge is mislukt")
        return None

    if nieuw_ip != huidig_ip:
        log.info(f"Bridge IP gewijzigd: '{huidig_ip}' -> '{nieuw_ip}' "
                  f"- config wordt automatisch bijgewerkt")
        cfg["hue"]["bridge_ip"] = nieuw_ip
        save_config(cfg)
    return nieuw_ip


def hue_set(aan: bool) -> bool:
    cfg = load_config()
    if not cfg or cfg.get("type") != "hue":
        log.error("hue_set: geen geldige Hue-configuratie aanwezig")
        return False
    try:
        h = cfg["hue"]
        bridge_ip = _hue_zelfherstel_ip(cfg)
        if not bridge_ip:
            log.error("hue_set: geen bereikbare Hue Bridge gevonden")
            return False
        import urllib.request
        data = json.dumps({"on": aan}).encode()
        req = urllib.request.Request(
            f"http://{bridge_ip}/api/{h['api_key']}/lights/{h['plug_id']}/state",
            data=data, method="PUT")
        resp = urllib.request.urlopen(req, timeout=5)
        body = resp.read().decode()
        # Hue API geeft bij een foute api_key/plug_id WEL HTTP 200 terug,
        # maar met een foutmelding in de JSON body - dat moet je checken,
        # anders denk je dat het gelukt is terwijl de plug niet reageerde.
        result = json.loads(body)
        errors = [r["error"]["description"] for r in result if "error" in r]
        if errors:
            log.error(f"Hue API foutmelding: {'; '.join(errors)}")
            return False
        log.info(f"Hue plug {'aan' if aan else 'uit'} gezet (bridge {bridge_ip})")
        return True
    except KeyError as e:
        log.error(f"hue_set: ontbrekend configveld {e}")
        return False
    except Exception as e:
        log.error(f"hue_set mislukt: {e}")
        return False

def hue_status() -> bool:
    cfg = load_config()
    if not cfg or cfg.get("type") != "hue":
        return None
    try:
        h = cfg["hue"]
        bridge_ip = _hue_zelfherstel_ip(cfg)
        if not bridge_ip:
            log.error("hue_status: geen bereikbare Hue Bridge gevonden")
            return None
        import urllib.request
        r = urllib.request.urlopen(
            f"http://{bridge_ip}/api/{h['api_key']}/lights/{h['plug_id']}", timeout=5)
        d = json.loads(r.read())
        return d["state"]["on"]
    except Exception as e:
        log.error(f"hue_status mislukt: {e}")
        return None

def hue_detect(bridge_ip: str, api_key: str) -> list:
    """Detecteer alle Hue pluggen op de bridge."""
    try:
        import urllib.request
        r = urllib.request.urlopen(f"http://{bridge_ip}/api/{api_key}/lights", timeout=5)
        lights = json.loads(r.read())
        plugs = [(id, d["name"]) for id, d in lights.items()
                 if "plug" in d.get("type","").lower() or "plug" in d.get("productname","").lower()]
        return plugs
    except Exception as e:
        log.error(f"hue_detect mislukt: {e}")
        return []

# -- Tapo ---------------------------------------------------------------------
def tapo_set(aan: bool) -> bool:
    cfg = load_config()
    if not cfg or cfg.get("type") != "tapo":
        log.error("tapo_set: geen geldige Tapo-configuratie aanwezig")
        return False
    try:
        t = cfg["tapo"]
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
            capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "onbekende fout").strip()
            log.error(f"tapo_set mislukt (returncode {result.returncode}): {err}")
            return False
        log.info(f"Tapo plug {'aan' if aan else 'uit'} gezet ({t.get('ip')})")
        return True
    except KeyError as e:
        log.error(f"tapo_set: ontbrekend configveld {e}")
        return False
    except subprocess.TimeoutExpired:
        log.error("tapo_set: timeout - plug niet bereikbaar binnen 15 sec")
        return False
    except Exception as e:
        log.error(f"tapo_set mislukt: {e}")
        return False

def tapo_status() -> bool:
    """Vraagt de werkelijke aan/uit-status van de Tapo plug op.
    Dit ontbrak voorheen volledig - plug_status() gaf altijd None
    terug voor Tapo, waardoor het menu de plug als 'UIT' liet zien
    zelfs als hij echt aanstond."""
    cfg = load_config()
    if not cfg or cfg.get("type") != "tapo":
        return None
    try:
        t = cfg["tapo"]
        result = subprocess.run(
            ["python3", "-c",
             f"from plugp100.api.plug_device import PlugDevice; "
             f"from plugp100.credentials import AuthCredential; "
             f"import asyncio; "
             f"async def run(): "
             f"  c = AuthCredential('{t['email']}', '{t['password']}'); "
             f"  d = PlugDevice('{t['ip']}', 80, c); "
             f"  await d.login(); "
             f"  info = await d.get_device_info(); "
             f"  print('ON' if info.device_on else 'OFF'); "
             f"asyncio.run(run())"],
            capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "onbekende fout").strip()
            log.error(f"tapo_status mislukt (returncode {result.returncode}): {err}")
            return None
        out = result.stdout.strip()
        if "ON" in out:
            return True
        if "OFF" in out:
            return False
        log.error(f"tapo_status: onverwachte output: {out!r}")
        return None
    except KeyError as e:
        log.error(f"tapo_status: ontbrekend configveld {e}")
        return None
    except subprocess.TimeoutExpired:
        log.error("tapo_status: timeout - plug niet bereikbaar binnen 10 sec")
        return None
    except Exception as e:
        log.error(f"tapo_status mislukt: {e}")
        return None

def tapo_install() -> bool:
    """Installeer plugp100 library."""
    r = subprocess.run(
        ["pip3", "install", "plugp100", "--break-system-packages"],
        capture_output=True, text=True)
    if r.returncode != 0:
        log.error(f"plugp100 installeren mislukt: {r.stderr.strip()}")
    return r.returncode == 0

# -- Universele interface ------------------------------------------------------
def plug_aan() -> bool:
    cfg = load_config()
    if not cfg:
        log.error("plug_aan: geen configuratie geladen, stekker NIET aangezet")
        return False
    if cfg.get("type") == "hue": return hue_set(True)
    if cfg.get("type") == "tapo": return tapo_set(True)
    log.error(f"plug_aan: onbekend plug-type '{cfg.get('type')}'")
    return False

def plug_uit() -> bool:
    cfg = load_config()
    if not cfg:
        log.error("plug_uit: geen configuratie geladen")
        return False
    if cfg.get("type") == "hue": return hue_set(False)
    if cfg.get("type") == "tapo": return tapo_set(False)
    log.error(f"plug_uit: onbekend plug-type '{cfg.get('type')}'")
    return False

def plug_status() -> bool:
    cfg = load_config()
    if not cfg: return None
    if cfg.get("type") == "hue": return hue_status()
    if cfg.get("type") == "tapo": return tapo_status()
    return None

def seagate_aan(mount="/mnt/backup") -> bool:
    """Seagate aanzetten en mounten."""
    ok = plug_aan()
    if not ok:
        log.error("seagate_aan: plug_aan() gaf False terug, sla mount over")
        return False
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
        print("OK - gemount" if ok else "FOUT - niet gemount (zie /home/pi/logs/smart_plug.log)")
    elif cmd == "uit":
        print("Seagate uitzetten...")
        ok = seagate_uit()
        print("OK" if ok else "FOUT (zie /home/pi/logs/smart_plug.log)")
    elif cmd == "status":
        s = plug_status()
        print(f"Stekker: {'aan' if s else 'uit' if s is not None else 'onbekend'}")
        print(f"Seagate gemount: {'ja' if os.path.ismount('/mnt/backup') else 'nee'}")
