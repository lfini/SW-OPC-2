"""
tappo.py - Funzioni di supporto e test del tappo del telescopio OPC

Uso:

    python tappo.py [-d]        - test comandi generici

    python tappo.py [-d] -ioc   - test procedura complesse

dove:

    -d: attiva debug

    -i: test inizializzazione
    -o: test inizializzazione + apertura
    -c: test inizializzazione + apertura + chiusura

NOTA: al termine della procedura complessa selezionata viene attivato il test dei comandi generici

"""

import sys
import time
import serial
from serial.tools.list_ports import comports

__version__ = "1.0"
__author__ = "Luca Fini"
__date__ = "01/2026"

################## Parametri - devono corrispondere alle impostazioni nel firmware
TTY_SPEED = 9600
ORDINE_APERTURA = [0, 2, 1, 3]
ORDINE_CHIUSURA = [3, 1, 2, 0]

START_DELAY = 3   # ritardo movimento petali in apertura/chiusura (sec)

DEMOLTIPLICA_MECCANICA = 90.    # rapporto demoltiplica meccanica
MICROSTEP = 4                   # Impostazione microstep
GRADI_STEP = 1.8                # Angolo per singolo step
###################################################################################

GRADI_MICROSTEP = 1.8/MICROSTEP/DEMOLTIPLICA_MECCANICA

