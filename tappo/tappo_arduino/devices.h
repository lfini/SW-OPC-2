// 
// header file for commands 
//

void motor_states(bool moving[4],     // read motors current positions
		  float position[4]); // into provided buffer

void motor_control(int n_motor);           // upodate motor status
                                    
void limit_switches(bool closed[4]);  // read limits switches status
                                      // into provided buffer (true: closed, false: open

bool open_petal(int n_petal);         // Start motor to open the petal
                                      // the motor must stop when the max angle is reached
bool close_petal(int n_petal);        // Start motor to close the petal
                                      // The motor stops when the home position is reached

bool stop_motor(int n_petal);        // stop motor

void init_motors();        // initialize motors

void set_max_position(int value);
