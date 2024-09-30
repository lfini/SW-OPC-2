"""
Costanti per procedure di supporto osservazioni ad OPC
"""

import sys
import os

CONFIG_VERSION = 7

REMOTE_DATADIR_ROOT = "Dati Oss. Chianti" # nome directory root per dati repository remoto
LOCAL_DATADIR_ROOT = "opc-data"           # nome directory root per dati locale
LOG_FILE = "Log_Sessione.txt"             # Nome file di log del logger generale
LOG_SUBDIR = "Logs"                       # Nome sottodirectory per i file di log delle applicazioni
LIST_FILE = "filelist.txt"                # Nome file per lista con checksum
INFO_FILE = "info.json"                   # Nome file per dati inziali

# Parametri telescopio
DBG_TEL_IP = "127.0.0.1"
DBG_TEL_PORT = 9753

OPC_TEL_IP = "192.168.0.67"
OPC_TEL_PORT = 9999
OPC_TEL_TMOUT = 0.8

# ambiente
HOMEDIR = os.path.expanduser("~")
INSTALLROOT = os.path.join(HOMEDIR, "opc-soft")

if sys.platform == "win32":
    DESKTOP = os.path.join(HOMEDIR, "Desktop")
    ASTAP_PATH = 'C:\\Program Files\\astap\\astap.exe'
else:
    DESKTOP = HOMEDIR
    ASTAP_PATH = '/usr/local/bin/astap'

# Parametri per cupola

DOME_PARK_POS = 1
DOME_ASCOM = "OCS.Dome"
DOME_MAXERR = 0.5
DOME_CRITICAL = 4.0
DOME_90  = 90

# nomi file di lavoro

HOMER_COEFF_PATH = os.path.join(HOMEDIR, '.homer_coeff')
CONFIG_PATH = os.path.join(HOMEDIR, ".opc_config")
LOCAL_STORE = os.path.join(DESKTOP, LOCAL_DATADIR_ROOT)
