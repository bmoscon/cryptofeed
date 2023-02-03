## Authenticated Channels

Cryptofeed has support for authenticated exchanges and authenticated data channels over websocket. Not every authenticated data channel has been implemented, so please open a ticket on GitHub if you know an exchange supports an authenticated websocket channel that you are interested in. This is a list of the currently supported authenticated channels.

| Exchange | Auth Channel | Notes |
| ---------|--------------|-------|
| Gemini   | ORDER_INFO   | Information about user's orders |
| OKX/OKCOIN | ORDER_INFO | Information about user's orders |
| Kucoin   | L2_BOOK      | Auth required to get book snapshot |
| Bequant, HitBTC | ORDER_INFO | User's order updates: new, suspended, partially filled, filled, cancelled, expired |
| Bequant, HitBTC | BALANCE | Real-time feed with balances (and changes to balances) for all non-zero wallets|
| Bequant, HitBTC | TRANSACTIONS | Real-time information on account deposits and withdrawals |
