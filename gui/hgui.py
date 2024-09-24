"""
hgui.py  Autoguider from scientific images [Vers. {}]

Usage:

    python3 hgui.py [-v] [-d] [-s]

Where:
    -v     Show version and exit
    -d     Set debug mode
    -s     Start in simulation mode
"""

import sys
import os
import time
import pprint
import multiprocessing as mp
import tkinter as tk
from tkinter import filedialog

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# pylint: disable=C0413
from opc.utils import get_config
from opc.logfile import Logger
from homer.calibrate import calibrate
from homer import guide
import widgets as wg

#__version__ = "1.5"   # Corretto errore quando lo shift è negativo
#__version__ = "1.6"   # Aggiunto log del tempo di ritardo dei comandi al telescopio
#__version__ = "1.7"   # Corretto bug (errore formato log) che bloccava dopo la prima immagine
#####

__version__ = "2.0"   # Nuova versione con plate solving locale ed integrazione nella opc_gui

__author__ = "L. Naponiello, L. Fini"
__date__ = "Novembre 2023"

TEST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "__work__"))

NO_CONFIG = """
  File di configurazione mancante o incompleto

  Sarà creato un file di default che sarà attivo
  al prossimo restart
"""

YOU_SURE = """Confirm? All text will be removed from screen.
Anyway the full log is saved in file:

%s"""

NO_IMG_DIR = '''
Some image directory missing
'''

NO_CALIB_FILE = '''
Some calibration file missing
'''

CAL_STOPPED = "Calibration process interrupted"

CLICK_DD = '     .... click to select a directory ....'
CLICK_FF = '     .... click to select a file ....'

DEF_BG = '#3c3b37'
TXT_BG = '#5f5e58'
TXT_FG = '#ffffff'

ERR_FG = 'black'
ERR_BG = '#ff4444'

INFO_FG = 'black'
INFO_BG = 'cyan'

ERR_LIFE = 5

SMALLFONT = 'helvetica 9'

LOCAL_SOLVE = 'Local'
REMOTE_SOLVE = 'Remote'

SCI_CALIB_DATA_NAME = "sci_calib.json"    # Name of calibration data file
AUX_CALIB_DATA_NAME = "aux_calib.json"    # Name of calibration data file

SCI_TILES = 32  # Number of tiles for Donuts (scientific image)

class _GB:                                # pylint: disable=R0903
    "Some global variables without global"
    debug = False
    config = {}
    root = None

def _debug(txt):
    "Show debug lines"
    if _GB.debug:
        print("HGUI DBG>", txt)

def remove(fname):
    "Rimuove file"
    try:
        os.unlink(fname)
    except FileNotFoundError:
        pass

def trim(name, maxlng):
    "Tronca nome file"
    if len(name) <= maxlng:
        return name
    trimmed = name[len(name)-maxlng-3:]
    sep = trimmed.find(os.sep)
    sep = max(sep, 0)
    return '...'+trimmed[sep:]

def all_files_in(path):
    "Return list of fit files in directory"
    return [os.path.join(path, f) for f in os.listdir(path) if f.endswith('.fit')]

def browse_folder(idir, title):
    "Allow user to select folder"
    ret = filedialog.askdirectory(title=title, initialdir=idir)
    if not ret:
        ret = ""
    _debug(f'Selected folder: {ret}')
    return ret

def browse_file(idir, title, filt='fits'):
    "Allow user to select a an existing file"
    filt = filt[:1].lower()
    if filt == 'f':
        ffilt = (("FITS files", "*.fit *.fits"),
                ("All files", "*.*"))
    elif filt == 'c':
        ffilt = (("calib files", "*.json"),
                ("All files", "*.*"))
    else:
        ffilt = ()
    _debug(f'Filter: {filt}: {ffilt}')
    filepath = filedialog.askopenfilename(title=title, filetypes=ffilt, initialdir=idir)
    if not filepath:
        filepath = ''
    _debug(f'Selected file: {filepath}')
    return filepath

