from cryptofeed import FeedHandler
from cryptofeed.defines import BALANCES, ORDER_INFO, POSITIONS
from cryptofeed.exchanges import Binance, BinanceDelivery, BinanceFutures


async def balance(b, receipt_timestamp):
    print(f"Balance update received at {receipt_timestamp}: {b}")


async def position(p, receipt_timestamp):
    print(f"Position update received at {receipt_timestamp}: {p}")


async def order_info(oi, receipt_timestamp):
    print(f"Order update received at {receipt_timestamp}: {oi}")


def main():
    path_to_config = 'config.yaml'

    binance = Binance(config=path_to_config, subscription={BALANCES: [], ORDER_INFO: []}, timeout=-1, callbacks={BALANCES: balance, ORDER_INFO: order_info})
    binance_delivery = BinanceDelivery(config=path_to_config, subscription={BALANCES: [], POSITIONS: [], ORDER_INFO: []}, timeout=-1, callbacks={BALANCES: balance, POSITIONS: position, ORDER_INFO: order_info})
    binance_futures = BinanceFutures(config=path_to_config, subscription={BALANCES: [], POSITIONS: [], ORDER_INFO: []}, timeout=-1, callbacks={BALANCES: balance, POSITIONS: position, ORDER_INFO: order_info})

    print(binance._generate_token())
    print(binance_delivery._generate_token())
    print(binance_futures._generate_token())

    f = FeedHandler()
    f.add_feed(binance)
    f.add_feed(binance_delivery)
    f.add_feed(binance_futures)
    f.run()


if __name__ == '__main__':
    main()
