#!/usr/bin/env python3
# Raspberry Pi NAS Installer v1.0.0
NAS_VERSION = "1.0.0"
"""
Raspberry Pi NAS Installer — Grafische versie (Tkinter)
Vereist: desktop + sudo python3 /home/pi/nas_installer.py
Identiek aan CLI-versie maar met grafische interface.
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess, threading, os, sys, time, glob

# ── Kleuren ──────────────────────────────────────────────────────────────────
BG="#0f172a"; FG="#f1f5f9"; ACCENT="#3b82f6"; GREEN="#22c55e"
RED="#ef4444"; WARN="#f97316"; PANEL="#1e293b"; PANEL2="#334155"
BTN="#1e293b"; YELLOW="#eab308"; TEAL="#0f766e"; MAGENTA="#7c3aed"
DIM="#64748b"

# ── Helpers ───────────────────────────────────────────────────────────────────
def sh(cmd):
    try: return subprocess.run(cmd,shell=True,capture_output=True,text=True).stdout.strip()
    except: return ""

def sh_rc(cmd):
    try: return subprocess.run(cmd,shell=True).returncode
    except: return 1

def get_ip():
    for ip in sh("hostname -I").split():
        if ip.startswith(("192.","10.","172.")): return ip
    return sh("hostname -I").split()[0] if sh("hostname -I") else "niet verbonden"

def is_connected(): return "connected" in sh("nmcli -t -f STATE general 2>/dev/null").lower()
def ssh_enabled(): return sh("sudo systemctl is-enabled ssh 2>/dev/null").strip()=="enabled"

def get_wifi_nets():
    raw=sh("nmcli -t -f SSID,SIGNAL,SECURITY dev wifi list 2>/dev/null")
    nets,seen=[],set()
    for line in raw.splitlines():
        p=line.split(":")
        if len(p)>=2 and p[0].strip() and p[0].strip() not in seen:
            seen.add(p[0].strip())
            nets.append((p[0].strip(),p[1] if len(p)>1 else "?",p[2] if len(p)>2 else ""))
    return sorted(nets,key=lambda x:-int(x[1]) if x[1].isdigit() else 0)

def fix_dev(dev):
    dev=dev.strip()
    return "/dev/"+dev if dev and not dev.startswith("/") else dev

def get_nas_mounts():
    result=[]
    for line in sh("lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT -rn").splitlines():
        p=line.split()
        if len(p)>=4 and "/mnt/" in p[3]:
            result.append((f"/dev/{p[0]}",p[3],p[2] if len(p)>2 else "?",p[1]))
    return result

def get_samba_shares():
    shares={}; cur=None
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
    return "/dev/sdb"

def suggest_mount(dev=None):
    """Stel een mountpunt voor op basis van schijfgrootte."""
    existing={m[1] for m in get_nas_mounts()}
    # Bepaal grootte als apparaat bekend is
    if dev:
        size_str=sh(f"lsblk -dn -o SIZE {dev} 2>/dev/null").strip()
        # Grote schijf (>= 500G of T) → backup
        if size_str and ('T' in size_str or
            ('G' in size_str and float(size_str.replace('G','').strip()) >= 500)):
            for s in ["",2,3]:
                mp=f"/mnt/backup{'' if not s else s}"
                if mp not in existing: return mp
        # Kleine schijf → opslag
        else:
            for s in ["",2,3,4,5]:
                mp=f"/mnt/opslag{'' if not s else s}"
                if mp not in existing: return mp
    # Fallback
    for s in ["",2,3,4,5]:
        mp=f"/mnt/opslag{'' if not s else s}"
        if mp not in existing: return mp
    return "/mnt/opslag2"

def suggest_share(dev=None):
    """Stel een share-naam voor op basis van schijfgrootte."""
    if dev:
        size_str=sh(f"lsblk -dn -o SIZE {dev} 2>/dev/null").strip()
        if size_str and ('T' in size_str or
            ('G' in size_str and float(size_str.replace('G','').strip()) >= 500)):
            return "Backup"
    return "Opslag"

def fs_format_cmds(dev,fs):
    if fs=="exfat": return [("exfatprogs","sudo apt-get install -y exfatprogs"),
                             ("Formatteren exFAT",f"sudo wipefs -a {dev} && sudo mkfs.exfat {dev}")]
    if fs=="ntfs":  return [("ntfs-3g","sudo apt-get install -y ntfs-3g"),
                             ("Formatteren NTFS",f"sudo wipefs -a {dev} && sudo mkfs.ntfs -f {dev}")]
    return [("Partitietabel wissen",f"sudo wipefs -a {dev}"),
            ("Formatteren ext4",f"sudo mkfs.ext4 -F {dev}"),
            ("Kernel update",f"sudo partprobe {dev} 2>/dev/null; sudo udevadm settle")]

def fs_fstab(uuid,mp,fs):
    if fs=="exfat": return f"UUID={uuid}  {mp}  exfat  defaults,nofail,uid=1000,gid=1000,umask=0022  0  0"
    if fs=="ntfs":  return f"UUID={uuid}  {mp}  ntfs-3g  defaults,nofail,uid=1000,gid=1000,umask=0022  0  0"
    return f"UUID={uuid}  {mp}  ext4  defaults,nofail  0  2"


def create_desktop_shortcuts():
    """Maak desktop snelkoppelingen aan als ze nog niet bestaan of gewijzigd zijn."""
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
    for path, content in shortcuts.items():
        if os.path.exists(path):
            with open(path) as f:
                if content.strip() == f.read().strip():
                    continue
        with open(path, "w") as f:
            f.write(content)
        subprocess.run(f"chmod +x {path} && chown pi:pi {path} && gio set {path} metadata::trusted true 2>/dev/null", shell=True)

def update_rechten_service():
    import glob as _glob
    mounts=[m[1] for m in get_nas_mounts()]
    if not mounts: return
    user=sh("logname 2>/dev/null || echo pi") or "pi"
    paths=" ".join(mounts)
    cmd=f"chown -R {user}:{user} {paths} && chmod -R 775 {paths}"
    for mp in mounts:
        for nc in _glob.glob(f"{mp}/nextcloud-data"):
            if os.path.exists(nc):
                cmd+=f" && chown -R www-data:www-data {nc} && chmod -R 755 {nc}"
    svc=f"""[Unit]
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
    with open("/tmp/nas-rechten.service","w") as f: f.write(svc)
    subprocess.run("sudo cp /tmp/nas-rechten.service /etc/systemd/system/nas-rechten.service",shell=True)
    subprocess.run("sudo systemctl daemon-reload && sudo systemctl enable nas-rechten.service && sudo systemctl start nas-rechten.service",shell=True)

