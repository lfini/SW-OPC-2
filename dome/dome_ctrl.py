'''
dome_ctrl.py - Thread based program for K8055 based Gambato dome controller
               and alpaca server

Test mode:

    python dome_ctrl.py [-a] [-d] [-h] [-k] [-s]

where:

    [-a]   enable Alpaca server function
    [-d]   set debug mode for dome controller
    [-h]   print this help page and exit
    [-k]   use K8055 simulator
    [-s]   use telescope simulator
'''

####################################################################################
# Support for slave mode
#
# In order to allow the operation in slave mode, an external module must be provided
# with name: "tel_sampler.py"

# The module must implement a function:

# tel_start(logger=None, simul=False) - called once at beginning of operations to
#                                       enable the communication with the telescope.
#        Parameters:
#              logger - if provided, must be an object providing two methods:
#                       logger.info(msg:str) and logger.error(msg:str)
#              simul  - if True, enables telescope simulation mode for offline
#                       testing.
#            Both arguments can be ignored in the implementation

#        Returns:
#            TelSampler : object providing the following two methods

#               TelSampler.az_from_tel()  - called periodically (typically a few
#                  times per second). It must return the azimuth required to the
#                  dome to be in front of the telescope. If azimuth cannot be computed,
#                  the returned value is set to -1.0
#
#               TelSampler.tel_stop() - called once, at the end of operations
#                  to stop the communication with the telescope

# If the module is available in the import path it will be imported and used,
# otherwise, the controller will not support the slave mode
####################################################################################

#pylint: disable=C0302

import sys
import os
import time
from datetime import datetime
import json
from threading import Thread, Lock

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

try:
    import readline          #pylint: disable=W0611
except ModuleNotFoundError:
    pass

from dome_tools import *     #pylint: disable=W0401,W0614

from k8055_simulator import K8055Simulator

THIS_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(THIS_DIR, "..")))

# pylint: disable=C0413
try:                               # Try importing local tel_sampler
    import tel_sampler as ts
except ImportError:
    TEL_SAMPLER = False
else:
    TEL_SAMPLER = True

if not TEL_SAMPLER:
    try:                                    # Try importing tel_sampler from opc environment
        from opc import tel_sampler as ts
    except ImportError:
        TEL_SAMPLER = False
    else:
        TEL_SAMPLER = True

DLL_PATH = os.path.join(THIS_DIR, 'K8055D.dll')

THISDIR = os.path.abspath(os.path.dirname(__file__))

LOGFILENAME = os.path.join(THISDIR, 'logdome.log')
LOGFILEBACK = os.path.join(THISDIR, 'logdome.bck')
LOGSIZEMAX = 10000000

if sys.platform == 'linux':
    import pyk8055
    HANDLE = pyk8055.k8055()
elif sys.platform == 'win32':
    from ctypes import cdll
    HANDLE = cdll.LoadLibrary(DLL_PATH)
else:
    raise RuntimeError(f'Unsupported platform: {sys.platform}')

__version__ = '1.4'
__author__ = 'Luca Fini'
__date__ = 'March 2023'

# pylint: disable=C0413

DEBUG_LOCK = False    # set to true to enable deadlock debugging mode

_PULSE_TIME = 1       # Duration of pulsed relais for open/close shutter (sec)
_SAMPLE_PERIOD = 1    # period of position logging

_ALPACA_THREAD_ERROR = 'Dome - Alpaca server thread did not start'
_ALREADY_RUNNING = 'Dome - server is running'
_CANT_EXECUTE = 'Dome - cannot execute command'
_CANT_SAVE_STATUS = 'Dome - cannot save dome status'
_DOME_THREAD_ERROR = 'Dome - controller thread did not start'
_NA = 'N.A.'
_NO_DOME_DATA = 'Dome - calibration data file missing'
_NO_ERROR = ''
_TEL_OK = 'Dome - azimuth from tel. OK'
_UNCONNECTED = 'Dome - server not connected'
_UNCONFIGURED = 'Dome - configuration parameter missing'
_UNIMPLEMENTED = 'Dome - function not yet implemented'
_VALUE_ERROR = 'Dome - value error'

_N_SWITCHES = 4

_CANT_SLAVE = 0     # Slave mode unsupported
_NO_AZIMUTH = 1     # Azimuth not available
_TEL_OK = 2


_NAN = float('nan')

_MOVE_HELP = '''
Comandi:
    ?        - Read status
    >        - Start moving clockwise
    <        - Start moving counterclockwise
    s        - Stop
    +/++     - Do a short/medium step clockwise
    -/--     - Do a short/medium step counterclockwise
    sl  azh  - Slew to azimuth

    q        - Quit
'''

_MORE_HELP = '''
    ??       - Read extended status
    f?       - Get path of log file
    i?       - Get version info
    p?       - Get dome parameters
    r?       - Get relay status
    s?       - Get shutter status

    os       - Open shutter
    cs       - Close shutter
    c  n     - Close relay N (0..3)
    o  n     - Open relay N (0..3)

    sv       - Set/unset slave mode

    sp       - Set current azimuth as park position
    p        - Go to park
    h        - Find home

    sy  azh  - sync to given azimut

    stress   - Launch extensive stress test to verify repeatability
               and precisione. It requres several minutes to complete
'''

####                                           Alpaca related constants
_ALP_DOME_DESCR = 'OPC dome Alpaca server'
_ALP_DOME_NAME = 'OPC dome'

_ALP_SWITCH_DESCR = 'Relais bank Alpaca server [numbers: 0..3]'
_ALP_SWITCH_NAME = 'OPC rele'

_ALP_IF_VERS = '1'

_ALP_TEST_PORT = 7777

UNSIGNED_32 = 2**32

_ALP_SUCCESS = (0, '')
_ALP_UNIMPL_PROP = (1024, 'Property/method not implemented: ')
_ALP_INVALID_VALUE = (1025, 'Invalid value: ')
_ALP_VALUE_NOT_SET = (1026, 'Value not set: ')
_ALP_NOT_CONNECTED = (1031, 'Device not connected: ')
_ALP_INVALID_WHILE_PARKED = (1032, 'Invalid while parked: ')
_ALP_INVALID_WHILE_SLAVED = (1033, 'Invalid while slaved: ')
_ALP_INVALID_OPERATION = (1035, 'Invalid operation: ')
_ALP_UNSUPPORTED_DEVICE = (20, 'Unsupported device: ')
_ALP_UNIMPL_ACTION = (1036, 'Action not implemented: ')
_ALP_TBI = (2000, 'Action to be implemented: ')
_ALP_DOME_SPECIFIC = (2010, 'Dome internal error: ')

_ALP_CLIENT_ID = 'ClientID'
_ALP_CLIENT_TRANS_ID = 'ClientTransactionID'
_ALP_ERROR_NUMBER = 'ErrorNumber'
_ALP_ERROR_MESSAGE = 'ErrorMessage'
_ALP_SERVER_TRANS_ID = 'ServerTransactionID'
_ALP_VALUE = 'Value'

_ALP_AZIMUTH = 'Azimuth'
_ALP_CONNECTED = 'Connected'
_ALP_SLAVED = 'Slaved'

IDLE = 0          # Dome moving status
STOPPING = 1
AIMING = 2
STEPPING = 3
RUNNING = 4

