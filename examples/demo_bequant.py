'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
from cryptofeed.connection import AsyncConnection
from cryptofeed.callback import AccBalancesCallback, AccTransactionsCallback, TickerCallback
import pprint
from cryptofeed import FeedHandler
from cryptofeed.defines import ASK, BEQUANT, BID, L2_BOOK, ORDER_INFO, ACC_BALANCES, ACC_TRANSACTIONS, TICKER, CANDLES, TRADES


async def order(conn: AsyncConnection, **kwargs):
    print(f"Order Update on {conn.uuid}: {kwargs}")


async def balances(feed, accounts):
    for account in accounts:
        print(f'{feed} balances statement: {account}')


async def transactions(**kwargs):
    pprint.pp(f'New transaction {kwargs}')

async def ticker(feed, symbol, bid, ask, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Received: {receipt_timestamp} Feed: {feed} Symbol: {symbol} Bid: {bid} Ask: {ask}')

async def book(feed, symbol, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Cryptofeed Receipt: {receipt_timestamp} Feed: {feed} Symbol: {symbol} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')

async def candles_callback(feed, symbol, start, stop, interval, trades, open_price, close_price, high_price, low_price, volume, closed, timestamp, receipt_timestamp):
    print(f"{feed}, TS: {timestamp} Rec'd: {receipt_timestamp} Symbol: {symbol} Start: {start} Stop: {stop} Interval: {interval} Trades: {trades} Open: {open_price} Close: {close_price} High: {high_price} Low: {low_price} Volume: {volume} Candle Closed? {closed}")


async def ticker(feed, symbol, bid, ask, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Received: {receipt_timestamp} Feed: {feed} Symbol: {symbol} Bid: {bid} Ask: {ask}')


async def book(feed, symbol, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Cryptofeed Receipt: {receipt_timestamp} Feed: {feed} Symbol: {symbol} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


async def candles_callback(feed, symbol, start, stop, interval, trades, open_price, close_price, high_price, low_price, volume, closed, timestamp, receipt_timestamp):
    print(f"{feed}, TS: {timestamp} Rec'd: {receipt_timestamp} Symbol: {symbol} Start: {start} Stop: {stop} Interval: {interval} Trades: {trades} Open: {open_price} Close: {close_price} High: {high_price} Low: {low_price} Volume: {volume} Candle Closed? {closed}")


async def trade(feed, symbol, order_id, timestamp, side, amount, price, receipt_timestamp):
    assert isinstance(timestamp, float)
    assert isinstance(side, str)
    assert isinstance(amount, Decimal)
    assert isinstance(price, Decimal)
    print(f"Timestamp: {timestamp} Cryptofeed Receipt: {receipt_timestamp} Feed: {feed} Symbol: {symbol} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


def main():
    f = FeedHandler(config='config.yaml')
    f.add_feed(BEQUANT, channels=[TICKER], symbols=['ADA-USDT'], callbacks={TICKER: TickerCallback(ticker)})
    f.add_feed(BEQUANT, channels=[L2_BOOK], symbols=['ALGO-USDT'], callbacks={L2_BOOK: (book)})
    f.add_feed(BEQUANT, channels=[CANDLES], symbols=['ETH-USDT'], callbacks={CANDLES: candles_callback})
    f.add_feed(BEQUANT, channels=[TRADES], symbols=['ETH-USDT'], callbacks={TRADES: trade})

    # The following channels are authenticated (non public). Make sure you have set the correct privileges on your API key(s)
    f.add_feed(BEQUANT, subscription={ORDER_INFO: ['BTC-USD', 'ETH-USD']}, callbacks={ORDER_INFO: order})
    f.add_feed(BEQUANT, timeout=-1, channels=[ACC_BALANCES], symbols=['ADA-USDT'], callbacks={ACC_BALANCES: AccBalancesCallback(balances)})
    f.add_feed(BEQUANT, timeout=-1, channels=[ACC_TRANSACTIONS], symbols=['ADA-USDT'], callbacks={ACC_TRANSACTIONS: AccTransactionsCallback(transactions)})
    f.run()


if __name__ == '__main__':
    main()
