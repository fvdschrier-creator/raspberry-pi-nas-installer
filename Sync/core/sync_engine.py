"""
Pi NAS Suite - generieke sync-engine.

Herbouwd vanuit de sync-engine van een eerdere, losse sync-tool die nog
specifiek voor het oude NAS-apparaat was gebouwd. Alle logica die in
de praktijk bewezen robuust is gebleken (proactieve verbindingscheck,
storing-duurt-voort logging, zelfherstel via HDD-stroomcyclus en
LanManFix, lang-pad ondersteuning, Windows-attributenfix) is hier
ONGEWIJZIGD overgenomen. Het enige verschil: bron en doel zijn nu
volledig vrij te kiezen in plaats van vast (voorheen hardcoded naar het
oude NAS-apparaat op Z:\\).

Bewust los van Tkinter, zodat deze module ook los gebruikt kan worden
(bijvoorbeeld later vanuit een Pi-side script of een testscript) zonder
dat de kernlogica opnieuw geschreven hoeft te worden.

Belangrijk: ELKE sync-taak heeft zijn EIGEN volledige doelpad. Er is
geen gedeelde "doel_root" meer - dat was de aanname die specifiek voor
het oude NAS-apparaat gold.
Een taak kan dus naar Z:\\Backup, Y:\\Iets, een UNC-pad, of zelfs een
ander station wijzen. De engine bepaalt zelf welke unieke doel-stations
er zijn en test/herstelt die los van elkaar.
"""

import os
import time
import hashlib
import threading
import subprocess
import configparser
import datetime
from dataclasses import dataclass, field
from enum import Enum


# =================================================================
# Kernlogica - bewust losstaand van enige UI-toolkit.
# =================================================================

class BestandStatus(Enum):
    AL_AANWEZIG = "al_aanwezig"
    TOEGEVOEGD = "toegevoegd"
    BIJGEWERKT = "bijgewerkt"
    MISLUKT = "mislukt"


@dataclass
class SyncResultaat:
    relatief_pad: str
    status: BestandStatus
    grootte: int = 0
    foutmelding: str = ""


@dataclass
class SyncTaak:
    """Een bron-naar-doel koppeling. Bron en doel zijn allebei
    volledig vrije paden - lokaal, Windows-drive, UNC-netwerkpad, of
    een Pi-mount (Y:/Z:). De engine behandelt ze allemaal gelijk."""
    bron_pad: str
    doel_pad: str
    label: str = ""  # optioneel, voor weergave in UI/log

    def __post_init__(self):
        if not self.label:
            self.label = self.bron_pad


@dataclass
class SyncVoortgang:
    fase: str = "wachten"  # wachten / onderzoeken / synchroniseren / gepauzeerd / klaar
    totaal_bestanden: int = 0
    totaal_bytes: int = 0
    totaal_onbekend: bool = False  # True als tellen bewust is overgeslagen
    onderzocht_bestanden: int = 0
    verwerkt_bestanden: int = 0
    verwerkt_bytes: int = 0
    al_aanwezig: int = 0
    toegevoegd: int = 0
    bijgewerkt: int = 0
    verwijderd: int = 0  # wees-bestanden opgeruimd (alleen bij echte sync)
    fouten: int = 0
    gestart_om: float = 0.0
    huidige_bestand: str = ""
    laatste_fout: str = ""
    overgeslagen_door_storing: list = field(default_factory=list)


def lang_pad(pad: str) -> str:
    """Geeft het pad terug met het \\\\?\\ voorvoegsel als dat nodig is
    om de Windows-limiet van 260 tekens te omzeilen. Korte paden
    worden ongewijzigd teruggegeven - het voorvoegsel is alleen nodig
    (en alleen veilig) bij paden van 240 tekens of langer."""
    if not os.path.isabs(pad):
        pad = os.path.abspath(pad)
    pad = pad.replace("/", "\\")
    if len(pad) < 240:
        return pad
    if pad.startswith("\\\\"):
        return "\\\\?\\UNC\\" + pad[2:]
    return "\\\\?\\" + pad


def bereken_md5(pad: str, chunk_grootte: int = 4 * 1024 * 1024):
    """Berekent de MD5-hash van een bestand. Geeft None terug als het
    bestand niet gelezen kan worden."""
    try:
        h = hashlib.md5()
        with open(lang_pad(pad), "rb") as f:
            while True:
                stuk = f.read(chunk_grootte)
                if not stuk:
                    break
                h.update(stuk)
        return h.hexdigest()
    except Exception:
        return None


def formatteer_bytes(aantal: float) -> str:
    for eenheid in ("B", "KB", "MB", "GB", "TB"):
        if aantal < 1024:
            return f"{aantal:.1f} {eenheid}"
        aantal /= 1024
    return f"{aantal:.1f} PB"


def formatteer_duur(seconden: float) -> str:
    seconden = max(0, int(seconden))
    if seconden < 60:
        return f"{seconden} sec"
    minuten, sec = divmod(seconden, 60)
    if minuten < 60:
        return f"{minuten} min {sec} sec"
    uren, minuten = divmod(minuten, 60)
    return f"{uren} uur {minuten} min"


