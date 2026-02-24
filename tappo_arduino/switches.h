#ifndef switches_h
#define switches_h

class Selector {     // Stato commutatore di selezione petali per modo manuale
		     // (con debounce)
  private:
    int  p_idx;
    int  active;
    void set(int n_idx);

  public:
    Selector();
    int update();
};

class PushButtons {  // Stato pulsanti apri/chiudi manuale (con debounce)
  private:
    int p_value;
    int value;

  public:
    PushButtons();
    int update();
};

class LimitSwitch {   // Stato limit switch (con debounce)
  private:
    int mypin;
    int p_value;

  public:
    LimitSwitch();
    LimitSwitch(int pin);
    int value;
    void reset();
    void update();
};

class Magnets {  // Magneti di rilascio
  private:
    int mypin[4];
    unsigned long release_time[4];

  public:
    Magnets();
    void activate(int n_petal);
    void update();
};

// stati per gestione manuale. Il numero di petalo viene introdotto con OR

#define DO_NOTHING              0x10  // == 16
#define STOP_REQUEST            0x20  // == 32
#define SET_AUTOMATIC           0x30  // == 48
#define SET_MANUAL              0x40  // == 64
#define START_OPEN_REQUEST      0x50  // == 80
#define START_CLOSE_REQUEST     0x60  // == 96


class Switches {  // Raccoglie tutti i dispositivi di tipo switch (selettore,
		              // pulsanti apri/chiudi, limit switch (fine corsa)
  private:
    int p_selector;
    int p_button;  
    bool stop_requested;
    unsigned long next_update;
    Selector selector;
    PushButtons buttons;
    LimitSwitch limit_switches[4];

  public:
    Switches();
    void reset(); 
    int update(bool moving);  // da chiamare da loop()
    int lsw(int id);          // legge valore fine corsa dato
};

#endif switches_h
