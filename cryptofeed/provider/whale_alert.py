'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com
Please see the LICENSE file for the terms and conditions
associated with this software.
'''

import asyncio
import logging
import time
from decimal import Decimal
from typing import Dict, Iterable, Union

from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import TRANSACTIONS, WHALE_ALERT
from cryptofeed.feed import Feed
from cryptofeed.standards import symbol_exchange_to_std

LOG = logging.getLogger('feedhandler')
TO_FROM_DATA = ('address', 'owner_type', 'owner')


class WhaleAlert(Feed):

    id = WHALE_ALERT
    SLEEP_TIME = 6  # Free plan is one request every 6 seconds.

    def __init__(self, sleep_time: float = 6, trans_min_value: float = 500000, max_history: Union[int, str] = 3600, **kwargs):
        """
        Parameters:
            sleep_time (float - optional):
                Number of seconds to wait between 2 API requests. By default, is 6, as per free plan.

            trans_min_value (float - optional):
                Minimal transaction value to filter returned transactions from API. By default, is 500k$, as per free plan.

            max_history (string - optional):
                Maximal allowed history, depending on your pricing plan. Format is of type '1H' (for 1 hour) or '1D' (for 1 day).
                Maximal history can only be specified with hours or days. By default, is 1 hour, as per free plan.

            kwargs['key_id'] (string - optional):
                API key to be used to connect. If not provided, that stored in 'feed_keys.yaml' will be used.
        """
        super().__init__('https://api.whale-alert.io/v1/', **kwargs)

        WhaleAlert.SLEEP_TIME = sleep_time

        self.trans_min_value = trans_min_value

        # Shamlessly inspired from bmoscon/cryptostore/aggregator/aggregator.py
        if isinstance(max_history, str):
            multiplier = 1
            if len(max_history) > 1:
                multiplier = int(max_history[:-1])
                max_history = max_history[-1]
            if max_history in {'H', 'D'}:
                if max_history == 'H':
                    max_history = 3600 * multiplier
                else:
                    max_history = 86400 * multiplier
            else:
                LOG.error("Format of 'max_history' {!s} is not understood.".format(max_history))
            self.max_history: int = max_history
        else:
            self.max_history: int = max_history

        self.key_id = kwargs.get('key_id')
        if not self.key_id:
            LOG.critical('WHALE_ALERT: No API key provided. Impossible to connect.')

        self.skip_coins = set()

        for chan in set(self.channels or self.subscription):
            if chan == TRANSACTIONS:
                break
        else:
            LOG.critical(f'%s: support the channel {TRANSACTIONS!r} only, but it is missing, cannot retrieve data', self.id)
            raise ValueError(f'WHALE_ALERT: Please set the missing channel {TRANSACTIONS!r}')

        # `self.last_trans_up` is voluntarily not reset in `__reset()` to avoid storing twice the same data after a reset.
        # dict({coin: (latest_cleared_timestamp, cursor, query_start_timestamp),...})
        # Whale Alert uses second-precise timestamps (not millisecond) which is why making chained calls is justified.
        # Making chained calls prevent having holes in the list of transactions.
        # To make a chained call, it is necessary to use same timestamp as that of the 1st call (`query_start_timestamp`),
        # and `cursor` given in previous response.
        self.last_trans_up = {}

    async def subscribe(self, conn: AsyncConnection):
        coins = set(self.symbols or self.subscription[TRANSACTIONS])
        if len(coins) <= len(self.skip_coins):
            LOG.warning('%s: reset skip_coins because the configured %s coins are less or equal to the %s skip_coins: %s',
                        self.id, len(coins), len(self.skip_coins), self.skip_coins)
            self.skip_coins = {}

    def addr_compute(self) -> Iterable[dict]:
        """Provide dynamic URLs to retrieve TRANSACTIONS for each coin."""
        coins = set(self.symbols or self.subscription[TRANSACTIONS])
        while True:
            LOG.info('WA: %r coins: %r', len(coins), coins)
            LOG.info('WA: %r skip: %r', len(self.skip_coins), self.skip_coins)
            coins.difference(self.skip_coins)
            if not coins:
                txt = f'{self.id}: no more coins. skip all: {self.skip_coins}'
                LOG.error(txt)
                raise txt

            for coin in coins:
                LOG.info('WA: coin = %r', coin)

                # Using 2s margin for the algo to issue the query and still being within `self.max_history`.
                max_history_ts = int(time.time()) - self.max_history + 2

                # Initialize `cursor` and `query_start_ts`.
                try:
                    latest_cleared_ts, cursor, query_start_ts = self.last_trans_up[coin]
                    if not cursor:
                        if latest_cleared_ts < max_history_ts:
                            LOG.warning('%s %s: Possible hole in transaction data due to impossibility to query far enough, back in time.', self.id, coin)
                            query_start_ts = max_history_ts
                        else:
                            query_start_ts = latest_cleared_ts
                except Exception:  # this always occurs the first time
                    cursor = ''
                    query_start_ts = max_history_ts
                    latest_cleared_ts = max_history_ts

                query = f"{self.address}transactions?api_key={self.key_id}&min_value={self.trans_min_value}&start={query_start_ts}&currency={coin}&cursor={cursor}" \
                    if cursor else f"{self.address}transactions?api_key={self.key_id}&min_value={self.trans_min_value}&start={query_start_ts}&currency={coin}"

                if __debug__:
                    LOG.debug('%s %s: GET URL: %s', self.id, coin, query)

                yield {'addr': query, 'coin': coin, 'latest_cleared_ts': latest_cleared_ts, 'query_start_ts': query_start_ts}

    async def handle(self, data, timestamp, conn: AsyncConnection):
        """Data from /transactions?api_key=_&min_value=_&start=_&currency=_ Query strategy seeks to prevent any missing data between 2 queries, even in case of simultaneous transactions, by use of 'cursor' when appropriate ('chained calls').

        https://docs.whale-alert.io/#transactions

        No transaction:
        {'result': 'success', 'cursor': '0-0-0', 'count': 0}

        Two transactions:
        {'result': 'success',
         'cursor': '46b85a05-46b85a05-5fdb7e13',
         'count': 22, 'transactions': [
            {'blockchain': 'tron',
             'symbol': 'usdt',
             'id': '1186367644',
             'transaction_type': 'transfer',
             'hash': '4564fdc14b83c5dbf304995f5870f7113960c5640d3abb8872f3ed5adab218ee',
             'from': {'address': 'TQdUk2rSNdKRsfT6HYaVQ4qGV7nhJckvBK', 'owner_type': 'unknown'},
             'to': {'address': 'TXFBqBbqJommqZf7BV8NNYzePh97UmJodJ', 'owner': 'bitfinex', 'owner_type': 'exchange'},
             'timestamp': 1608217245,
             'amount': 500000,
             'amount_usd': Decimal('502237.66'),
             'transaction_count': 1},
            {'blockchain': 'ethereum',
             'symbol': 'usdt',
             'id': '1186403033',
             'transaction_type': 'transfer',
             'hash': 'a0655ba695e25fa4d72105b138dc390ee59154c249945d66592a0bc0775f4ac4',
             'from': {'address': 'aca7287116cfeba6acc652f85add29ebfb48b326', 'owner_type': 'unknown'},
             'to': {'address': 'c398248f635d58d41669c925511a5bc4923f8797', 'owner': 'binance', 'owner_type': 'exchange'},
             'timestamp': 1608217451,
             'amount': 700000,
             'amount_usd': Decimal('695020.4'),
             'transaction_count': 1},
        ]}
        """
        LOG.debug('WA: handle ctx = %r', conn.ctx)

        msg = json.loads(data, parse_float=Decimal)

        coin = conn.ctx['coin']

        if msg['result'] == 'error':
            self.skip_coins.add(coin)
            LOG.warning('%s %s: Skip %s coins. Response: %r GET: %s', self.id, coin, len(self.skip_coins), msg.get('message'), conn.ctx['addr'])
            if 'currency parameter' not in msg.get('message', ''):  # "invalid value for currency parameter" (bczero is listed but cannot be retrieved)
                await asyncio.sleep(10 * WhaleAlert.SLEEP_TIME)
            return

        # Keeping previous `latest_cleared_ts` in `max_trans_ts` in case there is no new transactions.
        max_trans_ts = conn.ctx['latest_cleared_ts']
        latest_cleared_ts = int(timestamp) - 1200  # Leaving 20mn margin for Whale Alert to insert a new entry in their database.

        pair = symbol_exchange_to_std(coin)

        if 'transactions' not in msg:
            LOG.debug("%s %s: No 'transactions' in response: %s", self.id, pair, msg)
        else:
            for transaction in msg['transactions']:

                await self.callback(TRANSACTIONS,
                                    feed=self.id,
                                    pair=pair,
                                    blk=transaction.get('blockchain'),
                                    kind=transaction.get('transaction_type'),
                                    qty=transaction.get('amount'),
                                    usd=transaction.get('amount_usd'),
                                    fr=self.owner(transaction.get('from', {})),
                                    to=self.owner(transaction.get('to', {})),
                                    timestamp=transaction['timestamp'],
                                    receipt_timestamp=timestamp)

                max_trans_ts = max(max_trans_ts, transaction['timestamp'])

        # Comments regarding `latest_cleared_ts`:
        # From doc. : "Some transactions might be reported with a small delay."
        # From mail exchange with support: "That line is there as a disclaimer in case anything goes wrong.
        # In general (99.99% of the time) transactions are added instantly."
        # From experience, 40s delay is not uncommon.
        # Hence the 20mn substracted from `time.time()` before the `for` loop.
        # Conditions to make a chained call next time (to make sure not to miss any transactions):
        #  - latest transaction is no older than 20mn,
        #  - data['count'] is 100.
        # Otherwise `latest_cleared_ts` will be used for next call (not a chained call).
        # Comments regarding `data['count']`:
        # Number of results per query is limited to 100.
        # If we have 100 results in the query, we are not certain the last result is the last transaction up to the receipt time or not.
        # If it is lower than 100, we know there is no more transactions till the receipt time.
        # This `latest_cleared_ts` will not be used as start ts for the next query (use of chained call).
        if (max_trans_ts > latest_cleared_ts) or (msg.get('count', 0) == 100):
            query_start_ts = conn.ctx['query_start_ts']
            self.last_trans_up[coin] = (max_trans_ts, msg['cursor'], query_start_ts)
        else:
            self.last_trans_up[coin] = (latest_cleared_ts, '', '')

    @staticmethod
    def owner(from_to: Dict[str, str]):
        owner = from_to.get('owner')
        if owner:
            kind = from_to.get('owner_type')
            if kind == 'exchange':
                return f'{owner}.exch'
            if kind:
                return f'{owner}.{kind}'
            return f'{owner}'
        else:
            return from_to.get('address')
