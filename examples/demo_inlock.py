from cryptofeed.exchanges import Inlock
from cryptofeed.defines import L2_BOOK, TICKER


def main():
    print('Available Pairs: ', Inlock.info()['symbols'])

    # Read OrderBook
    ilk_orderbook = Inlock().l2_book_sync(symbol='ILK-USDC')
    print("Symbol: ", ilk_orderbook.symbol)
    print("OrderBook Bids:")
    for price in ilk_orderbook.book.bids:
        print(f"Price: {price} Size: {ilk_orderbook.book.bids[price]}")
    print("\n\nOrderBook Asks:")
    for price in ilk_orderbook.book.asks:
        print(f"Price: {price} Size: {ilk_orderbook.book.asks[price]}")

    # Read Ticker
    print("\n\nTickers:")
    ilk_ticker = (Inlock().ticker_sync(symbol='ILK-USDC'))
    print(ilk_ticker)


if __name__ == '__main__':
    main()
    