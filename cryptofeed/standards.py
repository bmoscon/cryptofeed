'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from datetime import datetime as dt
import calendar

from cryptofeed.exchanges import COINBASE, GEMINI, BITFINEX, BITSTAMP, HITBTC, BITMEX, POLONIEX, KRAKEN
from cryptofeed.poloniex.pairs import poloniex_trading_pairs
from cryptofeed.kraken.pairs import get_kraken_pairs


_std_trading_pairs = {
    'BTC-USD': {
        COINBASE: 'BTC-USD',
        BITFINEX: 'tBTCUSD',
        GEMINI: 'BTCUSD',
        HITBTC: 'BTCUSD',
        BITSTAMP: 'btcusd'
    },
    'ETH-USD': {
        GEMINI: 'ETHUSD',
        COINBASE: 'ETH-USD',
        BITFINEX: 'tETHUSD',
        HITBTC: 'ETHUSD',
        BITSTAMP: 'ethusd'
    },
    'ETH-BTC': {
        GEMINI: 'ETHBTC',
        COINBASE: 'ETH-BTC',
        BITFINEX: 'tETHBTC',
        HITBTC: 'ETHBTC',
        BITSTAMP: 'ethbtc'
    },
    'BCH-USD': {
        COINBASE: 'BCH-USD',
        BITFINEX: 'tBCHUSD',
        HITBTC: 'BCHUSD',
        BITSTAMP: 'bchusd'
    },
    'LTC-EUR': {
        COINBASE: 'LTC-EUR',
        BITSTAMP: 'ltceur'
    },
    'LTC-USD': {
        COINBASE: 'LTC-USD',
        BITFINEX: 'tLTCUSD',
        HITBTC: 'LTCUSD',
        BITSTAMP: 'ltcusd'
    },
    'LTC-BTC': {
        COINBASE: 'LTC-BTC',
        BITFINEX: 'tLTCBTC',
        HITBTC: 'LTCBTC',
        BITSTAMP: 'ltcbtc'
    },
    'ETH-EUR': {
        COINBASE: 'ETH-EUR',
        BITSTAMP: 'etheur'
    },
    'BTC-GBP': {
        COINBASE: 'BTC-GBP'
    },
    'BTC-EUR': {
        COINBASE: 'BTC-EUR',
        BITFINEX: 'tBTCEUR',
        BITSTAMP: 'btceur'
    },
    'BCH-ETH': {
        BITFINEX: 'tBCHETH',
        HITBTC: 'BCHETH'
    },
    'DATA-BTC': {
        BITFINEX: 'tDATABTC',
        HITBTC: 'DATABTC'
    },
    'ETC-BTC': {
        BITFINEX: 'tETCBTC',
        HITBTC: 'ETCBTC'
    },
    'GNT-BTC': {
        BITFINEX: 'tGNTBTC'
    },
    'QTUM-BTC': {
        BITFINEX: 'tQTUMBTC'
    },
    'SAN-USD': {
        BITFINEX: 'tSANUSD'
    },
    'OMG-ETH': {
        BITFINEX: 'tOMGETH',
        HITBTC: 'OMGETH'
    },
    'ETC-USD': {
        BITFINEX: 'tETCUSD',
        HITBTC: 'ETCUSD'
    },
    'DASH-USD': {
        BITFINEX: 'tDASHUSD',
        HITBTC: 'DASHUSD'
    },
    'RRT-USD': {
        BITFINEX: 'tRRTUSD'
    },
    'SAN-BTC': {
        BITFINEX: 'tSANBTC'
    },
    'GNT-USD': {
        BITFINEX: 'tGNTUSD'
    },
    'IOTA-EUR': {
        BITFINEX: 'tIOTAEUR'
    },
    'YYW-BTC': {
        BITFINEX: 'tYYWBTC'
    },
    'BCH-BTC': {
        BITFINEX: 'tBCHBTC',
        HITBTC: 'BCHBTC',
        BITSTAMP: 'bchbtc'
    },
    'NEO-USD': {
        BITFINEX: 'tNEOUSD',
        HITBTC: 'NEOUSD'
    },
    'EDO-BTC': {
        BITFINEX: 'tEDOBTC',
        HITBTC: 'EDOBTC'
    },
    'EDO-ETH': {
        BITFINEX: 'tEDOETH',
        HITBTC: 'EDOETH'
    },
    'QASH-USD': {
        BITFINEX: 'tQASHUSD'
    },
    'QTUM-USD': {
        BITFINEX: 'tQTUMUSD'
    },
    'BTG-BTC': {
        BITFINEX: 'tBTGBTC',
        HITBTC: 'BTGBTC'
    },
    'ZEC-BTC': {
        BITFINEX: 'tZECBTC',
        HITBTC: 'ZECBTC'
    },
    'XRP-BTC': {
        BITFINEX: 'tXRPBTC',
        HITBTC: 'XRPBTC',
        BITSTAMP: 'xrpbtc'
    },
    'AVT-USD': {
        BITFINEX: 'tAVTUSD'
    },
    'XRP-USD': {
        BITFINEX: 'tXRPUSD',
        BITSTAMP: 'xrpusd'
    },
    'XMR-BTC': {
        BITFINEX: 'tXMRBTC',
        HITBTC: 'XMRBTC'
    },
    'OMG-BTC': {
        BITFINEX: 'tOMGBTC',
        HITBTC: 'OMGBTC'
    },
    'IOTA-USD': {
        BITFINEX: 'tIOTAUSD'
    },
    'ETP-USD': {
        BITFINEX: 'tETPUSD',
        HITBTC: 'ETPUSD'
    },
    'IOTA-BTC': {
        BITFINEX: 'tIOTABTC'
    },
    'EDO-USD': {
        BITFINEX: 'tEDOUSD',
        HITBTC: 'EDOUSD'
    },
    'NEO-ETH': {
        BITFINEX: 'tNEOETH',
        HITBTC: 'NEOETH'
    },
    'SNT-USD': {
        BITFINEX: 'tSNTUSD'
    },
    'BTG-USD': {
        BITFINEX: 'tBTGUSD',
        HITBTC: 'BTGUSD'
    },
    'DATA-USD': {
        BITFINEX: 'tDATAUSD',
        HITBTC: 'DATAUSD'
    },
    'ETP-BTC': {
        BITFINEX: 'tETPBTC',
        HITBTC: 'ETPBTC'
    },
    'AVT-ETH': {
        BITFINEX: 'tAVTETH',
        HITBTC: 'AVTETH'
    },
    'SAN-ETH': {
        BITFINEX: 'tSANETH',
        HITBTC: 'SANETH'
    },
    'EOS-ETH': {
        BITFINEX: 'tEOSETH',
        HITBTC: 'EOSETH'
    },
    'DATA-ETH': {
        BITFINEX: 'tDATAETH',
        HITBTC: 'DATAETH'
    },
    'DASH-BTC': {
        BITFINEX: 'tDASHBTC',
        HITBTC: 'DASHBTC'
    },
    'XMR-USD': {
        BITFINEX: 'tXMRUSD',
        HITBTC: 'XMRUSD'
    },
    'IOTA-ETH': {
        BITFINEX: 'tIOTAETH'
    },
    'YYW-ETH': {
        BITFINEX: 'tYYWETH'
    },
    'QTUM-ETH': {
        BITFINEX: 'tQTUMETH',
        HITBTC: 'QTUMETH'
    },
    'YYW-USD': {
        BITFINEX: 'tYYWUSD'
    },
    'OMG-USD': {
        BITFINEX: 'tOMGUSD'
    },
    'GNT-ETH': {
        BITFINEX: 'tGNTETH'
    },
    'EOS-BTC': {
        BITFINEX: 'tEOSBTC',
        HITBTC: 'EOSBTC'
    },
    'ETP-ETH': {
        BITFINEX: 'tETPETH',
        HITBTC: 'ETPETH'
    },
    'SNT-BTC': {
        BITFINEX: 'tSNTBTC',
        HITBTC: 'SNTBTC'
    },
    'SNT-ETH': {
        BITFINEX: 'tSNTETH',
        HITBTC: 'SNTETH'
    },
    'QASH-BTC': {
        BITFINEX: 'tQASHBTC'
    },
    'QASH-ETH': {
        BITFINEX: 'tQASHETH'
    },
    'AVT-BTC': {
        BITFINEX: 'tAVTBTC'
    },
    'RRT-BTC': {
        BITFINEX: 'tRRTBTC'
    },
    'ZEC-USD': {
        BITFINEX: 'tZECUSD',
        HITBTC: 'ZECUSD'
    },
    'NEO-BTC': {
        BITFINEX: 'tNEOBTC',
        HITBTC: 'NEOBTC'
    },
    'EOS-USD': {
        BITFINEX: 'tEOSUSD',
        HITBTC: 'EOSUSD'
    },
    'CTR-ETH': {
        HITBTC: 'CTRETH'
    },
    'FYP-BTC': {
        HITBTC: 'FYPBTC'
    },
    'TRST-BTC': {
        HITBTC: 'TRSTBTC'
    },
    'SWFTC-USD': {
        HITBTC: 'SWFTCUSD'
    },
    'HDG-ETH': {
        HITBTC: 'HDGETH'
    },
    'DSH-BTC': {
        HITBTC: 'DSHBTC'
    },
    'VIB-USD': {
        HITBTC: 'VIBUSD'
    },
    'CPAY-ETH': {
        HITBTC: 'CPAYETH'
    },
    'AMM-ETH': {
        HITBTC: 'AMMETH'
    },
    'XUC-ETH': {
        HITBTC: 'XUCETH'
    },
    'ZRC-BTC': {
        HITBTC: 'ZRCBTC'
    },
    'AMM-BTC': {
        HITBTC: 'AMMBTC'
    },
    'COSS-BTC': {
        HITBTC: 'COSSBTC'
    },
    'LA-ETH': {
        HITBTC: 'LAETH'
    },
    'XMR-ETH': {
        HITBTC: 'XMRETH'
    },
    'UGT-USD': {
        HITBTC: 'UGTUSD'
    },
    'EBTCNEW-USD': {
        HITBTC: 'EBTCNEWUSD'
    },
    'VERI-ETH': {
        HITBTC: 'VERIETH'
    },
    'AIR-USD': {
        HITBTC: 'AIRUSD'
    },
    'INDI-BTC': {
        HITBTC: 'INDIBTC'
    },
    'AMP-BTC': {
        HITBTC: 'AMPBTC'
    },
    'FUEL-USD': {
        HITBTC: 'FUELUSD'
    },
    'XEM-USD': {
        HITBTC: 'XEMUSD'
    },
    'WMGO-USD': {
        HITBTC: 'WMGOUSD'
    },
    'CLD-BTC': {
        HITBTC: 'CLDBTC'
    },
    'ICX-ETH': {
        HITBTC: 'ICXETH'
    },
    'PRS-BTC': {
        HITBTC: 'PRSBTC'
    },
    'RKC-ETH': {
        HITBTC: 'RKCETH'
    },
    'MNE-BTC': {
        HITBTC: 'MNEBTC'
    },
    'EMCU-SDT': {
        HITBTC: 'EMCUSDT'
    },
    'ART-BTC': {
        HITBTC: 'ARTBTC'
    },
    'RVT-BTC': {
        HITBTC: 'RVTBTC'
    },
    'HAC-BTC': {
        HITBTC: 'HACBTC'
    },
    'DOV-ETH': {
        HITBTC: 'DOVETH'
    },
    'CND-BTC': {
        HITBTC: 'CNDBTC'
    },
    'ICOS-BTC': {
        HITBTC: 'ICOSBTC'
    },
    'PPT-BTC': {
        HITBTC: 'PPTBTC'
    },
    'SISA-ETH': {
        HITBTC: 'SISAETH'
    },
    'EBTCNEW-ETH': {
        HITBTC: 'EBTCNEWETH'
    },
    'SNC-USD': {
        HITBTC: 'SNCUSD'
    },
    'DENT-ETH': {
        HITBTC: 'DENTETH'
    },
    'NEBL-ETH': {
        HITBTC: 'NEBLETH'
    },
    'BTM-ETH': {
        HITBTC: 'BTMETH'
    },
    'XRP-ETH': {
        HITBTC: 'XRPETH'
    },
    'ATB-BTC': {
        HITBTC: 'ATBBTC'
    },
    'XTZ-USD': {
        HITBTC: 'XTZUSD'
    },
    'BTX-USDT': {
        HITBTC: 'BTXUSDT'
    },
    'ARN-ETH': {
        HITBTC: 'ARNETH'
    },
    'DDF-ETH': {
        HITBTC: 'DDFETH'
    },
    'SUB-USD': {
        HITBTC: 'SUBUSD'
    },
    'IGNIS-ETH': {
        HITBTC: 'IGNISETH'
    },
    'DICE-BTC': {
        HITBTC: 'DICEBTC'
    },
    'LUN-BTC': {
        HITBTC: 'LUNBTC'
    },
    'DIM-ETH': {
        HITBTC: 'DIMETH'
    },
    'SWT-BTC': {
        HITBTC: 'SWTBTC'
    },
    'GNO-ETH': {
        HITBTC: 'GNOETH'
    },
    'STRAT-USD': {
        HITBTC: 'STRATUSD'
    },
    'ADX-ETH': {
        HITBTC: 'ADXETH'
    },
    'STX-BTC': {
        HITBTC: 'STXBTC'
    },
    'SBD-BTC': {
        HITBTC: 'SBDBTC'
    },
    'BQX-ETH': {
        HITBTC: 'BQXETH'
    },
    'PAY-ETH': {
        HITBTC: 'PAYETH'
    },
    'PLU-ETH': {
        HITBTC: 'PLUETH'
    },
    'XRP-USDT': {
        HITBTC: 'XRPUSDT'
    },
    'VEN-ETH': {
        HITBTC: 'VENETH'
    },
    'EMC-BTC': {
        HITBTC: 'EMCBTC'
    },
    'PQT-USD': {
        HITBTC: 'PQTUSD'
    },
    'KICK-BTC': {
        HITBTC: 'KICKBTC'
    },
    'ETBS-BTC': {
        HITBTC: 'ETBSBTC'
    },
    'ICX-USD': {
        HITBTC: 'ICXUSD'
    },
    'ENJ-ETH': {
        HITBTC: 'ENJETH'
    },
    'ZRX-ETH': {
        HITBTC: 'ZRXETH'
    },
    'NXT-ETH': {
        HITBTC: 'NXTETH'
    },
    'DRPU-ETH': {
        HITBTC: 'DRPUETH'
    },
    'MCAP-BTC': {
        HITBTC: 'MCAPBTC'
    },
    'OAX-ETH': {
        HITBTC: 'OAXETH'
    },
    'NTO-BTC': {
        HITBTC: 'NTOBTC'
    },
    'SPF-ETH': {
        HITBTC: 'SPFETH'
    },
    'BQX-BTC': {
        HITBTC: 'BQXBTC'
    },
    'TKN-BTC': {
        HITBTC: 'TKNBTC'
    },
    'B2X-USD': {
        HITBTC: 'B2XUSD'
    },
    'DGB-ETH': {
        HITBTC: 'DGBETH'
    },
    'HVN-ETH': {
        HITBTC: 'HVNETH'
    },
    'B2X-ETH': {
        HITBTC: 'B2XETH'
    },
    'B2X-BTC': {
        HITBTC: 'B2XBTC'
    },
    'EBTCOLD-ETH': {
        HITBTC: 'EBTCOLDETH'
    },
    'CLD-USD': {
        HITBTC: 'CLDUSD'
    },
    'CTX-ETH': {
        HITBTC: 'CTXETH'
    },
    'VERI-BTC': {
        HITBTC: 'VERIBTC'
    },
    'TRX-USD': {
        HITBTC: 'TRXUSD'
    },
    'HPC-BTC': {
        HITBTC: 'HPCBTC'
    },
    'LTC-ETH': {
        HITBTC: 'LTCETH'
    },
    'BCC-BTC': {
        HITBTC: 'BCCBTC'
    },
    'TBT-BTC': {
        HITBTC: 'TBTBTC'
    },
    'SUB-BTC': {
        HITBTC: 'SUBBTC'
    },
    'ZAP-BTC': {
        HITBTC: 'ZAPBTC'
    },
    'QAU-BTC': {
        HITBTC: 'QAUBTC'
    },
    'GVT-ETH': {
        HITBTC: 'GVTETH'
    },
    'NDC-ETH': {
        HITBTC: 'NDCETH'
    },
    'CND-ETH': {
        HITBTC: 'CNDETH'
    },
    'XAUR-BTC': {
        HITBTC: 'XAURBTC'
    },
    'SMS-USD': {
        HITBTC: 'SMSUSD'
    },
    'ICN-BTC': {
        HITBTC: 'ICNBTC'
    },
    'FUN-ETH': {
        HITBTC: 'FUNETH'
    },
    'DCT-BTC': {
        HITBTC: 'DCTBTC'
    },
    'TRX-ETH': {
        HITBTC: 'TRXETH'
    },
    'PLU-BTC': {
        HITBTC: 'PLUBTC'
    },
    'PAY-BTC': {
        HITBTC: 'PAYBTC'
    },
    'AIR-ETH': {
        HITBTC: 'AIRETH'
    },
    'LRC-ETH': {
        HITBTC: 'LRCETH'
    },
    'VERI-USD': {
        HITBTC: 'VERIUSD'
    },
    'BMC-USD': {
        HITBTC: 'BMCUSD'
    },
    'SNC-BTC': {
        HITBTC: 'SNCBTC'
    },
    'FCN-BTC': {
        HITBTC: 'FCNBTC'
    },
    'EDG-BTC': {
        HITBTC: 'EDGBTC'
    },
    'SUB-ETH': {
        HITBTC: 'SUBETH'
    },
    'PPC-BTC': {
        HITBTC: 'PPCBTC'
    },
    'UGT-BTC': {
        HITBTC: 'UGTBTC'
    },
    'BET-ETH': {
        HITBTC: 'BETETH'
    },
    'UTT-USD': {
        HITBTC: 'UTTUSD'
    },
    'MCO-USD': {
        HITBTC: 'MCOUSD'
    },
    'BTG-ETH': {
        HITBTC: 'BTGETH'
    },
    'ATM-USD': {
        HITBTC: 'ATMUSD'
    },
    'HGT-ETH': {
        HITBTC: 'HGTETH'
    },
    'CTR-BTC': {
        HITBTC: 'CTRBTC'
    },
    'LRC-BTC': {
        HITBTC: 'LRCBTC'
    },
    'STX-ETH': {
        HITBTC: 'STXETH'
    },
    'MCO-BTC': {
        HITBTC: 'MCOBTC'
    },
    'ZSC-ETH': {
        HITBTC: 'ZSCETH'
    },
    'KBR-BTC': {
        HITBTC: 'KBRBTC'
    },
    'TGT-BTC': {
        HITBTC: 'TGTBTC'
    },
    'DCN-USD': {
        HITBTC: 'DCNUSD'
    },
    'FYN-ETH': {
        HITBTC: 'FYNETH'
    },
    'EBTCOLD-USD': {
        HITBTC: 'EBTCOLDUSD'
    },
    '8BT-USD': {
        HITBTC: '8BTUSD'
    },
    'DLT-BTC': {
        HITBTC: 'DLTBTC'
    },
    'OAX-USD': {
        HITBTC: 'OAXUSD'
    },
    'EXN-BTC': {
        HITBTC: 'EXNBTC'
    },
    'ITS-BTC': {
        HITBTC: 'ITSBTC'
    },
    'ORME-BTC': {
        HITBTC: 'ORMEBTC'
    },
    'CSNO-BTC': {
        HITBTC: 'CSNOBTC'
    },
    'UTT-BTC': {
        HITBTC: 'UTTBTC'
    },
    'SC-BTC': {
        HITBTC: 'SCBTC'
    },
    'WRC-ETH': {
        HITBTC: 'WRCETH'
    },
    'ATM-BTC': {
        HITBTC: 'ATMBTC'
    },
    'CCT-ETH': {
        HITBTC: 'CCTETH'
    },
    'SMART-BTC': {
        HITBTC: 'SMARTBTC'
    },
    'NXT-USD': {
        HITBTC: 'NXTUSD'
    },
    'ELM-BTC': {
        HITBTC: 'ELMBTC'
    },
    'FUN-BTC': {
        HITBTC: 'FUNBTC'
    },
    'BMC-BTC': {
        HITBTC: 'BMCBTC'
    },
    'DIM-USD': {
        HITBTC: 'DIMUSD'
    },
    'SMS-BTC': {
        HITBTC: 'SMSBTC'
    },
    'MIPS-BTC': {
        HITBTC: 'MIPSBTC'
    },
    'REP-BTC': {
        HITBTC: 'REPBTC'
    },
    'DCN-ETH': {
        HITBTC: 'DCNETH'
    },
    'DRPU-BTC': {
        HITBTC: 'DRPUBTC'
    },
    'FUEL-ETH': {
        HITBTC: 'FUELETH'
    },
    'DOGE-ETH': {
        HITBTC: 'DOGEETH'
    },
    'EMGO-BTC': {
        HITBTC: 'EMGOBTC'
    },
    'ECH-BTC': {
        HITBTC: 'ECHBTC'
    },
    'PING-BTC': {
        HITBTC: 'PINGBTC'
    },
    'AE-BTC': {
        HITBTC: 'AEBTC'
    },
    'DICE-ETH': {
        HITBTC: 'DICEETH'
    },
    'IXT-ETH': {
        HITBTC: 'IXTETH'
    },
    'ICOS-ETH': {
        HITBTC: 'ICOSETH'
    },
    'IXT-BTC': {
        HITBTC: 'IXTBTC'
    },
    'ATM-ETH': {
        HITBTC: 'ATMETH'
    },
    'AEON-BTC': {
        HITBTC: 'AEONBTC'
    },
    'MANA-ETH': {
        HITBTC: 'MANAETH'
    },
    'PPC-USD': {
        HITBTC: 'PPCUSD'
    },
    'STORM-BTC': {
        HITBTC: 'STORMBTC'
    },
    'ATL-BTC': {
        HITBTC: 'ATLBTC'
    },
    'CAT-BTC': {
        HITBTC: 'CATBTC'
    },
    'NXT-BTC': {
        HITBTC: 'NXTBTC'
    },
    'CNX-BTC': {
        HITBTC: 'CNXBTC'
    },
    'EBTCNEW-BTC': {
        HITBTC: 'EBTCNEWBTC'
    },
    'STU-USD': {
        HITBTC: 'STUUSD'
    },
    'ODN-BTC': {
        HITBTC: 'ODNBTC'
    },
    'CTX-BTC': {
        HITBTC: 'CTXBTC'
    },
    'ZRX-BTC': {
        HITBTC: 'ZRXBTC'
    },
    'BTM-BTC': {
        HITBTC: 'BTMBTC'
    },
    'BTCA-BTC': {
        HITBTC: 'BTCABTC'
    },
    'GNO-BTC': {
        HITBTC: 'GNOBTC'
    },
    'XUC-BTC': {
        HITBTC: 'XUCBTC'
    },
    'TNT-ETH': {
        HITBTC: 'TNTETH'
    },
    'BMT-ETH': {
        HITBTC: 'BMTETH'
    },
    'BUS-BTC': {
        HITBTC: 'BUSBTC'
    },
    'IND-ETH': {
        HITBTC: 'INDETH'
    },
    'SMS-ETH': {
        HITBTC: 'SMSETH'
    },
    'MAID-USD': {
        HITBTC: 'MAIDUSD'
    },
    'TNT-USD': {
        HITBTC: 'TNTUSD'
    },
    'DOGE-BTC': {
        HITBTC: 'DOGEBTC'
    },
    'FRD-BTC': {
        HITBTC: 'FRDBTC'
    },
    'STRAT-ETH': {
        HITBTC: 'STRATETH'
    },
    'OPT-BTC': {
        HITBTC: 'OPTBTC'
    },
    'NXC-BTC': {
        HITBTC: 'NXCBTC'
    },
    'ARDR-BTC': {
        HITBTC: 'ARDRBTC'
    },
    'MSP-ETH': {
        HITBTC: 'MSPETH'
    },
    'ZSC-USD': {
        HITBTC: 'ZSCUSD'
    },
    'SISA-BTC': {
        HITBTC: 'SISABTC'
    },
    'MTH-BTC': {
        HITBTC: 'MTHBTC'
    },
    'ZSC-BTC': {
        HITBTC: 'ZSCBTC'
    },
    'DRT-ETH': {
        HITBTC: 'DRTETH'
    },
    'QAU-ETH': {
        HITBTC: 'QAUETH'
    },
    'SKIN-BTC': {
        HITBTC: 'SKINBTC'
    },
    'BCC-ETH': {
        HITBTC: 'BCCETH'
    },
    'VEN-BTC': {
        HITBTC: 'VENBTC'
    },
    'GUP-BTC': {
        HITBTC: 'GUPBTC'
    },
    'CAT-USD': {
        HITBTC: 'CATUSD'
    },
    'NGC-USD': {
        HITBTC: 'NGCUSD'
    },
    'BCN-USD': {
        HITBTC: 'BCNUSD'
    },
    'SWT-ETH': {
        HITBTC: 'SWTETH'
    },
    'XUC-USD': {
        HITBTC: 'XUCUSD'
    },
    'TIME-ETH': {
        HITBTC: 'TIMEETH'
    },
    'DOV-BTC': {
        HITBTC: 'DOVBTC'
    },
    'ATB-USD': {
        HITBTC: 'ATBUSD'
    },
    'CDT-BTC': {
        HITBTC: 'CDTBTC'
    },
    'BTX-BTC': {
        HITBTC: 'BTXBTC'
    },
    'STU-BTC': {
        HITBTC: 'STUBTC'
    },
    'LOC-ETH': {
        HITBTC: 'LOCETH'
    },
    'BTCA-USD': {
        HITBTC: 'BTCAUSD'
    },
    'XDN-USD': {
        HITBTC: 'XDNUSD'
    },
    'CLD-ETH': {
        HITBTC: 'CLDETH'
    },
    'AMB-BTC': {
        HITBTC: 'AMBBTC'
    },
    'EVX-USD': {
        HITBTC: 'EVXUSD'
    },
    'VIB-ETH': {
        HITBTC: 'VIBETH'
    },
    'CL-ETH': {
        HITBTC: 'CLETH'
    },
    'WRC-BTC': {
        HITBTC: 'WRCBTC'
    },
    'EBTCOLD-BTC': {
        HITBTC: 'EBTCOLDBTC'
    },
    'ELE-BTC': {
        HITBTC: 'ELEBTC'
    },
    'VIBE-BTC': {
        HITBTC: 'VIBEBTC'
    },
    'CAT-ETH': {
        HITBTC: 'CATETH'
    },
    'GAME-BTC': {
        HITBTC: 'GAMEBTC'
    },
    'ATS-ETH': {
        HITBTC: 'ATSETH'
    },
    'BNT-BTC': {
        HITBTC: 'BNTBTC'
    },
    'SNGLS-BTC': {
        HITBTC: 'SNGLSBTC'
    },
    'CND-USD': {
        HITBTC: 'CNDUSD'
    },
    'ZRX-USD': {
        HITBTC: 'ZRXUSD'
    },
    'SCL-BTC': {
        HITBTC: 'SCLBTC'
    },
    'ETC-ETH': {
        HITBTC: 'ETCETH'
    },
    'MANA-BTC': {
        HITBTC: 'MANABTC'
    },
    'SWFTC-BTC': {
        HITBTC: 'SWFTCBTC'
    },
    'TAAS-BTC': {
        HITBTC: 'TAASBTC'
    },
    'SMART-ETH': {
        HITBTC: 'SMARTETH'
    },
    'WTT-BTC': {
        HITBTC: 'WTTBTC'
    },
    'PRE-BTC': {
        HITBTC: 'PREBTC'
    },
    'SBTC-BTC': {
        HITBTC: 'SBTCBTC'
    },
    'LIFE-BTC': {
        HITBTC: 'LIFEBTC'
    },
    'CTR-USD': {
        HITBTC: 'CTRUSD'
    },
    'FUEL-BTC': {
        HITBTC: 'FUELBTC'
    },
    'WMGO-BTC': {
        HITBTC: 'WMGOBTC'
    },
    'NEBL-BTC': {
        HITBTC: 'NEBLBTC'
    },
    'PLR-ETH': {
        HITBTC: 'PLRETH'
    },
    'STU-ETH': {
        HITBTC: 'STUETH'
    },
    'TRX-BTC': {
        HITBTC: 'TRXBTC'
    },
    'SUR-BTC': {
        HITBTC: 'SURBTC'
    },
    'KMD-USD': {
        HITBTC: 'KMDUSD'
    },
    'MAID-ETH': {
        HITBTC: 'MAIDETH'
    },
    'ATB-ETH': {
        HITBTC: 'ATBETH'
    },
    'ERO-BTC': {
        HITBTC: 'EROBTC'
    },
    'CL-USD': {
        HITBTC: 'CLUSD'
    },
    'DBIX-BTC': {
        HITBTC: 'DBIXBTC'
    },
    'TKR-ETH': {
        HITBTC: 'TKRETH'
    },
    'PIX-ETH': {
        HITBTC: 'PIXETH'
    },
    'BMC-ETH': {
        HITBTC: 'BMCETH'
    },
    'PPT-ETH': {
        HITBTC: 'PPTETH'
    },
    'MCO-ETH': {
        HITBTC: 'MCOETH'
    },
    'LSK-BTC': {
        HITBTC: 'LSKBTC'
    },
    'XAUR-ETH': {
        HITBTC: 'XAURETH'
    },
    'UGT-ETH': {
        HITBTC: 'UGTETH'
    },
    'LOC-BTC': {
        HITBTC: 'LOCBTC'
    },
    'STEE-MBTC': {
        HITBTC: 'STEEMBTC'
    },
    'ICX-BTC': {
        HITBTC: 'ICXBTC'
    },
    'PLBT-BTC': {
        HITBTC: 'PLBTBTC'
    },
    'XVG-USD': {
        HITBTC: 'XVGUSD'
    },
    'BCC-USD': {
        HITBTC: 'BCCUSD'
    },
    'CVC-USD': {
        HITBTC: 'CVCUSD'
    },
    'ANT-BTC': {
        HITBTC: 'ANTBTC'
    },
    'XVG-BTC': {
        HITBTC: 'XVGBTC'
    },
    'STAR-ETH': {
        HITBTC: 'STARETH'
    },
    'XDNCO-BTC': {
        HITBTC: 'XDNCOBTC'
    },
    'OTX-BTC': {
        HITBTC: 'OTXBTC'
    },
    'BNT-ETH': {
        HITBTC: 'BNTETH'
    },
    'PTOY-BTC': {
        HITBTC: 'PTOYBTC'
    },
    '1ST-ETH': {
        HITBTC: '1STETH'
    },
    'ICOS-USD': {
        HITBTC: 'ICOSUSD'
    },
    'AMB-USD': {
        HITBTC: 'AMBUSD'
    },
    'PTOY-ETH': {
        HITBTC: 'PTOYETH'
    },
    'SNC-ETH': {
        HITBTC: 'SNCETH'
    },
    'HVN-BTC': {
        HITBTC: 'HVNBTC'
    },
    'SNM-ETH': {
        HITBTC: 'SNMETH'
    },
    'ATS-BTC': {
        HITBTC: 'ATSBTC'
    },
    'PRO-ETH': {
        HITBTC: 'PROETH'
    },
    'MRV-ETH': {
        HITBTC: 'MRVETH'
    },
    'COSS-ETH': {
        HITBTC: 'COSSETH'
    },
    '1ST-BTC': {
        HITBTC: '1STBTC'
    },
    'EMGO-USD': {
        HITBTC: 'EMGOUSD'
    },
    'CFI-ETH': {
        HITBTC: 'CFIETH'
    },
    'FUN-USD': {
        HITBTC: 'FUNUSD'
    },
    'BOS-BTC': {
        HITBTC: 'BOSBTC'
    },
    'DGB-BTC': {
        HITBTC: 'DGBBTC'
    },
    'PRG-USD': {
        HITBTC: 'PRGUSD'
    },
    'BMT-BTC': {
        HITBTC: 'BMTBTC'
    },
    'DGD-BTC': {
        HITBTC: 'DGDBTC'
    },
    'DNT-BTC': {
        HITBTC: 'DNTBTC'
    },
    'NET-ETH': {
        HITBTC: 'NETETH'
    },
    'QCN-BTC': {
        HITBTC: 'QCNBTC'
    },
    'HSR-BTC': {
        HITBTC: 'HSRBTC'
    },
    'KMD-BTC': {
        HITBTC: 'KMDBTC'
    },
    'XTZ-ETH': {
        HITBTC: 'XTZETH'
    },
    'AMB-ETH': {
        HITBTC: 'AMBETH'
    },
    'TAAS-ETH': {
        HITBTC: 'TAASETH'
    },
    'PRGETH': {
        HITBTC: 'PRGETH'
    },
    'BNTUSD': {
        HITBTC: 'BNTUSD'
    },
    'ZECETH': {
        HITBTC: 'ZECETH'
    },
    'EVX-BTC': {
        HITBTC: 'EVXBTC'
    },
    'TNT-BTC': {
        HITBTC: 'TNTBTC'
    },
    'DIM-BTC': {
        HITBTC: 'DIMBTC'
    },
    'AMM-USD': {
        HITBTC: 'AMMUSD'
    },
    'ENJ-BTC': {
        HITBTC: 'ENJBTC'
    },
    'DOGE-USD': {
        HITBTC: 'DOGEUSD'
    },
    'BAS-ETH': {
        HITBTC: 'BASETH'
    },
    'OAX-BTC': {
        HITBTC: 'OAXBTC'
    },
    'ARN-BTC': {
        HITBTC: 'ARNBTC'
    },
    'AIRBTC': {
        HITBTC: 'AIRBTC'
    },
    'XTZ-BTC': {
        HITBTC: 'XTZBTC'
    },
    'BTCA-ETH': {
        HITBTC: 'BTCAETH'
    },
    'CDX-ETH': {
        HITBTC: 'CDXETH'
    },
    'LOC-USD': {
        HITBTC: 'LOCUSD'
    },
    'MYB-ETH': {
        HITBTC: 'MYBETH'
    },
    'XEM-ETH': {
        HITBTC: 'XEMETH'
    },
    'NGC-BTC': {
        HITBTC: 'NGCBTC'
    },
    'STRAT-BTC': {
        HITBTC: 'STRATBTC'
    },
    'MANA-USD': {
        HITBTC: 'MANAUSD'
    },
    'MAID-BTC': {
        HITBTC: 'MAIDBTC'
    },
    'SBTC-ETH': {
        HITBTC: 'SBTCETH'
    },
    'WRC-USD': {
        HITBTC: 'WRCUSD'
    },
    'CDT-ETH': {
        HITBTC: 'CDTETH'
    },
    'EMC-ETH': {
        HITBTC: 'EMCETH'
    },
    'CL-BTC': {
        HITBTC: 'CLBTC'
    },
    'POLL-BTC': {
        HITBTC: 'POLLBTC'
    },
    'XDN-BTC': {
        HITBTC: 'XDNBTC'
    },
    'XVG-ETH': {
        HITBTC: 'XVGETH'
    },
    'NGC-ETH': {
        HITBTC: 'NGCETH'
    },
    'XDN-ETH': {
        HITBTC: 'XDNETH'
    },
    'PLR-BTC': {
        HITBTC: 'PLRBTC'
    },
    'DASH-ETH': {
        HITBTC: 'DASHETH'
    },
    'YOYOW-BTC': {
        HITBTC: 'YOYOWBTC'
    },
    'BCN-BTC': {
        HITBTC: 'BCNBTC'
    },
    'CRS-USD': {
        HITBTC: 'CRSUSD'
    },
    'UET-ETH': {
        HITBTC: 'UETETH'
    },
    'DGB-USD': {
        HITBTC: 'DGBUSD'
    },
    'KMD-ETH': {
        HITBTC: 'KMDETH'
    },
    'UTT-ETH': {
        HITBTC: 'UTTETH'
    },
    'BTM-USD': {
        HITBTC: 'BTMUSD'
    },
    'WINGS-BTC': {
        HITBTC: 'WINGSBTC'
    },
    'EVX-ETH': {
        HITBTC: 'EVXETH'
    },
    'WTC-BTC': {
        HITBTC: 'WTCBTC'
    },
    'SBTC-USDT': {
        HITBTC: 'SBTCUSDT'
    },
    'XEM-BTC': {
        HITBTC: 'XEMBTC'
    },
    'LEND-ETH': {
        HITBTC: 'LENDETH'
    },
    'PRG-BTC': {
        HITBTC: 'PRGBTC'
    },
    'POE-ETH': {
        HITBTC: 'POEETH'
    },
    'CFI-BTC': {
        HITBTC: 'CFIBTC'
    },
    'VIB-BTC': {
        HITBTC: 'VIBBTC'
    },
    'RLC-BTC': {
        HITBTC: 'RLCBTC'
    },
    'BKB-BTC': {
        HITBTC: 'BKBBTC'
    },
    'ICO-BTC': {
        HITBTC: 'ICOBTC'
    },
    'SUR-ETH': {
        HITBTC: 'SURETH'
    },
    'ENJ-USD': {
        HITBTC: 'ENJUSD'
    },
    'LAT-BTC': {
        HITBTC: 'LATBTC'
    },
    'VOISE-BTC': {
        HITBTC: 'VOISEBTC'
    },
    'POE-BTC': {
        HITBTC: 'POEBTC'
    },
    'QVT-ETH': {
        HITBTC: 'QVTETH'
    },
    'LEND-BTC': {
        HITBTC: 'LENDBTC'
    },
    'PIX-BTC': {
        HITBTC: 'PIXBTC'
    },
    'BCN-ETH': {
        HITBTC: 'BCNETH'
    },
    'CDT-USD': {
        HITBTC: 'CDTUSD'
    },
    'WAVES-BTC': {
        HITBTC: 'WAVESBTC'
    },
    'TIME-BTC': {
        HITBTC: 'TIMEBTC'
    },
    'SWFTC-ETH': {
        HITBTC: 'SWFTCETH'
    },
    'OTN-BTC': {
        HITBTC: 'OTNBTC'
    },
    'TIX-ETH': {
        HITBTC: 'TIXETH'
    },
    'ECAT-ETH': {
        HITBTC: 'ECATETH'
    },
    'MTH-ETH': {
        HITBTC: 'MTHETH'
    },
    'STX-USD': {
        HITBTC: 'STXUSD'
    },
    'SMART-USD': {
        HITBTC: 'SMARTUSD'
    },
    'EBET-ETH': {
        HITBTC: 'EBETETH'
    },
    'VEN-USD': {
        HITBTC: 'VENUSD'
    },
    'EUR-USD': {
        BITSTAMP: 'eurusd'
    },
    'XRP-EUR': {
        BITSTAMP: 'xrpeur'
    },
    'BCH-EUR': {
        BITSTAMP: 'bcheur'
    }
}

