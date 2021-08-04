from collections import defaultdict
from cryptofeed.exchanges.mixins.deribit_rest import DeribitRestMixin
import logging
from decimal import Decimal
from typing import Dict, Tuple

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, DERIBIT, FUNDING, FUTURES, L2_BOOK, LIQUIDATIONS, OPEN_INTEREST, PERPETUAL, SELL, TICKER, TRADES, FILLED, USER_DATA
from cryptofeed.defines import CURRENCY, BALANCES, ORDER_INFO, USER_FILLS, L1_BOOK
from cryptofeed.feed import Feed
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.symbols import Symbol
# For auth
import hashlib
import hmac
from datetime import datetime


LOG = logging.getLogger('feedhandler')


class Deribit(Feed, DeribitRestMixin):
    id = DERIBIT
    symbol_endpoint = ['https://www.deribit.com/api/v2/public/get_instruments?currency=BTC', 'https://www.deribit.com/api/v2/public/get_instruments?currency=ETH']
    websocket_channels = {
        L1_BOOK: 'quote',
        L2_BOOK: 'book',
        TRADES: 'trades',
        TICKER: 'ticker',
        FUNDING: 'ticker',
        OPEN_INTEREST: 'ticker',
        LIQUIDATIONS: 'trades',
        ORDER_INFO: 'user.orders',
        USER_FILLS: 'user.trades',
        BALANCES: 'user.portfolio',
        USER_DATA: 'user.changes'
    }
    request_limit = 20

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1000.0

    @classmethod
    def _parse_symbol_data(cls, data: list) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        currencies = []
        for entry in data:
            for e in entry['result']:
                base = e['base_currency']
                if base not in currencies:
                    currencies.append(base)
                quote = e['quote_currency']
                stype = e['kind'] if e['settlement_period'] != 'perpetual' else PERPETUAL
                otype = e.get('option_type')
                strike_price = e.get('strike')
                strike_price = int(strike_price) if strike_price else None
                expiry = e['expiration_timestamp'] / 1000
                s = Symbol(base, quote, type=FUTURES if stype == 'future' else stype, option_type=otype, strike_price=strike_price, expiry_date=expiry)
                ret[s.normalized] = e['instrument_name']
                info['tick_size'][s.normalized] = e['tick_size']
                info['instrument_type'][s.normalized] = stype
        for currency in currencies:
            s = Symbol(currency, currency, type=CURRENCY)
            ret[s.normalized] = currency
            info['instrument_type'][s.normalized] = CURRENCY
        return ret, info

    def __init__(self, **kwargs):
        super().__init__('wss://www.deribit.com/ws/api/v2', **kwargs)
        self.__reset()

    def __reset(self):
        self.open_interest = {}
        self._l2_book = {}
        self.seq_no = {}

    async def _trade(self, msg: dict, timestamp: float):
        """
        {
            "params":
            {
                "data":
                [
                    {
                        "trade_seq": 933,
                        "trade_id": "9178",
                        "timestamp": 1550736299753,
                        "tick_direction": 3,
                        "price": 3948.69,
                        "instrument_name": "BTC-PERPETUAL",
                        "index_price": 3930.73,
                        "direction": "sell",
                        "amount": 10
                    }
                ],
                "channel": "trades.BTC-PERPETUAL.raw"
            },
            "method": "subscription",
            "jsonrpc": "2.0"
        }
        """
        for trade in msg["params"]["data"]:
            await self.callback(TRADES,
                                feed=self.id,
                                symbol=self.exchange_symbol_to_std_symbol(trade["instrument_name"]),
                                order_id=trade['trade_id'],
                                side=BUY if trade['direction'] == 'buy' else SELL,
                                amount=Decimal(trade['amount']),
                                price=Decimal(trade['price']),
                                timestamp=self.timestamp_normalize(trade['timestamp']),
                                receipt_timestamp=timestamp,
                                )
            if 'liquidation' in trade:
                await self.callback(LIQUIDATIONS,
                                    feed=self.id,
                                    symbol=self.exchange_symbol_to_std_symbol(trade["instrument_name"]),
                                    side=BUY if trade['direction'] == 'buy' else SELL,
                                    leaves_qty=Decimal(trade['amount']),
                                    price=Decimal(trade['price']),
                                    order_id=trade['trade_id'],
                                    status=FILLED,
                                    timestamp=self.timestamp_normalize(trade['timestamp']),
                                    receipt_timestamp=timestamp
                                    )

    async def _ticker(self, msg: dict, timestamp: float):
        '''
        {
            "params" : {
                "data" : {
                    "timestamp" : 1550652954406,
                    "stats" : {
                        "volume" : null,
                        "low" : null,
                        "high" : null
                    },
                    "state" : "open",
                    "settlement_price" : 3960.14,
                    "open_interest" : 0.12759952124659626,
                    "min_price" : 3943.21,
                    "max_price" : 3982.84,
                    "mark_price" : 3940.06,
                    "last_price" : 3906,
                    "instrument_name" : "BTC-PERPETUAL",
                    "index_price" : 3918.51,
                    "funding_8h" : 0.01520525,
                    "current_funding" : 0.00499954,
                    "best_bid_price" : 3914.97,
                    "best_bid_amount" : 40,
                    "best_ask_price" : 3996.61,
                    "best_ask_amount" : 50
                    },
                "channel" : "ticker.BTC-PERPETUAL.raw"
            },
            "method" : "subscription",
            "jsonrpc" : "2.0"}
        '''
        pair = self.exchange_symbol_to_std_symbol(msg['params']['data']['instrument_name'])
        ts = self.timestamp_normalize(msg['params']['data']['timestamp'])
        await self.callback(TICKER, feed=self.id,
                            symbol=pair,
                            bid=Decimal(msg["params"]["data"]['best_bid_price']),
                            ask=Decimal(msg["params"]["data"]['best_ask_price']),
                            timestamp=ts,
                            receipt_timestamp=timestamp)

        if "current_funding" in msg["params"]["data"] and "funding_8h" in msg["params"]["data"]:
            await self.callback(FUNDING, feed=self.id,
                                symbol=pair,
                                timestamp=ts,
                                receipt_timestamp=timestamp,
                                rate=msg["params"]["data"]["current_funding"],
                                rate_8h=msg["params"]["data"]["funding_8h"])
        oi = msg['params']['data']['open_interest']
        if pair in self.open_interest and oi == self.open_interest[pair]:
            return
        self.open_interest[pair] = oi
        await self.callback(OPEN_INTEREST,
                            feed=self.id,
                            symbol=pair,
                            open_interest=oi,
                            timestamp=ts,
                            receipt_timestamp=timestamp
                            )

    async def _quote(self, quote: dict, timestamp: float):
        await self.callback(L1_BOOK,
                            feed=self.id,
                            symbol=self.exchange_symbol_to_std_symbol(quote['instrument_name']),
                            bid_price=Decimal(quote['best_bid_price']),
                            ask_price=Decimal(quote['best_ask_price']),
                            bid_amount=Decimal(quote['best_bid_amount']),
                            ask_amount=Decimal(quote['best_ask_amount']),
                            timestamp=self.timestamp_normalize(quote['timestamp']),
                            receipt_timestamp=timestamp,
                            )

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()

        pub_channels = []
        pri_channels = []
        for chan in self.subscription:
            if self.is_authenticated_channel(self.exchange_channel_to_std(chan)):
                for pair in self.subscription[chan]:
                    if self.exchange_channel_to_std(chan) == BALANCES:
                        pri_channels.append(f"{chan}.{pair}")
                    else:
                        pri_channels.append(f"{chan}.{pair}.raw")
            else:
                for pair in self.subscription[chan]:
                    if self.exchange_channel_to_std(chan) == L1_BOOK:
                        pub_channels.append(f"{chan}.{pair}")
                    else:
                        pub_channels.append(f"{chan}.{pair}.raw")
        if pub_channels:
            msg = {"jsonrpc": "2.0",
                   "id": "101",
                   "method": "public/subscribe",
                   "params": {"channels": pub_channels}}
            LOG.debug(f'{conn.uuid}: Subscribing to public channels with message {msg}')
            await conn.write(json.dumps(msg))

        if pri_channels:
            msg = {"jsonrpc": "2.0",
                   "id": "102",
                   "method": "private/subscribe",
                   "params": {"scope": f"session:{conn.uuid}", "channels": pri_channels}}
            LOG.debug(f'{conn.uuid}: Subscribing to private channels with message {msg}')
            await conn.write(json.dumps(msg))

    async def _book_snapshot(self, msg: dict, timestamp: float):
        """
        {
            'jsonrpc': '2.0',
            'method': 'subscription',
            'params': {
                'channel': 'book.BTC-PERPETUAL.raw',
                'data': {
                    'timestamp': 1598232105378,
                    'instrument_name': 'BTC-PERPETUAL',
                    'change_id': 21486665526, '
                    'bids': [['new', Decimal('11618.5'), Decimal('279310.0')], ..... ]
                    'asks': [[ ....... ]]
                }
            }
        }
        """
        ts = msg["params"]["data"]["timestamp"]
        pair = self.exchange_symbol_to_std_symbol(msg["params"]["data"]["instrument_name"])
        self._l2_book[pair] = {
            BID: sd({
                Decimal(price): Decimal(amount)
                # _ is always 'new' for snapshot
                for _, price, amount in msg["params"]["data"]["bids"]
            }),
            ASK: sd({
                Decimal(price): Decimal(amount)
                for _, price, amount in msg["params"]["data"]["asks"]
            })
        }

        self.seq_no[pair] = msg["params"]["data"]["change_id"]

        await self.book_callback(self._l2_book[pair], L2_BOOK, pair, True, None, self.timestamp_normalize(ts), timestamp)

    async def _book_update(self, msg: dict, timestamp: float):
        ts = msg["params"]["data"]["timestamp"]
        pair = self.exchange_symbol_to_std_symbol(msg["params"]["data"]["instrument_name"])

        if msg['params']['data']['prev_change_id'] != self.seq_no[pair]:
            LOG.warning("%s: Missing sequence number detected for %s", self.id, pair)
            LOG.warning("%s: Requesting book snapshot", self.id)
            raise MissingSequenceNumber

        self.seq_no[pair] = msg['params']['data']['change_id']

        delta = {BID: [], ASK: []}

        for action, price, amount in msg["params"]["data"]["bids"]:
            bidask = self._l2_book[pair][BID]
            if action != "delete":
                bidask[price] = Decimal(amount)
                delta[BID].append((Decimal(price), Decimal(amount)))
            else:
                del bidask[price]
                delta[BID].append((Decimal(price), Decimal(amount)))

        for action, price, amount in msg["params"]["data"]["asks"]:
            bidask = self._l2_book[pair][ASK]
            if action != "delete":
                bidask[price] = amount
                delta[ASK].append((Decimal(price), Decimal(amount)))
            else:
                del bidask[price]
                delta[ASK].append((Decimal(price), Decimal(amount)))
        await self.book_callback(self._l2_book[pair], L2_BOOK, pair, False, delta, self.timestamp_normalize(ts), timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg_dict = json.loads(msg, parse_float=Decimal)
        if 'error' in msg_dict.keys():
            LOG.error("%s: Received Error message: %s, Error code: %s", conn.uuid, msg_dict['error']['message'], msg_dict['error']['code'])

        elif "result" in msg_dict:
            result = msg_dict["result"]
            if 'id' in msg_dict:
                id = str(msg_dict["id"])
                if id == "0":
                    LOG.debug("%s: Connected", conn.uuid)
                elif id == '101':
                    LOG.info("%s: Subscribed to public channels", conn.uuid)
                    LOG.debug("%s: %s", conn.uuid, result)
                elif id == '102':
                    LOG.info("%s: Subscribed to authenticated channels", conn.uuid)
                    LOG.debug("%s: %s", conn.uuid, result)
                elif id.startswith('auth') and "access_token" in result:
                    '''
                        Access token is another way to be authenticated while sending messages to Deribit.
                        In this implementation 'scope session' method is used instead of 'acces token' method.
                    '''
                    LOG.debug(f"{conn.uuid}: Access token received")
                else:
                    LOG.warning("%s: Unknown id in message %s", conn.uuid, msg_dict)
            else:
                LOG.warning("%s: Unknown 'result' message received: %s", conn.uuid, msg_dict)

        elif 'params' in msg_dict:
            params = msg_dict['params']

            if 'channel' in params:
                channel = params['channel']

                if "ticker" == channel.split(".")[0]:
                    await self._ticker(msg_dict, timestamp)

                elif "trades" == channel.split(".")[0]:
                    await self._trade(msg_dict, timestamp)

                elif "book" == channel.split(".")[0]:
                    # checking if we got full book or its update
                    # if it's update there is 'prev_change_id' field
                    if "prev_change_id" not in msg_dict["params"]["data"].keys():
                        await self._book_snapshot(msg_dict, timestamp)
                    elif "prev_change_id" in msg_dict["params"]["data"].keys():
                        await self._book_update(msg_dict, timestamp)

                elif "quote" == channel.split(".")[0]:
                    await self._quote(params['data'], timestamp)

                elif channel.startswith("user"):
                    await self._user_channels(conn, msg_dict, timestamp, channel.split(".")[1])

                else:
                    LOG.warning("%s: Unknown channel %s", conn.uuid, msg_dict)
            else:
                LOG.warning("%s: Unknown 'params' message received: %s", conn.uuid, msg_dict)
        else:
            LOG.warning("%s: Unknown message in msg_dict: %s", conn.uuid, msg_dict)

    async def authenticate(self, conn: AsyncConnection):
        if self.requires_authentication:
            auth = self._auth(self.key_id, self.key_secret, conn.uuid)
            LOG.debug(f"{conn.uuid}: Authenticating with message: {auth}")
            await conn.write(json.dumps(auth))

    def _auth(self, key_id, key_secret, session_id: str) -> str:
        # https://docs.deribit.com/?python#authentication

        timestamp = round(datetime.now().timestamp() * 1000)
        nonce = f'xyz{str(timestamp)[-5:]}'
        signature = hmac.new(
            bytes(key_secret, "latin-1"),
            bytes('{}\n{}\n{}'.format(timestamp, nonce, ""), "latin-1"),
            digestmod=hashlib.sha256
        ).hexdigest().lower()
        auth = {
            "jsonrpc": "2.0",
            "id": f"auth_{session_id}",
            "method": "public/auth",
            "params": {
                "grant_type": "client_signature",
                "client_id": key_id,
                "timestamp": timestamp,
                "signature": signature,
                "nonce": nonce,
                "data": "",
                "scope": f"session:{session_id}"
            }
        }
        return auth

    async def _user_channels(self, conn: AsyncConnection, msg: dict, timestamp: float, subchan: str):
        if 'data' in msg['params']:
            data = msg['params']['data']

            if subchan == 'portfolio':
                currency = self.exchange_symbol_to_std_symbol(data['currency'])
                await self.callback(BALANCES, feed=self.id, currency=currency, data=data, receipt_timestamp=timestamp)

            elif subchan == 'orders':
                symbol = self.exchange_symbol_to_std_symbol(data['instrument_name'])
                await self.callback(ORDER_INFO, feed=self.id, symbol=symbol, data=data, receipt_timestamp=timestamp)

            elif subchan == 'trades':
                for i in range(len(data)):
                    symbol = self.exchange_symbol_to_std_symbol(data[i]['instrument_name'])
                    await self.callback(USER_FILLS, feed=self.id, symbol=symbol, data=data[i], receipt_timestamp=timestamp)
            else:
                LOG.warning("%s: Unknown channel 'user.%s'", conn.uuid, subchan)
        else:
            LOG.warning("%s: Unknown message %s'", conn.uuid, msg)
