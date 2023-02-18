"""
Programma di test per la scheda K8055 (L.Fini, Nov. 2022)

Compatibilità: Linux/Windows

Uso:

    python k8055_test.py [-h]
"""

import sys
import os
import time
import signal

if sys.platform == 'linux':
    ISLINUX = True
    import pyk8055
elif sys.platform == 'win32':
    ISLINUX = False
    from ctypes import cdll
else:
    raise RuntimeError(f'Unsupported platform: {sys.platform}')

LOGFILE = 'k8055_data.txt'

HELP = """
Comandi definiti:
    c <n>    Clear canale n (n: 1..8)
    ca       Clear tutti i canali
    h        Identificazione canale per homing
    o <n>    Apri dispositivo n (0..3)
    ra       Legge tutti i canali digitali
    rd <n>   Legge canale digitale (n: 1..8)
    rc <n>   Legge valore contatore (n: 1, 2)
    re <n>   Reset contatore (n: 1, 2)
    q        Termina
    s <n>    Set canale n (n: 1..8)
    sa       Set tutti i canali
    sh       Cerca dispositivi
    v        Mostra versione DLL
"""

NOT_OPEN = """
Prima di ogni operazione il canale deve essere aperto
"""

CMD_ERR = """
Comando non riconosciuto
"""

ARG_ERR = """
Errore argomenti
"""

LEFT_MOVE = 3
RIGHT_MOVE = 4

class GLOB:     #pylint: disable=R0903
    'variabili globali'
    goon = True
    logfile = None

def check(args, funct):
    "Verifica e converte argomenti"
    if not isinstance(funct, (tuple, list)):
        funct = [funct]
    try:
        ret = list(f(arg) for f, arg in zip(funct, args[1:]))
    except:                       #pylint: disable=W0702
        ret = None
        print(ARG_ERR)
    return  ret

def print_result(command, args, ret, tbe, taf):
    "Stampa risultato chiamate DLL"
    tmex = (taf-tbe)/1000000.
    print("Risultato:", ret, f'  [time(ms): {tmex:.3f}]')
    print(f'{command}({str(args)}) - result: {ret} - time(ms): {tmex:.3f}', file=GLOB.logfile)

THIS_DIR = os.path.abspath(os.path.dirname(__file__))

POLLING = 0.50   # polling delay per homing

HOMING = '''
Verifica microswitch home.

Dopo aver lanciato il loop di lettura, premi e rilascia il microswitch di homing
e verifica su quale canale è impostato.

Interrompi ciclo con ctrl-c
'''

def homing(handle):
    'funzione controllo canale homing'
    print(HOMING)
    input('Premi <invio> per inizare')
    handle.ClearAllDigital()
    GLOB.goon = True
    while GLOB.goon:
        rdc = []
        for i in range(8):
            rdc.append(handle.ReadDigitalChannel(i+1))
        print('Canali digitali:', rdc)
        time.sleep(POLLING)
    print('Interrotto da CTRL-C')

def sghandler(*_unused):
    'signal handler per interruzione homing'
    GLOB.goon=False

def main():                      #pylint: disable=R0915,R0912
    "Programma principale"

    if '-h' in sys.argv:
        print(__doc__)
        sys.exit()

    GLOB.logfile = open(LOGFILE, 'w', encoding='utf8')   #pylint: disable=R1732

    dev_open = False

    signal.signal(2, sghandler)

    if ISLINUX:
        handle = pyk8055.k8055()
    else:
        dll_path = os.path.join(THIS_DIR, 'K8055D.dll')
        handle = cdll.LoadLibrary(dll_path)

    while True:
        print()
        ans = input("Comando (<invio> per aiuto): ").lower().split()
        if not ans:                    # Primo gruppo di comandi
            print(HELP)
            continue
        if ans[0] == '?':
            print(HELP)
            continue
        if ans[0] == "q":
            break
        if ans[0] == "sh":
            print("Dispositivi:", handle.SearchDevices())
            continue
        if ans[0] == "v":
            print("Versione DLL:", handle.Version())
            continue
        if ans[0] == 'o':
            args = check(ans, int)
            if args:
                port = args[0]
                ret = handle.OpenDevice(port)
                if ret == 0:
                    dev_open = True
                    print("Open OK - ret:", ret)
                else:
                    dev_open = False
                    print("Open Fallito - ret:", ret)
            continue
        if not dev_open:
            print(NOT_OPEN)
            continue
        if ans[0] == "s":
            args = check(ans, int)
            if args:
                tm0 = time.time_ns()
                ret = handle.SetDigitalChannel(args[0])
                tm1 = time.time_ns()
                print_result('SetDigitalChannel', args[0], ret, tm0, tm1)
            continue
        if ans[0] == "sa":
            tm0 = time.time_ns()
            ret = handle.SetAllDigital()
            tm1 = time.time_ns()
            print_result('SetAllDigital', None, ret, tm0, tm1)
            continue
        if ans[0] == "c":
            args = check(ans, int)
            if args:
                tm0 = time.time_ns()
                ret = handle.ClearDigitalChannel(args[0])
                tm1 = time.time_ns()
                print_result('ClearDigitalChannel', args[0], ret, tm0, tm1)
            continue
        if ans[0] == "ca":
            tm0 = time.time_ns()
            ret = handle.ClearAllDigital()
            tm1 = time.time_ns()
            print_result('ClearAllDigital', None, ret, tm0, tm1)
            continue
        if ans[0] == "ra":
            tm0 = time.time_ns()
            ret = handle.ReadAllDigital()
            tm1 = time.time_ns()
            print_result('ReadAllDigital', None, ret, tm0, tm1)
            continue
        if ans[0] == "rc":
            args = check(ans, int)
            if args:
                tm0 = time.time_ns()
                ret = handle.ReadCounter(args[0])
                tm1 = time.time_ns()
                print_result('ReadCounter', args[0], ret, tm0, tm1)
            continue
        if ans[0] == "re":
            args = check(ans, int)
            if args:
                tm0 = time.time_ns()
                ret = handle.ResetCounter(args[0])
                tm1 = time.time_ns()
                print_result('ResetCounter', args[0], ret, tm0, tm1)
            continue
        if ans[0] == "rd":
            args = check(ans, int)
            if args:
                tm0 = time.time_ns()
                ret = handle.ReadDigitalChannel(args[0])
                tm1 = time.time_ns()
                print_result('ReadDigitalChannel', args[0], ret, tm0, tm1)
            continue
        if ans[0] == "h":
            homing(handle)
            continue
        print(CMD_ERR)
    print('Programma di test terminato.')
    print('Dati di test salvati in:', LOGFILE)
    GLOB.logfile.close()

if __name__ == '__main__':
    main()
