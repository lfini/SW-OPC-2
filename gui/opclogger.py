"""
opclogger.py - Procedure di supporto alle osservazioni ad OPC

Uso per test:
    python opclogger.py [-s]

Dove:
    -s   Usa simulatore telescopio
"""

import sys
import os
import time
import json
import subprocess as subp
import tkinter as tk
import tkinter.messagebox as msb
import tkinter.scrolledtext as scr

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import opc.constants as const
from opc.utils import get_config
import opc.widgets as wg
from opc import tel_sampler as ts

__version__ = "2.0"
__date__ = "Marzo 2023"
__author__ = "Luca Fini"

MAIN_CHECK_PERIOD = 500     # Intervallo loop di check (ms)

NO_CONFIG = """
  File di configurazione mancante.
  o incompleto.

  Sarà lanciata la procedura di
  configurazione per crearlo o
  modificarlo.
"""

MISSING_INFO = """
Alcuni campi obbligatori sono stati lasciati vuoti.

Aggiungi i dati mancanti prima di proseguire.
"""

NO_DESCR = """
Per favore dai una descrizione sintetica del problema
nell'apposito campo
"""

NO_STIMA = """
Per favore verifica la posizione attuale della cupola
e inserisci la posizione approssimativa in gradi
"""

DUPLICATE_IDENT = """
L'identificatore %s è già stato usato.

E' necessario modificarlo
"""

CREATE_ERROR = """
Errore:

    %s

Impossibile proseguire
"""

CREATED_DIR = """
È stata creata la cartella:

 %s

da utilizzare per i dati di questa osservazione
"""

ILL_DIRECTORY = """
Nella cartella manca il file info.json

Sembra non sia stata correttamente inzializzata
"""

TBD = """
Funzione non ancora implementata

Usare: NOTA GENERICA
"""

BT_FONT = ("helvetica", 12, "bold")

NO_HOMER = """
Questa versione di Homer non è ancora adeguatamente testata.

Utilizzare la versione originale di L.Naponiello.
"""

NO_GOOD_FOR_FILENAME = "\\/*?:\"<>|^"

# Colori

BLACK = "#000000"
BLUE_D = "#000055"
CYAN_L = "#e0ffff"
GRAY_DD = "#222222"
GRAY_D = "#444444"
GREEN_L = "#66ff66"
GREEN_LL = "#99ff99"
RED_L = "#ff8888"
RED_LL = "#ffcccc"
WHITE = "#ffffff"
YELLOW = "#eeffff"

class _GB:
    'global status'
    debug = False
    do_stop = False
    stopped = False

def _debug(*args):
    "Funzione scrittura debug"
    if _GB.debug:
        print("DBG>", *args)

def safename(filename):
    "Verfica che filename sia una stringa valida come nome di file"
    for char in filename:
        if char in NO_GOOD_FOR_FILENAME:
            return False
    return True

SEPARATOR1 = " -- "
SEPARATOR2 = "---------"

DEV_NULL = open(os.devnull, "w")

def _time():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def start_process(path, with_python=False):
    "Lancia il processo identificato da path"
    if with_python:
        cmd = [sys.executable, path]
    else:
        cmd = [path]
    try:
        proc = subp.Popen(cmd, stdout=DEV_NULL, stderr=DEV_NULL, start_new_session=True)
    except Exception as excp:                           # pylint: disable=W0703
        msg = "Errore %s: %s"%(path, str(excp))
        _debug(msg)
        return None
    _debug("Lanciato:", path)
    return proc

def check_process(proc_obj):
    "Verifica se il processo è ancora attivo"
    return proc_obj.poll() is None

