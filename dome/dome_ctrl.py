'''
dome_ctrl.py - Thread based program for K8055 based Gambato dome controller

Usage for tests:

    python dome_ctrl.py [-d] [-h] [-k] [-i] [-s]

where:

    -d   set debug mode
    -h   print this help page and exit
    -k   use K8055 simulator
    -i   Set italian language for error messages
    -s   use telescope simulator
'''

####################################################################################
# Support for slave mode
#
# In order to allow the operation in slave mode, an external module must be provided
# with name: "telsamp.py"

# The module must implement a function:

# tel_start(logger=None, simul=False) - called once at beginning of operations to
#                                       enable the communication with the telescope.
#        Parameters:
#              logger - if provided, must be an object providing two methods:
#                       logger.info(msg: str) and logger.error(msg: str)
#                       (Typically provided by the Logging standard module)
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
import json
import logging
from threading import Thread, Lock

__version__ = '2.0'
__author__ = 'Luca Fini'
__date__ = 'September 2024'

try:
    import readline          #pylint: disable=W0611
except ModuleNotFoundError:
    pass

from dome_tools import *     #pylint: disable=W0401,W0614

from k8055_simulator import K8055Simulator

THIS_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(THIS_DIR, "..")))

# pylint: disable=C0413
try:                               # Try importing local telsamp
    import telsamp as ts
except ImportError:
    TEL_SAMPLER = False
else:
    TEL_SAMPLER = True

if not TEL_SAMPLER:
    try:                                    # Try importing telsamp from opc environment
        from opc import telsamp as ts
    except ImportError:
        TEL_SAMPLER = False
    else:
        TEL_SAMPLER = True

ARGERR = 'Argument error. Use -h for help'

DLL_PATH = os.path.join(THIS_DIR, 'K8055D.dll')

if sys.platform == 'linux':
    import pyk8055
    HANDLE = pyk8055.k8055()
elif sys.platform == 'win32':
    from ctypes import cdll
    HANDLE = cdll.LoadLibrary(DLL_PATH)
else:
    raise RuntimeError('Unsupported: '+sys.platform)

# pylint: disable=C0413

DEBUG_LOCK = False    # set to true to enable deadlock debugging mode

_PULSE_TIME = 1       # Duration of pulsed relais for open/close shutter (sec)
_SAMPLE_PERIOD = 2    # period of position logging
_CHECK_PERIOD = 1     # period of connection checking

_NO_ERROR = ''

class ENGLISH:             #pylint: disable=R0903
    'English messages'
    ALREADY_RUNNING = 'Dome - server is running'
    CANT_EXECUTE = 'Dome - busy, cannot execute command'
    CANT_OPEN_DEVICE = 'Dome - cannot open device'
    CANT_SAVE_STATUS = 'Dome - error saving dome status'
    CANT_SLAVE = 'Dome - Slave mode not available'
    DOME_THREAD_ERROR = 'Dome - controller thread did not start'
    NO_DOME_DATA = 'Dome - calibration data file missing'
    UNCONNECTED = 'Dome - server not connected'
    UNCONFIGURED = 'Dome - configuration parameter missing'
    UNIMPLEMENTED = 'Dome - function not yet implemented'
    VALUE_ERROR = 'Dome - value error'

class ITALIAN:             #pylint: disable=R0903
    'Italian messages'
    ALREADY_RUNNING = 'Cupola - server già attivo'
    CANT_EXECUTE = 'Cupola - operazione in corso: comando non eseguibile'
    CANT_OPEN_DEVICE = 'Cupola - errore di connessione'
    CANT_SAVE_STATUS = 'Cupola - stato corrente cupola non salvato'
    CANT_SLAVE = 'Cupola - modo slave non disponbile'
    DOME_THREAD_ERROR = 'Cupola - thread di controllo non attivato'
    NO_DOME_DATA = 'Cupola - stato cupola non presente'
    UNCONNECTED = 'Cupola - server non connesso'
    UNCONFIGURED = 'Cupola - parametro di configurazione non definito'
    UNIMPLEMENTED = 'Cupola - operazione non ancora implementata'
    VALUE_ERROR = 'Cupola - valore errato'

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

