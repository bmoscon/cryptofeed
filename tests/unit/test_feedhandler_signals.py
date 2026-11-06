import importlib
import signal

import pytest

import cryptofeed.feedhandler as feedhandler


pytestmark = pytest.mark.unit


def test_missing_sighup_import(monkeypatch):
    monkeypatch.delattr(signal, 'SIGHUP', raising=False)
    try:
        reloaded = importlib.reload(feedhandler)
        expected = {signal.SIGABRT, signal.SIGINT, signal.SIGTERM}
        if hasattr(signal, 'SIGBREAK'):
            expected.add(signal.SIGBREAK)
        assert set(reloaded.SIGNALS) == expected
    finally:
        monkeypatch.undo()
        importlib.reload(feedhandler)


class _FakeLoop:
    def __init__(self):
        self.scheduled = []
        self.removed = []

    def add_signal_handler(self, sig, callback):
        raise NotImplementedError

    def remove_signal_handler(self, sig):
        self.removed.append(sig)
        return True

    def call_soon_threadsafe(self, callback):
        self.scheduled.append(callback)


def test_signal_fallback(monkeypatch):
    fake = _FakeLoop()
    fh = feedhandler.FeedHandler(config={'log': {'disabled': True}})
    installed = {}
    original = {sig: signal.getsignal(sig) for sig in feedhandler.SIGNALS}

    def fake_signal(sig, handler):
        prev = installed.get(sig, original[sig])
        installed[sig] = handler
        return prev

    monkeypatch.setattr(signal, 'signal', fake_signal)

    fh._install_signal_handlers(fake)
    assert fh._signals_installed
    assert set(installed) == set(feedhandler.SIGNALS)
    assert set(fh._prev_handlers) == set(feedhandler.SIGNALS)

    callback = installed[feedhandler.SIGNALS[0]]
    callback()
    assert fh._on_signal in fake.scheduled

    fh._remove_signal_handlers(fake)
    assert not fh._signals_installed
    assert fh._prev_handlers == {}
    assert installed == original
    assert fake.removed == []
