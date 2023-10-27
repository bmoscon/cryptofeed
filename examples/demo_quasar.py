from cryptofeed import FeedHandler
from cryptofeed.exchanges import *
from cryptofeed.backends.quasar import *


def main():
    f = FeedHandler()
    
    f.add_feed(Binance(symbols=['BTC-USDT'], channels=[TRADES], callbacks={TRADES: TradeQuasar()}))
    f.add_feed(Coinbase(channels=[TICKER], symbols=['BTC-USD'], callbacks={TICKER: TickerQuasar()}))
    f.add_feed(Binance(candle_closed_only=False, channels=[CANDLES], symbols=['BTC-USDT'], callbacks={CANDLES: CandlesQuasar()}))
    
    f.run()

if __name__ == '__main__':
    main()