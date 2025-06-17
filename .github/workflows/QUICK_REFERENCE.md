# GitHub Workflows Quick Reference

## 🚀 One-Minute Overview

| Workflow         | When it Runs    | What it Does             | Time    |
| ---------------- | --------------- | ------------------------ | ------- |
| **CI/CD**        | Every push/PR   | Quality + Tests + Build  | ~8 min  |
| **Code Quality** | Push/PR/Weekly  | Deep analysis + Reports  | ~12 min |
| **Performance**  | Push to main/PR | Benchmarks + Profiling   | ~15 min |
| **Security**     | Push/PR/Weekly  | Multi-tool security scan | ~10 min |
| **Release**      | Git tags        | Build + Publish to PyPI  | ~20 min |
| **CodeQL**       | Weekly          | GitHub security analysis | ~25 min |

## ⚡ Quick Commands

### Local Development

```bash
# Run what CI runs
trunk check --all                    # Quality checks
uv run pytest tests/                 # Run tests
uv run python -m build               # Build package

# Performance testing
python benchmark_cryptofeed.py       # Local benchmarks

# Security scanning
bandit -r cryptofeed/                # Security scan
safety check                        # Vulnerability check
```

### Manual Workflow Triggers

```bash
# Via GitHub CLI
gh workflow run ci.yml
gh workflow run code-quality.yml --field full_analysis=true
gh workflow run performance.yml --field benchmark_type=comprehensive

# Via GitHub Web UI
# → Actions tab → Select workflow → Run workflow button
```

### Status Checking

```bash
# Check workflow status
gh run list --workflow=ci.yml --limit=5

# View specific run
gh run view <run-id>

# Download artifacts
gh run download <run-id>
```

## 🎯 Common Scenarios

### Before Submitting PR

```bash
# 1. Run local checks (same as CI)
trunk check --all
uv run pytest tests/

# 2. Check for secrets
git log --oneline -10 | xargs -I {} git show {} | grep -i "api\|key\|secret\|token" || echo "✅ No secrets found"

# 3. Performance check (optional)
python benchmark_cryptofeed.py
```

### PR Failed - What to Check

```bash
# 1. Check workflow logs
gh run view --log

# 2. Common fixes
trunk format                        # Fix formatting
trunk check --fix --all            # Auto-fix issues
uv sync --dev                      # Update dependencies

# 3. Re-run failed checks locally
trunk check --filter=ruff
trunk check --filter=mypy
```

### Release Process

```bash
# 1. Update version in pyproject.toml
# 2. Create and push tag
git tag v1.2.3
git push origin v1.2.3

# 3. Monitor release workflow
gh run list --workflow=release.yml --limit=1
```

## 🔧 Configuration Cheat Sheet

### Quality Gate Thresholds

```yaml
MAX_CRITICAL: 0 # Zero tolerance
MAX_HIGH: 10 # Warning threshold
```

### Python Versions Tested

```yaml
matrix:
  python-version: ["3.9", "3.10", "3.11", "3.12"]
```

### Tool Versions (Trunk Managed)

```yaml
- ruff@0.11.13 # Linting + Formatting
- mypy@1.16.1 # Type checking
- bandit@1.8.5 # Security scanning
```

### Workflow Schedules

```yaml
Code Quality: Weekly Monday 2 AM UTC
Performance: Weekly Monday 4 AM UTC
Security: Weekly Monday 6 AM UTC
CodeQL: Weekly Tuesday 10 AM UTC
```

## 📊 Monitoring Quick Links

### GitHub UI Links

- **Actions Dashboard**: `/actions`
- **Security Tab**: `/security`
- **Code Scanning**: `/security/code-scanning`
- **Dependabot**: `/security/dependabot`

### Key Metrics to Watch

- **CI Success Rate**: Target > 95%
- **Average Build Time**: Target < 10 min
- **Quality Gate Pass Rate**: Target > 90%
- **Security Issues**: Target = 0 critical

## 🚨 Emergency Procedures

### Workflow is Broken

```bash
# 1. Check recent changes
git log --oneline -5 .github/workflows/

# 2. Revert if needed
git revert <commit-hash>

# 3. Test workflow changes locally
act -j test  # Requires act CLI
```

### Performance Regression Detected

```bash
# 1. Check performance comparison in PR
# 2. Identify problematic changes
# 3. Profile specific functions
python -m cProfile -s cumtime your_script.py
```

### Security Alert

```bash
# 1. View alerts
gh api /repos/:owner/:repo/code-scanning/alerts

# 2. Check severity and fix
# 3. Verify fix with local scan
bandit -r cryptofeed/
```

## 📋 Artifact Locations

### CI/CD Artifacts

- **Test Results**: `pytest-results.xml`
- **Coverage Report**: `coverage.xml`
- **Build Packages**: `dist/`

### Code Quality Artifacts

- **Quality Reports**: `trunk-report.json`, `trunk-report.sarif`
- **Complexity Analysis**: `complexity-report.txt`
- **Documentation**: `doc-coverage.txt`

### Performance Artifacts

- **Benchmark Results**: `benchmark-results.json`
- **Memory Profiles**: `memory-profile.txt`
- **Performance Reports**: `performance-report.md`

### Security Artifacts

- **Security Scans**: `bandit-report.json`, `safety-report.json`
- **SARIF Reports**: `*.sarif` (auto-uploaded to Security tab)

## 🔗 Essential URLs

### Documentation

- **Main README**: `.github/workflows/README.md`
- **Practical Guide**: `.github/workflows/WORKFLOW_GUIDE.md`
- **This Reference**: `.github/workflows/QUICK_REFERENCE.md`

### External Resources

- [uv Documentation](https://docs.astral.sh/uv/)
- [Trunk Documentation](https://docs.trunk.io/)
- [GitHub Actions](https://docs.github.com/en/actions)

## 🎨 Status Badge HTML

```html
<!-- For README.md -->
<img src="https://github.com/bmoscon/cryptofeed/actions/workflows/ci.yml/badge.svg" alt="CI/CD" />
<img src="https://github.com/bmoscon/cryptofeed/actions/workflows/code-quality.yml/badge.svg" alt="Code Quality" />
<img src="https://github.com/bmoscon/cryptofeed/actions/workflows/security.yml/badge.svg" alt="Security" />
```

## ⚙️ Environment Variables

### Common Settings

```bash
PYTHON_VERSION=3.11              # Default Python version
ACTIONS_STEP_DEBUG=true          # Enable step debugging
ACTIONS_RUNNER_DEBUG=true        # Enable runner debugging
```

### Tool-Specific

```bash
RUFF_CONFIG=pyproject.toml       # Ruff configuration
MYPY_CONFIG_FILE=pyproject.toml  # MyPy configuration
PYTEST_ARGS=--verbose            # Pytest arguments
```

---

> 📖 **Need more details?** Check the [comprehensive README](./README.md) or [practical guide](./WORKFLOW_GUIDE.md)
> 🐛 **Found an issue?** Open a GitHub issue or submit a PR
> 💡 **Have suggestions?** We welcome workflow improvements!
