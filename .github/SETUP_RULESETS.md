# GitHub Branch Rulesets Setup Guide

This guide explains how to configure GitHub branch rulesets for the cryptofeed project using the provided configuration files.

## Overview

The repository includes four pre-configured rulesets:

1. **Main Branch Protection** - Strict protection for main/master branches
2. **Release Branch Protection** - Enhanced protection for release branches
3. **Tag Protection** - Semantic version tag enforcement
4. **Feature Branch Guidelines** - Lightweight rules for feature branches

## Manual Setup via GitHub Web Interface

### 1. Navigate to Repository Settings

1. Go to your repository on GitHub
2. Click **Settings** tab
3. In the left sidebar, click **Rules** → **Rulesets**

### 2. Create Main Branch Protection Ruleset

1. Click **New branch ruleset**
2. Copy configuration from `.github/ruleset-main-protection.json`
3. Configure:
   - **Name**: "Main Branch Protection"
   - **Enforcement status**: Active
   - **Target branches**: `main`, `master`
   - **Rules**: Enable all protection rules
   - **Bypass list**: Repository administrators

### 3. Create Release Branch Protection Ruleset

1. Click **New branch ruleset**
2. Copy configuration from `.github/ruleset-release-branches.json`
3. Configure:
   - **Name**: "Release Branch Protection"
   - **Enforcement status**: Active
   - **Target branches**: `release/*`, `hotfix/*`
   - **Rules**: Enhanced protection with required code owner reviews
   - **Required approvers**: 2

### 4. Create Tag Protection Ruleset

1. Click **New tag ruleset**
2. Copy configuration from `.github/ruleset-tag-protection.json`
3. Configure:
   - **Name**: "Tag Protection"
   - **Enforcement status**: Active
   - **Target tags**: `v*` (semantic versions only)
   - **Rules**: Deletion protection and signature requirements

### 5. Create Feature Branch Guidelines

1. Click **New branch ruleset**
2. Copy configuration from `.github/ruleset-feature-branches.json`
3. Configure:
   - **Name**: "Feature Branch Guidelines"
   - **Enforcement status**: Evaluate (non-blocking)
   - **Target branches**: `feature/*`, `feat/*`, `fix/*`, `docs/*`
   - **Rules**: Conventional commit enforcement

## Automated Setup via GitHub CLI

```bash
# Authenticate with GitHub CLI
gh auth login

# Create main branch protection
gh api repos/:owner/:repo/rulesets \\
  --method POST \\
  --input .github/ruleset-main-protection.json

# Create release branch protection
gh api repos/:owner/:repo/rulesets \\
  --method POST \\
  --input .github/ruleset-release-branches.json

# Create tag protection
gh api repos/:owner/:repo/rulesets \\
  --method POST \\
  --input .github/ruleset-tag-protection.json

# Create feature branch guidelines
gh api repos/:owner/:repo/rulesets \\
  --method POST \\
  --input .github/ruleset-feature-branches.json
```

## Required GitHub Actions Integration

The rulesets reference GitHub Actions workflows that must be present:

### Status Checks Referenced

- **Code Quality Checks** (from `ci.yml`)
- **Run Tests** (from `ci.yml`)
- **Security Scan** (from `security.yml`)
- **Build and Install Package** (from `ci.yml`)
- **Validate Release** (from `release.yml`)

### Workflow Job Names Must Match

Ensure your workflow job names exactly match the status check contexts in the rulesets:

```yaml
# In .github/workflows/ci.yml
jobs:
  lint-and-format:
    name: Code Quality Checks # Referenced in rulesets

  test:
    name: Run Tests # Referenced in rulesets

  security:
    name: Security Scan # Referenced in rulesets
```

## Enforcement Levels

### Active Enforcement

- **Main/Master Branches**: Strict enforcement, blocks non-compliant pushes
- **Release Branches**: Enhanced protection with mandatory reviews
- **Tags**: Prevents deletion and enforces semantic versioning

### Evaluate Mode

- **Feature Branches**: Provides feedback without blocking development

## Bypass Configuration

### Repository Administrators

- Can bypass main branch protection in emergency situations
- Cannot bypass release branch protection (requires PR)
- Can manage tags for release preparation

### No Bypass

- Feature branch guidelines have no bypass actors
- Encourages consistent development practices

## Customization

### Modify Target Branches

Edit the `conditions.ref_name.include` arrays in the JSON files:

```json
{
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/main", "refs/heads/develop"],
      "exclude": []
    }
  }
}
```

### Adjust Required Reviewers

Modify the `required_approving_review_count` parameter:

```json
{
  "type": "pull_request",
  "parameters": {
    "required_approving_review_count": 2
  }
}
```

### Update Status Checks

Add or remove required GitHub Actions jobs:

```json
{
  "type": "required_status_checks",
  "parameters": {
    "required_status_checks": [
      {
        "context": "Your Custom Check",
        "integration_id": 15368
      }
    ]
  }
}
```

## Validation

After setup, test the rulesets:

1. **Create test branch**: `git checkout -b test/ruleset-validation`
2. **Make commit with invalid format**: Should trigger feature branch rules
3. **Attempt direct push to main**: Should be blocked by main branch protection
4. **Create PR**: Should require status checks and reviews

## Troubleshooting

### Status Checks Not Found

- Ensure GitHub Actions workflows are committed and running
- Verify job names match exactly between workflows and rulesets
- Check that workflows trigger on the correct events

### Bypass Not Working

- Confirm user has appropriate repository permissions
- Check that bypass actor configuration matches user type
- Verify enforcement status is set correctly

### Rules Not Applying

- Ensure target branch patterns match your branch naming
- Check that rulesets are in "Active" enforcement mode
- Verify conditions are correctly configured

## Best Practices

1. **Start with Evaluate mode** for new rules
2. **Test thoroughly** before enabling Active enforcement
3. **Document exceptions** for bypass usage
4. **Regular review** of ruleset effectiveness
5. **Team training** on new workflow requirements

## Related Documentation

- [GitHub Rulesets Documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets)
- [GitHub Actions Integration](https://docs.github.com/en/actions)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Semantic Versioning](https://semver.org/)
