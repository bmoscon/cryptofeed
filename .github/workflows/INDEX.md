# GitHub Workflows Documentation Index

Welcome to the complete documentation for cryptofeed's modernized GitHub workflows! This index will help you find exactly what you need.

## 📚 Documentation Structure

### 🎯 **Quick Navigation**

| Document                                       | Purpose                    | Best For                 |
| ---------------------------------------------- | -------------------------- | ------------------------ |
| **[README.md](./README.md)**                   | Complete workflow overview | Understanding the system |
| **[QUICK_REFERENCE.md](./QUICK_REFERENCE.md)** | Essential commands & info  | Daily development        |
| **[WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md)**   | Hands-on examples          | Implementation details   |
| **[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)** | Problem-solving guide      | When things go wrong     |
| **[INDEX.md](./INDEX.md)**                     | This navigation guide      | Finding the right docs   |

## 🚀 Getting Started

### New to the Workflows?

1. **Start here**: [README.md](./README.md) - Complete overview
2. **Then read**: [QUICK_REFERENCE.md](./QUICK_REFERENCE.md) - Essential commands
3. **Keep handy**: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - When you need help

### Experienced Developer?

- **Quick commands**: [QUICK_REFERENCE.md](./QUICK_REFERENCE.md)
- **Advanced usage**: [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md)

### Setting Up New Workflows?

- **Architecture overview**: [README.md](./README.md) → "Workflow Details" section
- **Customization examples**: [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md) → "Customization Examples"

## 📋 Content by Topic

### 🔧 **Configuration & Setup**

