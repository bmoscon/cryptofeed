from cryptofeed.auth.binance import BinanceAuth
from cryptofeed.defines import BINANCE_DELIVERY
from cryptofeed.rest.binance_futures import BinanceDelivery

class BinanceDeliveryAuth(BinanceAuth):
    listen_key_endpoint = 'listenKey'

    def create_rest_api(self, config):
        self.rest_api = BinanceDelivery(config=config[BINANCE_DELIVERY.lower()])
