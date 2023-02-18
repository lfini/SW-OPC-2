#!/usr/bin/python3
'''
OPC - Interfaccia grafica per controllo manuale  cupola

Uso:
        python dome-gui.py [-d] [-k] [-h] [-v]

Dove:
       -d  Attiva debug
       -h  Mostra questa pagina ed esce
       -k  Usa simulatore di scheda k8055
       -n  Disabilita modo 'slave'
       -s  Usa simulatore di telescopio
'''

import sys
import os.path
import time

import tkinter as tk

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# pylint: disable=C0413
from dome import dome_ctrl as dc
from opc.widgets import Number, Controller, get_icon, Led

# pylint: disable=C0321
__author__ = 'Luca Fini'
__version__ = '1.0'
__date__ = 'Dicembre 2022'

BLACK = '#000000'
CYAN = '#00ffff'
CYAN3 = '#E0ffff'

LIGHTGREEN = '#90EE90'
GRAY = '#808080'
LIGHTRED = '#ff8080'
YELLOW = '#ffff00'
YELLOW3 = '#ffd700'
RED = '#ff0000'
WHITE = '#ffffff'
DISABLED_BG = '#808080'
DEFAULT_BG = '#CC6600'

GUI_REFRESH = 300       # Intervallo (ms) refresh della GUI
MSG_PERSISTENCE = 5     # Durata messaggio in linea informativa (secondi)

NAN = float('nan')

class GLOB:           # pylint: disable=R0903
    'globals senza usare global'
    root = None
    noslave = False   # disabilita modo 'slave' (per test)

ACTION_TABLE = {'apri_vano': dc.open_shutter,
                'chiudi_vano': dc.close_shutter,
                'home': dc.find_home,
                'move_left': dc.start_left,
                'move_right': dc.start_right,
                'park': dc.park,
                'step_left': lambda: dc.step_left(1),
                'step_right': lambda: dc.step_right(1),
                'switch1': lambda: dc.switch(0),
                'switch2': lambda: dc.switch(1),
               }

class ManualMovements(tk.Frame):
    'bottoniera per controllo manuale movimenti'
    def __init__(self, master, mainwdg, icon_size, bold):
        super().__init__(master, bg=DEFAULT_BG)
        self.mainwdg = mainwdg
        self.left2_b = tk.Button(self, image=get_icon('left2', icon_size, 'yellow'),
                padx=0, pady=0, border=0, command=lambda: dc.step_left(1))
        self.left2_b.grid(row=1, column=1)
        self.left_b = tk.Button(self, image=get_icon('left', icon_size, 'yellow'),
                              padx=0, pady=0, border=0, command= dc.start_left)
        self.left_b.grid(row=1, column=2)
        self.stop_b = tk.Button(self, text='STOP', font=bold, bg=YELLOW,
                                fg=BLACK, command=dc.stop)
        self.stop_b.grid(row=1, column=3, sticky='ew')
        self.right_b = tk.Button(self, image=get_icon('right', icon_size, 'yellow'),
                              padx=0, pady=0, border=0, command=dc.start_right)
        self.right_b.grid(row=1, column=4)
        self.right2_b = tk.Button(self, image=get_icon('right2', icon_size, 'yellow'),
                              padx=0, pady=0, border=0, command=lambda: dc.step_right(1))
        self.right2_b.grid(row=1, column=5)
        self.set_manual(True)

    def set_manual(self, enable):
        'abilita/disabilita modo manuale'
        if enable:
            self.right2_b.config(state=tk.NORMAL)
            self.right_b.config(state=tk.NORMAL)
            self.stop_b.config(state=tk.NORMAL)
            self.left2_b.config(state=tk.NORMAL)
            self.left_b.config(state=tk.NORMAL)
        else:
            self.right2_b.config(state=tk.DISABLED)
            self.right_b.config(state=tk.DISABLED)
            self.stop_b.config(state=tk.DISABLED)
            self.left2_b.config(state=tk.DISABLED)
            self.left_b.config(state=tk.DISABLED)