IDLE = 0          # Dome moving status
STOPPING = 1
AIMING = 2
STEPPING = 3
RUNNING = 4

class _GB:                  # pylint: disable=R0903
    'Global variables'
                         #### Housekeeping
    connected = False    # True when K8055 board is responding
    debug = False        # Debug mode for dome controller
    dctrl = None
    logger = None        # Main logger
    handle = HANDLE
    data_file = ''       # name of dome data file
    language = ENGLISH   # Language for messages
    loop = True
    server = None        # Serving Thread
    tsample = 0          # Position sampling time for debug
    tcheck = 0           # Connection checking time
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
    stopcn = -1          # Counts after a stop command
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

    telsamp = None   # Telescope sampler

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

def _sample(cnt):
    'Record periodic status'
    _GB.logger.info('azh: %.3f, tgt: %.3f, cnt: %d dir: %d, stat: %d, slave: %d, tel: %d',
                    _GB.domeaz, _GB.targetaz, cnt, _GB.direct,
                    _GB.movstat, _GB.isslave, _GB.telstat)

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
    _GB.logger.info('_start_lk(%d, %s)', direct, tstep)
    if not _GB.connected:
        return _GB.language.UNCONNECTED
    if _GB.movstat != IDLE:
        _GB.logger.error(_GB.language.CANT_EXECUTE)
        return _GB.language.CANT_EXECUTE
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
    _GB.logger.info('_stop_lk(%s)', reason)
    _GB.handle.ClearDigitalChannel(_GB.direct)         # stop the motor
    _GB.stopcn = _GB.handle.ReadCounter(ENCODER)       # get current count
    _GB.movstat = STOPPING
    _after(_GB.tsafe, _check_stopped)

def _check_stopped():
    'detect motion end'
    with _GB.dome_lock:
        cnt = _GB.handle.ReadCounter(ENCODER)
        _GB.logger.info('_check_stopped. cnt=%d', cnt)
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
            _GB.logger.info('_check_stopped: stop detected')
            return
        _GB.stopcn = cnt
        _after(_GB.tsafe, _check_stopped)

def _end_step():
    'End of time for pulse movement'
    with _GB.dome_lock:
        if _GB.stopcn < 0:
            _stop_lk('_end_step')

def _check_connection():
    'Check connection status'
    _GB.connected = _GB.handle.SearchDevices() > 0
    return _GB.connected

def _dome_loop():                          #pylint: disable=R0912,R0915
    'Dome status update loop (executed as Thread)'
    _GB.logger.info('control loop starting')
    while _GB.loop:
        _GB.logger.info('checking connection status')
        with _GB.dome_lock:
            if _check_connection():
                _GB.logger.info('connection established')
                break
        time.sleep(1)
    if not _GB.connected:
        _GB.logger.info('control loop terminated while not connected')
        return
    _GB.handle.ClearAllDigital()     # set a known status
    while _GB.loop:
        tstart = time.time()
        _exec_timers(tstart)
        with _GB.dome_lock:
            if tstart > _GB.tcheck:                       # periodically check connection
                if not _check_connection():
                    break
                _GB.tcheck = tstart+_CHECK_PERIOD
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
                azh = _GB.telsamp.az_from_tel()
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
                _GB.logger.info('tel. status now: %d', _GB.telstat)
                _GB.telsave = _GB.telstat
            if _GB.targetaz < 0:
                dst, adst = 0.0, 0.0
            else:
                dst = _ang_dist(_GB.targetaz, _GB.domeaz)
                adst=abs(dst)
            if _GB.movstat == IDLE:
                if adst > _GB.nstop:
                    direct = RIGHT_MOVE if dst > 0 else LEFT_MOVE
                    _GB.logger.info('Start movement (dist=%d)', dst)
                    _start_lk(direct)
                elif adst > _GB.maxerr:
                    direct = RIGHT_MOVE if dst > 0 else LEFT_MOVE
                    pls = _GB.ptable[adst]
                    _GB.logger.info('Stepping to final position (dist=%d, pulse=%.2f)', dst, pls)
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
        nextpoll = _GB.tpoll - (time.time()-tstart)
        _GB.idletime = nextpoll/_GB.tpoll
        if nextpoll>0:
            time.sleep(nextpoll)
    if _GB.connected:
        _GB.logger.info('control loop terminated')
    else:                 # K8055 not connected
        _GB.logger.error('control loop terminated for connection error')

