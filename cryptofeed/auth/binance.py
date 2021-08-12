import asyncio
import requests
from urllib.parse import urlencode


class BinanceAuth():
    api = 'https://api.binance.com/api/v3/'
    listen_key_endpoint = 'userDataStream'
    token = None

    def __init__(self, key_id: str):
        self.key_id = key_id

    async def refresh_token(self):
        while True:
            await asyncio.sleep(30 * 60)
            if self.token is None:
                raise ValueError('There is no token to refresh')
            payload = {'listenKey': self.token}
            r = requests.put(f'{self.api}{self.listen_key_endpoint}?{urlencode(payload)}', headers={'X-MBX-APIKEY': self.key_id})
            r.raise_for_status()

    def generate_token(self) -> str:
        url = self.api + self.listen_key_endpoint
        r = requests.post(url, headers={'X-MBX-APIKEY': self.key_id})
        r.raise_for_status()
        response = r.json()
        if 'listenKey' in response:
            self.token = response['listenKey']
            return self.token
        else:
            raise ValueError(f'Unable to retrieve listenKey token from {url}')


class BinanceFuturesAuth(BinanceAuth):
    api = 'https://fapi.binance.com/fapi/v1/'
    listen_key_endpoint = 'listenKey'


class BinanceDeliveryAuth(BinanceAuth):
    api = 'https://dapi.binance.com/dapi/v1/'
    listen_key_endpoint = 'listenKey'
