"""
tappo.py - Controllo tappo del telescopio OPC

Uso per test:

    python tappo.py [-d]

dove:

    -d: attiva debug
"""

import sys
import time
from threading import Thread, Lock
import serial
from serial.tools.list_ports import comports


HOMING_TIMEOUT = 30  # Timeout in secondi per homing/chiusura
OPENING_TIMEOUT = 30  # Timeout in secondi per apertura

SPEED = 9600

SUCCESS = "Ok"

HOMING = "Homing/In chiusura"
ERROR = "Errore"
TIMEOUT = "Timeout"
CONNECTED = "Connesso"
OPENING = "In Apertura"
CLOSED = "Chiuso"
OPEN = "Aperto"

E05 = "E05"

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
    connected = False
    debug = False
    serial = None
    petal_status = [""] * 4
    petal_position = [None] * 4
    lock = Lock()
    max_angle = 0


def _debug(text):
    "mostra info per debug"
    if GLOB.debug:
        print("DBG>", text)


def init_serial(tty):
    "initialize serial communication"
    _debug(f"Trying: {tty}")
    try:
        GLOB.serial = serial.Serial(tty, SPEED, timeout=1)
    except:  # pylint: disable=W0702
        return ""
    time.sleep(2)    # wait controller setup
    ident = send_command("v")
    if "Tappo" in ident:
        return ident
    GLOB.serial = None
    return ""


def find_tty():
    "find serial line"
    _debug("Looking for connected controller")
    if sys.platform == 'linux':
        template = "tty"
    elif sys.platform == 'win32':
        template = "COM"
    else:
        raise RuntimeError(f"Not supported: {sys.platform}")
    ports = comports()
    device = None
    ident = ""
    for port in ports:
        if template in port.description:
            ident = init_serial(port.device)
            if ident:
                device = port.device
                break
    _debug(f"tty found: {device}")
    return ident


def send_command(cmd):
    "send command to shutter controlleri, Return full reply"
    tcmd = ("!" + cmd + ":").encode("ascii")
    _debug(f"sending command: {tcmd}")
    with GLOB.lock:
        GLOB.serial.write(tcmd)
        line = GLOB.serial.readline()
    _debug(f"command returns: {line}")
    return line.decode("utf8").strip()


def set_debug(enable=True):
    "abilita/disabilita debug"
    GLOB.debug = enable


#############################à funzioni di supporto
def _do_homing(nptl):
    "procedura di homing di un petalo da lanciare in un thread"
    GLOB.petal_status[nptl] = HOMING
    spos = send_command("c" + str(nptl))
    if spos.startswith("E"):
        GLOB.petal_status[nptl] = ERROR
        return
    timeout = HOMING_TIMEOUT
    while timeout:
        timeout -= 1
        time.sleep(1)
        status = send_command("p" + str(nptl))
        if status.startswith("E"):
            GLOB.petal_status[nptl] = ERROR
            return
        pos0 = int(status.split(",")[2])
        if pos0 == 0:
            GLOB.petal_status[nptl] = CLOSED
            return
    GLOB.petal_status[nptl] = TIMEOUT


def _do_open(nptl):
    "funzione apertura del petalo da lanciare in un thread"
    spos = send_command("a")
    if spos.startswith("E"):
        GLOB.status = ERROR
        return
    max_angle = int(spos)

    ret = send_command(f"o{nptl}")
    if ret != SUCCESS:
        GLOB.petal_status[nptl] = ERROR
        return
    GLOB.status = OPENING
    timeout = OPENING_TIMEOUT
    while timeout:
        time.sleep(1)
        timeout -= 1
        status = send_command("p" + str(nptl))
        if status.startswith("E"):
            GLOB.petal_status[nptl] = ERROR
            return
        params = status.split(",")
        pos = int(params[2])
        GLOB.petal_position[nptl] = pos
        moving = int(params[0])
        if abs(pos - max_angle) < 5 and not moving:
            GLOB.petal_status[nptl] = OPEN
            return
    GLOB.petal_status[nptl] = TIMEOUT
    return


########## Funzioni complesse


def do_open():
    "apertura tappo"
    print("inizio procedura di apertura")
    send_command("A150")
    print("Angolo massimo impostato a 150 step")
    for n_petal in range(4):
        thread = Thread(target=_do_open, args=(n_petal,))
        thread.start()

    while True:
        time.sleep(1)
        for n_petal in range(4):
            print(
                f"Stato petalo {n_petal}: {GLOB.petal_status[n_petal]}",
                f"- Pos.: {GLOB.petal_position[n_petal]}"
            )
        if all(GLOB.petal_status[i] in (OPEN, ERROR, TIMEOUT) for i in range(4)):
            break


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
        ret = send_command(cmd)
        long = REPLIES.get(ret, "")
        if long:
            print("REPLY:", ret, "-", long)
        else:
            print("REPLY:", ret)


def do_homing():
    "Esegui procedura di homing (chiusura) del tappo"
    print("inizio procedura di homing")
    threads = [None] * 4
    for n_petal in range(4):
        threads[n_petal] = Thread(target=_do_homing, args=(n_petal,))
        threads[n_petal].start()

    while True:
        time.sleep(1)
        for n_petal in range(4):
            print(f"Stato petalo {n_petal}: {GLOB.petal_status[n_petal]}")
        if all(GLOB.petal_status[i] in (CLOSED, ERROR, TIMEOUT) for i in range(4)):
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
    else:
        print("Errore: controllore non connesso")
        sys.exit()

    while True:
        print(MENU)
        ans = input("Scelta? ").strip().lower()[:1]
        if ans == "m":
            manual_commands()
        elif ans == "h":
            do_homing()
        elif ans == "a":
            do_open()
        elif ans == "q":
            break


if __name__ == "__main__":
    main()
