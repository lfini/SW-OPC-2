"""
tappo.py - Controllo tappo del telescopio OPC

Uso per test:

    python tappo.py [-d]

dove:

    -d: attiva debug
"""

import sys
import time
import serial
from serial.tools.list_ports import comports

__version__ = "1.0"
__author__ = "Luca Fini"
__date__ = "26/10/2025"

##################### Valori da aggiustare in base
                    # alla configurazione di Arduino
MAX_ANGLE = 150     # impostazione angolo massimo (in steps)
TO_DEGREES = 1.8    # Converte step in gradi
SPEED = 9600        # Velocità linea seriale
#####################

############### Codici di stato/errore
SUCCESS = "Ok"

CLOSED = "Chiuso"
CLOSING = "Closing"
CONNECTED = "Connesso"
ERROR = "Errore"
OPEN = "Aperto"
OPENING = "In Apertura"
STOPPED = "Fermo"
UNCONNECTED = "Non connesso"
UNKNOWN = "Sconosciuto"
######################################

HELP = """
 Comandi di interrogazione:

 Cod. Risposta   Descrizione
 v    xxxxxxx    Identificazione (numero di versione del firmware)
 pN   M,D,P,L    Stato petalo N. D: 1/0 in moto/fermo, D: 1/0 direzione moto,
                 P: posizione (n.step da chiuso), L: limit switch (1:; aperto, 0:chiuso)
 a    xxxx       Valore angolo massimo (in step dalla posizione chiuso)

 Comandi operativi:

 Cod. Risposta   Descrizione
 oN   Ok/errore   Apri petalo N (inizia movimento in apertura)
 cN   Ok/errore   Chiudi petalo N (inzia movimento in chiusura)
 Axxx ang/errore  Imposta valore massimo angolo (in num di step) raggiungibile.
                  in caso di successo riporta il valore impostato
 sN   Ok/errore   Stop (interrompe movimento del..) petalo N
 S    Ok/errore   Stop tutti i motori

 Comandi per debug:

 dN   aaaa       Legge informazioni su stato petalo N
 n    xxxx       Legge numero di comandi ricevuti

 Comando per tentativo riconnessione:

 r    Ok/errore
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
    "E05": "Controller non connesso"
}


class GLOB:  # pylint: disable=R0903
    "global variables"
    debug = False
    serial = None
    max_angle = 0


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
    except:           #pylint: disable=W0702
        ret = "E05"
    else:
        ret = line.decode("utf8").strip()
    _debug(f"command returns: {ret}")
    return ret


def init_serial(tty):
    "initialize serial communication"
    _debug(f"Trying: {tty}")
    try:
        GLOB.serial = serial.Serial(tty, SPEED, timeout=1)
    except:  # pylint: disable=W0702
        return "E05"
    time.sleep(2)    # wait controller setup
    ident = send_command("v")
    if "Tappo" in ident:
        return ident
    try:
        GLOB.serial.close()
    except:  # pylint: disable=W0702
        pass
    GLOB.serial = None
    return "E05"


################### funzioni per controllo

def find_tty():
    "find and open serial line "
    _debug("Looking for connected controller")
    if sys.platform == 'linux':
        template = "tty"
    elif sys.platform == 'win32':
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
            if not ident.startswith("E"):
                device = port.device
                send_command(f"A{MAX_ANGLE}")
                GLOB.max_angle = MAX_ANGLE
                GLOB.homed = False
                break
    if device is not None:
        _debug(f"tty found: {device}. Angolo Max.: {send_command('a')}")
    else:
        _debug("tty NOT found")
    return ident


def set_debug(enable=True):
    "abilita/disabilita debug"
    GLOB.debug = enable


def get_status(nptl):
    "riporta lo stato del petalo dato: (stato, posizione)"
    if GLOB.serial is None:
        return (UNCONNECTED, 0)
    if not GLOB.homed:
        return (CONNECTED, 0)
    reply = send_command(f"p{nptl}")
    status = UNKNOWN
    if reply.startswith("E"):
        if reply == "E05":
            status, position = (UNCONNECTED, 0)
        else:
            status, position = (ERROR, 0)
    else:
        reply = reply.split(",")
        position = int(reply[2])
        if reply[0] == "0":
            if reply[3] == "0":
                status = CLOSED
            elif abs(position-GLOB.max_angle) < 2:
                status = OPEN
            else:
                status = STOPPED
        else:
            if reply[1] == "1":
                status = OPENING
            else:
                status = CLOSING
    return (status, position)


def stop():
    "interrompe movimento dei quattro petali"
    send_command("S")


def start_homing():
    "Lancia procedura di homing/chiusura dei quatttro petali"
    ret = [send_command(f"c{x}") for x in range(4)]
    GLOB.homed = True
    return ret


def start_opening():

    "Lancia procedura di chiusura"
    ret = [send_command(f"o{x}") for x in range(4)]
    return ret

def max_angle():
    "Riporta valore angolo massimo"
    return GLOB.max_angle

########## Funzioni per test

def manual_commands():
    "invio comandi in modo manuale"
    print(WARNING)
    while True:
        cmd = input("Comando (q: stop, ?/invio: help)? ").strip()
        if not (cmd) or cmd[:1] == "?":
            print(HELP)
            continue
        if cmd[:1] == "q":
            break
        if cmd[:1] == "r":
            ret = find_tty()
        else:
            ret = send_command(cmd)
        long = REPLIES.get(ret, "")
        if long:
            print("REPLY:", ret, "-", long)
        else:
            print("REPLY:", ret)


def do_open():
    "apertura tappo"
    print("inizio procedura di apertura")
    rets = start_opening()

    for  nptl, ret in enumerate(rets):
        print(f" - petalo #{nptl}: {ret}")

    if any(x.startswith("E") for x in rets):
           return

    while True:
        time.sleep(1)
        stat4 = []
        for nptl in range(4):
            stat = get_status(nptl)
            print(f"Stato petalo {nptl}: {stat[0]} - Pos.: {stat[1]}")
            stat4.append(stat[0])
        if all(x in (OPEN, ERROR, UNCONNECTED) for x in stat4):
            break

def do_close():
    "Esegui procedura di homing/chiusura del tappo"
    print("inizio procedura di chiusura/homing")
    rets = start_homing()

    for  nptl, ret in enumerate(rets):
        print(f" - petalo #{nptl}: {ret}")

    if any(x.startswith("E") for x in rets):
           return

    while True:
        time.sleep(1)
        stat4 = []
        for nptl in range(4):
            stat = get_status(nptl)
            stat4.append(stat[0])
            print(f"Stato petalo {nptl}: {stat[0]} - Pos.: {stat[1]}")
        if all(x in (CLOSED, ERROR, UNCONNECTED) for x in stat4):
            break


MENU = """
Seleziona operazione:
      m: comandi manuali
      h: homing (e chiusura)
      a: apertura
      q: termina
"""


def main():
    "test comandi elementari"
    if "-h" in sys.argv:
        print(__doc__)
        sys.exit()
    GLOB.debug = "-d" in sys.argv
    print("inizializzazione linea seriale")
    ident = find_tty()
    print()
    if ident:
        print("Controllore connesso:", ident)
        maxa = send_command("a")
        print(f"Angolo massimo impostato a {maxa} step")
    else:
        print("Errore: controllore non connesso")
        sys.exit()

    while True:
        print(MENU)
        ans = input("Scelta? ").strip().lower()[:1]
        if ans == "m":
            manual_commands()
        elif ans == "h":
            do_close()
        elif ans == "a":
            do_open()
        elif ans == "q":
            break


if __name__ == "__main__":
    main()
