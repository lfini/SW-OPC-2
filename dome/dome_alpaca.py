'''
dome_alpaca.py - Alpaca server for Gambato dome controller

Usage:

    python dome_alpaca.py [-d] [-h] [-k] [-i] [-l logfile] [-p al_port] [-s]

where:

    -d   set debug mode (test mode only)
    -h   print this help page and exit
    -k   use K8055 simulator
    -i   Set italian language for error messages
    -l   Specify path of a log file
    -p   Specify IP port for alpaca (default: {})
    -s   use telescope simulator
'''


import sys
import os
import getopt
import json
import logging

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

__version__ = '1.0'
__author__ = 'Luca Fini'
__date__ = 'September 2024'

THIS_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(THIS_DIR, "..")))

# pylint: disable=C0412,C0413
from opc import dome_ctrl as dc
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

ALP_DOME_DESCR = 'OPC dome Alpaca server'
ALP_DOME_NAME = 'OPC dome'

ALP_SWITCH_DESCR = 'Relais bank Alpaca server [numbers: 0..3]'
ALP_SWITCH_NAME = 'OPC rele'
ALP_NSWITCHES = 4

ALP_IF_VERS = '1'

ALP_PORT = 7777

UNSIGNED_32 = 2**32

ALP_SUCCESS = (0, '')
ALP_UNIMPL_PROP = (1024, 'Property/method not implemented: ')
ALP_INVALID_VALUE = (1025, 'Invalid value: ')
ALP_VALUE_NOT_SET = (1026, 'Value not set: ')
ALP_NOT_CONNECTED = (1031, 'Device not connected: ')
ALP_INVALID_WHILE_PARKED = (1032, 'Invalid while parked: ')
ALP_INVALID_WHILE_SLAVED = (1033, 'Invalid while slaved: ')
ALP_INVALID_OPERATION = (1035, 'Invalid operation: ')
ALP_UNSUPPORTED_DEVICE = (20, 'Unsupported device: ')
ALP_UNIMPL_ACTION = (1036, 'Action not implemented: ')
ALP_TBI = (2000, 'Action to be implemented: ')
ALP_DOME_SPECIFIC = (2010, 'Dome internal error: ')

ALP_CLIENT_ID = 'ClientID'
ALP_CLIENT_TRANS_ID = 'ClientTransactionID'
ALP_ERROR_NUMBER = 'ErrorNumber'
ALP_ERROR_MESSAGE = 'ErrorMessage'
ALP_SERVER_TRANS_ID = 'ServerTransactionID'
ALP_VALUE = 'Value'

ALP_AZIMUTH = 'Azimuth'
ALP_COMMANDBOOL = 'Command'
ALP_CONNECTED = 'Connected'
ALP_SLAVED = 'Slaved'
ALP_ACTION = 'Action'
ALP_PARAMS = 'Parameters'

DOME_CUSTOM_ACTIONS = ['stop_server', 'get_params',
                       'get_tel',
                       'start_left', 'start_right',
                       'step_left', 'step_right',
                      ]

class GB:                  # pylint: disable=R0903
    'Global variables'
                         #### Housekeeping
    al_server = None     # HTTPserver for Alpaca
    al_transid = 1       # Alpaca server transaction id
    debug = False        # Debug mode for dome controller
    dctrl = None         # Handle for dome controller
    dome_params = {}     # static parameters from dome
    ipport = 0           # IP port for Alpaca server
    tls = None           # Handle for tel_sampler

##################################  Alpaca server section  ############################

# The alpaca server implements the Dome Alpaca API and the Switch alpaca API

# Supported URLs for GET query

# http://ip.addr:7843/api/v1/dome/0/connected
# http://ip.addr:7843/api/v1/switch/0/connected

def alp_atpark(handle, params):
    'get IsAtPark property'
    ext_stat = GB.dctrl.get_ext_status()
    alp_reply_200(handle, params, ext_stat['atpark'])

def alp_getazimuth(handle, params):
    'get Azimuth property'
    dome_stat = GB.dctrl.get_status()
    alp_reply_200(handle, params, dome_stat.domeaz)

