import collections
import os
import time
from datetime import datetime

from cryptofeed import FeedHandler
from cryptofeed.defines import TRADES


# Gathers the first trade of each exchange and prints out info on the timestamps.
# To add an exchange, setup exch_sym_map with the most liquid symbol.
# Sample output:
'''
$ python demo_checki_trade_timestamps.py
Starting: 1562808668.105481
[0]: Subscribing to Binance
[1]: Subscribing to Bitfinex
[2]: Subscribing to BitMEX
[3]: Subscribing to Bitstamp
[4]: Subscribing to Bybit
[5]: Subscribing to Coinbase
[6]: Subscribing to Deribit
[7]: Subscribing to EXX
[8]: Subscribing to Gemini
[9]: Subscribing to HitBTC
[10]: Subscribing to Huobi
[11]: Subscribing to Kraken
[12]: Subscribing to OKCoin
[13]: Subscribing to OKEx
[14]: Subscribing to Poloniex
Added OKEX.
Added EXX.
Added OKCOIN.
Added HUOBI.
Added BINANCE.
Added BYBIT.
Added KRAKEN.
Added COINBASE.
Added BITMEX.
Added BITFINEX.
Added HITBTC.
Added DERIBIT.
Added BITSTAMP.
Added GEMINI.
Added POLONIEX.
BINANCE     : timestamp:1562808676.172       <class 'float'> 2019-07-11 09:31:16.172000
BITFINEX    : timestamp:1562808659.325       <class 'float'> 2019-07-11 09:30:59.325000
BITMEX      : timestamp:1562808675.125       <class 'float'> 2019-07-11 09:31:15.125000
BITSTAMP    : timestamp:1562808680.724683    <class 'float'> 2019-07-11 09:31:20.724683
BYBIT       : timestamp:1562808676.485       <class 'float'> 2019-07-11 09:31:16.485000
COINBASE    : timestamp:1562808676.184       <class 'float'> 2019-07-11 09:31:16.184000
DERIBIT     : timestamp:1562808678.384       <class 'float'> 2019-07-11 09:31:18.384000
EXX         : timestamp:1562808674.0         <class 'float'> 2019-07-11 09:31:14
GEMINI      : timestamp:1562808706.132       <class 'float'> 2019-07-11 09:31:46.132000
HITBTC      : timestamp:1562808491.473       <class 'float'> 2019-07-11 09:28:11.473000
HUOBI       : timestamp:1562808675.644       <class 'float'> 2019-07-11 09:31:15.644000
KRAKEN      : timestamp:1562808676.238593    <class 'float'> 2019-07-11 09:31:16.238593
OKCOIN      : timestamp:1562808671.739       <class 'float'> 2019-07-11 09:31:11.739000
OKEX        : timestamp:1562808675.317       <class 'float'> 2019-07-11 09:31:15.317000
POLONIEX    : timestamp:1562808726.0         <class 'float'> 2019-07-11 09:32:06
Ending: 1562808727.693259
'''


async def trade(data, receipt):
    exchange = data.exchange
    if exchange not in trades:
        print(f'Added {exchange}.')
        # exch_count += 1
        trades[exchange]['timestamp'] = data.timestamp
        trades[exchange]['id'] = data.id
        if exchanges == set(trades.keys()):
            for e in sorted(exchanges):
                ts = trades[e]['timestamp']
                print(f'{e:12s}:', end='')
                try:
                    print(f' timestamp:{str(ts):<20} {type(ts)} {datetime.fromtimestamp(ts)}')
                except TypeError as e:
                    print(e)
            print(f'Ending: {time.time()}')
            os._exit(0)


def main():
    channels = [TRADES]
    exch_sym_map = {}
    exch_sym_map['Binance'] = ['BTC-USDT', 'BTC-USDC', 'BTC-TUSD']
    exch_sym_map['Bitfinex'] = ['BTC-USD']
    exch_sym_map['BitMEX'] = ['BTC-USD-PERP']
    exch_sym_map['Bitstamp'] = ['BTC-USD']
    exch_sym_map['Bybit'] = ['BTC-USD-PERP']
    exch_sym_map['Coinbase'] = ['BTC-USD']
    exch_sym_map['Deribit'] = ['BTC-USD-PERP']
    exch_sym_map['Gemini'] = ['BTC-USD']
    exch_sym_map['HitBTC'] = ['BTC-USDT']
    exch_sym_map['Huobi'] = ['BTC-USDT']
    exch_sym_map['Kraken'] = ['BTC-USD']
    exch_sym_map['OKCoin'] = ['BTC-USD']
    exch_sym_map['OKEx'] = ['BTC-USDT']
    exch_sym_map['Poloniex'] = ['BTC-USDT']

    global exchanges
    exchanges = {e.upper() for e in exch_sym_map.keys()}

    print(f'Starting: {time.time()}')
    f = FeedHandler()
    for i, e in enumerate(exch_sym_map):
        print(f'{[i]}: Subscribing to {e}')
        f.add_feed(e.upper(), symbols=exch_sym_map[e], channels=channels, callbacks={TRADES: trade})
    f.run()


if __name__ == '__main__':
    trades = collections.defaultdict(dict)
    main()
