# FAQ and Oddities

* Why does BitMEX/Deribit not have normalized symbols / I noticed BitMEX uses XBTUSD whereas other exchanges use BTC-USD - why the difference?
  - BitMEX (and Deribit) offers futures contracts, swaps and other derivative products that are bought and sold in bitcoin, which differs from other exchanges where cryptocurrencies like bitcoin are bought in other currencies like dollars (or other cryptocurrencies). For this reason, most their symbols have no analogues on other exchanges. More information [here](https://www.bitmex.com/app/perpetualContractsGuide).

* Why don't all exchanges support book deltas?
  - Only some exchanges provide delta updates. If you want a delta for the exchanges that only provide snapshots, you can calculate the delta on each update.
