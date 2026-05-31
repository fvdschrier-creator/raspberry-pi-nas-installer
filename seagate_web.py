#!/usr/bin/env python3
# Raspberry Pi NAS Installer v1.0.0
# Seagate Web Controller — mini webserver voor aan/uitzetten Seagate
# Start: sudo python3 /home/pi/seagate_web.py
# Bereikbaar via: http://[PI_IP]:8765

import http.server, json, os, sys, subprocess, threading

PORT = 8765
PLUG_CONFIG = "/home/pi/smart_plug_config.json"

HTML = """<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Seagate — Pi NAS</title>
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
  <h1>🔌 Seagate</h1>
  <p class="subtitle">Pi NAS v1.0.0</p>
  <div class="status laden" id="status">⏳ Status laden...</div>
  <button class="btn btn-aan" id="btn-aan" onclick="actie('aan')" disabled>🔌 Aanzetten</button>
  <button class="btn btn-uit" id="btn-uit" onclick="actie('uit')" disabled>⏹ Uitzetten</button>
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
      el.textContent = '✅ Seagate AAN' + (d.gemount ? ' — gemount' : ' — niet gemount');
    } else {
      el.className = 'status uit';
      el.textContent = '⏹ Seagate UIT';
    }
    document.getElementById('btn-aan').disabled = d.aan;
    document.getElementById('btn-uit').disabled = !d.aan;
    document.getElementById('info').textContent = d.info || '';
  } catch(e) {
    document.getElementById('status').textContent = '❓ Status onbekend';
  }
}

async function actie(cmd) {
  document.getElementById('status').className = 'status laden';
  document.getElementById('status').textContent = cmd === 'aan' ? '⏳ Aanzetten...' : '⏳ Uitzetten...';
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
    def log_message(self, *args): pass  # Geen logging

    def do_GET(self):
        if self.path == '/':
            self.reply(200, 'text/html', HTML.encode())

        elif self.path == '/status':
            try:
                sys.path.insert(0, '/home/pi')
                from smart_plug import plug_status
                aan = plug_status()
                gemount = os.path.ismount('/mnt/backup')
                data = {'aan': bool(aan), 'gemount': gemount,
                        'info': '/mnt/backup gemount' if gemount else ''}
            except Exception as e:
                data = {'aan': False, 'gemount': False, 'info': str(e)}
            self.reply(200, 'application/json', json.dumps(data).encode())

        elif self.path == '/actie/aan':
            def bg():
                try:
                    sys.path.insert(0, '/home/pi')
                    from smart_plug import plug_aan
                    plug_aan()
                    import time; time.sleep(12)
                    subprocess.run('sudo mount -a', shell=True)
                except: pass
            threading.Thread(target=bg, daemon=True).start()
            self.reply(200, 'application/json', b'{"ok":true}')

        elif self.path == '/actie/uit':
            def bg():
                try:
                    subprocess.run('sudo umount /mnt/backup 2>/dev/null', shell=True)
                    import time; time.sleep(1)
                    sys.path.insert(0, '/home/pi')
                    from smart_plug import plug_uit
                    plug_uit()
                except: pass
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
        print("Configureer eerst de smart plug via: nas → Beheer → Smart plug instellen")
        sys.exit(1)
    print(f"Seagate Web Controller gestart op poort {PORT}")
    print(f"Open in browser: http://[PI_IP]:{PORT}")
    http.server.HTTPServer(('', PORT), Handler).serve_forever()
