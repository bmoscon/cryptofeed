'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal
from typing import Dict

from yapic import json

from cryptofeed.connection import AsyncConnection, HTTPAsyncConn
from cryptofeed.defines import COINGECKO, MARKET_INFO
from cryptofeed.feed import Feed
from cryptofeed.symbols import SYMBOL_SEP
from cryptofeed.standards import symbol_exchange_to_std, timestamp_normalize


LOG = logging.getLogger('feedhandler')

# Keys retained from Coingecko for `MARKET_INFO` channel.
# 'status_updates' is not in the list, but is added back in the data (see `_market_info()`)
# It is worthwhile to notice that all digit data is positive. Sometimes, Coingecko sends also null or None value,
# in which case they are then converted to -1 value, for compatibility reason with Redis stream.
ROOT_KEYS = {
    'sentiment_votes_up_percentage': 'up',
    'sentiment_votes_down_percentage': 'down',
    'market_cap_rank': 'capRank',
    'coingecko_rank': 'rank',
    'coingecko_score': 'score',
    'developer_score': 'developer',
    'community_score': 'community',
    'liquidity_score': 'liquidity',
    'public_interest_score': 'interest',
}
COMMUNITY_KEYS = {
    'reddit_average_posts_48h': 'redditPosts',
    'reddit_average_comments_48h': 'redditComments',
    'reddit_accounts_active_48h': 'redditAccounts',
    'telegram_channel_user_count': 'telegramUsers',
}
INTEREST_KEYS = {
    'alexa_rank': 'alexa',
    'bing_matches': 'bing',
}
MARKET_KEYS = {
    'price_change_24h': 'chgA',
    'price_change_percentage_24h': 'chgP',
    'market_cap_change_24h': 'mktCapChgA',
    'market_cap_change_percentage_24h': 'mktCapChgP',
    'total_supply': 'totSply',
    'max_supply': 'maxSply',
    'circulating_supply': 'circSply',
}
CCY_KEYS = {
    'current_price': 'px',
    'market_cap': 'mktCap',
    'fully_diluted_valuation': 'fdv',
    'total_volume': 'vol',
    'high_24h': 'high',  # Daily high
    'low_24h': 'low',    # Daily low
}

API_URL = 'https://api.coingecko.com/api/v3/coins'

QUERY_PARAMS = 'localization=false'
QUERY_PARAMS += '&tickers=false'
QUERY_PARAMS += '&market_data=true'
QUERY_PARAMS += '&community_data=true'
QUERY_PARAMS += '&developer_data=false'
QUERY_PARAMS += '&sparkline=false'


