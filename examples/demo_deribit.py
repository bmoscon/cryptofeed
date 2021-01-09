from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, TickerCallback, TradeCallback
from cryptofeed.defines import BID, ASK, FUNDING, L2_BOOK, OPEN_INTEREST, TICKER, TRADES
from cryptofeed.exchanges import Deribit


async def trade(feed, symbol, order_id, timestamp, side, amount, price, receipt_timestamp):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {symbol} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def ticker(feed, symbol, bid, ask, timestamp, receipt_timestamp):
    print(f'Feed: {feed} Pair: {symbol} Bid: {bid} Ask: {ask}')


async def book(feed, symbol, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {symbol} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


async def funding(**kwargs):
    print(f'Funding {kwargs}')


async def oi(feed, symbol, open_interest, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {symbol} open interest: {open_interest}')


def main():
    f = FeedHandler()

    # Deribit can't handle 400+ simultaneous requests, so if all
    # instruments are needed they should be fed in the different calls

    sub = {TRADES: ["BTC-PERPETUAL"], TICKER: ['ETH-PERPETUAL'], FUNDING: ['ETH-PERPETUAL'], OPEN_INTEREST: ['ETH-PERPETUAL']}
    f.add_feed(Deribit(subscription=sub, callbacks={OPEN_INTEREST: oi, FUNDING: funding, TICKER: TickerCallback(ticker), TRADES: TradeCallback(trade)}))
    f.add_feed(Deribit(symbols=['BTC-PERPETUAL'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book)}))

    f.run()


if __name__ == '__main__':
    main()
