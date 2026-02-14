"""
tappo.py - Funzioni di supporto e test del tappo del telescopio OPC

Uso:

    python tappo.py [-d]         - test comandi generici

    python tappo.py [-d] -c      - test completo


NOTA: al termine della procedura selezionata viene attivato il test dei
      comandi generici

"""

import sys
import time
import signal
from enum import StrEnum, Enum
from contextlib import AbstractContextManager
from threading import Thread, Lock

try:
    import readline     #pylint: disable=W0611
except:                 #pylint: disable=W0702
    pass
import serial
from serial.tools.list_ports import comports

__version__ = "2.1"
__author__ = "Luca Fini"
__date__ = "02/2026"

################## Parametri - devono corrispondere alle impostazioni nel firmware
TTY_SPEED = 9600

ORDINE_APERTURA = [(2, 4), (1, 3)]    # N.B.: i petali sono numerati come da documentaz.
ORDINE_CHIUSURA = [(1, 3), (2, 4)]    # di Telescopi Italiani

DEMOLTIPLICA_MECCANICA = 90.    # rapporto demoltiplica meccanica
MICROSTEP = 4                   # Impostazione microstep
GRADI_STEP = 1.8                # Angolo per singolo step

START_DELAY = 8              # ritardo movimento petali in apertura/chiusura (sec)
                             # serve ad impedire interferenze fra i petali

###################################################################################

GRADI_MICROSTEP = GRADI_STEP/MICROSTEP/DEMOLTIPLICA_MECCANICA

HELP = """
 Comandi di interrogazione:

 Cod. Risposta  Descrizione
 a    x,y,z,a   Accelerazione per i quattro petali
 i    xxxxxxx   Identificazione (numero di versione del firmware)
 m    x,y,z,a   Angolo max per i quattro petali
 f    0/1/2/3/4 Petalo attivo in modo manuale (0: modo automatico)
 p    x,y,z,a   Posizione dei 4 petali
 s    x,y,z,a   Velocità corrente per i quattro petali
 v    x,y,z,a   Velocità max per i quattro petali
 w    x,y,z,a   Stato limit switch: 1=aperto 0=chiuso

 Comandi di impostazione valori (NOTA: i petali sono numerati da 1 a 4):

 Cod. Risposta  Descrizione
 MNxxx errcod   Imposta valore massimo angolo (in num di step) raggiungibile per petalo N
 ANxxx errcod   Imposta valore accelerazione (steps/sec^2) per petalo N
 VNxxx errcod   Imposta valore velocità massima per petalo N

 Comandi di movimento (NOTA: i petali sono numerati da 1 a 4):

 Cod. Risposta  Descrizione
 0N    errcod    Imposta posizione corrente come 0 per petalo N
 oNxxx errcod    muove petalo N di xxx passi in direzione "apertura"
 cNxxx errcod    muove petalo N di xxx passi in direzione "chiusura"
 gNxxx errcod    muove petalo N a posizione assoluta
 xN    errcod    Stop (interrompe movimento del..) petalo N
 X     errcod    Stop tutti i petali
"""

WARNING_1 = """
***********************************************************
*  Attenzione il programma consente di mandare qualunque  *
*  comando al controller del tappo.                       *
*                                                         *
*             USARE CON CAUTELA!                          *
***********************************************************
"""

SUCCESS = "0"
WRONG_NUM = "1"
MOVING = "2"
OVERLIMIT = "3"
CMD_UNKN = "4"
M_MODE = "5"

INTERRUPT = "6"
WRONG_POS = "7"
NOT_CONN = "8"
UNSPEC_ERR = "9"

CTRL_ERRORS = "12345"  # Gli errori da 0 a 5 sono generati dal controllore

TABELLA_ERRORI = {
    SUCCESS: "Comando eseguito",
    WRONG_NUM: "Numero petalo errato",
    MOVING: "Comando non eseguibile con petalo in moto",
    OVERLIMIT: "Superamento limite",
    CMD_UNKN: "Comando non riconosciuto",
    M_MODE: "Comando non eseguibile in modo manuale",

    INTERRUPT: "Operazione interrotta su richiesta",
    WRONG_POS: "Posizione petali anomala",
    NOT_CONN: "Controller non connesso",
    UNSPEC_ERR: "Errore generico",
}

