"""
telsamp.py - support modo slave per dome_ctrl.py

Uso per test:

    python telsamp.py [-s]

where:
    -s:  usa simulatore telescopio
"""

################################################################
# Questo modulo interroga il telescopio tramite il relativo
# protocollo LX200 per avere la posizione (RA, DEC) e calcola
# l'azimuth della cupola per interpolazione da tabelle

# Le tabelle vengono generate dalla procedura tel_model.py
# e sono contenute nei files: dometab_e.p e dometab_w.p
#
# I due file devono trovarsi sulla stessa directory che contiene
# il modulo python
################################################################

import sys
import os
import re
import math
import socket
import time
import signal
import pickle
import threading

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# pylint: disable=C0413
from opc import utils

__version__ = "1.1"
__author__ = "Luca Fini"
__date__ = "Marzo 2023"

OPC_LON_RAD = 0.19627197066038454  # OPC longitude (radians)

                           # Comandi LX 200
_GET_CUR_DEH = ":GDe#"     # Get current declination (High precision)
_GET_CUR_RAH = ":GRa#"     # Get current right ascension (High precision)
_GET_PSIDE = ":Gm#"        # Get pier side

RAD_TO_HOUR = 3.8197186342054885
_DDMMSS_RE = re.compile("[+-]?(\\d{2,3})[*:](\\d{2})[':](\\d{2}(\\.\\d+)?)")

FLOAT_NAN = float('nan')
TIMEOUT = 1    # Timeout per interrogazione LX200
TEL_PERIOD = 2 # Periodo interrogazione LX200

THIS_DIR = os.path.dirname(__file__)

class _GB:                       # pylint: disable=R0903
    debug = False
    interp_e = None
    interp_w = None
    tel_ip = None
    tel_port = None
    tel_de = FLOAT_NAN
    tel_ra = FLOAT_NAN
    tel_side = ''
    lock = threading.Lock()
    logger = None
    longitude = None
    loop = False
    test_loop = False
    thread = None
    telsamp = None

def _debug(msg):
    'mostra messaggio di debug'
    if _GB.debug:
        print('TS DBG>', msg)

class Logger:
    'Gestione log'
    def __init__(self, logger):
        self._logger = logger

    def info(self, msg):
        'Messaggio informativo'
        _debug('Info: '+msg)
        if self._logger:
            self._logger.info(msg)

    def error(self, msg):
        'Messaggio di errore'
        _debug('Err: '+msg)
        if self._logger:
            self._logger.error(msg)


def _ddmmss_decode(the_str, with_sign=False):
    "Decodifica stringa DD.MM.SS. Riporta float"
    if the_str is None:
        return FLOAT_NAN
    flds = _DDMMSS_RE.match(the_str)
    if with_sign:
        sgn = -1 if the_str[0] == "-" else 1
    else:
        sgn = 1
    ddd = int(flds.group(1))
    mmm = int(flds.group(2))
    sss = float(flds.group(3))
    return (ddd+mmm/60.+sss/3600.)*sgn

def _send_cmd(command):
    """
    Invio comandi.
    """
    skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    skt.settimeout(TIMEOUT)
    try:
        skt.connect((_GB.tel_ip, _GB.tel_port))
    except IOError as exc:
        _GB.logger.error(f'TelSamp - connect exception: {exc}')
        return None
    try:
        skt.sendall(command.encode("ascii"))
    except socket.timeout:
        _GB.logger.error(f'TelSamp - send timeout [cmd:{command}]')
        skt.close()
        return None
    ret = b""
    try:
        while True:
            nchr = skt.recv(1)
            if not nchr:
                break
            if nchr == b"#":
                break
            ret += nchr
    except (socket.timeout, IOError):
        _GB.logger.error(f'TelSamp - receive timeout [buffer:{ret}]')
    skt.close()
    return ret.decode("ascii")

def get_current_deh():
    "[:GDe] Legge declinazione telescopio (gradi, alta precisione)"
    ret = _send_cmd(_GET_CUR_DEH)
    return _ddmmss_decode(ret, with_sign=True)

