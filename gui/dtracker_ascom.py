#!/usr/bin/python3
'''
OPC - GUI minimale per controllo cupola via ASCOM - [Vers. {}]

Uso:
        python dtracker_ascom.py [-dhks]

Dove:
       -d  Attiva modo debug
       -h  Mostra questa pagina ed esce
       -s  Usa simulatore di telescopio
'''
import sys
import os
import math
import tkinter as tk

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# pylint: disable=C0412,C0413

from opc import utils
from opc import telsamp as ts

if sys.platform == 'win32':
    import win32com.client as wcl
    SIMULATED = False
else:
    from opc import dome_ascom_fake as wcl
    print("Using ASCOM_FAKE !!!")
    SIMULATED = True

import widgets as wg

__author__ = 'Luca Fini'
__version__ = '1.0'
__date__ = 'Luglio 2025'

DOME_ASCOM_NAME = 'OCS.dome'

UPDATE_RATE = 1000        # periodo aggiornamento (ms)
POSITION_MAX_ERR = 1.0

ENTRY_BG = '#808080'
BACKGROUND = '#303030'
FOREGROUND = '#ffffff'
FRG_INFO = '#88ff88'
RED = '#ff8888'
GREEN = '#33ff33'
GRAY = '#808080'
YELLOW = '#ffff80'
BLACK = '#000000'
BKG_SLAVE = '#501010'

class DEBUG:           #pylint: disable=C0115,R0903
    d_on = False

class MyFrame(tk.Frame):                      #pylint: disable=R0901
    'versione colorabile di Frame'
    def __init__(self, parent, **kws):
        kws['bg'] = BACKGROUND
        super().__init__(parent, **kws)

class MyLabel(tk.Label):                      #pylint: disable=R0901
    'versione colorabile di Label'
    def __init__(self, parent, **kws):
        kws['bg'] = BACKGROUND
        kws['fg'] = FOREGROUND
        super().__init__(parent, **kws)

class MyButton(tk.Button):                      #pylint: disable=R0901
    'versione colorabile di Button'
    def __init__(self, parent, **kws):
        if 'bg' not in kws:
            kws['bg'] = BACKGROUND
        if 'fg' not in kws:
            kws['fg'] = FOREGROUND
        if 'font' not in kws:
            kws['font'] = wg.H4_FONT
        if 'pady' not in kws:
            kws['pady'] = 2
        if 'padx' not in kws:
            kws['padx'] = 4
        if 'width' not in kws:
            kws['width'] = 8
        super().__init__(parent, **kws)

class MyCoord(wg.Coord):                      #pylint: disable=R0901
    'versione colorabile di Coord'
    def __init__(self, parent, **kws):
        kws['bg'] = BACKGROUND
        kws['fg'] = FOREGROUND
        super().__init__(parent, **kws)

class MyNumber(wg.Number):                      #pylint: disable=R0901
    'versione colorabile di Number'
    def __init__(self, parent, **kws):
        kws['bg'] = BACKGROUND
        kws['fg'] = FOREGROUND
        super().__init__(parent, **kws)

class MyEntry(tk.Entry):                      #pylint: disable=R0901
    'versione colorabile di Entry'
    def __init__(self, parent, **kws):
        kws['bg'] = ENTRY_BG
        kws['fg'] = FOREGROUND
        if 'font' not in kws:
            kws['font'] = wg.H3_FONT
        super().__init__(parent, **kws)

class MySpacer(wg.HSpacer):                      #pylint: disable=R0901
    'versione colorabile di HSpacer'
    def __init__(self, parent, nspaces=0, **kws):
        kws['bg'] = BACKGROUND
        kws['fg'] = FOREGROUND
        super().__init__(parent, nspaces, **kws)

class MyCheckbutton(tk.Checkbutton):
    'versione colorabile di checkbutton'
    def __init__(self, parent, **kws):
        kws['bg'] = BACKGROUND
        kws['selectcolor'] = BLACK
        kws['fg'] = FOREGROUND
        super().__init__(parent, **kws)

class DTrackerASCOM(MyFrame):                #pylint: disable=R0901,R0902
    'widget minimale'
    def __init__(self, parent, dome, tls):
        super().__init__(parent)
        self.tls = tls
        self.dome = dome

        self.dome_led = wg.Led(self, size=24)
        self.dome_led.grid(row=3, column=0)
        MyLabel(self, text=' Cupola  ',
                font=wg.H2_FONT).grid(row=3, column=1, sticky='w', pady=10)
                                                     # area centrale cupola
        dome_fr = MyFrame(self, padx=5, pady=3)
        MyLabel(dome_fr, text='Azimuth(°) ', font=wg.H3_FONT).pack(side=tk.LEFT)
        MyLabel(dome_fr, text='   Corr. ').pack(side=tk.LEFT)
        self.dome_az_f = MyNumber(dome_fr, fmt='%.1f', width=6, font=wg.H3_FONT)
        self.dome_az_f.pack(side=tk.LEFT)
