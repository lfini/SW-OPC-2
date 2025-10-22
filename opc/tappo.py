"""
tappo.py - Controllo tappo del telescopio OPC

Uso per test:

    python tappo.py [-d] 0/1

dove:
    0:  lancia test 0 (invio comandi elementari)
    1:  lancia test 1 (test procedura completa di apertura / chiusura)

    -d: attiva debug
"""

import sys
import time
from threading import Thread, Lock
import serial


if sys.platform == "linux":
    TTY = "/dev/ttyACM0"
elif sys.platform == "win32":
    TTY = "COM3"
else:
    raise RuntimeError(f"{sys.platform} non supportato")

SPEED = 9600

SUCCESS = 'Ok'

HOMING = "Homing"
ERROR = "Errore"
CONNECTED = "Connesso"
MOVING = "In movimento"
CLOSED = "Chiuso"
OPEN = "Aperto"

DO_OPEN = 1
DO_CLOSE = 2

E05 = "E05"

HELP = """
 Comandi di interrogazione:

 Cod. Risposta   Descrizione
 v    xxxxxxx    Identificazione (numero di versione del firmware)
 fN   1/0        Stato finecorsa.N (N=[0..3] num. petalo), 1: aperto, 0: chiuso
 pN   xxxx       Posizione petalo N; xxx: numero step dalla posizione chiuso
 mN   1/0        Stato movimento petalo N (0: fermo, 1: in moto)
 M    xxxx       Valore angolo massimo (in step dalla posizione chiuso)
 I    xxxx       Tempo morto (idle) nel ciclo (millisec)

 Comandi operativi:

 Cod. Risposta   Descrizione
 aN   Ok/errore   Apri petalo N (inizia movimento in apertura)
 cN   Ok/errore   Chiudi petalo N (inzia movimento in chiusura)
 ixxx ang/errore  Imposta valore massimo angolo (in num di step) raggiungibile.
                   in caso di successo riporta il valore impostato
 sN   Ok/errore   Stop (interrompe movimento del..) petalo N
 S    Ok/errore   Stop tutti i motori

 Comandi per modo test:
 T    Ok/errore   Imposta modo test (consente alcuni test in assenza di motori)
 xNM  Ok/errore   Simula chiusura/apertura del limit switch N
                   (M == 0: aperto; M == 1: chiuso)
"""

WARNING = """
****************************************************
Attenzione il programma consente di mandare qualunque
comando al controller del tappo.

           USARE CON CAUTELA!
*****************************************************
"""
REPLIES = {
    "Ok": "Comando eseguito",
    "E00": "Valore max angolo non impostato",
    "E01": "Indice motore errato",
    "E02": "Massimo valore angolo illegale",
    "E03": "Errore esecuzione comando",
    "E04": "Comando non riconosciuto",
    E05: "Controller non connesso",
}


class GLOB:  # pylint: disable=R0903
    "global variables"
    status = ""
    connected = False
    debug = False
    serial = None
    homing_status = [""] * 4  # HOMING, CLOSED, ERROR o indefinito
    lock = Lock()
    max_angle = 0


def _debug(text):
    "mostra info per debug"
    if GLOB.debug:
        print("DBG>", text)


def init_serial():
    "initialize serial communication"
    try:
        GLOB.serial = serial.Serial(TTY, SPEED, timeout=1)
    except:                      #pylint: disable=W0702
        GLOB.status = ERROR
        GLOB.connected = False
        GLOB.max_angle = 0
    else:
        GLOB.connected = True
        time.sleep(3)
        GLOB.status = CONNECTED
        GLOB.max_angle = get_max_angle()
    return GLOB.connected


def send_command_raw(cmd):
    "send command to shutter controlleri, Return full reply"
    if not GLOB.connected:
        return E05
    tcmd = ("!"+cmd+":").encode("ascii")
    _debug(f"sending command: {tcmd}")
    with GLOB.lock:
        GLOB.serial.write(tcmd)
        line = GLOB.serial.readline()
    _debug(f"command returns: {line}")
    return line.decode("utf8").strip()

def send_command(cmd):
    "send command and remove verification code from reply"
    ret = send_command_raw(cmd)
    return ret.split("-")[0]

def set_debug(enable=True):
    "abilita/disabilita debug"
    GLOB.debug = enable


def get_status():
    "read status of four petals"
    ret = {"global": GLOB.status}
    if GLOB.connected:
        ret["positions"] = [int(send_command("p" + str(x))) for x in range(4)]
        ret["homing"] = GLOB.homing_status.copy()
    else:
        ret["positions"] = [-1]*4
        ret["homing"] = [""]*4
    return ret


def get_max_angle():
    "laggi valore angolo massimo"
    ret = send_command("M")
    if ret.startswith("E"):
        return -1
    return int(ret)