def drive_root(pad: str) -> str:
    """Geeft de schijf-root van een pad terug, voor gebruik als
    verbindings-testdoel. Werkt voor zowel 'Z:\\Iets\\Map' (-> 'Z:\\')
    als '\\\\HOST\\Share\\Map' (-> '\\\\HOST\\Share')."""
    pad = pad.replace("/", "\\")
    if pad.startswith("\\\\"):
        delen = pad.split("\\")
        # delen[0]='' delen[1]='' delen[2]=host delen[3]=share
        if len(delen) >= 4:
            return "\\\\" + delen[2] + "\\" + delen[3]
        return pad
    drive, _ = os.path.splitdrive(pad)
    return drive + "\\" if drive else pad


def host_van_pad(pad: str):
    """Haalt de hostnaam uit een UNC-pad, voor statuscontroles (ping).
    Geeft None terug als het geen netwerkpad is (bijv. een lokale
    schijfletter zoals Z:\\ of Y:\\ - die wijzen meestal naar de Pi en
    worden elders al via een ander mechanisme gecontroleerd)."""
    pad = pad.replace("/", "\\")
    if pad.startswith("\\\\"):
        delen = pad.split("\\")
        if len(delen) >= 3:
            return delen[2]
    return None


def _genormaliseerd_voor_vergelijking(pad: str) -> str:
    """Maakt een pad vergelijkbaar ongeacht / vs \\ en hoofdletters
    (Windows-paden zijn niet hoofdlettergevoelig)."""
    return os.path.normpath(pad.replace("/", "\\")).lower()


def doel_zit_in_bron(bron_pad: str, doel_pad: str) -> bool:
    """True als het doelpad gelijk is aan, of een (sub)map is van, de
    bron zelf. Dit is een GEVAARLIJKE configuratie, geen kwestie van
    smaak: je vraagt dan om een map te kopieren naar een plek die
    tijdens het kopieren ZELF onderdeel wordt van de map die nog
    doorzocht wordt. os.walk() ontdekt de nieuw aangemaakte doelmap
    dan als onderdeel van de bron, met onvoorspelbare en corrupte
    resultaten als gevolg (verschillende uitkomsten bij elke poging,
    afhankelijk van de volgorde waarin mappen doorlopen worden)."""
    b = _genormaliseerd_voor_vergelijking(bron_pad)
    d = _genormaliseerd_voor_vergelijking(doel_pad)
    if d == b:
        return True
    return d.startswith(b + "\\")


# ---------------------------------------------------------------
# Verbinding testen en herstellen - dezelfde paden en mechanismen
# als de rest van de suite (LanManFix, smart plug HDD aan/uit).
# ---------------------------------------------------------------

