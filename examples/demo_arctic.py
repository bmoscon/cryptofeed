'''
Copyright (C) 2018-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.arctic import FundingArctic, TickerArctic, TradeArctic
from cryptofeed.defines import FUNDING, TICKER, TRADES, L2_BOOK
from cryptofeed.exchanges import Bitfinex, Bitmex, Coinbase, BinanceFutures
import os

HOST_IP = os.environ['HOST_IP']


def main():
    f = FeedHandler()
    # f.add_feed(Bitmex(channels=[TRADES, FUNDING], pairs=['XBTUSD'],
    #                   callbacks={TRADES: TradeArctic('cryptofeed-test'), FUNDING: FundingArctic('cryptofeed-test')}))
    # f.add_feed(Bitfinex(channels=[TRADES], pairs=['BTC-USDT'],
    #                     callbacks={TRADES: TradeArctic('crypto_trade')}))
    f.add_feed(Coinbase(channels=[TICKER], pairs=['BTC-USD'],
                        callbacks={TICKER: TickerArctic('crypto_ticker', host=HOST_IP)}))
    f.add_feed(Coinbase(channels=[TRADES], pairs=['BTC-USD'],
                        callbacks={TRADES: TickerArctic('crypto_trade', host=HOST_IP)}))
    f.add_feed(Coinbase(channels=[L2_BOOK], pairs=['BTC-USD'],
                        callbacks={L2_BOOK: TickerArctic('crypto_quote', host=HOST_IP)}, max_depth=5))
    f.add_feed(BinanceFutures(channels=[TICKER], pairs=['BTC-USDT'],
                              callbacks={TICKER: TickerArctic('crypto_ticker', host=HOST_IP)}))
    f.add_feed(BinanceFutures(channels=[TRADES], pairs=['BTC-USDT'],
                              callbacks={TRADES: TickerArctic('crypto_trade', host=HOST_IP)}))
    f.run()


if __name__ == '__main__':
    main()
