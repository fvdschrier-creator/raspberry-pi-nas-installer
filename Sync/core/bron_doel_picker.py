"""
Pi NAS Suite - generieke bron/doel-kiezer (Tkinter).

Vervangt het Kivy-stuk uit main.py (FileTreePanel + SourceMappingPanel)
door een Tkinter-versie met hetzelfde gedrag, maar generiek: niet
gebonden aan een vaste NAS-doelbasis. Werkt met:
  - lokale mappen
  - Windows-stations (C:, D:, Y:, Z:, ...)
  - UNC-netwerkpaden (\\\\HOST\\Share\\...) - bijv. een Zorin-share of
    een andere netwerk-NAS
  - Pi-mounts (Y:/Z:) - die zijn voor dit onderdeel gewoon een station

Links: een uitklapbare checkbox-boom over alle stations + opgeslagen
netwerk-snelkoppelingen. Rechts: per aangevinkte bron een eigen
doelpad, automatisch voorgesteld op basis van de stationsnaam/mapnaam,
maar altijd handmatig aanpasbaar of via een mapkiezer te wijzigen.

Snelkoppelingen (handmatig toegevoegde netwerkpaden, zoals een Zorin-share
of een andere netwerk-NAS) worden onthouden in een klein JSON-bestand zodat
ze niet elke keer opnieuw ingevoerd moeten worden.
"""

import os
import sys
import json
import string
import ctypes
import threading
import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
from dataclasses import dataclass

try:
    from core.sync_engine import SyncTaak
except ImportError:
    from sync_engine import SyncTaak

try:
    from core.thema import ACCENT, TEKST, TEKST_DIM, ORANJE
except ImportError:
    from thema import ACCENT, TEKST, TEKST_DIM, ORANJE


VINKJE_AAN = "[x]"
VINKJE_UIT = "[ ]"
MAX_KINDEREN_PER_MAP = 200  # voorkomt bevriezen bij gigantische mappen


# =================================================================
# Snelkoppelingen-opslag (netwerkpaden die je vaker gebruikt)
# =================================================================

def _snelkoppelingen_pad():
    map_pad = os.path.join(os.path.expanduser("~"), ".pinas_sync")
    try:
        os.makedirs(map_pad, exist_ok=True)
    except Exception:
        pass
    return os.path.join(map_pad, "snelkoppelingen.json")


def laad_snelkoppelingen():
    pad = _snelkoppelingen_pad()
    if os.path.exists(pad):
        try:
            with open(pad, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def bewaar_snelkoppelingen(lijst):
    pad = _snelkoppelingen_pad()
    try:
        with open(pad, "w", encoding="utf-8") as f:
            json.dump(lijst, f, indent=2)
    except Exception:
        pass


# =================================================================
# Drive-/padhulpfuncties
# =================================================================

def _get_drives():
    """Geeft alle bereikbare Windows-stations terug (C:\\, D:\\, ...)."""
    if sys.platform != "win32":
        return []
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for letter in string.ascii_uppercase:
        if bitmask & 1:
            drives.append(letter + ":\\")
        bitmask >>= 1
    return drives


def _volumenaam(pad):
    """Volumenaam van een station, of leeg als niet te bepalen."""
    if sys.platform != "win32":
        return ""
    try:
        buf = ctypes.create_unicode_buffer(256)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            pad, buf, 256, None, None, None, None, 0)
        return buf.value.strip() if ok else ""
    except Exception:
        return ""


def _stationlabel(pad):
    naam = _volumenaam(pad)
    letter = pad.rstrip("\\")
    return f"{letter}  ({naam})" if naam else letter


