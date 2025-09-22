# Archived Proxy Specifications

This directory contains the original proxy system specification files that have been consolidated and reorganized.

## Status: ✅ ARCHIVED - DO NOT USE

These files are preserved for historical reference but should not be used. The content has been reorganized into a more maintainable structure.

## New Documentation Location

**Current Documentation:** [`../proxy/`](../../proxy/)

## Archived Files

| File | Original Purpose | New Location |
|------|------------------|---------------|
| `proxy_mvp_spec.md` | Main MVP specification | [Technical Specification](../../proxy/technical-specification.md) |
| `ccxt_proxy.md` | CCXT integration details | [Technical Specification - Integration](../../proxy/technical-specification.md#integration-points) |
| `simple_proxy_architecture.md` | Architecture comparison | [Architecture](../../proxy/architecture.md) |
| `proxy_configuration_examples.md` | Configuration patterns | [User Guide](../../proxy/user-guide.md) |
| `proxy_configuration_patterns.md` | More configuration examples | [User Guide](../../proxy/user-guide.md) |
| `proxy_system_overview.md` | System overview | [Overview](../../proxy/README.md) |
| `universal_proxy_injection.md` | Injection architecture | [Architecture](../../proxy/architecture.md) |

## Why These Files Were Archived

**Problems with Original Structure:**
- ❌ Redundant content across multiple files
- ❌ No clear audience separation (user vs developer)
- ❌ Difficult to find relevant information
- ❌ Inconsistent implementation details
- ❌ Scattered configuration examples

**Benefits of New Structure:**
- ✅ Clear audience-based organization
- ✅ Single source of truth for each topic
- ✅ Progressive disclosure (overview → usage → technical → design)
- ✅ Consistent and up-to-date implementation details
- ✅ Comprehensive configuration examples in one place

## Content Migration

All useful content from these archived files has been migrated to the new documentation structure:

- **User-facing content** → [User Guide](../../proxy/user-guide.md)
- **Implementation details** → [Technical Specification](../../proxy/technical-specification.md)
- **Design decisions** → [Architecture](../../proxy/architecture.md)
- **Quick start information** → [Overview](../../proxy/README.md)

## Historical Context

These files represent the evolution of the proxy system design:

1. **Initial over-engineering** - Complex plugin systems and enterprise features
2. **Refactoring to START SMALL** - Simplified to MVP functionality
3. **Implementation** - Actual working code with tests
4. **Documentation consolidation** - This reorganization

The archived files show the journey from complex theoretical design to simple, working implementation.

## For Historical Reference Only

These files are maintained for:
- Understanding design evolution
- Learning from over-engineering mistakes
- Seeing how START SMALL principles were applied
- Historical context for design decisions

**Do not use these files for current development or documentation.**

Use the current documentation at [`../proxy/`](../../proxy/) instead.