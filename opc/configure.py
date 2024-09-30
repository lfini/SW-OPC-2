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

__version__ = "1.12"
__date__ = "settembre 2024"
__author__ = "Luca Fini"

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

def store_config(config=None):
    "Salva configurazione"
    success = False
    if not config:
        config = DEFAULT_CONFIG
    if config.get("version", 0) == 0:
        msg = "Configurazione obsoleta non salvabile"
        return False, msg
    try:
        with open(const.CONFIG_PATH, "w", encoding='utf-8') as fpt:
            json.dump(config, fpt, indent=2)
    except Exception as excp:                   # pylint: disable=W0703
        msg = f'Excp: {excp}'
        success = False
    else:
        msg = 'Configurazione salvata. Avrà effetto dopo il prossimo restart'
        success = True
    return success, msg

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

class MakeConfig(tk.Frame):                            # pylint: disable=R0902,R0901
    "Crea file di configurazione"
    def __init__(self, parent):   # pylint: disable=R0915,R0914
        tk.Frame.__init__(self, parent, padx=10, pady=10)
        cur_conf = utils.get_config(check_version=False)
        tk.Label(self,
                 text="Latitudine osservatorio (rad): ").grid(row=4, column=0, sticky=tk.E)
        tk.Label(self,
                 text="Longitudine osservatorio (rad): ").grid(row=5, column=0, sticky=tk.E)
        tk.Label(self, text="").grid(row=7, column=0, columnspan=2)
        tk.Label(self,
                 text="Indirizzo IP server telescopio: ").grid(row=9, column=0, sticky=tk.E)
        tk.Label(self,
                 text="Port IP server telescopio: ").grid(row=10, column=0, sticky=tk.E)
        tk.Label(self, text="").grid(row=11, column=0, columnspan=2)
        tk.Label(self,
                 text="Timeout server telescopio: ").grid(row=11, column=0, sticky=tk.E)
        tk.Label(self, text="").grid(row=12, column=0, columnspan=2)
        tk.Label(self,
                 text="Identificatore ASCOM cupola: ").grid(row=13, column=0, sticky=tk.E)
        tk.Label(self,
                 text="Posizione parcheggio cupola (gradi): ").grid(row=14, column=0, sticky=tk.E)
        tk.Label(self,
                 text="Posizione salvata cupola (gradi): ").grid(row=15, column=0, sticky=tk.E)
        tk.Label(self,
                 text="Err. max inseguimento cupola (gradi): ").grid(row=17, column=0, sticky=tk.E)
        tk.Label(self,
                 text="Ampiezza zona critica cupola (gradi): ").grid(row=18, column=0, sticky=tk.E)
        tk.Label(self, text="").grid(row=22, column=0, columnspan=2)
        tk.Label(self,
                 text="Cartella archivio locale: ").grid(row=23, column=0, sticky=tk.E)
        tk.Label(self,
                 text="Cartella archivio remoto: ").grid(row=25, column=0, sticky=tk.E)
        tk.Label(self,
                 text="Path programma ASTAP: ").grid(row=26, column=0, sticky=tk.E)
        self.lat = tk.Entry(self, width=40)
        the_lat = cur_conf.get("lat", str(LAT_OPC_RAD))
        self.lat.insert(0, the_lat)
        self.lat.grid(row=4, column=1)
        self.lon = tk.Entry(self, width=40)
        the_lon = cur_conf.get("lon", str(LON_OPC_RAD))
        self.lon.insert(0, the_lon)
        self.lon.grid(row=5, column=1)
        self.tel_ip = tk.Entry(self, width=40)
        the_tel_ip = cur_conf.get("tel_ip", const.OPC_TEL_IP)
        self.tel_ip.insert(0, the_tel_ip)
        self.tel_ip.grid(row=9, column=1)
        self.tel_port = tk.Entry(self, width=40)
        the_tel_port = cur_conf.get("tel_port", const.OPC_TEL_PORT)
        the_tel_port = str(the_tel_port) if the_tel_port else ""
        self.tel_port.insert(0, the_tel_port)
        self.tel_port.grid(row=10, column=1)
        self.tel_tmout = tk.Entry(self, width=40)
        the_tel_tmout = cur_conf.get("tel_tmout", const.OPC_TEL_TMOUT)
        the_tel_tmout = str(the_tel_tmout) if the_tel_tmout else ""
        self.tel_tmout.insert(0, the_tel_tmout)
        self.tel_tmout.grid(row=11, column=1)

        self.dome_ascom = tk.Entry(self, width=40)
        the_dome_ascom = cur_conf.get("dome_ascom", const.DOME_ASCOM)
        self.dome_ascom.insert(0, the_dome_ascom)
        self.dome_ascom.grid(row=13, column=1)

        self.park_pos = tk.Entry(self, width=40)
        the_park_pos = cur_conf.get("park_position", const.DOME_PARK_POS)
        self.park_pos.insert(0, the_park_pos)
        self.park_pos.grid(row=14, column=1)

        self.save_pos = tk.Entry(self, width=40)
        the_save_pos = cur_conf.get("save_position", const.DOME_90)
        self.save_pos.insert(0, the_save_pos)
        self.save_pos.grid(row=15, column=1)

        self.dome_maxerr = tk.Entry(self, width=40)
        the_dome_maxerr = cur_conf.get("dome_maxerr", const.DOME_MAXERR)
        self.dome_maxerr.insert(0, the_dome_maxerr)
        self.dome_maxerr.grid(row=17, column=1)

        self.dome_crit = tk.Entry(self, width=40)
        the_dome_crit = cur_conf.get("dome_critical", const.DOME_CRITICAL)
        self.dome_crit.insert(0, the_dome_crit)
        self.dome_crit.grid(row=18, column=1)

        self.local_store = tk.Entry(self, width=40)
        loc_store = cur_conf.get("local_store", const.LOCAL_STORE)
        self.local_store.insert(0, loc_store)
        self.local_store.grid(row=23, column=1)

        self.remote_store = tk.Entry(self, width=40)
        rem_store = cur_conf.get("remote_store", const.REMOTE_DATADIR_ROOT)
        self.remote_store.insert(0, rem_store)
        self.remote_store.grid(row=25, column=1)

        self.astap_path = tk.Entry(self, width=40)
        ast_path = cur_conf.get("astap_path", const.ASTAP_PATH)
        self.astap_path.insert(0, ast_path)
        self.astap_path.grid(row=26, column=1)

        tk.Frame(self, border=2, height=3,
                 relief=tk.RIDGE).grid(row=29, column=0, columnspan=2, pady=3, sticky=tk.E+tk.W)

        self.infoline = tk.Label(self, text='', bg='white', border=2, relief=tk.SUNKEN)
        self.infoline.grid(row=30, column=0, columnspan=2, sticky='we')

    def saveme(self):                         # pylint: disable=R0914
        "Salva configurazione"
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
            msg = f"Errore formato dati: {excp}"
            success = False
        else:
            config = {"lat": rlat, "lon": rlon, "dome_ascom": dome_ascom,
                      "tel_ip": tel_ip, "tel_port": tel_port,
                      "tel_tmout": tel_tmout, "filename": const.CONFIG_PATH,
                      "dome_maxerr": dome_maxerr, "dome_critical": dome_crit,
                      "save_position": save_position,
                      "park_position": park_position,
                      "local_store": local_store,
                      "remote_store": remote_store,
                      "astap_path": astap_path,
                      "version": VERSION}
            success, msg = store_config(config)
        color = 'black' if success else 'red'
        self.infoline.config(text=msg, fg=color)

def main():
    "Lancia GUI per configurazione"
    root = tk.Tk()
    root.title(f"OPC - Configurazione parametri (CFG vers.: {VERSION})")
    if "-h" in sys.argv:
        msg = __doc__ % (__version__, __author__, __date__)
        wdg1 = ShowMsg(root, msg)
    else:
        config = utils.get_config(check_version=False)
        if "-s" in sys.argv:
            if config:
                wdg1 = ShowMsg(root, str(config))
            else:
                wdg1 = ShowMsg(root, NO_CONFIG)
        else:
            wdg1 = MakeConfig(root)
    wdg1.pack()
    tk.Button(root, text="Registra", command=wdg1.saveme).pack()
    root.mainloop()

if __name__ == "__main__":
    main()
