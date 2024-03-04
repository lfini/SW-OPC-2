Note sull'esecuzione della GUI in modo simulazione. Si devonio utilizzare tre
sessioni interattive (terminali).

NOTA: al momento è possibile simulare solo la sequenza di immagini
      scientifiche

1. Lanciare hgui.py con l'opzione "-s" da una delle sessioni

2. Lanciare il simulatore di telescopio (.../opc/telsimulator.py) dalla
   seconda sessione.

3. Utilizzare l'interfaccia grafica di homer per l'impostazione della
   directory per le immagini simulate. Si consiglia di usare la directory
   ..../homer/__work__ (default)

   Fare la calibrazione su una immagine opportuna (ad esempio una delle
   immagini di test sulla directory .../homer/: testim0.fit, ...)

   NOTA: la stessa immagine dovrà essere usata come "template" per la
   generazione delle immagini simulate.

4. Attivare Homer con: "start guiding".  Homer si mette in attesa delle
   immagini simulate.

5a  Dal terzo terminale copiare manualmente in sequenza immagini reali
    sulla directory selezionata da homer

.... oppure

5b  Dal terzo terminale interattivo, attivare il generatore di immagini
    simulate (camsim.py) specificando i parametri in modo che
    le immagini simulate siano generate sulla directory selezionata
    da homer per le immagini scientifiche ed utilizzando come template la
    stessa immagine usata per la calibrazione.