class _GB:                  # pylint: disable=R0903
    'Global variables'
                         #### Housekeeping
    alpaca = None        # Thread running Alpaca server
    al_server = None     # HTTPserver for Alpaca
    al_transid = 1       # Alpaca server transaction id
    dc_debug = False     # Debug mode for dome controller
    dctrl = None
    logger = None        # Main logger
    handle = HANDLE
    data_file = ''       # name of dome data file
    ipport = 0           # IP port for Alpaca server
    loop = True
    server = None        # Serving Thread
    tsample = 0          # Position sampling time for debug
    movstat = IDLE       # Status of movement: IDLE(0): idle,
                         #                     STOPPING(1): stopping,
                         #                     AIMING(2): aiming at target,
                         #                     STEPPING(3): doing a step
                         #                     RUNNING(4): running free
    dome_lock = Lock()   # Protect dome data
    cmd_lock = Lock()    # Serialize commands
                         # Telescope related variables
    canslave = False     # if True, the dome supports slave mode
    isslave = False      # if True, the dome is slaved to telescope
    telstat = 0          # telescope status: 0: cannot slave, 1: cannot compute azimuth, 2: ok
    telsave = 0          # Last telescope status
                         #### Dome status
    direct = 0           # Moving status (0: idle, 4: clockwise, 3: counterclockwise)
    stopcn = (-1)        # Counts after a stop command
    domeaz = 0           # Current dome azimuth (encoder units)
    saveaz = 0           # Remeber dome azimuth after start
    targetaz = 0         # Target azimut (encoder units)
    ptable = []          # Pulse duration lookup table
    switch_stat = [0, 0, # 0: open, 1: closed
                   0, 0]
    idletime = 0         # fraction of loop time remaining idle
                         #### Dome data and parameters
    n360 = 0             # Steps per complete turn
    n180 = 0             # Steps per half turn
    toenc = 1            # Converts degrees to encoder steps
    todeg = 1            # Converts encoder steps to degrees
    nstop = None         # Number of deceleration steps
    tshort = None        # Default duration of pulse for step movement
    tstop = None         # Deceleration time (seconds)
    maxerr = 0           # Max position error (encoder units)
    shuttime = None      # Duration of shutter relais closed
    shutstat = 0         # Shutter status (True: it is open)
    hoffset = None       # Offest zero.position-home.position (encoder steps)
    parkaz = None        # Park position (encoder steps)
    tpoll = None         # Main loop polling time (seconds)

    tel_sampler = None   # Telescope sampler

class _AFTER:                  # pylint: disable=R0903
    'support for timers'
    lock = Lock()
    queue = []

class _SWITCH:                  # pylint: disable=R0903
    'info about switches'
    names = ['SW-1', 'SW-2', 'SW-3', 'SW-4']
    descr = ['', '', '', '']

class _STAT:                  # pylint: disable=R0903
    'dome status'
    connected = False     # connection status
    domeaz = None         # Current azimuth (degrees), 0: north
    direct = None         # Movement direction:  0: idle
                          #                      1: clockwise
                          #                     -1: counterclockwise
    idletime = None       # fraction of loop time waiting idle
    isslave = None        # if True the dome is slaved to telescope
    movstat = None        # Movment status:
    targetaz = -1         # Current target azimnuth (degrees)

class _NoLogger:
    'dummy logger'
    def info(self, _unused):
        'do not record a log info'
    def error(self, _unused):
        'do not record a log error'

class _Logger:
    'standalone logger'
    def __init__(self, debug):
        self.debug = debug
        if os.path.exists(LOGFILENAME):
            logsize = os.stat(LOGFILENAME).st_size
            if logsize > LOGSIZEMAX:
                os.replace(LOGFILENAME, LOGFILEBACK)
        self.logfile = open(LOGFILENAME, 'a', encoding='utf8')  # pylint: disable=R1732
        self.info(f'Logger - logging to file: {LOGFILENAME}')

    def info(self, msg):
        'record a log info'
        if self.logfile:
            tstamp = datetime.now().isoformat(sep=' ', timespec='milliseconds')
            print(tstamp, 'Info:', msg, file=self.logfile)
        if self.debug:
            print('DBG>', 'Info:', msg)

    def error(self, msg):
        'record a log error'
        if self.logfile:
            tstamp = datetime.now().isoformat(sep=' ', timespec='milliseconds')
            print(tstamp, 'Error:', msg, file=self.logfile)
        if self.debug:
            print('DBG>', 'Error:', msg)

def _sample(cnt):
    'Record periodic status'
    _GB.logger.info(f'Dome - azh: {_GB.domeaz}, tgt: {_GB.targetaz}, cnt: {cnt} '\
                    f'dir: {_GB.direct}, stat: {_GB.movstat}, '\
                    f'slave: {_GB.isslave}, tel: {_GB.telstat}')

def _after(delay, func):
    'timer for action'
    firetime = time.time()+delay
    with _AFTER.lock:
        _AFTER.queue.append((firetime, func))
        _AFTER.queue.sort(key=lambda x: x[0])

def _exec_timers(now):
    'get next timed function'
    while True:
        with _AFTER.lock:
            func = None
            if _AFTER.queue:
                ftime, func = _AFTER.queue[0]
                if ftime <= now:
                    _AFTER.queue.pop(0)
                else:
                    break
            else:
                break
        if func:
            func()

def _ang_dist(ang1, ang2):
    'compute angular distance ang1-ang2 (in unità encoder)'
    dist = ang1-ang2
    if dist > _GB.n180:
        dist -= _GB.n360
    elif dist < -_GB.n180:
        dist += _GB.n360
    return dist

def _start_lk(direct, tstep=None):
    'Start movement (to protect with lock)'
    _GB.logger.info(f'Dome - _start_lk({direct}, {tstep})')
    if not _GB.handle:
        return _UNCONNECTED
    if _GB.movstat != IDLE:
        _GB.logger.error(_CANT_EXECUTE)
        return _CANT_EXECUTE
    safe_clear_counter(_GB.handle)
    _GB.saveaz = _GB.domeaz
    _GB.direct = direct
    _GB.handle.SetDigitalChannel(_GB.direct)
    if tstep is None:
        _GB.movstat = AIMING
    elif tstep < 0.0:
        _GB.movstat = RUNNING
    else:
        _after(tstep, _end_step)
        _GB.movstat = STEPPING
    return _NO_ERROR


def _stop_lk(reason):
    'stop movement (to protect with lock)'
    _GB.logger.info(f'Dome - _stop_lk({reason})')
    _GB.handle.ClearDigitalChannel(_GB.direct)         # stop the motor
    _GB.stopcn = _GB.handle.ReadCounter(ENCODER)       # get current count
    _GB.movstat = STOPPING
    _after(_GB.tsafe, _check_stopped)

def _check_stopped():
    'detect motion end'
    with _GB.dome_lock:
        cnt = _GB.handle.ReadCounter(ENCODER)
        _GB.logger.info(f'Dome - _check_stopped. cnt={cnt}')
        if cnt == _GB.stopcn:
            if _GB.direct == LEFT_MOVE:
                _GB.domeaz = int((_GB.saveaz-cnt)%_GB.n360)
            elif _GB.direct == RIGHT_MOVE:
                _GB.domeaz = int((_GB.saveaz+cnt)%_GB.n360)
            safe_clear_counter(_GB.handle)
            _GB.saveaz = _GB.domeaz
            _GB.direct = 0
            _GB.movstat = IDLE
            _GB.stopcn = -1
            _GB.logger.info('Dome - _check_stopped: stop detected')
            return
        _GB.stopcn = cnt
        _after(_GB.tsafe, _check_stopped)

def _end_step():
    'End of time for pulse movement'
    with _GB.dome_lock:
        if _GB.stopcn < 0:
            _stop_lk('_end_step')

def _dome_loop():                          #pylint: disable=R0912,R0915
    'Dome status update loop (executed as Thread)'
    _GB.logger.info('Dome - control loop starting')
    pollsec = _GB.tpoll
    _GB.handle.ClearAllDigital()     # set a known status
    while _GB.loop:
        tstart = time.time()
        if _GB.handle:
            _exec_timers(tstart)
            with _GB.dome_lock:
                cnt = _GB.handle.ReadCounter(ENCODER)                # update current position
                if _GB.direct == RIGHT_MOVE:
                    _GB.domeaz = int((_GB.saveaz+cnt)%_GB.n360)
                elif _GB.direct == LEFT_MOVE:
                    _GB.domeaz = int((_GB.saveaz-cnt)%_GB.n360)
                if tstart > _GB.tsample and _GB.movstat != IDLE:    # periodically log
                                                                     # current position
                    _sample(cnt)
                    _GB.tsample = tstart+_SAMPLE_PERIOD
                if _GB.canslave:
                    azh = _GB.tel_sampler.az_from_tel()
                    if azh < 0.0:
                        _GB.telstat = _NO_AZIMUTH
                    else:
                        _GB.telstat = _TEL_OK
                else:
                    azh = -1
                if _GB.isslave:                                     # manage slave mode
                    if azh < 0.0:
                        _GB.targetaz = -1
                    else:
                        _GB.targetaz = _to_encoder(azh)
                if _GB.telstat != _GB.telsave:
                    _GB.logger.info(f'Dome - tel. status now: {_GB.telstat}')
                    _GB.telsave = _GB.telstat
                if _GB.targetaz < 0:
                    dst, adst = 0.0, 0.0
                else:
                    dst = _ang_dist(_GB.targetaz, _GB.domeaz)
                    adst=abs(dst)
                if _GB.movstat == IDLE:
                    if adst > _GB.nstop:
                        direct = RIGHT_MOVE if dst > 0 else LEFT_MOVE
                        _GB.logger.info(f'Dome - Start movement (dist={dst})')
                        _start_lk(direct)
                    elif adst > _GB.maxerr:
                        direct = RIGHT_MOVE if dst > 0 else LEFT_MOVE
                        pls = _GB.ptable[adst]
                        _GB.logger.info('Dome - Stepping to final position '
                                        f'(dist={dst}, pulse={pls:.2f})')
                        _start_lk(direct, tstep=pls)
                    else:
                        _GB.targetaz = -1
                elif _GB.movstat == AIMING:
                    if adst < _GB.nstop:
                        _stop_lk('Approaching target')
                    else:
                        direct = RIGHT_MOVE if dst > 0 else LEFT_MOVE
                        if direct != _GB.direct:
                            _stop_lk('Wrong direction')
        nextpoll = pollsec - (time.time()-tstart)
        _GB.idletime = nextpoll/pollsec
        if nextpoll>0:
            time.sleep(nextpoll)
    _GB.logger.info('Dome - control loop terminated')

