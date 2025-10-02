/*
Questo file è uno "stub" che serve solo per i test. Poi dovrà essere
riempito con il vero codice.

*/
#include "comandi_esecutivi.h"

void leggi_posizioni(int buffer[4]){  // legge le posizioni in  gradi dei quattro petali
                                      // e li scrive nel buffer
  buffer[0] = 77;
  buffer[1] = 44;
  buffer[2] = 10;
  buffer[3] = 123;
}

void leggi_fine_corsa(int buffer[4]){ // legge lo stato dei quattro fine corsa
  buffer[0] = 0;                              // e li scrive nel buffer
  buffer[1] = 1;
  buffer[2] = 0;
  buffer[3] = 0;
}
void leggi_stato_moto(int buffer[4]){ // legge lo stato di moto dei quattro petali
  buffer[0] = 0;                              // e li scrive nel buffer
  buffer[1] = 1;
  buffer[2] = 1;
  buffer[3] = 1;
}

bool apri_petalo(int n_petalo){       // Inizia moto in senso di apertura del petalo.
  return true;
}


bool chiudi_petalo(int n_petalo){     // Inizia il moto in senso di chiusura del petalo
   return true;
}                      
                  
bool stop_moto(int n_petalo){         // interrompe il moto. La funzione ripura true in caso
  return true;
}
                             