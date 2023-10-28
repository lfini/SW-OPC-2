"""Funzioni di comunicazione per controllo telescopio OPC

Implementa i comandi LX200 specifici di OnStep.

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
import re
import socket
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# pylint: disable=C0413
from opc import utils
from opc.astro import OPC, float2ums, loc_st_now

__version__ = "2.9"
__date__ = "Febbraio 2023"
__author__ = "L.Fini, L.Naponiello"

#pylint: disable=C0302

                                  # Comandi definiti
                                  # Comandi di preset
_SET_ALT = ":Sa%s%02d*%02d'%02d#" # Set altezza target (+-dd,mm,ss)
_SET_AZ = ":Sz%03d*%02d"          # Set azimuth target (ddd,mm)
_SET_DATE = ":SC%02d/%02d/%02d#"  # Set data
_SET_DEC = ":Sd%s%02d*%02d:%02d.%03d#" # Set declinazione target (+dd,mm,ss.sss)
_SET_LAT = ":St%s%02d*%02d#"      # Set latitudine del luogo (+dd, mm)
_SET_LON = ":Sg%s%03d*%02d#"      # Set longitudine del luogo (+ddd, mm)
_SET_MNAP = ":Sh+%02d#"           # Set minima altezza raggiungibile (+dd)
_SET_MNAN = ":Sh-%02d#"           # Set minima altezza raggiungibile (-dd)
_SET_MAXA = ":So%02d#"            # Set massima altezza raggiungibile (dd)
_SET_LTIME = ":SL%02d:%02d:%02d#" # Set ora locale: hh, mm, ss
_SET_ONSTEP_V = ":SX%s,%s#"       # Set valore OnStep
_SET_RA = ":Sr%02d:%02d:%02d.%03d#"# Set ascensione retta dell'oggetto target (hh,mm,ss.sss)
_SET_TRATE = ":ST%08.5f#"         # Set freq. di tracking (formato da commenti nel codice)
_SET_TSID = ":SS%02d:%02d:%02d#"  # Set tempo sidereo: hh, mm, ss
_SET_UOFF = ":SG%s%04.1f#"        # Set UTC offset (UTC = LocalTime+Offset)

                           # Comandi set slew rate
_SET_SLEW1 = ":RA%.1f#"    # Imposta rate asse 1 a dd.d gradi/sec
_SET_SLEW2 = ":RE%.1f#"    # Imposta rate asse 2 a dd.d gradi/sec
_SET_SLEW = ":R%s#"        # Imposta slew: 0-9 / G=2, C=5, M=6, F=7, S=8

_SIDCLK_INCR = ":T+#"      # Incr. master sidereal clock di 0.02 Hz (stored in EEPROM)
_SIDCLK_DECR = ":T-#"      # Decr. master sidereal clock di 0.02 Hz (stored in EEPROM)
_SIDCLK_RESET = ":TR#"     # Reset master sidereal clock

_TRACK_ON = ":Te#"         # Abilita tracking
_TRACK_OFF = ":Td#"        # Disabilita tracking
_ONTRACK = ":To#"          # Abilita "On Track"
_TRACKR_ENB = ":Tr#"       # Abilita tracking con rifrazione
_TRACKR_DIS = ":Tn#"       # Disabilita tracking con rifrazione
                           # return: 0 failure, 1 success
_TRACK_KING = ":TK#"       # Tracking rate = king (include rifrazione)
_TRACK_LUNAR = ":TL#"      # Tracking rate = lunar
_TRACK_SIDER = ":TQ#"      # Tracking rate = sidereal
_TRACK_SOLAR = ":TS#"      # Tracking rate = solar
                           # return:  None
_TRACK_ONE = ":T1#"        # Track singolo asse (Disabilita Dec tracking)
_TRACK_TWO = ":T2#"        # Track due assi

                           # Comandi di movimento
_MOVE_TO = ":MS#"          # Muove a target definito
_MOVE_TO_E = ":MN#"        # Muove a target definito, ma ad est del Pier

_MOVE_DIR_E = ":Me#"       # Muove ad est
_MOVE_DIR_W = ":Mw#"       # Muove ad ovest
_MOVE_DIR_N = ":Mn#"       # Muove a nord
_MOVE_DIR_S = ":Ms#"       # Muove a sud

_STOP_DIR_E = ":Qe#"        # Stop movimento ad est
_STOP_DIR_W = ":Qw#"        # Stop movimento ad ovest
_STOP_DIR_N = ":Qn#"        # Stop movimento a nord
_STOP_DIR_S = ":Qs#"        # Stop movimento a sud

_STOP = ":Q#"              # Stop telescopio

_PULSE_M = ":Mg%s%d#"      # Pulse move              < TBD

_SET_HOME = ":hF#"         # Reset telescope at Home position.
_GOTO_HOME = ":hC#"        # Move telescope to Home position.
_PARK = ":hP#"             # Park telescope
_SET_PARK = ":hQ#"         # Park telescope
_UNPARK = ":hR#"           # Unpark telescope

_SYNC_RADEC = ":CS#"       # Sync with current RA/DEC (no reply)
_SYNC_TARADEC = ":CM#"     # Sync with target RA/DEC (no reply)

#Comandi set/get antibacklash

_SET_ANTIB_DEC = ":$BD%03d#"   # Set Dec Antibacklash
_SET_ANTIB_RA = ":$BR%03d#"    # Set RA Antibacklash

_GET_ANTIB_DEC = ":%BD#"       # Get Dec Antibacklash
_GET_ANTIB_RA = ":%BR#"        # Get RA Antibacklash


                           # Comandi informativi
_GET_AZ = ":GZ#"           # Get telescope azimuth
_GET_ALT = ":GA#"          # Get telescope altitude
_GET_CUR_DE = ":GD#"       # Get current declination
_GET_CUR_DEH = ":GDe#"     # Get current declination (High precision)
_GET_CUR_RA = ":GR#"       # Get current right ascension
_GET_CUR_RAH = ":GRa#"     # Get current right ascension (High precision)
_GET_DB = ":D#"            # Get distance bar
_GET_DATE = ":GC#"         # Get date
_GET_HLIM = ":Gh"          # Get horizont limit
_GET_OVER = ":Go"          # Get overhead limit
_GET_FMWNAME = ":GVP#"     # Get Firmware name
_GET_FMWDATE = ":GVD#"     # Get Firmware Date (mmm dd yyyy)
_GET_GENMSG = ":GVM#"      # Get general message (aaaaa)
_GET_FMWNUMB = ":GVN#"     # Get Firmware version (d.dc)
_GET_FMWTIME = ":GVT#"     # Get Firmware time (hh:mm:ss)
_GET_OSVALUE = ":GX..#"    # Get OnStep Value
_GET_LTIME = ":GL#"        # Get local time from telescope
_GET_LON = ":Gg#"          # Get telescope longitude
_GET_LAT = ":Gt#"          # Get telescope latitude
_GET_MSTAT = ":GW#"        # Get telescope mount status
_GET_PSIDE = ":Gm#"        # Get pier side
_GET_TSID = ":GS#"         # Get Sidereal time
_GET_TRATE = ":GT#"        # Get tracking rate
_GET_STAT = ":GU#"         # Get global status
                           # N: not slewing     H: at home position
                           # P: parked          p: not parked
                           # F: park failed     I: park in progress
                           # R: PEC recorded    G: Guiding
                           # S: GPS PPS synced
_GET_TAR_DE = ":Gd#"       # Get target declination
_GET_TAR_DEH = ":Gde#"     # Get target declination (High precision)
_GET_TAR_RA = ":Gr#"       # Get target right ascension
_GET_TAR_RAH = ":Gra#"     # Get target right ascension (High precision)
_GET_TFMT = ":Gc#"         # Get current time format (ret: 24#)
_GET_UOFF = ":GG#"         # Get UTC offset time

# Comandi fuocheggatore.
# Nota: gli stessi commandi valgono per il
#       fuocheggiatore 1 se iniziano per "F"
#       e il fuocheggiatore 2 se iniziano per "f"

_FOC_SELECT1 = ":FA1#"  # Seleziona fuocheggiatore 1
_FOC_SELECT2 = ":FA2#"  # Seleziona fuocheggiatore 2

_FOC_MOVEIN1 = ":F+#"   # Muove fuocheggiatore 1 verso obiettivo
_FOC_MOVEIN2 = ":f+#"   # Muove fuocheggiatore 2 verso obiettivo

_FOC_MOVEOUT1 = ":F-#"  # Muove fuocheggiatore via da obiettivo
_FOC_MOVEOUT2 = ":f-#"  # Muove fuocheggiatore via da obiettivo

_FOC_STOP1 = ":FQ#"     # Stop movimento fuocheggiatore
_FOC_STOP2 = ":fQ#"     # Stop movimento fuocheggiatore
_FOC_ZERO1 = ":FZ#"     # Muove in posizione zero
_FOC_ZERO2 = ":fZ#"     # Muove in posizione zero
_FOC_FAST1 = ":FF#"     # Imposta movimento veloce
_FOC_FAST2 = ":fF#"     # Imposta movimento veloce
_FOC_SETR = ":%sR%04d#" # Imposta posizione relativa (micron)
_FOC_SLOW1 = ":FS#"     # Imposta movimento lento
_FOC_SLOW2 = ":fS#"     # Imposta movimento lento
_FOC_SETA = ":%sS%04d#" # Imposta posizione assoluta (micron)
_FOC_RATE = ":%s%1d"    # Imposta velocità (1,2,3,4)

_GET_FOC_ACT1 = ":FA#"  # Fuocheggiatore attivo (ret: 0/1)
_GET_FOC_ACT2 = ":fA#"  # Fuocheggiatore attivo (ret: 0/1)

_GET_FOC_POS1 = ":FG#"  # Legge posizione corrente fuocheggiatore (+-ddd)
_GET_FOC_POS2 = ":fG#"  # Legge posizione corrente fuocheggiatore (+-ddd)

_GET_FOC_MIN1 = ":FI#"  # Legge posizione minima fuocheggiatore
_GET_FOC_MIN2 = ":fI#"  # Legge posizione minima fuocheggiatore

_GET_FOC_MAX1 = ":FM#"  # Legge posizione massima fuocheggiatore
_GET_FOC_MAX2 = ":fM#"  # Legge posizione massima fuocheggiatore

_GET_FOC_STAT1 = ":FT#" # Legge stato corrente fuocheggiatore (M: moving, S: stop)
_GET_FOC_STAT2 = ":fT#" # Legge stato corrente fuocheggiatore (M: moving, S: stop)

_ROT_SETCONT = ":rc#"   # Imposta movimento continuo
_ROT_ENABLE = ":r+#"    # Abilita rotatore
_ROT_DISABLE = ":r-#"   # Disabilita rotatore
_ROT_TOPAR = ":rP#"     # Muove rotatore ad angolo parallattico
_ROT_REVERS = ":rR#"    # Inverte direzione rotatore
_ROT_SETHOME = ":rF#"   # Reset rotatore a posizione home
_ROT_GOHOME = ":rC#"    # Muove rotatore a posizione home
_ROT_CLKWISE = ":r>#"   # Muove rotatore in senso orario come da comando
_ROT_CCLKWISE = ":r<#"  # Muove rotatore in senso antiorario come da incremento
_ROT_SETINCR = ":r%d#"  # Preset incremento per movimento rotatore (1,2,3)
_ROT_SETPOS = ":rS%s%03d*%02d'%02d#" # Set posizione rotatore (+-dd, mm, ss)

_ROT_GET = ":rG#"       # Legge posizione rotatore (gradi)

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

def get_version():
    "Riporta informazioni su versione"
    return f"telecomm.py - Vers. {__version__}, {__date__} by { __author__}"

_DDMMSS_RE = re.compile("[+-]?(\\d{2,3})[*:](\\d{2})[':](\\d{2}(\\.\\d+)?)")
_DDMM_RE = re.compile("[+-]?(\\d{2,3})[*:](\\d{2})")


class TeleCommunicator:              #pylint: disable=R0904
    "Gestione comunicazione con server telescopio (LX200 specifico OnStep)"

    def __init__(self, ipadr, port, timeout=0.5):
        """Inizializzazione TeleCommunicator:

