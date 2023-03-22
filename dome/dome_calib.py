'''
dome_calib.py  - Calibrazione dati cupola

Questa procedura misura e registra i dati di calibrazione necessari per il
corretto controllo della cupola.

Uso:

    python dome_calib.py [-h] [-k] [-p]

dove:

    -h:   mostra questa pagina di descrizione
    -k:   usa simulatore k8055 (per test)
    -u:   usa parametri dinamici da file

NOTA - la procedura genera due file con dati: dome_data.json e dome_dyn.json,
       ed un grafico: dome_dyn.png (tratto da dome_dyn.json)
'''

import sys
import os
import time
import json
import signal

import numpy as np
import matplotlib.pyplot as plt

#pylint: disable=W0401,W0614
from dome_tools import *
from k8055_simulator import K8055Simulator

THIS_DIR = os.path.abspath(os.path.dirname(__file__))

if sys.platform == 'linux':
    ISLINUX = True
    import pyk8055
elif sys.platform == 'win32':
    ISLINUX = False
    from ctypes import cdll
else:
    raise RuntimeError(f'Piattaforma non supportata: {sys.platform}')

__version__ = '1.0'

STEP_TIME = 1
TSAFE = 1.5     # Intervallo per verifica cupola ferma

DOME_DATA_FILE = os.path.join(THIS_DIR, 'dome_data.json')
DOME_DYN_FILE = os.path.join(THIS_DIR, 'dome_dyn.json')

DOME_PLOT_FILE = os.path.join(THIS_DIR, 'dome_dyn.png')

TASTI_MOVIMENTO = '''
Per muovere e fermare la cupola usare i tasti:

    >  Movimento continuo in senso orario
    <  Movimento continuo in senso antiorario
    s  Stop movimento continuo

    +  Movimento breve in senso orario
    -  Movimento breve in senso antiorario

    .  Mostra conteggi encoder

    t  Termina movimenti e procedi
'''

TASTI_VALIDI = '><s+-t.'

MISURA_N360 = '''




***************************************************************************
MISURA PASSI DI ENCODER PER GIRO

serve a determinare il numero di passi di encoder per un intero giro.

Si prevedono due opzioni:

    1 - Con l'utilizzo del microswitch di home
    2 - Senza utilizzo del microswitch di home
***************************************************************************
'''

MISURA_T360 = '''



***************************************************************************
MISURA TEMPO TOTALE PER GIRO

'''
CALIB_MICRO_1 = '''


***************************************************************************
MISURA PASSI DI ENCODER PER GIRO - passo 1

La misura richiede alcune rotazioni complete della cupola.

Per minimizzare la durata totale della procedura, è conveniente spostare
inizialmente la cupola in modo che la bandierina che aziona il microswitch
si trovi qualche grado a sinistra del microswitch.

Usa i comandi di movimento e termina con il comando "t"

'''

CALIB_MICRO_2 = '''


***************************************************************************
MISURA PASSI DI ENCODER PER GIRO

Portare manualmente la cupola in corrispondenza di un segno di riferimento
qualunque usando i tasti di movimento.

Ciò fatto, proseguire con il tasto "t"
***************************************************************************
'''

CALIB_MICRO_3 = '''


***************************************************************************
Adesso occorre fare fare alla cupola una rotazione completa, in senso orario,
fino a riportarla esattamente in corrispondenza del segno di riferimento.

Al termine, proseguire sempre con il tasto "t"'
***************************************************************************
'''

MISURA_TEMPO_ROTAZIONE = '''


***************************************************************************
MISURA TEMPO DI ROTAZIONE

La cupola farà una intera rotazione per misurare il tempo totale
***************************************************************************
'''

ERRORE_POSIZIONE = '''


***************************************************************************
SPECIFICA MANUALMENTE L'ERRORE MASSIMO DI POSIZIONE
***************************************************************************
'''