def cart2pol(xxx, yyy):
    "Convert cartesian coord into polar"
    if len(xxx) != 1 and len(yyy) != 1:
        xxx, yyy = np.delete(xxx, 0), np.delete(yyy, 0)
    radius = np.hypot(xxx, yyy)
    theta = np.arctan2(yyy, xxx)
    return theta, radius

class HomerGUI(tk.Frame):                                   # pylint: disable=R0901,R0902
    "GUI for Homer guiding app"
    def __init__(self, master, config, datadir, simul=False, debug=False):    # pylint: disable=R0915,R0914,R0913
        super().__init__(master, bg=DEF_BG, padx=10, pady=5)
        self.config = config
        datadir = os.path.abspath(datadir)
        if debug:
            _GB.debug = debug
            pcfg = 'Config: '+pprint.pformat(self.config)
            _debug(pcfg)
            _debug(f'datadir: {datadir}')
        self.arcsec_rate = 15
        self.donuts = None
        self.science_path = None
        self.first_science = None
        self.orientation = None
        self.tel = None
        self.simul = simul
        self._goon = False
        self.log = Logger(datadir, 'homer')
        self.log.mark(f"Homer {__version__} started ---------")
        self.dir_root = datadir
        self.sci_dir = None
        self.aux_dir = None
        self.sci_calib_dir = datadir
        self.aux_calib_dir = datadir
        self.sci_calib_file = ""
        self.aux_calib_file = ""
        self.cal_dir = os.path.join(datadir, 'calib')
        if not os.path.exists(self.cal_dir):
            os.makedirs(self.cal_dir)
        infomnu = tk.Button(self, text='  Info  ', fg=TXT_FG, bg=DEF_BG,
                            bd=None, pady=1, command=self.info)
        infomnu.pack(anchor=tk.E)
        frame1 = tk.LabelFrame(self, text="Directories", fg=TXT_FG, bg=DEF_BG)
        frame1.columnconfigure(1, weight=1)

        tk.Label(frame1, text="Science folder ", fg=TXT_FG,
                 bg=DEF_BG).grid(row=0, column=0, sticky=tk.E)
        self.sci_dir_f = tk.Label(frame1, width=50, text=CLICK_DD,
                                  fg=TXT_FG, bg=TXT_BG, anchor=tk.W)
        self.sci_dir_f.grid(row=0, column=1, sticky=tk.W+tk.E)
        self.sci_dir_f.bind('<Button-1>', self.sel_sci_dir)
        tk.Frame(frame1,  pady=6, bg=DEF_BG).grid(row=1, column=0,   # linea di separazione
                                                  columnspan=5, sticky='we')
        self.realcalibnew = tk.StringVar()
        tk.Label(frame1, text="Calib. data file ", fg=TXT_FG,
                 bg=DEF_BG).grid(row=2, column=0, sticky=tk.E)
        self.sci_calib_f = tk.Label(frame1, text=CLICK_FF,
                                    anchor=tk.W, width=50, fg=TXT_FG, bg=TXT_BG)
        self.sci_calib_f.grid(row=2, column=1, sticky=tk.E+tk.W)
        self.sci_calib_f.bind('<Button-1>', self.sel_sci_calib_file)
        tk.Frame(frame1,  pady=8, bg=DEF_BG).grid(row=3, column=0,  # linea di separazione
                                                  columnspan=5, sticky='we')
        tk.Label(frame1, text="Use aux camera? ", fg=TXT_FG,
                 bg=DEF_BG).grid(row=4, column=0, sticky=tk.E)
        tk.Label(frame1, text="   Aux camera folder ", fg=TXT_FG,
                 bg=DEF_BG).grid(row=6, column=0, sticky=tk.E)
        self.use_aux = tk.IntVar()
        frbb = tk.Frame(frame1, border=0, pady=2, bg=DEF_BG)
        tk.Radiobutton(frbb, text="No  ", fg=TXT_FG, bg=DEF_BG,
                       selectcolor='green', variable=self.use_aux, value=0,
                       command=self.disable_aux).pack(side=tk.LEFT)
        tk.Label(frbb, text='    ', bg=DEF_BG).pack(side=tk.LEFT)
        tk.Radiobutton(frbb, text="Yes", fg=TXT_FG, bg=DEF_BG,
                       selectcolor='green', variable=self.use_aux, value=1,
                       command=self.enable_aux).pack(side=tk.LEFT)
        frbb.grid(row=4, column=1, sticky=tk.W)
        self.aux_dir_f = tk.Label(frame1, text=CLICK_DD, width=50, fg=TXT_FG,
                                  bg=TXT_BG, anchor=tk.W, state=tk.DISABLED)
        self.aux_dir_f.grid(row=6, column=1, sticky=tk.E+tk.W)
        self.aux_dir_f.bind('<Button-1>', self.sel_aux_dir)
        tk.Frame(frame1,  pady=6, bg=DEF_BG).grid(row=7, column=0,    # linea di separazione
                                                  columnspan=5, sticky='we')
        tk.Label(frame1, text="Calib. data file ", fg=TXT_FG,
                 bg=DEF_BG).grid(row=8, column=0, sticky='e')
        self.aux_calib_f = tk.Label(frame1, text=CLICK_FF, state=tk.DISABLED,
                                    width=50, fg=TXT_FG, bg=TXT_BG, anchor=tk.W)
        self.aux_calib_f.grid(row=8, column=1, sticky=tk.E+tk.W)
        self.aux_calib_f.bind('<Button-1>', self.sel_sci_calib_file)
        frame1.pack(expand=1, fill=tk.X)

        frame2 = tk.Frame(self, bg=DEF_BG)
        frame21 = tk.Frame(frame2, bg=DEF_BG)
        tk.Label(frame21, text=' ', bg=DEF_BG, font=SMALLFONT).pack(expand=1, fill=tk.X)
        frame211 = tk.LabelFrame(frame21, text="Parameters", fg=TXT_FG, bg=DEF_BG)

        tk.Label(frame211, text="   Aux camera ntiles ", fg=TXT_FG,
                 bg=DEF_BG).grid(row=1, column=1, sticky=tk.E)
        self.tiles_e = tk.Entry(frame211, width=6, fg=TXT_FG, bg=TXT_BG)
        self.tiles_e.insert(0, "32")
        self.tiles_e.grid(row=1, column=2)
        tk.Label(frame211, text="  Sid. tracking freq. ", fg=TXT_FG,
                 bg=DEF_BG).grid(row=2, column=1, sticky='e')
        self.rate_e = tk.Entry(frame211, width=6, fg=TXT_FG, bg=TXT_BG)
        self.rate_e.insert(0, "59.2")
        self.rate_e.grid(row=2, column=2)
        frame211.pack(anchor='w')
        tk.Label(frame21, text=' ', bg=DEF_BG, font=SMALLFONT).pack(expand=1, fill=tk.X)
        frame212 = tk.LabelFrame(frame21, text="Calibration", fg=TXT_FG, bg=DEF_BG)
        tk.Label(frame212, text="    ", bg=DEF_BG).grid(row=1, column=1)

        tk.Label(frame212, text="Calib. mode: ", fg=TXT_FG,
                 bg=DEF_BG, pady=0).grid(row=1, column=2, sticky=tk.E)
        self.solve_mode = LOCAL_SOLVE
        self.solve_b = tk.Button(frame212, text=self.solve_mode, command=self.chg_mode,
                                 width=6, fg=TXT_FG, bg=DEF_BG, pady=0)
        wg.ToolTip(self.solve_b, text="Seleziona plate solving (locale/remoto)")
        self.solve_b.grid(row=1, column=3)
        bti = tk.Button(frame212, text="Sci.calib. image", command=lambda: self.calibrate("sci"),
                        width=17, fg=TXT_FG, bg=DEF_BG, pady=0)
        bti.grid(row=2, column=2, sticky=tk.W)
        wg.ToolTip(bti, text="Selezione immagine di calibrazione")
        self.sci_cal_stop = tk.Button(frame212, text="Stop", state=tk.DISABLED,
                                      command=self.cal_stop, width=6,
                                      fg=TXT_FG, bg=DEF_BG, pady=0)
        self.sci_cal_stop.grid(row=2, column=3, sticky=tk.W)
        self.aux_cal_start = tk.Button(frame212, text="Aux.calib. image", state=tk.DISABLED,
                                       command=lambda: self.calibrate("aux"), width=17,
                                       fg=TXT_FG, bg=DEF_BG, pady=0)
        self.aux_cal_start.grid(row=6, column=2, sticky=tk.W)
        self.aux_cal_stop = tk.Button(frame212, text="Stop", state=tk.DISABLED,
                                      command=self.cal_stop, width=6,
                                      fg=TXT_FG, bg=DEF_BG, pady=0)
        self.aux_cal_stop.grid(row=6, column=3, sticky=tk.W)
        frame212.pack(expand=1, fill=tk.X)