###### API support functions

def _to_encoder(azh):
    'Convert degrees to encoder units'
    return int(azh%360*_GB.toenc+0.5)

def _start_pulse(n_rele, p_time):
    'Start a pulsed rele'
    _GB.logger.info(f'Dome - _start_pulse({n_rele}, {p_time})')
    if not _GB.handle:
        return _UNCONNECTED
    _GB.handle.SetDigitalChannel(n_rele)
    _after(p_time, lambda: _end_pulse(n_rele))
    return _NO_ERROR

def _end_pulse(n_rele):
    'close relais after pulse period'
    _GB.logger.info(f'Dome - _end_pulse({n_rele})')
    _GB.handle.ClearDigitalChannel(n_rele)

def _slew_to(val):
    'Go to azimuth (in encoder units)'
    _GB.logger.info(f'Dome - _slew_to({val})')
    if not _GB.handle:
        return _UNCONNECTED
    with _GB.dome_lock:
        if _GB.isslave or _GB.movstat != IDLE:
            _GB.logger.error(_CANT_EXECUTE)
            return _CANT_EXECUTE
        _GB.targetaz = val
    return _NO_ERROR

def _set_shut_stat(val):
    'Set shutter status open(1)/closed(0)'
    _GB.shutstat = val

def _log_status():
    'Print status variables'
    _GB.logger.info('Dome - current status')
    _GB.logger.info(f'  domeaz: {_GB.domeaz}')
    _GB.logger.info(f'  hoffset: {_GB.hoffset}')
    _GB.logger.info(f'  maxerr: {_GB.maxerr}')
    _GB.logger.info(f'  n180: {_GB.n180}')
    _GB.logger.info(f'  n360: {_GB.n360}')
    _GB.logger.info(f'  nstart: {_GB.nstart}')
    _GB.logger.info(f'  nstop: {_GB.nstop}')
    _GB.logger.info(f'  parkaz: {_GB.parkaz}')
    _GB.logger.info(f'  ptable: {_GB.ptable}')
    _GB.logger.info(f'  shuttime: {_GB.shuttime}')
    _GB.logger.info(f'  t360: {_GB.t360}')
    _GB.logger.info(f'  targetaz: {_GB.targetaz}')
    _GB.logger.info(f'  todeg: {_GB.todeg}')
    _GB.logger.info(f'  toenc: {_GB.toenc}')
    _GB.logger.info(f'  tpoll: {_GB.tpoll}')
    _GB.logger.info(f'  tsafe: {_GB.tsafe}')
    _GB.logger.info(f'  tshort: {_GB.tshort}')
    _GB.logger.info(f'  tstart: {_GB.tstart}')
    _GB.logger.info(f'  tstop: {_GB.tstop}')
    _GB.logger.info(f'  vmax: {_GB.vmax}')

##################################  Alpaca server section  ############################

# The alpaca server implements the Dome Alpaca API and the Switch alpaca API

# Supported URLs for GET query

# http://ip.addr:7777/api/v1/dome/0/connected
# http://ip.addr:7777/api/v1/switch/0/connected


def _alp_atpark(handle, params):
    'get IsAtPark property'
    ext_stat = _GB.dctrl.get_ext_status()
    _alp_reply_200(handle, params, ext_stat['atpark'])

def _alp_getazimuth(handle, params):
    'get Azimuth property'
    dome_stat = _GB.dctrl.get_status()
    _alp_reply_200(handle, params, dome_stat.domeaz)

def _alp_unsupported_get(handle, params, command):
    'return unsupported get command error'
    err = (_ALP_UNIMPL_PROP[0], _ALP_UNIMPL_PROP[1]+command)
    _alp_reply_200(handle, params, err=err)

def _alp_unsupported_put(handle, data, command):
    'return unsupported get command error'
    err = (_ALP_UNIMPL_ACTION[0], _ALP_UNIMPL_ACTION[1]+command)
    _alp_reply_200(handle, data, err=err)

def _alp_retvalue(handle, params, value):
    'returns a value'
    _alp_reply_200(handle, params, value=value)

def _alp_getconnected(handle, params):
    'return connection status'
    dome_stat = _GB.dctrl.get_status()
    _alp_reply_200(handle, params, value=dome_stat.connected)

def _alp_driverinfo(handle, params):
    'Return info on driver'
    info = _GB.dctrl.get_info()
    _alp_reply_200(handle, params, value=info)

def _alp_driverversion(handle, params):
    'Return info on driver'
    info = _GB.dctrl.get_version()
    _alp_reply_200(handle, params, value=info)

def _alp_shutterstatus(handle, params):
    'return shutter status'
    stat = _GB.dctrl.get_shutter()
    _alp_reply_200(handle, params, value=stat)

def _alp_slavestatus(handle, params):
    'return slave status'
    stat = _GB.isslave
    _alp_reply_200(handle, params, value=stat)

def _alp_slewstatus(handle, params):
    'return slewing status'
    dome_stat = _GB.dctrl.get_status()
    _alp_reply_200(handle, params, value=dome_stat.direct != 0)

def _alp_get_dome_actions(handle, params):
    'returns list of supported actions'
    value = list(_DOME_GET_ACTS.keys()) + list(_DOME_PUT_ACTS.keys())
    _alp_reply_200(handle, params, value)

#   COMMON GET ACTIONS   command      function
_DOME_GET_ACTS = {'connected': _alp_getconnected,
                  'description': lambda x, y: _alp_retvalue(x, y, _ALP_DOME_DESCR),
                  'driverinfo': _alp_driverinfo,
                  'driverversion': _alp_driverversion,
                  'interfaceversion': lambda x, y: _alp_retvalue(x, y, _ALP_IF_VERS),
                  'name': lambda x, y: _alp_retvalue(x, y, _ALP_DOME_NAME),
                  'supportedactions': _alp_get_dome_actions,
#   DOME SPECIFIC GET ACTIONS
                  'altitude': lambda x, y: _alp_unsupported_get(x, y, 'Altitude'),
                  'athome': lambda x, y: _alp_unsupported_get(x, y, 'AtHome'),
                  'atpark': _alp_atpark,
                  'azimuth': _alp_getazimuth,
                  'canfindhome': lambda x, y: _alp_retvalue(x, y, False),
                  'canpark': lambda x, y: _alp_retvalue(x, y, True),
                  'cansetaltitude': lambda x, y: _alp_retvalue(x, y, False),
                  'cansetazimuth': lambda x, y: _alp_retvalue(x, y, True),
                  'cansetpark': lambda x, y: _alp_retvalue(x, y, True),
                  'cansetshutter': lambda x, y: _alp_retvalue(x, y, True),
                  'canslave': lambda x, y: _alp_retvalue(x, y, _GB.canslave),
                  'cansyncazimuth': lambda x, y: _alp_retvalue(x, y, True),
                  'shutterstatus': _alp_shutterstatus,
                  'slaved': _alp_slavestatus,
                  'slewing': _alp_slewstatus,
                  }

def _alp_tbi(handle, data, command):
    'Returns TBI error'
    err = (_ALP_TBI[0], _ALP_TBI[1]+command)
    _alp_reply_200(handle, data, err=err)

def _alp_abortslew(handle, data):
    'Stop dome movement'
    ret = _GB.dctrl.stop()
    _alp_reply_action(handle, data, ret)