class _Logger:
    "Supporto per archiviazione logs"
    def __init__(self, logfilepath, o_widget=None):
        self.logfd = open(logfilepath, "a")
        self.o_widget=o_widget

    def logblob(self, timestamp, title, blob=None):
        "Scrive un blocco di log"
        text = timestamp+SEPARATOR1+title+os.linesep
        if blob:
            if isinstance(blob, str):
                lines = blob.splitlines()
            else:
                lines = blob
            while lines:
                first = lines.pop(0).rstrip()
                if first:
                    text += "  "+first+os.linesep
                    break
            last = None
            while lines:
                last = lines.pop().rstrip()
                if last:
                    break
            while lines:
                text += "  "+lines.pop(0).rstrip()+os.linesep
            if last:
                text += "  "+last+os.linesep
        text += SEPARATOR2+os.linesep
        print(text, file=self.logfd, flush=True)
        if self.o_widget:
            self.o_widget.showlog(text)

    def close(self):
        "Chiude logfile"
        self.logfd.close()

def get_datadirs(config):
    "Riporta elenco directory sotto la directory dati OPC"
    dataroot = config.get("local_store")
    if dataroot:
        if os.path.isdir(dataroot):
            datadirs = [x for x in os.listdir(dataroot) if os.path.isdir(os.path.join(dataroot, x))]
            datadirs.sort()
        else:
            os.makedirs(dataroot)
            datadirs = []
    else:
        raise RuntimeError("Errore configurazione")
    return datadirs

def get_info(datadir):
    "Recupera informazioni iniziali"
    infopath = os.path.join(datadir, const.INFO_FILE)
    _debug("lettura stato da:", infopath)
    try:
        with open(infopath) as f_in:
            info = json.load(f_in)
    except FileNotFoundError:
        return {}
    _debug('stato recuperato: '+str(info))
    return info

def dome_snap():
    "Interrogazione stato cupola"
    lines = []
    if GLOB.dome.Connected:
        lines.append("Dome Azimuth: "+str(GLOB.dome.Azimuth))
        lines.append("Dome status: "+("SLEWING" if GLOB.dome.Slewing else "IDLE"))
        lines.append("Telescope DEC: "+str(GLOB.telc.get_current_deh(as_string=True)))
        lines.append("Telescope HA: "+str(GLOB.telc.get_current_ha(as_string=True)))
    return lines

OBBLIGATORI = "Nota: i campi indicati con (*) sono obbligatori"
NO_TEL_INFO = "Interrogazione telescopio fallita"
NO_DOME_INFO = "Interrogazione cupola fallita"

