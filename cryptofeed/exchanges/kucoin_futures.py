'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from typing import Dict, Tuple

from cryptofeed.connection import RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import FUTURES, KUCOIN_FUTURES, PERPETUAL
from cryptofeed.exchanges.kucoin import KuCoin
from cryptofeed.symbols import Symbol


LOG = logging.getLogger(__name__)


class KuCoinFutures(KuCoin):
    id = KUCOIN_FUTURES
    websocket_endpoints = [WebsocketEndpoint('wss://x-push-futures.kucoin.com')]
    TRADE_TYPE = 'FUTURES'
    rest_endpoints = [RestEndpoint('https://api-futures.kucoin.com', routes=Routes('/api/v1/contracts/active', l2book='/api/v1/level2/snapshot?symbol={}'))]
    CONTRACT_TYPES = {'FFWCSX': PERPETUAL, 'FFICSX': FUTURES}

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret, info = {}, {'instrument_type': {}, 'tick_size': {}, 'contract_size': {}, 'is_inverse': {}}

        for entry in data['data']:
            if entry.get('status') != 'Open':
                continue
            stype = cls.CONTRACT_TYPES.get(entry['type'])
            if stype is None:
                LOG.warning('%s: skipping %s, unknown contract type %s', cls.id, entry['symbol'], entry['type'])
                continue

            base = entry['baseCurrency'].replace('XBT', 'BTC')
            quote = entry['quoteCurrency'].replace('XBT', 'BTC')
            expiry = entry.get('expireDate')

            s = Symbol(base, quote, type=stype,
                       expiry_date=None if expiry is None else expiry / 1000)

            info['instrument_type'][s.normalized] = stype
            info['tick_size'][s.normalized] = entry['tickSize']
            info['contract_size'][s.normalized] = entry['multiplier']
            info['is_inverse'][s.normalized] = entry.get('isInverse', False)
            ret[s.normalized] = entry['symbol']

        return ret, info