_exchange_to_std = {
    'BTC-USD': 'BTC-USD',
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
    # Bitfinex
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
    # HitBTC
    'CTRETH': 'CTR-ETH',
    'FYPBTC': 'FYP-BTC',
    'TRSTBTC': 'TRST-BTC',
    'SWFTCUSD': 'SWFTC-USD',
    'HDGETH': 'HDG-ETH',
    'DSHBTC': 'DSH-BTC',
    'VIBUSD': 'VIB-USD',
    'CPAYETH': 'CPAY-ETH',
    'AMMETH': 'AMM-ETH',
    'XUCETH': 'XUC-ETH',
    'ZRCBTC': 'ZRC-BTC',
    'AMMBTC': 'AMM-BTC',
    'COSSBTC': 'COSS-BTC',
    'LAETH': 'LA-ETH',
    'XMRETH': 'XMR-ETH',
    'UGTUSD': 'UGT-USD',
    'SANETH': 'SAN-ETH',
    'EBTCNEWUSD': 'EBTCNEW-USD',
    'VERIETH': 'VERI-ETH',
    'XMRUSD': 'XMR-USD',
    'AIRUSD': 'AIR-USD',
    'INDIBTC': 'INDI-BTC',
    'AMPBTC': 'AMP-BTC',
    'FUELUSD': 'FUEL-USD',
    'BTGUSD': 'BTG-USD',
    'XEMUSD': 'XEM-USD',
    'WMGOUSD': 'WMGO-USD',
    'CLDBTC': 'CLD-BTC',
    'ICXETH': 'ICX-ETH',
    'PRSBTC': 'PRS-BTC',
    'NEOBTC': 'NEO-BTC',
    'RKCETH': 'RKC-ETH',
    'MNEBTC': 'MNE-BTC',
    'EMCUSDT': 'EMCU-SDT',
    'ARTBTC': 'ART-BTC',
    'RVTBTC': 'RVT-BTC',
    'EOSUSD': 'EOS-USD',
    'HACBTC': 'HAC-BTC',
    'DOVETH': 'DOV-ETH',
    'CNDBTC': 'CND-BTC',
    'ICOSBTC': 'ICOS-BTC',
    'PPTBTC': 'PPT-BTC',
    'SISAETH': 'SISA-ETH',
    'NEOETH': 'NEO-ETH',
    'EBTCNEWETH': 'EBTCNEW-ETH',
    'SNCUSD': 'SNC-USD',
    'DENTETH': 'DENT-ETH',
    'NEBLETH': 'NEBL-ETH',
    'BTMETH': 'BTM-ETH',
    'XRPETH': 'XRP-ETH',
    'ATBBTC': 'ATB-BTC',
    'EDOBTC': 'EDO-BTC',
    'XTZUSD': 'XTZ-USD',
    'BTXUSDT': 'BTX-USDT',
    'ARNETH': 'ARN-ETH',
    'DDFETH': 'DDF-ETH',
    'SUBUSD': 'SUB-USD',
    'IGNISETH': 'IGNIS-ETH',
    'DICEBTC': 'DICE-BTC',
    'LTCBTC': 'LTC-BTC',
    'LUNBTC': 'LUN-BTC',
    'DIMETH': 'DIM-ETH',
    'SWTBTC': 'SWT-BTC',
    'GNOETH': 'GNO-ETH',
    'STRATUSD': 'STRAT-USD',
    'ADXETH': 'ADX-ETH',
    'STXBTC': 'STX-BTC',
    'SBDBTC': 'SBD-BTC',
    'BQXETH': 'BQX-ETH',
    'PAYETH': 'PAY-ETH',
    'PLUETH': 'PLU-ETH',
    'XRPUSDT': 'XRP-USDT',
    'EOSBTC': 'EOS-BTC',
    'VENETH': 'VEN-ETH',
    'EMCBTC': 'EMC-BTC',
    'PQTUSD': 'PQT-USD',
    'KICKBTC': 'KICK-BTC',
    'ETBSBTC': 'ETBS-BTC',
    'ICXUSD': 'ICX-USD',
    'ENJETH': 'ENJ-ETH',
    'ZRXETH': 'ZRX-ETH',
    'BCHUSD': 'BCH-USD',
    'NXTETH': 'NXT-ETH',
    'DRPUETH': 'DRPU-ETH',
    'MCAPBTC': 'MCAP-BTC',
    'OMGBTC': 'OMG-BTC',
    'OAXETH': 'OAX-ETH',
    'NTOBTC': 'NTO-BTC',
    'SPFETH': 'SPF-ETH',
    'BQXBTC': 'BQX-BTC',
    'TKNBTC': 'TKN-BTC',
    'B2XUSD': 'B2X-USD',
    'DGBETH': 'DGB-ETH',
    'HVNETH': 'HVN-ETH',
    'B2XETH': 'B2X-ETH',
    'B2XBTC': 'B2X-BTC',
    'EBTCOLDETH': 'EBTCOLD-ETH',
    'ETCBTC': 'ETC-BTC',
    'CLDUSD': 'CLD-USD',
    'CTXETH': 'CTX-ETH',
    'VERIBTC': 'VERI-BTC',
    'TRXUSD': 'TRX-USD',
    'HPCBTC': 'HPC-BTC',
    'LTCETH': 'LTC-ETH',
    'BCCBTC': 'BCC-BTC',
    'TBTBTC': 'TBT-BTC',
    'SUBBTC': 'SUB-BTC',
    'ZAPBTC': 'ZAP-BTC',
    'QAUBTC': 'QAU-BTC',
    'QTUMETH': 'QTUM-ETH',
    'GVTETH': 'GVT-ETH',
    'NDCETH': 'NDC-ETH',
    'DATAUSD': 'DATA-USD',
    'CNDETH': 'CND-ETH',
    'XAURBTC': 'XAUR-BTC',
    'SMSUSD': 'SMS-USD',
    'ICNBTC': 'ICN-BTC',
    'FUNETH': 'FUN-ETH',
    'DCTBTC': 'DCT-BTC',
    'TRXETH': 'TRX-ETH',
    'PLUBTC': 'PLU-BTC',
    'PAYBTC': 'PAY-BTC',
    'AIRETH': 'AIR-ETH',
    'LRCETH': 'LRC-ETH',
    'VERIUSD': 'VERI-USD',
    'BMCUSD': 'BMC-USD',
    'OMGETH': 'OMG-ETH',
    'SNCBTC': 'SNC-BTC',
    'FCNBTC': 'FCN-BTC',
    'EDGBTC': 'EDG-BTC',
    'SUBETH': 'SUB-ETH',
    'PPCBTC': 'PPC-BTC',
    'UGTBTC': 'UGT-BTC',
    'BETETH': 'BET-ETH',
    'UTTUSD': 'UTT-USD',
    'MCOUSD': 'MCO-USD',
    'BTGETH': 'BTG-ETH',
    'ATMUSD': 'ATM-USD',
    'HGTETH': 'HGT-ETH',
    'CTRBTC': 'CTR-BTC',
    'LRCBTC': 'LRC-BTC',
    'ZECBTC': 'ZEC-BTC',
    'STXETH': 'STX-ETH',
    'MCOBTC': 'MCO-BTC',
    'ZSCETH': 'ZSC-ETH',
    'KBRBTC': 'KBR-BTC',
    'TGTBTC': 'TGT-BTC',
    'DCNUSD': 'DCN-USD',
    'FYNETH': 'FYN-ETH',
    'EBTCOLDUSD': 'EBTCOLD-USD',
    '8BTUSD': '8BT-USD',
    'DLTBTC': 'DLT-BTC',
    'OAXUSD': 'OAX-USD',
    'EXNBTC': 'EXN-BTC',
    'ITSBTC': 'ITS-BTC',
    'ORMEBTC': 'ORME-BTC',
    'CSNOBTC': 'CSNO-BTC',
    'UTTBTC': 'UTT-BTC',
    'SCBTC': 'SC-BTC',
    'WRCETH': 'WRC-ETH',
    'BCHBTC': 'BCH-BTC',
    'ATMBTC': 'ATM-BTC',
    'CCTETH': 'CCT-ETH',
    'EDOUSD': 'EDO-USD',
    'SMARTBTC': 'SMART-BTC',
    'NXTUSD': 'NXT-USD',
    'ELMBTC': 'ELM-BTC',
    'FUNBTC': 'FUN-BTC',
    'BMCBTC': 'BMC-BTC',
    'ETCUSD': 'ETC-USD',
    'DIMUSD': 'DIM-USD',
    'SMSBTC': 'SMS-BTC',
    'MIPSBTC': 'MIPS-BTC',
    'REPBTC': 'REP-BTC',
    'DCNETH': 'DCN-ETH',
    'DRPUBTC': 'DRPU-BTC',
    'FUELETH': 'FUEL-ETH',
    'ZECUSD': 'ZEC-USD',
    'DOGEETH': 'DOGE-ETH',
    'EMGOBTC': 'EMGO-BTC',
    'ECHBTC': 'ECH-BTC',
    'BTGBTC': 'BTG-BTC',
    'PINGBTC': 'PING-BTC',
    'AEBTC': 'AE-BTC',
    'DICEETH': 'DICE-ETH',
    'IXTETH': 'IXT-ETH',
    'ICOSETH': 'ICOS-ETH',
    'IXTBTC': 'IXT-BTC',
    'ATMETH': 'ATM-ETH',
    'AEONBTC': 'AEON-BTC',
    'MANAETH': 'MANA-ETH',
    'SNTETH': 'SNT-ETH',
    'PPCUSD': 'PPC-USD',
    'STORMBTC': 'STORM-BTC',
    'XMRBTC': 'XMR-BTC',
    'ATLBTC': 'ATL-BTC',
    'CATBTC': 'CAT-BTC',
    'NXTBTC': 'NXT-BTC',
    'CNXBTC': 'CNX-BTC',
    'EBTCNEWBTC': 'EBTCNEW-BTC',
    'STUUSD': 'STU-USD',
    'ODNBTC': 'ODN-BTC',
    'CTXBTC': 'CTX-BTC',
    'ZRXBTC': 'ZRX-BTC',
    'BTMBTC': 'BTM-BTC',
    'BTCABTC': 'BTCA-BTC',
    'GNOBTC': 'GNO-BTC',
    'XUCBTC': 'XUC-BTC',
    'TNTETH': 'TNT-ETH',
    'BMTETH': 'BMT-ETH',
    'BUSBTC': 'BUS-BTC',
    'DASHUSD': 'DASH-USD',
    'INDETH': 'IND-ETH',
    'SMSETH': 'SMS-ETH',
    'MAIDUSD': 'MAID-USD',
    'TNTUSD': 'TNT-USD',
    'DOGEBTC': 'DOGE-BTC',
    'FRDBTC': 'FRD-BTC',
    'STRATETH': 'STRAT-ETH',
    'OPTBTC': 'OPT-BTC',
    'NXCBTC': 'NXC-BTC',
    'ARDRBTC': 'ARDR-BTC',
    'MSPETH': 'MSP-ETH',
    'ZSCUSD': 'ZSC-USD',
    'SISABTC': 'SISA-BTC',
    'MTHBTC': 'MTH-BTC',
    'ZSCBTC': 'ZSC-BTC',
    'DRTETH': 'DRT-ETH',
    'QAUETH': 'QAU-ETH',
    'SKINBTC': 'SKIN-BTC',
    'BCCETH': 'BCC-ETH',
    'VENBTC': 'VEN-BTC',
    'GUPBTC': 'GUP-BTC',
    'CATUSD': 'CAT-USD',
    'NGCUSD': 'NGC-USD',
    'BCNUSD': 'BCN-USD',
    'ETPUSD': 'ETP-USD',
    'SWTETH': 'SWT-ETH',
    'XUCUSD': 'XUC-USD',
    'TIMEETH': 'TIME-ETH',
    'DOVBTC': 'DOV-BTC',
    'ATBUSD': 'ATB-USD',
    'CDTBTC': 'CDT-BTC',
    'BTXBTC': 'BTX-BTC',
    'STUBTC': 'STU-BTC',
    'LOCETH': 'LOC-ETH',
    'BTCAUSD': 'BTCA-USD',
    'XDNUSD': 'XDN-USD',
    'CLDETH': 'CLD-ETH',
    'AMBBTC': 'AMB-BTC',
    'EVXUSD': 'EVX-USD',
    'VIBETH': 'VIB-ETH',
    'CLETH': 'CL-ETH',
    'WRCBTC': 'WRC-BTC',
    'EBTCOLDBTC': 'EBTCOLD-BTC',
    'ELEBTC': 'ELE-BTC',
    'VIBEBTC': 'VIBE-BTC',
    'CATETH': 'CAT-ETH',
    'GAMEBTC': 'GAME-BTC',
    'DATAETH': 'DATA-ETH',
    'ATSETH': 'ATS-ETH',
    'BNTBTC': 'BNT-BTC',
    'SNGLSBTC': 'SNGLS-BTC',
    'CNDUSD': 'CND-USD',
    'ZRXUSD': 'ZRX-USD',
    'SCLBTC': 'SCL-BTC',
    'ETCETH': 'ETC-ETH',
    'DATABTC': 'DATA-BTC',
    'MANABTC': 'MANA-BTC',
    'SWFTCBTC': 'SWFTC-BTC',
    'TAASBTC': 'TAAS-BTC',
    'SMARTETH': 'SMART-ETH',
    'WTTBTC': 'WTT-BTC',
    'PREBTC': 'PRE-BTC',
    'SBTCBTC': 'SBTC-BTC',
    'LIFEBTC': 'LIFE-BTC',
    'CTRUSD': 'CTR-USD',
    'FUELBTC': 'FUEL-BTC',
    'WMGOBTC': 'WMGO-BTC',
    'NEBLBTC': 'NEBL-BTC',
    'PLRETH': 'PLR-ETH',
    'STUETH': 'STU-ETH',
    'TRXBTC': 'TRX-BTC',
    'SURBTC': 'SUR-BTC',
    'KMDUSD': 'KMD-USD',
    'MAIDETH': 'MAID-ETH',
    'ATBETH': 'ATB-ETH',
    'EROBTC': 'ERO-BTC',
    'LTCUSD': 'LTC-USD',
    'CLUSD': 'CL-USD',
    'DBIXBTC': 'DBIX-BTC',
    'TKRETH': 'TKR-ETH',
    'PIXETH': 'PIX-ETH',
    'BMCETH': 'BMC-ETH',
    'PPTETH': 'PPT-ETH',
    'MCOETH': 'MCO-ETH',
    'LSKBTC': 'LSK-BTC',
    'XAURETH': 'XAUR-ETH',
    'UGTETH': 'UGT-ETH',
    'LOCBTC': 'LOC-BTC',
    'STEEMBTC': 'STEE-MBTC',
    'BCHETH': 'BCH-ETH',
    'ICXBTC': 'ICX-BTC',
    'PLBTBTC': 'PLBT-BTC',
    'XVGUSD': 'XVG-USD',
    'BCCUSD': 'BCC-USD',
    'CVCUSD': 'CVC-USD',
    'ANTBTC': 'ANT-BTC',
    'XVGBTC': 'XVG-BTC',
    'STARETH': 'STAR-ETH',
    'XDNCOBTC': 'XDNCO-BTC',
    'OTXBTC': 'OTX-BTC',
    'BNTETH': 'BNT-ETH',
    'PTOYBTC': 'PTOY-BTC',
    '1STETH': '1ST-ETH',
    'ICOSUSD': 'ICOS-USD',
    'AMBUSD': 'AMB-USD',
    'PTOYETH': 'PTOY-ETH',
    'SNCETH': 'SNC-ETH',
    'HVNBTC': 'HVN-BTC',
    'SNMETH': 'SNM-ETH',
    'NEOUSD': 'NEO-USD',
    'ATSBTC': 'ATS-BTC',
    'AVTETH': 'AVT-ETH',
    'PROETH': 'PRO-ETH',
    'EDOETH': 'EDO-ETH',
    'MRVETH': 'MRV-ETH',
    'COSSETH': 'COSS-ETH',
    '1STBTC': '1ST-BTC',
    'EMGOUSD': 'EMGO-USD',
    'CFIETH': 'CFI-ETH',
    'FUNUSD': 'FUN-USD',
    'BOSBTC': 'BOS-BTC',
    'DGBBTC': 'DGB-BTC',
    'PRGUSD': 'PRG-USD',
    'BMTBTC': 'BMT-BTC',
    'DGDBTC': 'DGD-BTC',
    'DNTBTC': 'DNT-BTC',
    'DASHBTC': 'DASH-BTC',
    'NETETH': 'NET-ETH',
    'QCNBTC': 'QCN-BTC',
    'HSRBTC': 'HSR-BTC',
    'KMDBTC': 'KMD-BTC',
    'XTZETH': 'XTZ-ETH',
    'AMBETH': 'AMB-ETH',
    'TAASETH': 'TAAS-ETH',
    'PRGETH': 'PRGETH',
    'BNTUSD': 'BNTUSD',
    'ZECETH': 'ZECETH',
    'EVXBTC': 'EVX-BTC',
    'TNTBTC': 'TNT-BTC',
    'DIMBTC': 'DIM-BTC',
    'AMMUSD': 'AMM-USD',
    'ENJBTC': 'ENJ-BTC',
    'DOGEUSD': 'DOGE-USD',
    'BASETH': 'BAS-ETH',
    'OAXBTC': 'OAX-BTC',
    'ARNBTC': 'ARN-BTC',
    'AIRBTC': 'AIRBTC',
    'XTZBTC': 'XTZ-BTC',
    'BTCAETH': 'BTCA-ETH',
    'CDXETH': 'CDX-ETH',
    'LOCUSD': 'LOC-USD',
    'MYBETH': 'MYB-ETH',
    'XEMETH': 'XEM-ETH',
    'NGCBTC': 'NGC-BTC',
    'STRATBTC': 'STRAT-BTC',
    'MANAUSD': 'MANA-USD',
    'MAIDBTC': 'MAID-BTC',
    'SBTCETH': 'SBTC-ETH',
    'WRCUSD': 'WRC-USD',
    'CDTETH': 'CDT-ETH',
    'EMCETH': 'EMC-ETH',
    'CLBTC': 'CL-BTC',
    'POLLBTC': 'POLL-BTC',
    'XDNBTC': 'XDN-BTC',
    'XVGETH': 'XVG-ETH',
    'NGCETH': 'NGC-ETH',
    'XDNETH': 'XDN-ETH',
    'PLRBTC': 'PLR-BTC',
    'DASHETH': 'DASH-ETH',
    'YOYOWBTC': 'YOYOW-BTC',
    'BCNBTC': 'BCN-BTC',
    'CRSUSD': 'CRS-USD',
    'UETETH': 'UET-ETH',
    'DGBUSD': 'DGB-USD',
    'ETPETH': 'ETP-ETH',
    'ETPBTC': 'ETP-BTC',
    'KMDETH': 'KMD-ETH',
    'UTTETH': 'UTT-ETH',
    'BTMUSD': 'BTM-USD',
    'WINGSBTC': 'WINGS-BTC',
    'EVXETH': 'EVX-ETH',
    'WTCBTC': 'WTC-BTC',
    'SBTCUSDT': 'SBTC-USDT',
    'XEMBTC': 'XEM-BTC',
    'LENDETH': 'LEND-ETH',
    'PRGBTC': 'PRG-BTC',
    'POEETH': 'POE-ETH',
    'XRPBTC': 'XRP-BTC',
    'CFIBTC': 'CFI-BTC',
    'SNTBTC': 'SNT-BTC',
    'VIBBTC': 'VIB-BTC',
    'RLCBTC': 'RLC-BTC',
    'BKBBTC': 'BKB-BTC',
    'ICOBTC': 'ICO-BTC',
    'SURETH': 'SUR-ETH',
    'ENJUSD': 'ENJ-USD',
    'LATBTC': 'LAT-BTC',
    'VOISEBTC': 'VOISE-BTC',
    'POEBTC': 'POE-BTC',
    'QVTETH': 'QVT-ETH',
    'LENDBTC': 'LEND-BTC',
    'PIXBTC': 'PIX-BTC',
    'BCNETH': 'BCN-ETH',
    'CDTUSD': 'CDT-USD',
    'WAVESBTC': 'WAVES-BTC',
    'TIMEBTC': 'TIME-BTC',
    'SWFTCETH': 'SWFTC-ETH',
    'OTNBTC': 'OTN-BTC',
    'TIXETH': 'TIX-ETH',
    'ECATETH': 'ECAT-ETH',
    'MTHETH': 'MTH-ETH',
    'STXUSD': 'STX-USD',
    'SMARTUSD': 'SMART-USD',
    'EBETETH': 'EBET-ETH',
    'VENUSD': 'VEN-USD',
    'EOSETH': 'EOS-ETH',
    # Bitstamp
    'btcusd': 'BTC-USD',
    'btceur': 'BTC-EUR',
    'eurusd': 'EUR-USD',
    'xrpusd': 'XRP-USD',
    'xrpeur': 'XRP-EUR',
    'xrpbtc': 'XRP-BTC',
    'ltcusd': 'LTC-USD',
    'ltceur': 'LTC-EUR',
    'ltcbtc': 'LTC-BTC',
    'ethusd': 'ETH-USD',
    'etheur': 'ETH-EUR',
    'ethbtc': 'ETH-BTC',
    'bchusd': 'BCH-USD',
    'bcheur': 'BCH-EUR',
    'bchbtc': 'BCH-BTC'
}

