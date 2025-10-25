// Comandi definiti per il sistema di controllo
// Ogni comando è costituito da una stringa compresa fra un carattere '!' (inizio)
// e un carattere ':' (fine comando)

// Ogni comando riceve una risposta costituita da una stringa terminata da '\r\n'
//
// Comandi di interrogazione:
//
// Cod. Risposta   Descrizione
// v    xxxxxxx    Identificazione (numero di versione del firmware)
// pN   m,d,p      Stato petalo. m: in moto/fermo, d: direzione moto, p:posizione

// a    xxxx       Legge valore angolo massimo (in step dalla posizione chiuso)

// Comandi operativi:
//
// Cod. Risposta   Descrizione
// oN   Ok/errore   Apri petalo N (inizia movimento in apertura)
// cN   Ok/errore   Chiudi petalo N (inzia movimento in chiusura)
// Axxx ang/errore  Imposta valore massimo angolo (in num di step) raggiungibile.
// sN   Ok/errore   Stop (interrompe movimento del..) petalo N
// S    Ok/errore   Stop tutti i motori

// Comandi per debug:

// dN   aaaa       Legge informazioni su stato petalo N utile per debug
// n    xxxx       Legge numero di comandi ricevuti
// r    Ok/errore  Reinizializza stato motori

// Nota: le funzioni di controllo devono agire automaticamente
//       interrompendo il moto quando si chiude lo switch di fine
//       corsa o quando viene raggiunto l'angolo massimo di apertura

#include "config.h"
#include "devices.h"

#define REFRESH_INTERVAL 500      // LED refresh inrterval

#define BUF_LEN 11

char *ident = "Tappo OPC v. 1.0";

//                         Error codes
char *success = "Ok";   // success
char *err00 = "E00";    // Max angle not initialized
char *err01 = "E01";    // wrong petal/motor index
char *err02 = "E02";    // Wrong motor max angle
char *err03 = "E03";    // command execution error
char *err04 = "E04";    // unrecognized command

int ncommands = 0;

unsigned char command_buffer[BUF_LEN+1];
int char_ix = 0;
bool command_ready = false;
bool command_empty = true;

unsigned long motor_timer = 0;

void setup() {
  // put your setup code here, to run once:
  Serial.begin(9600);
  ncommands = 0;
  SetupMotors();
  InitMotors(); 
  ClearCommandBuffer(); 
};

void GetCommand() {               // Called from within the loop to
                                  // receive characters from the serial line
  if(command_ready) return;       // The command is ready for execution
  while(Serial.available()){
    char next_char = Serial.read();
    if(command_empty) {
      if(next_char == '!')
        command_empty = false;
    } else {
      if(next_char == ':') {
        command_buffer[char_ix] = '\0';
        command_ready = true;
        ncommands++;
      } else {
        command_buffer[char_ix] = next_char;
        if(char_ix < BUF_LEN) char_ix++;
      }
    }
  }
}

void ClearCommandBuffer() {  // clear command buffer
  char_ix = 0;
  command_ready = false;
  command_empty = true;
};

int DigitToInt(char achar) {   // convert digit character in int 0..3
                                 // on error returns -1
  int val = achar-'0';
  if(val<0 || val>3) val = -1;
  return val;
}

void ExecCommandInternal() {          // actual command executor
  char cmd = command_buffer[0];
  if(cmd == 'S') {
    StopMotor(0);
    StopMotor(1);
    StopMotor(2);
    StopMotor(3);
    Serial.println(success);
    return;
  }
  if(cmd == 'A') {
    int value = atoi(command_buffer+1);
    if(value >= 0) {
      SetMaxPosition(value);
      Serial.println(success);
    } else
      Serial.println(err02);
    return;
  }
  if(cmd == 'a') {
    Serial.println(GetMaxPosition());
    return;
  }
  if(cmd == 'v') {
    Serial.println(ident);
    return;
  }
  if(cmd == 'n') {
    Serial.println(ncommands);
    return;
  }
  
  int n_petal = DigitToInt(command_buffer[1]); // Convert argument value

  if(cmd == 's') {
    if(n_petal < 0) {
      Serial.println(err01);
      return;
    }
    if(StopMotor(n_petal))
      Serial.println(success);
    else
      Serial.println(err03);
    return;
  }
  if(cmd == 'p') {
    if(n_petal < 0)
      Serial.println(err01);
    else
      Serial.println(GetPetalStatus(n_petal));
    return;
  }
  if(cmd == 'c') {
    if(n_petal < 0) {
      Serial.println(err01);
      return;
    }
    if(ClosePetal(n_petal))
      Serial.println(success);
    else
      Serial.println(err03);
    return;
  }
  if(cmd == 'o') {
    if(n_petal < 0) {
      Serial.println(err01);
      return;
    }
    if(GetMaxPosition() <= 0) {
      Serial.println(err00);
      return;
    }
    if(OpenPetal(n_petal))
      Serial.println(success);
    else
      Serial.println(err03);
    return;
  }
  if(cmd == 'd') {
    if(n_petal < 0) {
      Serial.println(err01);
      return;
    }
    Serial.println(GetDebugInfo(n_petal));
    return;
  }
  Serial.println(err04);
}

void ExecCommand() {              // Execute the command from command buffer,
  if(command_ready){              // reset command buffer and retrurn reply
    ExecCommandInternal();
    ClearCommandBuffer();
  }
}

void loop() {
  unsigned long now = millis();
  if(now >= motor_timer) {
    MotorControl(0);
    MotorControl(1);
    MotorControl(2);
    MotorControl(3);    
    motor_timer = now+MOTOR_HALF_PERIOD;
  }
  GetCommand();
  ExecCommand();
}
