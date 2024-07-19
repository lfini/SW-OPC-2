'''
OPC - GUI per gestione osservazioni. Vers. {}

Uso:
        python opc_gui.py [-d] [-D] [-h] [-k] [-p port] [-s] [-T]

Dove:
       -d  Attiva debug locale GUI
       -D  Attiva debug controller cupola
       -h  Mostra questa pagina ed esce
       -k  Usa simulatore di scheda k8055
       -p  Attiva il modo "alpaca" del server della cupola sul port dato
       -s  Usa simulatore di telescopio
       -T  Attiva debug TelSampler
'''

import sys
import getopt
import os.path
import pprint
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# pylint: disable=C0413
from opc import utils
from opc import dome_ctrl as dc
from opc import telsamp as ts
from opc.configure import MakeConfig
import dtracker as dt
from hgui import HomerGUI
import widgets as wg

class _GB:           # pylint: disable=R0903
    'globals senza usare global'
    debug = False
    sim_tel = False

def _debug(par):
    'Scrivi linea di debug'
    if _GB.debug:
        print('GUI DBG>', par)

class MyConfig(tk.Frame):
    'pannello per configurazione'
    def __init__(self, master):
        super().__init__(master, bg=dt.BACKGROUND)
        intern = tk.Frame(self)
        self.cfg = MakeConfig(intern)
        self.cfg.pack()
        tk.Button(intern, text='REGISTRA', padx=10, pady=20,
                  command=self.cfg.saveme).pack(expand=1, fill=tk.X)
        intern.pack()



class MainPanel(ttk.Notebook):          #pylint: disable=R0901
    'Pannello principale'
    def __init__(self, master, config, datadir, dct, tls, dcterror=None):     #pylint: disable=R0913
        _debug('MainPanel:')
        _debug(f'  config={pprint.pformat(config)}')
        _debug(f'  {datadir=})')
        super().__init__(master)
        self.dtrk = dt.DTracker(self, config, dct, tls, dcterror)
        self.hgui = HomerGUI(self, config, datadir, simul=_GB.sim_tel, debug=_GB.debug)
        self.cfg = MyConfig(self)
        dummy = tk.Frame(self)
        self.add(self.dtrk, text='Cupola') #, sticky='nwe')
        self.add(self.hgui, text='Homer') #, sticky='nwe')
        spacer = ' '*130
        self.add(dummy, text=spacer, state=tk.DISABLED, sticky='nwe')
        self.add(self.cfg, text='Configura', sticky='nwe')

    def endpanel(self):
        'Gestione terminazione'
        _debug('Ricevuto segnale terminazione')
        self.hgui.stop()
        self.dtrk.stop()
        _debug('Inviato stop ai due pannelli')
        self.after(1000, self.endwait)

    def endwait(self):
        'Aspetta stop dei pannelli'
        _debug('attesa terminazione pannelli')
        notyet = self.hgui.running
        if notyet:
            self.after(1000, self.endwait)
        else:
            _debug('pannelli terminati')
            self.master.destroy()

def main():                 #pylint: disable=R0914,R0912,R0915
    'funzione main'
    if '-h' in sys.argv:
        root = tk.Tk()
        wdg = wg.MessageText(root, __doc__.format(utils.get_version()))
        wdg.pack(expand=1)
        root.mainloop()
        sys.exit()
    try:
        opts, _unused = getopt.getopt(sys.argv[1:], 'Ddkp:sT')
    except getopt.error:
        print('Errore negli argomenti')
        sys.exit()
    _GB.debug = False
    config = utils.get_config()
    sim_k8055 = False
    dcdebug = False
    ipport = 0
    mode = ''
    _GB.sim_tel = False
    tel_debug = False
    for opt, val in opts:
        if opt == '-d':
            _GB.debug = True
        elif opt == '-D':
            dcdebug = True
        elif opt == '-p':
            ipport = int(val)
        elif opt == '-s':
            _GB.sim_tel = True
            config = utils.get_config(simul=True)
            mode += ' [Sim. Tel.]'
        elif opt == '-k':
            mode += ' [Sim. K8055]'
            sim_k8055 = True
        elif opt == '-T':
            tel_debug = True
    root = tk.Tk()
    if not config:
        error = '\n\nErrore lettura del file di configurazione\n\n'
        wdg = wg.MessageText(root, error, bg=wg.ERROR_CLR)
        wdg.pack()
        root.mainloop()
        sys.exit()
    logname = utils.make_logname('dome')
    logger = utils.set_logger(logname)

    root.title(f"Pannello controllo OPC - v. {utils.get_version()}")
#   starter = ObsInit(root, config)
#   starter.grid()
#   wg.set_position(root, (0.01, 0.01))
#   root.wait_window(starter)
#   _debug('fine primo passo')
#   if not starter.valid:
#       sys.exit()
    if tel_debug:
        tls = ts.tel_start(logger, _GB.sim_tel)
    else:
        tls = ts.tel_start(None, _GB.sim_tel)
    error = None
    try:
        dct = dc.start_server(ipport=ipport, logger=logger, telsamp=tls,
                              sim_k8055=sim_k8055, language='it', debug=dcdebug)
    except Exception as exc:               # pylint: disable=W0703
        error = '\n\n'+str(exc)+'\n'
        dct = None
    datadir = config.get('local_store')
    style = ttk.Style()
    style.configure('TNotebook', background=dt.BACKGROUND)
    wdg = MainPanel(root, config, datadir, dct, tls, dcterror=error)
    wdg.pack()
    root.iconphoto(False, wg.get_icon('opclogo', 24))
    root.wm_protocol('WM_DELETE_WINDOW', wdg.endpanel)
    root.mainloop()
    if tls:
        tls.tel_stop()
    if dct:
        dct.stop_server()
    _debug('Opc GUI terminata')

if __name__ == '__main__':
    main()