class ObsInit(tk.Frame):                        # pylint: disable=R0901,R0902
    "Pannello per informazioni iniziali per osservazione"
    def __init__(self, master, config):
        super().__init__(master, padx=8, pady=8, bg=GRAY_D)
        self.config = config
        self.frame = tk.Frame(self, bg=GRAY_D)
        self.frame.pack()
        tk.Label(self.frame, text="Impostazioni iniziali", fg=YELLOW, bg=GRAY_D,
                 font=('Helvetica', 16, 'bold')).grid(row=0, column=0, columnspan=3)
        tk.Label(self.frame, fg=WHITE, bg=GRAY_D,
                 text="Nuovo identificatore: ").grid(row=2, column=0, pady=6, sticky=tk.E)
        validator = self.register(safename)
        frm1 = tk.Frame(self.frame, bg=GRAY_D)
        self.e_ident = tk.Entry(frm1, width=24, fg=WHITE, bg=GRAY_DD, insertbackground=WHITE,
                                validate="key", validatecommand=(validator, "%P"))
        self.e_ident.pack(side=tk.LEFT)
        tk.Button(frm1, text="Nuovo", pady=0, fg=WHITE, bg=GRAY_D,
                  command=self.set_ident).pack(side=tk.LEFT)
        frm1.grid(row=2, column=1, sticky=tk.W)
        options = get_datadirs(config)
        self.optionvar = tk.StringVar()
        if options:
            tk.Label(self.frame, fg=WHITE, bg=GRAY_D,
                     text="Seleziona esistente: ").grid(row=3, column=0, pady=6, sticky=tk.E)
            optm = tk.OptionMenu(self.frame, self.optionvar, *options, command=self.selected)
            optm.configure(fg=WHITE, bg=GRAY_D)
            optm.grid(row=3, column=1, sticky=tk.W)
        tk.Frame(self.frame, border=2, height=3,
                 relief=tk.RIDGE).grid(row=4, column=0, columnspan=3, sticky=tk.W+tk.E)
        tk.Label(self.frame, fg=WHITE, bg=GRAY_D,
                 text=OBBLIGATORI).grid(row=5, column=0, columnspan=2, sticky=tk.E)
        tk.Label(self.frame, fg=WHITE, bg=GRAY_D,
                 text="Data/ora inizio: ").grid(row=6, column=0, pady=6, sticky=tk.E)
        self.create_dir = True
        self.l_time = tk.Label(self.frame, text="", width=24, fg=WHITE,
                               anchor=tk.W, bg=BLUE_D, border=1, relief=tk.SUNKEN)
        self.l_time.grid(row=6, column=1, sticky=tk.W)
        tk.Label(self.frame, fg=WHITE, bg=GRAY_D,
                 text="Cartella per dati: ").grid(row=7, column=0, pady=6, sticky=tk.E)
        self.l_dir = tk.Label(self.frame, text="", width=60, fg=WHITE,
                              anchor=tk.W, bg=BLUE_D, border=1, relief=tk.SUNKEN)
        self.l_dir.grid(row=7, column=1, sticky=tk.W)
        tk.Label(self.frame, fg=WHITE, bg=GRAY_D,
                 text="Osservatore/i: ").grid(row=9, column=0, pady=6, sticky=tk.E)
        self.e_obs = tk.Entry(self.frame, width=60, fg=WHITE, bg=GRAY_DD,
                              insertbackground=WHITE, disabledbackground=GRAY_D, state=tk.DISABLED)
        self.e_obs.grid(row=9, column=1)
        tk.Label(self.frame, text="(*)", fg=WHITE, bg=GRAY_D).grid(row=9, column=2)
        tk.Label(self.frame, fg=WHITE, bg=GRAY_D,
                 text="Personale OPC: ").grid(row=11, column=0, pady=6, sticky=tk.E)
        self.e_pers = tk.Entry(self.frame, width=60, fg=WHITE, bg=GRAY_DD,
                               insertbackground=WHITE, disabledbackground=GRAY_D, state=tk.DISABLED)
        self.e_pers.grid(row=11, column=1, pady=6, sticky=tk.W)
        tk.Label(self.frame, fg=WHITE, bg=GRAY_D,
                 text="Note: ").grid(row=13, column=0, pady=6, sticky=tk.E+tk.N)
        self.e_note = tk.Text(self.frame, width=68, height=8, fg=WHITE,
                              insertbackground=WHITE, bg=GRAY_DD, state=tk.DISABLED)
        self.e_note.grid(row=13, column=1, pady=6, sticky=tk.W)

        self.b_goon = tk.Button(self.frame, text="   INIZIA   ",
                                state=tk.DISABLED, command=self.inizia)
        self.b_goon.grid(row=20, column=0, columnspan=3)
        self.timestamp = None
        self.datadir = None
        self.valid = False

    def set_ident(self):
        "Accetta identificatore"
        ident = self.e_ident.get().strip()
        if not ident:
            return
        self.timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        date = time.strftime("%Y-%m-%d_")
        self.datadir = os.path.join(self.config["local_store"], date+ident)
        self.l_time.config(text=self.timestamp)
        self.l_dir.config(text=self.datadir)
        self.e_pers.config(state=tk.NORMAL)
        self.e_obs.config(state=tk.NORMAL)
        self.e_note.config(state=tk.NORMAL)
        self.b_goon.config(state=tk.NORMAL)

    def selected(self, dirname):
        "Callback per selezione opzione"
        self.e_ident.delete(0, tk.END)
        self.datadir = os.path.join(self.config.get("local_store"), dirname)
        info = get_info(self.datadir)
        if not info:
            msb.showinfo(title="Cartella non valida", message=ILL_DIRECTORY)
            return
        self.e_pers.config(state=tk.NORMAL)
        self.e_obs.config(state=tk.NORMAL)
        self.e_note.config(state=tk.NORMAL)
        self.create_dir = False
        self.l_dir.config(text=self.datadir)
        inizio = info.get("inizio")
        if inizio:
            self.timestamp = inizio
            self.l_time.config(text=self.timestamp)
        osservatore = info.get("osservatore")
        if osservatore:
            self.e_obs.delete(0, tk.END)
            self.e_obs.insert(0, osservatore)
        personale = info.get("personale")
        if personale:
            self.e_pers.delete(0, tk.END)
            self.e_pers.insert(0, personale)
        nota = info.get("nota")
        if nota:
            self.e_note.delete("1.0", tk.END)
            self.e_note.insert("1.0", nota)
        self.b_goon.config(state=tk.NORMAL)
