# Trunk Setup and Integration Guide

This document provides comprehensive setup instructions for integrating Trunk with the cryptofeed project, along with the GitHub Actions workflows and branch protection rulesets.

## Overview

This setup combines:

- **Trunk**: Code quality and formatting tool
- **GitHub Actions**: Comprehensive CI/CD pipeline
- **Branch Rulesets**: Repository protection and quality gates

## 🌲 Trunk Integration

### What is Trunk?

Trunk is a universal code quality tool that:

- **Unifies linting and formatting** across multiple languages
- **Provides instant feedback** with super-fast performance
- **Integrates seamlessly** with existing workflows
- **Scales to large codebases** with intelligent caching

### Trunk Configuration

The repository includes pre-configured Trunk setup in `.trunk/`:

```
.trunk/
├── .gitignore              # Trunk cache exclusions
├── trunk.yaml              # Main configuration file
└── configs/
    ├── .markdownlint.yaml  # Markdown linting rules
    ├── .shellcheckrc       # Shell script linting
    ├── .yamllint.yaml      # YAML file linting
    └── ruff.toml           # Python linting configuration
```

### Trunk Tools Enabled

The configuration enables these quality tools:

**Python Tools:**

- **ruff**: Fast Python linter and formatter
- **black**: Code formatting
- **isort**: Import sorting
- **mypy**: Static type checking

**Other Tools:**

- **markdownlint**: Markdown formatting and style
- **shellcheck**: Shell script analysis
- **yamllint**: YAML file validation
- **prettier**: JavaScript/JSON/CSS formatting

## 🚀 Installation and Setup

### 1. Install Trunk

#### Option A: Automatic Installation (Recommended)

You can install Trunk automatically in one of two ways:

Option 1: Direct installation via curl:

```bash
# Install Trunk CLI
curl https://get.trunk.io -fsSL | bash

# Optional: Initialize in repository (if not already done)
# trunk init
```

Option 2: Use our provided bootstrap script to automatically install Trunk if not already installed:

```bash
./scripts/bootstrap_trunk.sh
```

#### Option B: Manual Installation

```bash
# macOS (Homebrew)
brew install trunk-io

# Linux/WSL (direct download)
curl -fsSL https://trunk.io/releases/trunk -o trunk
chmod +x trunk
sudo mv trunk /usr/local/bin/
```

### 2. Verify Installation

```bash
# Check Trunk version
trunk --version

# Verify configuration
trunk check --ci
```

### 3. VS Code Integration (Optional)

Install the Trunk VS Code extension for real-time feedback:

1. Open VS Code
2. Go to Extensions (Ctrl+Shift+X)
3. Search for "Trunk"
4. Install the official Trunk extension

## 🔧 Usage

### Basic Commands

```bash
# Check all files for issues
trunk check

# Format all files
trunk fmt

# Check specific files
trunk check src/file.py

# Format specific files
trunk fmt src/file.py

# Check and auto-fix issues
trunk check --fix

# Run in CI mode (strict)
trunk check --ci
```

### Git Hooks Integration

#### Pre-commit Hook

```bash
# Install pre-commit hook
trunk install-hooks

# This adds Trunk checks before each commit
```

#### Manual Pre-commit Setup

```bash
# Add to .git/hooks/pre-commit
#!/bin/bash
trunk check --ci --filter=diff-upstream
```

### Developer Workflow

```bash
# Before committing
trunk fmt              # Format all changed files
trunk check --fix      # Check and auto-fix issues

# Quick check of changed files only
trunk check --filter=diff-upstream

# Format only Python files
trunk fmt --filter=python
```

## 🏗️ GitHub Actions Integration

### Workflow Integration

The CI pipeline includes Trunk in the **Code Quality Checks** job:

```yaml
# In .github/workflows/ci.yml
- name: Run Trunk linting
  run: trunk check --ci --filter=diff-upstream
```

### Quality Gates

Trunk is integrated into branch protection as a required status check:

- **Feature branches**: Basic Trunk validation
- **Main/Release branches**: Full Trunk CI validation
- **Required for merge**: All Trunk checks must pass

### Caching Strategy

The workflows include intelligent caching:

```yaml
- name: Cache Trunk
  uses: actions/cache@v4
  with:
    path: ~/.trunk
    key: trunk-${{ runner.os }}-${{ hashFiles('.trunk/trunk.yaml') }}
```

## 📋 Configuration Customization

### Adding New Tools

Edit `.trunk/trunk.yaml` to add tools:

```yaml
lint:
  enabled:
    - ruff@0.1.6
    - black@23.11.0
    - mypy@1.7.1
    - your-new-tool@version
```

### Python-Specific Configuration

Ruff configuration in `.trunk/configs/ruff.toml`:

```toml
[tool.ruff]
line-length = 120
target-version = "py39"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]
ignore = ["E501"]  # Line too long
```

### Markdown Configuration

Customize `.trunk/configs/.markdownlint.yaml`:

```yaml
# Markdown linting rules
MD013: false # Line length
MD033: false # HTML elements
```

### Excluding Files

Add patterns to `.trunk/.gitignore`:

```
# Generated files
*.pb.go
node_modules/
.venv/

# Large data files
*.csv
*.json
```

## 🔄 Integration with Existing Tools

### Compatibility with Current Setup

Trunk works alongside existing tools:

