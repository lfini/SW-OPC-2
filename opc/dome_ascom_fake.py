"""
Simulatore di driver ASCOM per linux
"""
import sys
import os

from threading import Thread
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

#pylint: disable=C0413
from opc import astro

RESOLUTION = 0.4
TIMESTEP = 0.02
PRINT_COUNT = int(1./TIMESTEP)
STEP = RESOLUTION/20.

class GLOB:                              #pylint: disable=R0903
    'Globals che possono essere modificati'
    verbose = False

def set_verbose():
    'abilita modo verboso'
    GLOB.verbose = True

#pylint: disable=C0103

class Dispatch(Thread):                 #pylint: disable=R0902
    "Emulatore di ASCOM Dispatch"
    def __init__(self, selector):
        super().__init__()
        self.selector = selector
        self.Connected = True
        self.Azimuth = 0
        self._azimuth = 0
        self.Slewing = False
        self.targetaz = 0
        self.stop = False
        self._counter = 0
        self.start()

    def run(self):
        print("Simulatore cupola attivo")
        while True:
            if self.stop:
                break
            delta, sign = astro.find_shortest(self._azimuth, self.targetaz)
            if delta > RESOLUTION:
                if sign > 0:
                    self._azimuth += STEP
                else:
                    self._azimuth -= STEP
                self.Slewing = True
                self._azimuth %= 360.
                self.Azimuth = int(self._azimuth)
            else:
                self.Slewing = False

            if GLOB.verbose and self._counter == 0:
                status = "SLEWING" if self.Slewing else "IDLE    "
                print("AZ: ", self.Azimuth, "-", status)
            self._counter = (self._counter+1)%PRINT_COUNT

            time.sleep(TIMESTEP)
        print("Simulatore cupola terminato")

    def AbortSlew(self):
        "Interrompe movimento"
        print("SC: AbortSlew")
        self.targetaz = self.Azimuth
        self.Slewing = False

    def Dispose(self):
        "Termina loop"
        print("SC: Dispose")
        self.stop = True

    def SlewToAzimuth(self, azh):
        "Movimento cupola"
        print(f"SC: SlewToAzimuth({azh:.2f}) - current: {self._azimuth:.3f}")
        self.targetaz = azh%360.

    def FindHome(self):
        "Vai ad home"
        print("SC: FindHome()")
        self.Azimuth = 0.
        self._azimuth = 0.
        self.Slewing = False

    def Park(self):
        "Vai a posizione park"
        print("SC: Park()")
        self.Azimuth = 0.
        self._azimuth = 0.
        self.Slewing = False