def get_current_rah():
    "[:GR] Legge ascensione retta telescopio (ore)"
    ret = _send_cmd(_GET_CUR_RAH)
    return _ddmmss_decode(ret)

def get_pside():
    "[:Gm] Legge lato di posizione del braccio (E,W, N:non.disp.)"
    return _send_cmd(_GET_PSIDE)

############################################################ calcolo tempo sidereo ###############
def jul_date(year, mon, day, hour, mins, secs, utc_offset=0):              # pylint: disable=R0913
    "Calcolo data giuliana per dato tempo civile"
    if mon <= 2:
        year -= 1
        mon += 12
    aaa = int(year/100)
    bbb = 2-aaa+int(aaa/4)
    jd0 = int(365.25*(year+4716))+int(30.6*(mon+1))+day+bbb-1524.5
    hoff = (hour+mins/60.+secs/3600.-utc_offset)/24.
    return jd0+hoff

#   tsid_grnw usa una formula semplificata con errore 0.1 sec per secolo
#   vedi: http://aa.usno.navy.mil/faq/docs/GAST.php

def tsid_grnw(year, mon, day, hour, mins, secs, utc_offset=0):              # pylint: disable=R0913
    "Calcolo tempo sidereo medio di Greenwhich"
    jd2000 = jul_date(year, mon, day, hour, mins, secs, utc_offset)-2451545.0
    gmst = (18.697374558+24.06570982441908*jd2000)%24.
    if gmst < 0:
        gmst += 24.
    return gmst

def loc_st(year, mon, day, hour, mins, secs, utc_offset=0, lon_rad=0.0):    # pylint: disable=R0913
    "Calcolo tempo sidereo locale per generico luogo"
    gmst = tsid_grnw(year, mon, day, hour, mins, secs, utc_offset)
    locst = (gmst+lon_rad*RAD_TO_HOUR)%24
    if locst < 0:
        locst += 24.
    return locst

def loc_st_now():
    "Calcolo tempo sidereo locale qui e ora"
    loct = time.localtime()
    utc_offset = -time.timezone/3600.+loct.tm_isdst
    return loc_st(loct[0], loct[1], loct[2], loct[3],
                  loct[4], loct[5], utc_offset, _GB.longitude)
####################################################### fine calcolo tempo sidereo ###############

class Interpolator:                   # pylint: disable=R0902,R0903
    """
    Interpolatore per posizione cupola

    side:   e=est / w=ovest
    """
    def __init__(self, side="e"):
        "Costruttore"
        fname = "dometab_"+side+".p"
        datafile = os.path.join(THIS_DIR, fname)
        with open(datafile, "rb") as fpt:
            table = pickle.load(fpt)
        self.data = table["DATA"]
        self.side = table["SIDE"]
        self.ha_step = table["HA_STEP"]
        self.de_min = table["DE_0"]
        self.c_de = 1./table["DE_STEP"]
        self.c_ha = 1./table["HA_STEP"]
        self.ha_grid = tuple(x*self.ha_step for x in range(len(self.data[0])))

    def interpolate(self, ha, de):           # pylint: disable=C0103
        "Trova azimuth cupola per interpolazione"
        try:
            azl = self.data[int((de-self.de_min)*self.c_de+.5)]
            haix = int(ha*self.c_ha)
            az0 = azl[haix]
            val = (az0+(azl[haix+1]-az0)*self.c_ha*(ha-self.ha_grid[haix]))%360.
        except (IndexError, ValueError):
            return -1.0
        if math.isnan(val):
            val = -1.0
        return val

_GB.interp_e = Interpolator('e')
_GB.interp_w = Interpolator('w')

