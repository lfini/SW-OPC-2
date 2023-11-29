'''
Varie funzioni utili
'''

import sys
import os
import time
import json
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# pylint: disable=C0413
import opc.constants as const

_CONFIG_PATH = os.path.join(const.HOMEDIR, const.CONFIG_FILENAME)

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
    return config

def store_config(config):
    "Salva configurazione nel file relativo"
    try:
        with open(config_path(), "w", encoding='utf-8') as fpt:
            json.dump(config, fpt, indent=2)
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

def set_logger(filepath, debug=False):
    'Inizializzazione logger'
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    fhndl = logging.FileHandler(filepath, mode='a', encoding='utf-8')
    fhndl.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    logger.addHandler(fhndl)
    logger.filename = filepath
    if debug:
        shndl = logging.StreamHandler()
        shndl.setLevel(logging.DEBUG)
        shndl.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(shndl)
        print(f'LOG DBG> logger attivo su file: {filepath} e su stdout', flush=True)
    return logger
