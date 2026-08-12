"""
Pi NAS Suite — Handleiding builder
Genereert: PiNAS_Suite_Handleiding.pdf
Gebruik:   python build_suite_handleiding.py
Staat in en schrijft naar: C:\\PiNAS\\Publicatie\\  (Windows)
           ./PiNAS_Suite_Handleiding.pdf                    (Linux/build)
"""

import datetime

import os
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether, Image
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle, Polygon
from reportlab.graphics import renderPDF
from reportlab.platypus.flowables import Flowable

# ── Kleuren (donker thema, passend bij de suite) ────────────────────────────
BG          = colors.HexColor("#f8f9fa")
PANEL       = colors.HexColor("#e9ecef")
PANEL2      = colors.HexColor("#dee2e6")
ACCENT      = colors.HexColor("#1d6fd8")
ACCENT2     = colors.HexColor("#6610f2")
OK_C        = colors.HexColor("#198754")
WARN_C      = colors.HexColor("#e67e00")
ERR_C       = colors.HexColor("#dc3545")
FG          = colors.HexColor("#212529")
DIM         = colors.HexColor("#6c757d")
WHITE       = colors.white
GREEN       = colors.HexColor("#16a34a")
ORANGE      = colors.HexColor("#ea580c")
PURPLE      = colors.HexColor("#8b5cf6")
TEAL        = colors.HexColor("#0d9488")

W, H = A4
MARGE_L = 2.0 * cm
MARGE_R = 2.0 * cm
MARGE_T = 2.0 * cm
MARGE_B = 2.5 * cm
BREEDTE = W - MARGE_L - MARGE_R

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NAS_ROOT = os.path.dirname(SCRIPT_DIR) if os.path.basename(SCRIPT_DIR) == "Publicatie" \
           else (r"C:\PiNAS" if sys.platform == "win32" else SCRIPT_DIR)


def screenshot_flowable(bestandsnaam, bijschrift, s, max_breedte=None):
    pad = os.path.join(NAS_ROOT, "Beheer", "assets", bestandsnaam)
    if max_breedte is None:
        max_breedte = BREEDTE
    if not os.path.exists(pad):
        return [Paragraph(f"<i>(Schermafbeelding {bestandsnaam} niet gevonden - "
                          f"voeg deze toe in Beheer\\assets en bouw de "
                          f"handleiding opnieuw.)</i>", s["body"])]
    try:
        img = Image(pad)
        schaal = max_breedte / float(img.imageWidth)
        img.drawWidth = max_breedte
        img.drawHeight = img.imageHeight * schaal
        omkadering = Table([[img]], colWidths=[max_breedte])
        omkadering.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c8d0da")),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return [omkadering,
                Spacer(1, 0.12*cm),
                Paragraph(bijschrift, s["bijschrift"] if "bijschrift" in s else s["body"])]
    except Exception as e:
        return [Paragraph(f"<i>(Schermafbeelding {bestandsnaam} kon niet geladen "
                          f"worden: {e})</i>", s["body"])]

_MAANDEN_NL = ["januari","februari","maart","april","mei","juni","juli",
               "augustus","september","oktober","november","december"]
_nu = datetime.datetime.now()
DATUM = f"{_nu.day} {_MAANDEN_NL[_nu.month-1]} {_nu.year}"

# ── Stijlen ─────────────────────────────────────────────────────────────────
def maak_stijlen():
    s = {}
    basis = dict(fontName="Helvetica", textColor=FG, leading=14)

    s["titel"] = ParagraphStyle("titel",
        fontSize=28, fontName="Helvetica-Bold",
        textColor=ACCENT, alignment=TA_CENTER, spaceAfter=6, leading=34)

    s["ondertitel"] = ParagraphStyle("ondertitel",
        fontSize=12, fontName="Helvetica",
        textColor=DIM, alignment=TA_CENTER, spaceAfter=4, leading=16)

    s["versie"] = ParagraphStyle("versie",
        fontSize=10, fontName="Helvetica",
        textColor=DIM, alignment=TA_CENTER, spaceAfter=20, leading=14)

    s["h1"] = ParagraphStyle("h1",
        fontSize=16, fontName="Helvetica-Bold",
        textColor=ACCENT, spaceBefore=18, spaceAfter=8, leading=20,
        borderPad=4, keepWithNext=True)

    s["h2"] = ParagraphStyle("h2",
        fontSize=13, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#6610f2"), spaceBefore=12, spaceAfter=6, leading=17,
        keepWithNext=True)

    s["h3"] = ParagraphStyle("h3",
        fontSize=11, fontName="Helvetica-Bold",
        textColor=FG, spaceBefore=8, spaceAfter=4, leading=15,
        keepWithNext=True)

    s["body"] = ParagraphStyle("body",
        fontSize=10, fontName="Helvetica",
        textColor=FG, spaceAfter=6, leading=15)

    s["body_dim"] = ParagraphStyle("body_dim",
        fontSize=9, fontName="Helvetica",
        textColor=DIM, spaceAfter=4, leading=13)

    s["bullet"] = ParagraphStyle("bullet",
        fontSize=10, fontName="Helvetica",
        textColor=FG, spaceAfter=4, leading=14,
        leftIndent=14, bulletIndent=0)

    s["code"] = ParagraphStyle("code",
        fontSize=8.5, fontName="Courier",
        textColor=colors.HexColor("#155724"),
        backColor=colors.HexColor("#f0fff4"),
        spaceAfter=6, leading=13,
        leftIndent=8, rightIndent=8,
        borderPad=6)

    s["info_titel"] = ParagraphStyle("info_titel",
        fontSize=9, fontName="Helvetica-Bold",
        textColor=ACCENT, spaceAfter=2, leading=13)

    s["info_body"] = ParagraphStyle("info_body",
        fontSize=9, fontName="Helvetica",
        textColor=FG, spaceAfter=2, leading=13)

    s["toc"] = ParagraphStyle("toc",
        fontSize=10, fontName="Helvetica",
        textColor=FG, spaceAfter=3, leading=14, leftIndent=0)

    s["toc2"] = ParagraphStyle("toc2",
        fontSize=9, fontName="Helvetica",
        textColor=DIM, spaceAfter=2, leading=13, leftIndent=12)

    s["voetnoot"] = ParagraphStyle("voetnoot",
        fontSize=8, fontName="Helvetica",
        textColor=DIM, spaceAfter=2, leading=11)

    s["center"] = ParagraphStyle("center",
        fontSize=10, fontName="Helvetica",
        textColor=FG, alignment=TA_CENTER, spaceAfter=6, leading=14)

    s["symbool"] = ParagraphStyle("symbool",
        fontSize=10, fontName="Helvetica-Bold",
        textColor=OK_C, spaceAfter=2, leading=14)

    s["bijschrift"] = ParagraphStyle("bijschrift",
        fontSize=8, fontName="Helvetica-Oblique",
        textColor=DIM, alignment=TA_CENTER, spaceAfter=8, leading=11)

    return s

# ── Info box ────────────────────────────────────────────────────────────────
def info_box(stijlen, titel, regels, kleur=ACCENT, breedte=None):
    if breedte is None:
        breedte = BREEDTE
    data = [[Paragraph(f"<b>{titel}</b>", stijlen["info_titel"])]]
    for r in regels:
        data.append([Paragraph(r, stijlen["info_body"])])
    t = Table(data, colWidths=[breedte])
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0),  colors.HexColor("#1d6fd8")),
        ("BACKGROUND",  (0,1), (-1,-1), colors.HexColor("#ffffff")),
        ("LEFTPADDING",  (0,0), (-1,-1), 10),
        ("RIGHTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING",   (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,0), (-1,-1), 6),
        ("LINEBEFORE",   (0,0), (0,-1), 3, kleur),
        ("LINEBELOW",    (0,-1),(-1,-1), 0.5, DIM),
        ("LINEABOVE",    (0,0), (-1,0),  0.5, DIM),
    ]))
    return t

# ── Tabel helper ─────────────────────────────────────────────────────────────
def data_tabel(stijlen, headers, rijen, col_breedte=None):
    if col_breedte is None:
        n = len(headers)
        col_breedte = [BREEDTE / n] * n
    data = [[Paragraph(f"<b>{h}</b>", stijlen["info_titel"]) for h in headers]]
    for rij in rijen:
        data.append([Paragraph(str(c), stijlen["body"]) for c in rij])
    t = Table(data, colWidths=col_breedte, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0),  ACCENT),
        ("BACKGROUND",  (0,1), (-1,-1), colors.HexColor("#ffffff")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1),
         [colors.HexColor("#ffffff"), colors.HexColor("#f0f4ff")]),
        ("TEXTCOLOR",   (0,0), (-1,0), colors.HexColor("#ffffff")),
        ("TEXTCOLOR",   (0,1), (-1,-1), FG),
        ("GRID",        (0,0), (-1,-1), 0.3, DIM),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("LINEABOVE",    (0,0), (-1,0), 1, ACCENT),
    ]))
    return t

# ── Illustraties ─────────────────────────────────────────────────────────────
class IllustratiePiSysteem(Flowable):
    def __init__(self, breedte=BREEDTE, hoogte=5*cm):
        super().__init__()
        self.breedte = breedte
        self.hoogte = hoogte

    def wrap(self, *args):
        return self.breedte, self.hoogte

    def draw(self):
        c = self.canv
        w, h = self.breedte, self.hoogte

        c.setFillColor(colors.HexColor("#ffffff"))
        c.roundRect(0, 0, w, h, 8, fill=1, stroke=0)

        pc_x, pc_y, pc_w, pc_h = 0.5*cm, 0.8*cm, 3.5*cm, 3.0*cm
        c.setFillColor(PANEL2)
        c.roundRect(pc_x, pc_y, pc_w, pc_h, 6, fill=1, stroke=0)
        c.setFillColor(ACCENT)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(pc_x + pc_w/2, pc_y + pc_h - 0.5*cm, "Windows PC")
        c.setFillColor(FG)
        c.setFont("Helvetica", 7)
        c.drawCentredString(pc_x + pc_w/2, pc_y + pc_h - 0.9*cm, "Pi NAS Menu")
        c.drawCentredString(pc_x + pc_w/2, pc_y + pc_h - 1.2*cm, "Backup Beheer")
        c.drawCentredString(pc_x + pc_w/2, pc_y + 0.6*cm, "Opslag (SSD)")
        c.drawCentredString(pc_x + pc_w/2, pc_y + 0.35*cm, "Backup (HDD)")

        pi_x = w/2 - 2*cm
        pi_y, pi_w, pi_h = 0.8*cm, 4*cm, 3.0*cm
        c.setFillColor(colors.HexColor("#d1fae5"))
        c.roundRect(pi_x, pi_y, pi_w, pi_h, 6, fill=1, stroke=0)
        c.setStrokeColor(OK_C)
        c.setLineWidth(1)
        c.roundRect(pi_x, pi_y, pi_w, pi_h, 6, fill=0, stroke=1)
        c.setFillColor(OK_C)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(pi_x + pi_w/2, pi_y + pi_h - 0.5*cm, "Raspberry Pi 5")
        c.setFillColor(FG)
        c.setFont("Helvetica", 7)
        c.drawCentredString(pi_x + pi_w/2, pi_y + pi_h - 0.9*cm, "Samba  Nextcloud")
        c.drawCentredString(pi_x + pi_w/2, pi_y + pi_h - 1.2*cm, "FileBrowser  SSH")
        c.drawCentredString(pi_x + pi_w/2, pi_y + 0.5*cm, "/mnt/opslag (SSD)")
        c.drawCentredString(pi_x + pi_w/2, pi_y + 0.25*cm, "/mnt/backup (HDD)")

        hdd_x = w - 4.2*cm
        hdd_y, hdd_w, hdd_h = 0.8*cm, 3.5*cm, 3.0*cm
        c.setFillColor(colors.HexColor("#fff3cd"))
        c.roundRect(hdd_x, hdd_y, hdd_w, hdd_h, 6, fill=1, stroke=0)
        c.setStrokeColor(ORANGE)
        c.roundRect(hdd_x, hdd_y, hdd_w, hdd_h, 6, fill=0, stroke=1)
        c.setFillColor(ORANGE)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(hdd_x + hdd_w/2, hdd_y + hdd_h - 0.5*cm, "Externe HDD")
        c.setFillColor(FG)
        c.setFont("Helvetica", 7)
        c.drawCentredString(hdd_x + hdd_w/2, hdd_y + hdd_h - 0.9*cm, "Seagate 7.3 TB")
        c.drawCentredString(hdd_x + hdd_w/2, hdd_y + 0.5*cm, "Backups")
        c.drawCentredString(hdd_x + hdd_w/2, hdd_y + 0.25*cm, "PC Images")

        mid_y = h / 2
        c.setStrokeColor(ACCENT)
        c.setLineWidth(1.5)
        c.line(pc_x + pc_w, mid_y, pi_x, mid_y)
        c.setFillColor(ACCENT)
        p = c.beginPath(); p.moveTo(pi_x, mid_y); p.lineTo(pi_x-8, mid_y+4); p.lineTo(pi_x-8, mid_y-4); p.close(); c.drawPath(p, fill=1, stroke=0)
        c.setFillColor(ACCENT)
        c.setFont("Helvetica", 6)
        c.drawCentredString((pc_x + pc_w + pi_x) / 2, mid_y + 3, "SMB / SSH")

        c.setStrokeColor(ORANGE)
        c.line(pi_x + pi_w, mid_y, hdd_x, mid_y)
        c.setFillColor(ORANGE)
        p = c.beginPath(); p.moveTo(hdd_x, mid_y); p.lineTo(hdd_x-8, mid_y+4); p.lineTo(hdd_x-8, mid_y-4); p.close(); c.drawPath(p, fill=1, stroke=0)
        c.setFillColor(ORANGE)
        c.setFont("Helvetica", 6)
        c.drawCentredString((pi_x + pi_w + hdd_x) / 2, mid_y + 3, "USB / fstab")


class IllustratieBackupFlow(Flowable):
    def __init__(self, breedte=BREEDTE, hoogte=3.5*cm):
        super().__init__()
        self.breedte = breedte
        self.hoogte = hoogte

    def wrap(self, *args):
        return self.breedte, self.hoogte

    def draw(self):
        c = self.canv
        w, h = self.breedte, self.hoogte

        c.setFillColor(colors.HexColor("#ffffff"))
        c.roundRect(0, 0, w, h, 6, fill=1, stroke=0)

        stappen = [
            ("Verbinden",    ACCENT,  "Opslag/Backup"),
            ("Bronnen",      ACCENT2, "selecteren"),
            ("Doelpad",      TEAL,    "instellen"),
            ("Start",        GREEN,   "Backup"),
            ("Klaar",        OK_C,    "Log check"),
        ]

        n = len(stappen)
        blok_b = (w - 1.2*cm) / n
        for i, (naam, kleur, sub) in enumerate(stappen):
            x = 0.6*cm + i * blok_b
            bx = x + 0.1*cm
            by = 0.6*cm
            bw = blok_b - 0.3*cm
            bh = h - 1.2*cm

            c.setFillColor(kleur)
            c.setFillAlpha(0.2)
            c.roundRect(bx, by, bw, bh, 4, fill=1, stroke=0)
            c.setFillAlpha(1)

            c.setStrokeColor(kleur)
            c.setLineWidth(1)
            c.roundRect(bx, by, bw, bh, 4, fill=0, stroke=1)

            c.setFillColor(kleur)
            c.setFont("Helvetica-Bold", 8)
            c.drawCentredString(bx + bw/2, by + bh - 0.35*cm, naam)
            c.setFillColor(FG)
            c.setFont("Helvetica", 7)
            c.drawCentredString(bx + bw/2, by + 0.2*cm, sub)

            if i < n - 1:
                ax = bx + bw + 0.1*cm
                ay = by + bh/2
                c.setStrokeColor(DIM)
                c.setLineWidth(0.8)
                c.line(ax, ay, ax + 0.1*cm, ay)
                c.setFillColor(DIM)
                p = c.beginPath(); p.moveTo(ax+0.1*cm, ay); p.lineTo(ax-2, ay+3); p.lineTo(ax-2, ay-3); p.close(); c.drawPath(p, fill=1, stroke=0)

        for i in range(n):
            x = 0.6*cm + i * blok_b
            bx = x + 0.1*cm
            c.setFillColor(DIM)
            c.setFont("Helvetica", 6)
            c.drawCentredString(bx + (blok_b-0.3*cm)/2, 0.1*cm, f"Stap {i+1}")


