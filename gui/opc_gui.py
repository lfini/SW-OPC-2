'''
OPC - GUI per gestione osservazioni

Uso;:
        python opc_gui.py [-d] [-h] [-k] [-p port] [-s] [-v]

Dove:
       -d  Attiva debug locale GUI
       -D  Attiva debug controller cupola
       -h  Mostra questa pagina ed esce
       -k  Usa simulatore di scheeda k8055
       -p  Attiva il modo "alpaca" del server della cupola sul port dato
       -s  Usa simulatore di telescopio
'''

import sys
import getopt
import os.path
import time
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# pylint: disable=C0413
from opc import utils
import opc.widgets as wg
from opc import dome_ctrl as dc
from opc import tel_sampler as ts
from opclogger import ObsInit, OpcLogger
from dtracker import DTracker
from hgui import HomerGUI

__author__ = 'Luca Fini'
__version__ = '1.0'
__date__ = 'Marzo 2023'

class _GB:           # pylint: disable=R0903
    'globals senza usare global'
    debug = False

def _debug(*par):
    'Scrivi linea di debug'
    if _GB.debug:
        print('DBG>', *par)

class MainPanel(ttk.Notebook):
    'Pannello principale'
    def __init__(self, master, datadir, dct, tls):
        super().__init__(master)
        opcl = OpcLogger(self, datadir, tls)
        dtrk = DTracker(self, dct, tls)
        hgui = HomerGUI(self, datadir)
        self.add(opcl, text='OPC logger')
        self.add(dtrk, text='Cupola')
        self.add(hgui, text='Homer')

def main():                 #pylint: disable=R0915,R0912
    'funzione main'
    if '-v' in sys.argv:
        print(__version__)
        sys.exit()
    try:
        opts, _unused = getopt.getopt(sys.argv[1:], 'dhkp:st')
    except getopt.error:
        print('Errore negli argomenti')
        sys.exit()
    _GB.debug = False
    config = utils.get_config()
    sim_k8055 = False
    ipport = 0
    mode = ''
    sim_tel = False
    tel_sampler = True
    for opt, val in opts:
        if opt == '-d':
            _GB.debug = True
        elif opt == '-p':
            ipport = int(val)
        elif opt == '-s':
            sim_tel = True
            config = utils.get_config(simul=True)
            mode += ' [Sim. Tel.]'
        elif opt == '-h':
            print(__doc__)
            sys.exit()
        elif opt == '-k':
            mode += ' [Sim. K8055]'
            sim_k8055 = True
        elif opt == '-t':
            tel_sampler = False
    root = tk.Tk()
    if not config:
        error = '\n\nErrore lettura del file di configurazione\n\n'
        wdg = wg.MessageText(root, error, bg=wg.ERROR_CLR)
        wdg.pack()
        root.mainloop()
        sys.exit()
    logname = utils.make_logname('dome')
    logger = utils.set_logger(logname, debug=_GB.debug)

    root.title("Pannello controllo OPC")
    starter = ObsInit(root, config)
    starter.grid()
    wg.set_position(root, (0.01, 0.01))
    root.wait_window(starter)
    _debug('fine primo passo')
    if not starter.valid:
        sys.exit()
    if tel_sampler:
        tls = ts.tel_start(logger, sim_tel)
    else:
        tls = None
    error = None
    try:
        dct = dc.start_server(ipport=ipport, logger=logger, tel_sampler=tls, sim_k8055=sim_k8055)
    except Exception as exc:               # pylint: disable=W0703
        error = '\n\n'+str(exc)+'\n\n'
    if error:
        text = error+'\n\n'+__doc__
        wdg = wg.MessageText(root, text, bg=wg.ERROR_CLR)
        wdg.pack()
        root.mainloop()
        if tls:
            tls.tel_stop()
        sys.exit()
    wdg = MainPanel(root, starter.datadir, dct, tls)
    wdg.pack()
    root.iconphoto(False, wg.get_icon('opclogo', 24))
    root.mainloop()
    if tls:
        tls.tel_stop()
    dct.stop_server()

if __name__ == '__main__':
    main()
