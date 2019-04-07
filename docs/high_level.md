# Cryptofeed High Level Overview

Cryptofeed is composed of the following components:

* Feedhandler
* Exchange Interfaces
* Callbacks
* Backends


### Feedhandler

The feedhandler is the main object that a user of the library will configure. It has the following methods:

* `add_feed`
* `add_nbbo`
* `run`

`add_feed`is the main method used to register an exchange with the feedhandler. You can supply an Exchange object, or a string matching the exchange's name (all uppercase). Currently if you wish to add multiple exchanges, you must call add_feed multiple times (one per exchange).

`add_nbbo` lets you compose your own NBBO data feed. It takes the arguments `feeds`, `pairs` and `callback`, which are the normal arguments you'd supply for exchnage objects when supplied to the feed handler. The exhanges in the `feeds` list will subscribe to the `pairs` and NBBO updates will be supplied to the `callback` method as they are received from the exchanges.


### Exchange Interface

The exchange objects are supplied with the following arguments:

* `channels`
* `pairs`
* `config`
* `callbacks`

`channels` are the data channels for which you are interested in receiving updates. Examples are TRADES, TICKER, and L2_BOOK. Not all exchanges support all channels. `pairs` are the trading pairs. Every pair in `pairs` will subscribed to every channel in `channels`. If you wish to create a most custom subscription, use the `config` option.

Trading pairs follow the following scheme BASE-QUOTE. As an example, Bitcoin denominated by US Dollars would be BTC-USD. Many exchanges do not internally use this format, but cryptofeed handles trading pair normalization and all pairs should be subscribed to in this format and will be reported in this format. 

If you use `channels` and `pairs` you cannot use `config`, likewise if `config` is supplied you cannot use `channels` and `pairs`. `config` is supplied in a dictionary format, in the following manner: {CHANNEL: [trading pairs], ... }


