'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


Python 3.14 has compression.zstd in the standard library but
3.12 and 3.13 need the zstandard package
'''
import io

try:
    # Python 3.14+
    from compression import zstd as _impl

    BACKEND = 'stdlib'
except ImportError:
    try:
        # 3.12 / 3.13
        import zstandard as _impl

        BACKEND = 'zstandard'
    except ImportError:
        _impl = None
        BACKEND = None


AVAILABLE = BACKEND is not None
SUFFIX = '.zst'
LEVEL = 10


def open(path, mode='rb'):
    # Open a zstd compressed file
    if _impl is None:
        raise RuntimeError('no zstd implementation available - install zstandard or use Python 3.14+')
    writing = 'w' in mode or 'a' in mode
    if BACKEND == 'stdlib':
        return _impl.open(path, mode, level=LEVEL) if writing else _impl.open(path, mode)
    if writing:
        return _impl.open(path, mode, cctx=_impl.ZstdCompressor(level=LEVEL))
    return io.BufferedReader(_impl.open(path, mode))