#############################à funzioni di supporto
def _do_homing():
    "procedura di homing"
    for nptl in range(4):
        GLOB.homing_status[nptl] = HOMING
        spos = send_command("p" + str(nptl))
        pos0 = int(spos)
        if pos0 == 0:
            GLOB.homing_status[nptl] = CLOSED
            continue
        send_command_raw("c" + str(nptl))
        endtime = time.time() + 5
        while True:
            time.sleep(1)
            if time.time() > endtime:
                GLOB.homing_status[nptl] = ERROR
                send_command_raw("s" + str(nptl))
                break
            spos = send_command("p" + str(nptl))
            pos = int(spos)
            if pos == 0:
                GLOB.homing_status[nptl] = CLOSED
                break
            if pos < pos0:
                endtime += 1
                pos0 = pos
    if all(x==CLOSED for x in GLOB.homing_status):
        GLOB.status = CLOSED
    else:
        GLOB.status = ERROR

def _do_action(mode):
    "funzione apertura/chiusura da lanciare con thread"
    def check_max_angle(npt):
        spos = send_command(f"p{npt}:")
        if spos.startswith("E"):
            GLOB.status = ERROR
            return False
        pos = int(spos)
        return pos-GLOB.max_angle >= 0

    def check_closed(npt):
        ret = send_command(f"f{npt}:")
        return ret == CLOSED

    GLOB.status = MOVING
    if mode == DO_OPEN:
        cmd = "a"
        check_func = check_max_angle
    else:
        cmd = "c"
        check_func = check_closed
    for nptl in range(4):
        ret = send_command(f"{cmd}{nptl}")
        if ret != SUCCESS:
            GLOB.status = ERROR
            break
        time.sleep(3)
    if GLOB.status == ERROR:
        return

    for nptl in range(4):  # Verifica che tutti e quattro i petali
                           # abbiano raggiunto la posizione richiesta
        endtime = time.time()+5
        while True:
            time.sleep(1)
            if time.time() > endtime:
                GLOB.status = ERROR
                break
            if check_func(nptl):
                break
            endtime = time.time()+1
        if GLOB.status == ERROR:
            break
    if GLOB.status == MOVING:
        GLOB.status = OPEN if mode == DO_OPEN else CLOSED


########## Funzioni complesse

def start_homing():
    "lancia procedura di homing"
    if GLOB.status != CONNECTED:
        return False
    thread = Thread(target=_do_homing)
    thread.start()
    return True


def apri():
    "apertura tappo"
    if GLOB.status in CLOSED:
        return False
    thread = Thread(target=_do_action, args=(DO_OPEN, ))
    thread.start()
    return True

def chiudi():
    "chiusura tappo"
    if GLOB.status != OPEN:
        return False
    thread = Thread(target=_do_action, args=(DO_CLOSE, ))
    thread.start()
    return True


def test0():
    "test comandi elemantari"
    print("inizializzazione linea seriale")
    stat = init_serial()
    print()
    if stat:
        ident = send_command_raw("v:").strip()
        print("Controllore connesso:", ident)
    else:
        print("Errore: controllore non connesso")
        sys.exit()
    print(WARNING)
    while True:
        cmd = input("Comando (q: stop, ?/invio: help)? ").strip()
        if not(cmd) or cmd[:1] == "?":
            print(HELP)
            continue
        if cmd[:1] == "q":
            break
        reply = send_command_raw(cmd)
        long = REPLIES.get(reply, "")
        print("REPL:", reply, "-", long)


def test1():
    "test comandi complessi"
    print("inizializzazione linea seriale")
    init_serial()
    print("inizio procedura di homing")
    start_homing()
    while True:
        time.sleep(2)
        status = get_status()
        print(f"Stato controller: {status}")
        if status["global"] in (CLOSED, ERROR):
            break
    if status["global"] == ERROR:
        print("Procedura di homing fallita")
        sys.exit()
    print()
    print("Inizio apertura tappo")
    apri()
    while True:
        time.sleep(2)
        status = get_status()
        del status["homing"]
        print(f"Stato controller: {status}")
        if status["global"] in (OPEN, ERROR):
            break
    if status["global"] == ERROR:
        print("Procedura di apertura fallita")
        sys.exit()
    print()
    print("Inizio chiusura tappo")
    chiudi()
    while True:
        time.sleep(2)
        status = get_status()
        del status["homing"]
        print(f"Stato controller: {status}")
        if status["global"] in (CLOSED, ERROR):
            break
    if status["global"] == ERROR:
        print("Procedura di chiusura fallita")
        sys.exit()


if __name__ == "__main__":
    GLOB.debug = "-d" in sys.argv
    what = sys.argv[-1]
    if what == "0":
        test0()
    elif what == "1":
        test1()
    else:
        print(__doc__)
