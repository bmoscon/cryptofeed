'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import logging
from typing import Tuple

from yapic import json

from cryptofeed.defines import BINANCE_DELIVERY, OPEN_INTEREST, TICKER, PERPETURAL, FUTURE
from cryptofeed.exchange.binance import Binance

LOG = logging.getLogger('feedhandler')

class BinanceDeliveryInstrument():
    def __init__(self, instrument_name):
        self.instrument_name = instrument_name
        instrument_properties = instrument_name.split('_')
        self.pair = instrument_properties[0]
        pair_arr = instrument_properties[0].split('-')
        self.base = pair_arr[0]
        self.quote = pair_arr[1]
        
        if instrument_properties[1] == 'PERP':
            self.instrument_type = PERPETURAL
        else:
            self.instrument_type = FUTURE
            self.expiry_date_str = instrument_properties[1]

class BinanceDelivery(Binance):
    valid_depths = [5, 10, 20, 50, 100, 500, 1000]
    id = BINANCE_DELIVERY

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # overwrite values previously set by the super class Binance
        self.ws_endpoint = 'wss://dstream.binance.com'
        self.rest_endpoint = 'https://dapi.binance.com/dapi/v1'
        self.address = self._address()

    @staticmethod
    def get_instrument_objects():
        instruments = BinanceDelivery.get_instruments()
        return [BinanceDeliveryInstrument(instrument) for instrument in instruments]

    def _check_update_id(self, pair: str, msg: dict) -> Tuple[bool, bool]:
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

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        # Combined stream events are wrapped as follows: {"stream":"<streamName>","data":<rawPayload>}
        # streamName is of format <symbol>@<channel>
        pair, _ = msg['stream'].split('@', 1)
        msg = msg['data']

        pair = pair.upper()

        msg_type = msg.get('e')
        if msg_type == 'bookTicker':
            await self._ticker(msg, timestamp)
        elif msg_type == 'depthUpdate':
            await self._book(conn, msg, pair, timestamp)
        elif msg_type == 'aggTrade':
            await self._trade(msg, timestamp)
        elif msg_type == 'forceOrder':
            await self._liquidations(msg, timestamp)
        elif msg_type == 'markPriceUpdate':
            await self._funding(msg, timestamp)
        elif msg_type == 'kline':
            await self._candle(msg, timestamp)
        else:
            LOG.warning("%s: Unexpected message received: %s", self.id, msg)