###### API support functions

def _to_encoder(azh):
    'Convert degrees to encoder units'
    return int(azh%360*_GB.toenc+0.5)

def _start_pulse(n_rele, p_time):
    'Start a pulsed rele'
    _GB.logger.info('_start_pulse(%d, %d)', n_rele, p_time)
    if not _GB.connected:
        return _GB.language.UNCONNECTED
    _GB.handle.SetDigitalChannel(n_rele)
    _after(p_time, lambda: _end_pulse(n_rele))
    return _NO_ERROR

def _end_pulse(n_rele):
    'close relais after pulse period'
    _GB.logger.info('_end_pulse(%d)', n_rele)
    _GB.handle.ClearDigitalChannel(n_rele)

def _slew_to(val):
    'Go to azimuth (in encoder units)'
    _GB.logger.info('_slew_to(%d)', val)
    if not _GB.connected:
        return _GB.language.UNCONNECTED
    with _GB.dome_lock:
        if _GB.isslave or _GB.movstat != IDLE:
            _GB.logger.error(_GB.language.CANT_EXECUTE)
            return _GB.language.CANT_EXECUTE
        _GB.targetaz = val
    return _NO_ERROR

def _set_shut_stat(val):
    'Set shutter status open(1)/closed(0)'
    _GB.shutstat = val

def _log_status():
    'Print status variables'
    _GB.logger.info('current status')
    _GB.logger.info('  domeaz: %f', _GB.domeaz)
    _GB.logger.info('  hoffset: %d', _GB.hoffset)
    _GB.logger.info('  maxerr: %d', _GB.maxerr)
    _GB.logger.info('  n180: %d', _GB.n180)
    _GB.logger.info('  n360: %d', _GB.n360)
    _GB.logger.info('  nstart: %d', _GB.nstart)
    _GB.logger.info('  nstop: %d', _GB.nstop)
    _GB.logger.info('  parkaz: %f', _GB.parkaz)
    _GB.logger.info('  ptable: %s', str(_GB.ptable))
    _GB.logger.info('  shuttime: %d', _GB.shuttime)
    _GB.logger.info('  t360: %d', _GB.t360)
    _GB.logger.info('  targetaz: %f', _GB.targetaz)
    _GB.logger.info('  todeg: %f', _GB.todeg)
    _GB.logger.info('  toenc: %f', _GB.toenc)
    _GB.logger.info('  tpoll: %d', _GB.tpoll)
    _GB.logger.info('  tsafe: %d', _GB.tsafe)
    _GB.logger.info('  tshort: %d', _GB.tshort)
    _GB.logger.info('  tstart: %d', _GB.tstart)
    _GB.logger.info('  tstop: %d', _GB.tstop)
    _GB.logger.info('  vmax: %f', _GB.vmax)


##################################  API section  ############################