class Buttonbox(tk.Frame):
    'bottoniera per comandi'
    def __init__(self, master, font, cback):
        super().__init__(master, border=3, relief=tk.RIDGE, bg=DEFAULT_BG)
        self.home_b = tk.Button(self, text='Home', font=font, bg=DEFAULT_BG,
                                command=lambda: cback('home'))
        self.home_b.grid(row=2, column=1, sticky='ew')
        self.park_b = tk.Button(self, text='Park', font=font, bg=DEFAULT_BG,
                                command=lambda: cback('park'))
        self.park_b.grid(row=2, column=2, sticky='ew')
        tk.Button(self, text='Apri vano', font=font, bg=DEFAULT_BG,
               command=lambda: cback('apri_vano')).grid(row=3, column=1, sticky='ew')
        tk.Button(self, text='Chiudi vano', font=font, bg=DEFAULT_BG,
                  command=lambda: cback('chiudi_vano')).grid(row=3, column=2, sticky='ew')
        tk.Button(self, text='Interr. 1', font=font, bg=DEFAULT_BG,
               command=lambda: cback('switch1')).grid(row=4, column=1, sticky='ew')
        tk.Button(self, text='Interr. 2', font=font, bg=DEFAULT_BG,
                  command=lambda: cback('switch2')).grid(row=4, column=2, sticky='ew')
        self.columnconfigure(1, uniform='two')
        self.columnconfigure(2, uniform='two')

    def set_manual(self, enable):
        'abilita/disabilita comandi per modo manuale'
        if enable:
            self.home_b.config(state=tk.NORMAL)
            self.park_b.config(state=tk.NORMAL)
        else:
            self.home_b.config(state=tk.DISABLED)
            self.park_b.config(state=tk.DISABLED)