MISURA_HOME_OFFSET = '''


***************************************************************************
DETERMINA POSIZIONE NORD RISPETTO AD HOME

Nota: la posizione HOME corrisponde al passaggio dal microswitch di
home. Se il microswitch non è presente, si deve ignorare questo passo.
***************************************************************************
'''

HOME_STEP_1 = '''


***************************************************************************
Portare manualmente la cupola alcuni gradi a sinistra della posizione in
cui la bandierina attiva il microswitch usando i tasti do mivimento.

Al termine prioseguire con il tasto "t"
***************************************************************************
'''

HOME_STEP_2 = '''


***************************************************************************
Adesso occorre portare manualmente la cupola nella posizione Nord.

Quando la cupola si trova in posizione Nord, terminare premendo il tasto "t"
***************************************************************************
'''

SHUT_TIME = '''


***************************************************************************
IMPOSTAZIONE TEMPO DI CHIUSURA/APERTURA VANO


Occorre misurare con un cronometro il tempo necessario per l'apertura o
chiusura completa del vano di osservazione.
***************************************************************************
'''

SMALL_STEPS = '''

***************************************************************************
DETRMINAZIONE IMPULSI PER PICCOLI MOVIMENTI

Viene mostrata una tabella relativa ad impulsi di movimento di durata
crescente per selezionare due valori di durata per i piccoli movimenti
***************************************************************************
'''

MISURA_DYN = '''


***************************************************************************
DETERMINAZIONE PARAMETRI DINAMICI

Vengono valutati i parametri relativi alla dinamica di accelerazione e di
decelerazione della cupola, Allo scopo di determinare vari parametri usati
nella procedura di controllo.
***************************************************************************
'''

MANUAL_PARAMS = '''


***************************************************************************
PARAMETRI DA INSERIRE MANUALMENTE

I seguenti parametri devono essere scelti opportunamente. I grafici mostrati
servono di aiuto nella scelta di alcuni di essi.
***************************************************************************
'''

IMPULSO_BREVE = '''
Selezionare una durata adeguata dell'impulso per passi brevi. La curva nel
terzo grafico serve da aiuto nello scegliere un valore temporale che cor-
risponda ad una numero di passi ragionevolemnte piccolo.
'''

class GLOB:                #pylint: disable=R0903
    'Variabili globali'
    goon = False
    handle = None
    simulation = False
    dome_data = {}

def polling_stop(*_unused):
    'signal handler per interruzione homing'
    GLOB.goon=False

def simulator_stop(*_unused):
    'signal handler per stop simulatore'
    if GLOB.simulation:
        GLOB.handle.stop()
        print('Simulatore K8055 stopped')
    print('Procedura di calibrazione interrotta')
    sys.exit()

if ISLINUX:
    GLOB.handle = pyk8055.k8055()
else:
    DLL_PATH = os.path.join(THIS_DIR, 'K8055D.dll')
    GLOB.handle = cdll.LoadLibrary(DLL_PATH)

def my_input(prompt, valid=None, max_len=1, force_valid=False):
    'Prompt da utente con validazione'
    while True:
        ans = input(prompt).lower().strip()[:max_len]
        if valid is None:
            ret = True
        else:
            if callable(valid):
                ret = valid(ans)
            else:
                ret = ans in valid
        if ret:
            return ans
        if force_valid:
            print('** scelta non valida!')
        else:
            return None

def safe_stop(direct):
    'Stop cupola e attesa inerzia'
    GLOB.handle.ClearDigitalChannel(direct)
    tsafe = TSAFE
    cnt0 = cntstop = GLOB.handle.ReadCounter(ENCODER)
    tm0 = time.time_ns()
    while True:
        time.sleep(0.01)
        cnt1 = GLOB.handle.ReadCounter(ENCODER)
        if cnt1 == cnt0:
            tm1 = time.time_ns()
            if tm1-tm0 >= tsafe:
                break
            continue
        cnt0 = cnt1
        tm0 = time.time_ns()
    tstop = (tm1-tm0)/1000000000
    return cntstop, cnt1, tstop

