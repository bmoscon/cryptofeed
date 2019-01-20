'''
Copyright (C) 2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

import requests


LOG = logging.getLogger('feedhandler')


def gen_pairs():
    r = requests.get('https://api.exx.com/data/v1/tickers').json()

    exchange = [key.upper() for key in r.keys()]
    pairs = [key.replace("_", "-") for key in exchange]
    return {pair: exchange for pair, exchange in zip(pairs, exchange)}


exx_pair_mapping = gen_pairs()