class DomeControl(tk.Frame):                       # pylint: disable=R0901,R0902
    'Widget con bottoni per controllo cupola in modo manuale'
    def __init__(self, parent, size='s'):                     # pylint: disable=R0915
        super().__init__(parent)
        if size.lower() == 'l':
            icon_size = 48
            plain = 'helvetica 16'
            bold = 'helvetica 16 bold'
        elif size.lower() == 'm':
            icon_size = 32
            plain = 'helvetica 14'
            bold = 'helvetica 14 bold'
        else:
            icon_size = 24
            plain = 'helvetica 12'
            bold = 'helvetica 12 bold'
        frame0 = tk.Frame(self, bg=DEFAULT_BG, border=2, padx=5, pady=5, relief=tk.RIDGE)
        frame1 = tk.Frame(frame0, bg=DEFAULT_BG, pady=5)   # contenitore azimuth e >>
        tk.Label(frame1, text='Azh: ', font=bold, fg=BLACK, bg=DEFAULT_BG).pack(side=tk.LEFT)
        self.domeaz_n = Number(frame1, fmt='%.1f', width=8, font=plain)
        self.domeaz_n.pack(side=tk.LEFT)
        tk.Label(frame1, text='   ', bg=DEFAULT_BG).pack(side=tk.LEFT, expand=1, fill=tk.BOTH)
        self.vai_b = tk.Button(frame1, text='>>', font=bold, bg=DEFAULT_BG,
                               padx=10, pady=2, command=self.vai_a)
        self.vai_b.pack(side=tk.LEFT)
        self.slew_e = Controller(frame1, value=0, lower=0, upper=359, circular=True, bg=DEFAULT_BG)
        self.slew_e.pack(side=tk.LEFT)
        frame1.pack(expand=1, fill=tk.X)
        self.mbox = ManualMovements(frame0, self, icon_size, bold)
        self.mbox.pack()
                                                       # Bottoni home. park e vano
        self.obox = Buttonbox(frame0, bold, self.action)
        self.obox.pack()
                                                        # area per modo 'slave'
        frame3 = tk.Frame(frame0, bg=DEFAULT_BG, pady=5)
        tk.Label(frame3, text=' Telescopio  ', font=bold,
                 bg=DEFAULT_BG).pack(side=tk.LEFT)
        self.tel_l = Led(frame3, size=icon_size)
        self.tel_l.pack(side=tk.LEFT)
        tk.Label(frame3, text=' ', bg=DEFAULT_BG).pack(side=tk.LEFT, expand=1, fill=tk.BOTH)
        tk.Label(frame3, text='insegui ', font=plain, bg=DEFAULT_BG).pack(side=tk.LEFT)
        self.is_slave = tk.BooleanVar()
        self.slave_ck = tk.Checkbutton(frame3, variable=self.is_slave,
                                       bg=DEFAULT_BG, command=self.set_slave_cbk)
        self.slave_ck.pack(side=tk.LEFT)
        tk.Label(frame3, text=' ', bg=DEFAULT_BG).pack(side=tk.LEFT)
        if dc.get_params()['canslave'] or GLOB.noslave : # abilita sezione telescopio
            frame3.pack()                                # se modo slave è supportato
        frame0.pack()
                                                        # Linea messaggi
        self.info_l = tk.Label(self, text='', font=plain, bg=WHITE)
        self.info_l.pack(side=tk.LEFT, expand=1, fill=tk.X)
        self.goon = True
        self.info_ex = 0
        self.set_manual(True)
        self.update_me()

    def action(self, cmd):
        'attiva comando generico'
        func = ACTION_TABLE.get(cmd)
        if func is None:
            ret = f'ERRORE INTERNO - comando non  riconosciuto: {cmd}'
        else:
            ret = func()
        self.show_err(ret)

    def set_slave_cbk(self):
        'callback per bottone slave'
        if self.is_slave.get():
            ret = dc.set_slave()
            if ret:
                self.show_err(ret)
            else:
                self.set_manual(False)
        else:
            ret = dc.stop()
            if ret:
                self.show_err(ret)
            else:
                self.set_manual(True)

    def set_manual(self, enable):
        'abilita/disabilita bottoni modo manuale'
        if enable:
            self.mbox.set_manual(True)
            self.obox.set_manual(True)
            self.is_slave.set(False)
            self.vai_b.config(state=tk.NORMAL)
            self.slew_e.config(state=tk.NORMAL)
            self.slew_e.set(0)
        else:
            self.mbox.set_manual(False)
            self.obox.set_manual(False)
            self.is_slave.set(True)
            self.vai_b.config(state=tk.DISABLED)
            self.slew_e.config(state=tk.DISABLED)

    def vai_a(self):
        'comando vai a azimuth'
        azh = self.slew_e.get()
        ret = dc.slew_to_azimuth(azh)
        self.show_err(ret)

    def show_err(self, msg):
        'Visualizza errore'
        if msg:
            self.info_l.config(text=msg, fg=RED)
            self.info_ex = time.time()+MSG_PERSISTENCE
            dc.add_log('GUI Error', msg)

    def update_me(self):
        'update widget'
        if self.goon:
            if self.info_ex < time.time():
                self.info_l.config(text='')
            dome_stat = dc.get_status()
            self.domeaz_n.set(dome_stat.domeaz)
            if self.is_slave.get():
                if dome_stat.targetaz < 0:
                    self.slew_e.set(NAN)
                else:
                    self.slew_e.set(dome_stat.targetaz)
            self.after(GUI_REFRESH, self.update_me)

def connect_to_dome(debug, sim_k8055, sim_tel):
    'apre la connessione con cupola'
    ret = dc.start_server(debug=debug, sim_k8055=sim_k8055, sim_tel=sim_tel)
    return ret

def main():                      # pylint: disable=R0915
    'Codice di test'
    if '-h' in sys.argv:
        print(__doc__)
        sys.exit()
    if dc is None:
        raise RuntimeError('Cannot connect to k8055 board')
    debug = '-d' in sys.argv
    sim_k8055 = '-k' in sys.argv
    sim_tel = '-s' in sys.argv
    GLOB.noslave = '-n' in sys.argv
    connect_to_dome(debug=debug, sim_k8055=sim_k8055, sim_tel=sim_tel)
    GLOB.root = tk.Tk()

    wdg = DomeControl(GLOB.root, 'm')
    GLOB.root.title('Cupola')
    wdg.pack()
    GLOB.root.mainloop()
    dc.stop_server()

if __name__ == '__main__':
    main()