def _alp_closeshutter(handle, data):
    'close shutter command'
    ret = _GB.dctrl.close_shutter()
    _alp_reply_action(handle, data, ret)

def _alp_setconnected(handle, data):
    'set connection status (dummy stub)'
    _alp_reply_200(handle, data, value=True)

def _alp_find_home(handle, data):
    'find home command'
    _alp_tbi(handle, data, 'FindHome')

def _alp_open_shutter(handle, data):
    'open shutter command'
    ret = _GB.dctrl.open_shutter()
    _alp_reply_action(handle, data, ret)

def _alp_goto_park(handle, data):
    'park command'
    ret = _GB.dctrl.park()
    _alp_reply_action(handle, data, ret)

def _alp_set_park(handle, data):
    'set park command'
    ret = _GB.dctrl.set_park()
    _alp_reply_action(handle, data, ret)

def _alp_set_slaved(handle, data):
    'set slave command'
    slaved = data.get(_ALP_SLAVED)
    if slaved is None:
        err = (_ALP_VALUE_NOT_SET[0], _ALP_VALUE_NOT_SET[1]+_ALP_SLAVED)
        _alp_reply_200(handle, data, err=err)
    if slaved[0] == 'True':
        ret = _GB.dctrl.set_slave()
    else:
        ret = _GB.dctrl.stop()
    _alp_reply_action(handle, data, ret)

def _alp_slewtoazimuth(handle, data):
    'Slew to azimuth command'
    azh = data.get(_ALP_AZIMUTH)
    if azh is None:
        err = (_ALP_VALUE_NOT_SET[0], _ALP_VALUE_NOT_SET[1]+_ALP_AZIMUTH)
        _alp_reply_200(handle, data, err=err)
    ret = _GB.dctrl.slew_to_azimuth(azh[0])
    _alp_reply_action(handle, data, ret)

def _alp_synctoazimuth(handle, data):
    'Sync to azimuth command'
    azh = data.get(_ALP_AZIMUTH)
    if azh is None:
        err = (_ALP_VALUE_NOT_SET[0], _ALP_VALUE_NOT_SET[1]+_ALP_AZIMUTH)
        _alp_reply_200(handle, data, err=err)
    ret = _GB.dctrl.sync_to_azimuth(azh[0])
    _alp_reply_action(handle, data, ret)

#                    command      function                       # Common actions
_DOME_PUT_ACTS = {'action': lambda x, y: _alp_unsupported_put(x, y, 'Action'),
                  'commandblind': lambda x, y: _alp_unsupported_put(x, y, 'CommandBlind'),
                  'commandbool': lambda x, y: _alp_unsupported_put(x, y, 'CommandBool'),
                  'commandstring': lambda x, y: _alp_unsupported_put(x, y, 'CommandString'),
                  'connected': _alp_setconnected,           # arg: Connected
                                                                 # Dome specific actions
                  'abortslew': _alp_abortslew,
                  'closeshutter': _alp_closeshutter,
                  'findhome': _alp_find_home,
                  'openshutter': _alp_open_shutter,
                  'park': _alp_goto_park,
                  'setpark': _alp_set_park,
                  'slaved': _alp_set_slaved,                 # arg: 'Slaved'
                  'slewtoaltitude': _alp_unsupported_put,
                  'slewtoazimuth': _alp_slewtoazimuth,       # arg: 'Azimuth'
                  'synctoazimuth': _alp_synctoazimuth,       # arg: 'Azimuth'
                 }

def _alp_getswitchid(params):
    'Returns a valid switch ID or None'
    idn = params.get('Id')
    if idn is None:
        idn = params.get('ID')
    if idn is None:
        return idn
    try:
        idn = int(idn[0])-1
    except ValueError:
        return None
    if 0 <= idn < _N_SWITCHES:
        return idn
    return None

def _alp_retswitchpar(handle, params, vlist):
    'returns value from list of switch info'
    idn = _alp_getswitchid(params)
    if idn is None:
        err = (_ALP_INVALID_VALUE[0], _ALP_INVALID_VALUE[1]+'missing or invalid Id')
        _alp_reply_200(handle, params, err=err)
        return
    val = vlist[idn]
    _alp_reply_200(handle, params, value=val)

def _alp_getswitch(handle, params):
    'Return status of given switch (True/False)'
    sw_stat = _GB.dctrl.get_switch_states()
    _alp_retswitchpar(handle, params, sw_stat)

def _alp_switchcanwrite(handle, params):
    'Returns write capability of given switch'
    _alp_retswitchpar(handle, params, [1, 1, 1, 1])

def _alp_getswitchdescr(handle, params):
    'return description of switch'
    sw_stat = _GB.dctrl.get_switch_descr()
    _alp_retswitchpar(handle, params, sw_stat)

def _alp_getswitchname(handle, params):
    'return name of switch'
    sw_stat = _GB.dctrl.get_switch_names()
    _alp_retswitchpar(handle, params, sw_stat)

def _alp_getswitchvalue(handle, params):
    'Return status of given switch (1/0)'
    sw_stat = _GB.dctrl.get_switch_states()
    _alp_retswitchpar(handle, params, sw_stat)

def _alp_get_switch_actions(handle, params):
    'returns list of supported actions'
    value = list(_SWITCH_GET_ACTS.keys()) + list(_SWITCH_PUT_ACTS.keys())
    _alp_reply_200(handle, params, value)

#   COMMON ACTIONS     command         function
_SWITCH_GET_ACTS = {'connected': _alp_getconnected,
                    'description': lambda x, y: _alp_retvalue(x, y, _ALP_SWITCH_DESCR),
                    'driverinfo': _alp_driverinfo,
                    'driverversion': _alp_driverversion,
                    'interfaceversion': lambda x, y: _alp_retvalue(x, y, _ALP_IF_VERS),
                    'name': lambda x, y: _alp_retvalue(x, y, _ALP_SWITCH_NAME),
                    'supportedactions': _alp_get_switch_actions,
# SWITCH SPECIFIC ACTIONS
                    'maxswitch': lambda x, y: _alp_retvalue(x, y, _N_SWITCHES),
                    'canwrite': lambda x, y: _alp_retvalue(x, y, True),
                    'getswitch': _alp_getswitch,
                    'getswitchdescription': _alp_getswitchdescr,
                    'getswitchname': _alp_getswitchname,
                    'getswitchvalue': _alp_getswitchvalue,
                    'minswitchvalue': lambda x, y: _alp_retvalue(x, y, 0),
                    'maxswitchvalue': lambda x, y: _alp_retvalue(x, y, 1),
                    'switchstep': lambda x, y: _alp_retvalue(x, y, 1),
                   }

def _alp_setswitch(handle, data):
    'Set switch (True/false)'
    nrele = _alp_getswitchid(data)
    if nrele is None:
        err = (_ALP_INVALID_VALUE[0], _ALP_INVALID_VALUE[1]+'missing or invalid Id')
        _alp_reply_200(handle, data, err=err)
        return
    enable = data.get('State')
    if enable is None:
        err = (_ALP_INVALID_VALUE[0], _ALP_INVALID_VALUE[1]+'missing State')
        _alp_reply_200(handle, data, err=err)
        return
    enable = enable[0].startswith('T')
    ret = _GB.dctrl.switch(nrele, enable)
    _alp_reply_action(handle, data, ret)

def _alp_setswitchval(handle, data):
    'Set switch (1/0)'
    nrele = _alp_getswitchid(data)
    if nrele is None:
        err = (_ALP_INVALID_VALUE[0], _ALP_INVALID_VALUE[1]+'missing or invalid Id')
        _alp_reply_200(handle, data, err=err)
        return
    enable = data.get('Value')
    if enable is None:
        err = (_ALP_INVALID_VALUE[0], _ALP_INVALID_VALUE[1]+'missing Value')
        _alp_reply_200(handle, data, err=err)
        return
    try:
        enable = int(enable[0])
    except ValueError:
        err = (_ALP_INVALID_VALUE[0], _ALP_INVALID_VALUE[1]+enable)
        _alp_reply_200(handle, data, err=err)
        return
    if enable not in (0, 1):
        err = (_ALP_INVALID_VALUE[0], _ALP_INVALID_VALUE[1]+str(enable))
        _alp_reply_200(handle, data, err=err)
        return
    ret = _GB.dctrl.switch(nrele, enable)
    _alp_reply_action(handle, data, ret)