#       tk.Button(self, text="Clear text", command=self.clear_text_box, height=2, width=10,
#                 fg=TXT_FG, bg=DEF_BG).grid(row=21, column=12, columnspan=2)
        tk.Label(frame21, text=' ', bg=DEF_BG, font=SMALLFONT).pack(expand=1, fill=tk.X)
        self.start_button = tk.Button(frame21, text="START GUIDING", font=("Arial", 10, "bold"),
                                      command=self.startstop, height=2, width=10,
                                      fg=TXT_FG, bg=DEF_BG)
        self.start_button.pack(expand=1, fill=tk.X)
        tk.Label(frame21, text=' ', bg=DEF_BG, font=SMALLFONT).pack(expand=1, fill=tk.X)
        frame21.grid(row=1, column=0)
        self.u_point = [0]
        self.v_point = [0]
        tk.Label(frame2, text='                ', bg=DEF_BG).grid(row=1, column=1)
        frame22 = tk.Frame(frame2)
        fig = Figure(figsize=(2.20, 2.20), dpi=100, facecolor=DEF_BG)
        self.axes = fig.add_subplot(111, polar=True)
        radii = cart2pol(self.u_point, self.v_point)[1]
        self.axes.set_xticks(np.arange(0, 2.0*np.pi, np.pi/2))
        self.axes.set_xticklabels(['E', 'N', 'W', 'S'])
        self.axes.set_facecolor('green')
        self.axes.set_ylim(0, 10+1.5*np.max(radii))
        self.axes.tick_params(colors='w', grid_color='#9fe5a4')
        self.canvas = FigureCanvasTkAgg(fig, frame22)
        self.canvas.get_tk_widget().pack()
        frame22.grid(row=1, column=2)
        frame2.pack(anchor=tk.W)
        self.frame3 = tk.Frame(self, bg=DEF_BG)
        self.text_box = tk.Text(self.frame3, state=tk.DISABLED,
                                font=SMALLFONT, fg=TXT_FG, bg=TXT_BG)
        self.text_box.pack(expand=1, fill=tk.BOTH)
        self.frame3.pack(expand=1, fill=tk.BOTH)
        comm = guide.Comm()
        self.serverq = comm.server_side()
        self.comm = comm.client_side()
        self.guider = None
        self.guiding = False
        self.running = True
        guide.load_mult()
        self.log.mark(f"Homer mult loaded  AR: {guide.MULT.ar_mult}, DE: {guide.MULT.de_mult}")

    def info(self):
        'Scrive informazioni in pannello pseudo-popup'
        msg = [f'Homer GUI version: {__version__}']
        msg.append(f'datadir: {self.dir_root}')
        msg.append(f'sci. images dir: {self.sci_dir}')
        msg.append(f'aux. images dir: {self.aux_dir}')
        msg.append(f'Logfile: {self.log.logname}')
        msgw = wg.PopupText(self, '\n'.join(msg), border=2, relief=tk.RIDGE,
                         padx=10, pady=10, fg=INFO_FG, bg=INFO_BG)
        msgw.place(in_=self.frame3, relx=0.5, rely=0.5, anchor='center')
        msgw.lift()

    def error_msg(self, msg):
        'show error message'
        _debug('called error_msg()')
        errw = wg.PopupText(self, msg, ERR_LIFE, border=2, relief=tk.RIDGE,
                         padx=10, pady=10, fg=ERR_FG, bg=ERR_BG)
        errw.place(in_=self.frame3, relx=0.5, rely=0.5, anchor='center')
        errw.lift()

    def stop(self):
        'Gestione terminazione'
        _debug('Ricevuto stop')
        self.dostop()
        self.running = False
        guide.save_mult()
        self.log.mark(f"Homer mult saved  AR: {guide.MULT.ar_mult}, DE: {guide.MULT.de_mult}")
        self.log.stop()
        _debug('Homer terminato')

    def chg_mode(self):
        'Toggle solving mode'
        if self.solve_mode == LOCAL_SOLVE:
            self.solve_mode = REMOTE_SOLVE
        else:
            self.solve_mode = LOCAL_SOLVE
        self.solve_b.config(text=self.solve_mode)

    def sel_sci_dir(self, _unused):
        "Set the folder for scientific images"
        self.sci_dir = browse_folder(self.sci_dir, 'Select science dir.')
        self.sci_dir = self.sci_dir.strip()
        if self.sci_dir:
            self.sci_dir_f.config(text=self.sci_dir)
        else:
            self.sci_dir_f.config(text=CLICK_DD)
            self.write("Science image folder not set")
        self.sci_dir_f.config(text=self.sci_dir)

    def sel_aux_dir(self, _unused):
        "Set the folder for auxiliary images"
        self.aux_dir = browse_folder(self.aux_dir, "Select aux dir.")
        self.aux_dir = self.aux_dir.strip()
        if self.aux_dir:
            self.aux_dir_f.config(text=self.aux_dir)
        else:
            self.aux_dir_f.config(text=CLICK_DD)
            self.write("Aux image folder not set")

    def sel_sci_calib_file(self, _unused):
        'Select existent calib file'
        self.sci_calib_file = browse_file(self.sci_calib_dir, 'Select calib. file', filt='calib')
        self.sci_calib_file = self.sci_calib_file.strip()
        if os.path.exists(self.sci_calib_file):
            self.sci_calib_f.config(text=self.sci_calib_file)
            self.sci_calib_dir = os.path.dirname(self.sci_calib_file)
        else:
            self.sci_calib_f.config(text=CLICK_FF)
            self.write("Science calibration file not set")

    def sel_aux_calib_file(self, _unused):
        'Select existent calib file'
        self.aux_calib_file = browse_file(self.aux_calib_dir, 'Select calib. file', filt='calib')
        self.aux_calib_file = self.aux_calib_file.strip()
        if os.path.exists(self.aux_calib_file):
            self.aux_calib_f.config(text=self.aux_calib_file)
            self.aux_calib_dir = os.path.dirname(self.aux_calib_file)
        else:
            self.aux_calib_f.config(text=CLICK_FF)
            self.write("Aux calibration file not set")

    def write(self, words):
        "Add line to log window"
