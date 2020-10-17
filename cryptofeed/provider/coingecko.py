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


# Keys retained from Coingecko for `PROFILE` channel.
# 'status_updates' is not in the list, but if a not empty list, is added back in the data (see `_profile()`)
profile_filter = ('name', 'asset_platform_id', 'contract_address', 'sentiment_votes_up_percentage',
                  'sentiment_votes_down_percentage', 'market_cap_rank', 'coingecko_rank', 'coingecko_score',
                  'developer_score', 'community_score', 'liquidity_score', 'public_interest_score')
market_data_vs_currency = ('current_price', 'market_cap', 'fully_diluted_valuation', 'total_volume', 'high_24h', 'low_24h')
other_market_data_filter = ('price_change_percentage_24h', 'market_cap_change_percentage_24h', 'total_supply', 'max_supply',
                            'circulating_supply', 'last_updated')

class Coingecko(RestFeed):
    
    id = COINGECKO

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

        quote_c, base_c = pair.split('_')

        async with session.get(f"{self.address}coins/{quote_c}?localization=false&tickers=false\
&market_data=true&community_data=true&developer_data=false&sparkline=false") as response:
            data = await response.json()

        timestamp=timestamp_normalize(self.id, data['last_updated'])
        if (pair not in self.last_profile_update) or (self.last_profile_update[pair] < timestamp):
            self.last_profile_update[pair] = timestamp
            # `None` and null data is systematically removed for compatibility with Redis stream.
            market_data = {k:data['market_data'][k][base_c] for k in market_data_vs_currency if (base_c in data['market_data'][k] and data['market_data'][k][base_c])}
            other_market_data = {k:data['market_data'][k] for k in other_market_data_filter if data['market_data'][k]}
            community_data = {k:v for k,v in data['community_data'].items() if v}
            public_interest_stats = {k:v for k,v in data['public_interest_stats'].items() if v}
            # Only retain selected data, and remove as well `market_data`, `community_data` and `public_interest_stats`.
            # These latter are added back in `data` to have it in the shape of a flatten dict.
            data = {k:v for k,v in data.items() if (k in profile_filter and v)}
            data = {**data, **market_data, **other_market_data, **community_data, **public_interest_stats}
            # `list` data type is converted to string for compatibility with Redis stream.
            if 'status_updates' in data:
                data['status_updates'] = str(data['status_updates'])
            await self.callback(PROFILE, feed=self.id,
                                pair=pair_exchange_to_std(pair),
                                timestamp=timestamp,
                                **data)
        return
