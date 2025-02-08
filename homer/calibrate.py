'''
calibrate.py

Calibrazione per Homer 2.0

Uso per test:

    python calibrate.py [-r] [-k] <image>

Dove:
      -k     Salva i files generati dal solver

      -r     Usa plate solver remoto (Astrometry.net). Se non specificato
             usa solver locale (astap_cli.exe)

    <image>  nome file immagine
'''
import sys
import os
import shutil
import math
import time
import subprocess
import json
from astroquery.astrometry_net import AstrometryNet
from astropy.io import fits

#ASTROMETRY_KEY = 'jsknghvdadfvxljk'       # chiave di Luca Naponiello
ASTROMETRY_KEY = 'cvnpxtttxrpqaqju'        # chiave di Luca Fini

ASTAP_NAME_WIN = 'astap_cli.exe'   # nome eseguibile astap per Windows
ASTAP_NAME_LNX = 'astap_cli'       # path eseguibile astap per Linux

AST_NET_TIMEOUT = 1200    # Timeout for Astrometry.net method
PSOLV_TIMEOUT = 180       # Timeout for PlateSolve method

RADTOARCSEC = 206264.80624709636
RADTODEG = 57.29577951308232
ARCSECTORAD = 4.84813681109536e-06
DEGTORAD = 0.017453292519943295

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ASTAP_WIN = os.path.join(BASE_DIR, 'astap', ASTAP_NAME_WIN)
ASTAP_LNX = os.path.join(BASE_DIR, 'astap', ASTAP_NAME_LNX)
ASTAP_DB = os.path.join(BASE_DIR, 'astap', 'db')
ASTAP_EXE = ASTAP_WIN if sys.platform == 'win32' else ASTAP_LNX
L_SOLVED = os.path.join(BASE_DIR, 'astap', 'l_solved')

class MyQueue:                            # pylint: disable=R0903
    "Emulazione Queue per test"
    def __init__(self, silent=False):
        self.silent = silent

    def put(self, what):
        "Operazione put sulla coda"
        if self.silent:
            return
        print("Q:", what)

class Transformer:                            #pylint: disable=R0903,R0902
    'Trasforma coordinate da pixel a WCS'
    def __init__(self, calib_file):
        try:
            with open(calib_file, 'r', encoding='utf8') as f_in:
                calib = json.load(f_in)
        except Exception as exc:             #pylint: disable=W0703
            self.error = str(exc)
            return
        self.calib_file = os.path.abspath(calib_file)
        self.cd_11 = calib['matrix'][0][0]
        self.cd_12 = calib['matrix'][0][1]
        self.cd_21 = calib['matrix'][1][0]
        self.cd_22 = calib['matrix'][1][1]
        self.imagew = calib['imagew']
        self.imageh = calib['imageh']
        self.orient = calib['orient']
        self.scale = calib['scale']
        self.ras_deg = calib['ras_deg']
        self.dec_deg = calib['dec_deg']
        self.error = None

    def str_matrix(self):
        'returns transformation matrix as string'
        if self.error:
            return '--- error ---'
        return f'[[{self.cd_11:.6f}, {self.cd_12:.6f}], [{self.cd_21:.6f}, {self.cd_22:.6f}]]'

    def str_scale(self):
        'returns image scale as string'
        if self.error:
            return '--- error ---'
        return f'{self.scale:.4f}'

    def str_size(self):
        'returns image size as string'
        if self.error:
            return '--- error ---'
        return f'{self.imagew} x {self.imageh}'

    def str_orient(self):
        'returns image orientation as string'
        if self.error:
            return '--- error ---'
        return f'{self.orient:.4f}'

    def str_pos(self):
        'returns sky position as string'
        if self.error:
            return '--- error ---'
        return f'{self.ras_deg:.6f} {self.dec_deg:.6f} (RA, DE) deg.'

    def transform(self, xpix, ypix):
        'calcola trasformazione pixel/WCS'
        d_ras = self.cd_11*xpix + self.cd_12*ypix
        d_dec = self.cd_21*xpix + self.cd_22*ypix
        return d_ras, d_dec

ASTAP_KEYW = (b'CD1_1', b'CD1_2', b'CD2_1', b'CD2_2', b'CRVAL1', b'CRVAL2')

def parse(fname):
    'Parse lines from astap .ini file'
    ret = {}
# Workaround: si legge il file in binario, perché i nomi di file con caratteri "strani"
# in windows non risultano scritti in codifica utf8 e danno errori nel parsing
    with open(fname, mode='rb') as f_in:
        for line in f_in:
            name, value = line.strip().split(b'=')[:2]
            if name == b'PLTSOLVD':
                if value == b'F':
                    return {}
                continue
            if name in ASTAP_KEYW:
                ret[name.decode('ascii')] = float(value)
    return ret

def unlink(fname):
    'unlink ignorando errori'
    try:
        os.unlink(fname)
    except FileNotFoundError:
        pass

