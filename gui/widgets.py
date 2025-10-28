"""
Widget ed utilities per GUI OPC
"""

#pylint: disable=C0302

import sys
import os
import math
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from opc import astro  # pylint: disable=C0413

# import opc.configure as config       # pylint: disable=C0413

__version__ = "1.11"
__date__ = "Marzo 2023"
__author__ = "Luca Fini"


# Colors

BLACK = "#000000"
BLUE_D = "#000055"
CYAN_L = "#e0ffff"
GRAY_DD = "#222222"
GRAY_D = "#444444"
GRAY = "#808080"
GREEN = "#33ff33"
GREEN_L = "#66ff66"
GREEN_LL = "#99ff99"
HOTPINK = "#f01d7f"
RED_L = "#ff8888"
RED_LL = "#ffcccc"
WHITE = "#ffffff"
YELLOW = "#eeffff"

BG_MENU_1 = "#ff9933"
BG_MENU_2 = "#f6f6f6"

# fonts

H1_FONT = "Helvetica 18 bold"
H2_FONT = "Helvetica 16 bold"
H3_FONT = "Helvetica 14 bold"
H4_FONT = "Helvetica 12 bold"
H5_FONT = "Helvetica 10 bold"  # (era: BD_FONT)
H12_FONT = "Helvetica 12"

#                 Button states
ON = "on"
OFF = "off"
GRAY = "gray"
GREEN = "green"
YELLOW = "yellow"
RED = "red"

#                 Button types
ONOFF = "onoff"
CIRCLE = "circle"
SQUARE = "square"
UP = "up"
DOWN = "down"
LEFT = "left"
RIGHT = "right"

SHAPES = (ONOFF, CIRCLE, SQUARE, UP, DOWN, RIGHT, LEFT)
SIZES = (48, 64)

FOURCOLORS = (GRAY, GREEN, YELLOW, RED)

STATE_MAP = {
    ONOFF: (OFF, ON),
    CIRCLE: FOURCOLORS,
    LEFT: FOURCOLORS,
    RIGHT: FOURCOLORS,
    SQUARE: FOURCOLORS,
    DOWN: FOURCOLORS,
    UP: FOURCOLORS,
}

NAN = float("nan")

INFO_CLR = "#eeeeee"
WARNING_CLR = "#ffffbb"
ERROR_CLR = "#ff9999"

MAX = 9223372036854775807
MIN = -9223372036854775806

UP_IMAGE_DATA = """R0lGODlhCgAKAOMKAAAAAAEBAQQGCAUICwYJDAcKDgkOFAoPFgoQGAsRGP//////////////////
/////yH+EUNyZWF0ZWQgd2l0aCBHSU1QACH5BAEKAA8ALAAAAAAKAAoAAAQf8MlJKRp1ApBf2kS2
bdUxAqF2cpK5CtI6PkZg33YRAQA7"""

DOWN_IMAGE_DATA = """R0lGODlhCgAKAOMMAAAAAAYHCQQIDQcJDAcKDAgLDgkNEwkOFAoPFQoPFgwSGgwVIP//////////
/////yH+EUNyZWF0ZWQgd2l0aCBHSU1QACH5BAEKAA8ALAAAAAAKAAoAAAQfcIlJp3og6/ze2VnQ
YeD4GBthktyaZMXatTIyyPgTAQA7"""

PLUS_IMAGE_DATA = """
R0lGODdhDAAMAOeeAAAAAAABAQEBAAABBQABBgMEBgAFDAMFCAUHCAEJFAYJDgcLEgMMGQsNEAEQ
IgoPFgoQGQITKAUTJwQUKA4WHg8YJAoZLRIcKBUcJRQdJw0fNxAlQRgmORsmMx4qOiAtPiUwPR0y
TiQzSCM3Tyo4SyI6Wiw+VC1EZDVEWDdHXjxMYTdOajdRcj1TbT1Wd0dac01edUtjgVJid2RkZGZm
ZlNphWdnZ2pqalNukVVukFxwiVtzkWNzhnV1dWl3iml5jmR6lHl5eXt7e3x8fH19fX5+fn9/f4CA
gG2Dn3CDmoGBgYKCgnqGloWFhXKIpHWKpX+JmHiLon6MnYuLi4GQpIKSqISYsoyZqo+ZpZCbqY2c
sJScpZGerZOfrpChtJ2jq5qksJylr6GmrZ+otKCptKKqtaWqsqarsaastKysrK2trauusayusKmv
tqyvsqyvs6+wsq2xt6+xtLCxs62yuLGysrGys7KysrOysrKztLOzsrOzs7SzsrSzs7G0t7S0tLW0
srS0tbW0s7O1tre1s7a2tbe2s7e2tLi2tLi3tbm3tLi4uLy5try6uL+/v8DAwMHBwcLCwsPDw8jI
yM3Nzc7Ozs/Pz9HR0dra2tvb29zc3N3d3d7e3t/f3///////////////////////////////////
////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////
/////////////////////////////////////////////////////ywAAAAADAAMAAAIVQAxCRxI
ENOiS3cS3tmzR+GdJggT7gFhQ+EeiBY7zLCIkeEfjQwZQpzYoUOBBiVB/Bk5o2UDEC1nrIy4UCNH
mntsSsQokeLNkHv+AL24qInRo0iFBAQAOw=="""