#   COMMON ACTIONS     command         function
_SWITCH_PUT_ACTS = {'action': lambda x, y: _alp_unsupported_put(x, y, 'Action'),
                    'commandblind': lambda x, y: _alp_unsupported_put(x, y, 'CommandBlind'),
                    'commandbool': lambda x, y: _alp_unsupported_put(x, y, 'CommandBool'),
                    'commandstring': lambda x, y: _alp_unsupported_put(x, y, 'CommandString'),
                    'connected': _alp_setconnected,
                                                      # Switch specific actions
                    'setswitch': _alp_setswitch,
                    'setswitchname': lambda x, y: _alp_unsupported_put(x, y, 'SetSwitchName'),
                    'setswitchvalue': _alp_setswitchval,
                   }

def _alp_reply_200(handle, params, value=None, err=_ALP_SUCCESS):
    'normal reply'
    _GB.logger.info(f'Alpaca - Reply 200: value={value}, err={err}')
    ret = {_ALP_CLIENT_ID: int(params[_ALP_CLIENT_ID][0]),
           _ALP_CLIENT_TRANS_ID: int(params[_ALP_CLIENT_TRANS_ID][0]),
           _ALP_SERVER_TRANS_ID: _GB.al_transid,
           _ALP_ERROR_NUMBER: err[0],
           _ALP_ERROR_MESSAGE: err[1]}
    if value is not None:
        ret[_ALP_VALUE] = value
    _GB.al_transid = (_GB.al_transid+1)%UNSIGNED_32
    handle.send_response(200)
    handle.send_header('Content-type', 'application/json')
    handle.end_headers()
    handle.wfile.write(json.dumps(ret).encode('utf8'))

def _alp_reply_action(handle, params, ret):
    'returns status after action'
    if ret:
        err = (_ALP_DOME_SPECIFIC[0], _ALP_DOME_SPECIFIC[1]+ret)
    else:
        err = _ALP_SUCCESS
    _alp_reply_200(handle, params, err=err)

def _alp_reply_error(handle, code, msg):
    'error reply'
    _GB.logger.error(f'Alpaca - _alp_reply_error({code}, {msg})')
    handle.send_response(code)
    handle.send_header('Content-type', 'text/plain')
    handle.end_headers()
    handle.wfile.write(msg.encode('utf8'))

class _AlpacaHandler(BaseHTTPRequestHandler):
    'Alpaca request handler'
    def log_message(self, *args):
        'to disable logging of requests'

    def _parse_get(self):
        'Parse URL for GET request'
        parsed = urlparse(self.path)
        path = parsed.path.split('/')
        params = parse_qs(parsed.query)
        dev_type = path[3]
        dev_num = path[4]
        command = path[5]
        _GB.logger.info(f'Alpaca - GET request - Dev.type:{dev_type}, ' \
                   f'Dev.num:{dev_num}, Command:{command}, Params:{str(params)}')
        return dev_type, dev_num, command, params

    def _parse_put(self):
        'Parse URL or form data'
        parsed = urlparse(self.path)
        path = parsed.path.split('/')
        datalen = int(self.headers.get('Content-Length', 0))
        if datalen > 0:
            data = self.rfile.read(datalen).decode('utf8')
            data = parse_qs(data)
        else:
            data = {}
        dev_type = path[3]
        dev_num = path[4]
        command = path[5]
        _GB.logger.info(f'Alpaca - PUT request - Dev.type:{dev_type},' \
                   f'Dev.num:{dev_num}, Command:{command}, Data:{str(data)}')
        return dev_type, dev_num, command, data

    def do_get_dome(self, command, params):
        'Reply to GET requests for Dome'      ## table driven
        func = _DOME_GET_ACTS.get(command)
        if func is None:
            err = (_ALP_INVALID_OPERATION[0], _ALP_INVALID_OPERATION[1]+command)
            _alp_reply_200(self, params, err=err)
        else:
            func(self, params)

    def do_get_switch(self, command, params):
        'Reply to GET requests for Switch'       ## table driven'
        func = _SWITCH_GET_ACTS.get(command)
        if func is None:
            err = (_ALP_INVALID_OPERATION[0], _ALP_INVALID_OPERATION[1]+command)
            _alp_reply_200(self, params, err=err)
        else:
            func(self, params)

    def do_put_dome(self, command, data):
        'Reply to PUT requests for Dome'       ## table driven'
        func = _DOME_PUT_ACTS.get(command)
        if func is None:
            err = (_ALP_INVALID_OPERATION[0], _ALP_INVALID_OPERATION[1]+command)
            _alp_reply_200(self, data, err=err)
        else:
            func(self, data)

    def do_put_switch(self, command, data):
        'Reply to PUT requests for Switch'       ## table driven'
        func = _SWITCH_PUT_ACTS.get(command)
        if func is None:
            err = (_ALP_INVALID_OPERATION[0], _ALP_INVALID_OPERATION[1]+command)
            _alp_reply_200(self, data, err=err)
        else:
            func(self, data)

    def do_get(self):
        'Reply to GET requests'
        if self.path == '/':     # reply to dummy request
            _GB.logger.info('Alpaca - Got dummy request')
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.flush()
            _GB.logger.info('Alpaca - Sent dummy reply')
            return
        dev_type, dev_num, command, params = self._parse_get()
        if dev_num != '0':
            _alp_reply_error(self, 400, _ALP_INVALID_VALUE[1]+dev_num)
        if dev_type == 'dome':
            self.do_get_dome(command, params)
        elif dev_type == 'switch':
            self.do_get_switch(command, params)
        else:
            _alp_reply_error(self, 400, _ALP_UNSUPPORTED_DEVICE+dev_type)

    def do_put(self):
        'Reply to PUT requests'
        dev_type, dev_num, command, data = self._parse_put()
        if dev_num != '0':
            _alp_reply_error(self, 400, _ALP_INVALID_VALUE[1]+dev_num)
        if dev_type == 'dome':
            self.do_put_dome(command, data)
        elif dev_type == 'switch':
            self.do_put_switch(command, data)
        else:
            _alp_reply_error(self, 400, _ALP_UNSUPPORTED_DEVICE+dev_type)

    def do_GET(self):                        #pylint: disable=C0103
        'wrapper catching exceptions'
        try:
            self.do_get()
        except Exception as exc:             #pylint: disable=W0703
            _alp_reply_error(self, 500, str(exc))

    def do_PUT(self):                        #pylint: disable=C0103
        'wrapper catching exceptions'
        try:
            self.do_put()
        except Exception as exc:             #pylint: disable=W0703
            _alp_reply_error(self, 500, str(exc))

def _run_alpaca(port):
    'Starts alpaca server. To be launched in a thread'
    _GB.ipport = port
    _GB.al_server = HTTPServer(('', port), _AlpacaHandler)
    _GB.logger.info(f'Alpaca - server started on port: {port}')
    _GB.al_server.serve_forever()

##################################  API section  ############################

