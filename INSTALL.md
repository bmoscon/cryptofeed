# Cryptofeed Installation

The Cryptofeed library is intended for use by Python developers.

**Requirements:**

- Python 3.9+
- Optional: [uv](https://github.com/astral-sh/uv) for faster dependency management

## Installation Methods

### Using uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package manager with superior dependency resolution and installation speed.

**1. Install uv:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**2. Basic Installation:**

```bash
uv add cryptofeed
```

**3. With All Optional Dependencies:**

```bash
uv add cryptofeed[all]
```

### Using pip (Traditional)

**Basic Installation:**

```bash
pip install --user --upgrade cryptofeed
```

**With All Optional Dependencies:**

```bash
pip install --user --upgrade cryptofeed[all]
```

## Backend-Specific Installation

Cryptofeed supports many backends including Redis, ZeroMQ, RabbitMQ, MongoDB, PostgreSQL, Google Cloud, and others. Backend dependencies are optional to minimize installation footprint.

### Using uv

- **All backends:**

  ```bash
  uv add cryptofeed[all]
  ```

- **Arctic backend:**

  ```bash
  uv add cryptofeed[arctic]
  ```

- **Google Cloud Pub/Sub backend:**

  ```bash
  uv add cryptofeed[gcp_pubsub]
  ```

- **Kafka backend:**

  ```bash
  uv add cryptofeed[kafka]
  ```

- **MongoDB backend:**

  ```bash
  uv add cryptofeed[mongo]
  ```

- **PostgreSQL backend:**

  ```bash
  uv add cryptofeed[postgres]
  ```

- **QuasarDB backend:**

  ```bash
  uv add cryptofeed[quasardb]
  ```

- **RabbitMQ backend:**

  ```bash
  uv add cryptofeed[rabbit]
  ```

- **Redis backend:**

  ```bash
  uv add cryptofeed[redis]
  ```

- **ZeroMQ backend:**
  ```bash
  uv add cryptofeed[zmq]
  ```

### Using pip

Replace `uv add` with `pip install --user --upgrade` for any of the above commands.

## Development Installation

### Using uv (Recommended)

**1. Clone the repository:**

```bash
git clone https://github.com/bmoscon/cryptofeed.git
cd cryptofeed
```

**2. Install with all development dependencies:**

```bash
uv sync --frozen
```

**3. Activate virtual environment:**

```bash
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows
```

### Development Dependency Groups

The project uses uv dependency groups for organized development:

```bash
uv sync --group test        # Testing dependencies only
uv sync --group lint        # Code quality tools
uv sync --group build       # Build tools
uv sync --group security    # Security scanning tools
uv sync --group performance # Performance benchmarking
uv sync --group quality     # Code complexity analysis
```

### Alternative Development Setup (pip)

```bash
git clone https://github.com/bmoscon/cryptofeed.git
cd cryptofeed
pip install -e .  # Editable installation
```

If you have a problem with the installation/hacking of Cryptofeed, you are welcome to:

- open a new issue: https://github.com/bmoscon/cryptofeed/issues/
- join us on Slack: [cryptofeed-dev.slack.com](https://join.slack.com/t/cryptofeed-dev/shared_invite/enQtNjY4ODIwODA1MzQ3LTIzMzY3Y2YxMGVhNmQ4YzFhYTc3ODU1MjQ5MDdmY2QyZjdhMGU5ZDFhZDlmMmYzOTUzOTdkYTZiOGUwNGIzYTk)
- or on GitHub Discussion: https://github.com/bmoscon/cryptofeed/discussions

Your Pull Requests are also welcome, even for minor changes.
