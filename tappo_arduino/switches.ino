#include "switches.h"

Selector::Selector() {   // Stato del commutatore di selezione con "debouncing"
  p_idx = 0;
  active = 0;
};

void Selector::set(int n_idx) {
  if(n_idx == p_idx) {
    active = n_idx;
  } else {
    p_idx = n_idx;
  };
};

int Selector::update() {
  if(!digitalRead(SELECTOR_0_PIN))
    set(1);
  else if(!digitalRead(SELECTOR_1_PIN))
    set(2);
  else if(!digitalRead(SELECTOR_2_PIN))
    set(3);
  else if(!digitalRead(SELECTOR_3_PIN))
    set(4);
  else
    set(0);
  return active;
};

LimitSwitch::LimitSwitch() {
  mypin = 0;
  p_value = 0;
  value = 0;
};

LimitSwitch::LimitSwitch(int pin) {
  mypin = pin;
  p_value = 0;
  value = 0;
};

void LimitSwitch::reset() {
   p_value = 0;
   value = 0;
};

void LimitSwitch::update() {
  int val = digitalRead(mypin);
  if(val == p_value)
    value = val;
  else
    p_value = val;
}


PushButtons::PushButtons() {
  p_value = 0;
  value = 0;
};

int PushButtons::update() {    // imposta valore: 0 - nessun premuto, 1 - premuto open
                               //                 2 - premuto close
                               // Con debounce
  int next;
  if(!digitalRead(OPEN_BUTTON_PIN))
    next = 1;
  else if(!digitalRead(CLOSE_BUTTON_PIN))
    next = 2;
  else
    next = 0;
  if(next == p_value) {
    value = next;
  } else {
    p_value = next;
  }
  return value;
};


Switches::Switches() {
  selector = Selector();
  buttons = PushButtons();
  limit_switches[0] = LimitSwitch(M0_LIMIT_SWITCH_PIN);
  limit_switches[1] = LimitSwitch(M1_LIMIT_SWITCH_PIN);
  limit_switches[2] = LimitSwitch(M2_LIMIT_SWITCH_PIN);
  limit_switches[3] = LimitSwitch(M3_LIMIT_SWITCH_PIN);
  reset();
};

void Switches::reset() {
  p_selector = 0;
  p_button = 0;
  stop_requested = false;
  next_update = 0;
  for(int i=0; i<4; i++) limit_switches[i].reset();
};

int Switches::update(bool moving) {
  unsigned long now = millis();
  if(now >= next_update) {
    next_update = now + DEBOUNCE_TIME;
    for(int i=0; i<4; i++) limit_switches[i].update();
    if(stop_requested) {
      if(moving) return DO_NOTHING;
      stop_requested = false;
    }
    int _selector = selector.update();
    int _button = buttons.update();
    if(_selector != p_selector) {           // cambio di stato commutatore
#ifdef DEBUG
      Serial.print("# speed: "); Serial.println(speed); // DBG
#endif
      if(moving) {
        stop_requested = true;
        return STOP_REQUEST;  // in moto: richiedi stop
      };
      p_selector = _selector;
      if(_selector == 0) return SET_AUTOMATIC;
      return SET_MANUAL | _selector;
    }; 
//     questa sezione riguarda il caso di stato selettore immutato
    if(_selector == 0) return DO_NOTHING;      // modo automatico: nessuna operazione richiesta
    if(_button == p_button) return DO_NOTHING; // modo manuale, ma pulsanti invariati: come sopra
//     questa sezione riguarda il caso di stato pulsanti cambiato in modo manuale
    if(moving) {
      stop_requested = true;
      return STOP_REQUEST;      // in moto: richiedi stop
    };
    p_button = _button;
    if(_button == 1) return START_OPEN_REQUEST | _selector;
    if(_button == 2) return START_CLOSE_REQUEST | _selector;
    stop_requested = true;
    return STOP_REQUEST;
  };
};

int Switches::lsw(int idx) {
   return limit_switches[idx].value;
};