####################################################  Server management calls
def start_server(logger=False, telsamp=None,                   #pylint: disable=R0915
                 sim_k8055=False, language='', debug=False):
    '''
    Launch dome control loop.

    Parameters
    ----------
    logger : bool
        If true get a logger from logging module

    telsamp : TelSampler
        Object provided the telescope sampling capabilities (see info on top of this
        file)

    sim_k8055 : bool
        use simulation code for k8055 board controller (default: False)

    language : str
        language selector for error messages. Either 'EN' or 'IT'. Default: 'EN'

    debug : bool
        Enables debug messages

    Returns
    -------
    dct : DomeController object
    '''
    _GB.debug = debug
    if language.upper() == 'EN':
        _GB.language = ENGLISH
    elif language.upper() == 'IT':
        _GB.language = ITALIAN
    _GB.logger =  logging.getLogger('dome_ctrl')
    loglevel = logging.DEBUG if debug else logging.INFO
    if not logger:
        logging.disable(logging.CRITICAL)
    _GB.logger.setLevel(level=loglevel)
    _GB.logger.info('Dome API - start_server(Vers.%s, %s)', __version__, __date__)
    if _GB.server is not None:
        _GB.logger.info(_GB.language.ALREADY_RUNNING)
        raise RuntimeError(_GB.language.ALREADY_RUNNING)
    _GB.data_file = os.path.join(THIS_DIR, DOME_DATA_FILE)
    _GB.logger.info('getting data from: %s', _GB.data_file)
    _GB.telsamp = telsamp
    if telsamp:
        _GB.logger.info('tel. sampler is active')
    else:
        _GB.logger.info('tel. sampler not available')
    try:
        with open(_GB.data_file, encoding='utf8') as f_in:
            dome_data = json.load(f_in)
    except FileNotFoundError as exc:
        _GB.logger.error(_GB.language.NO_DOME_DATA)
        raise RuntimeError(_GB.language.NO_DOME_DATA) from exc
    if sim_k8055:
        _GB.logger.info('using K8055 simulator')
        _GB.handle = K8055Simulator()
    try:
        _GB.handle.OpenDevice(K8055_PORT)
    except Exception as excp:
        _GB.logger.error(_GB.language.CANT_OPEN_DEVICE)
        raise RuntimeError(_GB.language.CANT_OPEN_DEVICE) from excp

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
    _GB.canslave = bool(telsamp)
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
            raise RuntimeError(_GB.language.DOME_THREAD_ERROR)
        _log_status()
    _GB.logger.info('thread %d running', _GB.server.native_id)
    _GB.dctrl = DomeController()
    return _GB.dctrl

