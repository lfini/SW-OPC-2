#ifndef manual_h
#define manual_h

class Selector {
  private:
    int  previous_idx;
    int  _active;
    void set(int n_idx);

  public:
    Selector();
    int update();
};

class PushButtons {
  private:
    int _n_pin_open;
    int _n_pin_close;
    int _prev_value;
    int _value;

  public:
    PushButtons();
    int update();
};

// stati per gestione manuale

#define DO_NOTHING            0
#define STOP_REQUEST          1
#define SET_AUTOMATIC         2
#define SET_MANUAL            3
#define START_OPEN_REQUEST   16  // valore in OR con valore selettore
#define START_CLOSE_REQUEST  32  // valore in OR con valore selettore

#define OPEN_REQUEST  1
#define CLOSE_REQUEST 2

class Manual {
  private:
    int p_selector;
    int p_button;    
    unsigned long next_update;
    Selector selector;
    PushButtons buttons;

  public:
    Manual();
    void reset();
    int update(float speed);
};

#endif manual_h