def alp_unsupported_get(handle, params, command):
    'return unsupported get command error'
    err = (ALP_UNIMPL_PROP[0], ALP_UNIMPL_PROP[1]+command)
    alp_reply_200(handle, params, err=err)

def alp_unsupported_put(handle, data, command):
    'return unsupported get command error'
    err = (ALP_UNIMPL_ACTION[0], ALP_UNIMPL_ACTION[1]+command)
    alp_reply_200(handle, data, err=err)

def alp_retvalue(handle, params, value):
    'returns a value'
    alp_reply_200(handle, params, value=value)

def alp_getconnected(handle, params):
    'return connection status'
    dome_stat = GB.dctrl.get_status()
    alp_reply_200(handle, params, value=dome_stat.connected)

def alp_driverinfo(handle, params):
    'Return info on driver'
    info = GB.dctrl.get_info()
    alp_reply_200(handle, params, value=info)

def alp_driverversion(handle, params):
    'Return info on driver'
    info = GB.dctrl.get_version()
    alp_reply_200(handle, params, value=info)

def alp_shutterstatus(handle, params):
    'return shutter status'
    stat = GB.dctrl.get_shutter()
    alp_reply_200(handle, params, value=stat)

def alp_slavestatus(handle, params):
    'return slave status'
    stat = GB.dctrl.get_ext_status()['isslave']
    alp_reply_200(handle, params, value=stat)

def alp_slewstatus(handle, params):
    'return slewing status'
    dome_stat = GB.dctrl.get_status()
    alp_reply_200(handle, params, value=dome_stat.direct != 0)

def alp_get_dome_actions(handle, params):
    'returns list of supported actions'
    value = DOME_CUSTOM_ACTIONS
    alp_reply_200(handle, params, value)

#   COMMON GET ACTIONS   command      function
_DOME_GET_ACTS = {'connected': alp_getconnected,
                  'description': lambda x, y: alp_retvalue(x, y, ALP_DOME_DESCR),
                  'driverinfo': alp_driverinfo,
                  'driverversion': alp_driverversion,
                  'interfaceversion': lambda x, y: alp_retvalue(x, y, ALP_IF_VERS),
                  'name': lambda x, y: alp_retvalue(x, y, ALP_DOME_NAME),
                  'supportedactions': alp_get_dome_actions,
#   DOME SPECIFIC GET ACTIONS
                  'altitude': lambda x, y: alp_unsupported_get(x, y, 'Altitude'),
                  'athome': lambda x, y: alp_unsupported_get(x, y, 'AtHome'),
                  'atpark': alp_atpark,
                  'azimuth': alp_getazimuth,
                  'canfindhome': lambda x, y: alp_retvalue(x, y, False),
                  'canpark': lambda x, y: alp_retvalue(x, y, True),
                  'cansetaltitude': lambda x, y: alp_retvalue(x, y, False),
                  'cansetazimuth': lambda x, y: alp_retvalue(x, y, True),
                  'cansetpark': lambda x, y: alp_retvalue(x, y, True),
                  'cansetshutter': lambda x, y: alp_retvalue(x, y, True),
                  'canslave': lambda x, y: alp_retvalue(x, y, GB.dome_params['canslave']),
                  'cansyncazimuth': lambda x, y: alp_retvalue(x, y, True),
                  'shutterstatus': alp_shutterstatus,
                  'slaved': alp_slavestatus,
                  'slewing': alp_slewstatus,
                  }

def alp_tbi(handle, data, command):
    'Returns TBI error'
    err = (ALP_TBI[0], ALP_TBI[1]+command)
    alp_reply_200(handle, data, err=err)

def alp_abortslew(handle, data):
    'Stop dome movement'
    ret = GB.dctrl.stop()
    alp_reply_action(handle, data, ret)

def alp_closeshutter(handle, data):
    'close shutter command'
    ret = GB.dctrl.close_shutter()
    alp_reply_action(handle, data, ret)

def alp_setconnected(handle, data):
    'set connection status (dummy stub)'
    alp_reply_200(handle, data, value=True)

def alp_find_home(handle, data):
    'find home command'
    alp_tbi(handle, data, 'FindHome')

def alp_open_shutter(handle, data):
    'open shutter command'
    ret = GB.dctrl.open_shutter()
    alp_reply_action(handle, data, ret)

