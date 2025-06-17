# GitHub Workflows Documentation

This directory contains the CI/CD workflows for the cryptofeed project, modernized with **uv** and **Trunk** integration for optimal performance and reliability.

## 🚀 Workflow Overview

| Workflow                                       | Purpose                     | Triggers                   | Key Features                                 |
| ---------------------------------------------- | --------------------------- | -------------------------- | -------------------------------------------- |
| [`ci.yml`](./ci.yml)                           | Main CI/CD pipeline         | Push, PR, Manual           | uv + Trunk integration, multi-Python testing |
| [`code-quality.yml`](./code-quality.yml)       | Comprehensive code analysis | Push, PR, Schedule, Manual | Quality gates, detailed reporting            |
| [`performance.yml`](./performance.yml)         | Performance benchmarking    | Push, PR, Schedule, Manual | Multi-Python benchmarks, memory profiling    |
| [`security.yml`](./security.yml)               | Security scanning           | Push, PR, Schedule, Manual | Multi-tool security analysis                 |
| [`release.yml`](./release.yml)                 | Release automation          | Tags, Manual               | PyPI publishing, GitHub releases             |
| [`codeql-analysis.yml`](./codeql-analysis.yml) | GitHub CodeQL analysis      | Schedule, Manual           | Advanced security scanning                   |

## 🛠️ Modern Toolchain

### Core Technologies

