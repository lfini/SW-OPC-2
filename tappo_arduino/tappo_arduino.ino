// Comandi definiti per il sistema di controllo
// Ogni comando è costituito da una stringa compresa fra un carattere '!' (inizio)
// e un carattere ':' (fine comando)

// Ogni comando riceve una risposta costituita da una stringa terminata da '\r\n'
//
// Comandi di interrogazione:
//
// Cod. Risposta   Descrizione
// v    xxxxxxx    Identificazione (numero di versione del firmware)
// lN   1/0        Stato limit switch N (N=[0..3] num. petalo), 1: aperto, 0: chiuso
// pN   xxxx       Posizione petalo N; xxx: numero step dalla posizione chiuso
// mN   1/0        Stato movimento petalo N (0: fermo, 1: in apertura, -1: in chiusura)
// A    xxxx       Valore angolo massimo (in step dalla posizione chiuso)

// Comandi operativi:
//
// Cod. Risposta   Descrizione
// oN   Ok/errore   Apri petalo N (inizia movimento in apertura)
// cN   Ok/errore   Chiudi petalo N (inzia movimento in chiusura)
// axxx ang/errore  Imposta valore massimo angolo (in num di step) raggiungibile.
//                  in caso di successo riporta il valore impostato
// sN   Ok/errore   Stop (interrompe movimento del..) petalo N
// S    Ok/errore   Stop tutti i motori

// Comandi per debug:

// MN   aaaa       Legge informazioni su stato petalo N
// N    xxxx       Legge numero di comandi ricevuti
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

unsigned char ret_buf[BUF_LEN+1];  // Buffer for reply messages

int ncommands = 0;

unsigned char command_buffer[BUF_LEN+1];
int char_ix = 0;
bool command_ready = false;
bool command_empty = true;

unsigned long motor_timer = 0;

bool running = true;

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
  if(cmd == 'a') {
    int value = atoi(command_buffer+1);
    if(value >= 0) {
      SetMaxPosition(value);
      Serial.println(success);
    } else
      Serial.println(err02);
    return;
  }
  if(cmd == 'A') {
    Serial.println(GetMaxPosition());
    return;
  }
  if(cmd == 'v') {
    Serial.println(ident);
    return;
  }
  if(cmd == 'N') {
    Serial.println(ncommands);
    return;
  }
  if(cmd == 'r') {
    running = true;
    InitMotors();
    Serial.println(success);
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
      Serial.println(GetPosition(n_petal));
    return;
  }
  if(cmd == 'm') {
    if(n_petal < 0)
      Serial.println(err01);
    else
      Serial.println(GetDirection(n_petal));
    return;
  }
  if(cmd == 'l') {
    if(n_petal < 0)
      Serial.println(err01);
    else
      Serial.println(GetLimitSwitch(n_petal));
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
  if(cmd == 'M') {
    if(n_petal < 0) {
      Serial.println(err01);
      return;
    }
    Serial.println(GetMotorInfo(n_petal));
    return;
  }
  if(cmd == 'n') {
    running = false;
    if(n_petal < 0) {
      Serial.println(err01);
      return;
    }
    MotorControl(n_petal);  // manual motor step execution
    Serial.println(success);
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
  if((now >= motor_timer) && running) {
    MotorControl(0);
    MotorControl(1);
    MotorControl(2);
    MotorControl(3);    
    motor_timer = now+MOTOR_HALF_PERIOD;
  }
  GetCommand();
  ExecCommand();
}