'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''

_std_trading_pairs = {
    'BTC-USD': {
        'GDAX': 'BTC-USD',
        'BITFINEX': 'tBTCUSD',
        'GEMINI': 'BTCUSD',
        'HITBTC': 'BTCUSD'
    },
    'ETH-USD': {
        'GEMINI': 'ETHUSD',
        'GDAX': 'ETH-USD',
        'BITFINEX': 'tETHUSD'
    },
    'ETH-BTC': {
        'GEMINI': 'ETHBTC',
        'GDAX': 'ETH-BTC',
        'BITFINEX': 'tETHBTC'
    },
    'BCH-USD': {
        'GDAX': 'BCH-USD',
        'BITFINEX': 'tBCHUSD'
    },
    'LTC-EUR': {
        'GDAX': 'LTC-EUR'
    },
    'LTC-USD': {
        'GDAX': 'LTC-USD',
        'BITFINEX': 'tLTCUSD'
    },
    'LTC-BTC': {
        'GDAX': 'LTC-BTC',
        'BITFINEX': 'tLTCBTC'
    },
    'ETH-EUR': {
        'GDAX': 'ETH-EUR'
    },
    'BTC-GBP': {
        'GDAX': 'BTC-GBP'
    },
    'BTC-EUR': {
        'GDAX': 'BTC-EUR',
        'BITFINEX': 'tBTCEUR'
    },
    'BTC-BCN': {
        'POLONIEX': 'BTC_BCN'
    },
    'BTC-BELA': {
        'POLONIEX': 'BTC_BELA'
    },
    'BTC-BLK': {
        'POLONIEX': 'BTC_BLK'
    },
    'BTC-BTCD': {
        'POLONIEX': 'BTC_BTCD'
    },
    'BTC-BTM': {
        'POLONIEX': 'BTC_BTM'
    },
    'BTC-BTS': {
        'POLONIEX': 'BTC_BTS'
    },
    'BTC-BURST': {
        'POLONIEX': 'BTC_BURST'
    },
    'BTC-CLAM': {
        'POLONIEX': 'BTC_CLAM'
    },
    'BTC-DASH': {
        'POLONIEX': 'BTC_DASH'
    },
    'BTC-DGB': {
        'POLONIEX': 'BTC_DGB'
    },
    'BTC-DOGE': {
        'POLONIEX': 'BTC_DOGE'
    },
    'BTC-EMC2': {
        'POLONIEX': 'BTC_EMC2'
    },
    'BTC-FLDC': {
        'POLONIEX': 'BTC_FLDC'
    },
    'BTC-FLO': {
        'POLONIEX': 'BTC_FLO'
    },
    'BTC-GAME': {
        'POLONIEX': 'BTC_GAME'
    },
    'BTC-GRC': {
        'POLONIEX': 'BTC_GRC'
    },
    'BTC-HUC': {
        'POLONIEX': 'BTC_HUC'
    },
    'BTC-LTC': {
        'POLONIEX': 'BTC_LTC'
    },
    'BTC-MAID': {
        'POLONIEX': 'BTC_MAID'
    },
    'BTC-OMNI': {
        'POLONIEX': 'BTC_OMNI'
    },
    'BTC-NAV': {
        'POLONIEX': 'BTC_NAV'
    },
    'BTC-NEOS': {
        'POLONIEX': 'BTC_NEOS'
    },
    'BTC-NMC': {
        'POLONIEX': 'BTC_NMC'
    },
    'BTC-NXT': {
        'POLONIEX': 'BTC_NXT'
    },
    'BTC-PINK': {
        'POLONIEX': 'BTC_PINK'
    },
    'BTC-POT': {
        'POLONIEX': 'BTC_POT'
    },
    'BTC-PPC': {
        'POLONIEX': 'BTC_PPC'
    },
    'BTC-RIC': {
        'POLONIEX': 'BTC_RIC'
    },
    'BTC-STR': {
        'POLONIEX': 'BTC_STR'
    },
    'BTC-SYS': {
        'POLONIEX': 'BTC_SYS'
    },
    'BTC-VIA': {
        'POLONIEX': 'BTC_VIA'
    },
    'BTC-XVC': {
        'POLONIEX': 'BTC_XVC'
    },
    'BTC-VRC': {
        'POLONIEX': 'BTC_VRC'
    },
    'BTC-VTC': {
        'POLONIEX': 'BTC_VTC'
    },
    'BTC-XBC': {
        'POLONIEX': 'BTC_XBC'
    },
    'BTC-XCP': {
        'POLONIEX': 'BTC_XCP'
    },
    'BTC-XEM': {
        'POLONIEX': 'BTC_XEM'
    },
    'BTC-XMR': {
        'POLONIEX': 'BTC_XMR'
    },
    'BTC-XPM': {
        'POLONIEX': 'BTC_XPM'
    },
    'BTC-XRP': {
        'POLONIEX': 'BTC_XRP'
    },
    'USDT-BTC': {
        'POLONIEX': 'USDT_BTC'
    },
    'USDT-DASH': {
        'POLONIEX': 'USDT_DASH'
    },
    'USDT-LTC': {
        'POLONIEX': 'USDT_LTC'
    },
    'USDT-NXT': {
        'POLONIEX': 'USDT_NXT'
    },
    'USDT-STR': {
        'POLONIEX': 'USDT_STR'
    },
    'USDT-XMR': {
        'POLONIEX': 'USDT_XMR'
    },
    'USDT-XRP': {
        'POLONIEX': 'USDT_XRP'
    },
    'XMR-BCN': {
        'POLONIEX': 'XMR_BCN'
    },
    'XMR-BLK': {
        'POLONIEX': 'XMR_BLK'
    },
    'XMR-BTCD': {
        'POLONIEX': 'XMR_BTCD'
    },
    'XMR-DASH': {
        'POLONIEX': 'XMR_DASH'
    },
    'XMR-LTC': {
        'POLONIEX': 'XMR_LTC'
    },
    'XMR-MAID': {
        'POLONIEX': 'XMR_MAID'
    },
    'XMR-NXT': {
        'POLONIEX': 'XMR_NXT'
    },
    'BTC-ETH': {
        'POLONIEX': 'BTC_ETH'
    },
    'USDT-ETH': {
        'POLONIEX': 'USDT_ETH'
    },
    'BTC-SC': {
        'POLONIEX': 'BTC_SC'
    },
    'BTC-BCY': {
        'POLONIEX': 'BTC_BCY'
    },
    'BTC-EXP': {
        'POLONIEX': 'BTC_EXP'
    },
    'BTC-FCT': {
        'POLONIEX': 'BTC_FCT'
    },
    'BTC-RADS': {
        'POLONIEX': 'BTC_RADS'
    },
    'BTC-AMP': {
        'POLONIEX': 'BTC_AMP'
    },
    'BTC-DCR': {
        'POLONIEX': 'BTC_DCR'
    },
    'BTC-LSK': {
        'POLONIEX': 'BTC_LSK'
    },
    'ETH-LSK': {
        'POLONIEX': 'ETH_LSK'
    },
    'BTC-LBC': {
        'POLONIEX': 'BTC_LBC'
    },
    'BTC-STEEM': {
        'POLONIEX': 'BTC_STEEM'
    },
    'ETH-STEEM': {
        'POLONIEX': 'ETH_STEEM'
    },
    'BTC-SBD': {
        'POLONIEX': 'BTC_SBD'
    },
    'BTC-ETC': {
        'POLONIEX': 'BTC_ETC'
    },
    'ETH-ETC': {
        'POLONIEX': 'ETH_ETC'
    },
    'USDT-ETC': {
        'POLONIEX': 'USDT_ETC'
    },
    'BTC-REP': {
        'POLONIEX': 'BTC_REP'
    },
    'USDT-REP': {
        'POLONIEX': 'USDT_REP'
    },
    'ETH-REP': {
        'POLONIEX': 'ETH_REP'
    },
    'BTC-ARDR': {
        'POLONIEX': 'BTC_ARDR'
    },
    'BTC-ZEC': {
        'POLONIEX': 'BTC_ZEC'
    },
    'ETH-ZEC': {
        'POLONIEX': 'ETH_ZEC'
    },
    'USDT-ZEC': {
        'POLONIEX': 'USDT_ZEC'
    },
    'XMR-ZEC': {
        'POLONIEX': 'XMR_ZEC'
    },
    'BTC-STRAT': {
        'POLONIEX': 'BTC_STRAT'
    },
    'BTC-NXC': {
        'POLONIEX': 'BTC_NXC'
    },
    'BTC-PASC': {
        'POLONIEX': 'BTC_PASC'
    },
    'BTC-GNT': {
        'POLONIEX': 'BTC_GNT'
    },
    'ETH-GNT': {
        'POLONIEX': 'ETH_GNT'
    },
    'BTC-GNO': {
        'POLONIEX': 'BTC_GNO'
    },
    'ETH-GNO': {
        'POLONIEX': 'ETH_GNO'
    },
    'BTC-BCH': {
        'POLONIEX': 'BTC_BCH'
    },
    'ETH-BCH': {
        'POLONIEX': 'ETH_BCH'
    },
    'USDT-BCH': {
        'POLONIEX': 'USDT_BCH'
    },
    'BTC-ZRX': {
        'POLONIEX': 'BTC_ZRX'
    },
    'ETH-ZRX': {
        'POLONIEX': 'ETH_ZRX'
    },
    'BTC-CVC': {
        'POLONIEX': 'BTC_CVC'
    },
    'ETH-CVC': {
        'POLONIEX': 'ETH_CVC'
    },
    'BTC-OMG': {
        'POLONIEX': 'BTC_OMG'
    },
    'ETH-OMG': {
        'POLONIEX': 'ETH_OMG'
    },
    'BTC-GAS': {
        'POLONIEX': 'BTC_GAS'
    },
    'ETH-GAS': {
        'POLONIEX': 'ETH_GAS'
    },
    'BTC-STORJ': {
        'POLONIEX': 'BTC_STORJ'
    },
    'BCH-ETH': {
        'BITFINEX': 'tBCHETH'
    },
    'DATA-BTC': {
        'BITFINEX': 'tDATABTC'
    },
    'ETC-BTC': {
        'BITFINEX': 'tETCBTC'
    },
    'GNT-BTC': {
        'BITFINEX': 'tGNTBTC'
    },
    'QTUM-BTC': {
        'BITFINEX': 'tQTUMBTC'
    },
    'SAN-USD': {
        'BITFINEX': 'tSANUSD'
    },
    'OMG-ETH': {
        'BITFINEX': 'tOMGETH'
    },
    'ETC-USD': {
        'BITFINEX': 'tETCUSD'
    },
    'DASH-USD': {
        'BITFINEX': 'tDASHUSD'
    },
    'RRT-USD': {
        'BITFINEX': 'tRRTUSD'
    },
    'SAN-BTC': {
        'BITFINEX': 'tSANBTC'
    },
    'GNT-USD': {
        'BITFINEX': 'tGNTUSD'
    },
    'IOTA-EUR': {
        'BITFINEX': 'tIOTAEUR'
    },
    'YYW-BTC': {
        'BITFINEX': 'tYYWBTC'
    },
    'BCH-BTC': {
        'BITFINEX': 'tBCHBTC'
    },
    'NEO-USD': {
        'BITFINEX': 'tNEOUSD'
    },
    'EDO-BTC': {
        'BITFINEX': 'tEDOBTC'
    },
    'EDO-ETH': {
        'BITFINEX': 'tEDOETH'
    },
    'QASH-USD': {
        'BITFINEX': 'tQASHUSD'
    },
    'QTUM-USD': {
        'BITFINEX': 'tQTUMUSD'
    },
    'BTG-BTC': {
        'BITFINEX': 'tBTGBTC'
    },
    'ZEC-BTC': {
        'BITFINEX': 'tZECBTC'
    },
    'XRP-BTC': {
        'BITFINEX': 'tXRPBTC'
    },
    'AVT-USD': {
        'BITFINEX': 'tAVTUSD'
    },
    'XRP-USD': {
        'BITFINEX': 'tXRPUSD'
    },
    'XMR-BTC': {
        'BITFINEX': 'tXMRBTC'
    },
    'OMG-BTC': {
        'BITFINEX': 'tOMGBTC'
    },
    'IOTA-USD': {
        'BITFINEX': 'tIOTAUSD'
    },
    'ETP-USD': {
        'BITFINEX': 'tETPUSD'
    },
    'IOTA-BTC': {
        'BITFINEX': 'tIOTABTC'
    },
    'EDO-USD': {
        'BITFINEX': 'tEDOUSD'
    },
    'NEO-ETH': {
        'BITFINEX': 'tNEOETH'
    },
    'SNT-USD': {
        'BITFINEX': 'tSNTUSD'
    },
    'BTG-USD': {
        'BITFINEX': 'tBTGUSD'
    },
    'DATA-USD': {
        'BITFINEX': 'tDATAUSD'
    },
    'ETP-BTC': {
        'BITFINEX': 'tETPBTC'
    },
    'AVT-ETH': {
        'BITFINEX': 'tAVTETH'
    },
    'SAN-ETH': {
        'BITFINEX': 'tSANETH'
    },
    'EOS-ETH': {
        'BITFINEX': 'tEOSETH'
    },
    'DATA-ETH': {
        'BITFINEX': 'tDATAETH'
    },
    'DASH-BTC': {
        'BITFINEX': 'tDASHBTC'
    },
    'XMR-USD': {
        'BITFINEX': 'tXMRUSD'
    },
    'IOTA-ETH': {
        'BITFINEX': 'tIOTAETH'
    },
    'YYW-ETH': {
        'BITFINEX': 'tYYWETH'
    },
    'QTUM-ETH': {
        'BITFINEX': 'tQTUMETH'
    },
    'YYW-USD': {
        'BITFINEX': 'tYYWUSD'
    },
    'OMG-USD': {
        'BITFINEX': 'tOMGUSD'
    },
    'GNT-ETH': {
        'BITFINEX': 'tGNTETH'
    },
    'EOS-BTC': {
        'BITFINEX': 'tEOSBTC'
    },
    'ETP-ETH': {
        'BITFINEX': 'tETPETH'
    },
    'SNT-BTC': {
        'BITFINEX': 'tSNTBTC'
    },
    'SNT-ETH': {
        'BITFINEX': 'tSNTETH'
    },
    'QASH-BTC': {
        'BITFINEX': 'tQASHBTC'
    },
    'QASH-ETH': {
        'BITFINEX': 'tQASHETH'
    },
    'AVT-BTC': {
        'BITFINEX': 'tAVTBTC'
    },
    'RRT-BTC': {
        'BITFINEX': 'tRRTBTC'
    },
    'ZEC-USD': {
        'BITFINEX': 'tZECUSD'
    },
    'NEO-BTC': {
        'BITFINEX': 'tNEOBTC'
    },
    'EOS-USD': {
        'BITFINEX': 'tEOSUSD'
    },
}

