"""
opc package version


Uso:
    python version.py [-f]

dove:
    -f: Versione estesa (include data)
"""

import sys

# __version__ = "0.96"   # prima versione testata in cielo (Dic 2021)
# __version__ = "0.97"   # Corretto errore homer: controllo soglia con shift negativi (Gen 2022)
# __version__ = "1.00"   # Modifica algoritmo di tracking e vari bug fix.
                         # Aggiunti comandi di apertura vano

#__version__ = "1.01"   # Vari bugfix. Aggiornata procedura di setup. Aggiunto selezione
                        # versione attiva

#__version__ = "1.02"   # Aggiunte informazioni piattaforma a file di log

#__version__ = "1.03"   # Aggiunto invio file di log a www.lfini.cloud (da logger e dtracker)

__version__ = "2.0"   # Modificato tutto per unica applicazione di gestione osservazione

__date__ = "Ottobre 2022"

def get_version():
    "recupera versione, come stringa"
    return __version__

if __name__ == "__main__":
    if "-f" in sys.argv:
        print(f"Vers. {__version__} - {__date__}")
    else:
        print(__version__)