MINUS_IMAGE_DATA = """
R0lGODdhDAAMAOMPACgoKDk5OWJhYGdnZmhnZnt7e4SEhLKysrOzs7S0tLe3t9PT09jY2NnZ2dra
2v///ywAAAAADAAMAAAEL1CtSasz6Oi9G+Yg84GbiJwoeohJALxwgJiEYN/DPJLrTpo8jSmVOjQK
hqRyqYgAADs="""

_PERMANENT = {}  # Contenitore per immagini ad uso delle GUI

_ICONDIR = os.path.join(os.path.dirname(__file__), "icons")


# pylint: disable=R0913
class GLOB:  # pylint: disable=C0115,R0903
    root = None
    debug = False


def get_icon(name, size, color=""):
    "Alloca Photoimage per icona"
    if color:
        img_name = f"{name}_{size}_{color}.gif"
    else:
        img_name = f"{name}_{size}.gif"
    phimg = _PERMANENT.get(img_name)
    if not phimg:
        img_path = os.path.join(_ICONDIR, img_name)
        phimg = tk.PhotoImage(file=img_path)
        _PERMANENT[img_name] = phimg
    return phimg


def set_debug(enable=True):
    "Abilita/disabilita debug"
    GLOB.debug = bool(enable)
    if GLOB.debug:
        print("WDG DBG> debug enabled")


def set_position(wnd, xypos, rel=None):
    """
    Posiziona una window (root o Toplevel) in data posizione assoluta (o relativa ad altra window)

    xpos:   (pos.x, pos.y)  percentuale
    """
    swdt = wnd.winfo_screenwidth()
    shgt = wnd.winfo_screenheight()
    x_pix = int(xypos[0] * swdt + 0.4999)
    y_pix = int(xypos[1] * shgt + 0.4999)
    if rel:
        x_pix += rel.winfo_x()
        y_pix += rel.winfo_y()
    wdt = wnd.winfo_width()
    hgt = wnd.winfo_height()
    max_x = swdt - wdt
    max_y = shgt - hgt
    new_x = min(max(x_pix, 0), max_x)
    new_y = min(max(y_pix, 0), max_y)
    wnd.geometry(f"+{new_x}+{new_y}")


def show_help(master, dirpath, body):
    "Genera finestra per help"
    if isinstance(body, str):
        try:
            filename = os.path.join(dirpath, body + ".hlp")
            with open(filename, encoding="utf8") as in_f:
                sdict = eval(in_f.read())  # pylint: disable=W0123
                title = sdict.get("title")
                text = sdict.get("text")
        except FileNotFoundError:
            title = "Errore interno"
            text = f"Il file:\n\n    {filename}\n\nnon esiste!"
        except (SyntaxError, KeyError):
            title = "Errore interno"
            text = f"Errore di sintassi nel file:\n\n    {filename}"
    else:
        try:
            title = body["title"]
            text = body["text"]
        except KeyError:
            title = "Errore interno"
            text = "Errore di formato nell'argomento:\n\n    body"
    Message(master, text, title=title, position=(50, 50))


_UNITS = ["", "K", "M", "G", "T", "P"]


def _hfmt(abn, unt):
    "Funzione di supporto per hfmt()"
    if abn < 10:
        return f"{abn:.2f}{_UNITS[unt]}"
    if abn < 100:
        return f"{abn:.1f}{_UNITS[unt]}"
    return f"{int(abn+0.5)}{_UNITS[unt]}"


def hfmt(num, range=0):  # pylint: disable=W0622
    """
    Trasforma valore in stringa numerica + frango (K,M,G...)
    rango: rango iniziale, 0=unità, 1=Kilo, ecc."""
    sign = "" if num >= 0 else "-"
    abn = abs(num)
    if abn < 1000:
        return sign + _hfmt(abn, range)
    if abn < 1000000:
        return sign + _hfmt(abn * 0.001, range + 1)
    if abn < 1000000000:
        return sign + _hfmt(abn * 0.000001, range + 2)
    return sign + _hfmt(abn * 0.000000001, range + 3)


# def mod_config(master):
#    "Apre pannello per modifica configurazione"
#    tplvl = MyToplevel(master, position=(50, 50))
#    tplvl.title("Modifica configurazione")
#    wdg = config.MakeConfig(tplvl)
#    wdg.pack()
#    master.wait_window(wdg)
#    return wdg.success


class IMGS:  # pylint: disable=R0903
    "Per la persistenza delle immagini"
    up_image = None
    down_image = None
    plus_image = None
    minus_image = None


class WidgetError(Exception):
    "Exception per errori dei widget"


