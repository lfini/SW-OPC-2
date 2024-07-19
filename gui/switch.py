"""
switch.py - Selezione versione attiva

Uso:

    python switch.py

"""

import os
import sys
import tkinter as tk

try:
    import winshell
    from win32com.client import Dispatch
except ImportError:
    WIN32 = False
else:
    WIN32 = True

ROOTDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOTDIR)

#pylint: disable=C0413
from opc import utils
from opc.constants import INSTALLROOT

TITLE = "OPC-Sel"

MAIN_PROC = "opc_gui.py"
OPCICONFILE = "opc_128.ico"

SWTSCRIPT = "switch.py"
SWTICONFILE = "swt_128.ico"

HOMEDIR = os.path.expanduser("~")
DESTDIR = os.path.join(HOMEDIR, "opc-sw", "opc-"+utils.get_version().strip())
PYTHONW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")

class GLOB:               # pylint: disable=R0903
    'Variabili globali'
    gui = None
    dryrun = False

LINK_YES = 'Generato collegamento a "{}" sul Desktop'
LINK_NO = 'No window!  Il collegamento {} non può essere creato'

NO_MODIF = 'Selezione annullata!'

PRE = '\n\n     '
POST = '     \n\n'

class SelActive(tk.Frame):
    'Popup per selezione versione'
    def __init__(self, master):
        super().__init__(master, padx=10, pady=10)
        tk.Label(self, text='Seleziona versione da attivare').pack()
        tk.Label(self, text='...e premi Ok').pack()
        intern = tk.Frame(self, padx=10, pady=10)
        self.vers = utils.installed_versions()
        self.selct = tk.IntVar()
        btb = None
        nver = None
        for nver, ver in enumerate(self.vers):
            btb = tk.Radiobutton(intern, text=ver+'      ', value=nver,
                                 variable=self.selct)
            btb.pack(anchor=tk.W)
        if nver is not None:
            self.selct.set(nver)
        tk.Label(intern, text=' ').pack()
        btnsf = tk.Frame(intern)
        tk.Button(btnsf, text='  Ok  ', width=7, command=self._sel).pack(side=tk.LEFT)
        tk.Button(btnsf, text='Annulla', width=7, command=self._ann).pack(side=tk.LEFT)
        btnsf.pack()
        intern.pack()
        self.version = None

    def _sel(self):
        self.version = self.vers[self.selct.get()]
        self.master.destroy()

    def _ann(self):
        self.version = None
        self.master.destroy()

def makelink(linkname, destdir, exepath, iconpath):
    'Crea link sul desktop'
    if WIN32:
        desktop = winshell.desktop()                # genera link in Desktop
        shell = Dispatch('WScript.Shell')
        shortc = shell.CreateShortCut(os.path.join(desktop, linkname))
        shortc.Targetpath = PYTHONW
        shortc.Arguments = exepath
        shortc.WorkingDirectory = destdir
        shortc.IconLocation = iconpath
        shortc.save()
        return LINK_YES.format(exepath)
    return LINK_NO.format(linkname)

def makeswitchlink(version):
    'crea link alla procedura di switch versione'
    destdir = os.path.join(INSTALLROOT, version)
    swtpath = os.path.join(destdir, 'gui', SWTSCRIPT)
    iconpath = os.path.join(destdir, 'gui', 'icons', SWTICONFILE)
    return makelink("switch-2.0.lnk", destdir, swtpath, iconpath)

def makemainlink(version):
    'crea link alla procedura principale'
    destdir = os.path.join(INSTALLROOT, version)
    opcguipath = os.path.join(destdir, 'gui', MAIN_PROC)
    opcicon = os.path.join(DESTDIR, "gui", "icons", OPCICONFILE)
    return makelink("opc-2.0.lnk", destdir, opcguipath, opcicon)

def main():
    'script eseguibile'
    root = tk.Tk()
    root.title(TITLE)
    wdg = SelActive(root)
    wdg.pack()
    root.mainloop()

    if wdg.version:
        ret = makemainlink(wdg.version)
    else:
        ret = NO_MODIF
    root = tk.Tk()
    tk.Label(root, text=PRE+ret+POST).pack()
    root.mainloop()

if __name__ == '__main__':
    main()
