'''
Copyright (C) 2017-2021  Michael Zhao - mr_michaelzhao@hotmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


A set of helper functions for getting instrument info
'''

from cryptofeed.defines import PERPETURAL, OPTION, FUTURE

def get_instrument_type(instrument_name: str):
    if instrument_name.endswith("-PERPETUAL"):
        return PERPETURAL
    elif instrument_name.endswith("-C") or instrument_name.endswith("-P"):
        return OPTION
    else:
        return FUTURE