def calibrate_astap(impath, outq):   #nopylint: disable=R0914,R0913
    "Genera file di calibrazione usando astap"
    outq.put(('TMO', PSOLV_TIMEOUT))
    outq.put(('LOG', f'Calibrating via astap: {impath}'))
    command = [ASTAP_EXE, '-d', ASTAP_DB, '-o', L_SOLVED, '-f', impath]
    outq.put(('LOG', f'Command: {" ".join(command)}'))
    time0 = time.time()
    try:
        subprocess.run(command, timeout=PSOLV_TIMEOUT, check=True)
    except subprocess.CalledProcessError as exc:
        elaps = time.time()-time0
        outq.put(('LOG', f'Solver CalledProcessError exception after {elaps:.3f} sec'))
        outq.put(('LOG', f'EXC.STDOUT: {exc.stdout}'))
        outq.put(('LOG', f'EXC.STDERR: {exc.stderr}'))
    except Exception as exc:                               #pylint: disable=W0703
        elaps = time.time()-time0
        outq.put(('LOG', f'Solver generic exception: {str(exc)} after {elaps:.3f} sec'))
    else:
        elaps = time.time()-time0
    parsed = None
    inipath = L_SOLVED+'.ini'
    if os.path.exists(inipath):
        outq.put(('LOG', f'Parsing astap output file: {inipath}'))
        try:
            parsed = parse(inipath)
        except Exception as exc:       # pylint: disable=W0703
            outq.put(('LOG', f'Exception parsing solution: {str(exc)}'))
            outq.put(('LOG', 'Output file content:'))
            with open(inipath, mode='rb') as f_in:
                for line in f_in:
                    outq.put('LOG', ' - '+str(line).rstrip())
    else:
        outq.put(('LOG', 'Error: ASTAP output file not found'))
    return parsed

def calibrate_astrometrynet(impath, outq):
    "Genera file di calibrazione usando la API di astrometry.net"
    outq.put(('TMO', AST_NET_TIMEOUT))
    outq.put(('LOG', f'Calibrating via Astrometry.net: {impath}'))
    # Definisco tempo attuale in utc e posizione dell'osservatorio (???)
    ast = AstrometryNet()
    # API Key account di Luca Naponiello
    # E' normale che escano dei warning sulla chiave ed altro.. ignorateli
    ast.api_key = ASTROMETRY_KEY
    # Inserire la nuova immagine, se submission_id è vuoto
    try:
        wcs_header = ast.solve_from_image(impath, crpix_center=True, solve_timeout=AST_NET_TIMEOUT)
    except Exception as exc:                     # pylint: disable=W0703
        outq.put(('LOG', f'Solver exception: {str(exc)}'))
        return None
    return wcs_header

def calibrate(impath, outq, savepath, local=True, keep=False):    #pylint: disable=R0914,R0915
    'Called by homer to do calibration'
    time0 = time.time()
    impath = os.path.abspath(impath)
    hdr = fits.getheader(impath)
    imagew = hdr['NAXIS1']
    imageh = hdr['NAXIS2']
    if local:
        ret = calibrate_astap(impath, outq)
        method = 'ASTAP'
        inipath = L_SOLVED+'.ini'
        wcspath = L_SOLVED+'.wcs'
        try:
            if keep:
                shutil.move(inipath, '.')
                shutil.move(wcspath, '.')
            else:
                os.unlink(inipath)
                os.unlink(wcspath)
        except FileNotFoundError:
            pass
    else:
        ret = calibrate_astrometrynet(impath, outq)
        method = 'ASTROMETRY'
        if ret and keep:
            with open('r_solved.wcs', 'w', encoding='utf8') as fout:
                for key, val in ret.items():
                    print(f'{key}: {val}', file=fout)
    elaps = time.time()-time0
    if ret:
        outq.put(('LOG', f'Solving process terminated in {elaps:.3f} sec'))
        ret['IMAGEW'] = imagew
        ret['IMAGEH'] = imageh
        cd11 = ret['CD1_1']*3600    # Convert trasf.matrix in arcsec
        cd12 = ret['CD1_2']*3600
        cd21 = ret['CD2_1']*3600
        cd22 = ret['CD2_2']*3600
        ras = ret['CRVAL1']
        dec = ret['CRVAL2']
        det = cd11*cd22-cd12*cd21
        scale = math.sqrt(abs(det))
        parity = 1 if det >= 0 else -1
        ttt = parity*cd11+cd22
        aaa = parity*cd21-cd12
        orient = math.degrees(math.atan2(aaa, ttt))
        outq.put(('LOG', f'Trasf matrix: [[{cd11}, {cd12}], [{cd21}, {cd22}]]'))
        outq.put(('LOG', f'Orientation: {orient} degrees'))
        outq.put(('LOG', f'Pix scale: {scale} arcsec/pix'))
        outq.put(('LOG', f'RAS, DEC: {ras}, {dec} degrees'))
        outq.put(('LOG', f'IMAGEW: {ret["IMAGEW"]},  IMAGEH: {ret["IMAGEH"]}'))
        solved = {'matrix': [[cd11, cd12], [cd21, cd22]],
                  'image': impath, 'ras_deg': ras, 'dec_deg': dec,
                  'imagew': ret['IMAGEW'], 'imageh': ret['IMAGEH'],
                  'scale': scale, 'orient': orient, 'method': method}
        with open(savepath, 'w', encoding='utf8') as fout:
            json.dump(solved, fout)
            outq.put(("OK", savepath))
        return solved
    outq.put(('ERR', f'Solving process failed after {elaps:.3f} sec'))
    return None

def test():
    "Test calibrazione"
    if "-h" in sys.argv:
        print(__doc__)
        sys.exit()
    if len(sys.argv) < 2:
        print('\nErrore argomenti: usa -h per aiuto')
        sys.exit()
    keep = '-k' in sys.argv
    impath = sys.argv[-1]
    if not os.path.exists(impath):
        print(f'\nFile immagine non tovato [{impath}]')
        sys.exit()
    savefile = 'solved.json'
    if '-r' in sys.argv:
        islocal = False
    else:
        islocal = True
    ret = calibrate(impath, MyQueue(), savefile, islocal, keep)
    if ret:
        print('Creato file:', savefile)
    return ret

if __name__ == "__main__":
    result = test()
