"""
camsim.py - Simulatore di camera per tests di homer

Il programma genera versioni shiftate di un'immagine originale per simulare l'acquisizione
di dati con drift del telescopio. Il programma continua a generare immagini fino a che
non viene fermato con CTRL-C

uso:
     python camsim.py [-f sample] [-d to_dir] [-i interval] [-x x_shift] [-y y_shift]

     python camsim.py -c [-d to_dir]

dove:
     -f sample   Nome file immagine campione (default: ./TestImage.fit)
     -d to_dir   Directory di destinazione (default: ./sci_data)
     -i interval Intervallo fra immagini successive (default: 10 s)
     -x x_shift  Max shift in pixel lungo asse x (default: 5)
     -y y_shift  Max shift in pixel lungo asse y (default: 5)

     -c          Cancella files generati dalla directory destinazione

"""

import sys
import os
import random
import signal
import getopt
import time
from astropy.io import fits

class GLOB:                       #pylint: disable=R0903
    'Stato globale'
    goon = True

def sghandler(*_unused):
    'Riceve i segnale CTRL-C'
    GLOB.goon = False

def clean(destdir):
    'Rimuove tutti i file da directory di lavoro'
    files = [f for f in os.listdir(destdir) if f.endswith('.fit')]
    if not files:
        print('Nessun file immagine su directory:', destdir)
        return
    print()
    print(f'Trovati {len(files )} files su directory:', destdir)
    ans = input('Vuoi cancellarli? ').lower()
    if ans[:1] not in 'sy':
        return
    for fname in files:
        fpath = os.path.join(destdir, fname)
        os.unlink(fpath)
    print(f'Cancellati {len(files)} file da:', destdir)


def main():                        #pylint: disable=R0912,R0915,R0914
    'programma principale'
    if "-h" in sys.argv:
        print(__doc__)
        sys.exit()

    try:
        opts = getopt.getopt(sys.argv[1:], 'cf:d:i:x:y:')[0]
    except getopt.error:
        print('Errore argomenti')
        sys.exit()

    imgfile = 'TestImage.fit'
    destdir = 'sci_data'
    delay = 10
    x_shift = 5
    y_shift = 5
    cancella = False

    for opt, val in opts:
        if opt == '-f':
            imgfile = val
        elif opt == '-d':
            destdir = val
        elif opt == '-i':
            delay = int(val)
        elif opt == '-x':
            x_shift = int(val)
        elif opt == '-y':
            y_shift = int(val)
        elif opt == '-c':
            cancella = True

    if cancella:
        clean(destdir)
        sys.exit()

    print()
    print('CAMSIM - generazione immagini da:', imgfile)
    print(f'  Intervallo: {delay}, Max XY shift: ({x_shift}, {y_shift})')
    img0, hd0 = fits.getdata(imgfile, header=True)

    signal.signal(2, sghandler)

    imgnum = 0
    smalld = 0.5
    x_size = img0.shape[1]-2*x_shift
    y_size = img0.shape[0]-2*y_shift
    while True:
        wait = int(delay/smalld)
        while wait:
            wait -= 1
            if not GLOB.goon:
                break
            time.sleep(smalld)
        if not GLOB.goon:
            break
        xsh = random.randrange(x_shift+1)
        ysh = random.randrange(y_shift+1)
        newimg = img0[ysh:ysh+y_size, xsh:xsh+x_size]
        imgname = f'img_{imgnum:03d}.fit'
        imgpath = os.path.join(destdir, imgname)
        hdu = fits.PrimaryHDU(newimg)
        for key, value in hd0.items():
            hdu.header[key] = value
        hdu.header['NAXIS1'] = x_size
        hdu.header['NAXIS2'] = y_size
        hdu.writeto(imgpath)
        print(f'  Creato file: {imgpath} - XY shift: ({xsh}, {ysh})')
        imgnum += 1
    print()
    print('CAMSIM terminato')
    clean(destdir)

if __name__ == '__main__':
    main()
