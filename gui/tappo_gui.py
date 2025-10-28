"""
tappo_gui.py -  GUI per tappo del telescopio

uso:
    python tappo.py [-d] [-D]

dove:
    -d:  abilita modo debug
    -D:  abilita debug comunicazione con arduino
"""

import sys
from pathlib import Path

import tkinter as tk
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# pylint: disable=C0413

from opc import tappo
import widgets as wg


FONT = ("helvetica", 14, "bold")

RED = "#ff4444"
GREEN = "#80ff00"
YELLOW = "#ffff66"
ORANGE = "#ffb266"
BLUE = "#004c99"
BLACK = "black"
WHITE = "white"
LIGHTGRAY = "#cccccc"
GRAY = "#888888"


class GLOB:  # pylint: disable=R0903
    "variablili locali"
    root = None
    debug = False
    refresh = 1  # GUI refresh period


def _debug(text):
    if GLOB.debug:
        print("GUI DBG>", text)


class Petal(tk.Frame):
    "Widget per stato petalo"

    def __init__(self, parent):
        super().__init__(parent, bg=BLACK)
        self.pbar = ttk.Progressbar(
            self, style="TProgressbar", orient="horizontal", length=150
        )
        self.pbar.pack(side=tk.LEFT, expand=1, fill=tk.X)
        self.position = tk.Label(self, text="", width=5, bg=BLUE, fg=WHITE)
        self.position.pack(side=tk.LEFT)
        tk.Label(self, text="  ", bg=BLACK)
        self.status = wg.ExpandLabel(
            self, text=" " * 10, font=FONT, bg=BLACK, fg=WHITE, padx=5
        )
        self.status.pack(side=tk.LEFT)

    def set_max(self, value):
        "Imposta fondo scala della barra"
        self.pbar.config(maximum=value)

    def set_status(self, position, color=None, status=""):
        "imposta posizione petalo"
        if position < 0:
            position = 0
            spos = ""
        else:
            spos = str(int(position * tappo.TO_DEGREES + 0.5))
        self.pbar["value"] = position
        if color is not None:
            self.status.config(fg=color)
        self.position.config(text=spos)
        self.status.config(text=" " + status + " ")


