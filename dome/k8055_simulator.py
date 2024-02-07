'''
k8055_simulator.py  - Simulatore di skcheda k8055 per tests

Uso:
    python k8055_simulator.py [-t] [-1] [-0] [-d]

Dove:
    -1   Crea file di controllo con valore 1 (simula scheda attiva)
    -0   Crea file di controllo con valore 1 (simula scheda assente)
    -t   Test funzionamento
    -d   Cancella file di controllo
'''

import sys
import os
import time
from threading import Timer, Lock

from dome_tools import *     #pylint: disable=W0401,W0614

CTRL_FILE = '_devctrl'

DEVPATH = os.path.join(os.path.split(__file__)[0], CTRL_FILE)
TMPPATH = DEVPATH+'.tmp'

#pylint: disable=C0103

class K8055Simulator:            #pylint: disable=R0902
    'k8055 simulator'
    PERIOD = 0.1        # simulator update period
    ACCEL = 0.03        # simulator acceleration
    MAX_SPEED = 1       # simulator max speed
    def __init__(self):
        self.count = 0
        self.dig_channels = [0, 0, 0, 0, 0, 0, 0, 0]
        self.counters = [0, 0]
        self.goon = True
        self.next_t = time.time()
        self.direct = 0
        self.speed = 0
        self.lock = Lock()
        self._run()
        self.step = 0
        self._dev = 1

    def _run(self):
        'position update loop'
        if self.direct != 0:
            self.speed = self.speed+self.ACCEL if self.speed < self.MAX_SPEED else self.MAX_SPEED
        else:
            self.speed = self.speed-self.ACCEL if self.speed > 0 else 0
        if self.speed > 0:
            with self.lock:
                self.counters[ENCODER] += self.speed

        self.next_t += self.PERIOD
        if self.goon:
            Timer(self.next_t-time.time(), self._run).start()

    def stop(self):
        'stop simulator'
        self.goon = False

    def OpenDevice(self, _unused):
        'simulated entry'

    def ClearAllDigital(self):
        'simulated entry'
        self.dig_channels = [0, 0, 0, 0, 0, 0, 0, 0]

    def ClearDigitalChannel(self, nchan):
        'simulated entry'
        self.dig_channels[nchan-1] = 0
        if nchan in (RIGHT_MOVE, LEFT_MOVE):
            self.direct = 0

    def SetDigitalChannel(self, nchan):
        'simulated entry'
        self.dig_channels[nchan-1] = 1
        if nchan in (RIGHT_MOVE, LEFT_MOVE):
            self.direct = nchan

    def ReadCounter(self, ncnt):
        'simulated entry'
        with self.lock:
            return int(self.counters[ncnt])

    def ResetCounter(self, ncnt):
        'simulated entry'
        with self.lock:
            self.counters[ncnt] = 0

    def SearchDevices(self):
        'simulated entry'
        if os.path.exists(DEVPATH):
            with open(DEVPATH, encoding='utf8') as f_in:
                ret = f_in.readline()
                self._dev = int(ret)
            del_file()
        return self._dev

def test_print(duration, cnt0):
    'print counter and speed'
    for _unused in range(duration):
        cnt1 = K_SIM.ReadCounter(ENCODER)
        spe = cnt1-cnt0
        print('Counter:', cnt1, spe)
        cnt0 = cnt1
        time.sleep(0.5)
    return cnt1

def set_file(num):
    'Write num into control file'
    with open(TMPPATH, 'w', encoding='utf8') as f_out:
        print(num, file=f_out)
    os.rename(TMPPATH, DEVPATH)

def del_file():
    'Cancella file di controllo'
    try:
        os.unlink(DEVPATH)
    except FileNotFoundError:
        pass
    try:
        os.unlink(TMPPATH)
    except FileNotFoundError:
        pass

if __name__ == '__main__':
    if '-h' in sys.argv:
        print(__doc__)
        sys.exit()
    if '-1' in sys.argv:
        set_file(1)
        sys.exit()
    if '-0' in sys.argv:
        set_file(0)
        sys.exit()
    if '-t' in sys.argv:
        CNT0 = 0
        K_SIM = K8055Simulator()
        print('**** Start')
        K_SIM.SetDigitalChannel(RIGHT_MOVE)
        CNT = test_print(20, 0)
        print('**** Stop')
        K_SIM.ClearDigitalChannel(RIGHT_MOVE)
        test_print(20, CNT)
        print('**** End')
        K_SIM.stop()
        sys.exit()
    print('Errore argomenti. Usa -h per aiuto')
