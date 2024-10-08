'''
alpaca_test.py - Cliente per prova API alpaca. L.Fini, sett. 2023

Uso:
    python test_alpaca.py [-s] [ip_addr]

Dove:
    ip_addr: indirizzo IP del server (default: localhost)

    -s:      invia comando stop al server

NOTA: Richiede l'installazione di "alpyca", modulo alpaca client per python
'''

import sys
import time

import alpaca.dome as ad
import alpaca.switch as sw

if '-h' in sys.argv:
    print(__doc__)
    sys.exit()

IP_ADDR = '-'
if len(sys.argv) > 1:
    IP_ADDR = sys.argv[-1]
if IP_ADDR.startswith('-'):
    IP_ADDR = '127.0.0.1'

PORT = 7777             # Valori eventualmente da modificare in accordo ai corrispondenti
DEV_NUM = 0             # valori impostati in dome_alpaca.py

dome = ad.Dome(f'{IP_ADDR}:{PORT}', DEV_NUM)
switch = sw.Switch(f'{IP_ADDR}:{PORT}', DEV_NUM)

def waitstop():
    'attesa stato stop'
    print('Waiting stop', end=' ', flush=True)
    azh = dome.Azimuth
    oks = 3
    while oks:
        print('.', end='', flush=True)
        time.sleep(1)
        nazh = dome.Azimuth
        if azh == nazh:
            oks -= 1
        else:
            oks = 3
        azh = nazh
    time.sleep(1)
    print()

try:
    dome.Connected = True
except Exception as exc:
    print(f'Cannot connect to server ({str(exc)})')
    sys.exit()
print(f'Connected at {dome.Name}')
print(dome.Description)
if '-s' in sys.argv:
    cmd = 'stop_server'
    print(f'Action({cmd}) - returns:', dome.Action(cmd))
    sys.exit()
print('DriverInfo:', dome.DriverInfo)
print()
print('Capabilities for', dome.Name)
print(' - SupportedActions:', dome.SupportedActions)
print(' - CanFindHome:', dome.CanFindHome)
print(' - CanPark:', dome.CanPark)
print(' - CanSetAltitude:', dome.CanSetAltitude)
print(' - CanSetAzimuth:', dome.CanSetAzimuth)
print(' - CanSetPark:', dome.CanSetPark)
print(' - CanSetShutter:', dome.CanSetShutter)
print(' - CanSlave:', dome.CanSlave)
print(' - CanSyncAzimuth:', dome.CanSyncAzimuth)
print()
print('Get custom parameters')
print('Params:', dome.Action('get_params'))
print('Dome Status:')
print()
#print(' - Altitude:', dome.Altitude)
#print(' - AtHome:', dome.AtHome)
print(' - AtPark:', dome.AtPark)
print(' - Azimuth:', dome.Azimuth)
print(' - ShutterStatus:', dome.ShutterStatus)
print(' - Slaved:', dome.Slaved)
print(' - Slewing:', dome.Slewing)
print()
print('Capabilities for', switch.Name)
print()
print(' - Max Switch:', switch.MaxSwitch)
print(' - Max Switch Value')
for nsw in range(1, switch.MaxSwitch+1):
    print(f'     Switch {nsw}:', switch.MaxSwitchValue(nsw))
print(' - Min Switch Value')
for nsw in range(1, switch.MaxSwitch+1):
    print(f'     Switch {nsw}:', switch.MinSwitchValue(nsw))
print(' - Switch Step')
for nsw in range(1, switch.MaxSwitch+1):
    print(f'     Switch {nsw}:', switch.SwitchStep(nsw))
print(' - Can Write')
for nsw in range(1, switch.MaxSwitch+1):
    print(f'     Switch {nsw}:', switch.CanWrite(nsw))
print(' - Switch Names')
for nsw in range(1, switch.MaxSwitch+1):
    print(f'     Switch {nsw}:', switch.GetSwitchName(nsw))
print(' - Switch Descriptions')
for nsw in range(1, switch.MaxSwitch+1):
    print(f'     Switch {nsw}:', switch.GetSwitchDescription(nsw))
print(' - Switch Status')
for nsw in range(1, switch.MaxSwitch+1):
    print(f'     Switch {nsw}:', switch.GetSwitch(nsw))
print()
answ = input('Proseguo con i test di movimento? ')[:1]
if answ.lower() not in 'sy':
    sys.exit()
print('Testing some commands')
print(' - Azimuth:', dome.Azimuth)
print('SlewToAzimuth(37.2) - returns:', dome.SlewToAzimuth(37.2))
waitstop()
print('SlewToAzimuth(0) - returns:', dome.SlewToAzimuth(0))
waitstop()
print('SetPark() - returns:', dome.SetPark())
print('Park() - returns:', dome.Park())
waitstop()
print(' - Azimuth:', dome.Azimuth)
print(' - Atpark:', dome.AtPark)
print('Slaved = True')
dome.Slaved = True
print(' - Slaved:', dome.Slaved)
print('SlewToAzimuth(10) - previsto errore')
try:
    dome.SlewToAzimuth(10)
except Exception as exc:      #pylint: disable=W0703
    print('Errore:', exc)
waitstop()
print('Slaved = False')
dome.Slaved = False
print(' - Slaved:', dome.Slaved)
print('SlewToAzimuth(10)')
dome.SlewToAzimuth(10)
waitstop()
print(' - Azimuth:', dome.Azimuth)