- **Tool versions**: [README.md](./README.md#modern-toolchain)
- **Environment variables**: [QUICK_REFERENCE.md](./QUICK_REFERENCE.md#environment-variables)
- **Quality thresholds**: [README.md](./README.md#code-quality-analysis-code-qualityyml)
- **Custom workflows**: [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md#customization-examples)

### ⚡ **Daily Operations**

- **Running workflows**: [QUICK_REFERENCE.md](./QUICK_REFERENCE.md#quick-commands)
- **PR checklist**: [QUICK_REFERENCE.md](./QUICK_REFERENCE.md#before-submitting-pr)
- **Status monitoring**: [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md#monitoring-and-alerting)
- **Local testing**: [README.md](./README.md#debugging-workflows)

### 🛡️ **Security & Quality**

- **Security tools overview**: [README.md](./README.md#security-scanning-securityyml)
- **Quality gates**: [README.md](./README.md#code-quality-analysis-code-qualityyml)
- **SARIF integration**: [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md#sarif-integration)
- **False positive handling**: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md#issue-security-scan-false-positives)

### 📊 **Performance & Monitoring**

- **Benchmark types**: [README.md](./README.md#performance-benchmarks-performanceyml)
- **Performance analysis**: [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md#reading-performance-reports)
- **Workflow monitoring**: [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md#workflow-monitoring-setup)
- **Cost optimization**: [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md#cost-optimization)

### 🚨 **Troubleshooting**

- **Common issues**: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md#common-issues-and-solutions)
- **Emergency procedures**: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md#recovery-procedures)
- **Debugging tools**: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md#debugging-tools-and-techniques)
- **Getting help**: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md#getting-help)

## 🎯 Use Case Guide

### "I want to..."

#### **Understand the workflows**

→ [README.md](./README.md) - Start with the complete overview

#### **Run quality checks locally**

→ [QUICK_REFERENCE.md](./QUICK_REFERENCE.md#local-development)

```bash
trunk check --all
uv run pytest tests/
```

#### **Submit a pull request**

→ [QUICK_REFERENCE.md](./QUICK_REFERENCE.md#before-submitting-pr)

#### **Fix a failing workflow**

→ [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - Check common issues first

#### **Add a new workflow**

→ [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md#customization-examples)

#### **Monitor workflow performance**

→ [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md#workflow-performance-analytics)

#### **Configure security scanning**

→ [README.md](./README.md#security-scanning-securityyml) + [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md#security-tools-overview)

#### **Optimize workflow costs**

→ [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md#cost-optimization)

#### **Debug a hanging workflow**

→ [TROUBLESHOOTING.md](./TROUBLESHOOTING.md#issue-workflow-timeouthanging)

#### **Set up release automation**

→ [README.md](./README.md#release-pipeline-releaseyml) + [QUICK_REFERENCE.md](./QUICK_REFERENCE.md#release-process)

## 📖 Reading Guide by Role

### 👨‍💻 **Developer**

1. **Essential**: [QUICK_REFERENCE.md](./QUICK_REFERENCE.md) - Bookmark this!
2. **When PR fails**: [QUICK_REFERENCE.md](./QUICK_REFERENCE.md#pr-failed---what-to-check)
3. **Local testing**: [README.md](./README.md#debugging-workflows)

### 🔧 **DevOps Engineer**

1. **Architecture**: [README.md](./README.md) - Complete system overview
2. **Monitoring**: [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md#monitoring-and-alerting)
3. **Troubleshooting**: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - Keep this handy

### 👨‍💼 **Project Manager**

1. **Overview**: [README.md](./README.md#workflow-overview) - High-level summary
2. **Metrics**: [QUICK_REFERENCE.md](./QUICK_REFERENCE.md#key-metrics-to-watch)
3. **Status monitoring**: [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md#workflow-monitoring)

### 🛡️ **Security Team**

1. **Security features**: [README.md](./README.md#security-scanning-securityyml)
2. **Tool configuration**: [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md#security-tools-overview)
3. **SARIF integration**: [WORKFLOW_GUIDE.md](./WORKFLOW_GUIDE.md#sarif-integration)

## 🔍 Quick Lookup

### Common Commands

```bash
# Quality checks
trunk check --all

# Run tests
uv run pytest tests/

# Manual workflow trigger
gh workflow run ci.yml

# Check workflow status
gh run list --workflow=ci.yml --limit=5

# Emergency fallback
./tools/check-fallback.sh
```

### Key Files Referenced

- **Trunk config**: `.trunk/trunk.yaml`
- **Dependencies**: `pyproject.toml`
- **Fallback script**: `tools/check-fallback.sh`
- **Dependabot**: `.github/dependabot.yml`

### Important URLs

- **Actions dashboard**: `/actions`
- **Security tab**: `/security`
- **Code scanning**: `/security/code-scanning`

## 🆘 Emergency Quick Links

### Workflow is Broken

→ [TROUBLESHOOTING.md](./TROUBLESHOOTING.md#workflow-completely-broken)

### Quality Gate Failing

→ [TROUBLESHOOTING.md](./TROUBLESHOOTING.md#issue-quality-gate-failures)

### Performance Issues

→ [TROUBLESHOOTING.md](./TROUBLESHOOTING.md#issue-performance-test-failures)

### Security False Positives

→ [TROUBLESHOOTING.md](./TROUBLESHOOTING.md#issue-security-scan-false-positives)

### Need Help

→ [TROUBLESHOOTING.md](./TROUBLESHOOTING.md#getting-help)

## 📝 Document Maintenance

### Keeping Docs Current

- **Update frequency**: With each workflow change
- **Version alignment**: Docs match workflow versions
- **Link validation**: All internal links working
- **Example accuracy**: Commands and examples tested

### Contributing to Docs

1. **Follow existing structure** and formatting
2. **Test all examples** before submitting
3. **Update index** when adding new sections
4. **Keep quick reference** current with changes

---

## 🤖 About This Documentation

This documentation suite was created alongside the workflow modernization to ensure developers have comprehensive guidance for the new uv + Trunk toolchain.

**Key Features**:

- **Layered approach**: From quick reference to deep-dive guides
- **Role-based navigation**: Content organized by user needs
- **Practical focus**: Real commands and examples
- **Troubleshooting first**: Common issues prominently featured

**Last Updated**: With workflow modernization completion
**Maintained By**: Repository maintainers and community contributors

---

> 🔍 **Can't find what you need?** Check the [troubleshooting guide](./TROUBLESHOOTING.md#getting-help) for additional resources and support options.
