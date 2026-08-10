#!/usr/bin/env python3
# Raspberry Pi NAS Installer v1.0.0
# Seagate Web Controller - mini webserver voor aan/uitzetten Seagate
# Draait normaal als systemd-service (User=pi) - zie seagate-web.service.
# Handmatig testen: python3 /home/pi/seagate_web.py (ZONDER sudo - anders
# wordt het logbestand eigendom van root en kan de service daarna niet
# meer schrijven, wat de service blijvend laat crashen met Permission denied)
# Bereikbaar via: http://[PI_IP]:8765

import http.server, json, os, sys, subprocess, threading, logging
from logging.handlers import TimedRotatingFileHandler

# -- Logging setup ---------------------------------------------
def _setup_logging():
    log_map = "/home/pi/logs"
    log_pad = f"{log_map}/seagate.log"
    logger = logging.getLogger("seagate_web")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s [%(levelname)-7s] %(message)s",
                                datefmt="%Y-%m-%d %H:%M:%S")
        try:
            os.makedirs(log_map, exist_ok=True)
            fh = TimedRotatingFileHandler(log_pad, when="midnight",
                                          backupCount=30, encoding="utf-8")
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        except PermissionError:
            # Logbestand bestaat al maar is eigendom van een andere
            # gebruiker (bv. root, van een eerdere handmatige sudo-run).
            # Niet crashen op iets dat alleen logging betreft -- de
            # service moet blijven draaien, ook zonder bestandslog.
            sys.stderr.write(
                f"WAARSCHUWING: kan niet schrijven naar {log_pad} "
                f"(verkeerd bestandseigendom). Logt alleen naar console.\n"
                f"Fix: sudo chown pi:pi {log_pad}\n")
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        ch.setLevel(logging.WARNING)
        logger.addHandler(ch)
    return logger

log = _setup_logging()

PORT = 8765
PLUG_CONFIG = "/home/pi/smart_plug_config.json"