class ToolTip:
    "Tooltip per widget"

    def __init__(self, widget, text="widget info", position="NW"):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.close)
        self.x_offset = 0
        self.y_offset = 0
        if "N" in position:
            self.y_offset -= 20
        if "W" in position:
            self.x_offset -= 45
        if "S" in position:
            self.y_offset += 20
        if "E" in position:
            self.x_offset += 25
        self.twdg = None

    def enter(self, _unused=None):
        "Chiamata quando il focus è sul relativo widget"
        if not self.text:
            return
        xco = yco = 0
        xco, yco = self.widget.bbox("insert")[:2]
        xco += self.widget.winfo_rootx() + self.x_offset
        yco += self.widget.winfo_rooty() + self.y_offset
        # creates a toplevel window
        self.twdg = tk.Toplevel(self.widget)
        # Leaves only the label and removes the app window
        self.twdg.wm_overrideredirect(True)
        self.twdg.wm_geometry(f"+{xco}+{yco}")
        label = tk.Label(
            self.twdg,
            text=self.text,
            justify="left",
            background="yellow",
            relief="solid",
            borderwidth=1,
            font=("times", "10", "normal"),
        )
        label.pack(ipadx=1)

    def close(self, _unused=None):
        "Rimuove tooltip"
        if self.twdg:
            self.twdg.destroy()

    def set(self, text):
        "Cambia il testo del tool tip"
        self.text = text


def down_image(mode):
    "crea immagine per freccia in giu"
    if mode.startswith("a"):
        if not IMGS.down_image:
            IMGS.down_image = tk.PhotoImage(data=DOWN_IMAGE_DATA)
        return IMGS.down_image
    if not IMGS.minus_image:
        IMGS.minus_image = tk.PhotoImage(data=MINUS_IMAGE_DATA)
    return IMGS.minus_image


def up_image(mode):
    "crea immagine per freccia in su"
    if mode.startswith("a"):
        if not IMGS.up_image:
            IMGS.up_image = tk.PhotoImage(data=UP_IMAGE_DATA)
        return IMGS.up_image
    if not IMGS.plus_image:
        IMGS.plus_image = tk.PhotoImage(data=PLUS_IMAGE_DATA)
    return IMGS.plus_image


class LabelFrame(tk.Frame):  # pylint: disable=R0901
    "Frame con etichetta e widget generico"

    def __init__(self, master, label=None, label_side=tk.W, label_font=H4_FONT, **kw):
        super().__init__(master, **kw)
        self._side = label_side
        if label is not None:
            self.label = tk.Label(self, text=label, font=label_font)
        else:
            self.label = None
        self.widget = None

    def add_widget(self, widget, expand=None, fill=None):
        "Inserisce widget"
        if self.widget:
            raise WidgetError("Widget già definito")
        self.widget = widget
        if self._side == tk.N:
            if self.label:
                self.label.pack(side=tk.TOP, expand=expand, fill=fill)
            self.widget.pack(side=tk.TOP, expand=expand, fill=fill)
        elif self._side == tk.S:
            self.widget.pack(side=tk.TOP, expand=expand, fill=fill)
            if self.label:
                self.label.pack(side=tk.TOP, expand=expand, fill=fill)
        elif self._side == tk.E:
            self.widget.pack(side=tk.LEFT, expand=expand, fill=fill)
            if self.label:
                self.label.pack(side=tk.LEFT, expand=expand, fill=fill)
        else:
            if self.label:
                self.label.pack(side=tk.LEFT, expand=expand, fill=fill)
            self.widget.pack(side=tk.LEFT, expand=expand, fill=fill)

    def set_label(self, text):
        "Aggiorna testo della label"
        self.label.config(text=text)


class Controller(tk.Frame):  # pylint: disable=R0901,R0902
    "Widget per campo numerico con frecce +-"

    def __init__(           #pylint: disable=R0917
        self,
        master,
        value=0,
        width=5,
        lower=MIN,
        upper=MAX,  # pylint: disable=R0914
        font=H12_FONT,
        step=1,
        circular=False,
        mode="arrow",
        fmt="%d",
        invalid=" --",
        **kw,
    ):
        super().__init__(master, **kw)
        self.step = step
        self.value = value
        self.lower = lower
        self.upper = upper
        self.invalid = invalid
        self.fmt = fmt
        self.circular = circular
        self.entry = tk.Entry(self, width=width, font=font)
        self.entry.pack(side=tk.LEFT)
        btframe = tk.Frame(self)
        self.bup = tk.Button(btframe, image=up_image(mode), command=self.incr)
        self.bup.pack()
        self.bdown = tk.Button(btframe, image=down_image(mode), command=self.decr)
        self.bdown.pack()
        btframe.pack(side=tk.LEFT)
        self.set(value)

    def config(self, **kw):
        "config reimplementation"
        if "state" in kw:
            self.bup.config(state=kw["state"])
            self.bdown.config(state=kw["state"])
            del kw["state"]
        super().config(**kw)

    def set(self, value):
        "imposta valore Controller"
        try:
            self.value = float(value)
        except ValueError:
            self.value = None
            self.entry.delete(0, tk.END)
            self.entry.insert(0, self.invalid)
            return
        if math.isnan(self.value):
            self.entry.delete(0, tk.END)
            self.entry.insert(0, "NaN")
            return
        if value > self.upper:
            if self.circular:
                value = self.lower
            else:
                value = self.upper
        elif value < self.lower:
            if self.circular:
                value = self.upper
            else:
                value = self.lower
        self.value = value
        self.entry.delete(0, tk.END)
        self.entry.insert(0, self.fmt % value)

    def get(self):
        "riporta valore Controller"
        return float(self.entry.get())

    def incr(self):
        "incrementa valore Controller"
        newval = self.get() + self.step
        self.set(newval)

    def decr(self):
        "decrementa valore Controller"
        newval = self.get() - self.step
        self.set(newval)


