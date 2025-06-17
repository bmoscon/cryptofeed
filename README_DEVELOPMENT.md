# Development Setup Guide

This guide provides comprehensive setup instructions for developers working on the cryptofeed project.

## 🚀 Quick Start

### Prerequisites

- **Python 3.9+** (recommended: Python 3.11)
- **Git** with SSH or HTTPS access
- **Code editor** (VS Code recommended)

### 1. Clone and Setup

```bash
# Clone repository
git clone https://github.com/tommy-ca/cryptofeed.git
cd cryptofeed

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install development dependencies
pip install -e ".[all]"
pip install pytest ruff black isort mypy
```

### 2. Install Development Tools

#### Trunk (Code Quality - Recommended)
```bash
# Install Trunk CLI
curl https://get.trunk.io -fsSL | bash

# Verify installation
trunk --version

# Install pre-commit hooks
trunk install-hooks
```

#### Alternative: Manual Tool Setup
```bash
# If not using Trunk, install tools individually
pip install ruff black isort mypy pytest bandit safety
```

### 3. Verify Setup

```bash
# Run tests
pytest tests/

# Check code quality
trunk check
# or manually:
ruff check .
black --check .
isort --check .
```

## 🛠️ Development Workflow

### 1. Feature Development

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes
# ... edit files ...

# Format and check code
trunk fmt              # Format all files
trunk check --fix      # Fix issues automatically

# Run tests
pytest tests/

# Commit changes
git add .
git commit -m "feat: add your feature description"

# Push and create PR
git push -u origin feature/your-feature-name
```

### 2. Code Quality Standards

**Before every commit:**

```bash
# Format code
trunk fmt
# or manually:
black .
isort .

# Check for issues
trunk check
# or manually:
ruff check .
mypy cryptofeed/
```

**Required standards:**
- ✅ All tests pass
- ✅ Code follows Black formatting
- ✅ Imports sorted with isort
- ✅ No Ruff linting errors
- ✅ Type hints validated with mypy
- ✅ Security scan passes (Bandit)

### 3. Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_specific.py

# Run with coverage
pytest --cov=cryptofeed --cov-report=html

# Performance testing
pytest tests/performance/ -v
```

## 🏗️ Project Structure

```
cryptofeed/
├── .github/                 # GitHub workflows and rulesets
│   ├── workflows/          # CI/CD pipelines
│   │   ├── ci.yml         # Main CI pipeline
│   │   ├── release.yml    # Release automation
│   │   └── security.yml   # Security scanning
│   ├── ruleset-*.json     # Branch protection configs
│   └── *.md               # Setup documentation
├── .trunk/                 # Trunk configuration
│   ├── trunk.yaml         # Main Trunk config
│   └── configs/           # Tool-specific configs
├── cryptofeed/            # Main package
│   ├── backends/          # Data storage backends
│   ├── exchanges/         # Exchange implementations
│   ├── defines.py         # Constants and definitions
│   └── ...
├── examples/              # Usage examples
├── tests/                 # Test suite
├── setup.py              # Package configuration
└── requirements.txt      # Dependencies
```

## 🔧 IDE Setup

### VS Code (Recommended)

#### Extensions
Install these VS Code extensions:
```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.black-formatter",
    "ms-python.isort",
    "charliermarsh.ruff",
    "trunk.io",
    "ms-python.mypy-type-checker"
  ]
}
```

#### Settings
Add to `.vscode/settings.json`:
```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  }
}
```

### PyCharm

1. Configure interpreter: File → Settings → Project → Python Interpreter
2. Enable code inspections: File → Settings → Editor → Inspections
3. Configure external tools for Ruff, Black, etc.

## 🧪 Testing Guidelines

### Test Structure

```python
# tests/test_example.py
import pytest
import asyncio
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Binance


class TestExample:
    def test_sync_function(self):
        # Synchronous test
        result = some_function()
        assert result == expected_value
    
    @pytest.mark.asyncio
    async def test_async_function(self):
        # Asynchronous test
        result = await some_async_function()
        assert result == expected_value
    
    def test_exception_handling(self):
        # Test error conditions
        with pytest.raises(ValueError):
            function_that_should_raise()
```

### Test Categories

**Unit Tests** (`tests/unit/`):
- Test individual functions and classes
- Mock external dependencies
- Fast execution

**Integration Tests** (`tests/integration/`):
- Test component interactions
- Use real network connections (limited)
- Slower execution

**Performance Tests** (`tests/performance/`):
- Benchmark critical functions
- Memory usage validation
- Throughput testing

### Running Tests

```bash
# All tests
pytest

# Specific category
pytest tests/unit/
pytest tests/integration/
pytest tests/performance/

# With coverage
pytest --cov=cryptofeed --cov-report=html

# Parallel execution
pytest -n auto

# Verbose output
pytest -v
```

## 🔒 Security Guidelines

### Security Checks

```bash
# Security linting
bandit -r cryptofeed/

# Dependency vulnerability scan
safety check

# Full security scan (if using Trunk)
trunk check --filter=security
```

