
// Comandi definiti per il sistema di controllo
// Ogni comando è costituito da una stringa compresa fra un carattere '!' (inizio)
// e un carattere ':' (fine comando)

// Ogni comando riceve una risposta costituita da una stringa terminata da '\r\n'
//
// Comandi di interrogazione:
//
// Cod. Risposta  Descrizione
// a    x,y,z,a   Accelerazione per i quattro petali
// i    xxxxxxx   Identificazione (numero di versione del firmware)
// m    x,y,z,a   Angolo max per i quattro petali
// p    x,y,z,a   Posizione dei 4 petali
// s    x,y,z,a   Velocità corrente per i quattro petali
// v    x,y,z,a   Velocità max per i quattro petali
// w    x,y,z,a   Stato limit switch (1: chiuso, 0: aperto)


// Comandi di impostazione valori:
//
// Cod. Risposta  Descrizione
// MNxxx errcod   Imposta valore massimo angolo (in num di step) raggiungibile per petalo N
// ANxxx errcod   Imposta valore accelerazione (steps/sec^2) per petalo N
// VNxxx errcod   Imposta valore velocità massima per petalo N

// Comandi di movimento:
//
// Cod. Risposta  Descrizione
// 0N    errcod    Imposta posizione corrente come 0
// oNxxx errcod    muove petalo N di xxx passi in direzione "apertura"
// cNxxx errcod    muove petalo N di xxx passi in direzione "chiusura"
// gNxxx errcod    muove petalo N a posizione assoluta
// xN    errcod    Stop (interrompe movimento del..) petalo N
// X     errcod    Stop tutti i petali

#include <AccelStepper.h>
#include "config.h"
#include "manual.h"

#define BUF_LEN 22
#define REPLY_BUF_LEN 100

#define MOTOR_IF_TYPE AccelStepper::DRIVER

char *ident = "Tappo OPC v. 3.0";

static char reply_buffer[REPLY_BUF_LEN+1];
static char command_buffer[BUF_LEN+1];

int char_ix = 0;
bool command_ready = false;
bool command_empty = true;

AccelStepper motors[] = {AccelStepper(MOTOR_IF_TYPE, M0_PULSE_PIN, M0_DIRECTION_PIN),
                         AccelStepper(MOTOR_IF_TYPE, M1_PULSE_PIN, M1_DIRECTION_PIN),
                         AccelStepper(MOTOR_IF_TYPE, M2_PULSE_PIN, M2_DIRECTION_PIN),
                         AccelStepper(MOTOR_IF_TYPE, M3_PULSE_PIN, M3_DIRECTION_PIN)};

long max_position[4];

bool manual_on = false;

Manual manual;

static char* command_list = "aimpsvwMAVocgxX";


