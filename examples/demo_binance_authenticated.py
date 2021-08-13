import os
from pathlib import Path

from cryptofeed import FeedHandler
from cryptofeed.auth.binance import BinanceAuth, BinanceDeliveryAuth, BinanceFuturesAuth
from cryptofeed.config import Config
from cryptofeed.defines import BINANCE, BINANCE_DELIVERY, BINANCE_FUTURES, BALANCES, POSITIONS
from cryptofeed.exchanges import Binance, BinanceDelivery, BinanceFutures


async def balance(**kwargs):
    print(f"Balance: {kwargs}")


async def position(**kwargs):
    print(f"Position: {kwargs}")


def main():
    path_to_config = os.path.join(Path.home(), 'config.yaml')

    config = Config(config=path_to_config)
    auth = BinanceAuth(config[BINANCE.lower()].key_id)
    print(auth.generate_token())

    auth = BinanceFuturesAuth(config[BINANCE_FUTURES.lower()].key_id)
    print(auth.generate_token())

    auth = BinanceDeliveryAuth(config[BINANCE_DELIVERY.lower()].key_id)
    print(auth.generate_token())

    f = FeedHandler()
    f.add_feed(Binance(config=path_to_config, subscription={BALANCES: []}, timeout=-1,
                       callbacks={BALANCES: balance}))
    f.add_feed(BinanceDelivery(config=path_to_config, subscription={BALANCES: [], POSITIONS: []}, timeout=-1,
                               callbacks={BALANCES: balance, POSITIONS: position}))
    f.add_feed(BinanceFutures(config=path_to_config, subscription={BALANCES: [], POSITIONS: []}, timeout=-1,
                              callbacks={BALANCES: balance, POSITIONS: position}))
    f.run()


if __name__ == '__main__':
    main()
