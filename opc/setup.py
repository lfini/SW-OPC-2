"""
setup.py - Installatore per Windows

Normalmente lanciato da setup.bat
"""

import os
import sys
import shutil
import tkinter as tk

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

from gui.installer import Installer
from opc.utils import get_version

TITLE = "OPC-software. Installazione"

MISSING = []

if not WIN32COM:
    MISSING.append("win32com")
if not WEBDAV:
    MISSING.append("webdavclient3")

_DRYRUN = False
if sys.platform != "win32":
    _DRYRUN = True


MISSING_MSG = """

 I seguenti moduli python non sono installati:

      %s

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

HOMEDIR = os.path.expanduser("~")
DESTDIR = os.path.join(HOMEDIR, "opc-sw", get_version().strip())
MAIN_PROC = "opc-gui.py"
OPCICONFILE = "opc_128.ico"
OPCGUIPATH = os.path.join(DESTDIR, 'gui', MAIN_PROC)
OPCICON = os.path.join(DESTDIR, "gui", "icons", OPCICONFILE)
PYTHONW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")

INST_GUI = Installer(title=TITLE, prefix=' ')

def make_pth(pkg_dir):
    "Crea i file .pth"
    found = ""
    for pth in sys.path:
        if pth.endswith("site-packages"):
            found = pth
    pth_file = os.path.join(found, "opc.pth")
    if not _DRYRUN:
        with open(pth_file, "w", encoding='utf-8') as f_out:
            print(pkg_dir, file=f_out)
    return pth_file

def message(msg):
    "Segnala mancanza win32com"
    INST_GUI.warning(msg)
    INST_GUI.waitmsg()

def copyfile(src, dest):
    "Copia un file creando le directory se necessario"
    if not _DRYRUN:
        targetdir = os.path.dirname(dest)
        os.makedirs(targetdir, exist_ok=True)
        shutil.copy(src, dest)

def makelinks(workdir, links):
    "Crea links sul desktop"
    desktop = winshell.desktop()                # genera link in Desktop
    shell = Dispatch('WScript.Shell')
    for link in links:
        shortc = shell.CreateShortCut(os.path.join(desktop, "{link[0]}.lnk"))
        shortc.Targetpath = PYTHONW
        shortc.Arguments = link[1]
        shortc.WorkingDirectory = workdir
        shortc.IconLocation = link[2]
        shortc.save()
        INST_GUI.addtext(f'Generato collegamento: Desktop -> {link[1]}')

if "-v" in sys.argv:
    INST_GUI.addtext(VERIFICA)
    INST_GUI.prefix('   ')
    INST_GUI.addtext(f"ROOTDIR: {ROOTDIR}")
    INST_GUI.addtext(f"HOMEDIR: {HOMEDIR}")
    INST_GUI.addtext(f"DESTDIR: {DESTDIR}")
    INST_GUI.addtext(f"OPCGUIPATH: {OPCGUIPATH}")
    INST_GUI.addtext(f"OPCICON: {OPCICON}")
    INST_GUI.addtext(f"PYTHONW: {PYTHONW}")
    INST_GUI.wait()
    sys.exit()

if "-s" in sys.argv:
    SHORTCUT = SHORTCUT_2%(PYTHONW, OPCGUIPATH, PYTHONW, OPCICON)
    INST_GUI.info(SHORTCUT)
    INST_GUI.waitmsg()
    sys.exit()

if "-d" in sys.argv:
    _DRYRUN = True

if MISSING:
    INST_GUI.warning(MISSING_MSG%", ".join(MISSING))
    INST_GUI.waitmsg()
    if not _DRYRUN:
        sys.exit()

if os.path.exists(DESTDIR):
    yesno = INST_GUI.askyesno(INSTALL_OVER)
    if not yesno:
        sys.exit()

TREE = os.walk(ROOTDIR)
for droot, dname, fnames in TREE:
    INST_GUI.addtext(f"Copyng files from: {droot} -> {DESTDIR}")
    PREF = len(droot)
    for fname in fnames:
        SRC = os.path.join(droot, fname)
        DEST = os.path.join(DESTDIR, SRC[PREF:])
        copyfile(SRC, DEST)

PTH_FILE = make_pth(DESTDIR)
INST_GUI.addtext(f"Creato file: {PTH_FILE}")

if WINSHELL:
    DESKTOP = winshell.desktop()                # genera link in Desktop
    SHELL = Dispatch('WScript.Shell')
    SHORTC = SHELL.CreateShortCut(os.path.join(DESKTOP, "OPC.lnk"))
    SHORTC.Targetpath = PYTHONW
    SHORTC.Arguments = OPCGUIPATH
    SHORTC.WorkingDirectory = DESTDIR
    SHORTC.IconLocation = OPCICON
    SHORTC.save()
    INST_GUI.addtext("Generato collegamento su Desktop")
    LINKS.append(("OPC", OPCGUIPATH, OPCICON))
    makelinks(DESTDIR, LINKS)
INST_GUI.info(OK)
INST_GUI.waitmsg()