ipaddr:  Indirizzo IP telescopio (str)
port:    Port IP telescopio (int)
timeout: Timeout comunicazione in secondi (float)
"""
        self.connected = False
        self.ipadr = ipadr
        self.port = port
        self.timeout = timeout
        self._errmsg = ""
        self._command = ""
        self._reply = ""

    def _float_decode(self, the_str):
        "Decodifica stringa x.xxxx"
        try:
            val = float(the_str)
        except ValueError:
            val = float('nan')
            self._errmsg = "Errore decodifica valore float"
        return val

    def _ddmmss_decode(self, the_str, with_sign=False):
        "Decodifica stringa DD.MM.SS. Riporta float"
        if the_str is None:
            self._errmsg = "Valore mancante"
            return None
        try:
            flds = _DDMMSS_RE.match(the_str)
            if with_sign:
                sgn = -1 if the_str[0] == "-" else 1
            else:
                sgn = 1
            ddd = int(flds.group(1))
            mmm = int(flds.group(2))
            sss = float(flds.group(3))
        except Exception as excp:               # pylint: disable=W0703
            self._errmsg = f"Errore decodifica valore dd.mm.ss [str: {the_str}] ({str(excp)})"
            return None
        return (ddd+mmm/60.+sss/3600.)*sgn

    def _ddmm_decode(self, the_str, with_sign=False):
        "Decodifica stringa DD.MM. Riporta float"
        if the_str is None:
            self._errmsg = "Valore mancante"
            return None
        if with_sign:
            sgn = -1 if the_str[0] == "-" else 1
        else:
            sgn = 1
        flds = _DDMM_RE.match(the_str)
        if not flds:
            self._errmsg = "Errore decodifica valore dd.mm"
            return None
        ddd = int(flds.group(1))
        mmm = int(flds.group(2))
        return (ddd+mmm/60.)*sgn

    def _send_cmd(self, command, expected):
        """
