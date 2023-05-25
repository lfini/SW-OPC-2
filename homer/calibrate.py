"""
homercalib.py

Calibrazione per Homer 2.0

Uso per test:

    python calibrate.py <image.fit>
"""
import sys
import math
import numpy as np
from astropy.io import fits
from astroquery.astrometry_net import AstrometryNet

ASTROMETRY_KEY = 'jsknghvdadfvxljk'

SOLVE_TIMEOUT = 600    # Timeout for solve image (sec)

class GLOB:     # pylint: disable=R0903
    "Debug flag"
    debug = False

class MyQueue:                            # pylint: disable=R0903
    "Emulazione Queue per test"
    def put(self, what):                  # pylint: disable=R0201
        "Operazione put sulla coda"
        print("Q:", what)

def calibrate(image_path, outq, savepath):          #pylint: disable=R0914
    "Genera file di calibrazione"
    def send(code, what):
        "Invia messaggi al master"
        outq.put((code, what))

    if GLOB.debug:
        print("Start calibration test")
    # Definisco tempo attuale in utc e posizione dell'osservatorio
    ast = AstrometryNet()
    # API Key account di Luca Naponiello
    # E' normale che escano dei warning sulla chiave ed altro.. ignorateli
    ast.api_key = ASTROMETRY_KEY
    # Inserire la nuova immagine, se submission_id è vuoto
    send("LOG", f"Solving image ({image_path})")
    try:
        wcs_header = ast.solve_from_image(image_path, solve_timeout=SOLVE_TIMEOUT)
    except Exception as excp:                     # pylint: disable=W0703
        send("ERR", str(excp))
        return
    if wcs_header:
        send("LOG", 'Astrometry.net has successfully plate-solved the image.')
        # Prendi coefficienti della matrice di rotazione calcolata
        cd11 = wcs_header['CD1_1']
        cd12 = wcs_header['CD1_2']
        cd21 = wcs_header['CD2_1']
        cd22 = wcs_header['CD2_2']
        det = cd11*cd22 - cd12*cd21
        scale = 3600*math.sqrt(abs(det))
        send("LOG", f'Pix scale is: {scale:.5f} arcsec/pix')
        calibnew = fits.PrimaryHDU(np.arange(10))
        calibnew.header = wcs_header
        if det >= 0:
            parity = 1.
        else:
            parity = -1.
        ttt = parity * cd11 + cd22
        aaa = parity * cd21 - cd12
        orient = -math.degrees(math.atan2(aaa, ttt))
        send("LOG", f'Up is: {orient:.2f} degrees E of N')
        calibnew.header['ORIENT'] = f'{orient:.2f}'
        calibnew.writeto(savepath, overwrite=True)
        send("OK", savepath)
    else:
        send("ERR", "Could not solve field")

TESTFILE = "testcalib.fit"

def test():
    "Test calibrazione"
    if "-h" in sys.argv or len(sys.argv) != 2:
        print(__doc__)
        sys.exit()
    GLOB.debug = True
    calibrate(sys.argv[1], MyQueue(), TESTFILE)

if __name__ == "__main__":
    test()
