// Comandi definiti per il sistema di controllo
// Ogni comando è costituito da una stringa terminata da ':'
// il primo carattere identifica il comando, quelli eventualmente successivi
// specificano l'argomento.
// Ogni comando riceve una risposta costituita da una stringa terminata da '\r\n'
//
// Comandi di interrogazione:
//
// Cod. Risposta   Descrizione
// v:    xxxxxxx    Identificazione (numero di versione del firmware)
// fN:   1/0        Stato finecorsa.N (N=[0..3] num. petalo), 1: aperto, 0: chiuso
// pN:   xxx        Posizione petalo N; xxx: gradi dalla posizione chiuso
// mN:   1/0        Stato movimento petalo N (0: fermo, 1: in moto)

// Comandi operativi:
//
// Cod. Risposta   Descrizione
// aN:   Ok/errore   Apri petalo N (inizia movimento in apertura)
// cN:   Ok/errore   Chiudi petalo N (inzia movimento in chiusura)
// sN:   Ok/errore   Stop (interrompe movimento del..) petalo N
// ixxx: ang/errore  Imposta valore massimo angolo raggiungibile.
//                   in caso di successo riporta il valore impostato

// Nota: le funzioni di controllo devono agire automaticamente
//       interrompendo il moto quando si chiude lo switch di fine
//       corsa o quando viene raggiunto l'angolo massimo

#include "comandi_esecutivi.h"

#define REFRESH_INTERVAL 1000  // intrervallo di refresh status (millisec)

char *Ident = "Tappo OPC v 1.0";

//                         codici di errore
char *success = "Ok";   // Successo

char *err01 = "E01";    // indice petalo errato
char *err02 = "E02";    // Impostazione angolo limite errata
char *err03 = "E03";    // errore esecuzione comando
char *err04 = "E04";    // comando non riconosciuto

int posizione[4];
int fineCorsa[4];
int inMoto[4];

bool blinker = false;

unsigned long nextRefresh;

int AngoloMax = 270;

unsigned char commandBuffer[11];
int charIx = 0;
bool commandReady = false;
int bufferGuard = sizeof(commandBuffer)-1;

void setup() {
  // put your setup code here, to run once:
  Serial.begin(9600);
  pinMode(LED_BUILTIN, OUTPUT);
  for(int i=1; i<4; i++) posizione[i]=(-1);
  nextRefresh = 0; 
  azzera_buffer_comando(); 
  aggiorna_stato();
};

void ricevi_comando() {           // da chiamare nel loop per ricevere caratteri
                                  // dalla linea seriale
  if(commandReady) return;        // comando pronto. Attendi esecuzione
  while(Serial.available()){
    char nextChar = Serial.read();
    if(nextChar == ':') {
      commandBuffer[charIx] = '\0';
      commandReady = true;
    } else 
      if(isalnum(nextChar)) {
        commandBuffer[charIx] = nextChar;
        if(charIx < bufferGuard) charIx++;
      };
  };
  return;
};

void azzera_buffer_comando() {  // azzera il buffer dei comandi per accettare un nuovo comando
  charIx = 0;
  commandReady = false;
  for(int i=1; i<sizeof(commandBuffer); i++) commandBuffer[i] = '\0';
};

int digit_to_int(char achar) {   // converte singolo carattere in [0..9] in int
                                 // per errori riporta -1
  int val = achar-'0';
  if(val<0 || val>9) val = -1;
  return val;
}

void aggiorna_stato() {          // aggiorna periodicamente stato complessivo
  if(millis() > nextRefresh) {
    leggi_posizioni(posizione);
    leggi_fine_corsa(fineCorsa);
    leggi_stato_moto(inMoto);
    if(blinker) {
      digitalWrite(LED_BUILTIN, HIGH);
      blinker = false;
    } else {
      digitalWrite(LED_BUILTIN, LOW);
      blinker = true;
    }
    nextRefresh = millis()+REFRESH_INTERVAL;
  }
}

void esegui_comando() {   // Esegue comando ricevuto da PC
                          // Nota: utilizzata catrena di "if" perché
                          // la frase switch .. case sembra non funzionare
                          // in modo standard
  if(commandReady){
    unsigned char cmd = commandBuffer[0];
    if(cmd=='i') {                            // comandi senza argomenti
      int value = atoi(commandBuffer+1);
      if(value<=0 || value > 300)
        Serial.println(err02);
      else
        Serial.println(value);
      azzera_buffer_comando();
      return;
    };
    if(cmd=='v') {
      Serial.println(Ident);
      azzera_buffer_comando();
      return;
    };
    
    // i comandi che seguono richiedono num. di petalo
    int nPetalo = digit_to_int(commandBuffer[1]);

    if(nPetalo<0 || nPetalo>3){
      Serial.println(err01);
      azzera_buffer_comando();
      return;
    };

    if(cmd=='s') {
      if(stop_moto(nPetalo))
        Serial.println(success);
      else
        Serial.println(err03);
    } else if(cmd=='p')
      Serial.println(posizione[nPetalo]);
    else if(cmd=='m')
      Serial.println(inMoto[nPetalo]);
    else if(cmd=='f')
      Serial.println(fineCorsa[nPetalo]);
    else if(cmd=='c') {
      if(chiudi_petalo(nPetalo))
        Serial.println(success);
      else
        Serial.println(err03);
    } else if(cmd=='a') {
      if(apri_petalo(nPetalo))
        Serial.println(success);
      else
        Serial.println(err03);
    } else
      Serial.println(err04);

    azzera_buffer_comando();
  };
}

void loop() {
  // put your main code here, to run repeatedly:
  aggiorna_stato();
  ricevi_comando();
  esegui_comando();
}
