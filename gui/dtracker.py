#!/usr/bin/python3
'''
OPC - GUI per controllo cupola - [%s]

Uso per test:
        python dtracker.py [-d] [-h] [-k] [-s] [-v]

Dove:
       -d  Attiva debug locale GUI
       -D  Attiva debug controller cupola
       -h  Mostra questa pagina ed esce
       -k  Usa simulatore di scheeda k8055
       -p  Alpaca port
       -s  Usa simulatore di telescopio
       -t  Disabilita accesso telescopio (per test)
       -v  Scrive numero di versione
'''

import sys
import getopt
import os.path
import time
import tkinter as tk
import hid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# pylint: disable=C0413
from opc import utils
import opc.widgets as wg

from opc import dome_ctrl as dc

from opc import tel_sampler as ts

__author__ = 'Luca Fini'
__version__ = '2.1'
__date__ = 'Febbraio 2023'

ENTRY_BG = '#808080'
BACKGROUND = '#303030'
FOREGROUND = '#ffffff'
FRG_INFO = '#88ff88'
REDCOLOR = '#ff8888'
GREEN = '#33ff33'
GRAY = '#808080'
YELLOW = '#ffff80'
BLACK = '#000000'
BKG_SLAVE = '#a02020'

SW1_TEXT = 'Switch 1'
SW2_TEXT = 'Switch 2'
SW3_TEXT = 'Switch 3'
SW4_TEXT = 'Switch 4'

NAN = float('nan')

UPDATE_TIME = 300   # Intervallo (ms) refresh per widget
ERROR_TIME = 5     # persistenza messaggi errore (sec)

HOMEDIR = os.path.expanduser('~')

MY_PATH = os.path.dirname(os.path.abspath(__file__))

                   # Costanti per controllo relé USB del fuocheggiatore
VENDOR = 0x519
PRODUCT = 0x2018

ON_CMD_1 = (0, 0xf1)
OFF_CMD_1 = (0, 0x01)
ON_CMD_2 = (0, 0xf2)
OFF_CMD_2 = (0, 0x02)

NO_USB = 'USB relé non risponde'

B_FONT = wg.H4_FONT

class _GB:           # pylint: disable=R0903
    'globals senza usare global'
    config = {}
    debug = False
    logname = ''

DTRACKER_INFO = '''
  DTracker - GUI per controllo cupola OPC

  Vers. %s - %s, %s
  ----------------------------------
  Logfile: %s
  ----------------------------------
  '''

def _debug(*par):
    'Scrivi linea dui debug'
    if _GB.debug:
        print('DBG>', *par)

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

class FocusButtons(MyFrame):                    # pylint: disable=R0901
    'Bottone per controllo fuoco'
    def __init__(self, parent, err_cb, **kw):
        super().__init__(parent)
        self.usbrele = hid.device()             # pylint: disable=I1101
        bt1 = MyButton(self, text='Foc-', **kw)
        bt1.pack(side=tk.LEFT)
        bt1.bind('<ButtonRelease-1>', self.b1release)
        bt1.bind('<Button-1>', self.b1press)
        bt2 = MyButton(self, text='Foc+', **kw)
        bt2.pack(side=tk.LEFT)
        bt2.bind('<ButtonRelease-1>', self.b2release)
        bt2.bind('<Button-1>', self.b2press)
        self.onrele0 = False
        self.onrele1 = False
        self.imgood = False
        self.err_cb = err_cb
        self.usb_on()

    def _write(self, what):
        'invia comando a USB'
        try:
            ret = self.usbrele.write(what)
        except:                             # pylint: disable=W0702
            ret = -1
        return ret

    def b1press(self, *_unused):
        'callback per bottone 1 premuto'
        if not self.imgood:
            self.err_cb(NO_USB)
            return
        if not self.onrele0:
            ret = self._write(ON_CMD_2)
            if ret > 0:
                self.onrele1 = True
            else:
                self.usb_on()

    def b1release(self, *_unused):
        'callback per bottone 1 rilasciato'
        if not self.imgood:
            return
        ret = self._write(OFF_CMD_2)
        if ret > 0:
            self.onrele1 = False
        else:
            self.usb_on()

    def b2press(self, *_unused):
        'callback per bottone 2 premuto'
        if not self.imgood:
            self.err_cb(NO_USB)
            return
        if not self.onrele1:
            ret = self._write(ON_CMD_1)
            if ret > 0:
                self.onrele0 = True
            else:
                self.usb_on()

    def b2release(self, *_unused):
        'callback per bottone 2 rilasciato'
        if not self.imgood:
            return
        ret = self._write(OFF_CMD_1)
        if ret > 0:
            self.onrele0 = False
        else:
            self.usb_on()

    def usb_on(self):
        'Open communication with USB relé'
        self.usbrele.close()
        try:
            self.usbrele.open(VENDOR, PRODUCT)
        except OSError:
            self.imgood = False
            self.after(2000, self.usb_on)
            return
        self._write(OFF_CMD_1)
        self._write(OFF_CMD_2)
        self.onrele0 = False
        self.onrele1 = False
        self.imgood = True

