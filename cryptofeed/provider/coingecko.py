'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
import string
from typing import Dict, Tuple, Callable, List

from yapic import json

from cryptofeed.connection import AsyncConnection, HTTPPoll
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
    symbol_endpoint = 'https://api.coingecko.com/api/v3/coins/list'

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        intermediate = defaultdict(list)
        # First pass: generate & compare normalized symbol/name, and then select the most pertinent
        for coin in data:
            normalized = coingecko_normalize_all(coin)
            intermediate[normalized].append(coin)
            # Above line keeps together the coins having the same normalized symbol.
            # To reduce collision, the coin['name'] is sometimes used in lieu of the coin['symbol'].
            # The coin['name'] is not capitalized because lower case letters may be meaningful: cETH, yUSD, DATx, zLOT

        final = coingecko_second_pass(intermediate)
        return coingecko_third_pass(final), {}

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
        for chan in self.subscription:
            for pair in self.subscription[chan]:
                if chan == MARKET_INFO:
                    addrs.append(f"{self.address}coins/{pair}?localization=false&tickers=false&market_data=true&community_data=true&developer_data=false&sparkline=false")
        return [(HTTPPoll(addrs, self.id, delay=self.sleep_time * 2, sleep=self.sleep_time), self.subscribe, self.message_handler)]

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg = json.loads(msg)
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
                    market_data[key] = value if value else -1
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


def coingecko_normalize_symbol(symbol: str) -> str:
    # keep digits, letters and dots, replace others by space
    symbol = ''.join(c if c.isalnum() or c in ('.', '+') else ' ' for c in symbol)
    return coingecko_normalize(symbol.upper())


def coingecko_normalize_name(name: str) -> str:
    # keep digits and letters, replace others by space (except when only composed by upper case letters, digits and dots)
    if not all(c.isupper() or c.isdigit() or c == '.' for c in name):
        name = ''.join(c if c.isalnum() else ' ' for c in name)
    return coingecko_normalize(name)


def coingecko_normalize(sym: str) -> str:
    sym = sym.strip()
    # do not concatenate numbers => separate them with a dot
    sym = list(sym)
    if len(sym) > 4:
        for i in range(2, len(sym) - 1):
            if sym[i] == ' ' and sym[i - 1].isdigit() and sym[i + 1].isdigit():
                sym[i] = '.'
    sym = ''.join(sym)
    # concatenate space-separated words => use CamelCase to distinguish the words
    if ' ' in sym:
        if sum(c.islower() for c in sym):  # if there is at least one lower case letter
            sym = ' '.join(word[0].upper() + word[1:] for word in sym.split())  # Just capitalize initial letter of each word
        else:  # CoinGecko may provide full upper-case as for "THE STONE COIN"
            sym = string.capwords(sym)  # capwords converts "THE STONE COIN" to "The Stone Coin"
        sym = sym.replace(' ', '')  # concatenate words
    return sym


def is_name_short(coin: dict) -> bool:
    """return True if the coin name is enough short compared to the coin symbol."""
    return len(coin['name']) <= max(5, len(coin['symbol']) + 1)


def has_many_caps(name: str) -> bool:
    """return True if the symbol contains enough upper case letters, False if empty."""
    return str and sum(c.islower() for c in name) < (len(name) / 2)


