'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com
Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, TickerCallback, TradeCallback
from cryptofeed.defines import BID, ASK, L2_BOOK, TICKER, TRADES, FUNDING, OPEN_INTEREST, LIQUIDATIONS
from cryptofeed.exchanges import OKEx


async def trade(feed, pair, order_id, timestamp, side, amount, price, receipt_timestamp):
    print(
        f"Timestamp: {timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, pair, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Book Bid Size is {len(book[BID])} Ask Size is '
          f'{len(book[ASK])}')


async def ticker(feed, pair, bid, ask, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Bid: {bid} Ask: {ask}')


async def funding(**kwargs):
    print(f"Funding update: {kwargs}")


async def open_int(**kwargs):
    print(f"Open interest update: {kwargs}")


async def liquidation(**kwargs):
    print(f"Liquidation: {kwargs}")


def main():
    fh = FeedHandler()

    # Add futures contracts
    callbacks = {TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book), TICKER: TickerCallback(ticker)}
    pairs = OKEx.get_active_symbols()[:5]
    fh.add_feed(OKEx(checksum_validation=True, pairs=pairs, channels=[TRADES, TICKER, L2_BOOK], callbacks=callbacks))
    # Add swaps. Futures and swaps could be added together in one feed, but its clearer to
    # add them as separate feeds.
    # EOS-USD-SWAP is from the swap exchange, BTC-USDT is from spot exchage.
    fh.add_feed(OKEx(pairs=['EOS-USD-SWAP', 'BTC-USDT'], channels=[L2_BOOK, TICKER, TRADES], callbacks={L2_BOOK: book, TRADES: trade, TICKER: ticker}))

    # Open Interest, Liquidations, and Funding Rates
    # funding is low volume, so set timeout to -1
    fh.add_feed(OKEx(pairs=['EOS-USD-SWAP'], channels=[FUNDING, LIQUIDATIONS], callbacks={FUNDING: funding, LIQUIDATIONS: liquidation}), timeout=-1)
    fh.add_feed(OKEx(pairs=pairs, channels=[OPEN_INTEREST], callbacks={OPEN_INTEREST: open_int}))

    fh.run()


if __name__ == '__main__':
    main()