def move():                              #pylint: disable=R0915,R0912
    'Movimenti manuali cupola'
    print(TASTI_MOVIMENTO)
    GLOB.handle.ClearAllDigital()
    direct = 0
    count = 0
    safe_clear_counter(GLOB.handle)
    while True:
        ans = my_input('Comando movimento: ', TASTI_VALIDI, force_valid=True)
        if ans == '.':
            cnt = GLOB.handle.ReadCounter(ENCODER)
            if direct == RIGHT_MOVE:
                totcnt = count+cnt
            elif direct == LEFT_MOVE:
                totcnt = count-cnt
            else:
                totcnt = count
            print('Conteggi:', totcnt)
            continue
        if direct != 0:
            if ans == 's':
                cnt1 = safe_stop(direct)[1]
                if direct == RIGHT_MOVE:
                    count += cnt1
                else:
                    count -= cnt1
                print('Conteggi:', count)
                safe_clear_counter(GLOB.handle)
                direct = 0
            continue
        if ans == '+':
            GLOB.handle.SetDigitalChannel(RIGHT_MOVE)
            time.sleep(STEP_TIME)
            cnt1 = safe_stop(RIGHT_MOVE)[1]
            count += cnt1
            print('Conteggi:', count)
            safe_clear_counter(GLOB.handle)
            continue
        if ans == '-':
            GLOB.handle.SetDigitalChannel(LEFT_MOVE)
            time.sleep(STEP_TIME)
            cnt1 = safe_stop(LEFT_MOVE)[1]
            count -= cnt1
            print('Conteggi:', count)
            safe_clear_counter(GLOB.handle)
            continue
        if ans == '<':
            direct = LEFT_MOVE
            GLOB.handle.SetDigitalChannel(direct)
            continue
        if ans == '>':
            direct = RIGHT_MOVE
            GLOB.handle.SetDigitalChannel(direct)
            continue
        if ans == 't':
            break
    return count

def wait_microswitch():
    'Attende chiusura microswitch e riporta valore caounter'
    GLOB.goon = True
    signal.signal(2, polling_stop)
    while GLOB.goon:
        ret = GLOB.handle.ReadDigitalChannel(MICROSWITCH)
        if ret:
            count = GLOB.handle.ReadCounter(ENCODER)
            while GLOB.goon:
                ret = GLOB.handle.ReadDigitalChannel(MICROSWITCH)
                if not ret:
                    break
                time.sleep(0.01)
            signal.signal(2, simulator_stop)
            return count
        time.sleep(0.01)
    count = None
    signal.signal(2, simulator_stop)
    return count

def stop_at_counter(stopcount, direct):
    'Ferma cupola al valore di contatore dato'
    signal.signal(2, polling_stop)
    GLOB.goon = True
    while GLOB.goon:
        count = GLOB.handle.ReadCounter(ENCODER)
        if count >= stopcount:
            signal.signal(2, simulator_stop)
            return safe_stop(direct)
        time.sleep(0.01)
    signal.signal(2, simulator_stop)
    return None

def encoder_calib_micro():
    'calibrazione encoder con microswitch'
    GLOB.handle.ClearAllDigital()
    print(CALIB_MICRO_1)
    move()
    print('Inizio procedura di calibrazione encoder')
    safe_clear_counter(GLOB.handle)
    GLOB.handle.SetDigitalChannel(RIGHT_MOVE)
    count0 = wait_microswitch()
    if count0 is None:
        print('Calibrazione encoder interrotta!')
        return None
    print('Attivato microswitch')
    count1 = wait_microswitch()
    safe_stop(RIGHT_MOVE)
    if count1 is None:
        print('Calibrazione encoder interrotta!')
        return None
    counts = count1-count0
    print('Attivato microswitch')
    print('Conteggi misurati:', counts)
    return counts

