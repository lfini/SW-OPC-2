"""
Invio file di log a server aruba


Uso per test:

    python sendlog.py  [-t]

Dove:
    -t  Richiedi elenco tokens e associate directory

    Lanciato senza argomenti esegue un generico test

"""

# pylint: disable = W0703
import os
import gzip
import tempfile
try:
    import requests
except ModuleNotFoundError:
    HAS_REQUESTS = False
else:
    HAS_REQUESTS = True

__version__ = "1.1"
__date__ = "febbraio 2023"
__author__ = "Luca Fini"

UPLOAD_URL = 'https://www.lfini.cloud/cgi-bin/F/token_upl.py'
TOKEN = '3a2fd68adb51f8ec1ebea2d4'

WRONG_SCRIPT_URL = 'https://www.lfini.cloud/cgi-bin/F/token.py'
WRONG_SITE_URL = 'https://non.existent.site/cgi-bin/what.py'

TEMP_DIR = tempfile.gettempdir()
CHUNKSIZE = 16*4096
TIMEOUT = 5

class ErrResp:                            # pylint: disable=R0903
    'Class for error return'
    def __init__(self, reason, text):
        self.ok = False                   # pylint: disable=C0103
        self.reason = reason
        self.text = text

def __upload(filepath, debug, url):
    'Invia file'
    fname = os.path.split(filepath)[1]
    zname = fname+'.gz'
    zpath = os.path.join(TEMP_DIR, zname)

    params = {'fname': zname,
              'token': TOKEN}
    if debug:
        params['d'] = 1

    with open(filepath, 'rb') as f_in, gzip.open(zpath, 'wb') as f_out:
        while True:
            chunk = f_in.read(CHUNKSIZE)
            if not chunk:
                break
            f_out.write(chunk)

    with open(zpath, 'rb') as infile:
        files = {'file': ("file_to_upload", infile, 'application/data')}
        try:
            resp = requests.post(url, files=files, params=params, timeout=TIMEOUT)
        except Exception as excp:
            resp = ErrResp('requests exception', str(excp))
    os.unlink(zpath)
    return resp.ok, resp.reason, resp.text

def sendlog(filepath, debug=False, url=UPLOAD_URL):
    'Invio file con controllo errore'
    if HAS_REQUESTS:
        return  __upload(filepath, debug, url)
    return (False, 'ModuleNotFoundError', 'No module named \'requests\'')

def main():
    'Test code'
    sfile = os.path.abspath(__file__)
    print()
    print('Test sending file')
    ret = sendlog(sfile, debug=True)
    print('   sendlog returns:', ret)
    print()
    print('Test with wrong script')
    ret = sendlog(sfile, debug=True, url=WRONG_SCRIPT_URL)
    print('   sendlog returns:', ret)
    print()
    print('Test with wrong site')
    ret = sendlog(sfile, debug=True, url=WRONG_SITE_URL)
    print('   sendlog returns:', ret)

if __name__ == "__main__":
    main()