class SetupPanel(wg.MyToplevel):
    'Pannello per impostazioni'
    def __init__(self, parent, dct, sav_cback, err_cback):
        super().__init__(parent, 'Impostazioni', position='c', bg=BACKGROUND, padx=5, pady=5)
        self.dct = dct
        self.azh = self.dct.get_status().domeaz
        MyLabel(self, text='Posizione corrente: ',
                font=wg.H4_FONT).grid(row=1, column=1, sticky='e')
        MyNumber(self, fmt='%.1f', width=8, value=self.azh).grid(row=1, column=2)
        MyLabel(self, text='Imposta posizione assoluta: ').grid(row=2, column=1, sticky='e')
        sync_b = MyButton(self, text='Sync', command=self.sync)
        sync_b.grid(row=2, column=2)
        self.sync_e = MyEntry(self, width=5)
        self.sync_e.grid(row=2, column=3)
        MyLabel(self, text='Imposta posizione park: ').grid(row=3, column=1, sticky='e')
        sync_b = MyButton(self, text='Set park', command=self.set_park)
        sync_b.grid(row=3, column=2)
        MyLabel(self, text='Salva posizione corrente: ').grid(row=4, column=1, sticky='e')
        sync_b = MyButton(self, text='Salva', command=self.save_pos)
        sync_b.grid(row=4, column=2)
        self.err_cback = err_cback
        self.sav_cback = sav_cback

    def sync(self):
        'Sincronizza posizione cupola'
        sval = self.sync_e.get().strip()
        ret = self.dct.sync_to_azimuth(sval)
        self.err_cback(ret)

    def save_pos(self):
        'salva posizione corrente'
        _GB.config['save_position'] = self.azh
        self.sav_cback()

    def set_park(self):
        'imposta posizione corrente come park'

class DTracker(MyFrame):                              # pylint: disable=R0901,R0902,R0904
    'Widget per asservimento cupola'
    def __init__(self, parent, dct, tls):          # pylint: disable=R0915
        super().__init__(parent)
        self.tel_sampler = tls
        self.dct = dct
                                                      # Bottoni con icone
        gear = tk.Button(self, image=wg.get_icon('gear', 24, 'brown'),
                        bg=BACKGROUND, command=self.setup)
        gear.grid(row=1, column=0,sticky='nw')
        wg.ToolTip(gear, text='Impostazioni')
        bfr = tk.Frame(self)
        tk.Label(bfr, text='  ', fg=BACKGROUND, bg=BACKGROUND).pack(side=tk.LEFT, expand=1, fill=tk.BOTH)
        info = tk.Button(bfr, image=wg.get_icon('info', 24, 'cyan'),
                        bg=BACKGROUND, command=self.info)
        info.pack(side=tk.LEFT)
        wg.ToolTip(info, text='Informazioni')
#       tk.Label(bfr, text='  ', fg=BACKGROUND, bg=BACKGROUND).pack(side=tk.LEFT, expand=1, fill=tk.BOTH)
#       quest = tk.Button(bfr, image=wg.get_icon('question', 24, 'cyan'),
#                       bg=BACKGROUND, command=self.setup)
#       quest.pack(side=tk.LEFT)
#       wg.ToolTip(quest, text='Aiuto')
        bfr.grid(row=1, column=1,sticky='nw')

        MyFrame(self, border=4,                      # linea di separazione
                relief=tk.SUNKEN).grid(row=2, column=0,
                                       columnspan=5, sticky='we', ipady=1)
                                                      # area sinistra cupola
        self.dome_led = wg.Led(self, size=24)
        self.dome_led.grid(row=3, column=0)
        MyLabel(self, text=' Cupola  ', font=wg.H2_FONT).grid(row=3, column=1, sticky='w', pady=10)
                                                     # area centrale cupola
        dome_fr = MyFrame(self, padx=5, pady=3)
        MyLabel(dome_fr, text='Azimuth(°) ', font=wg.H3_FONT).pack(side=tk.LEFT)
        MyLabel(dome_fr, text='   Corr. ').pack(side=tk.LEFT)
        self.dome_az_f = MyNumber(dome_fr, fmt='%.1f', width=6, font=wg.H3_FONT)
        self.dome_az_f.pack(side=tk.LEFT)
        MyLabel(dome_fr, text='   Target: ').pack(side=tk.LEFT)
        self.trgt_az_f = MyNumber(dome_fr, width=6, fmt='%.1f', font=wg.H3_FONT)
        self.trgt_az_f.pack(side=tk.LEFT)
        MyLabel(dome_fr, text=' ').pack(side=tk.LEFT, expand=1, fill=tk.X)
        dome_fr.grid(row=3, column=2, pady=4, padx=2, sticky='w')

        mid_fr = MyFrame(self)
        self.slew_b = MyButton(mid_fr, text='Vai a >', command=self.slewto)
        self.slew_b.pack(side=tk.LEFT)
