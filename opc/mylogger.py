'''
mylogger.py - Logger centralizzato per tutte le applicazioni OPC

Uso per test:

    python mylogger.py
'''

import sys
import os
import time
from datetime import datetime
from threading import Thread
from queue import Queue

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from opc.utils import make_logname        # pylint: disable=C0413

_DEBUG = False    # set to True to debug quque management

########################### server code begins
_STARTCLIENT = 1
_SHUTDOWN = 2
_INFO = 3
_ERROR = 4

_LOGGER_ID = 'Logger'

_LEVELS = {_INFO: 'INFO', _ERROR: 'ERROR'}

class _GB:            #pylint: disable=R0903
    queue = None
    process = None
    logfile = None
    shut = False

def _open(filetag):
    'Apre log file'
    logname = make_logname(filetag)
    _GB.logfile = open(logname, 'a', encoding='utf8')     #pylint: disable=R1732

def _log(level, ident, msg):
    'scrive linea di log'
    line = f'{level}: {ident} - {msg}'
    tstamp = datetime.now().isoformat(sep=' ', timespec='milliseconds')
    print(tstamp, line, file=_GB.logfile)

def _listener():
    'thread che riceve i messaggi'
    _log(_LEVELS.get(_INFO), _LOGGER_ID, 'Logger starting *************************************')
    while True:
        cmd, ident, msg = _GB.queue.get()
        if _DEBUG:
            print('DBG> Queue rcv:', (cmd, ident, msg))
        if cmd == _SHUTDOWN:
            _log(_LEVELS.get(_INFO), _LOGGER_ID, 'Shutdown request')
            break
        if cmd == _STARTCLIENT:
            _log(_LEVELS.get(_INFO), _LOGGER_ID,  f'New client: {ident}')
            continue
        level = _LEVELS.get(cmd)
        if level is None:
            level = _LEVELS.get(_ERROR)
            msg = f'Protocol error [{(cmd, msg)}]'
        _log(level, ident, msg)
    _log(_LEVELS.get(_INFO), _LOGGER_ID, f'thread {_GB.process.native_id} terminated')
    _GB.logfile.close()
########################### server code ends

########################### client code begins
def _send(obj):
    'Invia obj alla coda'
    if _DEBUG:
        print('DBG> Queue snd:', obj)
    _GB.queue.put(obj)

class _GLogger:
    'Client per logger centralizzato'
    def __init__(self, ident, debug):
        if _GB.shut:
            raise RuntimeError('Logger chiuso')
        self.ident = ident
        self.debug_on = debug
        _send((_STARTCLIENT, ident, ''))

    def info(self, msg):
        'Log an info message'
        if _GB.shut:
            raise RuntimeError('Logger chiuso')
        if self.debug_on:
            print('DBG>', f'INFO: {self.ident} - {msg}')
        _send((_INFO, self.ident, msg))

    def error(self, msg):
        'Log an error message'
        if _GB.shut:
            raise RuntimeError('Logger chiuso')
        if self.debug_on:
            print('DBG>', f'ERROR: {self.ident} - {msg}')
        _send((_ERROR, self.ident, msg))

    def logname(self):                     #pylint: disable=R0201
        'riporta nome del file di log'
        if _GB.shut:
            raise RuntimeError('Logger chiuso')
        return _GB.logfile.name

    def debug(self, enable=True):
        'enable/disable modo debug'
        self.debug_on = enable

def get_logger(ident, debug=False, filetag='eng'):
    'accesso al logger'
    if _GB.shut:
        raise RuntimeError('Logger chiuso')
    if _GB.process is None:
        _open(filetag)
        _GB.queue = Queue()
        _GB.process = Thread(target=_listener)
        _GB.process.start()
        count = 10
        while not _GB.process.is_alive():
            time.sleep(0.1)
            count -= 1
        if not _GB.process.is_alive():
            return None
        msg =  f'logger thread {_GB.process.native_id} running'
        if debug:
            print('DBG>', f'INFO: _LOGGER_ID - {msg}')
        _log(_LEVELS.get(_INFO), _LOGGER_ID,  msg)

    return _GLogger(ident, debug)

def shut_logger():
    'Termina logger'
    _GB.shut = True
    _send((_SHUTDOWN, '', ''))
    _GB.process.join()
########################### client ends

def test():
    'codice di test'
    debug = '-d' in sys.argv
    log1 = get_logger('Test1', debug, filetag='test')
    log2 = get_logger('Test2', debug)
    print('File di log:', log1.logname())

    for i in range(10):
        time.sleep(1)
        log1.info(f'Logger 1 - step {i}')
        time.sleep(1)
        log2.error(f'Logger 2 - step {i}')
    shut_logger()

if __name__ == '__main__':
    test()
