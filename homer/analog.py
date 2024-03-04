'''
analog.py - parse Homer logfile to get drift data

Usage:

    python analog.py <logfile>

'''
import sys
import re

SHIFT = re.compile('Computed shift [^:]*: [(]([^,]*)[,] ([^)]*)[)]')
MOVE =   re.compile('Computed move [^:]*: [(]([^,]*)[,] ([^)]*)[)]')

def get_data(fname):
    '''
    Extract drift data from the homer log file

    Parameters
    ----------
    fname : str
       Logfile name

    Returns
    -------
    driftdata : dict
        keys: xpix, ypix, ras, dec
'''
    shift = []
    move = []
    with open(fname, encoding='utf8') as f_in:
        for line in f_in:
            if mtch := SHIFT.search(line):
                xsh = float(mtch.group(1))
                ysh = float(mtch.group(2))
                shift.append((xsh, ysh))
            elif mtch := MOVE.search(line):
                ras = float(mtch.group(1))
                dec = float(mtch.group(2))
                move.append((ras, dec))
    return {'shift': shift, 'move': move}

if __name__ == '__main__':
    if len(sys.argv) == 1:
        print(__doc__)
        sys.exit()
    ret = get_data(sys.argv[1])
    print(ret)
