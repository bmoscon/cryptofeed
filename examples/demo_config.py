'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, TradeCallback, TickerCallback, BookUpdateCallback
from cryptofeed.defines import BID, ASK, L2_BOOK, TRADES, TICKER, BOOK_DELTA
from cryptofeed.exchanges import Coinbase, OKEx, Gemini, Binance, Huobi, OKCoin
import logging

logging.basicConfig(level='INFO')


async def trade(feed, pair, order_id, timestamp, side, amount, price, receipt_timestamp):
    print("lag: {} Timestamp: {} Feed: {} Pair: {} ID: {} Side: {} Amount: {} Price: {}".format(
        receipt_timestamp - timestamp, timestamp, feed, pair, order_id, side, amount, price))


async def book(feed, pair, book, timestamp, receipt_timestamp):
    print('lag: {} Timestamp: {} Feed: {} Pair: {} Book Bid Size is {} Ask Size is {}'.format(
        receipt_timestamp - timestamp, timestamp, feed, pair, book[BID], book[ASK]))


# async def bookdelta(feed, pair, delta, timestamp, receipt_timestamp):
#     print('lag: {} Timestamp: {} Feed: {} Pair: {} Book Bid Size is {} Ask Size is {}'.format(
#         receipt_timestamp - timestamp, timestamp, feed, pair, delta[BID], delta[ASK]))


# async def ticker(feed, pair, bid, ask, timestamp, receipt_timestamp):
#     # #await super().__call__(feed, pair, bid, ask, timestamp, receipt_timestamp)
#     # print('timestamp: {}, receipt_timestamp: {}, feed, pair, bid, ask, '.format(
#     #     timestamp, receipt_timestamp, feed, pair, len(book[BID]), len(book[ASK])))
async def ticker(*args):
    # logging.info('feed, pair, bid, ask, timestamp, receipt_timestamp')
    logging.info([str(i) for i in args])


def main():
    f = FeedHandler()
    f = FeedHandler()

    f.add_feed(Huobi(config={TRADES: ['BTC-USDT'],
                                L2_BOOK: ['BTC-USDT'],
                                #BOOK_DELTA: ['BTC-USD'],
                                #TICKER: ['BTC-USDT'],
                                },
                        callbacks={TRADES: TradeCallback(trade),
                                   L2_BOOK: BookCallback(book),
                                   #TICKER: TickerCallback(ticker),
                                   })
               )
    # f.add_feed(Gemini(config={TRADES: ['BTC-USD'],
    #                           # L2_BOOK: ['BTC-USD'],
    #                           #BOOK_DELTA: ['BTC-USD'],
    #                           # TICKER: ['BTC-USD']
    #                           },
    #                   callbacks={TRADES: TradeCallback(trade),
    #                              # L2_BOOK: BookCallback(book),
    #                              BOOK_DELTA: BookUpdateCallback(bookdelta),
    #                              # TICKER: TickerCallback(ticker),
    #                              })
    #            )
    # f.add_feed(Binance(config={TRADES: ['BTC-USDT'],
    #                            # L2_BOOK: ['BTC-USDT'],
    #                            BOOK_DELTA: ['BTC-USD'],
    #                            # TICKER: ['BTC-USD']
    #                            },
    #                    callbacks={TRADES: TradeCallback(trade),
    #                               # L2_BOOK: BookCallback(book),
    #                               BOOK_DELTA: BookUpdateCallback(bookdelta),
    #                               # TICKER: TickerCallback(ticker),
    #                               })
    #            )
    f.run()


if __name__ == '__main__':
    main()
