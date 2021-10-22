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

The `to_dict()` method also supports an important kwarg: `as_type`. This allows us to convert numeric types to other types when constructing the dictionary.


```python
print(trade.to_dict(as_type=str))


{'exchange': 'COINBASE',
 'symbol': 'BTC-USD',
 'side': 'buy',
 'amount': '1.2',
 'price': '64342.12',
 'id': '23454323',
 'type': 'limit',
 'timestamp': 1634865952.143}
 
```

The `repr`, `eq` and `hash` magic methods are also defined allowing the object to printed, compared with others, and hashed.


## The OrderBook object