- **[uv](https://github.com/astral-sh/uv)**: Ultra-fast Python package manager (10-100x faster than pip)
- **[Trunk](https://trunk.io)**: Unified tool orchestration with hermetic installs
- **Fallback System**: Reliable uv-based fallbacks when Trunk has issues

### Tool Management

- **Trunk Managed**: ruff@0.11.13, mypy@1.16.1, bandit@1.8.5
- **uv Managed**: Project dependencies, development tools
- **Hermetic Installs**: Consistent tool versions across all environments

## 📋 Workflow Details

### 1. CI/CD Pipeline (`ci.yml`)

**Purpose**: Main continuous integration and deployment pipeline

**Key Jobs**:

- **Code Quality**: Trunk-managed linting, formatting, type checking
- **Testing**: Multi-Python version testing (3.9-3.12) with uv
- **Security**: Bandit security scanning via Trunk
- **Build**: Package building and installation testing
- **Integration**: Cross-platform compatibility testing
- **Performance**: Basic performance validation

**Performance Benefits**:

- ⚡ **10-150x faster** tool execution via Trunk
- 🚀 **Parallel execution** with uv's concurrent installs
- 🛡️ **Robust fallbacks** for reliability

**Triggers**:

```yaml
on:
  push:
    branches: [main, master, develop]
  pull_request:
    branches: [main, master, develop]
  workflow_dispatch:
```

### 2. Code Quality Analysis (`code-quality.yml`)

**Purpose**: Comprehensive code quality analysis and reporting

**Key Features**:

- **Trunk Analysis**: Unified linting, formatting, and security checks
- **Quality Gates**: Configurable thresholds for critical/high issues
- **Detailed Reporting**: JSON, SARIF, and human-readable formats
- **Complexity Analysis**: Cyclomatic complexity and maintainability metrics
- **Documentation Check**: Docstring coverage and style validation
- **PR Comments**: Automated quality summaries on pull requests

**Quality Thresholds**:

```yaml
MAX_CRITICAL: 0 # Zero tolerance for critical issues
MAX_HIGH: 10 # Warning threshold for high-priority issues
```

**Artifacts Generated**:

- `trunk-report.json` - Programmatic analysis results
- `trunk-report.sarif` - GitHub Security tab integration
- `complexity-report.txt` - Code complexity metrics
- `doc-coverage.txt` - Documentation coverage analysis

### 3. Performance Benchmarks (`performance.yml`)

**Purpose**: Performance monitoring and regression detection

**Key Features**:

- **Multi-Python Testing**: Benchmarks across Python 3.10-3.12
- **Memory Profiling**: Memory usage analysis and leak detection
- **Continuous Profiling**: Long-running performance analysis
- **PR Comparisons**: Performance impact analysis for pull requests
- **Cryptofeed-Specific**: Tailored benchmarks for exchange integrations

**Benchmark Types**:

- **Standard**: Core functionality benchmarks
- **Comprehensive**: Full system performance analysis
- **Memory**: Memory usage and leak detection
- **Network**: Network performance and latency testing

**Performance Metrics**:

- Function execution times
- Memory consumption patterns
- CPU utilization profiles
- Network latency measurements

### 4. Security Scanning (`security.yml`)

**Purpose**: Comprehensive security analysis and vulnerability detection

**Security Tools**:

- **CodeQL**: GitHub's semantic code analysis
- **Bandit**: Python security linter (Trunk-managed with fallback)
- **Safety**: Dependency vulnerability scanning
- **pip-audit**: PyPI package security analysis
- **TruffleHog**: Secrets detection
- **Trivy**: Container security scanning
- **OSSF Scorecard**: Open source security scoring

**Security Features**:

- **Dependency Review**: Automated dependency security analysis
- **License Compliance**: License compatibility checking
- **Secrets Detection**: Prevent accidental secret commits
- **Container Scanning**: Docker image vulnerability analysis
- **SARIF Integration**: Security findings in GitHub Security tab

### 5. Release Pipeline (`release.yml`)

**Purpose**: Automated release management and distribution

**Release Process**:

1. **Validation**: Quality checks with Trunk integration
2. **Building**: Source and wheel distribution creation
3. **Testing**: TestPyPI deployment and verification
4. **GitHub Release**: Automated release notes and artifact uploads
5. **PyPI Publishing**: Production deployment with security verification
6. **Docker**: Multi-platform container builds and publishing

**Release Features**:

- **Semantic Versioning**: Automated version detection
- **Release Notes**: Generated changelog and installation instructions
- **Multi-Platform**: Linux/ARM64 and AMD64 container builds
- **Security**: Trusted publishing with OIDC tokens

### 6. CodeQL Analysis (`codeql-analysis.yml`)

**Purpose**: Advanced security analysis with GitHub CodeQL

**Analysis Features**:

- **Semantic Analysis**: Deep code understanding beyond syntax
- **Security Queries**: Extended security and quality rule sets
- **Scheduled Scanning**: Weekly comprehensive analysis
- **SARIF Integration**: Direct GitHub Security tab reporting

## 🔧 Configuration

### Environment Variables

```yaml
env:
  PYTHON_VERSION: "3.11" # Default Python version for most jobs
```

### Dependabot Integration

The workflows are integrated with Dependabot for automated dependency updates:

```yaml
# .github/dependabot.yml
- package-ecosystem: "github-actions"
  schedule:
    interval: "weekly"
  groups:
    github-actions:
      patterns: ["actions/*", "github/*"]
```

### Branch Protection

Recommended branch protection rules:

- **Require PR reviews**: Minimum 1 reviewer
- **Require status checks**: CI/CD must pass
- **Require up-to-date branches**: Prevent outdated merges
- **Restrict pushes**: Direct pushes to main/master blocked

## 📊 Monitoring and Observability

### Workflow Monitoring

- **Status Badges**: Add to README for workflow status visibility
- **Artifact Retention**: 7-30 days based on workflow type
- **Performance Tracking**: Historical benchmark data
- **Security Dashboards**: GitHub Security tab integration

### Key Metrics

- **Build Times**: Track workflow execution duration
- **Success Rates**: Monitor workflow reliability
- **Performance Trends**: Benchmark result analysis
- **Security Coverage**: Vulnerability detection rates

## 🚨 Troubleshooting

### Common Issues

#### Trunk Installation Failures

```bash
# Fallback mechanism automatically activates
echo "🚨 Trunk failed, running fallback script..."
chmod +x tools/check-fallback.sh
./tools/check-fallback.sh
```

#### uv Dependency Resolution

```bash
# Clear cache and retry
uv cache clean
uv sync --dev
```

#### Python Version Conflicts

```bash
# Use explicit Python version
uv python install 3.11
uv sync --python 3.11
```

### Debugging Workflows

#### Enable Debug Logging

```yaml
env:
  ACTIONS_STEP_DEBUG: true
  ACTIONS_RUNNER_DEBUG: true
```

#### Local Testing

```bash
# Test workflows locally with act
act -j test --secret-file .secrets
```

## 🔄 Maintenance

### Regular Tasks

1. **Weekly**: Review workflow performance and failure rates
2. **Monthly**: Update action versions via Dependabot
3. **Quarterly**: Review and optimize quality gate thresholds
4. **Annually**: Audit security configurations and permissions

### Workflow Updates

When updating workflows:

1. **Test locally** with representative data
2. **Use feature branches** for workflow changes
3. **Monitor carefully** after deployment
4. **Document changes** in commit messages

### Performance Optimization

- **Cache Dependencies**: Use GitHub Actions cache for uv
- **Parallel Jobs**: Maximize concurrent execution
- **Artifact Management**: Clean up old artifacts regularly
- **Resource Allocation**: Match runner specs to job requirements

## 📚 Additional Resources

- [uv Documentation](https://docs.astral.sh/uv/)
- [Trunk Documentation](https://docs.trunk.io/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Dependabot Configuration](https://docs.github.com/en/code-security/dependabot)

## 🤝 Contributing

When contributing to workflow improvements:

1. **Follow conventions**: Use established patterns and naming
2. **Test thoroughly**: Validate changes in feature branches
3. **Document changes**: Update this README and commit messages
4. **Consider impact**: Assess effects on build times and reliability
5. **Maintain compatibility**: Ensure backward compatibility when possible

---

> 🤖 This documentation is maintained alongside the workflows and reflects the current state of the CI/CD pipeline. For questions or improvements, please open an issue or pull request.
