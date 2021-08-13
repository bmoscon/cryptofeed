from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, TickerCallback, TradeCallback, L1BookCallback
from cryptofeed.defines import BID, ASK, FUNDING, L2_BOOK, OPEN_INTEREST, TICKER, TRADES, L1_BOOK, DERIBIT
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


async def quote(feed, symbol, bid_price, ask_price, bid_amount, ask_amount, timestamp, receipt_timestamp):
    print(f"{feed}: {symbol} Best price (amount): bid: {bid_price} ({bid_amount}) ask: {ask_price} ({ask_amount}) timestamp: {timestamp}")


def main():
    f = FeedHandler()

    # Deribit can't handle 400+ simultaneous requests, so if all
    # instruments are needed they should be fed in the different calls

    sub = {TRADES: ["BTC-USD-PERP"], TICKER: ['ETH-USD-PERP'], FUNDING: ['ETH-USD-PERP'], OPEN_INTEREST: ['ETH-USD-PERP']}
    f.add_feed(Deribit(subscription=sub, callbacks={OPEN_INTEREST: oi, FUNDING: funding, TICKER: TickerCallback(ticker), TRADES: TradeCallback(trade)}))
    f.add_feed(Deribit(symbols=['BTC-USD-PERP'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book)}))
    f.add_feed(DERIBIT, channels=[L1_BOOK], symbols=["BTC-USD-22M24", "BTC-50000-22M24-call"], callbacks={L1_BOOK: L1BookCallback(quote)})

    f.run()


if __name__ == '__main__':
    main()
