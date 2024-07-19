"""
setup.py - Installatore per Windows

Normalmente lanciato da setup.cmd

Uso interattivo per test:

    python setup.py [-h] [-d]

Dove:

    -h:   mostra pagina di aiuto
    -d:   modo "dryrun", esegue la procedura senza copiare o modificare niente
"""

import os
import sys
import shutil

#pylint: disable=W0611
try:
    import winshell
except ImportError:
    WINSHELL = False
else:
    WINSHELL = True

try:
    from win32com.client import Dispatch
except ImportError:
    WIN32COM = False
else:
    WIN32COM = True

try:
    from webdav3.client import Client    # pylint: disable=W0611
except ImportError:
    WEBDAV = False
else:
    WEBDAV = True

ROOTDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOTDIR)

#pylint: disable=C0413
from gui.switch import makemainlink, makeswitchlink
from gui.switch import DESTDIR
from opc.utils import get_version

MISSING = []

if not WINSHELL:
    MISSING.append("winshell")
if not WIN32COM:
    MISSING.append("win32com")
if not WEBDAV:
    MISSING.append("webdavclient3")

WIN32 = sys.platform == "win32"

MISSING_MSG = """

 I seguenti moduli python non sono installati:

      {}

 Per l'installazione si può usare il comando:

       python -m pip install <nome-modulo>

"""

OK = """
Istallazione terminata (la cartella di installazione
può essere cancellata)
"""

VERIFICA = """
Verifica PATH calcolati:
"""

INSTALL_OVER = '''
La versione {} del software OPC risulta già installata.

Vuoi procedere comunque? (rispondendo "SI" sarà ripetuta
l'installazione eliminando quella precedente)
'''

NOT_ADMIN = '''
La procedura richiede privilegi di Amministratore.

Non è possibile proseguire
'''

VERSDIR = 'opc-'+get_version().strip()

class GLOB:                #pylint: disable=R0903
    'Global variables'
    gui = None
    dryrun = False

def makepth(pkg_dir):
    "Crea i file .pth"
    found = ""
    for pth in sys.path:
        if pth.endswith("site-packages"):
            found = pth
    if found:
        pth_file = os.path.join(found, "opc.pth")
        if not GLOB.dryrun:
            with open(pth_file, "w", encoding='utf-8') as f_out:
                print(pkg_dir, file=f_out)
        return pth_file
    return 'Non creato: manca directory in PYTHONPATH'

def copyfile(src, dest):
    "Copia un file creando le directory se necessario"
    if not GLOB.dryrun:
        targetdir = os.path.dirname(dest)
        os.makedirs(targetdir, exist_ok=True)
        shutil.copy(src, dest)

def main():                    #pylint: disable=R0912,R0915
    'script eseguibile'
    if '-h' in sys.argv:
        print(__doc__)
        sys.exit()

    if "-d" in sys.argv:
        GLOB.dryrun = True

    if MISSING:
        print(MISSING_MSG.format(", ".join(MISSING)))
        sys.exit()

    if os.path.exists(DESTDIR):
        print(INSTALL_OVER.format(VERSDIR))
        ans = input("Proseguo con l'installazione? ").strip().lower()[:1]
        if ans not in 'ys':
            sys.exit()

    tree = os.walk(ROOTDIR)
    for droot, _, fnames in tree:
        print(f"Copia file: {droot} -> {DESTDIR}")
        for fname in fnames:
            src = os.path.join(droot, fname)
            dest = os.path.join(DESTDIR, os.path.relpath(src, ROOTDIR))
            copyfile(src, dest)

#   try:
#       pth_file = makepth(DESTDIR)
#   except Exception as exc:            #pylint: disable=W0703
#       ret = f'Errore creazione file PTH: {exc}'
#   else:
#       ret = f'File PTH: {pth_file}'
#   GLOB.gui.addtext(ret)

    ret = makemainlink(VERSDIR)
    print(ret)
    ret = makeswitchlink(VERSDIR)
    print(ret)

if __name__ == '__main__':
    try:
        main()
    except Exception as excp:            #pylint: disable=W0703
        print(excp)
    else:
        print(OK)
    input('Premi <invio> per terminare')
