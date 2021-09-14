'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from datetime import datetime as dt
from typing import Dict, Tuple, Union

from cryptofeed.defines import FUTURES, FX, OPTION, PERPETUAL, SPOT, CALL, PUT, CURRENCY


class Symbol:
    symbol_sep = '-'

    def __init__(self, base: str, quote: str, type=SPOT, strike_price=None, option_type=None, expiry_date=None):
        if type == OPTION:
            if option_type not in (CALL, PUT):
                raise ValueError("option_type must be either CALL or PUT")
            if strike_price is None:
                raise ValueError("Missing value for strike_price")
        if type in (FUTURES, OPTION) and expiry_date is None:
            raise ValueError("Missing value for expiry_date")

        self.quote = quote
        self.base = base
        self.type = type
        self.option_type = option_type
        self.strike_price = strike_price

        if expiry_date:
            self.expiry_date = self.date_format(expiry_date)

    @staticmethod
    def month_code(month: str) -> str:
        ret = ['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z']
        return ret[int(month) - 1]

    @staticmethod
    def date_format(date):
        if isinstance(date, (int, float)):
            date = dt.fromtimestamp(date)
        if isinstance(date, dt):
            year = str(date.year)[2:]
            month = Symbol.month_code(date.month)
            day = date.day
            return f"{year}{month}{day}"

        if len(date) == 4:
            year = str(dt.now().year)[2:]
            date = year + date
        if len(date) == 6:
            year = date[:2]
            month = Symbol.month_code(date[2:4])
            day = date[4:]
            return f"{year}{month}{day}"

        if len(date) == 9:
            year, month, day = date[-2:], date[2:5], date[:2]
            months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
            month = Symbol.month_code(months.index(month) + 1)
            return f"{year}{month}{day}"

        raise ValueError(f"Unable to parse expiration date: {date}")

    @property
    def normalized(self) -> str:
        if self.base == self.quote:
            base = self.base
        else:
            base = f"{self.base}{self.symbol_sep}{self.quote}"
        if self.type == SPOT:
            return base
        if self.type == OPTION:
            return f"{base}{self.symbol_sep}{self.strike_price}{self.symbol_sep}{self.expiry_date}{self.symbol_sep}{self.option_type}"
        if self.type == FUTURES:
            return f"{base}{self.symbol_sep}{self.expiry_date}"
        if self.type == PERPETUAL:
            return f"{base}{self.symbol_sep}PERP"
        if self.type == CURRENCY:
            return base
        if self.type == FX:
            return f"{base}{self.symbol_sep}FX"
        raise ValueError(f"Unsupported symbol type: {self.type}")


class _Symbols:
    def __init__(self):
        self.data = {}

    def clear(self):
        self.data = {}

    def load_all(self):
        from cryptofeed.exchanges import EXCHANGE_MAP

        for _, exchange in EXCHANGE_MAP.items():
            exchange.symbols(refresh=True)

    def set(self, exchange: str, normalized: dict, exchange_info: dict):
        self.data[exchange] = {}
        self.data[exchange]['normalized'] = normalized
        self.data[exchange]['info'] = exchange_info

    def get(self, exchange: str) -> Tuple[Dict, Dict]:
        return self.data[exchange]['normalized'], self.data[exchange]['info']

    def populated(self, exchange: str) -> bool:
        return exchange in self.data

    def find(self, symbol: Union[str, Symbol]):
        ret = []

        if isinstance(symbol, Symbol):
            symbol = symbol.normalized
        for exchange, data in self.data.items():
            if symbol in data['normalized']:
                ret.append(exchange)
        return ret


Symbols = _Symbols()
