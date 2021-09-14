## Book Validation Mechanisms

Some exchanges support methods for ensuring orderbooks are correct. The two most prevalent methods are sequence numbers and orderbook checksums. With sequence numbers, you can detect a missing message and reset the book/connection. With checksums you must manually calculate a checksum on the orderbook (or some subset of  the book) and compare that to the exchange provided checksum. Sequence number checking takes a negligible amount of time, whereas checksum validation can take a noticeable amount of time (0.4 to 0.8 ms). Sequence number validation is enabled on all supporting exchanges. Checksum validation must be enabled by the end user (set the `checksum_validation` kwarg to `True`). Other exchanges do not supply orderbook deltas (snapshots only), so a missing message will not result in an incorrect orderbook. This list indicates what exchanges support what features. 

<br/>
<br/>

| Exchange      | Checksum      | Sequence Numbers | Snapshots only |
| ------------- |:-------------:| :---------------:|:--------------:|
| AscendEX      |               | x                |                |
| Bequant       |               | x                |                |
| Bitcoin.com   |               | x                |                |
| Bitfinex      |               | x                |                |
| Bitstamp      |               |                  | x              |
| Bittrex       |               | x                |                |
| Blockchain.com|               | x                |                |
| Bybit         |               |                  |   x            |
| Binance       |               |   x              |                |
| BinanceUS     |               | x                |                |
| Bitflyer      |               |                  |                |
| Bithumb       |               |                  |                |
| BitMEX        |               |                  |                |
| Coinbase      |               |  x <sup>1</sup>  |                |
| Deribit       |               | x                |                |
| dYdX          |               | x <sup>2</sup>   |                |
| EXX           |               |                  |                |
| FTX           | x             |                  |                |
| FTX US        | x             |                  |                |
| Gate.io       |               |                  |                |
| Gemini        |               |                  |                |
| HitBTC        |               |  x               |                |
| Huobi         |               |                  | x              |
| Huobi DM      |               |                  |  x             |
| Huobi Swap    |               |                  |  x             |
| Kraken        |    x          |                  |                |
| Kraken Futures|               | x                |                |
| KuCoin        |               | x                |                |
| OKCoin        |  x            |                  |                |
| OKEX          |  x            |                  |                |
| Phemex        |               |                  |                |
| Poloniex      |               | x                |                |
| Probit        |               |                  |                |
| Upbit         |               |                  |     x          |


<br/>
<sup>1</sup> Coinbase sequence number validation only works when L3 books are enabled for a symbol
<br/>
<br/>
<sup>2</sup> dYdX uses offsets that monotonically increase to help ensure updates are applied in order. They are not quite the same as sequence numbers, strictly speaking
<br/>
<br/>

For even more assurance that an orderbook is in the expected state (or for use in debugging), you can enable a cross check on book updates with the `cross_check` kwarg set to `True`.  

If an exchange does not provide snapshots only, sequence numbers, or checksums, there is no guarantee that all messages have been received or that an orderbook is in the correct state. 
