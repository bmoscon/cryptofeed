# Python Toolchain Modernization Guide

This document guides you through the cryptofeed project's migration to modern Python tooling with **uv** and **ruff**.

## 🎯 What Changed

### **Package Management: pip → uv**

- **8-20x faster** package installation and resolution
- **Universal lockfile** for reproducible builds
- **Unified interface** replacing pip, pip-tools, virtualenv, and more

### **Code Quality: Multiple Tools → ruff**

- **Single tool** replaces Black, isort, flake8, and many plugins
- **10-100x faster** linting and formatting
- **Same code style** with better performance and error messages

### **Tools Still Used**

- **mypy**: Type checking (v1.16.1, managed by Trunk)
- **bandit**: Security scanning (v1.8.5, managed by Trunk)
- **pytest**: Testing framework (managed by uv)

## 🚀 Getting Started

### 1. Install uv

#### Option A: Standalone Installer (Recommended)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### Option B: Alternative Methods

```bash
# Homebrew (macOS)
brew install uv

# pip (if you have Python already)
pip install uv
```

### 2. Setup Development Environment

```bash
# Clone repository
git clone <repository-url>
cd cryptofeed

# Create virtual environment and install dependencies
uv sync --dev

# Install package in development mode
uv pip install -e .
```

### 3. Verify Installation

```bash
# Check uv version
uv --version

# Check ruff is working
uv run ruff check --version
uv run ruff format --version

# Run a quick test
uv run ruff check cryptofeed/ --select F401  # Check for unused imports
```

## 💻 New Development Workflow

### Daily Commands

```bash
# Install new dependency
uv add requests>=2.28.0

# Install development dependency
uv add --dev pytest-mock

# Update dependencies
uv sync

# Run tests
uv run pytest

# Format code
uv run ruff format .

# Check code quality
uv run ruff check .

# Fix auto-fixable issues
uv run ruff check --fix .

# Type checking
uv run mypy cryptofeed/

# Security scanning
uv run bandit -r cryptofeed/
```

### Git Workflow

```bash
# Before committing (simplified with Trunk)
./scripts/check.sh        # Unified code quality checks
uv run pytest tests/     # Run tests

# Alternative: individual commands (with updated tool versions)
trunk check --filter=ruff,mypy,bandit  # ruff@0.11.13, mypy@1.16.1, bandit@1.8.5
trunk fmt
uv run pytest tests/

# Commit and push
git add .
git commit -m "feat: your feature description"
git push
```

## 🔧 IDE Integration

### VS Code

Update `.vscode/settings.json`:

```json
{
  "python.defaultInterpreter": "./.venv/bin/python",
  "python.formatting.provider": "none",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.codeActionsOnSave": {
      "source.organizeImports": "explicit",
      "source.fixAll": "explicit"
    }
  },
  "ruff.path": ["uv", "run", "ruff"]
}
```

Install extensions:

- `charliermarsh.ruff` - Ruff linting and formatting
- `ms-python.mypy-type-checker` - Type checking

### PyCharm

1. Go to Settings → Tools → External Tools
2. Add new tool:

   - **Name**: Ruff Format
   - **Program**: `uv`
   - **Arguments**: `run ruff format $FilePath$`
   - **Working Directory**: `$ProjectFileDir$`

3. Add another tool:
   - **Name**: Ruff Check
   - **Program**: `uv`
   - **Arguments**: `run ruff check $FilePath$`
   - **Working Directory**: `$ProjectFileDir$`

## 📦 Dependency Management

### Adding Dependencies

```bash
# Production dependency
uv add aiohttp>=3.9.0

# Development dependency
uv add --dev pytest-asyncio

# Optional dependency group
uv add --optional redis redis>=4.0.0

# From Git repository
uv add git+https://github.com/user/repo.git

# From local path
uv add ./local-package
```

### Dependency Resolution

```bash
# Update all dependencies
uv sync

# Update specific dependency
uv add package@latest

# Show dependency tree
uv tree

# Export to requirements.txt (for compatibility)
uv export --format requirements-txt --output-file requirements.txt
```

### Lock File Management

