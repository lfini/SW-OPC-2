// Firmware per il controllo dei quattro motori del tappo del telescopio OPC

//******************************************************************
// Comandi definiti per il sistema di controllo (inviati sulla linea seriale)

// Ogni comando è costituito da una stringa compresa fra un carattere '!' (inizio)
// e un carattere ':' (fine comando)

// Ogni comando riceve una risposta costituita da una stringa terminata da '\r\n'
//
// Comandi di interrogazione:
//
// Cod. Risposta  Descrizione
// a    x,y,z,a   Accelerazione per i quattro petali (step/s^2)
// f    A/MN      Automatico/manuale+petalo attivo in modo manuale
// i    xxxxxxx   Identificazione (numero di versione del firmware)
// m    x,y,z,a   Angolo max per i quattro petali (num. step)
// p    x,y,z,a   Posizione dei 4 petali (num. step)
// s    x,y,z,a   Velocità corrente per i quattro petali (step/s)
// v    x,y,z,a   Velocità max per i quattro petali (step/s)
// w    x,y,z,a   Stato limit switch (1: chiuso, 0: aperto)


// Comandi di impostazione valori (NOTA: i petali sono numerati da 1 a 4):
//
// Cod. Risposta  Descrizione
// MNxxx errcod   Imposta valore massimo angolo (in num di step) raggiungibile
//                per petalo N
// ANxxx errcod   Imposta valore accelerazione (steps/sec^2) per petalo N
// VNxxx errcod   Imposta valore velocità massima per petalo N

// Comandi di movimento:
//
// Cod. Risposta  Descrizione
// 0N    errcod   Imposta posizione corrente come 0 per petalo N
// oNxxx errcod   muove petalo N di xxx passi in direzione "apertura"
// cNxxx errcod   muove petalo N di xxx passi in direzione "chiusura"
// gNxxx errcod   muove petalo N a posizione assoluta
// xN    errcod   Stop (interrompe movimento del..) petalo N
// X     errcod   Stop tutti i petali

// Codici di errore:

// 0  Comando eseguito correttamente
// 1  Errore numero petalo
// 2  Comando non eseguibile con motore in movimento
// 3  Comando non eseguibile (posiz. < 0 o posiz. > posiz. max)
// 4  Comando non riconosciuto
// 5  Comando non eseguibile in modo manuale

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

static char* command_list = "xocgMAV0";  // elenco comandi che richiedono indice del
                                         // opetalo

void setup() {
  Serial.begin(9600);
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

  for(int i=0; i<4; i++) {
    motors[i].setMaxSpeed(DEFAULT_MAX_SPEED);
    motors[i].setAcceleration(DEFAULT_ACCELERATION);
    max_position[i] = DEFAULT_MAX_POSITION;
  };
  ClearCommandBuffer(); 
  switches.reset();
};

void GetCommand() {               // Chiamata all'interno del loop per ricevere
                                  // caratteri dalla linea seriale e formare il comando

  if(command_ready) return;       // Comando pronto per esecuzione
  while(Serial.available()){
    char next_char = Serial.read();
    if(command_empty) {           // ignora caratteri non compresi fra '!' e ':'
      if(next_char == '!')        // ricevuto carattere inizio comando
        command_empty = false;
    } else {
      if(next_char == ':') {     // ricevuto carattere fine comando
        command_buffer[char_ix] = '\0';   // aggiunge terminatore stringa
        command_ready = true;
      } else {
        command_buffer[char_ix] = next_char;  // accumula caratteri del comando
        if(char_ix < BUF_LEN) char_ix++;
      };
    };
  };
};

void ClearCommandBuffer() {  // prepara la ricezione di un nuovo comando
  char_ix = 0;
  command_ready = false;
  command_empty = true;
};


