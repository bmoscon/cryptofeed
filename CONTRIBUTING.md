## Contributing Guidelines

PRs, bug reports, feature requests, documentation, and other enhancements and improvements are welcomed. Please have a look at this checklist before contributing

### For Issues

* Is this a question? Questions are permitted, but a better way to get support for questions is to join the slack channel and ask there (Link in README), or open a thread in the repository's Discussions tab.
* Is this something that is extremely specific to your use case, or will it likely be useful and beneficial to other users of the library? 
* Do you have an idea for what you are requesting? If so, please include that! Details are helpful.
* For bug reports please include a way to reproduce the issue - issues that cannot be reproduced cannot be fixed and will be closed.
* For new exchange requests please include links to the API documentation.


### For PRs

* Has it been tested? How? See the test layers below - your change should come with a test in the layer that fits it.
* Does the code style match the overall code style of the project? Long lines are preferred, so please do not use formatters that turn 1 line into 4 lines.
* Please use type annotations.
* Please run `uv run ruff check .` and fix anything it uncovers (ruff replaced flake8 in 2.5.0).

### Running the tests

The suite is split into five layers. A test's layer is determined by the directory it lives in, so
put a new test file in the directory that matches what it needs:

| Layer | Directory | Needs | Runs |
|---|---|---|---|
| `unit` | `tests/unit/` | nothing - offline, no services | every PR |
| `playback` | `tests/playback/` | the recorded captures in `sample_data/` | every PR |
| `backend` | `tests/backend/` | backend services (redis, postgres, ...) | every PR, one CI job |
| `live` | `tests/live/` | network access to real exchanges | nightly only |
| `bench` | `tests/bench/` | nothing, but slow | on demand, release branches |

```console
uv sync                              # install the dev group
uv run pytest                        # the PR gate: unit + playback, fully offline
uv run pytest -m unit                # one layer
uv run pytest -m playback -k kraken  # one exchange's replay
uv run pytest -m backend             # needs services running locally
uv run pytest -m live                # hits real exchanges - run deliberately, never in bulk
uv run pytest -m bench               # benchmarks
```

Anything that touches the network outside `tests/live/` is a bug in the test. The default
`pytest` invocation must stay runnable on a laptop with no network and no services.