def coingecko_normalize_all(coin: dict):
    SYMBOL_TO_NORMALIZED = {'miota': 'IOTA'}
    normalized = SYMBOL_TO_NORMALIZED.get(coin['symbol'])
    if normalized:
        coin['ns'] = coin['nn'] = normalized
        return normalized

    # ns = normalized symbol, nn = normalized name
    coin['ns'] = coingecko_normalize_symbol(coin['symbol'])

    ID_SUFFIX = '-bitcoin-token'
    if coin['id'][-len(ID_SUFFIX):] == ID_SUFFIX:
        coin['nn'] = 'BTC' + coin['ns']
        return coin['nn']

    name = coin['name']

    prefixes = ('The ', 'the ')
    for p in prefixes:
        if name[:len(p)] == p:
            coin['reduced-name'] = True
            name = name[len(p):]
            break

    suffixes = ('coin', 'coins', 'money', 'finance', 'protocol', 'reward', 'rewards', 'token')
    for s in suffixes:
        if len(name) > len(s) and name[-len(s):].lower() == s:
            # but keep suffix when lower-case concatenated
            if name[-len(s)].islower() and name[-len(s) - 1] != ' ':
                continue
            # also keep suffix to avoid confusing nam: "Bitcoin Token" -> "Bitcoin"
            if name[:-len(s)].strip().lower() == 'bitcoin':
                continue
            coin['reduced-name'] = True
            name = name[:-len(s)]
            break

    coin['nn'] = coingecko_normalize_name(name)

    if len(coin['nn']) < len(coin['ns']):
        if 'reduced-name' in coin:
            coin['reduced-name'] = False
            name = coin['name']
            coin['nn'] = coingecko_normalize_name(name)
        elif not has_many_caps(name):
            return coin['ns']

    if not coin['ns']:  # coin['symbol'] may be an emoji that is striped when normalized
        return coin['nn']

    if coin.get('reduced-name') and coin['ns'].upper() != coin['nn'].upper():
        return coin['ns']

    i = coin['nn'].find('.')  # if there is a dot in normalized name => prefer the normalized symbol
    if i >= 0:
        if i > 1 and coin['nn'][i - 1].isdigit() and coin['nn'][i + 1].isdigit():
            pass  # except when the dot separates digits
        else:
            return coin['ns']

    if is_name_short(coin) and has_many_caps(name):
        return coin['nn']

    if 1.5 * len(coin['ns']) > len(coin['nn']) and any(c.islower() for c in coin['ns']):
        return coin['nn']

    return coin['ns']


def coingecko_second_pass(intermediate: Dict[str, List[dict]]) -> Dict[str, List[dict]]:
    # Second pass: fixes most of the symbol collisions
    final = defaultdict(list)
    for normalized, coins in intermediate.items():
        if len(coins) == 1:
            final[normalized].append(coins[0])
            continue
        set_normalized = False
        for i in range(len(coins)):
            if normalized == coins[i]['nn']:
                coin = coins.pop(i)
                final[normalized].append(coin)
                set_normalized = True
                break
        rest: List[dict] = []
        for coin in coins:
            if '%' in coin['name']:
                if len(coins) == 1:
                    n = coin['ns']
                else:
                    n = coingecko_normalize_name(coin['id'])
                final[n].append(coin)
            else:
                rest.append(coin)
        if not rest:
            continue
        if not set_normalized:
            rest.sort(key=lambda coin: len(coin['nn']), reverse=True)  # sort by the length of the normalized name
            coin = rest.pop(0)
            final[normalized].append(coin)
        for coin in rest:
            if coin['nn'] not in intermediate:
                n = coin['nn']
            elif coin.get('reduced-name'):
                n = coingecko_normalize_name(coin['name'])
            else:
                n = coingecko_normalize_name(coin['id'])
            final[n].append(coin)
    return final


def coingecko_third_pass(final: Dict[str, List[dict]]) -> Dict[str, str]:
    # Third pass: fixes some remaining collisions and fills the result
    symbols = {}
    for normalized, coins in final.items():
        if len(coins) == 1:
            symbols[normalized] = coins[0]['id']
            continue
        set_normalized = False
        for i in range(len(coins)):
            if normalized == coins[i]['nn']:
                coin = coins.pop(i)
                symbols[normalized] = coin['id']
                set_normalized = True
                break
        rest: List[dict] = []
        for coin in coins:
            if '%' in coin['name']:
                if len(coins) == 1:
                    n = coin['ns']
                else:
                    n = coingecko_normalize_name(coin['id'])
                symbols[n] = coin['id']
            else:
                rest.append(coin)
        if not rest:
            continue
        if not set_normalized:
            rest.sort(key=lambda coin: len(coin['nn']), reverse=True)  # sort by the length of the normalized name
            coin = rest.pop(0)
            symbols[normalized] = coin['id']
        for coin in rest:
            if coin['nn'] not in final:
                n = coin['nn']
            elif coin.get('reduced-name'):
                n = coingecko_normalize_name(coin['name'])
            else:
                n = coingecko_normalize_name(coin['id'])
            symbols[n] = coin['id']
    return symbols
