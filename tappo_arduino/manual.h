#ifndef manual_h
#define manual_h

class Selector {
  private:
    int  p_idx;
    int  active;
    void set(int n_idx);

  public:
    Selector();
    int update();
};

class PushButtons {
  private:
    int p_value;
    int value;

  public:
    PushButtons();
    int update();
};

// stati per gestione manuale. Il numero di petalo viene introdotto con OR

#define DO_NOTHING           0x10  // == 16
#define STOP_REQUEST         0x20  // == 32
#define SET_AUTOMATIC        0x30  // == 48
#define SET_MANUAL           0x40  // == 64
#define START_OPEN_REQUEST   0x50  // == 80
#define START_CLOSE_REQUEST  0x60  // == 96

class Manual {
  private:
    int p_selector;
    int p_button;  
    bool stop_requested;
    unsigned long next_update;
    Selector selector;
    PushButtons buttons;

  public:
    Manual();
    void reset();
    int update(float speed);
};

#endif manual_h
