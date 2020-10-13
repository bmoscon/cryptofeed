'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''

import asyncio
from decimal import Decimal

import aiohttp

from cryptofeed.defines import COINGECKO, PROFILE
from cryptofeed.feed import RestFeed
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize


class Coingecko(RestFeed):
    
    id = COINGECKO

    # Keys not retained from 'PROFILE' data.
    _profile_filter_out = set({'block_time_in_minutes', 'hashing_algorithm', 'categories', 'public_notice', 'description', 'links', 'image', 'country_origin'})
    _market_data_filter_out = set({'roi', 'ath', 'ath_change_percentage', 'ath_date', 'atl',
                                   'atl_change_percentage', 'atl_date', 'market_cap_rank',
                                   'price_change_24h_in_currency', 'price_change_percentage_1h_in_currency',
                                   'price_change_percentage_24h_in_currency', 'price_change_percentage_7d_in_currency',
                                   'price_change_percentage_14d_in_currency', 'price_change_percentage_30d_in_currency',
                                   'price_change_percentage_60d_in_currency', 'price_change_percentage_200d_in_currency',
                                   'price_change_percentage_1y_in_currency', 'market_cap_change_24h_in_currency',
                                   'market_cap_change_percentage_24h_in_currency'})

    def __init__(self, pairs=None, channels=None, callbacks=None, config=None, **kwargs):
        super().__init__('https://api.coingecko.com/api/v3/', pairs=pairs, channels=channels, config=config, callbacks=callbacks, **kwargs)


    async def subscribe(self):
        self.__reset()
        return


    def __reset(self):
        self.last_profile_update = {}
        pass


    async def message_handler(self):
        async def handle(session, pair, chan):
            if chan == PROFILE:
                await self._profile(session, pair)
            # Rate Limit: 100 requests/minute -> sleep 0.6s between each request 
            await asyncio.sleep(0.6)

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

        async with session.get(f"{self.address}coins/{pair}?localization=false&tickers=false\
&market_data=true&community_data=true&developer_data=false&sparkline=false") as response:
            data = await response.json()

        timestamp=timestamp_normalize(self.id, data['last_updated'])
        if (pair not in self.last_profile_update) or (self.last_profile_update[pair] < timestamp):
            self.last_profile_update[pair] = timestamp
            data = {k:v for k,v in data.items() if k not in self._profile_filter_out}
            data['market_data'] = {k:v for k,v in data['market_data'].items() if k not in self._market_data_filter_out}
            data['last_updated'] = timestamp
            await self.callback(PROFILE, feed=self.id,
                                pair=pair_exchange_to_std(pair),
                                timestamp=timestamp,
                                data=data)
        return
