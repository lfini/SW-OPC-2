"""
shutter_control.py - Controllo tappo del telescopio OPC
"""

import sys
import serial


if sys.platform == 'linux':
    TTY = "/dev/ttyACM0"
elif sys.platform == 'win32':
    TTY = "COM3"
else:
    raise RuntimeError(f"{sys.platform} non supportato")

SPEED = 9600

HELP = """
Comandi definiti:

Comandi di interrogazione:

 Cod. Risposta   Descrizione
 v    xxxxxxx    Identificazione (numero di versione del firmware)
 fN   1/0        Stato finecorsa.N (N=[0..3] num. petalo), 1: aperto, 0: chiuso
 pN   xxx        Posizione petalo N; xxx: gradi dalla posizione chiuso
 mN   1/0        Stato movimento petalo N (0: fermo, 1: in moto)
 M    xxxx       Valore angolo massimo

 Comandi operativi:

 Cod. Risposta   Descrizione
 aN   Ok/errore   Apri petalo N (inizia movimento in apertura)
 cN   Ok/errore   Chiudi petalo N (inzia movimento in chiusura)
 sN   Ok/errore   Stop (interrompe movimento del..) petalo N
 S    Ok/errore   Stop tutti i motori
 ixxx ang/errore  Imposta valore massimo angolo raggiungibile.
                   in caso di successo riporta il valore impostato
"""

REPLIES = {"Ok": "Comando correttamente eseguito", 
          "E01": "Indice motore errato", 
          "E02": "Massimo valore angolo illegale", 
          "E03": "Errore esecuzione comando", 
          "E04": "Comando non riconosciuto" }

class GLOB:               #pylint: disable=R0903
    "global variables"
    serial = None

def init_serial():
    "initialize serial communication"
    GLOB.serial = serial.Serial(TTY, SPEED, timeout=1)

def send_command(cmd):
    "send commad to shutter controller"
    tcmd = (cmd+":").encode("ascii")
    GLOB.serial.write(tcmd)
    return GLOB.serial.readline().strip()

def test():
    "simple test code"
    init_serial()
    while True:
        cmd = input("Comando (q: stop, ?: help)? ").strip()
        if cmd[:1] == 'q':
            break
        if cmd[:1] == '?':
            print(HELP)
            continue
        reply = send_command(cmd)
        print("REPL:", reply.decode("utf8"))

if __name__ == "__main__":
    test()
