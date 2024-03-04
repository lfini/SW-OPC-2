"""
logfile.py - supporto per logging
"""

import sys
import platform
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

#pylint: disable=C0413

from opc.version import get_version        # pylint: disable=C0413
from opc.sendlog import sendlog

LONG_FMT = "%Y-%m-%d %H:%M:%S"
SHORT_FMT = "%H:%M:%S"

def strfhigh():
    "Genera timestamp con millisecondi"
    ttt = time.time()
    frac = int((ttt-int(ttt))*1000)
    return time.strftime(LONG_FMT, time.localtime(ttt))+f'.{frac:03d}'

class Logger:                                  # pylint: disable=R0903,R0902
    "classe per gestione logging"
    def __init__(self, logdir, logtag, timestamp='long',      # pylint: disable=R0913
                 nodup=False, debug=False):
        name = os.path.join(logdir, time.strftime("%Y-%m-%d-")+logtag+".log")
        self.logname = os.path.abspath(name)
        self.logf = open(self.logname, "a", encoding='utf-8')       # pylint: disable=R1732
        self.time0 = time.time()
        print("--- Inizio logging:", time.strftime(LONG_FMT), file=self.logf)
        self.debug = debug
        self.nodup = nodup
        self.numdup = 0
        self.lastline = ""
        print("--- Versione istallazione:", get_version(), file=self.logf)
        print("--- platform:", platform.uname(), file=self.logf)
        print("--- python version:", sys.version, file=self.logf)
        if isinstance(timestamp, str):
            if timestamp.lower().startswith("h"):      # Usa formato alta precisione per timestamp
                self.prefix = strfhigh
            elif timestamp.lower().startswith("l"):      # Usa formato esteso per timestamp
                self.prefix = lambda x=LONG_FMT: time.strftime(x)
            elif timestamp.lower().startswith("s"):    # Usa formato breve per timestamp
                self.prefix = lambda x=SHORT_FMT: time.strftime(x)
            elif timestamp.lower().startswith("r"):    # Usa formato relativo per timestamp
                self.prefix = lambda: f"{(time.time()-self.time0):.3f}"
            else:
                self.prefix = lambda: ''
        else:
            if timestamp:
                self.prefix = lambda x=LONG_FMT: time.strftime(x)
            else:
                self.prefix = lambda: ''

    def mark(self, line):
        "Aggiunge linea al logfile"
        if self.debug:
            print("LOG>", line)
        if self.nodup and self.lastline == line:
            self.numdup += 1
            return
        self.lastline = line
        if self.numdup:
            print(" ...", self.numdup, "duplicated lines", file=self.logf)
            self.numdup = 0
        print(self.prefix(), line, file=self.logf)

    def stop(self):
        "Termina il logger"
        self.logf.close()
        sendlog(self.logname)

    def flush(self):
        "Forza scrittura buffer"
        self.logf.flush()

def test():
    "Codice per test"
    lll = Logger('.', 'prova', timestamp='high')
    lll.mark("primo messaggio di prova")
    time.sleep(0.250)
    lll.mark("secondo messaggio di prova (dopo 250 ms)")
    lll.stop()
    print('Generato file:', lll.logname)

if __name__ == '__main__':
    test()