HELP = """
 Comandi di interrogazione:

 Cod. Risposta  Descrizione
 a    x,y,z,a   Accelerazione per i quattro petali
 i    xxxxxxx   Identificazione (numero di versione del firmware)
 m    x,y,z,a   Angolo max per i quattro petali
 p    x,y,z,a   Posizione dei 4 petali
 s    x,y,z,a   Velocità corrente per i quattro petali
 v    x,y,z,a   Velocità max per i quattro petali
 w    x,y,z,a   Stato limit switch: 1=aperto 0=chiuso

 Comandi di impostazione valori:

 Cod. Risposta  Descrizione
 MNxxx errcod   Imposta valore massimo angolo (in num di step) raggiungibile per petalo N
 ANxxx errcod   Imposta valore accelerazione (steps/sec^2) per petalo N
 VNxxx errcod   Imposta valore velocità massima per petalo N

 Comandi di movimento:

 Cod. Risposta  Descrizione
 0N    errcod    Imposta posizione corrente come 0
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

SUCCESS = "0"

CODICI_STATO = {
    SUCCESS: "Comando eseguito",
    "1": "Numero petalo errato",
    "2": "Comando non eseguibile con petalo in moto",
    "3": "Superamento limite",
    "4": "Comando non riconosciuto",
    "8": "Operazione non conclusa",
    "9": "Controller non connesso",
}

HOMING_STEP = int(0.25 * GRADI_MICROSTEP + 0.5)
MAX_HOMING_STEPS = 10

class MotorStatus:
    "Stato di un motore"
    def __init__(self, my_order):
        self.my_order = my_order
        self.homed = False
        self.last_error = ""

    def _speed0(self, ntryes=0):
        "Attende che il motore sia fermo"
        while ntryes > 0:
            ntryes -= 1
            time.sleep(1)
            ret = send_command("s")
            if ret in CODICI_STATO:
                self.error("lettura velocità", ret)
                return False
            cur_speed = float(ret.split(",")[self.my_order])
            if cur_speed == 0.0:
                return True
        self.error("stop timeout", "8")
        return False


    def error(self, spec, errcod):
        "Genera stringa di errore"
        self.last_error = f"{spec} - {CODICI_STATO[errcod]}"

    def home(self):
        "posiziona/verifica petalo 'at home' return False in caso di errore"
        self.last_error = ""
        steps = MAX_HOMING_STEPS
        while steps:
            steps -= 1
            ret = send_command(f"c{self.my_order}{HOMING_STEP}")
            if ret != SUCCESS:
                self.error("step chiusura", ret)
                return False
            if not self._speed0(20):
                return False
            ret = send_command("w")
            if ret in CODICI_STATO:
                self.last_error = CODICI_STATO[ret]
                return False
            switches = [int(x) for x in ret.split(",")]
            if switches[self.my_order] == 1:    # limit switch open. Imposta posizione 0
                ret = send_command(f"0{self.my_order}")
                if ret != SUCCESS:
                    self.last_error = CODICI_STATO[ret]
                    self.error("imposta posizione 0", ret)
                    return False
                self.homed = True
                return True
        self.error("timeout", "8")
        return False


class GLOB:  # pylint: disable=R0903
    "global variables"
    debug = False
    serial = None
    ident = ""
    motors = [MotorStatus(idx) for idx in range(4)]
    log = print
    home_all = False
    open_all = False

def _debug(text):
    "mostra info per debug"
    if GLOB.debug:
        print("DBG>", text)


def send_command(cmd):
    "send command to shutter controlleri, Return full reply"
    tcmd = ("!" + cmd + ":").encode("ascii")
    _debug(f"sending command: {tcmd}")
    try:
        GLOB.serial.write(tcmd)
        line = GLOB.serial.readline()
    except:  # pylint: disable=W0702
        ret = "9"
    else:
        ret = line.decode("utf8").strip()
    _debug(f"command returns: {ret}")
    return ret


def init_serial(tty):
    "initialize serial communication"
    _debug(f"Trying: {tty}")
    try:
        GLOB.serial = serial.Serial(tty, TTY_SPEED, timeout=2)
    except:  # pylint: disable=W0702
        return "9"
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
    return "9"


################### funzioni per controllo
def find_tty():
    "find and open serial line"
    _debug("Looking for connected controller")
    if sys.platform == "linux":
        template = "tty"
    elif sys.platform == "win32":
        template = "COM"
    else:
        raise RuntimeError(f"Not supported: {sys.platform}")
    GLOB.init = False
    GLOB.serial = None
    ports = comports()
    device = None
    ident = ""
    for port in ports:
        if template in port.description:
            ident = init_serial(port.device)
            if not ident.startswith("9"):
                device = port.device
                GLOB.homed = [False] * 4
                break
    if device is not None:
        _debug(f"controller found on tty: {device}")
    else:
        _debug("tty NOT found")
    return ident


def set_debug(enable=True):
    "Abilita/disabilita debug"
    GLOB.debug = enable

def set_log(log_func):
    "Cambia funzione di log. log_func: funzione che accetta una stringa"
    GLOB.log = log_func


def reply(cmd, msg):
    "interpretazione risposte al comando"
    ret = msg.split(",")
    match cmd[0]:
        case 'a':
            print("REPLY - Accelerazioni:", msg, "(step/s^2)")
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
            print("REPLY:", ret, "- Inatteso!")

def home_all():
    "Procedura di homing per tutti i petali"
    GLOB.home_all = False
    GLOB.log("Inizio procedura homing")
    for idx in ORDINE_CHIUSURA:
        motor = GLOB.motors[idx]
        GLOB.log(f"Homing petalo {idx}")
        if not motor.home():
            GLOB.log(f"Errore homing petalo {idx}: {motor.last_error}")
            send_command("X")
            return False
    GLOB.home_all = True
    GLOB.log("Procedura homing OK")
    return True

def initialize():
    "initialize connection and set home for all petals"
    GLOB.ident = find_tty()
    if GLOB.ident == "9":
        GLOB.log("Controllore non connesso")
        return False
    GLOB.log(f"Controllore connesso: {GLOB.ident}")
    return home_all()


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
        cur_diff = sum_pos - sum(int(x) for x in ret.split(","))
        if cur_diff == 0:
            break
        if prev_diff is not None and cur_diff == prev_diff:
            GLOB.log("Errore: qualche motore apparentemente fermo!")
            return False
    GLOB.log("Posizione raggiunta")
    return True


def open_all():
    "Apertura in ordine corretto di tutti i petali"
    GLOB.open_all = False
    if GLOB.home_all:
        ret = send_command("m")
        if ret in CODICI_STATO:
            GLOB.log("Errore lettura pos. max: "+CODICI_STATO[ret])
            return False
        max_pos = [int(x) for x in ret.split(",")]
        for idx in ORDINE_APERTURA:
            GLOB.log(f"Apertura petalo: {idx}")
            ret = send_command(f"g{idx}{max_pos[idx]}")
            if ret != SUCCESS:
                GLOB.log(f"Errore apertura petalo {idx}: {GLOB.motors[idx].last_error}")
                send_command("X")     # stop all petals
                return False
            time.sleep(START_DELAY)
        max_sum = sum(max_pos)
        GLOB.open_all = _wait_sum(max_sum)
        return GLOB.open_all
    GLOB.log("Errore: procedura di homing non completata")
    return False


def close_all():
    "Chiusura in ordine corretto di tutti i petali"
    if GLOB.open_all:
        for idx in ORDINE_CHIUSURA:
            GLOB.log(f"Chiusura petalo: {idx}")
            ret = send_command(f"g{idx}0")
            if ret != SUCCESS:
                GLOB.log(f"Errore chiusura petalo {idx}: {GLOB.motors[idx].last_error}")
                send_command("X")
                return False
            time.sleep(START_DELAY)
        status = _wait_sum(0)
        if status:
            return home_all()
        return False
    GLOB.log("Errore: petali non aperti")
    return False


def test_comandi(init=True):
    "test comandi elementari"
    if init:
        print("inizializzazione linea seriale")
        ident = find_tty()
        print()
        if ident == "9":
            print("Errore: controllore non connesso")
            sys.exit()
        else:
            print("Controllore connesso:", ident)

    print(WARNING_1)
    while True:
        print()
        cmd = input("Comando (q: stop, ?/invio: help)? ").strip()
        if not (cmd) or cmd[:1] == "?":
            print(HELP)
            continue
        if cmd[:1] == "q":
            break
        ret = send_command(cmd)
        if ret in CODICI_STATO:
            print("REPLY:", ret, "-", CODICI_STATO[ret])
        else:
            reply(cmd, ret)

def test_inizializzazione():
    "prova procedura inizializzazione (+ homing)"
    ret = initialize()
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


def main():
    "test comandi elementari"
    if "-h" in sys.argv:
        print(__doc__)
        sys.exit()
    GLOB.debug = "-d" in sys.argv

    if "-i" in sys.argv:
        test_inizializzazione()
        test_comandi(init=False)
        sys.exit()

    if "-o" in sys.argv:
        test_inizializzazione()
        test_open()
        test_comandi(init=False)
        sys.exit()

    if "-c" in sys.argv:
        test_inizializzazione()
        test_open()
        test_close()
        test_comandi(init=False)
        sys.exit()

    test_comandi()

if __name__ == "__main__":
    main()
