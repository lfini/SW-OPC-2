
// Comandi definiti per il sistema di controllo
// Ogni comando è costituito da una stringa compresa fra un carattere '!' (inizio)
// e un carattere ':' (fine comando)

// Ogni comando riceve una risposta costituita da una stringa terminata da '\r\n'
//
// Comandi di interrogazione:
//
// Cod. Risposta  Descrizione
// a    x,y,z,a   Accelerazione per i quattro petali (step/s^2)
// f    A/MN      Automatico/manuale+petalo attivo in modo manuale1
// i    xxxxxxx   Identificazione (numero di versione del firmware)
// m    x,y,z,a   Angolo max per i quattro petali (num. step)
// p    x,y,z,a   Posizione dei 4 petali (num. step)
// s    x,y,z,a   Velocità corrente per i quattro petali (step/s)
// v    x,y,z,a   Velocità max per i quattro petali (step/s)
// w    x,y,z,a   Stato limit switch (1: chiuso, 0: aperto)


// Comandi di impostazione valori (NOTA: i petali sono numerati da 1 a 4):
//
// Cod. Risposta  Descrizione
// MNxxx errcod   Imposta valore massimo angolo (in num di step) raggiungibile per petalo N
// ANxxx errcod   Imposta valore accelerazione (steps/sec^2) per petalo N
// VNxxx errcod   Imposta valore velocità massima per petalo N

// Comandi di movimento:
//
// Cod. Risposta  Descrizione
// 0N    errcod    Imposta posizione corrente come 0 per petalo N
// oNxxx errcod    muove petalo N di xxx passi in direzione "apertura"
// cNxxx errcod    muove petalo N di xxx passi in direzione "chiusura"
// gNxxx errcod    muove petalo N a posizione assoluta
// xN    errcod    Stop (interrompe movimento del..) petalo N
// X     errcod    Stop tutti i petali

#include <AccelStepper.h>
#include "config.h"
#include "switches.h"

#define BUF_LEN 22
#define REPLY_BUF_LEN 100

#define MOTOR_IF_TYPE AccelStepper::DRIVER

#ifdef DEBUG
char *ident = "Tappo OPC v. 3.1 - DEBUG";
#else
char *ident = "Tappo OPC v. 3.1";
#endif

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
int cur_selector = 0;

Switches switches;

static char* command_list = "afimpsvwMAV0ocgxX";


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
  pinMode(MANUAL_MODE_LED_PIN, OUTPUT);
  digitalWrite(MANUAL_MODE_LED_PIN, LOW);
//  digitalWrite(ENABLE_PIN, LOW);  // enable CNC Shield

  for(int i=0; i<4; i++) {
    motors[i].setMaxSpeed(DEFAULT_MAX_SPEED);
    motors[i].setAcceleration(DEFAULT_ACCELERATION);
    max_position[i] = DEFAULT_MAX_POSITION;
  };
  ClearCommandBuffer(); 
  switches.reset();
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