### Best Practices

1. **Never commit secrets**: Use environment variables
2. **Validate inputs**: Sanitize all external data
3. **Use type hints**: Enable static analysis
4. **Secure dependencies**: Regularly update packages
5. **Follow OWASP guidelines**: For web-related code

### Handling Secrets

```python
# Good: Use environment variables
import os
api_key = os.getenv('API_KEY')

# Bad: Hardcoded secrets
api_key = "sk-1234567890abcdef"  # DON'T DO THIS
```

## 📝 Commit Guidelines

### Conventional Commits

Use the [Conventional Commits](https://www.conventionalcommits.org/) format:

```bash
# Format: type(scope): description
feat(backends): add Delta Lake support
fix(binance): resolve websocket connection issue
docs(readme): update installation instructions
test(unit): add tests for order book functionality
refactor(exchanges): optimize connection handling
chore(deps): update dependencies
```

### Commit Types

- **feat**: New features
- **fix**: Bug fixes
- **docs**: Documentation changes
- **test**: Test additions/modifications
- **refactor**: Code refactoring
- **style**: Formatting changes
- **chore**: Maintenance tasks
- **perf**: Performance improvements

### Example Good Commits

```bash
git commit -m "feat(backends): add Redis clustering support"
git commit -m "fix(kraken): handle rate limiting properly"
git commit -m "docs(api): add Delta Lake configuration examples"
git commit -m "test(integration): add Coinbase Pro websocket tests"
```

## 🚀 Release Process

### Version Management

The project uses [Semantic Versioning](https://semver.org/):
- **Major** (X.0.0): Breaking changes
- **Minor** (0.X.0): New features (backward compatible)
- **Patch** (0.0.X): Bug fixes

### Release Workflow

```bash
# 1. Create release branch
git checkout -b release/v2.5.0

# 2. Update version in setup.py
# Edit setup.py: version="2.5.0"

# 3. Update CHANGES.md
# Document new features and fixes

# 4. Create PR for review
gh pr create --title "Release v2.5.0" --base main

# 5. After merge, create tag
git tag -s v2.5.0 -m "Release v2.5.0"
git push origin v2.5.0

# 6. GitHub Actions automatically:
#    - Creates GitHub release
#    - Publishes to PyPI
#    - Builds Docker images
```

## 🐛 Debugging

### Common Issues

**Import Errors**:
```bash
# Ensure package is installed in development mode
pip install -e .
```

**Test Failures**:
```bash
# Run specific failing test with verbose output
pytest tests/test_failing.py -v -s

# Debug with pdb
pytest --pdb tests/test_failing.py
```

**Network Issues**:
```bash
# Test with increased timeout
pytest --timeout=60 tests/integration/

# Skip network tests
pytest -m "not network"
```

### Debug Tools

```python
# Built-in debugger
import pdb; pdb.set_trace()

# Rich debugging (install: pip install rich)
from rich import print
print(data, style="bold red")

# Logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📊 Performance

### Profiling

```bash
# Profile with cProfile
python -m cProfile -o profile.stats your_script.py

# Analyze profile
python -c "import pstats; pstats.Stats('profile.stats').sort_stats('cumulative').print_stats()"

# Memory profiling (install: pip install memory-profiler)
python -m memory_profiler your_script.py
```

### Optimization Guidelines

1. **Use async/await**: For I/O operations
2. **Minimize dependencies**: Keep imports lightweight
3. **Cache expensive operations**: Use functools.lru_cache
4. **Profile before optimizing**: Measure actual bottlenecks
5. **Batch operations**: Reduce API calls

## 🤝 Contributing

### Pull Request Process

1. **Fork repository** and create feature branch
2. **Make changes** following code quality standards
3. **Add tests** for new functionality
4. **Update documentation** as needed
5. **Submit PR** with clear description
6. **Address review feedback** promptly
7. **Ensure CI passes** before merge

### Review Guidelines

**For Authors**:
- Provide clear PR description
- Include test cases
- Document breaking changes
- Keep PRs focused and small

**For Reviewers**:
- Check code quality and style
- Verify test coverage
- Validate security implications
- Suggest improvements constructively

## 📚 Resources

### Documentation
- [Project README](README.md)
- [API Documentation](docs/)
- [GitHub Workflows](/.github/WORKFLOW_SETUP.md)
- [Trunk Setup](/.github/TRUNK_SETUP.md)

### External Resources
- [Python asyncio](https://docs.python.org/3/library/asyncio.html)
- [pytest Documentation](https://docs.pytest.org/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)

### Community
- [GitHub Issues](https://github.com/tommy-ca/cryptofeed/issues)
- [GitHub Discussions](https://github.com/tommy-ca/cryptofeed/discussions)

---

**Need Help?** 
- Check the [troubleshooting guide](/.github/WORKFLOW_SETUP.md#troubleshooting)
- Search [existing issues](https://github.com/tommy-ca/cryptofeed/issues)
- Create a [new issue](https://github.com/tommy-ca/cryptofeed/issues/new)