def alp_goto_park(handle, data):
    'park command'
    ret = GB.dctrl.park()
    alp_reply_action(handle, data, ret)

def alp_set_park(handle, data):
    'set park command'
    ret = GB.dctrl.set_park()
    alp_reply_action(handle, data, ret)

def alp_set_slaved(handle, data):
    'set slave command'
    slaved = data.get(ALP_SLAVED)
    if slaved is None:
        err = (ALP_VALUE_NOT_SET[0], ALP_VALUE_NOT_SET[1]+ALP_SLAVED)
        alp_reply_200(handle, data, err=err)
        return
    if slaved[0] == 'True':
        ret = GB.dctrl.set_slave()
    else:
        ret = GB.dctrl.stop()
    alp_reply_action(handle, data, ret)

def alp_action(handle, data):
    'Implement special commands'
    act = data.get(ALP_ACTION)
    aname = act[0] if act else ''

    match aname:
        case 'stop_server':
            errmsg = GB.dctrl.stop_server()
            if errmsg:
                alp_reply_error(handle, 400, errmsg)
            logging.debug('dome_alpaca exiting')
            if GB.tls:
                logging.debug('Stopping tel_sampler')
                GB.tls.tel_stop()
            alp_reply_200(handle, data)
            sys.exit()
        case 'start_left':
            errmsg = GB.dctrl.start_left()
            if errmsg:
                alp_reply_error(handle, 400, errmsg)
            alp_reply_200(handle, data)
        case 'start_right':
            errmsg = GB.dctrl.start_right()
            if errmsg:
                alp_reply_error(handle, 400, errmsg)
            alp_reply_200(handle, data)
        case 'step_left':
            errmsg = GB.dctrl.step_left()
            if errmsg:
                alp_reply_error(handle, 400, errmsg)
            alp_reply_200(handle, data)
        case 'step_right':
            errmsg = GB.dctrl.step_right()
            if errmsg:
                alp_reply_error(handle, 400, errmsg)
            alp_reply_200(handle, data)
        case 'get_params':
            params = GB.dctrl.get_params()
            alp_reply_200(handle, data, value=params)
        case 'get_tel':
            if GB.tls:
                val = GB.tls.tel_status()
            else:
                val = None
            alp_reply_200(handle, data, value=val)
        case _:
            err = (ALP_INVALID_VALUE[0], ALP_INVALID_VALUE[1]+f'{aname}: not a custom command')
            alp_reply_200(handle, data, err=err)

def alp_slewtoazimuth(handle, data):
    'Slew to azimuth command'
    azh = data.get(ALP_AZIMUTH)
    if azh is None:
        err = (ALP_VALUE_NOT_SET[0], ALP_VALUE_NOT_SET[1]+ALP_AZIMUTH)
        alp_reply_200(handle, data, err=err)
        return
    ret = GB.dctrl.slew_to_azimuth(azh[0])
    alp_reply_action(handle, data, ret)

def alp_synctoazimuth(handle, data):
    'Sync to azimuth command'
    azh = data.get(ALP_AZIMUTH)
    if azh is None:
        err = (ALP_VALUE_NOT_SET[0], ALP_VALUE_NOT_SET[1]+ALP_AZIMUTH)
        alp_reply_200(handle, data, err=err)
        return
    ret = GB.dctrl.sync_to_azimuth(azh[0])
    alp_reply_action(handle, data, ret)

#                    command      function                       # Common actions
_DOME_PUT_ACTS = {'action': alp_action,
                  'commandblind': lambda x, y: alp_unsupported_put(x, y, 'CommandBlind'),
                  'commandbool': lambda x, y: alp_unsupported_put(x, y, 'CommandBool'),
                  'commandstring': lambda x, y: alp_unsupported_put(x, y, 'CommandString'),
                  'connected': alp_setconnected,           # arg: Connected
                                                                 # Dome specific actions
                  'abortslew': alp_abortslew,
                  'closeshutter': alp_closeshutter,
                  'findhome': alp_find_home,
                  'openshutter': alp_open_shutter,
                  'park': alp_goto_park,
                  'setpark': alp_set_park,
                  'slaved': alp_set_slaved,                 # arg: 'Slaved'
                  'slewtoaltitude': alp_unsupported_put,
                  'slewtoazimuth': alp_slewtoazimuth,       # arg: 'Azimuth'
                  'synctoazimuth': alp_synctoazimuth,       # arg: 'Azimuth'
                 }

