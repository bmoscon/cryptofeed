from cryptofeed import FeedHandler
from cryptofeed.auth.binance import BinanceAuth
from cryptofeed.auth.binance_delivery import BinanceDeliveryAuth
from cryptofeed.config import Config
from cryptofeed.defines import BINANCE, BINANCE_DELIVERY, BINANCE_FUTURES, USER_BALANCE, USER_POSITION
from cryptofeed.exchanges import BinanceDelivery
from cryptofeed.rest.binance_futures import Binance as BinanceRest, BinanceDelivery as BinanceDeliveryRest

async def user_balance(**kwargs):
    print(f"User balance update: {kwargs}")

async def user_position(**kwargs):
    print(f"User position update: {kwargs}")

def main():
    config = Config(config='config.yaml')
    auth = BinanceAuth(config)
    print(auth.generate_token())
    print(auth.refresh_token())
    
    auth = BinanceDeliveryAuth(config)
    print(auth.generate_token())
    print(auth.refresh_token())
    
    # rest = BinanceDeliveryRest(config=config[BINANCE_DELIVERY.lower()])
    # print(rest._send_request('account', None, 0, auth=True))

    # rest = BinanceRest(config=config[BINANCE.lower()])
    # print(rest._send_request('account', None, 0, auth=True))

if __name__ == '__main__':
    main()