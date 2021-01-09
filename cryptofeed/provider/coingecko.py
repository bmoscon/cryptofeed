'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from decimal import Decimal
from typing import Tuple, Callable, List

from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import COINGECKO, MARKET_INFO
from cryptofeed.feed import Feed
from cryptofeed.standards import timestamp_normalize


# Keys retained from Coingecko for `MARKET_INFO` channel.
# 'status_updates' is not in the list, but is added back in the data (see `_market_info()`)
# It is worthwhile to notice that all digit data is positive. Sometimes, Coingecko sends also null or None value,
# in which case they are then converted to -1 value, for compatibility reason with Redis stream.
MARKET_INFO_FILTER_S = {'name', 'asset_platform_id', 'contract_address'}
MARKET_INFO_FILTER_D = {'sentiment_votes_up_percentage', 'sentiment_votes_down_percentage', 'market_cap_rank', 'coingecko_rank',
                        'coingecko_score', 'developer_score', 'community_score', 'liquidity_score', 'public_interest_score'}
MARKET_DATA_VS_CURRENCY = {'current_price', 'market_cap', 'fully_diluted_valuation', 'total_volume', 'high_24h', 'low_24h'}
OTHER_MARKET_DATA_FILTER = {'total_supply', 'max_supply', 'circulating_supply'}
ALL_MARKET_DATA = set(list(MARKET_DATA_VS_CURRENCY) + list(OTHER_MARKET_DATA_FILTER))


class Coingecko(Feed):

    id = COINGECKO
    # Rate Limit: 100 requests/minute -> sleep 0.6s after previous request.
    # From support (mail exchange):
    # "May I suggest (as provided by the engineers) that you try to make approximately 50 requests per minute instead?
    # We are currently experiencing very heavy loads from certain irresponsible individuals and have temporarily stepped up security measures."
    # From testing, safer to use 3x this limit.
    sleep_time = 1.8

    def __init__(self, symbols=None, subscription=None, **kwargs):
        self.currencies = defaultdict(list)

        if symbols:
            for symbol in symbols:
                base, quote = symbol.split("-")
                self.currencies[base].append(quote.lower())
            symbols = list(self.currencies.keys())

        if subscription and MARKET_INFO in subscription:
            for symbol in subscription[MARKET_INFO]:
                base, quote = symbol.split("-")
                self.currencies[base].append(quote.lower())
            subscription[MARKET_INFO] = list(self.currencies.keys())

        super().__init__('https://api.coingecko.com/api/v3/', symbols=symbols, subscription=subscription, **kwargs)
        self.__reset()

    def __reset(self):
        self.last_market_info_update = defaultdict(float)

    async def subscribe(self, connection: AsyncConnection):
        pass

    def connect(self) -> List[Tuple[AsyncConnection, Callable[[None], None], Callable[[str, float], None]]]:
        addrs = []
        for chan in self.channels if self.channels else self.subscription:
            for pair in self.symbols if not self.subscription else self.subscription[chan]:
                if chan == MARKET_INFO:
                    addrs.append(f"{self.address}coins/{pair}?localization=false&tickers=false&market_data=true&community_data=true&developer_data=false&sparkline=false")
        return [(AsyncConnection(addrs, self.id, delay=self.sleep_time * 2, sleep=self.sleep_time), self.subscribe, self.message_handler)]

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg = json.loads(msg, parse_float=Decimal)
        await self._market_info(msg, timestamp)

    async def _market_info(self, msg: dict, receipt_timestamp: float):
        """
        Data from /coins/{id}.
        """
        symbol = msg['symbol'].upper()
        timestamp = timestamp_normalize(self.id, msg['last_updated'])

        if self.last_market_info_update[symbol] < timestamp:
            self.last_market_info_update[symbol] = timestamp
            # `None` and null data is systematically replaced with '-1' for digits and '' for string (empty string), for compatibility with Redis stream.
            market_data = {}
            for key, value in msg['market_data'].items():
                if key not in ALL_MARKET_DATA:
                    continue
                if key in MARKET_DATA_VS_CURRENCY:
                    for cur, price in value.items():
                        if cur not in self.currencies[symbol]:
                            continue
                        market_data[f"{key}_{cur}"] = price
                else:
                    market_data[key] = value
            # 'last_updated' here is assumed to be specific for market data, so it is kept as well.
            market_data['last_updated'] = timestamp_normalize(self.id, msg['market_data']['last_updated'])
            community_data = {k: (v if v else -1) for k, v in msg['community_data'].items()}
            public_interest_stats = {k: (v if v else -1) for k, v in msg['public_interest_stats'].items()}
            # Only retain selected data, and remove as well `market_data`, `community_data` and `public_interest_stats`.
            # These latter are added back in `data` to have it in the shape of a flatten dict.
            data_s = {k: (v if v else '') for k, v in msg.items() if k in MARKET_INFO_FILTER_S}
            data_d = {k: (v if v else -1) for k, v in msg.items() if k in MARKET_INFO_FILTER_D}
            status = str(msg['status_updates'])
            data = {**data_s, **data_d, **market_data, **community_data, **public_interest_stats}
            # `list` data type is converted to string for compatibility with Redis stream.
            data['status_updates'] = status
            await self.callback(MARKET_INFO, feed=self.id,
                                symbol=symbol,
                                timestamp=timestamp,
                                **data)
