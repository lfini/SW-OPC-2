"""
guide.py  Autoguida da immagini scientifiche

uso per test:

    python guide.py [-s] sci_dir sci_calib  [aux_dir, aux_calib]

Dove:
    -s:        connessione al simulatore (default: telescope)

    sci_dir    Directory per immagini principali (scientifiche)
    sci_calib  File di calibrazione principale
    aux_dir    Directory per immagini ausiliarie (cercatore)
    aux_calib  File di calibrazione ausiliario
"""

# La funzione guideloop() è strutturata per essere lanciata in un thread
# La comunicazione con il programma chiamante avviene tramite l'oggeto Comm

import sys
import os
import time
import signal
import multiprocessing as mp
import astropy.units as u
from astropy.coordinates import Angle
from astropy.io import fits
from astropy.wcs import WCS
from donuts import Donuts

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# pylint: disable=C0413
from opc.utils import get_config
from opc.telecomm import TeleCommunicator

LOOP_TIME = 0.2    # Tempo di ritardo loop principale (secondi)

HOUR_TO_DEG = 15.0 # Conversione ore->gradi

                # parametri per test standalone
SCI_TILES = 32  # Numero di "tiles" da usare nell'inizializzazione
                # di donuts sull'immagine scientifica
AUX_TILES = 32  # ... e nell'immagine ausiliaria

class BidirectionalQueue:
    'Supporto per coda bidirezionale'
    def __init__(self, in_q, out_q):
        self.in_q = in_q
        self.out_q = out_q

    def empty(self):
        'Test stato coda di ingresso'
        return self.in_q.empty()

    def get(self):
        'estrae elemento da coda di ingresso'
        return self.in_q.get()

    def put(self, what):
        'scrive elemento su coda di uscita'
        self.out_q.put(what)

class Comm:
    'Code di comunicazione'
    def __init__(self):
        self._q1 = mp.SimpleQueue()
        self._q2 = mp.SimpleQueue()

    def server_side(self):
        'da passare al lato "server"'
        return BidirectionalQueue(self._q1, self._q2)

    def client_side(self):
        'da usare dal lato "client"'
        return BidirectionalQueue(self._q2, self._q1)

class FakeQueue:
    'Simulatore di coda per test'
    def get(self):
        print('Fake GET')

    def put(self, what):
        print('Fake PUT:', what)

class GLOB:                                # pylint: disable=R0903
    "Some global variables without global"
    debug = False
    loop = True
    comm = FakeQueue()
    tel = None

def set_debug(enable):
    "Abilita/disabilita debug mode"
    GLOB.debug = bool(enable)

def tostring(adict):
    "Converte dict in stringa"
    ret = []
    for key, value in adict.items():
        if key != "WCS":
            ret.append(f"{key}: {str(value)}")
    return "{"+", ".join(ret)+"}"


def debug(*pars):
    "Show debug lines"
    if GLOB.debug:
        print("GUIDE DBG>", *pars)

FITS_EXT = (".fit", ".fits", ".FIT", ".FITS")

def last_file(dirpath, keep=0):
    "Trova file più recente nella directory"
    all_fits = list(os.path.join(dirpath, x) for x in os.listdir(dirpath) if x.endswith(FITS_EXT))
    all_fits.sort(key=os.path.getmtime)
    if keep > 0:
        for remove in all_fits[:-keep]:
            os.unlink(remove)
    if all_fits:
        last = all_fits[-1]
        last_size = os.path.getsize(last)
        while True:                       # Trucchetto per aspettare che il file sia stabile
            time.sleep(0.1)               # ... si spera che la scrittura dei file non abbia
            size = os.path.getsize(last)  # pause di durata maggiore
            if last_size == size:
                break
            last_size = size
        return last
    return None

def read_calib(calib_file):
    "Legge file calibrazione e estrae parametri utili"
    try:
        calib_hdu = fits.open(calib_file)[0]
        wcs = WCS(calib_hdu.header)                         # pylint: disable=E1101
        params = {"WCS": wcs,
                  "SIZE_X": calib_hdu.header["IMAGEW"],     # pylint: disable=E1101
                  "SIZE_Y": calib_hdu.header["IMAGEH"],     # pylint: disable=E1101
                  "CENTER_X": calib_hdu.header["IMAGEW"]/2, # pylint: disable=E1101
                  "CENTER_Y": calib_hdu.header["IMAGEH"]/2, # pylint: disable=E1101
                  "ORIENT": calib_hdu.header["ORIENT"],     # pylint: disable=E1101
                  "ASRATE": 15}
    except Exception as exc:               # pylint: disable=W0703
        if GLOB.debug:
            raise
        return {}, str(exc)
    return params, None

