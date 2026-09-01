'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import io


ZSTD_MAGIC = b'\x28\xb5\x2f\xfd'
DEFAULT_LEVEL = 3

try:
    from compression.zstd import ZstdFile as _ZstdFile

    BACKEND = 'compression.zstd'

    def open_write(path: str, level: int = DEFAULT_LEVEL):
        return _ZstdFile(path, 'wb', level=level)

    def open_read(path: str):
        return _ZstdFile(path, 'rb')

except ImportError:
    try:
        import zstandard as _zstandard

        BACKEND = 'zstandard'

        def open_write(path: str, level: int = DEFAULT_LEVEL):
            return _zstandard.open(path, 'wb', cctx=_zstandard.ZstdCompressor(level=level))

        def open_read(path: str):
            return io.BufferedReader(_zstandard.open(path, 'rb'))

    except ImportError:
        try:
            import pyzstd as _pyzstd

            BACKEND = 'pyzstd'

            def open_write(path: str, level: int = DEFAULT_LEVEL):
                return _pyzstd.ZstdFile(path, 'wb', level_or_option=level)

            def open_read(path: str):
                return _pyzstd.ZstdFile(path, 'rb')

        except ImportError:
            BACKEND = None

            def _unavailable(*args, **kwargs):
                raise RuntimeError("must install zstandard")

            open_write = open_read = _unavailable
