ORDERBOOK_DEPTH = 500
DB_URI = 'mongodb://localhost:27017'

# Logging verbose levels:
#   20: info
#   30: warning/debug
#   40: error
LOGGING = dict(filename='feedhandler.log', level=20)

# Load any local setting that goes in the file config_local.py
from os.path import isfile
if isfile("./config_local.py"):
    from config_local import *
