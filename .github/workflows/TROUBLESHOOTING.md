# GitHub Workflows Troubleshooting Guide

## 🚨 Common Issues and Solutions

### Issue: Trunk Installation/Setup Failures

**Symptoms**:

- `trunk-io/trunk-action@v1` step fails
- Error: "Unable to download Trunk"
- Timeout during Trunk setup

**Solutions**:

1. **Automatic Fallback** (Already Configured):

   ```yaml
   - name: Run fallback tools if Trunk fails
     if: failure()
     run: |
       echo "🚨 Trunk failed, running fallback script..."
       chmod +x tools/check-fallback.sh
       ./tools/check-fallback.sh
   ```

2. **Manual Trunk Installation**:

   ```bash
   # If fallback doesn't work, debug manually
   curl -fsSL https://get.trunk.io | bash
   export PATH="$HOME/.local/bin:$PATH"
   trunk --version
   ```

3. **Skip Trunk Temporarily**:
   ```yaml
   # Emergency bypass - use direct tools
   - name: Run ruff directly
     run: |
       uv add --dev ruff
       uv run ruff check .
       uv remove --dev ruff
   ```

---

### Issue: uv Dependency Resolution Failures

**Symptoms**:

- `uv sync` fails with conflict errors
- "No solution found when resolving dependencies"
- Package installation timeouts

**Solutions**:

1. **Clear Cache and Retry**:

   ```bash
   uv cache clean
   uv sync --dev --resolution=highest
   ```

2. **Use Specific Python Version**:

   ```bash
   uv python install 3.11
   uv sync --python 3.11
   ```

3. **Debug Resolution**:

   ```bash
   # Verbose output to see conflicts
   uv sync --dev --verbose

   # Try offline mode if network issues
   uv sync --dev --offline
   ```

4. **Emergency pip Fallback**:
   ```yaml
   - name: Fallback to pip if uv fails
     if: failure()
     run: |
       python -m pip install --upgrade pip
       pip install -e .
       pip install pytest pytest-cov
   ```

---

### Issue: Quality Gate Failures

**Symptoms**:

- Code quality workflow fails with "Quality gate FAILED"
- Too many critical/high issues detected
- SARIF upload failures

**Solutions**:

1. **Check Issue Count**:

   ```bash
   # Local quality check
   trunk check --all --output-format=json > report.json
   grep -c "critical\|error" report.json
   ```

2. **Fix Critical Issues First**:

   ```bash
   # Auto-fix what's possible
   trunk format
   trunk check --fix --all

   # Manual review for remaining issues
   trunk check --all
   ```

3. **Adjust Quality Thresholds** (if needed):

   ```yaml
   # In code-quality.yml
   MAX_CRITICAL=5    # Temporarily increase if needed
   MAX_HIGH=20       # Adjust based on project state
   ```

4. **Bypass Quality Gate** (Emergency):
   ```yaml
   # Add to workflow for emergency bypass
   continue-on-error: true
   ```

---

### Issue: Performance Test Failures

**Symptoms**:

- Memory profiling OOM errors
- Benchmark timeouts
- Performance regression failures

**Solutions**:

1. **Use Larger Runner**:

   ```yaml
   runs-on: ubuntu-latest-8-cores # More memory/CPU
   ```

2. **Reduce Test Scope**:

   ```python
   # In benchmark scripts
   BENCHMARK_ITERATIONS = 10  # Reduce from 1000
   MEMORY_TEST_SIZE = 100     # Reduce test data size
   ```

3. **Skip Memory-Intensive Tests**:

   ```yaml
   - name: Run basic benchmarks only
     if: github.event_name == 'pull_request'
     run: |
       python benchmark_cryptofeed.py --basic-only
   ```

4. **Debug Memory Issues**:

   ```bash
   # Local memory debugging
   python -m memory_profiler your_script.py

   # Check for memory leaks
   valgrind --tool=memcheck python your_script.py
   ```

---

### Issue: Security Scan False Positives

**Symptoms**:

- Bandit reports non-issues as vulnerabilities
- Safety reports outdated CVEs
- TruffleHog detects test data as secrets

**Solutions**:

1. **Configure Bandit Exclusions**:

   ```yaml
   # .bandit config in pyproject.toml
   [tool.bandit]
   exclude_dirs = ["tests", "examples"]
   skips = ["B101", "B601"]  # Skip specific checks
   ```

2. **Safety Ignore File**:

   ```bash
   # Create .safety-policy.json
   {
     "security": {
       "ignore-cvss-severity-below": 7.0,
       "ignore-vulnerabilities": [
         "12345"  # Specific CVE to ignore
       ]
     }
   }
   ```

3. **TruffleHog Configuration**:

   ```yaml
   # In security.yml
   - name: Run TruffleHog with exclusions
     run: |
       trufflehog --exclude-paths=.trufflehogignore .
   ```

4. **Create Ignore Files**:
   ```bash
   # .trufflehogignore
   tests/fixtures/
   examples/
   *.md
   ```

---

### Issue: Release Pipeline Failures

**Symptoms**:

- PyPI upload authentication errors
- Docker build failures
- GitHub release creation errors

**Solutions**:

1. **Check PyPI Credentials**:

   ```bash
   # Verify PYPI_API_TOKEN secret is set
   # Test with TestPyPI first
   twine upload --repository testpypi dist/*
   ```

2. **Docker Build Issues**:

   ```yaml
   # Single platform first
   - name: Build Docker (single platform)
     run: |
       docker build -t cryptofeed:test .
   ```