def encoder_calib_nomicro():
    'calibrazione encoder senza uso del microswitch'
    GLOB.handle.ClearAllDigital()
    print(CALIB_MICRO_2)
    move()
    safe_clear_counter(GLOB.handle)
    print(CALIB_MICRO_3)
    count = move()
    return count

def home_offset():
    'misura numero passi fra HOME e Nord'
    GLOB.handle.ClearAllDigital()
    print(HOME_STEP_1)
    move()
    safe_clear_counter(GLOB.handle)
    GLOB.handle.SetDigitalChannel(RIGHT_MOVE)
    cnt0 = wait_microswitch()
    safe_stop(RIGHT_MOVE)
    print(HOME_STEP_2)
    cnt1 = move()
    return cnt1-cnt0

def measure_n360():
    'calcola numero passi per giro'
    print('Opzioni - 1: con microswitch, 2: senza microswitch, 0: annulla')
    ans = my_input('Opzione? ', '012')
    if ans == '1':
        n360 = encoder_calib_micro()
    elif ans == '2':
        n360 = encoder_calib_nomicro()
    else:
        return None
    print('Passi encoder calcolati:', n360)
    return n360

def measure_t360(n360):
    'calcola tempo per giro completo'
    print(MISURA_TEMPO_ROTAZIONE)
    input('Premi <invio> per iniziare')
    safe_clear_counter(GLOB.handle)
    GLOB.handle.SetDigitalChannel(RIGHT_MOVE)
    tstart = time.time()
    while True:
        cnt = GLOB.handle.ReadCounter(ENCODER)
        if cnt >= n360:
            tend = time.time()
            break
        time.sleep(0.01)
    GLOB.handle.ClearDigitalChannel(RIGHT_MOVE)
    t360 = int(tend-tstart+0.5)
    print('Tempo per rotazione competa:', t360)
    return t360

DYN_HTIME = 12     # Half duration of dyn parameters measure

def _getint(prompt):
    'accetta valore intero'
    while True:
        print()
        ans = input(prompt)
        try:
            ret = int(ans)
        except ValueError:
            print('Valore intero non valido!')
        else:
            break
    return ret

def _getfloat(prompt):
    'accetta valore float'
    while True:
        print()
        ans = input(prompt)
        try:
            ret = float(ans)
        except ValueError:
            print('Valore float non valido!')
        else:
            break
    return ret

def measure_dyn():             #pylint: disable=R0914
    'Misura parametri dinamici cupola'
    input('Premi <invio> per iniziare')
    cnts = []
    tmes = []
    tpoll = GLOB.dyn_data['t360']/GLOB.dyn_data['n360']/5
    safe_clear_counter(GLOB.handle)
    GLOB.handle.SetDigitalChannel(RIGHT_MOVE)
    stoptime0 = time.time()+DYN_HTIME
    stoptime1 = stoptime0+DYN_HTIME
    idx = 0
    stopidx = 0
    while True:               # sample acceleration ramp
        tme = time.time()
        if stopidx == 0 and tme >= stoptime0:
            stopidx = idx
            GLOB.handle.ClearDigitalChannel(RIGHT_MOVE)
        if tme >= stoptime1:
            break
        idx += 1
        tmes.append(tme)
        cnts.append(GLOB.handle.ReadCounter(ENCODER))
        time.sleep(tpoll)
    tm0 = tmes[0]
    cn0 = cnts[0]
    tmes = [(x-tm0) for x in tmes]
    cnts = [(x-cn0) for x in cnts]
    GLOB.dyn_data.update({'times': tmes, 'counts': cnts, 'nstop': stopidx, 'tpoll': tpoll})

def measure_one_step(tstep):
    'Misura spostamento corrispondente a step di data durata'
    GLOB.handle.ClearAllDigital()
    safe_clear_counter(GLOB.handle)
    print('Tstep:', tstep, end=' ', flush=True)
    GLOB.handle.SetDigitalChannel(RIGHT_MOVE)
    print(' dome start ...', end=' ', flush=True)
    time.sleep(tstep)
    print(' dome stop ...', end=' ', flush=True)
    counts = safe_stop(RIGHT_MOVE)[1]
    print(' counts:', counts)
    return counts

