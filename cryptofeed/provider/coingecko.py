'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''

import asyncio
import aiohttp
import json
from json import JSONDecodeError

from cryptofeed.defines import COINGECKO, MARKET_INFO
from cryptofeed.feed import RestFeed
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize


# Keys retained from Coingecko for `MARKET_INFO` channel.
# 'status_updates' is not in the list, but is added back in the data (see `_market_info()`)
# It is worthwhile to notice that all digit data is positive. Sometimes, Coingecko sends also null or None value,
# in which case they are then converted to -1 value, for compatibility reason with Redis stream.
MARKET_INFO_FILTER_S = ('name', 'asset_platform_id', 'contract_address')
MARKET_INFO_FILTER_D = ('sentiment_votes_up_percentage', 'sentiment_votes_down_percentage', 'market_cap_rank', 'coingecko_rank',
                        'coingecko_score', 'developer_score', 'community_score', 'liquidity_score', 'public_interest_score')
MARKET_DATA_VS_CURRENCY = ('current_price', 'market_cap', 'fully_diluted_valuation', 'total_volume', 'high_24h', 'low_24h')
OTHER_MARKET_DATA_FILTER = ('total_supply', 'max_supply', 'circulating_supply')
ALL_MARKET_DATA = (MARKET_DATA_VS_CURRENCY + OTHER_MARKET_DATA_FILTER)


class Coingecko(RestFeed):

    id = COINGECKO
    # Rate Limit: 100 requests/minute -> sleep 0.6s after previous request.
    # From support (mail exchange):
    # "May I suggest (as provided by the engineers) that you try to make approximately 50 requests per minute instead?
    # We are currently experiencing very heavy loads from certain irresponsible individuals and have temporarily stepped up security measures."
    # From testing, safer to use 3x this limit.
    sleep_time = 1.8

    def __init__(self, pairs=None, channels=None, callbacks=None, config=None, **kwargs):
        super().__init__('https://api.coingecko.com/api/v3/', pairs=pairs, channels=channels, config=config, callbacks=callbacks, **kwargs)

    async def subscribe(self):
        self.__reset()
        return

    def __reset(self):
        self.last_market_info_update = {}
        pass

    async def message_handler(self):
        async def handle(session, pair, chan):
            if chan == MARKET_INFO:
                await self._market_info(session, pair)
            await asyncio.sleep(self.sleep_time)

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

    async def _market_info(self, session, pair):
        """
        Data from /coins/{id}.
        """

        quote_c, base_c = pair.split('_')

        async with session.get(f"{self.address}coins/{quote_c}?localization=false&tickers=false&market_data=true&community_data=true&developer_data=false&sparkline=false") as response:
            data = await response.read()
            try:
                data = json.loads(data)
            except JSONDecodeError as jde:
                raise Exception('Rate limit possibly exceeded\nReturned error: {!s}\nReturned response content from HTTP request: {!s}'.format(jde, data))

            timestamp = timestamp_normalize(self.id, data['last_updated'])
            if (pair not in self.last_market_info_update) or (self.last_market_info_update[pair] < timestamp):
                self.last_market_info_update[pair] = timestamp
                # `None` and null data is systematically replaced with '-1' for digits and '' for string (empty string), for compatibility with Redis stream.
                market_data = {k: (-1 if (not v or (isinstance(v, dict) and not (base_c in v and v[base_c]))) else v if k in OTHER_MARKET_DATA_FILTER else v[base_c]) for k, v in data['market_data'].items() if k in ALL_MARKET_DATA}
                # 'last_updated' here is assumed to be specific for market data, so it is kept as well.
                market_data['last_updated'] = timestamp_normalize(self.id, data['market_data']['last_updated'])
                community_data = {k: (v if v else -1) for k, v in data['community_data'].items()}
                public_interest_stats = {k: (v if v else -1) for k, v in data['public_interest_stats'].items()}
                # Only retain selected data, and remove as well `market_data`, `community_data` and `public_interest_stats`.
                # These latter are added back in `data` to have it in the shape of a flatten dict.
                data_s = {k: (v if v else '') for k, v in data.items() if k in MARKET_INFO_FILTER_S}
                data_d = {k: (v if v else -1) for k, v in data.items() if k in MARKET_INFO_FILTER_D}
                status = str(data['status_updates'])
                data = {**data_s, **data_d, **market_data, **community_data, **public_interest_stats}
                # `list` data type is converted to string for compatibility with Redis stream.
                data['status_updates'] = status
                await self.callback(MARKET_INFO, feed=self.id,
                                    pair=pair_exchange_to_std(pair),
                                    timestamp=timestamp,
                                    **data)

        return
