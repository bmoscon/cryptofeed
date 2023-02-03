'''
Copyright (C) 2017-2023 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import random

from cryptofeed.exchanges import Binance


def test_binance_address_generation():
    symbols = Binance.symbols()
    channels = [channel for channel in Binance.info()['channels']['websocket'] if not Binance.is_authenticated_channel(channel)]
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
            assert isinstance(addr, list)

            for value in addr:
                value = value.split("=", 1)[1]
                value = value.split("/")
                for entry in value:
                    sym, chan = entry.split("@", 1)
                    syms.append(sym)
                    chans.append(chan)
        assert len(chans) == len(channels) * length == len(syms)
        assert len(set(chans)) == len(channels)
        assert (len(set(syms))) == length