def alp_getswitchid(params):
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
    if 0 <= idn < ALP_NSWITCHES:
        return idn
    return None

def alp_retswitchpar(handle, params, vlist):
    'returns value from list of switch info'
    idn = alp_getswitchid(params)
    if idn is None:
        err = (ALP_INVALID_VALUE[0], ALP_INVALID_VALUE[1]+'missing or invalid Id')
        alp_reply_200(handle, params, err=err)
        return
    val = vlist[idn]
    alp_reply_200(handle, params, value=val)

def alp_getswitch(handle, params):
    'Return status of given switch (True/False)'
    sw_stat = GB.dctrl.get_switch_states()
    alp_retswitchpar(handle, params, sw_stat)

def alp_switchcanwrite(handle, params):
    'Returns write capability of given switch'
    alp_retswitchpar(handle, params, [1, 1, 1, 1])

def alp_getswitchdescr(handle, params):
    'return description of switch'
    sw_stat = GB.dctrl.get_switch_descr()
    alp_retswitchpar(handle, params, sw_stat)

def alp_getswitchname(handle, params):
    'return name of switch'
    sw_stat = GB.dctrl.get_switch_names()
    alp_retswitchpar(handle, params, sw_stat)

def alp_getswitchvalue(handle, params):
    'Return status of given switch (1/0)'
    sw_stat = GB.dctrl.get_switch_states()
    alp_retswitchpar(handle, params, sw_stat)

def alp_get_switch_actions(handle, params):
    'returns list of supported actions'
    value = []
    alp_reply_200(handle, params, value)

#   COMMON ACTIONS     command         function
_SWITCH_GET_ACTS = {'connected': alp_getconnected,
                    'description': lambda x, y: alp_retvalue(x, y, ALP_SWITCH_DESCR),
                    'driverinfo': alp_driverinfo,
                    'driverversion': alp_driverversion,
                    'interfaceversion': lambda x, y: alp_retvalue(x, y, ALP_IF_VERS),
                    'name': lambda x, y: alp_retvalue(x, y, ALP_SWITCH_NAME),
                    'supportedactions': alp_get_switch_actions,
# SWITCH SPECIFIC ACTIONS
                    'maxswitch': lambda x, y: alp_retvalue(x, y,ALP_NSWITCHES),
                    'canwrite': lambda x, y: alp_retvalue(x, y, True),
                    'getswitch': alp_getswitch,
                    'getswitchdescription': alp_getswitchdescr,
                    'getswitchname': alp_getswitchname,
                    'getswitchvalue': alp_getswitchvalue,
                    'minswitchvalue': lambda x, y: alp_retvalue(x, y, 0),
                    'maxswitchvalue': lambda x, y: alp_retvalue(x, y, 1),
                    'switchstep': lambda x, y: alp_retvalue(x, y, 1),
                   }

def alp_setswitch(handle, data):
    'Set switch (True/false)'
    nrele = alp_getswitchid(data)
    if nrele is None:
        err = (ALP_INVALID_VALUE[0], ALP_INVALID_VALUE[1]+'missing or invalid Id')
        alp_reply_200(handle, data, err=err)
        return
    enable = data.get('State')
    if enable is None:
        err = (ALP_INVALID_VALUE[0], ALP_INVALID_VALUE[1]+'missing State')
        alp_reply_200(handle, data, err=err)
        return
    enable = enable[0].startswith('T')
    ret = GB.dctrl.switch(nrele, enable)
    alp_reply_action(handle, data, ret)

