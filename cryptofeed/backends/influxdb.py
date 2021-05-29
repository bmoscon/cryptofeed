'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from yapic import json

from cryptofeed.backends.backend import (BackendBookCallback, BackendBookDeltaCallback, BackendCandlesCallback, BackendFundingCallback,
                                         BackendOpenInterestCallback, BackendTickerCallback, BackendTradeCallback,
                                         BackendLiquidationsCallback, BackendMarketInfoCallback)
from cryptofeed.backends.http import HTTPCallback
from cryptofeed.defines import BID, ASK


LOG = logging.getLogger('feedhandler')


class InfluxCallback(HTTPCallback):
    def __init__(self, addr: str, org: str, bucket: str, token: str, key=None, **kwargs):
        """
        Parent class for InfluxDB callbacks

        influxDB schema
        ---------------
        MEASUREMENT | TAGS | FIELDS

        Measurement: Data Feed-Exchange (configurable)
        TAGS: symbol
        FIELDS: timestamp, amount, price, other funding specific fields

        Example data in InfluxDB
        ------------------------
        > select * from "book-COINBASE";
        name: COINBASE
        time                amount    symbol    price   side timestamp
        ----                ------    ----    -----   ---- ---------
        1542577584985404000 0.0018    BTC-USD 5536.17 bid  2018-11-18T21:46:24.963762Z
        1542577584985404000 0.0015    BTC-USD 5542    ask  2018-11-18T21:46:24.963762Z
        1542577585259616000 0.0018    BTC-USD 5536.17 bid  2018-11-18T21:46:25.256391Z

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
        super().__init__(addr, **kwargs)
        self.addr = f"{addr}/api/v2/write?org={org}&bucket={bucket}&precision=us"
        self.headers = {"Authorization": f"Token {token}"}

        self.session = None
        self.key = key if key else self.default_key
        self.numeric_type = float

    def format(self, data):
        ret = []
        for key, value in data.items():
            if key in {'timestamp', 'feed', 'symbol', 'receipt_timestamp'}:
                continue
            if isinstance(value, str):
                ret.append(f'{key}="{value}"')
            else:
                ret.append(f'{key}={value}')
        return ','.join(ret)

    async def write(self, feed, symbol, timestamp, receipt_timestamp, data):
        d = self.format(data)
        update = f'{self.key}-{feed},symbol={symbol} {d},timestamp={timestamp},receipt_timestamp={receipt_timestamp} {int(timestamp * 1000000)}'
        await self.queue.put({'data': update, 'headers': self.headers})


class TradeInflux(InfluxCallback, BackendTradeCallback):
    default_key = 'trades'

    def format(self, data):
        return f'side="{data["side"]}",price={data["price"]},amount={data["amount"]},id="{str(data["id"])}",order_type="{str(data["order_type"])}"'


class FundingInflux(InfluxCallback, BackendFundingCallback):
    default_key = 'funding'


class BookInflux(InfluxCallback, BackendBookCallback):
    default_key = 'book'

    def format(self, data):
        bids = json.dumps(data[BID])
        asks = json.dumps(data[ASK])
        return f'delta=false,{BID}="{bids}",{ASK}="{asks}"'


class BookDeltaInflux(InfluxCallback, BackendBookDeltaCallback):
    default_key = 'book'

    def format(self, data):
        bids = json.dumps(data[BID])
        asks = json.dumps(data[ASK])
        return f'delta=true,{BID}="{bids}",{ASK}="{asks}"'


class TickerInflux(InfluxCallback, BackendTickerCallback):
    default_key = 'ticker'


class OpenInterestInflux(InfluxCallback, BackendOpenInterestCallback):
    default_key = 'open_interest'


class LiquidationsInflux(InfluxCallback, BackendLiquidationsCallback):
    default_key = 'liquidations'


class MarketInfoInflux(InfluxCallback, BackendMarketInfoCallback):
    default_key = 'market_info'


class CandlesInflux(InfluxCallback, BackendCandlesCallback):
    default_key = 'candles'
