"""
telecomm.py - Funzioni di comunicazione specializzate per controllo telescopio OPC

Uso interattivo:

      python telcomm.py [-hvV]

Dove:
      -s  Collegamento al simulatore (IP: 127.0.0.1, Port: 9753)
      -v  Modo verboso (visualizza protocollo)
      -V  Mostra versione ed esci

Il file puo essere importato come modulo.
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# pylint: disable=C0413

from opc import utils
from opc.onstepdrv import OnStepCommunicator
from opc.astro import OPC, float2ums, loc_st_now

__version__ = "3.0"
__date__ = "Marzo 2024"
__author__ = "L.Fini"

#pylint: disable=C0302

_ERRCODE = "Codice di errore"

_CODICI_STATO = {
    "n": "non in tracking",
    "N": "Non in slewing",
    "p": "Non in park, ",
    "P": "in park  ",
    "I": "in movimento verso park, ",
    "F": "park fallito",
    "R": "I dati PEC data sono stati registrati",
    "H": "in posizione home",
    "S": "PPS sincronizzato",
    "G": "Modo guida attivo",
    "f": "Errore movimento asse",
    "r": "PEC refr abilitato    ",
    "s": "su asse singolo (solo equatoriale)",
    "t": "on-track abilitato    ",
    "w": "in posizione home     ",
    "u": "Pausa in pos. home abilitata",
    "z": "cicalino abilitato",
    "a": "Inversione al meridiano automatica",
    "/": "Stato pec: ignora",
    ",": "Stato pec: prepara disposizione ",
    "~": "Stato pec: disposizione  in corso",
    ";": "Stato pec: preparazione alla registrazione",
    "^": "Stato pec: registrazione in corso",
    ".": "PEC segnala detezione indice dall'ultima chiamata",
    "E": "Montatura equatoriale  tedesca",
    "K": "Montatura equatoriale a forcella",
    "k": "Montatura altaz a forcella",
    "A": "Montatura altaz",
    "o": "lato braccio ignoto",
    "T": "lato est",
    "W": "lato ovest",
    "0": "Nessun errore",
    "1": _ERRCODE,
    "2": _ERRCODE,
    "3": _ERRCODE,
    "4": _ERRCODE,
    "5": _ERRCODE,
    "6": _ERRCODE,
    "7": _ERRCODE,
    "8": _ERRCODE,
    "9": _ERRCODE}

_CODICI_RISPOSTA = """
    0: movimento possibile
    1: oggetto sotto orizzonte
    2: oggetto non selezionato
    3: controller in standby
    4: telescopio in park
    5: movimento in atto
    6: superati limiti (MaxDec, MinDec, UnderPoleLimit, MeridianLimit)
    7: errore hardware
    8: movimento in atto
    9: errore non specificato
"""

_CODICI_TABELLE_ONSTEP = """
0: Modello di allineamento     4: Encoder
8: Data e ora                  9: Varie
E: Parametri configurazione    F: Debug
G: Ausiliari (??)              U: Stato motori step
"""

_CODICI_ONSTEP_0X = """
0x: Modello allineamento
  00:  indexAxis1  (x 3600.)
  01:  indexAxis2  (x 3600.)
  02:  altCor      (x 3600.)
  03:  azmCor      (x 3600.)
  04:  doCor       (x 3600.)
  05:  pdCor       (x 3600.)
  06:  ffCor       (x 3600.)
  07:  dfCor       (x 3600.)
  08:  tfCor       (x 3600.)
  09:  Number of stars, reset to first star
  0A:  Star  #n HA   (hms)
  0B:  Star  #n Dec  (dms)
  0C:  Mount #n HA   (hms)
  0D:  Mount #n Dec  (dms)
  0E:  Mount PierSide (and increment n)
"""

_CODICI_ONSTEP_4X = """
4x: Encoder

40: Angolo Axis1 assoluto (DMS)
40: Angolo Axis2 assoluto (DMS)
42: Angolo Axis1 assoluto in gradi
43: Angolo Axis2 assoluto in gradi
49: Variabile trackingTimerRateAxis1
"""

_CODICI_ONSTEP_8X = """
8x: Data e ora
  80:  UTC time
  81:  UTC date