class Announce(tk.Frame):  # pylint: disable=R0901
    "Classe per linee con scroll"

    def __init__(self, master, nlines, width=54, **kargs):
        "Costruttore"
        super().__init__(master, **kargs)
        self.lines = []
        while nlines:
            self.lines.append(
                Field(self, border=0, width=width, font=H12_FONT, expand=1, fill=tk.X)
            )
            nlines -= 1
        for llne in self.lines:
            llne.pack(expand=1, fill=tk.X)
        self.nextid = 0

    def _scrollup(self):
        "Scroll lines up one step"
        for nline, dest in enumerate(self.lines[:-1]):
            src = self.lines[nline + 1]
            text = src.cget("text")
            fgc = src.cget("fg")
            dest.config(text=text, fg=fgc)

    def writeline(self, line, fgcolor):
        "Aggiunge una linea"
        if self.nextid == len(self.lines):
            self._scrollup()
            self.nextid -= 1
        self.lines[self.nextid].config(text=line, fg=fgcolor)
        self.nextid += 1

    def clear(self):
        "Azzera il widget"
        for line in self.lines:
            line.config(text="")
        self.nextid = 0


# Selettori tipo coordinate
HMS = 1
DMS = 2


class CoordEntry(tk.Frame):  # pylint: disable=R0901
    "Widget per coordinate"

    def __init__(self, master, label, ctype, width=2, editable=True):           #pylint: disable=R0917
        super().__init__(master)
        tk.Label(self, text=label).pack(side=tk.LEFT)
        self.ctype = ctype
        if ctype == HMS:
            seps = ("h", "m", "s")
        else:
            seps = ("°", "'", '"')
        state = "normal" if editable else "normal"
        self.deg = tk.Entry(self, width=width, state=state)
        self.deg.pack(side=tk.LEFT)
        tk.Label(self, text=seps[0]).pack(side=tk.LEFT)
        self.mnt = tk.Entry(self, width=2, state=state)
        self.mnt.pack(side=tk.LEFT)
        tk.Label(self, text=seps[1]).pack(side=tk.LEFT)
        self.sec = tk.Entry(self, width=2, state=state)
        self.sec.pack(side=tk.LEFT)
        tk.Label(self, text=seps[2]).pack(side=tk.LEFT)

    def value_dms(self):
        "Riporta valore campi: (deg, min, sec)"
        try:
            deg = int(self.deg.get())
            mnt = int(self.mnt.get())
            sec = int(self.sec.get())
        except:  # pylint: disable=W0702
            return ()
        return (deg, mnt, sec)

    def value_rad(self):
        "Riporta valore campi in radianti"
        ret = self.value_dms()
        if ret:
            if self.ctype == HMS:
                return astro.hms2rad(*ret)  # pylint: disable=E1120
            return astro.dms2rad(*ret)  # pylint: disable=E1120
        return float("nan")

    def set(self, value):
        "Assegna il valore"
        self.clear()
        sign, ddd, mmm, sss = astro.float2ums(value)
        ssgn = "-" if sign < 0 else "+"
        self.deg.insert(0, f"{ssgn}{int(ddd)}")
        self.mnt.insert(0, f"{int(mmm):02d}")
        self.sec.insert(0, f"{int(sss):02d}")

    def clear(self):
        "Azzera il widget"
        self.deg.delete(0, tk.END)
        self.mnt.delete(0, tk.END)
        self.sec.delete(0, tk.END)


class Led(tk.Frame):  # pylint: disable=R0901
    "Led di vari colori"

    def __init__(self, master, border=2, color=None, size=10):
        if not color:
            color = master["bg"]
        super().__init__(
            master, width=size, height=size, border=border, bg=color, relief=tk.RAISED
        )

    def set(self, color):
        "Imposta colore del Led"
        if not color:
            color = self.master["bg"]
        self.config(bg=color)


