'''
Copyright (C) 2018-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import hmac
import time
from collections import defaultdict
from cryptofeed.symbols import Symbol
import logging
from decimal import Decimal
from functools import partial
from typing import Dict, List, Callable, Tuple, Union
from datetime import datetime as dt

from yapic import json

from cryptofeed.connection import AsyncConnection, WSAsyncConn
from cryptofeed.defines import BID, ASK, BUY, BYBIT, CANCELLED, CANCELLING, CANDLES, FAILED, FILLED, FUNDING, L2_BOOK, LIMIT, MAKER, MARKET, OPEN, PARTIAL, SELL, SUBMITTING, TAKER, TRADES, OPEN_INTEREST, INDEX, ORDER_INFO, FILLS, FUTURES, PERPETUAL
from cryptofeed.feed import Feed
from cryptofeed.types import OrderBook, Trade, Index, OpenInterest, Funding, OrderInfo, Fill, Candle


LOG = logging.getLogger('feedhandler')


class Bybit(Feed):
    id = BYBIT
    symbol_endpoint = 'https://api.bybit.com/v2/public/symbols'
    websocket_channels = {
        L2_BOOK: 'orderBook_200.100ms',
        TRADES: 'trade',
        FILLS: 'execution',
        ORDER_INFO: 'order',
        INDEX: 'instrument_info.100ms',
        OPEN_INTEREST: 'instrument_info.100ms',
        FUNDING: 'instrument_info.100ms',
        CANDLES: 'klineV2',
        # BALANCES: 'position' removing temporarily, this is a position, not a balance
    }
    valid_candle_intervals = {'1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '1d', '1w', '1M'}

    @classmethod
    def timestamp_normalize(cls, ts: Union[int, dt]) -> float:
        if isinstance(ts, int):
            return ts / 1000.0
        else:
            return ts.timestamp()

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        # PERPETUAL & FUTURES
        for symbol in data['result']:
            base = symbol['base_currency']
            quote = symbol['quote_currency']

            stype = PERPETUAL
            expiry = None
            if not symbol['name'].endswith(quote):
                stype = FUTURES
                year = symbol['name'].replace(base + quote, '')[-2:]
                expiry = year + symbol['alias'].replace(base + quote, '')[-4:]

            s = Symbol(base, quote, type=stype, expiry_date=expiry)

            ret[s.normalized] = symbol['name']
            info['tick_size'][s.normalized] = symbol['price_filter']['tick_size']
            info['instrument_type'][s.normalized] = stype

        return ret, info

    def __init__(self, **kwargs):
        super().__init__({'USD': 'wss://stream.bybit.com/realtime', 'USDT': 'wss://stream.bybit.com/realtime_public', 'USDTP': 'wss://stream.bybit.com/realtime_private'}, **kwargs)
        self.ws_defaults['compression'] = None
        self.candle_mapping = {'1m': '1', '3m': '3', '5m': '5', '15m': '15', '30m': '30', '1h': '60', '2h': '120', '4h': '240', '6h': '360', '1d': 'D', '1w': 'W', '1M': 'M'}

    def __reset(self, quote=None):
        self._instrument_info_cache = {}
        if quote is None:
            self._l2_book = {}
        else:
            rem = [symbol for symbol in self._l2_book if quote in symbol]
            for symbol in rem:
                del self._l2_book[symbol]

    async def _candle(self, msg: dict, timestamp: float):
        '''
        {
            "topic": "klineV2.1.BTCUSD",                //topic name
            "data": [{
                "start": 1572425640,                    //start time of the candle
                "end": 1572425700,                      //end time of the candle
                "open": 9200,                           //open price
                "close": 9202.5,                        //close price
                "high": 9202.5,                         //max price
                "low": 9196,                            //min price
                "volume": 81790,                        //volume
                "turnover": 8.889247899999999,          //turnover
                "confirm": False,                       //snapshot flag
                "cross_seq": 297503466,
                "timestamp": 1572425676958323           //cross time
            }],
            "timestamp_e6": 1572425677047994            //server time
        }
        '''
        symbol = self.exchange_symbol_to_std_symbol(msg['topic'].split(".")[-1])
        ts = msg['timestamp_e6'] / 1_000_000

        for entry in msg['data']:
            c = Candle(self.id,
                       symbol,
                       entry['start'],
                       entry['end'],
                       self.candle_interval,
                       None,
                       Decimal(entry['open']),
                       Decimal(entry['close']),
                       Decimal(entry['high']),
                       Decimal(entry['low']),
                       Decimal(entry['volume']),
                       None,
                       ts,
                       raw=entry)
            await self.callback(CANDLES, c, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg = json.loads(msg, parse_float=Decimal)

        if "success" in msg:
            if msg['success']:
                if msg['request']['op'] == 'auth':
                    LOG.debug("%s: Authenticated successful", conn.uuid)
                elif msg['request']['op'] == 'subscribe':
                    LOG.debug("%s: Subscribed to channels: %s", conn.uuid, msg['request']['args'])
                else:
                    LOG.warning("%s: Unhandled 'successs' message received", conn.uuid)
            else:
                LOG.error("%s: Error from exchange %s", conn.uuid, msg)
        elif "trade" in msg["topic"]:
            await self._trade(msg, timestamp)
        elif msg["topic"].startswith('orderBook'):
            await self._book(msg, timestamp)
        elif "instrument_info" in msg["topic"]:
            await self._instrument_info(msg, timestamp)
        elif "order" in msg["topic"]:
            await self._order(msg, timestamp)
        elif "execution" in msg["topic"]:
            await self._execution(msg, timestamp)
        elif 'klineV2' in msg['topic'] or 'candle' in msg['topic']:
            await self._candle(msg, timestamp)
        # elif "position" in msg["topic"]:
        #     await self._balances(msg, timestamp)
        else:
            LOG.warning("%s: Unhandled message type %s", conn.uuid, msg)

    def connect(self) -> List[Tuple[AsyncConnection, Callable[[None], None], Callable[[str, float], None]]]:
        '''
            Linear PERPETUAL (USDT) public goes to USDT endpoint
            Linear PERPETUAL (USDT) private goes to USDTP endpoint
            Inverse PERPETUAL and FUTURES (USD) both private and public goes to USD endpoint
        '''
        ret = []
        if any(pair.split('-')[1] == 'USDT' for pair in self.normalized_symbols):
            if any(self.is_authenticated_channel(self.exchange_channel_to_std(chan)) for chan in self.subscription):
                ret.append((WSAsyncConn(self.address['USDTP'], self.id, **self.ws_defaults),
                            partial(self.subscribe, quote='USDTP'), self.message_handler, self.authenticate))
            if any(not self.is_authenticated_channel(self.exchange_channel_to_std(chan)) for chan in self.subscription):
                ret.append((WSAsyncConn(self.address['USDT'], self.id, **self.ws_defaults),
                            partial(self.subscribe, quote='USDT'), self.message_handler, self.__no_auth))
        if any(pair.split('-')[1] == 'USD' for pair in self.normalized_symbols):
            ret.append((WSAsyncConn(self.address['USD'], self.id, **self.ws_defaults),
                        partial(self.subscribe, quote='USD'), self.message_handler, self.authenticate))
        return ret

    async def subscribe(self, connection: AsyncConnection, quote: str = None):
        if quote == 'USD' or quote == 'USDTP':
            channels = []
            for chan in self.subscription:
                if self.is_authenticated_channel(self.exchange_channel_to_std(chan)):
                    channels.append(chan)
            if channels:
                await connection.write(json.dumps({"op": "subscribe", "args": channels}))
                LOG.debug(f'{connection.uuid}: Subscribing to auth, quote: {quote}, channels: {channels}')

        if quote == 'USDTP':
            return

        self.__reset(quote=quote)

        for chan in self.subscription:
            if not self.is_authenticated_channel(self.exchange_channel_to_std(chan)):
                for pair in self.subscription[chan]:
                    # Bybit uses separate addresses for difference quote currencies
                    if 'USDT' not in pair and quote == 'USDT':
                        continue
                    if 'USDT' in pair and quote == 'USD':
                        continue

                    await connection.write(json.dumps(
                        {
                            "op": "subscribe",
                            "args": [f"{chan}.{pair}"] if self.exchange_channel_to_std(chan) != CANDLES else [f"{chan if quote == 'USD' else 'candle'}.{self.candle_mapping[self.candle_interval]}.{pair}"]
                        }
                    ))
                    LOG.debug(f'{connection.uuid}: Subscribing to public, quote: {quote}, {chan}.{pair}')

    async def _instrument_info(self, msg: dict, timestamp: float):
        """
        ### Snapshot type update
        {
        "topic": "instrument_info.100ms.BTCUSD",
        "type": "snapshot",
        "data": {
            "id": 1,
            "symbol": "BTCUSD",                           //instrument name
            "last_price_e4": 81165000,                    //the latest price
            "last_tick_direction": "ZeroPlusTick",        //the direction of last tick:PlusTick,ZeroPlusTick,MinusTick,
                                                          //ZeroMinusTick
            "prev_price_24h_e4": 81585000,                //the price of prev 24h
            "price_24h_pcnt_e6": -5148,                   //the current last price percentage change from prev 24h price
            "high_price_24h_e4": 82900000,                //the highest price of prev 24h
            "low_price_24h_e4": 79655000,                 //the lowest price of prev 24h
            "prev_price_1h_e4": 81395000,                 //the price of prev 1h
            "price_1h_pcnt_e6": -2825,                    //the current last price percentage change from prev 1h price
            "mark_price_e4": 81178500,                    //mark price
            "index_price_e4": 81172800,                   //index price
            "open_interest": 154418471,                   //open interest quantity - Attention, the update is not
                                                          //immediate - slowest update is 1 minute
            "open_value_e8": 1997561103030,               //open value quantity - Attention, the update is not
                                                          //immediate - the slowest update is 1 minute
            "total_turnover_e8": 2029370141961401,        //total turnover
            "turnover_24h_e8": 9072939873591,             //24h turnover
            "total_volume": 175654418740,                 //total volume
            "volume_24h": 735865248,                      //24h volume
            "funding_rate_e6": 100,                       //funding rate
            "predicted_funding_rate_e6": 100,             //predicted funding rate
            "cross_seq": 1053192577,                      //sequence
            "created_at": "2018-11-14T16:33:26Z",
            "updated_at": "2020-01-12T18:25:16Z",
            "next_funding_time": "2020-01-13T00:00:00Z",  //next funding time
                                                          //the rest time to settle funding fee
            "countdown_hour": 6                           //the remaining time to settle the funding fee
        },
        "cross_seq": 1053192634,
        "timestamp_e6": 1578853524091081                  //the timestamp when this information was produced
        }

        ### Delta type update
        {
        "topic": "instrument_info.100ms.BTCUSD",
        "type": "delta",
        "data": {
            "delete": [],
            "update": [
                {
                    "id": 1,
                    "symbol": "BTCUSD",
                    "prev_price_24h_e4": 81565000,
                    "price_24h_pcnt_e6": -4904,
                    "open_value_e8": 2000479681106,
                    "total_turnover_e8": 2029370495672976,
                    "turnover_24h_e8": 9066215468687,
                    "volume_24h": 735316391,
                    "cross_seq": 1053192657,
                    "created_at": "2018-11-14T16:33:26Z",
                    "updated_at": "2020-01-12T18:25:25Z"
                }
            ],
            "insert": []
        },
        "cross_seq": 1053192657,
        "timestamp_e6": 1578853525691123
        }
        """
        update_type = msg['type']

        if update_type == 'snapshot':
            updates = [msg['data']]
        else:
            updates = msg['data']['update']

        for info in updates:
            if msg['topic'] in self._instrument_info_cache and self._instrument_info_cache[msg['topic']] == updates:
                continue
            else:
                self._instrument_info_cache[msg['topic']] = updates

            if 'updated_at_e9' in info:
                ts = info['updated_at_e9'] / 1e9
            elif 'updated_at' in info:
                ts = self.timestamp_normalize(info['updated_at'])
            else:
                continue

            if 'open_interest' in info:
                oi = OpenInterest(
                    self.id,
                    self.exchange_symbol_to_std_symbol(info['symbol']),
                    Decimal(info['open_interest']),
                    ts,
                    raw=info
                )
                await self.callback(OPEN_INTEREST, oi, timestamp)

            if 'index_price_e4' in info:
                i = Index(
                    self.id,
                    self.exchange_symbol_to_std_symbol(info['symbol']),
                    Decimal(info['index_price_e4']) * Decimal('1e-4'),
                    ts,
                    raw=info
                )
                await self.callback(INDEX, i, timestamp)

            if 'funding_rate_e6' in info:
                f = Funding(
                    self.id,
                    self.exchange_symbol_to_std_symbol(info['symbol']),
                    None,
                    Decimal(info['funding_rate_e6']) * Decimal('1e-6'),
                    info['next_funding_time'].timestamp(),
                    ts,
                    predicted_rate=Decimal(info['predicted_funding_rate_e6']) * Decimal('1e-6'),
                    raw=info
                )
                await self.callback(FUNDING, f, timestamp)

    async def _trade(self, msg: dict, timestamp: float):
        """
        {"topic":"trade.BTCUSD",
        "data":[
            {
                "timestamp":"2019-01-22T15:04:33.461Z",
                "symbol":"BTCUSD",
                "side":"Buy",
                "size":980,
                "price":3563.5,
                "tick_direction":"PlusTick",
                "trade_id":"9d229f26-09a8-42f8-aff3-0ba047b0449d",
                "cross_seq":163261271}]}
        """
        data = msg['data']
        for trade in data:
            if isinstance(trade['trade_time_ms'], str):
                ts = int(trade['trade_time_ms'])
            else:
                ts = trade['trade_time_ms']

            t = Trade(
                self.id,
                self.exchange_symbol_to_std_symbol(trade['symbol']),
                BUY if trade['side'] == 'Buy' else SELL,
                Decimal(trade['size']),
                Decimal(trade['price']),
                self.timestamp_normalize(ts),
                id=trade['trade_id'],
                raw=trade
            )
            await self.callback(TRADES, t, timestamp)

    async def _book(self, msg: dict, timestamp: float):
        pair = self.exchange_symbol_to_std_symbol(msg['topic'].split('.')[-1])
        update_type = msg['type']
        data = msg['data']
        delta = {BID: [], ASK: []}

        if update_type == 'snapshot':
            delta = None
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth)
            # the USDT perpetual data is under the order_book key
            if 'order_book' in data:
                data = data['order_book']

            for update in data:
                side = BID if update['side'] == 'Buy' else ASK
                self._l2_book[pair].book[side][Decimal(update['price'])] = Decimal(update['size'])
        else:
            for delete in data['delete']:
                side = BID if delete['side'] == 'Buy' else ASK
                price = Decimal(delete['price'])
                delta[side].append((price, 0))
                del self._l2_book[pair].book[side][price]

            for utype in ('update', 'insert'):
                for update in data[utype]:
                    side = BID if update['side'] == 'Buy' else ASK
                    price = Decimal(update['price'])
                    amount = Decimal(update['size'])
                    delta[side].append((price, amount))
                    self._l2_book[pair].book[side][price] = amount

        # timestamp is in microseconds
        ts = msg['timestamp_e6']
        if isinstance(ts, str):
            ts = int(ts)
        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=ts / 1000000, raw=msg, delta=delta)

    async def _order(self, msg: dict, timestamp: float):
        """
        {
            "topic": "order",
            "action": "",
            "data": [
                {
                    "order_id": "xxxxxxxx-xxxx-xxxx-9a8f-4a973eb5c418",
                    "order_link_id": "",
                    "symbol": "BTCUSDT",
                    "side": "Buy",
                    "order_type": "Limit",
                    "price": 11000,
                    "qty": 0.001,
                    "leaves_qty": 0.001,
                    "last_exec_price": 0,
                    "cum_exec_qty": 0,
                    "cum_exec_value": 0,
                    "cum_exec_fee": 0,
                    "time_in_force": "GoodTillCancel",
                    "create_type": "CreateByUser",
                    "cancel_type": "UNKNOWN",
                    "order_status": "New",
                    "take_profit": 0,
                    "stop_loss": 0,
                    "trailing_stop": 0,
                    "reduce_only": false,
                    "close_on_trigger": false,
                    "create_time": "2020-08-12T21:18:40.780039678Z",
                    "update_time": "2020-08-12T21:18:40.787986415Z"
                }
            ]
        }
        """
        order_status = {
            'Created': SUBMITTING,
            'Rejected': FAILED,
            'New': OPEN,
            'PartiallyFilled': PARTIAL,
            'Filled': FILLED,
            'Cancelled': CANCELLED,
            'PendingCancel': CANCELLING
        }

        for i in range(len(msg['data'])):
            data = msg['data'][i]

            oi = OrderInfo(
                self.id,
                self.exchange_symbol_to_std_symbol(data['symbol']),
                data["order_id"],
                BUY if msg["side"] == 'Buy' else SELL,
                order_status[data["order_status"]],
                LIMIT if data['order_type'] == 'Limit' else MARKET,
                Decimal(data['price']),
                Decimal(data['cumQuantity']),
                Decimal(data['qty']) - Decimal(data['cumQuantity']),
                self.timestamp_normalize(data["updateTime"]),
                raw=data
            )
            await self.callback(ORDER_INFO, oi, timestamp)

    async def _execution(self, msg: dict, timestamp: float):
        '''
        {
            "topic": "execution",
            "data": [
                {
                    "symbol": "BTCUSD",
                    "side": "Buy",
                    "order_id": "xxxxxxxx-xxxx-xxxx-9a8f-4a973eb5c418",
                    "exec_id": "xxxxxxxx-xxxx-xxxx-8b66-c3d2fcd352f6",
                    "order_link_id": "",
                    "price": "8300",
                    "order_qty": 1,
                    "exec_type": "Trade",
                    "exec_qty": 1,
                    "exec_fee": "0.00000009",
                    "leaves_qty": 0,
                    "is_maker": false,
                    "trade_time": "2020-01-14T14:07:23.629Z" // trade time
                }
            ]
        }
        '''
        for entry in msg['data']:
            symbol = self.exchange_symbol_to_std_symbol(entry['symbol'])
            f = Fill(
                self.id,
                symbol,
                BUY if entry['side'] == 'Buy' else SELL,
                Decimal(entry['exec_qty']),
                Decimal(entry['price']),
                Decimal(entry['exec_fee']),
                entry['exec_id'],
                entry['order_id'],
                None,
                MAKER if entry['is_maker'] else TAKER,
                entry['trade_time'].timestamp(),
                raw=entry
            )
            await self.callback(FILLS, f, timestamp)

    # async def _balances(self, msg: dict, timestamp: float):
    #    for i in range(len(msg['data'])):
    #        data = msg['data'][i]
    #        symbol = self.exchange_symbol_to_std_symbol(data['symbol'])
    #        await self.callback(BALANCES, feed=self.id, symbol=symbol, data=data, receipt_timestamp=timestamp)

    async def authenticate(self, conn: AsyncConnection):
        if any(self.is_authenticated_channel(self.exchange_channel_to_std(chan)) for chan in self.subscription):
            auth = self._auth(self.key_id, self.key_secret)
            LOG.debug(f"{conn.uuid}: Sending authentication request with message {auth}")
            await conn.write(auth)

    def _auth(self, key_id: str, key_secret: str) -> str:
        # https://bybit-exchange.github.io/docs/inverse/#t-websocketauthentication

        expires = int((time.time() + 60)) * 1000
        signature = str(hmac.new(bytes(key_secret, 'utf-8'), bytes(f'GET/realtime{expires}', 'utf-8'), digestmod='sha256').hexdigest())
        return json.dumps({'op': 'auth', 'args': [key_id, expires, signature]})

    async def __no_auth(self, conn: AsyncConnection):
        pass
