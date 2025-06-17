# GitHub Workflows Practical Guide

This guide provides hands-on examples and practical instructions for working with the modernized GitHub workflows.

## 🚀 Quick Start

### Running Workflows Manually

All workflows support manual triggering via `workflow_dispatch`:

1. **Navigate to Actions tab** in GitHub repository
2. **Select workflow** from the left sidebar
3. **Click "Run workflow"** button
4. **Choose options** (if available) and click "Run workflow"

### Workflow Status Badges

Add these badges to your README.md to show workflow status:

```markdown
[![CI/CD](https://github.com/bmoscon/cryptofeed/actions/workflows/ci.yml/badge.svg)](https://github.com/bmoscon/cryptofeed/actions/workflows/ci.yml)
[![Code Quality](https://github.com/bmoscon/cryptofeed/actions/workflows/code-quality.yml/badge.svg)](https://github.com/bmoscon/cryptofeed/actions/workflows/code-quality.yml)
[![Security](https://github.com/bmoscon/cryptofeed/actions/workflows/security.yml/badge.svg)](https://github.com/bmoscon/cryptofeed/actions/workflows/security.yml)
[![Performance](https://github.com/bmoscon/cryptofeed/actions/workflows/performance.yml/badge.svg)](https://github.com/bmoscon/cryptofeed/actions/workflows/performance.yml)
```

## 📋 Workflow-Specific Guides

### CI/CD Pipeline (`ci.yml`)

#### Job Dependencies
```yaml
build-and-install:
  needs: [lint-and-format, test]  # Waits for quality and tests
integration-tests:
  needs: build-and-install        # Runs after successful build
```

#### Matrix Strategy
```yaml
strategy:
  matrix:
    python-version: ['3.9', '3.10', '3.11', '3.12']
```

#### Running Specific Jobs Locally
```bash
# Test quality checks locally
trunk check --all

# Test with specific Python version
uv sync --python 3.11
uv run pytest tests/

# Build package locally
uv run python -m build
```

### Code Quality (`code-quality.yml`)

#### Understanding Quality Gates

**Critical Issues (MAX: 0)**:
- Security vulnerabilities
- Syntax errors
- Import errors
- Breaking changes

**High Issues (MAX: 10)**:
- Code complexity warnings
- Style violations
- Type checking errors
- Documentation issues

#### Manual Quality Check
```bash
# Full quality analysis
trunk check --all --output-format=json > quality-report.json

# Specific tool analysis
trunk check --filter=ruff --all
trunk check --filter=mypy --all
trunk check --filter=bandit --all
```

#### Quality Report Interpretation
```json
{
  "issues": [
    {
      "tool": "ruff",
      "severity": "high",
      "file": "cryptofeed/exchanges/binance.py",
      "line": 42,
      "message": "Line too long (89 > 88 characters)"
    }
  ]
}
```

### Performance Benchmarks (`performance.yml`)

#### Benchmark Types

**Standard Benchmarks**:
- Core functionality timing
- Basic memory usage
- Import performance

**Comprehensive Benchmarks**:
- Full system integration
- Memory leak detection
- Concurrent operation testing

**Memory Profiling**:
- Detailed memory usage analysis
- Object lifecycle tracking
- Memory leak detection

#### Reading Performance Reports

```json
{
  "FeedHandler creation": 0.0045,
  "Exchange setup": 0.0123,
  "memory_usage_mb": 12.3
}
```

#### Performance Regression Detection
```bash
# Compare current vs baseline
python compare_benchmarks.py baseline.json current.json

# Acceptable thresholds
PERFORMANCE_REGRESSION_THRESHOLD = 1.2  # 20% slower
MEMORY_REGRESSION_THRESHOLD = 1.5       # 50% more memory
```

### Security Scanning (`security.yml`)

#### Security Tools Overview