def init_donuts(image_file, ntiles, ident):
    "Inizializza Donuts con nuova immagine"
    debug(f"init_donuts({image_file}, {ntiles}, {ident})")
    send("LOG", f"[{ident}] Init. donuts on image: {image_file} (ntiles={ntiles})")
    try:
        donuts = Donuts(refimage=image_file, image_ext=0, overscan_width=20, prescan_width=20,
                        border=64, normalise=True,
                        exposure='EXPOSURE', subtract_bkg=True, ntiles=ntiles)
    except Exception as excp:            # pylint: disable=W0703
        if GLOB.debug:
            raise
        send("LOG", f"[{ident}] *** Error initializing Donuts [{str(excp)}]")
        return None
    return donuts

def send(code, what=None):
    "comunica con GUI"
    debug(f"send({code}, {what})")
    GLOB.comm.put((code, what))

def adjust_telescope(wcs, shift_result, calib_params, ident):     # pylint: disable=R0914,R0912,R0915
    "Corregge posizione telescopio"
                        # Converto coordinate centro immmagine in RA, DEC
    arcsec_rate = calib_params["ASRATE"]
    ra0, dec0 = wcs.all_pix2world([[calib_params['CENTER_X'],
                                    calib_params['CENTER_Y']]], 0)[0]
                        # Converto coordinate centro immagine + shift(x,y) in RA,DEC
    xx1 = calib_params['CENTER_X']+shift_result.x.value
    yy1 = calib_params['CENTER_Y']+shift_result.y.value
    ra1, dec1 = wcs.all_pix2world([[xx1, yy1]], 0)[0]
                    # Calcolo lo shift
    ra_shift, de_shift = ra1-ra0, dec1-dec0
    ras, dec = Angle(-ra_shift, u.degree), Angle(-de_shift, u.degree)
                    # Comunica valori di ricentraggio
    send("LOG", f'[{ident}] Computed move (RA, DEC): '
                f'({ras.to_string(unit=u.arcsec)}, {dec.to_string(unit=u.arcsec)})')
                    # Controlla che lo spostamento non sia eccessivo
    if abs(ras.arcmin) > 4 or abs(dec.arcmin) > 4:
        send("LOG", f'[{ident}] *** Error: RA/DE shift higher than 4 arcmins... guiding stopped')
        return False
                    # Ricentro il telescopio  in A.R.
    duration = int(1000*abs(ras.arcsec)/arcsec_rate)
    if 20 < duration < 16399:
        if ra_shift <= 0:
            direct = "east"
            mover = GLOB.tel.pulse_guide_east
        else:
            direct = "west"
            mover = GLOB.tel.pulse_guide_west
        send("LOG", f"[{ident}] Pulse guide {direct} {duration}")
        time0 = time.time_ns()
        stat = mover(duration)
        time1 = time.time_ns()
        delay = (time1-time0)*0.000001
        if stat != '':
            send("LOG", f'[{ident}] *** Error: {GLOB.tel.last_error()} [delay: {delay:.3f} ms]')
        else:
            send("LOG", f'[{ident}] Pulse guide {direct} - OK [delay: {delay:.3f} ms]')
    else:
        send("LOG", f'[{ident}] Telescope not moved in RA. Pulse was: {duration}')
                    # Ricentro il telescopio  in DEC.
    duration = int(1000*abs(dec.arcsec)/arcsec_rate)
    if 20 < duration < 16399:
        if de_shift <= 0:
            direct = "north"
            mover = GLOB.tel.pulse_guide_north
        else:
            direct = "south"
            mover = GLOB.tel.pulse_guide_south
        send("LOG", f"[{ident}] Pulse guide {direct} {duration}")
        time0 = time.time_ns()
        stat = mover(duration)
        time1 = time.time_ns()
        delay = (time1-time0)*0.000001
        if stat != '':
            send("LOG", f'[{ident}] *** Error: {GLOB.tel.last_error()} [delay: {delay:.3f} ms]')
        else:
            send("LOG", f'[{ident}] Pulse guide {direct} - OK [delay: {delay:.3f} ms]')
    else:
        send("LOG", f'[{ident}] Telescope not moved in DE. Pulse was: {duration}')

    while GLOB.tel.get_status() == 'n':
        send("LOG", f'[{ident}] Telescope moving...')
        time.sleep(0.5)
                    # Invia comando sync al telescopio
    GLOB.tel.sync_radec()
    return True, ras, dec
