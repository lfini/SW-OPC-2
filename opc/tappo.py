"""
tappo.py - Funzioni di supporto e test del tappo del telescopio OPC

Uso:

    python tappo.py [-d]         - test comandi generici

    python tappo.py [-d] -iIoOcC - test procedura complesse

    python tappo.py [-d] -s      - stress test

dove:

    -d: attiva debug

    -i/I: test inizializzazione (I: non tenta homing, per test senza finecorsa)
    -o/O: test inizializzazione + apertura  (O: non tenta homing)
    -c/C: test inizializzazione + apertura + chiusura (C: non tenta homing)

NOTA: al termine della procedura complessa selezionata viene attivato il test dei
      comandi generici

"""

import sys
import time
import signal

try:
    import readline     #pylint: disable=W0611
except:                 #pylint: disable=W0702
    pass
import serial
from serial.tools.list_ports import comports

__version__ = "1.3"
__author__ = "Luca Fini"
__date__ = "01/2026"

################## Parametri - devono corrispondere alle impostazioni nel firmware
TTY_SPEED = 9600
\
ORDINE_APERTURA = [2, 4, 1, 3]    # N.B.: i petali sono numerati come da documentaz.
ORDINE_CHIUSURA = [1, 3, 2, 4]    # di Telescopi Italiani

DEMOLTIPLICA_MECCANICA = 90.    # rapporto demoltiplica meccanica
MICROSTEP = 4                   # Impostazione microstep
GRADI_STEP = 1.8                # Angolo per singolo step

START_DELAY = 5              # ritardo movimento petali in apertura/chiusura (sec)
                             # serve ad impedire interferenze fra i petali

WAIT_STOP = 10               # Tempo massimo di attesa dell'arresto (sec)
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
****************************************************
Attenzione il programma consente di mandare qualunque
comando al controller del tappo.

           USARE CON CAUTELA!
*****************************************************
"""

STRESS_ERROR = """
La procedura di stress test deve iniziare
con i petali in posizione 0
"""

STRESS_WARN = """
Inizio procedura di stress test. I motori verranno azionati
fino alla posizione verticale nell'ordine previsto.

