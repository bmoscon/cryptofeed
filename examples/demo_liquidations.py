from cryptofeed import FeedHandler
from cryptofeed.callback import LiquidationCallback
from cryptofeed.defines import LIQUIDATIONS
from cryptofeed.exchanges import Bitmex


async def liquidations(feed, symbol, side, leaves_qty, price, order_id, status, timestamp, receipt_timestamp):
    print(f'Cryptofeed Receipt: {receipt_timestamp} Feed: {feed} Pair: {symbol} Side: {side} LeavesQty: {leaves_qty} Price: {price} ID: {order_id} Status: {status}')


def main():

    f = FeedHandler()
    # Liquidations happen not frequently, disable feed timeout
    f.add_feed(Bitmex(channels=[LIQUIDATIONS], symbols=['BTC-USD'], callbacks={LIQUIDATIONS: LiquidationCallback(liquidations)}), timeout=-1)
    f.run()


if __name__ == '__main__':
    main()