class TappoGui(tk.Frame):
    "pannello controllo tappo"

    def __init__(self, parent):
        super().__init__(parent, padx=10, pady=10, bg=BLACK)
        ptfr = tk.Frame(self)
        self.petals = []
        for _ in range(4):
            self.petals.append(Petal(ptfr))
        for petal in self.petals:
            petal.pack()
        ptfr.pack()
        btfr = tk.Frame(self, pady=5, bg=BLACK)
        self.openbt = tk.Button(
            btfr,
            text="Apri",
            pady=1,
            width=8,
            bg=BLACK,
            fg=WHITE,
            activeforeground=LIGHTGRAY,
            activebackground=GRAY,
            command=self.open,
        )
        self.openbt.pack(side=tk.LEFT)
        self.closebt = tk.Button(
            btfr,
            text="Chiudi",
            pady=1,
            width=8,
            bg=BLACK,
            fg=WHITE,
            activeforeground=LIGHTGRAY,
            activebackground=GRAY,
            command=self.close,
        )
        self.closebt.pack(side=tk.LEFT)
        tk.Label(btfr, text="", bg=BLACK).pack(side=tk.LEFT, expand=1, fill=tk.X)
        self.stopbt = tk.Button(
            btfr,
            text="Stop",
            pady=1,
            bg=BLACK,
            fg=WHITE,
            activeforeground=LIGHTGRAY,
            activebackground=GRAY,
            command=self.stop,
        )
        self.stopbt.pack(side=tk.LEFT)
        btfr.pack(expand=1, fill=tk.X)
        self.status_line = tk.Label(
            self, text="", border=1, bg=BLACK, fg=WHITE, relief=tk.RIDGE
        )
        self.status_line.pack(expand=1, fill=tk.X)

        self.update()

    def open(self, nptl=0):
        "chiamato da bottone apri e poi via after"
        if nptl >= 4:
            return
        _debug(f"Start opening petal {nptl}")
        self.openbt.config(state=tk.DISABLED)
        self.closebt.config(state=tk.DISABLED)
        tappo.start_opening(nptl)
        self.after(2000, self.open, nptl + 1)

    def close(self, nptl=0):
        "chiamato da bottone chiudi e poi via after"
        if nptl >= 4:
            return
        _debug(f"Start homing petal {nptl}")
        self.openbt.config(state=tk.DISABLED)
        self.closebt.config(state=tk.DISABLED)
        tappo.start_homing(nptl)
        self.after(2000, self.close, nptl + 1)

    def stop(self):
        "chiamato da bottone stop"
        _debug("Stop all petals")
        tappo.stop()

    def update(self):  # pylint: disable=R0912,R0915
        "aggiorna stato"
        stat4 = []
        for nptl in range(4):
            status, position = tappo.get_status(nptl)
            stat4.append(status)
            if status == tappo.CLOSING:
                self.petals[nptl].set_status(position, color=ORANGE, status=status)
            elif status == tappo.OPENING:
                self.petals[nptl].set_status(position, color=ORANGE, status=status)
            elif status == tappo.CLOSED:
                self.petals[nptl].set_status(position, color=GREEN, status=status)
            elif status in (tappo.ERROR, tappo.UNCONNECTED):
                self.petals[nptl].set_status(position, color=RED, status=status)
            elif status == tappo.OPEN:
                self.petals[nptl].set_status(position, color=YELLOW, status=status)
            elif status == tappo.CONNECTED:
                self.petals[nptl].set_status(position, color=YELLOW, status=status)
            else:
                self.petals[nptl].set_status(position, color=RED, status=status)
        if any(x == tappo.UNCONNECTED for x in stat4):
            self.openbt.config(state=tk.DISABLED)
            self.closebt.config(state=tk.DISABLED)
            self.stopbt.config(state=tk.DISABLED)
            _debug("Controller non connesso. Tenta connessione")
            ident = tappo.find_tty()
            if ident:
                _debug("Connessione attiva")
                self.status_line.config(text=ident)
                max_pos = tappo.max_angle()
                for nptl in range(4):
                    self.petals[nptl].set_max(max_pos)
                self.stopbt.config(state=tk.NORMAL)
            else:
                _debug("Connessione non attiva")
        if all(x == tappo.CONNECTED for x in stat4):
            _debug("Inizia homing")
            self.openbt.config(state=tk.DISABLED)
            self.closebt.config(state=tk.DISABLED)
            self.stopbt.config(state=tk.NORMAL)
            self.close()  # Per iniziare homing
        if any(x == tappo.OPEN for x in stat4):
            self.closebt.config(state=tk.NORMAL)
            self.stopbt.config(state=tk.NORMAL)
        if any(x == tappo.CLOSED for x in stat4):
            self.openbt.config(state=tk.NORMAL)
            self.stopbt.config(state=tk.NORMAL)
        if any(x in (tappo.CLOSING, tappo.OPENING) for x in stat4):
            self.openbt.config(state=tk.DISABLED)
            self.closebt.config(state=tk.DISABLED)
            self.stopbt.config(state=tk.NORMAL)
        if any(x == tappo.STOPPED for x in stat4):
            self.openbt.config(state=tk.NORMAL)
            self.closebt.config(state=tk.NORMAL)
            self.stopbt.config(state=tk.NORMAL)
        self.after(2000, self.update)


def main():
    "esecuzione programma"
    if "-h" in sys.argv:
        print(__doc__)
        sys.exit()
    if "-d" in sys.argv:
        GLOB.debug = True
        GLOB.refresh = 5
    _debug(f"Intervallo aggiornamento: {GLOB.refresh}")

    if "-D" in sys.argv:
        tappo.set_debug(GLOB.debug)

    GLOB.root = tk.Tk()

    styl = ttk.Style()
    styl.theme_use("default")
    styl.configure("Horizontal.TProgressbar", foreground=BLACK, background=BLACK)
    wdg = TappoGui(GLOB.root)
    wdg.pack()
    GLOB.root.mainloop()


if __name__ == "__main__":
    main()
