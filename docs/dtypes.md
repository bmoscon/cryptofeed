# Custom Data Types

Cryptofeed uses custom data types when returning data to the client via callbacks. They are defined in [types.pyx](../cryptofeed/types.pyx). The use of these custom types allows for a few important things:

1. Every callback knows exactly what to expect (what the data type is, what fields it contains, etc).
2. The data objects can be configured to provide type checking on the fields (you need to build the library with this [line](https://github.com/bmoscon/cryptofeed/blob/master/setup.py#L40) in setup.py commented out).
3. Adding new fields to a data type requires that all other exchanges be modified at the same time, or the build will fail.
4. Fields are readonly, to prevent the client from accidentally modifying them.

In general, to access the fields in the object, you can access the data members as you would with any other Python object:

```python

trade = Trade('COINBASE', 'BTC-USD', 'buy', 1.2, 64342.12, 1634865952.143, id='23454323', type='limit')
assert trade.symbol == 'BTC-USD'
```

We can also access the data as a dictionary with the `to_dict()` method:

```python
print(trade.to_dict())


{'exchange': 'COINBASE',
 'symbol': 'BTC-USD',
 'side': 'buy',
 'amount': 1.2,
 'price': 64342.12,
 'id': '23454323',
 'type': 'limit',
 'timestamp': 1634865952.143}
```

The `to_dict()` method also supports an important kwarg: `numeric_type`. This allows us to convert numeric types to other types when constructing the dictionary.


```python
print(trade.to_dict(numeric_type=str))


{'exchange': 'COINBASE',
 'symbol': 'BTC-USD',
 'side': 'buy',
 'amount': '1.2',
 'price': '64342.12',
 'id': '23454323',
 'type': 'limit',
 'timestamp': 1634865952.143}
 
```

The `repr`, `eq` and `hash` magic methods are also defined allowing the object to printed, compared with others, and hashed. Each object also has a member called `raw` that contains the raw message from the exchange that was used to generate the object. You can use this to inspect the data and obtain additional data that may not be part of the object in question.

The datatypes currently supported by cryptofeed are:

* Trade
* Ticker
* Liquidation
* Funding
* Candle
* Index
* OpenInterest
* OrderBook
* OrderInfo
* Balance
* L1Book
* Transaction
* Fill


## The OrderBook object

The orderbook object contains some fields and data structures that may not be completely self documenting. They are described below for clarity.

The fields in the [OrderBook object](https://github.com/bmoscon/cryptofeed/blob/master/cryptofeed/types.pyx#L297) are:

* exchange
* symbol
* book
* delta
* sequence_number
* checksum
* timestamp

Let's dig into the ones that may not be completely intuitive. `delta` contains the exchange provided delta from the last book update (if the exchange provides deltas, and if this is not a snapshot update). The delta will be in the format of {BIDS: \[\], ASKS: \[\]}. If there are updates to the bid or ask sides of the books, the list will contain tuples of the changes. The changes are in the format of (price, size), so each price in the existing book should be updated to the corresponding size. A size of 0 means the level should be removed from the book.

`sequence_number` contains the exchange provided sequence number, if one if provided. Similarly, `checksum` contains the exchange provided checksum, if one is provided. You can see which exchanges privide checksums and sequence numbers in the [documentation](book_validation.md).

The `book` member contains an [orderbook](https://github.com/bmoscon/orderbook) data structure. You can access the sides of the orderbook via `.bids` and `.asks` or also via `['bids']` and `['asks']`. The object supports various forms of this, so you can use bid(s) and ask(s) as well as their variants in all-caps. Each side is an ordered dictionary that you can access with `to_dict()` or via iteration:


```python

ob = OrderBook(.......)
ob.book.bids.to_dict()  # returns dict of this side


for price in ob.book.bids:
    print(f"Price: {price} Size: {ob.book.bids[price]}")

for price in ob.book.asks:
    print(f"Price: {price} Size: {ob.book.asks[price]}")
```

Or you can access specific levels with the `index` method:

```python

print("The top level of the order book is:", ob.book.bids.index(0), ob.book.asks.index(0)
```

Note that `index` returns the price and size as a tuple.

You can also retrieve the whole book as a dictionary with `to_dict`, and like the other types, it supports `numeric_type` as well.


```python

ob.to_dict(numeric_type=float)
```