#       wg.ToolTip(self.slew_b, text='Vai ad azimuth impostato')
        self.slew_e = MyEntry(mid_fr, font=wg.H4_FONT, width=5)
        wg.ToolTip(self.slew_e, text='Imposta azimuth manualmente')
        self.slew_e.pack(side=tk.LEFT)
        MyLabel(mid_fr, text=' ').pack(side=tk.LEFT, expand=1, fill=tk.X)
        self.lstep_b = MyButton(mid_fr, text='<', width=6, command=lambda: self.step('l'))
        self.lstep_b.pack(side=tk.LEFT)
        self.lmove_b = MyButton(mid_fr, text='<<', width=6, command=lambda: self.move('l'))
        self.lmove_b.pack(side=tk.LEFT)
        self.stop_b = MyButton(mid_fr, text='Stop', width=6, command=self.stop)
        self.stop_b.pack(side=tk.LEFT)
        self.rmove_b = MyButton(mid_fr, text='>>', width=6, command=lambda: self.move('r'))
        self.rmove_b.pack(side=tk.LEFT)
        self.rstep_b = MyButton(mid_fr, text='>', width=6, command=lambda: self.step('r'))
        self.rstep_b.pack(side=tk.LEFT)
        mid_fr.grid(row=4, column=2, sticky='we', ipady=4)

        bot_fr = MyFrame(self)
        self.pos_b = MyButton(bot_fr, text='Vai a    ', width=12, command=self.goto_saved)
        self.pos_b.pack(side=tk.LEFT)
        self.set_save()
        wg.ToolTip(self.pos_b, text='Muovi a posizione salvata')
        MySpacer(bot_fr, 4)
        self.park_b = MyButton(bot_fr, text='Park', command=self.park)
        self.park_b.pack(side=tk.LEFT)
        wg.ToolTip(self.park_b, text='Muovi in posizione Park')
        bot_fr.grid(row=5, column=2, sticky='e', ipady=4)

        MyFrame(self, border=4,                      # linea di separazione
                relief=tk.SUNKEN).grid(row=6, column=0,
                                       columnspan=5, sticky='we', ipady=1)
        self.tel_led = wg.Led(self, size=24)
        self.tel_led.grid(row=7, column=0)
        tel_lab = MyLabel(self, text=' Telescopio  ', font=wg.H3_FONT)
        tel_lab.grid(row=7, column=1, ipady=10)
        self.tel_ws = [tel_lab]
                                                    # area centrale telescopio
        tel_fr = MyFrame(self)
        lab = MyLabel(tel_fr, text=' HA(h): ')
        lab.pack(side=tk.LEFT)
        self.tel_ws.append(lab)
        self.tel_ha = MyCoord(tel_fr, precision='m', mode=':', width=6, font=wg.H4_FONT)
        self.tel_ha.pack(side=tk.LEFT)
        lab = MyLabel(tel_fr, text='   DE(°): ')
        lab.pack(side=tk.LEFT)
        self.tel_ws.append(lab)
        self.tel_de = MyCoord(tel_fr, precision='m', mode=':', width=6, font=wg.H4_FONT)
        self.tel_de.pack(side=tk.LEFT)
        lab = MyLabel(tel_fr, text='   Lato: ')
        lab.pack(side=tk.LEFT)
        self.tel_ws.append(lab)
        self.tside = MyLabel(tel_fr, text='', width=3, bg='black', fg='lightgreen', font=wg.H4_FONT)
        self.tside.pack(side=tk.LEFT)
        spa = MySpacer(tel_fr, 3)
        self.tel_ws.append(spa)
        self.slave_b = MyButton(tel_fr, text='Slave', command=self.set_slave)
        self.slave_b.pack(side=tk.LEFT)
        spa = MySpacer(tel_fr)
        self.tel_ws.append(spa)
        tel_fr.grid(row=7, column=2, sticky='nswe')
        self.tel_ws.append(tel_fr)
        self.foc_w = FocusButtons(self, self.showerror)
        wg.ToolTip(self.foc_w, text='Fuoco secondario')
        self.foc_w.grid(row=7, column=4)
        if self.tel_sampler:
            wg.ToolTip(self.slave_b, text='Attiva inseguimento telescopio')
        else:
            self.tel_ha.config(state=tk.DISABLED)
            self.tel_de.config(state=tk.DISABLED)
            self.tel_led.set(color=BLACK)
            self.slave_b.config(state=tk.DISABLED)
            wg.ToolTip(tel_fr, text='Accesso al telescopio non attivo')

        MyFrame(self, border=2,                               # separatore verticale
                relief=tk.SUNKEN).grid(row=3,
                                       column=3, rowspan=3, sticky='ns', ipadx=1, padx=3)

                                                        # colonna con azionamenti
        az1_fr = MyFrame(self)
        self.apre_b = MyButton(az1_fr, text='Apre', command=lambda: self.portello('o'))
        self.apre_b.pack(side=tk.LEFT)
        self.chiude_b = MyButton(az1_fr, text='Chiude', command=lambda: self.portello('c'))
        self.chiude_b.pack(side=tk.LEFT)
        wg.ToolTip(az1_fr, text='Aziona portello')
        az1_fr.grid(row=3, column=4)
        az2_fr = MyFrame(self)
        self.sw1_b = MyButton(az2_fr, text=SW1_TEXT, command=lambda: self.sw_tog(0))
        self.sw1_b.pack(side=tk.LEFT)
        self.sw2_b = MyButton(az2_fr, text=SW2_TEXT, command=lambda: self.sw_tog(1))
        self.sw2_b.pack(side=tk.LEFT)
        wg.ToolTip(az2_fr, text='Interruttori ausiliari')
        az2_fr.grid(row=4, column=4)
        az3_fr = MyFrame(self)
        self.sw3_b = MyButton(az3_fr, text=SW3_TEXT, command=lambda: self.sw_tog(2))
        self.sw3_b.pack(side=tk.LEFT)
        self.sw3_b = MyButton(az3_fr, text=SW4_TEXT, command=lambda: self.sw_tog(3))
        self.sw3_b.pack(side=tk.LEFT)
        wg.ToolTip(az3_fr, text='Interruttori ausiliari')
        az3_fr.grid(row=5, column=4)
        self.sws = [False, False, False, False]
        self.stline = MyLabel(self, text='', border=4, font=wg.H4_FONT,
                              fg=REDCOLOR, pady=4, relief=tk.RIDGE)
        self.stline.grid(row=8, column=0, columnspan=5, sticky='we')
        self.moreinfo = tk.Text(self, bg=BACKGROUND, fg=FRG_INFO)
        self.moreinfo.bind('<Button-1>', lambda *x: self.moreinfo.delete('1.0', tk.END))
        self.moreinfo.grid(row=10, column=0, columnspan=5, sticky='nswe')
        self.manual(True)
        self.errtime = 0
        self.help('init.hlp')
        self.update()

    def clearinfo(self, *_unused):
        'Azzera pagina di testo'
        self.moreinfo.delete("1.0", tk.END)

    def update(self):                       #pylint: disable=R0912
        'aggiorna stato panel'
        if self.errtime and self.errtime < time.time():
            self.showerror()
        if self.tel_sampler:
            tel_stat = self.tel_sampler.tel_status()
            self.tel_de.set(tel_stat[0])
            self.tel_ha.set(tel_stat[3])
            self.tside.config(text=tel_stat[2])
            if tel_stat[2]:
                self.tel_led.set(GREEN)
            else:
                self.tel_led.set(GRAY)
        stat = self.dct.get_status()
        if stat.connected:
            self.dome_led.set(GREEN)
            if stat.direct == 0:
                self.dome_az_f.set(stat.domeaz, fg=FOREGROUND)
            else:
                self.dome_az_f.set(stat.domeaz, fg=YELLOW)
            if stat.targetaz >= 0:
                self.trgt_az_f.set(stat.targetaz)
            else:
                self.trgt_az_f.clear()
            if stat.isslave:
                if self.slave_b.cget('state') == tk.NORMAL:
                    self.manual(False)
                    self.show_slave(True)
            else:
                if self.tel_sampler and self.slave_b.cget('state') == tk.DISABLED:
                    self.manual(True)
                    self.show_slave(False)
        else:
            self.dome_led.set(GRAY)
        self.after(UPDATE_TIME, self.update)

    def showerror(self, msg=''):
        'scrive avviso errore'
        if msg:
            self.stline.config(text='ERR: '+msg, fg=REDCOLOR)
            self.errtime = time.time()+ERROR_TIME
        else:
            self.stline.config(text='')
            self.errtime = 0

    def slewto(self):
        'slew to azimuth'
        _debug('slewto()')
        azh = self.slew_e.get().strip()
        ret = self.dct.slew_to_azimuth(azh)
        self.showerror(ret)

    def stop(self):
        'interrompi movimento'
        _debug('stop()')
        ret = self.dct.stop()
        self.showerror(ret)

    def step(self, direct):
        'passo breve a sinistra/destra'
        _debug(f'step({direct})')
        if direct == 'l':
            ret = self.dct.step_left()
        else:
            ret = self.dct.step_right()
        self.showerror(ret)

    def move(self, direct):
        'movimento a sinistra/destra'
        _debug(f'move({direct})')
        if direct == 'l':
            ret = self.dct.start_left()
        else:
            ret = self.dct.start_right()
        self.showerror(ret)

    def portello(self, mode):
        'comando apri/chiudi portello'
        _debug(f'portello({mode})')
        if mode == 'o':
            ret = self.dct.open_shutter()
        else:
            ret = self.dct.close_shutter()
        self.showerror(ret)

    def sw_tog(self, nsw):
        'apre/chiude switch N. 0-3'
        _debug(f'sw_tog({nsw})')
        self.sws[nsw] = not self.sws[nsw]
        ret = self.dct.switch(nsw, self.sws[nsw])
        self.showerror(ret)

    def setup(self):
        'lancia popup per setup'
        if not self.im_busy():
            panel = SetupPanel(self, self.dct, self.set_cback, self.showerror)
            panel.grab_set()
            self.wait_window(panel)

    def help(self, what):
        'Scrive aiuto nella zona di testo'
        filepath = os.path.join(MY_PATH, what)
        self.moreinfo.delete(1.0, tk.END)
        try:
            with open(filepath, encoding='utf8') as fin:
                for line in fin:
                    self.moreinfo.insert(tk.END, '  '+line)
        except FileNotFoundError:
            self.showerror(f'file non trovato: {filepath}')

    def info(self):
        'Scrive informazioni nella zona di testo'
        ctrl_vers=self.dct.get_info()
        params = self.dct.get_params()
        parkaz = params['parkaz']*360/params['n360']
        text = ['']
        text.append(f'OPC Dome GUI - Vers. {__version__}. {__author__}, {__date__}')
        text.append('')
        text.append(ctrl_vers)
        text.append('')
        text.append('Parametri controller cupola:')
        text.append(f'  Nome file di log: {params["logfile"]}')
        text.append('  Asservimento telescopio: '+('OK' if params["canslave"] else 'NO'))
        text.append(f'  Errore posizione max.: {params["maxerr"]} (passi encoder)')
        text.append(f'  Passi encoder per giro: {params["n360"]}')
        text.append(f'  Tempo totale per giro: {params["t360"]:.2f} sec')
        text.append(f'  Periodo polling: {params["tpoll"]:.2f} sec')
        text.append(f'  Posizione di park: {parkaz:.1f}°')
        text.append('')
        text.append('Parametri di configurazione:')
        text.append(f'  Versione: {_GB.config["version"]}')
        text.append(f'  Nome file: {_GB.config["filename"]}')
        text.append(f'  Posizione salvata: {_GB.config["save_position"]:.1f}°')
        text.append(f'  Indirizzo IP telescopio: {_GB.config["tel_ip"]}:{_GB.config["tel_port"]}')
        text.append(f'  Directory dati: {_GB.config["local_store"]}')
        self.moreinfo.delete(1.0, tk.END)
        for line in text:
            self.moreinfo.insert(tk.END, '  '+line+'\n')

    def set_cback(self):
        'Scrive valore posizione salvata'
        self.set_save()
        msg = utils.store_config(_GB.config)
        self.showerror(msg)

    def set_save(self):
        'Scrive valore posizione salvata'
        _debug(f'set_save(). Now: {_GB.config.get("save_position")}')
        if 'save_position' not in _GB.config:
            _GB.config['save_position'] = 90
        self.pos_b.config(text=f'Vai a {_GB.config["save_position"]:.1f}° ')

    def goto_saved(self):
        'Vai a posizione salvata'
        if not self.im_busy():
            azh = _GB.config['save_position']
            ret = self.dct.slew_to_azimuth(azh)
            self.showerror(ret)

    def manual(self, enable):
        'Abilita/disabilita tutti comandi manuali'
        _debug(f'manual({enable})')
        if enable:
            self.lstep_b.config(state=tk.NORMAL)
            self.lmove_b.config(state=tk.NORMAL)
            self.rstep_b.config(state=tk.NORMAL)
            self.rmove_b.config(state=tk.NORMAL)
            self.slew_b.config(state=tk.NORMAL)
            self.pos_b.config(state=tk.NORMAL)
            self.park_b.config(state=tk.NORMAL)
            self.slave_b.config(state=tk.NORMAL)
        else:
            self.lstep_b.config(state=tk.DISABLED)
            self.lmove_b.config(state=tk.DISABLED)
            self.rstep_b.config(state=tk.DISABLED)
            self.rmove_b.config(state=tk.DISABLED)
            self.slew_b.config(state=tk.DISABLED)
            self.pos_b.config(state=tk.DISABLED)
            self.park_b.config(state=tk.DISABLED)
            self.slave_b.config(state=tk.DISABLED)

    def im_busy(self):
        'Verifica se cupola è "busy" (in movimento o in modo slave)'
        stat = self.dct.get_status()
        ret = True
        if stat.isslave:
            self.showerror('Comando disabilitato in modo "slave"')
        elif stat.direct != 0:
            self.showerror('Comando disabilitato in con cupola in moto')
        else:
            ret = False
        return ret

    def show_slave(self, enable=True):
        'Segnala il modo slave sulla GUI'
        bgr = BKG_SLAVE if enable else BACKGROUND
        for wdg in self.tel_ws:
            wdg.config(bg=bgr)

    def set_slave(self, *_unused):
        'attiva inseguimento telescopio'
        if not self.im_busy():
            ret = self.dct.set_slave()
            if ret:
                self.showerror(ret)
            else:
                self.manual(False)
                self.show_slave(True)

    def park(self):
        'Ritorna in posizione park'
        if not self.im_busy():
            ret = self.dct.park()
            self.showerror(ret)