def measure_steps(max_t):
    'Misura spostamento corrispondente a varie durate di step'
    times = [0.0]
    counts = [0]
    tstep = 0.5
    while True:
        if tstep > max_t:
            break
        times.append(tstep)
        counts.append(measure_one_step(tstep))
        tstep +=  0.5
    ptable = np.interp(np.arange(counts[-1]), counts, times)
    return ptable.tolist()

def save_data():
    'salva dati generati'
    if os.path.exists(DOME_DYN_FILE):
        savefile = DOME_DYN_FILE+'.bck'
        os.rename(DOME_DYN_FILE, savefile)
        print('Salvato file precedente:', savefile)
    if os.path.exists(DOME_DATA_FILE):
        savefile = DOME_DATA_FILE+'.bck'
        os.rename(DOME_DATA_FILE, savefile)
        print('Salvato file precedente:', savefile)
    with open(DOME_DYN_FILE, 'w', encoding='utf8') as f_out:
        json.dump(GLOB.dyn_data, f_out, indent=2)
    print('Dati dinamica salvati in:', DOME_DYN_FILE)
    with open(DOME_DATA_FILE, 'w', encoding='utf8') as out_f:
        json.dump(GLOB.dome_data, out_f, indent=2)
    print('Creato file:', DOME_DATA_FILE)

def print_all():
    'Stampa valore dei parametri'
    print(f'Dati calibrazione registrati il {GLOB.dome_data["savetime"]}')
    print()
    print(' - step encoder per giro:', GLOB.dome_data['n360'])
    print(f' - tempo per giro completo: {GLOB.dome_data["t360"]:.1f} s')
    print(f' - intervallo di campionamento: {GLOB.dome_data["tpoll"]:.3f} s')
    print(' - conteggi encoder per accelerazione:', GLOB.dome_data["nstart"])
    print(f' - tempo per accelerazione: {GLOB.dome_data["tstart"]:.2f} s')
    print(' - conteggi encoder per decelerazione:', GLOB.dome_data["nstop"])
    print(f' - tempo per decelerazione: {GLOB.dome_data["tstop"]:.2f} s')
    print(f' - intervallo per verifica stop (sec): {GLOB.dome_data["tsafe"]:.3f} s')
    print(f' - velocità massima: {GLOB.dome_data["vmax"]:.2f} conteggi/s')
    print(' - offset HOME - Nord:', GLOB.dome_data["hoffset"], 'conteggi')
    print(' - errore max inseguimento:', GLOB.dome_data["maxerr"], 'conteggi')
    print(f' - tempo di chiusura/apertura vano: {GLOB.dome_data["shuttime"]:.1f} s')
    print(' - num. elementi tabella impulsi per piccoli movimenti: ', len(GLOB.dome_data["ptable"]))

def accel_params(times, counts, nstop):
    'Calcola parametri della fase di accelerazione'
    times = times[:nstop]
    counts = counts[:nstop]
    err = float('inf')
    end_accel = 0
    guard = nstop/2
    while True:
        if end_accel > guard:
            print('Non converge!!!')
            return None, None
        line, res = np.polyfit(times[end_accel:],counts[end_accel:],1,full=True)[:2]
        res = res[0]/len(times[end_accel:])
        if res >= err:
            break
        err = res
        end_accel += 1
    vmax = line[0]
    return end_accel, vmax

def decel_params(times, counts, nstop):
    'Calcola parametri della fase di decelerazione'
    err = float('inf')
    end_decel = nstop
    guard = nstop+(len(times)-nstop)/2

    while True:
        if end_decel > guard:
            print('Non converge!!!')
            return None
        _unused, res = np.polyfit(times[end_decel:],counts[end_decel:],1,full=True)[:2]
        res = res[0]/len(times[end_decel:])
        if res >= err:
            break
        err = res
        end_decel += 1
    return end_decel