| Tool | Purpose | Coverage |
|------|---------|----------|
| **Bandit** | Python security issues | Source code analysis |
| **Safety** | Dependency vulnerabilities | PyPI packages |
| **pip-audit** | Package vulnerabilities | Python dependencies |
| **TruffleHog** | Secrets detection | Git history |
| **CodeQL** | Semantic analysis | Deep code patterns |
| **Trivy** | Container scanning | Docker images |

#### SARIF Integration

Security findings automatically appear in:
- **GitHub Security tab** → Code scanning alerts
- **Pull Request checks** → Security findings
- **Repository insights** → Security overview

#### Manual Security Scanning
```bash
# Run all security tools
./tools/security-scan.sh

# Individual tools
bandit -r cryptofeed/ -f json
safety check --json
pip-audit --desc --format json
```

### Release Pipeline (`release.yml`)

#### Release Process Flow

1. **Tag Creation**: `git tag v1.2.3 && git push origin v1.2.3`
2. **Validation**: Quality checks and tests
3. **Building**: Create distributions
4. **TestPyPI**: Deploy and test
5. **GitHub Release**: Create release with notes
6. **PyPI**: Production deployment
7. **Docker**: Multi-platform builds

#### Release Configuration

```yaml
# Version tag format validation
^refs/tags/v[0-9]+\.[0-9]+\.[0-9]+.*$

# Prerelease detection
prerelease: ${{ contains(steps.version.outputs.version, 'rc') || 
                contains(steps.version.outputs.version, 'beta') }}
```

#### Manual Release Process
```bash
# 1. Update version in pyproject.toml
# 2. Create and push tag
git tag v1.2.3
git push origin v1.2.3

# 3. Monitor workflow at:
# https://github.com/bmoscon/cryptofeed/actions/workflows/release.yml
```

## 🔧 Customization Examples

### Adding New Quality Checks

```yaml
# In code-quality.yml
- name: Custom quality check
  run: |
    # Add your custom analysis
    python scripts/custom_analysis.py > custom-report.txt
    
- name: Upload custom reports
  uses: actions/upload-artifact@v4
  with:
    name: custom-analysis
    path: custom-report.txt
```

### Custom Performance Benchmarks

```yaml
# In performance.yml
- name: Custom benchmarks
  run: |
    cat > custom_benchmark.py << 'EOF'
    import time
    from cryptofeed import YourComponent
    
    def benchmark_your_feature():
        start = time.perf_counter()
        # Your benchmark code
        YourComponent().your_method()
        return time.perf_counter() - start
    
    result = benchmark_your_feature()
    print(f"Custom benchmark: {result:.4f}s")
    EOF
    
    python custom_benchmark.py
```

### Environment-Specific Configuration

```yaml
# Development environment
env:
  PYTHON_VERSION: '3.11'
  PYTEST_ARGS: '--verbose --tb=short'
  
# Production environment  
env:
  PYTHON_VERSION: '3.11'
  PYTEST_ARGS: '--quiet --tb=no'
```

## 🔍 Monitoring and Alerting

### Workflow Monitoring Setup

```yaml
# .github/workflows/monitor.yml
name: Workflow Health Check
on:
  schedule:
    - cron: '0 8 * * 1'  # Weekly Monday 8 AM

jobs:
  health-check:
    runs-on: ubuntu-latest
    steps:
      - name: Check workflow success rates
        uses: actions/github-script@v7
        with:
          script: |
            const { data: runs } = await github.rest.actions.listWorkflowRuns({
              owner: context.repo.owner,
              repo: context.repo.repo,
              workflow_id: 'ci.yml',
              per_page: 100
            });
            
            const successRate = runs.workflow_runs
              .filter(run => run.conclusion === 'success').length / runs.workflow_runs.length;
            
            if (successRate < 0.9) {
              core.setFailed(`CI success rate below 90%: ${successRate}`);
            }
```

### Performance Monitoring

```bash
# Track workflow execution times
gh run list --workflow=ci.yml --limit=10 --json conclusion,startedAt,updatedAt
```