void ExecCommandInternal() {          // actual command executor
  char cmd = command_buffer[0];
//Serial.println(command_buffer);
  switch(cmd) {
    case 'X': {
      if(manual_on) {
         Serial.println(MANUAL);
         return;
      };
      for(int n=0; n<4; n++) motors[n].stop();
      Serial.println(SUCCESS);
      return;
    };
    case 'p': {
      Serial.print(motors[0].currentPosition()); Serial.print(','); 
      Serial.print(motors[1].currentPosition()); Serial.print(',');
      Serial.print(motors[2].currentPosition()); Serial.print(',');
      Serial.println(motors[3].currentPosition());
      return;
    };
    case 'w': {
      Serial.print(switches.lsw(0)); Serial.print(',');
      Serial.print(switches.lsw(1)); Serial.print(',');
      Serial.print(switches.lsw(2)); Serial.print(',');
      Serial.println(switches.lsw(3));
      return;
    };
    case 's': {
      Serial.print(motors[0].speed()); Serial.print(','); 
      Serial.print(motors[1].speed()); Serial.print(',');
      Serial.print(motors[2].speed()); Serial.print(','); 
      Serial.println(motors[3].speed());
      return;
    };
    case 'v': {
      Serial.print(motors[0].maxSpeed()); Serial.print(','); 
      Serial.print(motors[1].maxSpeed()); Serial.print(',');
      Serial.print(motors[2].maxSpeed()); Serial.print(','); 
      Serial.println(motors[3].maxSpeed());
      return;
    };
    case 'a': {
      Serial.print(motors[0].acceleration()); Serial.print(','); 
      Serial.print(motors[1].acceleration()); Serial.print(',');
      Serial.print(motors[2].acceleration()); Serial.print(','); 
      Serial.println(motors[3].acceleration());
      return;
    };
    case 'm': {
      Serial.print(max_position[0]); Serial.print(','); 
      Serial.print(max_position[1]); Serial.print(',');
      Serial.print(max_position[2]); Serial.print(','); 
      Serial.println(max_position[3]);
      return;
    };
    case 'f': {
      if(manual_on) {
        Serial.print('M');
        Serial.println(cur_selector);
      } else {
        Serial.println('A');
      };
      return;
    };
    case 'i': {
      Serial.println(ident);
      return;
    };
  };
  
  int n_motor = command_buffer[1]-'1';    // Convert argument value
  if(n_motor < 0 || n_motor > 3) {
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
      motors[n_motor].stop();
      Serial.println(SUCCESS);
      return;
    };
    case 'c': {
      if(manual_on) {
         Serial.println(MANUAL);
         return;
      }
      long value = -atol(command_buffer+2);
      motors[n_motor].move(value);
      Serial.println(SUCCESS);
      return;
    };
    case 'o': {
      if(manual_on) {
         Serial.println(MANUAL);
         return;
      }
      long value = atol(command_buffer+2);
      motors[n_motor].move(value);
      Serial.println(SUCCESS);
      return;
    };
    case 'g': {
      if(manual_on) {
         Serial.println(MANUAL);
         return;
      }
      long value = atol(command_buffer+2);
      if(value < 0 || value > max_position[n_motor]) {
        Serial.println(LIMIT);
        return;
      };
      motors[n_motor].moveTo(value);
      Serial.println(SUCCESS);
      return;
    };
    case '0': {
      if(manual_on) {
         Serial.println(MANUAL);
         return;
      }
      motors[n_motor].setCurrentPosition(0);
      Serial.println(SUCCESS);
      return;
    }
    case 'M': {
      long value = atol(command_buffer+2);
      max_position[n_motor] = value;
      Serial.println(SUCCESS);
     return;
    };
    case 'A': {
      float accel = atof(command_buffer+2);
      motors[n_motor].setAcceleration(accel);
      Serial.println(SUCCESS);
      return;
    };
    case 'V': {
      float speedmax = atof(command_buffer+2);
      motors[n_motor].setMaxSpeed(speedmax);
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

int p_what = 0;

void loop() {
  for(int i=0; i<4; i++) motors[i].run();
  bool moving = (motors[0].speed()!=0.0) || (motors[1].speed()!=0.0) ||
                (motors[2].speed()!=0.0) || (motors[3].speed()!=0.0);
  int what = switches.update(moving);
  if(what != p_what) {
    p_what = what;

    int selector = what & 0xf;
    int cmd = what & 0xf0;
    int n_motor;

#ifdef DEBUG
    Serial.print("# cmd: "); Serial.println(cmd);  // DBG
    Serial.print("# sel: "); Serial.println(selector);  // DBG
#endif

    switch(cmd) {
      case DO_NOTHING: {
        break;
      };
      case STOP_REQUEST: {
#ifdef DEBUG
        Serial.println("# Stop motori");  // DBG
#endif
        for(int i=0; i<4; i++) motors[i].stop();
        break;
      };
      case SET_AUTOMATIC: {
        manual_on = false;
        digitalWrite(MANUAL_MODE_LED_PIN, LOW);
        cur_selector = 0;
        break;
      };
      case SET_MANUAL: {
        manual_on = true;
        digitalWrite(MANUAL_MODE_LED_PIN, HIGH);
        cur_selector = selector;
        break;
      };
      case START_OPEN_REQUEST: {
        n_motor = selector - 1;
#ifdef DEBUG
        Serial.print("# apri petalo "); Serial.println(n_motor); // DBG
#endif
        motors[n_motor].moveTo(max_position[n_motor]);
        break;
      };
      case START_CLOSE_REQUEST: {
        n_motor = selector - 1;
#ifdef DEBUG
        Serial.print("# chiudi petalo "); Serial.println(n_motor); // DBG
#endif
        motors[n_motor].moveTo(0);
        break;
      };
    };
  };
  GetCommand();
  ExecCommand();
};