class Coingecko(Feed):
    id = COINGECKO

    # Rate Limit: 100 requests/minute -> sleep 0.6s after previous request.
    # From support (mail exchange):
    # "May I suggest (as provided by the engineers) that you try to make approximately 50 requests per minute instead?
    # We are currently experiencing very heavy loads from certain irresponsible individuals and have temporarily stepped up security measures."
    # From testing, safer to use 3x this limit.
    SLEEP_TIME = 1.8

    def __init__(self, **kwargs):
        super().__init__({}, **kwargs)
        self.last_updated = {}
        self.address = self._address()

    def _address(self):
        address: Dict[str, str] = {}
        for chan in set(self.channels or self.subscription):
            if chan != MARKET_INFO:
                continue
            for symbol_id in set(self.symbols or self.subscription[chan]):
                quote = symbol_exchange_to_std(symbol_id)
                LOG.debug('%s: Prepare quote=%s symbol_id=%s', self.id, quote, symbol_id)
                address[quote] = f'{API_URL}/{symbol_id}?{QUERY_PARAMS}'
        return address

    async def subscribe(self, conn: AsyncConnection):
        assert isinstance(conn, HTTPAsyncConn)
        conn.sleep += 0.5  # increase sleep time when we start a new HTTP polling session to limit the bit rate

    async def handle(self, data: bytes, timestamp: float, conn: AsyncConnection):
        assert isinstance(conn, HTTPAsyncConn)

        try:
            msg = json.loads(data, parse_float=Decimal)
        except Exception as why:  # json.JSONDecodeError:
            i = data.find(bytes('<div'))
            if i > 0:
                data = data[i:]
            conn.sleep += 1
            LOG.warning('%s: %r rate limit possibly exceeded => increase sleep +1 -> %s sec. Response: %s', why, conn.id, conn.sleep, data)
            return

        updated = await self._market_info(conn.ctx, msg, timestamp)

        # Adaptive sleep time
        if updated:
            conn.sleep = (9 * conn.sleep + 1) / 10  # Reduce (always greater than 1 second)
        else:
            conn.sleep += 0.01  # Increase slowly

    async def _market_info(self, ctx: dict, msg: dict, timestamp: float) -> bool:
        """Data from /coins/{id}.

        Doc: https://www.coingecko.com/api/documentations/v3#/operations/coins/get_coins__id_

        {'id': '01coin',
         'symbol': 'zoc',
         'name': '01coin',
         'asset_platform_id': None,
         'block_time_in_minutes': 0,
         'hashing_algorithm': 'NeoScrypt',
         'categories': ['Masternodes'],
         'public_notice': None,
         'additional_notices': [],
         'description': {'en': ''},
         'links': {'homepage': ['https://01coin.io/', '', ''],
                   'blockchain_site': ['https://explorer.01coin.io/', 'https://zoc.ccore.online/', 'https://openchains.info/coin/01coin', '', ''],
                   'official_forum_url': ['', '', ''],
                   'chat_url': ['https://discordapp.com/invite/wq5xD6M', '', ''],
                   'announcement_url': ['', ''],
                   'twitter_screen_name': '01CoinTeam',
                   'facebook_username': '01CoinTeam',
                   'bitcointalk_thread_identifier': 3457534,
                   'telegram_channel_identifier': 'ZOCCoinOfficial',
                   'subreddit_url': 'https://www.reddit.com/r/01coin/',
                   'repos_url': {'github': ['https://github.com/zocteam/zeroonecoin'], 'bitbucket': []}},
         'image': {'thumb': 'https://assets.coingecko.com/coins/images/5720/thumb/F1nTlw9I_400x400.jpg?1547041588',
                   'small': 'https://assets.coingecko.com/coins/images/5720/small/F1nTlw9I_400x400.jpg?1547041588',
                   'large': 'https://assets.coingecko.com/coins/images/5720/large/F1nTlw9I_400x400.jpg?1547041588'},
         'country_origin': '',
         'genesis_date': None,
         'sentiment_votes_up_percentage': Decimal('100.0'),
         'sentiment_votes_down_percentage': Decimal('0.0'),
         'market_cap_rank': 1775,
         'coingecko_rank': 746,
         'coingecko_score': Decimal('22.832'),
         'developer_score': Decimal('45.036'),
         'community_score': Decimal('14.885'),
         'liquidity_score': Decimal('1.0'),
         'public_interest_score': Decimal('0.0'),
         'market_data': { 'current_price': {'aed': Decimal('0.01842256'), 'ars': Decimal('0.414901'), 'aud': Decimal('0.
                          'roi': {'times': Decimal('-0.9101505090160869'), 'currency': 'usd', 'percentage': Decimal('-91.01505090160869')},
                          'ath': {'aed': Decimal('0.12555'), 'ars': Decimal('1.27'), 'aud': Decimal('0.04813117'), 'bch'
                          'ath_change_percentage': {'aed': Decimal('-85.37635'), 'ars': Decimal('-67.55522'), 'aud': Dec
                          'ath_date': {'aed': datetime.datetime(2018, 10, 10, 17, 27, 38, 34, tzinfo=datetime.timezone.u
                          'atl': {'aed': Decimal('0.00259466'), 'ars': Decimal('0.04442241'), 'aud': Decimal('0.00113298
                          'atl_change_percentage': {'aed': Decimal('607.60663'), 'ars': Decimal('830.83003'), 'aud': Dec
                          'atl_date': {'aed': datetime.datetime(2020, 3, 16, 10, 22, 30, 944, tzinfo=datetime.timezone.u
                          'market_cap': {'aed': 195467, 'ars': 4402240, 'aud': 69833, 'bch': Decimal('172.456'), 'bdt':
                          'market_cap_rank': 1775,
                          'fully_diluted_valuation': {},
                          'total_volume': {'aed': 49262, 'ars': 1109437, 'aud': Decimal('17596.23'), 'bch': Decimal('43.
                          'high_24h': {'aed': Decimal('0.02026924'), 'ars': Decimal('0.456461'), 'aud': Decimal('0.00724
                          'low_24h': {'aed': Decimal('0.0160679'), 'ars': Decimal('0.361171'), 'aud': Decimal('0.0057753
                          'price_change_24h': Decimal('0.00064114'),
                          'price_change_percentage_24h': Decimal('14.65599'),
                          'price_change_percentage_7d': Decimal('24.97599'),
                          'price_change_percentage_14d': Decimal('15.52352'),
                          'price_change_percentage_30d': Decimal('-21.79181'),
                          'price_change_percentage_60d': Decimal('31.1943'),
                          'price_change_percentage_200d': Decimal('182.00787'),
                          'price_change_percentage_1y': Decimal('153.21198'),
                          'market_cap_change_24h': Decimal('6585.89'),
                          'market_cap_change_percentage_24h': Decimal('14.12307'),
                          'price_change_24h_in_currency': {'aed': Decimal('0.00235466'), 'ars': Decimal('0.053445'), 'au
                          'price_change_percentage_1h_in_currency': {'aed': Decimal('-6.81616'), 'ars': Decimal('-6.8171
                          'price_change_percentage_24h_in_currency': {'aed': Decimal('14.65443'), 'ars': Decimal('14.786
                          'price_change_percentage_7d_in_currency': {'aed': Decimal('24.96748'), 'ars': Decimal('26.1088
                          'price_change_percentage_14d_in_currency': {'aed': Decimal('15.52194'), 'ars': Decimal('17.271
                          'price_change_percentage_30d_in_currency': {'aed': Decimal('-21.79287'), 'ars': Decimal('-19.0
                          'price_change_percentage_60d_in_currency': {'aed': Decimal('31.19252'), 'ars': Decimal('40.039
                          'price_change_percentage_200d_in_currency': {'aed': Decimal('182.00787'), 'ars': Decimal('240.
                          'price_change_percentage_1y_in_currency': {'aed': Decimal('153.20329'), 'ars': Decimal('250.60
                          'market_cap_change_24h_in_currency': {'aed': 24187, 'ars': 548535, 'aud': Decimal('8204.18'),
                          'market_cap_change_percentage_24h_in_currency': {'aed': Decimal('14.12152'), 'ars': Decimal('1
                          'total_supply': Decimal('65658824.0'),
                          'max_supply': None,
                          'circulating_supply': Decimal('10646360.834599'),
                          'last_updated': datetime.datetime(2020, 12, 17, 20, 24, 16, 604, tzinfo=datetime.timezone.utc)},
         'community_data': {'facebook_likes': None,
                            'twitter_followers': 334,
                            'reddit_average_posts_48h': Decimal('0.0'),
                            'reddit_average_comments_48h': Decimal('0.0'),
                            'reddit_subscribers': 15,
                            'reddit_accounts_active_48h': 7,
                            'telegram_channel_user_count': 151},
         'public_interest_stats': {'alexa_rank': 4678489, 'bing_matches': None},
         'status_updates': [],
         'last_updated': datetime.datetime(2020, 12, 17, 20, 24, 16, 604, tzinfo=datetime.timezone.utc)}
        """
        assert 'opt' in ctx
        assert isinstance(ctx['opt'], str)
        quote = ctx['opt']

        try:
            last = msg['last_updated']
            if ('last' in ctx) and (last == ctx['last']):
                return False  # Skip because already processed => Increase sleep time
            ctx['last'] = last
            if last:
                market_ts = timestamp_normalize(self.id, last)
            else:
                market_ts = 0
                LOG.info('%s: no last_updated for quote=%r - to be removed from HTTP polling', self.id, quote)  # TODO
        except Exception as why:
            LOG.warning('%s: %r - skip unexpected msg: %s', self.id, why, msg)
            return False

        mkt_data = msg.get('market_data', {})
        kwargs = {**{k2: mkt_data[k1] for k1, k2 in MARKET_KEYS.items() if k1 in mkt_data},
                  **{k2: msg[k1] for k1, k2 in ROOT_KEYS.items() if k1 in msg},
                  **{COMMUNITY_KEYS.get(k, k): v for k, v in msg.get('community_data', {}).items() if v},
                  **{INTEREST_KEYS.get(k, k): v for k, v in msg.get('public_interest_stats', {}).items() if v}}
        if 'roi' in msg:
            roi = msg.get('roi', {})
            if 'percentage' in roi:
                kwargs['roi'] = roi['percentage']

        # if kwargs:
        #     await self.callback(SCORE, feed=self.id,
        #                         pair=quote,
        #                         **kwargs,
        #                         timestamp=market_ts,
        #                         receipt_timestamp=timestamp)
        bases = set()
        for k in CCY_KEYS:
            for b in mkt_data.get(k, {}):
                bases.add(b)

        # CoinGecko may send the base ccy in double: lower and upper case
        low_up = dict()
        for b in bases:
            low_up[b.lower()] = b.upper()

        for b, B in low_up.items():
            kwargs = {}
            for k1, k2 in CCY_KEYS.items():
                data = mkt_data.get(k1)
                if not data:
                    continue
                if b in data:
                    v = data[b]
                elif B in data:
                    v = data[B]
                else:
                    continue
                if v:
                    kwargs[k2] = v
            if kwargs:
                await self.callback(MARKET_INFO, feed=self.id,
                                    pair=f'{quote}{SYMBOL_SEP}{B}',
                                    **kwargs,
                                    timestamp=market_ts,
                                    receipt_timestamp=timestamp)
