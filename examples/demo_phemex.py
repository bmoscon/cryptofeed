#!/usr/bin/env python
from decimal import Decimal
from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, TradeCallback, CandleCallback, UserDataCallback, LastPriceCallback
from cryptofeed.defines import BID, ASK, PHEMEX, L2_BOOK, TRADES, CANDLES, LAST_PRICE, USER_DATA


'''
    Public channels supported:
        L2_BOOK, TRADES, CANDLES, LAST_PRICE

    Authenticated channel: USER_DATA
        It streams info regarding user accounts, orders and positions.
        Latest account snapshot messages will be sent immediately on subscription,
        and incremental messages will be sent for later updates.
        Each account snapshot contains a trading account information, holding positions,
        and open / max 100 closed / max 100 filled order event message history.
'''


async def trade(feed, symbol, order_id, timestamp, side, amount, price, receipt_timestamp):
    assert isinstance(timestamp, float)
    assert isinstance(side, str)
    assert isinstance(amount, Decimal)
    assert isinstance(price, Decimal)
    print(f'{feed} Trades: {symbol}: Side: {side} Amount: {amount} Price: {price} Time: {timestamp}')


async def book(feed, symbol, book, timestamp, receipt_timestamp):
    print(f'{feed} Book: {symbol}: Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])} Time: {timestamp}')


async def candle(feed, symbol, start, stop, interval, trades, open_price, close_price, high_price, low_price, volume, closed, timestamp, receipt_timestamp):
    print(f'{feed} Candle: {symbol}: Start: {start} Stop: {stop} Interval: {interval} Trades: {trades} Open: {open_price} Close: {close_price} High: {high_price} Low: {low_price} Volume: {volume} Candle Closed? {closed} Time: {timestamp}')


async def price(feed, symbol, last_price, receipt_timestamp):
    print(f'{feed} Price: {symbol}: {last_price}')


async def userdata(feed, data: dict, receipt_timestamp):
    print(f'{feed} User data update: {data}')


def main():
    f = FeedHandler(config="config.yaml")

    f.add_feed(PHEMEX, channels=[L2_BOOK, TRADES, CANDLES],
               symbols=["ETH-USD-PERP", "BTC-USD-PERP"],
               callbacks={L2_BOOK: BookCallback(book), TRADES: TradeCallback(trade), CANDLES: CandleCallback(candle)})

    f.add_feed(PHEMEX, channels=[LAST_PRICE], symbols=["ETH-USD-PERP", "BTC-USD-PERP"], callbacks={LAST_PRICE: LastPriceCallback(price)})

    f.add_feed(PHEMEX, channels=[USER_DATA], symbols=["BTC-USD-PERP"], callbacks={USER_DATA: UserDataCallback(userdata)}, timeout=-1)

    f.run()


if __name__ == '__main__':
    main()
