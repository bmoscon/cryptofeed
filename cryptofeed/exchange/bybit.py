'''
Copyright (C) 2018-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
import logging
from decimal import Decimal
from functools import partial
from typing import Dict, List, Callable, Tuple

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection, WSAsyncConn
from cryptofeed.defines import BID, ASK, BUY, BYBIT, L2_BOOK, SELL, TRADES, OPEN_INTEREST, FUTURES_INDEX, ORDER_INFO, USER_FILLS, FUTURES, PERPETUAL
from cryptofeed.feed import Feed
from cryptofeed.standards import timestamp_normalize, is_authenticated_channel, normalize_channel

# For auth
import hmac
import time

LOG = logging.getLogger('feedhandler')


class Bybit(Feed):
    id = BYBIT
    symbol_endpoint = 'https://api.bybit.com/v2/public/symbols'

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        '''
            Bybit uses two notation fields for instruments: 'name' and 'alias'.
            On the Bybit's web trading application futures are shown as 'alias' name.
            Notation 'BTCUSDZ21' in 'name' field assumes only mounthly futures.
            For compatibility with other exchange's notations, where daily futures are trade,
            it is better to use 'alias' for FUTURES, which looks like 'BTCUSD1231' 
            and normilazed as 'BTC-USD-1231' instead of 'BTC-USD-Z21' 
        '''
        ret = {}
        info = defaultdict(dict)
        for symbol in data['result']:
            quote = symbol['quote_currency']
            if not symbol['name'].endswith(quote):
                base, contract = symbol['alias'].split(quote)
                normalized = f"{base}{symbol_separator}{quote}-{contract}"
                info['instrument_type'][normalized] = FUTURES
            else:
                normalized = f"{symbol['base_currency']}{symbol_separator}{quote}"
                info['instrument_type'][normalized] = PERPETUAL
            ret[normalized] = symbol['name']
            info['tick_size'][normalized] = symbol['price_filter']['tick_size']
        return ret, info

    def __init__(self, **kwargs):
        super().__init__({'USD': 'wss://stream.bybit.com/realtime', 'USDT': 'wss://stream.bybit.com/realtime_public', 'USDT_PRIV': 'wss://stream.bybit.com/realtime_private'}, **kwargs)

    def __reset(self, quote=None):
        if quote is None:
            self.l2_book = {}
        else:
            rem = [symbol for symbol in self.l2_book if quote in symbol]
            for symbol in rem:
                del self.l2_book[symbol]


    async def message_handler(self, msg: str, conn, timestamp: float):

        msg = json.loads(msg, parse_float=Decimal)

        if "success" in msg:
            if msg['success']:
                if msg['request']['op'] == 'auth':
                    LOG.info("%s: Authenticated successful", conn.uuid)
                    channels = []
                    for chan in self.subscription:
                        if is_authenticated_channel(normalize_channel(self.id, chan)):
                            channels.append(chan)
                    if channels:
                        await conn.write(json.dumps({"op": "subscribe", "args": channels}))
                        LOG.info(f'{conn.uuid}: Subscribe to auth channels request sent: {channels}')

                elif msg['request']['op'] == 'subscribe':
                    LOG.info("%s: Subscribed to channels: %s", conn.uuid, msg['request']['args'])
                else:
                    LOG.warning("%s: Unhandled 'successs' message received", conn.uuid)
            else:
                LOG.error("%s: Error from exchange %s", conn.uuid, msg)
        elif "trade" in msg["topic"]:
            await self._trade(msg, timestamp)
        elif "orderBookL2" in msg["topic"]:
            await self._book(msg, timestamp)
        elif "instrument_info" in msg["topic"]:
            await self._instrument_info(msg, timestamp)
        elif "order" in msg["topic"]:
            await self._order(msg, timestamp)
        elif "execution" in msg["topic"]:
            await self._execution(msg, timestamp)
        else:
            LOG.warning("%s: Unhandled message type %s", conn.uuid, msg)


    def connect(self) -> List[Tuple[AsyncConnection, Callable[[None], None], Callable[[str, float], None]]]:
        ret = []

        if any(pair[-4:] == 'USDT' for pair in self.normalized_symbols):
            subscribe = partial(self.subscribe, quote='USDT')
            ret.append((WSAsyncConn(self.address['USDT'], self.id, **self.ws_defaults), subscribe, self.message_handler, self.__no_auth))
        if any((pair[-3:] == 'USD' or pair[-2:].isdigit()) for pair in self.normalized_symbols):
            subscribe = partial(self.subscribe, quote='USD')
            ret.append((WSAsyncConn(self.address['USD'], self.id, **self.ws_defaults), subscribe, self.message_handler, self.authenticate))

        return ret


    async def subscribe(self, connection: AsyncConnection, quote: str = None):
        self.__reset(quote=quote)

        for chan in self.subscription:
            if not is_authenticated_channel(normalize_channel(self.id, chan)):
                for pair in self.subscription[chan]:
                    # Bybit uses separate addresses for difference quote currencies
                    if 'USDT' not in pair and quote == 'USDT':
                        continue
                    if 'USDT' in pair and quote == 'USD':
                        continue

                    await connection.write(json.dumps(
                        {
                            "op": "subscribe",
                            "args": [f"{chan}.{pair}"]
                        }
                    ))


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
            if 'updated_at_e9' in info:
                ts = info['updated_at_e9'] / 1e9
            elif 'updated_at' in info:
                ts = timestamp_normalize(self.id, info['updated_at'])
            else:
                continue

            if 'open_interest' in info:
                await self.callback(OPEN_INTEREST, feed=self.id,
                                    symbol=self.exchange_symbol_to_std_symbol(info['symbol']),
                                    open_interest=Decimal(info['open_interest']),
                                    timestamp=ts,
                                    receipt_timestamp=timestamp)

            if 'index_price_e4' in info:
                await self.callback(FUTURES_INDEX, feed=self.id,
                                    symbol=self.exchange_symbol_to_std_symbol(info['symbol']),
                                    futures_index=Decimal(info['index_price_e4']) * Decimal(1e-4),
                                    timestamp=ts,
                                    receipt_timestamp=timestamp)

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

            await self.callback(TRADES,
                                feed=self.id,
                                symbol=self.exchange_symbol_to_std_symbol(trade['symbol']),
                                order_id=trade['trade_id'],
                                side=BUY if trade['side'] == 'Buy' else SELL,
                                amount=Decimal(trade['size']),
                                price=Decimal(trade['price']),
                                timestamp=timestamp_normalize(self.id, ts),
                                receipt_timestamp=timestamp
                                )

    async def _book(self, msg: dict, timestamp: float):
        pair = self.exchange_symbol_to_std_symbol(msg['topic'].split('.')[1])
        update_type = msg['type']
        data = msg['data']
        forced = False
        delta = {BID: [], ASK: []}

        if update_type == 'snapshot':
            self.l2_book[pair] = {BID: sd({}), ASK: sd({})}
            # the USDT perpetual data is under the order_book key
            if 'order_book' in data:
                data = data['order_book']

            for update in data:
                side = BID if update['side'] == 'Buy' else ASK
                self.l2_book[pair][side][Decimal(update['price'])] = Decimal(update['size'])
            forced = True
        else:
            for delete in data['delete']:
                side = BID if delete['side'] == 'Buy' else ASK
                price = Decimal(delete['price'])
                delta[side].append((price, 0))
                del self.l2_book[pair][side][price]

            for utype in ('update', 'insert'):
                for update in data[utype]:
                    side = BID if update['side'] == 'Buy' else ASK
                    price = Decimal(update['price'])
                    amount = Decimal(update['size'])
                    delta[side].append((price, amount))
                    self.l2_book[pair][side][price] = amount

        # timestamp is in microseconds
        ts = msg['timestamp_e6']
        if isinstance(ts, str):
            ts = int(ts)
        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, delta, ts / 1000000, timestamp)


    async def _order(self, msg: dict, timestamp: float):
        for i in range(len(msg['data'])):
            data = msg['data'][i]
            symbol = self.exchange_symbol_to_std_symbol(data['symbol'])
            await self.callback(ORDER_INFO, feed=self.id, symbol=symbol, data=data, receipt_timestamp=timestamp)


    async def _execution(self, msg: dict, timestamp: float):
        for i in range(len(msg['data'])):
            data = msg['data'][i]
            symbol = self.exchange_symbol_to_std_symbol(data['symbol'])
            await self.callback(USER_FILLS, feed=self.id, symbol=symbol, data=data, receipt_timestamp=timestamp)


    async def authenticate(self, conn: AsyncConnection):
        if any(is_authenticated_channel(normalize_channel(self.id, chan)) for chan in self.subscription):
            # https://bybit-exchange.github.io/docs/inverse/#t-websocketauthentication

            expires = int((time.time() + 60)) * 1000
            signature = str(hmac.new(bytes(self.key_secret, 'utf-8'), bytes(f'GET/realtime{expires}', 'utf-8'), digestmod='sha256').hexdigest())
            await conn.write(json.dumps({'op': 'auth','args': [self.key_id, expires, signature]}))
            LOG.info(f"{conn.uuid}: Authentication request sent")
            
    async def __no_auth(self, conn: AsyncConnection):
        pass
