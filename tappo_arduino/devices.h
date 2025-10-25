
int GetPosition(int n_petal);       // get motor position
int GetDirection(int n_petal);      // get motor direction (-1, 0, 1)
int GetLimitSwitch(int n_petal);    // get limit switch status (1: open, 0: closed)

void MotorControl(int n_motor);     // update motor status
                                    
bool OpenPetal(int n_petal);         // Start motor N to open the petal
                                     // the motor must stop when the max angle is reached
bool ClosePetal(int n_petal);        // Start motor N to close the petal
                                     // The motor stops when the home position is reached

bool StopMotor(int n_petal);        // stop motor N

void InitMotors();                  // initialize motors
void SetupMotors();                 // Setup motors

void SetMaxPosition(int value);
int GetMaxPosition();

char *GetMotorInfo(int n_petal);