def _voorgestelde_doelnaam(bron_pad):
    """Bepaalt een leesbare naam voor een bron, voor gebruik als
    doel-submapnaam: volumenaam bij een station-root, sharenaam bij
    een UNC-netwerkpad-root (bijv. \\\\NASF1451B\\Backup -> 'Backup'),
    anders de mapnaam zelf."""
    bron_pad = bron_pad.rstrip("\\/")

    if len(bron_pad) == 2 and bron_pad[1] == ":":
        vol = _volumenaam(bron_pad + "\\")
        if vol:
            return vol
        return bron_pad[0] + "_station"

    if bron_pad.startswith("\\\\"):
        # ntpath behandelt een UNC-share-root (\\HOST\Share) net als
        # een schijf-root: os.path.basename geeft dan LEEG terug,
        # omdat het hele \\HOST\Share als "station" gezien wordt. Pak
        # in dat geval de sharenaam zelf (het laatste deel), net zoals
        # de oorspronkelijke, oudere sync-tool deed met "Backup"/"Public".
        delen = [d for d in bron_pad.split("\\") if d]
        if len(delen) <= 2:  # alleen host+share, geen submap erin
            return delen[-1] if delen else bron_pad.replace("\\", "_")
        return delen[-1]

    return os.path.basename(bron_pad) or bron_pad.replace(":", "").replace("\\", "_")


def _lijst_mapinhoud(pad, timeout_seconden=8.0):
    """Mappen eerst, dan bestanden, allemaal alfabetisch. Best-effort:
    geeft (entries, foutmelding) terug - bij een onbereikbare/
    ontoegankelijke map is entries leeg en staat de reden in
    foutmelding. Met een TIMEOUT: een instabiele netwerkverbinding
    (Y:/Z: via SMB naar de Pi) kan os.scandir() onbeperkt laten
    hangen zonder timeout - dat zou de boom voor altijd op '...'
    laten staan zonder dat de gebruiker weet of er nog iets gebeurt."""
    resultaat = {"entries": None, "fout": None}

    def doe():
        try:
            entries = list(os.scandir(pad))
            entries.sort(key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))
            resultaat["entries"] = [
                (e.name, e.path, e.is_dir(follow_symlinks=False))
                for e in entries[:MAX_KINDEREN_PER_MAP]]
        except (PermissionError, OSError) as e:
            resultaat["fout"] = str(e)
        except Exception as e:
            resultaat["fout"] = str(e)

    draad = threading.Thread(target=doe, daemon=True)
    draad.start()
    draad.join(timeout=timeout_seconden)
    if draad.is_alive():
        return [], f"geen reactie binnen {timeout_seconden:.0f} sec (verbinding hapert mogelijk)"
    if resultaat["entries"] is not None:
        return resultaat["entries"], None
    return [], resultaat["fout"] or "onbekende fout"


# =================================================================
# Checkbox-boom voor bronselectie
# =================================================================

