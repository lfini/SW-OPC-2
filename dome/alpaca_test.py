'''
alpaca_test.py - Cliente per prova API alpaca. L.Fini, gen. 2023

Uso:
    python test:_alpaca.py [ip_addr]

Dove:
    ip_addr: indirizzo IP del server (default: localhost)

NOTA: Richiede l'installazione di "alpyca", modulo alpaca client per python
'''

import sys

import alpaca.dome as ad
import alpaca.switch as sw

if '-h' in sys.argv:
    print(__doc__)
    sys.exit()

try:
    IP_ADDR = sys.argv[1]
except IndexError:
    IP_ADDR = '127.0.0.1'

PORT = 7777             # Valori eventualmente da modificare in accordo ai corrispondenti
DEV_NUM = 0             # valori impostati in dome_ctrl.py

STEP = True if '-s' in sys.argv else False

def mprint(*args):
    'print after prompt'
    if STEP:
        input('? ')
    print(*args)

dome = ad.Dome(f'{IP_ADDR}:{PORT}', DEV_NUM)
switch = sw.Switch(f'{IP_ADDR}:{PORT}', DEV_NUM)

dome.Connected = True
print(f'Connected at {dome.Name}')
print(dome.Description)
print()
print('Capabilities for', dome.Name)
mprint(' - CanFindHome:', dome.CanFindHome)
mprint(' - CanPark:', dome.CanPark)
mprint(' - CanSetAltitude:', dome.CanSetAltitude)
mprint(' - CanSetAzimuth:', dome.CanSetAzimuth)
mprint(' - CanSetPark:', dome.CanSetPark)
mprint(' - CanSetShutter:', dome.CanSetShutter)
mprint(' - CanSlave:', dome.CanSlave)
mprint(' - CanSyncAzimuth:', dome.CanSyncAzimuth)
mprint()
print('Dome Status:')
print()
#mprint(' - Altitude:', dome.Altitude)
#mprint(' - AtHome:', dome.AtHome)
mprint(' - AtPark:', dome.AtPark)
mprint(' - Azimuth:', dome.Azimuth)
mprint(' - ShutterStatus:', dome.ShutterStatus)
mprint(' - Slaved:', dome.Slaved)
mprint(' - Slewing:', dome.Slewing)
print()
print('Capabilities for', switch.Name)
print()
mprint(' - Max Switch:', switch.MaxSwitch)
mprint(' - Max Switch Value')
for nsw in range(1, switch.MaxSwitch+1):
    print(f'     Switch {nsw}:', switch.MaxSwitchValue(nsw))
mprint(' - Min Switch Value')
for nsw in range(1, switch.MaxSwitch+1):
    print(f'     Switch {nsw}:', switch.MinSwitchValue(nsw))
mprint(' - Switch Step')
for nsw in range(1, switch.MaxSwitch+1):
    print(f'     Switch {nsw}:', switch.SwitchStep(nsw))
mprint(' - Can Write')
for nsw in range(1, switch.MaxSwitch+1):
    print(f'     Switch {nsw}:', switch.CanWrite(nsw))
mprint(' - Switch Names')
for nsw in range(1, switch.MaxSwitch+1):
    print(f'     Switch {nsw}:', switch.GetSwitchName(nsw))
mprint(' - Switch Descriptions')
for nsw in range(1, switch.MaxSwitch+1):
    print(f'     Switch {nsw}:', switch.GetSwitchDescription(nsw))
mprint(' - Switch Status')
for nsw in range(1, switch.MaxSwitch+1):
    print(f'     Switch {nsw}:', switch.GetSwitch(nsw))

