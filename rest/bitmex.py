from time import sleep
import time
import hashlib
import hmac
from urllib.parse import urlparse
import argparse
import yaml

import requests
import pandas as pd


API_MAX = 500
API_REFRESH = 300


def generate_signature(verb: str, url: str, key_id: str, key_secret: str, data='') -> dict:
    """
    verb: GET/POST/PUT
    url: api endpoint
    data: body (if present)
    """
    expires = int(round(time.time()) + 5)

    parsedURL = urlparse(url)
    path = parsedURL.path
    if parsedURL.query:
        path = path + '?' + parsedURL.query

    if isinstance(data, (bytes, bytearray)):
        data = data.decode('utf8')

    message = verb + path + str(expires) + data

    signature = hmac.new(bytes(key_secret, 'utf8'), bytes(message, 'utf8'), digestmod=hashlib.sha256).hexdigest()
    return {
        "api-expires": str(expires),
        "api-key": key_id,
        "api-signature": signature
    }


def get_trades(symbol: str, start_date: str, end_date: str, key_id=None, key_secret=None) -> list:
    total_data = []

    dates = pd.interval_range(pd.Timestamp(start_date), pd.Timestamp(end_date), freq="6H").tolist()

    for interval in dates:
        start = 0

        end = interval.right
        end -= pd.Timedelta(nanoseconds=1)

        start_date = str(interval.left).replace(" ", "T") + "Z"
        end_date = str(end).replace(" ", "T") + "Z"

        while True:
            endpoint = '/api/v1/trade?symbol={}&count={}&reverse=false&start={}&startTime={}&endTime={}'.format(symbol, API_MAX, start, start_date, end_date)
            header = None
            if key_id and key_secret:
                header = generate_signature("GET", endpoint, key_id, key_secret)
            r = requests.get('https://www.bitmex.com{}'.format(endpoint), headers=header)
            try:
                limit = int(r.headers['X-RateLimit-Remaining'])
                if r.status_code != 200:
                    r.raise_for_status()
            except:
                print(r.json())
                print(r.headers)
                raise
            data = r.json()

            total_data.extend(data)

            if len(data) != API_MAX:
                break

            if limit < 1:
                sleep(API_REFRESH)

            start += len(data)

    return total_data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="BitMEX historical data loader")
    parser.add_argument("--start-date", type=str, required=True, help="Closed on Start Date")
    parser.add_argument("--end-date", type=str, required=True, help="Open on End Date")
    parser.add_argument("--symbol", type=str, required=True)
    parser.add_argument("--config", type=str, help="config path")
    args = parser.parse_args()

    key_id, key_secret = None, None
    if args.config:
        config = args.config
    else:
        config = "config.yaml"
    
    try:
        with open(config, 'r') as fp:
            data = yaml.load(fp)
            key_id = data['key_id']
            key_secret = data['key_secret']
    except:
        pass

    data = get_trades(args.symbol, args.start_date, args.end_date, key_id, key_secret)

    print("Got {} trades.".format(len(data)))
