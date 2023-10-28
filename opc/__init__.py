import os, sys

THIS_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(THIS_DIR, '..', 'dome')))

import dome_ctrl
