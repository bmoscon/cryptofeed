from cryptofeed import FeedHandler
from cryptofeed.exchanges import *
from cryptofeed.backends.quasardb import *


async def ticker_info(ticker, receipt_timestamp):
    print(f'Ticker: {ticker} at {receipt_timestamp}')


async def trade_info(trade, receipt_timestamp):
    print(f'Trade: {trade} at {receipt_timestamp}')


def main():
    f = FeedHandler()

    # print to console
    f.add_feed(Coinbase(channels=[TICKER], symbols=['BTC-USD'], callbacks={TICKER: ticker_info}))
    f.add_feed(Coinbase(symbols=['BTC-USD'], channels=[TRADES], callbacks={TRADES: trade_info}))

    # save to database
    f.add_feed(Coinbase(channels=[TICKER], symbols=['BTC-USD'], callbacks={TICKER: TickerQuasar()}))
    f.add_feed(Coinbase(symbols=['BTC-USD'], channels=[TRADES], callbacks={TRADES: TradeQuasar()}))

    f.run()


if __name__ == '__main__':
    main()
