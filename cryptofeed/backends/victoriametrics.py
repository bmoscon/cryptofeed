'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from cryptofeed.backends.backend import (BackendBookCallback, BackendBookDeltaCallback, BackendCandlesCallback, BackendFundingCallback,
                                         BackendOpenInterestCallback, BackendTickerCallback, BackendTradeCallback,
                                         BackendLiquidationsCallback, BackendMarketInfoCallback, BackendTransactionsCallback)
from cryptofeed.backends.socket import SocketCallback
from cryptofeed.defines import BID, ASK
from typing import Optional


LOG = logging.getLogger('feedhandler')


class VictoriaMetricsCallback(SocketCallback):
    def __init__(self, addr: str, port: int, key: Optional[str] = None, **kwargs):
        """
        Parent class for VictoriaMetrics callbacks

        VictoriaMetrics support multiple protocol for data ingestion.
        In the following implementation we present data in InfluxDB Line Protocol format.

        InfluxDB schema
        ---------------
        MEASUREMENT | TAGS | FIELDS

        Measurement: Data Feed-Exchange (configurable)
        TAGS: symbol
        FIELDS: timestamp, amount, price, other funding specific fields

        InfluxDB Line Protocol to VictoriaMetrics storage
        -------------------------------------------------
        Please note that Field names are mapped to time series names prefixed with
        {measurement}{separator} value, where {separator} equals to _ by default.
        It can be changed with -influxMeasurementFieldSeparator command-line flag.

        For example, the following InfluxDB line:
            foo,tag1=value1,tag2=value2 field1=12,field2=40

        is converted into the following Prometheus data points:
            foo_field1{tag1="value1", tag2="value2"} 12
            foo_field2{tag1="value1", tag2="value2"} 40

        Ref: Ref: https://github.com/VictoriaMetrics/VictoriaMetrics#how-to-send-data-from-influxdb-compatible-agents-such-as-telegraf

        Parameters
        ----------
        addr: str
          Address for connection. Should be in the format:
          <protocol>://<address>
          Example:
          tcp://127.0.0.1
          udp://127.0.0.1
         port: int
           port for connection.
         key: str
           key to use when writing data
        """
        super().__init__(addr, port=port, key=key, numeric_type=float, **kwargs)

    async def write(self, feed, symbol, timestamp, receipt_timestamp, data):
        # Convert data to InfluxDB Line Protocol format
        d = ''
        t = ''
        for key, value in data.items():
            if key in {'timestamp', 'feed', 'symbol', 'receipt_timestamp'}:
                continue
            # VictoriaMetrics does not support discrete data as values,
            # convert strings to VictoriaMetricsDB tags.
            if isinstance(value, str):
                t += f',{key}={value}'
            else:
                d += f'{key}={value},'

        update = f'{self.key},feed={feed},symbol={symbol}{t} {d}timestamp={timestamp},receipt_timestamp={receipt_timestamp}\n'
        await self.queue.put(update)


class VictoriaMetricsBookCallback(VictoriaMetricsCallback):
    default_key = 'book'

    async def _write_rows(self, start, data, timestamp, receipt_timestamp):
        msg = []
        ts = int(timestamp * 1000000000)
        for side in (BID, ASK):
            for price, val in data[side].items():
                if isinstance(val, dict):
                    for order_id, amount in val.items():
                        msg.append(f'{start},side={side} id={order_id},receipt_timestamp={receipt_timestamp},timestamp={timestamp},price={price},amount={amount} {ts}')
                        ts += 1
                else:
                    msg.append(f'{start},side={side} receipt_timestamp={receipt_timestamp},timestamp={timestamp},price={price},amount={val} {ts}')
                    ts += 1
        await self.queue.put('\n'.join(msg) + '\n')


class TradeVictoriaMetrics(VictoriaMetricsCallback, BackendTradeCallback):
    default_key = 'trades'


class FundingVictoriaMetrics(VictoriaMetricsCallback, BackendFundingCallback):
    default_key = 'funding'


class BookVictoriaMetrics(VictoriaMetricsBookCallback, BackendBookCallback):
    async def write(self, feed, symbol, timestamp, receipt_timestamp, data):
        start = f"{self.key},feed={feed},symbol={symbol},delta=False"
        await self._write_rows(start, data, timestamp, receipt_timestamp)


class BookDeltaVictoriaMetrics(VictoriaMetricsBookCallback, BackendBookDeltaCallback):
    async def write(self, feed, symbol, timestamp, receipt_timestamp, data):
        start = f"{self.key},feed={feed},symbol={symbol},delta=True"
        await self._write_rows(start, data, timestamp, receipt_timestamp)


class TickerVictoriaMetrics(VictoriaMetricsCallback, BackendTickerCallback):
    default_key = 'ticker'


class OpenInterestVictoriaMetrics(VictoriaMetricsCallback, BackendOpenInterestCallback):
    default_key = 'open_interest'


class LiquidationsVictoriaMetrics(VictoriaMetricsCallback, BackendLiquidationsCallback):
    default_key = 'liquidations'


class MarketInfoVictoriaMetrics(VictoriaMetricsCallback, BackendMarketInfoCallback):
    default_key = 'market_info'


class TransactionsVictoriaMetrics(VictoriaMetricsCallback, BackendTransactionsCallback):
    default_key = 'transactions'


class CandlesVictoriaMetrics(VictoriaMetricsCallback, BackendCandlesCallback):
    default_key = 'candles'