class BronBoom(ttk.Frame):
    """Uitklapbare checkbox-boom: Windows-stations + opgeslagen
    netwerk-snelkoppelingen. Interactie is bewust ondubbelzinnig:
    - Klik op het driehoekje: uitklappen/inklappen.
    - Klik ergens anders op de regel (vinkje, naam, lege ruimte):
      aanvinken/uitvinken.
    Dit werkt voor mappen, bestanden, stations en netwerkpaden
    allemaal hetzelfde, en blijft kloppen op elk inspringniveau -
    er wordt niet meer gegokt op een vaste pixelafstand."""

    def __init__(self, master, op_wijziging=None, **kw):
        super().__init__(master, **kw)
        self._op_wijziging = op_wijziging or (lambda geselecteerd: None)
        self._geselecteerd = set()
        self._uitgeklapt = set()
        self._cache = {}
        self._build()
        self.verversen()

    def _build(self):
        kop = ttk.Frame(self)
        kop.pack(fill="x", pady=(0, 4))
        ttk.Label(kop, text="BRONNEN", font=("Segoe UI", 9, "bold")).pack(side="left")
        ttk.Button(kop, text="+ Netwerkpad", width=14,
                   command=self._voeg_netwerkpad_toe).pack(side="right")
        ttk.Button(kop, text="Ververs", width=8,
                   command=self.verversen).pack(side="right", padx=(0, 4))

        omkader = ttk.Frame(self)
        omkader.pack(fill="both", expand=True)
        self.boom = ttk.Treeview(omkader, show="tree", selectmode="none")
        sb = ttk.Scrollbar(omkader, orient="vertical", command=self.boom.yview)
        self.boom.configure(yscrollcommand=sb.set)
        self.boom.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.boom.bind("<Button-1>", self._klik)
        self.boom.tag_configure("snelkoppeling", foreground=ACCENT)
        self.boom.tag_configure("map", foreground=TEKST)
        self.boom.tag_configure("bestand", foreground=TEKST_DIM)

    def verversen(self):
        self.boom.delete(*self.boom.get_children())
        self._cache.clear()
        self._uitgeklapt.clear()

        snelkoppelingen = laad_snelkoppelingen()
        if snelkoppelingen:
            kop_id = self.boom.insert("", "end", text="-- Snelkoppelingen --", open=True,
                                      tags=("kopregel",), values=("kop",))
            for naam, pad in snelkoppelingen:
                self._voeg_root_toe(f"{VINKJE_UIT} {naam}", pad)

        self._voeg_root_toe("-- Stations --", None, is_kop=True)
        for d in _get_drives():
            self._voeg_root_toe(f"{VINKJE_UIT} {_stationlabel(d)}", d)

    def _voeg_root_toe(self, tekst, volledig_pad, is_kop=False):
        if is_kop:
            self.boom.insert("", "end", text=tekst, open=True, tags=("kopregel",), values=("kop",))
            return
        node_id = self.boom.insert("", "end", text=tekst, values=(volledig_pad,),
                                   tags=("map",))
        # Plaatshouder zodat het uitklap-driehoekje verschijnt
        self.boom.insert(node_id, "end", text="...", values=("__placeholder__",))

    def _is_selecteerbaar(self, item_id):
        """True voor elk item met een echt pad (map, bestand, station,
        netwerkpad) - False voor kopregels en statusmeldingen zoals
        '(bezig met laden...)' of '(leeg)'."""
        waarden = self.boom.item(item_id, "values")
        return bool(waarden) and waarden[0] not in ("kop",)

    def _volledig_pad(self, item_id):
        waarden = self.boom.item(item_id, "values")
        return waarden[0] if waarden else None

    def _klik(self, event):
        item_id = self.boom.identify_row(event.y)
        if not item_id:
            return

        if not self._is_selecteerbaar(item_id) or self._volledig_pad(item_id) in (
                "__placeholder__", "__laden__", "__fout__", "__leeg__"):
            return

        element = self.boom.identify_element(event.x, event.y)

        # Het driehoekje (indicator) is en blijft uitsluitend voor
        # uitklappen/inklappen - ongeacht inspringdiepte, want
        # identify_element kijkt naar WAT er onder de muis staat, niet
        # naar een vaste pixelgrens. Dat was de fout hiervoor: bij
        # genestelde mappen schuift de tekst naar rechts door de
        # inspringing, maar een vaste "eerste 40 pixels"-grens schuift
        # niet mee, waardoor de vinkjes-zone bij diepere niveaus niet
        # meer klopte.
        if "indicator" in element:
            self._toggle_uitklap(item_id)
            return

        # Overal elders op de regel (vinkje-tekst, naam, of de lege
        # ruimte erachter) telt als "aanvinken/uitvinken" - dit is
        # bewust het grootste deel van de klikbare regel, niet een
        # dun randje, zodat het altijd duidelijk is waar je moet
        # klikken om te selecteren.
        self._toggle_selectie(item_id)

    def _toggle_selectie(self, item_id):
        pad = self._volledig_pad(item_id)
        tekst = self.boom.item(item_id, "text")
        if pad in self._geselecteerd:
            self._geselecteerd.discard(pad)
            nieuwe_tekst = tekst.replace(VINKJE_AAN, VINKJE_UIT, 1)
        else:
            self._geselecteerd.add(pad)
            nieuwe_tekst = tekst.replace(VINKJE_UIT, VINKJE_AAN, 1)
        self.boom.item(item_id, text=nieuwe_tekst)
        self._op_wijziging(list(self._geselecteerd))

    def _toggle_uitklap(self, item_id):
        pad = self._volledig_pad(item_id)
        if item_id in self._uitgeklapt:
            self._uitgeklapt.discard(item_id)
            for kind in self.boom.get_children(item_id):
                self.boom.delete(kind)
            self.boom.insert(item_id, "end", text="...", values=("__placeholder__",))
            return

        self._uitgeklapt.add(item_id)
        for kind in self.boom.get_children(item_id):
            self.boom.delete(kind)

        if pad in self._cache:
            self._vul_kinderen(item_id, self._cache[pad], None)
            return

        # Direct zichtbare feedback - zonder dit lijkt het of er niets
        # gebeurt zolang de achtergrondthread nog bezig is (vooral bij
        # Y:/Z: die via een haperende SMB-verbinding kunnen lopen).
        self.boom.insert(item_id, "end", text="(bezig met laden...)",
                         values=("__laden__",), tags=("bestand",))

        def laden():
            entries, fout = _lijst_mapinhoud(pad)
            if fout is None:
                self._cache[pad] = entries
            self.after(0, lambda: self._vul_kinderen(item_id, entries, fout))

        threading.Thread(target=laden, daemon=True).start()

    def _vul_kinderen(self, parent_id, entries, fout):
        for kind in self.boom.get_children(parent_id):
            self.boom.delete(kind)
        if fout:
            self.boom.insert(parent_id, "end", text=f"(niet bereikbaar: {fout})",
                             values=("__fout__",))
            return
        if not entries:
            self.boom.insert(parent_id, "end", text="(leeg)",
                             values=("__leeg__",))
            return
        for naam, volledig, is_dir in entries:
            tags = ("map",) if is_dir else ("bestand",)
            node_id = self.boom.insert(parent_id, "end",
                                       text=f"{VINKJE_UIT} {naam}",
                                       values=(volledig,), tags=tags)
            if is_dir:
                self.boom.insert(node_id, "end", text="...", values=("__placeholder__",))

    def _voeg_netwerkpad_toe(self):
        pad = simpledialog.askstring(
            "Netwerkpad toevoegen",
            "UNC-pad (bijv. \\\\NASF1451B\\Backup of \\\\UW_PI_IP_ADRES\\share):",
            parent=self)
        if not pad:
            return
        pad = pad.strip()
        if not pad:
            return
        naam = simpledialog.askstring(
            "Naam voor snelkoppeling",
            "Korte naam (voor in de lijst):",
            initialvalue=os.path.basename(pad.rstrip("\\")) or pad,
            parent=self)
        if not naam:
            naam = pad
        snelkoppelingen = laad_snelkoppelingen()
        snelkoppelingen.append([naam, pad])
        bewaar_snelkoppelingen(snelkoppelingen)
        self.verversen()

    def get_geselecteerd(self):
        return list(self._geselecteerd)