HOMING_STEPS = int(0.25 * GRADI_MICROSTEP + 0.5)

# Stati

class GlobalStatus(StrEnum):
    "definizione stati della chiusura"
    TRANSITION = "..."
    UNCONNECTED = "Non connesso"
    UNKNOWN = "N.D."
    CLOSED = "Chiuso"
    OPEN = "Aperto"
    HOMING = "Homing in corso"
    OPENING = "Apertura in corso"
    CLOSING = "Chiusura in corso"
    ERROR = "Errore"

class Oper(Enum):
    "operazioni selezionabili"
    HOMING = 1
    OPEN = 2
    CLOSE = 3

class GLOB:  # pylint: disable=R0903
    "global variables"
    debug = False
    serial = None
    ident = ""
    motors = []
    log = print

    status = GlobalStatus.UNCONNECTED
    thread = None
    positions = [-1, -1, -1, -1]
    goon = False
    mutex = Lock()


def mysleep(delay):
    "Attende numero di secondi dato o Ctrl_C"
    while delay>0:
        if not GLOB.goon:
            return INTERRUPT
        time.sleep(1)
        ret = send_command("p")
        if ret in CTRL_ERRORS:
            return ret
        with GLOB.mutex:
            GLOB.positions = [int(x) for x in ret.split(",")]
        delay -= 1
    return SUCCESS


def speed0():
    "Attende che i motori siano tutti fermi"
    while True:
        if not GLOB.goon:
            return INTERRUPT
        ret = send_command("p")
        time.sleep(1)
        if ret in CTRL_ERRORS:
            return ret
        with GLOB.mutex:
            GLOB.positions = [int(x) for x in ret.split(",")]
        time.sleep(1)
        ret = send_command("s")
        if ret in CTRL_ERRORS:
            return ret
        tot_speed = sum((float(x) for x in ret.split(",")))
        if tot_speed == 0.0:
            return SUCCESS
    return False

def wait_sum(sum_pos):
    "Attende raggiungimento della somma di posizioni data"
    while True:         # Controllo raggiungimento posizione aperto
        if not GLOB.goon:
            return INTERRUPT
        time.sleep(2)
        ret = send_command("p")
        if ret in CTRL_ERRORS:
            return ret
        with GLOB.mutex:
            GLOB.positions = [int(x) for x in ret.split(",")]
        cur_diff = sum_pos - sum(GLOB.positions)
        if cur_diff == 0:
            break
    return SUCCESS


class MotorStatus:
    "Controllo e stato di un motore"
    def __init__(self, order):
        self.my_id = order + 1
        self.homed = False
        self.max_pos = None


    def home(self):           #pylint: disable=R0911
        "posiziona/verifica petalo 'at home'"
        self.homed = False
        if self.max_pos is None:
            ret = send_command("m")
            if ret in CTRL_ERRORS:
                return ret
            self.max_pos = int(ret.split(",")[self.my_id-1])
        GLOB.goon = True
        angle_span = self.max_pos
        while angle_span:
            if not GLOB.goon:
                return INTERRUPT
            if (ret := wrong_position()) != SUCCESS:
                return ret
            angle_span -= HOMING_STEPS
            ret = send_command(f"c{self.my_id}{HOMING_STEPS}")
            if ret in CTRL_ERRORS:
                return ret
            if (ret := speed0()) != SUCCESS:
                return ret
            ret = send_command("w")
            if ret in CTRL_ERRORS:
                return ret
            switches = ret.split(",")
            if switches[self.my_id-1] == "1":    # limit switch open. Imposta posizione 0
                send_command(f"0{self.my_id}")
                self.homed = True
                with GLOB.mutex:
                    GLOB.positions[self.my_id-1] = 0
                return SUCCESS
        return UNSPEC_ERR

    def command_open(self):
        "Manda comando di apertura completa"
        if not self.homed:
            return UNSPEC_ERR
        return send_command(f"g{self.my_id}{self.max_pos}")

    def command_close(self):
        "manda commando di chiusura del petalo"
        if not self.homed:
            return UNSPEC_ERR
        return send_command(f"g{self.my_id}0")


