"""
hgui.py  Autoguider from scientific images (and more)

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
import multiprocessing as mp
import tkinter as tk
from tkinter import filedialog

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# pylint: disable=C0413
import opc.widgets as wg
from opc.utils import get_config
import opc.constants as const
from opc.logfile import Logger
from calibrate import calibrate, SOLVE_TIMEOUT
import guide

#__version__ = "1.5"   # Corretto errore quando lo shift è negativo
#__version__ = "1.6"   # Aggiunto log del tempo di ritardo dei comandi al telescopio
__version__ = "1.7"   # Corretto bug (errore formato log) che bloccava dopo la prima immagine

__author__ = "L. Naponiello, L. Fini"
__date__ = "Settembre 2022"

TEST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tests", "__work__"))

NO_CONFIG = """
  File di configurazione mancante o incompleto

  Sarà creato un file di default che sarà attivo
  al prossimo restart
"""

YOU_SURE = """Confirm? All text will be removed from screen.
Anyway the full log is saved in file:

%s"""

CANT_START = """Autoguiding can't start without
all the files and folders required."""

CAL_STOPPED = "Calibration process interrupted"

MAIN_BG_COLOR = '#3c3b37'

CALIB_DATA_NAME = "calib_data.wcs"    # Name of calibration data file

SCI_TILES = 32  # Number of tiles for Donuts (scientific image)

class GLOB:                                # pylint: disable=R0903
    "Some global variables without global"
    debug = False
    config = {}
    root = None

def debug(txt):
    "Show debug lines"
    if GLOB.debug:
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

def browse_folder(ftype, initialdir=None):
    "Allow user to select folder"
    msg = f"Select the folder where the {ftype} images will be saved"
    ret = filedialog.askdirectory(title=msg, initialdir=initialdir)
    if not ret:
        ret = ""
    return ret

def browse_image(initialdir):
    "Allow user to select a new image for calibration"
    msg = "Select the image fit/s file for the calibration"
    calpath = filedialog.askopenfilename(title=msg,
                                         filetypes=(("fit files", "*.fit*"),
                                                    ("all files", "*.*")),
                                         initialdir=initialdir)
    return calpath

def cart2pol(xxx, yyy):
    "Convert cartesian coord into polar"
    if len(xxx) != 1 and len(yyy) != 1:
        xxx, yyy = np.delete(xxx, 0), np.delete(yyy, 0)
    radius = np.hypot(xxx, yyy)
    theta = np.arctan2(yyy, xxx)
    return theta, radius

class HomerGUI(tk.Frame):                                   # pylint: disable=R0901,R0902
    "GUI for Homer guiding app"
    def __init__(self, master, basedir, simul=False):    # pylint: disable=R0915
        super().__init__(master, bg=MAIN_BG_COLOR)
        self.arcsec_rate = 15
        self.donuts = None
        self.science_path = None
        self.first_science = None
        self.orientation = None
        self.tel = None
        self.simul = simul
        self._goon = False
        self.log = Logger(GLOB.logdir, "homer")
        self.log.mark(f"Homer {__version__} started ---------")
        self.sci_root = basedir
        self.aux_root = basedir

        self.folderimg = wg.get_icon("folder", 24)
        tk.Label(self, image=wg.get_icon("opc", 64),
                 bg=MAIN_BG_COLOR).grid(row=18, rowspan=8, column=0, sticky=tk.W+tk.S)

        self.text_box = tk.Text(self, state=tk.DISABLED, fg='white', bg='#5f5e58')
        self.text_box.grid(row=0, column=12, rowspan=20, columnspan=20)

        frame1 = tk.LabelFrame(self, text="Directories", fg='white', bg=MAIN_BG_COLOR)
        frame1.grid(row=0, column=0, columnspan=11, sticky=tk.W+tk.N)

        tk.Label(frame1, text="Science folder ", fg='white',
                 bg=MAIN_BG_COLOR).grid(row=0, column=0, sticky=tk.E)
        self.sci_dir_f = tk.Label(frame1, width=50, fg='white', bg='#5f5e58', anchor=tk.W)
        self.sci_dir_f.grid(row=0, column=1, columnspan=10)
        self.sci_dir_tt = wg.ToolTip(self.sci_dir_f, text="")
        tk.Button(frame1, image=self.folderimg, command=self.set_sci_folder,
                  bg=MAIN_BG_COLOR).grid(row=0, column=11)
        self.realcalibnew = tk.StringVar()
        tk.Label(frame1, text="Calib. data file ", fg='white',
                 bg=MAIN_BG_COLOR).grid(row=1, column=0, sticky=tk.E)
        self.sci_calib_f = tk.Label(frame1, anchor=tk.W, width=50, fg='white', bg='#5f5e58')
        self.sci_calib_f.grid(row=1, column=1, columnspan=10)
        self.sci_calib_tt = wg.ToolTip(self.sci_calib_f, text="")
#       tk.Button(frame1, image=self.folderimg, command=self.browse_calib_file,
#                 bg=MAIN_BG_COLOR).grid(row=1, column=11)

        tk.Label(frame1, text="Use aux camera? ", fg='white',
                 bg=MAIN_BG_COLOR).grid(row=2, column=0, sticky=tk.E)
        tk.Label(frame1, text="Aux camera folder ", fg='white',
                 bg=MAIN_BG_COLOR).grid(row=3, column=0, sticky=tk.E)
        self.use_aux = tk.IntVar()
        tk.Radiobutton(frame1, text="No  ", fg='white', bg=MAIN_BG_COLOR,
                       selectcolor='green', variable=self.use_aux, value=0,
                       command=self.disable_aux).grid(row=2, column=1, sticky=tk.W)
        tk.Radiobutton(frame1, text="Yes", fg='white', bg=MAIN_BG_COLOR,
                       selectcolor='green', variable=self.use_aux, value=1,
                       command=self.enable_aux).grid(row=2, column=2, sticky=tk.W)
        self.aux_dir_f = tk.Label(frame1, width=50, fg='white',
                                  bg='#5f5e58', anchor=tk.W, state=tk.DISABLED)
        self.aux_dir_f.grid(row=3, column=1, columnspan=10)
        self.aux_dir_tt = wg.ToolTip(self.aux_dir_f, text="")
        self.use_aux_b = tk.Button(frame1, image=self.folderimg, state=tk.DISABLED,
                                   command=self.set_aux_folder, bg=MAIN_BG_COLOR)
        self.use_aux_b.grid(row=3, column=11)
        tk.Label(frame1, text="Calib. data file ", fg='white',
                 bg=MAIN_BG_COLOR).grid(row=4, column=0)
        self.aux_calib_f = tk.Label(frame1, state=tk.DISABLED,
                                    width=50, fg='white', bg='#5f5e58', anchor=tk.W)
        self.aux_calib_f.grid(row=4, column=1, columnspan=10)
        self.aux_calib_tt = wg.ToolTip(self.aux_calib_f, text="")
        frame2 = tk.LabelFrame(self, text="Connection", fg='white', bg=MAIN_BG_COLOR)
        frame2.grid(row=1, column=0, rowspan=6, sticky=tk.W+tk.N)

        frame3 = tk.LabelFrame(self, text="Parameters", fg='white', bg=MAIN_BG_COLOR)
        frame3.grid(row=1, column=0, sticky=tk.W+tk.N)

        tk.Label(frame3, text="Aux camera ntiles ", fg='white',
                 bg=MAIN_BG_COLOR).grid(row=0, column=0, sticky=tk.E)
        self.tiles_e = tk.Entry(frame3, width=6, fg='white', bg='#5f5e58')
        self.tiles_e.insert(0, "32")
        self.tiles_e.grid(row=0, column=1)
        tk.Label(frame3, text="Sid. tracking freq. ", fg='white',
                 bg=MAIN_BG_COLOR).grid(row=1, column=0)
        self.rate_e = tk.Entry(frame3, width=6, fg='white', bg='#5f5e58')
        self.rate_e.insert(0, "59.2")
        self.rate_e.grid(row=1, column=1)

        frame4 = tk.LabelFrame(self, text="Calibration", fg='white', bg=MAIN_BG_COLOR)
        frame4.grid(row=1, column=2)
        tk.Label(frame4, text="    ", bg=MAIN_BG_COLOR).grid(row=1, column=1)
        tk.Button(frame4, text="Sci. image ", command=lambda: self.calibrate("sci"), width=10,
                  fg='white', bg=MAIN_BG_COLOR, pady=0).grid(row=1, column=2, sticky=tk.W)
        self.sci_cal_stop = tk.Button(frame4, text="Stop", state=tk.DISABLED,
                                      command=self.cal_stop, width=6,
                                      fg='white', bg=MAIN_BG_COLOR, pady=0)
        self.sci_cal_stop.grid(row=1, column=3, sticky=tk.W)
        self.aux_cal_start = tk.Button(frame4, text="Aux. image", state=tk.DISABLED,
                                       command=lambda: self.calibrate("aux"), width=10,
                                       fg='white', bg=MAIN_BG_COLOR, pady=0)
        self.aux_cal_start.grid(row=2, column=2, sticky=tk.W)
        self.aux_cal_stop = tk.Button(frame4, text="Stop", state=tk.DISABLED,
                                      command=self.cal_stop, width=6,
                                      fg='white', bg=MAIN_BG_COLOR, pady=0)
        self.aux_cal_stop.grid(row=2, column=3, sticky=tk.W)
        tk.Button(self, text="Clear text", command=self.clear_text_box, height=2, width=10,
                  fg='white', bg=MAIN_BG_COLOR).grid(row=21, column=12, columnspan=2)
        self.start_button = tk.Button(self, text="START", font=("Arial", 10, "bold"),
                                      command=self.startstop, height=2, width=10,
                                      fg='white', bg=MAIN_BG_COLOR)
        self.start_button.grid(row=21, column=31, sticky=tk.E)
        self.u_point = [0]
        self.v_point = [0]

        fig = Figure(figsize=(2.20, 2.20), dpi=100, facecolor=MAIN_BG_COLOR)
        self.axes = fig.add_subplot(111, polar=True)
        radii = cart2pol(self.u_point, self.v_point)[1]
        self.axes.set_xticks(np.arange(0, 2.0*np.pi, np.pi/2))
        self.axes.set_xticklabels(['E', 'N', 'W', 'S'])
        self.axes.set_facecolor('green')
        self.axes.set_ylim(0, 10+1.5*np.max(radii))
        self.axes.tick_params(colors='w', grid_color='#9fe5a4')
        self.canvas = FigureCanvasTkAgg(fig, self)
        self.canvas.get_tk_widget().grid(row=2, column=1, columnspan=3, rowspan=20)

        comm = guide.Comm()
        self.serverq = comm.server_side()
        self.comm = comm.client_side()
        self.guider = None
        self.guiding = False
        self.sci_dir = ""
        self.aux_dir = ""
        self.sci_calib_name = ""
        self.aux_calib_name = ""

    def set_sci_folder(self):
        "Set the folder for scientific images"
        self.sci_dir = browse_folder("science camera", self.sci_root)
        dname = trim(self.sci_dir, self.sci_dir_f.cget('width'))
        self.sci_dir_f.config(text=dname)
        self.sci_dir_tt.set(self.sci_dir)
        self.set_sci_calib_file()

    def set_aux_folder(self):
        "Set the folder for auxiliary images"
        self.aux_dir = browse_folder("aux camera", self.aux_root)
        dname = trim(self.aux_dir, self.aux_dir_f.cget('width'))
        self.aux_dir_f.config(text=dname)
        self.aux_dir_tt.set(self.aux_dir)
        self.set_aux_calib_file()

    def set_sci_calib_file(self):
        "Check existence of science calib file an set it"
        print("DBG> ", self.sci_dir, CALIB_DATA_NAME)
        self.sci_calib_name = os.path.join(self.sci_dir, CALIB_DATA_NAME)
        debug("In set_sci_calib_file, sci_dir: "+self.sci_dir)
        if os.path.exists(self.sci_calib_name):
            fname = trim(self.sci_calib_name, self.sci_calib_f.cget('width'))
        else:
            self.write("Science calibration file not found")
            fname = ""
            self.sci_calib_name = ""
        self.sci_calib_f.config(text=fname)
        self.sci_calib_tt.set(self.sci_calib_name)

    def set_aux_calib_file(self):
        "Check existence of auxiliary calib file an set it"
        self.aux_calib_name = os.path.join(self.aux_dir, CALIB_DATA_NAME)
        debug("In set_aux_calib_file, self.aux_dir: "+self.aux_dir)
        if os.path.exists(self.aux_calib_name):
            fname = trim(self.aux_calib_name, self.aux_calib_f.cget('width'))
        else:
            self.write("Auxiliary calibration file not found")
            self.aux_calib_name = ""
            fname = ""
        self.aux_calib_f.config(text=fname)
        self.aux_calib_tt.set(self.aux_calib_name)

    def write(self, words):
        "Add line to log window"
        debug("write: "+words)
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
        self.use_aux_b.config(state=tk.NORMAL)
        self.aux_calib_f.config(stat=tk.NORMAL)
        self.aux_cal_start.config(state=tk.NORMAL)

    def disable_aux(self):
        "Set aux camera widget to state disabled"
        self.aux_dir_f.config(state=tk.DISABLED)
        self.use_aux_b.config(state=tk.DISABLED)
        self.aux_calib_f.config(stat=tk.DISABLED)
        self.aux_cal_start.config(state=tk.DISABLED)

    def guider_listener(self):
        "Listen to guired queue for interactions"
        if not self.comm.empty():
            cmd, data = self.comm.get()
            debug(f"from guider: {cmd} - {str(data)}")
            if cmd == "LOG":
                self.write(str(data))
            elif cmd == "TERM":
                self.guider.join()
                self.write('Guiding terminated with error')
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
        "Start guiding"
        if self.start_button['text'] == "STOP":
            self.dostop()
            return

        use_aux = self.use_aux.get() == 1
        sci_tiles = SCI_TILES
        aux_tiles = int(self.tiles_e.get())

        error = (not self.sci_calib_name) or \
                (use_aux and (not self.aux_calib_name))
        if error:
            wg.ErrorMsg(self, CANT_START, position="c")
            return
        guider_args = (self.serverq, self.sci_dir,
                       self.sci_calib_name, sci_tiles,
                       self.aux_dir, self.aux_calib_name,
                       aux_tiles, self.simul, GLOB.debug)
        self.guider = mp.Process(target=guide.guideloop, args=guider_args)
        self.start_button.config(text="STOP")
        self.guider_listener()

        self.write('Homer Autoguiding starting')
        self.guiding = True
        self.guider.start()

    def calibrate(self, what):
        "lancia procedura di calibrazione"
        if what == "sci":
            image_path = browse_image(self.sci_dir)
            out_file = os.path.join(self.sci_dir, CALIB_DATA_NAME)
            checkfile = self.set_sci_calib_file
            self.sci_cal_stop.config(state=tk.NORMAL)
        else:
            image_path = browse_image(self.aux_dir)
            out_file = os.path.join(self.aux_dir, CALIB_DATA_NAME)
            checkfile = self.set_aux_calib_file
            self.aux_cal_stop.config(state=tk.NORMAL)
        if not image_path:
            return
        aqueue = mp.SimpleQueue()
        proc = mp.Process(target=calibrate, args=(image_path, aqueue, out_file))
        proc.start()
        self.write("Calibration process started")
        self.update()
        progr = wg.Progress(self, title="Doing calibration",
                             duration=SOLVE_TIMEOUT+5, position=(100, 100))
        self._goon = True
        while self._goon:
            if not aqueue.empty():
                cmd, value = aqueue.get()
                debug(f"From queue ({str(cmd)}, {str(value)[:30]})")
                if cmd == "LOG":
                    self.write(value)
                elif cmd == "ERR":
                    wg.ErrorMsg(self, value, title="Calibration error", position="c")
                    self.write('Calibration error: '+value)
                    self.write('Calibration file not saved')
                    remove(out_file)
                    progr.kill()
                    break
                elif cmd == "OK":
                    self.write('Calibration file saved to: '+value)
                    progr.kill()
                    break
            self.update()
            time.sleep(0.1)
        progr.kill()
        if self._goon:
            checkfile()
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

    def finish(self):
        "Terminate app"
        self.dostop()
        GLOB.root.destroy()

def main():
    "Lancia la GUI"
    if "-h" in sys.argv:
        print(__doc__)
        sys.exit()

    if "-v" in sys.argv:
        print(__version__)
        sys.exit()

    if "-d" in sys.argv:
        GLOB.debug = True
        guide.set_debug(True)
        wg.set_debug(True)

    simulation = "-s" in sys.argv

    GLOB.root = tk.Tk()
    GLOB.config = get_config()
    if not GLOB.config:
        info = wg.WarningMsg(GLOB.root, NO_CONFIG, title="Homer")
#       config.store_config()
        GLOB.root.withdraw()
        GLOB.root.wait_window(info)
        sys.exit()

    GLOB.logdir = os.path.join(GLOB.config["local_store"], const.LOG_SUBDIR)
    if not os.path.isdir(GLOB.logdir):
        os.makedirs(GLOB.logdir)

    debug("Homer GUI starting")
    if simulation:
        basedir = TEST_DIR
        mode = " [Simulation]"
    else:
        basedir = GLOB.config["local_store"]
        if not os.path.exists(basedir):
            os.makedirs(basedir)
        mode = ""

    GLOB.root.title("Homer GUIding v. "+__version__+mode)
    GLOB.root.configure(bg=MAIN_BG_COLOR)

    GLOB.root.iconphoto(False, wg.get_icon("homer", 32))

    app = HomerGUI(GLOB.root, basedir, simul=simulation)
    GLOB.root.protocol("WM_DELETE_WINDOW", app.finish)
    app.pack()

    debug("Homer GUI ready")
    GLOB.root.mainloop()

if __name__ == "__main__":
    main()
