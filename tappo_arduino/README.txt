Software di controllo per tappo telescopio.

- questa directory contiene il codice del firmware per Arduino.

- il file tappo.py nella cartella "opc" implementa una semplice interfaccia python
  per inviare comandi al controller via seriale.

- L'interfaccia grafica si trova nel file "tappo_gr.py" nella directory "gui"


Per il test del firmware del controller si possono usare i comandI:

Linux:  cu -l /dev/ttyACM0 -s 9600

Windows:

PINOUT per scheda CNC:

X step/dir = pin 2/5
Y step/dir = pin 3/6
Z step/dir = pin 4/7
A step/dir = pin 12/13 ma bisogna collegare con jumpers D12 e D13 (blu/giallo)

ENABLE = pin 8 (per averlo permanentemente enabled, jumper su EN/GND)

FINE CORSA headers bianco/neri (nero tutto GND):
X+ = X- = 9
Y+ = Y- = 10
Z+ = Z- = 11
Per il fine corsa A si può usare un pin libero da 14 a 21

NOTA: a quanto capisco i finecorsa devono mandare un segnale positivo ad un limite e negativo
all'altro (suppong 0 quando siamo a mezza strada). Per questo usa gli ingressi analogici.

Dato che noi abbiamo solo il limit switch in chiusura io utilizzo ingressi digitali
(14, 15, 16, 17)
