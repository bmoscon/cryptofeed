'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''

import asyncio
from collections import defaultdict
import logging
from decimal import Decimal
import hmac
import os
from time import time
import zlib
from typing import Dict, Iterable, Tuple

import aiohttp
from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, ORDER_INFO, USER_FILLS
from cryptofeed.defines import FTX as FTX_id
from cryptofeed.defines import FUNDING, L2_BOOK, LIQUIDATIONS, OPEN_INTEREST, SELL, TICKER, TRADES, FILLED
from cryptofeed.exceptions import BadChecksum
from cryptofeed.feed import Feed
from cryptofeed.standards import is_authenticated_channel, normalize_channel, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class FTX(Feed):
    id = FTX_id
    symbol_endpoint = "https://ftx.com/api/markets"

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for d in data['result']:
            normalized = d['name'].replace("/", symbol_separator)
            symbol = d['name']
            ret[normalized] = symbol
            info['tick_size'][normalized] = d['priceIncrement']
            info['quantity_step'][normalized] = d['sizeIncrement']
        return ret, info

    def __init__(self, subaccount=None, **kwargs):
        self.subaccount = subaccount
        super().__init__('wss://ftexchange.com/ws/', **kwargs)

    def load_keys(self):
        self.key_id = os.environ.get(f'CF_{self.id}_KEY_ID') or (self.config[self.id.lower()][self.subaccount].key_id if self.subaccount else self.config[self.id.lower()].key_id)
        self.key_secret = os.environ.get(f'CF_{self.id}_KEY_SECRET') or (self.config[self.id.lower()][self.subaccount].key_secret if self.subaccount else self.config[self.id.lower()].key_secret)

    def __reset(self):
        self.l2_book = {}
        self.funding = {}
        self.open_interest = {}

    async def generate_token(self, conn: AsyncConnection):
        ts = int(time() * 1000)
        msg = {
            'op': 'login',
            'args':
            {
                'key': self.key_id,
                'sign': hmac.new(self.key_secret.encode(), f'{ts}websocket_login'.encode(), 'sha256').hexdigest(),
                'time': ts,
            }
        }
        if self.subaccount:
            msg['args']['subaccount'] = self.subaccount
        await conn.write(json.dumps(msg))

    async def authenticate(self, conn: AsyncConnection):
        if self.requires_authentication:
            await self.generate_token(conn)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        for chan in self.subscription:
            symbols = self.subscription[chan]
            if chan == FUNDING:
                asyncio.create_task(self._funding(symbols))  # TODO: use HTTPAsyncConn
                continue
            if chan == OPEN_INTEREST:
                asyncio.create_task(self._open_interest(symbols))  # TODO: use HTTPAsyncConn
                continue
            if is_authenticated_channel(normalize_channel(self.id, chan)):
                await conn.write(json.dumps(
                    {
                        "channel": chan,
                        "op": "subscribe"
                    }
                ))
                continue
            for pair in symbols:
                await conn.write(json.dumps(
                    {
                        "channel": chan,
                        "market": pair,
                        "op": "subscribe"
                    }
                ))

    def __calc_checksum(self, pair):
        bid_it = reversed(self.l2_book[pair][BID])
        ask_it = iter(self.l2_book[pair][ASK])

        bids = [f"{bid}:{self.l2_book[pair][BID][bid]}" for bid in bid_it]
        asks = [f"{ask}:{self.l2_book[pair][ASK][ask]}" for ask in ask_it]

        if len(bids) == len(asks):
            combined = [val for pair in zip(bids, asks) for val in pair]
        elif len(bids) > len(asks):
            combined = [val for pair in zip(bids[:len(asks)], asks) for val in pair]
            combined += bids[len(asks):]
        else:
            combined = [val for pair in zip(bids, asks[:len(bids)]) for val in pair]
            combined += asks[len(bids):]

        computed = ":".join(combined).encode()
        return zlib.crc32(computed)

    async def _open_interest(self, pairs: Iterable):
        """
            {
              "success": true,
              "result": {
                "volume": 1000.23,
                "nextFundingRate": 0.00025,
                "nextFundingTime": "2019-03-29T03:00:00+00:00",
                "expirationPrice": 3992.1,
                "predictedExpirationPrice": 3993.6,
                "strikePrice": 8182.35,
                "openInterest": 21124.583
              }
            }
        """

        rate_limiter = 1  # don't fetch too many pairs too fast
        async with aiohttp.ClientSession() as session:
            while True:
                for pair in pairs:
                    # OI only for perp and futures, so check for / in pair name indicating spot
                    if '/' in pair:
                        continue
                    end_point = f"https://ftx.com/api/futures/{pair}/stats"
                    async with session.get(end_point) as response:
                        data = await response.text()
                        data = json.loads(data, parse_float=Decimal)
                        if 'result' in data:
                            oi = data['result']['openInterest']
                            if oi != self.open_interest.get(pair, None):
                                await self.callback(OPEN_INTEREST,
                                                    feed=self.id,
                                                    symbol=pair,
                                                    open_interest=oi,
                                                    timestamp=time(),
                                                    receipt_timestamp=time()
                                                    )
                                self.open_interest[pair] = oi
                                await asyncio.sleep(rate_limiter)
                wait_time = 60
                await asyncio.sleep(wait_time)

    async def _funding(self, pairs: Iterable):
        """
            {
              "success": true,
              "result": [
                {
                  "future": "BTC-PERP",
                  "rate": 0.0025,
                  "time": "2019-06-02T08:00:00+00:00"
                }
              ]
            }
        """
        # do not send more than 30 requests per second: doing so will result in HTTP 429 errors
        rate_limiter = 0.1
        # funding rates do not change frequently
        wait_time = 60
        async with aiohttp.ClientSession() as session:
            while True:
                for pair in pairs:
                    if '-PERP' not in pair:
                        continue
                    async with session.get(f"https://ftx.com/api/funding_rates?future={pair}") as response:
                        data = await response.text()
                        data = json.loads(data, parse_float=Decimal)

                        last_update = self.funding.get(pair, None)
                        update = str(data['result'][0]['rate']) + str(data['result'][0]['time'])
                        if last_update and last_update == update:
                            continue
                        else:
                            self.funding[pair] = update

                        await self.callback(FUNDING, feed=self.id,
                                            symbol=self.exchange_symbol_to_std_symbol(data['result'][0]['future']),
                                            rate=data['result'][0]['rate'],
                                            timestamp=timestamp_normalize(self.id, data['result'][0]['time']),
                                            receipt_timestamp=time()
                                            )
                    await asyncio.sleep(rate_limiter)
                await asyncio.sleep(wait_time)

    async def _trade(self, msg: dict, timestamp: float):
        """
        example message:

        {"channel": "trades", "market": "BTC-PERP", "type": "update", "data": [{"id": null, "price": 10738.75,
        "size": 0.3616, "side": "buy", "liquidation": false, "time": "2019-08-03T12:20:19.170586+00:00"}]}
        """
        for trade in msg['data']:
            await self.callback(TRADES, feed=self.id,
                                symbol=self.exchange_symbol_to_std_symbol(msg['market']),
                                side=BUY if trade['side'] == 'buy' else SELL,
                                amount=Decimal(trade['size']),
                                price=Decimal(trade['price']),
                                order_id=trade['id'],
                                timestamp=float(timestamp_normalize(self.id, trade['time'])),
                                receipt_timestamp=timestamp)
            if bool(trade['liquidation']):
                await self.callback(LIQUIDATIONS,
                                    feed=self.id,
                                    symbol=self.exchange_symbol_to_std_symbol(msg['market']),
                                    side=BUY if trade['side'] == 'buy' else SELL,
                                    leaves_qty=Decimal(trade['size']),
                                    price=Decimal(trade['price']),
                                    order_id=trade['id'],
                                    status=FILLED,
                                    timestamp=float(timestamp_normalize(self.id, trade['time'])),
                                    receipt_timestamp=timestamp)

    async def _ticker(self, msg: dict, timestamp: float):
        """
        example message:

        {"channel": "ticker", "market": "BTC/USD", "type": "update", "data": {"bid": 10717.5, "ask": 10719.0,
        "last": 10719.0, "time": 1564834587.1299787}}
        """
        await self.callback(TICKER, feed=self.id,
                            symbol=self.exchange_symbol_to_std_symbol(msg['market']),
                            bid=Decimal(msg['data']['bid'] if msg['data']['bid'] else 0.0),
                            ask=Decimal(msg['data']['ask'] if msg['data']['ask'] else 0.0),
                            timestamp=float(msg['data']['time']),
                            receipt_timestamp=timestamp)

    async def _book(self, msg: dict, timestamp: float):
        """
        example messages:

        snapshot:
        {"channel": "orderbook", "market": "BTC/USD", "type": "partial", "data": {"time": 1564834586.3382702,
        "checksum": 427503966, "bids": [[10717.5, 4.092], ...], "asks": [[10720.5, 15.3458], ...], "action": "partial"}}

        update:
        {"channel": "orderbook", "market": "BTC/USD", "type": "update", "data": {"time": 1564834587.1299787,
        "checksum": 3115602423, "bids": [], "asks": [[10719.0, 14.7461]], "action": "update"}}
        """
        check = msg['data']['checksum']
        if msg['type'] == 'partial':
            # snapshot
            pair = self.exchange_symbol_to_std_symbol(msg['market'])
            self.l2_book[pair] = {
                BID: sd({
                    Decimal(price): Decimal(amount) for price, amount in msg['data']['bids']
                }),
                ASK: sd({
                    Decimal(price): Decimal(amount) for price, amount in msg['data']['asks']
                })
            }
            if self.checksum_validation and self.__calc_checksum(pair) != check:
                raise BadChecksum
            await self.book_callback(self.l2_book[pair], L2_BOOK, pair, True, None, float(msg['data']['time']), timestamp)
        else:
            # update
            delta = {BID: [], ASK: []}
            pair = self.exchange_symbol_to_std_symbol(msg['market'])
            for side in ('bids', 'asks'):
                s = BID if side == 'bids' else ASK
                for price, amount in msg['data'][side]:
                    price = Decimal(price)
                    amount = Decimal(amount)
                    if amount == 0:
                        delta[s].append((price, 0))
                        del self.l2_book[pair][s][price]
                    else:
                        delta[s].append((price, amount))
                        self.l2_book[pair][s][price] = amount
            if self.checksum_validation and self.__calc_checksum(pair) != check:
                raise BadChecksum
            await self.book_callback(self.l2_book[pair], L2_BOOK, pair, False, delta, float(msg['data']['time']), timestamp)

    async def _fill(self, msg: dict, timestamp: float):
        """
        example message:
        {
            "channel": "fills",
            "data": {
                "fee": 78.05799225,
                "feeRate": 0.0014,
                "future": "BTC-PERP",
                "id": 7828307,
                "liquidity": "taker",
                "market": "BTC-PERP",
                "orderId": 38065410,
                "tradeId": 19129310,
                "price": 3723.75,
                "side": "buy",
                "size": 14.973,
                "time": "2019-05-07T16:40:58.358438+00:00",
                "type": "order"
            },
            "type": "update"
        }
        """
        fill = msg['data']
        await self.callback(USER_FILLS, feed=self.id,
                            symbol=self.exchange_symbol_to_std_symbol(fill['market']),
                            side=BUY if fill['side'] == 'buy' else SELL,
                            amount=Decimal(fill['size']),
                            price=Decimal(fill['price']),
                            liquidity=fill['liquidity'],
                            order_id=fill['id'],
                            trade_id=fill['tradeId'],
                            timestamp=float(timestamp_normalize(self.id, fill['time'])),
                            receipt_timestamp=timestamp)

    async def _order(self, msg: dict, timestamp: float):
        """
        example message:
        {
            "channel": "orders",
            "data": {
                "id": 24852229,
                "clientId": null,
                "market": "XRP-PERP",
                "type": "limit",
                "side": "buy",
                "size": 42353.0,
                "price": 0.2977,
                "reduceOnly": false,
                "ioc": false,
                "postOnly": false,
                "status": "closed",
                "filledSize": 0.0,
                "remainingSize": 0.0,
                "avgFillPrice": 0.2978
            },
            "type": "update"
        }
        """
        order = msg['data']
        await self.callback(ORDER_INFO, feed=self.id,
                            symbol=self.exchange_symbol_to_std_symbol(order['market']),
                            status=order['status'],
                            order_id=order['id'],
                            side=BUY if order['side'].lower() == 'buy' else SELL,
                            order_type=order['type'],
                            avg_fill_price=Decimal(order['avgFillPrice']) if order['avgFillPrice'] else None,
                            filled_size=Decimal(order['filledSize']),
                            remaining_size=Decimal(order['remainingSize']),
                            amount=Decimal(order['size']),
                            timestamp=timestamp,
                            receipt_timestamp=timestamp,
                            )

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)
        if 'type' in msg:
            if msg['type'] == 'subscribed':
                if 'market' in msg:
                    LOG.info('%s: Subscribed to %s channel for %s', self.id, msg['channel'], msg['market'])
                else:
                    LOG.info('%s: Subscribed to %s channel', self.id, msg['channel'])
            elif msg['type'] == 'error':
                LOG.error('%s: Received error message %s', self.id, msg)
                raise Exception('Error from %s: %s', self.id, msg)
            elif 'channel' in msg:
                if msg['channel'] == 'orderbook':
                    await self._book(msg, timestamp)
                elif msg['channel'] == 'trades':
                    await self._trade(msg, timestamp)
                elif msg['channel'] == 'ticker':
                    await self._ticker(msg, timestamp)
                elif msg['channel'] == 'fills':
                    await self._fill(msg, timestamp)
                elif msg['channel'] == 'orders':
                    await self._order(msg, timestamp)
                else:
                    LOG.warning("%s: Invalid message type %s", self.id, msg)
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)