### Security Alert Management

```bash
# List security alerts
gh api /repos/:owner/:repo/code-scanning/alerts

# Get specific alert details
gh api /repos/:owner/:repo/code-scanning/alerts/1
```

## 🚨 Troubleshooting Scenarios

### Scenario 1: Trunk Installation Fails

**Symptoms**: `trunk-io/trunk-action@v1` fails to install
**Solution**: Automatic fallback activates

```yaml
- name: Run fallback tools if Trunk fails
  if: failure()
  run: |
    echo "🚨 Trunk failed, running fallback script..."
    chmod +x tools/check-fallback.sh
    ./tools/check-fallback.sh
```

### Scenario 2: uv Dependency Resolution Issues

**Symptoms**: `uv sync` fails with conflict errors
**Solution**: Clear cache and use explicit resolution

```bash
# Clear uv cache
uv cache clean

# Use explicit Python version
uv python install 3.11
uv sync --python 3.11 --resolution=highest
```

### Scenario 3: Memory Issues in Performance Tests

**Symptoms**: Performance workflow OOM killed
**Solution**: Reduce test scope or increase runner memory

```yaml
# Use larger runner for memory-intensive tests
runs-on: ubuntu-latest-8-cores  # More memory available
```

### Scenario 4: Security Tool False Positives

**Symptoms**: Security scan fails on false positives
**Solution**: Configure tool-specific ignores

```yaml
# Bandit ignore patterns
- name: Run Bandit with exclusions
  run: |
    bandit -r cryptofeed/ -x */tests/* -f json
```

### Scenario 5: Workflow Permission Issues

**Symptoms**: Actions fail with permission errors
**Solution**: Configure appropriate permissions

```yaml
permissions:
  contents: read
  security-events: write
  pull-requests: write
  actions: read
```

## 📊 Analytics and Insights

### Workflow Performance Analytics

```bash
# Average workflow duration
gh run list --workflow=ci.yml --limit=50 --json startedAt,updatedAt | \
  jq '[.[] | ((.updatedAt | fromdateiso8601) - (.startedAt | fromdateiso8601))] | add / length'

# Success rate calculation
gh run list --workflow=ci.yml --limit=100 --json conclusion | \
  jq '[.[] | select(.conclusion == "success")] | length'
```

### Quality Metrics Tracking

```python
# Track quality trends
import json
import matplotlib.pyplot as plt

def analyze_quality_trends(reports_dir):
    """Analyze quality trends over time"""
    # Load historical quality reports
    # Generate trend charts
    # Identify regression patterns
    pass
```

### Cost Optimization

```yaml
# Optimize runner usage
strategy:
  matrix:
    include:
      - python-version: '3.9'
        os: ubuntu-latest     # Cheapest option
      - python-version: '3.12'
        os: ubuntu-latest-4-cores  # Only for latest Python
```

## 🎯 Best Practices Summary

### Workflow Design
1. **Fail Fast**: Run quick checks first
2. **Parallel Execution**: Maximize concurrent jobs
3. **Caching**: Use GitHub Actions cache effectively
4. **Fallbacks**: Always have backup plans

### Security
1. **Least Privilege**: Minimal required permissions
2. **Secret Management**: Use GitHub secrets properly
3. **SARIF Integration**: Leverage GitHub security features
4. **Regular Updates**: Keep actions and tools current

### Performance
1. **Runner Selection**: Choose appropriate runner sizes
2. **Artifact Management**: Clean up regularly
3. **Cache Strategy**: Cache dependencies and tools
4. **Resource Monitoring**: Track usage and costs

### Maintainability
1. **Documentation**: Keep guides current
2. **Version Pinning**: Use specific action versions
3. **Testing**: Validate workflow changes
4. **Monitoring**: Track health and performance

---

> 🤖 This guide complements the main README and provides practical examples for working with the modernized GitHub workflows.