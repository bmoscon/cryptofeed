'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio

from decimal import Decimal
from itertools import islice
from functools import partial
import logging
import zlib
from typing import List, Tuple, Callable

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.auth.okcoin import generate_token
from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import ASK, BID, BUY, FUNDING, L2_BOOK, OKCOIN, OPEN_INTEREST, SELL, TICKER, TRADES, LIQUIDATIONS, ORDER_INFO
from cryptofeed.exceptions import BadChecksum
from cryptofeed.feed import Feed
from cryptofeed.standards import symbol_exchange_to_std, timestamp_normalize, is_authenticated_channel
from cryptofeed.symbols import get_symbol_separator
from cryptofeed.util import split


LOG = logging.getLogger('feedhandler')


class OKCoin(Feed):
    id = OKCOIN

    def __init__(self, **kwargs):
        super().__init__('wss://real.okcoin.com:8443/ws/v3', **kwargs)
        self.open_interest = {}

    def __reset(self):
        self.l2_book = {}
        self.open_interest = {}

    def __calc_checksum(self, pair):
        bid_it = reversed(self.l2_book[pair][BID])
        ask_it = iter(self.l2_book[pair][ASK])

        bids = (f"{bid}:{self.l2_book[pair][BID][bid]}" for bid in bid_it)
        bids = list(islice(bids, 25))
        asks = (f"{ask}:{self.l2_book[pair][ASK][ask]}" for ask in ask_it)
        asks = list(islice(asks, 25))

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

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()

        symbol_channels = list(self.get_channel_symbol_combinations())
        LOG.info("%s: Got %r combinations of pairs and channels", self.id, len(symbol_channels))

        if len(symbol_channels) == 0:
            LOG.info("%s: No websocket subscription", self.id)
            return False

        # Avoid error "Max frame length of 65536 has been exceeded" by limiting requests to some args
        for chunk in split.list_by_max_items(symbol_channels, 33):
            LOG.info("%s: Subscribe to %s args from %r to %r", self.id, len(chunk), chunk[0], chunk[-1])
            request = {"op": "subscribe", "args": chunk}
            await conn.send(json.dumps(request))

    @staticmethod
    def instrument_type(pair):
        dash_count = pair.count(get_symbol_separator())
        if dash_count == 1:  # BTC-USDT
            return 'spot'
        if dash_count == 4:  # BTC-USD-201225-35000-P
            return 'option'
        if pair[-4:] == "SWAP":  # BTC-USDT-SWAP
            return 'swap'
        return 'futures'  # BTC-USDT-201225

    def get_channel_symbol_combinations(self):
        for chan in set(self.channels or self.subscription):
            if not is_authenticated_channel(chan):
                if chan == LIQUIDATIONS:
                    continue
                for symbol in set(self.symbols or self.subscription[chan]):
                    instrument_type = self.instrument_type(symbol)
                    if instrument_type != 'swap' and 'funding' in chan:
                        continue  # No funding for spot, futures and options
                    yield f"{chan.format(instrument_type)}:{symbol}"

    async def _ticker(self, msg: dict, timestamp: float):
        """
        {'table': 'spot/ticker', 'data': [{'instrument_id': 'BTC-USD', 'last': '3977.74', 'best_bid': '3977.08', 'best_ask': '3978.73', 'open_24h': '3978.21', 'high_24h': '3995.43', 'low_24h': '3961.02', 'base_volume_24h': '248.245', 'quote_volume_24h': '988112.225861', 'timestamp': '2019-03-22T22:26:34.019Z'}]}
        """
        for update in msg['data']:
            pair = update['instrument_id']
            update_timestamp = timestamp_normalize(self.id, update['timestamp'])
            await self.callback(TICKER, feed=self.id,
                                symbol=pair,
                                bid=Decimal(update['best_bid']),
                                ask=Decimal(update['best_ask']),
                                timestamp=update_timestamp,
                                receipt_timestamp=timestamp)
            if 'open_interest' in update:
                oi = update['open_interest']
                if pair in self.open_interest and oi == self.open_interest[pair]:
                    continue
                self.open_interest[pair] = oi
                await self.callback(OPEN_INTEREST, feed=self.id, symbol=pair, open_interest=oi, timestamp=update_timestamp, receipt_timestamp=timestamp)

    async def _trade(self, msg: dict, timestamp: float):
        """
        {'table': 'spot/trade', 'data': [{'instrument_id': 'BTC-USD', 'price': '3977.44', 'side': 'buy', 'size': '0.0096', 'timestamp': '2019-03-22T22:45:44.578Z', 'trade_id': '486519521'}]}
        """
        for trade in msg['data']:
            if msg['table'] == 'futures/trade':
                amount_sym = 'qty'
            else:
                amount_sym = 'size'
            await self.callback(TRADES,
                                feed=self.id,
                                symbol=symbol_exchange_to_std(trade['instrument_id']),
                                order_id=trade['trade_id'],
                                side=BUY if trade['side'] == 'buy' else SELL,
                                amount=Decimal(trade[amount_sym]),
                                price=Decimal(trade['price']),
                                timestamp=timestamp_normalize(self.id, trade['timestamp']),
                                receipt_timestamp=timestamp
                                )

    async def _funding(self, msg: dict, timestamp: float):
        for update in msg['data']:
            await self.callback(FUNDING,
                                feed=self.id,
                                symbol=symbol_exchange_to_std(update['instrument_id']),
                                timestamp=timestamp_normalize(self.id, update['funding_time']),
                                receipt_timestamp=timestamp,
                                rate=update['funding_rate'],
                                estimated_rate=update['estimated_rate'],
                                settlement_time=timestamp_normalize(self.id, update['settlement_time']))

    async def _book(self, msg: dict, timestamp: float):
        if msg['action'] == 'partial':
            # snapshot
            for update in msg['data']:
                pair = symbol_exchange_to_std(update['instrument_id'])
                self.l2_book[pair] = {
                    BID: sd({
                        Decimal(price): Decimal(amount) for price, amount, *_ in update['bids']
                    }),
                    ASK: sd({
                        Decimal(price): Decimal(amount) for price, amount, *_ in update['asks']
                    })
                }

                if self.checksum_validation and self.__calc_checksum(pair) != (update['checksum'] & 0xFFFFFFFF):
                    raise BadChecksum
                await self.book_callback(self.l2_book[pair], L2_BOOK, pair, True, None, timestamp_normalize(self.id, update['timestamp']), timestamp)
        else:
            # update
            for update in msg['data']:
                delta = {BID: [], ASK: []}
                pair = symbol_exchange_to_std(update['instrument_id'])
                for side in ('bids', 'asks'):
                    s = BID if side == 'bids' else ASK
                    for price, amount, *_ in update[side]:
                        price = Decimal(price)
                        amount = Decimal(amount)
                        if amount == 0:
                            if price in self.l2_book[pair][s]:
                                delta[s].append((price, 0))
                                del self.l2_book[pair][s][price]
                        else:
                            delta[s].append((price, amount))
                            self.l2_book[pair][s][price] = amount
                if self.checksum_validation and self.__calc_checksum(pair) != (update['checksum'] & 0xFFFFFFFF):
                    raise BadChecksum
                await self.book_callback(self.l2_book[pair], L2_BOOK, pair, False, delta, timestamp_normalize(self.id, update['timestamp']), timestamp)

    async def _order(self, msg: dict, timestamp: float):
        if msg['data'][0]['status'] == "open":
            status = "active"
        else:
            status = msg['data'][0]['status']

        keys = ('filled_size', 'size', 'filled_notional')
        data = {k: Decimal(msg['data'][0][k]) for k in keys if k in msg['data'][0]}

        await self.callback(ORDER_INFO, feed=self.id,
                            symbol=symbol_exchange_to_std(msg['data'][0]['instrument_id'].upper()),  # This uses the REST endpoint format (lower case)
                            status=status,
                            order_id=msg['data'][0]['order_id'],
                            side=BUY if msg['data'][0]['side'].lower() == 'buy' else SELL,
                            order_type=msg['data'][0]['type'],
                            timestamp=msg['data'][0]['timestamp'].timestamp(),
                            receipt_timestamp=timestamp,
                            **data
                            )

    async def _login(self, msg: dict, timestamp: float):
        LOG.info('%s: Websocket logged in? %s', self.id, msg['success'])

    async def message_handler(self, msg: str, conn, timestamp: float):

        # DEFLATE compression, no header
        msg = zlib.decompress(msg, -15)
        msg = json.loads(msg, parse_float=Decimal)

        if 'event' in msg:
            if msg['event'] == 'error':
                LOG.error("%s: Error: %s", self.id, msg)
            elif msg['event'] == 'subscribe':
                pass
            elif msg['event'] == 'login':
                await self._login(msg, timestamp)
            else:
                LOG.warning("%s: Unhandled event %s", self.id, msg)
        elif 'table' in msg:
            if 'ticker' in msg['table']:
                await self._ticker(msg, timestamp)
            elif 'trade' in msg['table']:
                await self._trade(msg, timestamp)
            elif 'depth_l2_tbt' in msg['table']:
                await self._book(msg, timestamp)
            elif 'swap/funding_rate' in msg['table']:
                await self._funding(msg, timestamp)
            elif 'spot/order' in msg['table']:
                await self._order(msg, timestamp)
            else:
                LOG.warning("%s: Unhandled message %s", self.id, msg)
        else:
            LOG.warning("%s: Unhandled message %s", self.id, msg)

    def connect(self) -> List[Tuple[AsyncConnection, Callable[[None], None], Callable[[str, float], None]]]:
        ret = []
        for channel in self.subscription or self.channels:
            if is_authenticated_channel(channel):
                syms = self.symbols or self.subscription[channel]
                for s in syms:
                    ret.append((AsyncConnection(self.address, self.id, **self.ws_defaults), partial(self.user_order_subscribe, symbol=s), self.message_handler))
            else:
                ret.append((AsyncConnection(self.address, self.id, **self.ws_defaults), self.subscribe, self.message_handler))

        return ret

    async def user_order_subscribe(self, conn: AsyncConnection, symbol=None):
        self.__reset()
        timestamp, sign = generate_token(self.key_id, self.key_secret)
        login_param = {"op": "login", "args": [self.key_id, self.config.okex.key_passphrase, timestamp, sign.decode("utf-8")]}
        login_str = json.dumps(login_param)
        await conn.send(login_str)
        await asyncio.sleep(5)
        sub_param = {"op": "subscribe", "args": ["spot/order:{}".format(symbol)]}
        sub_str = json.dumps(sub_param)
        await conn.send(sub_str)
