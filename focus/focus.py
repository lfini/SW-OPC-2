'''
fuoco.py - Controllo focheggiatore sul secondario OPC 
'''

# NOTE:
#
# 1. Windows+Linux: richiede il package python hidapi (installabile con pip)
#
# 2. Solo Windows: mettere la libreria hidapi.dll in una directory contenuta in %PATH%
#

import hid
import tkinter as tk

_DEBUG = False    # Mettere True per modo debug

VENDOR = 0x519
PRODUCT = 0x2018

ON_CMD_1 = (0, 0xf1)
OFF_CMD_1 = (0, 0x01)
ON_CMD_2 = (0, 0xf2)
OFF_CMD_2 = (0, 0x02)

BTFONT = 'Helvetica 18 bold'


class Focuser(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.usbrele = hid.device()
        self.onrele0 = False
        self.onrele1 = False
        bt1 = tk.Button(self, text='-', font=(BTFONT), padx=50)
        bt1.grid(row=1, column=1)
        bt1.bind('<ButtonRelease-1>', self.b1release)
        bt1.bind('<Button-1>', self.b1press)
        bt2 = tk.Button(self, text='+', font=(BTFONT), padx=50)
        bt2.grid(row=1, column=2)
        bt2.bind('<ButtonRelease-1>', self.b2release)
        bt2.bind('<Button-1>', self.b2press)
        self.line = tk.Label(self, bg='white', font='helvetica 12 bold', fg='red')
        self.line.grid(row=2, column=1, columnspan=2, sticky=tk.W+tk.E)
        self.usb_on()

    def _write(self, what):
        'invia comando a USB'
        try:
            ret = self.usbrele.write(what)
        except:
            ret = -1
        return ret

    def b1press(self, *_unused):
        if _DEBUG:
            print('DBG> b1press')
        if not self.onrele0:
            ret = self._write(ON_CMD_2)
            if ret > 0:
                self.onrele1 = True
            else:
                self.usb_on()

    def b1release(self, *_unused):
        if _DEBUG:
            print('DBG> b1release')
        ret = self._write(OFF_CMD_2)
        if ret > 0:
            self.onrele1 = False
        else:
            self.usb_on()

    def b2press(self, *_unused):
        if _DEBUG:
            print('DBG> b2press')
        if not self.onrele1:
            ret = self._write(ON_CMD_1)
            if ret > 0:
                self.onrele0 = True
            else:
                self.usb_on()

    def b2release(self, *_unused):
        if _DEBUG:
            print('DBG> b2press')
        ret = self._write(OFF_CMD_1)
        if ret > 0:
            self.onrele0 = False
        else:
            self.usb_on()

    def usb_on(self):
        'Open communication with USB relé'
        self.usbrele.close()
        try:
            self.usbrele.open(VENDOR, PRODUCT)
        except OSError:
            self.line.config(text='Comunicazione interrotta')
            self.after(1000, self.usb_on)
            return
        self._write(OFF_CMD_1)
        self._write(OFF_CMD_2)
        self.onrele0 = False
        self.onrele1 = False
        self.line.config(text='')

def main():
    root = tk.Tk()
    root.title('FOCUS')
    wdg = Focuser(root)
    wdg.pack()
    root.mainloop()

if __name__ == '__main__':
    main()

