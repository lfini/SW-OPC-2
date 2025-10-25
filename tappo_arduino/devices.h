
char *GetPetalStatus(int n_petal);    // get status of petal: M, D, P, L

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

char *GetDebugInfo(int n_petal);
