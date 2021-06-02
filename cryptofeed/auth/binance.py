from cryptofeed.defines import BINANCE
from cryptofeed.rest.binance_futures import Binance

class BinanceAuth():
    listen_key_endpoint = 'userDataStream'
    token = None

    def __init__(self, config):
        self.create_rest_api(config)
        self.token = None

    def create_rest_api(self, config):
        self.rest_api = Binance(config=config[BINANCE.lower()])

    async def refresh_token(self):
        if self.token is None:
            return self.generate_token()
        return self.rest_api._send_request(self.listen_key_endpoint, None, 0, http_method='PUT', payload={'listenKey': self.token}) 

    def generate_token(self) -> str:
        response = self.rest_api._send_request(self.listen_key_endpoint, None, 0, http_method='POST')
        if 'listenKey' in response:
            self.token = response['listenKey']
            return self.token
        else:
            raise ValueError(response)
