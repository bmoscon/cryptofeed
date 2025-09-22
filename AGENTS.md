# Agent Usage Guide

This repository supports Kiro-style spec-driven development via Claude CLI commands stored under `.claude/commands/kiro/`. The primary commands are:

| Command | Purpose |
| --- | --- |
| `/kiro:spec-init <project description>` | Create a new spec (metadata + requirements stub) |
| `/kiro:spec-requirements <feature>` | Generate and iterate on requirements.md |
| `/kiro:spec-design <feature>` | Produce design.md once requirements are approved |
| `/kiro:spec-tasks <feature>` | Generate tasks.md after design approval |
| `/kiro:spec-status [feature]` | Report current phase/approvals for specs |
| `/kiro:spec-impl <feature> [tasks]` | Execute implementation tasks using TDD |
| `/kiro:steering` / `/kiro:steering-custom` | Maintain global steering/context documents |
| `/kiro:validate-design <feature>` | Check design compliance |
| `/kiro:validate-gap <feature>` | Identify gaps between spec artifacts |

## Spec-Driven Flow

1. Initialize a spec with `/kiro:spec-init`.
2. Generate/approve requirements `/kiro:spec-requirements`.
3. Generate/approve design via `/kiro:spec-design`.
4. Produce implementation tasks `/kiro:spec-tasks`.
5. Implement features with `/kiro:spec-impl` (TDD, update tasks.md).
6. Monitor progress using `/kiro:spec-status`.
7. Utilize steering commands for repository-wide guidance.

