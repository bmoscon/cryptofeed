'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from datetime import datetime
from decimal import Decimal
import logging
from typing import Tuple

from yapic import json

from cryptofeed.defines import FUTURES_INDEX, BINANCE_DELIVERY, OPEN_INTEREST, TICKER, PERPETUAL, FUTURE, SPOT
from cryptofeed.exchange.binance import Binance
from cryptofeed.standards import symbol_exchange_to_std, timestamp_normalize, _exchange_to_std

LOG = logging.getLogger('feedhandler')

class BinanceDeliveryInstrument():
    def __init__(self, instrument_name):
        self.instrument_name = instrument_name
        instrument_properties = instrument_name.split('_')
        self.pair = instrument_properties[0]
        pair_arr = instrument_properties[0].split('-')
        self.base = pair_arr[0]
        self.quote = pair_arr[1]
        self.usd_spot = f'{self.base}-USD'
        self.usdt_spot = f'{self.base}-USDT'
        if len(instrument_properties) == 1:
            self.instrument_type = SPOT
        elif instrument_properties[1] == 'PERP':
            self.instrument_type = PERPETUAL
        else:
            self.instrument_type = FUTURE
            self.expiry_date_str = instrument_properties[1]
            self.expiry_date = datetime.strptime(self.expiry_date_str, "%y%m%d")
            self.expiry_date = self.expiry_date.replace(hour=8)

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

    @staticmethod
    def convert_to_instrument_object(instrument_name):
        return BinanceDeliveryInstrument(instrument_name)

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

    async def _futures_index(self, msg: dict, timestamp: float):
        """
        {
            "e": "indexPriceUpdate",  // Event type
            "E": 1591261236000,       // Event time
            "i": "BTCUSD",            // Pair
            "p": "9636.57860000",     // Index Price
        }
        """
        await self.callback(FUTURES_INDEX,
                            feed=self.id,
                            symbol=symbol_exchange_to_std(msg['i']),
                            timestamp=timestamp_normalize(self.id, msg['E']),
                            receipt_timestamp=timestamp,
                            futures_index=Decimal(msg['p']),
                            )

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
        elif msg_type == 'indexPriceUpdate':
            await self._futures_index(msg, timestamp)
        elif msg_type == '24hrMiniTicker':
            await self._volume(msg, timestamp)
        elif msg_type == 'kline':
            await self._candle(msg, timestamp)
        else:
            LOG.warning("%s: Unexpected message received: %s", self.id, msg)
