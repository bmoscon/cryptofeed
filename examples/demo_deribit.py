from cryptofeed.callback import TickerCallback, TradeCallback
from cryptofeed import FeedHandler

from cryptofeed.exchanges import Deribit
from cryptofeed.defines import TRADES, TICKER


async def trade(feed, pair, order_id, timestamp, side, amount, price):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")

async def ticker(feed, pair, bid, ask):
    print(f'Feed: {feed} Pair: {pair} Bid: {bid} Ask: {ask}')


def main():
    f = FeedHandler()
    f.add_feed(Deribit(pairs=['BTC-PERPETUAL'], channels=[TRADES, TICKER], callbacks={TICKER: TickerCallback(ticker), TRADES: TradeCallback(trade)}))
  
    f.run()


if __name__ == '__main__':
    main()
