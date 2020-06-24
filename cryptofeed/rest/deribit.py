from time import sleep
import time
import hmac
import random
import logging
import pandas as pd
import requests
from urllib import parse
from requests import Request
import asyncio
import websockets
import json
import hashlib
from datetime import datetime
from cryptofeed.rest.api import API, request_retry
from cryptofeed.defines import DERIBIT, SELL, BUY, BID, ASK
from cryptofeed.standards import pair_std_to_exchange, timestamp_normalize
from sortedcontainers import SortedDict as sd
import json

REQUEST_LIMIT = 1000
RATE_LIMIT_SLEEP = 0.2
LOG = logging.getLogger('rest')


class Deribit(API):
    ID = DERIBIT
    API_MAX = 128
    api = "https://www.deribit.com/api/v2/public/"
    priv_api = "https://www.deribit.com/api/v2/private/"

    def __init__(self, config, sandbox=False, **kwargs):
        super().__init__(config, sandbox, **kwargs)
        self.token = None

    def _wallet_value_normalization(self, wallet_value: dict) -> dict:
        return {
            'coin': wallet_value['currency'],
            'available': wallet_value['available_withdrawal_funds'],
            'balance': wallet_value['balance']
        }

    async def wallet_value(self):
        msg = self._get_wallet_value_msg()
        stop = False
        total_records_fetched = 0
        await self._call_api(json.dumps(msg))
        yield self._wallet_value_normalization(self.result)

    def _money_flow_normalization(self, funding: dict) -> dict:
        if 'confirmed_timestamp' in funding:
            return {
                'time': funding['confirmed_timestamp'],
                'coin': funding['currency'],
                'amount': funding['amount'] * -1,
                'fee': funding['fee']
            }
        else:
            return {
                'time': funding['received_timestamp'],
                'coin': funding['currency'],
                'amount': funding['amount']
            }

    async def get_money_flow(self):
        msg = self._get_withdrawals_msg()
        stop = False
        total_records_fetched = 0
        while not stop:
            await self._call_api(json.dumps(msg))
            yield list(map(self._money_flow_normalization, self.result['data']))
            total_records_fetched += len(self.result['data'])
            if total_records_fetched < self.result['count']:
                msg = self._get_withdrawals_msg(total_records_fetched)
            else:
                stop = True
        msg = self._get_deposits_msg()
        stop = False
        total_records_fetched = 0
        while not stop:
            await self._call_api(json.dumps(msg))
            yield list(map(self._money_flow_normalization, self.result['data']))
            total_records_fetched += len(self.result['data'])
            if total_records_fetched < self.result['count']:
                msg = self._get_deposits_msg(total_records_fetched)
            else:
                stop = True


    def _funding_normalization(self, funding: dict) -> dict:
        """{'type': 'settlement', 'timestamp': 1586073600409, 'session_profit_loss': 121.931867297,
        'profit_loss': 0.0, 'position': 0, 'mark_price': 6778.6, 'instrument_name': 'BTC-PERPETUAL',
        'index_price': 6778.11, 'funding': 3.102e-05}
        """
        if 'funding' in funding:
            return {
                'time': funding['timestamp'],
                'pair': funding['instrument_name'],
                'funding': funding['funding']
            }
        else:
            return {}

    async def funding_payment(self):
        msg = self._get_funding_payment_msg(continuation=None)
        stop = False
        while not stop:
            await self._call_api(json.dumps(msg))
            yield list(map(self._funding_normalization, self.result['settlements']))
            continuation = self.result['continuation']
            if continuation != 'none':
                msg = self._get_funding_payment_msg(continuation=continuation)
            else:
                stop = True

    def _fills_normalization(self, fills: dict) -> dict:
        """
            {'underlying_price': 9819.72, 'trade_seq': 523, 'trade_id': '82044521', 'timestamp': 1591859743408,
            'tick_direction': 1, 'state': 'filled', 'self_trade': False, 'reduce_only': False, 'price': 0.009,
            'post_only': False, 'order_type': 'market', 'order_id': '19899143482', 'matching_id': None,
            'mark_price': 0.0098678,
             'liquidity': 'T', 'iv': 57.87, 'instrument_name': 'BTC-12JUN20-9750-P', 'index_price': 9817.91,
             'fee_currency': 'BTC', 'fee': 0.0009, 'direction': 'sell', 'amount': 2.5}
        """
        return {
            'time': fills['timestamp'],
            'trade_id': str(fills['trade_id']),
            'symbol': fills['instrument_name'],
            'side': fills['direction'].lower(),
            'size': fills['amount'],
            'price': fills['price'],
            'fees': fills['fee'],
        }

    async def fills(self):
        msg = self._get_fills_msg()
        stop = False
        while not stop:
            await self._call_api(json.dumps(msg))
            yield list(map(self._fills_normalization, self.result['trades']))
            l = len(self.result['trades'])
            if len(self.result['trades']) >= self.API_MAX:
                end_id = self.result['trades'][self.API_MAX-1]['trade_id']
                msg = self._get_fills_msg(end_id)
            else:
                stop = True

    def trades(self, symbol: str, start=None, end=None, retry=None, retry_wait=10):
        symbol = pair_std_to_exchange(symbol, self.ID)
        for data in self._get_trades(symbol, start, end, retry, retry_wait):
            yield data

    def _get_trades(self, instrument, start_date, end_date, retry, retry_wait):
        start = None
        end = None

        if start_date:
            if not end_date:
                end_date = pd.Timestamp.utcnow()
            start = API._timestamp(start_date)
            end = API._timestamp(end_date) - pd.Timedelta(nanoseconds=1)

            start = int(start.timestamp() * 1000)
            end = int(end.timestamp() * 1000)

        @request_retry(self.ID, retry, retry_wait)
        def helper(start, end):
            if start and end:
                return requests.get(f"{self.api}get_last_trades_by_instrument_and_time?&start_timestamp={start}&end_timestamp={end}&instrument_name={instrument}&include_old=true&count={REQUEST_LIMIT}")
            else:
                return requests.get(f"{self.api}get_last_trades_by_instrument_and_time/")

        while True:
            r = helper(start, end)

            if r.status_code == 429:
                sleep(int(r.headers['Retry-After']))
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.ID, r.url, r.text)
                sleep(retry_wait)
                continue
            elif r.status_code != 200:
                self._handle_error(r, LOG)
            else:
                sleep(RATE_LIMIT_SLEEP)

            data = r.json()["result"]["trades"]
            if data == []:
                LOG.warning("%s: No data for range %d - %d",
                            self.ID, start, end)
            else:
                if data[-1]["timestamp"] == start:
                    LOG.warning(
                        "%s: number of trades exceeds exchange time window, some data will not be retrieved for time %d", self.ID, start)
                    start += 1
                else:
                    start = data[-1]["timestamp"]

            orig_data = data
            data = [self._trade_normalization(x) for x in data]
            yield data

            if len(orig_data) < REQUEST_LIMIT:
                break

    def _trade_normalization(self, trade: list) -> dict:

        ret = {
            'timestamp': timestamp_normalize(self.ID, trade["timestamp"]),
            'pair': trade["instrument_name"],
            'id': int(trade["trade_id"]),
            'feed': self.ID,
            'side': BUY if trade["direction"] == 'buy' else SELL,
            'amount': trade["amount"],
            'price': trade["price"],
        }
        return ret

    def l2_book(self, symbol: str, retry=0, retry_wait=0):
        return self._book(symbol, retry=retry, retry_wait=retry_wait)

    def _book(self, symbol: str, retry=0, retry_wait=0):
        ret = {}
        symbol = pair_std_to_exchange(symbol, self.ID)
        ret[symbol] = {BID: sd(), ASK: sd()}

        @request_retry(self.ID, retry, retry_wait)
        def helper():
            return requests.get(f"{self.api}get_order_book?depth=10000&instrument_name={symbol}")

        while True:
            r = helper()

            if r.status_code == 429:
                sleep(int(r.headers['Retry-After']))
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.ID, r.url, r.text)
                sleep(retry_wait)
                if retry == 0:
                    break
                continue
            elif r.status_code != 200:
                self._handle_error(r, LOG)

            data = r.json()
            break

        for side, key in ((BID, 'bids'), (ASK, 'asks')):
            for entry_bid in data["result"][key]:
                price, amount = entry_bid
                ret[symbol][side][price] = amount

        return ret

    def _get_auth_msg(self):
        clientId = self.key_id
        clientSecret = self.key_secret
        timestamp = round(datetime.now().timestamp() * 1000)
        nonce = 'abcdklm'
        data = ""
        signature = hmac.new(
            bytes(clientSecret, "latin-1"),
            msg=bytes('{}\n{}\n{}'.format(timestamp, nonce, data), "latin-1"),
            digestmod=hashlib.sha256
        ).hexdigest().lower()

        msg = {
            "jsonrpc": "2.0",
            "id": 8748,
            "method": "public/auth",
            "params": {
                "grant_type": "client_signature",
                "client_id": clientId,
                "timestamp": timestamp,
                "signature": signature,
                "nonce": nonce,
                "data": data
            }
        }
        return json.dumps(msg)

    async def _call_api(self, msg):
        async with websockets.connect('wss://www.deribit.com/ws/api/v2') as websocket:
            auth = self._get_auth_msg()
            await websocket.send(auth)
            response = await websocket.recv()
            self.result = json.loads(response)['result']
            if 'refresh_token' in self.result:
                self.token = self.result['refresh_token']
            await websocket.send(msg)
            result = await websocket.recv()
            self.result = json.loads(result)['result']
            print(' ')

    def _get_fills_msg(self, end_id=None):
        # give the end if, because result are returned youngest to oldest
        msg = {
                "jsonrpc": "2.0",
                "id": 9305,
                "method": "private/get_user_trades_by_currency",
                "params": {
                            "currency": "BTC",
                            "include_old": "true",
                            "count": self.API_MAX,
                            "sorting": "desc"
                }
            }
        if end_id is not None:
            msg['params']['end_id'] = str(end_id)
        return msg

    def _get_funding_payment_msg(self, continuation=None):
        # give the end if, because result are returned youngest to oldest
        msg = \
            {
                "jsonrpc": "2.0",
                "id": 8304,
                "method": "private/get_settlement_history_by_currency",
                "params": {
                    "currency": "BTC",
                    "type": "settlement",
                    "count": str(self.API_MAX)
                }
            }
        if continuation is not None:
            msg['params']['continuation'] = str(continuation)
        return msg

    def _get_deposits_msg(self, offset=0):
        # give the end if, because result are returned youngest to oldest
        msg = \
            {
                "jsonrpc": "2.0",
                "id": 5611,
                "method": "private/get_deposits",
                "params": {
                    "currency": "BTC",
                    "count": self.API_MAX,
                    "offset": offset
                }
            }
        return msg

    def _get_wallet_value_msg(self, offset=0):
        # give the end if, because result are returned youngest to oldest
        msg = \
            {
                "jsonrpc": "2.0",
                "id": 2515,
                "method": "private/get_account_summary",
                "params": {
                    "currency": "BTC",
                    "extended": True
                }
            }
        return msg

    def _get_withdrawals_msg(self, offset=0):
        # give the end if, because result are returned youngest to oldest
        msg = \
            {
                "jsonrpc": "2.0",
                "id": 5611,
                "method": "private/get_withdrawals",
                "params": {
                    "currency": "BTC",
                    "count": self.API_MAX,
                    "offset": offset
                }
            }
        return msg


if __name__ == "__main__":
    e = Deribit(None)
    for x in e.transaction_log():
        print(' ')
