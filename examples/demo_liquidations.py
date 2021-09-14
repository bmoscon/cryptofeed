from cryptofeed import FeedHandler
from cryptofeed.defines import LIQUIDATIONS
from cryptofeed.exchanges import EXCHANGE_MAP


async def liquidations(feed, symbol, side, leaves_qty, price, order_id, status, timestamp, receipt_timestamp):
    print(f'Cryptofeed Receipt: {receipt_timestamp} Feed: {feed} Pair: {symbol} Side: {side} LeavesQty: {leaves_qty} Price: {price} ID: {order_id} Status: {status}')


def main():
    f = FeedHandler()
    configured = []

    print("Querying exchange metadata")
    for exchange_string, exchange_class in EXCHANGE_MAP.items():
        if LIQUIDATIONS in exchange_class.info()['channels']['websocket']:
            configured.append(exchange_string)
            symbols = [sym for sym in exchange_class.symbols() if 'PINDEX' not in sym]
            f.add_feed(exchange_class(subscription={LIQUIDATIONS: symbols}, callbacks={LIQUIDATIONS: liquidations}))
    print("Starting feedhandler for exchanges:", ', '.join(configured))
    f.run()


if __name__ == '__main__':
    main()
