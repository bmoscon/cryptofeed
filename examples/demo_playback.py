'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import os
import glob

from cryptofeed.defines import COINBASE, L2_BOOK, TRADES, TICKER, BID, ASK
from cryptofeed.raw_data_collection import playback


async def ticker(ticker, receipt_timestamp):
    print(f'Timestamp: {ticker.timestamp} Exchange: {ticker.exchange} Symbol: {ticker.symbol} Bid: {ticker.bid} Ask: {ticker.ask}')


async def trade(trade, receipt_timestamp):
    print(f"Timestamp: {trade.timestamp} Cryptofeed Receipt: {receipt_timestamp} Exchange: {trade.exchange} Symbol: {trade.symbol} ID: {trade.id} Side: {trade.side} Amount: {trade.amount} Price: {trade.price}")


async def book(update, receipt_timestamp):
    print(f'Timestamp: {update.timestamp} Exchange: {update.exchange} Symbol: {update.symbol} Book Bid Size is {len(update.book[BID])} Ask Size is {len(update.book[ASK])}')


def main():
    dir = os.path.dirname(os.path.realpath(__file__))
    pcaps = glob.glob(f"{dir}/../sample_data/COINBASE*")
    print(pcaps)
    stats = playback(COINBASE, pcaps, callbacks={L2_BOOK: book, TICKER: ticker, TRADES: trade})

    print("\nPlayback complete!")
    print(stats)


if __name__ == '__main__':
    main()
