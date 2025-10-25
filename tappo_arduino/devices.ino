/*
Interface to hardware: limit switches and motors

*/

#include "config.h"
#include "devices.h"

#define DEBUG_BUF_LEN 100 

static int motor_direction_pin[4];
static int motor_pulse_pin[4];
static int motor_limit_switch_pin[4];
static int motor_pulse_on[4];
static int motor_position[4];      // steps in opening direction (0: at home, i.e.: closed)

static int max_position = 0;
static char debug_buffer[DEBUG_BUF_LEN+1] = "...";

void SetupMotors() {       // Setup motors
  motor_direction_pin[0] = M0_DIRECTION_PIN;
  motor_direction_pin[1] = M1_DIRECTION_PIN;
  motor_direction_pin[2] = M2_DIRECTION_PIN;
  motor_direction_pin[3] = M3_DIRECTION_PIN;
  motor_pulse_pin[0] = M0_PULSE_PIN;
  motor_pulse_pin[1] = M1_PULSE_PIN;
  motor_pulse_pin[2] = M2_PULSE_PIN;
  motor_pulse_pin[3] = M3_PULSE_PIN;
  motor_limit_switch_pin[0] = M0_LIMIT_SWITCH_PIN;
  motor_limit_switch_pin[1] = M1_LIMIT_SWITCH_PIN;
  motor_limit_switch_pin[2] = M2_LIMIT_SWITCH_PIN;
  motor_limit_switch_pin[3] = M3_LIMIT_SWITCH_PIN;
}

void InitMotors() {       // Initialize motor status
  for(int i=0; i<4; i++) {
    pinMode(motor_direction_pin[i], OUTPUT);
    pinMode(motor_pulse_pin[i], OUTPUT);
    pinMode(motor_limit_switch_pin[i], INPUT_PULLUP);
    digitalWrite(motor_direction_pin[i], OPEN);
    motor_pulse_on[i] = 0;
    motor_position[i] = -1;
    digitalWrite(motor_pulse_pin[i], LOW);
  }
}

void MotorControl(int n_petal) { // update motor status, generating pulses
                                 // as necessary. TO BE CALLED AT PROPER FREQUENCY
  bool closing = motor_pulse_on[n_petal] && (digitalRead(motor_direction_pin[n_petal]) == CLOSE);
  bool opening = motor_pulse_on[n_petal] && (digitalRead(motor_direction_pin[n_petal]) == OPEN);
  if(closing) {
    if(GetLimitSwitch(n_petal) == LOW) {  // control stop at closed position
      motor_pulse_on[n_petal] = 0;
      motor_position[n_petal] = 0;
      digitalWrite(motor_pulse_pin[n_petal], LOW);
    }
  } else if(opening) {
    if(motor_position[n_petal] >= max_position) {  // control stop at opened position
      motor_pulse_on[n_petal] = 0;
      digitalWrite(motor_pulse_pin[n_petal], LOW);
    }
  }
  if(motor_pulse_on[n_petal]) {                         // motor is running
    if(digitalRead(motor_pulse_pin[n_petal]) == HIGH)   // generate pulses
      digitalWrite(motor_pulse_pin[n_petal], LOW);
    else 
      digitalWrite(motor_pulse_pin[n_petal], HIGH);
    if(closing) {
        motor_position[n_petal]--;
    } else {
        motor_position[n_petal]++;
    }
  }
}

int GetPosition(int n_petal) {
  return motor_position[n_petal];
}

int GetDirection(int n_petal) {
  int dir = digitalRead(motor_direction_pin[n_petal]);
  if(motor_pulse_on[n_petal]) 
    return (dir == CLOSE) ? -1 : 1;
  return 0;
}

int GetLimitSwitch(int n_petal) {  // legge stato del limit switch
  return digitalRead(motor_limit_switch_pin[n_petal]);
}

bool OpenPetal(int n_petal){       // Start opening petal
                                    // returns true on success
  if(motor_pulse_on[n_petal])
    return false;
  if(motor_position[n_petal] < 0)   // motor has not be homed
    return false;
  if(motor_position[n_petal] >= max_position)
    return false;
  digitalWrite(motor_direction_pin[n_petal], OPEN);
  motor_pulse_on[n_petal] = 1;
  return true;
}

void SetMaxPosition(int value) {  // set angle limit
  max_position = value;
}

int GetMaxPosition() {
  return max_position;
}

bool ClosePetal(int n_petal){     // Starts closing petal
                                  // returns true on success
  if(motor_pulse_on[n_petal])
    return false;
  if(GetLimitSwitch(n_petal) == LOW)
    return false;
  digitalWrite(motor_direction_pin[n_petal], CLOSE);
  motor_pulse_on[n_petal] = 1;
  return true;
}                      
                  
bool StopMotor(int n_petal) {       // stop motor
  motor_pulse_on[n_petal] = 0;
  return true;
}

char *GetMotorInfo(int n_petal) {
  snprintf(debug_buffer, DEBUG_BUF_LEN, "Mot.#%d [pul.pin:%d, dir.pin:%d, lsw.pin:%d] - pulse:%d, direc:%d, pos:%d, lsw:%d", 
           n_petal, motor_pulse_pin[n_petal], motor_direction_pin[n_petal], motor_limit_switch_pin[n_petal],
           motor_pulse_on[n_petal], digitalRead(motor_direction_pin[n_petal]), motor_position[n_petal], GetLimitSwitch(n_petal));
  return debug_buffer;
}
