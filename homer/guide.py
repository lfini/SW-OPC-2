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
from donuts import Donuts

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# pylint: disable=C0413
from opc.utils import get_config
from opc.telecomm import TeleCommunicator
from homer.calibrate import Transformer

LOOP_TIME = 0.2    # Tempo di ritardo loop principale (secondi)

HOUR_TO_DEG = 15.0 # Conversione ore->gradi

                # parametri per test standalone
SCI_TILES = 32  # Numero di "tiles" da usare nell'inizializzazione
                # di donuts sull'immagine scientifica
AUX_TILES = 32  # ... e nell'immagine ausiliaria

ASRATE = 15     # Conversione spostamento "pulse" da arcsec in secondi di durata

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
    @staticmethod
    def get():
        'get function'
        print('Fake GET')

    @staticmethod
    def put(what):
        'put function'
        print('Fake PUT:', what)

    @staticmethod
    def empty():
        'empty function'
        return True

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
            ret.append(f'{key}: {str(value)}')
    return "{"+", ".join(ret)+"}"

def protect(func):
    'Decoratore per proteggere da eccezioni'
    def wrapper(*args, **kwargs):
        try:
            ret = func(*args, **kwargs)
        except Exception:                     #pylint: disable=W0703
            ret = None
        return ret
    return wrapper

def debug(*pars):
    "Show debug lines"
    if GLOB.debug:
        print("GUIDE DBG>", *pars)

FITS_EXT = (".fit", ".fits", ".FIT", ".FITS")


@protect
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

def init_donuts(image_file, ntiles, ident):
    "Inizializza Donuts con nuova immagine"
    debug(f'init_donuts({image_file}, {ntiles}, {ident})')
    send('LOG', f'[{ident}] Init. donuts on image: {image_file} (ntiles={ntiles})')
    try:
        donuts = Donuts(refimage=image_file, image_ext=0, overscan_width=20, prescan_width=20,
                        border=64, normalise=True,
                        exposure='EXPOSURE', subtract_bkg=True, ntiles=ntiles)
    except Exception as excp:            # pylint: disable=W0703
        if GLOB.debug:
            raise
        send('LOG', f'[{ident}] *** Error initializing Donuts [{str(excp)}]')
        return None
    return donuts

def send(code, what=None):
    "comunica con GUI"
    debug(f'send({code}, {what})')
    GLOB.comm.put((code, what))