_exchange_to_std = {
    'BTC-USD': 'BTC-USD',
    'tBTCUSD': 'BTC-USD',
    'BTCUSD': 'BTC-USD',
    'ETHUSD': 'ETH-USD',
    'ETH-USD': 'ETH-USD',
    'ETHBTC': 'ETH-BTC',
    'ETH-BTC': 'ETH-BTC',
    'BCH-USD': 'BCH-USD',
    'LTC-USD': 'LTC-USD',
    'LTC-EUR': 'LTC-EUR',
    'LTC-BTC': 'LTC-BTC',
    'ETH-EUR': 'ETH-EUR',
    'BTC-GBP': 'BTC-GBP',
    'BTC-EUR': 'BTC-EUR',
    'BTC_BCN': 'BTC-BCN',
    'BTC_BCN': 'BTC-BCN',
    'BTC_BELA': 'BTC-BELA',
    'BTC_BLK': 'BTC-BLK',
    'BTC_BTCD': 'BTC-BTCD',
    'BTC_BTM': 'BTC-BTM',
    'BTC_BTS': 'BTC-BTS',
    'BTC_BURST': 'BTC-BURST',
    'BTC_CLAM': 'BTC-CLAM',
    'BTC_DASH': 'BTC-DASH',
    'BTC_DGB': 'BTC-DGB',
    'BTC_DOGE': 'BTC-DOGE',
    'BTC_EMC2': 'BTC-EMC2',
    'BTC_FLDC': 'BTC-FLDC',
    'BTC_FLO': 'BTC-FLO',
    'BTC_GAME': 'BTC-GAME',
    'BTC_GRC': 'BTC-GRC',
    'BTC_HUC': 'BTC-HUC',
    'BTC_LTC': 'BTC-LTC',
    'BTC_MAID': 'BTC-MAID',
    'BTC_OMNI': 'BTC-OMNI',
    'BTC_NAV': 'BTC-NAV',
    'BTC_NEOS': 'BTC-NEOS',
    'BTC_NMC': 'BTC-NMC',
    'BTC_NXT': 'BTC-NXT',
    'BTC_PINK': 'BTC-PINK',
    'BTC_POT': 'BTC-POT',
    'BTC_PPC': 'BTC-PPC',
    'BTC_RIC': 'BTC-RIC',
    'BTC_STR': 'BTC-STR',
    'BTC_SYS': 'BTC-SYS',
    'BTC_VIA': 'BTC-VIA',
    'BTC_XVC': 'BTC-XVC',
    'BTC_VRC': 'BTC-VRC',
    'BTC_VTC': 'BTC-VTC',
    'BTC_XBC': 'BTC-XBC',
    'BTC_XCP': 'BTC-XCP',
    'BTC_XEM': 'BTC-XEM',
    'BTC_XMR': 'BTC-XMR',
    'BTC_XPM': 'BTC-XPM',
    'BTC_XRP': 'BTC-XRP',
    'USDT_BTC': 'USDT-BTC',
    'USDT_DASH': 'USDT-DASH',
    'USDT_LTC': 'USDT-LTC',
    'USDT_NXT': 'USDT-NXT',
    'USDT_STR': 'USDT-STR',
    'USDT_XMR': 'USDT-XMR',
    'USDT_XRP': 'USDT-XRP',
    'XMR_BCN': 'XMR-BCN',
    'XMR_BLK': 'XMR-BLK',
    'XMR_BTCD': 'XMR-BTCD',
    'XMR_DASH': 'XMR-DASH',
    'XMR_LTC': 'XMR-LTC',
    'XMR_MAID': 'XMR-MAID',
    'XMR_NXT': 'XMR-NXT',
    'BTC_ETH': 'BTC-ETH',
    'USDT_ETH': 'USDT-ETH',
    'BTC_SC': 'BTC-SC',
    'BTC_BCY': 'BTC-BCY',
    'BTC_EXP': 'BTC-EXP',
    'BTC_FCT': 'BTC-FCT',
    'BTC_RADS': 'BTC-RADS',
    'BTC_AMP': 'BTC-AMP',
    'BTC_DCR': 'BTC-DCR',
    'BTC_LSK': 'BTC-LSK',
    'ETH_LSK': 'ETH-LSK',
    'BTC_LBC': 'BTC-LBC',
    'BTC_STEEM': 'BTC-STEEM',
    'ETH_STEEM': 'ETH-STEEM',
    'BTC_SBD': 'BTC-SBD',
    'BTC_ETC': 'BTC-ETC',
    'ETH_ETC': 'ETH-ETC',
    'USDT_ETC': 'USDT-ETC',
    'BTC_REP': 'BTC-REP',
    'USDT_REP': 'USDT-REP',
    'ETH_REP': 'ETH-REP',
    'BTC_ARDR': 'BTC-ARDR',
    'BTC_ZEC': 'BTC-ZEC',
    'ETH_ZEC': 'ETH-ZEC',
    'USDT_ZEC': 'USDT-ZEC',
    'XMR_ZEC': 'XMR-ZEC',
    'BTC_STRAT': 'BTC-STRAT',
    'BTC_NXC': 'BTC-NXC',
    'BTC_PASC': 'BTC-PASC',
    'BTC_GNT': 'BTC-GNT',
    'ETH_GNT': 'ETH-GNT',
    'BTC_GNO': 'BTC-GNO',
    'ETH_GNO': 'ETH-GNO',
    'BTC_BCH': 'BTC-BCH',
    'ETH_BCH': 'ETH-BCH',
    'USDT_BCH': 'USDT-BCH',
    'BTC_ZRX': 'BTC-ZRX',
    'ETH_ZRX': 'ETH-ZRX',
    'BTC_CVC': 'BTC-CVC',
    'ETH_CVC': 'ETH-CVC',
    'BTC_OMG': 'BTC-OMG',
    'ETH_OMG': 'ETH-OMG',
    'BTC_GAS': 'BTC-GAS',
    'ETH_GAS': 'ETH-GAS',
    'BTC_STORJ': 'BTC-STORJ',
    'tBCHETH': 'BCH-ETH',
    'tDATABTC': 'DATA-BTC',
    'tETCBTC': 'ETC-BTC',
    'tGNTBTC': 'GNT-BTC',
    'tQTUMBTC': 'QTUM-BTC',
    'tSANUSD': 'SAN-USD',
    'tOMGETH': 'OMG-ETH',
    'tETCUSD': 'ETC-USD',
    'tDASHUSD': 'DASH-USD',
    'tRRTUSD': 'RRT-USD',
    'tLTCUSD': 'LTC-USD',
    'tSANBTC': 'SAN-BTC',
    'tGNTUSD': 'GNT-USD',
    'tIOTAEUR': 'IOTA-EUR',
    'tETHUSD': 'ETH-USD',
    'tYYWBTC': 'YYW-BTC',
    'tBCHBTC': 'BCH-BTC',
    'tNEOUSD': 'NEO-USD',
    'tEDOBTC': 'EDO-BTC',
    'tEDOETH': 'EDO-ETH',
    'tQASHUSD': 'QASH-USD',
    'tQTUMUSD': 'QTUM-USD',
    'tBTGBTC': 'BTG-BTC',
    'tZECBTC': 'ZEC-BTC',
    'tXRPBTC': 'XRP-BTC',
    'tAVTUSD': 'AVT-USD',
    'tXRPUSD': 'XRP-USD',
    'tXMRBTC': 'XMR-BTC',
    'tOMGBTC': 'OMG-BTC',
    'tIOTAUSD': 'IOTA-USD',
    'tETPUSD': 'ETP-USD',
    'tIOTABTC': 'IOTA-BTC',
    'tEDOUSD': 'EDO-USD',
    'tNEOETH': 'NEO-ETH',
    'tSNTUSD': 'SNT-USD',
    'tETHBTC': 'ETH-BTC',
    'tLTCBTC': 'LTC-BTC',
    'tBTGUSD': 'BTG-USD',
    'tDATAUSD': 'DATA-USD',
    'tETPBTC': 'ETP-BTC',
    'tAVTETH': 'AVT-ETH',
    'tSANETH': 'SAN-ETH',
    'tEOSETH': 'EOS-ETH',
    'tDATAETH': 'DATA-ETH',
    'tDASHBTC': 'DASH-BTC',
    'tBCHUSD': 'BCH-USD',
    'tXMRUSD': 'XMR-USD',
    'tIOTAETH': 'IOTA-ETH',
    'tYYWETH': 'YYW-ETH',
    'tQTUMETH': 'QTUM-ETH',
    'tYYWUSD': 'YYW-USD',
    'tOMGUSD': 'OMG-USD',
    'tGNTETH': 'GNT-ETH',
    'tEOSBTC': 'EOS-BTC',
    'tETPETH': 'ETP-ETH',
    'tBTCUSD': 'BTC-USD',
    'tSNTBTC': 'SNT-BTC',
    'tSNTETH': 'SNT-ETH',
    'tBTCEUR': 'BTC-EUR',
    'tQASHBTC': 'QASH-BTC',
    'tQASHETH': 'QASH-ETH',
    'tAVTBTC': 'AVT-BTC',
    'tRRTBTC': 'RRT-BTC',
    'tZECUSD': 'ZEC-USD',
    'tNEOBTC': 'NEO-BTC',
    'tEOSUSD': 'EOS-USD',
}


def pair_std_to_exchange(pair, exchange):
    return _std_trading_pairs[pair][exchange]


def pair_exchange_to_std(pair):
    return _exchange_to_std[pair]


_channel_to_exchange = {'ticker': {'HITBTC': 'subscribeTicker'}}


def std_channel_to_exchange(channel, exchange):
    if channel in _channel_to_exchange:
        if exchange in _channel_to_exchange[channel]:
            return _channel_to_exchange[channel][exchange]
    return channel
