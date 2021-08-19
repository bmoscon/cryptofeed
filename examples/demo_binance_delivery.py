from datetime import datetime

from cryptofeed import FeedHandler
from cryptofeed.defines import GOOD_TIL_CANCELED, L2_BOOK, LIMIT, SELL, TICKER, TRADES
from cryptofeed.exchanges import Binance, BinanceDelivery, BinanceFutures


info = BinanceDelivery.info()


async def abook(feed, symbol, book, timestamp, receipt_timestamp):
    print(f'BOOK lag: {receipt_timestamp - timestamp} Timestamp: {datetime.fromtimestamp(timestamp)} Receipt Timestamp: {datetime.fromtimestamp(receipt_timestamp)} Feed: {feed} Pair: {symbol} Snapshot: {book}')


async def ticker(**kwargs):
    print(kwargs)


async def trades(**kwargs):
    print(kwargs)


def main():
    path_to_config = 'config.yaml'
    binance = Binance(config=path_to_config)
    print(binance.balances_sync())
    print(binance.orders_sync())
    order = binance.place_order_sync('BTC-USDT', SELL, LIMIT, 0.002, 80000, time_in_force=GOOD_TIL_CANCELED, test=False)
    print(binance.orders_sync(symbol='BTC-USDT'))
    print(order)
    print(binance.cancel_order_sync(order['orderId'], symbol='BTC-USDT'))
    print(binance.orders_sync(symbol='BTC-USDT'))

    binance_futures = BinanceFutures(config=path_to_config)
    print(binance_futures.balances_sync())
    print(binance_futures.orders_sync())
    print(binance_futures.positions_sync())
    order = binance_futures.place_order_sync('ETH-USDT-PERP', SELL, LIMIT, 20, 5000, time_in_force=GOOD_TIL_CANCELED)
    print(binance_futures.orders_sync(symbol='BTC-USDT-PERP'))
    print(binance_futures.orders_sync(symbol='ETH-USDT-PERP'))
    print(order)
    print(binance_futures.cancel_order_sync(order['orderId'], symbol='ETH-USDT-PERP'))
    print(binance_futures.orders_sync(symbol='ETH-USDT-PERP'))

    binance_delivery = BinanceDelivery(config=path_to_config)
    print(binance_delivery.balances_sync())
    print(binance_delivery.orders_sync())
    print(binance_delivery.positions_sync())
    order = binance_delivery.place_order_sync('ETH-USD-PERP', SELL, LIMIT, 0.05, 5000, time_in_force=GOOD_TIL_CANCELED, test=False)
    print(binance_delivery.orders_sync(symbol='BTC-USDT-PERP'))
    print(binance_delivery.orders_sync(symbol='ETH-USDT-PERP'))
    print(order)
    print(binance_delivery.cancel_order_sync(order['orderId'], symbol='ETH-USDT-PERP'))
    print(binance_delivery.orders_sync(symbol='ETH-USDT-PERP'))

    f = FeedHandler()
    f.add_feed(BinanceDelivery(max_depth=3, symbols=[info['symbols'][-1]],
                               channels=[L2_BOOK, TRADES, TICKER],
                               callbacks={L2_BOOK: abook, TRADES: trades, TICKER: ticker}))
    f.run()


if __name__ == '__main__':
    main()
