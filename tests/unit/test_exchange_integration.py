import os

from cryptofeed.feedhandler import _EXCHANGES


def test_exchanges_fh():
    """
    Ensure all exchanges are in feedhandler's string to class mapping
    """
    path = os.path.dirname(os.path.abspath(__file__))
    files = os.listdir(f"{path}/../../cryptofeed/exchange")
    files = [f for f in files if '__' not in f]
    assert(len(files) == len(_EXCHANGES))