#       MyLabel(dome_fr, text='   Target: ').pack(side=tk.LEFT)
#       self.trgt_az_f = MyNumber(dome_fr, width=6, fmt='%.1f', font=wg.H3_FONT)
#       self.trgt_az_f.pack(side=tk.LEFT)
        MyLabel(dome_fr, text=' ').pack(side=tk.LEFT, expand=1, fill=tk.X)
        dome_fr.grid(row=3, column=2, pady=4, padx=2, sticky='w')

        led_bg = tk.Label(self, text=' ', bg=BACKGROUND)
        led_bg.grid(row=7, column=0, sticky=tk.W+tk.E+tk.N+tk.S)
        self.tel_led = wg.Led(self, size=24)
        self.tel_led.grid(row=7, column=0)
        tel_lab = MyLabel(self, text=' Telescopio  ', font=wg.H3_FONT)
        tel_lab.grid(row=7, column=1, ipady=10)
                                                    # area centrale telescopio
        tel_fr = MyFrame(self)
        lab = MyLabel(tel_fr, text=' HA(h): ')
        lab.pack(side=tk.LEFT)
        self.tel_ha = MyCoord(tel_fr, precision='m', mode=':', width=6, font=wg.H4_FONT)
        self.tel_ha.pack(side=tk.LEFT)
        lab = MyLabel(tel_fr, text='   DE(°): ')
        lab.pack(side=tk.LEFT)
        self.tel_de = MyCoord(tel_fr, precision='m', mode=':', width=6, font=wg.H4_FONT)
        self.tel_de.pack(side=tk.LEFT)
        lab = MyLabel(tel_fr, text='   Lato: ')
        lab.pack(side=tk.LEFT)
        self.tside = MyLabel(tel_fr, text='', width=3, bg='black', fg='lightgreen', font=wg.H4_FONT)
        self.tside.pack(side=tk.LEFT)
        spa = MySpacer(tel_fr, 5)
        spa.pack(side=tk.LEFT)
        self.slave = tk.IntVar()
        MyCheckbutton(tel_fr, text='Slave', variable=self.slave,
                      command=self.set_slave).pack(side=tk.LEFT)
        spa = MySpacer(tel_fr)
        spa.pack(side=tk.LEFT)
        tel_fr.grid(row=7, column=2, sticky='nswe')
        self.update()

    def set_slave(self):
        'attiva/disattiva modo slave'
        val = self.slave.get()
        if DEBUG.d_on:
            print(f'set_slave. stato={val}')

    def update(self):
        'aggiornamento periodico'
        azm = self.dome.Azimuth
        if azm is not None:
            self.dome_led.set(GREEN)
        else:
            self.dome_led.set(None)
        ded, rah, psi, hah, azh = self.tls.tel_status()
        if DEBUG.d_on:
            print(f"tel_status: {ded=}, {rah=}, {psi=}, {hah=}, {azh=}")
        if math.isnan(hah):
            self.tel_led.set(None)
        else:
            self.tel_led.set(GREEN)
        self.tel_ha.set(hah)
        self.tel_de.set(ded)
        self.tside.config(text=psi)
        if self.dome.Slewing:
            azm_color = YELLOW
        else:
            azm_color = GREEN
            if self.slave:
                if abs(azm-azh) > POSITION_MAX_ERR:
                    self.dome.SlewToAzimuth(azh)
                    azm_color = YELLOW
        self.dome_az_f.set(azm, fg=azm_color)
        self.after(UPDATE_RATE, self.update)


def main():                 #pylint: disable=R0915,R0912,R0914
    'funzione main'
    if '-h' in sys.argv:
        root = tk.Tk()
        wdg = wg.MessageText(root, __doc__.format(__version__))
        wdg.pack()
        root.mainloop()
        sys.exit()

    DEBUG.d_on = '-d' in sys.argv
    config = utils.get_config()
    sim_tel = '-s' in sys.argv
    if sim_tel:
        config = utils.get_config(simul=True)
    root = tk.Tk()
    if not config:
        error = '\n\n Errore lettura del file di configurazione \n\n'
        wdg = wg.MessageText(root, error, bg=wg.ERROR_CLR)
        wdg.pack()
        root.mainloop()
        sys.exit()
    try:
        dome = wcl.Dispatch(DOME_ASCOM_NAME)
    except Exception as exc:                #pylint: disable=W0718
        error = '\n\n Errore ASCOM:\n\n'+'  '+exc.strerror+' \n'
        wdg = wg.MessageText(root, error, bg=wg.ERROR_CLR)
        wdg.pack()
        root.mainloop()
        sys.exit()

    tls = ts.tel_start(sim_tel)

    root.title(f'OPC - Controllo cupola via ASCOM - V. {__version__}')
    wdg = DTrackerASCOM(root, dome, tls)
    wdg.pack()
    root.iconphoto(False, wg.get_icon('dome', 24))
    root.mainloop()
    tls.tel_stop()
    if SIMULATED:
        print("\nInterruzione simulatore cupola")
        sys.stdout.flush()
        dome.Dispose()
        dome.join()
        print("OK")

if __name__ == '__main__':
    main()