for pair in poloniex_trading_pairs:
    std = pair.replace("_", "-")
    _exchange_to_std[pair] = pair.replace("_", "-")
    if std in _std_trading_pairs:
        _std_trading_pairs[std][POLONIEX] = pair
    else:
        _std_trading_pairs[std] = {POLONIEX: pair}

kraken_pairs = get_kraken_pairs()

for kraken, std in kraken_pairs.items():
    if std in _std_trading_pairs:
        _std_trading_pairs[std][KRAKEN] = kraken
    else:
        _std_trading_pairs[std] = {KRAKEN: kraken}

_exchange_to_std.update(kraken_pairs)



def pair_std_to_exchange(pair, exchange):
    if pair in _std_trading_pairs:
        try:
            return _std_trading_pairs[pair][exchange]
        except KeyError:
            raise KeyError("{} is not configured/availble for {}".format(
                pair, exchange))
    else:
        if exchange == BITFINEX and '-' not in pair:
            return "f{}".format(pair)
        return None


def pair_exchange_to_std(pair):
    if pair in _exchange_to_std:
        return _exchange_to_std[pair]
    if pair[0] == 'f':
        return pair[1:]
    return None


def timestamp_normalize(exchange, ts):
    if exchange == BITMEX or exchange == COINBASE:
        ts = dt.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ")
        return calendar.timegm(ts.utctimetuple())
    elif exchange == 'BITFINEX':
        return ts / 1000.0
    return ts
