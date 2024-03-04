'''
installer.py - GUI di supporto per installazione
'''

import sys
import os
import tkinter as tk

ROOTDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOTDIR)

import gui.widgets as wg

LOOPTIME = 50

ERR_FG = 'black'
ERR_BG = '#ff4444'
WARN_FG = 'black'
WARN_BG = '#ffa500'
INFO_FG = 'black'
INFO_BG = '#ffff00'

class Installer:
    'Widget per display delle operazioni'
    def __init__(self, title='Installer', width=100, prefix='', **kwa):
        self.prefx = prefix
        self.root = tk.Tk()
        self.root.withdraw()
        self.mainw = tk.Toplevel(self.root)
        self.mainw.title(title)
        self.text = tk.Text(self.mainw, width=width, **kwa)
        self.text.pack()
        self.wdg = None
        self.yesno = None

    def prefix(self, prefix):
        'cambia prefisso linee'
        self.prefx = prefix
    def addtext(self, line, end='\n'):
        'inserisce una linea di testo'
        self.text.insert(tk.END, self.prefx+line+end)
        self.text.see(tk.END)

    def clear(self):
        'Clear testo completo'
        self.text.delete('1.0', tk.END)

    def _message(self, text, fgr, bgr):
        'Popup messaggio generico'
        self.wdg = wg.PopupText(self.mainw, text, border=2, relief=tk.RIDGE,
                           padx=10, pady=10, fg=fgr, bg=bgr)
        self.wdg.place(in_=self.mainw, relx=0.5, rely=0.5, anchor='center')
        self.wdg.lift()

    def error(self, text):
        'Popup per errori'
        self._message(text, ERR_FG, ERR_BG)

    def warning(self, text):
        'Popup per errori'
        self._message(text, WARN_FG, WARN_BG)

    def info(self, text):
        'Popup per errori'
        self._message(text, INFO_FG, INFO_BG)

    def askyesno(self, text):
        'Popup per messaggio cion richiesta Yes/no'
        wdg = wg.AskYesNo(self.mainw, text)
        wdg.place(in_=self.mainw, relx=0.5, rely=0.5, anchor='center')
        self.mainw.wait_window(wdg)
        return wdg.yesno

    def waitmsg(self):
        'Attende chiusura popup'
        if self.wdg is not None:
            self.mainw.wait_window(self.wdg)
        return None

    def wait(self):
        self.root.wait_window(self.mainw)

def main():
    'Procedura di test'
    inst = Installer()
    while True:
        ans = input('linea da aggiuingere (c: clear, e: errore, q: termina)? ').strip()
        if ans == 'q':
            break
        if ans == 'c':
            inst.clear()
        elif ans == 'e':
            inst.error('Esempio di messaggio di errore')
            inst.wait()
        else:
            inst.addtext(ans)

if __name__ == '__main__':
    main()