class CButton(LabelFrame):  # pylint: disable=R0901
    "Bottone colorabile con etichetta opzionale"

    def __init__(           #pylint: disable=R0917
        self,
        master,
        name,
        text="",
        color=None,
        font=H4_FONT,
        width=None,
        command=None,
        padx=None,
        pady=None,
        label=None,
        label_side=tk.W,
        label_font=H4_FONT,
        **kw,
    ):
        super().__init__(
            master, label=label, label_side=label_side, label_font=label_font, **kw
        )
        self.name = name
        if command:
            _command = lambda name=name: command(name)
        else:
            _command = None
        self.button = tk.Button(
            self,
            text=text,
            font=font,
            width=width,
            padx=padx,
            pady=pady,
            command=_command,
        )
        self.add_widget(self.button)
        if color:
            self.defc = color
        else:
            self.defc = self.cget("bg")
        self.set(self.defc)

    def set(self, color):
        "Imposta colore del bottone"
        if color:
            self.button.config(bg=color, activebackground=color)
        else:
            self.button.config(bg=self.defc, activebackground=self.defc)

    def clear(self):
        "Azzera  bottone"
        self.set(None)


class MButton(tk.Button):  # pylint: disable=R0901
    "Bottone Multi-icona a piu stati"

    def __init__(self, master, name, shape, size, value=None, command=None, **kw):          #pylint: disable=R0917
        self.name = name
        self.status = 0
        self.shape = shape
        self.size = size
        self.states = STATE_MAP[shape]
        image0 = get_icon(shape, size, self.states[0])
        super().__init__(master, image=image0, **kw)
        ncommand = None if command is None else lambda x=name: command(x)
        super().__init__(master, command=ncommand, **kw)
        if value:
            self.set(value)

    def nstates(self):
        "Riporta numero di stati definiti"
        return len(self.states)

    def get(self):
        "Riporta stato corrente"
        return self.status

    def set(self, status):
        "Imposta stato del bottone"
        if isinstance(status, str):
            idx = self.states.index(status)
        else:
            if self.shape == ONOFF:
                idx = 1 if status else 0
            else:
                idx = status
        self.status = idx
        self.config(image=get_icon(self.shape, self.size, self.states[idx]))

    def clear(self):
        "Azzera bottone"
        self.set(0)


class FrameTitle(tk.Frame):  # pylint: disable=R0901
    "Frame con titolo"

    def __init__(self, master, title, font=H1_FONT, **kw):
        super().__init__(master, padx=5, pady=5, **kw)
        self.title = tk.Label(self, text=title, font=font)
        self.title.pack(expand=1, fill=tk.X)
        self.body = tk.Frame(self)
        self.body.pack(expand=1, fill=tk.BOTH)


class Field(tk.Label):  # pylint: disable=R0901
    "Widget per display di stringa generica"

    def __init__(           #pylint: disable=R0917
        self,
        master,
        bg="black",
        fg="lightgreen",
        font="TkDefaultFont",
        width=10,
        text="",
        border=1,
        relief=tk.SUNKEN,
        **kws,
    ):
        super().__init__(
            master,
            text=text,
            bg=bg,
            fg=fg,
            width=width,
            font=font,
            border=border,
            relief=relief,
            **kws,
        )

    def get(self):
        "recupera contenuto campo"
        return self.cget("text")

    def set(self, value, **kw):
        "Imposta valore campo"
        if not value:
            self.clear()
        else:
            self.config(text=value, **kw)

    def clear(self, clear="", **kw):
        "Azzera campo"
        self.config(text=clear, **kw)


class Number(Field):  # pylint: disable=R0901
    "Widget per display di valore numerico"

    def __init__(self, master, /, value=None, fmt="%d", invalid="", **kw):
        super().__init__(master, **kw)
        self.fmt = fmt
        self.invalid = invalid
        self.value = None
        self.set(value)

    def set(self, value, **kw):  # pylint: disable=W0221
        "Imposta valore del campo"
        if value is None or math.isnan(value):
            self.clear(clear=self.invalid, **kw)
            self.value = None
        else:
            self.value = value
            svalue = self.fmt % value
            Field.set(self, svalue, **kw)

    def get(self):
        "Riporta valore del campo"
        return self.value


class Coord(Field):  # pylint: disable=R0901
    "Classe per display di coordinata"

    def __init__(self, master, value=None, mode="°", precision="s", invalid="", **kw):          #pylint: disable=R0917
        """
        Parametri
        ---------
        master : widget
            widget padre
        value : float
            valore della coordinata in decimale (None: cancella)
        mode : str
            ':' (generic) : ..:..:..
            'd' (degrees) : ..°..'.."
            ,h, (ore) ccordinata ..h..m..s
        precision : str
            's': secondi
            'm': minuti
        invalid : str
            string to use for invalid values (default='')

        gli argomenti seguenti vengono passati al widget Entry
        """
        super().__init__(master, **kw)
        if precision == "s":
            self.func = lambda x: astro.float2ums(x, as_string=mode)
        else:
            self.func = lambda x: astro.float2um(x, as_string=mode)
        self.invalid = invalid
        self.set(value)

    def set(self, value, **kw):  # pylint: disable=W0221
        "Imposta valore"
        try:
            strv = self.func(value)
        except:  # pylint: disable=W0702
            self.value = None
            self.clear(clear=self.invalid, **kw)
            return
        self.value = value
        Field.set(self, strv, **kw)

    def get(self):
        "Riporta valore numerico widget"
        return self.value


