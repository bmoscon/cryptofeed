from cryptofeed.callback import TickerCallback, TradeCallback, BookCallback
from cryptofeed import FeedHandler

from cryptofeed.exchanges import Deribit
from cryptofeed.defines import TRADES, TICKER, L2_BOOK, BID, ASK, FUNDING


async def trade(feed, pair, order_id, timestamp, side, amount, price):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def ticker(feed, pair, bid, ask, timestamp):
    print(f'Feed: {feed} Pair: {pair} Bid: {bid} Ask: {ask}')


async def book(feed, pair, book, timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


async def funding(**kwargs):
    print(f'Funding {kwargs}')


def main():
    f = FeedHandler()

    # Deribit can't handle 400+ simultaneous requests, so if all
    # instruments are needed they should be fed in the different calls

    config = {TRADES: ["BTC-PERPETUAL"], TICKER: ['ETH-PERPETUAL'], FUNDING: ['ETH-PERPETUAL']}
    f.add_feed(Deribit(config=config, callbacks={FUNDING: funding, TICKER: TickerCallback(ticker), TRADES: TradeCallback(trade)}))

    #f.add_feed(Deribit(pairs=['BTC-PERPETUAL'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book)}))
    f.run()


if __name__ == '__main__':
    main()
