'''
domelogger.py - supporto per creazione logfile in modo standalone

                Nell'ambiente OPC si usa preferibilmente mylogger
'''

import os
from datetime import datetime

THISDIR = os.path.abspath(os.path.dirname(__file__))

LOGFILENAME = os.path.join(THISDIR, 'logdome.log')
LOGFILEBACK = os.path.join(THISDIR, 'logdome.bck')
LOGSIZEMAX = 10000000

class _GB:            #pylint: disable=R0903
    dc_debug = False
    logfile = None
    nclients = 0
    shut = False

def _dc_log(ident, level, line):
    'Record logs'
    if _GB.shut:
        raise RuntimeError('logger is terminated')
    if _GB.logfile:
        tstamp = datetime.now().isoformat(sep=' ', timespec='milliseconds')
        print(tstamp, f'{level}: {ident} -', line, file=_GB.logfile)
    if _GB.dc_debug:
        print('DBG>', f'{level}: {ident} -', line, flush=True)

class _GLogger:                # pylint: disable=R0903
    def __init__(self, ident):
        self.ident = ident

class _GLogger:
    'Client per logger centralizzato'
    def __init__(self, ident):
        self.ident = ident
        self.info('logger started')

    def info(self, msg):
        'Log an info message'
        _dc_log(self.ident, 'INFO', msg)

    def error(self, msg):
        'Log an error message'
        _dc_log(self.ident, 'ERROR', msg)

def get_logger(ident, debug):
    'crea un nuovo logger'
    _GB.dc_debug = debug
    if not _GB.logfile:
        if os.path.exists(LOGFILENAME):
            logsize = os.stat(LOGFILENAME).st_size
            if logsize > LOGSIZEMAX:
                os.replace(LOGFILENAME, LOGFILEBACK)
        _GB.logfile = open(LOGFILENAME, 'a', encoding='utf8')  # pylint: disable=R1732
        _dc_log('INFO', 'Logger', f'logging to file: {LOGFILENAME}')
    return _GLogger(ident)

def shut_logger():
    'terminate logger'
    _GB.shut = True
    _GB.logfile.close()
