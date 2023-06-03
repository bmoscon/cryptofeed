'''
Copyright (C) 2018-2023 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.influxdb import BookInflux, CandlesInflux, FundingInflux, TickerInflux, TradeInflux
from cryptofeed.defines import CANDLES, FUNDING, L2_BOOK, TICKER, TRADES
from cryptofeed.exchanges import Bitmex, Coinbase
from cryptofeed.exchanges.binance import Binance


INFLUX_ADDR = 'http://localhost:8086'
ORG = 'cryptofeed'
BUCKET = 'cryptofeed'
TOKEN = 'XXXXXXXXXX'


def main():

    f = FeedHandler()
    f.add_feed(Bitmex(channels=[FUNDING, L2_BOOK], symbols=['BTC-USD-PERP'], callbacks={FUNDING: FundingInflux(INFLUX_ADDR, ORG, BUCKET, TOKEN), L2_BOOK: BookInflux(INFLUX_ADDR, ORG, BUCKET, TOKEN)}))
    f.add_feed(Coinbase(channels=[TRADES], symbols=['BTC-USD'], callbacks={TRADES: TradeInflux(INFLUX_ADDR, ORG, BUCKET, TOKEN)}))
    f.add_feed(Coinbase(channels=[L2_BOOK], symbols=['BTC-USD'], callbacks={L2_BOOK: BookInflux(INFLUX_ADDR, ORG, BUCKET, TOKEN)}))
    f.add_feed(Coinbase(channels=[TICKER], symbols=['BTC-USD'], callbacks={TICKER: TickerInflux(INFLUX_ADDR, ORG, BUCKET, TOKEN)}))
    f.add_feed(Binance(candle_closed_only=False, channels=[CANDLES], symbols=['BTC-USDT'], callbacks={CANDLES: CandlesInflux(INFLUX_ADDR, ORG, BUCKET, TOKEN)}))
    f.run()


if __name__ == '__main__':
    main()