# =================================================================
# Doel-toewijzing per bron (rechterpaneel)
# =================================================================

class TaakRij(ttk.Frame):
    def __init__(self, master, bron_pad, doel_pad, op_verwijderen=None, **kw):
        super().__init__(master, **kw)
        self.bron_pad = bron_pad
        self._op_verwijderen = op_verwijderen

        ttk.Label(self, text=bron_pad, foreground=ACCENT,
                 width=38, anchor="w").pack(side="left", padx=(0, 4))
        ttk.Label(self, text="->", foreground=TEKST_DIM).pack(side="left", padx=2)

        self.doel_var = tk.StringVar(value=doel_pad)
        ttk.Entry(self, textvariable=self.doel_var, width=38).pack(
            side="left", fill="x", expand=True, padx=4)

        ttk.Button(self, text="...", width=3,
                  command=self._kies_map).pack(side="left", padx=2)
        ttk.Button(self, text="X", width=2,
                  command=self._verwijder).pack(side="left", padx=(2, 0))

    def _kies_map(self):
        gekozen = filedialog.askdirectory(title="Kies doelmap (de bronmap komt hier ALS SUBMAP in)")
        if not gekozen:
            return
        # Belangrijk: een gekozen map is de PLEK WAAR de bronmap in
        # terechtkomt, niet de plek waar de INHOUD los in gedumpt
        # wordt. Zonder deze toevoeging zou het kiezen van bijv. Z:\
        # als doel betekenen dat de inhoud van de bronmap direct op
        # Z:\ landt, in plaats van in Z:\<bronmapnaam>\. Dat is niet
        # wat iemand verwacht die een MAP als bron aanvinkt.
        naam = _voorgestelde_doelnaam(self.bron_pad)
        gekozen_genormaliseerd = gekozen.rstrip("/\\")
        if naam and not gekozen_genormaliseerd.lower().endswith(naam.lower()):
            gekozen = os.path.join(gekozen, naam)
        self.doel_var.set(gekozen)

    def _verwijder(self):
        if self._op_verwijderen:
            self._op_verwijderen(self)

    def get_doel(self):
        return self.doel_var.get().strip()