Invio comandi. expected == True: prevista risposta.

Possibili valori di ritorno:
    '':      Nessuna risposta attesa
    'xxxx':  Stringa di ritorno da OnStep
    1/0:     Successo/fallimento da OnStep
    None:    Errore comunicazione"""
        self._errmsg = ""
        self._reply = ""
        self._command = command
        skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        skt.settimeout(self.timeout)
        try:
            skt.connect((self.ipadr, self.port))
        except IOError:
            self._errmsg = "Connection timeout"
            return None
        try:
            skt.sendall(command.encode("ascii"))
        except socket.timeout:
            skt.close()
            self._errmsg = "Send timeout"
            return None
        ret = b""
        repl = None
        if expected:
            try:
                while True:
                    nchr = skt.recv(1)
                    if not nchr:
                        break
                    if nchr == b"#":
                        break
                    ret += nchr
            except (socket.timeout, IOError):
                self._errmsg = "Risposta senza terminatore #"
            finally:
                skt.close()
                repl = ret.decode("ascii")
                self._reply = repl
        else:
            repl = ""
        return repl

    def last_command(self):
        "Riporta ultimo comando LX200"
        return self._command

    def last_reply(self):
        "Riporta ultima risposta LX200"
        return self._reply

    def last_error(self):
        "Riporta ultimo messaggio di errore"
        return self._errmsg

    def set_ra(self, hours):
        "[:Sr] Imposta ascensione retta oggetto (ore)"
        if 0. <= hours < 24.:
            _unused, hrs, mins, secs = float2ums(hours, precision=4)
            isec = int(secs)
            rest = int((secs-isec)*10000)
            cmd = _SET_RA % (hrs, mins, isec, rest)
            ret = self._send_cmd(cmd, 1)
        else:
            raise ValueError
        return ret

    def set_alt(self, deg):
        "[:Sa] Imposta altezza oggetto (gradi)"
        if -90. <= deg <= 90.:
            sign, degs, mins, secs = float2ums(deg, precision=3)
            sign = "+" if sign >= 0 else "-"
            cmd = _SET_ALT%(sign, degs, mins, secs)
            ret = self._send_cmd(cmd, 1)
        else:
            raise ValueError
        return ret

    def set_az(self, deg):
        "[:Sz] Imposta azimut oggetto (0..360 gradi)"
        if 0. <= deg <= 360.:
            cmd = _SET_AZ%float2ums(deg)[1:3]
            ret = self._send_cmd(cmd, 1)
        else:
            raise ValueError
        return ret

    def set_de(self, deg):
        "[:Sd] Imposta declinazione oggetto (gradi)"
        if -90. <= deg <= 90.:
            sign, degs, mins, secs = float2ums(deg, precision=4)
            sign = "+" if sign >= 0 else "-"
            isec = int(secs)
            rest = int((secs-isec)*10000)
            cmd = _SET_DEC%(sign, degs, mins, isec, rest)
            ret = self._send_cmd(cmd, 1)
        else:
            raise ValueError
        return ret

    def set_max_alt(self, deg):
        "[:So] Imposta altezza massima raggiungibile (60..90 gradi)"
        if 60 <= deg <= 90:
            cmd = _SET_MAXA%deg
            ret = self._send_cmd(cmd, 1)
        else:
            raise ValueError
        return ret

    def set_min_alt(self, deg):
        "[:Sh] Imposta altezza minima raggiungibile (-30..30 gradi)"
        if -30 <= deg <= 30:
            if deg >= 0:
                cmd = _SET_MNAP%(deg)
            else:
                cmd = _SET_MNAN%(-deg)
            ret = self._send_cmd(cmd, 1)
        else:
            raise ValueError
        return ret

    def set_trate(self, rate):
        "[:ST] Imposta frequenza di tracking (Hz)"
        return self._send_cmd(_SET_TRATE%rate, True)

    def set_lat(self, deg):
        "[:St] Imposta latitudine locale (gradi)"
        sign, degs, mins, _unused = float2ums(deg)
        sign = "+" if sign >= 0 else "-"
        cmd = _SET_LAT%(sign, degs, mins)
        return self._send_cmd(cmd, 1)

    def set_lon(self, deg):
        "[:Sg] Imposta longitudine locale (gradi)"
        sign, degs, mins, _unused = float2ums(deg)
        sign = "+" if sign >= 0 else "-"
        cmd = _SET_LON%(sign, degs, mins)
        return self._send_cmd(cmd, 1)

    def set_date(self):
        "[:SC] Imposta data da clock del PC"
        ttt = list(time.localtime())
        ttt[8] = 0                # elimina ora legale
        tt0 = time.mktime(tuple(ttt))
        ttt = time.localtime(tt0)
        cmd = _SET_DATE%(ttt[1], ttt[2], ttt[0]-2000)
        return self._send_cmd(cmd, 1)

    def set_tsid(self):
        "[:SS] Imposta tempo sidereo da clock PC"
        tsidh = loc_st_now()
        return self._send_cmd(_SET_TSID%float2ums(tsidh)[1:], False)

    def set_time(self):
        "[:SL + :SG] Imposta tempo telescopio da clock del PC"
        tm0 = time.time()
        ltime = time.localtime(tm0)
        if ltime.tm_isdst:
            tm0 -= 3600
            ltime = time.localtime(tm0)
        gmto = time.timezone/3600.
        cmd1 = _SET_LTIME%tuple(ltime[3:6])
        if gmto < 0.0:
            sgn = "-"
            gmto = -gmto
        else:
            sgn = "+"
        cmd2 = _SET_UOFF%(sgn, gmto)
        ret1 = self._send_cmd(cmd1, 1)
        ret2 = self._send_cmd(cmd2, 1)
        try:
            ret = ret1+ret2
        except TypeError:
            self._errmsg = f"Invalid return ({str(ret1)}+{str(ret2)})"
            ret = None
        return ret

    def set_slew_ha(self, degsec):
        "[:RA] Imposta velocità slew asse orario in gradi/sec"
        cmd = _SET_SLEW1%degsec
        return self._send_cmd(cmd, False)

    def set_slew_dec(self, degsec):
        "[:RE] Imposta velocità slew asse declinazione in gradi/sec"
        cmd = _SET_SLEW2%degsec
        return self._send_cmd(cmd, False)

    def set_slew(self, spec):
        "[:R] Imposta velocità a G:Guide, C:Center, M:Move, F:Fast, S:Slew o 0-9"
        cmd = _SET_SLEW%spec
        return self._send_cmd(cmd, False)

    def _set_os_par(self, code, str_val):
        "[:SX] Imposta parametro on step generico"
        cmd = _SET_ONSTEP_V%(code, str_val)
        return self._send_cmd(cmd, True)

    def set_onstep_00(self, value):
        "[:SX00] Imposta OnStep indexAxis1 [integer]"
        return self._set_os_par("00", f"{value:d}")

    def set_onstep_01(self, value):
        "[:SX01] Imposta OnStep indexAxis2 [integer]"
        return self._set_os_par("01", f"{value:d}")

    def set_onstep_02(self, value):
        "[:SX02] Imposta OnStep altCor [integer]"
        return self._set_os_par("02", f"{value:d}")

    def set_onstep_03(self, value):
        "[:SX03] Imposta OnStep azmCor [integer]"
        return self._set_os_par("03", f"{value:d}")

    def set_onstep_04(self, value):
        "[:SX04] Imposta OnStep doCor [integer]"
        return self._set_os_par("04", f"{value:d}")

    def set_onstep_05(self, value):
        "[:SX05] Imposta OnStep pdCor [integer]"
        return self._set_os_par("05", f"{value:d}")

    def set_onstep_06(self, value):
        "[:SX06] Imposta OnStep dfCor [integer]"
        return self._set_os_par("06", f"{value:d}")

    def set_onstep_07(self, value):
        "[:SX07] Imposta OnStep ffCor (inutilizz. per montatura equ) [integer]"
        return self._set_os_par("07", f"{value:d}")

    def set_onstep_08(self, value):
        "[:SX08] Imposta OnStep tfCor [integer]"
        return self._set_os_par("08", f"{value:d}")

    def set_onstep_92(self, value):
        "[:SX92] Imposta OnStep MaxRate (max. accelerazione) [integer]"
        return self._set_os_par("92", f"{value:d}")

    def set_onstep_93(self, value):
        "[:SX93] Imposta OnStep MaxRate preset (max. accelerazione) [1-5: 200%,150%,100%,75%,50%]"
        if  0 < value < 6:
            return self._set_os_par("93", f"{value:d}")
        return "0"

    def set_onstep_95(self, value):
        "[:SX95] Imposta OnStep autoMeridianFlip [0: disabilita, 1: abilita]"
        if value not in (0, 1):
            return "0"
        return self._set_os_par("95", f"{value:d}")

    def set_onstep_96(self, value):
        "[:SX96] Imposta OnStep preferredPierSide [E, W, B (best)]"
        try:
            value = value.upper()
        except:                           #pylint: disable=W0702
            return "0"
        if value not in ("EWB"):
            return "0"
        return self._set_os_par("96", value)

    def set_onstep_97(self, value):
        "[:SX97] Imposta OnStep cicalino [0: disabilita, 1: abilita]"
        if value not in (0, 1):
            return "0"
        return self._set_os_par("97", f"{value:d}")

    def set_onstep_98(self, value):
        "[:SX98] Imposta pausa a HOME all'inversione meridiano [0: disabilita, 1: abilita]"
        if value not in (0, 1):
            return "0"
        return self._set_os_par("98", f"{value:d}")

    def set_onstep_99(self, value):
        "[:SX99] Imposta OnStep continua dopo pausa a HOME [0: disabilita, 1: abilita]"
        if value not in (0, 1):
            return "0"
        return self._set_os_par("99", f"{value:d}")

    def set_onstep_e9(self, value):
        "[:SXe9] Imposta OnStep minuti dopo il meridiano EST [integer]"
        return self._set_os_par("E9", f"{value:d}")

    def set_onstep_ea(self, value):
        "[:SXea] Imposta OnStep minuti dopo il meridiano OVEST [integer]"
        return self._set_os_par("EA", f"{value:d}")

    def sync_radec(self):
        "[:CS] Sincronizza con coordinate oggetto target"
        return self._send_cmd(_SYNC_RADEC, False)

    def sync_taradec(self):
        "[:CM] Sincronizza con coordinate oggetto corrente dal database"
        return self._send_cmd(_SYNC_TARADEC, False)

    def move_target(self):
        "[:MS] Muove telescopio al target definito. Risposta: vedi mvt?"
        return self._send_cmd(_MOVE_TO, True)

    def move_target_e(self):
        "[:MN] Muove telescopio al target definito (ma ad est del supporto). Risposta: vedi mvt?"
        return self._send_cmd(_MOVE_TO_E, True)

    def move_east(self):
        "[:Me] Muove telescopio direz. est"
        return self._send_cmd(_MOVE_DIR_E, False)

    def move_west(self):
        "[:Mw] Muove telescopio direz. ovest"
        return self._send_cmd(_MOVE_DIR_W, False)

    def move_north(self):
        "[:Mn] Muove telescopio direz. nord"
        return self._send_cmd(_MOVE_DIR_N, False)

    def move_south(self):
        "[:Ms] Muove telescopio direz. sud"
        return self._send_cmd(_MOVE_DIR_S, False)

    def stop(self):
        "[:Q] Ferma movimento telescopio"
        return self._send_cmd(_STOP, False)

    def stop_east(self):
        "[:Se] Ferma movimento in direzione est"
        return self._send_cmd(_STOP_DIR_E, False)

    def stop_west(self):
        "[:Sw] Ferma movimento in direzione ovest"
        return self._send_cmd(_STOP_DIR_W, False)

    def stop_north(self):
        "[:Sn] Ferma movimento in direzione nord"
        return self._send_cmd(_STOP_DIR_N, False)

    def stop_south(self):
        "[:Ss] Ferma movimento in direzione sud"
        return self._send_cmd(_STOP_DIR_S, False)

    def pulse_guide_east(self, dtime):
        "[:Mge] Movimento ad impulso in direzione est (dtime=20-16399)"
        if dtime < 20 or dtime > 16399:
            self._errmsg = "Value error"
            return None
        return self._send_cmd(_PULSE_M%("e", dtime), False)

    def pulse_guide_west(self, dtime):
        "[:Mgw] Movimento ad impulso in direzione ovest (dtime=20-16399)"
        if dtime < 20 or dtime > 16399:
            self._errmsg = "Value error"
            return None
        return self._send_cmd(_PULSE_M%("w", dtime), False)

    def pulse_guide_south(self, dtime):
        "[:Mgs] Movimento ad impulso in direzione sud (dtime=20-16399)"
        if dtime < 20 or dtime > 16399:
            self._errmsg = "Value error"
            return None
        return self._send_cmd(_PULSE_M%("s", dtime), False)

    def pulse_guide_north(self, dtime):
        "[:Mgn] Movimento ad impulso in direzione nord (dtime=20-16399)"
        if dtime < 20 or dtime > 16399:
            self._errmsg = "Value error"
            return None
        return self._send_cmd(_PULSE_M%("n", dtime), False)

    def get_alt(self, as_string=False):
        "[:GA] Legge altezza telescopio (gradi)"
        ret = self._send_cmd(_GET_ALT, True)
        if as_string:
            return ret
        return self._ddmmss_decode(ret, with_sign=True)

    def get_antib_dec(self):
        "[:%BD] Legge valore antibacklash declinazione (steps/arcsec)"
        ret = self._send_cmd(_GET_ANTIB_DEC, True)
        if ret:
            return int(ret)
        return None

    def get_antib_ra(self):
        "[:%BR] Legge valore antibacklash ascensione retta (steps/arcsec)"
        ret = self._send_cmd(_GET_ANTIB_RA, True)
        if ret:
            return int(ret)
        return None

    def get_az(self, as_string=False):
        "[:GZ] Legge azimuth telescopio (gradi)"
        ret = self._send_cmd(_GET_AZ, True)
        if as_string:
            return ret
        return self._ddmmss_decode(ret)

    def get_current_de(self, as_string=False):
        "[:GD] Legge declinazione telescopio (gradi)"
        ret = self._send_cmd(_GET_CUR_DE, True)
        if as_string:
            return ret
        return self._ddmmss_decode(ret, with_sign=True)

    def get_current_deh(self, as_string=False):
        "[:GDe] Legge declinazione telescopio (gradi, alta precisione)"
        ret = self._send_cmd(_GET_CUR_DEH, True)
        if as_string:
            return ret
        return self._ddmmss_decode(ret, with_sign=True)

    def get_current_ha(self, as_string=False):
        "Legge ascensione retta telescopio e calcola angolo orario (ore)"
        ret = self._send_cmd(_GET_CUR_RAH, True)
        rah = self._ddmmss_decode(ret)
        if rah is None:
            return None
        hah = (loc_st_now()-rah)%24
        if as_string:
            return float2ums(hah)
        return hah

    def get_current_ra(self, as_string=False):
        "[:GR] Legge ascensione retta telescopio (ore)"
        ret = self._send_cmd(_GET_CUR_RA, True)
        if as_string:
            return ret
        return self._ddmmss_decode(ret)

    def get_current_rah(self, as_string=False):
        "[:GRa] Legge ascensione retta telescopio (ore, alta precisione)"
        ret = self._send_cmd(_GET_CUR_RAH, True)
        if as_string:
            return ret
        return self._ddmmss_decode(ret)

    def get_date(self):
        "[:GC] Legge data impostata al telescopio"
        return self._send_cmd(_GET_DATE, True)

    def get_db(self):
        "[:D] Legge stato movimento (riporta '0x7f' se in moto)"
        return self._send_cmd(_GET_DB, True)

    def foc1_get_act(self):
        "[:FA] Legge stato attività fuocheggiatore (1:attivo, 0:disattivo)"
        return self._send_cmd(_GET_FOC_ACT1, True)

    def foc2_get_act(self):
        "[:fA] Legge stato attività fuocheggiatore 2 (1:attivo, 0:disattivo)"
        return self._send_cmd(_GET_FOC_ACT2, True)

    def foc1_get_min(self):
        "Legge posizione minima fuocheggiatore 1 (micron)"
        return int(self._send_cmd(_GET_FOC_MIN1, True))

    def foc2_get_min(self):
        "Legge posizione minima fuocheggiatore 2 (micron)"
        return int(self._send_cmd(_GET_FOC_MIN2, True))

    def foc1_get_max(self):
        "[:FM] Legge posizione massima fuocheggiatore 1 (micron)"
        ret = self._send_cmd(_GET_FOC_MAX1, True)
        if ret:
            try:
                val = int(ret)
            except ValueError:
                val = None
                self._errmsg = "Errore decodifica valore intero"
            return val
        return ret

    def foc2_get_max(self):
        "[:fM] Legge posizione massima fuocheggiatore 2 (micron)"
        ret = self._send_cmd(_GET_FOC_MAX2, True)
        if ret:
            try:
                val = int(ret)
            except ValueError:
                val = None
                self._errmsg = "Errore decodifica valore intero"
            return val
        return ret

    def foc1_get_pos(self):
        "[:FG] Legge posizione corrente fuocheggiatore 1 (micron)"
        ret = self._send_cmd(_GET_FOC_POS1, True)
        if ret:
            return int(ret)
        return None

    def foc2_get_pos(self):
        "[:fG] Legge posizione corrente fuocheggiatore 2 (micron)"
        ret = self._send_cmd(_GET_FOC_POS2, True)
        if ret:
            return int(ret)
        return None

    def foc1_get_stat(self):
        "[:FT] Legge stato di moto fuocheggiatore 1 (M: in movimento, S: fermo)"
        return self._send_cmd(_GET_FOC_STAT1, True)

    def foc2_get_stat(self):
        "[:fT] Legge stato di moto fuocheggiatore 2 (M: in movimento, S: fermo)"
        return self._send_cmd(_GET_FOC_STAT2, True)

    def get_hlim(self):
        "[:Gh] Legge minima altezza sull'orizzonte (gradi)"
        ret = self._send_cmd(_GET_HLIM, True)
        return ret

    def get_olim(self):
        "[:Go] Legge massima altezza sull'orizzonte (gradi)"
        ret = self._send_cmd(_GET_OVER, True)
        return ret

    def get_lon(self, as_string=False):
        "[:Gg] Legge longitudine del sito (gradi)"
        ret = self._send_cmd(_GET_LON, True)
        if as_string:
            return ret
        return self._ddmm_decode(ret, with_sign=True)

    def get_lat(self, as_string=False):
        "[:Gt] Legge latitudine del sito (gradi)"
        ret = self._send_cmd(_GET_LAT, True)
        if as_string:
            return ret
        return self._ddmm_decode(ret, with_sign=True)

    def get_fmwname(self):
        "[:GVP] Legge nome firmware"
        return self._send_cmd(_GET_FMWNAME, True)

    def get_fmwdate(self):
        "[:GWD] Legge data firmware"
        return self._send_cmd(_GET_FMWDATE, True)

    def get_genmsg(self):
        "[:GVM] Legge informazioni su firmware"
        return self._send_cmd(_GET_GENMSG, True)

    def get_fmwnumb(self):
        "[:GVN] Legge versione firmware"
        return self._send_cmd(_GET_FMWNUMB, True)

    def get_fmwtime(self):
        "[:GVT] Legge ora firmware"
        return self._send_cmd(_GET_FMWTIME, True)

    def get_firmware(self):
        "Legge informazioni complete su firmware"
        return (self._send_cmd(_GET_FMWNAME, True),
                self._send_cmd(_GET_FMWNUMB, True),
                self._send_cmd(_GET_FMWDATE, True),
                self._send_cmd(_GET_FMWTIME, True))

    def get_onstep_value(self, value):
        "[:GX..] Legge valore parametro OnStep (per tabella: gos?)"
        if len(value) < 2:
            value = "0"+value
        cmd = _GET_OSVALUE.replace("..", value[:2].upper())
        ret = self._send_cmd(cmd, True)
        return ret

    def get_ltime(self, as_string=False):
        "[:GL] Legge tempo locale (ore)"
        ret = self._send_cmd(_GET_LTIME, True)
        if as_string:
            return ret
        return self._ddmmss_decode(ret)

    def get_mstat(self):
        "[:GW] Legge stato allineamento montatura"
        return self._send_cmd(_GET_MSTAT, True)

    def get_pside(self):
        "[:Gm] Legge lato di posizione del braccio (E,W, N:non.disp.)"
        return self._send_cmd(_GET_PSIDE, True)

    def get_status(self):
        "[:GU] Legge stato telescopio. Per tabella stati: gst?"
        ret = self._send_cmd(_GET_STAT, True)
        return ret

    def get_target_de(self, as_string=False):
        "[:Gd] Legge declinazione oggetto (gradi)"
        ret = self._send_cmd(_GET_TAR_DE, True)
        if as_string:
            return ret
        return self._ddmmss_decode(ret, with_sign=True)

    def get_target_deh(self, as_string=False):
        "[:Gde] Legge declinazione oggetto (gradi, alta precisione)"
        ret = self._send_cmd(_GET_TAR_DEH, True)
        if as_string:
            return ret
        return self._ddmmss_decode(ret, with_sign=True)

    def get_target_ra(self, as_string=False):
        "[:Gr] Legge ascensione retta oggetto (ore)"
        ret = self._send_cmd(_GET_TAR_RA, True)
        if as_string:
            return ret
        return self._ddmmss_decode(ret)

    def get_target_rah(self, as_string=False):
        "[:Gra] Legge ascensione retta oggetto (ore, alta precisione)"
        ret = self._send_cmd(_GET_TAR_RAH, True)
        if as_string:
            return ret
        return self._ddmmss_decode(ret)

    def get_timefmt(self):
        "[:Gc] Legge formato ora"
        return self._send_cmd(_GET_TFMT, True)

    def get_trate(self):
        "[:GT] Legge frequenza di tracking (Hz)"
        ret = self._send_cmd(_GET_TRATE, True)
        if ret is not None:
            ret = self._float_decode(ret)
        return ret

    def get_tsid(self, as_string=False):
        "[:GS] Legge tempo sidereo (ore)"
        ret = self._send_cmd(_GET_TSID, True)
        if as_string:
            return ret
        if ret is None:
            return ret
        return self._ddmmss_decode(ret)

    def get_utcoffset(self):
        "[:GG] Legge offset UTC (ore)"
        ret = self._send_cmd(_GET_UOFF, True)
        return self._float_decode(ret)

    def foc1_sel(self):
        "[:FA1] Seleziona fuocheggiatore 1"
        return self._send_cmd(_FOC_SELECT1, True)

    def foc2_sel(self):
        "[:FA2] Seleziona fuocheggiatore 2"
        return self._send_cmd(_FOC_SELECT2, True)

    def foc1_move_in(self):
        "[:F+] Muove fuocheggiatore 1 verso obiettivo"
        return self._send_cmd(_FOC_MOVEIN1, False)

    def foc2_move_in(self):
        "[:f+] Muove fuocheggiatore 2 verso obiettivo"
        return self._send_cmd(_FOC_MOVEIN2, False)

    def foc1_move_out(self):
        "[:F-] Muove fuocheggiatore 1 via da obiettivo"
        return self._send_cmd(_FOC_MOVEOUT1, False)

    def foc2_move_out(self):
        "[:f-] Muove fuocheggiatore 2 via da obiettivo"
        return self._send_cmd(_FOC_MOVEOUT2, False)

    def foc1_stop(self):
        "[:FQ] Ferma movimento fuocheggiatore 1"
        return self._send_cmd(_FOC_STOP1, False)

    def foc2_stop(self):
        "[:fQ] Ferma movimento fuocheggiatore 2"
        return self._send_cmd(_FOC_STOP2, False)

    def foc1_move_zero(self):
        "[:FZ] Muove fuocheggiatore 1 in posizione zero"
        return self._send_cmd(_FOC_ZERO1, False)

    def foc2_move_zero(self):
        "[:fZ] Muove fuocheggiatore 2 in posizione zero"
        return self._send_cmd(_FOC_ZERO2, False)

    def foc1_set_fast(self):
        "[:FF] Imposta velocità alta fuocheggiatore 1"
        return self._send_cmd(_FOC_FAST1, False)

    def foc2_set_fast(self):
        "[:fF] Imposta velocità alta fuocheggiatore 2"
        return self._send_cmd(_FOC_FAST2, False)

    def foc1_set_slow(self):
        "[:FS] Imposta velocità bassa fuocheggiatore 1"
        return self._send_cmd(_FOC_SLOW1, False)

    def foc2_set_slow(self):
        "[:fS] Imposta velocità bassa fuocheggiatore 2"
        return self._send_cmd(_FOC_SLOW2, False)

    def _set_foc_speed(self, rate, focuser):
        "Imposta velocità (1,2,3,4) fuocheggiatore 1/2"
        if rate > 4:
            rate = 4
        elif rate < 1:
            rate = 1
        cmd = _FOC_RATE%(focuser, rate)
        return self._send_cmd(cmd, False)

    def foc1_set_speed(self, rate):
        "[:F.] Imposta velocità (1,2,3,4) fuocheggiatore 1"
        return self._set_foc_speed(rate, "F")

    def foc2_set_speed(self, rate):
        "[:f.] Imposta velocità (1,2,3,4) fuocheggiatore 2"
        return self._set_foc_speed(rate, "f")

    def foc1_set_rel(self, pos):
        "[:FR] Imposta posizione relativa fuocheggiatore 1 (micron)"
        cmd = _FOC_SETR%("F", pos)
        return self._send_cmd(cmd, False)

    def foc2_set_rel(self, pos):
        "[:fR] Imposta posizione relativa fuocheggiatore 2 (micron)"
        cmd = _FOC_SETR%("f", pos)
        return self._send_cmd(cmd, False)

    def foc1_set_abs(self, pos):
        "[:FS....] Imposta posizione assoluta fuocheggiatore 1 (micron)"
        cmd = _FOC_SETA%("F", pos)
        return self._send_cmd(cmd, False)

    def foc2_set_abs(self, pos):
        "[fS....] Imposta posizione assoulta fuocheggiatore 2 (micron)"
        cmd = _FOC_SETA%("f", pos)
        return self._send_cmd(cmd, False)

    def rot_disable(self):
        "[:r-] Disabilita rotatore"
        return self._send_cmd(_ROT_DISABLE, False)

    def rot_enable(self):
        "[:r+] Abilita rotatore"
        return self._send_cmd(_ROT_ENABLE, False)

    def rot_setcont(self):
        "[:rc] Imposta movimento continuo per rotatore"
        return self._send_cmd(_ROT_SETCONT, False)

    def rot_topar(self):
        "[:rP] Muove rotatore ad angolo parallattico"
        return self._send_cmd(_ROT_TOPAR, False)

    def rot_reverse(self):
        "[:rR] Inverte direzione movimento rotatore"
        return self._send_cmd(_ROT_REVERS, False)

    def rot_sethome(self):
        "[:rF] Imposta posizione corrente rotatore come HOME"
        return self._send_cmd(_ROT_SETHOME, False)

    def rot_gohome(self):
        "[:rC] Muove rotatore a posizione home"
        return self._send_cmd(_ROT_GOHOME, False)

    def rot_clkwise(self):
        "[:r>] Muove rotatore in senso orario (incremento prefissato)"
        return self._send_cmd(_ROT_CLKWISE, False)

    def rot_cclkwise(self):
        "[:r<] Muove rotatore in senso antiorario (incremento prefissato)"
        return self._send_cmd(_ROT_CCLKWISE, False)

    def rot_setincr(self, incr):
        "[:r.] Imposta incremento per movimento rotatore (1:1 grado, 2:5 gradi, 3: 10 gradi)"
        if incr < 1:
            incr = 1
        elif incr > 3:
            incr = 3
        cmd = _ROT_SETINCR%incr
        return self._send_cmd(cmd, False)

    def rot_setpos(self, deg):
        "[:rS...] Imposta posizione rotatore (gradi)"
        sign, degs, mins, secs = float2ums(deg, precision=3)
        sign = "+" if sign >= 0 else "-"
        cmd = _ROT_SETPOS%(sign, degs, mins, secs)
        return self._send_cmd(cmd, 1)

    def rot_getpos(self):
        "[:rG] Legge posizione rotatore (gradi)"
        ret = self._send_cmd(_ROT_GET, True)
        return self._ddmm_decode(ret)

    def set_antib_dec(self, stpar):
        "[:$BD] Imposta valore anti backlash declinazione (steps per arcsec)"
        return self._send_cmd(_SET_ANTIB_DEC%stpar, True)

    def set_antib_ra(self, stpar):
        "[:$BR] Imposta valore anti backlash ascensione retta (steps per arcsec)"
        return self._send_cmd(_SET_ANTIB_RA%stpar, True)

    def track_on(self):
        "[:Te] Abilita tracking"
        return self._send_cmd(_TRACK_ON, True)

    def track_off(self):
        "[:Td] Disabilita tracking"
        return self._send_cmd(_TRACK_OFF, True)

    def ontrack(self):
        "[:To] Abilita modo On Track"
        return self._send_cmd(_ONTRACK, True)

    def track_refrac_on(self):
        "[:Tr] Abilita correzione per rifrazione su tracking"
        return self._send_cmd(_TRACKR_ENB, True)

    def track_refrac_off(self):
        "[:Tn] Disabilita correzione per rifrazione su tracking"
        return self._send_cmd(_TRACKR_DIS, True)

    def sid_clock_incr(self):
        "[:T+] Incrementa frequenza clock sidereo di 0.02 Hz"
        return self._send_cmd(_SIDCLK_INCR, False)

    def sid_clock_decr(self):
        "[:T-] Decrementa frequenza clock sidereo di 0.02 Hz"
        return self._send_cmd(_SIDCLK_DECR, False)

    def track_king(self):
        "[:TK] Imposta frequenza di tracking king"
        return self._send_cmd(_TRACK_KING, False)

    def track_lunar(self):
        "[:TL] Imposta frequenza di tracking lunare"
        return self._send_cmd(_TRACK_LUNAR, False)

    def track_sidereal(self):
        "[:TQ] Imposta frequenza di tracking siderea"
        return self._send_cmd(_TRACK_SIDER, False)

    def track_solar(self):
        "[:TS] Imposta frequenza di tracking solare"
        return self._send_cmd(_TRACK_SOLAR, False)

    def track_one(self):
        "[:T1] Imposta tracking su singolo asse (disab. DEC tracking)"
        return self._send_cmd(_TRACK_ONE, False)

    def track_two(self):
        "[:T2] Imposta tracking sui due assi"
        return self._send_cmd(_TRACK_TWO, False)

    def sid_clock_reset(self):
        "[:TR] Riporta frequenza clock sidereo a valore iniziale"
        return self._send_cmd(_SIDCLK_RESET, False)

    def park(self):
        "[:hP] Mette telescopio a riposo (PARK)"
        return self._send_cmd(_PARK, True)

    def reset_home(self):
        "[:hF] Imposta posizione HOME"
        return self._send_cmd(_SET_HOME, False)

    def goto_home(self):
        "[:hC] Muove telescopio a posizione HOME"
        return self._send_cmd(_GOTO_HOME, False)

    def set_park(self):
        "[:hQ] Imposta posizione PARK"
        return self._send_cmd(_SET_PARK, False)

    def unpark(self):
        "[:hR] Mette telescopio operativo (UNPARK)"
        return self._send_cmd(_UNPARK, True)

    def gen_cmd(self, text):
        "Invia comando generico (:, # possono essere omessi)"
        if not text.startswith(":"):
            text = ":"+text
        if not text.endswith("#"):
            text += "#"
        return self._send_cmd(text, True)

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

def _gos_info(cset=""):
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

def _gst_info():
    "Mostra  tabella dei codici di stato"
    print("Tabella codici di stato da comando gst")
    for schr, text in _CODICI_STATO.items():
        print(f" {schr}: {text}")
    return ""


def _mvt_info():
    "Mostra  codici risposta da comando move to target"
    print("Tabella codici di risposta da comando move to")
    print()
    print(_CODICI_RISPOSTA)
    return ""


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
                      "gos?": (_gos_info, _getword),
                      "gha": (dcom.get_current_ha, _noargs),
                      "gst?": (_gst_info, _noargs),
                      "mvt?": (_mvt_info, _noargs),
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