"""

_CODICI_ONSTEP_9X = """
9x: Varie
  90:  pulse-guide rate
  91:  pec analog value
  92:  MaxRate
  93:  MaxRate (default)
  94:  pierSide (E, W, N:none)
  95:  autoMeridianFlip
  96:  preferred pier side  (E, W, N:none)
  97:  slew speed
  98:  Rotator mode (D: derotate, R:rotate, N:no rotator)
  99:  Max Rate (fastest/lowest)
  9A:  temperature in deg. C
  9B:  pressure in mb
  9C:  relative humidity in %
  9D:  altitude in meters
  9E:  dew point in deg. C
  9F:  internal MCU temperature in deg. C
"""

_CODICI_ONSTEP_UX = """
Ux: Stato motori step
  U1: ST(Stand Still),  OA(Open Load A), OB(Open Load B), GA(Short to Ground A),
  U2: GB(Short to Ground B), OT(Overtemperature Shutdown 150C),
      PW(Overtemperature Pre-warning 120C)
"""

_CODICI_ONSTEP_EX = """
Ex: Parametri configurazione
  E1: MaxRate
  E2: DegreesForAcceleration
  E3: BacklashTakeupRate
  E4: PerDegreeAxis1
  E5: StepsPerDegreeAxis2
  E6: StepsPerSecondAxis1
  E7: StepsPerWormRotationAxis1
  E8: PECBufferSize
  E9: minutesPastMeridianE
  EA: minutesPastMeridianW
  EB: UnderPoleLimit
  EC: Dec
  ED: MaxDec
  EE: Coordinate mode for getting and setting RA/Dec
        0 = OBSERVED_PLACE
        1 = TOPOCENTRIC (does refraction)
        2 = ASTROMETRIC_J2000
"""

_CODICI_ONSTEP_FX = """
Fn: Debug
  F0:  Debug0, true vs. target RA position
  F1:  Debug1, true vs. target Dec position
  F2:  Debug2, trackingState
  F3:  Debug3, RA refraction tracking rate
  F4:  Debug4, Dec refraction tracking rate
  F6:  Debug6, HA target position
  F7:  Debug7, Dec target position
  F8:  Debug8, HA motor position
  F9:  Debug9, Dec motor position
  FA:  DebugA, Workload
  FB:  DebugB, trackingTimerRateAxis1
  FC:  DebugC, sidereal interval  (L.F.)
  FD:  DebugD, sidereal rate  (L.F.)
  FE:  DebugE, equatorial coordinates degrees (no division by 15)
"""

_CODICI_ONSTEP_GX = """
  G0:   valueAux0/2.55
  G1:   valueAux1/2.55
  G2:   valueAux2/2.55
  G3:   valueAux3/2.55
  G4:   valueAux4/2.55
  G5:   valueAux5/2.55
  G6:   valueAux6/2.55
  G7:   valueAux7/2.55
  G8:   valueAux8/2.55
  G9:   valueAux9/2.55
  GA:   valueAux10/2.5
  GB:   valueAux11/2.55
  GC:   valueAux12/2.55
  GD:   valueAux13/2.55
  GE:   valueAux14/2.55
  GF:   valueAux15/2.55
