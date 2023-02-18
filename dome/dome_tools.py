'''
dome_tools - Constants and support functions for k8055 based dome controller
'''

import time

# The following values are valid for Gambato dome at OPC

K8055_PORT = 0           # Card address

#################  Digital ouput channels
OPEN_SHUTTER = 1
CLOSE_SHUTTER = 2
LEFT_MOVE = 3
RIGHT_MOVE = 4
AUX_RELE_1 = 5     # Named 'telescope' in OCS-III
AUX_RELE_2 = 6     # Named 'CCD' in OCS-III
AUX_RELE_3 = 7     # Named 'luce flat' in OCS-III
AUX_RELE_4 = 8     # Named 'luce cupola' in OCS-III

#################  Encoder counter
ENCODER = 1

#################  Home microswitch channel
MICROSWITCH = 5     # Warning: ReadDigitalChannel not working on windows

DOME_DATA_FILE = 'dome_data.json'

def safe_clear_counter(handle):
    'Clear encoder counter with check'
    handle.ResetCounter(ENCODER)
    while True:
        cnt = handle.ReadCounter(ENCODER)
        if cnt == 0:
            break
        time.sleep(0.01)