def adjust_tel(trans, xsh, ysh, ident):     #pylint: disable=R0914,R0912,R0915
    "Calcola e corregge posizione telescopio"
    ra_shift, de_shift = trans.transform(xsh, ysh)    # Calcolo aggiustamento
    send('LOG', f'[{ident}] Computed move (RA, DEC): '
         f'({ra_shift:.2f}, {de_shift:.2f}) arcsec')
    ra_abs, de_abs = abs(ra_shift), abs(de_shift)    # Controlla spostamento eccessivo
    if ra_abs > 120 or de_abs > 120:
        send('LOG', f'[{ident}] *** Error: RA/DE shift higher than 2 arcmins... guiding stopped')
        return False
                    # Ricentro il telescopio  in A.R.
    moved = False
    duration = int(1000*ra_abs/ASRATE)
    if 20 < duration < 16399:
        if ra_shift <= 0:
            direct = "east"
            mover = GLOB.tel.pulse_guide_east
        else:
            direct = "west"
            mover = GLOB.tel.pulse_guide_west
        send('LOG', f'[{ident}] Pulse guide {direct} {duration}')
        moved = True
        time0 = time.time_ns()
        stat = mover(duration)
        time1 = time.time_ns()
        delay = (time1-time0)*0.000001
        if stat != '':
            send('LOG', f'[{ident}] *** Error: {GLOB.tel.last_error()} [delay: {delay:.3f} ms]')
        else:
            send('LOG', f'[{ident}] Pulse guide {direct} - OK [delay: {delay:.3f} ms]')
    else:
        send('LOG', f'[{ident}] Telescope not moved in RA. Pulse was: {duration}')
                    # Ricentro il telescopio  in DEC.
    duration = int(1000*de_abs/ASRATE)
    if 20 < duration < 16399:
        if de_shift <= 0:
            direct = "north"
            mover = GLOB.tel.pulse_guide_north
        else:
            direct = "south"
            mover = GLOB.tel.pulse_guide_south
        send('LOG', f'[{ident}] Pulse guide {direct} {duration}')
        moved = True
        time0 = time.time_ns()
        stat = mover(duration)
        time1 = time.time_ns()
        delay = (time1-time0)*0.000001
        if stat != '':
            send('LOG', f'[{ident}] *** Error: {GLOB.tel.last_error()} [delay: {delay:.3f} ms]')
        else:
            send('LOG', f'[{ident}] Pulse guide {direct} - OK [delay: {delay:.3f} ms]')
    else:
        send('LOG', f'[{ident}] Telescope not moved in DE. Pulse was: {duration}')
    if moved:
        while GLOB.tel.get_status() == 'n':
            send('LOG', f'[{ident}] Telescope moving...')
            time.sleep(0.5)
                    # Invia comando sync al telescopio
        send('LOG', f'[{ident}] Telescope sync')
        GLOB.tel.sync_radec()
    return True

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
        send('LOG', "Connecting to telescope simulator")
    else:
        send('LOG', "Connecting to telescope")
    if not config:
        send('LOG', "*** Error: No configuration file")
        send("TERM")
        return
    GLOB.tel = TeleCommunicator(config["tel_ip"], config["tel_port"],
                                timeout=config["tel_tmout"])
    ra_deg = GLOB.tel.get_target_rah()
    de_deg = GLOB.tel.get_target_deh()
    if ra_deg is None or de_deg is None:
        send('LOG', "*** Error: telescope not responding")
        send("TERM")
        return
    ra_deg *= HOUR_TO_DEG
    if not os.path.isdir(sci_dir):
        send('LOG', f'*** Error: directory not found ({sci_dir})')
        send("TERM")
        return
    sci_trans = Transformer(sci_calib)
    if sci_trans.error:
        send('LOG', f'[sci] *** Error on calibration file [{sci_trans.error}]')
        send("TERM")
        return
    send('LOG', "[sci] Calib.matrix: "+sci_trans.str_matrix())
    send('LOG', "[sci] Image scale: "+sci_trans.str_scale())
    send('LOG', "[sci] Image size: "+sci_trans.str_size())
    send('LOG', "[sci] Image orient.: "+sci_trans.str_orient())
    debug("Science calibration file OK")
    if aux_dir:
        if not os.path.isdir(aux_dir):
            send('LOG', f'[aux] *** Error: directory not found ({aux_dir})')
            send("TERM")
            return
        aux_trans = Transformer(aux_calib)
        if aux_trans.error:
            send('LOG', f'[aux] *** Error reading calibration file [{aux_trans.error}]')
            send("TERM")
            return
        send('LOG', "[aux] Calib.params: "+str(aux_trans))
        debug("Aux calibration file OK")
    send("ORNT", sci_trans.orient)
    guard_x = sci_trans.imagew/10
    guard_y = sci_trans.imageh/10
    sci_donuts = None
    aux_donuts = None
    first_sci_im = None
    first_aux_im = None
    while GLOB.loop:                 # pylint: disable=R1702
        time.sleep(LOOP_TIME)
        if not GLOB.comm.empty():
            cmd = GLOB.comm.get()
            debug("Input command:", cmd)
            if cmd == "STOP":
                break
            send('LOG', "*** Error: illegal command: "+str(cmd))
        if not sci_donuts: # Aspetta prima immagine utile
            first_sci_im = last_file(sci_dir)
            if first_sci_im:
                send('LOG', "[sci] First image: "+first_sci_im)
                sci_donuts = init_donuts(first_sci_im, sci_tiles, "sci")
                if not sci_donuts:
                    send("TERM")
                    break
                last_sci_im = first_sci_im
            continue
        next_sci_im = last_file(sci_dir)
        if next_sci_im and (next_sci_im != last_sci_im):
            send('LOG', "[sci] New image: "+str(next_sci_im))
            last_sci_im = next_sci_im

            # Calcolo shift su immagine scientifica
            try:
                shift_result = sci_donuts.measure_shift(last_sci_im)
            except Exception as excp:            # pylint: disable=W0703
                if GLOB.debug:
                    raise
                send('LOG', f'[sci] Donuts error on last image [{str(excp)}]')
                continue
            aux_donuts = None
            xsh, ysh = shift_result.x.value, shift_result.y.value
            send('LOG', f'[sci] Computed shift (X, Y): ({xsh:.1f}, {ysh:.1f})')
            send("SHIFT", (xsh, ysh))
            abs_x, abs_y = abs(xsh), abs(ysh)
            if abs_x > guard_x or abs_y > guard_y:  # reinizializza Donuts in caso di drift
                send('LOG', "[sci] Recentering Donuts")
                sci_donuts = init_donuts(last_sci_im, sci_tiles, "sci")
                if not sci_donuts:
                    send("TERM")
                    break
            adjusted = adjust_tel(sci_trans, xsh, ysh, "sci")   # Movimento telescopio
            if not adjusted:
                send("TERM")
                break
        elif aux_dir:                # Aggiusta con guida ausiliaria
            if not aux_donuts:
                first_aux_im = last_file(aux_dir, keep=3)
                if first_aux_im:
                    send('LOG', "[aux] First image: "+first_aux_im)
                    aux_donuts = init_donuts(first_aux_im, aux_tiles, "aux")
                    if aux_donuts:
                        last_aux_im = first_aux_im
                continue
            next_aux_im = last_file(aux_dir, keep=3)
            if next_aux_im and (next_aux_im != last_aux_im):
                send('LOG', "[aux] New image: "+str(next_aux_im))
                last_aux_im = next_aux_im
                # Calcolo shift su immagine ausiliaria
                try:
                    shift_result = aux_donuts.measure_shift(last_aux_im)
                except Exception as excp:            # pylint: disable=W0703
                    if GLOB.debug:
                        raise
                    send('LOG', f'[aux] Donuts error on last image [{str(excp)}]')
                    continue
                xsh, ysh = shift_result.x.value, shift_result.y.value
                send('LOG', '[aux] Computed shift (X, Y): ({xsh:.2f}, {ysh:.2f})')
                send("SHIFT", (xsh, ysh))
                abs_x, abs_y = abs(xsh), abs(ysh)
                adjusted = adjust_tel(aux_trans, xsh, ysh, "aux")   # Movimento telescopio
                if not adjusted:
                    aux_donuts = None

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