class MyToplevel(tk.Toplevel):
    """Toplevel posizionabile con metodo quit

    position = "center" or (x, y)
    """

    def __init__(self, master, title=None, position=None, **kw):
        super().__init__(master, **kw)
        if title:
            self.title(title)
        if isinstance(position, str) and position.startswith("c"):
            self.position = "c"
        elif isinstance(position, (tuple, list)) and len(position) == 2:
            self.position = position
        else:
            self.position = None
        self.bind("<Visibility>", self._vis_event)
        self._posfree = True

    def _vis_event(self, event):
        "Event server per cambiamento visibilità"
        if event.state == "VisibilityUnobscured" and self.position and self._posfree:
            if self.position == "c":
                xp0 = self.master.winfo_rootx() + int(
                    0.5 * (self.master.winfo_width() - self.winfo_width())
                )
                yp0 = self.master.winfo_rooty() + int(
                    0.5 * (self.master.winfo_height() - self.winfo_height())
                )
            else:
                xp0 = self.master.winfo_rootx() + self.position[0]
                yp0 = self.master.winfo_rooty() + self.position[1]
            xp0 = max(xp0, 0)
            yp0 = max(yp0, 0)
            xp0 = min(xp0, self.winfo_screenwidth() - self.winfo_width())
            yp0 = min(yp0, self.winfo_screenheight() - self.winfo_height())
            self.geometry(f"+{xp0}+{yp0}")
            self._posfree = False
            if GLOB.debug:
                print("WDG DBG> position =", repr(self.position))
                print(
                    "WDG DBG> self.master.winfo(rootx,rooty) =",
                    (self.master.winfo_rootx(), self.master.winfo_rooty()),
                )
                print(
                    "WDG DBG> self.master.winfo(wdt, hgt) =",
                    (self.master.winfo_width(), self.master.winfo_height()),
                )
                print(
                    "WDG DBG> self.winfo(wdt, hgt) =",
                    (self.winfo_width(), self.winfo_height()),
                )
                print("WDG DBG> (xp0, yp0) =", (xp0, yp0))


class MessageText(tk.Text):  # pylint: disable=R0901
    "display di messaggi"

    def __init__(self, master, msg, **kwa):
        lines_len = tuple(len(x) for x in msg.split("\n"))
        n_lines = len(lines_len)
        n_chars = max(lines_len)
        kwa["height"] = n_lines
        kwa["width"] = n_chars
        super().__init__(master, **kwa)
        self.insert(tk.END, msg)


class PopupText(MessageText):       #pylint: disable=R0901
    "Display di messaggi, kill on click e con tempo di espirazione"

    def __init__(self, master, msg, lifetime=0, **kwa):
        super().__init__(master, msg, **kwa)
        self.bind("<Button-1>", self.killme)
        if lifetime > 0:
            lifetime = int(lifetime * 1000)
            self.after(lifetime, self.destroy)

    def killme(self, _ev):
        "callback for left-click"
        self.destroy()


class AskYesNo(tk.Frame):
    "display di messaggi con richiesta YesNo"

    def __init__(self, master, msg, **kwa):
        super().__init__(master)
        MessageText(self, msg, **kwa).pack()
        btf = tk.Frame(self)
        tk.Button(btf, text="No", command=lambda x=False: self._yesno(x)).pack(
            side=tk.LEFT
        )
        tk.Button(btf, text="Si", command=lambda x=True: self._yesno(x)).pack(
            side=tk.LEFT
        )
        btf.pack()
        self.yesno = None

    def _yesno(self, yno):
        self.yesno = yno
        self.destroy()


class Message(MyToplevel):
    "Display di messaggio (in Toplevel)"

    def __init__(           #pylint: disable=R0917
        self,
        master,
        msg,
        title=None,
        position=None,
        font=None,
        fg=None,
        bg=None,
        button="Chiudi",
    ):
        super().__init__(master, title=title, position=position)
        self.text = MessageText(self, msg, font=font, fg=fg, bg=bg)
        self.text.pack()
        self.status = None
        if button:
            tk.Button(self, text=button, command=self.destroy).pack(pady=4)


class InfoMsg(Message):  # pylint: disable=R0901
    "Display di messaggio informativo"

    def __init__(self, master, msg, title="Info", position=(30, 30), **kwd):
        super().__init__(master, msg, title=title, position=position, **kwd)
        self.config(bg=INFO_CLR)