"""

def gos_info(cset:str):
    "Mostra  tabella dei codici per interrogazioni valori OnStep"
    cset = cset.upper()
    if cset == "0":
        print(_CODICI_ONSTEP_0X)
    elif cset == "4":
        print(_CODICI_ONSTEP_4X)
    elif cset == "8":
        print(_CODICI_ONSTEP_8X)
    elif cset == "9":
        print(_CODICI_ONSTEP_9X)
    elif cset == "E":
        print(_CODICI_ONSTEP_EX)
    elif cset == "F":
        print(_CODICI_ONSTEP_FX)
    elif cset == "G":
        print(_CODICI_ONSTEP_GX)
    elif cset == "U":
        print(_CODICI_ONSTEP_UX)
    else:
        print("Seleziona tabella specifica:")
        print(_CODICI_TABELLE_ONSTEP)
    return ""

def gst_info():
    "Mostra  tabella dei codici di stato"
    print("Tabella codici di stato da comando gst")
    for schr, text in _CODICI_STATO.items():
        print(f" {schr}: {text}")
    return ""

def mvt_info():
    "Mostra  codici risposta da comando move to target"
    print("Tabella codici di risposta da comando move to")
    print()
    print(_CODICI_RISPOSTA)
    return ""

def get_version():
    "Riporta informazioni su versione"
    return f"telecomm.py - Vers. {__version__}, {__date__} by { __author__}"

class TeleCommunicator(OnStepCommunicator):              #pylint: disable=R0904
    "Gestione comunicazione con server telescopio (per uso interno OPC)"

    def get_current_ha(self, as_string=False):
        "Legge ascensione retta telescopio e calcola angolo orario (ore)"
        rah = super().get_current_rah()
        if rah is None:
            return None
        hah = (loc_st_now()-rah)%24
        if as_string:
            return float2ums(hah, as_string=True)
        return hah

    def set_ra(self, hours:float):
        "[:Sr] Imposta ascensione retta oggetto (ore)"
        if 0. <= hours < 24.:
            hrs, mins, secs = float2ums(hours, precision=4)[1:]
        else:
            raise ValueError
        return super().set_ra_o(hrs, mins, secs)

    def set_alt(self, deg:float):
        "[:Sa] Imposta altezza oggetto (gradi)"
        if -90. <= deg <= 90.:
            sign, degs, mins, secs = float2ums(deg, precision=3)
        else:
            raise ValueError
        return super().set_alt_o(sign, degs, mins, secs)

    def set_az(self, deg:float):
        "[:Sz] Imposta azimut oggetto (0..360 gradi)"
        if 0. <= deg <= 360.:
            degs, mins = float2ums(deg)[1:3]
        else:
            raise ValueError
        return super().set_az_o(degs, mins)

    def set_de(self, deg:float):
        "[:Sd] Imposta declinazione oggetto (gradi)"
        if -90. <= deg <= 90.:
            sign, degs, mins, secs = float2ums(deg, precision=4)
        else:
            raise ValueError
        return super().set_de_o(sign, degs, mins, secs)

    def set_lat(self, deg):
        "[:St] Imposta latitudine locale (gradi)"
        sign, degs, mins = float2ums(deg)[:3]
        return super().set_lat_o(sign, degs, mins)

    def set_lon(self, deg):
        "[:Sg] Imposta longitudine locale (gradi)"
        sign, degs, mins = float2ums(deg)[:3]
        return super().set_lon_o(sign, degs, mins)

    def set_date(self):
        "[:SC] Imposta data da clock del PC"
        ttt = list(time.localtime())
        ttt[8] = 0                # elimina ora legale
        tt0 = time.mktime(tuple(ttt))
        ttt = time.localtime(tt0)
        return super().set_date_o(ttt[0]-2000, ttt[1], ttt[2])

    def set_tsid(self):
        "[:SS] Imposta tempo sidereo da clock PC"
        tsidh = loc_st_now()
        hhh, mmm, sss = float2ums(tsidh)[1:]
        return super().set_tsid_o(hhh, mmm, sss)

    def set_time(self):
        "[:SL + :SG] Imposta tempo telescopio da clock del PC"
        tm0 = time.time()
        ltime = time.localtime(tm0)
        if ltime.tm_isdst:
            tm0 -= 3600
            ltime = time.localtime(tm0)
        gmto = time.timezone/3600.
        ret1 = super().set_ltime_o(*ltime[3:6])
        ret2 = super().set_uoff_o(gmto)
        try:
            ret = ret1+ret2
        except TypeError:
            self._errmsg = f"Invalid return ({str(ret1)}+{str(ret2)})"
            ret = None
        return ret

    def opc_init(self):
        "Invia comandi di inizializzazione per telescopio OPC"
        ret1 = self.set_lat(OPC.lat_deg)
        ret2 = self.set_lon(-OPC.lon_deg)  # Convenzione OnStep !!!
        ret3 = self.set_time()
        ret4 = self.set_date()
        try:
            ret = ret1+ret2+ret3+ret4
        except TypeError:
            ret = None
        return ret

########################################################
# Classe per il supporto del modo interattivo

def _getddmmss(args):
    "[dd [mm [ss]]]"
    if not args:
        return None
    value = float(args[0])
    sign = 1 if value >= 0 else -1
    value = abs(value)
    if len(args) >= 2:
        value += float(args[1])/60.
    if len(args) >= 3:
        value += float(args[2])/3600.
    return value*sign

def _getint(args):
    "[nnnn]"
    if args:
        return int(args[0])
    return None

def _getfloat(args):
    "[n.nnn]"
    if args:
        return float(args[0])
    return None

def _getword(args):
    "[aaaa]"
    if args:
        return args[0]
    return None

def _noargs(*_unused):
    " "
    return None

def _print_cmd(cmdict):
    "Visualizza comandi in elenco"
    keys = list(cmdict.keys())
    keys.sort()
    for key in keys:
        print(f"   {key:3s}: {cmdict[key][0].__doc__} {cmdict[key][1].__doc__}")

def _myexit():
    "Termina programma"
    sys.exit()

class _Executor:                     # pylint: disable=C0103
    "Esecuzione comandi interattivi"
    def __init__(self, config, verbose):
        dcom = TeleCommunicator(config["tel_ip"], config["tel_port"])
        self._verbose = verbose
#                    codice   funzione      convers.argom.
        self.lxcmd = {"f1+": (dcom.foc1_move_in, _noargs),
                      "f2+": (dcom.foc2_move_in, _noargs),
                      "f1-": (dcom.foc1_move_out, _noargs),
                      "f2-": (dcom.foc2_move_out, _noargs),
                      "f1a": (dcom.foc1_get_act, _noargs),
                      "f2a": (dcom.foc2_get_act, _noargs),
                      "f1b": (dcom.foc1_set_abs, _getint),
                      "f2b": (dcom.foc2_set_abs, _getint),
                      "f1f": (dcom.foc1_set_fast, _noargs),
                      "f2f": (dcom.foc2_set_fast, _noargs),
                      "f1i": (dcom.foc1_get_min, _noargs),
                      "f2i": (dcom.foc2_get_min, _noargs),
                      "f1l": (dcom.foc1_set_slow, _noargs),
                      "f2l": (dcom.foc2_set_slow, _noargs),
                      "f1m": (dcom.foc1_get_max, _noargs),
                      "f2m": (dcom.foc2_get_max, _noargs),
                      "f1p": (dcom.foc1_get_pos, _noargs),
                      "f2p": (dcom.foc2_get_pos, _noargs),
                      "f1q": (dcom.foc1_stop, _noargs),
                      "f2q": (dcom.foc2_stop, _noargs),
                      "f1r": (dcom.foc1_set_rel, _getint),
                      "f2r": (dcom.foc2_set_rel, _getint),
                      "f1s": (dcom.foc1_sel, _noargs),
                      "f2s": (dcom.foc2_sel, _noargs),
                      "f1t": (dcom.foc1_get_stat, _noargs),
                      "f2t": (dcom.foc2_get_stat, _noargs),
                      "f1v": (dcom.foc1_set_speed, _getint),
                      "f2v": (dcom.foc2_set_speed, _getint),
                      "f1z": (dcom.foc1_move_zero, _noargs),
                      "f2z": (dcom.foc2_move_zero, _noargs),
                      "gad": (dcom.get_antib_dec, _noargs),
                      "gar": (dcom.get_antib_ra, _noargs),
                      "gat": (dcom.get_alt, _noargs),
                      "gda": (dcom.get_date, _noargs),
                      "gdt": (dcom.get_current_de, _noargs),
                      "gdo": (dcom.get_target_de, _noargs),
                      "gfd": (dcom.get_fmwdate, _noargs),
                      "gfi": (dcom.get_fmwnumb, _noargs),
                      "gfn": (dcom.get_fmwname, _noargs),
                      "gft": (dcom.get_fmwtime, _noargs),
                      "ggm": (dcom.get_genmsg, _noargs),
                      "gla": (dcom.get_lat, _noargs),
                      "gli": (dcom.get_hlim, _noargs),
                      "glo": (dcom.get_lon, _noargs),
                      "glt": (dcom.get_ltime, _noargs),
                      "glb": (dcom.get_pside, _noargs),
                      "glh": (dcom.get_olim, _noargs),
                      "gmo": (dcom.get_db, _noargs),
                      "gro": (dcom.get_target_ra, _noargs),
                      "grt": (dcom.get_current_ra, _noargs),
                      "gsm": (dcom.get_mstat, _noargs),
                      "gst": (self._gst_print, _noargs),
                      "gtf": (dcom.get_timefmt, _noargs),
                      "gtr": (dcom.get_trate, _noargs),
                      "gts": (dcom.get_tsid, _noargs),
                      "guo": (dcom.get_utcoffset, _noargs),
                      "gzt": (dcom.get_az, _noargs),
                      "hdo": (dcom.get_target_deh, _noargs),
                      "hdt": (dcom.get_current_deh, _noargs),
                      "hom": (dcom.goto_home, _noargs),
                      "hro": (dcom.get_target_rah, _noargs),
                      "hrt": (dcom.get_current_rah, _noargs),
                      "mve": (dcom.move_east, _noargs),
                      "mvo": (dcom.move_west, _noargs),
                      "mvn": (dcom.move_north, _noargs),
                      "mvs": (dcom.move_south, _noargs),
                      "mvp": (dcom.move_target_e, _noargs),
                      "mvt": (dcom.move_target, _noargs),
                      "par": (dcom.park, _noargs),
                      "pge": (dcom.pulse_guide_east, _getint),
                      "pgo": (dcom.pulse_guide_west, _getint),
                      "pgn": (dcom.pulse_guide_north, _getint),
                      "pgs": (dcom.pulse_guide_south, _getint),
                      "rcc": (dcom.rot_cclkwise, _noargs),
                      "rct": (dcom.rot_setcont, _noargs),
                      "rcw": (dcom.rot_clkwise, _noargs),
                      "rdi": (dcom.rot_disable, _noargs),
                      "ren": (dcom.rot_enable, _noargs),
                      "rge": (dcom.rot_getpos, _noargs),
                      "rho": (dcom.rot_gohome, _noargs),
                      "rpa": (dcom.rot_topar, _noargs),
                      "rrv": (dcom.rot_reverse, _noargs),
                      "rsh": (dcom.rot_sethome, _noargs),
                      "rsi": (dcom.rot_setincr, _getint),
                      "rsp": (dcom.rot_setpos, _getddmmss),
                      "s+":  (dcom.sid_clock_incr, _noargs),
                      "s-":  (dcom.sid_clock_decr, _noargs),
                      "sad": (dcom.set_antib_dec, _getint),
                      "sar": (dcom.set_antib_ra, _getint),
                      "sde": (dcom.set_slew_dec, _getfloat),
                      "sha": (dcom.set_slew_ha, _getfloat),
                      "sho": (dcom.reset_home, _noargs),
                      "sla": (dcom.set_lat, _getddmmss),
                      "slv": (dcom.set_slew, _getword),
                      "spa": (dcom.set_park, _noargs),
                      "sre": (dcom.sid_clock_reset, _noargs),
                      "stp": (dcom.stop, _noargs),
                      "ste": (dcom.stop_east, _noargs),
                      "sti": (dcom.set_time, _noargs),
                      "sto": (dcom.stop_west, _noargs),
                      "stn": (dcom.stop_north, _noargs),
                      "sts": (dcom.stop_south, _noargs),
                      "sda": (dcom.set_date, _noargs),
                      "sdo": (dcom.set_de, _getddmmss),
                      "sal": (dcom.set_alt, _getddmmss),
                      "saz": (dcom.set_az, _getddmmss),
                      "smn": (dcom.set_min_alt, _getint),
                      "smx": (dcom.set_max_alt, _getint),
                      "slo": (dcom.set_lon, _getddmmss),
                      "sro": (dcom.set_ra, _getddmmss),
                      "std": (dcom.set_tsid, _noargs),
                      "syn": (dcom.sync_radec, _noargs),
                      "syt": (dcom.sync_taradec, _noargs),
                      "trs": (dcom.set_trate, _getfloat),
                      "tof": (dcom.track_off, _noargs),
                      "ton": (dcom.track_on, _noargs),
                      "tot": (dcom.ontrack, _noargs),
                      "trn": (dcom.track_refrac_on, _noargs),
                      "trf": (dcom.track_refrac_off, _noargs),
                      "tki": (dcom.track_king, _noargs),
                      "tlu": (dcom.track_lunar, _noargs),
                      "tsi": (dcom.track_sidereal, _noargs),
                      "tso": (dcom.track_solar, _noargs),
                      "tr1": (dcom.track_one, _noargs),
                      "tr2": (dcom.track_two, _noargs),
                      "unp": (dcom.unpark, _noargs),
                     }
        self.spcmd = {"gos": (dcom.get_onstep_value, _getword),
                      "x00": (dcom.set_onstep_00, _getint),
                      "x01": (dcom.set_onstep_01, _getint),
                      "x02": (dcom.set_onstep_02, _getint),
                      "x03": (dcom.set_onstep_03, _getint),
                      "x04": (dcom.set_onstep_04, _getint),
                      "x05": (dcom.set_onstep_05, _getint),
                      "x06": (dcom.set_onstep_06, _getint),
                      "x07": (dcom.set_onstep_07, _getint),
                      "x08": (dcom.set_onstep_08, _getint),
                      "x92": (dcom.set_onstep_92, _getint),
                      "x93": (dcom.set_onstep_93, _getint),
                      "x95": (dcom.set_onstep_95, _getint),
                      "x96": (dcom.set_onstep_96, _getword),
                      "x97": (dcom.set_onstep_97, _getint),
                      "x98": (dcom.set_onstep_98, _getint),
                      "x99": (dcom.set_onstep_99, _getint),
                      "xe9": (dcom.set_onstep_e9, _getint),
                      "xea": (dcom.set_onstep_ea, _getint),
                     }
        self.hkcmd = {"q": (_myexit, _noargs),
                      "?": (self.search, _getword),
                      "gos?": (gos_info, _getword),
                      "gha": (dcom.get_current_ha, _noargs),
                      "gst?": (gst_info, _noargs),
                      "mvt?": (mvt_info, _noargs),
                      "ini": (dcom.opc_init, _noargs),
                      "cmd": (dcom.gen_cmd, _getword),
                      "fmw": (dcom.get_firmware, _noargs),
                      "ver": (self._toggle_verbose, _noargs),
                     }
        self._dcom = dcom

    def _gst_print(self):
        "[:GU] Mostra stato telescopio. Per tabella stati: gst?"
        stat = self._dcom.get_status()
        if stat:
            for stchr in stat:
                print(f" {stchr}: {_CODICI_STATO.get(stchr, '???')}")
        return stat

    def _toggle_verbose(self):
        "Abilita/Disabilita modo verboso"
        self._verbose = not self._verbose
        return ""

    def search(self, word=""):
        "Cerca comando contenente la parola"
        wsc = word.lower()
        allc = self.lxcmd.copy()
        allc.update(self.hkcmd)
        allc.update(self.spcmd)
        found = {}
        for key, value in allc.items():
            descr = value[0].__doc__
            if descr and wsc in descr.lower():
                found[key] = value
        _print_cmd(found)
        return ""

    def execute(self, command):
        "Esegue comando interattivo"
        cmdw = command.split()
        if not cmdw:
            return "Nessun comando"
        cmd0 = cmdw[0][:4].lower()
        clist = self.lxcmd
        cmd_spec = clist.get(cmd0)
        showc = True
        if not cmd_spec:
            clist = self.hkcmd
            cmd_spec = clist.get(cmd0)
            showc = False
        if not cmd_spec:
            clist = self.spcmd
            cmd_spec = clist.get(cmd0)
            showc = True
        if cmd_spec:
            the_arg = cmd_spec[1](cmdw[1:])
            if the_arg is None:
                try:
                    ret = cmd_spec[0]()
                except TypeError:
                    return "Argomento mancante"
            else:
                ret = cmd_spec[0](the_arg)
            if self._verbose and showc:
                print("CMD -", self._dcom.last_command())
                print("RPL -", self._dcom.last_reply())
                error = self._dcom.last_error()
                if error:
                    print("ERR -", error)
            if ret is None:
                ret = "Errore comando: "+self._dcom.last_error()
        else:
            ret = "Comando sconosciuto!"
        return ret

    def usage(self):
        "Visualizza elenco comandi"
        print("\nComandi LX200 standard:")
        _print_cmd(self.lxcmd)
        print("\nComandi speciali:")
        _print_cmd(self.spcmd)
        print("\nComandi aggiuntivi:")
        _print_cmd(self.hkcmd)

def main():
    "Invio comandi da console e test"
    if '-h' in sys.argv:
        print(get_version())
        print(__doc__)
        sys.exit()

    if '-V' in sys.argv:
        print(get_version())
        sys.exit()

    if '-s' in sys.argv:
        config = {"tel_ip": "127.0.0.1",
                  "tel_port": 9753,
                  "debug": 1}
    else:
        config = utils.get_config()
    if not config:
        print("File di configurazione inesistente!")
        print("occorre definirlo con:")
        print()
        print("   python cupola.py -c")
        sys.exit()

    verbose = ("-v" in sys.argv)

    exe = _Executor(config, verbose)

    while True:
        answ = input("\nComando (invio per aiuto): ")
        if answ:
            ret = exe.execute(answ)
            print(ret)
        else:
            exe.usage()

if __name__ == "__main__":
    try:
        import readline    # pylint: disable=W0611
    except ImportError:
        pass
    main()