void setup() {
  // put your setup code here, to run once:
  Serial.begin(9600);
//  pinMode(ENABLE_PIN, OUTPUT);    // configure enable pin
  pinMode(M0_LIMIT_SWITCH_PIN, INPUT_PULLUP);
  pinMode(M1_LIMIT_SWITCH_PIN, INPUT_PULLUP);
  pinMode(M2_LIMIT_SWITCH_PIN, INPUT_PULLUP);
  pinMode(M3_LIMIT_SWITCH_PIN, INPUT_PULLUP);
  pinMode(SELECTOR_0_PIN, INPUT_PULLUP);
  pinMode(SELECTOR_1_PIN, INPUT_PULLUP);
  pinMode(SELECTOR_2_PIN, INPUT_PULLUP);
  pinMode(SELECTOR_3_PIN, INPUT_PULLUP);
  pinMode(OPEN_BUTTON_PIN, INPUT_PULLUP);
  pinMode(CLOSE_BUTTON_PIN, INPUT_PULLUP);
//  digitalWrite(ENABLE_PIN, LOW);  // enable CNC Shield
  for(int i=0; i<4; i++) {
    motors[i].setMaxSpeed(DEFAULT_MAX_SPEED);
    motors[i].setAcceleration(DEFAULT_ACCELERATION);
    max_position[i] = DEFAULT_MAX_POSITION;
  };
  ClearCommandBuffer(); 
  manual.reset();
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
      } else {
        command_buffer[char_ix] = next_char;
        if(char_ix < BUF_LEN) char_ix++;
      };
    };
  };
};

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
//Serial.println(command_buffer);
  long lbuf[4];
  float fbuf[4];
  switch(cmd) {
    case 'X': {
      if(manual_on) {
         Serial.println(MANUAL);
         return;
      }
      for(int n=0; n<4; n++) motors[n].stop();
      Serial.println(SUCCESS);
      return;
    };
    case 'p': {
      for(int i=0; i<4; i++) lbuf[i] = motors[i].currentPosition();
      Serial.print(lbuf[0]); Serial.print(','); Serial.print(lbuf[1]); Serial.print(',');
      Serial.print(lbuf[2]); Serial.print(','); Serial.println(lbuf[3]);
      return;
    };
    case 'w': {
      Serial.print(digitalRead(M0_LIMIT_SWITCH_PIN)); Serial.print(',');
      Serial.print(digitalRead(M1_LIMIT_SWITCH_PIN)); Serial.print(',');
      Serial.print(digitalRead(M2_LIMIT_SWITCH_PIN)); Serial.print(',');
      Serial.println(digitalRead(M3_LIMIT_SWITCH_PIN));
      return;
    };
    case 's': {
      for(int i=0; i<4; i++) fbuf[i] = motors[i].speed();
      Serial.print(fbuf[0]); Serial.print(','); Serial.print(fbuf[1]); Serial.print(',');
      Serial.print(fbuf[2]); Serial.print(','); Serial.println(fbuf[3]);
      return;
    };
    case 'v': {
      for(int i=0; i<4; i++) fbuf[i] = motors[i].maxSpeed();
      Serial.print(fbuf[0]); Serial.print(','); Serial.print(fbuf[1]); Serial.print(',');
      Serial.print(fbuf[2]); Serial.print(','); Serial.println(fbuf[3]);
      return;
    };
    case 'a': {
      for(int i=0; i<4; i++) fbuf[i] = motors[i].acceleration();
      Serial.print(fbuf[0]); Serial.print(','); Serial.print(fbuf[1]); Serial.print(',');
      Serial.print(fbuf[2]); Serial.print(','); Serial.println(fbuf[3]);
      return;
    };
    case 'm': {
      for(int i=0; i<4; i++) lbuf[i] = max_position[i];
      Serial.print(lbuf[0]); Serial.print(','); Serial.print(lbuf[1]); Serial.print(',');
      Serial.print(lbuf[2]); Serial.print(','); Serial.println(lbuf[3]);
      return;
    };
    case 'i': {
      Serial.println(ident);
      return;
    };
  };
  
  int n_petal = DigitToInt(command_buffer[1]); // Convert argument value
  if(n_petal < 0) {
    if(strchr(command_list, cmd))
      Serial.println(WRONG_ID);
    else
      Serial.println(ILL_CMD);
    return;
  };
  switch(cmd) {
    int errcod;
    case 'x': {
      if(manual_on) {
         Serial.println(MANUAL);
         return;
      }
      motors[n_petal].stop();
      Serial.println(SUCCESS);
      return;
    };
    case 'c': {
      if(manual_on) {
         Serial.println(MANUAL);
         return;
      }
      long value = -atol(command_buffer+2);
      motors[n_petal].move(value);
      Serial.println(SUCCESS);
      return;
    };
    case 'o': {
      if(manual_on) {
         Serial.println(MANUAL);
         return;
      }
      long value = atol(command_buffer+2);
      motors[n_petal].move(value);
      Serial.println(SUCCESS);
      return;
    };
    case 'g': {
      if(manual_on) {
         Serial.println(MANUAL);
         return;
      }
      long value = atol(command_buffer+2);
      if(value < 0 || value > max_position[n_petal]) {
        Serial.println(LIMIT);
        return;
      };
      motors[n_petal].moveTo(value);
      Serial.println(SUCCESS);
      return;
    };
    case '0': {
      if(manual_on) {
         Serial.println(MANUAL);
         return;
      }
      motors[n_petal].setCurrentPosition(0);
      Serial.println(SUCCESS);
      return;
    }
    case 'M': {
      long value = atol(command_buffer+2);
      max_position[n_petal] = value;
      Serial.println(SUCCESS);
     return;
    };
    case 'A': {
      float accel = atof(command_buffer+2);
      motors[n_petal].setAcceleration(accel);
      Serial.println(SUCCESS);
      return;
    };
    case 'V': {
      float speedmax = atof(command_buffer+2);
      motors[n_petal].setMaxSpeed(speedmax);
      Serial.println(SUCCESS);
      return;
    };
    default:
      Serial.println(ILL_CMD);
  };
};

void ExecCommand() {              // Execute the command from command buffer,
  if(command_ready) {             // reset the command buffer
    ExecCommandInternal();
    ClearCommandBuffer();
  };
};


void loop() {
  for(int i=0; i<4; i++) motors[i].run();
  float speed = motors[0].speed()+motors[1].speed()+motors[2].speed()+motors[3].speed();
  int what = manual.update(speed);

  int selector = what | 7;
  what |= what & 7;

  switch(what) {
    int n_petal;
    case DO_NOTHING: {
      break;
    };
    case STOP_REQUEST: {
      for(int i=0; i<4; i++) motors[i].stop();
      break;
    };
    case SET_AUTOMATIC: {
      manual_on = false;
      break;
    };
    case SET_MANUAL: {
      manual_on = true;
      break;
    };
    case START_OPEN_REQUEST: {
      n_petal = selector - 1;
      motors[n_petal].move(max_position[n_petal]);
      break;
    };
    case START_CLOSE_REQUEST: {
      n_petal = selector - 1;
      motors[n_petal].move(0);
      break;
    };
  };
  GetCommand();
  ExecCommand();
};
