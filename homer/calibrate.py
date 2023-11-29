'''
calibrate.py

Calibrazione per Homer 2.0

Uso per test:

    python calibrate.py <image.fit> [executable]

Dove:
    <image.fit>:  nome file immagine
    executable:   eseguibile ASTAP (se non specificato, risolve
                  solo col metodo remoto
'''
import sys
import os
import math
import time
import subprocess
import json
from astroquery.astrometry_net import AstrometryNet

#ASTROMETRY_KEY = 'jsknghvdadfvxljk'       # Luca Naponiello
ASTROMETRY_KEY = 'cvnpxtttxrpqaqju'        # Luca Fini

AST_NET_TIMEOUT = 1200    # Timeout for Astrometry.net method
PSOLV_TIMEOUT = 180       # Timeout for PlateSolve method

RADTOARCSEC = 206264.80624709636
RADTODEG = 57.29577951308232
ARCSECTORAD = 4.84813681109536e-06
DEGTORAD = 0.017453292519943295

class MyQueue:                            # pylint: disable=R0903
    "Emulazione Queue per test"
    def put(self, what):                  # pylint: disable=R0201
        "Operazione put sulla coda"
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
        self.cd_11 = calib['matrix'][0][0]
        self.cd_12 = calib['matrix'][0][1]
        self.cd_21 = calib['matrix'][1][0]
        self.cd_22 = calib['matrix'][1][1]
        self.imagew = calib['imagew']
        self.imageh = calib['imageh']
        self.orient = calib['orient']
        self.scale = calib['scale']
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

    def transform(self, xpix, ypix):
        'calcola trasformazione pixel/WCS'
        d_ras = self.cd_11*xpix + self.cd_12*ypix
        d_dec = self.cd_21*xpix + self.cd_22*ypix
        return d_ras, d_dec

def parse(fname):
    'Parse lines from astap .ini file'
    ret = {}
    with open(fname, encoding='utf8') as f_in:
        for line in f_in:
            name, value = line.strip().split('=')
            if name == 'PLTSOLVD':
                if value == 'F':
                    return {}
                continue
            if name == 'CMDLINE':
                continue
            if name == 'DIMENSIONS':
                xdim, ydim = (int(x) for x in value.split('x'))
                ret['IMAGEW'] = xdim
                ret['IMAGEH'] = ydim
            else:
                ret[name] = float(value)
    return ret

def calibrate_astap(executable, impath, outq):   #nopylint: disable=R0914,R0913
    "Genera file di calibrazione usando astap"
    executable = os.path.abspath(executable)
    outq.put(('TMO', PSOLV_TIMEOUT))
    outq.put(('LOG', f'Calibrating via astap: {impath}'))
    command = [executable, '-f', impath]
    outq.put(('LOG', f'Command: {str(command)}'))
    outfn = os.path.splitext(impath)[0]
    outpath = outfn+'.ini'
    wcspath = outfn+'.wcs'
    time0 = time.time()
    try:
        subprocess.run(command, timeout=PSOLV_TIMEOUT, check=True)
    except Exception as exc:                               #pylint: disable=W0703
        elaps = time.time()-time0
        outq.put(('LOG', f'Solver exception: {str(exc)} after {elaps:.3f} sec'))
    else:
        elaps = time.time()-time0
    if os.path.exists(outpath):
        parsed = parse(outpath)
        os.unlink(outpath)
        try:
            os.unlink(wcspath)
        except FileNotFoundError:
            pass
        return parsed
    outq.put(('LOG', 'Error: ASTAP output file not found'))
    return None

def calibrate_astrometrynet(impath, outq):          #nopylint: disable=R0914
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

def calibrate(impath, outq, savepath, executable=None):    #pylint: disable=R0914
    'Called by homer to do calibration'
    time0 = time.time()
    impath = os.path.abspath(impath)
    if executable:
        ret = calibrate_astap(executable, impath, outq)
        method = 'ASTAP'
    else:
        ret = calibrate_astrometrynet(impath, outq)
        method = 'ASTROMETRY'
    elaps = time.time()-time0
    if ret:
        outq.put(('LOG', f'Solving process terminated in {elaps:.3f} sec'))
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
    if len(sys.argv) == 3:
        impath = sys.argv[1]
        executable = sys.argv[2]
        savefile = 'l_solved.json'
    elif len(sys.argv) == 2:
        impath = sys.argv[1]
        executable = None
        savefile = 'r_solved.json'
    else:
        print('Errore argomenti. Usa "-h" per aiuto')
        sys.exit()
    ret = calibrate(impath, MyQueue(), savefile, executable)
    if ret:
        print('Creato file:', savefile)
    return ret

if __name__ == "__main__":
    result = test()
