// 
// header file per i comandi esecutivi

void leggi_posizioni(int buffer[4]);  // legge le posizioni in  gradi dei quattro petali
                                      // e li scrive nel buffer
void leggi_fine_corsa(int buffer[4]); // legge lo stato dei quattro fine corsa
                                      // e li scrive nel buffer
void leggi_stato_moto(int buffer[4]); // legge lo stato di moto dei quattro petali
                                      // e li scrive nel buffer

bool apri_petalo(int n_petalo);       // Inizia moto in senso di apertura del petalo.
                                      // il moto si interrompe automaticamente quando
                                      // la posizione del petalo raggiunge la soglia
                                      // la funzione ritorna immediatamente con valore true
                                      // in caso di successo, falso altrimenti
bool chiudi_petalo(int n_petalo);     // Inizia il moto in senso di chiusura del petalo
                                      // il moto si interrompe automaticamente quando
                                      // la il petalo raggiunge il fine corsa.
                                      // la funzione ritorna immediatamente con valore true
                                      // in caso di successo, falso altrimenti
bool stop_moto(int n_petalo);         // interrompe il moto. La funzione ripura true in caso
                                      // di successo, false altrimenti