'''
Varie funzioni di supporto per procedure ad OPC

Uso come script:

    python utils.py [-l]

mostra versione del package (-l:  mostra versione, data e autore)

'''

import sys
import os
import time
import json
import logging
from collections import UserDict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# pylint: disable=C0413
import opc.constants as const

# __version__ = "0.96"   # prima versione testata in cielo (Dic 2021)
# __version__ = "0.97"   # Corretto errore homer: controllo soglia con shift negativi (Gen 2022)
# __version__ = "1.00"   # Modifica algoritmo di tracking e vari bug fix.
                         # Aggiunti comandi di apertura vano

#__version__ = "1.01"   # Vari bugfix. Aggiornata procedura di setup. Aggiunto selezione
                        # versione attiva

#__version__ = "1.02"   # Aggiunte informazioni piattaforma a file di log

#__version__ = "1.03"   # Aggiunto invio file di log a www.lfini.cloud (da logger e dtracker)

__version__ = "2.0"   # Modificato tutto per unica applicazione di gestione osservazione
__date__ = "Gennaio 2024"
__author__ = 'Luca Fini'

_CONFIG_PATH = os.path.join(const.HOMEDIR, const.CONFIG_FILENAME)

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

def get_version(long=False):
    "recupera versione, come stringa"
    if long:
        return f"{__version__} - {__author__}, {__date__}"
    return __version__

class Config(UserDict):
    'modified dict con configurazione'
    def __str__(self):
        return SHOW_CONFIG.format_map(self)

def config_path():
    'riporta il path completo del file di configurazione'
    return _CONFIG_PATH

def get_config(simul=False):
    "Legge il file di configurazione"
    fname = _CONFIG_PATH
    try:
        with open(fname, encoding='utf-8') as fpt:
            config = json.load(fpt)
    except FileNotFoundError:
        config = {}
    if simul:
        config['tel_ip'] = const.DBG_TEL_IP
        config['tel_port'] = const.DBG_TEL_PORT
    return Config(config)

def store_config(config):
    "Salva configurazione nel file relativo"
    try:
        with open(config_path(), "w", encoding='utf-8') as fpt:
            json.dump(config.data, fpt, indent=2)
    except Exception as excp:                   # pylint: disable=W0703
        msg_text = "\nErrore configurazione:\n\n   "+str(excp)+"\n"
    else:
        msg_text = ''
    return msg_text

def make_logname(logtag, onlydir=False, ext='log'):
    'genera nome per file di log'
    config = get_config()
    ldir = os.path.abspath(os.path.join(config['local_store'], const.LOG_SUBDIR))
    if not os.path.isdir(ldir):
        os.makedirs(ldir)
    if onlydir:
        return ldir
    lnam = time.strftime("%Y-%m-%d-")+logtag+'.'+ext
    return os.path.join(ldir, lnam)

def set_logger(filepath):
    'Inizializzazione logger'
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    fhndl = logging.FileHandler(filepath, mode='a', encoding='utf-8')
    fhndl.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    logger.addHandler(fhndl)
    logger.filename = filepath
    return logger

if __name__ == "__main__":
    if "-l" in sys.argv:
        print(get_version(long=True))
    else:
        print(get_version())