3. **GitHub Token Permissions**:

   ```yaml
   permissions:
     contents: write # For releases
     packages: write # For container registry
   ```

4. **Version Tag Issues**:
   ```bash
   # Ensure proper tag format
   git tag v1.2.3  # Not 1.2.3 or v1.2.3-beta
   ```

---

### Issue: Workflow Permission Errors

**Symptoms**:

- "insufficient permissions" errors
- SARIF upload failures
- Artifact upload denied

**Solutions**:

1. **Configure Workflow Permissions**:

   ```yaml
   permissions:
     contents: read
     security-events: write
     pull-requests: write
     actions: read
     checks: write
   ```

2. **Repository Settings**:

   - Go to Settings → Actions → General
   - Set "Workflow permissions" to "Read and write permissions"
   - Enable "Allow GitHub Actions to create and approve pull requests"

3. **Token Scope Issues**:
   ```yaml
   # Use explicit token for sensitive operations
   - name: Upload SARIF
     uses: github/codeql-action/upload-sarif@v3
     with:
       token: ${{ secrets.GITHUB_TOKEN }}
   ```

---

### Issue: Workflow Timeout/Hanging

**Symptoms**:

- Jobs exceed 6-hour limit
- Steps hang indefinitely
- No progress for extended periods

**Solutions**:

1. **Add Timeouts**:

   ```yaml
   jobs:
     test:
       timeout-minutes: 30 # Job timeout
       steps:
         - name: Run tests
           timeout-minutes: 10 # Step timeout
           run: pytest tests/
   ```

2. **Debug Hanging Steps**:

   ```yaml
   # Add debugging
   env:
     ACTIONS_STEP_DEBUG: true
     ACTIONS_RUNNER_DEBUG: true
   ```

3. **Kill Hanging Processes**:
   ```yaml
   - name: Cleanup hanging processes
     if: always()
     run: |
       pkill -f python || true
       pkill -f pytest || true
   ```

---

### Issue: Cache-Related Problems

**Symptoms**:

- Cache restore failures
- Stale cached dependencies
- Excessive cache usage

**Solutions**:

1. **Clear Cache**:

   ```bash
   # Via GitHub CLI
   gh cache delete --all

   # Or use cache action
   - name: Clear cache
     run: |
       rm -rf ~/.cache/uv
   ```

2. **Better Cache Keys**:

   ```yaml
   - uses: actions/cache@v4
     with:
       path: ~/.cache/uv
       key: ${{ runner.os }}-uv-${{ hashFiles('**/pyproject.toml', 'uv.lock') }}
       restore-keys: |
         ${{ runner.os }}-uv-
   ```

3. **Cache Size Limits**:
   ```yaml
   # Limit cache scope
   - name: Clean large cache files
     run: |
       find ~/.cache/uv -name "*.whl" -size +50M -delete
   ```

---

## 🔧 Debugging Tools and Techniques

### Enable Verbose Logging

```yaml
env:
  ACTIONS_STEP_DEBUG: true
  ACTIONS_RUNNER_DEBUG: true
  TRUNK_DEBUG: true
  UV_VERBOSE: true
```

### Local Workflow Testing

```bash
# Install act for local testing
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Run workflow locally
act -j test --secret-file .secrets

# Test specific job
act -j lint-and-format -v
```

### Step-by-Step Debugging

```yaml
- name: Debug environment
  run: |
    echo "Python version: $(python --version)"
    echo "PATH: $PATH"
    echo "Working directory: $(pwd)"
    echo "Disk space: $(df -h)"
    echo "Memory: $(free -h)"
    env | sort
```

### Tool-Specific Debugging

```bash
# Trunk debugging
trunk --version
trunk config
trunk check --dry-run

# uv debugging
uv --version
uv tree
uv pip list

# Python environment
python -c "import sys; print(sys.path)"
python -c "import cryptofeed; print(cryptofeed.__file__)"
```

## 📞 Getting Help

### Internal Resources

1. **Check logs**: GitHub Actions → Failed run → View logs
2. **Review changes**: Compare with last successful run
3. **Local testing**: Reproduce issue locally
4. **Documentation**: Check workflow README files

### External Resources

1. **GitHub Actions docs**: https://docs.github.com/en/actions
2. **uv documentation**: https://docs.astral.sh/uv/
3. **Trunk documentation**: https://docs.trunk.io/
4. **Community forums**: GitHub Discussions

### Emergency Contacts

- **Repository maintainer**: @bmoscon
- **GitHub support**: For platform issues
- **Tool vendors**: For tool-specific problems

## 🔄 Recovery Procedures

### Workflow Completely Broken

```bash
# 1. Identify breaking change
git log --oneline -10 .github/workflows/

# 2. Revert problematic commit
git revert <bad-commit-hash>

# 3. Create hotfix branch
git checkout -b hotfix/workflow-fix

# 4. Test fix locally
act -j test

# 5. Deploy fix
git push origin hotfix/workflow-fix
```

### Mass Quality Issues

```bash
# 1. Run auto-fixes
trunk format
trunk check --fix --all

# 2. Commit auto-fixes
git add -A
git commit -m "fix: auto-format code with trunk"

# 3. Review remaining issues
trunk check --all > quality-issues.txt
```

### Performance Regression

```bash
# 1. Identify regression point
git bisect start
git bisect bad HEAD
git bisect good <last-good-commit>

# 2. Test each commit
git bisect run python benchmark_test.py

# 3. Fix or revert problematic change
```

---

> 📧 **Still stuck?** Open a GitHub issue with:
>
> - Workflow run URL
> - Error messages
> - Steps to reproduce
> - Expected vs actual behavior
