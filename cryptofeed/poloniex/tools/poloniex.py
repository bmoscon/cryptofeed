from urllib.request import urlopen
import json


def get_ticker_map():
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


if __name__ == '__main__':
    get_ticker_map()