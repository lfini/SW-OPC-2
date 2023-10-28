"""
makelinks.py - Genera links per il lancio dei programmi
"""

import sys
import os
import tkinter as tk

__all__ = ['destdir', 'archivia_link', 'logger_link','makelinks', 'show_all',
           'PYWIN32', 'WINSHELL']

try:
    from win32com.client import Dispatch
except ImportError:
    PYWIN32 = False
else:
    PYWIN32 = True

try:
    import winshell
except ImportError:
    WINSHELL = False
else:
    WINSHELL = True

HOMEDIR = os.path.expanduser("~")
BASEDIR = os.path.join(HOMEDIR, "opc-soft")
PYTHONW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
LOGGER = "logger.py"
ARCHIVIA = "archivia.py"
LOGGERICONFILE = "opc_128.ico"
ARCHIVIAICONFILE = "remotearchive_128.ico"


VERIFICA = """
Verifica PATH calcolati
"""

def destdir(version):
    "Genera directory destinazione codice"
    return os.path.join(BASEDIR, version)

def scriptdir(version):
    "Genera directory con procedure principali"
    return os.path.join(destdir(version), "support")

def show_all(version):
    "Mostra valori variabili significative"
    print(VERIFICA)
    print(" ", "HOMEDIR:", HOMEDIR)
    print(" ", "BASESDIR:", BASEDIR)
    print(" ", "DESTDIR:", destdir(version))
    logger_path, logger_icon = logger_link(version)
    archivia_path, archivia_icon = logger_link(version)
    print(" ", "LOGGERPATH:", logger_path)
    print(" ", "LOGGERICON:", logger_icon)
    print(" ", "ARCHIVIAPATH:", archivia_path)
    print(" ", "ARCHIVIAICON:", archivia_icon)
    print(" ", "PYTHONW:", PYTHONW)
    print()

class VSelector(tk.Frame):
    "Widget per selezione directory"
    def __init__(self, master):
        super().__init__(master, padx=10, pady=10)
        dirs = [x for x in os.listdir(BASEDIR) if x.startswith("opc-")]
        dirs.sort()
        title = "Scegli la versione e premi 'Seleziona'"
        tk.Label(self, text=title).pack()
        tk.Label(self, text=" ").pack()
        self.choice = tk.StringVar()
        self.selection = ""
        box = tk.Frame(self)
        for ddd in dirs:
            last = tk.Radiobutton(box, text=ddd, value=ddd, variable=self.choice)
            last.pack(anchor=tk.W)
        box.pack()
        last.select()
        tk.Label(self, text=" ").pack()
        btbox = tk.Frame(self)
        tk.Button(btbox, text="Annulla", command=lambda: self.done(False)).pack(side=tk.LEFT)
        tk.Button(btbox, text="Seleziona", command=lambda: self.done(True)).pack(side=tk.LEFT)
        btbox.pack()

    def done(self, stat):
        "Termina selezione"
        if stat:
            self.selection = self.choice.get()
            if self.selection:
                makelinks(self.selection)
        self.destroy()

def makelink(workdir, linkname, linkpath, linkicon):
    "Crea un link (shortcut)"
    desktop = winshell.desktop()   # crea il link sul desktop
    shell = Dispatch('WScript.Shell')
    shortc = shell.CreateShortCut(os.path.join(desktop, f"{linkname}.lnk"))
    shortc.Targetpath = PYTHONW
    shortc.Arguments = linkpath
    shortc.WorkingDirectory = workdir
    shortc.IconLocation = linkicon
    shortc.save()

def fake_makelink(workdir, linkname, linkpath, linkicon):
    "Mostra link che sarebbe creato (per test no windows)"
    print()
    print('-- Link:')
    print('   CreateShortCut = ', f"..desktop\\{linkname}.lnk")
    print('   shortc.Targetpath =', PYTHONW)
    print('   shortc.Arguments =', linkpath)
    print('   shortc.WorkingDirectory =', workdir)
    print('   shortc.IconLocation =', linkicon)
    print()

def archivia_link(version):
    "Genera dati per link archivia"
    archivia_path = os.path.join(scriptdir(version), ARCHIVIA)
    archivia_icon = os.path.join(destdir(version), "opc", "icons", ARCHIVIAICONFILE)
    return archivia_path, archivia_icon

def logger_link(version):
    "Genera dati per link logger"
    logger_path = os.path.join(scriptdir(version), LOGGER)
    logger_icon = os.path.join(destdir(version), "opc", "icons", LOGGERICONFILE)
    return logger_path, logger_icon

def makelinks(version):
    "Crea i link necessari"
    domake = makelink if WINSHELL else fake_makelink
    logger_path, logger_icon = logger_link(version)
    archivia_path, archivia_icon = archivia_link(version)
    links = [("Archivia", archivia_path, archivia_icon),
             ("OPC", logger_path, logger_icon)]
    workdir = os.path.join(BASEDIR, version)
    for link in links:
        domake(workdir, *link)

def main():
    "Attiva versione software"
    root = tk.Tk()
    wdg = VSelector(root)
    wdg.pack()
    root.wait_window(wdg)
    print()
    print("Selezione:", wdg.selection)

if __name__ == '__main__':
    main()
