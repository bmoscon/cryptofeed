'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import os

from cryptofeed.capture import Replayer, playback
from cryptofeed.capture.recorder import metadata_path
from cryptofeed.defines import INDEPENDENT_RESERVE


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, 'tests', 'config_test.yaml')
DEFAULT_SAMPLE_DATA = os.path.join(ROOT, 'sample_data', 'small')

# attributes to inject before replay
feed_overrides = {
    INDEPENDENT_RESERVE: {'request_limit': 1_000_000, 'SNAPSHOT_STALENESS_WAIT': 0},
}


def sample_data() -> str:
    return os.environ.get('CRYPTOFEED_SAMPLE_DATA') or DEFAULT_SAMPLE_DATA


def capture_path(exchange: str) -> str:
    return os.path.join(sample_data(), f'{exchange}.pcap.zst')


def read_metadata(exchange: str) -> dict:
    with open(metadata_path(capture_path(exchange))) as fp:
        return json.load(fp)


def feed_entry(exchange: str) -> dict:
    return next(entry for entry in read_metadata(exchange)['feeds'] if entry['exchange'] == exchange)


def expected_callbacks() -> dict:
    with open(os.path.join(sample_data(), 'expected_callbacks.json')) as fp:
        return json.load(fp)


def replay(exchange: str):
    path = capture_path(exchange)
    feed = None

    if exchange in feed_overrides:
        feed = Replayer(path).build_feed(config=CONFIG)
        for attr, value in feed_overrides[exchange].items():
            setattr(feed, attr, value)

    return playback(path, feed=feed, config=CONFIG, on_error='raise')