#       self.frame.destroy()

    def inizia(self):
        "Inizio operazioni"
        ident = self.e_ident.get().strip()
        observer = self.e_obs.get().strip()
        opc_pers = self.e_pers.get().strip()
        notes = self.e_note.get("1.0", tk.END)
        valid = bool(self.datadir) and bool(observer)
        if not valid:
            msb.showinfo(title="Informazioni mancanti", message=MISSING_INFO)
            return
        if self.create_dir:
            try:
                os.mkdir(self.datadir)
            except FileExistsError:
                msb.showinfo(title="Identificatore duplicato",
                             message=DUPLICATE_IDENT%ident)
                return
            except Exception as excp:                    # pylint: disable=W0703
                msb.showinfo(title="Errore creazione cartella:",
                             message=CREATE_ERROR%str(excp))
                return
            _debug('Creata directory:', self.datadir)
            msb.showinfo(title="Creazione cartella",
                         message=CREATED_DIR%self.datadir)
            info = {"ident": ident,
                    "osservatore": observer,
                    "personale": opc_pers,
                    "inizio": self.timestamp,
                    "nota": notes}
            with open(os.path.join(self.datadir, const.INFO_FILE), "w") as f_out:
                json.dump(info, f_out)
                _debug('Creato file:', f_out.name)
        self.valid = True
        _debug('primo passo termina correttamente')
        self.destroy()


class ButtonPanel(tk.Frame):                             # pylint: disable=R0901
    "bottoniera per logs"
    def __init__(self, master, tel_sampler):
        super().__init__(master, bg=GRAY_D, pady=5)
        self.tel_sampler = tel_sampler
        btframe = tk.Frame(self, bg=GRAY_D)
        tk.Button(btframe, text="NUOVO\nOGGETTO", padx=5, pady=5, font=BT_FONT,
                  width=11, command=self.az_nuovo).grid(row=1, column=1)
        tk.Button(btframe, text="INFO\nSTRUMENTI", padx=5, pady=5, font=BT_FONT,
                  width=11, command=self.az_strum).grid(row=1, column=2)
        tk.Button(btframe, text="NOTA\nGENERICA", padx=5, pady=5, font=BT_FONT,
                  width=11, command=self.az_nota).grid(row=1, column=3)
        tk.Button(btframe, text="ANOMALIA\nTELESCOPIO", padx=5, pady=5, bg=RED_L, font=BT_FONT,
                  activebackground=RED_LL, width=11, command=self.az_anomtel).grid(row=1, column=4)
        tk.Button(btframe, text="ANOMALIA\nCUPOLA", padx=5, pady=5, bg=RED_L, font=BT_FONT,
                  activebackground=RED_LL, width=11, command=self.az_anomdome).grid(row=1, column=5)
        tk.Button(btframe, text="ANOMALIA\nCAMERA", padx=5, pady=5, bg=RED_L, font=BT_FONT,
                  activebackground=RED_LL, width=11, command=self.az_anomcam).grid(row=1, column=6)
