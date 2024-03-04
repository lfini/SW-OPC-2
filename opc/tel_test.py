'''
tel_test.py - Programma di test per telsamp.py


Il test lancia due thread di interrogazione del telescopio
'''

import signal
import time

from threading import thread

import telsamp as ts

class GLOB:                  # pylint: disable=R0903
    'Goon flag'
    goon = True

def sghandler(_unused1, _unused2):
    'signal handler per stop test'
    GLOB.goon = False

def test():
    'procedura di test'
    fake_config = {'tel_ip': '127.0.0.1',
                   'tel_port': 9753}
    print("Test di comunicazione con simulatore di telescopio")
    signal.signal(signal.SIGINT, sghandler)
    print("Interrompi con ctrl-C")
    ts.start(fake_config, debug=True)
    nloop = 0
    while GLOB.goon:
        if nloop == 0:
            ret = ts.get_full_status()
            if not isinstance(ret, dict):
                print('Full status:', ret)
            else:
                print('Full status:')
                for key, value in ret.items():
                    print(f'  {key}: {value}')
        print('(RA, DE, SIDE):', ts.get_status())
        nloop = (nloop+1)%10
        time.sleep(1.5)
    err = ts.get_last_err()
    ts.stop()
    print()
    print("Ultimo errore:", err)

if __name__ == '__main__':
    test()
