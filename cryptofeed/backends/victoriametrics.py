'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback
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

    async def write(self, data: dict):
        # Convert data to InfluxDB Line Protocol format
        d = ''
        t = ''
        for key, value in data.items():
            if key in {'timestamp', 'exchange', 'symbol', 'receipt_timestamp'}:
                continue
            # VictoriaMetrics does not support discrete data as values,
            # convert strings to VictoriaMetricsDB tags.
            if isinstance(value, str):
                t += f',{key}={value}'
            else:
                d += f'{key}={value},'

        update = f'{self.key},exchange={data["exchange"]},symbol={data["symbol"]}{t} {d}timestamp={data["timestamp"]},receipt_timestamp={data["receipt_timestamp"]}\n'
        await self.queue.put(update)


class VictoriaMetricsBookCallback(VictoriaMetricsCallback):
    default_key = 'book'

    async def _write_rows(self, start, data):
        msg = []
        timestamp = data['timestamp']
        receipt_timestamp = data['receipt_timestamp']
        ts = int(timestamp * 1000000000) if timestamp else int(receipt_timestamp * 1000000000)
        for side in (BID, ASK):
            for price in data.book[side]:
                val = data.book[side][price]
                if isinstance(val, dict):
                    for order_id, amount in val.items():
                        msg.append(f'{start},side={side} id={order_id},receipt_timestamp={receipt_timestamp},timestamp={timestamp},price={price},amount={amount} {ts}')
                        ts += 1
                else:
                    msg.append(f'{start},side={side} receipt_timestamp={receipt_timestamp},timestamp={timestamp},price={price},amount={val} {ts}')
                    ts += 1
        await self.queue.put('\n'.join(msg) + '\n')


class TradeVictoriaMetrics(VictoriaMetricsCallback, BackendCallback):
    default_key = 'trades'


class FundingVictoriaMetrics(VictoriaMetricsCallback, BackendCallback):
    default_key = 'funding'


class BookVictoriaMetrics(VictoriaMetricsBookCallback, BackendBookCallback):
    async def write(self, data):
        start = f"{self.key},feed={data['exchange']},symbol={data['symbol']},delta={str('delta' in data)}"
        await self._write_rows(start, data)


class TickerVictoriaMetrics(VictoriaMetricsCallback, BackendCallback):
    default_key = 'ticker'


class OpenInterestVictoriaMetrics(VictoriaMetricsCallback, BackendCallback):
    default_key = 'open_interest'


class LiquidationsVictoriaMetrics(VictoriaMetricsCallback, BackendCallback):
    default_key = 'liquidations'


class CandlesVictoriaMetrics(VictoriaMetricsCallback, BackendCallback):
    default_key = 'candles'
