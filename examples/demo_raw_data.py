'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.defines import L3_BOOK, TICKER, TRADES
from cryptofeed.exchanges import Coinbase
from cryptofeed.util.async_file import AsyncFileCallback
import logging
from cryptofeed import FeedHandler
from cryptofeed.backends.influxdb import BookDeltaInflux, BookInflux, FundingInflux, TickerInflux, TradeInflux
from cryptofeed.defines import BOOK_DELTA, FUNDING, L2_BOOK, TICKER, TRADES, LIQUIDATIONS
from cryptofeed.exchanges import Bitmex, Coinbase, BinanceFutures, Binance, BinanceDelivery
from cryptofeed.util.async_file import AsyncFileCallback
logging.basicConfig(level='INFO', format='%(asctime)s|%(name)s|%(levelname)s|%(message)s')
#DIR_DATA=os.environ['DIR_DATA_SAVE']
DIR_DATA = 'D:/Data/data_binance/raw'

def main():
    # f = FeedHandler(raw_message_capture=AsyncFileCallback('./'), handler_enabled=False)
    # f.add_feed(Coinbase(pairs=['BTC-USD'], channels=[L3_BOOK, TICKER, TRADES]))
    #
    # f.run()
    list_symbol_binance_future = [i for i in BinanceFutures.info()['pairs']]# if i.endswith('USDT')]
    #list_symbol_binance_future = ['BTC-USDT', 'ETH-USDT']
    list_symbol_binance_delivery = [i for i in BinanceDelivery.info()['pairs']]
    list_symbol_binance = [i for i in Binance.info()['pairs'] if i.endswith('USDT')]
    print([list_symbol_binance_future+list_symbol_binance_delivery])
    f = FeedHandler(raw_message_capture=AsyncFileCallback(DIR_DATA), )
    f.add_feed(Binance(pairs=list_symbol_binance, channels=[TRADES, TICKER]))
    f.add_feed(BinanceFutures(pairs=list_symbol_binance_future, channels=[TRADES]))
    f.add_feed(BinanceFutures(pairs=list_symbol_binance_future, channels=[TICKER]))
    f.add_feed(BinanceFutures(pairs=list_symbol_binance_future, channels=[LIQUIDATIONS, FUNDING]))
    #f.add_feed(BinanceDelivery(max_depth=5, pairs=list_symbol_binance_delivery, channels=[L2_BOOK]))
    f.add_feed(BinanceDelivery(pairs=list_symbol_binance_delivery, channels=[TRADES, TICKER, LIQUIDATIONS, FUNDING]))
    f.run()

if __name__ == '__main__':
    main()
