'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.

The zstd shim, which has two backends that do not behave identically.
'''
import pytest

from cryptofeed import _zstd


pytestmark = pytest.mark.skipif(not _zstd.AVAILABLE, reason='no zstd implementation available')

LINES = [f'{{"n": {i}, "payload": "value-{i}"}}' for i in range(500)]


@pytest.fixture
def corpus(tmp_path):
    path = tmp_path / f'test.jsonl{_zstd.SUFFIX}'
    with _zstd.open(str(path), 'wb') as fp:
        for line in LINES:
            fp.write((line + '\n').encode())
    return str(path)


def test_backend_is_known():
    assert _zstd.BACKEND in ('stdlib', 'zstandard')


def test_round_trip(corpus):
    with _zstd.open(corpus, 'rb') as fp:
        assert fp.read().decode().splitlines() == LINES


def test_readline(corpus):
    with _zstd.open(corpus, 'rb') as fp:
        assert fp.readline().decode().strip() == LINES[0]
        assert fp.readline().decode().strip() == LINES[1]


def test_iteration_after_readline(corpus):
    with _zstd.open(corpus, 'rb') as fp:
        fp.readline()
        rest = [line.decode().strip() for line in fp if line.strip()]
    assert rest == LINES[1:]


def test_incremental_writes_are_readable(corpus):
    with _zstd.open(corpus, 'rb') as fp:
        assert len(fp.read().decode().splitlines()) == len(LINES)


def test_compression_actually_happens(corpus):
    import os

    raw = sum(len(line) + 1 for line in LINES)
    assert os.path.getsize(corpus) < raw / 2, 'the file is not meaningfully compressed'
