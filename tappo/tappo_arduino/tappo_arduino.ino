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
// fN:   1/0        Stato finecorsa.N (N=[0..3] num. petalo), 0: aperto, 1: chiuso
// pN:   xxx        Posizione petalo N; xxx: gradi dalla posizione chiuso
// mN:   1/0        Stato movimento petalo N (0: fermo, 1: in moto)
// M:    xxxx       Valore angolo massimo

// Comandi operativi:
//
// Cod. Risposta   Descrizione
// aN:   Ok/errore   Apri petalo N (inizia movimento in apertura)
// cN:   Ok/errore   Chiudi petalo N (inzia movimento in chiusura)
// sN:   Ok/errore   Stop (interrompe movimento del..) petalo N
// S:    Ok/errore   Stop tutti i motori
// ixxx: ang/errore  Imposta valore massimo angolo raggiungibile.
//                   in caso di successo riporta il valore impostato

// Nota: le funzioni di controllo devono agire automaticamente
//       interrompendo il moto quando si chiude lo switch di fine
//       corsa o quando viene raggiunto l'angolo massimo

#include "devices.h"

#define REFRESH_INTERVAL 500      // statu srefresh inrterval

char *Ident = "Tappo OPC v 1.0";

//                         Error codes
char *success = "Ok";   // success

char *err01 = "E01";    // wrong petal/motor index
char *err02 = "E02";    // Wrong motor max angle
char *err03 = "E03";    // command execution error
char *err04 = "E04";    // unrecognized command

float position[4];     // motor positions
bool atHome[4];         // petal at home
bool moving[4];        // motor moving status

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
  for(int i=1; i<4; i++) position[i]=(-1);
  nextRefresh = 0;
  init_motors(); 
  clear_command_buffer(); 
  update_status();
};

void get_command() {              // Called from within the loop to
                                  // receive characters from the serial line
  if(commandReady) return;        // The commnad i sready for execution
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

void clear_command_buffer() {  // clear commnad buffer
  charIx = 0;
  commandReady = false;
};

int digit_to_int(char achar) {   // convert digit character in int 0..9
                                 // on error returns -1
  int val = achar-'0';
  if(val<0 || val>9) val = -1;
  return val;
}


void update_status() {           // update system status
  if(millis() > nextRefresh) {   // called every 500 ms
    motor_states(moving, position);
    limit_switches(atHome);
    if(blinker) {                // blink the LED
      digitalWrite(LED_BUILTIN, HIGH);
      blinker = false;
    } else {
      digitalWrite(LED_BUILTIN, LOW);
      blinker = true;
    }
    nextRefresh = millis()+REFRESH_INTERVAL;
  }
}

void exec_command() {   // Executes the command from command buffer
  if(commandReady){
    bool done = false;
    switch(commandBuffer[0]) {             // commands without arguments
      case 'S': {
        stop_motor(0);
        stop_motor(1);
        stop_motor(2);
        stop_motor(3);
        Serial.println(success);
      }
      done = true;
      break;
      case 'i': {
        int value = atoi(commandBuffer+1);
        if(value<=0 || value > 300)
          Serial.println(err02);
        else {
          Serial.println(value);
          set_max_position(value);
        }
        done = true; }
        break;
      case 'M': {
        Serial.println(get_max_position());
        done = true;
        }
        break;
      case 'v': {
        Serial.println(Ident);
        done = true; }
    }
    if(done) {
      clear_command_buffer();
      return;
    }
    
    int nPetal = digit_to_int(commandBuffer[1]); // Convert argument value

    if(nPetal<0 || nPetal>3){
      Serial.println(err01);
      clear_command_buffer();
      return;
    }

    switch(commandBuffer[0]) {              // commands with argument
      case 's':
        if(stop_motor(nPetal))
          Serial.println(success);
        else
          Serial.println(err03);
        break;
      case 'p': 
        Serial.println(position[nPetal]);
        break;
      case 'm':
        Serial.println(moving[nPetal]);
        break;
      case 'f':
        Serial.println(atHome[nPetal]);
        break;
      case 'c':
        if(close_petal(nPetal))
          Serial.println(success);
        else
          Serial.println(err03);
        break;
      case 'a':
        if(open_petal(nPetal))
          Serial.println(success);
        else
          Serial.println(err03);
        break;
      default:
        Serial.println(err04);
    }
    clear_command_buffer();
  }
}

void loop() {
  motor_control(0);
  motor_control(1);
  motor_control(2);
  motor_control(3);    
  update_status();
  get_command();
  exec_command();
}
