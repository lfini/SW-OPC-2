Software di controllo per tappo telescopio.

- questa directory contiene il codice del firmware per Arduino.

- il file tappo.py nella cartella "opc" implementa una semplice interfaccia python
  per inviare comandi al controller via seriale.

- L'interfaccia grafica si trova nel file "tappo_gr.py" nella directory "gui"


Per il test del firmware del controller si possono usare i comandI:

Linux:  cu -l /dev/ttyACM0 -s 9600

Windows:
