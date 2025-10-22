// 
// header file for commands 
//

void MotorStates(bool moving[4],     // read motors current positions
		              int position[4]);   // into provided buffer

void MotorControl(int n_motor);       // upodate motor status
                                    
void LimitSwitches(int closed[4]);    // read limits switches status
                                      // into provided buffer (0: closed, 1: open)

bool OpenPetal(int n_petal);         // Start motor N to open the petal
                                     // the motor must stop when the max angle is reached
bool ClosePetal(int n_petal);        // Start motor N to close the petal
                                     // The motor stops when the home position is reached

bool StopMotor(int n_petal);        // stop motor N

void InitMotors();                  // initialize motors

void SetMaxPosition(int value);
int GetMaxPosition();

// test mode support functions

void SetTestMode();
bool IsTestMode();
bool SetFakeSwitch(int n_petal, int mode);