class FakeMutex(AbstractContextManager):     #pylint: disable=R0903
    "emulatore mutex per uso non threaded"
    def __exit__(self, *_):
        ...

GLOB.motors = [MotorStatus(idx) for idx in range(4)]

def _debug(text):
    "mostra info per debug"
    if GLOB.debug:
        print("DBG>", text)


def send_command(cmd):
    "Invia comando al coltrollore e gestisce messaggi di debug 'out of band'"
    tcmd = ("!" + cmd + ":").encode("ascii")
    _debug(f"sending command: {tcmd}")
    try:
        GLOB.serial.write(tcmd)
    except:  # pylint: disable=W0702
        return NOT_CONN
    while True:
        try:
            line = GLOB.serial.readline()
        except:  # pylint: disable=W0702
            return NOT_CONN
        ret = line.decode("utf8").strip()
        if ret[:1] != "#":
            _debug(f"command returns: {ret}")
            return ret
        print("A.DBG>", ret[1:])


def init_serial(tty):
    "Inizializza la comunicazione. Riporta la stringa di identificazione"
    _debug(f"Trying: {tty}")
    try:
        GLOB.serial = serial.Serial(tty, TTY_SPEED, timeout=2)
    except:  # pylint: disable=W0702
        return ""
    time.sleep(2)  # wait controller setup
    _debug("Serial connected")
    ident = send_command("i")
    if "Tappo" in ident:
        return ident
    try:
        GLOB.serial.close()
    except:  # pylint: disable=W0702
        pass
    GLOB.serial = None
    return ""


################### funzioni per controllo
def find_tty():
    "Cerca linea USB con controllore e inizializza la comunicazione"
    _debug("Ricerca controllore attivo")
    GLOB.status = GlobalStatus.UNCONNECTED
    if sys.platform == "linux":
        template = "tty"
    elif sys.platform == "win32":
        template = "COM"
    else:
        raise RuntimeError(f"Piattaforma non supportata: {sys.platform}")
    GLOB.serial = None
    GLOB.tty = ""
    GLOB.ident = ""
    ports = comports()
    for port in ports:
        if template in port.description:
            GLOB.ident = init_serial(port.device)
            if GLOB.ident:
                GLOB.tty = port.device
                _debug(f"Controllore attivo su linea: {GLOB.tty}")
                return GLOB.ident
    _debug("Controller NON trovato")
    return ""


def set_debug(enable=True):
    "Abilita/disabilita debug"
    GLOB.debug = enable

def set_log(log_func):
    "Cambia funzione di log. log_func: funzione che accetta una stringa"
    GLOB.log = log_func


def reply(cmd, msg):
    "interpretazione risposte al comando"
    match cmd[0]:
        case 'a':
            print("REPLY - Accelerazioni:", msg, "(step/s^2)")
        case 'f':
            if msg[0] == "M":
                mode = f"Manuale (selettore: {msg[1]})"
            else:
                mode = "A"
            print("REPLY - Modo funzionamento:", mode)
        case 'i':
            print("REPLY - Identificazione:", msg)
        case 'm':
            print("REPLY - Angolo max:", msg, "(step)")
        case 'p':
            print("REPLY - Posizione:", msg, "(step)")
        case 's':
            print("REPLY - Velocità:", msg, "(step/s)")
        case 'v':
            print("REPLY - Velocità max:", msg, "(step/s)")
        case 'w':
            print("REPLY - Lim. Switch:", msg, "(1:aperto, 0:chiuso)")
        case _:
            print("REPLY:", msg, "- Inatteso!")

# Le seguenti funzioni supportano le operazioni in modo asincrono ############
def stop_homing():
    "Interrompe procedura di homing"
    GLOB.goon = False

def get_positions():
    "Legge posizioni con operazioni in corso"
    return GLOB.positions

