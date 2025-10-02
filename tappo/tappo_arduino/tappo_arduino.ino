// Comandi definiti per il sistema di controllo
// Ogni comando è costituito da una stringa terminata da '\n'
// il primo carattere identifica il comando, quelli eventualmente successivi
// specificano l'argomento
//
// Comandi di interrogazione:
//
// Cod. Risposta   Descrizione
// v    xxxxxxx    Identificazione (numero di versione del firmware)
// fN   1/0        Stato finecorsa.N (N=[0..3] num. petalo), 1: aperto, 0: chiuso
// pN   xxx        Posizione petalo N; xxx: gradi dalla posizione chiuso
// mN   1/0        Stato movimento petalo N (0: fermo, 1: in moto)

// Comandi operativi:
//
// Cod. Risposta   Descrizione
// aN   0/errore   Apri petalo N (inizia movimento in apertura)
// cN   0/errore   Chiudi petalo N (inzia movimento in chiusura)
// sN   0/error    Stop (interrompe movimento del..) petalo N
// ixxx 0/errore   Imposta valore massimo angolo raggiungibile

// Nota: le funzioni di controllo devono agire automaticamente
//       interrompendo il moto quando si chiude lo switch di fine
//       corsa o quando viene raggiunto l'angolo massimo

#include "comandi_esecutivi.h"

char *IDENT = "Tappo OPC v 1.0";

//                      codici di errore
char *OK = "0";       // Successo

char *E01 = "E01";    // indice petalo errato
char *E02 = "E02";    // Impostazione angolo limite errata
char *E03 = "E03";    // errore esecuzione comando

int POSIZIONE[4];
int FINE_CORSA[4];
int IN_MOTO[4];

int ANGOLO_MAX = 270;

char CMD_BUFFER[11];
int char_ix = 0;
bool CMD_READY = false;
int CMD_GUARD = sizeof(CMD_BUFFER)-1;

void setup() {
  // put your setup code here, to run once:
Serial.begin(9600);
for(int i=1; i<4; i++) POSIZIONE[i]=(-1);
aggiorna_stato();
};

void ricevi_comando() {  // da chiamare nel loop per ricevere caratteri dalla line seriale
  if(CMD_READY) return;      // comando completo e non ancora usato
  while(Serial.available()){
    char next_ch = Serial.read();
    if(next_ch == '\r') continue;
    if(next_ch == '\n'){
      CMD_BUFFER[char_ix] = '\0';
      CMD_READY = true;
    } else
      if(char_ix < CMD_GUARD)
        CMD_BUFFER[char_ix++] = next_ch;
  };
};

void azzera_buffer_comando() {  // azzera il buffer dei comandi per accettare un nuovo comando
  char_ix = 0;
  CMD_READY = false;
  };

int getdigit(char achar) {   // converte singolo carattere in [0..9] in int
                       // per errori riporta -1
  int val = achar-'0';
  if(val<0 || val>9) val = -1;
  return val;
}

void aggiorna_stato() {   // aggiorna stato complessivo
  leggi_posizioni(POSIZIONE);
  leggi_fine_corsa(FINE_CORSA);
  leggi_stato_moto(IN_MOTO);
  }

void esegui_comando() {
  if(CMD_READY) {
    char* command = CMD_BUFFER;
   
    switch(command[0]){
      case 'i':
        int value = atoi(command+1);
        if(value<=0 || value > 300)
          Serial.println(E02);
        else
          Serial.println(OK);
        azzera_buffer_comando();
        return;
      case 'v':
        Serial.println(IDENT);
        azzera_buffer_comando();
        return;
    };
    
    int n_petalo = getdigit(command[1]);
    if(n_petalo<0 || n_petalo>3){
      Serial.println(E01);
      azzera_buffer_comando();
      return;

    };
    switch(command[0]){
      case 's':
        if(stop_moto(n_petalo))
          Serial.println(OK);
        else
          Serial.println(E03);
        break;
      case 'p':
        Serial.println(POSIZIONE[n_petalo]);
        break;
      case 'm':
        Serial.println(IN_MOTO[n_petalo]);
        break;
      case 'f':
        Serial.println(FINE_CORSA[n_petalo]);
        break;
      case 'c':
        if(chiudi_petalo(n_petalo))
          Serial.println(OK);
        else
          Serial.println(E03);
        break;
      case 'a':
        if(apri_petalo(n_petalo))
          Serial.println(OK);
        else
          Serial.println(E03);
        break;
      case 'v':
        Serial.println(IDENT);
        break;
    };
    azzera_buffer_comando();
  }
}

void loop() {
  // put your main code here, to run repeatedly:
  aggiorna_stato();
  ricevi_comando();
  esegui_comando();
}