def pagina_achtergrond(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(BG)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    canvas.setStrokeColor(colors.HexColor("#adb5bd"))
    canvas.setLineWidth(1)
    canvas.rect(0.8*cm, 0.8*cm, W - 1.6*cm, H - 1.6*cm, fill=0, stroke=1)
    canvas.setStrokeColor(ACCENT)
    canvas.setLineWidth(0.5)
    canvas.line(MARGE_L, H - 1.5*cm, W - MARGE_R, H - 1.5*cm)
    canvas.setStrokeColor(DIM)
    canvas.setLineWidth(0.3)
    canvas.line(MARGE_L, 1.8*cm, W - MARGE_R, 1.8*cm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(DIM)
    canvas.drawString(MARGE_L, 1.2*cm, f"Pi NAS Suite Handleiding · {DATUM}")
    canvas.drawRightString(W - MARGE_R, 1.2*cm, f"Pagina {doc.page}")
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(DIM)
    canvas.drawString(MARGE_L, H - 1.2*cm, "Pi NAS Suite — Gebruikershandleiding")
    canvas.drawRightString(W - MARGE_R, H - 1.2*cm, "Gemaakt met Claude (Anthropic)")
    canvas.restoreState()

def eerste_pagina(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(BG)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    canvas.setFillColor(PANEL)
    canvas.rect(0, H - 4*cm, W, 4*cm, fill=1, stroke=0)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, H - 4.1*cm, W, 0.15*cm, fill=1, stroke=0)
    canvas.setFillColor(PANEL)
    canvas.rect(0, 0, W, 1.5*cm, fill=1, stroke=0)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, 1.5*cm, W, 0.1*cm, fill=1, stroke=0)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(DIM)
    canvas.drawCentredString(W/2, 0.6*cm,
        f"Pi NAS Suite · {DATUM} · Gemaakt met Claude (Anthropic)")
    canvas.restoreState()



def h2_blok(stijlen, titel, *elementen):
    inhoud = [Paragraph(titel, stijlen["h2"])]
    if elementen:
        inhoud.append(elementen[0])
    blok = [KeepTogether(inhoud)]
    for el in elementen[1:]:
        blok.append(el)
    return blok

# ── Content opbouwen ─────────────────────────────────────────────────────────
def bouw_handleiding():
    s = maak_stijlen()
    story = []

    story.append(Spacer(1, 3.5*cm))
    story.append(Paragraph("Pi NAS Suite", s["titel"]))
    story.append(Paragraph("Gebruikershandleiding", ParagraphStyle("ot2",
        fontSize=18, fontName="Helvetica",
        textColor=FG, alignment=TA_CENTER, spaceAfter=8, leading=24)))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "Raspberry Pi thuisserver met Windows backup, Nextcloud en bestandsbeheer",
        s["ondertitel"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(f"Python + Tkinter · {DATUM}", s["versie"]))
    story.append(Spacer(1, 0.8*cm))

    story.append(IllustratiePiSysteem(BREEDTE, 5*cm))
    story.append(Spacer(1, 0.8*cm))

    intro = data_tabel(s,
        ["Onderdeel", "Beschrijving"],
        [
            ["Pi NAS Menu",  "Centraal beheer van je NAS — verbinden, uploaden, diagnose"],
            ["PiNAS Sync",   "Bestanden synchroniseren en PC Images veiligstellen op de NAS"],
            ["Pi NAS Server","Raspberry Pi 5 met Samba, Nextcloud en FileBrowser"],
        ],
        [5*cm, BREEDTE - 5*cm])
    story.append(intro)
    story.append(PageBreak())

    story.append(Paragraph("Inhoudsopgave", s["h1"]))
    story.append(HRFlowable(width=BREEDTE, thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 0.3*cm))

    toc = [
        ("1.", "Wat is de Pi NAS Suite?", None),
        ("2.", "Installatie", [
            ("2.1", "Vereisten"),
            ("2.2", "Bron kiezen & Beheer_install.bat (eenmalig, alleen op een gloednieuwe pc)"),
            ("2.3", "Stap 1 — Jouw gegevens invullen"),
            ("2.4", "Stap 2 — SD-kaart voorbereiden"),
            ("2.5", "Stap 3 — Pi instellen"),
            ("2.6", "Stap 4 — Windows klaarzetten"),
            ("2.7", "Mappenstructuur na installatie"),
        ]),
        ("3.", "Pi NAS Menu", [
            ("3.1", "Hoofdvenster"),
            ("3.2", "Verbinden via SSH en VNC"),
            ("3.3", "Externe HDD"),
            ("3.4", "Status & details"),
            ("3.5", "Installatie & Herstel, Controles, Onderhoud"),
            ("3.6", "Backup Beheer"),
            ("3.7", "Addons Beheer"),
            ("3.8", "Pi NAS herstarten"),
        ]),
        ("4.", "Controles", [
            ("4.1", "Structuurcheck & Opruimen"),
            ("4.2", "Suite testen"),
            ("4.3", "Diagnose uitvoeren"),
            ("4.4", "Log Bestanden Bekijken"),
            ("4.5", "Systeem-image terugzetten (SD-kaart)"),
        ]),
        ("5.", "PiNAS Sync (Synchronisatie)", [
            ("5.1", "Scherm 1 - Bronnen en doelen kiezen"),
            ("5.2", "Scherm 2 - Synchroniseren"),
        ]),
        ("6.", "PC Image Backup", None),
        ("7.", "NAS Wachtwoord beheren", None),
        ("8.", "Veelvoorkomende problemen", None),
        ("9.", "Technische informatie", None),
        ("10.", "Bekende eigenaardigheden", None),
    ]

    for num, titel, subs in toc:
        story.append(Paragraph(f"<b>{num}</b>  {titel}", s["toc"]))
        if subs:
            for snum, stitel in subs:
                story.append(Paragraph(f"  {snum}  {stitel}", s["toc2"]))
    story.append(PageBreak())

    story.append(Paragraph("1. Wat is de Pi NAS Suite?", s["h1"]))
    story.append(HRFlowable(width=BREEDTE, thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "De Pi NAS Suite is een complete thuisserver oplossing op basis van een Raspberry Pi 5. "
        "Je kunt er bestanden op opslaan, automatisch backups naar maken, en de server beheren "
        "vanuit Windows — zonder technische kennis.", s["body"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "De suite bestaat uit drie delen die samenwerken:", s["body"]))
    story.append(Spacer(1, 0.2*cm))

    story.append(data_tabel(s,
        ["Onderdeel", "Wat doet het?", "Op welk apparaat?"],
        [
            ["Pi NAS Menu",   "Verbinden, uploaden, diagnose, beheer",    "Windows PC"],
            ["PiNAS Sync",    "Synchroniseren en PC Images backuppen",      "Windows PC"],
            ["Pi NAS Server", "Bestanden opslaan, Nextcloud, FileBrowser", "Raspberry Pi 5"],
        ],
        [3.5*cm, 8*cm, 4*cm]))
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph(
        "De Pi fungeert als een netwerkschijf op je thuisnetwerk. Windows ziet hem als "
        "twee schijven: Opslag (snelle SSD) en Backup (grote externe HDD) - elk met een "
        "eigen stationsletter die je zelf kiest bij installatie (standaard Y: en Z:).",
        s["body"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(info_box(s, "Tip",
        ["De Pi NAS Suite werkt volledig lokaal op je thuisnetwerk.",
         "Geen cloud abonnement, geen maandelijkse kosten — jouw data blijft bij jou."],
        kleur=OK_C))
    story.append(PageBreak())

    story.append(Paragraph("2. Installatie", s["h1"]))
    story.append(HRFlowable(width=BREEDTE, thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("2.1 Vereisten", s["h2"]))
    story.append(data_tabel(s,
        ["Onderdeel", "Vereiste", "Opmerking"],
        [
            ["Raspberry Pi",  "Pi 5 (aanbevolen) of Pi 4",  "Min. 4GB RAM"],
            ["SD-kaart",      "Min. 16 GB",                  "Class 10 of beter"],
            ["SSD",           "USB SSD, bijv. 220 GB",       "Voor de Opslag-schijf"],
            ["Externe HDD",   "USB HDD, bijv. 7.3 TB",       "Voor de Backup-schijf (optioneel)"],
            ["Windows PC",    "Windows 10 of 11",            "Voor Pi NAS Menu en PiNAS Sync"],
            ["Python",        "Python 3.10 of hoger",        "Gratis via python.org"],
            ["Netwerk",       "Thuisnetwerk (router/switch)", "Pi en PC op zelfde netwerk"],
        ],
        [3.5*cm, 5*cm, 7*cm]))
    story.append(Spacer(1, 0.4*cm))

    # 9 augustus 2026 (Frans, over hoofdstuk 2: "komt het geheel niet
    # correct over - ik mis de Github en/of Starter Kit, anders kom of
    # weet je helemaal niets van menu"): hoofdstuk 2 begon tot nu toe
    # meteen met "download Pi Imager", alsof Pi NAS Menu al op de pc
    # staat. Voor iemand die ECHT vanaf 0 begint (geen Pi, lege SD-kaart,
    # nog geen suite op de pc) ontbrak de eerste, noodzakelijke stap
    # volledig: een bron kiezen en Beheer_install.bat draaien. Tegelijk
    # ontbrak wizard-stap 1 (Gegevens invullen) hier ook - hoofdstuk 2
    # sprong direct naar wizard-stap 2 (SD-kaart). Nu volledig gelijk
    # getrokken met de al geverifieerde 4-stappen-wizard uit hoofdstuk 3.5
    # en de presentatie: Bron kiezen -> Gegevens -> SD-kaart -> Pi
    # instellen -> Windows klaarzetten.
    story.append(Paragraph("2.2 Bron kiezen & Beheer_install.bat (eenmalig, alleen op een gloednieuwe pc)", s["h2"]))
    story.append(Paragraph(
        "Staat de suite nog helemaal niet op deze Windows-pc? Dan begin je hier - dit is de "
        "enige stap die je maar één keer per pc doet, VOORDAT er ook maar een Pi NAS Menu "
        "bestaat om te openen:", s["body"]))
    for stap in [
        "Kies een bron: de <b>Starter Kit ZIP</b> (kant-en-klaar pakket, bijv. van een USB-stick "
        "of gedeelde map) of de <b>publieke GitHub-versie</b> (download/kloon) - allebei precies "
        "hetzelfde pakket, alleen het kanaal verschilt",
        "Pak het pakket uit naar een map naar keuze",
        "Draai daarin <b>Beheer_install.bat</b> - dit losse bestand staat los in de root van het "
        "uitgepakte geheel",
        "Beheer_install.bat zet de hele suite neer op C:\\PiNAS, installeert de Windows-onderdelen "
        "(PuTTY, TigerVNC) en maakt een bureaubladsnelkoppeling",
        "Belangrijk: Beheer_install.bat opent zelf NIETS - open daarna zelf de nieuwe "
        "snelkoppeling om Pi NAS Menu voor het eerst te starten",
    ]:
        story.append(Paragraph(f"+ {stap}", s["bullet"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(info_box(s, "Staat de suite al op deze pc?",
        ["Sla deze stap dan over en ga direct naar 2.3 hieronder - Beheer_install.bat hoeft er "
         "dan niet meer aan te pas te komen.",
         "Pi NAS Menu opent gewoon, ook als de Pi nog nergens aanstaat en de SD-kaart nog leeg "
         "is - de statuscontroles lopen op de achtergrond en blokkeren het openen niet."],
        kleur=ACCENT))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("2.3 Stap 1 — Jouw gegevens invullen", s["h2"]))
    story.append(Paragraph(
        "Open Pi NAS Menu (via de nieuwe snelkoppeling) en klik onder BEHEER op "
        "<b>Installatie & Herstel</b>. Dit start de Setup wizard (pi_nas_setup.pyw), die je in "
        "4 stappen door de rest van de installatie leidt. Stap 1 vraagt:", s["body"]))
    for item in [
        "Het IP-adres van de Pi (mag je op dit moment nog niet zeker weten - dat wordt in "
        "stap 2 en 3 gecontroleerd)",
        "Het gewenste NAS-wachtwoord - dit wordt veilig opgeslagen in de Windows Credential "
        "Manager, nergens los in een tekstbestand",
    ]:
        story.append(Paragraph(f"+ {item}", s["bullet"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("2.4 Stap 2 — SD-kaart voorbereiden", s["h2"]))
    story.append(Paragraph(
        "Gebruik het externe programma Raspberry Pi Imager om de SD-kaart klaar te maken - "
        "dit is een aparte download, geen onderdeel van de Starter Kit of Beheer_install.bat:", s["body"]))
    for stap in [
        "Download Pi Imager via <b>raspberrypi.com/software</b>",
        "Kies apparaat: <b>Raspberry Pi 5</b>",
        "Kies OS: <b>Raspberry Pi OS Lite (64-bit)</b>",
        "Kies jouw SD-kaart",
        "Klik op het tandwiel en stel in: hostname <b>piNAS</b>, SSH inschakelen, gebruiker <b>pi</b> met jouw wachtwoord",
        "Schrijf de SD-kaart en stop hem in de Pi",
    ]:
        story.append(Paragraph(f"+ {stap}", s["bullet"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "Zodra de Pi opstart met deze kaart, wacht de wizard automatisch (ping + SSH-controle) "
        "tot hij online is - of klik 'Ik weet zeker dat de Pi al bereikbaar is' om dit over te "
        "slaan bij een bestaande Pi.", s["body"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("2.5 Stap 3 — Pi instellen", s["h2"]))
    story.append(Paragraph(
        "Zodra de Pi online is, gaat de wizard vanzelf door naar stap 3. Dit installeert "
        "automatisch alle benodigde software op de Pi:", s["body"]))
    for item in [
        "Samba — voor de netwerkschijven Opslag en Backup",
        "Nextcloud — voor bestanden via de browser",
        "FileBrowser — eenvoudig bestandsbeheer",
        "SSH — voor beheer op afstand",
    ]:
        story.append(Paragraph(f"+ {item}", s["bullet"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(info_box(s, "Let op",
        ["De Pi heeft een vast IP-adres nodig op je netwerk.",
         "Reserveer het IP in je router of stel een statisch IP in."],
        kleur=WARN_C))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("2.6 Stap 4 — Windows klaarzetten", s["h2"]))
    story.append(Paragraph(
        "De laatste wizardstap, ook volledig automatisch, installeert:", s["body"]))
    story.append(data_tabel(s,
        ["Software", "Waarvoor?"],
        [
            ["PuTTY",         "SSH verbinding via terminal"],
            ["TigerVNC",      "Grafisch bureaublad van de Pi op je scherm"],
            ["Python 3 + Tkinter", "Vereist voor PiNAS Sync (geen externe pakketten)"],
            ["Opslag-schijf",     "Netwerkschijf gekoppeld aan de SSD op de Pi"],
            ["Backup-schijf",     "Netwerkschijf gekoppeld aan de externe HDD"],
        ],
        [4*cm, BREEDTE - 4*cm]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "Hierna staat er een werkende snelkoppeling op je bureaublad en is Pi NAS Menu direct "
        "te gebruiken - de installatie is klaar.", s["body"]))
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("2.7 Mappenstructuur na installatie", s["h2"]))
    story.append(data_tabel(s,
        ["Map", "Inhoud", "Beschikbaar in"],
        [
            [r"C:\PiNAS\Beheer" + "\\",  "Pi NAS Menu, installer, Backup Beheer, tools",     "Minimaal + Schaduwkopie"],
            [r"C:\PiNAS\Sync" + "\\",   "PiNAS Sync programma (synchronisatie)",           "Minimaal + Schaduwkopie"],
            [r"C:\PiNAS\PiServer" + "\\",      "Server scripts (nas_installer.py e.a.)",          "Minimaal + Schaduwkopie"],
            [r"C:\PiNAS\ArchiefBackup" + "\\",    "Archief Backup Bewaking programma",           "Minimaal + Schaduwkopie"],
            [r"C:\PiNAS\Gedeeld" + "\\",    "Gedeelde hulpscripts en modules",                "Schaduwkopie"],
            [r"C:\PiNAS\Logs" + "\\",       "Logbestanden en wachtwoordcache",                "Automatisch aangemaakt"],
            [r"C:\PiNAS\Publicatie" + "\\", "Handleiding, topografie, presentatie, GitHub publieke versie",            "Schaduwkopie"],
            [r"C:\PiNAS\Installatie" + "\\","Installers (TigerVNC, Pi Imager, PuTTY, Python)",  "Schaduwkopie"],
        ],
        [5.5*cm, 6*cm, BREEDTE - 11.5*cm]))
    story.append(PageBreak())

    story.append(Paragraph("3. Pi NAS Menu", s["h1"]))
    story.append(HRFlowable(width=BREEDTE, thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "Het Pi NAS Menu is het centrale beheerprogramma op je Windows PC. "
        "Het heeft twee lagen: dagelijks beheer en een Setup wizard.", s["body"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(data_tabel(s,
        ["Laag", "Functie", "Bereikbaar via"],
        [
            ["Laag 1 — Dagelijks beheer", "Status, verbinden, backup, diagnose, beheer",    "Hoofdvenster"],
            ["Laag 2 — Setup wizard",     "Pi Server, Pi Opties, Windows klaarzetten",      "Knop 'Installatie & Herstel' onder BEHEER"],
        ],
        [4.5*cm, 6.5*cm, BREEDTE - 11*cm]))
    story.append(Spacer(1, 0.2*cm))
    story.append(info_box(s, "Info",
        ["Elke 15 sec: Pi bereikbaarheid controleren.",
         "Elke 30 sec: Windows status (Opslag/Backup-schijven) verversen.",
         "Elke 60 sec: Pi services status verversen.",
         "Bij opstarten: Pi scripts sync check (MD5 vergelijking lokaal vs Pi)."],
        kleur=ACCENT))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("3.1 Hoofdvenster", s["h2"]))
    story.append(Paragraph(
        "Het hoofdvenster toont bovenaan drie statusbollen:", s["body"]))
    story.append(data_tabel(s,
        ["Bol", "Betekenis"],
        [
            ["PC — software & schijven",  "Groen = PuTTY, TigerVNC, PiNAS Sync en Opslag/Backup allemaal OK"],
            ["Raspberry Pi — services",   "Groen = Samba, Nextcloud, FileBrowser, Cockpit beschikbaar op de Pi"],
            ["Pi scripts — sync",         "Groen = alle scripts op de Pi zijn up-to-date t.o.v. lokaal"],
            ["Nextcloud URL",              "Verschijnt als Nextcloud actief is — klikbaar, opent browser direct naar Nextcloud"],
        ],
        [6*cm, BREEDTE - 6*cm]))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "Onder de statusbollen staan de secties: VERBINDEN, EXTERNE HDD, "
        "BACKUP (Backup Beheer), ADDONS (Addons Beheer) en BEHEER "
        "(Installatie & Herstel, Controles, Onderhoud).", s["body"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("3.2 Verbinden via SSH en VNC", s["h2"]))
    story.append(data_tabel(s,
        ["Knop", "Wat doet het?"],
        [
            ["SSH via PowerShell", "Opent een terminal rechtstreeks naar de Pi — geen extra software nodig"],
            ["SSH via PuTTY",      "Opent PuTTY met het ingestelde IP-adres"],
            ["TigerVNC bureaublad","Opent het grafische bureaublad van de Pi op je scherm (poort 5901)"],
            ["Schijven verbinden (netwerkschijven)", "Koppelt Opslag en Backup schoon opnieuw (zonder /persistent), gebruikt het opgeslagen wachtwoord, ververst de status direct"],
        ],
        [4.5*cm, BREEDTE - 4.5*cm]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("3.3 Externe HDD", s["h2"]))
    story.append(Paragraph(
        "De externe HDD (Backup-schijf) wordt aangestuurd via een smart plug. "
        "Je kunt hem aan- en uitzetten vanuit het menu:", s["body"]))
    story.append(data_tabel(s,
        ["Knop", "Werking"],
        [
            ["Aanzetten", "Smart plug aan → wacht ~15 sec op mount → Backup-schijf automatisch koppelen in Windows"],
            ["Uitzetten", "Backup-schijf ontkoppelen in Windows → umount op Pi → smart plug uit"],
        ],
        [3.5*cm, BREEDTE - 3.5*cm]))
    story.append(Spacer(1, 0.2*cm))
    story.append(info_box(s, "Info",
        ["De HDD hoeft niet altijd aan te staan.",
         "Zet hem alleen aan als je een grote backup wilt maken of een PC Image wilt opslaan."],
        kleur=ACCENT))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("3.4 Status & details", s["h2"]))
    story.append(Paragraph(
        "De knop 'Status & details' opent een uitgebreid venster met:", s["body"]))
    for item in [
        "Deze PC — software: PuTTY, TigerVNC, PiNAS Sync, Opslag/Backup-schijven",
        "Raspberry Pi — services: Samba, Nextcloud, FileBrowser, Cockpit, Externe HDD svc",
        "Raspberry Pi — hardware: model, RAM, SD-kaart grootte, CPU temperatuur, uptime",
        "Pi scripts — sync: status per script (up-to-date / verschil / upload nodig) met upload knop",
        "Logbestanden: Pi NAS Menu, PiNAS Sync en Externe HDD logs met Open knop",
    ]:
        story.append(Paragraph(f"+ {item}", s["bullet"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("3.5 Installatie & Herstel, Controles, Onderhoud", s["h2"]))
    story.append(Paragraph(
        "Sinds de reorganisatie van 16 juli 2026 is wat vroeger 1 brede 'Beheer'-tab was, "
        "opgesplitst in drie knoppen onder BEHEER op het hoofdmenu, elk met een eigen doel:",
        s["body"]))
    story.append(Spacer(1, 0.15*cm))

    # 5 augustus 2026 (Frans: "we hebben een top-down benadering nodig,
    # nieuwe installatie is een beetje ondergeschoven"): 3 wegen bestaan
    # al, maar stonden verspreid zonder ooit als geheel benoemd te zijn.
    # Verwijst naar de al bestaande, gedetailleerde stukken hieronder
    # i.p.v. ze te herhalen (Frans: "we willen niets dubbel hebben").
    story.append(info_box(s, "3 wegen: wachtwoord, reparatie, of nieuwe installatie",
        ["1. Wachtwoord kwijt/wijzigen - Onderhoud -> Beveiliging -> 'NAS wachtwoord' (zie tabel hieronder).",
         "2. Iets kapot op een BESTAANDE installatie - gerichte reparatietools: Onderhoud -> "
         "'Pi services', 'Windows onderdelen', Geavanceerd -> LanMan-fix, of 'Schijven verbinden' "
         "op het hoofdmenu (zie tabellen hieronder).",
         "3. Volledig NIEUWE installatie (nieuwe Pi/pc) - zie 'De installatiereis' hieronder."]))
    story.append(Spacer(1, 0.2*cm))

    # 5 augustus 2026 (Frans: "dit ontdek ik zelf nu pas, moet overal heel
    # duidelijk zijn"): de volledige installatiereis stond nergens als
    # geheel beschreven, alleen de losse onderdelen apart. Later dezelfde
    # dag bleek een hele stap te ontbreken: Beheer_install.bat (de
    # bootstrap-installer voor een pc waar de suite nog NIET op staat) was
    # nog nooit gezien/gedocumenteerd - nu als beslisboom i.p.v. alleen een
    # lineaire lijst, want het startpunt bepaalt welke stap je nodig hebt.
    story.append(info_box(s, "De installatiereis - van 0 naar werkend NAS",
        ["Startpunt bepaalt de eerste stap: compleet NIEUWE Windows-pc (suite staat er nog niet "
         "op) -> eerst Beheer_install.bat draaien (staat los, in de root van het uitgepakte "
         "Starter Kit/GitHub-geheel). Dat zet de hele suite neer + Windows-onderdelen + "
         "bureaubladsnelkoppeling, maar opent zelf nog niets - open daarna zelf de nieuwe "
         "snelkoppeling. Suite staat al op deze pc? Sla deze stap over.",
         "1. Starter Kit bouwen - ALLEEN nodig om het pakket voor een ANDERE pc te maken "
         "(Distributie, hieronder), niet op de pc waar je het zelf installeert.",
         "2. Installatie & Herstel - VERPLICHT. De wizard (pi_nas_setup.pyw, 4 interne stappen: "
         "Gegevens, SD-kaart, Pi configureren, Windows afronden) installeert in Stap 3 automatisch "
         "al Samba, Cockpit en FileBrowser op de Pi, en koppelt in Stap 4 automatisch de Opslag-/"
         "Backup-schijven in Windows - geen van beide is een aparte, latere actie.",
         "3. Windows onderdelen (Onderhoud) - OPTIONEEL, als je bij Beheer_install.bat iets hebt "
         "overgeslagen of later nog iets wilt toevoegen/herstellen.",
         "4. Addons (Addons Beheer) - OPTIONEEL. Nextcloud, Pi-hole, ZeroTier, Vaultwarden, Mobiele "
         "statuspagina, Printserver, PiNAS Dashboard - kies zelf wat je installeert."]))
    story.append(Spacer(1, 0.2*cm))

    # 9 augustus 2026 (Frans: "je heb niets, wel een Pi, en een lege SD
    # kaart... werkt Pi Menu zonder werkende Pi en zonder geinstalleerde
    # SD kaart? maakt Starter Kit de SD kaart al, of moet dat via het
    # menu?") - twee punten die impliciet al uit de structuur volgden,
    # maar nooit met zoveel woorden waren uitgesproken. Geverifieerd in
    # de broncode (Pi_NAS_Menu.pyw: statuscontroles zijn asynchroon/
    # niet-blokkerend; Beheer_install.bat/Starter Kit raken de SD-kaart
    # nergens aan) voordat dit hier is toegevoegd.
    story.append(info_box(s, "Twee dingen die vaak over het hoofd worden gezien",
        ["Pi NAS Menu opent gewoon, ook als de Pi nog nergens aanstaat en de SD-kaart nog leeg is - "
         "de statuscontroles (bereikbaarheid, diensten) lopen op de achtergrond en blokkeren het "
         "openen niet. Je hoeft dus niet te wachten tot de Pi al draait om te beginnen.",
         "De SD-kaart wordt NIET door Beheer_install.bat of de Starter Kit geschreven - dat gebeurt "
         "in Stap 2 van de wizard, met het externe programma Raspberry Pi Imager (een aparte download, "
         "zie Installatie in de map Installatie). Beheer_install.bat/Starter Kit zetten alleen de "
         "Windows-kant van de suite neer."]))
    story.append(Spacer(1, 0.3*cm))

    # 5 augustus 2026 (Frans: "herinstallatie verdient een eigen
    # hoofdstukje om de 4 stappen te laten zien"): eigen sub-hoofdstuk,
    # elke stap apart uitgelegd - rechtstreeks uit pi_nas_setup.pyw
    # gehaald, niet aangenomen. Bewust GEEN nieuw genummerd 3.X-hoofdstuk
    # (de bestaande 3.1-3.9-nummering bleek al licht uit de pas te lopen
    # met de inhoudsopgave - dat risico niet vergroten door de hele keten
    # te moeten omnummeren).
    story.append(Paragraph("De 4 stappen van pi_nas_setup.pyw in detail", s["h3"]))
    story.append(data_tabel(s,
        ["Stap", "Wat gebeurt er", "Automatisch?"],
        [
            ["1. Jouw gegevens", "Pi IP-adres invullen, NAS-wachtwoord instellen (opgeslagen in "
             "Windows Credential Manager). Al een wachtwoord bekend? Veld leeg laten om het te "
             "behouden.", "Handmatig invullen"],
            ["2. SD-kaart voorbereiden", "Checklist voor Raspberry Pi Imager (Raspberry Pi 5, "
             "Raspberry Pi OS Lite 64-bit, hostname 'piNAS', SSH inschakelen, gebruiker pi). "
             "Daarna wacht de wizard automatisch (ping + SSH-controle) tot de Pi online is - of "
             "klik 'Ik weet zeker dat de Pi al bereikbaar is' om dit over te slaan bij een "
             "bestaande Pi.", "Handmatig (Imager) + automatische wachtcontrole"],
            ["3. Pi configureren", "Uploadt de PiServer-scripts naar de Pi en draait install.sh. "
             "Dat formatteert/koppelt de schijven en installeert Samba, Cockpit en FileBrowser. "
             "Duurt 5-15 minuten, met live voortgangsbalk en een uitklapbaar technisch log.",
             "Volledig automatisch"],
            ["4. Windows afronden", "LanManFix toepassen, inloggegevens opslaan, de Opslag- en "
             "Backup-schijf koppelen (kiest zelf een vrije letter, geen vaste Y:/Z: meer), een "
             "snelkoppeling op het bureaublad aanmaken, en Pi NAS Menu starten.",
             "Volledig automatisch"],
        ],
        [3.2*cm, BREEDTE - 7.2*cm, 4*cm]))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph(
        "Alleen Stap 1 en het Pi Imager-gedeelte van Stap 2 vragen om handmatige invoer - "
        "vanaf het moment dat de Pi online is, lopen Stap 3 en Stap 4 vanzelf door tot een "
        "werkend Pi NAS Menu op je bureaublad.", s["body"]))

    story.append(data_tabel(s,
        ["Knop", "Voor wat"],
        [
            ["Installatie & Herstel", "Start de installatiewizard (pi_nas_setup.pyw) - voor een nieuwe installatie of het herstellen van een bestaande."],
            ["Controles",             "Structuurcheck & Opruimen, Suite testen, Diagnose uitvoeren, Log Bestanden Bekijken - zie 4."],
            ["Onderhoud",             "Pi services en Windows onderdelen installeren/herstellen, Publicatie, Distributie, Geavanceerd, Weergave en Beveiliging - hieronder."],
        ],
        [3.5*cm, BREEDTE - 3.5*cm]))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "Onderhoud is zelf weer onderverdeeld in secties:", s["body"]))
    story.append(data_tabel(s,
        ["Sectie", "Functies"],
        [
            ["Pi services",       "Samba, FileBrowser, Cockpit en Externe HDD service installeren of herstellen op de Pi. Status per service wordt live gecheckt. Bij een NIEUWE installatie doet Installatie & Herstel dit al automatisch - deze knop is voor een latere reparatie."],
            ["Windows onderdelen","PuTTY, TigerVNC, Sync & Backup en Netwerkschijven (Opslag/Backup) - elk los aan te vinken en te installeren/herstellen."],
            ["Publicatie",        "Suite handleiding en Topografie herbouwen - elk met een 'Open'-knop ernaast om het resultaat meteen te bekijken. Het functieoverzicht staat sinds 10 augustus 2026 als losse pagina in de presentatie (PiNAS_Suite_Presentatie.pptx), niet meer als apart bestand."],
            ["Distributie",       "Starter Kit ZIP bouwen: verpakt de suite geanonimiseerd (zonder IP/wachtwoorden) in 1 ZIP voor een nieuwe pc; publieke versie maken voor GitHub."],
            ["Geavanceerd",       "Pi OS bijwerken (apt update + upgrade), Python bijwerken naar de laatste versie, Pi NAS herstarten (sudo reboot), LanMan-fix (alleen bij 'Toegang geweigerd' / Systeemfout 5), Scripts uploaden naar Pi, Download links beheren."],
            ["Weergave",          "Thema wisselen (licht/donker)"],
            ["Beveiliging",       "NAS wachtwoord instellen — wijzigt Samba wachtwoord op Pi én in Windows Credential Manager tegelijk. Wachtwoord wordt opgehaald via Credential Manager (primair) of bestandsfallback"],
        ],
        [3.5*cm, BREEDTE - 3.5*cm]))
    story.append(Spacer(1, 0.2*cm))

    # 6 augustus 2026 (Frans: "een tabel als je dat nog niet gedaan hebt
    # moet in de manual voor de duidelijkheid"): Beheer_install.bat versus
    # Installatie & Herstel als echte tabel, plus expliciet dat dit
    # ongeacht het distributiekanaal (Starter Kit ZIP of de publieke
    # GitHub-versie) precies hetzelfde werkt - alleen "map versus ZIP"
    # verschilt, de rest van de reis is identiek.
    story.append(Paragraph(
        "<b>Beheer_install.bat versus Installatie & Herstel</b> - dit geldt ONGEACHT via welk "
        "kanaal je aan de suite komt: Starter Kit ZIP en de publieke GitHub-versie werken hier "
        "identiek (de één een ZIP-bestand, de ander een gekloonde/gedownloade map) - beide "
        "resulteren in dezelfde map met bestanden, waarin Beheer_install.bat los in de root staat.",
        s["body"]))
    story.append(Spacer(1, 0.15*cm))
    story.append(data_tabel(s,
        ["", "Beheer_install.bat", "Installatie & Herstel (pi_nas_setup.pyw)"],
        [
            ["Wanneer nodig", "Alleen de allereerste keer, op een Windows-pc waar de suite nog "
             "helemaal niet op staat", "Elke keer dat de Pi zelf ingesteld/gerepareerd moet worden"],
            ["Waarom", "Er is nog geen Pi NAS Menu om te openen - dit bestand moet de hele suite "
             "eerst neerzetten", "Draait vanuit het al-werkende Pi NAS Menu"],
            ["Wat het doet", "Kopieert alle suite-bestanden naar C:\\PiNAS, installeert PuTTY/VNC, "
             "maakt de bureaubladsnelkoppeling", "Stelt de Pi zelf in (Samba/Cockpit/"
             "FileBrowser), koppelt de schijven"],
        ],
        [2.6*cm, (BREEDTE-2.6*cm)/2, (BREEDTE-2.6*cm)/2]))
    story.append(Spacer(1, 0.15*cm))
    story.append(info_box(s, "De beslisboom",
        ["Compleet nieuwe Windows-pc, suite staat er nog niet op? -> Beheer_install.bat draaien "
         "(staat los, in de root van het uitgepakte ZIP/GitHub-geheel). Daarna pas heb je een Pi "
         "NAS Menu om in te klikken. Belangrijk: dit bestand opent aan het eind NIETS automatisch "
         "- het maakt alleen de snelkoppeling, jij opent die daarna zelf.",
         "Suite staat al op deze pc, alleen de Pi zelf moet (opnieuw) ingesteld/gerepareerd worden? "
         "-> Gewoon Pi Menu -> Installatie & Herstel. Beheer_install.bat hoeft er dan niet meer aan "
         "te pas te komen."]))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph(
        "<b>Starter Kit versus Installatie & Herstel - de relatie tussen deze twee</b>: dit zijn "
        "twee kanten van dezelfde medaille, geen overlappende functies. Starter Kit ZIP bouwen "
        "<i>verpakt</i> de suite - het doet zelf niets op een Pi of pc, het maakt alleen het lege, "
        "schone pakket. Installatie & Herstel <i>gebruikt</i> zo'n pakket (of een bestaande "
        "installatie) om daadwerkelijk stappen te doorlopen. Volgorde bij een nieuwe pc: eerst "
        "Starter Kit bouwen op de oude/bestaande installatie, het ZIP-bestand meenemen naar de "
        "nieuwe plek uitpakken, en daar pas Installatie & Herstel starten.", s["body"]))
    story.append(Spacer(1, 0.15*cm))
    story.append(info_box(s, "Python bijwerken",
        ["Installeert de nieuwste Python-versie naast je huidige installatie - handig als de "
         "suite een verouderde Python-versie signaleert. Node.js is sinds 6 augustus 2026 niet "
         "meer nodig (was alleen voor de oude, inmiddels vervangen Functieoverzicht-build).",
         "Wordt net als PuTTY/TigerVNC eerst gezocht in Installatie\\; ontbreekt het "
         "installatiebestand daar, dan wordt het gedownload."],
        kleur=ACCENT))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("3.6 Backup Beheer", s["h2"]))
    story.append(Paragraph(
        "Backup Beheer is de ene centrale plek voor alle backup-gerelateerde acties - "
        "eerder stonden deze verspreid over het hoofdmenu, PiNAS Sync en NAS Map Beheer. "
        "Bereikbaar via de knop 'Backup Beheer' in de BACKUP-sectie van het hoofdmenu.",
        s["body"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(data_tabel(s,
        ["Actie", "Wat doet het?"],
        [
            ["Synchronisatie", "Start PiNAS Sync voor het synchroniseren van bestanden (zie hoofdstuk 5)"],
            ["PC Image Backup", "Volledige kopie van schijf C: naar de Backup-schijf via wbAdmin - nu een eigen programma, los van PiNAS Sync"],
            ["iPhone Back-up", "Foto's, Downloads, Boeken, app-bestanden en (best effort) WhatsApp van een iPhone naar de Backup-schijf - iPhone moet aan de Pi hangen, niet aan de pc"],
            ["Archief Backup Bewaking", "Controle en veilige spiegeling van een vaste backup-relatie (Archief Backup op de Backup-schijf naar de Spiegel Backup op H:)"],
            ["Systeem-image maken (SD-kaart)", "Volledige, gecomprimeerde kopie van de actieve Pi SD-kaart naar de Backup-schijf (destructieve/zware actie, geel gemarkeerd)"],
            ["Backup-HDD controleren/herstellen", "Veilige bestandssysteemcontrole (e2fsck) op de backup-HDD via SSH (destructieve/zware actie, geel gemarkeerd)"],
            ["Rechten backup-HDD herstellen", "Zet alle bestanden/mappen op de backup-HDD terug naar gebruiker 'pi' (chown/chmod via SSH), zodat Verkenner nooit meer 'Toegang geweigerd' geeft - bijvoorbeeld bij oudere back-ups die als root zijn aangemaakt (destructieve/zware actie, geel gemarkeerd)"],
        ],
        [5*cm, BREEDTE - 5*cm]))
    story.append(Spacer(1, 0.2*cm))
    story.append(info_box(s, "Info",
        ["Elke knop doet precies een ding - er is bewust geen 'alles-in-1'-knop, "
         "zodat je nooit per ongeluk een zware actie (zoals een SD-kaart-image) "
         "naast een routine-synchronisatie start."],
        kleur=ACCENT))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("iPhone Back-up", s["h3"]))
    story.append(Paragraph(
        "<b>BELANGRIJK:</b> de iPhone moet aan een usb-poort VAN DE PI zelf hangen, niet aan "
        "deze Windows-pc - het onderliggende script draait op de Pi en heeft daar rechtstreeks "
        "usb-toegang voor nodig. Eerste keer: ontgrendel de iPhone en tik op 'Vertrouw deze "
        "computer' zodra dat gevraagd wordt.", s["body"]))
    story.append(Spacer(1, 0.15*cm))
    story.append(data_tabel(s,
        ["Onderdeel", "Status"],
        [
            ["Foto's en video's (camerarol)", "Altijd - gewone, leesbare bestanden"],
            ["Downloads en Boeken (Books)", "Altijd, indien aanwezig - de rest van de Media-koppeling "
             "naast de camerarol (11 augustus 2026: hiervóór werd dit stilzwijgend overgeslagen). "
             "Onbekende overige mappen onder Media komen mee in 'Overig'; de interne PhotoData-cache "
             "van de Foto's-app wordt bewust nooit meegenomen (geen gebruikersbestanden)."],
            ["'Op mijn iPhone' (lokale opslag Bestanden-app)", "Bekende beperking (10 augustus "
             "2026, met pinas_iphone_diagnose.sh uitgezocht): NIET mogelijk via deze methode - "
             "Apple's installatie-proxy behandelt de systeem-Bestanden-app niet als een gewone "
             "app met bestandsdeling aan, dus koppelen wordt geweigerd ('InstallationLookupFailed'). "
             "Geen bug in dit script, bevestigd met twee onafhankelijke tools. Foto's en Bestanden "
             "van andere apps zijn hier niet door geraakt."],
            ["Bestanden van andere apps met bestandsdeling", "Altijd - gewone, leesbare bestanden. "
             "Een vaste lijst apps waar Frans niets aan heeft (bijv. Spotify, DuckDuckGo) wordt "
             "automatisch overgeslagen - aan te passen in het script zelf (OVERSLAAN_APPS)."],
            ["WhatsApp-chats", "Best effort - via een tijdelijke volledige back-up + een los "
             "hulpprogramma dat er een leesbare HTML-export van maakt. Kan mislukken zonder de "
             "rest van de back-up te breken. (11 augustus 2026, oorzaak bevestigd via het "
             "logbestand op de Pi) Meest voorkomende oorzaak: de iPhone was VERGRENDELD op het "
             "moment dat deze stap draaide ('ErrorCode 208: Device locked' in het logbestand). "
             "idevicebackup2 heeft voor een volledige back-up het toestel ontgrendeld nodig - "
             "gaat het scherm tijdens de eerdere stappen (foto's/bestanden kopieren) op slot, dan "
             "stopt de WhatsApp-stap hiermee. Oplossen: houd de iPhone ontgrendeld zolang de "
             "back-up loopt, of zet tijdelijk de automatische vergrendeling uit (Instellingen > "
             "Beeldscherm en helderheid > Automatische vergrendeling), en draai de back-up "
             "opnieuw. Tweede, minder vaak voorkomende oorzaak: 'Codeer lokale back-up' staat aan "
             "op de iPhone, waardoor idevicebackup2 een back-upwachtwoord nodig heeft dat dit "
             "script niet heeft. Dit is een instelling van het toestel zelf, niet van dit script: "
             "sluit de iPhone aan op een Windows-pc met iTunes of de 'Apple Devices'-app, open het "
             "toestel, ga naar Back-ups, en vink 'Codeer lokale back-up' UIT (het huidige "
             "back-upwachtwoord is dan nodig - dit is NIET de Apple ID of de toestelcode). Is dat "
             "wachtwoord kwijt, dan is er geen manier om de instelling te verwijderen zonder het "
             "toestel te wissen."],
            ["Notities", "Bewust NIET meegenomen - Apple Notities synct standaard via iCloud, "
             "niet lokaal op het toestel, dus hier is geen leesbare kopie van te maken."],
        ],
        [5*cm, BREEDTE - 5*cm]))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph(
        "Komt op de Backup-schijf te staan in de map 'PiNAS iPhone Backup\\iPhone_&lt;datum&gt;\\', "
        "met submappen Fotos, Downloads, Boeken, Overig, 'Op mijn iPhone', Bestanden en WhatsApp "
        "(submappen die niets bevatten worden overgeslagen).", s["body"]))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("iPhone Doorbladeren", s["h3"]))
    story.append(Paragraph(
        "Geen back-up, maar de iPhone LIVE en ALLEEN-LEZEN zichtbaar maken in Verkenner - handig "
        "om gewoon even te kijken wat er op het toestel staat, zonder eerst een volledige back-up "
        "te draaien. Zelfde BELANGRIJK als hierboven: iPhone aan de Pi, niet aan de pc.", s["body"]))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph(
        "Zolang het venster open blijft, wordt de iPhone automatisch als schijfletter gekoppeld "
        "- net als Opslag en Backup - en opent Verkenner vanzelf zodra hij actief is, met de map "
        "Media (camerarol en meer). Geen inlogscherm nodig: dit gebruikt dezelfde inloggegevens "
        "die bij Installatie al zijn opgeslagen. Druk in het venster op ENTER om te stoppen - de "
        "schijfletter, de tijdelijke koppeling en het netwerkzicht worden dan meteen weer "
        "opgeruimd, er blijft niets achter.", s["body"]))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph(
        "Duurt het koppelen langer dan anderhalve minuut (bijv. omdat de iPhone eerst 'Vertrouw "
        "deze computer' moet bevestigen), dan probeert Windows het rechtstreekse pad alsnog te "
        "openen - vraagt dat om een wachtwoord, vul dan je NAS-wachtwoord in (hetzelfde als voor "
        "Opslag/Backup).", s["body"]))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph(
        "Er verschijnt ook een lege map 'Op mijn iPhone' naast Media - dat blijft leeg. Bekende "
        "beperking (10 augustus 2026, zie de iPhone Back-up-tabel hierboven voor de technische "
        "reden): geen bug, Media werkt gewoon door.", s["body"]))
    story.append(PageBreak())

    story.append(Paragraph("Archief Backup Bewaking", s["h3"]))
    story.append(Paragraph(
        "Bewaakt een vaste backup-relatie tussen een bronmap (de Archief Backup, standaard op de "
        "Backup-schijf) en de Spiegel Backup ervan (op H:). De bron is altijd leidend en wordt nooit aangeraakt; "
        "verwijderen gebeurt alleen aan de backup-kant. Werk altijd in twee stappen: eerst "
        "<b>Controleren</b> (alleen lezen, toont alleen de afwijkingen), daarna pas "
        "<b>Synchroniseren</b>. Bij het synchroniseren kies je uit drie modi:", s["body"]))
    story.append(Spacer(1, 0.15*cm))
    story.append(data_tabel(s,
        ["Sync-modus", "Wat het doet"],
        [
            ["Alleen aanvullen",        "Kopieert ontbrekende/gewijzigde bestanden naar H, verwijdert niets uit H (veiligst)"],
            ["Spiegel met quarantaine", "Kopieert naar H en verplaatst overtollige H-bestanden naar _ArchiefBackup_verwijderd (aanbevolen)"],
            ["Spiegel met verwijderen", "Kopieert naar H en verwijdert overtollige H-bestanden direct (extra bevestiging)"],
        ],
        [4.2*cm, BREEDTE - 4.2*cm]))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph(
        "Tijdens het werk toont de tool een meebewegende tijdschatting (\"~nog Xm\"). Elke "
        "controle sluit af met een <b>eindcontrole</b> die de totale grootte en het aantal "
        "bestanden van bron en backup naast elkaar zet, zodat ook onvolledig gekopieerde "
        "bestanden opvallen. Mislukte kopieen worden apart verzameld en onderaan getoond. "
        "Het thema volgt automatisch de rest van de suite.", s["body"]))
    story.append(PageBreak())

    story.append(Paragraph("3.7 Addons Beheer", s["h2"]))
    story.append(Paragraph(
        "Addons Beheer is de centrale plek voor de optionele add-ons op de Pi - elk los "
        "te installeren en te verwijderen. Bereikbaar via de knop 'Addons Beheer' in de "
        "ADDONS-sectie van het hoofdmenu.", s["body"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(data_tabel(s,
        ["Add-on", "Wat het is"],
        [
            ["Nextcloud",   "Eigen prive-cloud: bestanden, foto's, muziek en documenten - eigen alternatief voor Google Drive/iCloud."],
            ["Pi-hole",     "Advertentieblokkering en versleutelde DNS voor het hele netwerk."],
            ["ZeroTier",    "VPN - veilig bij de NAS komen van onderweg, zonder poorten open te zetten op de router."],
            ["Vaultwarden", "Eigen wachtwoordkluis (Bitwarden-compatibel). Gebruikt een eigen root-certificaat - zie 'Certificaat vertrouwen' hieronder."],
            ["Mobiele statuspagina", "Met wachtwoord beveiligde webpagina op de Pi zelf (poort 8090) met een mobielvriendelijk overzicht: diensten, hardware en schijfruimte. Thuis en, via ZeroTier, ook onderweg bereikbaar."],
            ["Printserver", "Maakt van de Pi een netwerk-printserver (CUPS + AirPrint): een USB-printer aan de Pi of een netwerkprinter wordt door alle apparaten te gebruiken. Thuis via AirPrint/IPP, onderweg via ZeroTier. Beheer via de webinterface op poort 631."],
            ["PiNAS Dashboard", "Met wachtwoord beveiligde webpagina op de Pi zelf (poort 8095) die het statusoverzicht en het addon-overzicht (installeren/openen) samenbrengt in 1 pagina. Thuis en, via ZeroTier, ook onderweg bereikbaar."],
        ],
        [3*cm, BREEDTE - 3*cm]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "Elke add-on heeft een 'Installeren' en 'Verwijderen'-knop, die het bijbehorende "
        "script op de Pi uitvoert via SSH in een eigen CMD-venster met live voortgang. De "
        "Printserver heeft daarnaast een 'Starten'-knop: staat de status op 'Geinstalleerd, "
        "maar gestopt' (bijvoorbeeld na een herstart van de Pi), dan zet deze knop de "
        "printserver weer aan zonder opnieuw te hoeven installeren. Vaultwarden heeft een "
        "'Certificaat vertrouwen'-knop: Vaultwarden maakt "
        "bij installatie een EIGEN ROOT-CERTIFICAAT aan (een kleine eigen "
        "'certificaatinstantie', alleen voor jouw Pi) - dit certificaat vertrouw je "
        "EENMALIG in Windows via deze knop, anders waarschuwt de browser bij elk bezoek. "
        "Het onderliggende servercertificaat wordt daarna automatisch elk jaar vernieuwd "
        "op de Pi zelf, zonder dat je ooit opnieuw hoeft te vertrouwen. Voor iPhone en "
        "Android download je hetzelfde root-certificaat via de mobiele statuspagina en "
        "vertrouw je het daar zelf eenmalig - zie paragraaf 3.9 hieronder. De mobiele "
        "statuspagina heeft daarnaast een 'Wachtwoord "
        "resetten'-knop: het toegangswachtwoord wordt bij installatie eenmalig getoond "
        "(schrijf het op) - ben je het toch kwijt, dan maakt deze knop een nieuw "
        "wachtwoord aan zonder de pagina opnieuw te hoeven installeren.", s["body"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "Printserver - een printer toevoegen: open na installeren "
        "http://[Pi IP]:631 en log in als gebruiker 'pi' met je Pi-wachtwoord. Ga naar "
        "Administration -> Add Printer. Een netwerkprinter verschijnt na even wachten "
        "onder 'Discovered Network Printers' - kies bij voorkeur de regel met "
        "'(driverless)' erbij (dit is IPP Everywhere, de moderne universele standaard). "
        "Klik Continue: het 'Connection'-veld staat dan al ingevuld en hoort met rust "
        "gelaten te worden. Krijg je toch een lege of duidelijk onjuiste waarde (een paar "
        "rare tekens in plaats van een adres), typ dan zelf het IP-adres van de printer "
        "in als <font face=\"Courier\">ipp://&lt;printer-IP&gt;/ipp/print</font> (het "
        "IP-adres van de printer zelf vind je in het menu van de printer of in de "
        "apparatenlijst van je router - dit is NIET het IP-adres van de Pi). Vul een naam "
        "in en vink 'Share This Printer' aan. Kies bij het merk/model-scherm bij voorkeur "
        "'Generic' -> 'IPP Everywhere' in plaats van een merkspecifiek stuurprogramma - "
        "dat werkt betrouwbaarder samen met AirPrint en hoeft niet exact het juiste "
        "printermodel te zijn.", s["body"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "Printen - thuis en onderweg: THUIS verschijnt de printer vanzelf in het "
        "print-menu van iPhone/iPad (AirPrint), Android (Mopria/IPP) en Windows/Mac. "
        "ONDERWEG (via ZeroTier) is de printserver zelf altijd bereikbaar - CUPS luistert "
        "op alle netwerkinterfaces en staat externe toegang toe, dus een netwerkprinter "
        "handmatig toevoegen op het ZeroTier-IP van de Pi werkt op Windows/Mac ook "
        "onderweg. Er wordt BEWUST geen poort naar internet opengezet; dat is veiliger.",
        s["body"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "Onderweg printen op iPhone/iPad ZONDER wifi - opzet in 3 stappen: dit is "
        "bevestigd werkend (27 juli 2026), mits deze drie dingen EENMALIG, VOORAF, "
        "THUIS zijn gedaan.<br/>"
        "<b>1. Een 2e wachtrij in CUPS.</b> Herhaal de stappen hierboven nog een keer "
        "voor DEZELFDE fysieke printer, met een naam die eindigt op '_onderweg' (bijv. "
        "Epson_ET8550_onderweg) - 1 naam met 2 adressen bleek niet betrouwbaar op iOS, "
        "vandaar 2 losse wachtrijen.<br/>"
        "<b>2. Het AirPrint-profiel installeren.</b> Op de mobiele statuspagina (add-on "
        "hierboven) staat bij 'Printserver' een downloadknop voor een AirPrint-profiel - "
        "dat wordt live opgebouwd uit de wachtrijen die echt in CUPS staan. Open de "
        "statuspagina rechtstreeks in Safari op het toestel zelf, tik op de knop, en "
        "installeer (Instellingen -> Profiel gedownload -> Installeren; de gele 'Niet "
        "geverifieerd'-waarschuwing is normaal bij een zelfgemaakt profiel).<br/>"
        "<b>3. De printer koppelen met Epson Smart Panel.</b> Installeer de gratis "
        "Epson Smart Panel-app en koppel de printer er EEN KEER mee (via Wi-Fi "
        "Direct/QR-code op het display van de printer, terwijl je gewoon thuis op wifi "
        "zit).", s["body"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(info_box(s, "Waarom stap 3 nodig is",
        ["Zonder de Smart Panel-koppeling bleek printen zonder wifi consequent te "
         "mislukken (\"Geen AirPrint-printers gevonden\"), ook met een verder correct "
         "profiel - de koppeling lijkt iets in iOS te \"ontgrendelen\". De precieze "
         "technische reden hiervoor is niet met zekerheid vastgesteld, alleen het "
         "herhaalde verband tussen wel/niet gekoppeld en wel/niet werkend printen. "
         "Voer stap 3 dus ook uit als je AirPrint-detectie eerder al leek te werken "
         "zonder deze koppeling."],
        kleur=ACCENT))
    story.append(Spacer(1, 0.2*cm))
    story.append(info_box(s, "Alternatief - Epson Connect",
        ["Werkt het onverhoopt toch niet, of wil je geen Smart Panel-koppeling maken: "
         "Epson Connect is Epson's eigen clouddienst, volledig los van de "
         "PiNAS-printserver/de Pi/ZeroTier - werkt via gewoon internet (ook mobiele "
         "data). Eenmalig activeren op de printer zelf voor een eigen, uniek "
         "e-mailadres. Email Print: mail een bijlage naar dat adres, de printer print "
         "'m vanzelf uit. Remote Print: in de Epson iPrint-app, tabblad 'Remote', "
         "document kiezen en op Print tikken."],
        kleur=WARN_C))
    story.append(Spacer(1, 0.2*cm))
    story.append(info_box(s, "Als de Smart Panel-koppeling opnieuw moet (nieuwe telefoon, printer-reset)",
        ["1. Installeer Epson Smart Panel op het nieuwe toestel.<br/>"
         "2. Op de printer zelf: het scherm 'Smartphone verbinden' (soms onder een "
         "instellingen-/verbindingsmenu) toont een QR-code.<br/>"
         "3. Scan die QR-code met de standaard Camera-app (iOS 11+) - dit koppelt via "
         "Wi-Fi Direct, terwijl je toestel gewoon op je eigen wifi verbonden blijft.<br/>"
         "4. Doe dit THUIS, met wifi aan, voordat je voor het eerst onderweg zonder "
         "wifi probeert te printen.<br/>"
         "Nodig na: een nieuwe telefoon, een fabrieksreset van de printer, of het "
         "verwijderen/opnieuw installeren van Smart Panel."],
        kleur=ACCENT))
    story.append(Spacer(1, 0.2*cm))
    story.append(info_box(s, "Let op voor toekomstige add-ons",
        ["De '_onderweg'-naamgeving (2 losse CUPS-wachtrijen voor dezelfde printer) is "
         "een printer/iOS-specifieke workaround, geen algemeen suite-patroon. Krijgt een "
         "andere add-on ooit een vergelijkbare 'thuis vs. onderweg'-behoefte, kopieer dit "
         "patroon dan niet automatisch - controleer eerst of het onderliggende probleem "
         "echt hetzelfde is."],
        kleur=WARN_C))
    story.append(Spacer(1, 0.2*cm))
    story.append(info_box(s, "Info",
        ["Status en links naar actieve add-ons (bijv. de Nextcloud- of Vaultwarden-URL) "
         "staan ook in Status & details → Snelle links. Een add-on die niet is "
         "geinstalleerd, toont daar 'n.v.t.' in plaats van een link."],
        kleur=ACCENT))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("3.8 Vaultwarden op iPhone en Android", s["h2"]))
    story.append(Paragraph(
        "Op de telefoon gebruik je de Bitwarden-app (App Store / Play Store) - er bestaat "
        "GEEN losse 'Bitwarden-extensie' voor Chrome op mobiel; dat ondersteunt geen enkele "
        "mobiele browser. De Bitwarden-app regelt het invullen wel automatisch in elke "
        "browser (ook Chrome) via de systeem-AutoFill-functie van de telefoon.", s["body"]))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph("<b>iPhone:</b>", s["body"]))
    story.append(Paragraph(
        "1. Download het root-certificaat via de mobiele statuspagina "
        "(http://&lt;ip-van-de-pi&gt;:8090) op je iPhone.<br/>"
        "2. Instellingen → Algemeen → VPN en apparaatbeheer → tik op het gedownloade "
        "profiel → Installeren.<br/>"
        "3. Instellingen → Algemeen → Info → Certificaatvertrouwen-instellingen → zet het "
        "nieuwe root-certificaat aan.<br/>"
        "4. Installeer de Bitwarden-app en log in via 'Zelf-hostend' met je server-URL.<br/>"
        "5. Instellingen (van iOS) → Algemeen → AutoFill en wachtwoorden → zet Bitwarden "
        "aan naast de Sleutelhanger. Vanaf nu biedt elke browser, ook Chrome, Bitwarden aan "
        "boven het toetsenbord bij een wachtwoordveld.", s["body"]))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph("<b>Android:</b>", s["body"]))
    story.append(Paragraph(
        "1. Download het root-certificaat via de mobiele statuspagina.<br/>"
        "2. Instellingen → Beveiliging → Versleuteling en inloggegevens → Certificaat "
        "installeren → CA-certificaat → kies het gedownloade bestand (de waarschuwing over "
        "gemonitord netwerkverkeer is normaal bij een zelf toegevoegd certificaat).<br/>"
        "3. Installeer de Bitwarden-app en log in via 'Zelf-hostend'.<br/>"
        "4. Instellingen → Wachtwoorden (of Systeem → Talen en invoer → Autofill-service) → "
        "kies Bitwarden als autofill-dienst.", s["body"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(info_box(s, "Info",
        ["Het root-certificaat vertrouw je maar EENMALIG per apparaat - het "
         "servercertificaat wordt daarna automatisch elk jaar vernieuwd zonder dat dit "
         "opnieuw hoeft."],
        kleur=ACCENT))
    story.append(Spacer(1, 0.3*cm))

    # 10 augustus 2026 (Frans: Bitwarden-extensie bleef eeuwig laden, geen
    # autofill meer, "heel internet staat vol met dit probleem in relatie
    # tot vaultwarden" - bewust GEEN nieuw genummerd 3.X-hoofdstuk, zelfde
    # reden als bij "De 4 stappen van pi_nas_setup.pyw in detail" hierboven:
    # niet de hele keten hoeven omnummeren.
    story.append(Paragraph(
        "Vaultwarden-extensie blijft eeuwig laden / geen automatisch invullen (opgelost)",
        s["h3"]))
    story.append(Paragraph(
        "Symptoom: de Bitwarden-browserextensie opent wel, maar de kluis blijft eindeloos "
        "laden en er wordt nergens een wachtwoord aangeboden - terwijl de webkluis "
        "(https://&lt;ip-van-de-pi&gt;:8443, gewoon in de browser) de kluis prima laat zien. "
        "Dat laatste is de sleutel: als de webkluis wel werkt, ligt de oorzaak niet bij de "
        "server (certificaat, container, netwerk), maar bij de client.", s["body"]))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph(
        "Oorzaak: de Bitwarden-browserextensie werkt zichzelf via de Chrome Web Store "
        "voortdurend automatisch bij, maar Vaultwarden zelf werd tot voor kort alleen "
        "bijgewerkt bij een nieuwe installatie. Draait Vaultwarden een tijdje, dan ontstaat "
        "een steeds groter gat tussen een oude server-versie en een nieuwe extensie-versie - "
        "dit geeft een decodeerfout in de extensie (zichtbaar in de browserconsole als een "
        "WASM-foutmelding) zodra die de kluisgegevens probeert te verwerken.", s["body"]))
    story.append(Spacer(1, 0.15*cm))
    story.append(info_box(s, "Blijvend opgelost sinds 10 augustus 2026",
        ["pinas_vaultwarden.sh haalt bij elke (her)installatie nu eerst automatisch de "
         "nieuwste Vaultwarden-versie op (docker pull), voordat de container start. Een "
         "verouderde server-versie kan dus niet meer sluipenderwijs ontstaan.",
         "Kom je dit tegen op een oudere installatie: Addons Beheer → Vaultwarden → "
         "nogmaals op 'Installeren' klikken. Dat haalt de nieuwste versie op en herstart "
         "de container - je kluisgegevens blijven volledig staan.",
         "Werkt de extensie daarna nog niet meteen: volledig UITLOGGEN in de extensie "
         "(Instellingen → Uitloggen, niet alleen vergrendelen) en opnieuw inloggen dwingt "
         "een verse download van de kluis af."],
        kleur=ACCENT))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("3.9 Pi NAS herstarten", s["h2"]))
    story.append(Paragraph(
        "Onder Geavanceerd zit ook <b>Pi NAS herstarten</b>: herstart de Pi met 'sudo reboot' "
        "via SSH, na een bevestigingsvraag. De verbinding (Opslag, Backup, Nextcloud, FileBrowser) valt "
        "kort weg zodra de Pi herstart - dat is normaal en geen fout. Na ongeveer 30-60 seconden "
        "is de Pi weer bereikbaar; klik dan eventueel op 'Nu controleren' in het hoofdvenster.", s["body"]))
    story.append(PageBreak())

    story.append(Paragraph("4. Controles", s["h1"]))
    story.append(HRFlowable(width=BREEDTE, thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "Controles is de centrale plek voor alles wat de suite controleert en test - "
        "bereikbaar via de knop 'Controles' onder BEHEER op het hoofdmenu. Vier "
        "onderdelen:", s["body"]))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("4.1 Structuurcheck & Opruimen", s["h2"]))
    story.append(Paragraph(
        "Opent NAS_Map_Beheer.pyw met twee tabs. Structuurcheck controleert of alle "
        "verwachte bestanden aanwezig zijn in de suite-mappenstructuur — groen = OK, "
        "rood = ontbreekt. Opruimen toont verouderde en onnodige bestanden met "
        "checkboxes — verwijder in één klik.", s["body"]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("4.2 Suite testen", s["h2"]))
    story.append(Paragraph(
        "Draait test_suite.py: een reeks kwaliteitschecks over bestanden, syntax, "
        "packages, schijven en Pi services, met een duidelijke geslaagd/mislukt-uitkomst "
        "per check.", s["body"]))
    story.append(PageBreak())

    story.append(Paragraph("4.3 Diagnose uitvoeren", s["h2"]))
    story.append(Paragraph(
        "Opent een venster met twee opties:", s["body"]))
    story.append(data_tabel(s,
        ["Optie", "Wat wordt gecontroleerd?"],
        [
            ["PC diagnose",      "PuTTY, TigerVNC, PiNAS Sync, Opslag/Backup-schijven, wachtwoord in Credential Manager"],
            ["Pi diagnose (SSH)", "Alle services, schijfmounts, fstab, scripts, Nextcloud, Samba shares — via SSH"],
        ],
        [4*cm, BREEDTE - 4*cm]))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("4.4 Log Bestanden Bekijken", s["h2"]))
    story.append(Paragraph(
        "Overzicht van alle logbestanden (Pi NAS Menu, PiNAS Sync, Externe HDD). Klik 'Open' "
        "naast een log om het in Kladblok te openen. Logmap: C:\\PiNAS\\Logs\\. Logs worden "
        "automatisch verwijderd na 30 dagen.", s["body"]))
    story.append(PageBreak())

    story.append(Paragraph("4.5 Systeem-image terugzetten (SD-kaart)", s["h2"]))
    story.append(Paragraph(
        "Het <b>maken</b> van een systeem-image gebeurt via Backup Beheer "
        "(zie 3.6), niet in Controles. Dit hoofdstuk beschrijft het terugzetten, wat "
        "onafhankelijk is van waar de image gemaakt is.", s["body"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "Backup Beheer maakt een volledige, gecomprimeerde kopie van de actieve Pi SD-kaart "
        "(dd + gzip) terwijl de Pi gewoon doorwerkt, en zet die op de backup-HDD onder:", s["body"]))
    story.append(Spacer(1, 0.1*cm))
    story.append(Paragraph("[Backup-schijf]:\\PiNAS\\pinas_sd_&lt;datum&gt;.img.gz", s["code"]))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph(
        "Dit draait via SSH in een eigen CMD-venster met live voortgang, zodat het venster open kan "
        "blijven staan tijdens de tientallen minuten die het kan duren. De externe HDD (Backup-schijf) moet "
        "aanstaan. Er is bewust <b>geen knop voor terugzetten</b>: dat kan niet veilig gebeuren "
        "vanaf de kaart die op dat moment actief draait. Terugzetten doe je handmatig, zoals hieronder "
        "beschreven.", s["body"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(info_box(s, "Belangrijk om te weten",
        ["Dit zet de image terug op DEZELFDE SD-kaart die nu in de Pi zit - er is geen "
         "tweede kaart nodig. Je haalt de kaart tijdelijk uit de Pi, schrijft 'm via een "
         "andere Windows- of Linux-pc, en stopt 'm daarna terug in dezelfde Pi.",
         "De Pi is tijdens het hele terugzet-proces uit en offline (Samba, Nextcloud, "
         "FileBrowser onbereikbaar) - dat is normaal en geen storing.",
         "Terugzetten overschrijft de kaart volledig naar de staat van het moment waarop "
         "de image gemaakt is. Wijzigingen op de kaart zelf van daarna gaan verloren. Je "
         "bestanden (documenten, muziek, Nextcloud-data) staan apart op de externe SSD "
         "(Opslag) en externe HDD (Backup) en worden hier niet door geraakt."]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "<b>Stap 0 - Pi veilig uitzetten (op beide routes hieronder van toepassing):</b> "
        "gebruik Onderhoud → Geavanceerd → Pi NAS herstarten, of via SSH "
        "'sudo poweroff'. Wacht tot de groene lampjes van de Pi stil staan (geen "
        "schijfactiviteit meer) voordat je de stroom loskoppelt en de kaart eruit haalt - "
        "een kaart eruit trekken terwijl de Pi nog actief schrijft kan het bestandssysteem "
        "beschadigen.", s["body"]))
    story.append(Spacer(1, 0.25*cm))

    story.append(Paragraph("Terugzetten - Windows (Win32DiskImager)", s["h3"]))
    story.append(data_tabel(s,
        ["Stap", "Actie"],
        [
            ["1", "Kopieer het .img.gz bestand van de Backup-schijf (\\PiNAS\\) naar de Windows-pc."],
            ["2", "Pak het uit met 7-Zip tot een .img bestand (gzip uitpakken)."],
            ["3", "Download en start Win32 Disk Imager."],
            ["4", "Kies het uitgepakte .img bestand en dezelfde SD-kaart die uit de Pi kwam (let op de juiste schijfletter)."],
            ["5", "Klik op 'Write' en wacht tot het klaar is - de kaart is daarna weer exact zoals op het moment van de image."],
        ],
        [1.3*cm, BREEDTE - 1.3*cm]))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("Terugzetten - Linux / Zorin (dd)", s["h3"]))
    story.append(data_tabel(s,
        ["Stap", "Actie"],
        [
            ["1", "Kopieer of open het .img.gz bestand vanaf de Backup-schijf (\\PiNAS\\) op de Linux-pc."],
            ["2", "Zoek het apparaat van DEZELFDE SD-kaart (die uit de Pi kwam) op met 'lsblk' (bijv. /dev/sdX) - controleer dit zorgvuldig."],
            ["3", "Zet de image terug met: gunzip -c pinas_sd_&lt;datum&gt;.img.gz | sudo dd of=/dev/sdX bs=4M status=progress"],
            ["4", "Wacht tot dd klaar is en voer 'sync' uit voordat je de kaart verwijdert."],
        ],
        [1.3*cm, BREEDTE - 1.3*cm]))
    story.append(Spacer(1, 0.15*cm))
    story.append(info_box(s, "Let op",
        ["Controleer het schijf-apparaat (/dev/sdX) altijd dubbel voordat je dd uitvoert - "
         "een verkeerde keuze overschrijft de verkeerde schijf zonder waarschuwing. Dit "
         "hoort de SD-kaart te zijn, nooit je eigen Linux-systeemschijf."]))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph(
        "Stop na het terugzetten de kaart weer in dezelfde Pi en zet 'm aan - de suite "
        "draait dan weer precies zoals op het moment dat de image gemaakt is.", s["body"]))
    story.append(PageBreak())

    story.append(Paragraph("5. PiNAS Sync (Synchronisatie)", s["h1"]))
    story.append(HRFlowable(width=BREEDTE, thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "PiNAS Sync is het synchronisatieprogramma van de Pi NAS Suite. Het is de "
        "Tkinter-opvolger van het oude PiBackup (Kivy) en van een eerdere, losse sync-tool die nog "
        "specifiek voor het oude NAS-apparaat was gebouwd. "
        "Bron en doel zijn nu volledig vrij te kiezen: lokale mappen, Windows-schijven, "
        "netwerkpaden (UNC) zoals een Zorin-share of andere netwerk-NAS, en de Pi-koppelingen Opslag en Backup. "
        "Het programma heeft twee schermen: bron/doel kiezen en synchroniseren. PC Image "
        "Backup is inmiddels een eigen programma, zie hoofdstuk 6.",
        s["body"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(IllustratieBackupFlow(BREEDTE, 3.5*cm))
    story.append(Spacer(1, 0.4*cm))

    story.append(info_box(s, "Starten",
        [r"Dubbelklik C:\PiNAS\Sync\pinas_sync_app.pyw, of start via Backup Beheer "
         "(knop 'Synchronisatie') in het hoofdmenu.",
         "Vereist Python 3 met Tkinter. Geen externe pakketten meer nodig "
         "(geen Kivy, smbprotocol of paramiko)."],
        kleur=OK_C))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("5.1 Scherm 1 - Bronnen en doelen kiezen", s["h2"]))
    story.append(Paragraph(
        "Links staat een uitklapbare boom met alle Windows-schijven en eventueel toegevoegde "
        "netwerkpaden. Klik op het driehoekje om een map uit te klappen; klik elders op de regel "
        "om een map of bestand aan of uit te vinken. Meerdere bronnen tegelijk kan - mappen, "
        "bestanden, schijven en netwerkpaden werken allemaal hetzelfde.", s["body"]))
    story.append(Spacer(1, 0.2*cm))
    story.extend(screenshot_flowable(
        "pinas_sync_scherm1.png",
        "Scherm 1 - Bronnen en doelen kiezen: links de boom met schijven en "
        "netwerkpaden, rechts de doelbasis en de bron/doel-koppelingen.", s))
    story.append(Spacer(1, 0.2*cm))
    story.append(data_tabel(s,
        ["Onderdeel", "Werking"],
        [
            ["+ Netwerkpad", "Voeg een UNC-share toe (bijv. een Zorin-share of andere netwerk-NAS). Wordt onthouden."],
            ["Doelbasis", "Vul een keer een basismap in (bijv. Backup-schijf:\\Backup). Elke aangevinkte bron krijgt automatisch een eigen submap."],
            ["Toepassen op alle bronnen", "Werkt ook al-aangevinkte rijen bij met de ingestelde doelbasis."],
        ],
        [4.5*cm, BREEDTE - 4.5*cm]))
    story.append(Spacer(1, 0.2*cm))
    story.append(info_box(s, "Veiligheidscontroles",
        ["Een doel dat gelijk is aan of binnen de bron ligt wordt hard geblokkeerd (zou corrupte resultaten geven).",
         "Een doel dat exact een schijf-root is (geen eigen submap) geeft een waarschuwing, met de keuze om toch door te gaan."],
        kleur=WARN_C))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("5.2 Scherm 2 - Synchroniseren", s["h2"]))
    story.append(Paragraph(
        "Bovenin staan gekleurde bolletjes voor elke bron en elk doel uit scherm 1 (het aantal past "
        "zich automatisch aan). Groen = bereikbaar, rood = niet. De status wordt periodiek gecontroleerd "
        "en alleen gelogd bij een verandering.", s["body"]))
    story.append(Spacer(1, 0.2*cm))
    story.extend(screenshot_flowable(
        "pinas_sync_scherm2.png",
        "Scherm 2 - Synchroniseren: statusbalk met bron/doel-bolletjes, "
        "reparatieknoppen, inventarisatie en het live activiteitenlog.", s))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph("Reparatieknoppenbalk", s["h3"]))
    story.append(data_tabel(s,
        ["Knop", "Werking"],
        [
            ["Verbinding testen", "Test alle doel-schijven."],
            ["HDD uit/aan (volledige cyclus)", "Zet de externe schijf via de smart plug volledig uit en weer aan, met stabilisatietijd."],
            ["LanManFix uitvoeren", "Lost Windows-netwerkfouten op (Systeemfout 67/5-achtig)."],
            ["Backup-schijf opnieuw koppelen", "Vervangt een vastgelopen SMB-verbinding door een verse."],
        ],
        [5*cm, BREEDTE - 5*cm]))
    story.append(Spacer(1, 0.2*cm))
    story.append(info_box(s, "Zelfherstel en echte sync",
        ["Bij 6 fouten op rij of een proactieve controle elke 200 bestanden pauzeert de sync en wordt automatisch herstel aangeboden (HDD-cyclus, dan LanManFix).",
         "'Tellen overslaan, direct starten' begint zonder vooraf te tellen - handig bij grote volumes.",
         "Echte sync (optioneel, standaard UIT): verwijdert na het aanvullen ook wees-bestanden en lege mappen in het doel, met bevestiging vooraf. Dit is onomkeerbaar."],
        kleur=ACCENT2))
    story.append(Spacer(1, 0.3*cm))

    story.append(PageBreak())

    story.append(Paragraph("6. PC Image Backup", s["h1"]))
    story.append(HRFlowable(width=BREEDTE, thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "PC Image Backup is een eigen programma geworden, los van PiNAS Sync - bereikbaar "
        "via Backup Beheer (zie 3.6). Het maakt een volledige kopie van schijf C: inclusief de EFI-partitie, via Windows' eigen "
        "wbAdmin. Dit is GEEN System Restore-herstelpunt maar de hele schijf, terug te zetten via de "
        "Windows-herstelomgeving onder 'Systeemkopie herstellen' (System Image Recovery) - een ander "
        "menu-item dan 'Systeemherstel'.", s["body"]))
    story.append(Spacer(1, 0.2*cm))
    story.extend(screenshot_flowable(
        "pinas_sync_scherm3.png",
        "PC Image Backup: het oranje voorbereidingspaneel (herstel-USB "
        "+ noodkaartje), de doelmap en de vereisten-controle.", s))
    story.append(Spacer(1, 0.2*cm))
    story.append(info_box(s, "Locatie",
        [r"[Backup-schijf]:\Windows-Systeemherstel-<PC>\WindowsImageBackup",
         "Een volledige backup duurt 1-3 uur, afhankelijk van schijfgrootte en netwerksnelheid."],
        kleur=ACCENT2))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Voorbereiding (eenmalig, voordat er iets misgaat)", s["h3"]))
    story.append(data_tabel(s,
        ["Actie", "Werking"],
        [
            ["Herstelschijf + noodkaartje", "Open zelf de Windows-wizard (Start, typ 'herstelschijf'). Het programma zet daarna een noodkaartje op de stick met netwerkpad en gebruikersnaam (geen wachtwoord)."],
            ["Alleen noodkaartje opslaan", "Als de stick al bestaat en je alleen het kaartje wilt bijwerken."],
            ["Structuur herstelschijf controleren", "Best-effort check op bootbestanden (bootmgr, EFI, Boot, Sources). Geen garantie op bootbaarheid - test dit een keer echt."],
        ],
        [5.5*cm, BREEDTE - 5.5*cm]))
    story.append(Spacer(1, 0.2*cm))
    story.append(info_box(s, "Waarom dit nodig is",
        ["Als de PC zelf niet meer opstart, heb je een apart, vooraf gemaakt bootbaar medium nodig om bij de herstelomgeving te komen. Dat kun je niet meer maken als de PC al kapot is."],
        kleur=WARN_C))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Vereisten en starten", s["h3"]))
    story.append(data_tabel(s,
        ["Vereiste", "Detail"],
        [
            ["Windows-versie", "Pro of Enterprise (niet Home) - wbAdmin moet aanwezig zijn"],
            ["Doelmap", "Een schijfletter of netwerkpad; wordt automatisch omgezet naar UNC voor de elevated actie"],
            ["Vrije ruimte", "Voldoende ruimte voor de volledige C:-kopie"],
            ["Schaduwkopie-station", "Automatisch bepaald; handmatig in te stellen als er geen plek wordt gevonden"],
        ],
        [4.5*cm, BREEDTE - 4.5*cm]))
    story.append(Spacer(1, 0.2*cm))
    story.append(info_box(s, "Schijfletters en elevatie",
        ["Start via de oranje knop 'als Administrator' - dan blijft de UAC-vraag beperkt tot deze ene actie en blijven je Opslag-/Backup-koppelingen intact.",
         "Een gekoppelde letter (zoals bij Backup) bestaat niet in een elevated sessie. Het programma zet daarom elke letter automatisch om naar het echte netwerkpad voordat er iets elevated draait."],
        kleur=OK_C))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Controleren en terugzetten", s["h3"]))
    story.append(Paragraph(
        "Na afloop verifieert het script zichzelf met 'wbadmin get versions' (naar een logbestand) en "
        "schrijft het HERSTELLEN-LEES-DIT.txt in de backupmap met de volledige terugzet-instructie. De "
        "knop 'Controleer of er een geldige backup bestaat' draait dezelfde leesopdracht handmatig.", s["body"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(data_tabel(s,
        ["Stap", "Actie (terugzetten)"],
        [
            ["1", "PC start nog op: Instellingen > Systeem > Herstel > Geavanceerd opnieuw opstarten"],
            ["2", "Problemen oplossen > Geavanceerde opties > Systeemkopie herstellen"],
            ["3", "PC start NIET op: boot vanaf de herstel-USB, kies 'Een systeemkopie zoeken op het netwerk'"],
            ["4", "Typ het netwerkpad van het noodkaartje, log in met de genoemde gebruiker + apart bewaard wachtwoord"],
            ["5", "Volg de wizard - Windows herstart automatisch zodra het klaar is"],
        ],
        [1.5*cm, BREEDTE - 1.5*cm]))
    story.append(PageBreak())

    story.append(Paragraph("7. NAS Wachtwoord beheren", s["h1"]))
    story.append(HRFlowable(width=BREEDTE, thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "Het NAS wachtwoord is het Samba wachtwoord van gebruiker <b>pi</b> op de Pi. "
        "Dit wachtwoord gebruik je voor de netwerkschijven (Opslag en Backup) en SSH.", s["body"]))
    story.append(Spacer(1, 0.3*cm))
    story.append(info_box(s, "Belangrijk",
        ["Wijzig het wachtwoord ALTIJD via Onderhoud → Beveiliging → NAS wachtwoord.",
         "Dit past zowel de Pi (Samba) als Windows (Credential Manager) tegelijk aan.",
         "Als je het wachtwoord handmatig wijzigt via SSH, vergeet dan niet het ook in het menu bij te werken."],
        kleur=WARN_C))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Wachtwoord vergeten of niet meer synchroon?", s["h3"]))
    for stap in [
        "Maak verbinding via SSH: <b>ssh pi@[Pi IP-adres]</b>",
        "Reset Samba wachtwoord: <b>echo -e \"wachtwoord\\nwachtwoord\" | sudo smbpasswd -s pi</b>",
        "Stel hetzelfde wachtwoord in via Onderhoud → Beveiliging → NAS wachtwoord",
        "Test met: <b>net use [gekozen letter]: \\\\[Pi IP]\\PiNas /user:pi wachtwoord</b>",
    ]:
        story.append(Paragraph(f"+ {stap}", s["bullet"]))
    story.append(PageBreak())

    story.append(Paragraph("8. Veelvoorkomende problemen", s["h1"]))
    story.append(HRFlowable(width=BREEDTE, thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 0.3*cm))

    problemen = [
        (
            "HDD-status toont 'UIT' terwijl de schijf/plug echt aanstaat",
            ERR_C,
            [
                "MEEST VOORKOMENDE OORZAAK: het IP-adres van de smart plug "
                "(Hue/Tapo) of van de Pi zelf is via DHCP gewijzigd — een ander "
                "apparaat op je netwerk kreeg het oude IP toegewezen.",
                "Herkenning: foutmelding 'Connection refused' in /home/pi/logs/smart_plug.log, "
                "of de status klopt structureel niet meer met de werkelijkheid.",
                "Oplossing — eenmalig, voorkomt herhaling: stel in je router een vaste "
                "IP-reservering in (DHCP Reservation) voor het MAC-adres van de smart "
                "plug/bridge én van de Pi. Werk daarna bridge_ip in "
                "smart_plug_config.json op de Pi bij naar het vaste IP.",
                "Diagnose: draai 'python3 /home/pi/hue_diagnose.py' op de Pi — toont alle "
                "Hue-apparaten met hun werkelijke status, zodat een verkeerd IP of plug_id "
                "direct opvalt in plaats van pas na lang zoeken.",
            ]
        ),
        (
            "Opslag of Backup verdwenen (bijv. na de HDD uit/aan te zetten)",
            WARN_C,
            [
                "Oorzaak: de netwerkkoppeling naar de Pi is verbroken toen de share even wegviel.",
                "Oplossing 1 (bijna altijd genoeg): klik in het hoofdmenu op 'Schijven verbinden' "
                "(of op de blauwe balk die verschijnt als een schijf mist). Dat koppelt de "
                "netwerkschijven schoon opnieuw met het opgeslagen wachtwoord; ze zijn daarna "
                "direct zichtbaar in Verkenner.",
                "Oplossing 2 (zeldzaam, bij 'Toegang geweigerd' of Systeemfout 5): gebruik "
                "LanMan-fix onder Onderhoud → Geavanceerd. Die past Windows-registerinstellingen aan; "
                "alleen nodig als Windows de verbinding helemaal weigert.",
                "Handmatig testen kan via CMD: net use [Backup-letter]: \\\\[Pi IP]\\Backup /user:pi",
                "Als fout 86 (onjuist wachtwoord): reset Samba wachtwoord via SSH en stel opnieuw in via Onderhoud → Beveiliging.",
            ]
        ),
        (
            "Pi niet bereikbaar (rood bolletje)",
            ERR_C,
            [
                "Controleer: staat de Pi aan?",
                "Controleer: zit de Pi op hetzelfde netwerk?",
                "Test via PowerShell: ping [Pi IP-adres]",
                "Als de Pi reageert op ping maar het menu zegt 'niet bereikbaar': wacht 15 sec — het menu herprobeert automatisch.",
            ]
        ),
        (
            "TigerVNC verbinding mislukt",
            WARN_C,
            [
                "VNC server loopt soms niet meer na een herstart van de Pi.",
                "Oplossing via SSH: vncserver -kill :1 → daarna: vncserver :1 -geometry 1920x1080 -depth 24 -localhost no",
            ]
        ),
        (
            "Externe HDD niet gemount na aanzetten",
            WARN_C,
            [
                "Wacht 20-30 seconden — de HDD heeft tijd nodig om op te starten.",
                "Het menu wacht automatisch 18 sec en probeert dan de Backup-schijf te koppelen.",
                "Als de Backup-schijf dan nog leeg is: controleer de Pi via SSH: ls /mnt/backup",
                "Als de map leeg is: sudo mount -a op de Pi uitvoeren.",
            ]
        ),
        (
            "PuTTY geen toegang tot de Pi",
            WARN_C,
            [
                "SSH sleutel mogelijk niet meer geldig of verkeerd pad.",
                "Oplossing: Onderhoud → Windows onderdelen → PuTTY + SSH sleutel opnieuw instellen.",
            ]
        ),
        (
            "Externe HDD svc onbekend of niet actief",
            WARN_C,
            [
                "De webservice voor de externe HDD draait niet op de Pi.",
                "Oplossing via SSH: sudo systemctl restart seagate-web",
                "Of via Pi NAS Menu: Onderhoud → Pi services → Externe HDD svc herstarten.",
            ]
        ),
        (
            "Pi server niet geconfigureerd na nieuwe SD-kaart",
            WARN_C,
            [
                "Doorloop de Setup wizard: Installatie & Herstel → Stap 0 (SD-kaart) → Stap 1 (Pi Server).",
                "De wizard begeleidt je stap voor stap van lege SD-kaart tot werkende NAS.",
            ]
        ),
        (
            "Systeemfout 86 — onjuist netwerkwachtwoord",
            ERR_C,
            [
                "Het Samba wachtwoord op de Pi en Windows Credential Manager zijn niet synchroon.",
                "Oplossing: zie hoofdstuk 7 — NAS Wachtwoord beheren.",
            ]
        ),
    ]

    for titel, kleur, stappen in problemen:
        story.append(KeepTogether([
            info_box(s, titel, stappen, kleur=kleur),
            Spacer(1, 0.3*cm),
        ]))

    story.append(PageBreak())

    story.append(Paragraph("9. Technische informatie", s["h1"]))
    story.append(HRFlowable(width=BREEDTE, thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Software componenten", s["h2"]))
    story.append(data_tabel(s,
        ["Component", "Details"],
        [
            ["Pi NAS Menu",       f"Python + Tkinter · Laatst bijgewerkt {DATUM}"],
            ["PiNAS Sync",        "Python 3 + Tkinter (standaardbibliotheek)"],
            ["Pi NAS Server",     "Raspberry Pi OS Lite 64-bit"],
            ["Samba",             "Windows bestandsshares (SMB)"],
            ["Nextcloud",         "Persoonlijke cloud via browser"],
            ["FileBrowser",       "Bestandsbeheer via browser (poort 8080)"],
            ["Cockpit",           "Systeembeheer via browser (poort 9090)"],
            ["Externe HDD svc",   "Seagate webservice op poort 8765"],
        ],
        [4*cm, BREEDTE - 4*cm]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Schijven en paden", s["h2"]))
    story.append(data_tabel(s,
        ["Schijf", "Naam", "Mountpunt Pi", "Grootte", "Gebruik"],
        [
            ["Opslag", "PiNas (SSD)",    "/mnt/opslag",  "~220 GB", "Snelle opslag, Nextcloud"],
            ["Backup", "Backup (HDD)",   "/mnt/backup",  "7.3 TB",  "Grote backups, PC Images"],
        ],
        [1.5*cm, 3.5*cm, 4*cm, 2.5*cm, BREEDTE - 11.5*cm]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Bestandslocaties Windows", s["h2"]))
    story.append(data_tabel(s,
        ["Bestand / Map", "Locatie"],
        [
            ["Pi NAS Menu",          r"C:\PiNAS\Beheer\Pi_NAS_Menu.pyw"],
            ["Backup Beheer",        r"C:\PiNAS\Beheer\pinas_backup_beheer.pyw"],
            ["PC Image Backup",      r"C:\PiNAS\Beheer\pinas_image_backup.pyw"],
            ["PiNAS Sync",           r"C:\PiNAS\Sync\pinas_sync_app.pyw"],
            ["Archief Backup Bewaking",    r"C:\PiNAS\ArchiefBackup\archief_backup_bewaking.pyw"],
            ["NAS Map Beheer",       r"C:\PiNAS\Beheer\NAS_Map_Beheer.pyw"],
            ["Suite Handleiding",    r"C:\PiNAS\Publicatie\PiNAS_Suite_Handleiding.pdf"],
            ["Gedeelde modules",     r"C:\PiNAS\Gedeeld\\"],
            ["Conventies (lees dit eerst)", r"C:\PiNAS\Gedeeld\CONVENTIES.md"],
            ["Logbestanden",         r"C:\PiNAS\Logs\\"],
            ["Logmap suite",         r"C:\PiNAS\Logs\\"],
            ["Sync-logs",            r"C:\PiNAS\Logs\pinas_sync_*.log"],
            ["PC Image locatie",     r"[Backup-schijf]:\Windows-Systeemherstel-<PC>\WindowsImageBackup\\"],
            ["Starter Kit output",   r"C:\PiNAS\Publicatie\StarterKit\\"],
        ],
        [5.5*cm, BREEDTE - 5.5*cm]))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Netwerk poorten", s["h2"]))
    story.append(data_tabel(s,
        ["Poort", "Service", "Bereikbaar via"],
        [
            ["22",   "SSH",          "PuTTY, PowerShell, SCP"],
            ["80",   "Apache/Nextcloud", "Browser: http://[Pi IP]"],
            ["445",  "Samba (SMB)",  "Windows Verkenner, net use"],
            ["5901", "TigerVNC",     "TigerVNC Viewer"],
            ["8080", "FileBrowser",  "Browser: http://[Pi IP]:8080"],
            ["8765", "Externe HDD", "Pi NAS Menu (intern)"],
            ["9090", "Cockpit",     "Browser: http://[Pi IP]:9090"],
            ["631",  "Printserver (CUPS)", "Browser: http://[Pi IP]:631 (add-on)"],
            ["8095", "PiNAS Dashboard", "Browser: http://[Pi IP]:8095 (add-on)"],
        ],
        [2*cm, 4*cm, BREEDTE - 6*cm]))

    story.append(PageBreak())

    story.append(Paragraph("10. Bekende eigenaardigheden", s["h1"]))
    story.append(HRFlowable(width=BREEDTE, thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "Dit hoofdstuk verzamelt niet-voor-de-hand-liggende gedragingen die tijdens de "
        "ontwikkeling zijn tegengekomen - handig als je iets herkent maar niet meteen "
        "begrijpt waarom.", s["body"]))
    story.append(Spacer(1, 0.3*cm))

    eigenaardigheden = [
        ("CUPS WebInterface staat standaard uit",
         ["Op Raspberry Pi OS/Debian zet CUPS 'WebInterface=yes' niet automatisch aan. "
          "De Printserver-installatie (pinas_printer.sh) doet dit voor je; alleen "
          "relevant als je CUPS handmatig hebt aangepast en poort 631 opeens "
          "'Web Interface is Disabled' toont."], ACCENT),
        ("CUPS Connection-veld bij Add Printer",
         ["De auto-ingevulde waarde bij een gedetecteerde driverless-printer kan een "
          "ongeldige tekenreeks tonen (encoding-glitch). Typ dan zelf "
          "ipp://<printer-IP>/ipp/print in - zie ook hoofdstuk 3.7."], ACCENT),
        ("zerotier-cli vereist root",
         ["Commando's als 'zerotier-cli listnetworks' falen stil als ze als gewone "
          "gebruiker (niet root) worden uitgevoerd, bijvoorbeeld vanuit een "
          "achtergronddienst. Relevant als een ZeroTier-adres onverwacht ontbreekt in "
          "een door de suite gegenereerd bestand."], ACCENT),
        ("Epson Smart Panel-koppeling nodig voor onderweg printen",
         ["Zie hoofdstuk 3.7, 'Onderweg printen op iPhone/iPad zonder wifi' - zonder "
          "deze eenmalige koppeling faalt printen zonder wifi consequent, ook met een "
          "verder correct AirPrint-profiel."], ACCENT),
    ]

    for titel, regels, kleur in eigenaardigheden:
        story.append(KeepTogether([
            info_box(s, titel, regels, kleur=kleur),
            Spacer(1, 0.3*cm),
        ]))

    # ── Hoofdstuk 11: Bestandsoverzicht - functie per bestand ─────────────────
    # 9 augustus 2026 (Frans, na een CSV-export van de hele boom vergeleken met
    # pinas_versies.json/Structuurcheck): "het zou erg mooi zijn als ook de
    # functie van alle bestanden in een hoofdstuk 11 in handleiding een
    # beschrijving krijgen. over een half jaar weet ik het niet meer, en een
    # leek kan niets opzoeken wat een functie van een bestand is." De korte
    # omschrijvingen hieronder zijn een uitgeschreven versie van dezelfde tekst
    # die Structuurcheck (NAS_Map_Beheer.pyw) per bestand gebruikt - dat blijft
    # zo de ENE bron voor "welke bestanden bestaan er", dit hoofdstuk is puur
    # de leesbare, uitgebreide toelichting erbij.
    story.append(PageBreak())
    story.append(Paragraph("11. Bestandsoverzicht - functie per bestand", s["h1"]))
    story.append(HRFlowable(width=BREEDTE, thickness=0.5, color=ACCENT))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "Compleet overzicht van alle bestanden in de suite, per map, met een korte "
        "omschrijving van de functie - puur als naslagwerk. Handig als je over een "
        "half jaar niet meer weet waar een bestand voor dient, of als iemand anders "
        "(zonder de ontwikkelgeschiedenis te kennen) moet begrijpen wat iets doet. "
        "Gegenereerde/tijdelijke bestanden staan hier bewust niet in: __pycache__ "
        "(Python-cache) en Logs\\ (draait vanzelf vol tijdens gebruik).", s["body"]))
    story.append(Spacer(1, 0.3*cm))

    kol_breedte_bestanden = [5.3*cm, BREEDTE - 5.3*cm]

    story.append(Paragraph("11.1 PiServer - installatiebestanden (Pi-kant)", s["h2"]))
    story.append(Paragraph(
        "Bestanden die NAAR de Pi gekopieerd worden en daar draaien - niet te "
        "verwarren met Addons\\, dat zijn add-on-scripts voor NA de installatie.",
        s["body"]))
    story.append(data_tabel(s, ["Bestand", "Functie"], [
        ["nas_installer.py", "Grafische (GUI) installatiewizard die op de Pi zelf draait bij een verse installatie: Samba, Nextcloud, Pi-hole enzovoort instellen."],
        ["nas_installer_cli.py", "Tekst-gebaseerde (command line) versie van dezelfde wizard - voor als er geen grafische omgeving beschikbaar is."],
        ["seagate_web.py", "Achtergronddienst op de Pi die de status van de externe Backup-HDD doorgeeft aan Pi NAS Menu (aan/uit, temperatuur)."],
        ["seagate-web.service", "Systemd-servicebestand dat seagate_web.py automatisch laat starten en herstarten op de Pi."],
        ["smart_plug.py", "Bedient de smart plug (slimme stekkerdoos) waarmee de Backup-HDD volledig uit/aan gezet kan worden - gebruikt door de HDD-volledige-cyclus-herstelactie."],
        ["smart_plug_config.json", "Configuratie (IP-adres, inloggegevens) van de smart plug."],
        ["hue_diagnose.py", "Diagnosescript voor een eventuele Philips Hue Bridge-koppeling."],
        ["pi_welkom.sh", "Welkomstbericht/samenvatting die getoond wordt bij het inloggen op de Pi via SSH."],
        ["install.sh", "Basis Linux-installatiescript dat de Pi-kant voorbereidt (packages installeren) voordat nas_installer.py draait."],
        ["nas_start.sh", "Desktop-snelkoppelingen wrapper (pkexec) op de Pi: start installer/config/diagnose-commando's vanuit een snelkoppeling zonder los een terminal te hoeven openen."],
        ["README.md", "Korte technische uitleg over de PiServer-map (Engelstalig/kort, voor ontwikkeling)."],
    ], kol_breedte_bestanden))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("11.2 ArchiefBackup - backup van de backup", s["h2"]))
    story.append(data_tabel(s, ["Bestand", "Functie"], [
        ["archief_backup_bewaking.pyw", "Vergelijkt de Archief Backup (Z:) met de Spiegel Backup (H:) en kan ze synchroniseren, met drie modi: alleen aanvullen, spiegel met quarantaine, of spiegel met direct verwijderen."],
        ["start.bat", "Start archief_backup_bewaking.pyw."],
    ], kol_breedte_bestanden))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("11.3 Sync - PiNAS Sync (dagelijkse bestanden-backup)", s["h2"]))
    story.append(data_tabel(s, ["Bestand", "Functie"], [
        ["pinas_sync_app.pyw", "Hoofdprogramma van PiNAS Sync: kopieert bestanden van deze pc naar de NAS, met automatische herstelacties bij verbindingsproblemen."],
        ["start.bat", "Start pinas_sync_app.pyw."],
        ["core\\sync_engine.py", "De eigenlijke synchronisatielogica: bestanden vergelijken/kopiëren, plus herstelacties zoals LanManFix en het opnieuw koppelen van een schijfletter."],
        ["core\\bron_doel_picker.py", "Het scherm waarin je bron- en doelmappen kiest en beheert (de lijst met sync-taken)."],
        ["core\\thema.py", "Kleuren/thema-instellingen specifiek voor PiNAS Sync."],
        ["core\\__init__.py", "Leeg bestand dat van de map core\\ een importeerbaar Python-package maakt - technische noodzaak, geen eigen inhoud."],
        ["requirements.txt", "Lijst van Python-afhankelijkheden (momenteel leeg - geen externe pakketten nodig, alleen de standaardbibliotheek)."],
        ["install_windows.bat", "Zet PiNAS Sync op deze Windows-pc op (snelkoppelingen e.d.)."],
    ], kol_breedte_bestanden))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("11.4 Beheer - hoofdmenu en centrale beheertools", s["h2"]))
    story.append(data_tabel(s, ["Bestand", "Functie"], [
        ["Pi_NAS_Menu.pyw", "Het hoofdmenu van de hele suite - vertrekpunt naar alle andere onderdelen, toont bovenin de statusbalk."],
        ["pi_nas_setup.pyw", "Wizard voor installatie of herstel van de suite (nieuwe pc, of iets stuk)."],
        ["Pi_NAS_Menu.ico", "Icoonbestand voor de vensters/snelkoppelingen van de suite."],
        ["Beheer_install.bat", "Installeert/herstelt de Beheer-map zelf, o.a. bij een Starter Kit-installatie op een nieuwe pc."],
        ["lanman_fix.py", "Past een Windows-registerinstelling aan die 'Systeemfout 5/67'-verbindingsproblemen met de Samba-shares oplost, en herstart zo nodig de Workstation-service (Systeemfout 1219)."],
        ["install_vnc_viewer.py", "Installeert TigerVNC Viewer."],
        ["python_bijwerken.bat", "Download en installeert de nieuwste Python-versie op deze pc (bestandsnaam bevat daardoor een versienummer dat steeds wijzigt)."],
        ["pinas_backup_beheer.pyw", "Centraal overzicht van alle backup-acties (Synchronisatie, PC Image Backup, Archief Backup Bewaking, Systeem-image, Backup-HDD controleren) met korte uitleg per knop."],
        ["pinas_image_backup.pyw", "Maakt een volledige systeemkopie van de Windows-schijf (C:) met wbAdmin - voor als deze pc's schijf ooit crasht."],
        ["picontrol.cfg", "Het centrale configuratiebestand: Pi-IP-adres, thema, en welke schijven (Opslag/Backup/Spiegel Backup) aanwezig zijn."],
        ["core\\image_backup.py", "De logica achter PC Image Backup, los van het scherm zelf."],
        ["core\\__init__.py", "Maakt core\\ een Python-package (Beheer-variant) - geen eigen inhoud."],
        ["assets\\pinas_logo.png / .svg", "Het PiNAS-logo (PNG voor algemeen gebruik, SVG als vector-bronbestand)."],
        ["assets\\pinas_logo_header.png", "Logo-variant voor vensterkoppen."],
        ["assets\\pinas_logo_hoofdmenu.png", "Logo-variant voor het hoofdmenuscherm."],
        ["assets\\pinas_logo_icoon.png", "Logo-variant als icoon-formaat."],
        ["assets\\pinas_sync_scherm1/2/3.png", "Schermafbeeldingen van PiNAS Sync, gebruikt in hoofdstuk 5 van deze handleiding."],
        ["NAS_Map_Beheer.pyw", "Structuurcheck en Opruimen: controleert of alle verwachte bestanden er zijn en up-to-date zijn, en helpt overbodige/onbekende bestanden opsporen."],
        ["NAS_Map_Beheer.bat", "Start NAS_Map_Beheer.pyw."],
        ["pinas_controle_beheer.pyw", "Verzamelt Suite testen, PC/Pi Diagnose en Logbestanden-bekijken op één plek (Controles)."],
        ["pinas_kleuren_kiezer.pyw", "Hiermee pas je het kleurenschema (thema) van de hele suite aan via kleurstalen."],
    ], kol_breedte_bestanden))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("11.5 Gedeeld - modules die door meerdere programma's gebruikt worden", s["h2"]))
    story.append(data_tabel(s, ["Bestand", "Functie"], [
        ["nas_upload.py", "Uploadt bestanden/scripts vanaf deze pc naar de Pi."],
        ["nas_diagnose.py", "Start een diagnose vanaf Windows-kant (roept nas_diagnose.sh op de Pi aan)."],
        ["nas_diagnose.sh", "Het diagnosescript dat op de Pi zelf draait (hardware/diensten controleren)."],
        ["pinas_theme.py", "Het centrale thema (kleuren) waar bijna elk scherm van de suite uit put."],
        ["pinas_theme_donker.py / _licht.py", "De twee concrete kleurensets (donker/licht) waartussen je kunt kiezen via Kleuren kiezen."],
        ["pinas_ui.py", "Herbruikbare bouwstenen voor vensters (header, secties, knoppen), zodat alle schermen er hetzelfde uitzien."],
        ["pinas_wachtwoord.py", "Beheert het opslaan/ophalen van het Samba-wachtwoord (Windows Credential Manager + cmdkey)."],
        ["pinas_logging.py", "Centrale logfunctie die door meerdere programma's gebruikt wordt."],
        ["pinas_launcher.py", "Voorkomt dat je een programma per ongeluk twee keer tegelijk opent."],
        ["pinas_pi_status.py", "Haalt in één keer (één SSH-commando) de status van alle Pi-diensten op, voor zowel Status als Addons Beheer."],
        ["controleer_documentatie_consistentie.py", "Controleert of elke add-on ook echt beschreven staat in Topografie, Structuurcheck en Handleiding."],
        ["pinas_schijven.py", "Zoekt de werkelijke stationsletter van een netwerkschijf op via de share-naam, in plaats van een vaste letter aan te nemen."],
        ["pinas_versies.json", "Houdt per bestand bij wanneer de laatst geleverde versie gemaakt is - de basis van Structuurcheck's versiecontrole."],
        ["maak_publieke_versie.py", "Bouwt een geanonimiseerde versie van de suite voor GitHub (zonder wachtwoorden/IP-adres)."],
        ["maak_starterkit.py", "Bouwt een ZIP-pakket om de suite op een nieuwe pc te installeren."],
        ["download_links.ini", "Bewaart downloadlinks voor externe software (PuTTY, TigerVNC, Python, enzovoort)."],
        ["herstel_backup_hdd.sh", "Herstelscript dat op de Pi draait om de Backup-HDD te repareren/opnieuw te mounten."],
        ["pinas_iphone_backup.sh", "Draait op de Pi (iPhone via usb aangesloten op de Pi): kopieert foto's, 'Op mijn iPhone', app-bestanden en (best effort) WhatsApp naar de Backup-schijf."],
        ["pinas_iphone_verkennen.sh", "Draait op de Pi: maakt de iPhone tijdelijk en alleen-lezen zichtbaar in Verkenner (geen back-up), ruimt zichzelf op bij afsluiten."],
        ["version.py", "Het centrale versienummer en de datum van de laatste wijziging, getoond in elk scherm."],
        ["test_suite.py", "Suite testen: draait tientallen kwaliteitschecks (bestanden, syntax, schijven, Pi-diensten, documentatie) in één overzicht, exporteerbaar naar CSV."],
        ["CONVENTIES.md", "De vaste spelregels van het project op één plek (ASCII-only in .bat/.ps1, dry-run vóór destructieve acties, enzovoort) - lees dit eerst als je iets structureels wijzigt."],
    ], kol_breedte_bestanden))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("11.6 Addons - installeerbare uitbreidingen op de Pi", s["h2"]))
    story.append(Paragraph(
        "Elke add-on heeft een installatie- en een verwijderscript; sommige ook nog "
        "een extra hulpscript. Beheerd via Addons Beheer.", s["body"]))
    story.append(data_tabel(s, ["Bestand", "Functie"], [
        ["pinas_addons_beheer.pyw", "Het scherm van waaruit je alle add-ons hieronder installeert, verwijdert en beheert - de hub voor add-ons."],
        ["pinas_pihole.sh / _verwijderen.sh", "Installeert/verwijdert Pi-hole (advertentieblokkerende DNS-server)."],
        ["pinas_zerotier.sh / _verwijderen.sh", "Installeert/verwijdert ZeroTier (VPN voor toegang van onderweg)."],
        ["pinas_nextcloud.sh / _verwijderen.sh", "Installeert/verwijdert Nextcloud (privé-cloudopslag voor bestanden, foto's, muziek)."],
        ["pinas_vaultwarden.sh / _verwijderen.sh", "Installeert/verwijdert Vaultwarden (Bitwarden-compatibele wachtwoordkluis), inclusief een eigen root-certificaat."],
        ["pinas_vaultwarden_cert_vertrouwen.pyw", "Maakt het Vaultwarden-certificaat vertrouwd op deze Windows-pc."],
        ["pinas_vaultwarden_cert_import.ps1", "PowerShell-script dat het certificaat daadwerkelijk importeert (met verhoogde/elevated rechten)."],
        ["pinas_status_pagina.sh / _verwijderen.sh", "Installeert/verwijdert de mobiele statuspagina (overzicht van de NAS op je telefoon)."],
        ["pinas_status_pagina_wachtwoord_resetten.sh", "Zet het wachtwoord van de mobiele statuspagina opnieuw."],
        ["pinas_printer.sh / _verwijderen.sh", "Installeert/verwijdert de netwerk-printserver (CUPS + AirPrint)."],
        ["pinas_dashboard.sh / _verwijderen.sh", "Installeert/verwijdert het PiNAS Dashboard (overzicht van alle add-ons op één webpagina)."],
    ], kol_breedte_bestanden))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("11.7 Publicatie - documentatie-generators en eindproducten", s["h2"]))
    story.append(Paragraph(
        "Belangrijk: de .pdf/.html-bestanden hieronder zijn EINDPRODUCTEN, gebouwd "
        "door het bijbehorende build_*.py-script. Wijzig nooit het eindproduct zelf "
        "- dat wordt bij de volgende build gewoon overschreven.", s["body"]))
    story.append(data_tabel(s, ["Bestand", "Functie"], [
        ["PiNAS_Suite_Handleiding.pdf", "Dit document - de volledige gebruikershandleiding."],
        ["build_suite_handleiding.py", "Het Python-script dat PiNAS_Suite_Handleiding.pdf genereert."],
        ["PiNAS_Topografie.html", "Interactief overzicht (matrix) van welk bestand bij welk menu-item/categorie hoort - vergelijkt zichzelf ook met pinas_versies.json."],
        ["build_topografie.py", "Het Python-script dat PiNAS_Topografie.html genereert."],
        ["PiNAS_Suite_Presentatie.pptx", "Presentatie voor bekendheid/publiciteit - installatie tot gebruik, inclusief een compact functieoverzicht als losse pagina (10 augustus 2026, verving PiNAS_Functieoverzicht.pdf)."],
        ["PiNAS_Suite_Presentatie_Preview.pdf", "PDF-export van de presentatie, alleen voor GitHub's ingebouwde viewer - géén los eindproduct om te lezen, wordt gemaakt via 'Presentatie exporteren als PDF' in PowerPoint."],
        ["PiNAS_Suite_Architectuur.png", "Architectuurplaatje (5 lagen) voor de GitHub README."],
        ["Publicatie_Gids.md / .pdf", "Uitleg over hoe je een nieuwe versie publiceert (Starter Kit of publieke GitHub-versie)."],
    ], kol_breedte_bestanden))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("11.8 Installatie - meegeleverde installatiebestanden", s["h2"]))
    story.append(Paragraph(
        "Kant-en-klare, door derden gemaakte installers - geen eigen broncode, dus "
        "geen versiedatum-controle zoals de rest van de suite (dat zou geen "
        "toegevoegde waarde hebben). De Python-installer staat hier bewust NIET "
        "met een vaste bestandsnaam bij: 'Windows onderdelen' download altijd de "
        "nieuwste versie, dus de bestandsnaam (met versienummer erin) wijzigt bij "
        "elke update - Structuurcheck herkent 'm via een patroon (python-3*.exe) "
        "in plaats van een vaste naam.", s["body"]))
    story.append(data_tabel(s, ["Bestand", "Functie"], [
        ["imager_2.0.7.exe", "Raspberry Pi Imager - zet het besturingssysteem op de SD-kaart van de Pi."],
        ["tigervnc64-1.16.2.exe", "TigerVNC Viewer - voor het grafisch bureaublad van de Pi bekijken."],
        ["putty-64bit-0.84-installer.msi", "PuTTY - SSH-terminaltoegang tot de Pi."],
        ["python-3.x-amd64.exe (versienummer wisselt)", "Python voor Windows - nodig voor de Publicatie-builders en Suite testen."],
    ], kol_breedte_bestanden))

    return story


def main():
    if sys.platform == "win32":
        uit_map = r"C:\PiNAS\Publicatie"
    else:
        uit_map = os.path.dirname(os.path.abspath(__file__))

    os.makedirs(uit_map, exist_ok=True)
    uit_pad = os.path.join(uit_map, "PiNAS_Suite_Handleiding.pdf")

    print(f"Pi NAS Suite Handleiding bouwen...")
    print(f"Output: {uit_pad}")

    doc = SimpleDocTemplate(
        uit_pad,
        pagesize=A4,
        leftMargin=MARGE_L,
        rightMargin=MARGE_R,
        topMargin=MARGE_T + 0.8*cm,
        bottomMargin=MARGE_B,
        title=f"Pi NAS Suite Handleiding {DATUM}",
        author="Pi NAS Suite",
        subject="Gebruikershandleiding",
        creator="build_suite_handleiding.py",
    )

    story = bouw_handleiding()

    doc.build(story,
              onFirstPage=eerste_pagina,
              onLaterPages=pagina_achtergrond)

    grootte = os.path.getsize(uit_pad)
    print(f"OK: {uit_pad} ({grootte//1024} KB)")
    return uit_pad

if __name__ == "__main__":
    main()