**Replaces**:

- Multiple separate linter configurations
- Manual formatting steps
- Inconsistent code quality checks

**Enhances**:

- pytest (testing remains unchanged)
- GitHub Actions (adds quality layer)
- Development workflow (faster feedback)

### Migration Strategy

1. **Phase 1**: Run Trunk alongside existing tools
2. **Phase 2**: Gradually adopt Trunk formatting
3. **Phase 3**: Replace individual tool configurations
4. **Phase 4**: Full Trunk adoption with team training

## 🏭 Enterprise Features

### Team Collaboration

**Shared Configuration**:

- Consistent formatting across all developers
- Unified linting rules in version control
- Automatic tool version management

**Conflict Prevention**:

- Pre-commit hooks prevent bad commits
- CI validation blocks problematic merges
- Automatic formatting reduces style debates

### Performance Benefits

**Fast Execution**:

- Intelligent caching for large repositories
- Parallel execution of multiple tools
- Incremental checking of changed files only

**Developer Experience**:

- Single command for all quality checks
- IDE integration for real-time feedback
- Minimal configuration overhead

## 🛠️ Troubleshooting

### Common Issues

**❌ Trunk not found**

```bash
# Ensure Trunk is in PATH
which trunk
# If not found, reinstall or add to PATH
export PATH="$HOME/.trunk/bin:$PATH"
```

**❌ Configuration conflicts**

```bash
# Reset configuration
trunk init --force
# Restore custom configs from backup
```

**❌ Performance issues**

```bash
# Clear cache
trunk clean
# Run with verbose output
trunk check --verbose
```

**❌ CI failures**

```bash
# Check differences from main
trunk check --ci --filter=diff-upstream

# Show all issues
trunk check --all
```

### Debug Commands

```bash
# Show detailed tool information
trunk status

# List all available tools
trunk catalog

# Show configuration
trunk config

# Verbose execution
trunk check --verbose
```

## 📊 Monitoring and Metrics

### Quality Metrics

Track code quality improvements:

**Before Trunk**:

- Inconsistent formatting
- Manual linting processes
- Style-related PR discussions

**After Trunk**:

- Automated quality enforcement
- Consistent codebase formatting
- Focus on logic in code reviews

### CI/CD Metrics

Monitor workflow efficiency:

- **Build time reduction** through caching
- **Error detection speed** with pre-commit hooks
- **Developer productivity** with instant feedback

## 🔗 Integration Examples

### Local Development Workflow

```bash
# Start development
git checkout -b feature/new-functionality

# Make changes
# ... edit files ...

# Format and check before commit
trunk fmt
trunk check --fix

# Commit with confidence
git add .
git commit -m "feat: add new functionality"

# Push with pre-commit validation
git push -u origin feature/new-functionality
```

### CI/CD Workflow

```bash
# Triggered automatically on push/PR
# GitHub Actions runs:
1. Code quality checks (including Trunk)
2. Multi-Python testing
3. Security scanning
4. Build verification

# Branch protection ensures:
- All quality checks pass
- Required reviews obtained
- Conventional commit format followed
```

### Release Workflow

```bash
# Pre-release quality validation
trunk check --all --ci

# If issues found, fix automatically
trunk fmt
trunk check --fix

# Commit fixes
git commit -m "style: apply trunk formatting"

# Continue with release process
git tag v1.2.0
git push origin v1.2.0
```

## 📚 Best Practices

### Development Guidelines

1. **Run Trunk before commits**: Always format and check before committing
2. **Use pre-commit hooks**: Prevent issues from entering the repository
3. **Address issues promptly**: Don't accumulate technical debt
4. **Leverage IDE integration**: Get real-time feedback while coding
5. **Customize judiciously**: Start with defaults, customize as needed

### Team Adoption

1. **Training**: Ensure all developers understand Trunk commands
2. **Documentation**: Maintain team-specific guidelines
3. **Gradual rollout**: Introduce features incrementally
4. **Feedback loop**: Regularly review and adjust configuration
5. **Automation**: Maximize automated checks, minimize manual steps

### Performance Optimization

1. **Use filters**: Check only relevant files when possible
2. **Enable caching**: Leverage Trunk's caching for faster runs
3. **Parallel execution**: Let Trunk run tools in parallel
4. **Incremental checks**: Focus on changed files in CI
5. **Tool selection**: Enable only necessary tools for your codebase

## 🎯 Next Steps

### Immediate Actions

1. **Install Trunk CLI** on all development machines
2. **Set up IDE integration** for real-time feedback
3. **Configure pre-commit hooks** for quality gates
4. **Test workflow** with sample commits
5. **Train team members** on new commands

### Advanced Setup

1. **Custom tool configuration** for project-specific needs
2. **Additional language support** if needed
3. **Performance monitoring** and optimization
4. **Integration with deployment pipelines**
5. **Quality metrics collection** and reporting

---

**Related Documentation:**

- [Trunk Official Documentation](https://docs.trunk.io/)
- [GitHub Actions Workflows](WORKFLOW_SETUP.md)
- [Branch Rulesets Setup](SETUP_RULESETS.md)
- [Conventional Commits](https://www.conventionalcommits.org/)

This comprehensive setup provides enterprise-grade code quality and CI/CD infrastructure for the cryptofeed project, combining the power of Trunk with GitHub's native features for a seamless development experience.
