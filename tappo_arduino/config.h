/*
 * Valori relativi alle connessioni:
 *
 * motore  controller
 *    A      B1
 *    B      A2
 *    C      A1
 *    D      B2
 */

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

#define OPEN HIGH     // Direzione apertura (Senso antiorario dal lato asse)
#define CLOSE LOW     // Direzione chiusura (Senso orario dal lato asse) 

#define MOTOR_HALF_PERIOD 100  //(millisec): La velocità del motore risulta
			       // 5 passi al secondo o 9°/sec
