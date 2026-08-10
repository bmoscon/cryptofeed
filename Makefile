# cryptofeed developer tasks. Everything runs through uv, so `uv sync` is the only setup step.
.PHONY: help sync test test-all lint corpus corpus-missing corpus-verify bench clean

EXCHANGE ?=
SECONDS  ?= 45

help:
	@echo "make sync                     install the dev environment"
	@echo "make test                     the PR gate: unit + playback, offline"
	@echo "make test-all                 every layer except live"
	@echo "make lint                     ruff check"
	@echo "make corpus                   re-record every exchange (hits live venues)"
	@echo "make corpus EXCHANGE=KRAKEN   re-record one exchange"
	@echo "make corpus-missing           record only exchanges that have no recording"
	@echo "make corpus-verify            validate every stored recording, offline"
	@echo "make bench                    run the benchmark layer"
	@echo "make bench-replay             corpus replay throughput and peak RSS"

sync:
	uv sync

test:
	uv run pytest -m 'unit or playback'

test-all:
	uv run pytest -m 'unit or playback or backend or bench'

lint:
	uv run ruff check .

# recording hits live venues, so it never runs in CI - several exchanges rate limit or
# geo-block cloud IP ranges
corpus:
ifeq ($(EXCHANGE),)
	uv run python tools/record_corpus.py --all --seconds $(SECONDS) --force
else
	uv run python tools/record_corpus.py --exchange $(EXCHANGE) --seconds $(SECONDS) --force
endif

corpus-missing:
	uv run python tools/record_corpus.py --missing --seconds $(SECONDS)

corpus-verify:
	uv run python tools/corpus_verify.py --all

bench:
	uv run pytest -m bench

bench-replay:
	uv run python tools/bench_replay.py

clean:
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	rm -rf build dist *.egg-info