####################################################  Server management calls
def start_server(ipport=0, logger=None, tel_sampler=None, sim_k8055=False):   #pylint: disable=R0915
    '''
    Launch dome control loop.

    Parameters
    ----------
    ipport : int
        If > 0 start alpaca server with given value as port number (default: 0)

    logger : object
        The logger object it must provide two methods: logger.info(msg:str),
        logger.error(msg:str) used to record logging messages. (default: None)

    tel_sampler : TelSampler
        Object provided the telescope sampling capabilities (see info on top of this
        file

    sim_k8055 : bool
        use simulation code for k8055 board controller (default: False)

    Returns
    -------
    dct : DomeController object
    '''
    _GB.logger =  logger if logger else _NoLogger()
    _GB.logger.info(f'Dome API - start_server(Vers.{__version__}, {__date__})')
    if _GB.server is not None:
        _GB.logger.info('Dome server already running')
        raise RuntimeError(_ALREADY_RUNNING)
    if sim_k8055:
        _GB.logger.info('Dome - using K8055 simulator')
        _GB.handle = K8055Simulator()
    _GB.handle.OpenDevice(K8055_PORT)
    _GB.data_file = os.path.join(THIS_DIR, DOME_DATA_FILE)
    _GB.logger.info(f'Dome - getting data from: {_GB.data_file}')
    _GB.tel_sampler = tel_sampler
    if tel_sampler:
        _GB.logger.info('Dome - tel. sampler is active')
    else:
        _GB.logger.info('Dome - tel_sampler not available')
    try:
        with open(_GB.data_file, encoding='utf8') as f_in:
            dome_data = json.load(f_in)
    except FileNotFoundError as exc:
        raise RuntimeError(_NO_DOME_DATA) from exc
    _GB.domeaz = dome_data['domeaz']     # Dati calibrazione
    _GB.hoffset = dome_data['hoffset']   #
    _GB.maxerr = dome_data['maxerr']     #
    _GB.n360 = dome_data['n360']         #
    _GB.nstart = dome_data['nstart']     #
    _GB.nstop = dome_data['nstop']       #
    _GB.parkaz = dome_data['parkaz']     #
    _GB.ptable = dome_data['ptable']     #
    _GB.shuttime = dome_data['shuttime'] #
    _GB.t360 = dome_data['t360']         #
    _GB.tpoll = dome_data['tpoll']       #
    _GB.tsafe = dome_data['tsafe']       #
    _GB.tshort = dome_data['tshort']     #
    _GB.tstart = dome_data['tstart']     #
    _GB.tstop = dome_data['tstop']       #
    _GB.vmax = dome_data['vmax']         # fine dati calibrazione

    _GB.targetaz = -1
    _GB.canslave = bool(tel_sampler)
    if not _GB.canslave:
        _GB.telstat = _CANT_SLAVE
    _GB.saveaz = _GB.domeaz
    _GB.n180 = _GB.n360/2
    _GB.todeg = 360./_GB.n360
    _GB.toenc = _GB.n360/360.

    with _GB.cmd_lock:                  # block other API calls
        _GB.server = Thread(target=_dome_loop)
        _GB.server.start()
        count = 10
        while not _GB.server.is_alive():
            time.sleep(0.1)
            count -= 1
        if not _GB.server.is_alive():
            raise RuntimeError(_DOME_THREAD_ERROR)
        _log_status()

    _GB.logger.info(f'Dome - thread {_GB.server.native_id} running')
    if ipport > 0:
        _GB.logger.info('Alpaca - starting server')
        _GB.alpaca = Thread(target=_run_alpaca, args=(ipport, ))
        _GB.alpaca.start()
        count = 10
        while not _GB.alpaca.is_alive():
            time.sleep(0.1)
        if not _GB.alpaca.is_alive():
            raise RuntimeError(_ALPACA_THREAD_ERROR)
        _GB.logger.info(f'Alpaca - thread {_GB.alpaca.native_id} running')
    _GB.dctrl = DomeController()
    return _GB.dctrl

class DomeController:              #pylint: disable=R0904
    'DomeController (singleton)'
    @staticmethod
    def stop_server():
        '''
        Stop dome control loop. To be called before application exit
        (Note: after being stoppep the server cannot be started again)

        Returns
        -------
        err : str
            Error message. No error is an empty string
        '''
        _GB.logger.info('Dome API - stop_server()')

        with _GB.cmd_lock:                # Block all API calls
            with _GB.dome_lock:               # stop dome movement, if necessary
                _GB.isslave = False
                _GB.targetaz = -1.0
                if _GB.movstat in (AIMING, STEPPING, RUNNING):
                    _stop_lk('stop_server')
            while True:                   # wait for dome complete stop
                if _GB.movstat == IDLE:
                    break
                time.sleep(_GB.tpoll)
            if _GB.alpaca:
                _GB.logger.info('Alpaca - shutting down http server')
                threadid = _GB.alpaca.native_id
                _GB.al_server.shutdown()
                _GB.logger.info('Alpaca - waiting thread to exit')
                _GB.alpaca.join()
                _GB.logger.info(f'Alpaca - thread {threadid} terminated')
            while True:                 # wait for timers to be executed
                with _AFTER.lock:
                    if not _AFTER.queue:
                        break
                time.sleep(0.1)
            if _GB.server:
                threadid = _GB.server.native_id
                _GB.loop = False
                _GB.logger.info('Dome - waiting thread to exit')
                _GB.server.join()        # wait server loop termination
                _GB.logger.info(f'Dome - thread {threadid} terminated')
            _GB.server = None
        _GB.logger.info('Dome - clearing all digital outputs')
        _GB.handle.ClearAllDigital()
        if isinstance(_GB.handle, K8055Simulator):   # stop K8055 simulator, if necessary
            _GB.logger.info('Dome - stop K8055 simulator loop')
            _GB.handle.stop()
        try:
            with open(_GB.data_file, encoding='utf8') as f_in:
                dome_data = json.load(f_in)
        except FileNotFoundError:
            return _CANT_SAVE_STATUS
        dome_data['parkaz'] = _GB.parkaz
        dome_data['domeaz'] = _GB.domeaz
        with open(_GB.data_file, 'w', encoding='utf8') as f_out:
            json.dump(dome_data, f_out)
        _GB.logger.info('Dome - saved dome_data file: '+_GB.data_file)
        _GB.logger.info('Dome - end of stop_server() procedure')
        return _NO_ERROR

############################################################  Dome control calls
    @staticmethod
    def close_shutter():
        '''
        Close shutter

        Returns
        -------
        err : str
            Error message. No error is an empty string
        '''
        _GB.logger.info('Dome API - close_shutter()')
        with _GB.cmd_lock:
            ret = _start_pulse(CLOSE_SHUTTER, _PULSE_TIME)
            _after(_GB.shuttime, lambda: _set_shut_stat(0))
        return ret

    @staticmethod
    def find_home():
        '''
        Go to home position (if supported by hardware)

        Returns
        -------
        err : str
            Error message. No error is an empty string
        '''
        with _GB.cmd_lock:
            return 'find_home:' +_UNIMPLEMENTED

    @staticmethod
    def get_ext_status():
        '''
        Read extended dome status

        Returns
        -------
        status : dict
            athome         Dome is at home
            atpark         Dome is at park
            connected      Connection status, True if dome is connected
            direct         Moving direction:  0=Idle, 4=clockwise, 3=counterclockwise
            domeaz         Current azimuth in encoder units
            isslave        Dome is currently slaved to telescope
            homeaz         Home position in encoder units
            movstat        Moving satus: 0:Idle, 1:Stopping, 2: aiming at target,
                                         3: doing a step, 4: running free
            parkaz         Parking position in encoder units
            targetaz       Current target azimuth in encoder units
            telstat        Telescope status: 0: cannot slave, 1: azimuth not avaliable
                                             2: telescope ok
         '''
        ret = {}
        with _GB.cmd_lock:
            with _GB.dome_lock:
                direct = _GB.direct
                movstat = _GB.movstat
                domeaz = _GB.domeaz
                targetaz = _GB.targetaz
            ret['athome'] = None    # TBD
            ret['atpark'] = movstat == IDLE and abs(_ang_dist(domeaz, _GB.parkaz)) <= _GB.maxerr
            ret['connected'] = bool(_GB.handle)
            ret['direct'] = direct
            ret['domeaz'] = domeaz
            ret['isslave'] = _GB.isslave
            ret['homeaz'] = _GB.hoffset
            ret['movstat'] = movstat
            ret['parkaz'] = _GB.parkaz
            ret['targetaz'] = targetaz
            ret['telstat'] = _GB.telstat
        return ret

    @staticmethod
    def get_info():
        '''
        Get extended info about the controller

        Returns
        -------
        info : str
        '''
        return f'OPC dome controller. Vers. {__version__}. {__author__}, {__date__}'

    @staticmethod
    def get_params():
        '''
        Get dome static parameters

        Returns
        -------
        params: dict
            canslave       Dome can be slaved to telescope
            maxerr         Max position error in encoder units
            n360           Number of encoder steps for 360°
            nstart         Encoder counts for acceleration to max speed
            nstop          Encoder steps for deceleration from max speed
            t360           Time to do a full 360° turn
            tpoll          Polling period (sec)
            tsafe          Time for safe assess of stopping (sec)
            tstart         Time for accelartion to full speed (sec)
            tstop          Time for deceleration from full speed (sec)
            vmax           Max speed in encoder counts/sec
    '''
        ret = {}
        with _GB.cmd_lock:
            ret['canslave'] = _GB.canslave
            ret['maxerr'] = _GB.maxerr
            ret['n360'] = _GB.n360
            ret['nstart'] = _GB.nstart
            ret['nstop'] = _GB.nstop
            ret['t360'] = _GB.t360
            ret['tpoll'] = _GB.tpoll
            ret['tsafe'] = _GB.tsafe
            ret['tstart'] = _GB.tstart
            ret['tstop'] = _GB.tstop
            ret['vmax'] = _GB.vmax
        return ret

    @staticmethod
    def get_shutter():
        '''
        Get shutter status

        Returns
        -------
        status : int
            0: closed,  1: open
        '''
        return _GB.shutstat

    @staticmethod
    def get_status():
        '''Read essential dome status

        Returns
        -------
        status : STAT class
            connected - True if dome is connected
            domeaz    - Current azimuth (degrees)
            direct    - Moving status: 0=idle, 1=clockwise, -1=counterclockwise
            idletime  - Idle fraction of contol loop period
            isslave   - If dome is slaved to telescope
            movstat   - Motion status: 0=idle, 1=stopping, 2=aiming, 3=stepping
            targetaz  - Current target azimuth (degrees). If < 0, then target
                        azimuth is not set
        '''
