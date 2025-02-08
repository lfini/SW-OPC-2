"""
camsim.py - Simulatore di camera per tests di homer

Il programma genera versioni shiftate di un'immagine originale per simulare
l'acquisizione di dati con drift del telescopio.

uso:
     python camsim.py [-cnrw] [-d to_dir] [-i interval] [-s scal] [-x x_max] [-y y_max] cal_image

     python camsim.py -c [-d to_dir]

     python camsim.py [-d to_dir] -s percent

dove:
     cal_image   Nome file immagine di calibrazione
     -d to_dir   Directory di destinazione (default: ./__work__)
     -i interval Intervallo fra immagini successive (default: 10 s)
     -x x_max    Max shift in pixel lungo asse x (default: 10)
     -y y_max    Max shift in pixel lungo asse y (default: 5)

     -c          Cancella files generati dalla directory destinazione

     -n          Si arresta dopo aver generato n immagini. Se non specificato continua
                 a generare immagini e può essere arrestato con CTRL-C

     -r          Genera immagini con shift random in [-xy_max, xy_max]
                 Altrimenti usa x_max, y_max come incrementi costanti

     -s scal     Genera un file FITS con immagine scalata della percentuale data

     -w          Genera la prima immagine, poi aspetta invio per iniziare il loop

"""

import sys
import os
import random
import signal
import getopt
import time
import numpy as np
from astropy.io import fits
from PIL import Image

SCALED_FITS = 'image_scaled_{:d}.fit'

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

def doscale(infile, percent):
    'genera immagine con data scala'
    percent = int(percent)
    data0, hd0 = fits.getdata(infile, header=True)
    scale = percent*0.01
    ydim, xdim = data0.shape
    xdim = int(xdim*scale+1)
    ydim = int(ydim*scale+1)
    img = Image.fromarray(data0)
    simg = img.resize((xdim, ydim), resample=Image.Resampling.NEAREST)
    hdu = fits.PrimaryHDU(np.array(simg))
    del hd0['NAXIS1']
    del hd0['NAXIS2']
    outfile = SCALED_FITS.format(percent)
    hdu.header.update(hd0)
    hdu.writeto(outfile)
    print('Creato file:', outfile)

class Shifter:                           #pylint: disable=R0902,R0903
    'generatore di immagini shiftate'
    def __init__(self, imgdir, origfile, x_max, y_max, rand=False):    #pylint: disable=R0913
        self.imgtempl = os.path.join(imgdir, 'img_')+'{0:03d}.fit'
        self.img0, self.hd0 = fits.getdata(origfile, header=True)
        self.x_max = x_max
        self.y_max = y_max
        self.imgnum = 0
        self.rand = rand
        logname = os.path.join(imgdir, 'camsim.log')
        self.x_size = self.img0.shape[1]-2*self.x_max-1
        self.y_size = self.img0.shape[0]-2*self.y_max-1
        self.logfile = open(logname, 'w', encoding='utf8')   #pylint: disable=R1732
        print('Logfile:', logname)
        self._make(0, 0)

    def _make(self, xsh, ysh):
        'genera immagine con  dato shift (in pixel)'
        xofs = xsh+self.x_max
        yofs = ysh+self.y_max
        newimg = self.img0[yofs:yofs+self.y_size, xofs:xofs+self.x_size]
        imgpath = self.imgtempl.format(self.imgnum)
        hdu = fits.PrimaryHDU(newimg)
#       del self.hd0['NAXIS1']
#       del self.hd0['NAXIS2']
#       hdu.header.update(self.hd0)
        hdu.writeto(imgpath)
        log = f' {imgpath} - XY shift: ({xsh}, {ysh})'
        print(time.strftime('%Y-%m-%d %H:%M:%S'), log, file=self.logfile)
        print(log)
        self.imgnum += 1

    def new(self):
        'genera immagine con shift casuale'
        if self.rand:
            xsh = random.randrange(-self.x_max, self.x_max+1)
            ysh = random.randrange(-self.y_max, self.y_max+1)
        else:
            xsh = self.x_max
            ysh = self.y_max
        self._make(xsh, ysh)

ARGERR = 'Errore argomenti. Usa "-h" per informazioni'

def main():                        #pylint: disable=R0912,R0915,R0914
    'programma principale'
    if "-h" in sys.argv:
        print(__doc__)
        sys.exit()

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'cnrwd:i:s:x:y:')
    except getopt.error:
        print(ARGERR)
        sys.exit()

    destdir = '__work__'
    delay = 10
    x_max = 10
    y_max = 5
    cancella = False
    scale = None
    israndom = False
    nmax = 1000000
    mustwait = False

    for opt, val in opts:
        if opt == '-d':
            destdir = val
        elif opt == '-i':
            delay = int(val)
        elif opt == '-x':
            x_max = abs(int(val))
        elif opt == '-y':
            y_max = abs(int(val))
        elif opt == '-c':
            cancella = True
        elif opt == '-n':
            nmax = int(val)
        elif opt == '-r':
            israndom = True
        elif opt == '-w':
            mustwait = True
        elif opt == '-s':
            scale = abs(float(val))

    if cancella:
        clean(destdir)
        sys.exit()

    if not args:
        print(ARGERR)
        sys.exit()

    if scale is not None:
        doscale(args[0], scale)
        sys.exit()
    imgfile = args[0]
    print()
    print('CAMSIM - generazione immagini da:', imgfile)
    print(f'  Intervallo: {delay}, Max XY shift: (+-{x_max}, +-{y_max})')

    signal.signal(2, sghandler)

    shifter = Shifter(destdir, imgfile, x_max, y_max, rand=israndom)
    smalld = 0.5
    if mustwait:
        input('Premi <invio> per iniziare')
    while True:
        if not nmax:
            break
        nmax -= 1
        wait = int(delay/smalld)
        while wait:
            wait -= 1
            if not GLOB.goon:
                break
            time.sleep(smalld)
        if not GLOB.goon:
            break
        shifter.new()
    print()
    print('CAMSIM terminato')
    clean(destdir)

if __name__ == '__main__':
    main()
