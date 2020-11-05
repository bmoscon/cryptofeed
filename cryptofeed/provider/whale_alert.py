'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com
Please see the LICENSE file for the terms and conditions
associated with this software.
'''

import asyncio
import aiohttp

from cryptofeed.defines import COINGECKO, PROFILE
from cryptofeed.feed import RestFeed
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize


class WhaleAlert(RestFeed):
    
    id = WHALE_ALERT

    def __init__(self, pairs=None, channels=None, callbacks=None, config=None, **kwargs):
        self.api_key=api_key
        self.sleep_time=kwargs[sleep_time] if sleep_time in kwargs else 6     # Free plan is one request every 6 seconds.
        self.max_history=kwargs[max_history] if max_history in kwargs else 1  # Free plan is 1 hour transaction history.
        self.min_value=kwargs[min_value] if min_value in kwargs else 500000   # Free plan is 500k$ transaction minimum value
        super().__init__('https://api.whale-alert.io/v1/', pairs=pairs, channels=channels, config=config, callbacks=callbacks, **kwargs)

    async def subscribe(self):
        self.__reset()
        return


    def __reset(self):
        # Dict storing per coin the timestamp of the last known transaction.
        self.last_transaction_update = {}
        pass

# ToDo
    async def message_handler(self):
        async def handle(session, pair, chan):
            if chan == PROFILE:
                await self._profile(session, pair)
            if self.cooling:
                # If Coingecko API goes crazy, let's cool it down by waiting for 10s.
                await asyncio.sleep(10)
                self.cooling=False
            else:
                # Rate Limit: 100 requests/minute -> sleep 0.6s after previous request.
                # From testing, need to use 3x this limit.
                await asyncio.sleep(1.8)

        async with aiohttp.ClientSession() as session:
            if self.config:
                for chan in self.config:
                    for pair in self.config[chan]:
                        await handle(session, pair, chan)
            else:
                for chan in self.channels:
                    for pair in self.pairs:
                        await handle(session, pair, chan)
        return


    async def _profile(self, session, pair):
        """
        Data from /coins/{id}.
        """

        quote_c, base_c = pair.split('_')

        async with session.get(f"{self.address}coins/{quote_c}?localization=false&tickers=false\
&market_data=true&community_data=true&developer_data=false&sparkline=false") as response:
            data = await response.json()

            try:
                timestamp=timestamp_normalize(self.id, data['last_updated'])
                if (pair not in self.last_profile_update) or (self.last_profile_update[pair] < timestamp):
                    self.last_profile_update[pair] = timestamp
                    # `None` and null data is systematically replaced with '-1' for digits and '' for string (empty string), for compatibility with Redis stream.
                    market_data = {k:(-1 if (not v or (isinstance(v,dict) and not (base_c in v and v[base_c]))) else v if k in other_market_data_filter else v[base_c]) for k,v in data['market_data'].items() if k in all_market_data}
                    # 'last_updated' here is assumed to be specific for market data, so it is kept as well.
                    market_data['last_updated']=timestamp_normalize(self.id, data['market_data']['last_updated'])
                    community_data = {k:(v if v else -1) for k,v in data['community_data'].items()}
                    public_interest_stats = {k:(v if v else -1) for k,v in data['public_interest_stats'].items()}
                    # Only retain selected data, and remove as well `market_data`, `community_data` and `public_interest_stats`.
                    # These latter are added back in `data` to have it in the shape of a flatten dict.
                    data_s = {k:(v if v else '') for k,v in data.items() if k in profile_filter_s}
                    data_d = {k:(v if v else -1) for k,v in data.items() if k in profile_filter_d}
                    status = str(data['status_updates'])
                    data = {**data_s, **data_d, **market_data, **community_data, **public_interest_stats}
                    # `list` data type is converted to string for compatibility with Redis stream.
                    data['status_updates'] = status
                    await self.callback(PROFILE, feed=self.id,
                                        pair=pair_exchange_to_std(pair),
                                        timestamp=timestamp,
                                        **data)
            except KeyError as ke:
                LOG.warning("Coingecko API going crazy.\n{!s}\nResponse returned:\n{!s}\n".format(ke, str(data)))
                self.cooling = True
                pass

        return