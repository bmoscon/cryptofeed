'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import os

from cryptofeed.capture.recorder import metadata_path


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_DATA = os.path.join(ROOT, 'sample_data')
CONFIG = os.path.join(ROOT, 'tests', 'config_test.yaml')


def capture_path(exchange: str) -> str:
    return os.path.join(SAMPLE_DATA, f'{exchange}.pcap.zst')


def read_metadata(exchange: str) -> dict:
    with open(metadata_path(capture_path(exchange))) as fp:
        return json.load(fp)


def feed_entry(exchange: str) -> dict:
    return next(entry for entry in read_metadata(exchange)['feeds'] if entry['exchange'] == exchange)
