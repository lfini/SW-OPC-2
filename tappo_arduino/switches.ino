#include "switches.h"

/*
   supporto per il controllo dei dispositivi elettro-meccanici: microswitch di
   fine-corsa, commutatore di selezione motore manuale, e pulsanti per il
   movimento manuale.

   Nota: il debouncing richiede che i metodi update() delle classi seguenti
         vengano chiamate a intervalli opportuni (es: 200 millisec).
         La temporizzazione è implementata all'interno della classe Switches
*/

// class Selector:  stato del commutatore di selezione con "debouncing"
Selector::Selector() {
  p_idx = 0;
  active = 0;
};

void Selector::set(int n_idx) {  // Aggiorna valore se uguale al precedente
  if(n_idx == p_idx) {
    active = n_idx;
  } else {
    p_idx = n_idx;
  };
};

int Selector::update() {     // da chiamare periodicamente
  if(!digitalRead(SELECTOR_1_PIN))
    set(1);
  else if(!digitalRead(SELECTOR_2_PIN))
    set(2);
  else if(!digitalRead(SELECTOR_3_PIN))
    set(3);
  else if(!digitalRead(SELECTOR_4_PIN))
    set(4);
  else
    set(0);
  return active;
};

// class LimitSwitch:  stato di un microswitch di fine-corsa con "debouncing"
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


// class PushButtons:  stato congiunto dei due pulsanti di movimento manuale
//                     con "debouncing"

//                     Lo stato assume i seguenti valori:
//                     0 - nessun premuto,  1 - premuto apri,  2 - premuto chiudi

PushButtons::PushButtons() {
  p_value = 0;
  value = 0;
};

int PushButtons::update() {    //
                               //             
                               // Con debounce
  int next;
  if(!digitalRead(OPEN_BUTTON_PIN))
    next = 1;
  else if(!digitalRead(CLOSE_BUTTON_PIN))
    next = 2;
  else if(!digitalRead(RELEASE_BUTTON_PIN))
    next = 3;
  else
    next = 0;
  if(next == p_value) {
    value = next;
  } else {
    p_value = next;
  }
  return value;
};


// class Switches:  stato congiunto di tutti i dispositivi elettromeccanici
Switches::Switches() {
  selector = Selector();
  buttons = PushButtons();
  limit_switches[0] = LimitSwitch(M1_LIMIT_SWITCH_PIN);
  limit_switches[1] = LimitSwitch(M2_LIMIT_SWITCH_PIN);
  limit_switches[2] = LimitSwitch(M3_LIMIT_SWITCH_PIN);
  limit_switches[3] = LimitSwitch(M4_LIMIT_SWITCH_PIN);
  reset();
};

void Switches::reset() {
  p_selector = 0;
  p_button = 0;
  stop_requested = false;
  next_update = 0;
  for(int i=0; i<4; i++) limit_switches[i].reset();
};

int Switches::update(bool moving) {  // aggiornamento stato. Viene chiamato ad ogni
                                     // ciclo del loop(), la temporizzazione
                                     // è implementata internamente
  unsigned long now = millis();
  if(now >= next_update) {           // controllo temporizzazione
    next_update = now + DEBOUNCE_TIME;
    for(int i=0; i<4; i++) limit_switches[i].update();
    if(stop_requested) {
      if(moving) return DO_NOTHING;
      stop_requested = false;
    }
    int _selector = selector.update();
    int _button = buttons.update();
    if(_selector != p_selector) {           // cambio di stato commutatore
      if(moving) {
        stop_requested = true;
        return STOP_REQUEST;  // in moto: richiedi stop
      };
      p_selector = _selector;
      if(_selector == 0) return SET_AUTOMATIC;
      return SET_MANUAL | _selector;
    }; 

//     questa sezione riguarda il caso di stato selettore immutato
    if(_selector == 0) return DO_NOTHING;      // modo automatico: nessuna operazione
                                               // richiesta
    if(_button == p_button) return DO_NOTHING; // modo manuale, ma pulsanti invariati:
                                               // come sopra

//     questa sezione riguarda il caso di stato pulsanti cambiato in modo manuale
    if(moving) {       // stato cambiato durante un movimento: richeista di stop
      stop_requested = true;
      return STOP_REQUEST;
    };
    p_button = _button;

    if(_button == 1)      // richiesta apertura
      return START_OPEN_REQUEST | _selector;

    if(_button == 2)     // richiesta chiusura
      return START_CLOSE_REQUEST | _selector;

    if(_button == 3)     // richiesta rilascio magnete
      return MAGNET_RELEASE_REQUEST | _selector;

    // Nessun pulsante premuto: richiesta di stop
    stop_requested = true;
    return STOP_REQUEST;
  };
};

int Switches::lsw(int idx) {   // richiesta stato di limit switch
   return limit_switches[idx].value;
};


Magnets::Magnets() {
  mypin[0] = MAGNET_1_PIN;
  mypin[1] = MAGNET_2_PIN;
  mypin[2] = MAGNET_3_PIN;
  mypin[3] = MAGNET_4_PIN;
  for(int i=0; i<4; i++) release_time[i] = 0;
};

void Magnets::activate(int idx) {
  digitalWrite(mypin[idx], HIGH);
  release_time[idx] = millis()+MAGNET_TIME;
};

void Magnets::update() {
  unsigned long now = millis();
  for(int i=0; i<4; i++)
    if(now >= release_time[i])
      digitalWrite(mypin[i], LOW);
};