def do_plot(times, counts, end_accel, nstop, end_decel, xtsafe, ytsafe): #pylint: disable=R0913,R0914
    'Genera grafico'
    tacc = GLOB.dome_data['tstart']
    nacc = GLOB.dome_data['nstart']
    tdec = GLOB.dome_data['tstop']
    ndec = GLOB.dome_data['nstop']
    plt.figure(figsize=(6,10))
    ax0 = plt.subplot(311)
    ax0.plot(times, counts, 'b-')
    ax0.plot(times[0], counts[0], 'r+',
             label=f'Accel. (c:{nacc}, t:{tacc:.2f})', markersize=10)
    ax0.plot(times[end_accel], counts[end_accel], 'r+', markersize=10)
    ax0.plot(times[nstop], counts[nstop], 'g+',
             label=f'Decel. (c:{ndec}, t:{tdec:.2f})', markersize=10)
    ax0.plot(times[end_decel], counts[end_decel], 'g+', markersize=10)
    ax0.legend()
    ax0.set_ylabel('conteggi')
    ax0.set_xlabel('secondi')
    ax0.set_title('Parametri dinamici della cupola')
    textstr = f'Velocità massima: {GLOB.dome_data["vmax"]:.2f} cnt/s'
    ax0.text(0.95, 0.10, textstr, transform=ax0.transAxes,
             fontsize=10, verticalalignment='bottom', horizontalalignment='right',
             bbox={'facecolor': 'white', 'alpha': 0.5, 'pad': 10})
    ax0.grid()

    ax1 = plt.subplot(312)
    sta = nstop-20
    enda = end_decel+20
    tsafe = GLOB.dome_data['tsafe']
    ax1.plot(times[sta:enda], counts[sta:enda], 'b-')
    ax1.plot(times[nstop], counts[nstop], 'g+', markersize=10,
             label=f'decel. (c:{ndec}, t:{tdec:.2f})')
    ax1.plot(times[end_decel], counts[end_decel], 'g+', markersize=10)
    ax1.errorbar(xtsafe, ytsafe, yerr=(2, 2), color='k', label=f'attesa stop (t:{tsafe:.3f})')
    ax1.legend()
    ax1.grid()
    ax1.set_ylabel('conteggi')
    ax1.set_xlabel('secondi')
    ax1.set_title('Dettaglio decelerazione')

    ax2 = plt.subplot(313)
    ax2.plot(GLOB.dyn_data['ptable'])
    ax2.grid()
    ax2.set_title('Tabella impulsi')
    ax2.set_xlabel('conteggi')
    ax2.set_ylabel('secondi')
    plt.tight_layout()
    plt.savefig(DOME_PLOT_FILE, dpi=200)
    print('Figura salvata nel file:', DOME_PLOT_FILE)
    plt.show(block=False)

