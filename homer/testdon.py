'''
testdon.py - Test per donuts.

Usage:
    python tstdon.py file1 file2

'''

import sys
import donuts

don = donuts.Donuts(refimage=sys.argv[1], image_ext=0, overscan_width=20,
                    prescan_width=20, border=64, normalise=True,
                    exposure='EXPOSURE', subtract_bkg=True, ntiles=32)
shift = don.measure_shift(sys.argv[2])
print()
print('Shift X Y:', shift.x.value, shift.y.value)

