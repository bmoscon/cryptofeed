'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal

from cryptofeed import FeedHandler
from cryptofeed.callback import LiquidationCallback, OpenInterestCallback
from cryptofeed.defines import BID, ASK, LIQUIDATIONS, OPEN_INTEREST
from cryptofeed.exchanges import FTX, BinanceFutures, Deribit
from cryptofeed.pairs import binance_futures_pairs, ftx_pairs


# Examples of some handlers for different updates. These currently don't do much.
# Handlers should conform to the patterns/signatures in callback.py
# Handlers can be normal methods/functions or async. The feedhandler is paused
# while the callbacks are being handled (unless they in turn await other functions or I/O)
# so they should be as lightweight as possible
async def ticker(feed, pair, bid, ask, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Bid: {bid} Ask: {ask}')


async def trade(feed, pair, order_id, timestamp, side, amount, price, receipt_timestamp):
    assert isinstance(timestamp, float)
    assert isinstance(side, str)
    assert isinstance(amount, Decimal)
    assert isinstance(price, Decimal)
    print(f"Timestamp: {timestamp} Cryptofeed Receipt: {receipt_timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, pair, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


async def funding(**kwargs):
    print(f"Funding Update for {kwargs['feed']}")
    print(kwargs)


async def oi(feed, pair, open_interest, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} open interest: {open_interest}')


async def liquidations(feed, pair, side, leaves_qty, price, order_id, timestamp, receipt_timestamp):
    print(f"Liquidation @ {timestamp}: {feed} {pair} {side}: qty: {leaves_qty} @ {price} - order id: {order_id}")


def main():
    f = FeedHandler()
    f.add_feed(FTX(pairs=ftx_pairs(), channels=[OPEN_INTEREST, LIQUIDATIONS],
                   callbacks={OPEN_INTEREST: OpenInterestCallback(oi),
                              LIQUIDATIONS: LiquidationCallback(liquidations)}))

    f.add_feed(BinanceFutures(pairs=binance_futures_pairs(), channels=[OPEN_INTEREST, LIQUIDATIONS], callbacks={OPEN_INTEREST: OpenInterestCallback(oi), LIQUIDATIONS: LiquidationCallback(liquidations)}))

    f.add_feed(Deribit(pairs=['BTC-PERPETUAL', 'ETH-PERPETUAL'], channels=[LIQUIDATIONS, OPEN_INTEREST],
                       callbacks={OPEN_INTEREST: OpenInterestCallback(oi),
                                  LIQUIDATIONS: LiquidationCallback(liquidations)}))
    f.run()


if __name__ == '__main__':
    main()