def guideloop(comm_serv, sci_dir, sci_calib, sci_tiles,      # pylint: disable=R0912,R0915,R0913,R0914
              aux_dir, aux_calib, aux_tiles, simul, debug_on):
    """
    Loop di guida

    Parametri
    ---------
    comm_serv : Comm.server_side()
        Canale di comunicazione "server side"
    sci_dir : str
        Directory con immagini scientifiche
    sci_calib : str
        Immagine calibrazione scientifica
    sci_tiles : int
        numero tiles per valutazione background
    aux_dir : str
        Directory per immagini ausiliarie (cercatore e smimili)
    aux_calib : str
        Immagine di calibrazione ausiliaria (cercatore e smimili)
    aux_tiles : int
        numero tiles per valutazione background
    simul : bool
        True - Connessione al simulatore
    debug_on : bool
        Abilita/disabilita il modo debug
    """
    GLOB.debug = debug_on
    debug("Guide process started")
    GLOB.comm = comm_serv
    config = get_config(simul=simul)
    if simul:
        send("LOG", "Connecting to telescope simulator")
    else:
        send("LOG", "Connecting to telescope")
    if not config:
        send("LOG", "*** Error: No configuration file")
        send("TERM")
        return
    GLOB.tel = TeleCommunicator(config["tel_ip"], config["tel_port"],
                                timeout=config["tel_tmout"])
    ra_deg = GLOB.tel.get_target_rah()
    de_deg = GLOB.tel.get_target_deh()
    if ra_deg is None or de_deg is None:
        send("LOG", "*** Error: telescope not responding")
        send("TERM")
        return
    ra_deg *= HOUR_TO_DEG
    if not os.path.isdir(sci_dir):
        send("LOG", f"*** Error: directory not found ({sci_dir})")
        send("TERM")
        return
    sci_calib_params, error = read_calib(sci_calib)
    if not sci_calib_params:
        send("LOG", f"[sci] *** Error on calibration file [{error}]")
        send("TERM")
        return
    send("LOG", "[sci] Calib.params: "+tostring(sci_calib_params))
    debug("Science calibration file OK")
    sci_wcs = sci_calib_params["WCS"]
    if aux_dir:
        if not os.path.isdir(aux_dir):
            send("LOG", f"[aux] *** Error: directory not found ({aux_dir})")
            send("TERM")
            return
        aux_calib_params, error = read_calib(aux_calib)
        if not aux_calib_params:
            send("LOG", f"[aux] *** Error reading calibration file [{error}]")
            send("TERM")
            return
        send("LOG", "[aux] Calib.params: "+tostring(aux_calib_params))
        debug("Aux calibration file OK")
        aux_wcs = aux_calib_params["WCS"]
    send("ORNT", sci_calib_params["ORIENT"])
    guard_x = sci_calib_params["SIZE_X"]/10
    guard_y = sci_calib_params["SIZE_Y"]/10
    sci_donuts = None
    aux_donuts = None
    first_sci_image = None
    first_aux_image = None
    while GLOB.loop:                 # pylint: disable=R1702
        time.sleep(LOOP_TIME)
        if not GLOB.comm.empty():
            cmd = GLOB.comm.get()
            debug("Input command:", cmd)
            if cmd == "STOP":
                break
            send("LOG", "*** Error: illegal command: "+str(cmd))
        if not sci_donuts: # Aspetta prima immagine utile
            first_sci_image = last_file(sci_dir)
            if first_sci_image:
                send("LOG", "[sci] First image: "+first_sci_image)
                sci_donuts = init_donuts(first_sci_image, sci_tiles, "sci")
                if not sci_donuts:
                    send("TERM")
                    break
                last_sci_image = first_sci_image
            continue
        next_sci_image = last_file(sci_dir)
        if next_sci_image != last_sci_image:
            send("LOG", "[sci] New image: "+str(next_sci_image))
            last_sci_image = next_sci_image

            # Donuts calcola lo shift dell'ultima immagine da quella di riferimento
            try:
                shift_result = sci_donuts.measure_shift(last_sci_image)
            except Exception as excp:            # pylint: disable=W0703
                if GLOB.debug:
                    raise
                send("LOG", f'[sci] Donuts error on last image [{str(excp)}]')
            else:
                aux_donuts = None
                send("LOG", "[sci] Computed shift (X, Y): "
                           f"({shift_result.x.value:.2f}, {shift_result.y.value:.2f})")
                send("SHIFT", (shift_result.x.value, shift_result.y.value))
                abs_x, abs_y = abs(shift_result.x.value), abs(shift_result.y.value)
                flag = 0
                if abs_x > guard_x or abs_y > guard_y:  # reinizializza Donuts in caso di drift
                    send("LOG", "[sci] Recentering Donuts")
                    sci_donuts = init_donuts(last_sci_image, sci_tiles, "sci")
                    if not sci_donuts:
                        send("TERM")
                        break
                    flag = 4
                # Movimento telescopio
                adjusted = adjust_telescope(sci_wcs, shift_result, sci_calib_params, "sci")
                if adjusted is None:
                    send("TERM")
                    break
                flag += 2 if adjusted else 0
        elif aux_dir:                # Aggiusta con guida ausiliaria
            if not aux_donuts:
                first_aux_image = last_file(aux_dir, keep=3)
                send("LOG", "[aux] First image: "+first_aux_image)
                aux_donuts = init_donuts(first_aux_image, aux_tiles, "aux")
                if aux_donuts:
                    last_aux_image = first_aux_image
                continue
            if aux_donuts:
                next_aux_image = last_file(aux_dir, keep=3)
                if next_aux_image != last_aux_image:
                    send("LOG", "[aux] New image: "+str(next_aux_image))
                    last_aux_image = next_aux_image
                    # Calcolo shift su immagine ausiliaria
                    try:
                        shift_result = aux_donuts.measure_shift(last_aux_image)
                    except Exception as excp:            # pylint: disable=W0703
                        if GLOB.debug:
                            raise
                        send("LOG", f'[aux] Donuts error on last image [{str(excp)}]')
                    else:
                        flag = 1
                        send("LOG", "[aux] Calculated shift on (X,Y) axes are: "
                                f"({shift_result.x.value:.2f}, {shift_result.y.value:.2f})")
                        send("SHIFT", (shift_result.x.value, shift_result.y.value))
                        abs_x, abs_y = abs(shift_result.x.value), abs(shift_result.y.value)
                        adjusted = adjust_telescope(aux_wcs, shift_result,
                                                    aux_calib_params, "aux")
                        if not adjusted:
                            aux_donuts = None
                        flag += 2 if adjusted else 0

def test():
    "Procedura di test"
    if "-h" in sys.argv:
        print(__doc__)
        sys.exit()
    if "-s" in sys.argv:
        simul = True
        argspt = 2
    else:
        simul = False
        argspt = 1

    args = sys.argv[argspt:]
    if len(args) == 2:
        sci_dir = args[0]
        sci_cal = args[1]
        aux_dir = None
        aux_cal = None
    elif len(args) == 4:
        sci_dir = args[0]
        sci_cal = args[1]
        aux_dir = args[2]
        aux_cal = args[3]
    else:
        print("Errore negli argomenti. Usa '-h' per aiuto")
        sys.exit()

    GLOB.debug = True
    print()
    print("Il test deve essere interrotto con CTRL-C")
    comm = Comm()
    guideloop(comm.server_side, sci_dir, sci_cal, SCI_TILES,
              aux_dir, aux_cal, AUX_TILES, simul, True)

def stoptest(*_unused):
    "Stop test with CTRL-C"
    GLOB.loop = False

if __name__ == "__main__":
    signal.signal(signal.SIGINT, stoptest)
    test()
