import re
from collections import defaultdict
from typing import Dict, Tuple

from cryptofeed.connection import RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import ASCENDEX_FUTURES, L2_BOOK, TRADES, PERPETUAL
from cryptofeed.exchanges import AscendEX
from cryptofeed.symbols import Symbol


# noinspection PyAbstractClass
class AscendEXFutures(AscendEX):
    """
    Docs, https://ascendex.github.io/ascendex-futures-pro-api-v2/#introducing-futures-pro-v2-apis
    """
    id = ASCENDEX_FUTURES
    websocket_channels = {
        **AscendEX.websocket_channels,
    }
    # Docs, https://ascendex.github.io/ascendex-futures-pro-api-v2/#how-to-connect
    # noinspection PyTypeChecker
    websocket_endpoints = [WebsocketEndpoint('wss://ascendex.com:443/api/pro/v2/stream', channel_filter=(websocket_channels[L2_BOOK], websocket_channels[TRADES],), sandbox='wss://api-test.ascendex-sandbox.com:443/api/pro/v2/stream')]
    # Docs, https://ascendex.github.io/ascendex-futures-pro-api-v2/#futures-contracts-info
    rest_endpoints = [RestEndpoint('https://ascendex.com', routes=Routes('/api/pro/v2/futures/contract'), sandbox='https://api-test.ascendex-sandbox.com')]

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        # Docs, https://ascendex.github.io/ascendex-futures-pro-api-v2/#futures-contracts-info
        ret = {}
        info = defaultdict(dict)

        for entry in data['data']:
            # Only "Normal" status symbols are tradeable
            if entry['status'] == 'Normal':
                s = Symbol(
                    re.sub(entry['settlementAsset'], '', entry['displayName']),
                    entry['settlementAsset'],
                    type=PERPETUAL
                )
                ret[s.normalized] = entry['symbol']
                info['tick_size'][s.normalized] = entry['priceFilter']['tickSize']
                info['instrument_type'][s.normalized] = s.type

        return ret, info