def alp_setswitchval(handle, data):
    'Set switch (1/0)'
    nrele = alp_getswitchid(data)
    if nrele is None:
        err = (ALP_INVALID_VALUE[0], ALP_INVALID_VALUE[1]+'missing or invalid Id')
        alp_reply_200(handle, data, err=err)
        return
    enable = data.get('Value')
    if enable is None:
        err = (ALP_INVALID_VALUE[0], ALP_INVALID_VALUE[1]+'missing Value')
        alp_reply_200(handle, data, err=err)
        return
    try:
        enable = int(enable[0])
    except ValueError:
        err = (ALP_INVALID_VALUE[0], ALP_INVALID_VALUE[1]+enable)
        alp_reply_200(handle, data, err=err)
        return
    if enable not in (0, 1):
        err = (ALP_INVALID_VALUE[0], ALP_INVALID_VALUE[1]+str(enable))
        alp_reply_200(handle, data, err=err)
        return
    ret = GB.dctrl.switch(nrele, enable)
    alp_reply_action(handle, data, ret)

#   COMMON ACTIONS     command         function
_SWITCH_PUT_ACTS = {'action': lambda x, y: alp_unsupported_put(x, y, 'Action'),
                    'commandblind': lambda x, y: alp_unsupported_put(x, y, 'CommandBlind'),
                    'commandbool': lambda x, y: alp_unsupported_put(x, y, 'CommandBool'),
                    'commandstring': lambda x, y: alp_unsupported_put(x, y, 'CommandString'),
                    'connected': alp_setconnected,
                                                      # Switch specific actions
                    'setswitch': alp_setswitch,
                    'setswitchname': lambda x, y: alp_unsupported_put(x, y, 'SetSwitchName'),
                    'setswitchvalue': alp_setswitchval,
                   }

def alp_reply_200(handle, params, value=None, err=ALP_SUCCESS):
    'normal reply'
    logging.debug('Reply 200: value=%s, err=%s', value, err)
    ret = {ALP_CLIENT_ID: int(params[ALP_CLIENT_ID][0]),
           ALP_CLIENT_TRANS_ID: int(params[ALP_CLIENT_TRANS_ID][0]),
           ALP_SERVER_TRANS_ID: GB.al_transid,
           ALP_ERROR_NUMBER: err[0],
           ALP_ERROR_MESSAGE: err[1]}
    ret[ALP_VALUE] = value
    GB.al_transid = (GB.al_transid+1)%UNSIGNED_32
    handle.send_response(200)
    handle.send_header('Content-type', 'application/json')
    handle.end_headers()
    handle.wfile.write(json.dumps(ret).encode('utf8'))

def alp_reply_action(handle, params, errmsg):
    'returns status after action'
    if errmsg:
        err = (ALP_DOME_SPECIFIC[0], ALP_DOME_SPECIFIC[1]+errmsg)
    else:
        err = ALP_SUCCESS
    alp_reply_200(handle, params, err=err)

def alp_reply_error(handle, code, msg):
    'error reply'
    logging.debug('alp_reply_error(%d, %s)', code, msg)
    handle.send_response(code)
    handle.send_header('Content-type', 'text/plain')
    handle.end_headers()
    handle.wfile.write(msg.encode('utf8'))

