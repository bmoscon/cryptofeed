#!/usr/bin/env python

from cryptofeed import FeedHandler
from cryptofeed.callback import OrderInfoCallback, AccBalancesCallback, UserFillsCallback, L1BookCallback
from cryptofeed.defines import DERIBIT, ORDER_INFO, ACC_BALANCES, USER_FILLS, L1_BOOK


async def quote(feed, symbol, bid_price, ask_price, bid_amount, ask_amount, timestamp, receipt_timestamp):
    print(f"{feed} Symbol: {symbol} Best price (amount): bid: {bid_price} ({bid_amount}) ask: {ask_price} ({ask_amount})")

async def order(feed, symbol, data: dict, receipt_timestamp):
    print(f"{feed}: {symbol}: Order update: {data}")

async def fill(feed, symbol, data: dict, receipt_timestamp):
    print(f"{feed}: {symbol}: Fill update: {data}")

async def balance(feed, currency, data: dict, receipt_timestamp):
    print(f"{feed}: {currency}: Balance update: {data}")

def main():

    f = FeedHandler(config="config.yaml")
    f.add_feed(DERIBIT,
                channels=[L1_BOOK],
                symbols=["BTC-24JUN22", "BTC-24JUN22-50000-C"],
                callbacks={L1_BOOK: L1BookCallback(quote)},
                timeout=-1
    )
    f.add_feed(DERIBIT,
                channels=[USER_FILLS, ORDER_INFO],
                symbols=["ETH-USD-PERPETUAL", "BTC-USD-PERPETUAL", "ETH-24JUN22", "BTC-24JUN22-50000-C"],
                callbacks={USER_FILLS: UserFillsCallback(fill), ORDER_INFO: OrderInfoCallback(order)},
                timeout=-1		
    )    
    f.add_feed(DERIBIT,
                channels=[ACC_BALANCES],
                symbols=['BTC', 'ETH'],
                callbacks={ACC_BALANCES: AccBalancesCallback(balance)},
	            timeout=-1
    )    

    f.run()

if __name__ == '__main__':
    main()