La procedura termina dopo ilo numnero di cicli impostati,
e può essere interrotta con Ctrl-C
"""

END_ON_CTRLC = """
Procedura di stress test interrotta con Ctrl-C
"""

SUCCESS = "0"

ERRORS = "1234589"

CODICI_STATO = {
    SUCCESS: "Comando eseguito",
    "1": "Numero petalo errato",
    "2": "Comando non eseguibile con petalo in moto",
    "3": "Superamento limite",
    "4": "Comando non riconosciuto",
    "5": "Comando non eseguibile in modo manuale",
    "7": "Posizione petali anomala",
    "8": "Operazione non conclusa",
    "9": "Controller non connesso",
}

HOMING_STEPS = int(0.25 * GRADI_MICROSTEP + 0.5)

# Stati

UNKNOWN = "N.D."
CLOSED = "Chiuso"
OPEN = "Aperto"
MOVING = "In movimento"

class CommandError(RuntimeError):
    "Errore sui comandi"
    def __init__(self, code, aux=""):
        if aux:
            msg = f"[{aux}] {CODICI_STATO[code]}"
        else:
            msg = CODICI_STATO[code]
        super().__init__(msg)


class MotorStatus:
    "Controllo e stato di un motore"
    def __init__(self, order):
        self.my_id = order + 1
        self.homed = False
        self.last_error = ""

    def _speed0(self, ntry=WAIT_STOP):
        "Attende che il motore sia fermo"
        while ntry > 0:
            ntry -= 1
            time.sleep(1)
            ret = send_command_excp("s")
            cur_speed = float(ret.split(",")[self.my_id])
            if cur_speed == 0.0:
                return True
        return False


    def error(self, spec, errcod):
        "Genera stringa di errore"
        self.last_error = f"{spec} - {CODICI_STATO[errcod]}"

    def home(self):
        "posiziona/verifica petalo 'at home'"
        self.last_error = ""
        self.homed = False
        ret = send_command_excp("m")
        max_angle = int(ret.split(",")[self.my_id])
        GLOB.home_goon = True
        while max_angle:
            if not GLOB.home_goon:
                raise CommandError("8", "stop su richiesta")
            if wrong_position():
                raise CommandError("8", "posizione petali anomala")
            max_angle -= HOMING_STEPS
            ret = send_command_excp(f"c{self.my_id}{HOMING_STEPS}")
            if not self._speed0():
                raise CommandError("8", "mancato arresto")
            ret = send_command_excp("w")
            switches = ret.split(",")
            if switches[self.my_id] == "1":    # limit switch open. Imposta posizione 0
                send_command_excp(f"0{self.my_id}")
                self.homed = True
                GLOB.positions[self.my_id] = 0
                return
        raise CommandError("8", "homing")

class GLOB:  # pylint: disable=R0903
    "global variables"
    debug = False
    serial = None
    ident = ""
    motors = [MotorStatus(idx) for idx in range(4)]
    log = print
    all_homed = False
    all_open = False
    positions = [-1, -1, -1, -1]
    stress_goon = False
    home_goon = False


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
        return "9"
    while True:
        try:
            line = GLOB.serial.readline()
        except:  # pylint: disable=W0702
            return "9"
        ret = line.decode("utf8").strip()
        if ret[:1] != "#":
            _debug(f"command returns: {ret}")
            return ret
        print("A.DBG>", ret[1:])


def send_command_excp(cmd):
    "Invia comando al controllore e genera excp per errori"
    ret = send_command(cmd)
    if ret in ERRORS:
        raise CommandError(ret, f"cmd: {cmd}")
    return ret


def init_serial(tty):
    "Inizializza la comunicazione. Riporta la stringa di identificazione"
    _debug(f"Trying: {tty}")
    try:
        GLOB.serial = serial.Serial(tty, TTY_SPEED, timeout=2)
    except:  # pylint: disable=W0702
        return None
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
    _debug("Looking for connected controller")
    if sys.platform == "linux":
        template = "tty"
    elif sys.platform == "win32":
        template = "COM"
    else:
        raise RuntimeError(f"Not supported: {sys.platform}")
    GLOB.status = UNKNOWN
    GLOB.serial = None
    GLOB.tty = ""
    GLOB.ident = ""
    ports = comports()
    for port in ports:
        if template in port.description:
            GLOB.ident = init_serial(port.device)
            if GLOB.ident:
                GLOB.tty = port.device
                _debug(f"Controller attivo su linea: {GLOB.tty}")
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
    GLOB.home_goon = False

def get_positions():
    "Legge posizioni con operazioni in corso"
    return GLOB.positions

def wrong_position():
    """
    Controlla che i petali non siano in posizione anomala per l'homing.
    Return: True se la posizione è errata
    """
    ret = send_command_excp("w")
    swtc = ret.split(",")
    set1_open = (swtc[0] == "0") or (swtc[2] == "0")    # Almeno uno dei petali che devono
                                                        # chiudersi per primi, è aperto
    set2_closed = (swtc[1] == "1") or (swtc[3] == "1")  # Almeno uno dei petali che devono
                                                        # chiudersi per secondi, è chiuso
    return set1_open and set2_closed

def home_all():
    "Procedura di homing per tutti i petali"
    GLOB.all_homed = False
    GLOB.positions = [-1, -1, -1, -1]
    GLOB.log("Inizio procedura homing")
    for idx in ORDINE_CHIUSURA:
        motor = GLOB.motors[idx]
        GLOB.log(f"Homing petalo {idx}")
        try:
            motor.home()
        except CommandError as excp:
            GLOB.log(f"Errore homing petalo {idx}: {excp}")
            send_command("X")
            return False
    GLOB.status = CLOSED
    GLOB.log("Procedura homing petalo {idx} OK")
    return True

def initialize(do_homing=True):
    "initialize connection and (optionally) set home for all petals"
    if not find_tty():
        GLOB.log("Controllore non connesso")
        return False
    GLOB.log(f"Controllore connesso: {GLOB.ident}")
    if do_homing:
        return home_all()
    return True


def _wait_sum(sum_pos):
    "Attende raggiungimento della somma di posizioni data"
    prev_diff = None
    while True:         # Controllo raggiungimento posizione aperto
        time.sleep(1)
        ret = send_command("p")
        if ret in CODICI_STATO:
            GLOB.log(f"Errore lettura posizioni: {CODICI_STATO[ret]}")
            send_command("X")     # stop all petals
            return False
        GLOB.positions = [int(x) for x in ret.split(",")]
        cur_diff = sum_pos - sum(GLOB.positions)
        if cur_diff == 0:
            break
        if prev_diff is not None and cur_diff == prev_diff:
            GLOB.log("Errore: qualche motore apparentemente bloccato!")
            return False
    GLOB.log("Posizione raggiunta")
    return True


def open_all():
    "Apertura in ordine corretto di tutti i petali"
    GLOB.all_open = False
    if GLOB.all_homed:
        ret = send_command("m")
        if ret in CODICI_STATO:
            GLOB.log("Errore lettura pos. max: "+CODICI_STATO[ret])
            return False
        max_pos = [int(x) for x in ret.split(",")]
        for nstep, idx in enumerate(ORDINE_APERTURA):
            GLOB.log(f"Apertura petalo: {idx}")
            ret = send_command(f"g{idx}{max_pos[idx]}")
            if ret != SUCCESS:
                GLOB.log(f"Errore apertura petalo {idx}: {GLOB.motors[idx].last_error}")
                send_command("X")     # stop all petals
                return False
            if nstep == 1:
                time.sleep(START_DELAY)
        max_sum = sum(max_pos)
        GLOB.all_open = _wait_sum(max_sum)
        return GLOB.all_open
    GLOB.log("Errore: stato patali ignoto")
    return False


def close_all():
    "Chiusura in ordine corretto di tutti i petali"
    if GLOB.all_open:
        for nstep, idx in enumerate(ORDINE_CHIUSURA):
            GLOB.log(f"Chiusura petalo: {idx}")
            ret = send_command(f"g{idx}0")
            if ret != SUCCESS:
                GLOB.log(f"Errore chiusura petalo {idx}: {GLOB.motors[idx].last_error}")
                send_command("X")
                return False
            if nstep == 1:
                time.sleep(START_DELAY)
        status = _wait_sum(0)
        if status:
            return home_all()
        return False
    GLOB.log("Errore: petali non aperti")
    return False

def read_position():
    "Legge posizioni petali"
    ret = send_command("p")
    if ret in CODICI_STATO:
        GLOB.log(f"Errore lettura posizioni: {CODICI_STATO[ret]}")
        ret = [-1, -1, -1, -1]
    ret = [int(x) for x in ret.split(",")]
    GLOB.position = ret
    return ret


##############################
#  Funzioni per test

def test_comandi(init=True):
    "test comandi elementari"
    if init:
        print()
        ident = find_tty()
        if not ident:
            print("Errore: controllore non connesso")
            print()
            sys.exit()
        else:
            print("Controllore connesso:", ident)

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
        if ret in CODICI_STATO:
            print("REPLY:", ret, "-", CODICI_STATO[ret])
        else:
            reply(cmd, ret)


def test_inizializzazione(do_homing):
    "prova procedura inizializzazione (+ homing)"
    ret = initialize(do_homing)
    stat = "OK" if ret else "FALLITO"
    print(f"Test inizializzazione: {stat}")

def test_open():
    "prova procedura apertura petali"
    ret = open_all()
    stat = "OK" if ret else "FALLITO"
    print(f"Test apertura petali: {stat}")

def test_close():
    "prova procedura apertura petali"
    ret = close_all()
    stat = "OK" if ret else "FALLITO"
    print(f"Test chiusura petali: {stat}")

def sleep_ctrlc(secs, oper):
    "Attende secs secondi o Ctrl-C"
    while secs:
        secs -= 1
        if not GLOB.stress_goon:
            return
        time.sleep(1)
        print(f" - {oper}. Posizione petali:", read_position())

def stress_cycle(num):            #pylint: disable=R0911
    "esegue un ciclo di stress"
    pos = read_position()
    if pos != [0, 0, 0, 0]:
        print(STRESS_ERROR)
        return False
    print(f"Inizio ciclo apertura {num}. Posizione petali:", pos)
    send_command_excp("g220000")
    send_command_excp("g420000")
    sleep_ctrlc(10, "apertura")
    if not GLOB.stress_goon:
        return False
    send_command_excp("g120000")
    send_command_excp("g320000")
    sumpos = 0
    while sumpos < 80000:
        if not GLOB.stress_goon:
            return False
        time.sleep(1)
        pos = read_position()
        print(" - apertura. Posizione petali:", pos)
        sumpos = sum(pos)
    sleep_ctrlc(2, "fine apertura")
    if not GLOB.stress_goon:
        return False
    print(f"Inizio ciclo chiusura {num}. Posizione petali:", pos)
    send_command_excp("g10")
    send_command_excp("g30")
    sleep_ctrlc(10, "chiusura")
    if not GLOB.stress_goon:
        return False
    send_command_excp("g40")
    send_command_excp("g20")
    sumpos = 1000
    while sumpos > 0:
        if not GLOB.stress_goon:
            return False
        time.sleep(1)
        pos = read_position()
        print(" - chiusura. Posizione petali:", pos)
        sumpos = sum(pos)
    sleep_ctrlc(2, "fine chiusura")
    if not GLOB.stress_goon:
        return False
    return True


def stop_request(*_):
    "Handler oper Ctrl-C"
    print("Ricevuto Ctrl-C")
    send_command_excp("X")
    GLOB.stress_goon = False


def stress_test():
    "procedura per muovere a lungo i motori"
    print(STRESS_WARN)
    ans = input("Numero cicli? ")
    try:
        remains = int(ans)
    except ValueError:
        remains = 0
    if remains == 0:
        return
    initialize(do_homing=False)
    GLOB.stress_goon = True
    num_cyc = 0
    while remains > 0:
        remains -= 1
        num_cyc += 1
        if not GLOB.stress_goon:
            print(END_ON_CTRLC)
            break
        if not stress_cycle(num_cyc):
            break


def main():
    "test comandi elementari"
    if "-h" in sys.argv:
        print(__doc__)
        sys.exit()
    GLOB.debug = "-d" in sys.argv

    if "-i" in sys.argv:
        test_inizializzazione(True)
        test_comandi(init=False)
        sys.exit()

    if "-I" in sys.argv:
        test_inizializzazione(False)
        test_comandi(init=False)
        sys.exit()

    if "-o" in sys.argv:
        test_inizializzazione(True)
        test_open()
        test_comandi(init=False)
        sys.exit()

    if "-O" in sys.argv:
        test_inizializzazione(False)
        test_open()
        test_comandi(init=False)
        sys.exit()

    if "-c" in sys.argv:
        test_inizializzazione(True)
        test_open()
        test_close()
        test_comandi(init=False)
        sys.exit()

    if "-C" in sys.argv:
        test_inizializzazione(False)
        test_open()
        test_close()
        test_comandi(init=False)
        sys.exit()

    if "-s" in sys.argv:
        signal.signal(signal.SIGINT, stop_request)
        stress_test()
        sys.exit()

    test_comandi()

if __name__ == "__main__":
    main()