def _nas_root() -> str:
    for kandidaat in (r"C:\PiNAS",
                      os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")):
        if os.path.isdir(kandidaat):
            return os.path.abspath(kandidaat)
    return r"C:\PiNAS"


def _lees_pi_ip() -> str:
    # 9 augustus 2026: stond hier op "PiControl" - die map bestaat niet
    # (heet "Beheer"), dus cfg.read() vond nooit iets en dit las altijd
    # stil de hardcoded terugvalwaarde hieronder, ongeacht wat er echt
    # in picontrol.cfg stond.
    cfg_pad = os.path.join(_nas_root(), "Beheer", "picontrol.cfg")
    cfg = configparser.ConfigParser()
    if os.path.exists(cfg_pad):
        try:
            cfg.read(cfg_pad, encoding="utf-8")
            return cfg.get("pi", "ip", fallback="UW_PI_IP_ADRES")
        except Exception:
            pass
    return "UW_PI_IP_ADRES"


PI_IP = _lees_pi_ip()


def _run_stil(commando, timeout=60):
    """Voert een commando uit zonder zichtbaar consolevenster."""
    try:
        r = subprocess.run(
            commando, capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode == 0, (r.stdout or r.stderr or "").strip()
    except Exception as e:
        return False, str(e)


def test_verbinding(doel: str, max_acceptabele_duur: float = 5.0):
    """Test of een doelpad echt bereikbaar EN schrijfbaar is, door een
    klein bestand te schrijven en meteen terug te lezen. Geeft
    (succes: bool, detail: str, duur_seconden: float) terug."""
    testpad = os.path.join(doel, ".sync_verbindingstest.tmp")
    start = time.time()
    try:
        with open(lang_pad(testpad), "wb") as f:
            f.write(b"verbindingstest")
        with open(lang_pad(testpad), "rb") as f:
            inhoud = f.read()
        duur = time.time() - start
        try:
            os.remove(lang_pad(testpad))
        except Exception:
            pass
        if inhoud != b"verbindingstest":
            return False, "Testbestand kwam beschadigd terug", duur
        if duur > max_acceptabele_duur:
            return False, f"Verbinding traag ({duur:.1f} sec voor 15 bytes)", duur
        return True, f"OK ({duur*1000:.0f} ms)", duur
    except Exception as e:
        return False, str(e), time.time() - start


def herstelactie_lanmanfix(log_func=None):
    """Voert lanman_fix.bat uit - hetzelfde script dat Pi NAS Menu
    gebruikt bij Systeemfout 67/5. Vereist Administrator-rechten."""
    pad = os.path.join(_nas_root(), "Beheer", "lanman_fix.bat")
    if not os.path.exists(pad):
        return False, f"lanman_fix.bat niet gevonden op {pad}"
    if log_func:
        log_func("LanManFix wordt uitgevoerd (kan een UAC-melding tonen)...", "info")
    ok, output = _run_stil(["cmd", "/c", pad], timeout=120)
    return ok, output


def herstelactie_hdd_volledige_cyclus(log_func=None):
    """Zet de HDD via de smart plug volledig uit, wacht, en zet hem
    daarna weer aan met een ruime stabilisatieperiode. Bewust een
    VOLLEDIGE stroomcyclus (niet alleen remounten) - uit eigen
    ervaring bleek een korte uit/aan-wissel onvoldoende; een langere,
    bewuste cyclus herstelde de verbinding wel."""
    commando = (
        "python3 -c \""
        "import sys, time; sys.path.insert(0,'/home/pi'); "
        "from smart_plug import seagate_uit, seagate_aan; "
        "print('UITZETTEN...'); seagate_uit(); "
        "time.sleep(12); "
        "print('AANZETTEN...'); "
        "ok = seagate_aan(); "
        "print('HERSTEL_OK' if ok else 'HERSTEL_MISLUKT')\""
    )
    if log_func:
        log_func("HDD wordt via smart plug volledig uit- en aangezet "
                  "(dit duurt ongeveer 30-45 seconden)...", "info")
    ok, output = _run_stil(
        ["ssh", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no",
         "-o", "BatchMode=yes", f"pi@{PI_IP}", commando],
        timeout=90)
    gelukt = ok and "HERSTEL_OK" in output
    if gelukt:
        if log_func:
            log_func("HDD aangezet en gemount op de Pi - 15 sec extra "
                      "wachten voor stabilisatie...", "info")
        time.sleep(15)
    return gelukt, output


def herstelactie_netuse_herkoppelen(drive_letter: str, log_func=None):
    """Koppelt een Windows-schijfletter volledig los en opnieuw aan
    (dezelfde share als waar hij al op stond), zodat een vastgelopen of
    verouderde SMB-sessie wordt vervangen door een verse verbinding.

    9 augustus 2026: haalde voorheen de share-naam op met een simpele
    letter-gok (Z -> "Backup", elke andere letter -> "PiNas") - "PiNas"
    bestaat al lang niet meer als share (heet nu "Opslag"), dus die tak
    verbond een niet-Z-letter altijd met een niet-bestaande share. Nu:
    het HUIDIGE doel van de schijfletter zelf opvragen via 'net use'
    voordat hij losgekoppeld wordt, en exact diezelfde share opnieuw
    koppelen - werkt daardoor voor elke letter/share-combinatie (Y/Opslag,
    Z/Backup, H/SpiegelBackup of een toekomstige toevoeging) zonder een
    aparte, dubbele aannamelijst te hoeven bijhouden."""
    doel_unc = None
    ok0, output0 = _run_stil(["net", "use", drive_letter], timeout=10)
    if ok0:
        for regel in output0.splitlines():
            for token in regel.split():
                if token.startswith("\\\\"):
                    doel_unc = token
                    break
            if doel_unc:
                break
    if not doel_unc:
        # Kon het huidige doel niet opvragen (schijf stond al los) -
        # terugval op de bekende standaard-shares.
        naam = "Backup" if drive_letter.upper().startswith("Z") else "Opslag"
        doel_unc = f"\\\\{PI_IP}\\{naam}"
    if log_func:
        log_func(f"{drive_letter} ({doel_unc}) wordt losgekoppeld en opnieuw gekoppeld...", "info")
    _run_stil(["net", "use", drive_letter, "/delete", "/y"], timeout=15)
    time.sleep(2)
    ok, output = _run_stil(
        ["net", "use", drive_letter, doel_unc, "/persistent:yes"],
        timeout=20)
    return ok, output


def _ping(host: str, timeout_ms: int = 1500):
    ok, output = _run_stil(["ping", "-n", "1", "-w", str(timeout_ms), host], timeout=5)
    if ok and "TTL=" in output.upper():
        return True, "bereikbaar"
    return False, "geen antwoord"


# ---------------------------------------------------------------
# Systeemstatus - generiek: past zich aan op het aantal bronnen en
# doelen dat de gebruiker heeft samengesteld. Geen vaste aanname meer
# over "Pi + oud NAS-apparaat + Z:" - dat was de oude, apparaat-specifieke aanname.
# ---------------------------------------------------------------

@dataclass
class StationStatus:
    naam: str
    pad: str
    leesbaar: bool = None
    schrijfbaar: bool = None
    detail: str = ""


@dataclass
class BronStatus:
    naam: str
    bereikbaar: bool = None
    detail: str = ""


@dataclass
class SysteemStatus:
    bronnen: list = field(default_factory=list)   # lijst van BronStatus
    doelen: list = field(default_factory=list)     # lijst van StationStatus
    laatst_gecontroleerd: float = 0.0

    def alles_ok(self) -> bool:
        if not self.bronnen and not self.doelen:
            return True
        for b in self.bronnen:
            if not b.bereikbaar:
                return False
        for d in self.doelen:
            if not (d.leesbaar and d.schrijfbaar):
                return False
        return True

    def detail_tekst(self) -> str:
        details = []
        for b in self.bronnen:
            if not b.bereikbaar:
                details.append(f"{b.naam}: {b.detail}")
        for d in self.doelen:
            if not (d.leesbaar and d.schrijfbaar):
                details.append(f"{d.naam}: {d.detail}")
        if details:
            return " | ".join(details)
        if self.doelen:
            return f"Alles in orde ({self.doelen[0].detail})"
        return "Alles in orde"


def controleer_systeemstatus(engine: "SyncEngine") -> SysteemStatus:
    """Voert alle statuscontroles uit voor de bronnen/doelen van de
    gegeven engine. Bewust kort en licht gehouden (geen zware
    bestandsoperaties) zodat dit elke paar seconden herhaald kan
    worden zonder zelf belasting te veroorzaken."""
    status = SysteemStatus()
    status.laatst_gecontroleerd = time.time()

    # Altijd de Pi meenemen als bekende, vaste schakel - die is bij
    # bijna elke taak relevant (Y:/Z: lopen via de Pi).
    pi_ok, pi_detail = _ping(PI_IP)
    status.bronnen.append(BronStatus(naam="Pi", bereikbaar=pi_ok, detail=pi_detail))

    for host in engine.bron_stations():
        ok, detail = _ping(host)
        status.bronnen.append(BronStatus(naam=host, bereikbaar=ok, detail=detail))

    for station in engine.doel_stations():
        if os.path.isdir(station):
            ok, detail, _duur = test_verbinding(station)
            status.doelen.append(StationStatus(
                naam=station, pad=station, leesbaar=True,
                schrijfbaar=ok, detail=detail))
        else:
            status.doelen.append(StationStatus(
                naam=station, pad=station, leesbaar=False,
                schrijfbaar=False, detail=f"{station} niet zichtbaar in Windows"))

    return status


# ---------------------------------------------------------------
# Logbestand op schijf - schrijft ALTIJD mee, los van de UI.
# ---------------------------------------------------------------

class BestandLogger:
    def __init__(self, map_pad=None, bestandsnaam_voorvoegsel="sync"):
        if map_pad is None:
            map_pad = os.path.join(_nas_root(), "Logs")
        try:
            os.makedirs(map_pad, exist_ok=True)
        except Exception:
            map_pad = os.path.expanduser("~")
        tijdstempel = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.pad = os.path.join(map_pad, f"{bestandsnaam_voorvoegsel}_{tijdstempel}.log")
        self._vergrendeling = threading.Lock()
        try:
            with open(self.pad, "w", encoding="utf-8") as f:
                f.write(f"Sync log gestart: {datetime.datetime.now()}\n")
                f.write("=" * 70 + "\n")
        except Exception:
            pass

    def schrijf(self, tekst, niveau="info"):
        regel = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [{niveau.upper():<11}] {tekst}\n"
        with self._vergrendeling:
            try:
                with open(self.pad, "a", encoding="utf-8") as f:
                    f.write(regel)
            except Exception:
                pass


# ---------------------------------------------------------------
# Sync-engine. Praat met de buitenwereld uitsluitend via callbacks.
# ---------------------------------------------------------------

MAX_FOUTEN_OP_RIJ = 6
HERSTEL_POGINGEN_MAX = 3
PROACTIEVE_CHECK_INTERVAL = 200  # elke zoveel bestanden, proactief de verbinding testen


class SyncEngine:
    def __init__(self, taken, on_log=None, on_voortgang=None, on_pauze=None,
                 on_klaar=None, verwijder_wezen_bestanden=False):
        """
        taken: lijst van SyncTaak-objecten (bron_pad -> doel_pad).
               Elke taak mag een volledig ander doel-station hebben.
        on_log(tekst, niveau): "info" / "ok" / "fout" / "waarschuwing"
        on_voortgang(SyncVoortgang): bij elke wijziging
        on_pauze(reden) -> bool: vraagt toestemming om automatisch
                           herstel te proberen; True = doorgaan
        on_klaar(SyncVoortgang): aangeroepen zodra alles klaar is
        verwijder_wezen_bestanden: standaard False (alleen aanvullen,
                           net als de oorspronkelijke, oudere sync-tool -
                           nooit verwijderen). Op True: ECHTE sync - na het
                           aanvullen worden bestanden (en lege mappen)
                           in het doel die niet meer in de bron
                           bestaan, verwijderd. Bewust opt-in, nooit
                           de standaard - verwijderen is onomkeerbaar.
        """
        self.taken = list(taken)
        self.on_log = on_log or (lambda t, n: None)
        self.on_voortgang = on_voortgang or (lambda v: None)
        self.on_pauze = on_pauze or (lambda r: True)
        self.on_klaar = on_klaar or (lambda v: None)
        self.verwijder_wezen_bestanden = verwijder_wezen_bestanden

        self.voortgang = SyncVoortgang()
        self._stop_gevraagd = False

    def stop(self):
        self._stop_gevraagd = True

    def _log(self, tekst, niveau="info"):
        self.on_log(tekst, niveau)

    def _meld_voortgang(self):
        self.on_voortgang(self.voortgang)

    def doel_stations(self):
        """Unieke doel-stations/roots over alle taken - voor
        statuscontrole-paneel (bijv. Z:\\ en Y:\\ allebei los tonen)."""
        roots = []
        for taak in self.taken:
            r = drive_root(taak.doel_pad)
            if r not in roots:
                roots.append(r)
        return roots

    def bron_stations(self):
        """Unieke bronhosts (alleen UNC-netwerkpaden) - voor ping-
        statuscontrole. Lokale schijven/Pi-mounts leveren geen host op
        en worden hier overgeslagen."""
        hosts = []
        for taak in self.taken:
            h = host_van_pad(taak.bron_pad)
            if h and h not in hosts:
                hosts.append(h)
        return hosts

    def _test_bron_leesbaar(self, bron_pad: str, timeout_seconden: float = 8.0):
        """Test of een bron daadwerkelijk leesbaar is, niet alleen of
        het pad 'bestaat' volgens os.path.isdir (dat kan soms True
        teruggeven voor een verbinding die feitelijk al hapert)."""
        resultaat = {"ok": False, "detail": "niet getest"}

        def probeer():
            try:
                start = time.time()
                _ = os.listdir(lang_pad(bron_pad))
                duur = time.time() - start
                resultaat["ok"] = True
                resultaat["detail"] = f"reageert in {duur*1000:.0f} ms"
            except Exception as e:
                resultaat["detail"] = str(e)

        draad = threading.Thread(target=probeer, daemon=True)
        draad.start()
        draad.join(timeout=timeout_seconden)
        if draad.is_alive():
            return False, f"geen reactie binnen {timeout_seconden:.0f} sec (hangt mogelijk)"
        return resultaat["ok"], resultaat["detail"]

    # -- Fase 1: volume bepalen, MET live voortgang -------------------

    def onderzoek_bronnen(self):
        """Loopt door alle bronnen om het totale aantal bestanden en
        bytes te tellen. Test EERST de verbinding met elke bron."""
        self.voortgang.fase = "onderzoeken"
        self._meld_voortgang()
        self._log("Verbinding met bronnen wordt eerst getest...", "info")

        alle_bronnen_onbereikbaar = True
        for taak in self.taken:
            ok, detail = self._test_bron_leesbaar(taak.bron_pad)
            if ok:
                alle_bronnen_onbereikbaar = False
                self._log(f"Bron bereikbaar: {taak.bron_pad} ({detail})", "ok")
            else:
                self._log(f"WAARSCHUWING: bron NIET bereikbaar: {taak.bron_pad} -- {detail}", "fout")

        if alle_bronnen_onbereikbaar:
            self._log(
                "Geen van de bronnen is bereikbaar. Controleer dit handmatig.",
                "fout")
            self.voortgang.totaal_bestanden = 0
            self.voortgang.fase = "wachten"
            self._meld_voortgang()
            return

        self._log("Bronnen worden doorzocht om het volume te bepalen...", "info")

        totaal_bestanden = 0
        totaal_bytes = 0
        for taak in self.taken:
            if self._stop_gevraagd:
                return
            if not os.path.isdir(taak.bron_pad):
                self._log(f"Bron niet bereikbaar (overgeslagen bij telling): {taak.bron_pad}", "waarschuwing")
                continue
            self._log(f"Doorzoeken: {taak.bron_pad}", "info")
            for hoofdmap, _, bestanden in os.walk(taak.bron_pad):
                if self._stop_gevraagd:
                    return
                for naam in bestanden:
                    try:
                        volledig = os.path.join(hoofdmap, naam)
                        totaal_bytes += os.path.getsize(lang_pad(volledig))
                        totaal_bestanden += 1
                    except Exception:
                        pass
                    if totaal_bestanden % 50 == 0:
                        self.voortgang.onderzocht_bestanden = totaal_bestanden
                        self.voortgang.totaal_bytes = totaal_bytes
                        self._meld_voortgang()

        self.voortgang.totaal_bestanden = totaal_bestanden
        self.voortgang.onderzocht_bestanden = totaal_bestanden
        self.voortgang.totaal_bytes = totaal_bytes
        self.voortgang.fase = "wachten"
        self._log(f"Onderzoek klaar: {totaal_bestanden:,} bestanden, "
                   f"{formatteer_bytes(totaal_bytes)} totaal.", "ok")
        self._meld_voortgang()

    # -- Fase 2: daadwerkelijke synchronisatie ------------------------

    def start(self):
        self.voortgang.fase = "synchroniseren"
        self.voortgang.gestart_om = time.time()
        self._meld_voortgang()
        fouten_op_rij = 0
        bestanden_sinds_laatste_check = 0

        for taak in self.taken:
            if self._stop_gevraagd:
                break

            if doel_zit_in_bron(taak.bron_pad, taak.doel_pad):
                self._log(
                    f"FOUT: doel ligt binnen de bron zelf - deze taak wordt "
                    f"GEWEIGERD om corruptie te voorkomen: {taak.bron_pad} -> "
                    f"{taak.doel_pad}. Pas het doelpad aan zodat het buiten de "
                    f"bron ligt.", "fout")
                continue

            try:
                self._verwerk_taak(taak)
            except Exception as e:
                # KRITIEK: zonder deze try/except zou een onverwachte
                # fout bij EEN taak (bijv. doel-station even niet
                # bereikbaar op het moment van starten) de hele
                # synchronisatie ONOPGEMERKT laten stoppen - de
                # achtergrondthread crasht dan stil, vooral gevaarlijk
                # in een .pyw-toepassing zonder zichtbaar
                # consolevenster, waar zo'n crash gewoon nergens
                # getoond wordt. Met deze vangst gaat de log dit altijd
                # melden EN gaan de overige taken gewoon door.
                self._log(
                    f"FOUT: onverwachte fout bij taak {taak.bron_pad} -> "
                    f"{taak.doel_pad}: {e}. Deze taak is overgeslagen, de "
                    f"overige taken gaan door.", "fout")
                self.voortgang.fouten += 1
                self._meld_voortgang()
                continue

        if self.voortgang.overgeslagen_door_storing and not self._stop_gevraagd:
            self._probeer_overgeslagen_opnieuw()

        self.voortgang.fase = "klaar"
        self._meld_voortgang()
        self.on_klaar(self.voortgang)

    def _verwerk_taak(self, taak):
        """De synchronisatie van EEN taak (bron->doel). Losgetrokken
        uit start() zodat een fout hierin per taak afgevangen kan
        worden, in plaats van de hele engine te laten crashen."""
        fouten_op_rij = 0
        bestanden_sinds_laatste_check = 0

        doel_pad_root = taak.doel_pad
        self.voortgang.fase = "synchroniseren"
        os.makedirs(lang_pad(doel_pad_root), exist_ok=True)

        if not os.path.isdir(taak.bron_pad):
            self._log(f"FOUT: bron niet bereikbaar: {taak.bron_pad}", "fout")
            return

        self._log(f"--- Bron: {taak.bron_pad} -> Doel: {doel_pad_root} ---", "info")
        huidig_doel_station = drive_root(taak.doel_pad)

        for hoofdmap, _, bestanden in os.walk(taak.bron_pad):
            if self._stop_gevraagd:
                break
            for naam in bestanden:
                if self._stop_gevraagd:
                    break

                bestanden_sinds_laatste_check += 1
                if bestanden_sinds_laatste_check >= PROACTIEVE_CHECK_INTERVAL:
                    bestanden_sinds_laatste_check = 0
                    ok, detail, _duur = test_verbinding(huidig_doel_station)
                    if not ok:
                        self._log(f"Proactieve check: verbinding hapert ({detail}) "
                                  f"-- wordt vroeg opgemerkt, niet pas na meerdere "
                                  f"mislukte bestanden.", "waarschuwing")
                        if not self._pauzeer_en_herstel(huidig_doel_station):
                            self.voortgang.fase = "gepauzeerd"
                            self._meld_voortgang()
                            return
                        fouten_op_rij = 0

                bron_bestand = os.path.join(hoofdmap, naam)
                relatief = os.path.relpath(bron_bestand, taak.bron_pad)
                doel_bestand = os.path.join(doel_pad_root, relatief)

                resultaat = self._verwerk_bestand(bron_bestand, doel_bestand, relatief)
                self._verwerk_resultaat(resultaat, bron_bestand, doel_bestand)

                if resultaat.status == BestandStatus.MISLUKT:
                    fouten_op_rij += 1
                    if fouten_op_rij >= MAX_FOUTEN_OP_RIJ:
                        if self._pauzeer_en_herstel(huidig_doel_station):
                            fouten_op_rij = 0
                        else:
                            self.voortgang.fase = "gepauzeerd"
                            self._meld_voortgang()
                            return
                else:
                    fouten_op_rij = 0

        if self.verwijder_wezen_bestanden and not self._stop_gevraagd:
            self._verwijder_wezen(taak)

    def _verwijder_wezen(self, taak):
        """Verwijdert bestanden EN lege mappen in het doel die niet
        meer overeenkomen met de bron - dit maakt het een ECHTE sync
        (mirror) in plaats van alleen-aanvullen. Wordt na de
        aanvul-fase van een taak uitgevoerd, en alleen als
        verwijder_wezen_bestanden=True bewust is aangezet."""
        self._log(f"Wees-bestanden zoeken in doel (opruimfase): {taak.doel_pad} ...", "info")
        verwijderd_bestanden = 0
        verwijderd_mappen = 0

        for hoofdmap, _submappen, bestanden in os.walk(taak.doel_pad, topdown=False):
            if self._stop_gevraagd:
                break
            relatieve_map = os.path.relpath(hoofdmap, taak.doel_pad)
            bron_map = taak.bron_pad if relatieve_map == "." else os.path.join(taak.bron_pad, relatieve_map)

            for naam in bestanden:
                doel_bestand = os.path.join(hoofdmap, naam)
                bron_bestand = os.path.join(bron_map, naam)
                if not os.path.exists(lang_pad(bron_bestand)):
                    relatief = os.path.relpath(doel_bestand, taak.doel_pad)
                    try:
                        self._verwijder_bestandsattributen(doel_bestand)
                        os.remove(lang_pad(doel_bestand))
                        verwijderd_bestanden += 1
                        self.voortgang.verwijderd += 1
                        self._log(f"VERWIJDERD (niet meer in bron): {relatief}", "waarschuwing")
                    except Exception as e:
                        self._log(f"FOUT bij verwijderen wees-bestand {relatief}: {e}", "fout")

            # Lege map opruimen als de overeenkomstige bronmap niet
            # meer bestaat - alleen als de map ECHT leeg is, om nooit
            # per ongeluk iets te verwijderen wat er nog wel toe doet.
            if relatieve_map != "." and not os.path.isdir(lang_pad(bron_map)):
                try:
                    if not os.listdir(lang_pad(hoofdmap)):
                        os.rmdir(lang_pad(hoofdmap))
                        verwijderd_mappen += 1
                        self._log(f"VERWIJDERD (lege map, niet meer in bron): {relatieve_map}", "waarschuwing")
                except Exception:
                    pass

        self._meld_voortgang()
        self._log(
            f"Opruimfase klaar voor {taak.doel_pad}: {verwijderd_bestanden} "
            f"bestand(en) en {verwijderd_mappen} map(pen) verwijderd.", "ok")

    def _verwerk_resultaat(self, resultaat: SyncResultaat, bron_bestand, doel_bestand):
        if resultaat.status == BestandStatus.MISLUKT:
            self.voortgang.fouten += 1
            self.voortgang.laatste_fout = resultaat.foutmelding
            self.voortgang.overgeslagen_door_storing.append(
                (bron_bestand, doel_bestand, resultaat.relatief_pad))
            self._log(f"FOUT: {resultaat.relatief_pad} -- {resultaat.foutmelding}", "fout")
        elif resultaat.status == BestandStatus.TOEGEVOEGD:
            self.voortgang.toegevoegd += 1
            self._log(f"TOEGEVOEGD: {resultaat.relatief_pad}", "ok")
        elif resultaat.status == BestandStatus.BIJGEWERKT:
            self.voortgang.bijgewerkt += 1
            self._log(f"BIJGEWERKT: {resultaat.relatief_pad}", "ok")
        elif resultaat.status == BestandStatus.AL_AANWEZIG:
            self.voortgang.al_aanwezig += 1

        self.voortgang.verwerkt_bestanden += 1
        self.voortgang.verwerkt_bytes += resultaat.grootte
        self.voortgang.huidige_bestand = resultaat.relatief_pad
        self._meld_voortgang()

    def _probeer_overgeslagen_opnieuw(self):
        self._log(
            f"Nogmaals proberen: {len(self.voortgang.overgeslagen_door_storing)} "
            f"bestand(en) die eerder werden overgeslagen door een storing...",
            "info")
        opnieuw_te_proberen = list(self.voortgang.overgeslagen_door_storing)
        self.voortgang.overgeslagen_door_storing = []
        for bron_bestand, doel_bestand, relatief in opnieuw_te_proberen:
            if self._stop_gevraagd:
                break
            resultaat = self._verwerk_bestand(bron_bestand, doel_bestand, relatief)
            if resultaat.status == BestandStatus.MISLUKT:
                self.voortgang.overgeslagen_door_storing.append(
                    (bron_bestand, doel_bestand, relatief))
                self._log(f"NOG STEEDS MISLUKT: {relatief}", "fout")
            else:
                self.voortgang.fouten = max(0, self.voortgang.fouten - 1)
                self._log(f"HERSTELD BIJ HERHALING: {relatief}", "ok")
            self._meld_voortgang()

    def _pauzeer_en_herstel(self, doel_station: str) -> bool:
        """Na een reeks fouten op rij: pauzeert, vraagt toestemming,
        en probeert dan automatisch te herstellen met een volledige
        HDD-stroomcyclus, gevolgd door LanManFix als dat niet
        voldoende was. doel_station is het specifieke station waar de
        huidige taak naartoe schrijft - bij meerdere doelen wordt dus
        alleen het relevante station opnieuw getest."""
        self.voortgang.fase = "gepauzeerd"
        self._meld_voortgang()
        mag_door = self.on_pauze(
            f"{MAX_FOUTEN_OP_RIJ} fouten op rij -- mogelijk een verbindingsstoring "
            f"met de schijf. Automatisch herstel proberen?")
        if not mag_door:
            return False

        for poging in range(1, HERSTEL_POGINGEN_MAX + 1):
            self._log(f"--- Herstelpoging {poging} van {HERSTEL_POGINGEN_MAX} ---", "waarschuwing")
            ok, detail, duur = test_verbinding(doel_station)
            if ok:
                self._log(f"Verbinding is herstelt: {detail}", "ok")
                self.voortgang.fase = "synchroniseren"
                self._meld_voortgang()
                return True

            self._log(f"Verbinding nog niet in orde: {detail}", "fout")

            gelukt, detail = herstelactie_hdd_volledige_cyclus(log_func=self._log)
            if gelukt:
                self._log("HDD-cyclus uitgevoerd.", "ok")
            else:
                self._log(f"HDD-cyclus niet gelukt: {detail}", "fout")
                gelukt2, detail2 = herstelactie_lanmanfix(log_func=self._log)
                if gelukt2:
                    self._log("LanManFix uitgevoerd.", "ok")
                else:
                    self._log(f"LanManFix niet gelukt: {detail2}", "fout")

            ok, detail, duur = test_verbinding(doel_station)
            if ok:
                self._log(f"Verbinding is herstelt na reparatie: {detail}", "ok")
                self.voortgang.fase = "synchroniseren"
                self._meld_voortgang()
                return True

        self.voortgang.fase = "gepauzeerd"
        self._meld_voortgang()
        return False

    def _verwerk_bestand(self, bron_bestand, doel_bestand, relatief) -> SyncResultaat:
        try:
            bron_info = os.stat(lang_pad(bron_bestand))
        except Exception as e:
            return SyncResultaat(relatief, BestandStatus.MISLUKT, foutmelding=f"bron onleesbaar: {e}")

        if os.path.exists(lang_pad(doel_bestand)):
            try:
                doel_info = os.stat(lang_pad(doel_bestand))
            except Exception as e:
                return SyncResultaat(relatief, BestandStatus.MISLUKT,
                                     foutmelding=f"doel onleesbaar: {e}")

            grootte_gelijk = doel_info.st_size == bron_info.st_size
            datum_gelijk = abs(doel_info.st_mtime - bron_info.st_mtime) < 2

            if grootte_gelijk and datum_gelijk:
                return SyncResultaat(relatief, BestandStatus.AL_AANWEZIG, grootte=bron_info.st_size)

            hash_bron = bereken_md5(bron_bestand)
            hash_doel = bereken_md5(doel_bestand)
            if hash_bron and hash_doel and hash_bron == hash_doel:
                return SyncResultaat(relatief, BestandStatus.AL_AANWEZIG, grootte=bron_info.st_size)
            if hash_bron is None or hash_doel is None:
                return SyncResultaat(relatief, BestandStatus.MISLUKT,
                                     foutmelding="kon hash niet berekenen (verbinding?)")

        bestond_al = os.path.exists(lang_pad(doel_bestand))

        # Windows-systeem/verborgen-attributen (vaak op Thumbs.db, of op
        # macOS-herkomst "._"-bestanden) kunnen een gewone open(...,"wb")
        # laten falen met "Permission denied". Verwijder deze vooraf
        # als het doelbestand al bestaat.
        if bestond_al:
            self._verwijder_bestandsattributen(doel_bestand)

        try:
            doel_map = os.path.dirname(doel_bestand)
            os.makedirs(lang_pad(doel_map), exist_ok=True)
            self._schrijf_bestand(bron_bestand, doel_bestand)
            try:
                os.utime(lang_pad(doel_bestand), (bron_info.st_atime, bron_info.st_mtime))
            except Exception:
                pass
            status = BestandStatus.BIJGEWERKT if bestond_al else BestandStatus.TOEGEVOEGD
            return SyncResultaat(relatief, status, grootte=bron_info.st_size)
        except PermissionError as e:
            try:
                self._verwijder_bestandsattributen(doel_bestand)
                self._schrijf_bestand(bron_bestand, doel_bestand)
                try:
                    os.utime(lang_pad(doel_bestand), (bron_info.st_atime, bron_info.st_mtime))
                except Exception:
                    pass
                status = BestandStatus.BIJGEWERKT if bestond_al else BestandStatus.TOEGEVOEGD
                return SyncResultaat(relatief, status, grootte=bron_info.st_size)
            except Exception as e2:
                return SyncResultaat(relatief, BestandStatus.MISLUKT,
                                     foutmelding=f"Permission denied, ook na attribuut-reset: {e2}")
        except Exception as e:
            return SyncResultaat(relatief, BestandStatus.MISLUKT, foutmelding=str(e))

    def _verwijder_bestandsattributen(self, pad: str):
        """Verwijdert het Windows systeem/verborgen/alleen-lezen
        attribuut van een bestand, als dat bestand al bestaat. Negeert
        fouten stil - dit is een best-effort voorbereidende stap."""
        try:
            _run_stil(["attrib", "-r", "-s", "-h", lang_pad(pad)], timeout=10)
        except Exception:
            pass

    def _schrijf_bestand(self, bron_bestand: str, doel_bestand: str):
        with open(lang_pad(bron_bestand), "rb") as bron_f:
            with open(lang_pad(doel_bestand), "wb") as doel_f:
                while True:
                    stuk = bron_f.read(4 * 1024 * 1024)
                    if not stuk:
                        break
                    doel_f.write(stuk)
