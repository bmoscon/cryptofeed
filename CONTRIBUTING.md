## Contributing Guidelines

PRs, bug reports, feature requests, documentation, and other enhancements and improvements are welcomed. Please have a look at this checklist before contributing

## Development Setup

For the best development experience, please follow our [Development Setup Guide](README_DEVELOPMENT.md) which covers:

### Quick Setup with uv (Recommended)

```bash
# Clone and setup
git clone https://github.com/bmoscon/cryptofeed.git
cd cryptofeed

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all development dependencies
uv sync --frozen

# Activate environment
source .venv/bin/activate  # Linux/macOS
```

### For Issues

* Is this a question? Questions are permitted, but a better way to get support for questions is to join the slack channel and ask there (Link in README), or open a thread in the repository's Discussions tab.
* Is this something that is extremely specific to your use case, or will it likely be useful and beneficial to other users of the library? 
* Do you have an idea for what you are requesting? If so, please include that! Details are helpful.
* For bug reports please include a way to reproduce the issue - issues that cannot be reproduced cannot be fixed and will be closed.
* For new exchange requests please include links to the API documentation.

### For PRs

* Has it been tested? How?
* Does the code style match the overall code style of the project?
* Please use type annotations.
* **Code Quality**: Please run our quality checks before submitting:

#### Using Trunk (Recommended)
```bash
trunk check --fix      # Fix issues automatically
trunk fmt              # Format code
```

#### Manual Quality Checks
```bash
uv run ruff check .     # Linting
uv run ruff format .    # Code formatting  
uv run mypy cryptofeed  # Type checking
uv run pytest tests/   # Run tests
```

#### Before Submitting
- [ ] Code passes all quality checks
- [ ] Tests are included and passing
- [ ] Documentation is updated if needed
- [ ] Commit messages follow conventional format (feat:, fix:, docs:, etc.)

See [README_DEVELOPMENT.md](README_DEVELOPMENT.md) for detailed development workflow and coding standards.
