// Comandi definiti per il sistema di controllo
// Ogni comando è costituito da una stringa compresa fra un carattere '!' (inizio)
// e un carattere ':' (fine comando)

// Ogni comando riceve una risposta costituita da una stringa terminata da '\r\n'
//
// Comandi di interrogazione:
//
// Cod. Risposta   Descrizione
// v    xxxxxxx    Identificazione (numero di versione del firmware)
// fN   1/0        Stato finecorsa.N (N=[0..3] num. petalo), 1: aperto, 0: chiuso
// pN   xxxx       Posizione petalo N; xxx: numero step dalla posizione chiuso
// mN   1/0        Stato movimento petalo N (0: fermo, 1: in moto)
// M    xxxx       Valore angolo massimo (in step dalla posizione chiuso)
// I    xxxx       Tempo morto (idle) nel ciclo (millisec)

// Comandi operativi:
//
// Cod. Risposta   Descrizione
// aN   Ok/errore   Apri petalo N (inizia movimento in apertura)
// cN   Ok/errore   Chiudi petalo N (inzia movimento in chiusura)
// ixxx ang/errore  Imposta valore massimo angolo (in num di step) raggiungibile.
//                  in caso di successo riporta il valore impostato
// sN   Ok/errore   Stop (interrompe movimento del..) petalo N
// S    Ok/errore   Stop tutti i motori

// Comandi per modo test:
// T    Ok/errore   Imposta modo test (consente alcuni test in assenza di motori)
//                  Nota: una volta impostato il modo test, per tornare al modo
//                  normale occorre disalimentare l'arduino
// xNM  Ok/errore   Simula chiusura/apertura del limit switch N
//                  (M == 0: aperto; M == 1: chiuso)

// Nota: le funzioni di controllo devono agire automaticamente
//       interrompendo il moto quando si chiude lo switch di fine
//       corsa o quando viene raggiunto l'angolo massimo di apertura

#include "devices.h"

#define REFRESH_INTERVAL 500      // status srefresh inrterval

#define BUF_LEN 11

char *Ident = "Tappo OPC v 1.0";
char *Ident_test = "Tappo OPC - TEST";

//                         Error codes
char *success = "Ok";   // success
char *err00 = "E00";    // Max angle not initialized
char *err01 = "E01";    // wrong petal/motor index
char *err02 = "E02";    // Wrong motor max angle
char *err03 = "E03";    // command execution error
char *err04 = "E04";    // unrecognized command

int position[4];       // motor positions
bool atHome[4];        // petal at home if 0 else 1
bool moving[4];        // motor moving status

unsigned char ret_buf[BUF_LEN+1];  // Buffer for reply messages

bool blinker = false;

unsigned long next_refresh;

unsigned char command_buffer[BUF_LEN+1];
int char_ix = 0;
bool command_ready = false;
bool command_empty;
int buffer_guard = BUF_LEN-1;

void setup() {
  // put your setup code here, to run once:
  Serial.begin(9600);
  pinMode(LED_BUILTIN, OUTPUT);
  for(int i=1; i<4; i++) position[i]=(-1);
  next_refresh = 0;
  InitMotors(); 
  ClearCommandBuffer(); 
  UpdateStatus();
};

