'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

import requests


LOG = logging.getLogger('feedhandler')


def gen_pairs():
    ret = {}
    defaults = ['btcusd', 'ethusd', 'ethbtc','zecusd','zecbtc','zeceth','zecbch','zecltc','bchusd','bchbtc','bcheth','ltcusd','ltcbtc','ltceth','ltcbch']

    try:
        r = requests.get('https://api.gemini.com/v1/symbols').json()
    except Exception:
        LOG.warning("Gemini: encountered an exception generating trading pairs, using defaults", exc_info=True)
        r = defaults

    for pair in r:
        std = "{}-{}".format(pair[:-3], pair[-3:])
        std = std.upper()
        ret[std] = pair

    return ret


gemini_pair_mapping = gen_pairs()