class WarningMsg(Message):  # pylint: disable=R0901
    "Display di messaggio warning"

    def __init__(self, master, msg, title="Warning", position=(30, 30), **kwd):
        super().__init__(master, msg, title=title, position=position, **kwd)
        self.config(bg=WARNING_CLR)


class ErrorMsg(Message):  # pylint: disable=R0901
    "Display di messaggio errore"

    def __init__(self, master, msg, title="Error", position=(30, 30), **kwd):
        super().__init__(master, msg, title=title, position=position, **kwd)
        self.config(bg=ERROR_CLR)


class YesNo(Message):  # pylint: disable=R0901
    "Display di messaggio con scelta opzioni Si/No"

    def __init__(self, master, msg, position=(30, 30), **kwd):
        kwd["button"] = ""
        super().__init__(master, msg, position=position, **kwd)
        bot_frame = tk.Frame(self)
        tk.Button(bot_frame, text="Si", command=lambda x=True: self._quit(x)).pack(
            side=tk.LEFT
        )
        tk.Button(bot_frame, text="No", command=lambda x=False: self._quit(x)).pack(
            side=tk.LEFT
        )
        bot_frame.pack()

    def _quit(self, isyes):
        self.status = isyes
        self.destroy()


class SelectionMsg(Message):  # pylint: disable=R0901
    "Display di messaggio con scelta opzioni"

    def __init__(self, master, msg, choices=None, **kwd):
        kwd["button"] = ""
        super().__init__(master, msg, **kwd)
        bot_frame = tk.Frame(self)
        for nbutt, choice in enumerate(choices):
            tk.Button(
                bot_frame, text=choice, command=lambda x=nbutt: self._quit(x)
            ).pack(side=tk.LEFT)
        bot_frame.pack()

    def _quit(self, nbutt):
        self.status = nbutt
        self.destroy()


class Progress(MyToplevel):
    "Indicatore di progresso toplevel"
    LOOPTIME = 100  # loop time in millisec

    def __init__(           #pylint: disable=R0917
        self, master, pre="", post="", length=280, title="", position=None, duration=0
    ):
        super().__init__(master, title=title, position=position)
        self.pbar = ttk.Progressbar(
            self, orient="horizontal", mode="determinate", length=length
        )
        if title:
            self.title(title)
        if pre:
            tk.Label(self, text=pre).pack(side=tk.LEFT)
        self.pbar.pack(side=tk.LEFT)
        if post:
            tk.Label(self, text=post).pack(side=tk.LEFT)
        self.set(0)
        self._first = True
        if duration:
            self._incr = 0.1 * self.LOOPTIME / duration
            self._value = self._incr
            self._update()

    def _update(self):
        "Aggiorna valore in modo 'timer'"
        self._value += self._incr
        if self._first:
            self._first = False
        else:
            self.set(self._value)
            self.lift()
            if self._value > 100.0:
                self.destroy()
                return
        self.after(self.LOOPTIME, self._update)

    def set(self, value):
        "Incremente valore barra (0..100)"
        if 0 <= value <= 100:
            self.pbar["value"] = int(value + 0.4999999)

    def get(self):
        "Legge valore barra"
        return self.pbar["value"]

    def kill(self):
        "Termina e chiude"
        try:
            self.destroy()
        except:  # pylint: disable=W0702
            pass


class HSpacer(tk.Label):  # pylint: disable=R0901
    "Spaziatore orizzontale: se nspaces=0, riempie tutto lo spazio disponibile"

    def __init__(self, master, nspaces=0, **kw):
        if nspaces:
            spaces = " " * nspaces
            super().__init__(master, text=spaces, **kw)
            self.pack(side=tk.LEFT)
        else:
            super().__init__(master, text=" ", **kw)
            self.pack(side=tk.LEFT, expand=1, fill=tk.X)

class ExpandLabel(tk.Label):
    "Label che si espande ma non si restringe"
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.max_width = 0

    def config(self, **kws):
        "ovverride del metodo config"
        if "text" in kws:
            self.max_width = max(self.max_width, len(kws["text"]))
            kws["width"] = self.max_width
        super().config(**kws)


class ShowText(MyToplevel):
    "Finestra non modale per visualizzazione testo"

    def __init__(self, master, title="", position=None, icon="", **kwa):
        super().__init__(master, title=title, position=position)
        if title:
            self.title(title)
        if icon:
            self.iconphoto(False, icon)
        self.body = tk.Text(self, padx=5, pady=5, **kwa)
        self.body.pack()
        tk.Button(self, text="Chiudi", command=self.withdraw).pack()
        self.withdraw()

    def append(self, text):
        "Aggiunge testo"
        self.body.insert(tk.END, text)
        self.deiconify()


WNG_MSG = """Messaggio di prova
per widget popup"""


