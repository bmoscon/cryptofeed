'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import logging

from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BINANCE_FUTURES, OPEN_INTEREST, TICKER
from cryptofeed.exchange.binance import Binance

LOG = logging.getLogger('feedhandler')


class BinanceFutures(Binance):
    id = BINANCE_FUTURES

    def __init__(self, depth=1000, **kwargs):
        super().__init__(depth=depth, **kwargs)
        # overwrite values previously set by the super class Binance
        self.rest_endpoint = 'https://fapi.binance.com/fapi/v1'
        self.address = self._address('wss://fstream.binance.com', stream_builder=self.book_ticker_stream)

    def _check_update_id(self, pair: str, msg: dict) -> (bool, bool):
        skip_update = False
        forced = not self.forced[pair]

        if forced and msg['u'] < self.last_update_id[pair]:
            skip_update = True
        elif forced and msg['U'] <= self.last_update_id[pair] <= msg['u']:
            self.last_update_id[pair] = msg['u']
            self.forced[pair] = True
        elif not forced and self.last_update_id[pair] == msg['pu']:
            self.last_update_id[pair] = msg['u']
        else:
            self._reset()
            LOG.warning("%s: Missing book update detected, resetting book", self.id)
            skip_update = True
        return skip_update, forced

    async def handle(self, data: bytes, timestamp: float, conn: AsyncConnection):

        msg = json.loads(data, parse_float=Decimal)

        # Combined stream events are wrapped as follows: {"stream":"<streamName>","data":<rawPayload>}
        # streamName is of format <symbol>@<channel>
        pair, _ = msg['stream'].split('@', 1)
        msg = msg['data']

        pair = pair.upper()

        msg_type = msg.get('e')
        if msg_type == 'bookTicker':
            await self._ticker(msg, timestamp)
        elif msg_type == 'depthUpdate':
            await self._book(msg, pair, timestamp)
        elif msg_type == 'aggTrade':
            await self._trade(msg, timestamp)
        elif msg_type == 'forceOrder':
            await self._liquidations(msg, timestamp)
        elif msg_type == 'markPriceUpdate':
            await self._funding(msg, timestamp)
        else:
            LOG.warning("%s: Unexpected message received: %s", conn.id, msg)
