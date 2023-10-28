"""
Supporto per ASCOM. Include un simulatore per test sotto Linux
"""

import sys
import os
import math
from threading import Thread, Lock
import time

#pylint: disable=C0103

try:
    import win32com.client as wcl
    from pywintypes import com_error
    SIMULATED_ASCOM = False
except ModuleNotFoundError:
    SIMULATED_ASCOM = True

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from opc import astro      # pylint: disable=C0413

_RESOLUTION = 0.05
_TIMESTEP = 0.005
_PRINT_COUNT = int(1./_TIMESTEP)
_STEP = _RESOLUTION/10.

class _Dispatch(Thread):               # pylint: disable=R0902
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
        self._lock = Lock()
        self.vano_aperto = False
        self.start()

    def run(self):
        print("Simulatore cupola attivo")
        while True:
            if self.stop:
                break
            with self._lock:
                delta, sign = astro.find_shortest(self._azimuth, self.targetaz)
                if delta > _RESOLUTION:
                    if sign > 0:
                        self._azimuth += _STEP
                    else:
                        self._azimuth -= _STEP
                    self._azimuth %= 360.
                    self.Azimuth = self._azimuth
                    self.Slewing = True
                else:
                    self.Slewing = False
            time.sleep(_TIMESTEP)
        print("Simulatore cupola terminato")

    def AbortSlew(self):
        "Interrompe movimento"
        print("SC: AbortSlew")
        with self._lock:
            self.Slewing = False
            self.targetaz = self._azimuth

    def Dispose(self):
        "Termina loop"
        print("SC: Dispose")
        self.stop = True

    def SlewToAzimuth(self, azh):
        "Movimento cupola"
        print(f"SC: SlewToAzimuth({azh:.2f}) - current: {self._azimuth:.3f}")
        if azh < 0 or azh >= 360 or math.isnan(azh):
            raise RuntimeError("Azimuth out of range")
        with self._lock:
            self.targetaz = azh

    def FindHome(self):
        "Vai ad home"
        print("SC: FindHome()")
        with self._lock:
            self.Azimuth = 0.
            self._azimuth = 0.
            self.targetaz = 0

    def Park(self):
        "Vai a posizione park"
        print("SC: Park()")
        with self._lock:
            self.Azimuth = 0.
            self._azimuth = 0.
            self.targetaz = 0

    def CloseShutter(self):
        "Apre vano o tetto mobile"
        with self._lock:
            self.vano_aperto = False

    def OpenShutter(self):
        "Apre vano o tetto mobile"
        with self._lock:
            self.vano_aperto = True

    def SyncToAzimuth(self, azh):
        'Imposta valore azimuth'
        if azh < 0 or azh >= 360 or math.isnan(azh):
            raise RuntimeError("Azimuth out of range")
        with self._lock:
            self.Azimuth = azh
            self._azimuth = azh
            self.targetaz = azh

if SIMULATED_ASCOM:
    Dispatch = _Dispatch
    COM_ERROR = RuntimeError("Fake exception")
else:
    Dispatch = wcl.Dispatch
    COM_ERROR = com_error
