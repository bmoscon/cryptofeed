from cryptofeed import FeedHandler
from cryptofeed.exchanges import *
from cryptofeed.backends.quasar import *


def main():
    f = FeedHandler()    
    pairs = BinanceFutures.symbols[:1]
    f.add_feed(BinanceFutures(symbols=pairs, channels=[FUNDING], callbacks={FUNDING: FundingQuasar()}))
    f.add_feed(Binance(candle_closed_only=False, channels=[CANDLES], symbols=['BTC-USDT'], callbacks={CANDLES: CandlesQuasar()}))
    f.add_feed(Coinbase(symbols=['BTC-USD'], channels=[TRADES], callbacks={TRADES: TradeQuasar()}))
    f.add_feed(Coinbase(channels=[TICKER], symbols=['BTC-USD'], callbacks={TICKER: TickerQuasar()}))
    
    f.run()

if __name__ == '__main__':
    main()