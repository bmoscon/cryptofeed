'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
import logging
import re

from cryptofeed import _json as json

from cryptofeed.backends._line_protocol import INFLUXDB, encode
from cryptofeed.backends.backend import BackendBookCallback, BackendCallback
from cryptofeed.backends.http import HTTPCallback, error_message
from cryptofeed.defines import BID, ASK

LOG = logging.getLogger(__name__)

UNPARSEABLE = re.compile(r"unable to parse '(.*)': ")
DROPPED = re.compile(r'dropped=(\d+)')


class InfluxCallback(HTTPCallback):
    def __init__(self, addr: str, org: str, bucket: str, token: str, key=None, **kwargs):
        """
        Parent class for InfluxDB callbacks

        influxDB schema
        ---------------
        MEASUREMENT | TAGS | FIELDS

        Measurement: Data Feed-Exchange (configurable)
        TAGS: symbol (plus interval for candles)
        FIELDS: timestamp, amount, price, other data type specific fields

        Parameters
        ----------
        addr: str
          Address for connection. Should be in the format:
          http(s)://<ip addr>:port
        org: str
          Organization name for authentication
        bucket: str
          Bucket name for authentication
        token: str
          Token string for authentication
        key:
          key to use when writing data, will be a combination of key-datatype
        """
        super().__init__(f"{addr}/api/v2/write?org={org}&bucket={bucket}&precision=ns", **kwargs)
        self.headers = {"Authorization": f"Token {token}"}
        self.key = key if key else self.default_key
        self.numeric_type = float
        self.none_to = None
        self._last_point_ns = 0

    def _tags(self, data: dict) -> dict:
        tags = {'symbol': data['symbol']}
        if 'interval' in data:
            tags['interval'] = data['interval']
        return tags

    def _fields(self, data: dict) -> dict:
        return {key: value for key, value in data.items()
                if key not in ('exchange', 'symbol', 'interval') and not key.startswith('_')}

    def _point_time(self, data: dict) -> int:
        stamp = data.get('_influx_ns')
        if stamp is None:
            stamp = max(int(data['receipt_timestamp'] * 1_000_000_000), self._last_point_ns + 1)
            self._last_point_ns = stamp
            data['_influx_ns'] = stamp
        return stamp

    def _encode(self, data: dict) -> str:
        return encode(f'{self.key}-{data["exchange"]}', self._tags(data), self._fields(data), self._point_time(data), dialect=INFLUXDB)

    def _rejected_line(self, body: str, lines: list):
        match = UNPARSEABLE.search(error_message(body))
        if match is None:
            return None
        try:
            return lines.index(match.group(1))
        except ValueError:
            return None

    def _partial_write(self, body: str, lines: list):
        message = error_message(body)
        if 'partial write' not in message:
            return None
        match = DROPPED.search(message)
        return min(int(match.group(1)), len(lines)) if match else None


class TradeInflux(InfluxCallback, BackendCallback):
    default_key = 'trades'


class FundingInflux(InfluxCallback, BackendCallback):
    default_key = 'funding'


class BookInflux(InfluxCallback, BackendBookCallback):
    default_key = 'book'

    def __init__(self, *args, snapshots_only=False, snapshot_interval=1000, **kwargs):
        self.snapshots_only = snapshots_only
        self.snapshot_interval = snapshot_interval
        self.snapshot_count = defaultdict(int)
        super().__init__(*args, **kwargs)

    def _fields(self, data: dict) -> dict:
        delta = 'delta' in data
        book = data['delta'] if delta else data['book']
        return {'delta': delta, BID: json.dumps(book[BID]), ASK: json.dumps(book[ASK]),
                'timestamp': data['timestamp'], 'receipt_timestamp': data['receipt_timestamp']}


class TickerInflux(InfluxCallback, BackendCallback):
    default_key = 'ticker'


class OpenInterestInflux(InfluxCallback, BackendCallback):
    default_key = 'open_interest'


class LiquidationsInflux(InfluxCallback, BackendCallback):
    default_key = 'liquidations'


class CandlesInflux(InfluxCallback, BackendCallback):
    default_key = 'candles'
