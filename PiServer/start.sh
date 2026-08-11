#!/bin/bash
# Start virtueel scherm en VNC server
Xvfb :1 -screen 0 1280x800x24 &
sleep 2
export DISPLAY=:1

# Start window manager
openbox &
sleep 1

# Setup simulator schijven
/home/pi/sim_setup.sh

# Start NAS installer direct
DISPLAY=:1 python3 /home/pi/nas_installer.py &
INSTALLER_PID=$!
echo "Installer gestart met PID $INSTALLER_PID"
sleep 2

# Start VNC server
x11vnc -display :1 -rfbauth /home/pi/.vnc/passwd -rfbport 5900 -forever -noxdamage -shared

