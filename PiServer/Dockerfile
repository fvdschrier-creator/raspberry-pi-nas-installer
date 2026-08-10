FROM debian:bookworm-slim

# Basis packages
RUN apt-get update && apt-get install -y \
    python3 python3-tk python3-pip \
    samba samba-common-bin \
    curl net-tools iproute2 \
    x11vnc xvfb x11-xserver-utils \
    openbox \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Maak pi gebruiker aan zonder welkomstmenu
RUN useradd -m -s /bin/bash pi && \
    echo "pi:raspberry" | chpasswd && \
    echo "pi ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Nep schijven aanmaken
RUN mkdir -p /mnt/opslag /mnt/backup && \
    chown pi:pi /mnt/opslag /mnt/backup

# Kopieer scripts
COPY sim_setup.sh /home/pi/sim_setup.sh
COPY nas_installer.py /home/pi/nas_installer.py
COPY nas_installer_cli.py /home/pi/nas_installer_cli.py
COPY smart_plug.py /home/pi/smart_plug.py
RUN chmod +x /home/pi/sim_setup.sh

# VNC wachtwoord instellen
RUN mkdir -p /home/pi/.vnc && \
    x11vnc -storepasswd raspberry /home/pi/.vnc/passwd && \
    chown -R pi:pi /home/pi/.vnc

# Startscript
COPY start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 5900

CMD ["/start.sh"]