```bash
# Generate lock file
uv lock

# Install from lock file
uv sync

# Update lock file
uv lock --upgrade

# Install only production dependencies
uv sync --no-dev
```

## 🧪 Testing

### Running Tests

```bash
# All tests
uv run pytest

# Specific test file
uv run pytest tests/test_example.py

# With coverage
uv run pytest --cov=cryptofeed --cov-report=html

# Parallel execution
uv run pytest -n auto

# Watch mode (install pytest-watch first: uv add --dev pytest-watch)
uv run ptw
```

### Test Configuration

Tests are configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = [
    "--strict-markers",
    "--cov=cryptofeed",
    "--cov-report=term-missing",
]
markers = [
    "slow: marks tests as slow",
    "integration: marks tests as integration tests",
    "network: marks tests that require network access",
]
```

## 🎨 Code Quality

### Ruff Configuration

All configuration is in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 120
target-version = "py39"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "D", "UP", "B", ...]
ignore = ["D100", "D101", ...]  # Allow missing docstrings

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### Available Commands

```bash
# Check all files
uv run ruff check .

# Check specific files
uv run ruff check cryptofeed/exchanges/

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run ruff format .

# Check formatting without changing
uv run ruff format --check .

# Show rule documentation
uv run ruff rule F401
```

### Rule Categories

Ruff includes rules from many tools:

- **E, W**: pycodestyle (PEP 8)
- **F**: Pyflakes (unused imports, variables)
- **I**: isort (import sorting)
- **N**: pep8-naming (naming conventions)
- **D**: pydocstyle (docstring conventions)
- **UP**: pyupgrade (syntax modernization)
- **B**: flake8-bugbear (likely bugs)
- **C4**: flake8-comprehensions (better comprehensions)
- **SIM**: flake8-simplify (code simplification)
- **PLR**: Pylint refactor (complexity checks)

## 🔍 Migration from Old Tools

### Command Mapping

| Old Command                       | New Command                            | Notes                      |
| --------------------------------- | -------------------------------------- | -------------------------- |
| `black .`                         | `uv run ruff format .`                 | Same output, faster        |
| `isort .`                         | `uv run ruff check --select I --fix .` | Or use `ruff format`       |
| `flake8 .`                        | `uv run ruff check .`                  | More comprehensive         |
| `pip install -r requirements.txt` | `uv sync`                              | Uses pyproject.toml        |
| `pip install package`             | `uv add package`                       | Automatic lock file update |
| `python -m venv venv`             | `uv venv`                              | Faster, automatic          |

### Configuration Migration

Old separate config files → `pyproject.toml`:

```toml
# Replaces setup.cfg [tool:pytest]
[tool.pytest.ini_options]

# Replaces .flake8 or setup.cfg [flake8]
[tool.ruff.lint]

# Replaces pyproject.toml [tool.black]
[tool.ruff.format]

# Replaces .isort.cfg or pyproject.toml [tool.isort]
[tool.ruff.lint.isort]
```

## 🚀 Performance Improvements

### Before vs After

| Operation            | Old Tools  | New Tools   | Improvement    |
| -------------------- | ---------- | ----------- | -------------- |
| Package install      | pip        | uv          | 8-20x faster   |
| Code formatting      | Black      | ruff format | 30x faster     |
| Import sorting       | isort      | ruff        | 10-100x faster |
| Linting              | flake8     | ruff check  | 10-100x faster |
| Environment creation | venv + pip | uv venv     | 5-10x faster   |

### Benchmarks (on typical project)

```bash
# Old workflow timing
time (black . && isort . && flake8 .)
# ~5-15 seconds

# New workflow timing (with Trunk)
time (trunk check --filter=ruff,mypy,bandit && trunk fmt)
# ~0.1-0.5 seconds

# Alternative with uv (fallback)
time (uv run ruff format . && uv run ruff check .)
# ~0.1-0.5 seconds
```

## 🔧 Trunk Configuration

### Updated Runtime Versions

The project uses stable, tested runtime versions:

```yaml
# .trunk/trunk.yaml
runtimes:
  enabled:
    - go@1.21.0 # Stable Go version
    - node@22.16.0 # Latest Node LTS
    - python@3.10.8 # Stable Python (resolves download issues)

