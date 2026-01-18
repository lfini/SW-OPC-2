#include "manual.h"

Selector::Selector() {   // Stato del commutatore di selezione con "debouncing"
  previous_idx = 0;
  _active = 0;
};

void Selector::set(int n_idx) {
  if(n_idx == previous_idx) {
    _active = n_idx;
  } else {
    previous_idx = n_idx;
  };
};

int Selector::update() {
  if(!digitalRead(SELECTOR_0_PIN))
    set(4);
  else if(!digitalRead(SELECTOR_1_PIN))
    set(8);
  else if(!digitalRead(SELECTOR_2_PIN))
    set(16);
  else if(!digitalRead(SELECTOR_3_PIN))
    set(32);
  else
    set(0);
  return _active;
};


PushButtons::PushButtons() {
  _prev_value = 0;
  _value = 0;
  _n_pin_open = OPEN_BUTTON_PIN;
  _n_pin_close = CLOSE_BUTTON_PIN;
};

int PushButtons::update() {    // imposta valore: 0 -nessun premuto, 1 - premuto open
                               //                 2 - premuto close
                               // Con debounce
  int next;
  if(!digitalRead(OPEN_BUTTON_PIN))
    next = OPEN_REQUEST;
  else if(!digitalRead(CLOSE_BUTTON_PIN))
    next = CLOSE_REQUEST;
  else
    next = 0;
  if(next == _prev_value) {
    _value = next;
  } else {
    _prev_value = next;
  }
  return _value;
};


Manual::Manual() {
  selector = Selector();
  buttons = PushButtons();
  reset();
};

void Manual::reset() {
  p_selector = 0;
  p_button = 0;
  next_update = 0;
};

int Manual::update(float speed) {
  unsigned long now = millis();
  if(now >= next_update) {
    next_update = now + DEBOUNCE_TIME;
    int _selector = selector.update();
    int _button = buttons.update();
    if(_selector != p_selector) {           // cambio di stato commutatore
      if(speed > 0.0) return STOP_REQUEST;  // in moto: richiedi stop
      p_selector = _selector;
      if(_selector == 0) return SET_AUTOMATIC;
      return SET_MANUAL;
    }; 
//     questa sezione riguarda il caso di stato selettore immutato
    if(_selector == 0) return DO_NOTHING;      // modo automatico: nessuna operazione richiesta
    if(_button == p_button) return DO_NOTHING; // modo manuale, ma pulsanti invariati: come sopra
//     questa sezione riguarda il caso di stato pulsanti cambiato in modo manuale
    if(speed != 0.0) return STOP_REQUEST;      // in moto: richiedi stop
    p_button = _button;
    if(_button == 1) return START_OPEN_REQUEST | _selector;
    if(_button == 2) return START_CLOSE_REQUEST | _selector;
    return STOP_REQUEST;
  };
};
