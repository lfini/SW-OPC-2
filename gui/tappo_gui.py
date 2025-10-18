"""
tappo_gui.py -  GUI per tappo del telescopio

uso:
    python tappo.py [-d] [-D]

dove:
    -d:  abilita modo debug
    -D:  abilita debug comunicazione con aeduino
"""

import sys
from pathlib import Path

import tkinter as tk
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

#pylint: disable=C0413

from opc import tappo
import widgets as wg

# Comandi per controller tappo
GET_INFO = "v"

class GLOB:             #pylint: disable=R0903
    "variablili locali"
    root = None
    debug = False

def _debug(text):
    if GLOB.debug:
        print("DBG>", text)

class Petal(tk.Frame):
    "Widget per stato petalo"
    def __init__(self, parent, max_position):
        super().__init__(parent)
        self.init_led = wg.Led(self, color="gray", size=20)
        self.init_led.pack(side=tk.LEFT)
        self.pos = ttk.Progressbar(self, orient="horizontal", length=120, maximum=max_position)
        self.pos.pack(side=tk.LEFT, expand=1, fill=tk.X)

    def set_status(self, position=None, color=None):
        "imposta posizione petalo"
        if position is None:
            self.init_led.set(color)
            return False

        if position < 0:
            self.init_led.set("gray")
            position = 0
            success = False
        else:
            self.init_led.set("green")
            success = True
        self.pos['value'] = position
        return success


class TappoGui(tk.Frame):
    "pannello controllo tappo"
    def __init__(self, parent, max_position):
        super().__init__(parent)
        ptfr = tk.Frame(self)
        self.petals = []
        for _ in range(4):
            self.petals.append(Petal(ptfr, max_position))
        for petal in self.petals:
            petal.pack()
        self.max_pos = tappo.get_max_angle()
        ptfr.pack(expand=1, fill=tk.X)
        btfr = tk.Frame(self)
        self.apribt = tk.Button(btfr, text="Apri", pady=1, command=tappo.apri)
        self.apribt.pack(side=tk.LEFT)
        self.chiudibt = tk.Button(btfr, text="Chiudi", pady=1, command=tappo.chiudi)
        self.chiudibt.pack(side=tk.LEFT)
        self.stopbt = tk.Button(btfr, text="Stop", pady=1, command=self.stop)
        self.stopbt.pack(side=tk.LEFT)
        btfr.pack()
        self.status_line = tk.Label(self, text="", border=1, relief=tk.RIDGE)
        self.status_line.pack(expand=1, fill= tk.X)

        self.update()


    def stop(self):
        "interrompi moto"
        ret = tappo.send_command("S")
        self.status_line.config(text=tappo.REPLIES.get(ret, str(ret)))

    def update(self):
        "aggiorna stato"
        status = tappo.get_status()
        _debug(f"update status: {status}")
        self.status_line.config(text=status["global"])
        for nptl in range(4):
            if status["homing"][nptl] == tappo.HOMING:
                self.petals[nptl].set_status(color="yellow")
            elif status["homing"][nptl] == tappo.CLOSED:
                self.petals[nptl].set_status(None, color="green")
            elif status["homing"][nptl] == tappo.ERROR:
                self.petals[nptl].set_status(color="red")
            else:
                self.petals[nptl].set_status(color="gray")
            if (pos := status["positions"][nptl]) >= 0:
                self.petals[nptl].set_status(position=pos)
        if status["global"] == tappo.CLOSED:
            self.apribt.config(state=tk.NORMAL)
            self.chiudibt.config(state=tk.DISABLED)
        elif status["global"] == tappo.OPEN:
            self.apribt.config(state=tk.DISABLED)
            self.chiudibt.config(state=tk.NORMAL)
        else:
            self.apribt.config(state=tk.DISABLED)
            self.chiudibt.config(state=tk.DISABLED)
        self.after(1000, self.update)


def main():
    "esecuzione programma"
    if '-h' in sys.argv:
        print(__doc__)
        sys.exit()
    GLOB.debug = '-d' in sys.argv
    if '-D' in sys.argv:
        tappo.set_debug(GLOB.debug)
    tappo.init_serial()

    GLOB.root = tk.Tk()
    tappo.start_homing()
    max_pos = tappo.get_max_angle()
    wdg = TappoGui(GLOB.root, max_pos)
    wdg.pack()
    GLOB.root.mainloop()

if __name__ == "__main__":
    main()
