#!/bin/bash
# Wrapper voor desktop shortcuts — vraagt wachtwoord via GUI
# Gebruik: nas_start.sh [installer|config|diagnose]
case "$1" in
    installer) pkexec python3 /home/pi/nas_installer.py ;;
    config)    pkexec bash -c "raspi-config" ;;
    diagnose)  pkexec bash /home/pi/nas_diagnose.sh ;;
    *) echo "Gebruik: nas_start.sh [installer|config|diagnose]" ;;
esac
