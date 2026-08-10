"""
Pi NAS Suite — Centrale logging module
Importeer in elk programma met: from pinas_logging import get_logger

Logbestanden in C:\\PiNAS\\Logs\\ (Windows) of /home/pi/logs/ (Pi):
    picontrol.log   — Pi NAS Menu
    pibackup.log    — PiBackup
    seagate.log     — Seagate web controller (op Pi)
    diagnose.log    — Diagnose uitvoer
    nas_upload.log  — Upload acties

Logs worden automatisch verwijderd na 30 dagen.
"""

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from datetime import datetime, timedelta

# ── Log map detectie ──────────────────────────────────────────
def _log_map():
    """Detecteer juiste logmap — Windows of Pi."""
    # Windows
    pinas = Path("C:/PiNAS/Logs")
    if pinas.parent.parent.exists():  # C:\PiNAS bestaat
        pinas.mkdir(parents=True, exist_ok=True)
        return pinas
    # Pi / Linux
    pi_logs = Path("/home/pi/logs")
    try:
        pi_logs.mkdir(parents=True, exist_ok=True)
        return pi_logs
    except PermissionError:
        pass
    # Fallback: naast dit script
    fallback = Path(__file__).parent / "Logs"
    fallback.mkdir(exist_ok=True)
    return fallback

LOG_MAP = _log_map()

# ── Log bestanden per product ─────────────────────────────────
LOG_BESTANDEN = {
    "picontrol":  LOG_MAP / "picontrol.log",
    "pibackup":   LOG_MAP / "pibackup.log",
    "seagate":    LOG_MAP / "seagate.log",
    "diagnose":   LOG_MAP / "diagnose.log",
    "nas_upload": LOG_MAP / "nas_upload.log",
    "installer":  LOG_MAP / "nas_installer.log",
}

# ── Opruimen oude logs (>30 dagen) ────────────────────────────
def opruim_oude_logs(dagen=30):
    """Verwijder logbestanden ouder dan opgegeven aantal dagen."""
    grens = datetime.now() - timedelta(days=dagen)
    verwijderd = []
    try:
        for pad in LOG_MAP.glob("*.log*"):
            try:
                mtime = datetime.fromtimestamp(pad.stat().st_mtime)
                if mtime < grens:
                    pad.unlink()
                    verwijderd.append(pad.name)
            except Exception:
                pass
    except Exception:
        pass
    return verwijderd

# ── Logger factory ────────────────────────────────────────────
_loggers = {}

def get_logger(naam="picontrol", niveau=logging.DEBUG):
    """
    Haal logger op voor opgegeven product.
    naam: 'picontrol', 'pibackup', 'seagate', 'diagnose', 'nas_upload', 'installer'
    Geeft geconfigureerde logger terug.
    """
    if naam in _loggers:
        return _loggers[naam]

    log_pad = LOG_BESTANDEN.get(naam, LOG_MAP / f"{naam}.log")
    logger = logging.getLogger(f"pinas.{naam}")
    logger.setLevel(niveau)

    # Voorkom dubbele handlers
    if logger.handlers:
        _loggers[naam] = logger
        return logger

    # Formaat
    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-7s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Bestand handler — dagelijks roterend, 30 dagen bewaren
    try:
        fh = TimedRotatingFileHandler(
            log_pad,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8"
        )
        fh.setFormatter(fmt)
        fh.setLevel(niveau)
        logger.addHandler(fh)
    except Exception as e:
        print(f"[pinas_logging] Kan logbestand niet aanmaken: {log_pad} — {e}")

    # Console handler (alleen bij DEBUG of als geen bestand)
    if niveau == logging.DEBUG or not log_pad.parent.exists():
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        ch.setLevel(logging.WARNING)
        logger.addHandler(ch)

    _loggers[naam] = logger

    # Opruimen bij eerste gebruik
    opruim_oude_logs()

    logger.info(f"=== Pi NAS Suite logger gestart: {naam} ===")
    return logger


def get_log_pad(naam="picontrol"):
    """Geef het pad van het logbestand terug."""
    return LOG_BESTANDEN.get(naam, LOG_MAP / f"{naam}.log")