def main():                        #pylint: disable=R0912,R0914,R0915
    'Programma principale'
    if '-h' in sys.argv:
        print(__doc__)
        sys.exit()

    if '-k' in sys.argv:
        GLOB.handle = K8055Simulator()
        GLOB.simulation = True

    signal.signal(2, simulator_stop)

    try:
        with open(DOME_DATA_FILE, encoding='utf8') as f_in:
            GLOB.dome_data = json.load(f_in)
    except FileNotFoundError:
        GLOB.dome_data = {}
    GLOB.dome_data = {'parkaz': 0, 'domeaz': 0}

    if '-u' in sys.argv:
        with open(DOME_DYN_FILE, encoding='utf8') as f_in:
            GLOB.dyn_data = json.load(f_in)
    else:
        GLOB.dyn_data = {}
        GLOB.handle.OpenDevice(K8055_PORT)
        print(MISURA_N360)
        n360 = measure_n360()
        GLOB.dyn_data['n360'] = n360
        if n360 is not None:
            GLOB.dome_data['n360'] = n360
        print(MISURA_T360)
        t360 = measure_t360(n360)
        GLOB.dyn_data['t360'] = t360
        print(MISURA_DYN)
        measure_dyn()
        print(MISURA_HOME_OFFSET)
        ans = my_input('La cupola è dotata di microswitch di HOME (s/n)? ', 'sny')
        if ans in 'sy':
            hoffset = home_offset()
        else:
            hoffset = 0
        GLOB.dyn_data['hoffset'] = hoffset

    times = np.array(GLOB.dyn_data['times'])
    counts = np.array(GLOB.dyn_data['counts'])
    nstop = GLOB.dyn_data['nstop']
    end_accel, vmax = accel_params(times, counts, nstop)
    end_decel = decel_params(times, counts, nstop)

    GLOB.dome_data['hoffset'] = int(GLOB.dyn_data['hoffset'])
    GLOB.dome_data['n360'] = int(GLOB.dyn_data['n360'])
    GLOB.dome_data['t360'] = float(GLOB.dyn_data['t360'])
    GLOB.dome_data['tpoll'] = float(GLOB.dyn_data['t360']/GLOB.dyn_data['n360']/5)
    GLOB.dome_data['n360'] = int(GLOB.dyn_data['n360'])
    GLOB.dome_data['tstart'] = float(times[end_accel])
    GLOB.dome_data['nstart'] = int(counts[end_accel])
    GLOB.dome_data['tstop'] = float(times[end_decel]-times[nstop])
    GLOB.dome_data['nstop'] = int(counts[end_decel]-counts[nstop])
    GLOB.dome_data['vmax'] = float(vmax)

    stp = counts[1:]-counts[:-1]
    stptm = times[np.asarray(stp).nonzero()]    # istanti di transizione
    GLOB.dome_data['tsafe'] = (stptm[-1]-stptm[-2])*1.2
    ytsafe = counts[-1]+5
    ytsafe = (ytsafe, ytsafe)
    xtsafe = (stptm[-2], stptm[-2]+GLOB.dome_data['tsafe'])

    if '-u' not in sys.argv:
        t_accel = times[end_accel]
        max_t = t_accel+0.6
        print(SMALL_STEPS)
        ptable = measure_steps(max_t)
        GLOB.dyn_data['ptable'] = ptable

    GLOB.dome_data['ptable'] = GLOB.dyn_data['ptable']
    do_plot(times, counts, end_accel, nstop, end_decel, xtsafe, ytsafe)

    print(MANUAL_PARAMS)

    print(IMPULSO_BREVE)
    tshort = GLOB.dome_data.get('tshort')
    if tshort is not None:
        print(f'Valore attuale durata impulso breve: {tshort:.2f}')
    tshort = _getfloat('Nuova durata impulso per movimento breve? ')
    GLOB.dome_data['tshort'] = tshort

    print(ERRORE_POSIZIONE)
    maxerr = GLOB.dome_data.get('maxerr')
    if maxerr is not None:
        print(f'Valore attuale durata impulso breve: {maxerr}')
    ans = _getint('Max errore di posizione (conteggi)? ')
    maxerr = int(ans)
    GLOB.dome_data['maxerr'] = maxerr

    print(SHUT_TIME)
    shuttime = GLOB.dome_data.get('shuttime')
    if shuttime is not None:
        print()
        print(f'Valore attuale tempo chiusura/apertura vano (s): {shuttime}')
    ans = _getint('Tempo di chiusura/apertura vano (s)? ')
    shut_time = ans
    GLOB.dome_data['shuttime'] = shut_time

    GLOB.dome_data['savetime'] = time.strftime('%Y-%m-%d %H:%m:%S')
    print_all()

    if GLOB.simulation:
        GLOB.handle.stop()
    print()
    ans = my_input('Registro dati di calibrazione (s/n)? ', 'sny')
    if ans in 'ys':
        save_data()

if __name__ == '__main__':
    main()
