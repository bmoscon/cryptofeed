'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import requests
import logging

LOG = logging.getLogger('bitstamp.pairs')

def gen_pairs():
    ret = {}
    r = requests.get('https://www.bitstamp.net/api/v2/trading-pairs-info/').json()
    for data in r:
        normalized = data['name'].replace("/", "-")
        pair = data['url_symbol']
        ret[normalized] = pair
    return ret

try:
    bitstamp_pair_mapping = gen_pairs()
except:
    LOG.exception("Unable to get pairs from Bitstamp")
    bitstamp_pair_mapping = None
