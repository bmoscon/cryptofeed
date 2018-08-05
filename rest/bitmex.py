from time import sleep
import time
import hashlib
import hmac
from urllib.parse import urlparse
import argparse

import requests
import pandas as pd


API_MAX = 500
API_REFRESH = 300


def generate_signature(verb: str, url: str, data='') -> dict:
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

    signature = hmac.new(bytes(key, 'utf8'), bytes(message, 'utf8'), digestmod=hashlib.sha256).hexdigest()
    return {
        "api-expires": str(expires),
        "api-key": key_id,
        "api-signature": signature
    }
  
  
  def get_trades(symbol: str, start_date: str, end_date: str) -> list:
    total_data = []

    dates = pd.interval_range(pd.Timestamp(start_date), pd.Timestamp(end_date), freq="6H").tolist()

    for interval in dates:
        start = 0

        end = interval.right
        end -= pd.Timedelta(nanoseconds=1)

        start_date = str(interval.left).replace(" ", "T") + "Z"
        end_date = str(end).replace(" ", "T") + "Z"

        print(start_date)
        print(end_date)
        while True:
            endpoint = '/api/v1/trade?symbol={}&count={}&reverse=false&start={}&startTime={}&endTime={}'.format(symbol, API_MAX, start, start_date, end_date)
            header = generate_signature("GET", endpoint)
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
    args = parser.parse_args()

    data = get_trades(args.symbol, args.start_date, args.end_date)
    
    print(data[-1])
    print("Got {} trades.".format(len(data)))
    