HTML = """<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Seagate - Pi NAS</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #1a1b2e;
    color: #e2e8f0;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .card {
    background: #2d3561;
    border-radius: 16px;
    padding: 32px;
    width: 320px;
    text-align: center;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  }
  h1 { font-size: 22px; margin-bottom: 6px; color: #7c9ef0; }
  .subtitle { font-size: 13px; color: #718096; margin-bottom: 24px; }
  .status {
    font-size: 16px;
    font-weight: 600;
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 24px;
  }
  .status.aan { background: #1a3a2a; color: #48bb78; }
  .status.uit { background: #3a2a1e; color: #ed8936; }
  .status.laden { background: #2a2a3a; color: #7c9ef0; }
  .btn {
    display: block;
    width: 100%;
    padding: 16px;
    border: none;
    border-radius: 10px;
    font-size: 18px;
    font-weight: 700;
    cursor: pointer;
    margin-bottom: 12px;
    transition: opacity 0.2s;
  }
  .btn:active { opacity: 0.8; }
  .btn-aan { background: #48bb78; color: #1a1b2e; }
  .btn-uit { background: #4a5568; color: #e2e8f0; }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .footer { font-size: 11px; color: #4a5568; margin-top: 16px; }
</style>
</head>
<body>
<div class="card">
  <h1>[PLUG] Seagate</h1>
  <p class="subtitle">Pi NAS v1.0.0</p>
  <div class="status laden" id="status">[...] Status laden...</div>
  <button class="btn btn-aan" id="btn-aan" onclick="actie('aan')" disabled>[PLUG] Aanzetten</button>
  <button class="btn btn-uit" id="btn-uit" onclick="actie('uit')" disabled>[STOP] Uitzetten</button>
  <p class="footer" id="info"></p>
</div>
<script>
async function status() {
  try {
    const r = await fetch('/status');
    const d = await r.json();
    const el = document.getElementById('status');
    if (d.aan) {
      el.className = 'status aan';
      el.textContent = '[OK] Seagate AAN' + (d.gemount ? ' - gemount' : ' - niet gemount');
    } else {
      el.className = 'status uit';
      el.textContent = '[STOP] Seagate UIT';
    }
    document.getElementById('btn-aan').disabled = d.aan;
    document.getElementById('btn-uit').disabled = !d.aan;
    document.getElementById('info').textContent = d.info || '';
  } catch(e) {
    document.getElementById('status').textContent = '[?] Status onbekend';
  }
}

async function actie(cmd) {
  document.getElementById('status').className = 'status laden';
  document.getElementById('status').textContent = cmd === 'aan' ? '[...] Aanzetten...' : '[...] Uitzetten...';
  document.getElementById('btn-aan').disabled = true;
  document.getElementById('btn-uit').disabled = true;
  try {
    await fetch('/actie/' + cmd);
    setTimeout(status, cmd === 'aan' ? 14000 : 3000);
  } catch(e) {}
}

status();
setInterval(status, 10000);
</script>
</body>
</html>"""

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Alleen fouten loggen, geen routine requests
        if args and str(args[1]) not in ('200', '304'):
            log.warning(f"HTTP {args[1]} - {self.path}")

    def do_GET(self):
        if self.path == '/':
            self.reply(200, 'text/html', HTML.encode())

        elif self.path == '/status':
            try:
                sys.path.insert(0, '/home/pi')
                from smart_plug import plug_status
                aan = bool(plug_status())
                gemount = os.path.ismount('/mnt/backup')
                data = {'aan': aan, 'gemount': gemount}
            except Exception as e:
                data = {'aan': False, 'gemount': False, 'info': str(e)}
            self.reply(200, 'application/json', json.dumps(data).encode())

        elif self.path == '/actie/aan':
            def bg():
                log.info("Seagate AAN gestart")
                try:
                    sys.path.insert(0, '/home/pi')
                    from smart_plug import plug_aan
                    plug_ok = plug_aan()
                    if not plug_ok:
                        log.error("plug_aan() gaf False terug - stekker is "
                                  "NIET aangezet. Zie smart_plug.log voor de "
                                  "echte oorzaak (config/credentials/netwerk).")
                        # Toch doorgaan met mount-poging is hier nutteloos
                        # als de schijf geen stroom heeft, dus stoppen.
                        return
                    log.info("Smart plug aangezet")
                    import time
                    # Wacht tot Seagate filesystem klaar is via blkid UUID check
                    seagate_klaar = False
                    for poging in range(45):
                        time.sleep(1)
                        result = subprocess.run(
                            'blkid | grep UW_BACKUP_HDD_UUID',
                            shell=True, capture_output=True, text=True)
                        if result.stdout.strip():
                            seagate_klaar = True
                            log.info(f"Seagate filesystem klaar na {poging+1} sec")
                            break
                    if not seagate_klaar:
                        log.warning("Seagate niet gevonden na 45 sec - toch mount proberen")
                    time.sleep(1)
                    # Mount en Samba herstarten
                    r_mount = subprocess.run('sudo mount -a', shell=True,
                                             capture_output=True, text=True)
                    if r_mount.returncode != 0:
                        log.error(f"mount -a mislukt: {r_mount.stderr.strip()}")
                    else:
                        log.info("mount -a geslaagd")
                    r_smbd = subprocess.run('sudo systemctl restart smbd', shell=True,
                                            capture_output=True, text=True)
                    if r_smbd.returncode != 0:
                        log.error(f"smbd restart mislukt: {r_smbd.stderr.strip()}")
                    else:
                        log.info("smbd herstart geslaagd")
                    # Wacht max 20 sec tot /mnt/backup echt gemount is
                    for wacht in range(20):
                        time.sleep(1)
                        if os.path.ismount('/mnt/backup'):
                            log.info(f"/mnt/backup gemount na {wacht+1} sec")
                            break
                    else:
                        log.error("/mnt/backup NIET gemount na 20 sec wachten")
                except Exception as e:
                    log.error(f"Fout bij Seagate aanzetten: {e}", exc_info=True)
            threading.Thread(target=bg, daemon=True).start()
            self.reply(200, 'application/json', b'{"ok":true}')

        elif self.path == '/actie/uit':
            def bg():
                log.info("Seagate UIT gestart")
                try:
                    r = subprocess.run('sudo umount /mnt/backup', shell=True,
                                       capture_output=True, text=True)
                    if r.returncode != 0:
                        log.warning(f"umount: {r.stderr.strip() or 'al ontkoppeld'}")
                    else:
                        log.info("/mnt/backup ontkoppeld")
                    import time; time.sleep(1)
                    sys.path.insert(0, '/home/pi')
                    from smart_plug import plug_uit
                    plug_uit()
                    log.info("Smart plug uitgezet")
                except Exception as e:
                    log.error(f"Fout bij Seagate uitzetten: {e}", exc_info=True)
            threading.Thread(target=bg, daemon=True).start()
            self.reply(200, 'application/json', b'{"ok":true}')

        else:
            self.reply(404, 'text/plain', b'Not found')

    def reply(self, code, ctype, body):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

if __name__ == '__main__':
    if not os.path.exists(PLUG_CONFIG):
        print("FOUT: smart_plug_config.json niet gevonden.")
        print("Configureer eerst de smart plug via: nas -> Beheer -> Smart plug instellen")
        sys.exit(1)
    print(f"Seagate Web Controller gestart op poort {PORT}")
    log.info(f"Seagate Web Controller gestart op poort {PORT}")
    print(f"Open in browser: http://[PI_IP]:{PORT}")
    http.server.HTTPServer(('', PORT), Handler).serve_forever()
