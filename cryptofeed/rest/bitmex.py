'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from time import sleep
import time
import hashlib
import hmac
from urllib.parse import urlparse
import logging
import zlib
from datetime import datetime as dt
from datetime import timedelta

from sortedcontainers import SortedDict as sd
import requests
import pandas as pd

from cryptofeed.rest.api import API, request_retry
from cryptofeed.defines import BITMEX, SELL, BUY, BID, ASK
from cryptofeed.standards import timestamp_normalize


S3_ENDPOINT = 'https://s3-eu-west-1.amazonaws.com/public.bitmex.com/data/{}/{}.csv.gz'
RATE_LIMIT_SLEEP = 2
API_MAX = 500
API_REFRESH = 300

LOG = logging.getLogger('rest')


class Bitmex(API):
    ID = BITMEX
    api = 'https://www.bitmex.com'

    def _generate_signature(self, verb: str, url: str, data='') -> dict:
        """
        verb: GET/POST/PUT
        url: api endpoint
        data: body (if present)
        """
        expires = int(round(time.time()) + 30)

        parsedURL = urlparse(url)
        path = parsedURL.path
        if parsedURL.query:
            path = path + '?' + parsedURL.query

        if isinstance(data, (bytes, bytearray)):
            data = data.decode('utf8')

        message = verb + path + str(expires) + data

        signature = hmac.new(bytes(self.key_secret, 'utf8'), bytes(message, 'utf8'), digestmod=hashlib.sha256).hexdigest()
        return {
            "api-expires": str(expires),
            "api-key": self.key_id,
            "api-signature": signature
        }

    def _get(self, ep, symbol, start_date, end_date, retry, retry_wait, freq='6H'):
        dates = [None]
        if start_date:
            if not end_date:
                end_date = pd.Timestamp.utcnow()
            dates = pd.interval_range(API._timestamp(start_date), API._timestamp(end_date), freq=freq).tolist()
            if len(dates) == 0:
                dates.append(pd.Interval(left=API._timestamp(start_date), right=API._timestamp(end_date)))
            elif dates[-1].right < API._timestamp(end_date):
                dates.append(pd.Interval(dates[-1].right, API._timestamp(end_date)))

        @request_retry(self.ID, retry, retry_wait)
        def helper(start, start_date, end_date):
            if start_date and end_date:
                if symbol is None:
                    endpoint = f'/api/v1/{ep}?count={API_MAX}&reverse=false&start={start}&startTime={start_date}&endTime={end_date}'
                else:
                    endpoint = f'/api/v1/{ep}?symbol={symbol}&count={API_MAX}&reverse=false&start={start}&startTime={start_date}&endTime={end_date}'
            else:
                if symbol is None:
                    endpoint = f'/api/v1/{ep}?count={API_MAX}&start={start}&reverse=true'
                else:
                    endpoint = f'/api/v1/{ep}?symbol={symbol}&count={API_MAX}&start={start}&reverse=true'
            header = {}
            if self.key_id and self.key_secret:
                header = self._generate_signature("GET", endpoint)
            header['Accept'] = 'application/json'
            return requests.get('{}{}'.format(self.api, endpoint), headers=header)

        for interval in dates:
            start = 0
            if interval is not None:
                end = interval.right
                end -= pd.Timedelta(nanoseconds=1)

                start_date = str(interval.left).replace(" ", "T") + "Z"
                end_date = str(end).replace(" ", "T") + "Z"

            while True:
                r = helper(start, start_date, end_date)

                if r.status_code in {502, 504}:
                    LOG.warning("%s: %d for URL %s - %s", self.ID, r.status_code, r.url, r.text)
                    sleep(retry_wait)
                    continue
                elif r.status_code == 429:
                    sleep(API_REFRESH)
                    continue
                elif r.status_code != 200:
                    self._handle_error(r, LOG)
                else:
                    sleep(RATE_LIMIT_SLEEP)

                limit = int(r.headers['X-RateLimit-Remaining'])
                data = r.json()

                yield data

                if len(data) != API_MAX:
                    break

                if limit < 1:
                    sleep(API_REFRESH)

                start += len(data)

    def _trade_normalization(self, trade: dict) -> dict:
        return {
            'timestamp': timestamp_normalize(self.ID, trade['timestamp']),
            'pair': trade['symbol'],
            'id': trade['trdMatchID'],
            'feed': self.ID,
            'side': BUY if trade['side'] == 'Buy' else SELL,
            'amount': trade['size'],
            'price': trade['price']
        }

    def _fills_normalization(self, fills: dict) -> dict:
        """
         {'execID': '03c4d502-2e40-174e-36d8-08f9806654d0', 'orderID': '97291bdf-4955-b905-3ca8-bce62c125666',
         'clOrdID': '', 'clOrdLinkID': '', 'account': 1223021, 'symbol': 'XBTUSD', 'side': 'Buy', 'lastQty': 1000,
         'lastPx': 9270, 'underlyingLastPx': None, 'lastMkt': 'XBME', 'lastLiquidityInd': 'AddedLiquidity',
         'simpleOrderQty': None, 'orderQty': 1000, 'price': 9270, 'displayQty': None, 'stopPx': None,
         'pegOffsetValue': None, 'pegPriceType': '', 'currency': 'USD', 'settlCurrency': 'XBt', 'execType': 'Trade',
         'ordType': 'Limit', 'timeInForce': 'GoodTillCancel', 'execInst': 'ParticipateDoNotInitiate',
         'contingencyType': '', 'exDestination': 'XBME', 'ordStatus': 'Filled', 'triggered': '',
         'workingIndicator': False, 'ordRejReason': '', 'simpleLeavesQty': None, 'leavesQty': 0, 'simpleCumQty': None,
         'cumQty': 1000, 'avgPx': 9270.5, 'commission': -0.00025, 'tradePublishIndicator': 'PublishTrade',
         'multiLegReportingType': 'SingleSecurity', 'text': 'Submission from www.bitmex.com',
         'trdMatchID': '615d1fac-63e9-8287-951a-6a15aa4cebb4', 'execCost': -10787000, 'execComm': -2696,
         'homeNotional': 0.10787, 'foreignNotional': -1000, 'transactTime': '2020-06-19T07:37:00.623Z',
         'timestamp': '2020-06-19T07:37:00.623Z'}
        """
        return {
            'time': API._timestamp(fills['timestamp']).timestamp(),
            'symbol': fills['symbol'],
            'side': fills['side'].lower(),
            'size': fills['lastQty'],
            'price': fills['price'],
            'fees': fills['execComm'] * 0.00000001,
            'rate': fills['commission'],
            'text': fills['text']
        }

    def fills(self, symbol=None, start=None, end=None, retry=None, retry_wait=10):
        for data in self._get('execution/tradeHistory', symbol, start, end, retry, retry_wait):
            yield list(map(self._fills_normalization, data))

    def _money_flow_normalization(self, mf: dict) -> dict:
        """
        {'transactID': 'd16912d9-557c-ef38-a035-7a4426a428d6', 'account': 1223021, 'currency': 'XBt',
         'transactType': 'Withdrawal', 'amount': -14420000, 'fee': 20000, 'transactStatus': 'Completed',
         'address': '32mjqoLSZe5gG9bMWgPVhTxTqnyrvRTnVj', 'tx': '3BMEXEMgfMT75tctrbgB88q4373CwTopR1', 'text': '',
         'transactTime': '2020-04-18T11:48:55.018Z', 'walletBalance': 84196394, 'marginBalance': None,
         'timestamp': '2020-04-18T13:13:50.808Z'}
         """

        if mf['fee'] is not None:
            fee = mf['fee'] * 0.00000001
        else:
            fee = 0.0
        return {
            'time': API._timestamp(mf['timestamp']).timestamp(),
            'coin': mf['currency'],
            'amount': mf['amount'] * 0.00000001,
            'fee': fee,
            'tx_type': mf['transactType'].lower()
        }

    def money_flow(self, symbol=None, start=None, end=None, retry=None, retry_wait=10):
        for data in self._get('user/walletHistory', symbol, start, end, retry, retry_wait):
            yield list(map(self._money_flow_normalization, data))

    def ticker(self, symbol, start=None, end=None, retry=None, retry_wait=10):
        # return list(self._get('quote', symbol, start, end, retry, retry_wait))
        for data in self._scrape_s3(symbol, 'quote', start, end):
            yield data

    def trades(self, symbol, start=None, end=None, retry=None, retry_wait=10):
        """
        data format

        {
            'timestamp': '2018-01-01T23:59:59.907Z',
            'symbol': 'XBTUSD',
            'side': 'Buy',
            'size': 1900,
            'price': 13477,
            'tickDirection': 'ZeroPlusTick',
            'trdMatchID': '14fcc8d7-d056-768d-3c46-1fdf98728343',
            'grossValue': 14098000,
            'homeNotional': 0.14098,
            'foreignNotional': 1900
        }
        """
        d = dt.utcnow().date()
        d -= timedelta(days=1)
        rest_end_date = pd.Timestamp(dt(d.year, d.month, d.day))
        start = API._timestamp(start) if start else start
        end = API._timestamp(end) if end else end
        rest_start = start
        s3_scrape = False

        if start:
            if rest_end_date - pd.Timedelta(microseconds=1) > start:
                rest_start = rest_end_date
                s3_scrape = True

        if s3_scrape:
            rest_end_date -= pd.Timedelta(microseconds=1)
            if API._timestamp(end) < rest_end_date:
                rest_end_date = end
            for data in self._scrape_s3(symbol, 'trade', start, rest_end_date):
                yield list(map(self._s3_data_normalization, data))

        if end is None or end > rest_end_date:
            for data in self._get('trade', symbol, rest_start, end, retry, retry_wait):
                yield list(map(self._trade_normalization, data))

    def _funding_normalization(self, funding: dict) -> dict:
        return {
            'timestamp': funding['timestamp'],
            'pair': funding['symbol'],
            'feed': self.ID,
            'interval': funding['fundingInterval'],
            'rate': funding['fundingRate'],
            'rate_daily': funding['fundingRateDaily']
        }

    def funding(self, symbol, start=None, end=None, retry=None, retry_wait=10):
        """
        {
            'timestamp': '2017-01-05T12:00:00.000Z',
            'symbol': 'XBTUSD',
            'fundingInterval': '2000-01-01T08:00:00.000Z',
            'fundingRate': 0.00375,
            'fundingRateDaily': 0.01125
        }
        """
        for data in self._get('funding', symbol, start, end, retry, retry_wait, freq='2W'):
            yield list(map(self._funding_normalization, data))

    def l2_book(self, symbol: str, retry=None, retry_wait=10):
        ret = {symbol: {BID: sd(), ASK: sd()}}
        data = next(self._get('orderBook/L2', symbol, None, None, retry, retry_wait))
        for update in data:
            side = ASK if update['side'] == 'Sell' else BID
            ret[symbol][side][update['price']] = update['size']
        return ret

    def _s3_data_normalization(self, data):
        vals = data.split(",")
        return {
            'timestamp': pd.Timestamp(vals[0].replace("D", "T")).timestamp(),
            'pair': vals[1],
            'id': vals[6],
            'feed': self.ID,
            'side': BUY if vals[2] == 'Buy' else SELL,
            'amount': vals[3],
            'price': vals[4]
        }

    def _scrape_s3(self, symbol: str, dtype: str, start_date, end_date):
        date = dt(end_date.year, end_date.month, end_date.day)
        end = dt(start_date.year, start_date.month, start_date.day)

        while date >= end:
            date_str = date.strftime('%Y%m%d')
            count = 0
            while True:
                r = requests.get(S3_ENDPOINT.format(dtype, date_str))
                if r.status_code == 200:
                    break
                else:
                    count += 1
                    if count == 10:
                        r.raise_for_status()
                    LOG.warning("%s: Error processing %s: %s - %s, trying again", self.ID, symbol, date, r.status_code)
                    time.sleep(10)

            data = zlib.decompress(r.content, zlib.MAX_WBITS | 32)
            yield filter(lambda x: len(x) and x.split(",")[1] == symbol and end_date >= pd.Timestamp(x.split(",")[0].replace("D", "T")) >= start_date, data.decode().split("\n")[1:])

            date -= timedelta(days=1)


if __name__ == '__main__':
    b = Bitmex(None)
    for data in b.money_flow():
        print(data)