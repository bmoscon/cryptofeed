# GitHub Workflows and Rulesets Setup Guide

This guide provides complete setup instructions for the cryptofeed project's GitHub Actions workflows and branch protection rulesets.

## Overview

The repository includes a comprehensive CI/CD and security infrastructure:

- **3 GitHub Actions Workflows** for CI/CD, releases, and security
- **4 Branch Protection Rulesets** for different branch types
- **Automated quality gates** and security scanning
- **Release automation** with multi-platform publishing

## 🔧 GitHub Actions Workflows

### 1. CI/CD Pipeline (`.github/workflows/ci.yml`)

**Triggers**: Push/PR to main, master, develop branches + manual dispatch

**Jobs**:

- **Code Quality Checks**: Ruff linting, Black formatting, isort imports, mypy typing
- **Multi-Python Testing**: Tests on Python 3.9, 3.10, 3.11, 3.12
- **Security Scan**: Bandit security linting with artifact upload
- **Build & Install**: Package building and installation verification
- **Integration Tests**: End-to-end testing (on PRs)
- **Dependency Check**: Vulnerability scanning with Safety
- **Performance Tests**: Benchmark execution (on PRs)

**Key Features**:

- Caching for faster builds
- Parallel job execution
- Codecov integration
- Artifact preservation
- Matrix testing across Python versions

### 2. Release Pipeline (`.github/workflows/release.yml`)

**Triggers**: Git tags (v\*) + manual dispatch

**Jobs**:

- **Validate Release**: Quality checks and version validation
- **Build Release**: Source and wheel distribution creation
- **GitHub Release**: Automated release notes and asset upload
- **PyPI Publishing**: TestPyPI validation → PyPI deployment
- **Docker Build**: Multi-platform container images

**Key Features**:

- Semantic version enforcement
- TestPyPI validation before production
- Automated release notes generation
- Multi-architecture Docker builds
- OIDC-based PyPI publishing (secure, no tokens)

### 3. Security Scanning (`.github/workflows/security.yml`)

**Triggers**: Push/PR + weekly schedule (Mondays 6 AM) + manual dispatch

**Jobs**:

- **CodeQL Analysis**: GitHub's semantic code analysis
- **Dependency Review**: License and vulnerability review (PRs only)
- **Vulnerability Scan**: Safety, pip-audit, Bandit security tools
- **Secrets Detection**: TruffleHog secrets scanning
- **License Check**: License compliance verification
- **Container Scan**: Trivy container vulnerability scanning
- **OSSF Scorecard**: Security posture assessment

**Key Features**:

- SARIF upload for security findings
- License compliance tracking
- Secrets detection across git history
- Container security scanning
- Supply chain security assessment

## 🛡️ Branch Protection Rulesets

### 1. Main Branch Protection (`ruleset-main-protection.json`)

**Target**: `main`, `master` branches  
**Enforcement**: Active (blocking)

**Rules**:

- ❌ Deletion protection
- ❌ Force push protection
- ✅ Linear history requirement
- ✅ Signed commits required
- ✅ Pull request required (1 approval)
- ✅ Dismiss stale reviews
- ✅ Require conversation resolution
- ✅ Required status checks:
  - Code Quality Checks
  - Run Tests (Python 3.11)
  - Security Scan
  - Build and Install Package

**Bypass**: Organization administrators only

### 2. Release Branch Protection (`ruleset-release-branches.json`)

**Target**: `release/*`, `hotfix/*` branches  
**Enforcement**: Active (blocking)

**Rules**:

- ❌ Deletion protection
- ❌ Force push protection
- ✅ Signed commits required
- ✅ Pull request required (2 approvals)
- ✅ Code owner review required
- ✅ Last push approval required
- ✅ Enhanced status checks (includes release validation)

**Bypass**: Administrators (PR only, no direct push)

### 3. Tag Protection (`ruleset-tag-protection.json`)

**Target**: `v*` tags (production releases)  
**Enforcement**: Active (blocking)

**Rules**:

- ❌ Tag deletion protection
- ✅ Signed tags required
- ✅ Semantic version pattern: `^v[0-9]+\.[0-9]+\.[0-9]+$`

**Excludes**: Pre-release tags (`*-rc*`, `*-beta*`, `*-alpha*`)

### 4. Feature Branch Guidelines (`ruleset-feature-branches.json`)

**Target**: `feature/*`, `feat/*`, `fix/*`, `docs/*` branches  
**Enforcement**: Evaluate (non-blocking feedback)

**Rules**:

- ✅ Conventional commit format validation
- ✅ Valid email format requirement
- ✅ Basic status checks (code quality only)

**Purpose**: Encourage best practices without blocking development

## 📋 Setup Instructions

### Prerequisites

1. **Repository admin access** for ruleset configuration
2. **GitHub Actions enabled** in repository settings
3. **Required secrets configured** (if using optional features):
   - `DOCKER_USERNAME` / `DOCKER_PASSWORD` (for Docker Hub)
   - `CODECOV_TOKEN` (for coverage reporting)

### Step 1: Deploy Workflows

The workflows are automatically active once committed to the repository:

```bash
# Workflows are in .github/workflows/ and auto-activate
git add .github/workflows/
git commit -m "feat: add GitHub Actions CI/CD workflows"
git push
```

### Step 2: Configure Rulesets

#### Option A: GitHub Web Interface (Recommended)