class DoelToewijzingPaneel(ttk.Frame):
    """Toont voor elke aangevinkte bron een eigen, aanpasbare
    doelmap. Geen vaste doel-root meer - elke regel mag naar een
    volledig ander station wijzen."""

    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self._rijen = {}
        self._build()

    def _build(self):
        basis_paneel = ttk.Frame(self)
        basis_paneel.pack(fill="x", pady=(0, 8))
        ttk.Label(basis_paneel, text="Doelbasis (een keer instellen, geldt voor elke "
                 "aangevinkte bron):", font=("Segoe UI", 9, "bold")
                 ).pack(anchor="w")
        basis_rij = ttk.Frame(basis_paneel)
        basis_rij.pack(fill="x", pady=(2, 0))
        self._doel_basis_var = tk.StringVar(value="")
        basis_invoer = ttk.Entry(basis_rij, textvariable=self._doel_basis_var)
        basis_invoer.pack(side="left", fill="x", expand=True, padx=(0, 4))
        basis_invoer.bind("<Return>", lambda e: self._doel_basis_handmatig_gewijzigd())
        basis_invoer.bind("<FocusOut>", lambda e: self._doel_basis_handmatig_gewijzigd())
        ttk.Button(basis_rij, text="...", width=3,
                  command=self._kies_doel_basis).pack(side="left", padx=2)
        ttk.Button(basis_rij, text="Toepassen op alle bronnen", 
                  command=self._toepassen_op_alle).pack(side="left", padx=(4, 0))
        ttk.Label(basis_paneel,
                 text="Zonder doelbasis moet je per bron zelf een volledig doelpad "
                      "intypen of kiezen - vergeet dan niet zelf een submap met de "
                      "bronnaam toe te voegen, anders komt de INHOUD los in die map "
                      "te staan in plaats van de map zelf.",
                 font=("Segoe UI", 8), foreground=ORANJE, wraplength=520,
                 justify="left").pack(anchor="w", pady=(4, 0))

        kop = ttk.Frame(self)
        kop.pack(fill="x", pady=(8, 4))
        ttk.Label(kop, text="BRON", font=("Segoe UI", 9, "bold"), width=38,
                 anchor="w").pack(side="left", padx=(0, 4))
        ttk.Label(kop, text="", width=4).pack(side="left")
        ttk.Label(kop, text="DOEL (aanpasbaar)", font=("Segoe UI", 9, "bold")
                 ).pack(side="left", fill="x", expand=True)

        omkader = ttk.Frame(self)
        omkader.pack(fill="both", expand=True)
        self._canvas = tk.Canvas(omkader, highlightthickness=0)
        sb = ttk.Scrollbar(omkader, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=sb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._binnenframe = ttk.Frame(self._canvas)
        self._canvas.create_window((0, 0), window=self._binnenframe, anchor="nw")
        self._binnenframe.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))

        self._leeg_label = ttk.Label(self._binnenframe,
                                     text="Vink bronnen aan in de boom links",
                                     foreground=TEKST_DIM)
        self._leeg_label.pack(anchor="w", pady=8)

    def _kies_doel_basis(self):
        gekozen = filedialog.askdirectory(
            title="Kies de doelbasis (elke bron krijgt hier automatisch een eigen submap in)")
        if gekozen:
            self._doel_basis_var.set(gekozen)
            self._doel_basis_handmatig_gewijzigd()

    def _doel_basis_handmatig_gewijzigd(self):
        self.doel_basis_instellen(self._doel_basis_var.get())

    def _toepassen_op_alle(self):
        """Overschrijft het doelpad van ELKE huidige rij met
        doelbasis + bronnaam - ook rijen die al een (mogelijk
        verkeerd ingevulde) doel hadden. Expliciete actie, geen
        automatisch gedrag, zodat handmatige aanpassingen niet
        zomaar stilletjes overschreven worden."""
        basis = getattr(self, "_doel_basis", "")
        if not basis:
            messagebox.showwarning("Geen doelbasis", "Stel eerst een doelbasis in.")
            return
        for bron_pad, rij in self._rijen.items():
            naam = _voorgestelde_doelnaam(bron_pad)
            rij.doel_var.set(os.path.join(basis, naam))

    def doel_basis_instellen(self, doel_basis):
        """Vult een gemeenschappelijke doelbasis in voor alle NIEUWE
        bronnen die nog geen doel hebben - handig als je bijvoorbeeld
        alles standaard naar Z:\\Backup wilt laten wijzen, maar
        individueel kan dit altijd aangepast worden."""
        self._doel_basis = doel_basis.rstrip("\\/")
        if doel_basis and self._doel_basis_var.get() != doel_basis:
            self._doel_basis_var.set(doel_basis)

    def bijwerken_bronnen(self, geselecteerde_paden):
        huidige = set(self._rijen.keys())
        nieuwe = set(geselecteerde_paden)

        for pad in huidige - nieuwe:
            self._rijen.pop(pad).destroy()

        basis = getattr(self, "_doel_basis", "")
        for pad in nieuwe - huidige:
            naam = _voorgestelde_doelnaam(pad)
            voorgesteld_doel = os.path.join(basis, naam) if basis else ""
            rij = TaakRij(self._binnenframe, pad, voorgesteld_doel,
                         op_verwijderen=self._verwijder_rij)
            rij.pack(fill="x", pady=2)
            self._rijen[pad] = rij

        if self._rijen:
            self._leeg_label.pack_forget()
        else:
            self._leeg_label.pack(anchor="w", pady=8)

    def _verwijder_rij(self, rij):
        if rij.bron_pad in self._rijen:
            del self._rijen[rij.bron_pad]
        rij.destroy()
        if not self._rijen:
            self._leeg_label.pack(anchor="w", pady=8)

    def get_taken(self):
        taken = []
        for bron_pad, rij in self._rijen.items():
            doel = rij.get_doel()
            if doel:
                taken.append(SyncTaak(bron_pad=bron_pad, doel_pad=doel))
        return taken