lint:
  enabled:
    - ruff@0.11.13 # Latest available ruff
    - mypy@1.16.1 # Latest available mypy
    - bandit@1.8.5 # Stable bandit
```

### Tool Management Strategy

- **Trunk manages**: ruff, mypy, bandit (with hermetic installs)
- **uv manages**: pytest, project dependencies
- **Result**: Clean separation, no version conflicts

## 🔧 Troubleshooting

### Common Issues

**Q: uv command not found**

```bash
# Add to PATH or restart terminal
export PATH="$HOME/.cargo/bin:$PATH"
# Or reinstall: curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Q: Dependencies not resolving**

```bash
# Clear cache and retry
uv cache clean
uv sync --refresh
```

**Q: Trunk Python download issues**

```bash
# If you see Python download errors, use fallback script
./tools/check-fallback.sh

# Or check Trunk runtime configuration
trunk --version  # Should be 1.24.0+
```

**Q: Ruff errors after migration**

```bash
# Via Trunk (preferred)
trunk check --filter=ruff --show-source

# Via fallback
uv run ruff check --show-source

# Auto-fix with Trunk
trunk fmt
trunk check --filter=ruff --fix

# Auto-fix with uv fallback
uv run ruff check --fix
```

**Q: mypy errors**

```bash
# Install type stubs
uv add --dev types-requests types-PyYAML

# Check mypy configuration in pyproject.toml
uv run mypy --show-config
```

**Q: Tests failing**

```bash
# Install test dependencies
uv sync --dev

# Check pytest configuration
uv run pytest --collect-only

# Run with verbose output
uv run pytest -v
```

### Performance Issues

**Slow uv operations:**

```bash
# Use faster resolver
uv add package --resolution=lowest-direct

# Skip unnecessary operations
uv sync --no-sources
```

**Large dependency trees:**

```bash
# Use dependency groups
uv add --group dev pytest
uv sync --group main  # Only main dependencies
```

## 🔄 CI/CD Integration

### GitHub Actions

The project's CI automatically uses uv:

```yaml
- name: Install uv
  uses: astral-sh/setup-uv@v4

- name: Install dependencies
  run: uv sync --dev

- name: Run tests
  run: uv run pytest
```

### Pre-commit Hooks

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.13 # Match Trunk version
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  # Alternative: Use Trunk for pre-commit
  - repo: https://github.com/trunk-io/pre-commit
    rev: v1.24.0
    hooks:
      - id: trunk
        args: [check, --filter=ruff, mypy, bandit]
```

## 📚 Additional Resources

### Documentation

- [uv Documentation](https://docs.astral.sh/uv/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Trunk Documentation](https://docs.trunk.io/)
- [pyproject.toml Guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)

### Migration Guides

- [Migrating from pip-tools to uv](https://docs.astral.sh/uv/guides/pip-tools/)
- [Ruff vs Black, isort, flake8](https://docs.astral.sh/ruff/faq/#how-does-ruff-compare-to-flake8-black-and-isort)

### Community

- [uv GitHub](https://github.com/astral-sh/uv)
- [Ruff GitHub](https://github.com/astral-sh/ruff)
- [Trunk GitHub](https://github.com/trunk-io/trunk)
- [Python Packaging Discord](https://discord.gg/packaging)
- [Trunk Community Slack](https://slack.trunk.io)

---

## 🎉 Next Steps

1. **Install uv**: Follow the installation guide above
2. **Install Trunk**: `curl -fsSL https://get.trunk.io | bash` (if not already installed)
3. **Setup environment**: Run `uv sync --dev`
4. **Verify Trunk**: Run `trunk check --sample=1` to test configuration
5. **Update IDE**: Configure ruff and Trunk extensions
6. **Try new workflow**: Use `trunk check` and `trunk fmt` for daily development
7. **Fallback ready**: Use `./tools/check-fallback.sh` if Trunk has issues
8. **Team coordination**: Share this guide with team members

The modernized toolchain with Trunk provides significant performance improvements while maintaining the same code quality standards. Happy coding! 🚀