def wrong_position():
    """
    Controlla che i petali non siano in posizione anomala per l'homing.
    Return: Codice errore o SUCCESS se la posizione è corretta
    """
    ret = send_command("w")
    if ret in CTRL_ERRORS:
        return ret
    swtc = ret.split(",")
    set1_open = (swtc[0] == "0") or (swtc[2] == "0")    # Almeno uno dei petali che devono
                                                        # chiudersi per primi, è aperto
    set2_closed = (swtc[1] == "1") or (swtc[3] == "1")  # Almeno uno dei petali che devono
                                                        # chiudersi per secondi, è chiuso
    ret = UNSPEC_ERR if set1_open and set2_closed else SUCCESS
    return ret

def _home_all():
    "Procedura di homing per tutti i petali"
    GLOB.log("Inizio procedura homing")
    with GLOB.mutex:
        GLOB.positions = [-1, -1, -1, -1]
        GLOB.status = GlobalStatus.HOMING
    for idx in ORDINE_CHIUSURA[0]+ORDINE_CHIUSURA[1]:
        motor = GLOB.motors[idx-1]
        GLOB.log(f"Homing petalo {idx}")
        ret = motor.home()
        if ret != SUCCESS:
            GLOB.log(f"Errore homing petalo {idx}: {TABELLA_ERRORI[ret]}")
            send_command("X")
            with GLOB.mutex:
                GLOB.status = GlobalStatus.ERROR
            return
        GLOB.log(f"Procedura homing petalo {idx} OK")
    with GLOB.mutex:
        GLOB.status = GlobalStatus.CLOSED
    return

def initialize():
    "apre la connessione con il controllore"
    if not find_tty():
        GLOB.log("Controllore non connesso")
        GLOB.status = GlobalStatus.UNCONNECTED
        return False
    GLOB.log(f"Controllore connesso: {GLOB.ident}")
    GLOB.status = GlobalStatus.UNKNOWN
    return True


def _open_all():
    "Apertura in ordine corretto di tutti i petali"
    def log_error(npt, code):
        GLOB.log(f"Errore comando petalo {npt}: {TABELLA_ERRORI[code]}")

    GLOB.log("Richiesta apertura petali")
    if GLOB.status == GlobalStatus.CLOSED:
        with GLOB.mutex:
            GLOB.status = GlobalStatus.OPENING
        for idx in ORDINE_APERTURA[0]:
            ret = GLOB.motors[idx-1].command_open()
            if ret != SUCCESS:
                log_error(idx, ret)
                return
        if (ret := mysleep(START_DELAY)) != SUCCESS:
            GLOB.log("Procedura interrotta su richiesta")
            with GLOB.mutex:
                GLOB.status = GlobalStatus.ERROR
            return
        for idx in ORDINE_APERTURA[1]:
            ret = GLOB.motors[idx-1].command_open()
            if ret != SUCCESS:
                log_error(idx, ret)
                return
        max_sum = sum(GLOB.motors[i].max_pos for i in range(4))
        if (ret := wait_sum(max_sum)) == SUCCESS:
            with GLOB.mutex:
                GLOB.status = GlobalStatus.OPEN
            GLOB.log("Petali aperti")
        else:
            with GLOB.mutex:
                GLOB.status = GlobalStatus.ERROR
            GLOB.log(f"Errore apertura petali: {TABELLA_ERRORI[ret]}")
        return
    GLOB.log("Errore: apertura petali possibile solo da stato chiuso")


def _close_all():
    "Chiusura in ordine corretto di tutti i petali"
    def log_error(npt, code):
        GLOB.log(f"Errore comando petalo {npt}: {TABELLA_ERRORI[code]}")

    GLOB.log("Richiesta chiusura petali")
    if GLOB.status == GlobalStatus.OPEN:
        with GLOB.mutex:
            GLOB.status = GlobalStatus.CLOSING
        for idx in ORDINE_CHIUSURA[0]:
            ret = GLOB.motors[idx-1].command_close()
            if ret != SUCCESS:
                log_error(idx, ret)
                return
        if (ret := mysleep(START_DELAY)) != SUCCESS:
            GLOB.log("Procedura interrotta su richiesta")
            with GLOB.mutex:
                GLOB.status = GlobalStatus.ERROR
            return
        for idx in ORDINE_CHIUSURA[1]:
            ret = GLOB.motors[idx-1].command_close()
            if ret != SUCCESS:
                log_error(idx, ret)
                return
        if (ret := wait_sum(0)) == SUCCESS:
            with GLOB.mutex:
                GLOB.status = GlobalStatus.CLOSED
            GLOB.log("Petali aperti")
        else:
            GLOB.log(f"Errore chiusura petali: {TABELLA_ERRORI[ret]}")
            with GLOB.mutex:
                GLOB.status = GlobalStatus.ERROR
        return
    GLOB.log("Errore: chiusura petali possibile solo da stato aperto")