def showmsg(what):
    "Lancia test ShowText"
    if what == "InfoMsg":
        ret = InfoMsg(GLOB.root, WNG_MSG, position=(30, 30))
    if what == "WarningMsg":
        ret = WarningMsg(GLOB.root, WNG_MSG, position=(30, 30))
    if what == "ErrorMsg":
        ret = ErrorMsg(GLOB.root, WNG_MSG, position=(30, 30))
    if what == "WarningMsg":
        ret = WarningMsg(GLOB.root, WNG_MSG, title="Warning", position=(30, 30))
    elif what == "YesNo":
        ret = YesNo(GLOB.root, WNG_MSG, title="Deciditi!", position=(-10, -10))
    elif what == "SelectionMsg":
        ret = SelectionMsg(
            GLOB.root, WNG_MSG, choices=("Uno", "Due", "Tre"), position="center"
        )
    elif what == "ShowText":
        ret = ShowText(GLOB.root, title="Testo generico", position="c")
        ret.append(WNG_MSG)
        return
    GLOB.root.wait_window(ret)
    print("Stato di ritorno:", ret.status)


class TestWidget(tk.Frame):
    "widget per test cambio colore"

    def __init__(self, master, wdg, *args, **kargs):
        super().__init__(master)
        self.wdg = wdg(self, *args, **kargs)
        self.wdg.pack(side=tk.LEFT)
        MButton(self, "r", "circle", 24, value=RED, command=self.setcolor).pack(
            side=tk.LEFT
        )
        MButton(self, "g", "circle", 24, value=GREEN, command=self.setcolor).pack(
            side=tk.LEFT
        )

    def setcolor(self, name):
        "cambia colore"
        value = self.wdg.get()
        if name == "r":
            self.wdg.set(value, fg=RED)
        else:
            self.wdg.set(value, fg=GREEN_L)

    def set(self, value):
        "override metodo set"
        self.wdg.set(value)


def main():
    "Procedura di test"

    def premuto_bottone(b_name):
        "Bottone premuto"
        print("Premuto bottone:", b_name)
        if b_name == "b5":
            Progress(GLOB.root, pre="  EOT: ", post="  ", duration=5, position="c")

    if "-d" in sys.argv:
        set_debug(True)
    GLOB.root = tk.Tk()
    sinistra = FrameTitle(GLOB.root, "Vari bottoni", border=2, relief=tk.RIDGE)
    ToolTip(sinistra.title, text="Tooltip del titolo di sinistra")
    # Esempi di vari tipi di bottone
    MButton(sinistra, "b1", "circle", 32, command=premuto_bottone).pack()
    MButton(sinistra, "b2", "square", 32, value=RED).pack()
    MButton(sinistra, "b3", "up", 32, value=GREEN, command=premuto_bottone).pack()
    MButton(sinistra, "b4", "left", 32, value=YELLOW, command=premuto_bottone).pack()
    CButton(
        sinistra, "b5", color="lightgreen", text="Progress Bar", command=premuto_bottone
    ).pack()
    sinistra.pack(side=tk.LEFT, anchor=tk.N)
    # Esempi di altri widget
    centro = FrameTitle(GLOB.root, "Altri widget", border=2, relief=tk.RIDGE)
    # Controller con frecce
    Controller(centro, lower=-10, upper=10, circular=True).pack()
    # Controller +/-
    Controller(centro, mode="plus", lower=-10, upper=10, circular=True).pack()
    # Campo per visualizzazione stringhe
    tar = TestWidget(centro, Field, text="Tarabaralla")
    tar.pack()
    # Campo per visualizzazione Valori numerici
    fld = TestWidget(centro, Number, fmt="%.2f")
    fld.pack()
    fld.set(1234)
    crd = TestWidget(centro, Coord)
    crd.pack()
    crd.set(-137.34)
    leds = tk.Frame(centro)
    tk.Label(leds, text="Vari led colorati: ").pack(side=tk.LEFT)
    Led(leds, color="blue").pack(side=tk.LEFT)
    Led(leds, color="white", size=15).pack(side=tk.LEFT)
    Led(leds, size=20).pack(side=tk.LEFT)
    Led(leds, color="yellow", size=25).pack(side=tk.LEFT)
    Led(leds, color="red", size=30).pack(side=tk.LEFT)
    leds.pack()
    centro.pack(side=tk.LEFT, anchor=tk.N)
    destra = FrameTitle(GLOB.root, "Widget PopUp", border=2, relief=tk.RIDGE)
    tk.Button(destra, text="InfoMsg", command=lambda: showmsg("InfoMsg")).pack()
    tk.Button(destra, text="WarningMsg", command=lambda: showmsg("WarningMsg")).pack()
    tk.Button(destra, text="ErrorMsg", command=lambda: showmsg("ErrorMsg")).pack()
    tk.Button(destra, text="YesNo", command=lambda: showmsg("YesNo")).pack()
    tk.Button(
        destra, text="SelectionMsg", command=lambda: showmsg("SelectionMsg")
    ).pack()
    tk.Button(destra, text="ShowText", command=lambda: showmsg("ShowText")).pack()
    destra.pack(side=tk.LEFT, anchor=tk.N)
    GLOB.root.mainloop()


if __name__ == "__main__":
    main()