#       _debug("write: "+words)
        self.log.mark(words)
        self.text_box.config(state=tk.NORMAL)
        self.text_box.insert("end", words+"\n")
        self.text_box.see("end")
        self.text_box.config(state=tk.DISABLED)

    def clear_text_box(self):
        "Clear log window"
        yesorno = wg.YesNo(self, YOU_SURE%self.log.logname, position="c")
        self.wait_window(yesorno)
        if yesorno.status:
            self.text_box.config(state=tk.NORMAL)
            self.text_box.delete('1.0', tk.END)
            self.text_box.config(state=tk.DISABLED)
            self.add_points(0, 0, 1, "blue")

    def enable_aux(self):
        "Set aux camera widget to state enabled"
        self.aux_dir_f.config(state=tk.NORMAL)
        self.aux_calib_f.config(stat=tk.NORMAL)
        self.aux_cal_start.config(state=tk.NORMAL)

    def disable_aux(self):
        "Set aux camera widget to state disabled"
        self.aux_dir_f.config(state=tk.DISABLED)
        self.aux_calib_f.config(stat=tk.DISABLED)
        self.aux_cal_start.config(state=tk.DISABLED)

    def guider_listener(self):
        "Listen to guider queue for interactions"
        if not self.comm.empty():
            cmd, data = self.comm.get()
            _debug(f"from guider: {cmd} - {str(data)}")
            if cmd == "LOG":
                self.write(str(data))
            elif cmd == "TERM":
                self.guider.join()
                self.write(f'Guiding terminated: {data}')
                self.start_button.config(text="START")
                return
            if cmd == "ERR":
                self.guider.join()
                errmsg = f'Guiding error: {data}'
                self.write(errmsg)
                self.error_msg(errmsg)
                self.start_button.config(text="START")
                return
            if cmd == "SHIFT":
                self.add_points(data[0], data[1], 40, "blue")
            elif cmd == "ORNT":
                self.orientation = -(90+float(data))*np.pi/180
                self.axes.axvline(x=self.orientation, color="orange",
                                  linewidth=2, linestyle="--", label="DEC")
                self.axes.axvline(x=np.pi/2+self.orientation, color="brown",
                                  linewidth=2, linestyle="--", label="RA")
                self.axes.legend(loc=2, bbox_to_anchor=(0.8, 1.1), prop={'size': 5})
                self.canvas.draw()
        self.after(200, self.guider_listener)

    def dostop(self):
        "Stop guider"
        if self.guiding:
            self.comm.put("STOP")
            self.start_button.config(text="START")
            self.guider.join()
            self.write("Homer Autoguiding stopped")
            self.guiding = False

    def startstop(self):
        "Start/stop guiding"
        if self.start_button['text'] == "STOP":
            self.dostop()
            return
        self.axes.cla()
        use_aux = self.use_aux.get() == 1
        sci_tiles = SCI_TILES
        aux_tiles = int(self.tiles_e.get())

        errlist = ''
        if not self.sci_dir or (use_aux and (not self.aux_dir)):
            errlist += NO_IMG_DIR
        if (not self.sci_calib_file) or (use_aux and (not self.aux_calib_file)):
            errlist += '\n'+NO_CALIB_FILE
        if errlist:
            self.error_msg('ERROR\n'+errlist)
            return
        guider_args = (self.serverq, self.sci_dir,
                       self.sci_calib_file, sci_tiles,
                       self.aux_dir, self.aux_calib_file,
                       aux_tiles, self.simul, _GB.debug)
        self.guider = mp.Process(target=guide.guideloop, args=guider_args)
        self.start_button.config(text="STOP")
        self.guider_listener()
        self.write('Homer Autoguiding starting')
        self.guiding = True
        self.guider.start()

    def calibrate(self, what):                #pylint: disable=R0912,R0915
        "lancia procedura di calibrazione"
        prefix = time.strftime('%Y-%m-%d_%H%M%S-')
        if what == "sci":
            image_path = browse_file(self.sci_calib_dir, 'Select calib. image')
            out_file = os.path.join(self.cal_dir, prefix+SCI_CALIB_DATA_NAME)
            self.sci_cal_stop.config(state=tk.NORMAL)
        else:
            image_path = browse_file(self.aux_calib_dir, 'Select calib. image')
            out_file = os.path.join(self.cal_dir, prefix+AUX_CALIB_DATA_NAME)
            self.aux_cal_stop.config(state=tk.NORMAL)
        if not image_path:
            return
        aqueue = mp.SimpleQueue()
        islocal = self.solve_mode == LOCAL_SOLVE
        proc = mp.Process(target=calibrate, args=(image_path, aqueue, out_file, islocal))
        proc.start()
        self.write("Calibration process started")
        self.update()
        self._goon = True
        while self._goon:
            if not aqueue.empty():
                cmd, value = aqueue.get()
                _debug(f"QUEUE ({str(cmd)}, {str(value)})")
                if cmd == "LOG":
                    self.write(value)
                elif cmd == 'TMO':
                    tmout = value+5
                    progr = wg.Progress(self, title="Doing calibration",
                                        duration=tmout, position=(100, 100))
                elif cmd == "ERR":
                    err = 'Calibration error: '+value
                    self.error_msg(err)
                    self.write(err)
                    self.write('Calibration file not saved')
                    remove(out_file)
                    progr.kill()
                    out_file = ''
                    break
                elif cmd == "OK":
                    self.write('Calibration file saved to: '+value)
                    progr.kill()
                    break
            self.update()
            time.sleep(0.1)
        progr.kill()
        if out_file:
            if what == 'sci':
                _debug(f'New sci. calib file {out_file}')
                self.sci_calib_file = out_file
                self.sci_calib_f.config(text=out_file)
            else:
                _debug(f'New aux. calib file {out_file}')
                self.aux_calib_file = out_file
                self.aux_calib_f.config(text=out_file)
        else:
            wg.WarningMsg(self, CAL_STOPPED, position="c")
            self.write(CAL_STOPPED)
        self.sci_cal_stop.config(state=tk.DISABLED)
        self.aux_cal_stop.config(state=tk.DISABLED)

    def cal_stop(self):
        "Interrompe calibrazione"
        self._goon = False

    def add_points(self, ics, ipsilon, dimension, paint):
        "Aggiungi punti al plot radiale"
        self.axes.cla()
        self.u_point.append(ics)
        self.v_point.append(ipsilon)
        if self.start_button['text'] == "START":
            self.u_point.clear()
            self.u_point.append(0)
            self.v_point.clear()
            self.v_point.append(0)
        angles, radii = cart2pol(self.u_point, self.v_point)
        self.axes.scatter(angles, radii, color=paint, s=dimension, alpha=0.3)
        self.axes.set_xticks(np.arange(0, 2.0*np.pi, np.pi/2))
        self.axes.set_xticklabels(['E', 'N', 'W', 'S'])
        self.axes.set_ylim(0, 10+1.5*np.max(radii))
        self.axes.tick_params(colors='w', grid_color='#9fe5a4')
        self.axes.axvline(x=self.orientation, color="orange",
                          linewidth=2, linestyle="--", label="DEC")
        self.axes.axvline(x=np.pi/2+self.orientation, color="brown",
                          linewidth=2, linestyle="--", label="RA")
        self.axes.legend(loc=2, bbox_to_anchor=(0.8, 1.1), prop={'size': 5})
        self.canvas.draw()

