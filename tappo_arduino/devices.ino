/*
Interface to hardware: limit switches and motors

*/

#include "config.h"
#include "devices.h"

typedef struct {
  int direction_pin;
  int pulse_pin;
  int limit_switch_pin;
  int max_position;
  int direction;
  long timer;
  bool pulse_on;
  int position;      // steps in opening direction (0: at home, i.e.: closed)
} Motor;

Motor motors[4];

int fake_switch[4];
int max_position = 0;
bool test_mode = false;

void InitMotors() {       // Initialize motors
  pinMode(M0_DIRECTION_PIN, OUTPUT);
  pinMode(M1_DIRECTION_PIN, OUTPUT);
  pinMode(M2_DIRECTION_PIN, OUTPUT);
  pinMode(M3_DIRECTION_PIN, OUTPUT);
  pinMode(M0_PULSE_PIN, OUTPUT);
  pinMode(M1_PULSE_PIN, OUTPUT);
  pinMode(M2_PULSE_PIN, OUTPUT);
  pinMode(M3_PULSE_PIN, OUTPUT);
  pinMode(M0_LIMIT_SWITCH_PIN, INPUT_PULLUP);
  pinMode(M1_LIMIT_SWITCH_PIN, INPUT_PULLUP);
  pinMode(M2_LIMIT_SWITCH_PIN, INPUT_PULLUP);
  pinMode(M3_LIMIT_SWITCH_PIN, INPUT_PULLUP);

  motors[0].direction_pin = M0_DIRECTION_PIN;
  motors[1].direction_pin = M1_DIRECTION_PIN;
  motors[2].direction_pin = M2_DIRECTION_PIN;
  motors[3].direction_pin = M3_DIRECTION_PIN;
  motors[0].pulse_pin = M0_PULSE_PIN;
  motors[1].pulse_pin = M1_PULSE_PIN;
  motors[2].pulse_pin = M2_PULSE_PIN;
  motors[3].pulse_pin = M3_PULSE_PIN;
  motors[0].limit_switch_pin = M0_LIMIT_SWITCH_PIN;
  motors[1].limit_switch_pin = M1_LIMIT_SWITCH_PIN;
  motors[2].limit_switch_pin = M2_LIMIT_SWITCH_PIN;
  motors[3].limit_switch_pin = M3_LIMIT_SWITCH_PIN;
  for(int i=0; i<4; i++) {
    motors[i].direction = OPEN;
    motors[i].pulse_on = false;
    motors[i].position = -1;
    motors[i].timer = millis();
    digitalWrite(motors[i].pulse_pin, LOW);
  }
}

void MotorControl(int n_motor) { // update motor status, generating pulses
                                  // as necessary
  Motor motor = motors[n_motor];
  if(motor.timer < millis()) {
    if(digitalRead(motor.limit_switch_pin) == LOW) {
      motor.pulse_on = false;
      motor.position = 0;
      digitalWrite(motor.pulse_pin, LOW);
    } else
      if(motor.position >= motor.max_position) {
        motor.pulse_on = false;
        digitalWrite(motor.pulse_pin, LOW);
      }
    if(motor.pulse_on) {        // motor is running
      if(digitalRead(motor.pulse_pin) == HIGH)
        digitalWrite(motor.pulse_pin, LOW);
      else
        digitalWrite(motor.pulse_pin, HIGH);
        if(motor.direction == OPEN)
          motor.position++;
        else
          motor.position--;
    }
    motor.timer = millis()+MOTOR_HALF_PERIOD;
  } 
}

void MotorStates(bool moving[4],      // return motors running status
                  int position[4]) {   // and position (in steps from closed position)
  for(int i=0; i<4; i++) {
    moving[i] = motors[i].pulse_on;
    position[i] = motors[i].position;
  }
}

void LimitSwitches(bool buffer[4]){ // returns status of limit switches
                                     // true: closed, fasle:open
  if(test_mode)
    for(int i=0; i<4; i++)
      buffer[i] = fake_switch[i];
  else
    for(int i=0; i<4; i++)
      buffer[i] = digitalRead(motors[i].limit_switch_pin);
}

bool OpenPetal(int n_petal){       // Start opening petal
                                    // returns true on success
  if(motors[n_petal].pulse_on)
    return false;
  if(motors[n_petal].position < 0)   // motor has not be homed
    return false;
  motors[n_petal].direction = OPEN;
  motors[n_petal].pulse_on = true;
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
  if(motors[n_petal].pulse_on)
    return false;
  if(digitalRead(motors[n_petal].limit_switch_pin) == LOW)
    return false;
  motors[n_petal].direction = CLOSE;
  motors[n_petal].pulse_on = true;
  return true;
}                      
                  
bool StopMotor(int n_petal) {       // stop motor
  motors[n_petal].pulse_on = false;
  return true;
}

// --------------------  Test mode support functions

void SetTestMode() {
  test_mode = true;
  for(int i=0; i<4; i++) {         // simulate system at home
    motors[i].position = 0;
    fake_switch[i] = LOW;      // fake switches set as closed
  }
}

bool SetFakeSwitch(int n_petal, int mode) {
  bool ret = false;
  if(test_mode) {
    ret = true; 
    fake_switch[n_petal] = mode;
  }
  return ret;
}

bool IsTestMode() {
  return test_mode;
}

