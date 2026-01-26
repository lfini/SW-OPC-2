Software di controllo per tappo telescopio.

- questa directory contiene il codice del firmare per Arduino (AT Mega 2560).

- il file tappo.py /(nella cartella: ../opc) contiene la libreria per
  il controllo da python con la procedura di test.

Per il test base del firmware del controller si può inviare commandi dalla
console di Arduino IDE o tramite un qualunque emulatore di terminale, ad esempio;:

    Linux:  cu -l /dev/ttyACM0 -s 9600

    Windows:

PINOUT per scheda CNC:

X step/dir = pin 2/5
Y step/dir = pin 3/6
Z step/dir = pin 4/7
A step/dir = pin 12/13

Per abilitare il canale A, bisogna collegare con jumpers D12 e D13 (blu/giallo)

Occorre mettere un ponticello di abilitazione della scheda (accanto al pulsante
di reset)





