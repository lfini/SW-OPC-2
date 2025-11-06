
#define M0_DIRECTION_PIN 5    // asse X
#define M1_DIRECTION_PIN 6    // asse Y
#define M2_DIRECTION_PIN 7    // asse Z
#define M3_DIRECTION_PIN 13   // asse A

#define M0_PULSE_PIN 2
#define M1_PULSE_PIN 3
#define M2_PULSE_PIN 4
#define M3_PULSE_PIN 12

#define M0_LIMIT_SWITCH_PIN 14
#define M1_LIMIT_SWITCH_PIN 15
#define M2_LIMIT_SWITCH_PIN 16
#define M3_LIMIT_SWITCH_PIN 17

#define OPEN HIGH     // motor direction to open the petal
#define CLOSE LOW     // motor direction to close the petal

#define MOTOR_HALF_PERIOD 100  //(millisec): motor speed is thus
			       // 5 steps per second or 9°/sec
