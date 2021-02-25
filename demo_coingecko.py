'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''

from cryptofeed import FeedHandler
from cryptofeed.providers import Coingecko
from cryptofeed.defines import MARKET_INFO


from cryptofeed.symbols import set_symbol_separator, binance_symbols, gen_symbols

import ccxt

async def minfo(**kwargs):
    print(kwargs)


def main():
    config = {'log': {'filename': 'demo_coingecko.log', 'level': 'DEBUG'}}
    f = FeedHandler(config=config)
    exch = ccxt.binance()
    syms = []
    m = exch.load_markets()
    for sym, mkt in m.items():
        if mkt['info']['status'] != 'BREAK':
            syms.append(sym.replace('/', '-'))
    #set_symbol_separator("/")
    #syms = binance_symbols()
    #syms = gen_symbols("BINANCE")
    #print(syms['HSR/BTC'])
    syms.remove('BQX-BTC')
    syms.remove('SNM-BTC')
    syms.remove('BQX-ETH')
    f.add_feed(Coingecko(symbols=syms, channels=[MARKET_INFO], callbacks={MARKET_INFO: minfo}))
    #f.add_feed(Coingecko(symbols=['BTC-USD', 'ETH-EUR'], channels=[MARKET_INFO], callbacks={MARKET_INFO: minfo}))
    f.run()


if __name__ == '__main__':
    main()
