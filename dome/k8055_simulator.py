'''
k8055_simulator.py
'''

# To be used for test when hardware is not available

import time
from threading import Timer, Lock

from dome_tools import *     #pylint: disable=W0401,W0614

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

    def ClearDigitalChannel(self, nchan):       #pylint: disable=C0103
        'simulated entry'
        self.dig_channels[nchan-1] = 0
        if nchan in (RIGHT_MOVE, LEFT_MOVE):
            self.direct = 0

    def SetDigitalChannel(self, nchan):       #pylint: disable=C0103
        'simulated entry'
        self.dig_channels[nchan-1] = 1
        if nchan in (RIGHT_MOVE, LEFT_MOVE):
            self.direct = nchan

    def ReadCounter(self, ncnt):       #pylint: disable=C0103
        'simulated entry'
        with self.lock:
            return int(self.counters[ncnt])

    def ResetCounter(self, ncnt):       #pylint: disable=C0103
        'simulated entry'
        with self.lock:
            self.counters[ncnt] = 0

def test_print(duration, cnt0):
    'print counter and speed'
    for _unused in range(duration):
        cnt1 = K_SIM.ReadCounter(ENCODER)
        spe = cnt1-cnt0
        print('Counter:', cnt1, spe)
        cnt0 = cnt1
        time.sleep(0.5)
    return cnt1

if __name__ == '__main__':
    CNT0 = 0
    K_SIM = K8055Simulator()
    print('**** Start')
    K_SIM.SetDigitalChannel(RIGHT_MOVE)
    cnt = test_print(20, 0)
    print('**** Stop')
    K_SIM.ClearDigitalChannel(RIGHT_MOVE)
    test_print(20, cnt)
    print('**** End')
    K_SIM.stop()