def main():                 #pylint: disable=R0915,R0912,R0914
    'funzione main'
    if '-v' in sys.argv:
        print(__version__)
        sys.exit()
    try:
        opts, _unused = getopt.getopt(sys.argv[1:], 'Ddhkp:st')
    except getopt.error:
        print('Errore negli argomenti')
        sys.exit()
    _GB.debug = False
    dcdebug = False
    _GB.config = utils.get_config()
    sim_k8055 = False
    ipport = 0
    mode = ''
    sim_tel = False
    tel_sampler = True
    for opt, val in opts:
        if opt == '-d':
            _GB.debug = True
        elif opt == '-D':
            dcdebug = True
        elif opt == '-p':
            ipport = int(val)
        elif opt == '-s':
            sim_tel = True
            _GB.config = utils.get_config(simul=True)
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
    if not _GB.config:
        error = '\n\nErrore lettura del file di configurazione\n\n'
        wdg = wg.MessageText(root, error, bg=wg.ERROR_CLR)
        wdg.pack()
        root.mainloop()
        sys.exit()
    logname = utils.make_logname('dome')
    logger = utils.set_logger(logname, debug=dcdebug)
    if tel_sampler:
        tls = ts.tel_start(logger, sim_tel)
    error = None
    try:
        dct = dc.start_server(ipport=ipport, logger=logger, tel_sampler=tls, sim_k8055=sim_k8055)
    except Exception as exc:               # pylint: disable=W0703
        error = '\n\n'+str(exc)+'\n\n'
    root.title(f'OPC - Controllo cupola - V. {__version__}{mode}')
    if error:
        wdg = wg.MessageText(root, error, bg=wg.ERROR_CLR)
        wdg.pack()
        root.mainloop()
        tls.tel_stop()
        sys.exit()
    wdg = DTracker(root, dct, tls)
    wdg.pack()
    root.iconphoto(False, wg.get_icon('dome', 24))
    root.mainloop()
    tls.tel_stop()
    dct.stop_server()

if __name__ == '__main__':
    main()
