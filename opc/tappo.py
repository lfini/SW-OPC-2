"""
tappo.py - Funzioni di test del tappo del telescopio OPC

Uso:

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
__date__ = "01/2026"

TTY_SPEED = 9600


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

CODICI_STATO = {
    "0": "Comando eseguito",
    "1": "Numero petalo errato",
    "2": "Comando non eseguibile con petalo in moto",
    "3": "Superamento limite",
    "4": "Comando non riconosciuto",
    "9": "Controller non connesso",
}

MOTOR_ORDER = [0, 2, 1, 3]


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


def main():
    "test comandi elementari"
    if "-h" in sys.argv:
        print(__doc__)
        sys.exit()
    GLOB.debug = "-d" in sys.argv
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


if __name__ == "__main__":
    main()
