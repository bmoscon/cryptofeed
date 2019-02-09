# Adding a new exchange

Perhaps the best way to understand the workings of the library is to walk through the addition of a new exchange. For this example, we'll 
add support for the exchange [Huobi](https://huobi.readme.io/docs/ws-api-reference). The exchange supports websocket data, so we'll 
add support for these endopoints.


### Adding a new Feed class
The first step is to define a new class, with the Feed class as the parent. By convention new feeds go into new modules, so the 
class definition will go in the `huobi` module within `cryptofeed`. 

```python
from cryptofeed.feed import Feed
from cryptofeed.defines import HUOBI


LOG = logging.getLogger('feedhandler')


class Huobi(Feed):
    id = HUOBI

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('wss://api.huobi.pro/hbus/ws', pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.__reset()

    def __reset(self):
        pass
```

We've basically just extended Feed, populated the websocket address in the parent's constructor call, and defined the `__reset` 
method, which we may or may not need (more on this later). You might notice that `HUOBI` is being imported from `defines`, so 
we'll need to add that as well:

```python
HUOBI = 'HUOBI'
```

Again by convention the exchange names in `defines.py` are all uppercase.