# =================================================================
# Samengesteld widget: boom + doeltoewijzing naast elkaar
# =================================================================

class BronDoelKiezer(ttk.Frame):
    """Combineert BronBoom (links) en DoelToewijzingPaneel (rechts)
    tot een herbruikbaar widget. get_taken() geeft de uiteindelijke
    lijst SyncTaak-objecten terug, klaar voor de SyncEngine."""

    def __init__(self, master, doel_basis="", **kw):
        super().__init__(master, **kw)
        self._build(doel_basis)

    def _build(self, doel_basis):
        verdeler = ttk.PanedWindow(self, orient="horizontal")
        verdeler.pack(fill="both", expand=True)

        links = ttk.Frame(verdeler)
        rechts = ttk.Frame(verdeler)
        verdeler.add(links, weight=1)
        verdeler.add(rechts, weight=1)

        self.boom = BronBoom(links, op_wijziging=self._bron_gewijzigd)
        self.boom.pack(fill="both", expand=True)

        self.doelpaneel = DoelToewijzingPaneel(rechts)
        self.doelpaneel.pack(fill="both", expand=True)
        if doel_basis:
            self.doelpaneel.doel_basis_instellen(doel_basis)

    def _bron_gewijzigd(self, geselecteerde_paden):
        self.doelpaneel.bijwerken_bronnen(geselecteerde_paden)

    def get_taken(self):
        return self.doelpaneel.get_taken()


# =================================================================
# Losse test - laat het widget op zichzelf zien
# =================================================================

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Bron/doel-kiezer - test")
    root.geometry("1100x650")

    kiezer = BronDoelKiezer(root, doel_basis="Z:\\Backup")
    kiezer.pack(fill="both", expand=True, padx=8, pady=8)

    def toon_taken():
        taken = kiezer.get_taken()
        if not taken:
            messagebox.showinfo("Taken", "Geen bronnen geselecteerd.")
            return
        tekst = "\n".join(f"{t.bron_pad}  ->  {t.doel_pad}" for t in taken)
        messagebox.showinfo("Taken", tekst)

    ttk.Button(root, text="Toon gekozen taken", command=toon_taken).pack(pady=4)

    root.mainloop()
