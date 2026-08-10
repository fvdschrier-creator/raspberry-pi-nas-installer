#!/bin/bash
# Simuleert twee schijven: SSD (120GB) en Seagate (500GB)

# Maak loop image bestanden
dd if=/dev/zero of=/tmp/ssd.img bs=1M count=100 2>/dev/null
dd if=/dev/zero of=/tmp/seagate.img bs=1M count=200 2>/dev/null

# Koppel als loop devices
losetup /dev/loop10 /tmp/ssd.img 2>/dev/null
losetup /dev/loop11 /tmp/seagate.img 2>/dev/null

# Formateer als ext4
mkfs.ext4 -F /dev/loop10 2>/dev/null
mkfs.ext4 -F /dev/loop11 2>/dev/null

# Mount
mount /dev/loop10 /mnt/opslag
mount /dev/loop11 /mnt/backup
chown -R pi:pi /mnt/opslag /mnt/backup

# Samba config
cat > /etc/samba/smb.conf << 'SAMBA'
[global]
   workgroup = WORKGROUP
   server string = Pi NAS Simulator
   security = user

[Opslag]
   path = /mnt/opslag
   browseable = yes
   read only = no
   guest ok = yes

[Backup]
   path = /mnt/backup
   browseable = yes
   read only = no
   guest ok = yes
SAMBA

service smbd start 2>/dev/null

# Stel hostname in zodat installer het herkent
hostname piNAS
echo "127.0.0.1 piNAS" >> /etc/hosts

echo "Simulator schijven klaar"
