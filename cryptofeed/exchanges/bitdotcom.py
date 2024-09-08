'''
Copyright (C) 2021 - STS Digital
'''
import itertools
import logging
from decimal import Decimal
import time
from typing import Dict, Tuple
from collections import defaultdict
import hashlib
import hmac

from yapic import json
from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint

from cryptofeed.defines import ASK, BALANCES, BID, BUY, BITDOTCOM, CANCELLED, FILLED, FILLS, FUTURES, L2_BOOK, LIMIT, MARKET, OPEN, OPTION, PENDING, PERPETUAL, SELL, SPOT, STOP_LIMIT, STOP_MARKET, TICKER, TRADES, ORDER_INFO, TRIGGER_LIMIT, TRIGGER_MARKET
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol, str_to_symbol
from cryptofeed.types import Trade, Ticker, OrderBook, OrderInfo, Balance, Fill


LOG = logging.getLogger('feedhandler')


class BitDotCom(Feed):
    id = BITDOTCOM

    websocket_endpoints = [
        WebsocketEndpoint('wss://spot-ws.bit.com', instrument_filter=('TYPE', (SPOT,)), sandbox='wss://betaspot-ws.bitexch.dev'),
        WebsocketEndpoint('wss://ws.bit.com', instrument_filter=('TYPE', (FUTURES, OPTION, PERPETUAL)), sandbox='wss://betaws.bitexch.dev'),
    ]
    rest_endpoints = [
        RestEndpoint('https://spot-api.bit.com', instrument_filter=('TYPE', (SPOT,)), sandbox='https://betaspot-api.bitexch.dev', routes=Routes('/spot/v1/instruments', authentication='/spot/v1/ws/auth')),
        RestEndpoint('https://api.bit.com', instrument_filter=('TYPE', (OPTION, FUTURES, PERPETUAL)), sandbox='https://betaapi.bitexch.dev', routes=Routes('/linear/v1/instruments?currency={}&active=true', currencies=True, authentication='/v1/ws/auth'))
    ]

    websocket_channels = {
        L2_BOOK: 'depth',
        TRADES: 'trade',
        TICKER: 'ticker',
        ORDER_INFO: 'order',
        BALANCES: 'account',
        FILLS: 'user_trade',
        # funding rates paid and received
    }
    request_limit = 10

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sequence_no = defaultdict(int)

    @classmethod
    def _symbol_endpoint_prepare(cls, ep: RestEndpoint) -> str:
        if ep.routes.currencies:
            return ep.route('instruments').format('USDT')
        return ep.route('instruments')

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1000.0

    @classmethod
    def _parse_symbol_data(cls, data: list) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data:
            if entry['code'] != 0:
                raise ValueError('%s - Failed to collect instrument data - %s', cls.id, entry['message'])

            for mapping in entry['data']:
                if 'category' in mapping:
                    expiry = None
                    strike = None
                    otype = None
                    if mapping['category'] == 'option':
                        stype = OPTION
                        strike = int(float(mapping['strike_price']))
                        expiry = cls.timestamp_normalize(mapping['expiration_at'])
                        otype = mapping['option_type']
                    elif mapping['category'] == 'future':
                        if 'PERPETUAL' in mapping['instrument_id']:
                            stype = PERPETUAL
                        else:
                            stype = FUTURES
                            expiry = cls.timestamp_normalize(mapping['expiration_at'])

                    s = Symbol(mapping['base_currency'], mapping['quote_currency'], type=stype, option_type=otype, expiry_date=expiry, strike_price=strike)
                    ret[s.normalized] = mapping['instrument_id']
                    info['instrument_type'][s.normalized] = stype
                else:
                    # Spot
                    s = Symbol(mapping['base_currency'], mapping['quote_currency'], type=SPOT)
                    ret[s.normalized] = mapping['pair']
                    info['instrument_type'][s.normalized] = SPOT

        return ret, info

    def __reset(self, conn: AsyncConnection):
        if self.std_channel_to_exchange(L2_BOOK) in conn.subscription:
            for pair in conn.subscription[self.std_channel_to_exchange(L2_BOOK)]:
                std_pair = self.exchange_symbol_to_std_symbol(pair)

                if std_pair in self._l2_book:
                    del self._l2_book[std_pair]

                if std_pair in self._sequence_no:
                    del self._sequence_no[std_pair]

    def encode_list(self, item_list: list):
        list_val = []
        for item in item_list:
            obj_val = self.encode_object(item)
            list_val.append(obj_val)
        output = '&'.join(list_val)
        return '[' + output + ']'

    def get_signature(self, api_path: str, param_map: dict):
        str_to_sign = api_path + '&' + self.encode_object(param_map)
        return hmac.new(self.key_secret.encode('utf-8'), str_to_sign.encode('utf-8'), digestmod=hashlib.sha256).hexdigest()

    def encode_object(self, param_map: dict):
        sorted_keys = sorted(param_map.keys())
        ret_list = []
        for key in sorted_keys:
            val = param_map[key]
            if isinstance(val, list):
                list_val = self.encode_list(val)
                ret_list.append(f'{key}={list_val}')
            elif isinstance(val, dict):
                dict_val = self.encode_object(val)
                ret_list.append(f'{key}={dict_val}')
            elif isinstance(val, bool):
                bool_val = str(val).lower()
                ret_list.append(f'{key}={bool_val}')
            else:
                general_val = str(val)
                ret_list.append(f'{key}={general_val}')

        sorted_list = sorted(ret_list)
        return '&'.join(sorted_list)

    async def authenticate(self, connection: AsyncConnection):
        if not self.key_id or not self.key_secret:
            return
        if any([self.is_authenticated_channel(self.exchange_channel_to_std(c)) for c in connection.subscription]):
            symbols = list(set(itertools.chain(*connection.subscription.values())))
            sym = str_to_symbol(self.exchange_symbol_to_std_symbol(symbols[0]))
            for ep in self.rest_endpoints:
                if sym.type in ep.instrument_filter[1]:
                    ts = int(round(time.time() * 1000))
                    signature = self.get_signature(ep.routes.authentication, {'timestamp': ts})
                    params = {'timestamp': ts, 'signature': signature}
                    ret = self.http_sync.read(ep.route('authentication', sandbox=self.sandbox), params=params, headers={'X-Bit-Access-Key': self.key_id}, json=True)
                    if ret['code'] != 0 or 'token' not in ret['data']:
                        LOG.warning('%s: authentication failed: %s', ret)
                    token = ret['data']['token']
                    self._auth_token = token
                    return

    async def subscribe(self, connection: AsyncConnection):
        self.__reset(connection)

        for chan, symbols in connection.subscription.items():
            if len(symbols) == 0:
                continue
            stype = str_to_symbol(self.exchange_symbol_to_std_symbol(symbols[0])).type
            msg = {
                'type': 'subscribe',
                'channels': [chan],
                'instruments' if stype in {PERPETUAL, FUTURES, OPTION} else 'pairs': symbols,
            }
            if self.is_authenticated_channel(self.exchange_channel_to_std(chan)):
                msg['token'] = self._auth_token
            await connection.write(json.dumps(msg))

    async def _trade(self, data: dict, timestamp: float):
        """
        {
            'channel': 'trade',
            'timestamp': 1639080717242,
            'data': [{
                'trade_id': '7016884324',
                'instrument_id': 'BTC-PERPETUAL',
                'price': '47482.50000000',
                'qty': '6000.00000000',
                'side': 'sell',
                'sigma': '0.00000000',
                'is_block_trade': False,
                'created_at': 1639080717195
            }]
        }
        """
        for t in data['data']:
            trade = Trade(self.id,
                          self.exchange_symbol_to_std_symbol(t.get('instrument_id') or t.get('pair')),
                          SELL if t['side'] == 'sell' else BUY,
                          Decimal(t['qty']),
                          Decimal(t['price']),
                          self.timestamp_normalize(t['created_at']),
                          id=t['trade_id'],
                          raw=t)
            await self.callback(TRADES, trade, timestamp)

    async def _book(self, data: dict, timestamp: float):
        '''
        Snapshot

        {
            'channel': 'depth',
            'timestamp': 1639083660346,
            'data': {
                'type': 'snapshot',
                'instrument_id': 'BTC-PERPETUAL',
                'sequence': 1639042602148589825,
                'bids': [
                    ['47763.00000000', '20000.00000000'],
                    ['47762.50000000', '6260.00000000'],
                    ...
                ]
                'asks': [
                    ['47768.00000000', '10000.00000000'],
                    ['47776.50000000', '20000.00000000'],
                    ...
                ]
            }
        }

        Delta

        {
            'channel': 'depth',
            'timestamp': 1639083660401,
            'data': {
                'type': 'update',
                'instrument_id': 'BTC-PERPETUAL',
                'sequence': 1639042602148589842,
                'prev_sequence': 1639042602148589841,
                'changes': [
                    ['sell', '47874.00000000', '0.00000000']
                ]
            }
        }
        '''
        if data['data']['type'] == 'update':
            pair = self.exchange_symbol_to_std_symbol(data['data'].get('instrument_id') or data['data'].get('pair'))
            if data['data']['sequence'] != self._sequence_no[pair] + 1:
                raise MissingSequenceNumber("Missing sequence number, restarting")

            self._sequence_no[pair] = data['data']['sequence']
            delta = {BID: [], ASK: []}

            for side, price, amount in data['data']['changes']:
                side = ASK if side == 'sell' else BID
                price = Decimal(price)
                amount = Decimal(amount)

                if amount == 0:
                    delta[side].append((price, 0))
                    del self._l2_book[pair].book[side][price]
                else:
                    delta[side].append((price, amount))
                    self._l2_book[pair].book[side][price] = amount

            await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(data['timestamp']), raw=data, sequence_number=self._sequence_no[pair], delta=delta)
        else:
            pair = self.exchange_symbol_to_std_symbol(data['data'].get('instrument_id') or data['data'].get('pair'))
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth, bids={Decimal(price): Decimal(size) for price, size in data['data']['bids']}, asks={Decimal(price): Decimal(size) for price, size in data['data']['asks']})
            self._sequence_no[pair] = data['data']['sequence']
            await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(data['timestamp']), raw=data, sequence_number=data['data']['sequence'])

    async def _ticker(self, data: dict, timestamp: float):
        '''
        {
            'channel': 'ticker',
            'timestamp': 1639093870710,
            'data': {
                'time': 1639093870710,
                'instrument_id': 'ETH-PERPETUAL',
                'best_bid': '4155.85000000',
                'best_ask': '4155.90000000',
                'best_bid_qty': '2000.00000000',
                'best_ask_qty': '3000.00000000',
                'ask_sigma': '',
                'bid_sigma': '',
                'last_price': '4157.80000000',
                'last_qty': '1000.00000000',
                'open24h': '4436.75000000',
                'high24h': '4490.00000000',
                'low24h': '4086.60000000',
                'price_change24h': '-0.06287260',
                'volume24h': '1000218.00000000',
                'open_interest': '7564685.00000000',
                'funding_rate': '0.00025108',
                'funding_rate8h': '0.00006396',
                'mark_price': '4155.62874869',
                'min_sell': '4030.50000000',
                'max_buy': '4280.50000000'
            }
        }
        '''
        if data['data']['best_bid'] and data['data']['best_ask']:
            t = Ticker(
                self.id,
                self.exchange_symbol_to_std_symbol(data['data'].get('instrument_id') or data['data'].get('pair')),
                Decimal(data['data']['best_bid']),
                Decimal(data['data']['best_ask']),
                self.timestamp_normalize(data['timestamp']),
                raw=data
            )
            await self.callback(TICKER, t, timestamp)

    def _order_type_translate(self, t: str) -> str:
        if t == 'limit':
            return LIMIT
        if t == 'market':
            return MARKET
        if t == 'stop-limit':
            return STOP_LIMIT
        if t == 'stop-market':
            return STOP_MARKET
        if t == 'trigger-limit':
            return TRIGGER_LIMIT
        if t == 'trigger-market':
            return TRIGGER_MARKET
        raise ValueError('Invalid order type detected %s', t)

    def _status_translate(self, s: str) -> str:
        if s == 'open':
            return OPEN
        if s == 'pending':
            return PENDING
        if s == 'filled':
            return FILLED
        if s == 'cancelled':
            return CANCELLED
        raise ValueError('Invalid order status detected %s', s)

    async def _order(self, msg: dict, timestamp: float):
        """
        {
            "channel":"order",
            "timestamp":1587994934089,
            "data":[
                {
                    "order_id":"1590",
                    "instrument_id":"BTC-1MAY20-8750-P",
                    "qty":"0.50000000",
                    "filled_qty":"0.10000000",
                    "remain_qty":"0.40000000",
                    "price":"0.16000000",
                    "avg_price":"0.16000000",
                    "side":"buy",
                    "order_type":"limit",
                    "time_in_force":"gtc",
                    "created_at":1587870609000,
                    "updated_at":1587870609000,
                    "status":"open",
                    "fee":"0.00002000",
                    "cash_flow":"-0.01600000",
                    "pnl":"0.00000000",
                    "is_liquidation": false,
                    "auto_price":"0.00000000",
                    "auto_price_type":"",
                    "taker_fee_rate": "0.00050000",
                    "maker_fee_rate": "0.00020000",
                    "label": "hedge",
                    "stop_price": "0.00000000",
                    "reduce_only": false,
                    "post_only": false,
                    "reject_post_only": false,
                    "mmp": false,
                    "reorder_index": 1
                }
            ]
        }
        """
        for entry in msg['data']:
            oi = OrderInfo(
                self.id,
                self.exchange_symbol_to_std_symbol(entry['instrument_id']),
                entry['order_id'],
                BUY if entry['side'] == 'buy' else SELL,
                self._status_translate(entry['status']),
                self._order_type_translate(entry['order_type']),
                Decimal(entry['price']),
                Decimal(entry['filled_qty']),
                Decimal(entry['remain_qty']),
                self.timestamp_normalize(entry['updated_at']),
                raw=entry
            )
            await self.callback(ORDER_INFO, oi, timestamp)

    async def _balances(self, msg: dict, timestamp: float):
        '''
        Futures/Options
        {
            "channel":"account",
            "timestamp":1589031930115,
            "data":{
                "user_id":"53345",
                "currency":"BTC",
                "cash_balance":"9999.94981346",
                "available_balance":"9999.90496213",
                "margin_balance":"9999.94981421",
                "initial_margin":"0.04485208",
                "maintenance_margin":"0.00000114",
                "equity":"10000.00074364",
                "pnl":"0.00746583",
                "total_delta":"0.06207078",
                "account_id":"8",
                "mode":"regular",
                "session_upl":"0.00081244",
                "session_rpl":"0.00000021",
                "option_value":"0.05092943",
                "option_pnl":"0.00737943",
                "option_session_rpl":"0.00000000",
                "option_session_upl":"0.00081190",
                "option_delta":"0.11279249",
                "option_gamma":"0.00002905",
                "option_vega":"4.30272923",
                "option_theta":"-3.08908220",
                "future_pnl":"0.00008640",
                "future_session_rpl":"0.00000021",
                "future_session_upl":"0.00000054",
                "future_session_funding":"0.00000021",
                "future_delta":"0.00955630",
                "created_at":1588997840512,
                "projected_info": {
                    "projected_initial_margin": "0.97919888",
                    "projected_maintenance_margin": "0.78335911",
                    "projected_total_delta": "3.89635553"
                }
            }
        }

        Spot
        {
            'channel': 'account',
            'timestamp': 1641516119102,
            'data': {
                'user_id': '979394',
                'balances': [
                    {
                        'currency': 'BTC',
                        'available': '31.02527500',
                        'frozen': '0.00000000'
                    },
                    {
                        'currency': 'ETH',
                        'available': '110.00000000',
                        'frozen': '0.00000000'
                    }
                ]
            }
        }
        '''
        if 'balances' in msg['data']:
            # Spot
            for balance in msg['data']['balances']:
                b = Balance(
                    self.id,
                    balance['currency'],
                    Decimal(balance['available']),
                    Decimal(balance['frozen']),
                    raw=msg
                )
                await self.callback(BALANCES, b, timestamp)
        else:
            b = Balance(
                self.id,
                msg['data']['currency'],
                Decimal(msg['data']['cash_balance']),
                Decimal(msg['data']['cash_balance']) - Decimal(msg['data']['available_balance']),
                raw=msg
            )
            await self.callback(BALANCES, b, timestamp)

    async def _fill(self, msg: dict, timestamp: float):
        '''
        {
            "channel":"user_trade",
            "timestamp":1588997059737,
            "data":[
                {
                    "trade_id":2388418,
                    "order_id":1384232,
                    "instrument_id":"BTC-26JUN20-6000-P",
                    "qty":"0.10000000",
                    "price":"0.01800000",
                    "sigma":"1.15054346",
                    "underlying_price":"9905.54000000",
                    "index_price":"9850.47000000",
                    "usd_price":"177.30846000",
                    "fee":"0.00005000",
                    "fee_rate":"0.00050000",
                    "side":"buy",
                    "created_at":1588997060000,
                    "is_taker":true,
                    "order_type":"limit",
                    "is_block_trade":false,
                    "label": "hedge"
                }
            ]
        }
        '''
        for entry in msg['data']:
            f = Fill(
                self.id,
                self.exchange_symbol_to_std_symbol(entry['instrument_id']),
                BUY if entry['side'] == 'buy' else SELL,
                Decimal(entry['qty']),
                Decimal(entry['price']),
                Decimal(entry['fee']),
                str(entry['trade_id']),
                str(entry['order_id']),
                self._order_type_translate(entry['order_type']),
                None,
                self.timestamp_normalize(entry['created_at']),
                raw=entry
            )
            await self.callback(FILLS, f, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if msg['channel'] == 'depth':
            await self._book(msg, timestamp)
        elif msg['channel'] == 'trade':
            await self._trade(msg, timestamp)
        elif msg['channel'] == 'ticker':
            await self._ticker(msg, timestamp)
        elif msg['channel'] == 'order':
            await self._order(msg, timestamp)
        elif msg['channel'] == 'account':
            await self._balances(msg, timestamp)
        elif msg['channel'] == 'user_trade':
            await self._fill(msg, timestamp)
        elif msg['channel'] == 'subscription':
            """
            {
                'channel': 'subscription',
                'timestamp': 1639080572093,
                'data': {'code': 0, 'subscription': ['trade']}
            }
            """
            if msg['data']['code'] == 0:
                return
            else:
                LOG.warning("%s: error received from exchange while subscribing: %s", self.id, msg)
        else:
            LOG.warning("%s: Unexpected message received: %s", self.id, msg)