# ════════════════════════════════════════════════════════════════════════════
class NASInstaller(tk.Tk):
    PAGES=["Welkom","Netwerk","SSH","Systeem bijwerken","Schijf beheer",
           "NAS-methode","Instellingen","Installatie","Gereed","🚀 Initiële setup",
           "🌐 FileBrowser","🖥️ Desktop & VNC","🔑 SSH-sleutel","🗑 Deïnstalleren",
           "💾 Configuratie","⬆ Scripts bijwerken","🔬 Diagnose","📋 Systeem info","❓ Help","🛠 Beheer","⚙️ Cockpit"]

    def __init__(self):
        super().__init__()
        self.title("🍓 Raspberry Pi NAS Installer")
        self.geometry("1020x810"); self.minsize(920,700); self.configure(bg=BG)
        # Vars
        self.wifi_ssid=tk.StringVar(); self.wifi_pass=tk.StringVar()
        self.method=tk.StringVar(value="A")
        self.share_name=tk.StringVar(value="Opslag"); self.samba_user=tk.StringVar(value="pi")
        self.samba_pass=tk.StringVar(); self.samba_pass2=tk.StringVar()
        self.nc_admin=tk.StringVar(value="admin"); self.nc_pass=tk.StringVar()
        self.nc_db_pass=tk.StringVar()
        self.d_dev=tk.StringVar(value=suggest_device())
        self.d_mp=tk.StringVar(value=suggest_mount(self.d_dev.get()))
        self.d_share=tk.StringVar(value=suggest_share(self.d_dev.get()))
        self.d_fmt=tk.BooleanVar(value=False); self.d_fs=tk.StringVar(value="ext4")
        self.d_share=tk.StringVar(value="Opslag"); self.d_add_samba=tk.BooleanVar(value=True)
        self.sw_dev=tk.StringVar(value="/dev/sda"); self.sw_fmt=tk.BooleanVar(value=False)
        self.sw_fs=tk.StringVar(value="ext4"); self.sw_mp=tk.StringVar()
        self.rm_mp=tk.StringVar(); self.fmt_dev=tk.StringVar(value="/dev/sda")
        self.fmt_fs=tk.StringVar(value="ext4")
        self.d2_dev=tk.StringVar(value="/dev/sdb")
        dev=self.d2_dev.get()
        self.d2_mp=tk.StringVar(value=suggest_mount(dev))
        self.d2_share=tk.StringVar(value=suggest_share(dev))
        self.d2_fmt=tk.BooleanVar(value=False)
        self.d2_fs=tk.StringVar(value="ext4")
        self.current_page=0; self._history=[]
        self._build_chrome(); self._show_page(0)

    # ── Chrome ───────────────────────────────────────────────────────────────
    def _build_chrome(self):
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        tk.Frame(self,bg=ACCENT,height=3).grid(row=0,column=0,sticky="ew")

        hdr=tk.Frame(self,bg=BG,padx=22,pady=6)
        hdr.grid(row=1,column=0,sticky="ew")
        tk.Label(hdr,text="🍓  Raspberry Pi NAS Installer  v1.0.0",
                 font=("Segoe UI",12,"bold"),bg=BG,fg=FG).pack(side="left")
        self.lbl_step=tk.Label(hdr,text="",font=("Segoe UI",10),bg=BG,fg=DIM)
        self.lbl_step.pack(side="right")

        self.content=tk.Frame(self,bg=BG)
        self.content.grid(row=2,column=0,sticky="nsew",padx=20,pady=8)

        nav=tk.Frame(self,bg=PANEL2,pady=8)
        nav.grid(row=3,column=0,sticky="ew")

        self.btn_back=tk.Button(nav,text="← Terug",command=self._prev,
                                 bg=BTN,fg=FG,relief="flat",padx=12,pady=5,
                                 font=("Segoe UI",11),cursor="hand2")
        self.btn_back.pack(side="left",padx=12)
        self.btn_skip=tk.Button(nav,text="⏭ Overslaan",command=self._skip,
                                 bg=PANEL2,fg=YELLOW,relief="flat",padx=10,pady=5,
                                 font=("Segoe UI",11),cursor="hand2")
        self.btn_skip.pack(side="left",padx=4)
        self.btn_next=tk.Button(nav,text="Volgende →",command=self._next,
                                 bg=ACCENT,fg=BG,relief="flat",padx=12,pady=5,
                                 font=("Segoe UI",12,"bold"),cursor="hand2")
        self.btn_next.pack(side="right",padx=12)

        style=ttk.Style(self); style.theme_use("clam")
        style.configure("T.Horizontal.TProgressbar",troughcolor=PANEL2,background=ACCENT,borderwidth=0,thickness=4)
        self.top_prog=ttk.Progressbar(nav,style="T.Horizontal.TProgressbar",maximum=8)
        self.top_prog.pack(side="left",fill="x",expand=True,padx=8)

    def _clear(self):
        for w in self.content.winfo_children(): w.destroy()

    def _show_page(self,idx):
        self._clear(); self.current_page=idx
        main_pages=["Welkom","Netwerk","SSH","Bijwerken","Schijf","Methode","Config","Installatie","Gereed"]
        if idx<9:
            self.lbl_step.config(text=f"Stap {idx+1}/9  —  {main_pages[idx]}")
            # Progress bar
            pct = (idx+1)/9
            if hasattr(self,'prog_bar'):
                self.prog_bar.place(relwidth=pct)
            self.top_prog["value"]=idx
        else:
            self.lbl_step.config(text=self.PAGES[idx])
        pages=[self._pg_welcome,self._pg_network,self._pg_ssh,self._pg_update,
               self._pg_disk,self._pg_method,self._pg_config,self._pg_install,
               self._pg_done,self._pg_initsetup,self._pg_filebrowser,
               self._pg_desktop,self._pg_sshkey,self._pg_deinstall,
               self._pg_nasconfig,self._pg_scripts,self._pg_diagnose,self._pg_sysinfo,self._pg_help,self._pg_beheer,self._pg_cockpit]
        if idx < len(pages): pages[idx]()
        # Scroll terug naar boven na laden
        try:
            for w in self.winfo_children():
                if hasattr(w,"yview_moveto"): w.yview_moveto(0)
        except: pass
        self.btn_back.config(state="normal" if self._history or idx>0 else "disabled", command=self._prev)

        if idx >= 9:
            # Extra pagina's — alleen Terug knop
            self.btn_skip.config(state="disabled", fg="#444")
            self.btn_next.config(state="disabled", text="", fg=PANEL2)
        elif idx==8:
            self.btn_skip.config(state="disabled", fg="#444")
            self.btn_next.config(text="Sluiten", state="normal", command=self.destroy, fg=BG)
        else:
            skip_hidden=idx in (0,7)
            self.btn_skip.config(state="disabled" if skip_hidden else "normal",
                                  fg="#444" if skip_hidden else YELLOW)
            if idx==7:
                self.btn_next.config(text="Volgende →", state="disabled", command=self._next, fg=BG)
            else:
                self.btn_next.config(text="Volgende →", state="normal", command=self._next, fg=BG)

    def _next(self):
        p=self.current_page
        if p==6 and not self._validate_config(): return
        self._history.append(p)
        self._show_page(p+1)
        if self.current_page==7: self.after(400,self._start_install)

    def _prev(self):
        if self._history:
            self._show_page(self._history.pop())
        elif self.current_page>0:
            self._show_page(self.current_page-1)
        else:
            self._show_page(0)

    def _skip(self):
        self._history.append(self.current_page)
        self._show_page(self.current_page+1)

    def _open_browser(self, url):
        popup=tk.Toplevel(self)
        popup.title("URL openen")
        popup.configure(bg=BG)
        popup.resizable(False,False)
        tk.Label(popup,text="Kopieer deze URL naar je browser op Windows:",
                 font=("Segoe UI",10),bg=BG,fg=FG).pack(padx=20,pady=(16,6))
        e=tk.Entry(popup,font=("Courier",11),bg=PANEL,fg=GREEN,
                   relief="flat",width=50)
        e.insert(0,url)
        e.config(state="readonly")
        e.pack(padx=20,pady=(0,6))
        e.select_range(0,"end")
        e.focus_set()
        self._btn(popup,"✖  Sluiten",popup.destroy,bg=BTN,fg=FG).pack(pady=(0,12))

    def _start_service(self, svc, url):
        def bg():
            sh(f"sudo systemctl start {svc}")
            import time; time.sleep(2)
            self.after(0, lambda: self._open_browser(url))
        import threading; threading.Thread(target=bg, daemon=True).start()

    def _fb_actie(self, actie):
        cmds={"start":"sudo systemctl start filebrowser",
              "stop":"sudo systemctl stop filebrowser",
              "enable":"sudo systemctl enable filebrowser",
              "disable":"sudo systemctl disable filebrowser"}
        if actie in cmds:
            sh(cmds[actie])
            self._jump(0)  # Refresh welkomscherm

    def _uitloggen(self):
        if not messagebox.askyesno("Uitloggen","Sessie beëindigen en VNC vergrendelen?"): return
        # VNC scherm vergrendelen
        sh("xdg-screensaver lock 2>/dev/null || lxlock 2>/dev/null || xscreensaver-command -lock 2>/dev/null")
        self.destroy()

    def _redraw(self):
        """Herteken huidige pagina zonder history te wijzigen."""
        idx = self.current_page
        self._clear()
        pages=[self._pg_welcome,self._pg_network,self._pg_ssh,self._pg_update,
               self._pg_disk,self._pg_method,self._pg_config,self._pg_install,
               self._pg_done,self._pg_initsetup,self._pg_filebrowser,
               self._pg_desktop,self._pg_sshkey,self._pg_deinstall,
               self._pg_nasconfig,self._pg_scripts,self._pg_diagnose,self._pg_sysinfo,self._pg_help,self._pg_beheer,self._pg_cockpit]
        if idx < len(pages): pages[idx]()
        # Back-knop state bijwerken
        self.btn_back.config(
            state="normal" if self._history or idx>0 else "disabled",
            command=self._prev
        )

    def _jump(self,idx):
        self._history.append(self.current_page)
        self._show_page(idx)

    # ── UI helpers ────────────────────────────────────────────────────────────
    def _head(self,txt,color=FG):
        tk.Label(self.content,text=txt,font=("Segoe UI",12,"bold"),
                 bg=BG,fg=color).pack(anchor="w",pady=(0,6))

    def _panel(self,parent=None,color=PANEL):
        p=tk.Frame(parent or self.content,bg=color,padx=13,pady=10)
        p.pack(fill="x",pady=4); return p

    def _row(self,parent,label,var,show="",width=24):
        r=tk.Frame(parent,bg=parent["bg"]); r.pack(anchor="w",fill="x",pady=2)
        tk.Label(r,text=label,font=("Segoe UI",11),bg=parent["bg"],fg=FG,
                 width=24,anchor="w").pack(side="left")
        tk.Entry(r,textvariable=var,font=("Segoe UI",11),bg=PANEL2,fg=FG,
                 insertbackground=FG,show=show,width=width,relief="flat").pack(side="left")

    def _logw(self,parent,height=8):
        w=scrolledtext.ScrolledText(parent,height=height,bg=PANEL,fg=GREEN,
                                     font=("Consolas",10),relief="flat",padx=8,pady=5)
        w.pack(fill="both",expand=True,padx=4,pady=(4,6))
        for tag,col in [("warn",WARN),("error",RED),("head",ACCENT),("ok",GREEN),("info",YELLOW)]:
            w.tag_config(tag,foreground=col)
        return w

    def _btn(self,parent,text,cmd,bg=BTN,fg=FG,bold=False):
        return tk.Button(parent,text=text,command=cmd,bg=bg,fg=fg,relief="flat",
                         padx=10,pady=5,font=("Segoe UI",15,"bold" if bold else "normal"),
                         cursor="hand2")

    def _fs_sel(self,parent,var):
        f=tk.Frame(parent,bg=parent["bg"]); f.pack(anchor="w",fill="x",pady=(6,2))
        tk.Label(f,text="Bestandssysteem:",font=("Segoe UI",12,"bold"),
                 bg=parent["bg"],fg=FG).pack(anchor="w",pady=(0,3))
        for val,short,desc in [
            ("ext4","ext4","Beste keuze voor NAS. Niet direct op Windows via USB."),
            ("exfat","exFAT","Leesbaar op Linux én Windows/Mac. Goed voor >4 GB."),
            ("ntfs","NTFS","Windows-native, ook op Linux (ntfs-3g)."),
        ]:
            r=tk.Frame(f,bg=parent["bg"]); r.pack(anchor="w",pady=1)
            tk.Radiobutton(r,variable=var,value=val,bg=parent["bg"],
                           activebackground=parent["bg"],selectcolor=PANEL2).pack(side="left")
            tk.Label(r,text=f"{short:6}  {desc}",font=("Segoe UI",10),
                     bg=parent["bg"],fg=FG,justify="left").pack(side="left")
        tk.Label(f,text="ℹ  Via Samba altijd leesbaar op Windows, ongeacht bestandssysteem.",
                 font=("Segoe UI",10),bg=parent["bg"],fg=YELLOW).pack(anchor="w",pady=(3,0))

    def _run_bg(self,steps,log_widget,on_done=None):
        def work():
            for desc,cmd in steps:
                self.after(0,lambda d=desc:(log_widget.insert(tk.END,f"\n▶  {d}\n","head"),
                                             log_widget.see(tk.END)))
                proc=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT,text=True)
                for line in proc.stdout:
                    s=line.rstrip()
                    if s: self.after(0,lambda l=s:(log_widget.insert(tk.END,f"   {l}\n"),
                                                    log_widget.see(tk.END)))
                proc.wait()
                tag="ok" if proc.returncode==0 else "warn"
                msg="   ✔  Klaar" if proc.returncode==0 else f"   ⚠  Exitcode {proc.returncode}"
                self.after(0,lambda m=msg,t=tag:(log_widget.insert(tk.END,m+"\n",t),
                                                   log_widget.see(tk.END)))
            if on_done: self.after(0,on_done)
        threading.Thread(target=work,daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # WELKOM
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_welcome(self):
        self._head("Welkom bij de NAS Installer")
        # Initiële setup banner — alleen tonen als Samba nog niet geïnstalleerd
        samba_ok = sh("systemctl is-active smbd 2>/dev/null").strip() == "active"
        if not samba_ok:
            p0=tk.Frame(self.content,bg="#0d2518",padx=14,pady=12)
            p0.pack(fill="x",pady=(0,8))
            tk.Label(p0,text="🚀  Eerste keer instellen?",
                     font=("Segoe UI",12,"bold"),bg="#0d2518",fg=GREEN).pack(anchor="w")
            drives=sh("lsblk -o NAME,SIZE,TYPE -rn | grep disk")
            drive_txt=" · ".join(f"/dev/{l.split()[0]}({l.split()[1]})"
                                  for l in drives.splitlines() if l.strip()) or "geen schijven gevonden"
            tk.Label(p0,text=f"Gevonden schijven: {drive_txt}",
                     font=("Segoe UI",11),bg="#0d2518",fg=YELLOW).pack(anchor="w",pady=(3,4))
            tk.Label(p0,text="Regelt alles in één keer: netwerk · SSH · update · schijf · NAS-software.",
                     font=("Segoe UI",11),bg="#0d2518",fg=FG).pack(anchor="w",pady=(0,8))
            self._btn(p0,"🚀  Volledige initiële setup →",
                      lambda:self._jump(9),bg=GREEN,fg=BG,bold=True).pack(anchor="w")
        # Status
        ip=get_ip(); conn=is_connected(); ssh=ssh_enabled()
        p=self._panel()
        tk.Label(p,text="Huidige status",font=("Segoe UI",12,"bold"),
                 bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,6))
        for lbl,val,col in [
            ("📡  IP-adres",ip,GREEN if conn else WARN),
            ("🌐  Netwerk","Verbonden" if conn else "Niet verbonden",GREEN if conn else WARN),
            ("🔑  SSH","Ingeschakeld" if ssh else "Uitgeschakeld",GREEN if ssh else WARN),
            ("🖥  Hostname",sh("hostname") or "?",FG),
        ]:
            r=tk.Frame(p,bg=PANEL); r.pack(anchor="w",pady=1,fill="x")
            tk.Label(r,text=lbl,font=("Segoe UI",11),bg=PANEL,fg=FG,
                     width=20,anchor="w").pack(side="left")
            tk.Label(r,text=val,font=("Segoe UI",12,"bold"),bg=PANEL,fg=col).pack(side="left")
        # Uitloggen knop rechtsboven
        p_logout=tk.Frame(self.content,bg=BG); p_logout.pack(anchor="e",pady=(0,4))
        self._btn(p_logout,"🔒  Uitloggen",self._uitloggen,bg=BTN,fg=YELLOW).pack(side="right")

        # Snelknoppen rij 1
        p2=self._panel()
        tk.Label(p2,text="GA DIRECT NAAR",font=("Segoe UI",9,"bold"),
                 bg=PANEL,fg=DIM).pack(anchor="w",pady=(0,6))
        br=tk.Frame(p2,bg=PANEL); br.pack(anchor="w",pady=(0,4))
        for txt,idx,bg,fg in [
            ("💾  Schijf beheer",4,ACCENT,BG),
            ("⚙️  NAS software",5,"#1d4ed8",BG),
            ("🌐  FileBrowser",10,MAGENTA,BG),
            ("⚙️  Cockpit",20,WARN,BG),
            ("🖥️  Desktop & VNC",11,TEAL,BG)]:
            self._btn(br,txt,lambda i=idx:self._jump(i),bg=bg,fg=fg,bold=True).pack(side="left",padx=(0,6))
        tk.Label(p2,text="",bg=PANEL,height=1).pack(anchor="w")
        br2=tk.Frame(p2,bg=PANEL); br2.pack(anchor="w",pady=(0,2))
        for txt,idx,bg,fg in [
            ("🔑  SSH-sleutel",       12, PANEL,  "#94a3b8"),
            ("💾  Configuratie",      14, PANEL,  "#94a3b8"),
            ("⬆  Scripts bijwerken",  15, PANEL,  "#94a3b8"),
            ("🔬  Diagnose",          16, PANEL,  "#94a3b8"),
            ("📋  Systeem info",      17, PANEL,  TEAL),
            ("❓  Help",              18, PANEL,  "#94a3b8"),
            ("🛠  Beheer",            19, PANEL,  YELLOW),
            ("🗑  Deïnstalleren",     13, "#7f1d1d", "#fca5a5"),
        ]:
            b=self._btn(br2,txt,lambda i=idx:self._jump(i),bg=bg,fg=fg,bold=False)
            b.config(highlightthickness=1,highlightbackground=PANEL2,highlightcolor=PANEL2)
            b.pack(side="left",padx=(0,4))

        # Webinterfaces
        p3=self._panel()
        tk.Label(p3,text="WEBINTERFACES",font=("Segoe UI",9,"bold"),
                 bg=PANEL,fg=DIM).pack(anchor="w",pady=(0,6))
        ip=get_ip()
        webservices=[
            ("🌐  FileBrowser",  f"http://{ip}:8080", "filebrowser",  MAGENTA),
            ("⚙️   Cockpit",      f"http://{ip}:9090", "cockpit",       "#ed8936"),
            ("☁   Nextcloud",    f"http://{ip}/nextcloud","apache2",   ACCENT),
        ]
        br3=tk.Frame(p3,bg=PANEL); br3.pack(anchor="w",pady=(0,4))
        for naam,url,svc,kleur in webservices:
            actief=sh(f"systemctl is-active {svc} 2>/dev/null").strip()=="active"
            geinstalleerd=sh(f"systemctl is-enabled {svc} 2>/dev/null 2>/dev/null").strip() not in ("","not-found","static")
            frame=tk.Frame(br3,bg=PANEL); frame.pack(side="left",padx=(0,8))
            if actief:
                self._btn(frame,naam,lambda u=url:self._open_browser(u),
                          bg=kleur,fg=BG,bold=True).pack()
                tk.Label(frame,text="● actief",font=("Segoe UI",8),
                         bg=PANEL,fg=GREEN).pack()
            elif geinstalleerd:
                self._btn(frame,naam,lambda s=svc,u=url:self._start_service(s,u),
                          bg=BTN,fg=FG).pack()
                tk.Label(frame,text="○ gestopt — klik om te starten",font=("Segoe UI",8),
                         bg=PANEL,fg=WARN).pack()
            else:
                # Niet geïnstalleerd — installeer knop tonen
                install_idx={"filebrowser":10,"cockpit":20,"apache2":5}
                idx_pg=install_idx.get(svc,0)
                self._btn(frame,f"➕ {naam.split()[1]} installeren",
                          lambda i=idx_pg:self._jump(i),bg=PANEL2,fg=FG).pack()
                tk.Label(frame,text="─ niet geïnstalleerd",font=("Segoe UI",8),
                         bg=PANEL,fg="#555").pack()



    # ══════════════════════════════════════════════════════════════════════════
    # NETWERK
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_network(self):
        self._head("Netwerk — WiFi of UTP")
        if is_connected():
            p=self._panel(color="#1e3a1e")
            tk.Label(p,text=f"✅  Verbonden — IP: {get_ip()}",
                     font=("Segoe UI",12,"bold"),bg="#1e3a1e",fg=GREEN).pack(anchor="w")
            tk.Label(p,text="Je kunt deze stap overslaan.",
                     font=("Segoe UI",11),bg="#1e3a1e",fg=FG).pack(anchor="w",pady=(3,0))
        p2=self._panel()
        tk.Label(p2,text="Via UTP-kabel",font=("Segoe UI",12,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w")
        tk.Label(p2,text="Sluit kabel aan op Pi en router — automatisch IP.",
                 font=("Segoe UI",11),bg=PANEL,fg=FG).pack(anchor="w",pady=(3,0))
        p3=self._panel()
        tk.Label(p3,text="Via WiFi",font=("Segoe UI",12,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,6))
        sf=tk.Frame(p3,bg=PANEL); sf.pack(fill="x")
        self.wifi_lb=tk.Listbox(sf,bg=PANEL2,fg=FG,font=("Segoe UI",11),height=4,
                                 selectbackground=ACCENT,selectforeground=BG,
                                 relief="flat",activestyle="none")
        self.wifi_lb.pack(side="left",fill="x",expand=True)
        sb=tk.Scrollbar(sf,command=self.wifi_lb.yview,bg=PANEL2)
        sb.pack(side="left",fill="y")
        self.wifi_lb.config(yscrollcommand=sb.set)
        self.wifi_lb.bind("<<ListboxSelect>>",self._wifi_sel)
        self._btn(p3,"🔍 Scannen",self._wifi_scan).pack(anchor="w",pady=(5,4))
        self._row(p3,"SSID:",self.wifi_ssid); self._row(p3,"Wachtwoord:",self.wifi_pass,show="•")
        br=tk.Frame(p3,bg=PANEL); br.pack(anchor="w",pady=(7,0))
        self._btn(br,"📶 Verbinden",self._wifi_connect,bg=ACCENT,fg=BG,bold=True).pack(side="left",padx=(0,8))
        self.lbl_wifi=tk.Label(br,text="",font=("Segoe UI",11),bg=PANEL,fg=FG); self.lbl_wifi.pack(side="left")
        self._wifi_scan()

    def _wifi_scan(self):
        self.wifi_lb.delete(0,tk.END); self.wifi_lb.insert(tk.END,"  Scannen...")
        self.after(100,self._wifi_fill)

    def _wifi_fill(self):
        nets=get_wifi_nets(); self.wifi_lb.delete(0,tk.END); self._wnets=nets
        if not nets: self.wifi_lb.insert(tk.END,"  Geen netwerken gevonden")
        for ssid,sig,sec in nets:
            self.wifi_lb.insert(tk.END,f"  {'🔒' if sec else '🔓'} {ssid:<32} {sig}%")

    def _wifi_sel(self,_=None):
        sel=self.wifi_lb.curselection()
        if sel and hasattr(self,"_wnets") and sel[0]<len(self._wnets):
            self.wifi_ssid.set(self._wnets[sel[0]][0])

    def _wifi_connect(self):
        ssid=self.wifi_ssid.get().strip()
        if not ssid: messagebox.showerror("Fout","Selecteer een netwerk."); return
        self.lbl_wifi.config(text="Verbinden...",fg=WARN); self.update()
        pwd=self.wifi_pass.get()
        cmd=f'sudo nmcli dev wifi connect "{ssid}"'+(f' password "{pwd}"' if pwd else "")
        r=sh(f"{cmd} 2>&1")
        if "successfully" in r.lower() or is_connected():
            self.lbl_wifi.config(text=f"✅  Verbonden! IP: {get_ip()}",fg=GREEN)
        else: self.lbl_wifi.config(text=f"❌  {r[:55]}",fg=RED)

    # ══════════════════════════════════════════════════════════════════════════
    # SSH
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_ssh(self):
        self._head("SSH instellen")
        ena=ssh_enabled()
        p=self._panel(color="#1e3a1e" if ena else PANEL)
        tk.Label(p,text="✅  SSH ingeschakeld" if ena else "⚠  SSH uitgeschakeld",
                 font=("Segoe UI",12,"bold"),bg=p["bg"],
                 fg=GREEN if ena else WARN).pack(anchor="w")
        if ena: tk.Label(p,text=f"Verbind via: ssh pi@{get_ip()}",
                          font=("Segoe UI",11),bg=p["bg"],fg=FG).pack(anchor="w",pady=(3,0))
        p2=self._panel()
        tk.Label(p2,text="SSH laat je de Pi bedienen vanuit Windows.\n"
                          f"PowerShell: ssh pi@{get_ip()}",
                 font=("Segoe UI",11),bg=PANEL,fg=FG,justify="left").pack(anchor="w")
        p3=self._panel()
        br=tk.Frame(p3,bg=PANEL); br.pack(anchor="w")
        self._btn(br,"✅ SSH inschakelen",self._ssh_on,bg=GREEN,fg=BG,bold=True).pack(side="left",padx=(0,8))
        self._btn(br,"🔑 SSH-sleutel beheren",lambda:self._jump(12),bg=BTN,fg=FG).pack(side="left")
        self.lbl_ssh=tk.Label(p3,text="",font=("Segoe UI",11),bg=PANEL,fg=FG)
        self.lbl_ssh.pack(anchor="w",pady=(7,0))

    def _ssh_on(self):
        sh("sudo systemctl enable ssh && sudo systemctl start ssh")
        self.lbl_ssh.config(text=f"✅  SSH ingeschakeld — ssh pi@{get_ip()}",fg=GREEN)

    # ══════════════════════════════════════════════════════════════════════════
    # SYSTEEM BIJWERKEN
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_update(self):
        self._head("Systeem bijwerken")
        tk.Label(self.content,text="Bijwerken voorkomt installatieproblemen. Klik of sla over.",
                 font=("Segoe UI",11),bg=BG,fg=FG).pack(anchor="w",pady=(0,8))
        br=tk.Frame(self.content,bg=BG); br.pack(anchor="w",pady=(0,8))
        self._btn(br,"🔄 Bijwerken",self._do_update,bg=ACCENT,fg=BG,bold=True).pack(side="left",padx=(0,10))
        self.upd_out=self._logw(self.content,13)

    def _do_update(self):
        self.btn_next.config(state="disabled"); self.upd_out.delete("1.0",tk.END)
        def done():
            self.upd_out.insert(tk.END,"\n✅  Bijgewerkt!\n","ok")
            self.btn_next.config(state="normal")
        self._run_bg([("apt update","sudo apt-get update -y"),
                      ("apt upgrade","sudo apt-get upgrade -y")],
                     self.upd_out,on_done=done)

    # ══════════════════════════════════════════════════════════════════════════
    # SCHIJF BEHEER — 6 tabbladen
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_disk(self):
        self._head("Schijf beheer")
        style=ttk.Style()
        style.configure("D.TNotebook",background=BG,borderwidth=0)
        style.configure("D.TNotebook.Tab",background=PANEL2,foreground=FG,
                         padding=[10,4],font=("Segoe UI",11))
        style.map("D.TNotebook.Tab",background=[("selected",ACCENT)],foreground=[("selected",BG)])
        nb=ttk.Notebook(self.content,style="D.TNotebook"); nb.pack(fill="both",expand=True)
        tabs={}
        for key,label in [("ov","📋  Overzicht"),("kop","💾  Koppelen"),
                           ("wis","🔄  Wisselen"),("ver","🗑  Verwijderen"),
                           ("fmt","🔧  Formatteren"),("dia","🔬  Diagnose")]:
            t=tk.Frame(nb,bg=BG); nb.add(t,text=label); tabs[key]=t
        self._tab_overzicht(tabs["ov"]); self._tab_koppelen(tabs["kop"])
        self._tab_wisselen(tabs["wis"]); self._tab_verwijderen(tabs["ver"])
        self._tab_formatteren(tabs["fmt"]); self._tab_diagnose(tabs["dia"])

    def _logw_in(self,parent,height=6):
        w=scrolledtext.ScrolledText(parent,height=height,bg=PANEL,fg=GREEN,
                                     font=("Consolas",10),relief="flat",padx=8,pady=5)
        w.pack(fill="both",expand=True,padx=6,pady=(4,6))
        for tag,col in [("warn",WARN),("error",RED),("head",ACCENT),("ok",GREEN),("info",YELLOW)]:
            w.tag_config(tag,foreground=col)
        return w

    def _tab_overzicht(self,parent):
        p=tk.Frame(parent,bg=PANEL,padx=12,pady=10); p.pack(fill="x",padx=6,pady=6)
        hdr=tk.Frame(p,bg=PANEL); hdr.pack(fill="x")
        tk.Label(hdr,text="Gekoppelde NAS-schijven",font=("Segoe UI",12,"bold"),
                 bg=PANEL,fg=ACCENT).pack(side="left")
        self._btn(hdr,"🔄 Vernieuwen",lambda:self._ov_refresh(),bg=BTN,fg=FG).pack(side="right")
        cols=("Apparaat","Mountpunt","FS","Grootte","Samba-share")
        style=ttk.Style()
        style.configure("Ov.Treeview",background=PANEL2,foreground=FG,
                         fieldbackground=PANEL2,font=("Segoe UI",11),rowheight=22)
        style.configure("Ov.Treeview.Heading",background=PANEL,foreground=ACCENT,
                         font=("Segoe UI",12,"bold"))
        style.map("Ov.Treeview",background=[("selected",ACCENT)],foreground=[("selected",BG)])
        self.ov_tree=ttk.Treeview(parent,columns=cols,show="headings",height=5,style="Ov.Treeview")
        for col,w in zip(cols,[80,110,60,60,100]):
            self.ov_tree.heading(col,text=col); self.ov_tree.column(col,width=w,anchor="w")
        self.ov_tree.pack(fill="x",padx=6,pady=(4,2))
        self.ov_info=tk.Label(parent,text="",font=("Segoe UI",11),bg=BG,fg=YELLOW)
        self.ov_info.pack(anchor="w",padx=8); self._ov_refresh()

    def _ov_refresh(self):
        if not hasattr(self,"ov_tree"): return
        self.ov_tree.delete(*self.ov_tree.get_children())
        mounts=get_nas_mounts(); shares=get_samba_shares()
        sp={v:k for k,v in shares.items()}
        if not mounts: self.ov_info.config(text="⚠  Geen NAS-schijven gevonden — gebruik tab Koppelen.",fg=WARN)
        else: self.ov_info.config(text=f"✅  {len(mounts)} schijf(ven) gekoppeld.",fg=GREEN)
        for dev,mp,fs,sz in mounts:
            self.ov_tree.insert("","end",values=(dev,mp,fs,sz,sp.get(mp,"—")))

    def _tab_koppelen(self,parent):
        self.d_dev.set(suggest_device()); self.d_mp.set(suggest_mount(self.d_dev.get()))
        p=tk.Frame(parent,bg=PANEL,padx=12,pady=10); p.pack(fill="x",padx=6,pady=6)
        tk.Label(p,text="Schijf koppelen (eerste of extra schijf)",
                 font=("Segoe UI",12,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,6))
        tk.Label(p,text="Auto-detecteert vrij apparaat en mountpunt.",
                 font=("Segoe UI",11),bg=PANEL,fg=FG).pack(anchor="w",pady=(0,4))
        # Toon beschikbare schijven met grootte
        schijven=sh("lsblk -dn -o NAME,SIZE,TYPE 2>/dev/null | grep disk")
        grote_vrij=False
        if schijven:
            tk.Label(p,text="Beschikbare schijven:",font=("Segoe UI",9,"bold"),
                     bg=PANEL,fg=ACCENT).pack(anchor="w")
            for regel in schijven.splitlines():
                parts=regel.split()
                if len(parts)>=2:
                    dev=f"/dev/{parts[0]}"; sz=parts[1]
                    mount=sh(f"lsblk -dn -o MOUNTPOINT {dev} 2>/dev/null").strip()
                    status=f"→ {mount}" if mount else "→ vrij"
                    kleur=GREEN if not mount else "#888888"
                    tk.Label(p,text=f"  {dev}  {sz}  {status}",
                             font=("Segoe UI",9),bg=PANEL,fg=kleur).pack(anchor="w")
                    # Grote vrije schijf?
                    if not mount and ('T' in sz or ('G' in sz and float(sz.replace('G','').strip() or '0') >= 500)):
                        grote_vrij=True
        # Waarschuwing als geen grote schijf vrij is
        if not grote_vrij:
            plug_cfg="/home/pi/smart_plug_config.json"
            import os as _os
            if _os.path.exists(plug_cfg):
                tk.Label(p,text="⚠  Geen grote schijf gevonden — zet de Seagate aan via Beheer → Seagate aanzetten",
                         font=("Segoe UI",9,"bold"),bg=PANEL,fg=WARN).pack(anchor="w",pady=(4,0))
            else:
                tk.Label(p,text="⚠  Geen grote schijf gevonden — controleer of de Seagate aangesloten en ingeschakeld is",
                         font=("Segoe UI",9,"bold"),bg=PANEL,fg=WARN).pack(anchor="w",pady=(4,0))
        tk.Label(p,text="",bg=PANEL).pack(anchor="w")
        self._row(p,"Schijf (bijv. /dev/sda):",self.d_dev)
        self._row(p,"Mountpunt:",self.d_mp)
        self._row(p,"Samba share-naam:",self.d_share)
        opt=tk.Frame(p,bg=PANEL); opt.pack(anchor="w",pady=(6,0))
        tk.Checkbutton(opt,text="  Toevoegen als Samba-share",variable=self.d_add_samba,
                       bg=PANEL,fg=FG,selectcolor=PANEL2,activebackground=PANEL,
                       font=("Segoe UI",11)).pack(side="left")
        opt2=tk.Frame(p,bg=PANEL); opt2.pack(anchor="w",pady=(3,0))
        tk.Checkbutton(opt2,text="  Formatteren (wist alle data!)",variable=self.d_fmt,
                       bg=PANEL,fg=WARN,selectcolor=PANEL2,activebackground=PANEL,
                       font=("Segoe UI",11)).pack(side="left")
        self._fs_sel(p,self.d_fs)
        br=tk.Frame(parent,bg=BG); br.pack(anchor="w",padx=6,pady=(4,2))
        self._btn(br,"⚙️  Koppelen",self._do_koppelen,bg=GREEN,fg=BG,bold=True).pack(side="left",padx=(0,8))
        self._btn(br,"🔍 Schijven",lambda:(self.kop_out.delete("1.0",tk.END),
                                           self.kop_out.insert(tk.END,sh("lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT")+"\n")),
                  bg=BTN,fg=FG).pack(side="left")
        self.kop_out=self._logw_in(parent,7)

    def _do_koppelen(self):
        dev=fix_dev(self.d_dev.get()); mp=self.d_mp.get().strip()
        share=self.d_share.get().strip(); fs=self.d_fs.get()
        user=self.samba_user.get().strip() or sh("logname 2>/dev/null || echo pi")
        if not dev or not mp: messagebox.showerror("Fout","Vul schijf en mountpunt in."); return
        if self.d_fmt.get():
            if not messagebox.askyesno("Bevestigen",f"ALLE DATA op {dev} wordt gewist!"): return
        self.kop_out.delete("1.0",tk.END)
        steps=[]
        if self.d_fmt.get(): steps+=fs_format_cmds(dev,fs)
        steps+=[("Mountpunt aanmaken",f"sudo mkdir -p {mp}")]
        def after():
            def bg():
                def u(t,tag=None):
                    self.after(0,lambda:(self.kop_out.insert(tk.END,t+"\n",tag or ""),
                                          self.kop_out.see(tk.END)))
                uuid=sh(f"sudo blkid -s UUID -o value {dev}")
                if not uuid: u("✗  Geen UUID gevonden.","error"); return
                u(f"   UUID: {uuid}","info")
                fstab=sh("cat /etc/fstab")
                if uuid not in fstab:
                    entry=fs_fstab(uuid,mp,fs)+"\n"
                    subprocess.run(f"echo '{entry}' | sudo tee -a /etc/fstab",shell=True)
                    u(f"✔  fstab bijgewerkt ({fs})","ok")
                r=subprocess.run("sudo mount -a",shell=True,capture_output=True,text=True)
                if r.returncode!=0: u(f"✗  Mount mislukt: {r.stderr}","error"); return
                u("✔  Gemount!","ok")
                subprocess.run(f"sudo chown -R {user}:{user} {mp} && sudo chmod -R 775 {mp}",shell=True)
                u(f"✔  Eigenaarschap: {user}","ok")
                if self.d_add_samba.get():
                    smbd=sh("sudo systemctl is-enabled smbd 2>/dev/null")
                    if smbd in ("enabled","static"):
                        conf=sh("cat /etc/samba/smb.conf")
                        if f"[{share}]" not in conf:
                            blk=(f"\n[{share}]\n   comment=Pi Opslag\n   path={mp}\n"
                                 f"   browseable=yes\n   writable=yes\n"
                                 f"   valid users={user}\n   force user={user}\n")
                            subprocess.run(f"printf '{blk}' | sudo tee -a /etc/samba/smb.conf>/dev/null",shell=True)
                            subprocess.run("sudo systemctl restart smbd",shell=True)
                            u(f"✔  Samba-share [{share}] aangemaakt","ok")
                update_rechten_service()
                u("\n✅  Schijf succesvol gekoppeld!","ok")
                self.after(0,self._ov_refresh)
            threading.Thread(target=bg,daemon=True).start()
        self._run_bg(steps,self.kop_out,on_done=after)

    def _tab_wisselen(self,parent):
        p=tk.Frame(parent,bg=PANEL,padx=12,pady=10); p.pack(fill="x",padx=6,pady=6)
        tk.Label(p,text="Schijf wisselen — testschijf → definitieve schijf",
                 font=("Segoe UI",12,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,4))
        tk.Label(p,text="NAS-software blijft geïnstalleerd. Alleen fstab wordt bijgewerkt.",
                 font=("Segoe UI",11),bg=PANEL,fg=FG).pack(anchor="w",pady=(0,6))
        tk.Label(p,text="Te vervangen mountpunt:",font=("Segoe UI",11),bg=PANEL,fg=FG).pack(anchor="w")
        mounts=[m[1] for m in get_nas_mounts()] or ["/mnt/opslag"]
        self.sw_mp.set(mounts[0])
        self.sw_combo=ttk.Combobox(p,textvariable=self.sw_mp,values=mounts,
                                    font=("Segoe UI",11),state="readonly",width=26)
        self.sw_combo.pack(anchor="w",pady=(2,6))
        self._row(p,"Nieuwe schijf:",self.sw_dev)
        opt=tk.Frame(p,bg=PANEL); opt.pack(anchor="w",pady=(6,0))
        tk.Checkbutton(opt,text="  Nieuwe schijf formatteren (wist alle data!)",
                       variable=self.sw_fmt,bg=PANEL,fg=WARN,selectcolor=PANEL2,
                       activebackground=PANEL,font=("Segoe UI",11)).pack(side="left")
        self._fs_sel(p,self.sw_fs)
        tk.Label(parent,text="⚠  Nextcloud-data staat op de oude schijf en gaat NIET mee.",
                 font=("Segoe UI",11),bg=BG,fg=WARN).pack(anchor="w",padx=6,pady=(4,2))
        self._btn(parent,"🔄  Wisselen",self._do_wisselen,bg=WARN,fg=BG,bold=True).pack(anchor="w",padx=6,pady=(0,4))
        self.wis_out=self._logw_in(parent,7)

    def _do_wisselen(self):
        dev=fix_dev(self.sw_dev.get()); mp=self.sw_mp.get(); fs=self.sw_fs.get()
        user=self.samba_user.get().strip() or sh("logname 2>/dev/null || echo pi")
        if not messagebox.askyesno("Bevestigen",f"Vervangt schijfkoppeling voor {mp}\nmet {dev}.\nDoorgaan?"): return
        self.wis_out.delete("1.0",tk.END)
        def bg():
            def u(t,tag=None):
                self.after(0,lambda:(self.wis_out.insert(tk.END,t+"\n",tag or ""),
                                     self.wis_out.see(tk.END)))
            u("▶  Services stoppen...","head")
            for svc in ["smbd","apache2","mariadb"]:
                if sh(f"sudo systemctl is-active {svc}")=="active":
                    subprocess.run(f"sudo systemctl stop {svc}",shell=True); u(f"   ✔  {svc}","ok")
            subprocess.run(f"sudo umount {mp} 2>/dev/null",shell=True); u("✔  Ge-unmount","ok")
            if self.sw_fmt.get():
                for desc,cmd in fs_format_cmds(dev,fs):
                    u(f"▶  {desc}...","head")
                    r=subprocess.run(cmd,shell=True,capture_output=True,text=True)
                    u("   ✔  Klaar" if r.returncode==0 else f"   ✗  {r.stderr}","ok" if r.returncode==0 else "error")
                    if r.returncode!=0: return
            uuid=sh(f"sudo blkid -s UUID -o value {dev}")
            if not uuid: u("✗  Geen UUID","error"); return
            u(f"   UUID: {uuid}","info")
            lines=[l for l in sh("cat /etc/fstab").splitlines() if mp not in l or l.strip().startswith("#")]
            lines.append(fs_fstab(uuid,mp,fs))
            new_fstab="\n".join(lines)+"\n"
            subprocess.run(f"sudo bash -c \"printf '%s' '{new_fstab}' > /etc/fstab\"",shell=True)
            u("✔  fstab bijgewerkt","ok")
            subprocess.run(f"sudo mkdir -p {mp}",shell=True)
            r2=subprocess.run("sudo mount -a",shell=True,capture_output=True,text=True)
            if r2.returncode!=0: u(f"✗  Mount mislukt","error"); return
            u("✔  Gemount!","ok")
            subprocess.run(f"sudo chown -R {user}:{user} {mp} && sudo chmod -R 775 {mp}",shell=True)
            u(f"✔  Eigenaarschap: {user}","ok")
            for svc in ["smbd","apache2","mariadb"]:
                if sh(f"sudo systemctl is-enabled {svc} 2>/dev/null") in ("enabled","static"):
                    subprocess.run(f"sudo systemctl start {svc}",shell=True); u(f"✔  {svc} herstart","ok")
            update_rechten_service()
            u("\n✅  Schijf gewisseld!","ok"); u("  Samba werkt direct.","ok")
            u("  Nextcloud: data op oude schijf.","warn")
            self.after(0,self._ov_refresh)
        threading.Thread(target=bg,daemon=True).start()

    def _tab_verwijderen(self,parent):
        p=tk.Frame(parent,bg=PANEL,padx=12,pady=10); p.pack(fill="x",padx=6,pady=6)
        tk.Label(p,text="Schijf netjes verwijderen",font=("Segoe UI",12,"bold"),
                 bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,4))
        tk.Label(p,text="Verwijdert koppeling, fstab-regel en Samba-share. Data blijft bewaard.",
                 font=("Segoe UI",11),bg=PANEL,fg=FG).pack(anchor="w",pady=(0,6))
        tk.Label(p,text="Kies schijf:",font=("Segoe UI",11),bg=PANEL,fg=FG).pack(anchor="w")
        mounts=[m[1] for m in get_nas_mounts()] or ["(geen schijven)"]
        if mounts: self.rm_mp.set(mounts[0])
        self.rm_combo=ttk.Combobox(p,textvariable=self.rm_mp,values=mounts,
                                    font=("Segoe UI",11),state="readonly",width=26)
        self.rm_combo.pack(anchor="w",pady=(2,6))
        self.rm_preview=tk.Label(p,text="",font=("Segoe UI",11),bg=PANEL,fg=WARN,justify="left")
        self.rm_preview.pack(anchor="w",pady=(0,4))
        self.rm_combo.bind("<<ComboboxSelected>>",self._rm_preview)
        self._rm_preview()
        br=tk.Frame(parent,bg=BG); br.pack(anchor="w",padx=6,pady=(4,2))
        self._btn(br,"🔄 Lijst vernieuwen",self._rm_reload,bg=BTN,fg=FG).pack(side="left",padx=(0,8))
        self._btn(br,"🗑  Verwijderen",self._do_verwijderen,bg=RED,fg=BG,bold=True).pack(side="left")
        self.rm_out=self._logw_in(parent,7)

    def _rm_preview(self,_=None):
        mp=self.rm_mp.get(); shares=get_samba_shares(); sp={v:k for k,v in shares.items()}
        share=sp.get(mp)
        lines=[f"• fstab-regel voor {mp} wordt verwijderd","• Schijf wordt ge-unmount",
               f"• Samba-share [{share}] wordt verwijderd" if share else "• Geen Samba-share gevonden"]
        if hasattr(self,"rm_preview"): self.rm_preview.config(text="\n".join(lines))

    def _rm_reload(self):
        mounts=[m[1] for m in get_nas_mounts()] or ["(geen)"]
        self.rm_combo["values"]=mounts; self.rm_mp.set(mounts[0]); self._rm_preview()

    def _do_verwijderen(self):
        mp=self.rm_mp.get()
        if "(geen" in mp: messagebox.showinfo("Info","Geen schijven."); return
        if not messagebox.askyesno("Bevestigen",f"Schijfkoppeling {mp} verwijderen?\nData blijft bewaard."): return
        self.rm_out.delete("1.0",tk.END)
        def bg():
            def u(t,tag=None):
                self.after(0,lambda:(self.rm_out.insert(tk.END,t+"\n",tag or ""),
                                     self.rm_out.see(tk.END)))
            shares=get_samba_shares(); sp={v:k for k,v in shares.items()}; share=sp.get(mp)
            if share:
                conf=sh("cat /etc/samba/smb.conf"); lines=conf.splitlines(); new=[]; skip=False
                for line in lines:
                    if line.strip()==f"[{share}]": skip=True
                    elif skip and line.strip().startswith("["): skip=False
                    if not skip: new.append(line)
                subprocess.run(f"printf '%s\\n' "+(" ".join(f"'{l}'" for l in new))+" | sudo tee /etc/samba/smb.conf>/dev/null",shell=True)
                subprocess.run("sudo systemctl restart smbd 2>/dev/null",shell=True)
                u(f"✔  Share [{share}] verwijderd","ok")
            lines=[l for l in sh("cat /etc/fstab").splitlines() if mp not in l or l.strip().startswith("#")]
            subprocess.run(f"sudo bash -c \"printf '%s\\n' > /etc/fstab\"",shell=True)
            for l in lines: subprocess.run(f"echo '{l}' | sudo tee -a /etc/fstab>/dev/null",shell=True)
            u("✔  fstab bijgewerkt","ok")
            subprocess.run(f"sudo umount {mp} 2>/dev/null",shell=True)
            u("✔  Ge-unmount","ok")
            update_rechten_service()
            u("\n✅  Schijf verwijderd — data onaangeroerd.","ok")
            self.after(0,self._ov_refresh); self.after(0,self._rm_reload)
        threading.Thread(target=bg,daemon=True).start()

    def _tab_formatteren(self,parent):
        p=tk.Frame(parent,bg=PANEL,padx=12,pady=10); p.pack(fill="x",padx=6,pady=6)
        tk.Label(p,text="Schijf formatteren",font=("Segoe UI",12,"bold"),
                 bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,4))
        wb=tk.Frame(p,bg="#3d1a1a",padx=10,pady=8); wb.pack(fill="x",pady=(0,8))
        tk.Label(wb,text="⚠  WAARSCHUWING: formatteren wist ALLE data permanent.",
                 font=("Segoe UI",12,"bold"),bg="#3d1a1a",fg=RED).pack(anchor="w")
        tk.Label(wb,text="Gebruik alleen voor nieuwe/lege schijven.",
                 font=("Segoe UI",11),bg="#3d1a1a",fg=FG).pack(anchor="w")
        self._row(p,"Schijf (bijv. /dev/sda):",self.fmt_dev)
        self._fs_sel(p,self.fmt_fs)
        self._btn(parent,"🔧  Formatteren",self._do_formatteren,bg=RED,fg=BG,bold=True).pack(anchor="w",padx=6,pady=(8,4))
        self.fmt_out=self._logw_in(parent,7)

    def _do_formatteren(self):
        dev=fix_dev(self.fmt_dev.get()); fs=self.fmt_fs.get()
        if not dev: messagebox.showerror("Fout","Vul een schijfnaam in."); return
        if not messagebox.askyesno("BEVESTIGEN",f"⚠  ALLE DATA op {dev} wordt gewist!\n\nBestandssysteem: {fs}\n\nZeker weten?"): return
        if not messagebox.askyesno("TWEEDE BEVESTIGING",f"Laatste kans: {dev} formatteren?"): return
        self.fmt_out.delete("1.0",tk.END)
        self._run_bg(fs_format_cmds(dev,fs),self.fmt_out,
                     on_done=lambda:self.fmt_out.insert(tk.END,"\n✅  Formatteren klaar!\n","ok"))

    def _tab_diagnose(self,parent):
        p=tk.Frame(parent,bg=PANEL,padx=12,pady=10); p.pack(fill="x",padx=6,pady=6)
        tk.Label(p,text="Diagnose",font=("Segoe UI",12,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,6))
        br=tk.Frame(p,bg=PANEL); br.pack(anchor="w")
        self.diag_out=self._logw_in(parent,8)
        for lbl,cmd in [("🔍 lsblk","lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT"),
                         ("📊 df -h","df -h"),("📋 fstab","cat /etc/fstab"),
                         ("🔗 Mounts","mount | grep /mnt/"),("🌡 Temp",f"sudo hddtemp {self.fmt_dev.get()} 2>&1")]:
            self._btn(br,lbl,lambda c=cmd:(self.diag_out.delete("1.0",tk.END),
                                            self.diag_out.insert(tk.END,f"$ {c}\n","head"),
                                            self.diag_out.insert(tk.END,sh(c)+"\n")),
                      bg=BTN,fg=FG).pack(side="left",padx=(0,5))
        sep=tk.Frame(parent,bg=PANEL2,height=1); sep.pack(fill="x",padx=6,pady=6)
        p2=tk.Frame(parent,bg=PANEL,padx=12,pady=10); p2.pack(fill="x",padx=6)
        tk.Label(p2,text="NAS-software herinstalleren",font=("Segoe UI",12,"bold"),
                 bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,4))
        tk.Label(p2,text="Data blijft bewaard. Alleen software opnieuw.",
                 font=("Segoe UI",11),bg=PANEL,fg=FG).pack(anchor="w",pady=(0,6))
        self._btn(p2,"⚙️  Naar installatiestap",lambda:self._jump(5),
                  bg=ACCENT,fg=BG,bold=True).pack(anchor="w")

    # ══════════════════════════════════════════════════════════════════════════
    # NAS METHODE
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_method(self):
        self._head("Kies NAS-methode")

        # Detecteer wat al geïnstalleerd is
        samba_ok=sh("dpkg -l samba 2>/dev/null | grep -c '^ii'").strip()=="1"
        nc_ok=os.path.exists("/var/www/html/nextcloud")
        if samba_ok or nc_ok:
            already=[]
            if samba_ok: already.append("Samba")
            if nc_ok: already.append("Nextcloud")
            p=tk.Frame(self.content,bg="#3d2a1a",padx=12,pady=8)
            p.pack(fill="x",pady=(0,8))
            tk.Label(p,text=f"⚠  Al geïnstalleerd: {', '.join(already)}",
                     font=("Segoe UI",11,"bold"),bg="#3d2a1a",fg=WARN).pack(anchor="w")
            tk.Label(p,text="Opnieuw installeren overschrijft de huidige configuratie.\n"
                             "Klik Terug om te annuleren.",
                     font=("Segoe UI",9),bg="#3d2a1a",fg=FG,justify="left").pack(anchor="w",pady=(3,0))

        for val,title,sub,feats in [
            ("A","Methode A — Samba + Cockpit","Aanbevolen · ~20 min",
             ["✔  Netwerkschijf op Windows, Linux, Android, iPhone","✔  Cockpit + remote shutdown"]),
            ("B","Methode B — Nextcloud","Eigen cloud · ~45 min",
             ["✔  Officiële apps · automatische foto-back-up"]),
            ("AB","Beide","Volledig · ~65 min",["✔  Alles van A én B"]),
        ]:
            sel=self.method.get()==val
            box=tk.Frame(self.content,bg=PANEL,highlightbackground=ACCENT if sel else PANEL,highlightthickness=2)
            box.pack(fill="x",pady=4)
            box.bind("<Button-1>",lambda e,v=val:(self.method.set(v),self._redraw()))
            top=tk.Frame(box,bg=PANEL,padx=14,pady=8); top.pack(fill="x")
            tk.Radiobutton(top,variable=self.method,value=val,bg=PANEL,activebackground=PANEL,
                           command=lambda:self._redraw()).pack(side="left")
            tk.Label(top,text=title,font=("Segoe UI",11,"bold"),
                     bg=PANEL,fg=ACCENT if sel else FG).pack(side="left")
            # Toon geïnstalleerd-badge
            if (val=="A" and samba_ok) or (val=="B" and nc_ok) or (val=="AB" and samba_ok and nc_ok):
                tk.Label(top,text=" ✔ geïnstalleerd",font=("Segoe UI",10),
                         bg=PANEL,fg=GREEN).pack(side="left",padx=8)
            tk.Label(top,text=f"   {sub}",font=("Segoe UI",9),bg=PANEL,fg=FG).pack(side="left")
            ff=tk.Frame(box,bg=PANEL,padx=50,pady=4); ff.pack(fill="x",pady=(0,6))
            for f in feats: tk.Label(ff,text=f,font=("Segoe UI",9),bg=PANEL,fg=FG).pack(anchor="w")

    # ══════════════════════════════════════════════════════════════════════════
    # CONFIGURATIE
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_config(self):
        self._head("Instellingen")
        m=self.method.get()
        if m in ("A","AB"):
            p=self._panel()
            tk.Label(p,text="Samba",font=("Segoe UI",12,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,6))
            self._row(p,"Gedeelde mapnaam:",self.share_name)
            self._row(p,"Gebruikersnaam:",self.samba_user)
            self._row(p,"Wachtwoord:",self.samba_pass,show="•")
            self._row(p,"Wachtwoord (herhaal):",self.samba_pass2,show="•")
            tk.Label(p,text="ℹ  Dit wachtwoord gebruik je op Windows, telefoon, etc.",
                     font=("Segoe UI",11),bg=PANEL,fg=WARN).pack(anchor="w",pady=(5,0))
        if m in ("B","AB"):
            p2=self._panel()
            tk.Label(p2,text="Nextcloud",font=("Segoe UI",12,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,6))
            self._row(p2,"Beheerder gebruikersnaam:",self.nc_admin)
            self._row(p2,"Beheerder wachtwoord:",self.nc_pass,show="•")
            self._row(p2,"Database wachtwoord:",self.nc_db_pass,show="•")

    def _validate_config(self):
        m=self.method.get()
        if m in ("A","AB"):
            if not self.share_name.get().strip(): messagebox.showerror("Ontbreekt","Vul een mapnaam in."); return False
            if not self.samba_pass.get(): messagebox.showerror("Ontbreekt","Voer een wachtwoord in."); return False
            if self.samba_pass.get()!=self.samba_pass2.get(): messagebox.showerror("Fout","Wachtwoorden komen niet overeen."); return False
            if len(self.samba_pass.get())<6: messagebox.showerror("Te kort","Minimaal 6 tekens."); return False
        if m in ("B","AB"):
            if not self.nc_pass.get() or not self.nc_db_pass.get():
                messagebox.showerror("Ontbreekt","Vul alle Nextcloud-velden in."); return False
        return True

    # ══════════════════════════════════════════════════════════════════════════
    # INSTALLATIE
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_install(self):
        self._head("Installatie")

        # Annuleren-knop bovenaan
        br=tk.Frame(self.content,bg=BG); br.pack(anchor="w",pady=(0,8))
        self._btn(br,"← Annuleren (terug naar methode)",
                  lambda:self._show_page(5),bg=BTN,fg=FG).pack(side="left")

        style=ttk.Style()
        style.configure("I.Horizontal.TProgressbar",troughcolor=PANEL2,background=GREEN,borderwidth=0,thickness=10)
        self.ipv=tk.DoubleVar()
        ttk.Progressbar(self.content,variable=self.ipv,style="I.Horizontal.TProgressbar",
                         maximum=100).pack(fill="x",pady=(0,6))
        self.ilbl=tk.Label(self.content,text="Bezig...",font=("Segoe UI",11),bg=BG,fg=ACCENT)
        self.ilbl.pack(anchor="w",pady=(0,4))
        self.inst_out=self._logw(self.content,14)

    def _start_install(self):
        threading.Thread(target=self._do_install,daemon=True).start()

    def _ilog(self,t,tag=None):
        self.after(0,lambda:(self.inst_out.insert(tk.END,t+"\n",tag or ""),self.inst_out.see(tk.END)))

    def _do_install(self):
        m=self.method.get(); share=self.share_name.get().strip()
        user=self.samba_user.get().strip(); passwd=self.samba_pass.get()
        mp=self.d_mp.get().strip() or "/mnt/opslag"; ip=get_ip()
        nc_adm=self.nc_admin.get().strip(); nc_pw=self.nc_pass.get(); nc_db=self.nc_db_pass.get()
        steps=[]
        if m in ("A","AB"):
            smb=(f"\\n[{share}]\\n   comment=Pi NAS\\n   path={mp}\\n"
                 f"   browseable=yes\\n   writable=yes\\n   valid users={user}\\n"
                 f"   create mask=0664\\n   directory mask=0775\\n   force user={user}\\n")
            steps+=[("apt update","sudo apt-get update -y"),
                    ("Samba","sudo apt-get install -y samba samba-common-bin"),
                    ("Rechten",f"sudo chown -R {user}:{user} {mp} && sudo chmod -R 775 {mp}"),
                    ("Samba gebruiker",f"(echo '{passwd}';echo '{passwd}')|sudo smbpasswd -a {user} -s"),
                    ("Samba config",f"printf '{smb}'|sudo tee -a /etc/samba/smb.conf>/dev/null"),
                    ("Samba starten","sudo systemctl restart smbd && sudo systemctl enable smbd"),
                    ("Cockpit","sudo apt-get install -y cockpit"),
                    ("Cockpit starten","sudo systemctl enable cockpit && sudo systemctl start cockpit")]
        if m in ("B","AB"):
            sql=(f"CREATE DATABASE IF NOT EXISTS nextcloud CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"
                 f"CREATE USER IF NOT EXISTS 'ncuser'@'localhost' IDENTIFIED BY '{nc_db}';"
                 f"GRANT ALL PRIVILEGES ON nextcloud.* TO 'ncuser'@'localhost';FLUSH PRIVILEGES;")
            nc_data=f"{mp}/nextcloud-data"
            steps+=[("Vereisten","sudo apt-get install -y apache2 mariadb-server php php-mysql php-gd "
                      "php-curl php-zip php-xml php-mbstring php-intl php-imagick php-bcmath php-gmp "
                      "libapache2-mod-php unzip wget"),
                    ("MariaDB","sudo systemctl start mariadb && sudo systemctl enable mariadb"),
                    ("Database",f'sudo mysql -u root -e "{sql}"'),
                    ("Nextcloud downloaden","cd /tmp && sudo wget -q -O latest.zip "
                      "https://download.nextcloud.com/server/releases/latest.zip"),
                    ("Uitpakken","cd /tmp && sudo unzip -q latest.zip"),
                    ("Plaatsen","sudo mv /tmp/nextcloud /var/www/html/ && sudo chown -R www-data:www-data /var/www/html/nextcloud"),
                    ("Datamap",f"sudo mkdir -p {nc_data} && sudo chown -R www-data:www-data {nc_data}"),
                    ("Apache","sudo a2enmod rewrite headers env dir mime && sudo systemctl restart apache2"),
                    ("Nextcloud init",f"sudo -u www-data php /var/www/html/nextcloud/occ maintenance:install "
                      f"--database mysql --database-name nextcloud --database-user ncuser "
                      f"--database-pass '{nc_db}' --admin-user '{nc_adm}' --admin-pass '{nc_pw}' --data-dir '{nc_data}'"),
                    ("Trusted host",f"sudo -u www-data php /var/www/html/nextcloud/occ config:system:set trusted_domains 1 --value={ip}"),
                    ("Voorbeeldbestanden verwijderen","sudo rm -rf /var/www/html/nextcloud/core/skeleton/*"),
                    ("Bestandsindex bijwerken",f"sudo -u www-data php /var/www/html/nextcloud/occ files:scan {nc_adm} --quiet 2>/dev/null")]
        total=len(steps)
        for i,(desc,cmd) in enumerate(steps,1):
            self.after(0,lambda v=((i-1)/total*100):self.ipv.set(v))
            self.after(0,lambda d=desc,ii=i,t=total:self.ilbl.config(text=f"Stap {ii}/{t}: {d}"))
            self._ilog(f"\n▶  {desc}","head")
            proc=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            for line in proc.stdout:
                s=line.rstrip()
                if s: self._ilog(f"   {s}")
            proc.wait()
            self._ilog("   ✔  Klaar" if proc.returncode==0 else f"   ⚠  Exitcode {proc.returncode}",
                       "ok" if proc.returncode==0 else "warn")
        self.after(0,lambda:self.ipv.set(100))
        self.after(0,lambda:self.ilbl.config(text="✅  Installatie voltooid!"))
        self._ilog("\n✅  KLAAR","ok")
        self.after(0,lambda:self.btn_next.config(state="normal"))

    # ══════════════════════════════════════════════════════════════════════════
    # GEREED
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_done(self):
        self._head("✅  Alles is klaar!",GREEN)
        m=self.method.get(); ip=get_ip(); share=self.share_name.get().strip() or "Opslag"
        def row(parent,lbl,val):
            r=tk.Frame(parent,bg=PANEL); r.pack(anchor="w",pady=2,fill="x")
            tk.Label(r,text=lbl,font=("Segoe UI",12,"bold"),bg=PANEL,fg=FG,width=28,anchor="w").pack(side="left")
            tk.Label(r,text=val,font=("Courier",10),bg=PANEL,fg=GREEN).pack(side="left")
        p0=self._panel()
        tk.Label(p0,text="Netwerk",font=("Segoe UI",12,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,5))
        row(p0,"IP-adres:",ip); row(p0,"SSH:",f"ssh pi@{ip}")
        if m in ("A","AB"):
            p=self._panel()
            tk.Label(p,text="Samba",font=("Segoe UI",12,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,5))
            row(p,"Windows:",f"\\\\{ip}\\{share}"); row(p,"iPhone:",f"smb://{ip}")
            row(p,"Android:",f"Server: {ip}  Share: {share}"); row(p,"Cockpit:",f"http://{ip}:9090")
        if m in ("B","AB"):
            p2=self._panel()
            tk.Label(p2,text="Nextcloud",font=("Segoe UI",12,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,5))
            row(p2,"Browser:",f"http://{ip}/nextcloud"); row(p2,"Gebruiker:",self.nc_admin.get())
        p3=self._panel()
        tk.Label(p3,text="⚠  Afsluiten:",font=("Segoe UI",12,"bold"),bg=PANEL,fg=WARN).pack(anchor="w",pady=(0,3))
        for tip in [f"Cockpit: http://{ip}:9090","Terminal: sudo shutdown -h now",
                    "Wacht ~30 sec voor je de schijfbehuizing uitzet."]:
            tk.Label(p3,text=f"  • {tip}",font=("Segoe UI",11),bg=PANEL,fg=FG).pack(anchor="w")

    # ══════════════════════════════════════════════════════════════════════════
    # INITIËLE SETUP
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_initsetup(self):
        self._head("🚀  Initiële setup — alles in één")
        tk.Label(self.content,
                 text="Vul de essentiële instellingen in. De wizard regelt daarna alles automatisch.",
                 font=("Segoe UI",11),bg=BG,fg=FG,justify="left").pack(anchor="w",pady=(0,8))
        p0=self._panel()
        tk.Label(p0,text="Gevonden schijven",font=("Segoe UI",12,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,4))
        drives=sh("lsblk -o NAME,SIZE,TYPE -rn | grep disk")
        for line in (drives.splitlines() or ["Geen schijven gevonden"]):
            tk.Label(p0,text=f"  {line}",font=("Courier",10),bg=PANEL,fg=GREEN).pack(anchor="w")
        if not is_connected():
            p1=self._panel()
            tk.Label(p1,text="WiFi (niet verbonden)",font=("Segoe UI",12,"bold"),bg=PANEL,fg=WARN).pack(anchor="w",pady=(0,6))
            self._row(p1,"WiFi netwerknaam:",self.wifi_ssid); self._row(p1,"WiFi wachtwoord:",self.wifi_pass,show="•")
        p2=self._panel()
        tk.Label(p2,text="Schijf",font=("Segoe UI",12,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,6))
        self._row(p2,"Schijf (bijv. /dev/sda):",self.d_dev); self._row(p2,"Mountpunt:",self.d_mp)
        opt=tk.Frame(p2,bg=PANEL); opt.pack(anchor="w",pady=(4,0))
        tk.Checkbutton(opt,text="  Schijf formatteren als ext4 (wist alle data!)",
                       variable=self.d_fmt,bg=PANEL,fg=WARN,selectcolor=PANEL2,
                       activebackground=PANEL,font=("Segoe UI",11)).pack(side="left")
        p3=self._panel()
        tk.Label(p3,text="NAS-software",font=("Segoe UI",12,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,6))
        mf=tk.Frame(p3,bg=PANEL); mf.pack(anchor="w")
        for val,lbl in [("A","Samba + Cockpit (aanbevolen)"),("B","Nextcloud"),("AB","Beide")]:
            r=tk.Frame(mf,bg=PANEL); r.pack(anchor="w",pady=1)
            tk.Radiobutton(r,variable=self.method,value=val,bg=PANEL,activebackground=PANEL,selectcolor=PANEL2).pack(side="left")
            tk.Label(r,text=lbl,font=("Segoe UI",11),bg=PANEL,fg=FG).pack(side="left")
        self._row(p3,"Gedeelde mapnaam:",self.share_name); self._row(p3,"Gebruikersnaam:",self.samba_user)
        self._row(p3,"Wachtwoord:",self.samba_pass,show="•"); self._row(p3,"Wachtwoord (herhaal):",self.samba_pass2,show="•")
        self._btn(self.content,"▶  Alles installeren",self._run_initsetup,bg=GREEN,fg=BG,bold=True).pack(anchor="w",pady=8)
        self.init_out=self._logw(self.content,7)

    def _run_initsetup(self):
        if not self.samba_pass.get(): messagebox.showerror("Ontbreekt","Voer een wachtwoord in."); return
        if self.samba_pass.get()!=self.samba_pass2.get(): messagebox.showerror("Fout","Wachtwoorden komen niet overeen."); return
        if len(self.samba_pass.get())<6: messagebox.showerror("Te kort","Minimaal 6 tekens."); return
        self.btn_next.config(state="disabled"); self.init_out.delete("1.0",tk.END)
        def log(t,tag=None):
            self.after(0,lambda:(self.init_out.insert(tk.END,t+"\n",tag or ""),self.init_out.see(tk.END)))
        def run():
            log("════════════════════════════════","head")
            log("  INITIËLE SETUP","head"); log("════════════════════════════════","head")
            if not is_connected() and self.wifi_ssid.get().strip():
                log("\n▶  WiFi verbinden...","head")
                pwd=self.wifi_pass.get()
                cmd=f'sudo nmcli dev wifi connect "{self.wifi_ssid.get()}"'+(f' password "{pwd}"' if pwd else "")
                r=sh(f"{cmd} 2>&1")
                log(f"   {'✔  '+get_ip() if is_connected() else '⚠  '+r[:60]}","ok" if is_connected() else "warn")
            log("\n▶  SSH...","head"); sh("sudo systemctl enable ssh && sudo systemctl start ssh"); log("   ✔  SSH actief","ok")
            log("\n▶  Bijwerken (kan even duren)...","head")
            proc=subprocess.Popen("sudo apt-get update -y && sudo apt-get upgrade -y",shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            for line in proc.stdout:
                s=line.rstrip()
                if s and any(k in s for k in ["upgraded","Get:","Setting up"]): log(f"   {s}")
            proc.wait(); log("   ✔  Bijgewerkt","ok")
            dev=fix_dev(self.d_dev.get()); mp=self.d_mp.get().strip(); user=self.samba_user.get().strip() or "pi"
            log(f"\n▶  Schijf koppelen: {dev} → {mp}...","head")
            if self.d_fmt.get():
                for desc,cmd in fs_format_cmds(dev,"ext4"):
                    subprocess.run(cmd,shell=True)
                    log(f"   ✔  {desc}","ok")
            subprocess.run(f"sudo mkdir -p {mp}",shell=True)
            uuid=sh(f"sudo blkid -s UUID -o value {dev}")
            if uuid:
                fstab=sh("cat /etc/fstab")
                if uuid not in fstab:
                    entry=f"UUID={uuid}  {mp}  ext4  defaults,nofail  0  2\n"
                    subprocess.run(f"echo '{entry}' | sudo tee -a /etc/fstab",shell=True)
                subprocess.run("sudo mount -a",shell=True)
                subprocess.run(f"sudo chown -R {user}:{user} {mp} && sudo chmod -R 775 {mp}",shell=True)
                update_rechten_service()
                log(f"   ✔  Gekoppeld op {mp}","ok")
            else: log("   ⚠  Geen UUID — schijf niet gevonden","warn")
            log("\n▶  NAS-software...","head")
            self.inst_out=self.init_out
            self._do_install()
            log("\n════════════════════════════════","ok"); log("  ✅  KLAAR!","ok")
            log(f"  IP: {get_ip()}","info")
            share=self.share_name.get().strip() or "Opslag"
            log(f"  Windows: \\\\{get_ip()}\\{share}","info")
            log("════════════════════════════════","ok")
            self.after(0,lambda:self.btn_next.config(state="normal"))
        threading.Thread(target=run,daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # FILEBROWSER
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_filebrowser(self):
        self._head("🌐  FileBrowser — webbeheer bestanden",FG)
        ip=get_ip()
        fb_actief=bool(sh("pgrep -x filebrowser 2>/dev/null")) or \
                  sh("systemctl is-active filebrowser 2>/dev/null").strip()=="active"
        fb_installed=bool(sh("which filebrowser 2>/dev/null"))
        fb_enabled=sh("systemctl is-enabled filebrowser 2>/dev/null").strip()=="enabled"

        # Status
        if fb_installed:
            color=GREEN if fb_actief else WARN
            status="actief" if fb_actief else "gestopt"
            p0=self._panel(color="#1e3a2a" if fb_actief else "#3a2a1e")
            r=tk.Frame(p0,bg=p0["bg"]); r.pack(anchor="w",fill="x")
            tk.Label(r,text=f"{'✅' if fb_actief else '⚠'}  FileBrowser {status}",
                     font=("Segoe UI",11,"bold"),bg=p0["bg"],fg=color).pack(side="left")
            if fb_actief:
                self._btn(r,f"🌐  Openen: http://{ip}:8080",
                          lambda:self._open_browser(f"http://{ip}:8080"),
                          bg=MAGENTA,fg=BG,bold=True).pack(side="right")
            tk.Label(p0,text="Gebruikersnaam: admin  |  Wachtwoord: ingesteld bij eerste installatie",
                     font=("Segoe UI",9),bg=p0["bg"],fg=FG).pack(anchor="w")
        else:
            p0=self._panel(color="#3a2a1e")
            tk.Label(p0,text="FileBrowser is niet geïnstalleerd",
                     font=("Segoe UI",11,"bold"),bg="#3a2a1e",fg=WARN).pack(anchor="w")
            tk.Label(p0,text="FileBrowser geeft webbeheer voor bestanden via http://[IP]:8080",
                     font=("Segoe UI",9),bg="#3a2a1e",fg=FG).pack(anchor="w")

        # Installatie
        p=self._panel()
        tk.Label(p,text="Installatie",font=("Segoe UI",10,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,6))
        tk.Label(p,text="Rootmap: /mnt  —  Poort: 8080  —  Gebruiker: admin",
                 font=("Segoe UI",9),bg=PANEL,fg=FG).pack(anchor="w",pady=(0,6))
        br=tk.Frame(p,bg=PANEL); br.pack(anchor="w")
        self._btn(br,"🌐  FileBrowser installeren",self._fb_install,bg=MAGENTA,fg=BG,bold=True).pack(side="left",padx=(0,8))
        self._btn(br,"🗑  Verwijderen",lambda:sh("sudo systemctl stop filebrowser; sudo systemctl disable filebrowser; sudo rm -f /usr/local/bin/filebrowser /etc/systemd/system/filebrowser.service") or self._jump(10),bg=WARN,fg=BG).pack(side="left")

        # Beheer
        p2=self._panel()
        tk.Label(p2,text="Beheer",font=("Segoe UI",10,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,6))
        br2=tk.Frame(p2,bg=PANEL); br2.pack(anchor="w",pady=(0,4))
        self._btn(br2,"▶  Starten",self._fb_start,bg=GREEN,fg=BG).pack(side="left",padx=(0,8))
        self._btn(br2,"⏹  Stoppen",self._fb_stop,bg=BTN,fg=FG).pack(side="left",padx=(0,8))
        if fb_enabled:
            self._btn(br2,"Uitschakelen bij opstarten",
                      lambda:sh("sudo systemctl disable filebrowser") or self._jump(10),bg=BTN,fg=FG).pack(side="left")
        else:
            self._btn(br2,"Inschakelen bij opstarten",
                      lambda:sh("sudo systemctl enable filebrowser") or self._jump(10),bg=ACCENT,fg=BG).pack(side="left")
        br3=tk.Frame(p2,bg=PANEL); br3.pack(anchor="w",pady=(4,0))
        self._btn(br3,"🔑  Wachtwoord resetten",self._fb_reset,bg=BTN,fg=FG).pack(side="left")

        self.fb_out=self._logw(self.content,6)

    def _fb_log(self,t,tag=None):
        self.after(0,lambda:(self.fb_out.insert(tk.END,t+"\n",tag or ""),self.fb_out.see(tk.END)))

    def _fb_install(self):
        self.fb_out.delete("1.0",tk.END)
        def bg():
            self._fb_log("▶  FileBrowser installeren...","head")
            if not sh("which filebrowser"):
                proc=subprocess.Popen("curl -fsSL https://raw.githubusercontent.com/filebrowser/get/master/get.sh | bash",
                                       shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
                for line in proc.stdout: self._fb_log(f"   {line.rstrip()}")
                proc.wait()
            svc="""[Unit]
Description=FileBrowser NAS
After=network.target

[Service]
ExecStart=/usr/local/bin/filebrowser -r /mnt -a 0.0.0.0 -p 8080 -d /home/pi/filebrowser.db
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
"""
            with open("/tmp/filebrowser.service","w") as f: f.write(svc)
            sh("sudo cp /tmp/filebrowser.service /etc/systemd/system/filebrowser.service")
            sh("sudo systemctl daemon-reload && sudo systemctl enable filebrowser && sudo systemctl start filebrowser")
            import time; time.sleep(2)
            ip=get_ip()
            self._fb_log(f"✅  FileBrowser actief op http://{ip}:8080","ok")
            self._fb_log("   Gebruikersnaam: admin","info")
            self._fb_log("   Wachtwoord: zie terminal bij eerste start","info")
        threading.Thread(target=bg,daemon=True).start()

    def _fb_start(self):
        self.fb_out.delete("1.0",tk.END)
        sh("sudo systemctl start filebrowser 2>/dev/null || filebrowser -r /mnt -a 0.0.0.0 -p 8080 -d /home/pi/filebrowser.db &")
        import time; time.sleep(1)
        ip=get_ip()
        self.fb_out.insert(tk.END,f"✅  Gestart op http://{ip}:8080\n","ok")

    def _fb_stop(self):
        self.fb_out.delete("1.0",tk.END)
        sh("sudo systemctl stop filebrowser 2>/dev/null; pkill filebrowser 2>/dev/null")
        self.fb_out.insert(tk.END,"✅  FileBrowser gestopt.\n","ok")

    def _fb_reset(self):
        self.fb_out.delete("1.0",tk.END)
        sh("sudo systemctl stop filebrowser 2>/dev/null; rm -f /home/pi/filebrowser.db")
        sh("sudo systemctl start filebrowser 2>/dev/null")
        self.fb_out.insert(tk.END,"✅  Database gereset — nieuw wachtwoord in service-log:\n","ok")
        self.fb_out.insert(tk.END,"sudo journalctl -u filebrowser -n 10 --no-pager\n","info")

    # ══════════════════════════════════════════════════════════════════════════
    # DESKTOP
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_desktop(self):
        self._head("🖥️  Desktop & VNC",FG)
        has_desktop=sh("dpkg -l lxde-core 2>/dev/null | grep -c '^ii'").strip()=="1"
        vnc_ok=bool(sh("dpkg -l realvnc-vnc-server 2>/dev/null | grep -c '^ii'").strip()=="1")
        ip=get_ip()
        avail=sh("df -BG / | tail -1 | awk '{print $4}'").replace("G","").strip()

        p=self._panel(color="#1e3a1e" if has_desktop else PANEL)
        tk.Label(p,text="✅  Desktop (LXDE) geïnstalleerd" if has_desktop else "ℹ  Geen desktop — Lite modus",
                 font=("Segoe UI",12,"bold"),bg=p["bg"],fg=GREEN if has_desktop else FG).pack(anchor="w")
        tk.Label(p,text=f"VNC: {'✅ geïnstalleerd op '+ip+':5900' if vnc_ok else 'niet geïnstalleerd'}",
                 font=("Segoe UI",11),bg=p["bg"],fg=GREEN if vnc_ok else YELLOW).pack(anchor="w",pady=(3,0))
        tk.Label(p,text=f"SD-kaart vrij: {avail}GB",
                 font=("Segoe UI",11),bg=p["bg"],fg=FG).pack(anchor="w",pady=(3,0))

        p2=self._panel()
        tk.Label(p2,text="Desktop",font=("Segoe UI",12,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,4))
        tk.Label(p2,text="~500MB · ~10 min · Pi 4 trager · Pi 5 nauwelijks verschil",
                 font=("Segoe UI",11),bg=PANEL,fg=FG).pack(anchor="w",pady=(0,6))
        br=tk.Frame(p2,bg=PANEL); br.pack(anchor="w",pady=(0,4))
        self._btn(br,"🖥️  Desktop installeren",self._desktop_install,bg=ACCENT,fg=BG,bold=True).pack(side="left",padx=(0,8))
        self._btn(br,"🗑  Desktop verwijderen",self._desktop_remove,bg=WARN,fg=BG).pack(side="left")

        p3=self._panel()
        tk.Label(p3,text="VNC — grafische omgeving via Windows/tablet",
                 font=("Segoe UI",12,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,4))
        tk.Label(p3,text=f"Verbind via VNC Viewer: {ip}:5900\n"
                          "Download: https://www.realvnc.com/en/connect/download/viewer/",
                 font=("Segoe UI",11),bg=PANEL,fg=FG,justify="left").pack(anchor="w",pady=(0,6))
        br2=tk.Frame(p3,bg=PANEL); br2.pack(anchor="w",pady=(0,3))
        self._btn(br2,"📺  VNC installeren",self._vnc_install,bg=TEAL,fg=BG,bold=True).pack(side="left",padx=(0,6))
        self._btn(br2,"▶  Starten",self._vnc_start,bg=GREEN,fg=BG).pack(side="left",padx=(0,6))
        br3=tk.Frame(p3,bg=PANEL); br3.pack(anchor="w",pady=(0,2))
        self._btn(br3,"⏹  Stoppen",self._vnc_stop,bg=BTN,fg=FG).pack(side="left",padx=(0,6))
        self._btn(br3,"🗑  VNC verwijderen",self._vnc_remove,bg=WARN,fg=BG).pack(side="left")

        self.desk_out=self._logw(self.content,6)

    def _vnc_remove(self):
        if not messagebox.askyesno("VNC verwijderen","VNC verwijderen van de Pi?"): return
        self.desk_out.delete("1.0",tk.END)
        self._run_bg([
            ("VNC stoppen","sudo systemctl stop vncserver-x11-serviced 2>/dev/null"),
            ("VNC uitschakelen","sudo systemctl disable vncserver-x11-serviced 2>/dev/null"),
            ("VNC verwijderen","sudo apt-get remove -y realvnc-vnc-server"),
            ("Opruimen","sudo apt-get autoremove -y"),
        ],self.desk_out,on_done=lambda:self._dei_log("✅  VNC verwijderd","ok"))

    def _vnc_install(self):
        self.desk_out.delete("1.0",tk.END)
        ip=get_ip()
        def done():
            self._dei_log(f"✅  VNC geïnstalleerd en actief op {ip}:5900","ok")
            self._dei_log("   Inloggen met Pi OS gebruikersnaam en wachtwoord","info")
            self._dei_log("   VNC Viewer: https://www.realvnc.com/en/connect/download/viewer/","info")
        self._run_bg([
            ("apt update","sudo apt-get update -y"),
            ("RealVNC installeren","sudo apt-get install -y realvnc-vnc-server"),
            ("VNC inschakelen","sudo systemctl enable vncserver-x11-serviced"),
            ("VNC starten","sudo systemctl start vncserver-x11-serviced"),
        ],self.desk_out,on_done=done)

    def _vnc_start(self):
        self.desk_out.delete("1.0",tk.END)
        sh("sudo systemctl start vncserver-x11-serviced 2>/dev/null")
        ip=get_ip()
        self.desk_out.insert(tk.END,f"✅  VNC gestart op {ip}:5900\n","ok")

    def _vnc_stop(self):
        self.desk_out.delete("1.0",tk.END)
        sh("sudo systemctl stop vncserver-x11-serviced 2>/dev/null")
        self.desk_out.insert(tk.END,"✅  VNC gestopt\n","ok")

    def _desktop_install(self):
        if not messagebox.askyesno("Desktop installeren",
                                    "~500MB installatie, ~10 min.\nPi herstart daarna.\nDoorgaan?"): return
        self.desk_out.delete("1.0",tk.END)
        def done():
            self.desk_out.insert(tk.END,"\n✅  Desktop geïnstalleerd! Pi herstart...\n","ok")
            import time; time.sleep(2); sh("sudo reboot")
        self._run_bg([("apt update","sudo apt-get update -y"),
                      ("Desktop installeren","sudo apt-get install -y xorg lxde-core lightdm"),
                      ("Tkinter","sudo apt-get install -y python3-tk"),
                      ("Grafische opstart","sudo systemctl set-default graphical.target")],
                     self.desk_out,on_done=done)

    def _desktop_remove(self):
        if not messagebox.askyesno("Desktop verwijderen","Pi keert terug naar tekstmodus.\nNAS blijft werken.\nDoorgaan?"): return
        self.desk_out.delete("1.0",tk.END)
        def done():
            self.desk_out.insert(tk.END,"\n✅  Desktop verwijderd. Pi herstart...\n","ok")
            import time; time.sleep(2); sh("sudo reboot")
        self._run_bg([("Desktop verwijderen","sudo apt-get remove -y lxde-core lxde lightdm xorg"),
                      ("Opruimen","sudo apt-get autoremove -y"),
                      ("Tekstmodus","sudo systemctl set-default multi-user.target")],
                     self.desk_out,on_done=done)

    # ══════════════════════════════════════════════════════════════════════════
    # SSH SLEUTEL
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_sshkey(self):
        self._head("🔑  SSH-sleutel beheren",FG)
        ip=get_ip()
        keys=sh("cat /home/pi/.ssh/authorized_keys 2>/dev/null | wc -l")
        has_keys=keys and int(keys)>0
        pw_auth=sh("sudo grep -E '^PasswordAuthentication' /etc/ssh/sshd_config 2>/dev/null")
        pw_off="no" in pw_auth.lower()
        p=self._panel(color="#1e3a1e" if has_keys else PANEL)
        tk.Label(p,text=f"✅  {keys} SSH-sleutel(s) aanwezig" if has_keys else "⚠  Nog geen SSH-sleutel",
                 font=("Segoe UI",12,"bold"),bg=p["bg"],fg=GREEN if has_keys else WARN).pack(anchor="w")
        p2=self._panel()
        tk.Label(p2,text="SSH-sleutel instellen — voer dit eenmalig uit op Windows (PowerShell):",
                 font=("Segoe UI",12,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,6))
        for cmd in [("Stap 1 — Sleutel aanmaken:","ssh-keygen -t ed25519"),
                    ("Stap 2 — Naar Pi kopiëren:",
                     f'type C:\\Users\\NAAM\\.ssh\\id_ed25519.pub | ssh pi@{ip} "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"')]:
            tk.Label(p2,text=cmd[0],font=("Segoe UI",11),bg=PANEL,fg=FG).pack(anchor="w",pady=(3,0))
            tf=tk.Frame(p2,bg=PANEL2,padx=8,pady=5); tf.pack(fill="x",pady=(2,4))
            tk.Label(tf,text=cmd[1],font=("Courier",8),bg=PANEL2,fg=GREEN,wraplength=560,justify="left").pack(anchor="w")
        tk.Label(p2,text="Vervang NAAM door je Windows-gebruikersnaam.",
                 font=("Segoe UI",11),bg=PANEL,fg=YELLOW).pack(anchor="w",pady=(0,4))
        p3=self._panel()
        tk.Label(p3,text="Wachtwoordlogin",font=("Segoe UI",12,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,4))
        status="✅  Uitgeschakeld (alleen SSH-sleutel)" if pw_off else "ℹ  Ingeschakeld (standaard)"
        tk.Label(p3,text=status,font=("Segoe UI",11),bg=PANEL,fg=GREEN if pw_off else FG).pack(anchor="w",pady=(0,6))
        if not pw_off:
            tk.Label(p3,text="⚠  Schakel alleen uit als je SSH-sleutel werkt!",
                     font=("Segoe UI",11),bg=PANEL,fg=WARN).pack(anchor="w",pady=(0,6))
        br=tk.Frame(p3,bg=PANEL); br.pack(anchor="w")
        self._btn(br,"Wachtwoordlogin uitschakelen",self._ssh_pw_off,bg=WARN,fg=BG).pack(side="left",padx=(0,8))
        self._btn(br,"Wachtwoordlogin inschakelen",self._ssh_pw_on,bg=BTN,fg=FG).pack(side="left")
        self.key_lbl=tk.Label(self.content,text="",font=("Segoe UI",11),bg=BG,fg=FG)
        self.key_lbl.pack(anchor="w",pady=(6,0))

    def _ssh_pw_off(self):
        keys=sh("cat /home/pi/.ssh/authorized_keys 2>/dev/null | wc -l")
        if not keys or int(keys)==0:
            messagebox.showerror("Gevaarlijk!","Geen SSH-sleutel aanwezig!\nUitschakelen zou je buitensluiten."); return
        if not messagebox.askyesno("Bevestigen","Wachtwoordlogin uitschakelen?\nAlleen SSH-sleutel werkt nog."): return
        sh("sudo sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config")
        sh("sudo systemctl restart ssh")
        self.key_lbl.config(text="✅  Wachtwoordlogin uitgeschakeld.",fg=GREEN)

    def _ssh_pw_on(self):
        sh("sudo sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config")
        sh("sudo systemctl restart ssh")
        self.key_lbl.config(text="✅  Wachtwoordlogin ingeschakeld.",fg=GREEN)


# ────────────────────────────────────────────────────────────────────────────
    def _pg_deinstall(self):
        self._head("🗑  Software deïnstalleren",RED)
        tk.Label(self.content,
                 text="Verwijder NAS-software. Data op schijven blijft altijd bewaard.\n"
                      "Pi OS blijft intact — Pi blijft werken.",
                 font=("Segoe UI",11),bg=BG,fg=FG,justify="left").pack(anchor="w",pady=(0,8))

        # Status
        samba_ok  = sh("dpkg -l samba 2>/dev/null | grep -c '^ii'").strip()=="1"
        nc_ok     = os.path.exists("/var/www/html/nextcloud")
        fb_ok     = bool(sh("which filebrowser 2>/dev/null"))
        ck_ok     = sh("dpkg -l cockpit 2>/dev/null | grep -c '^ii'").strip()=="1"
        desk_ok   = sh("dpkg -l lxde-core 2>/dev/null | grep -c '^ii'").strip()=="1"

        p=self._panel()
        tk.Label(p,text="Geïnstalleerde software:",font=("Segoe UI",12,"bold"),
                 bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,6))
        for naam,status in [("Samba",samba_ok),("Nextcloud",nc_ok),
                             ("FileBrowser",fb_ok),("Cockpit",ck_ok),
                             ("Desktop (LXDE)",desk_ok)]:
            r=tk.Frame(p,bg=PANEL); r.pack(anchor="w",pady=1)
            tk.Label(r,text="✔" if status else "✗",
                     font=("Segoe UI",12,"bold"),bg=PANEL,
                     fg=GREEN if status else PANEL2).pack(side="left",padx=(0,8))
            tk.Label(r,text=naam,font=("Segoe UI",11),bg=PANEL,fg=FG).pack(side="left")

        # Knoppen
        p2=self._panel()
        tk.Label(p2,text="Verwijderen:",font=("Segoe UI",12,"bold"),
                 bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,6))
        for naam,cmd,enabled in [
            ("Samba",    self._dei_samba,    samba_ok),
            ("Nextcloud",self._dei_nextcloud,nc_ok),
            ("FileBrowser",self._dei_fb,    fb_ok),
            ("Cockpit",  self._dei_cockpit,  ck_ok),
            ("Desktop",  self._dei_desktop,  desk_ok),
            ("Samba shares (data blijft bewaard)", self._dei_shares, samba_ok),
        ]:
            self._btn(p2,f"🗑  {naam} verwijderen",cmd,
                      bg=WARN if enabled else BTN,
                      fg=BG if enabled else PANEL2).pack(anchor="w",pady=2)

        # Alles verwijderen
        p3=self._panel()
        tk.Label(p3,text="⚠  Volledige software reset",font=("Segoe UI",12,"bold"),
                 bg=PANEL,fg=RED).pack(anchor="w",pady=(0,4))
        tk.Label(p3,text="Verwijdert alles: Samba, Nextcloud, FileBrowser, Cockpit, Desktop.\n"
                          "Data op schijven blijft bewaard. Pi OS blijft intact.",
                 font=("Segoe UI",11),bg=PANEL,fg=FG,justify="left").pack(anchor="w",pady=(0,6))
        self._btn(p3,"🗑  Alles verwijderen",self._dei_alles,bg=RED,fg=BG,bold=True).pack(anchor="w")

        self.dei_out=self._logw(self.content,6)

    def _dei_log(self,t,tag=None):
        self.after(0,lambda:(self.dei_out.insert(tk.END,t+"\n",tag or ""),self.dei_out.see(tk.END)))

    def _dei_shares(self):
        if not messagebox.askyesno("Bevestigen",
            "Alle Samba shares verwijderen?\n\nMappen en data op schijven blijven BEWAARD.\n"
            "Alleen de share-definities worden verwijderd."): return
        self.dei_out.delete("1.0",tk.END)
        def bg():
            conf=sh("cat /etc/samba/smb.conf")
            lines=conf.splitlines()
            new=[]; skip=False
            system_sections=["global","homes","printers","print$"]
            for line in lines:
                stripped=line.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    section=stripped[1:-1].lower()
                    skip=section not in system_sections
                if not skip: new.append(line)
            with open("/tmp/smb_new.conf","w") as f: f.write("\n".join(new))
            sh("sudo cp /tmp/smb_new.conf /etc/samba/smb.conf")
            subprocess.run("sudo systemctl restart smbd",shell=True)
            self.after(0,lambda:(
                self._dei_log("✅  Shares verwijderd — data bewaard","ok"),
                self._dei_log("   Gebruik Beheer → Standaard aanmaken om shares opnieuw aan te maken.","info")))
        import threading; threading.Thread(target=bg,daemon=True).start()

    def _dei_samba(self):
        if not messagebox.askyesno("Bevestigen","Samba verwijderen?\nData blijft bewaard."): return
        self.dei_out.delete("1.0",tk.END)
        self._run_bg([("Samba stoppen","sudo systemctl stop smbd nmbd 2>/dev/null"),
                      ("Samba verwijderen","sudo apt-get remove -y samba samba-common-bin"),
                      ("Opruimen","sudo apt-get autoremove -y")],
                     self.dei_out,on_done=lambda:self._dei_log("✅  Samba verwijderd","ok"))

    def _dei_nextcloud(self):
        if not messagebox.askyesno("Bevestigen",
                "Nextcloud verwijderen?\nData in /mnt/opslag/nextcloud-data blijft bewaard."): return
        self.dei_out.delete("1.0",tk.END)
        self._run_bg([("Services stoppen","sudo systemctl stop apache2 mariadb 2>/dev/null"),
                      ("Nextcloud verwijderen","sudo rm -rf /var/www/html/nextcloud"),
                      ("Pakketten","sudo apt-get remove -y apache2 mariadb-server 'php*' libapache2-mod-php"),
                      ("Opruimen","sudo apt-get autoremove -y")],
                     self.dei_out,on_done=lambda:self._dei_log("✅  Nextcloud verwijderd","ok"))

    def _dei_fb(self):
        if not messagebox.askyesno("Bevestigen","FileBrowser verwijderen?"): return
        self.dei_out.delete("1.0",tk.END)
        sh("sudo systemctl stop filebrowser 2>/dev/null")
        sh("sudo systemctl disable filebrowser 2>/dev/null")
        sh("sudo rm -f /etc/systemd/system/filebrowser.service /usr/local/bin/filebrowser")
        sh("sudo systemctl daemon-reload")
        self.dei_out.insert(tk.END,"✅  FileBrowser verwijderd\n","ok")

    def _dei_cockpit(self):
        if not messagebox.askyesno("Bevestigen","Cockpit verwijderen?"): return
        self.dei_out.delete("1.0",tk.END)
        self._run_bg([("Cockpit stoppen","sudo systemctl stop cockpit 2>/dev/null"),
                      ("Cockpit verwijderen","sudo apt-get remove -y cockpit"),
                      ("Opruimen","sudo apt-get autoremove -y")],
                     self.dei_out,on_done=lambda:self._dei_log("✅  Cockpit verwijderd","ok"))

    def _dei_desktop(self):
        if not messagebox.askyesno("Bevestigen","Desktop verwijderen?\nPi start daarna op in tekstmodus."): return
        self.dei_out.delete("1.0",tk.END)
        def done():
            self._dei_log("✅  Desktop verwijderd","ok")
            if messagebox.askyesno("Herstarten","Pi herstarten?"):
                sh("sudo reboot")
        self._run_bg([("Desktop verwijderen","sudo apt-get remove -y lxde-core lxde lightdm xorg"),
                      ("Opruimen","sudo apt-get autoremove -y"),
                      ("Tekstmodus","sudo systemctl set-default multi-user.target")],
                     self.dei_out,on_done=done)

    def _dei_alles(self):
        if not messagebox.askyesno("BEVESTIGEN",
                "Alles verwijderen: Samba, Nextcloud, FileBrowser, Cockpit, Desktop?\n"
                "Data op schijven blijft bewaard."): return
        if not messagebox.askyesno("TWEEDE BEVESTIGING","Echt alles verwijderen?"): return
        self.dei_out.delete("1.0",tk.END)
        self._run_bg([
            ("Samba stoppen","sudo systemctl stop smbd nmbd 2>/dev/null; sudo apt-get remove -y samba samba-common-bin"),
            ("Nextcloud","sudo systemctl stop apache2 mariadb 2>/dev/null; sudo rm -rf /var/www/html/nextcloud; sudo apt-get remove -y apache2 mariadb-server 'php*' libapache2-mod-php"),
            ("FileBrowser","sudo systemctl stop filebrowser 2>/dev/null; sudo rm -f /usr/local/bin/filebrowser /etc/systemd/system/filebrowser.service"),
            ("Cockpit","sudo apt-get remove -y cockpit"),
            ("Desktop","sudo apt-get remove -y lxde-core lxde lightdm xorg 2>/dev/null; sudo systemctl set-default multi-user.target"),
            ("Opruimen","sudo apt-get autoremove -y; sudo systemctl daemon-reload"),
        ],self.dei_out,on_done=lambda:(
            self._dei_log("\n✅  Alles verwijderd — Pi OS is schoon.","ok"),
            self._dei_log("   Data op externe schijven is onaangeroerd.","info")))


    # ══════════════════════════════════════════════════════════════════════════
    # CONFIGURATIE EXPORT/IMPORT
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_nasconfig(self):
        self._head("💾  Configuratie export/import",FG)
        ip=get_ip()
        p=self._panel()
        tk.Label(p,text="Configuratie exporteren",font=("Segoe UI",11,"bold"),
                 bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,4))
        tk.Label(p,text="Slaat alle instellingen op naar 4 locaties:\n"
                        "/mnt/opslag · /mnt/backup · /boot/firmware · /home/pi",
                 font=("Segoe UI",9),bg=PANEL,fg=FG,justify="left").pack(anchor="w",pady=(0,6))
        self._btn(p,"💾  Exporteren",self._nasconfig_export,bg=GREEN,fg=BG,bold=True).pack(anchor="w")
        p2=self._panel()
        tk.Label(p2,text="Configuratie importeren",font=("Segoe UI",11,"bold"),
                 bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,4))
        tk.Label(p2,text="Herstelt fstab, Samba-shares en FileBrowser na herinstallatie of Pi-wissel.",
                 font=("Segoe UI",9),bg=PANEL,fg=FG,justify="left").pack(anchor="w",pady=(0,6))
        self._btn(p2,"📥  Importeren",self._nasconfig_import,bg=ACCENT,fg=BG,bold=True).pack(anchor="w")
        p3=self._panel()
        tk.Label(p3,text="Synchroniseren",font=("Segoe UI",11,"bold"),
                 bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,4))
        tk.Label(p3,text="Zorgt dat alle 4 kopieën up-to-date zijn.",
                 font=("Segoe UI",9),bg=PANEL,fg=FG).pack(anchor="w",pady=(0,6))
        self._btn(p3,"🔄  Synchroniseren",self._nasconfig_sync,bg=BTN,fg=FG).pack(anchor="w")
        self.cfg_out=self._logw(self.content,6)

    def _nasconfig_export(self):
        self.cfg_out.delete("1.0",tk.END)
        def bg():
            r=subprocess.run("sudo python3 /home/pi/nas_config.py",
                             input="1\n\n",shell=True,capture_output=True,text=True)
            self.after(0,lambda:(
                self.cfg_out.insert(tk.END,r.stdout+"\n"),
                self.cfg_out.insert(tk.END,"✅  Export klaar\n","ok"),
                self.cfg_out.see(tk.END)))
        threading.Thread(target=bg,daemon=True).start()

    def _nasconfig_import(self):
        if not messagebox.askyesno("Importeren","Configuratie importeren?\nHerstelt fstab en Samba-shares."): return
        self.cfg_out.delete("1.0",tk.END)
        def bg():
            r=subprocess.run("sudo python3 /home/pi/nas_config.py",
                             input="2\nj\n\n",shell=True,capture_output=True,text=True)
            self.after(0,lambda:(
                self.cfg_out.insert(tk.END,r.stdout+"\n"),
                self.cfg_out.insert(tk.END,"✅  Import klaar\n","ok"),
                self.cfg_out.see(tk.END)))
        threading.Thread(target=bg,daemon=True).start()

    def _nasconfig_sync(self):
        self.cfg_out.delete("1.0",tk.END)
        def bg():
            r=subprocess.run("sudo python3 /home/pi/nas_config.py",
                             input="3\n\n",shell=True,capture_output=True,text=True)
            self.after(0,lambda:(
                self.cfg_out.insert(tk.END,r.stdout+"\n"),
                self.cfg_out.insert(tk.END,"✅  Gesynchroniseerd\n","ok"),
                self.cfg_out.see(tk.END)))
        threading.Thread(target=bg,daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # SCRIPTS BIJWERKEN
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_scripts(self):
        self._head("⬆  Scripts bijwerken vanuit SD-kaart",FG)
        p=self._panel()
        tk.Label(p,text="Kopieert nieuwe scripts van /boot/firmware/ naar /home/pi/",
                 font=("Segoe UI",9),bg=PANEL,fg=FG).pack(anchor="w",pady=(0,6))
        # Toon beschikbare scripts
        scripts=sh("ls /boot/firmware/*.py /boot/firmware/*.sh 2>/dev/null")
        if scripts:
            for s in scripts.splitlines():
                import os as _os
                base=_os.path.basename(s)
                dest=f"/home/pi/{base}"
                diff=sh(f"diff -q {s} {dest} 2>/dev/null")
                status="⚠ nieuwer" if diff or not _os.path.exists(dest) else "✔ up-to-date"
                color=WARN if "nieuwer" in status else GREEN
                r=tk.Frame(p,bg=PANEL); r.pack(anchor="w",fill="x",pady=1)
                tk.Label(r,text=base,font=("Segoe UI",9),bg=PANEL,fg=FG,width=32,anchor="w").pack(side="left")
                tk.Label(r,text=status,font=("Segoe UI",9),bg=PANEL,fg=color).pack(side="left")
        else:
            tk.Label(p,text="Geen scripts gevonden in /boot/firmware/",
                     font=("Segoe UI",9),bg=PANEL,fg=WARN).pack(anchor="w")
        br=tk.Frame(self.content,bg=BG); br.pack(anchor="w",pady=6)
        self._btn(br,"⬆  Bijwerken",self._scripts_update,bg=ACCENT,fg=BG,bold=True).pack(side="left",padx=(0,8))
        self._btn(br,"🔄  Vernieuwen",lambda:self._jump(15),bg=BTN,fg=FG).pack(side="left")
        self.scr_out=self._logw(self.content,7)

    def _scripts_update(self):
        self.scr_out.delete("1.0",tk.END)
        def bg():
            import glob,os,shutil
            copied=0
            for f in glob.glob("/boot/firmware/*.py")+glob.glob("/boot/firmware/*.sh"):
                base=os.path.basename(f)
                if base=="install.sh": continue
                dest=f"/home/pi/{base}"
                try:
                    shutil.copy2(f,dest)
                    os.chmod(dest,0o755)
                    msg=f"✔  Bijgewerkt: {base}\n"
                    self.after(0,lambda m=msg:(self.scr_out.insert(tk.END,m,"ok"),self.scr_out.see(tk.END)))
                    copied+=1
                except Exception as e:
                    msg=f"✗  Fout: {base}: {e}\n"
                    self.after(0,lambda m=msg:(self.scr_out.insert(tk.END,m,"warn"),self.scr_out.see(tk.END)))
            # Ook naar bootfs kopiëren
            for f in glob.glob("/home/pi/*.py")+glob.glob("/home/pi/*.sh"):
                base=os.path.basename(f)
                subprocess.run(f"sudo cp {f} /boot/firmware/{base} 2>/dev/null",shell=True)
            self.after(0,lambda:(
                self.scr_out.insert(tk.END,f"\n✅  {copied} script(s) bijgewerkt\n","ok"),
                self.scr_out.see(tk.END)))
        threading.Thread(target=bg,daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    # DIAGNOSE
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_diagnose(self):
        self._head("🔬  Diagnose",FG)
        ip=get_ip()
        # Status overzicht
        p=self._panel()
        tk.Label(p,text="Systeem status",font=("Segoe UI",11,"bold"),
                 bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,6))
        for lbl,val,col in [
            ("IP-adres",ip,GREEN),
            ("Hostname",sh("hostname"),FG),
            ("Uptime",sh("uptime -p 2>/dev/null || uptime"),FG),
            ("CPU temp",sh("vcgencmd measure_temp 2>/dev/null || cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{printf \"%.1f°C\", $1/1000}'"),WARN),
            ("RAM vrij",sh("free -h | awk '/Mem/{print $7}'"),FG),
            ("SD-kaart",sh("df -h / | tail -1 | awk '{print $4\" vrij van \"$2}'"),FG),
        ]:
            r=tk.Frame(p,bg=PANEL); r.pack(anchor="w",fill="x",pady=1)
            tk.Label(r,text=f"{lbl}:",font=("Segoe UI",9,"bold"),bg=PANEL,fg=FG,
                     width=14,anchor="w").pack(side="left")
            tk.Label(r,text=val,font=("Segoe UI",9),bg=PANEL,fg=col).pack(side="left")
        # Services
        p2=self._panel()
        tk.Label(p2,text="Services",font=("Segoe UI",11,"bold"),
                 bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,6))
        for svc in ["smbd","apache2","mariadb","filebrowser","cockpit","vncserver-x11-serviced"]:
            status=sh(f"sudo systemctl is-active {svc} 2>/dev/null")
            r=tk.Frame(p2,bg=PANEL); r.pack(anchor="w",fill="x",pady=1)
            tk.Label(r,text="✔" if status=="active" else "✗",
                     font=("Segoe UI",9,"bold"),bg=PANEL,
                     fg=GREEN if status=="active" else PANEL2).pack(side="left",padx=(0,8))
            tk.Label(r,text=svc,font=("Segoe UI",9),bg=PANEL,fg=FG).pack(side="left")
        # Diagnose knoppen
        br=tk.Frame(self.content,bg=BG); br.pack(anchor="w",pady=6)
        self.diag_out=self._logw(self.content,7)
        for lbl,cmd in [("lsblk","lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT"),
                         ("df -h","df -h"),
                         ("fstab","cat /etc/fstab"),
                         ("Mounts","mount | grep /mnt/")]:
            self._btn(br,lbl,lambda c=cmd:(
                self.diag_out.delete("1.0",tk.END),
                self.diag_out.insert(tk.END,f"$ {c}\n","head"),
                self.diag_out.insert(tk.END,sh(c)+"\n")),
                bg=BTN,fg=FG).pack(side="left",padx=(0,5))


    # ══════════════════════════════════════════════════════════════════════════
    # SYSTEEM INFO — ook gebruikt als Gereed-scherm
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_sysinfo(self, installatie_klaar=False):
        if installatie_klaar:
            self._head("✅  Installatie voltooid!",GREEN)
        else:
            self._head("📋  Systeem info",FG)

        ip=get_ip()
        share=self.share_name.get().strip() or sh("grep -A1 '\\[PiNas\\]\\|\\[Opslag\\]' /etc/samba/smb.conf 2>/dev/null | grep path | awk -F= '{print $2}' | xargs basename 2>/dev/null") or "Opslag"
        samba_ok=sh("dpkg -l samba 2>/dev/null | grep -c '^ii'").strip()=="1"
        nc_ok=os.path.exists("/var/www/html/nextcloud")
        fb_ok=bool(sh("pgrep -x filebrowser 2>/dev/null"))

        def row(parent,lbl,val,col=None):
            r=tk.Frame(parent,bg=PANEL); r.pack(anchor="w",pady=2,fill="x")
            tk.Label(r,text=lbl,font=("Segoe UI",9,"bold"),bg=PANEL,fg=FG,
                     width=22,anchor="w").pack(side="left")
            tk.Label(r,text=val,font=("Courier",9),bg=PANEL,
                     fg=col or GREEN).pack(side="left")

        # Netwerk & systeem
        p0=self._panel()
        tk.Label(p0,text="Systeem",font=("Segoe UI",11,"bold"),
                 bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,5))
        row(p0,"IP-adres:",ip)
        row(p0,"Hostname:",sh("hostname") or "?")
        row(p0,"SSH:","Ingeschakeld" if sh("sudo systemctl is-active ssh 2>/dev/null")=="active" else "Uitgeschakeld")
        row(p0,"SSH verbinden:",f"ssh pi@{ip}")
        row(p0,"Uptime:",sh("uptime -p 2>/dev/null") or sh("uptime"),FG)
        row(p0,"CPU temp:",sh("vcgencmd measure_temp 2>/dev/null || echo 'n/b'"),WARN)

        # Schijven
        p1=self._panel()
        tk.Label(p1,text="Schijven",font=("Segoe UI",11,"bold"),
                 bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,5))
        mounts=get_nas_mounts()
        if mounts:
            for dev,mp,fs,sz in mounts:
                used=sh(f"df -h {mp} 2>/dev/null | tail -1 | awk '{{print $3\" gebruikt, \"$4\" vrij\"}}'")
                row(p1,f"{mp}:",f"{dev}  {sz}  {used}")
        else:
            tk.Label(p1,text="Geen NAS-schijven gemount",
                     font=("Segoe UI",9),bg=PANEL,fg=WARN).pack(anchor="w")

        # Services & verbindingen
        p2=self._panel()
        tk.Label(p2,text="Services & verbindingen",font=("Segoe UI",11,"bold"),
                 bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,5))
        if samba_ok:
            samba_share=sh("grep -A5 '\\[PiNas\\]' /etc/samba/smb.conf 2>/dev/null | grep path | awk -F= '{print $2}' | xargs").strip() or "/mnt/opslag"
            samba_name=sh("grep '\\[PiNas\\]\\|\\[Opslag\\]\\|\\[Backup\\]' /etc/samba/smb.conf 2>/dev/null | head -1 | tr -d '[]'").strip() or "Opslag"
            row(p2,"Samba (Windows):",f"\\\\{ip}\\{samba_name}")
            row(p2,"Samba (iPhone):",f"smb://{ip}")
        if nc_ok:
            row(p2,"Nextcloud:",f"http://{ip}/nextcloud")
        if fb_ok:
            row(p2,"FileBrowser:",f"http://{ip}:8080")
        if sh("sudo systemctl is-active cockpit 2>/dev/null")=="active":
            row(p2,"Cockpit:",f"http://{ip}:9090")

        # Afsluiten tip
        p3=self._panel()
        tk.Label(p3,text="⚠  Pi afsluiten",font=("Segoe UI",10,"bold"),
                 bg=PANEL,fg=WARN).pack(anchor="w",pady=(0,3))
        for tip in [f"Via Cockpit: http://{ip}:9090",
                    "Via terminal: sudo shutdown -h now",
                    "Wacht ~30 sec na afsluiten voor schijf uitzetten."]:
            tk.Label(p3,text=f"  • {tip}",font=("Segoe UI",9),bg=PANEL,fg=FG).pack(anchor="w")

        if not installatie_klaar:
            br=tk.Frame(self.content,bg=BG); br.pack(anchor="w",pady=8)
            self._btn(br,"🔄  Vernieuwen",lambda:self._jump(17),bg=BTN,fg=FG).pack(side="left")


    # ══════════════════════════════════════════════════════════════════════════
    # HELP
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_help(self):
        self._head("❓  Help — overzicht van alle functies",FG)
        secties=[
            ("🚀 Initiële setup","Alles in één keer instellen op een verse Pi: netwerk, SSH, schijf en NAS-software."),
            ("💾 Schijf beheer","Koppelen, wisselen, verwijderen, formatteren en diagnose van NAS-schijven."),
            ("⚙️ NAS-software","Methode A: Samba + Cockpit (netwerkschijf). Methode B: Nextcloud (eigen cloud). Of beide."),
            ("🌐 FileBrowser","Webbeheer voor bestanden via browser op http://[IP]:8080. Installeren, starten, stoppen."),
            ("🖥️ Desktop & VNC","Desktop (LXDE) en VNC installeren voor grafische omgeving via Windows (RealVNC Viewer)."),
            ("💾 Configuratie","Exporteer/importeer alle instellingen naar 4 locaties. Ideaal voor herinstallatie of Pi-wissel."),
            ("🔬 Diagnose","Systeem status: IP, temperatuur, RAM, schijven, services, lsblk, df, fstab."),
            ("📋 Systeem info","Overzicht van alle verbindingsgegevens: Samba-pad, Nextcloud, FileBrowser, Cockpit."),
            ("🔑 SSH-sleutel","SSH inschakelen, sleutel controleren, wachtwoordlogin uitschakelen."),
            ("⬆ Scripts bijwerken","Kopieert nieuwe scripts van /boot/firmware/ naar /home/pi/ én bootfs."),
            ("🗑 Deïnstalleren","Verwijder afzonderlijke componenten of alles. Pi OS blijft intact, data bewaard."),
            ("🛠 Beheer","Standaard NAS-structuur aanmaken (Opslag/Fotos/Bestanden/Music) · Eigen map/share toevoegen · Nextcloud opslag koppelen · Gebruikers beheren · Schijfruimte overzicht."),
        ]
        for titel,desc in secties:
            p=tk.Frame(self.content,bg=PANEL,padx=12,pady=8)
            p.pack(fill="x",pady=2)
            tk.Label(p,text=titel,font=("Segoe UI",10,"bold"),
                     bg=PANEL,fg=ACCENT).pack(anchor="w")
            tk.Label(p,text=desc,font=("Segoe UI",9),bg=PANEL,fg=FG,
                     justify="left",wraplength=700).pack(anchor="w",pady=(2,0))

        p_tips=self._panel()
        tk.Label(p_tips,text="Tips",font=("Segoe UI",10,"bold"),
                 bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,4))
        for tip in ["← Terug knop gaat altijd terug naar de vorige pagina.",
                    "Overslaan knop slaat een stap over zonder actie.",
                    "GUI-installer vereist desktop + VNC of native scherm.",
                    "CLI-installer (nas commando) werkt altijd via SSH — ook zonder desktop.",
                    "Scripts worden automatisch bijgewerkt vanuit /boot/firmware/ bij elke login."]:
            tk.Label(p_tips,text=f"  • {tip}",font=("Segoe UI",9),
                     bg=PANEL,fg=FG).pack(anchor="w",pady=1)


    # ══════════════════════════════════════════════════════════════════════════
    # BEHEER
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_beheer(self):
        self._head("🛠  Beheer",FG)
        ip=get_ip()
        # Output log alvast aanmaken zodat knoppen er altijd naar kunnen verwijzen
        self.beh_out=None

        STANDAARD=[
            ("Opslag",    "/mnt/opslag",           "SSD — tijdelijke opslag"),
            ("Fotos",     "/mnt/backup/fotos",      "Seagate — foto's iPhone/Android"),
            ("Bestanden", "/mnt/backup/bestanden",  "Seagate — PC en overige bestanden"),
            ("Music",     "/mnt/backup/music",      "Seagate — muziekcollectie"),
        ]
        shares=get_samba_shares()
        # Vergelijk op pad EN naam
        bestaande_paden=[p.rstrip('/') for p in shares.values()]
        bestaande_namen=[n.lower() for n in shares.keys()]
        ontbreekt=[(n,p,b) for n,p,b in STANDAARD 
                   if n.lower() not in bestaande_namen 
                   and p.rstrip('/') not in bestaande_paden]

        # ── Standaard NAS-structuur ────────────────────────────────────────
        p=self._panel()
        tk.Label(p,text="📋  Standaard NAS-structuur",font=("Segoe UI",11,"bold"),
                 bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,6))
        tk.Label(p,text="Overzicht van de aanbevolen mappen en shares. Groen = aanwezig, geel = ontbreekt.",
                 font=("Segoe UI",9),bg=PANEL,fg=FG).pack(anchor="w",pady=(0,6))
        for naam,pad,beschr in STANDAARD:
            bestaat=naam.lower() in bestaande_namen or pad.rstrip('/') in bestaande_paden
            r=tk.Frame(p,bg=PANEL); r.pack(anchor="w",fill="x",pady=1)
            tk.Label(r,text="✔" if bestaat else "✗",font=("Segoe UI",9,"bold"),
                     bg=PANEL,fg=GREEN if bestaat else YELLOW,width=3).pack(side="left")
            tk.Label(r,text=f"[{naam}]",font=("Segoe UI",9,"bold"),
                     bg=PANEL,fg=GREEN if bestaat else YELLOW,width=12).pack(side="left")
            tk.Label(r,text=f"{pad}",font=("Courier",8),
                     bg=PANEL,fg=FG,width=30).pack(side="left")
            tk.Label(r,text=f"  {beschr}",font=("Segoe UI",8),
                     bg=PANEL,fg="#888888").pack(side="left")
        br=tk.Frame(p,bg=PANEL); br.pack(anchor="w",pady=(8,0))
        self._btn(br,f"✅  Ontbrekende aanmaken ({len(ontbreekt)})",
                  self._beheer_standaard_shares,
                  bg=GREEN if ontbreekt else BTN,fg=BG if ontbreekt else FG,
                  bold=True).pack(side="left",padx=(0,8))
        self._btn(br,"➕  Eigen map/share",self._beheer_map_aanmaken,bg=BTN,fg=FG).pack(side="left",padx=(0,8))
        self._btn(br,"🗑  Share verwijderen",self._beheer_share_verwijderen,bg=WARN,fg=BG).pack(side="left")

        # ── Nextcloud ──────────────────────────────────────────────────────
        p2=self._panel()
        tk.Label(p2,text="☁  Nextcloud externe opslag",font=("Segoe UI",11,"bold"),
                 bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,4))
        tk.Label(p2,text="Koppel een map op SSD of Seagate direct aan Nextcloud als externe opslag.",
                 font=("Segoe UI",9),bg=PANEL,fg=FG,justify="left").pack(anchor="w",pady=(0,6))
        try:
            nc_mounts=sh("sudo -u www-data php /var/www/html/nextcloud/occ files_external:list 2>/dev/null")
            if nc_mounts and "No mounts" not in nc_mounts and "Exception" not in nc_mounts:
                for line in nc_mounts.splitlines()[1:3]:
                    if line.strip():
                        tk.Label(p2,text=f"  {line.strip()}",font=("Segoe UI",8),
                                 bg=PANEL,fg=GREEN).pack(anchor="w")
        except: pass
        br2=tk.Frame(p2,bg=PANEL); br2.pack(anchor="w",pady=(4,0))
        self._btn(br2,"🗑  Nextcloud koppeling verwijderen",self._beheer_nc_verwijderen,bg=WARN,fg=BG).pack(side="left")

        # ── Seagate aan/uit ───────────────────────────────────────────────
        if os.path.exists("/home/pi/smart_plug_config.json"):
            p3=self._panel()
            tk.Label(p3,text="🔌  Seagate",font=("Segoe UI",11,"bold"),
                     bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,4))
            # Status tonen
            try:
                sys.path.insert(0,'/home/pi')
                from smart_plug import plug_status as _ps
                status=_ps()
                gemount=os.path.ismount("/mnt/backup")
                stekker_txt="aan ✔" if status else "uit"
                mount_txt="gemount ✔" if gemount else "niet gemount"
                status_txt=f"Stekker: {stekker_txt}  |  /mnt/backup: {mount_txt}"
                kleur=GREEN if status and gemount else WARN if status else "#888888"
            except:
                status_txt="Status onbekend"; kleur="#888888"
            tk.Label(p3,text=status_txt,font=("Segoe UI",9),
                     bg=PANEL,fg=kleur).pack(anchor="w",pady=(0,6))
            br3=tk.Frame(p3,bg=PANEL); br3.pack(anchor="w")
            self._btn(br3,"🔌  Aanzetten",self._seagate_aan,bg=GREEN,fg=BG,bold=True).pack(side="left",padx=(0,8))
            self._btn(br3,"⏹  Uitzetten",self._seagate_uit,bg=BTN,fg=FG).pack(side="left")

            # Web Controller sectie
            tk.Label(p3,text="",bg=PANEL).pack()
            tk.Label(p3,text="🌐  Web Controller",font=("Segoe UI",10,"bold"),
                     bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(4,2))
            wc_actief=sh("systemctl is-active seagate-web 2>/dev/null").strip()=="active"
            wc_installed=sh("systemctl is-enabled seagate-web 2>/dev/null").strip() not in ("","not-found")
            ip=get_ip()
            if wc_actief:
                tk.Label(p3,text=f"● Actief — bereikbaar op http://{ip}:8765",
                         font=("Segoe UI",9),bg=PANEL,fg=GREEN).pack(anchor="w",pady=(0,4))
            elif wc_installed:
                tk.Label(p3,text="○ Gestopt",font=("Segoe UI",9),bg=PANEL,fg=WARN).pack(anchor="w",pady=(0,4))
            else:
                tk.Label(p3,text="─ Niet geïnstalleerd — installeer om Seagate via browser te bedienen",
                         font=("Segoe UI",9),bg=PANEL,fg=DIM).pack(anchor="w",pady=(0,4))
            br4=tk.Frame(p3,bg=PANEL); br4.pack(anchor="w")
            self._btn(br4,"⚙️  Installeren als service",self._wc_install,bg=ACCENT,fg=BG).pack(side="left",padx=(0,8))
            if wc_actief:
                self._btn(br4,"⏹  Stoppen",self._wc_stop,bg=BTN,fg=FG).pack(side="left",padx=(0,8))
                self._btn(br4,"🌐  Openen",lambda:self._open_browser(f"http://{ip}:8765"),bg=TEAL,fg=BG).pack(side="left")
            elif wc_installed:
                self._btn(br4,"▶  Starten",self._wc_start,bg=GREEN,fg=BG).pack(side="left",padx=(0,8))
                self._btn(br4,"🗑  Verwijderen",self._wc_remove,bg=WARN,fg=BG).pack(side="left")

        # ── Output log ────────────────────────────────────────────────────
        self.beh_out=self._logw(self.content,5)

    def _beheer_log(self,t,tag=None):
        if not self.beh_out: return
        self.after(0,lambda:(self.beh_out.insert(tk.END,t+"\n",tag or ""),self.beh_out.see(tk.END)))

    def _wc_install(self):
        self.beh_out.delete("1.0",tk.END)
        self._beheer_log("Web Controller installeren...","info")
        def bg():
            sh("sudo cp /home/pi/seagate-web.service /etc/systemd/system/")
            sh("sudo systemctl daemon-reload")
            sh("sudo systemctl enable --now seagate-web")
            ip=get_ip()
            self.after(0,lambda:(
                self._beheer_log(f"OK  Web Controller actief op http://{ip}:8765","ok"),
                self._jump(19)))
        import threading; threading.Thread(target=bg,daemon=True).start()

    def _wc_start(self):
        sh("sudo systemctl start seagate-web")
        self._jump(19)

    def _wc_stop(self):
        sh("sudo systemctl stop seagate-web")
        self._jump(19)

    def _wc_remove(self):
        if not messagebox.askyesno("Verwijderen","Web Controller service verwijderen?"): return
        sh("sudo systemctl stop seagate-web 2>/dev/null")
        sh("sudo systemctl disable seagate-web 2>/dev/null")
        sh("sudo rm -f /etc/systemd/system/seagate-web.service")
        sh("sudo systemctl daemon-reload")
        self._jump(19)

    def _seagate_aan(self):
        self.beh_out.delete("1.0",tk.END)
        self._beheer_log("Seagate aanzetten...","info")
        def bg():
            try:
                sys.path.insert(0,'/home/pi')
                from smart_plug import plug_aan, seagate_aan as _aan
                plug_aan()
                self.after(0,lambda:self._beheer_log("Stekker aan — wacht 12 seconden tot schijf opstart...","info"))
                import time; time.sleep(12)
                import subprocess
                subprocess.run("sudo mount -a", shell=True)
                import os as _os
                gemount=_os.path.ismount("/mnt/backup")
                if not gemount:
                    # Nog een keer proberen na extra 5 sec
                    self.after(0,lambda:self._beheer_log("Nog even geduld...","info"))
                    time.sleep(5)
                    subprocess.run("sudo mount -a", shell=True)
                    gemount=_os.path.ismount("/mnt/backup")
                self.after(0,lambda:(
                    self._beheer_log("OK  Seagate aan en gemount" if gemount else "!  Seagate aan maar nog niet gemount — controleer de USB-verbinding",
                                     "ok" if gemount else "warn"),
                    self._jump(19)))
            except Exception as e:
                self.after(0,lambda:(self._beheer_log(f"FOUT: {e}","warn")))
        import threading; threading.Thread(target=bg,daemon=True).start()

    def _seagate_uit(self):
        if not messagebox.askyesno("Seagate uitzetten","Seagate netjes ontkoppelen en uitzetten?"): return
        self.beh_out.delete("1.0",tk.END)
        self._beheer_log("Seagate uitzetten...","info")
        def bg():
            try:
                sys.path.insert(0,'/home/pi')
                import subprocess, time
                subprocess.run("sudo umount /mnt/backup 2>/dev/null", shell=True)
                time.sleep(1)
                from smart_plug import plug_uit
                plug_uit()
                self.after(0,lambda:(
                    self._beheer_log("OK  Seagate uitgezet","ok"),
                    self._jump(19)))  # Refresh beheer pagina
            except Exception as e:
                self.after(0,lambda:(self._beheer_log(f"FOUT: {e}","warn")))
        import threading; threading.Thread(target=bg,daemon=True).start()

    def _beheer_standaard_shares(self):
        STANDAARD=[
            ("Opslag",    "/mnt/opslag",           "SSD tijdelijke opslag"),
            ("Fotos",     "/mnt/backup/fotos",      "Seagate fotos"),
            ("Bestanden", "/mnt/backup/bestanden",  "Seagate PC bestanden"),
            ("Music",     "/mnt/backup/music",      "Seagate muziek"),
        ]
        shares=get_samba_shares()
        user=sh("logname 2>/dev/null || echo pi") or "pi"
        ip=get_ip()
        self.beh_out.delete("1.0",tk.END)
        def bg():
            aangemaakt=0
            for naam,pad,beschr in STANDAARD:
                if naam.lower() in [s.lower() for s in shares.keys()]:
                    self.after(0,lambda n=naam:(self.beh_out.insert(tk.END,f"OK  [{n}] al aanwezig\n","ok"),self.beh_out.see(tk.END)))
                    continue
                if not os.path.exists(pad):
                    sh(f"sudo mkdir -p '{pad}' && sudo chown {user}:{user} '{pad}' && sudo chmod 775 '{pad}'")
                blk=(f"\n[{naam}]\n   comment={beschr}\n   path={pad}\n"
                     f"   browseable=yes\n   writable=yes\n"
                     f"   valid users={user}\n   force user={user}\n")
                subprocess.run(f"printf '{blk}' | sudo tee -a /etc/samba/smb.conf>/dev/null",shell=True)
                self.after(0,lambda n=naam,p=pad:(
                    self.beh_out.insert(tk.END,f"OK  [{n}] aangemaakt - {p}\n","ok"),
                    self.beh_out.see(tk.END)))
                aangemaakt+=1
            subprocess.run("sudo systemctl restart smbd",shell=True)
            self.after(0,lambda:(
                self.beh_out.insert(tk.END,f"\nOK  {aangemaakt} share(s) aangemaakt\n","ok"),
                self.beh_out.insert(tk.END,f"   Windows: \\\\{ip}\\Fotos  \\\\{ip}\\Bestanden  \\\\{ip}\\Music\n","info"),
                self.beh_out.see(tk.END)))
        import threading; threading.Thread(target=bg,daemon=True).start()

    def _beheer_nc_verwijderen(self):
        self.beh_out.delete("1.0",tk.END)
        mounts=sh("sudo -u www-data php /var/www/html/nextcloud/occ files_external:list 2>/dev/null")
        if not mounts or "No mounts" in mounts:
            self.beh_out.insert(tk.END,"Geen Nextcloud koppelingen gevonden.\n","warn"); return
        self.beh_out.insert(tk.END,mounts+"\n","info")
        from tkinter.simpledialog import askstring
        mount_id=askstring("Koppeling verwijderen","ID van de koppeling (zie lijst hierboven):")
        if not mount_id: return
        r=sh(f"sudo -u www-data php /var/www/html/nextcloud/occ files_external:delete {mount_id} 2>&1")
        self.beh_out.insert(tk.END,f"OK  Koppeling {mount_id} verwijderd\n","ok")

    def _beheer_map_aanmaken(self):
        from tkinter.simpledialog import askstring
        mounts=get_nas_mounts()
        if not mounts: messagebox.showinfo("Info","Geen schijven gemount."); return

        # Locatie kiezen
        if len(mounts)==1:
            gekozen=[mounts[0][1]]
        else:
            lijst="\n".join(f"{i+1}.  {m[1]}  ({m[3]})" for i,m in enumerate(mounts))
            keuze=askstring("Kies locatie",
                f"Waar wil je de map aanmaken?\n\n{lijst}\n\n"
                f"Typ nummer voor één locatie.\n"
                f"Leeg laten = op ALLE schijven aanmaken:")
            if keuze is None: return  # Annuleren knop
            if not keuze.strip():
                gekozen=[m[1] for m in mounts]  # Alle schijven
            elif keuze.strip().isdigit() and 1<=int(keuze.strip())<=len(mounts):
                gekozen=[mounts[int(keuze.strip())-1][1]]
            else:
                messagebox.showwarning("Ongeldig","Ongeldig nummer — geannuleerd."); return

        naam=askstring("Map naam",f"Naam van de nieuwe map:")
        if not naam or not naam.strip():
            messagebox.showwarning("Geannuleerd","Geen naam opgegeven — geannuleerd."); return
        naam=naam.strip()

        user=sh("logname 2>/dev/null || echo pi") or "pi"
        self.beh_out.delete("1.0",tk.END)
        aangemaakt=[]
        bestond_al=[]

        for mp in gekozen:
            pad=f"{mp}/{naam}"
            if os.path.exists(pad):
                bestond_al.append(pad)
                self._beheer_log(f"!  Al aanwezig: {pad}","warn")
            else:
                sh(f"sudo mkdir -p '{pad}' && sudo chown {user}:{user} '{pad}' && sudo chmod 775 '{pad}'")
                self._beheer_log(f"OK  Aangemaakt: {pad}","ok")
                aangemaakt.append(pad)

        if bestond_al and not aangemaakt:
            messagebox.showinfo("Al aanwezig",
                "Alle mappen bestonden al:\n" + "\n".join(bestond_al))
            return
        if bestond_al:
            self._beheer_log(f"   Let op: {len(bestond_al)} map(pen) bestond(en) al","warn")

        if aangemaakt and messagebox.askyesno("Samba share","Samba-share(s) aanmaken?"):
            for pad in aangemaakt:
                blk=(f"\n[{naam}]\n   comment={naam}\n   path={pad}\n"
                     f"   browseable=yes\n   writable=yes\n"
                     f"   valid users={user}\n   force user={user}\n")
                subprocess.run(f"printf '{blk}' | sudo tee -a /etc/samba/smb.conf>/dev/null",shell=True)
            subprocess.run("sudo systemctl restart smbd",shell=True)
            ip=get_ip()
            self._beheer_log(f"OK  Share [{naam}] aangemaakt","ok")
            self._beheer_log(f"   Windows: \\\\{ip}\\{naam}","info")

    def _beheer_map_verwijderen(self):
        from tkinter.simpledialog import askstring
        mounts=get_nas_mounts()
        paden=[]
        for dev,mp,fs,sz in mounts:
            dirs=sh(f"find {mp} -maxdepth 1 -mindepth 1 -type d 2>/dev/null | grep -v lost+found | grep -v nextcloud-data | sort")
            for d in dirs.splitlines():
                if d: paden.append(d)
        if not paden: messagebox.showinfo("Info","Geen mappen gevonden."); return
        lijst="\n".join(f"{i+1}. {p}" for i,p in enumerate(paden))
        keuze=askstring("Map verwijderen",f"Kies map (nummer):\n{lijst}")
        if not keuze or not keuze.isdigit() or int(keuze)>len(paden): return
        pad=paden[int(keuze)-1]
        if not messagebox.askyesno("BEVESTIGEN",f"Map verwijderen:\n{pad}\n\nALLE DATA WORDT GEWIST!"): return
        self.beh_out.delete("1.0",tk.END)
        sh(f"sudo rm -rf '{pad}'")
        self._beheer_log(f"OK  Map verwijderd: {pad}","ok")

    def _beheer_share_toevoegen(self):
        from tkinter.simpledialog import askstring
        naam=askstring("Share naam","Naam van de share (bijv. Fotos):")
        if not naam: return
        pad=askstring("Pad","Volledig pad (bijv. /mnt/backup/fotos):")
        if not pad: return
        user=sh("logname 2>/dev/null || echo pi") or "pi"
        self.beh_out.delete("1.0",tk.END)
        if not os.path.exists(pad):
            sh(f"sudo mkdir -p '{pad}' && sudo chown {user}:{user} '{pad}' && sudo chmod 775 '{pad}'")
            self._beheer_log(f"OK  Map aangemaakt: {pad}","ok")
        blk=(f"\n[{naam}]\n   comment={naam}\n   path={pad}\n"
             f"   browseable=yes\n   writable=yes\n"
             f"   valid users={user}\n   force user={user}\n")
        subprocess.run(f"printf '{blk}' | sudo tee -a /etc/samba/smb.conf>/dev/null",shell=True)
        subprocess.run("sudo systemctl restart smbd",shell=True)
        ip=get_ip()
        self._beheer_log(f"OK  Share [{naam}] aangemaakt → {pad}","ok")
        self._beheer_log(f"   Windows: \\\\{ip}\\{naam}","info")

    def _beheer_share_verwijderen(self):
        from tkinter.simpledialog import askstring
        shares=get_samba_shares()
        if not shares: messagebox.showinfo("Info","Geen shares gevonden."); return
        lijst="\n".join(f"{i+1}. [{n}] → {p}" for i,(n,p) in enumerate(shares.items()))
        keuze=askstring("Share verwijderen",f"Kies share (nummer):\n{lijst}")
        if not keuze or not keuze.isdigit() or int(keuze)>len(shares): return
        naam=list(shares.keys())[int(keuze)-1]
        if not messagebox.askyesno("Bevestigen",f"Share [{naam}] verwijderen?"): return
        self.beh_out.delete("1.0",tk.END)
        conf=sh("cat /etc/samba/smb.conf"); lines=conf.splitlines()
        new=[]; skip=False
        for line in lines:
            if line.strip()==f"[{naam}]": skip=True
            elif skip and line.strip().startswith("["): skip=False
            if not skip: new.append(line)
        with open("/tmp/smb_new.conf","w") as f: f.write("\n".join(new))
        sh("sudo cp /tmp/smb_new.conf /etc/samba/smb.conf")
        subprocess.run("sudo systemctl restart smbd",shell=True)
        self._beheer_log(f"OK  Share [{naam}] verwijderd","ok")

    def _beheer_nc_koppelen(self):
        from tkinter.simpledialog import askstring
        if not os.path.exists("/var/www/html/nextcloud"):
            messagebox.showwarning("Nextcloud","Nextcloud is niet geinstalleerd."); return
        sh("sudo -u www-data php /var/www/html/nextcloud/occ app:enable files_external 2>/dev/null")
        map_naam=askstring("Nextcloud map","Naam in Nextcloud (bijv. Fotos):")
        if not map_naam: return
        pad=askstring("Pad","Volledig pad op Pi (bijv. /mnt/backup/fotos):")
        if not pad: return
        gebruiker=askstring("Gebruiker","Nextcloud gebruiker:","admin")
        if not gebruiker: return
        self.beh_out.delete("1.0",tk.END)
        if not os.path.exists(pad):
            sh(f"sudo mkdir -p '{pad}'")
        sh(f"sudo chown -R www-data:www-data '{pad}' && sudo chmod -R 755 '{pad}'")
        def bg():
            r=sh(f"sudo -u www-data php /var/www/html/nextcloud/occ files_external:create "
                 f"'{map_naam}' local null::null -c datadir='{pad}' --apply-to-user {gebruiker} 2>&1")
            sh("sudo -u www-data php /var/www/html/nextcloud/occ files:scan --all -q 2>/dev/null")
            self.after(0,lambda:(
                self._beheer_log(f"OK  '{map_naam}' gekoppeld aan {pad}","ok"),
                self._beheer_log("   Bestanden gesynchroniseerd","info")))
        import threading; threading.Thread(target=bg,daemon=True).start()
        self._beheer_log("Bezig met koppelen...","info")


    # ══════════════════════════════════════════════════════════════════════════
    # COCKPIT
    # ══════════════════════════════════════════════════════════════════════════
    def _pg_cockpit(self):
        self._head("⚙️  Cockpit — webbeheer Raspberry Pi",FG)
        ip=get_ip()
        ck_actief=sh("systemctl is-active cockpit 2>/dev/null").strip()=="active"
        ck_installed=bool(sh("which cockpit 2>/dev/null") or sh("dpkg -l cockpit 2>/dev/null | grep '^ii'"))
        ck_enabled=sh("systemctl is-enabled cockpit 2>/dev/null").strip()=="enabled"

        # Status
        if ck_installed:
            color=GREEN if ck_actief else WARN
            status="actief" if ck_actief else "gestopt"
            p0=self._panel(color="#1e3a2a" if ck_actief else "#3a2a1e")
            r=tk.Frame(p0,bg=p0["bg"]); r.pack(anchor="w",fill="x")
            tk.Label(r,text=f"{'✅' if ck_actief else '⚠'}  Cockpit {status}",
                     font=("Segoe UI",11,"bold"),bg=p0["bg"],fg=color).pack(side="left")
            if ck_actief:
                self._btn(r,f"🌐  Openen: http://{ip}:9090",
                          lambda:self._open_browser(f"http://{ip}:9090"),
                          bg="#ed8936",fg=BG,bold=True).pack(side="right")
            tk.Label(p0,text=f"Login: pi / Pi OS wachtwoord",
                     font=("Segoe UI",9),bg=p0["bg"],fg=FG).pack(anchor="w")
        else:
            p0=self._panel(color="#3a2a1e")
            tk.Label(p0,text="Cockpit is niet geïnstalleerd",
                     font=("Segoe UI",11,"bold"),bg="#3a2a1e",fg=WARN).pack(anchor="w")
            tk.Label(p0,text="Cockpit geeft webbeheer voor de Pi: CPU, geheugen, schijven, services en updates.",
                     font=("Segoe UI",9),bg="#3a2a1e",fg=FG).pack(anchor="w")

        # Installeren
        p=self._panel()
        tk.Label(p,text="Installatie",font=("Segoe UI",10,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,6))
        tk.Label(p,text="~5 min · Vereist internet · Login met Pi OS gebruikersnaam en wachtwoord",
                 font=("Segoe UI",9),bg=PANEL,fg=FG).pack(anchor="w",pady=(0,6))
        br=tk.Frame(p,bg=PANEL); br.pack(anchor="w")
        self._btn(br,"⚙️  Cockpit installeren",self._cockpit_install,bg="#ed8936",fg=BG,bold=True).pack(side="left",padx=(0,8))
        self._btn(br,"🗑  Verwijderen",self._cockpit_remove,bg=WARN,fg=BG).pack(side="left")

        # Beheer
        p2=self._panel()
        tk.Label(p2,text="Beheer",font=("Segoe UI",10,"bold"),bg=PANEL,fg=ACCENT).pack(anchor="w",pady=(0,6))
        br2=tk.Frame(p2,bg=PANEL); br2.pack(anchor="w",pady=(0,4))
        self._btn(br2,"▶  Starten",self._cockpit_start,bg=GREEN,fg=BG).pack(side="left",padx=(0,8))
        self._btn(br2,"⏹  Stoppen",self._cockpit_stop,bg=BTN,fg=FG).pack(side="left",padx=(0,8))
        if ck_enabled:
            self._btn(br2,"Uitschakelen bij opstarten",self._cockpit_disable,bg=BTN,fg=FG).pack(side="left")
        else:
            self._btn(br2,"Inschakelen bij opstarten",self._cockpit_enable,bg=ACCENT,fg=BG).pack(side="left")

        self.ck_out=self._logw(self.content,5)

    def _cockpit_install(self):
        self.ck_out.delete("1.0",tk.END)
        self._run_bg([
            ("Cockpit installeren","sudo apt-get install -y cockpit"),
            ("Inschakelen","sudo systemctl enable --now cockpit.socket"),
        ], self.ck_out, on_done=lambda:(
            self._dei_log("✅  Cockpit geïnstalleerd","ok"),
            self._jump(20)))

    def _cockpit_remove(self):
        if not messagebox.askyesno("Verwijderen","Cockpit verwijderen?"): return
        self.ck_out.delete("1.0",tk.END)
        self._run_bg([
            ("Stoppen","sudo systemctl stop cockpit 2>/dev/null"),
            ("Uitschakelen","sudo systemctl disable cockpit.socket 2>/dev/null"),
            ("Verwijderen","sudo apt-get remove -y cockpit"),
        ], self.ck_out, on_done=lambda:self._jump(20))

    def _cockpit_start(self):
        sh("sudo systemctl start cockpit")
        self._jump(20)

    def _cockpit_stop(self):
        sh("sudo systemctl stop cockpit")
        self._jump(20)

    def _cockpit_enable(self):
        sh("sudo systemctl enable cockpit.socket")
        self._jump(20)

    def _cockpit_disable(self):
        sh("sudo systemctl disable cockpit.socket")
        self._jump(20)


if __name__=="__main__":
    if os.geteuid()!=0:
        print("\n⚠  Start met: sudo python3 nas_installer.py\n"); sys.exit(1)
    NASInstaller().mainloop()
