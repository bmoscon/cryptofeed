from decimal import Decimal

from cryptofeed.exchanges import Binance
from yapic import json as json_parser


def temp_f(r, address, json=False, text=False, uuid=None):
        if r.status_code == 451:
            return {'symbols': []}
        r.raise_for_status()
        if json:
            return json_parser.loads(r.text, parse_float=Decimal)
        if text:
            return r.text
        return r 

Binance.http_sync.process_response = temp_f
