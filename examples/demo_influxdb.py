'''
Copyright (C) 2018-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.influxdb import BookDeltaInflux, BookInflux, FundingInflux, TickerInflux, TradeInflux
from cryptofeed.defines import BOOK_DELTA, FUNDING, L2_BOOK, TICKER, TRADES
from cryptofeed.exchanges import Bitmex, Coinbase


def main():

    f = FeedHandler()
    f.add_feed(Bitmex(channels=[FUNDING, L2_BOOK], symbols=['XBTUSD'], callbacks={FUNDING: FundingInflux('http://localhost:8086', 'example'), L2_BOOK: BookInflux('http://localhost:8086', 'example', numeric_type=float), BOOK_DELTA: BookDeltaInflux('http://localhost:8086', 'example', numeric_type=float)}))
    f.add_feed(Coinbase(channels=[TRADES], symbols=['BTC-USD'], callbacks={TRADES: TradeInflux('http://localhost:8086', 'example')}))
    f.add_feed(Coinbase(channels=[L2_BOOK], symbols=['BTC-USD'], callbacks={L2_BOOK: BookInflux('http://localhost:8086', 'example', numeric_type=float), BOOK_DELTA: BookDeltaInflux('http://localhost:8086', 'example', numeric_type=float)}))
    f.add_feed(Coinbase(channels=[TICKER], symbols=['BTC-USD'], callbacks={TICKER: TickerInflux('http://localhost:8086', 'example', numeric_type=float)}))

    """
    # Uncomment Here When Using InfluxDB 2.0
    # For InfluxDB 2.0, provide additional org, bucket(instead of db), token and precision(optional)
    # [Note] In order to use visualization and aggregation, numeric_type with float is strongly recommended.

    ADDR = 'https://localhost:9999'
    ORG='my-org'
    BUCKET = 'my-bucket'
    TOKEN = 'token-something-like-end-with-=='

    f = FeedHandler()
    funding_influx = FundingInflux(ADDR, org=ORG, bucket=BUCKET, token=TOKEN, numeric_type=float)
    trade_influx = TradeInflux(ADDR, org=ORG, bucket=BUCKET, token=TOKEN, numeric_type=float)
    book_influx = BookInflux(ADDR, org=ORG, bucket=BUCKET, token=TOKEN, numeric_type=float)
    bookdelta_influx = BookDeltaInflux(ADDR, org=ORG, bucket=BUCKET, token=TOKEN, numeric_type=float)
    ticker_influx = TickerInflux(ADDR, org=ORG, bucket=BUCKET, token=TOKEN, numeric_type=float)

    f.add_feed(Bitmex(channels=[FUNDING, L2_BOOK],symbols=['XBTUSD'], callbacks={FUNDING: funding_influx, L2_BOOK: book_influx, BOOK_DELTA: bookdelta_influx}))
    f.add_feed(Coinbase(channels=[TRADES], symbols=['BTC-USD'], callbacks={TRADES: trade_influx}))
    f.add_feed(Coinbase(channels=[L2_BOOK], symbols=['BTC-USD'], callbacks={L2_BOOK: book_influx, BOOK_DELTA: bookdelta_influx}))
    f.add_feed(Coinbase(channels=[TICKER], symbols=['BTC-USD'], callbacks={TICKER: ticker_influx}))
    """

    f.run()


if __name__ == '__main__':
    main()