def read_position():
    "Legge posizioni petali"
    ret = send_command("p")
    if ret in TABELLA_ERRORI:
        GLOB.log(f"Errore lettura posizioni: {TABELLA_ERRORI[ret]}")
        ret = [-1, -1, -1, -1]
    ret = [int(x) for x in ret.split(",")]
    GLOB.position = ret
    return ret


def exec_thread(oper):
    "Esegue comando in un thread"
    if oper == Oper.HOMING:
        GLOB.thread = Thread(target=_home_all)
    elif oper == Oper.OPEN:
        GLOB.thread = Thread(target=_open_all)
    elif oper == Oper.CLOSE:
        GLOB.thread = Thread(target=_close_all)
    else:
        return UNSPEC_ERR
    GLOB.thread.start()
    time.sleep(1)      # per assicurarsi che il thread sia in esecuzione
    return SUCCESS

def exec_check():
    "controlla stato del thread"
    with GLOB.mutex:
        status = GLOB.status
        positions = GLOB.positions.copy()
    running = False if GLOB.thread is None else GLOB.thread.is_alive()
    return running, status, positions

def exec_stop():
    "rinchiesta di interruzione dell'operazione in corso"
    GLOB.log("Interruzione su richiesta")
    send_command("X")
    GLOB.goon = False

#  Funzioni per test

def test_comandi():
    "test comandi elementari"
    print(WARNING_1)
    while True:
        print()
        cmd = input("Comando (q: stop, <invio>: help)? ").strip()
        if not cmd:
            print(HELP)
            continue
        if cmd[:1] == "q":
            break
        ret = send_command(cmd)
        if ret in TABELLA_ERRORI:
            print("REPLY:", ret, "-", TABELLA_ERRORI[ret])
        else:
            reply(cmd, ret)


def test_homing():
    "Test procedura di homing"
    exec_thread(Oper.HOMING)
    running = True
    while running:
        time.sleep(1)
        running, status, positions = exec_check()
        print(" - Stato:", status, "- Pos.:", *positions)
    return status == GlobalStatus.CLOSED

def test_open():
    "prova procedura apertura petali"
    exec_thread(Oper.OPEN)
    running = True
    while running:
        time.sleep(1)
        running, status, positions = exec_check()
        print(" - Stato:", status, "- Pos.:", *positions)
    return GLOB.status == GlobalStatus.OPEN

def test_close():
    "prova procedura apertura petali"
    exec_thread(Oper.CLOSE)
    running = True
    while running:
        time.sleep(1)
        running, status, positions = exec_check()
        print(" - Stato:", status, "- Pos.:", *positions)
    return status == GlobalStatus.CLOSED


def stop_request(*_):
    "Handler per Ctrl-C"
    GLOB.log("Ricevuto Ctrl-C")
    exec_stop()

SEPARATE = """
================================================================"""

def main():
    "operazioni di test"
    if "-h" in sys.argv:
        print(__doc__)
        sys.exit()
    GLOB.debug = "-d" in sys.argv

    GLOB.mutex = FakeMutex()
    print()
    ret = initialize()
    if not ret:
        sys.exit()


    if "-c" in sys.argv:
        signal.signal(signal.SIGINT, stop_request)
        print(SEPARATE)
        ret = test_homing()
        if ret:
            print(SEPARATE)
            ret = test_open()
        if ret:
            print(SEPARATE)
            test_close()
        print(SEPARATE)
        test_comandi()
        sys.exit()

    test_comandi()

if __name__ == "__main__":
    main()
