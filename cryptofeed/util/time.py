'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


This file contains helper functions for performance instrumentation
'''
from pandas import Timedelta


def timedelta_str_to_sec(td: str):
    return Timedelta(td).seconds
