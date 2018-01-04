from urllib.request import urlopen
import json


def poloniex_get_ticker_map():
    """
    mappings between pair strings and pair IDs are not documented
    so we can use their ticker endpoint which has the mappings embedded
    """
    with urlopen("https://poloniex.com/public?command=returnTicker") as url:
        data = json.loads(url.read().decode())
        print("{")
        for key in data:
            print("'{}': {},".format(key, data[key]['id']))
        print("}")

        print("[", end='')
        for key in data:
            print("'{}', ".format(key), end='')
        print("]", end='')


def bittrex_get_trading_pairs():
    with urlopen('https://bittrex.com/api/v1.1/public/getmarkets') as url:
        data = json.loads(url.read().decode())
        print("[", end='')
        for market in data['result']:
            print("'{}', ".format(market['MarketName']), end='')
        print("]", end='')


if __name__ == '__main__':
    bittrex_get_trading_pairs()