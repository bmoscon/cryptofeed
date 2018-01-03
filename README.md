# Cryptocurrency Feed Handler
[![License](https://img.shields.io/badge/license-XFree86-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.5+-green.svg)](LICENSE)

Uses asyncio to handle multiple feeds and return normalized and standardized results across exchanges to client registered callbacks for events like trades, book updates, ticker updates, etc.

Supports the following exchanges:
* Bitfinex
* GDAX
* Poloniex
* Gemini

Also provides a synthetic NBBO (National Best Bid/Offer) feed that aggregates the best bids and asks from the user specified feeds.
