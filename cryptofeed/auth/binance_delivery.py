from cryptofeed.auth.binance import BinanceAuth
from cryptofeed.rest.rest import Rest
class BinanceDeliveryAuth(BinanceAuth):
    listen_key_endpoint = 'listenKey'

    def create_rest_api(self, config):
        self.rest_api = Rest(config=config).binance_delivery