class DomeController:              #pylint: disable=R0904
    'DomeController (singleton)'
    @staticmethod
    def stop_server():
        '''
        Stop dome control loop. To be called before application exit
        (Note: after being stopped the server cannot be started again)

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
            _GB.logger.debug('Dome is idle')
            while True:                 # wait for timers to be executed
                with _AFTER.lock:
                    if not _AFTER.queue:
                        break
                time.sleep(0.1)
            if _GB.server:
                _GB.loop = False
                _GB.logger.info('waiting thread to exit')
                _GB.server.join()        # wait server loop termination
                _GB.logger.info('thread %d terminated', _GB.server.native_id)
            _GB.server = None
        _GB.logger.info('clearing all digital outputs')
        _GB.handle.ClearAllDigital()
        if isinstance(_GB.handle, K8055Simulator):   # stop K8055 simulator, if necessary
            _GB.logger.info('stop K8055 simulator loop')
            _GB.handle.stop()
        try:
            with open(_GB.data_file, encoding='utf8') as f_in:
                dome_data = json.load(f_in)
        except FileNotFoundError:
            _GB.logger.error(_GB.language.CANT_SAVE_STATUS)
            return _GB.language.CANT_SAVE_STATUS
        dome_data['parkaz'] = _GB.parkaz
        dome_data['domeaz'] = _GB.domeaz
        with open(_GB.data_file, 'w', encoding='utf8') as f_out:
            json.dump(dome_data, f_out)
        _GB.logger.info('saved dome_data file: '+_GB.data_file)
        _GB.logger.info('end of stop_server() procedure')
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
            return 'find_home:' +_GB.language.UNIMPLEMENTED

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
        return f'OPC dome controller - Vers. {__version__}. {__author__} - {__date__}'

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
            parkaz         Parking position in encoder units
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
            ret['parkaz'] = _GB.parkaz
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
            _STAT.connected = (_GB.server is not None) and _GB.connected
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
            if not _GB.connected:
                return _GB.language.UNCONNECTED
            if _GB.parkaz is None:
                return _GB.language.UNCONFIGURED
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
                    _GB.logger.error(_GB.language.CANT_EXECUTE)
                    return _GB.language.CANT_EXECUTE
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
            if not _GB.connected:
                return _GB.language.UNCONNECTED
            if not _GB.canslave:
                _GB.logger.error(_GB.language.CANT_SLAVE)
                return _GB.language.CANT_SLAVE
            if _GB.isslave:
                return _NO_ERROR
            with _GB.dome_lock:
                if _GB.movstat != IDLE:
                    _GB.logger.error(_GB.language.CANT_EXECUTE)
                    return _GB.language.CANT_EXECUTE
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
        _GB.logger.info('Dome API - slew_to_azimuth(%s)', azh)
        with _GB.cmd_lock:
            try:
                return _slew_to(_to_encoder(float(azh)))
            except ValueError:
                return _GB.language.VALUE_ERROR

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
        _GB.logger.info('Dome API - step_left(%f)', tstep)
        if tstep <= 0:
            return _GB.language.VALUE_ERROR
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
        _GB.logger.info('Dome API - step_right(%f)', tstep)
        if tstep <= 0:
            return _GB.language.VALUE_ERROR
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
            if not _GB.connected:
                return _GB.language.UNCONNECTED
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
        _GB.logger.info('Dome API - switch(%d, %d)', n_rele, enable)
        with _GB.cmd_lock:
            if not _GB.connected:
                return _GB.language.UNCONNECTED
            try:
                n_rele = int(n_rele)
            except ValueError:
                return _GB.language.VALUE_ERROR
            if 0 <= n_rele <= 3:
                if enable:
                    _GB.handle.SetDigitalChannel(AUX_RELE_1+n_rele)
                    _GB.switch_stat[n_rele] = 1
                else:
                    _GB.handle.ClearDigitalChannel(AUX_RELE_1+n_rele)
                    _GB.switch_stat[n_rele] = 0
                return _NO_ERROR
        return _GB.language.VALUE_ERROR

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
        _GB.logger.info('Dome API - sync_to_azimuth(%f)', azh)
        try:
            domeaz = _to_encoder(float(azh))
        except ValueError:
            return _GB.language.VALUE_ERROR
        with _GB.cmd_lock:
            if not _GB.connected:
                return _GB.language.UNCONNECTED
            with _GB.dome_lock:
                if _GB.movstat != IDLE:
                    _GB.logger.error(_GB.language.CANT_EXECUTE)
                    return _GB.language.CANT_EXECUTE
                _GB.domeaz = domeaz
        return _NO_ERROR

    @staticmethod
    def wait():
        'Attesa terminazione del server'
        if _GB.server is not None:
            _GB.server.join()

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
    _GB.logger.info('Test goto: %f', deg)
    print('Slewing to {deg:.2f}°...', end=' ', flush=True)
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

def main():                     #pylint: disable=R0912,R0915,R0914
    'main entry point'
    if '-h' in sys.argv:
        print(__doc__)
        sys.exit()
    ksimul = '-k' in sys.argv
    debug = '-d' in sys.argv
    telsim = '-s' in sys.argv
    lang = 'it' if '-i' in sys.argv else 'en'
    loglevel = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=loglevel)
    print()
    print('Test program')
    print()
    if TEL_SAMPLER:
        tls = ts.tel_start(telsim, debug)
        logging.info('** slave mode available **')
    else:
        tls = None
        logging.info('** slave mode unavailable **')
    print()

    try:
        dct = start_server(logger=True, telsamp=tls, sim_k8055=ksimul, language=lang, debug=debug)
    except RuntimeError:
        if tls:
            tls.tel_stop()
        raise
    _GB.logger.debug('dome_ctrl started')
                                # test section
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
            if tls:
                tls.tel_stop()
            dct.stop_server()
            break

if __name__ == '__main__':
    main()
