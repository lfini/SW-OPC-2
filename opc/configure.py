"""
configure.py. Vers. %s - %s. %s

Gestione file di configurazione

Uso:
      python configure.py [-s] [-h]

dove:
      -s  Mostra file di configurazione
"""

import sys
import json
import os
import re
import tkinter as tk

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# pylint: disable=C0413
from opc import utils
from opc import astro
from opc import constants as const

__version__ = "1.9"
__date__ = "ottobre 2023"
__author__ = "Luca Fini"

SHOW_CONFIG = """
  File configurazione - {filename}
             Versione - {version}

           Latitudine Osservatorio [lat]: {lat} radianti
          Longitudine Osservatorio [lon]: {lon} radianti

     Indirizzo IP server telescopio [tel_ip]: {tel_ip}
           Port server telescopio [tel_port]: {tel_port}
                    Port timeout [tel_tmout]: {tel_tmout} sec

    Identificatore ASCOM cupola [dome_ascom]: {dome_ascom}
    Posizione di park cupola [park_position]: {park_position:.1f} gradi
    Posizione cupola salvata [save_position]: {save_position:.1f} gradi
Errore max inseguimento cupola [dome_maxerr]: {dome_maxerr:.1f} gradi
Ampiezza zona critica cupola [dome_critical]: {dome_critical:.1f} gradi

      Cartella archivio locale [local_store]: {local_store}
     Cartella archivio remoto [remote_store]: {remote_store}

           Path programma ASTAP [astap_path]: {astap_path}
"""

NO_CONFIG = """
  File di configurazione mancante.
  o incompleto
"""

NOTA = """
NOTA: la configurazione ha effetto dopo un restart
"""

#  Valori di default dei parametri di configurazione

LAT_OPC_RAD = astro.OPC.lat_rad
LON_OPC_RAD = astro.OPC.lon_rad

VERSION = 7

DEFAULT_CONFIG = {"lat": LAT_OPC_RAD,
                  "lon": LON_OPC_RAD,
                  "dome_ascom": const.DOME_ASCOM,
                  "tel_ip": const.OPC_TEL_IP,
                  "tel_port": const.OPC_TEL_PORT,
                  "tel_tmout": const.OPC_TEL_TMOUT,
                  "filename": '',
                  "park_position": 1,
                  "save_position": 90,
                  "dome_maxerr": const.DOME_MAXERR,
                  "dome_critical": const.DOME_CRITICAL,
                  "version": VERSION,
                  "local_store": const.LOCAL_STORE,
                  "remote_store": const.REMOTE_DATADIR_ROOT,
                  "astap_path": None
                 }

def as_string(config):
    "riporta configurazione come stringa stampabile"
    return SHOW_CONFIG.format_map(config)

def store_config(config=None):
    "Salva configurazione"
    success = False
    if not config:
        config = DEFAULT_CONFIG
    if config.get("version", 0) == 0:
        raise RuntimeError("Configurazione non salvabile")
    try:
        with open(utils.config_path(), "w", encoding='utf-8') as fpt:
            json.dump(config, fpt, indent=2)
    except Exception as excp:                   # pylint: disable=W0703
        msg_text = "\nErrore configurazione:\n\n   "+str(excp)+"\n"
    else:
        msg_text = as_string(config)
        msg_text += NOTA
        success = True
    return success, msg_text

def simul_config(config):
    "modifica configurazione per accesso a simulatore telescopio"
    config['tel_ip'] = const.DBG_TEL_IP
    config['tel_port'] = const.DBG_TEL_PORT

PUNCT = re.compile("[^0-9.]+")
def str2rad(line):
    "Converte tre numeri (g,m,s) in radianti"
    three = [float(x) for x in PUNCT.split(line)]
    rad = astro.dms2rad(*three)
    return rad

class ShowMsg(tk.Frame):              # pylint: disable=R0901
    "Display di messaggio"
    def __init__(self, parent, msg):
        super().__init__(parent)
        lines_len = tuple(len(x) for x in msg.split("\n"))
        n_lines = len(lines_len)+1
        n_chars = max(lines_len)+2
        self.body = tk.Text(self, height=n_lines, width=n_chars,
                            padx=5, pady=5, border=3, relief=tk.RIDGE)
        self.body.insert(tk.END, msg)
        self.body.pack()
        self.status = None
        tk.Button(self, text="Chiudi", command=self._quit).pack()

    def _quit(self):
        self.master.quit()