void GetCommand() {               // Called from within the loop to
                                  // receive characters from the serial line
  if(command_ready) return;       // The command is ready for execution
  while(Serial.available()){
    char next_char = Serial.read();
    if(command_empty) {
      char_ix = 0;
      if(next_char == '!')
        command_empty = false;
    } else {
      if(next_char == ':') {
        command_buffer[char_ix] = '\0';
        command_ready = true;
      } else {
        command_buffer[char_ix] = next_char;
        if(char_ix < buffer_guard) char_ix++;
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

unsigned long stoptime = 0;
unsigned long idletime = 0;

void UpdateStatus() {           // update system status
  unsigned long now = millis();
  if(now >= next_refresh) {   // called every 500 ms
    idletime = now-stoptime;
    stoptime = 0;
    MotorStates(moving, position);
    LimitSwitches(atHome);
    if(blinker) {                // blink the LED
      digitalWrite(LED_BUILTIN, HIGH);
      blinker = false;
    } else {
      digitalWrite(LED_BUILTIN, LOW);
      blinker = true;
    }
    next_refresh = millis()+REFRESH_INTERVAL;
  } else if(stoptime==0) stoptime=now;
}


static char *add(char cmd) {   // add space+cmd at end of ret_buf
  int len = strlen(ret_buf);
  if(len < BUF_LEN-3) {
    char *pt = ret_buf+len;
    *pt++ = '-'; *pt++ = cmd; *pt = '\0';
  }
  return ret_buf;
}

static char *cat(char *ret, char cmd) {     // Copies the input string to ret_buf adding " "+cmd at the end
  strncpy(ret_buf, ret, BUF_LEN-3);
  return add(cmd);
}


static char *ExecInternal() {
  char cmd = command_buffer[0];
  if(cmd == 'S') {
    StopMotor(0);
    StopMotor(1);
    StopMotor(2);
    StopMotor(3);
    return(cat(success, cmd));
  }
  if(cmd == 'i') {
    int value = atoi(command_buffer+1);
    if(value >= 0) {
      SetMaxPosition(value);
      return(cat(success, cmd));
    } else
      return(cat(err02, cmd));
  }
  if(cmd == 'M') {
    snprintf(ret_buf, BUF_LEN, "%d", GetMaxPosition());
    return(add(cmd));
  }
  if(cmd == 'v') {
    if(IsTestMode())
      return(Ident_test);
    else
      return(Ident);
  }
  if(cmd == 'I') {
    snprintf(ret_buf, BUF_LEN, "%u", idletime);
    return(add(cmd));
  }
  if(cmd == 'T') {
    SetTestMode();
    return(cat(success, cmd));
  }
    
  int nPetal = DigitToInt(command_buffer[1]); // Convert argument value

  if(cmd == 's') {
    if(nPetal < 0)
      return(cat(err01, cmd));
    if(StopMotor(nPetal))
      return(cat(success, cmd));
    else
      return(cat(err03, cmd));
  }unsigned long idletime;
  if(cmd == 'p') {
    if(nPetal < 0)
      return(cat(err01, cmd));
    snprintf(ret_buf, BUF_LEN, "%d", position[nPetal]);
    return(add(cmd));
  }
  if(cmd == 'm') {
    if(nPetal < 0)
      return(err01);
    if(moving[nPetal])
      return cat("1", cmd);
    else
      return cat("0", cmd);
  }
  if(cmd == 'f') {
    if(nPetal < 0)
      return(cat(err01, cmd));
    if(atHome[nPetal])
      return cat("0", cmd);
    else
      return cat("1", cmd);
  }
  if(cmd == 'c') {
    if(nPetal < 0)
      return(cat(err01, cmd));
    if(ClosePetal(nPetal))
      return(cat(success, cmd));
    else
      return(cat(err03, cmd));
  }
  if(cmd == 'a') {
    if(nPetal < 0)
      return(cat(err01, cmd));
    if(GetMaxPosition() == 0)
      return(cat(err00, cmd));
    if(OpenPetal(nPetal))
      return(cat(success, cmd));
    else
      return(cat(err03, cmd));
  }
  if(cmd == 'x') {
    if(nPetal < 0)
      return(cat(err01, cmd));
    int mode = command_buffer[2];
    if(mode == '0' or mode == '1') {
      mode = mode-'0';
      if(SetFakeSwitch(nPetal, mode))
        return(cat(success, cmd));
      else
        return(cat(err03, cmd));
    }
    return(cat(err03, cmd));
  }
  return(cat(err04, cmd));
}

void ExecCommand() {   // Executes the command from command buffer
  if(command_ready){
    char *ret = ExecInternal();
    ClearCommandBuffer();
    Serial.println(ret);
  }
}


void loop() {
  MotorControl(0);
  MotorControl(1);
  MotorControl(2);
  MotorControl(3);    
  UpdateStatus();
  GetCommand();
  ExecCommand();
}
