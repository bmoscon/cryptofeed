'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com
Please see the LICENSE file for the terms and conditions
associated with this software.
'''

import asyncio
import aiohttp
import logging
from time import time
import json
from json import JSONDecodeError

from cryptofeed.defines import WHALE_ALERT, TRANSACTIONS
from cryptofeed.feed import Feed
from cryptofeed.standards import symbol_exchange_to_std
from cryptofeed.exceptions import RestResponseError


LOG = logging.getLogger('feedhandler')
TO_FROM_DATA = ('address', 'owner_type', 'owner')


class WhaleAlert(Feed):

    id = WHALE_ALERT

    def __init__(self, **kwargs):
        """
        Parameters:
            kwargs['sleep_time'] (float - optional):
                Number of seconds to wait between 2 API requests. By default, is 6, as per free plan.

            kwargs['trans_min_value'] (float - optional):
                Minimal transaction value to filter returned transactions from API. By default, is 500k$, as per free plan.

            kwargs['key_id'] (string - optional):
                API key to be used to connect. If not provided, that stored in 'feed_keys.yaml' will be used.

            kwargs['max_history'] (string - optional):
                Maximal allowed history, depending on your pricing plan. Format is of type '1H' (for 1 hour) or '1D' (for 1 day).
                Maximal history can only be specified with hours or days. By default, is 1 hour, as per free plan.

        """
        self.sleep_time = kwargs.pop('sleep_time') if 'sleep_time' in kwargs else 6                      # Free plan is one request every 6 seconds.
        self.trans_min_value = kwargs.pop('trans_min_value') if 'trans_min_value' in kwargs else 500000  # Free plan is 500k$ transaction minimum value.
        max_history = kwargs.pop('max_history') if 'max_history' in kwargs else 3600                     # Free plan is 1 hour transaction history.
        super().__init__('https://api.whale-alert.io/v1/', **kwargs)
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
            self.max_history = max_history
        else:
            self.max_history = max_history

        # `self.last_transaction_update` is voluntarily not reset in `__reset()` to avoid storing twice the same data after a reset.
        # dict({coin: (latest_cleared_timestamp, cursor, query_start_timestamp),...})
        # Whale Alert uses second-precise timestamps (not millisecond) which is why making chained calls is justified.
        # Making chained calls prevent having holes in the list of transactions.
        # To make a chained call, it is necessary to use same timestamp as that of the 1st call (`query_start_timestamp`),
        # and `cursor` given in previous response.
        self.last_transaction_update = dict()

    async def subscribe(self):
        self.__reset()
        return

    def __reset(self):
        pass

    async def message_handler(self):
        async def handle(session, coin, chan):
            if chan == TRANSACTIONS:
                await self._transactions(session, coin)
            await asyncio.sleep(self.sleep_time)

        async with aiohttp.ClientSession() as session:
            if self.subscription:
                for chan in self.subscription:
                    for coin in self.subscription[chan]:
                        await handle(session, coin, chan)
            else:
                for chan in self.channels:
                    for coin in self.symbols:
                        await handle(session, coin, chan)
        return

    async def _transactions(self, session, coin):
        """
        Data from /transactions?api_key=_&min_value=_&start=_&currency=_
        Query strategy seeks to prevent any missing data between 2 queries, even in case of simultaneous transactions,
        by use of 'cursor' when appropriate ('chained calls').
        """

        receipt_timestamp = int(time())
        last_trans_up = self.last_transaction_update
        # Using 2s margin for the algo to issue the query and still being within `self.max_history`.
        max_history_ts = receipt_timestamp - self.max_history + 2

        # Initialize `cursor` and `query_start_ts`.
        try:
            latest_cleared_ts, cursor, query_start_ts = last_trans_up[coin]
            if not cursor:
                if latest_cleared_ts < max_history_ts:
                    LOG.warning("{!s} - Possible hole in transaction data for coin {!s} due to impossibility to query far enough, back in time.".format(self.id, coin))
                    query_start_ts = max_history_ts
                else:
                    query_start_ts = latest_cleared_ts
        except Exception:
            cursor = ''
            query_start_ts = max_history_ts
            latest_cleared_ts = max_history_ts

        query = f"{self.address}transactions?api_key={self.key_id}&min_value={self.trans_min_value}&start={query_start_ts}&currency={coin}&cursor={cursor}" \
                if cursor else f"{self.address}transactions?api_key={self.key_id}&min_value={self.trans_min_value}&start={query_start_ts}&currency={coin}"

        async with session.get(query) as response:
            data = await response.read()
            try:
                data = json.loads(data)
            except JSONDecodeError as jde:
                raise Exception('Returned error: {!s}\nReturned response content from HTTP request: {!s}'.format(jde, data))

            if data['result'] == 'error':
                raise RestResponseError('Error message in response: {!s}'.format(data['message']))

            # Keeping previous `latest_cleared_ts` in `max_trans_ts` in case there is no new transactions.
            max_trans_ts = latest_cleared_ts
            latest_cleared_ts = receipt_timestamp - 1200  # Leaving 20mn margin for Whale Alert to insert a new entry in their database.
            if 'transactions' in data:
                for transaction in data['transactions']:
                    # Flattening the nested dicts.
                    # 'Owner' is not provided if not known. Forcing it as '' into the dict so that DataFrame remains consistent in Cryptostore.
                    to = transaction.pop('to')
                    to = {('to_' + k): (to[k] if k in to else '') for k in TO_FROM_DATA}
                    fro = transaction.pop('from')
                    fro = {('from_' + k): (fro[k] if k in fro else '') for k in TO_FROM_DATA}
                    del transaction['symbol']  # removing duplicate data with `pair` that is added
                    await self.callback(TRANSACTIONS,
                                        feed=self.id,
                                        symbol=symbol_exchange_to_std(coin),
                                        # `timestamp` is already with the correct format in `transaction` dict (in unit second).
                                        **transaction, **to, **fro)
                    max_trans_ts = transaction['timestamp'] if transaction['timestamp'] > max_trans_ts else max_trans_ts

            # Comments regarding `latest_cleared_ts`:
            # From doc. : "Some transactions might be reported with a small delay."
            # From mail exchange with support: "That line is there as a disclaimer in case anything goes wrong.
            # In general (99.99% of the time) transactions are added instantly."
            # From experience, 40s delay is not uncommon.
            # Hence the 20mn substracted from `receipt_time` before the `for` loop.
            # Conditions to make a chained call next time (to make sure not to miss any transactions):
            #  - latest transaction is no older than 20mn,
            #  - data['count'] is 100.
            # Otherwise `latest_cleared_ts` will be used for next call (not a chained call).
            # Comments regarding `data['count']`:
            # Number of results per query is limited to 100.
            # If we have 100 results in the query, we are not certain the last result is the last transaction up to the receipt time or not.
            # If it is lower than 100, we know there is no more transactions till the receipt time.
            # This `latest_cleared_ts` will not be used as start ts for the next query (use of chained call).
            if max_trans_ts > latest_cleared_ts or data['count'] == 100:
                last_trans_up[coin] = (max_trans_ts, data['cursor'], query_start_ts)
            else:
                last_trans_up[coin] = (latest_cleared_ts, '', '')

        return