class MakeConfig(tk.Frame):                          # pylint: disable=R0902,R0901
    "Crea file di configurazione"
    def __init__(self, parent, force=False):         # pylint: disable=R0915,R0914
        tk.Frame.__init__(self, parent, padx=10, pady=10)
        cur_conf = utils.get_config()
        self.body = tk.Frame(self)
        tk.Label(self.body,
                 text="Latitudine osservatorio (rad): ").grid(row=4, column=0, sticky=tk.E)
        tk.Label(self.body,
                 text="Longitudine osservatorio (rad): ").grid(row=5, column=0, sticky=tk.E)
        tk.Label(self.body, text="").grid(row=7, column=0, columnspan=2)
        tk.Label(self.body,
                 text="Indirizzo IP server telescopio: ").grid(row=9, column=0, sticky=tk.E)
        tk.Label(self.body,
                 text="Port IP server telescopio: ").grid(row=10, column=0, sticky=tk.E)
        tk.Label(self.body, text="").grid(row=11, column=0, columnspan=2)
        tk.Label(self.body,
                 text="Timeout server telescopio: ").grid(row=11, column=0, sticky=tk.E)
        tk.Label(self.body, text="").grid(row=12, column=0, columnspan=2)
        tk.Label(self.body,
                 text="Identificatore ASCOM cupola: ").grid(row=13, column=0, sticky=tk.E)
        tk.Label(self.body,
                 text="Posizione parcheggio cupola (gradi): ").grid(row=14, column=0, sticky=tk.E)
        tk.Label(self.body,
                 text="Posizione salvata cupola (gradi): ").grid(row=15, column=0, sticky=tk.E)
        tk.Label(self.body,
                 text="Err. max inseguimento cupola (gradi): ").grid(row=17, column=0, sticky=tk.E)
        tk.Label(self.body,
                 text="Ampiezza zona critica cupola (gradi): ").grid(row=18, column=0, sticky=tk.E)
        tk.Label(self.body, text="").grid(row=22, column=0, columnspan=2)
        tk.Label(self.body,
                 text="Cartella archivio locale: ").grid(row=23, column=0, sticky=tk.E)
        tk.Label(self.body,
                 text="Cartella archivio remoto: ").grid(row=25, column=0, sticky=tk.E)
        tk.Label(self.body,
                 text="Path programma ASTAP: ").grid(row=26, column=0, sticky=tk.E)
        self.lat = tk.Entry(self.body, width=40)
        the_lat = cur_conf.get("lat", str(LAT_OPC_RAD))
        self.lat.insert(0, the_lat)
        self.lat.grid(row=4, column=1)
        self.lon = tk.Entry(self.body, width=40)
        the_lon = cur_conf.get("lon", str(LON_OPC_RAD))
        self.lon.insert(0, the_lon)
        self.lon.grid(row=5, column=1)
        self.tel_ip = tk.Entry(self.body, width=40)
        the_tel_ip = cur_conf.get("tel_ip", const.OPC_TEL_IP)
        self.tel_ip.insert(0, the_tel_ip)
        self.tel_ip.grid(row=9, column=1)
        self.tel_port = tk.Entry(self.body, width=40)
        the_tel_port = cur_conf.get("tel_port", const.OPC_TEL_PORT)
        the_tel_port = str(the_tel_port) if the_tel_port else ""
        self.tel_port.insert(0, the_tel_port)
        self.tel_port.grid(row=10, column=1)
        self.tel_tmout = tk.Entry(self.body, width=40)
        the_tel_tmout = cur_conf.get("tel_tmout", const.OPC_TEL_TMOUT)
        the_tel_tmout = str(the_tel_tmout) if the_tel_tmout else ""
        self.tel_tmout.insert(0, the_tel_tmout)
        self.tel_tmout.grid(row=11, column=1)

        self.dome_ascom = tk.Entry(self.body, width=40)
        the_dome_ascom = cur_conf.get("dome_ascom", const.DOME_ASCOM)
        self.dome_ascom.insert(0, the_dome_ascom)
        self.dome_ascom.grid(row=13, column=1)

        self.park_pos = tk.Entry(self.body, width=40)
        the_park_pos = cur_conf.get("park_position", const.DOME_PARK_POS)
        self.park_pos.insert(0, the_park_pos)
        self.park_pos.grid(row=14, column=1)

        self.save_pos = tk.Entry(self.body, width=40)
        the_save_pos = cur_conf.get("save_position", const.DOME_90)
        self.save_pos.insert(0, the_save_pos)
        self.save_pos.grid(row=15, column=1)

        self.dome_maxerr = tk.Entry(self.body, width=40)
        the_dome_maxerr = cur_conf.get("dome_maxerr", const.DOME_MAXERR)
        self.dome_maxerr.insert(0, the_dome_maxerr)
        self.dome_maxerr.grid(row=17, column=1)

        self.dome_crit = tk.Entry(self.body, width=40)
        the_dome_crit = cur_conf.get("dome_critical", const.DOME_CRITICAL)
        self.dome_crit.insert(0, the_dome_crit)
        self.dome_crit.grid(row=18, column=1)

        self.local_store = tk.Entry(self.body, width=40)
        loc_store = cur_conf.get("local_store", const.LOCAL_STORE)
        self.local_store.insert(0, loc_store)
        self.local_store.grid(row=23, column=1)

        self.remote_store = tk.Entry(self.body, width=40)
        rem_store = cur_conf.get("remote_store", const.REMOTE_DATADIR_ROOT)
        self.remote_store.insert(0, rem_store)
        self.remote_store.grid(row=25, column=1)

        self.astap_path = tk.Entry(self.body, width=40)
        ast_path = cur_conf.get("astap_path", const.ASTAP_PATH)
        self.astap_path.insert(0, ast_path)
        self.astap_path.grid(row=26, column=1)

        tk.Frame(self.body, border=2, height=3,
                 relief=tk.RIDGE).grid(row=29, column=0, columnspan=2, pady=3, sticky=tk.E+tk.W)
        if force:
            tk.Button(self.body, text="Registra",
                      command=self.done).grid(row=30, column=1, sticky=tk.E)
        else:
            tk.Button(self.body, text="Registra",
                      command=self.done).grid(row=30, column=0, sticky=tk.W)
            tk.Button(self.body, text="Esci",
                      command=self.quit).grid(row=30, column=1, sticky=tk.E)
        self.success = False
        self.body.pack()

    def done(self):                         # pylint: disable=R0914
        "Salva configurazione ed esci"
        try:
            rlat = float(self.lat.get())
            rlon = float(self.lon.get())
            tel_ip = self.tel_ip.get()
            tel_port = int(self.tel_port.get())
            tel_tmout = float(self.tel_tmout.get())
            dome_ascom = self.dome_ascom.get()
            park_position = int(self.park_pos.get())
            dome_maxerr = float(self.dome_maxerr.get())
            dome_crit = float(self.dome_crit.get())
            save_position = float(self.save_pos.get())
            local_store = self.local_store.get()
            remote_store = self.remote_store.get()
            astap_path = self.astap_path.get()
        except Exception as excp:                         # pylint: disable=W0703
            msg_text = f"\nErrore formato dati: \n\n   {str(excp)}\n"
        else:
            config = {"lat": rlat, "lon": rlon, "dome_ascom": dome_ascom,
                      "tel_ip": tel_ip, "tel_port": tel_port,
                      "tel_tmout": tel_tmout, "filename": utils.config_path(),
                      "dome_maxerr": dome_maxerr, "dome_critical": dome_crit,
                      "save_position": save_position,
                      "park_position": park_position,
                      "local_store": local_store,
                      "remote_store": remote_store,
                      "astap_path": astap_path,
                      "version": VERSION}
            self.success, msg_text = store_config(config)
        self.body.destroy()
        msg = ShowMsg(self, msg_text)
        msg.pack()

    def quit(self):
        "Esci distruggendo il master"
        self.master.destroy()

def main():
    "Lancia GUI per configurazione"
    root = tk.Tk()
    root.title(f"OPC - Configurazione parametri (CFG vers.: {VERSION})")
    if "-h" in sys.argv:
        msg = __doc__ % (__version__, __author__, __date__)
        wdg1 = ShowMsg(root, msg)
    else:
        config = utils.get_config()
        if "-s" in sys.argv:
            if config:
                wdg1 = ShowMsg(root, as_string(config))
            else:
                wdg1 = ShowMsg(root, NO_CONFIG)
        else:
            if config:
                wdg1 = MakeConfig(root)
            else:
                wdg1 = MakeConfig(root, force=True)
    wdg1.pack()
    root.mainloop()

if __name__ == "__main__":
    main()