class AlpacaHandler(BaseHTTPRequestHandler):
    'Alpaca request handler'
    def log_message(self, *args):
        'to disable logging of requests'

    def _parse_get(self):
        'Parse URL for GET request'
        logging.debug('GET - %s', self.path)
        parsed = urlparse(self.path)
        path = parsed.path.split('/')
        params = parse_qs(parsed.query)
        dev_type = path[3]
        dev_num = path[4]
        command = path[5]
        return dev_type, dev_num, command, params

    def _parse_put(self):
        'Parse URL or form data'
        logging.debug('PUT - %s', self.path)
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
        return dev_type, dev_num, command, data

    def do_get_dome(self, command, params):
        'Reply to GET requests for Dome'      ## table driven
        func = _DOME_GET_ACTS.get(command)
        if func is None:
            err = (ALP_INVALID_OPERATION[0], ALP_INVALID_OPERATION[1]+command)
            alp_reply_200(self, params, err=err)
        else:
            func(self, params)

    def do_get_switch(self, command, params):
        'Reply to GET requests for Switch'       ## table driven'
        func = _SWITCH_GET_ACTS.get(command)
        if func is None:
            err = (ALP_INVALID_OPERATION[0], ALP_INVALID_OPERATION[1]+command)
            alp_reply_200(self, params, err=err)
        else:
            func(self, params)

    def do_put_dome(self, command, data):
        'Reply to PUT requests for Dome'       ## table driven'
        func = _DOME_PUT_ACTS.get(command)
        if func is None:
            err = (ALP_INVALID_OPERATION[0], ALP_INVALID_OPERATION[1]+command)
            alp_reply_200(self, data, err=err)
        else:
            func(self, data)

    def do_put_switch(self, command, data):
        'Reply to PUT requests for Switch'       ## table driven'
        func = _SWITCH_PUT_ACTS.get(command)
        if func is None:
            err = (ALP_INVALID_OPERATION[0], ALP_INVALID_OPERATION[1]+command)
            alp_reply_200(self, data, err=err)
        else:
            func(self, data)

    def do_get(self):
        'Reply to GET requests'
        if self.path == '/':     # reply to dummy request
            logging.debug('Got dummy request')
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.flush()
            logging.debug('Sent dummy reply')
            return
        dev_type, dev_num, command, params = self._parse_get()
        if dev_num != '0':
            alp_reply_error(self, 400, ALP_INVALID_VALUE[1]+dev_num)
        if dev_type == 'dome':
            self.do_get_dome(command, params)
        elif dev_type == 'switch':
            self.do_get_switch(command, params)
        else:
            alp_reply_error(self, 400, ALP_UNSUPPORTED_DEVICE+dev_type)

    def do_put(self):
        'Reply to PUT requests'
        dev_type, dev_num, command, data = self._parse_put()
        if dev_num != '0':
            alp_reply_error(self, 400, ALP_INVALID_VALUE[1]+dev_num)
        if dev_type == 'dome':
            self.do_put_dome(command, data)
        elif dev_type == 'switch':
            self.do_put_switch(command, data)
        else:
            alp_reply_error(self, 400, ALP_UNSUPPORTED_DEVICE+dev_type)

    def do_GET(self):                        #pylint: disable=C0103
        'wrapper catching exceptions'
        try:
            self.do_get()
        except Exception as exc:             #pylint: disable=W0703
            alp_reply_error(self, 500, str(exc))

    def do_PUT(self):                        #pylint: disable=C0103
        'wrapper catching exceptions'
        try:
            self.do_put()
        except Exception as exc:             #pylint: disable=W0703
            alp_reply_error(self, 500, str(exc))

def main():                     #pylint: disable=R0912,R0915,R0914
    'main entry point'
    if '-h' in sys.argv:
        print(__doc__.format(ALP_PORT))
        sys.exit()
    ksimul = False
    telsim = False
    lang = 'en'
    alport = ALP_PORT
    debug = False
    logfile = None
    try:
        opts, _ = getopt.getopt(sys.argv[1:], 'dkl:p:s')
    except getopt.error:
        print(ARGERR)
        sys.exit()
    for opt, val in opts:
        if opt == '-d':
            debug = True
        elif opt == '-k':
            ksimul = True
        elif opt == '-i':
            lang = 'it'
        elif opt == '-l':
            logfile = val
        elif opt == '-p':
            alport = int(val)
        elif opt == '-s':
            telsim = True

    loglevel = logging.DEBUG if debug else logging.INFO
    if logfile:
        logging.basicConfig(filename=logfile, level=loglevel,
                            format='%(asctime)s-%(levelname)s - %(message)s')
    else:
        logging.basicConfig(level=loglevel)
    logger = logging.getLogger('dome_alpaca')

    if TEL_SAMPLER:
        GB.tls = ts.tel_start(telsim, debug)
        logger.info('Slave mode available')
    else:
        GB.tls = None
        logger.info('Slave mode unavailable')
    try:
        GB.dctrl = dc.start_server(logger=True, telsamp=GB.tls,
                                   sim_k8055=ksimul, language=lang, debug=debug)
    except RuntimeError:
        if GB.tls:
            GB.tls.tel_stop()
        raise
    logger.debug('dome_ctrl started')
    GB.dome_params = GB.dctrl.get_params()
    GB.al_server = HTTPServer(('', alport), AlpacaHandler)
    logger.debug('server started on port: %s', alport)
    GB.al_server.serve_forever()

if __name__ == '__main__':
    main()
