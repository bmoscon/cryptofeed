'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import random

from cryptofeed.exchanges import Binance
from cryptofeed.standards import feed_to_exchange


def test_binance_address_generation():
    symbols = Binance.symbols()
    channels = Binance.info()['channels']
    for length in (10, 20, 30, 40, 50, 100, 200, 500, len(symbols)):
        syms = []
        chans = []

        sub = random.sample(symbols, length)
        addr = Binance(symbols=sub, channels=channels)._address()
        if length * len(channels) < 200:
            assert isinstance(addr, str)
            value = addr.split("=", 1)[1]
            value = value.split("/")
            for entry in value:
                sym, chan = entry.split("@", 1)
                syms.append(sym)
                chans.append(chan)
        else:
            assert isinstance(addr, dict)

            for _, value in addr.items():
                value = value.split("=", 1)[1]
                value = value.split("/")
                for entry in value:
                    sym, chan = entry.split("@", 1)
                    syms.append(sym)
                    chans.append(chan)
        assert len(chans) == len(channels) * length == len(syms)
        assert len(set(chans)) == len(channels)
        assert (len(set(syms))) == length