#       self.b_dtracker = tk.Button(btframe, text="LANCIA\nDTRACKER", padx=5, pady=5,
#                                   bg=GREEN_L, font=BT_FONT, activebackground=GREEN_LL,
#                                   width=11, command=self.start_dtracker)
#       self.b_dtracker.grid(row=2, column=1)
#       self.p_dtracker = None
#       self.b_homer = tk.Button(btframe, text="LANCIA\nHOMER", padx=5, pady=5,
#                                bg=GREEN_L, font=BT_FONT, activebackground=GREEN_LL,
#                                width=11, command=self.start_homer)
#       self.b_homer.grid(row=2, column=2)
#       self.p_homer = None
#       tk.Frame(btframe, bg=GREEN_L, border=2,
#                relief=tk.RIDGE).grid(row=2, column=3, sticky=tk.E+tk.W+tk.N+tk.S)
#       tk.Frame(btframe, bg=GREEN_L, border=2,
#                relief=tk.RIDGE).grid(row=2, column=4, sticky=tk.E+tk.W+tk.N+tk.S)
#       tk.Frame(btframe, bg=GREEN_L, border=2,
#                relief=tk.RIDGE).grid(row=2, column=5, sticky=tk.E+tk.W+tk.N+tk.S)
#       tk.Frame(btframe, bg=GREEN_L, border=2,
#                relief=tk.RIDGE).grid(row=2, column=6, sticky=tk.E+tk.W+tk.N+tk.S)
        btframe.pack()
        self.setinfo = master.setinfo
#       self.maincheck()

