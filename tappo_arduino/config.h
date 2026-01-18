#ifndef config_h
#define config_h


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

//                            //  Pin per comandi manuali
#define SELECTOR_0_PIN  23    //  Low: attiva motore 0
#define SELECTOR_1_PIN  25    //  Low: attiva motore 1
#define SELECTOR_2_PIN  27    //  Low: attiva motore 2
#define SELECTOR_3_PIN  29    //  Low: attiva motore 3

#define OPEN_BUTTON_PIN     31    //  Low: muove in direzione apertura
#define CLOSE_BUTTON_PIN    33    //  Low: muove in direzione chiusura

#define ENABLE_PIN  8         // Non usato: mettere ponticello

#define DEBOUNCE_TIME 200     // Intervallo verifica debounce (ms)

//  Valori default per microstepping 1/4
#define DEFAULT_MAX_POSITION 54000  // Angolo massimo (step: corrisponde a 270°)
#define DEFAULT_MAX_SPEED     1400  // Velocità max (step/sec: corrisponde a 9°/sec)
#define DEFAULT_ACCELERATION   200  // Accelerazione (step/sec^2)

/*  Valori di default per NO microstepping
#define DEFAULT_MAX_POSITION 13500  // Angolo massimo (step: corrisponde a 270°)
#define DEFAULT_MAX_SPEED      450  // Velocità max (step/sec: corrisponde a 9°/sec)
#define DEFAULT_ACCELERATION    60  // Accelerazione (sep/sec^2)
*/

//                  codici di errore
#define SUCCESS  0    // successo     
#define WRONG_ID 1    // Errore numero petalo
#define NO_EXE   2    // Comando non eseguibile (motore in moto)
#define LIMIT    3    // Comando non eseguibile (intervento limite)
#define ILL_CMD  4    // Comando non riconosciuto
#define MANUAL   5    // comando illegale in modo manuale

#endif