def finish(app):
    "Terminate app"
    app.stop()
    _GB.root.destroy()

def main():
    "Lancia la GUI"
    if "-h" in sys.argv:
        root = tk.Tk()
        wdg = wg.MessageText(root, __doc__.format(__version__))
        wdg.pack()
        root.mainloop()
        sys.exit()

    if "-v" in sys.argv:
        print(__version__)
        sys.exit()

    if "-d" in sys.argv:
        _GB.debug = True
        guide.set_debug(True)
        wg.set_debug(True)

    simulation = "-s" in sys.argv

    _GB.root = tk.Tk()
    _GB.config = get_config()

    if not _GB.config:
        info = wg.WarningMsg(_GB.root, NO_CONFIG, title="Homer")
#       config.store_config()
        _GB.root.withdraw()
        _GB.root.wait_window(info)
        sys.exit()

    _debug("Homer GUI starting")
    if simulation:
        basedir = '__work__'
        mode = " [Simulation]"
    else:
        basedir = _GB.config['local_store']
        mode = ""
    if not os.path.exists(basedir):
        os.makedirs(basedir)

    _GB.root.title("Homer GUIding v. "+__version__+mode)
    _GB.root.configure(bg=DEF_BG)

    _GB.root.iconphoto(False, wg.get_icon("homer", 32))

    app = HomerGUI(_GB.root, _GB.config, basedir,  simul=simulation, debug=_GB.debug)
    _GB.root.protocol("WM_DELETE_WINDOW", lambda x=app: finish(app))
    app.pack()
    _debug("Homer GUI ready")
    _GB.root.mainloop()

if __name__ == "__main__":
    main()