#   def maincheck(self):
#       "Loop di verifica stato"
#       if _GB.do_stop:
#           _debug("ButtonPanel: ricevuto stop")
#           _GB.stopped = True
#           return
#       if self.p_dtracker is not None:
#           if not check_process(self.p_dtracker):
#               msg = "DTracker terminato"
#               _debug(msg)
#               text = _GB.logger.logblob(_time(), msg)
#               self.setinfo(msg)
#               self.p_dtracker = None
#               self.b_dtracker.config(state=tk.NORMAL)
#       if self.p_homer is not None:
#           if not check_process(self.p_homer):
#               msg = "Homer terminato"
#               _debug(msg)
#               text = _GB.logger.logblob(_time(), msg)
#               self.setinfo(msg)
#               self.p_homer = None
#               self.b_homer.config(state=tk.NORMAL)
#       self.after(MAIN_CHECK_PERIOD, self.maincheck)

    def tel_snap():
        "Snapshot stato telescopio TBD"
        lines = []
        ret = self.tel_sampler.get_status()
        if ret is None:
            return []
        lines.append("Global status: "+str(ret))
        ret = GLOB.telc.get_current_deh(as_string=True)
        lines.append("Current DE: "+str(ret))
        ret = GLOB.telc.get_current_rah(as_string=True)
        lines.append("Current RA: "+str(ret))
        ret = GLOB.telc.get_tsid(as_string=True)
        lines.append("Sidereal time: "+str(ret))
        ret = GLOB.telc.get_target_deh(as_string=True)
        lines.append("Target DE: "+str(ret))
        ret = GLOB.telc.get_target_rah(as_string=True)
        lines.append("Target RA: "+str(ret))
        mvstat = GLOB.telc.get_db()
        if mvstat is None:
            mvstat = "None"
        else:
            mvstat = "YES" if mvstat == 0x7f else "NO"
        lines.append("Tel. moving: "+mvstat)
        ret = GLOB.telc.get_trate()
        lines.append("Tracking freq: "+str(ret))
        ret = GLOB.telc.get_pside()
        lines.append("Pier side: "+str(ret))
        ret = GLOB.telc.get_olim()
        lines.append("Max. altitude: "+str(ret))
        ret = GLOB.telc.get_hlim()
        lines.append("Min. altitude: "+str(ret))
        firmw = (str(x) for x in GLOB.telc.get_firmware())
        lines.append("OnStep vers.: "+" ".join(firmw))
        ret = GLOB.telc.get_onstep_value("U1")
        lines.append("Motor 1 status: "+str(ret))
        ret = GLOB.telc.get_onstep_value("U2")
        lines.append("Motor 2 status: "+str(ret))
        return lines

    def az_nuovo(self):
        "Azione per bottone nuovo oggetto"
        self.setinfo()
        ret = NewObject(self)
        self.wait_window(ret)
        if ret.content:
            title = "Osservazione: "+ret.content["brief"]
            text = _GB.logger.logblob(ret.timestamp, title, ret.content["long"])

    def az_nota(self):
        "Azione per bottone nota generica"
        self.setinfo()
        ret = GenNote(self)
        self.wait_window(ret)
        if ret.content:
            title = "Nota: "+ret.content["brief"]
            text = _GB.logger.logblob(ret.timestamp, title, ret.content["long"])

    def az_strum(self):
        "Azione per bottone scegli strumenti"
        self.setinfo()
        ret = wg.Message(self, TBD, title="Definizione strumenti in uso", position=(30, 30))
        self.wait_window(ret)

    def az_anomtel(self):
        "Azione per bottone anomalia telescopio"
        self.setinfo()
        tmst = _time()
        tel_stat = self.tel_snap()
        if not tel_stat:
            self.setinfo(NO_TEL_INFO)
        ret = AnomTelescopio(self)
        self.wait_window(ret)
        if ret.content:
            title = "ANOMALIA TELESCOPIO: "+ret.content["brief"]
            text = _GB.logger.logblob(tmst, title, ret.content["long"])
            title = "DUMP STATO ONSTEP"
            if tel_stat:
                text = _GB.logger.logblob(tmst, title, tel_stat)
            else:
                text = _GB.logger.logblob(tmst, title, [NO_TEL_INFO])

    def az_anomdome(self):
        "Azione per bottone anomalia cupola"
        self.setinfo()
        tmst = _time()
        dome_stat = dome_snap()
        if not dome_stat:
            self.setinfo(NO_DOME_INFO)
        ret = AnomDome(self)
        self.wait_window(ret)
        if ret.content:
            title = "ANOMALIA CUPOLA: "+ret.content["brief"]
            text = _GB.logger.logblob(tmst, title, ret.content["long"])
            title = "DUMP STATO CUPOLA"
            if dome_stat:
                text = _GB.logger.logblob(tmst, title, dome_stat)
            else:
                text = _GB.logger.logblob(tmst, title, [NO_DOME_INFO])

    def az_anomcam(self):
        "Azione per bottone anomalia camera"
        self.setinfo()
        ret = wg.Message(self, TBD, title="Descrizione anomalia camera", position=(100, 100))
        self.wait_window(ret)


