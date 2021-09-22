from cryptofeed import FeedHandler
from cryptofeed.defines import BALANCES, POSITIONS
from cryptofeed.exchanges import Binance, BinanceDelivery, BinanceFutures


async def balance(**kwargs):
    print(f"Balance: {kwargs}")


async def position(**kwargs):
    print(f"Position: {kwargs}")


def main():
    path_to_config = 'config.yaml'

    binance = Binance(config=path_to_config, subscription={BALANCES: []}, timeout=-1, callbacks={BALANCES: balance})
    binance_delivery = BinanceDelivery(config=path_to_config, subscription={BALANCES: [], POSITIONS: []}, timeout=-1, callbacks={BALANCES: balance, POSITIONS: position})
    binance_futures = BinanceFutures(config=path_to_config, subscription={BALANCES: [], POSITIONS: []}, timeout=-1, callbacks={BALANCES: balance, POSITIONS: position})

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
