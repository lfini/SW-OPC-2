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
import subprocess
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

#__version__ = "2.0"   # Modificato tutto per unica applicazione di gestione osservazione
#__version__ = "2.1"    # Corretto bug che impediva di uscire dal modo "slave" di DTracker

__version__ = "2.2"    # Aggiubnte funzioni per lock

__date__ = "Settembre 2024"
__author__ = 'Luca Fini'

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

LOCK_TEMPLATE = '.opc_lock_{}'
LOCK_START = '.opc_lock_'

HOMEDIR = os.path.expanduser('~')

def crealock(tag):
    'crea directory come lock'
    lockdir = os.path.join(HOMEDIR, LOCK_TEMPLATE.format(tag))
    try:
        os.mkdir(lockdir)
    except FileExistsError:
        return False
    return True

def _remlock_all():
    'rimuove tutte le directory lock'
    for fname in os.listdir(HOMEDIR):
        if fname.startswith(LOCK_START):
            lockdir = os.path.join(HOMEDIR, fname)
            os.rmdir(lockdir)

def remlock(tag):
    'rimuove lock directory'
    if tag == '*':
        _remlock_all()
        return
    lockdir = os.path.join(HOMEDIR, LOCK_TEMPLATE.format(tag))
    os.rmdir(lockdir)

def get_version(long=False):
    "recupera versione, come stringa"
    if long:
        return f"{__version__} - {__author__}, {__date__}"
    return __version__

class Config(UserDict):
    'modified dict con configurazione'
    def __str__(self):
        return SHOW_CONFIG.format_map(self)

def get_config(check_version=True, simul=False):
    "Legge il file di configurazione"
    fname = const.CONFIG_PATH
    try:
        with open(fname, encoding='utf-8') as fpt:
            config = json.load(fpt)
    except FileNotFoundError:
        config = {}
    if simul:
        config['tel_ip'] = const.DBG_TEL_IP
        config['tel_port'] = const.DBG_TEL_PORT

    if check_version and config['version'] != const.CONFIG_VERSION:
        raise RuntimeError('Configuration to be updated ' \
                           f'(required: {config["version"]}, got: {const.CONFIG_VERSION})')
    return Config(config)

def store_config(config):
    "Salva configurazione nel file relativo"
    try:
        with open(const.CONFIG_PATH, "w", encoding='utf-8') as fpt:
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

class ExecPythonScript:                 #pylint: disable=R0903
    'Lancia programma python dato'
    def __init__(self, script_path, options=None, bg=True):
        if sys.platform == 'linux':
            pythonpath = sys.executable
            amp = ' &' if bg else ''
        elif sys.platform == 'win32':
            pythonpath = sys.executable
            if bg:
                pythonpath = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
                amp = ''
        else:
            raise RuntimeError(f'platform {sys.platform} unsupported')
        opt = ' '.join(str(x) for x in options)
        self.command = f'{pythonpath} {script_path} {opt} {amp}'
        self.process = None

    def start(self):
        'esegue comando dato'
        self.process = subprocess.run(self.command, shell=True, check=False)#, capture_output=True)

def installed_versions():
    'genera lista delle versioni installate'
    dlist = [x for x in os.listdir(const.INSTALLROOT) if x.startswith('opc-')]
    dlist.sort()
    return dlist

if __name__ == "__main__":
    if "-l" in sys.argv:
        print(get_version(long=True))
    else:
        print(get_version())