class ItemCard(tk.Toplevel):
    "Immissione informazioni"
    def __init__(self, master, title, brief_txt, long_txt, options=None):  # pylint: disable=R0913
        "Nota: options è una tupla (label, OptionsClass)"
        super().__init__(master, bg=GRAY_D)
        self.title(title)
        tk.Label(self, text="Data/ora:", bg=GRAY_D,
                 fg=WHITE).grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)
        self.timestamp = _time()
        tk.Label(self, text=self.timestamp, bg=GRAY_D, # border=2, relief=tk.RIDGE,
                 fg=WHITE).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        tk.Label(self, text=brief_txt, bg=GRAY_D,
                 fg=WHITE).grid(row=2, column=0, padx=5, pady=5, sticky=tk.E)
        self.e_nome = tk.Entry(self, width=60, bg=GRAY_DD, insertbackground=WHITE, fg=WHITE)
        self.e_nome.grid(row=2, column=1)
        if options:
            tk.Label(self, text=options[0], bg=GRAY_D,
                     fg=WHITE).grid(row=3, column=0, padx=5, pady=5, sticky=tk.NE)
            self.options = options[1](self, options[0])
            self.options.grid(row=3, column=1, padx=5, pady=5, sticky=tk.NW)
        else:
            self.options = None
        tk.Label(self, text=long_txt, bg=GRAY_D,
                 fg=WHITE).grid(row=5, column=0, padx=5, pady=5, sticky=tk.NE)
        self.e_text = tk.Text(self, width=68, height=8, bg=GRAY_DD,
                              insertbackground=WHITE, fg=WHITE)
        self.e_text.grid(row=5, column=1, padx=5, pady=5)
        bfr = tk.Frame(self, bg=GRAY_D)
        tk.Button(bfr, text="Annulla", width=8, command=self.annulla).pack(side=tk.LEFT)
        tk.Label(bfr, text="   ", bg=GRAY_D).pack(side=tk.LEFT)
        tk.Button(bfr, text="Registra", width=8, command=self.store).pack(side=tk.LEFT)
        bfr.grid(row=8, column=0, padx=6, pady=6, columnspan=2)
        wg.set_position(self, (0.01, 0.06), rel=master)
        self.content = None

    def annulla(self):
        "Callback pulsante Annulla"
        self.destroy()

    def store(self):
        "Callback pulsante OK"
        brief = self.e_nome.get().strip()
        if not brief:
            wg.WarningMsg(GLOB.root, NO_DESCR)
            return
        if self.options:
            msg = self.options.check_me()
            if msg:
                wg.WarningMsg(GLOB.root, msg)
                return
        self.content = {"brief": brief}
        text = ""
        if self.options:
            text += self.options.as_text()+"\n\n"
        text += self.e_text.get("1.0", tk.END)
        self.content["long"] = text
        self.destroy()

class NewObject(ItemCard):
    "Immissione informazioni per nuovo oggetto"
    def __init__(self, master):
        super().__init__(master, "Segnala nuovo oggetto osservazione",
                         "Nome oggetto:", "Commento:", None)

class GenNote(ItemCard):
    "Immissione informazioni per nuovo oggetto"
    def __init__(self, master):
        super().__init__(master, "Aggiungi nota",
                         "Titolo:", "Nota:", None)

class AnomTelescopio(ItemCard):
    "Immissione informazioni per anomalia telescopio"
    def __init__(self, master):
        super().__init__(master, "Segnala anomalia telescopio",
                         "Descrizione:", "Commenti:", None)
def sino(boolv):
    "Ritorna SI/NO"
    return "SI" if boolv else "NO"