#   _dc_log('API: get_status()')
        with _GB.cmd_lock:
            with _GB.dome_lock:
                domeaz = _GB.domeaz
                direct = _GB.direct
                idtime = _GB.idletime
                movstat = _GB.movstat
                targetaz = _GB.targetaz
            _STAT.idletime = idtime
            _STAT.movstat = movstat
            _STAT.connected = _GB.server is not None
            _STAT.domeaz = domeaz*_GB.todeg
            _STAT.targetaz = targetaz*_GB.todeg
            _STAT.isslave = _GB.isslave
            if direct == RIGHT_MOVE:
                _STAT.direct = 1
            elif direct == LEFT_MOVE:
                _STAT.direct = -1
            else:
                _STAT.direct = 0
        return _STAT

    @staticmethod
    def get_switch_names():
        '''
        Get names of switches.

        Returns
        -------
        names : [str]
        '''
        return _SWITCH.names

    @staticmethod
    def get_switch_descr():
        '''
        Get extended descriptions of switches.

        Returns
        -------
        descr : [str]
        '''
        return _SWITCH.descr

    @staticmethod
    def get_switch_states():
        '''
        Get states of all switches

        Returns
        -------
        states : [int]   0: open,  1: closed
        '''
        with _GB.cmd_lock:
            return _GB.switch_stat.copy()

    @staticmethod
    def get_version():
        '''
        Get controller version

        Returns
        -------
        version : str
        '''
        return __version__

    @staticmethod
    def open_shutter():
        '''
        Open shutter

        Returns
        -------
        err : str
            Error message. No error is an empty string
        '''
        with _GB.cmd_lock:
            _GB.logger.info('Dome API - open_shutter()')
            ret = _start_pulse(OPEN_SHUTTER, _PULSE_TIME)
            _after(_GB.shuttime, lambda: _set_shut_stat(1))
        return ret

    @staticmethod
    def park():
        '''
        Slew to park position

        Returns
        -------
        err : str
            Error message. No error is an empty string
        '''
        _GB.logger.info('Dome API - park')
        with _GB.cmd_lock:
            if not _GB.handle:
                return _UNCONNECTED
            if _GB.parkaz is None:
                return _UNCONFIGURED
        return _slew_to(_GB.parkaz)

    @staticmethod
    def set_park():
        '''
        Set current position as park

        Returns
        -------
        err : str
            Error message. No error is an empty string
        '''
        _GB.logger.info('Dome API - set_park()')
        with _GB.cmd_lock:
            with _GB.dome_lock:
                if _GB.movstat != IDLE or _GB.isslave:
                    _GB.logger.error(_CANT_EXECUTE)
                    return _CANT_EXECUTE
                _GB.parkaz = _GB.domeaz
        return _NO_ERROR

    @staticmethod
    def set_slave():             # pylint: disable=R0911
        '''
        Enable slave mode (slave mode can disabled by stop())

        Returns
        -------
        err : str
            Error message. No error is an empty string
        '''
        _GB.logger.info('Dome API - set_slave()')
        with _GB.cmd_lock:
            if not _GB.handle:
                return _UNCONNECTED
            if not _GB.canslave:
                _GB.logger.error(_CANT_EXECUTE)
                return _CANT_EXECUTE
            if _GB.isslave:
                return _NO_ERROR
            with _GB.dome_lock:
                if _GB.movstat != IDLE:
                    _GB.logger.error(_CANT_EXECUTE)
                    return _CANT_EXECUTE
                _GB.isslave = True
            return _NO_ERROR
        return _NO_ERROR

    @staticmethod
    def slew_to_azimuth(azh):
        '''
        Slew to given azimuth

        Parameters
        ----------
        azh : float
            azimuth position (degrees)

        Returns
        -------
        err : str
            Error message. No error is an empty string
        '''
        _GB.logger.info(f'Dome API - slew_to_azimuth({azh})')
        with _GB.cmd_lock:
            try:
                return _slew_to(_to_encoder(float(azh)))
            except ValueError:
                return _VALUE_ERROR

    @staticmethod
    def start_left():
        '''
        Start dome movement counterclockwise

        Returns
        -------
        err : str
            Error message. No error is an empty string
        '''
        _GB.logger.info('Dome API - start_left()')
        with _GB.cmd_lock:
            with _GB.dome_lock:
                return _start_lk(LEFT_MOVE, -1.0)

    @staticmethod
    def start_right():
        '''
        Start dome movement clockwise

        Returns
        -------
        err : str
            Error message. No error is an empty string
        '''
        _GB.logger.info('Dome API - start_right()')
        with _GB.cmd_lock:
            with _GB.dome_lock:
                return _start_lk(RIGHT_MOVE, -1.0)

    @staticmethod
    def step_left(tstep=1):
        '''
        Do a short dome movement counterclockwise

        Parameters
        ----------
        tstep : float
            Duration of step pulse

        Returns
        -------
        err : str
            Error message. No error is an empty string
        '''
        _GB.logger.info(f'Dome API - step_left({tstep})')
        if tstep <= 0:
            return _VALUE_ERROR
        with _GB.cmd_lock:
            with _GB.dome_lock:
                return _start_lk(LEFT_MOVE, tstep)

    @staticmethod
    def step_right(tstep=1):
        '''
        Do a short dome movement clockwise

        Parameters
        ----------
        tstep : float
            Duration of step pulse

        Returns
        -------
        err : str
            Error message. No error is an empty string
        '''
        _GB.logger.info(f'Dome API - step_right({tstep})')
        if tstep <= 0:
            return _VALUE_ERROR
        with _GB.cmd_lock:
            with _GB.dome_lock:
                return _start_lk(RIGHT_MOVE, tstep)

    @staticmethod
    def stop():
        '''
        Stop movement (if in slave mode also set not slave)

        Returns
        -------
        err : str
            Error message. No error is an empty string
        '''
        _GB.logger.info('Dome API - stop()')
        with _GB.cmd_lock:
            if not _GB.handle:
                return _UNCONNECTED
            with _GB.dome_lock:
                _GB.isslave = False
                if _GB.movstat == IDLE:
                    return _NO_ERROR
                if _GB.movstat in (AIMING, STEPPING, RUNNING):
                    _stop_lk('Stop command')
                _GB.targetaz = -1
        return _NO_ERROR

    @staticmethod
    def switch(n_rele, enable=True):
        '''
        Set/clear specified switch

        Parameters
        ----------
        n_switch : int
            Number of switch to operate [0..3]
        enable : bool
            True: close switch, False: open switch

        Returns
        -------
        err : str
            Error message. No error is an empty string
        '''
        _GB.logger.info(f'Dome API - switch({n_rele}, {enable})')
        with _GB.cmd_lock:
            if not _GB.handle:
                return _UNCONNECTED
            try:
                n_rele = int(n_rele)
            except ValueError:
                return _VALUE_ERROR
            if 0 <= n_rele <= 3:
                if enable:
                    _GB.handle.SetDigitalChannel(AUX_RELE_1+n_rele)
                    _GB.switch_stat[n_rele] = 1
                else:
                    _GB.handle.ClearDigitalChannel(AUX_RELE_1+n_rele)
                    _GB.switch_stat[n_rele] = 0
                return _NO_ERROR
        return _VALUE_ERROR

    @staticmethod
    def sync_to_azimuth(azh):
        '''
        Set current azimuth

        Parameters
        ----------
        azh : float
            azimuth value (degrees)

        Returns
        -------
        err : str
            Error message. No error is an empty string
        '''
        _GB.logger.info(f'Dome API - sync_to_azimuth({azh})')
        try:
            domeaz = _to_encoder(float(azh))
        except ValueError:
            return _VALUE_ERROR
        with _GB.cmd_lock:
            if not _GB.handle:
                return _UNCONNECTED
            with _GB.dome_lock:
                if _GB.movstat != IDLE:
                    _GB.logger.error(_CANT_EXECUTE)
                    return _CANT_EXECUTE
                _GB.domeaz = domeaz
        return _NO_ERROR

