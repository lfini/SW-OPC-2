#ifndef config_h
#define config_h

//#define DEBUG       // commentare per disabilitare modo debug

#define M1_DIRECTION_PIN 5    // asse X
#define M2_DIRECTION_PIN 6    // asse Y
#define M3_DIRECTION_PIN 7    // asse Z
#define M4_DIRECTION_PIN 13   // asse A

#define M1_PULSE_PIN 2
#define M2_PULSE_PIN 3
#define M3_PULSE_PIN 4
#define M4_PULSE_PIN 12

#define M1_LIMIT_SWITCH_PIN 14
#define M2_LIMIT_SWITCH_PIN 15
#define M3_LIMIT_SWITCH_PIN 16
#define M4_LIMIT_SWITCH_PIN 17

//                            //  Pin per comandi manuali
#define SELECTOR_1_PIN  31    //  Low: attiva motore 1
#define SELECTOR_2_PIN  33    //  Low: attiva motore 2
#define SELECTOR_3_PIN  35    //  Low: attiva motore 3
#define SELECTOR_4_PIN  37    //  Low: attiva motore 4

#define OPEN_BUTTON_PIN     34    //  Low: muove in direzione apertura
#define CLOSE_BUTTON_PIN    36    //  Low: muove in direzione chiusura
#define RELEASE_BUTTON_PIN  38    //  Low: attiva impulso rilascio magneti

//                            // Pin per relé
#define MOTOR_POWER_PIN  41   //  Controllo corrente motori
#define MAGNET_1_PIN     40   //  Attiva magnete 1
#define MAGNET_2_PIN     42   //  Attiva magnete 2
#define MAGNET_3_PIN     44   //  Attiva magnete 3
#define MAGNET_4_PIN     46   //  Attiva magnete 4

#define MANUAL_MODE_LED_PIN 32    //  Led di segnalazione modo manuale

#define ENABLE_PIN  8         // Pin abilitazione Shield-CNC (non usato)

#define DEBOUNCE_TIME 200     // Intervallo verifica debounce (ms)

#define MAGNET_TIME 1000      // Durata impulso per rilascio magneti (ms)

//  Valori default per microstepping 1/4
#define DEFAULT_MAX_POSITION 54000  // Angolo massimo (step: corrisponde a 270°)
#define DEFAULT_MAX_SPEED     1400  // Velocità max (step/sec: corrisponde a 9°/sec)
#define DEFAULT_ACCELERATION   300  // Accelerazione (step/sec^2)

/*  Valori di default per NO microstepping
#define DEFAULT_MAX_POSITION 13500  // Angolo massimo (step: corrisponde a 270°)
#define DEFAULT_MAX_SPEED      450  // Velocità max (step/sec: corrisponde a 9°/sec)
#define DEFAULT_ACCELERATION    60  // Accelerazione (sep/sec^2)
*/

//                  codici di errore
#define SUCCESS  '0'    // successo     
#define WRONG_ID '1'    // Errore numero petalo
#define NO_EXE   '2'    // Comando non eseguibile (motore in moto)
#define LIMIT    '3'    // Comando "g" non eseguibile (intervento limite)
#define ILL_CMD  '4'    // Comando non riconosciuto
#define MANUAL   '5'    // Comando illegale in modo manuale
#define DISABLED '6'    // Driver motori disabilitato

#endif