void ExecCommandInternal() {          // Esecuzione dei comandi
  char cmd = command_buffer[0];       // estrae primo carattere
  switch(cmd) {
    case 'X': {        // Comando: Stop tutti i petali
      if(manual_on) {  // non ammesso in modo Manuale
         Serial.println(MANUAL);
         return;
      };
      for(int n=0; n<4; n++) motors[n].stop();
      Serial.println(SUCCESS);
      return;
    };
    case 'p': {      // Comando: legge posizione dei quattro motori
      Serial.print(motors[0].currentPosition()); Serial.print(','); 
      Serial.print(motors[1].currentPosition()); Serial.print(',');
      Serial.print(motors[2].currentPosition()); Serial.print(',');
      Serial.println(motors[3].currentPosition());
      return;
    };
    case 'w': {     // Comando: legge stato dei quattro finecorsa
      Serial.print(switches.lsw(0)); Serial.print(',');
      Serial.print(switches.lsw(1)); Serial.print(',');
      Serial.print(switches.lsw(2)); Serial.print(',');
      Serial.println(switches.lsw(3));
      return;
    };
    case 's': {    // Comando: legge velocità dei quattro motori
      Serial.print(motors[0].speed()); Serial.print(','); 
      Serial.print(motors[1].speed()); Serial.print(',');
      Serial.print(motors[2].speed()); Serial.print(','); 
      Serial.println(motors[3].speed());
      return;
    };
    case 'v': {    // Comando: legge velocità massima dei quattro motori
      Serial.print(motors[0].maxSpeed()); Serial.print(','); 
      Serial.print(motors[1].maxSpeed()); Serial.print(',');
      Serial.print(motors[2].maxSpeed()); Serial.print(','); 
      Serial.println(motors[3].maxSpeed());
      return;
    };
    case 'a': {   // Comando: legge accelerazione dei quattro motori
      Serial.print(motors[0].acceleration()); Serial.print(','); 
      Serial.print(motors[1].acceleration()); Serial.print(',');
      Serial.print(motors[2].acceleration()); Serial.print(','); 
      Serial.println(motors[3].acceleration());
      return;
    };
    case 'm': {   // Comando: legge posizione massima dei quattro motori
      Serial.print(max_position[0]); Serial.print(','); 
      Serial.print(max_position[1]); Serial.print(',');
      Serial.print(max_position[2]); Serial.print(','); 
      Serial.println(max_position[3]);
      return;
    };
    case 'f': {   // Comando: legge stato automatico/manuale
      if(manual_on) {
        Serial.print('M');
        Serial.println(cur_selector);
      } else {
        Serial.println('A');
      };
      return;
    };
    case 'i': {   // Comando: legge stringa di identificazione
      Serial.println(ident);
      return;
    };
  };
  
  if(!strchr(command_list, cmd)) {   // controllo validità comando
    Serial.println(ILL_CMD);
    return;
  }

// I comandi seguenti richiedono l'indice del petalo

  int n_motor = command_buffer[1]-'1';    // Converte in intero indice del petalo
  if(n_motor < 0 || n_motor > 3) {        // Controllo indice motore
    Serial.println(WRONG_ID);
    return;
  };
  switch(cmd) {
    int errcod;
    case 'x': {       // Comando: stop motore N
      if(manual_on) { // non valido in modo manuale
         Serial.println(MANUAL);
         return;
      }
      motors[n_motor].stop();
      Serial.println(SUCCESS);
      return;
    };
    case 'c': {      // Comando: inizia movimento in direzione chiusura
      if(manual_on) { // non valido in modo manuale
         Serial.println(MANUAL);
         return;
      }
      long value = -atol(command_buffer+2);  // converte in intero valore spostamento
      motors[n_motor].move(value);
      Serial.println(SUCCESS);
      return;
    };
    case 'o': {    // Comando: inizia movimento in direzione apertura
      if(manual_on) { // non valido in modo manuale
         Serial.println(MANUAL);
         return;
      }
      long value = atol(command_buffer+2);  // converte in intero valore spostamento
      motors[n_motor].move(value);
      Serial.println(SUCCESS);
      return;
    };
    case 'g': {        // Comando: vai a posizione data
      if(manual_on) { // non valido in modo manuale
         Serial.println(MANUAL);
         return;
      }
      long value = atol(command_buffer+2);    // converte in intero valore posizione
      if(value < 0 || value > max_position[n_motor]) {
        Serial.println(LIMIT);
        return;
      };
      motors[n_motor].moveTo(value);
      Serial.println(SUCCESS);
      return;
    };
    case '0': {    // Comando: imposta posizione zero (chiuso)
      motors[n_motor].setCurrentPosition(0);
      Serial.println(SUCCESS);
      return;
    }
    case 'M': {   // Comando: imposta valore massimo posizione
      long value = atol(command_buffer+2);
      max_position[n_motor] = value;
      Serial.println(SUCCESS);
     return;
    };
    case 'A': {   // Comando: imposta valore massimo accelerazione
      float accel = atof(command_buffer+2);
      motors[n_motor].setAcceleration(accel);
      Serial.println(SUCCESS);
      return;
    };
    case 'V': {   // Comando: imposta valore massimo velocità
      float speedmax = atof(command_buffer+2);
      motors[n_motor].setMaxSpeed(speedmax);
      Serial.println(SUCCESS);
      return;
    };
    default:
      Serial.println(ILL_CMD);
  };
};

