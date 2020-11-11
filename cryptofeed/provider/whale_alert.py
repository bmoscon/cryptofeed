'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com
Please see the LICENSE file for the terms and conditions
associated with this software.
'''

import os
import asyncio
import aiohttp
import logging
from sortedcontainers import SortedDict
from functools import reduce
from operator import iconcat
from time import time

from cryptofeed.log import get_logger
from cryptofeed.defines import WHALE_ALERT, TRANSACTIONS
from cryptofeed.feed import RestFeed
from cryptofeed.standards import pair_exchange_to_std

LOG = get_logger('feedhandler',
                 os.environ.get('CRYPTOFEED_FEEDHANDLER_LOG_FILENAME', "feedhandler.log"),
                 int(os.environ.get('CRYPTOFEED_FEEDHANDLER_LOG_LEVEL', logging.WARNING)))

to_from_data = ('address', 'owner_type', 'owner')


class WhaleAlert(RestFeed):

    id = WHALE_ALERT

    def __init__(self, pairs=None, channels=None, callbacks=None, config=None, **kwargs):
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
                Maximal history can only be specific with hours or days. By default, is 1 hour, as per free plan.

        """
        self.sleep_time = kwargs.pop('sleep_time') if 'sleep_time' in kwargs else 6                      # Free plan is one request every 6 seconds.
        self.trans_min_value = kwargs.pop('trans_min_value') if 'trans_min_value' in kwargs else 500000  # Free plan is 500k$ transaction minimum value.
        max_history = kwargs.pop('max_history') if 'max_history' in kwargs else 3600                     # Free plan is 1 hour transaction history.
        super().__init__('https://api.whale-alert.io/v1/', pairs=pairs, channels=channels, config=config, callbacks=callbacks, **kwargs)
        if not self.key_id:
            LOG.error("No API key provided. Impossible to connect.")
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
                LOG.error("Format of 'max_history' {!s} is not understood.", max_history)
            self.max_history = max_history
        else:
            self.max_history = max_history

        # /!\ Following variables would be defined in `__reset()` follwoing 'standard' implementation.
        # Check with Bryant if it is ok to have them here. This would avoid to store twice the same data after a reset.
        # SortedDict storing per last cleared timestamp corresponding coins.
        # SortedDict({last_cleared_timestamp: [coin1, coin2, ...], ...})
        self.last_transaction_update = SortedDict()
        # Whale Alert uses second precise timestamps (not millisecond) which is why making chained calls is justified.
        # Making chained calls prevent having holes in the list of transactions.
        # To make a chained call, it is necessary to use same timestamp as that of the 1st call, and the cursor given in the previous call.
        # dict({coin: (cursor, first_call_timestamp),...})
        self.chained_call = dict()
        # Dict to store transaction data till they are popped out at callback call.
        self.buffer_transactions = dict()


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
            if self.config:
                for chan in self.config:
                    for coin in self.config[chan]:
                        await handle(session, coin, chan)
            else:
                for chan in self.channels:
                    for coin in self.pairs:
                        await handle(session, coin, chan)
        return

    async def _transactions(self, session, coin):
        """
        Data from /transactions?api_key=_&min_value=_&start=_&currency=_
        Query strategy seeks:
            - 1/ to maximize number of data retrieved despite limited number of possible queries.
            - 2/ to prevent any missing data between 2 queries, even in case of simultaneous transactions,
              despite the limit of 100 results per query.
        To do so:
            - for 1/ coins are prioritized in the query order from the one with the oldest transaction, to the coin with the newest transaction.
            - for 2/ implementation makes use of chained calls (use of cursor)
        """

        receipt_timestamp = int(time())
        last_trans_up = self.last_transaction_update
        # Step 1 / identification of coin and start timestamp for query to be issued.
        # If no query has been done so far for requested coin, it is kept.
        # Otherwise, coin with the oldest transaction time is queried first.
        max_history_ts = receipt_timestamp-self.max_history+2  # Using 2s margin for the algo to issue the query and still being within `self.max_history`.

        if coin in reduce(iconcat, last_trans_up.values(), []):
            latest_cleared_ts, query_coin_l = last_trans_up.popitem(index=0)
            query_coin = query_coin_l.pop(0)
            if query_coin_l != []:
                last_trans_up[latest_cleared_ts] = query_coin_l
            # `query_start_ts` is overwritten in case a chained call is to be made.
            query_cursor, query_start_ts = self.chained_call.pop(query_coin, ('', latest_cleared_ts))
            if not query_cursor and latest_cleared_ts < max_history_ts:
                LOG.warning("{!s} - Possible hole in transaction data for coins {!s} due to impossibility to query often enough.".format(self.id, query_coin))
                query_start_ts = max_history_ts
        else:
            query_coin = coin
            query_start_ts = max_history_ts
            query_cursor = ''

        # Step 2 / API query.
        query = f"{self.address}transactions?api_key={self.key_id}&min_value={self.trans_min_value}&start={query_start_ts}&currency={query_coin}&cursor={query_cursor}" \
                if query_cursor else f"{self.address}transactions?api_key={self.key_id}&min_value={self.trans_min_value}&start={query_start_ts}&currency={query_coin}"

        async with session.get(query) as response:
            data = await response.json()

            latest_cleared_ts = receipt_timestamp-4  # Using 4s margin for Whale Alert to insert a new entry in their database.
            if 'transactions' in data:
                if query_coin not in self.buffer_transactions:
                    self.buffer_transactions[query_coin] = []
                max_trans_ts = 0
                for transaction in data['transactions']:
                    # Flattening the nested dicts.
                    # 'Owner' is not provided if not known. Forcing it as '' into the dict so that DataFrame remains consistent in Cryptostore.
                    to = transaction.pop('to')
                    to = {('to_' + k): (to[k] if k in to else '') for k in to_from_data}
                    fro = transaction.pop('from')
                    fro = {('from_' + k): (fro[k] if k in fro else '') for k in to_from_data}
                    del transaction['symbol']  # removing duplicate data with `pair` that is added
                    # Store in buffer
                    self.buffer_transactions[query_coin].append({**transaction, **to, **fro})
                    max_trans_ts = transaction['timestamp'] if transaction['timestamp'] > max_trans_ts else max_trans_ts

                # Comments regarding `latest_cleared_ts`:
                # From doc. : "Some transactions might be reported with a small delay."
                # From mail exchange with support: "That line is there as a disclaimer in case anything goes wrong.
                # In general (99.99% of the time) transactions are added instantly."
                # Hence the 4s substracted from `receipt_time` before the `for` loop.
                # Conditions to make a chained call next time (to make sure not to miss any transactions):
                #  - latest transaction is no older than 4s,
                #  - data['count'] is 100.
                # Otherwise `latest_cleared_ts` will be used for next call (not a chained call).
                if max_trans_ts > latest_cleared_ts or data['count'] == 100:
                    self.chained_call[query_coin] = (data['cursor'], query_start_ts)
                    # Comments regarding `data['count']`:
                    # Number of results per query is limited to 100.
                    # If we have 100 results in the query, we are not certain the last result is the last transaction up to the receipt time or not.
                    # If it is lower than 100, we know there is no more transactions till the receipt time.
                    if data['count'] == 100:
                        # This `latest_cleared_ts` will not be used as start ts for the next query, but only for knowing when to do the next query.
                        latest_cleared_ts = max_trans_ts

            # If there has not been any transactions, latest know timestamp is receipt timestamp - 4s.
            if latest_cleared_ts in last_trans_up:
                last_trans_up[latest_cleared_ts].append(query_coin)
            else:
                last_trans_up[latest_cleared_ts] = [query_coin]

        # Step 3 / feed the callback with transactions for `coin` initially requested.
        if coin in self.buffer_transactions:
            # Flush data for `coin` in `self.buffer_transactions`.
            for trans in self.buffer_transactions.pop(coin):
                await self.callback(TRANSACTIONS,
                                    feed=self.id,
                                    pair=pair_exchange_to_std(coin),
                                    # `timestamp` is already with the correct format in `transaction` dict (in unit second).
                                    **trans)

        return
