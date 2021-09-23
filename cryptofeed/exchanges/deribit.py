from collections import defaultdict
import logging
from decimal import Decimal
from typing import Dict, Tuple
import hashlib
import hmac
from datetime import datetime

from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, CANCELLED, DERIBIT, FAILED, FUNDING, FUTURES, L2_BOOK, LIMIT, LIQUIDATIONS, MAKER, MARKET, OPEN, OPEN_INTEREST, PERPETUAL, SELL, STOP_LIMIT, STOP_MARKET, TAKER, TICKER, TRADES, FILLED
from cryptofeed.defines import CURRENCY, BALANCES, ORDER_INFO, FILLS, L1_BOOK
from cryptofeed.feed import Feed
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.symbols import Symbol
from cryptofeed.exchanges.mixins.deribit_rest import DeribitRestMixin
from cryptofeed.types import OrderBook, Trade, Ticker, Funding, OpenInterest, Liquidation, OrderInfo, Balance, L1Book, Fill

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
        FILLS: 'user.trades',
        BALANCES: 'user.portfolio',
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
        self._open_interest_cache = {}
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
            t = Trade(
                self.id,
                self.exchange_symbol_to_std_symbol(trade["instrument_name"]),
                BUY if trade['direction'] == 'buy' else SELL,
                Decimal(trade['amount']),
                Decimal(trade['price']),
                self.timestamp_normalize(trade['timestamp']),
                id=trade['trade_id'],
                raw=trade
            )
            await self.callback(TRADES, t, timestamp)

            if 'liquidation' in trade:
                liq = Liquidation(
                    self.id,
                    self.exchange_symbol_to_std_symbol(trade["instrument_name"]),
                    BUY if trade['direction'] == 'buy' else SELL,
                    Decimal(trade['amount']),
                    Decimal(trade['price']),
                    trade['trade_id'],
                    FILLED,
                    self.timestamp_normalize(trade['timestamp']),
                    raw=trade
                )
                await self.callback(LIQUIDATIONS, liq, timestamp)

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
        t = Ticker(
            self.id,
            pair,
            Decimal(msg["params"]["data"]['best_bid_price']),
            Decimal(msg["params"]["data"]['best_ask_price']),
            ts,
            raw=msg
        )
        await self.callback(TICKER, t, timestamp)

        if "current_funding" in msg["params"]["data"] and "funding_8h" in msg["params"]["data"]:
            f = Funding(
                self.id,
                pair,
                Decimal(msg['params']['data']['mark_price']),
                Decimal(msg["params"]["data"]["current_funding"]),
                None,
                ts,
                raw=msg
            )
            await self.callback(FUNDING, f, timestamp)

        oi = msg['params']['data']['open_interest']
        if pair in self._open_interest_cache and oi == self._open_interest_cache[pair]:
            return
        self._open_interest_cache[pair] = oi
        o = OpenInterest(
            self.id,
            pair,
            Decimal(oi),
            ts,
            raw=msg
        )
        await self.callback(OPEN_INTEREST, o, timestamp)

    async def _quote(self, quote: dict, timestamp: float):
        book = L1Book(
            self.id,
            self.exchange_symbol_to_std_symbol(quote['instrument_name']),
            Decimal(quote['best_bid_price']),
            Decimal(quote['best_bid_amount']),
            Decimal(quote['best_ask_price']),
            Decimal(quote['best_ask_amount']),
            self.timestamp_normalize(quote['timestamp']),
            raw=quote
        )
        await self.callback(L1_BOOK, book, timestamp)

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
        self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth)
        self._l2_book[pair].book.bids = {Decimal(price): Decimal(amount) for _, price, amount in msg["params"]["data"]["bids"]}
        self._l2_book[pair].book.asks = {Decimal(price): Decimal(amount) for _, price, amount in msg["params"]["data"]["asks"]}
        self.seq_no[pair] = msg["params"]["data"]["change_id"]

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(ts), sequence_number=msg["params"]["data"]["change_id"], raw=msg)

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
            if action != "delete":
                self._l2_book[pair].book.bids[price] = Decimal(amount)
                delta[BID].append((Decimal(price), Decimal(amount)))
            else:
                del self._l2_book[pair].book.bids[price]
                delta[BID].append((Decimal(price), Decimal(amount)))

        for action, price, amount in msg["params"]["data"]["asks"]:
            if action != "delete":
                self._l2_book[pair].book.asks[price] = amount
                delta[ASK].append((Decimal(price), Decimal(amount)))
            else:
                del self._l2_book[pair].book.asks[price]
                delta[ASK].append((Decimal(price), Decimal(amount)))
        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(ts), raw=msg, delta=delta, sequence_number=msg['params']['data']['change_id'])

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
        order_status = {
            "open": OPEN,
            "filled": FILLED,
            "rejected": FAILED,
            "cancelled": CANCELLED,
            "untriggered": OPEN
        }
        order_types = {
            "limit": LIMIT,
            "market": MARKET,
            "stop_limit": STOP_LIMIT,
            "stop_market": STOP_MARKET
        }

        if 'data' in msg['params']:
            data = msg['params']['data']

            if subchan == 'portfolio':
                '''
                {
                    "params" : {
                        "data" : {
                            "total_pl" : 0.00000425,
                            "session_upl" : 0.00000425,
                            "session_rpl" : -2e-8,
                            "projected_maintenance_margin" : 0.00009141,
                            "projected_initial_margin" : 0.00012542,
                            "projected_delta_total" : 0.0043,
                            "portfolio_margining_enabled" : false,
                            "options_vega" : 0,
                            "options_value" : 0,
                            "options_theta" : 0,
                            "options_session_upl" : 0,
                            "options_session_rpl" : 0,
                            "options_pl" : 0,
                            "options_gamma" : 0,
                            "options_delta" : 0,
                            "margin_balance" : 0.2340038,
                            "maintenance_margin" : 0.00009141,
                            "initial_margin" : 0.00012542,
                            "futures_session_upl" : 0.00000425,
                            "futures_session_rpl" : -2e-8,
                            "futures_pl" : 0.00000425,
                            "estimated_liquidation_ratio" : 0.01822795,
                            "equity" : 0.2340038,
                            "delta_total" : 0.0043,
                            "currency" : "BTC",
                            "balance" : 0.23399957,
                            "available_withdrawal_funds" : 0.23387415,
                            "available_funds" : 0.23387838
                        },
                        "channel" : "user.portfolio.btc"
                    },
                    "method" : "subscription",
                    "jsonrpc" : "2.0"
                }
                '''
                b = Balance(
                    self.id,
                    data['currency'],
                    Decimal(data['balance']),
                    Decimal(data['balance']) - Decimal(data['available_withdrawal_funds']),
                    raw=data
                )
                await self.callback(BALANCES, b, timestamp)

            elif subchan == 'orders':
                '''
                {
                    "params" : {
                        "data" : {
                            "time_in_force" : "good_til_cancelled",
                            "replaced" : false,
                            "reduce_only" : false,
                            "profit_loss" : 0,
                            "price" : 10502.52,
                            "post_only" : false,
                            "original_order_type" : "market",
                            "order_type" : "limit",
                            "order_state" : "open",
                            "order_id" : "5",
                            "max_show" : 200,
                            "last_update_timestamp" : 1581507423789,
                            "label" : "",
                            "is_liquidation" : false,
                            "instrument_name" : "BTC-PERPETUAL",
                            "filled_amount" : 0,
                            "direction" : "buy",
                            "creation_timestamp" : 1581507423789,
                            "commission" : 0,
                            "average_price" : 0,
                            "api" : false,
                            "amount" : 200
                        },
                        "channel" : "user.orders.BTC-PERPETUAL.raw"
                    },
                    "method" : "subscription",
                    "jsonrpc" : "2.0"
                }
                '''
                oi = OrderInfo(
                    self.id,
                    self.exchange_symbol_to_std_symbol(data['instrument_name']),
                    data["order_id"],
                    BUY if msg["side"] == 'Buy' else SELL,
                    order_status[data["order_state"]],
                    order_types[data['order_type']],
                    Decimal(data['price']),
                    Decimal(data['filled_amount']),
                    Decimal(data['amount']) - Decimal(data['cumQuantity']),
                    self.timestamp_normalize(data["last_update_timestamp"]),
                    raw=data
                )
                await self.callback(ORDER_INFO, oi, timestamp)

            elif subchan == 'trades':
                '''
                {
                    "params" : {
                        "data" : [
                        {
                            "trade_seq" : 30289432,
                            "trade_id" : "48079254",
                            "timestamp" : 1590484156350,
                            "tick_direction" : 0,
                            "state" : "filled",
                            "self_trade" : false,
                            "reduce_only" : false,
                            "price" : 8954,
                            "post_only" : false,
                            "order_type" : "market",
                            "order_id" : "4008965646",
                            "matching_id" : null,
                            "mark_price" : 8952.86,
                            "liquidity" : "T",
                            "instrument_name" : "BTC-PERPETUAL",
                            "index_price" : 8956.73,
                            "fee_currency" : "BTC",
                            "fee" : 0.00000168,
                            "direction" : "sell",
                            "amount" : 20
                        }]
                    }
                }
                '''
                for entry in data:
                    symbol = self.exchange_symbol_to_std_symbol(entry['instrument_name'])
                    f = Fill(
                        self.id,
                        symbol,
                        SELL if entry['direction'] == 'sell' else BUY,
                        Decimal(entry['amount']),
                        Decimal(entry['price']),
                        Decimal(entry['fee']),
                        entry['trade_id'],
                        entry['order_id'],
                        entry['order_type'],
                        TAKER if entry['liquidity'] == 'T' else MAKER,
                        self.timestamp_normalize(entry['timestamp']),
                        raw=entry
                    )
                    await self.callback(FILLS, f, timestamp)
            else:
                LOG.warning("%s: Unknown channel 'user.%s'", conn.uuid, subchan)
        else:
            LOG.warning("%s: Unknown message %s'", conn.uuid, msg)