void ExecCommand() {              // Manda in esecuzione il comando dopo aver
  if(command_ready) {             // verificato  che il commando è pronto
    ExecCommandInternal();
    ClearCommandBuffer();      // predispone accettazione del comando successivo
  };
};

int p_what = 0;

void loop() {
  for(int i=0; i<4; i++) motors[i].run();   // aggiorna stato motori

  bool moving = (motors[0].speed()!=0.0) || (motors[1].speed()!=0.0) ||
                (motors[2].speed()!=0.0) || (motors[3].speed()!=0.0);

  int what = switches.update(moving);   // aggiorna stato dei comandi manuali

  if(what != p_what) {     // determina se i comandi manuali hanno cambiato stato
    p_what = what;
                                 // separa componenti dello stato comamndi manuali
    int selector = what & 0xf;   // posizione selettore
    int cmd = what & 0xf0;       // stato del comlessso comandi manuali
    int n_motor;

#ifdef DEBUG
    Serial.print("# cmd: "); Serial.println(cmd);  // DBG
    Serial.print("# sel: "); Serial.println(selector);  // DBG
#endif

    switch(cmd) {
      case DO_NOTHING: {
        break;
      };
      case STOP_REQUEST: {  // richiesta di stop in seguito a comando manuale
#ifdef DEBUG
        Serial.println("# Stop motori");  // DBG
#endif
        for(int i=0; i<4; i++) motors[i].stop();
        break;
      };
      case SET_AUTOMATIC: {  // terminato stato manuale
        manual_on = false;
        digitalWrite(MANUAL_MODE_LED_PIN, LOW);
        cur_selector = 0;
        break;
      };
      case SET_MANUAL: {    // attivato stato manuale
        manual_on = true;
        digitalWrite(MANUAL_MODE_LED_PIN, HIGH);
        cur_selector = selector;
        break;
      };
      case START_OPEN_REQUEST: {  // Richiesta di apertura manuale
        n_motor = selector - 1;
#ifdef DEBUG
        Serial.print("# apri petalo "); Serial.println(n_motor); // DBG
#endif
        motors[n_motor].moveTo(max_position[n_motor]);
        break;
      };
      case START_CLOSE_REQUEST: {  // richiesta di chiusura manuale
        n_motor = selector - 1;
#ifdef DEBUG
        Serial.print("# chiudi petalo "); Serial.println(n_motor); // DBG
#endif
        motors[n_motor].moveTo(0);
        break;
      };
    };
  };
  GetCommand();    // aggiorna stato comandi
  ExecCommand();   // verifica esecuzione comandi
};