#################################################### test section #################################
def _print_err(err):
    'Print error string'
    if err:
        print('ERROR:', err)
    else:
        print('OK')

_NODEVICE = '''

*************************************************************
Error connecting to K8055 board.

Maybe the K8055 based hardware controller for the dome is not
connected?

You may test the dome controller application starting with
the "-k" option (use K8055 simulator)
*************************************************************
'''

_STRESS_HELP1 = '''
Testing the precision and repeatability of dome movememts.

The dome will do several movements and verify that the final
position is reached correctly.

************************************************************
First of all you must move the dome manually and put it very
precisely in NORTH position.

When ready, goon with command "q"
************************************************************
'''

_STRESS_HELP2 = '''


************************************************************
Now we start the dome stress test

You may stop it with Ctrl-C
************************************************************
'''

_STRESS_HELP3 = '''


************************************************************
Now you must check the real position of the dome

'''


def _wait_stop():
    'check dome status and exit when it''s idle'
    goon = True
    while goon:
        time.sleep(1)
        stat = _GB.dctrl.get_status()
        if stat.direct == 0:
            break
    return stat

def _test_goto(deg):
    'Goto given position'
    _GB.logger.info(f'Test goto: {deg}')
    print(f'Slewing to {deg:.2f}°...', end=' ', flush=True)
    _GB.dctrl.slew_to_azimuth(deg)
    stat = _wait_stop()
    fullst = _GB.dctrl.get_ext_status()
    deg_enc = _to_encoder(deg)
    dist = _ang_dist(deg_enc, fullst['domeaz'])*_GB.todeg
    print(f'stopped at {stat.domeaz:.2f}° (err: {dist:.2f})')
    return dist

def _test_steps(nsteps, direct):
    'Do some steps'
    if direct.startswith('f'):
        sdir = 'forward'
        func = _GB.dctrl.step_right
    else:
        sdir = 'backward'
        func = _GB.dctrl.step_left
    print(f'Doing {nsteps} steps {sdir} ...', end=' ', flush=True)
    for ist in range(nsteps):
        print(f'{ist+1},', end=' ', flush=True)
        func(8)
        stat = _wait_stop()
    print(f'done at {stat.domeaz:.2f}°')

def _test_timed(nsecs, direct):
    'move dome for given time'
    nsecs = int(nsecs+0.5)
    if direct.startswith('f'):
        sdir = 'forward'
        func = _GB.dctrl.start_right
    else:
        sdir = 'backward'
        func = _GB.dctrl.start_left
    print(f'Going {sdir} for {nsecs} seconds ...', end=' ', flush=True)
    func()
    time.sleep(nsecs)
    _GB.dctrl.stop()
    stat = _wait_stop()
    print(f'done at {stat.domeaz:.2f}°')

def _stresstest():
    'Extensive test'
    print(_STRESS_HELP1)
    _move_cmds()
    _GB.dctrl.sync_to_azimuth(0)
    print(_STRESS_HELP2)
    _test_goto(87)
    _test_steps(15, 'forward')
    _test_goto(192)
    _test_steps(10, 'backward')
    _test_goto(274)
    _test_timed(15, 'backward')
    _test_steps(15, 'forward')
    dist = _test_goto(0)
    print(_STRESS_HELP3)
    side = 'right' if dist < 0 else 'left'
    print(f'The dome should be {abs(dist):.2f}° to the {side} of the north position')

def _move_cmds(add_help=None, one_shot=False):      #pylint: disable=R0912
    'Accept movement commands'
    ans = []
    while True:
        print()
        ans = input('Command (<enter>: help)? ').strip().lower().split()
        if not ans:
            print(_MOVE_HELP)
            if add_help:
                print(add_help)
            continue
        if ans[0] == '?':
            stat = _GB.dctrl.get_status()
            print('Dome status -  connected:', stat.connected,
                  f'  azimuth: {stat.domeaz:.2f}',
                  f'  targetaz: {stat.targetaz:.2f}',
                  '  direction:', stat.direct,
                  '  move status:', stat.movstat,
                  '  is slaved:', stat.isslave,
                  f'  idletime: {stat.idletime:.2f}')
            continue
        if ans[0] == '<':
            ret = _GB.dctrl.start_left()
            _print_err(ret)
            continue
        if ans[0] == '>':
            ret = _GB.dctrl.start_right()
            _print_err(ret)
            continue
        if ans[0] == 's':
            _GB.dctrl.stop()
            continue
        if ans[0] == '+':
            ret = _GB.dctrl.step_right(0.8)
            _print_err(ret)
            continue
        if ans[0] == '-':
            ret = _GB.dctrl.step_left(0.8)
            _print_err(ret)
            continue
        if ans[0] == '++':
            ret = _GB.dctrl.step_right(2)
            _print_err(ret)
            continue
        if ans[0] == '--':
            ret = _GB.dctrl.step_left(2)
            _print_err(ret)
            continue
        if ans[0] == 'sl':
            if len(ans) < 2:
                print('Command error!')
                continue
            ret = _GB.dctrl.slew_to_azimuth(ans[1])
            _print_err(ret)
            continue
        if ans[0] == 'q' or one_shot:
            break
    return ans

def _test():                     #pylint: disable=R0912,R0915,R0914
    'Test code'
    if '-h' in sys.argv:
        print(__doc__)
        sys.exit()
    ksimul = '-k' in sys.argv
    debug = '-d' in sys.argv
    telsim = '-s' in sys.argv
    alport = _ALP_TEST_PORT if '-a' in sys.argv else 0
    print()
    print('Test program')
    print()
    if TEL_SAMPLER:
        print('** slave mode available **')
    else:
        print('** slave mode unavailable **')
    print()
    logger = _Logger(debug)
    if TEL_SAMPLER:
        tls = ts.tel_start(logger, telsim)
    else:
        tls = None
    try:
        dct = start_server(ipport=alport, logger=logger, tel_sampler=tls, sim_k8055=ksimul)
    except Exception as excp:        #pylint: disable=W0703
        print(excp)
        tls.tel_stop()
        sys.exit()
    print()
    print(dct.get_info())
    while True:
        ans = _move_cmds(_MORE_HELP, one_shot=True)
        if ans[0] == '??':
            stat = dct.get_ext_status()
            keys = list(stat.keys())
            keys.sort()
            print()
            for key in keys:
                print(f' - {key}:', stat[key])
            continue
        if ans[0] == 'os':
            dct.open_shutter()
            continue
        if ans[0] == 'cs':
            dct.close_shutter()
            continue
        if ans[0] == 'o':
            ret = dct.switch(ans[1], False)
            _print_err(ret)
            continue
        if ans[0] == 'c':
            ret = dct.switch(ans[1], True)
            _print_err(ret)
            continue
        if ans[0] == 'sp':
            ret = dct.set_park()
            _print_err(ret)
            continue
        if ans[0] == 'p':
            ret = dct.park()
            _print_err(ret)
            continue
        if ans[0] == 'h':
            ret = dct.find_home()
            _print_err(ret)
            continue
        if ans[0] == 'f?':
            ret = _GB.logger.logname()
            print('Log file path:', ret)
            continue
        if ans[0] == 'p?':
            ret = dct.get_params()
            print()
            keys = list(ret.keys())
            for key in keys:
                print(f' - {key}:', ret[key])
            continue
        if ans[0] == 's?':
            ret = dct.get_shutter()
            print('Shutter status:', ret)
            continue
        if ans[0] == 'r?':
            stat = dct.get_switch_states()
            names = dct.get_switch_names()
            print('Relay status:')
            for nmm, stt in zip(names, stat):
                print(' ', nmm, stt)
            continue
        if ans[0] == 'sv':
            ret = dct.set_slave()
            _print_err(ret)
            continue
        if ans[0] == 'sy':
            ret = dct.sync_to_azimuth(ans[1])
            _print_err(ret)
            continue
        if ans[0] == 'i?':
            ret = dct.get_info()
            print(ret)
            continue
        if ans[0] == 'stress':
            _stresstest()
            continue
        if ans[0] == 'q':
            dct.stop()
            tls.tel_stop()
            dct.stop_server()
            break

if __name__ == '__main__':
    _test()