class DomeOptions(tk.Frame):         # pylint: disable=R0913, R0901
    "Opzioni per anomalia cupola"
    def __init__(self, master, label):
        super().__init__(master, bd=2, relief=tk.RIDGE)
        self.olabel = label
        self.stima = ""
        self.v_moto = tk.BooleanVar()
        bt1 = tk.Checkbutton(self, text="Movim. manuale possibile ", variable=self.v_moto,
                             fg="white", bg=GRAY_D, selectcolor=GRAY_DD)
        bt1.pack(side=tk.LEFT)
        wg.ToolTip(bt1, text="Seleziona se funziona movim. manuale")
        self.v_posiz = tk.BooleanVar()
        bt2 = tk.Checkbutton(self, text="Posiz. corretta ", variable=self.v_posiz,
                             fg="white", bg=GRAY_D, selectcolor=GRAY_DD)
        wg.ToolTip(bt2, text="Seleziona se la posizione è corretta")
        bt2.pack(side=tk.LEFT)
        bt3 = tk.Label(self, text="   Stima posiz. attuale:", fg="white", bg=GRAY_D)
        bt3.pack(side=tk.LEFT)
        wg.ToolTip(bt3, text="Se posizione non corretta: indica azimuth stimato")
        self.e_stima = tk.Entry(self, width=4, fg="white", bg=GRAY_DD)
        self.e_stima.pack(side=tk.LEFT)
        tk.Label(self, text="°", fg="white", bg=GRAY_D).pack(side=tk.LEFT)

    def check_me(self):
        "Verifica consistenza informazioni"
        try:
            self.stima = int(self.e_stima.get())
        except ValueError:
            self.stima = ""
        if not self.v_posiz.get() and not self.stima:
            return NO_STIMA
        return ""

    def as_text(self):
        "Riporta versione testuale dello stato"
        v_moto = self.v_moto.get()
        v_posiz = self.v_posiz.get()
        text = self.olabel+" [Movim. manuale possibile: %s;  Posiz. corretta: %s"% \
               (sino(v_moto), sino(v_posiz))
        if not v_posiz:
            text += "; Stima posiz.: %d"%self.stima
        text += "]"
        return text

class AnomDome(ItemCard):
    "Immissione informazioni per anomalia cupola"
    def __init__(self, master):
        super().__init__(master, "Segnala anomalia cupola",
                         "Descrizione:", "Commenti:",
                         options=("Stato cupola:", DomeOptions))

class OpcLogger(tk.Frame):                            # pylint: disable=R0901
    "Pannello per la generazione di logs"
    def __init__(self, master, datadir, tel_sampler, **kwargs):
        super().__init__(master, **kwargs)
        self.datadir = datadir
        self.tls = tel_sampler
        ButtonPanel(self, tel_sampler).pack(expand=1, fill=tk.X)
        self.statline = tk.Label(self, bg=BLUE_D, fg=WHITE, border=2, relief=tk.RIDGE)
        self.statline.pack(expand=1, fill=tk.X)
        self.ttt = scr.ScrolledText(self, width=100, height=30, bg=GRAY_DD, fg=WHITE)
        logfile = os.path.join(datadir, const.LOG_FILE)
        try:
            with open(logfile) as f_in:
                for line in f_in:
                    self.ttt.insert(tk.END, line)
        except FileNotFoundError:
            pass
        self.ttt.pack()
        self.ttt.see(tk.END)
        _GB.logger = _Logger(os.path.join(datadir, const.LOG_FILE), self)
#       self.after(100, self.check_term)
        _debug("OpcLogger attivo")

#   def check_term(self):
#       "Verifica richiesta termine"
#       if _GB.stopped:
#           _debug("Termina OpcLogger")
#           _termina()
#           return
#       self.after(100, self.check_term)

    def setinfo(self, line=""):
        "Scrive informazione sulla linea di stato"
        self.statline.config(text=line)

    def showlog(self, text=""):
        "Visualizza log"
        if text:
            self.ttt.insert(tk.END, text)
        self.ttt.see(tk.END)

def main():
    "Programma per test"

    _GB.debug = True
    sim_tel = "-s" in sys.argv
    config = get_config(sim_tel)

    root = tk.Tk()
    root.configure(bg=GRAY_D)
    root.title("Test OpcLogger")
    starter = ObsInit(root, config)
#   GLOB.root.protocol("WM_DELETE_WINDOW", _stop_all)
    starter.grid()
    wg.set_position(root, (0.01, 0.01))
    root.wait_window(starter)
    _debug('fine primo passo')
    if starter.valid:
        tls = ts.tel_start(logger=None, simul=sim_tel)
        app = OpcLogger(root, starter.datadir, tls)
        app.grid()
        root.mainloop()
        sys.exit()
    _debug('secondo passo non eseguibile')


if __name__ == "__main__":
    main()