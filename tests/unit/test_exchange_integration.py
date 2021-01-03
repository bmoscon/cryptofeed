import os

from cryptofeed.feedhandler import _EXCHANGES


def test_exchanges_fh():
    """
    Ensure all exchanges are in feedhandler's string to class mapping
    """
    path = os.path.dirname(os.path.abspath(__file__))
    files = os.listdir(f"{path}/../../cryptofeed/exchange")
    files += os.listdir(f"{path}/../../cryptofeed/provider")
    files = [f for f in files if '__' not in f]
    files = [f[:-3].upper() for f in files]  # Drop extension .py and uppercase
    assert(sorted(files) == sorted(_EXCHANGES))