def _tel_loop():
    'Loop di interrogazione telescopio (da lanciare in un Thread)'
    _GB.loop = True
    rot = 0
    sleep_time = 0.5
    n_steps = TEL_PERIOD/sleep_time
    step = 0
    _GB.logger.info('TelSamp - loop starting')
    while _GB.loop:
        if step == 0:
            if rot == 0:
                rah = get_current_rah()
                with _GB.lock:
                    _GB.tel_ra = rah
                    ded, rah, psi, hah, azh = _tel_status()
                read = 'RA  '
            elif rot == 1:
                ded = get_current_deh()
                with _GB.lock:
                    _GB.tel_de = ded
                    ded, rah, psi, hah, azh = _tel_status()
                read = 'DE  '
            elif rot == 2:
                psi = get_pside()
                with _GB.lock:
                    _GB.tel_side = psi
                    ded, rah, psi, hah, azh = _tel_status()
                read = 'Side'
            _GB.logger.info(f'TelSamp - Upd {read}: DE:{ded:.3f} '\
                            f'RA:{rah:.3f} HA:{hah:.3f} S:{psi} AZ:{azh:.1f}')
            rot = (rot+1)%3
        step = (step+1)%n_steps
        time.sleep(sleep_time)
    _GB.logger.info(f'TelSamp - thread {_GB.thread.native_id} terminated')

def _tel_status():
    'legge stato del telescopio e calcola azimut cupola (da progeggere con _GB.lock)'
    ded = _GB.tel_de
    rah = _GB.tel_ra
    psi = _GB.tel_side
    hah = (loc_st_now()-rah)%24
    if psi == 'E':
        azh = _GB.interp_e.interpolate(hah, ded)
    elif psi == 'W':
        azh = _GB.interp_w.interpolate(hah, ded)
    else:
        azh = -1.0
    return ded, rah, psi, hah, azh

#################################################### API inizio
def tel_start(logger=None, simul=False, debug=False):
    'lancia loop di interrogazione  del telescopio'
    _GB.debug = debug
    if _GB.telsamp is not None:
        _debug('already running')
        return _GB.telsamp
    config = utils.get_config(simul)
    _GB.tel_ip = config['tel_ip']
    _GB.tel_port = config['tel_port']
    _GB.longitude = config['lon']
    _GB.logger = Logger(logger)

    _GB.logger.info(f'TelSamp API: tel_start(tel_ip={_GB.tel_ip}, tel_port={_GB.tel_port})')
    _GB.thread = threading.Thread(target=_tel_loop)
    _GB.thread.start()
    count = 10
    while not _GB.thread.is_alive():
        time.sleep(0.1)
        count -= 1
    if not _GB.thread.is_alive():
        _GB.logger.error('TelSamp - thread not started')
        return None
    _GB.logger.info(f'TelSamp - thread {_GB.thread.native_id} running')
    _GB.telsamp = _TelSampler()
    return _GB.telsamp

class _TelSampler:
    'campionatore dello stato del telescopio'
    @staticmethod
    def tel_stop():
        'Termina loop'
        _GB.logger.info('TelSamp API: tel_stop()')
        _GB.loop = False
        _GB.thread.join()

    @staticmethod
    def az_from_tel():
        'calcola azimut cupola'
        with _GB.lock:
            ret = _tel_status()
        return ret[-1]

    @staticmethod
    def tel_status():              # Funzione opzionale usata dalla GUI
        'legge stato del telescopio. return: ded, rah, psi, hah, azh'
        with _GB.lock:
            return _tel_status()

#################################################### API fine

def _stoptest(*_unused):
    _GB.logger.info('TelSamp - ricevuto segnale STOP')
    _GB.test_loop = False

def main():
    "Codice di test"
    if '-h' in sys.argv:
        print(__doc__)
        sys.exit()

    tel_sim = '-s' in sys.argv

    signal.signal(2, _stoptest)
    tls = tel_start(simul=tel_sim)

    print()
    input('<invio> per iniziare (interrompi con Ctrl-C)')
    _GB.test_loop = True
    while _GB.test_loop:
        ded, rah, psi, hah = tls.tel_status()
        azh = tls.az_from_tel()
        print(f'de: {ded:.6f}, ra: {rah:.6f}, ha: {hah:.6f}, side: {psi} -> azh: {azh:.2f}')
        time.sleep(1)
    tls.tel_stop()


if __name__ == "__main__":
    main()