1. Navigate to **Settings** → **Rules** → **Rulesets**
2. Click **New branch ruleset** for each branch ruleset
3. Copy configurations from the JSON files:
   - `.github/ruleset-main-protection.json`
   - `.github/ruleset-release-branches.json`
   - `.github/ruleset-feature-branches.json`
4. Click **New tag ruleset** for tag protection
5. Copy configuration from `.github/ruleset-tag-protection.json`

#### Option B: GitHub CLI (Automated)

```bash
# Authenticate first
gh auth login

# Create all rulesets
gh api repos/:owner/:repo/rulesets --method POST --input .github/ruleset-main-protection.json
gh api repos/:owner/:repo/rulesets --method POST --input .github/ruleset-release-branches.json
gh api repos/:owner/:repo/rulesets --method POST --input .github/ruleset-tag-protection.json
gh api repos/:owner/:repo/rulesets --method POST --input .github/ruleset-feature-branches.json
```

### Step 3: Verify Setup

1. **Test CI Pipeline**: Create a test PR and verify all checks run
2. **Verify Branch Protection**: Try direct push to main (should be blocked)
3. **Check Status Checks**: Ensure workflow jobs appear as required checks
4. **Test Conventional Commits**: Use proper commit format on feature branches

## 🚀 Usage Workflows

### Development Workflow

```bash
# 1. Create feature branch
git checkout -b feature/new-functionality

# 2. Make changes with conventional commits
git commit -m "feat: add new delta lake optimization"

# 3. Push and create PR
git push -u origin feature/new-functionality
gh pr create --title "feat: add new functionality"

# 4. CI runs automatically, address any failures
# 5. Get required approvals
# 6. Merge when all checks pass
```

### Release Workflow

```bash
# 1. Create release branch
git checkout -b release/v1.2.0

# 2. Update version numbers, changelog
git commit -m "chore: prepare v1.2.0 release"

# 3. Create PR to main, get 2 approvals + code owner review
gh pr create --base main --title "release: v1.2.0"

# 4. After merge, create and push tag
git tag -s v1.2.0 -m "Release v1.2.0"
git push origin v1.2.0

# 5. Release workflow automatically:
#    - Validates release
#    - Builds packages
#    - Creates GitHub release
#    - Publishes to PyPI
#    - Builds Docker images
```

### Hotfix Workflow

```bash
# 1. Create hotfix branch from main
git checkout main
git pull
git checkout -b hotfix/critical-security-fix

# 2. Make minimal fix
git commit -m "fix: resolve critical security vulnerability"

# 3. Create PR with enhanced protection
gh pr create --base main --title "hotfix: critical security fix"

# 4. Get required approvals (2 reviewers + code owner)
# 5. Deploy hotfix release
git tag -s v1.2.1 -m "Hotfix v1.2.1"
git push origin v1.2.1
```

## 🔧 Customization

### Modifying Required Status Checks

Edit the ruleset JSON files to add/remove required checks:

```json
{
  "type": "required_status_checks",
  "parameters": {
    "required_status_checks": [
      {
        "context": "Your Custom Check Name",
        "integration_id": 15368
      }
    ]
  }
}
```

### Adding New Workflows

1. Create workflow file in `.github/workflows/`
2. Update ruleset configurations to include new status checks
3. Test thoroughly before enforcing

### Branch Naming Conventions

Supported patterns:

- **Feature**: `feature/`, `feat/`
- **Fixes**: `fix/`, `bugfix/`
- **Documentation**: `docs/`
- **Releases**: `release/`, `hotfix/`

## 🛠️ Troubleshooting

### Common Issues

**❌ Status checks not appearing**

- Ensure workflow job names match ruleset contexts exactly
- Verify workflows trigger on correct events (push/PR)
- Check that workflows have run at least once

**❌ Rulesets not enforcing**

- Confirm enforcement is set to "Active"
- Verify target branch patterns match your naming
- Check user permissions and bypass settings

**❌ Required reviewers not working**

- Ensure users have appropriate repository permissions
- Verify code owner files (CODEOWNERS) if required
- Check team membership for organization repositories

**❌ Signed commits failing**

- Configure GPG signing: `git config commit.gpgsign true`
- Set up GPG key in GitHub settings
- Use `git commit -S` for signed commits

### Debugging Steps

1. **Check workflow runs**: GitHub Actions tab
2. **Verify ruleset config**: Settings → Rules → Rulesets
3. **Test branch protection**: Try direct push to protected branch
4. **Review permissions**: Settings → Collaborators
5. **Check logs**: Workflow run details and annotations

## 📊 Monitoring and Metrics

### Available Metrics

- **Code Coverage**: Via Codecov integration
- **Security Findings**: SARIF uploads to GitHub Security tab
- **Build Success Rate**: GitHub Actions insights
- **Release Frequency**: Release history tracking
- **Dependency Vulnerabilities**: Security advisories

### Regular Maintenance

- **Weekly**: Review security scan results
- **Monthly**: Update workflow dependencies (actions versions)
- **Quarterly**: Review and adjust ruleset effectiveness
- **As needed**: Update Python versions, dependencies, security tools

## 📚 References

- [GitHub Rulesets Documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Conventional Commits Specification](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
- [OSSF Scorecard](https://github.com/ossf/scorecard)

---

**Note**: This infrastructure provides enterprise-grade CI/CD and security for the cryptofeed project. Start with basic configurations and gradually enable stricter enforcement as the team adapts to the new workflows.
