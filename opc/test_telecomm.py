'''
test_telecomm.py - test per telecomm.py (e onstepdrv.py)

Versione per test con simulatore.
'''

import sys
import random
import time
import unittest
from telecomm import TeleCommunicator
from astro import OPC, loc_st_now

N_TESTS = 50             # Numero di test singoli effettuati
SEC_PREC = .0006         # un po' più di 1/1800
MIN_PREC = .04           # un po' più di 1/30

CMD_DELAY = 0.05         # ritardo invio comandi

class GLOB:
    tcm = None

class TestAll(unittest.TestCase):
    def test_getha(self):
        'Test funzione get_current_ha'
        time.sleep(CMD_DELAY)
        cur_ha = GLOB.tcm.get_current_ha()
        comp_ra = loc_st_now()-cur_ha
        time.sleep(CMD_DELAY)
        cur_ra = GLOB.tcm.get_current_rah()
        self.assertLessEqual(abs(comp_ra-cur_ra), SEC_PREC, msg=f'{cur_ra=}, {comp_ra=}')

    def test_setra(self):
        'Test funzioni set_ra e get_target_ra'
        for _ in range(N_TESTS):
            rand_ra = random.random()*24
            time.sleep(CMD_DELAY)
            GLOB.tcm.set_ra(rand_ra)
            time.sleep(CMD_DELAY)
            set_ra = GLOB.tcm.get_target_ra()
            self.assertLessEqual(abs(rand_ra-set_ra), SEC_PREC, msg=f'{rand_ra=}, {set_ra=}')

    def test_setde(self):
        'Test funzioni set_de e get_target_de'
        for _ in range(N_TESTS):
            rand_de = random.random()*180-90
            time.sleep(CMD_DELAY)
            GLOB.tcm.set_de(rand_de)
            time.sleep(CMD_DELAY)
            set_de = GLOB.tcm.get_target_de()
            self.assertLessEqual(abs(rand_de-set_de), SEC_PREC, msg=f'{rand_de=}, {set_de=}')

#   def test_setaz(self):
#       'Test funzioni set_az e get_az'
#       for _ in range(N_TESTS):
#           rand_az = random.random()*360
#           GLOB.tcm.set_az(rand_az)
#           set_az = GLOB.tcm.get_az()
#           self.assertLessEqual(abs(rand_az-set_az), SEC_PREC, msg=f'{rand_az=}, {set_az=}')

#   def test_setalt(self):
#       'Test funzioni set_alt e get_alt'
#       for _ in range(N_TESTS):
#           rand_alt = random.random()*90
#           GLOB.tcm.set_alt(rand_alt)
#           set_alt = GLOB.tcm.get_alt()
#           self.assertLessEqual(abs(rand_alt-set_alt), SEC_PREC, msg=f'{rand_alt=}, {set_alt=}')

    def test_setlat(self):
        'Test funzioni set_lat e get_lat'
        for _ in range(N_TESTS):
            rand_lat = random.random()*180-90
            time.sleep(CMD_DELAY)
            GLOB.tcm.set_lat(rand_lat)
            time.sleep(CMD_DELAY)
            set_lat = GLOB.tcm.get_lat()
            self.assertLessEqual(abs(rand_lat-set_lat), MIN_PREC, msg=f'{rand_lat=}, {set_lat=}')

    def test_setlon(self):
        'Test funzioni set_lon e get_lon'
        for _ in range(N_TESTS):
            rand_lon = random.random()*180-90
            time.sleep(CMD_DELAY)
            GLOB.tcm.set_lon(rand_lon)
            time.sleep(CMD_DELAY)
            set_lon = GLOB.tcm.get_lon()
            self.assertLessEqual(abs(rand_lon-set_lon), MIN_PREC, msg=f'{rand_lon=}, {set_lon=}')

    def test_setdate(self):
        'Test funzioni set_date e get_date'
        time.sleep(CMD_DELAY)
        GLOB.tcm.set_date()
        time.sleep(CMD_DELAY)
        gdate = GLOB.tcm.get_date()
        cdate = time.strftime('%m:%d:%y')
        self.assertEqual(gdate, cdate)

    def test_settsid(self):
        'Test funzioni set_tsid e get_tsid'
        time.sleep(CMD_DELAY)
        GLOB.tcm.set_tsid()
        tsid_pc = loc_st_now()
        time.sleep(CMD_DELAY)
        tsid_tel = GLOB.tcm.get_tsid()
        self.assertLessEqual(abs(tsid_pc-tsid_tel), SEC_PREC, msg=f'{tsid_pc=}, {tsid_tel=}')

    def test_settime(self):
        'Test funzione set_time'
        time.sleep(CMD_DELAY)
        GLOB.tcm.set_time()
        now = time.localtime()
        time.sleep(CMD_DELAY)
        tel_time = GLOB.tcm.get_ltime()
        tel_uoff = GLOB.tcm.get_utcoffset()
        self.assertEqual(tel_uoff, -1)
        midn = list(now)
        midn[3] = 0
        midn[4] = 0
        midn[5] = 0
        now_hour = (time.mktime(now)-time.mktime(tuple(midn)))/3600
        self.assertLessEqual(abs(now_hour-tel_time), SEC_PREC, msg=f'{now_hour=}, {tel_time=}')


HELP = '''
Usa: '-h' per aiuto
'''

if __name__ == '__main__':
    GLOB.tcm = TeleCommunicator('127.0.0.1', 9753)   # open connection with telescope simulator
    fwmname = GLOB.tcm.get_fmwname()
    if not fwmname:
        print('Errore connessione al simulatore di telescopio')
        sys.exit()
    unittest.main()
