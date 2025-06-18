#!/bin/bash
# Simplified code quality checking using Trunk
# This replaces the individual tool commands with a unified Trunk workflow

set -e

echo "🔍 Running comprehensive code quality checks with Trunk..."

# Use Trunk for unified linting and formatting (mypy disabled for performance)
echo "📋 Checking code with Trunk (ruff, bandit, git-diff-check)..."
trunk check --filter=ruff,bandit,git-diff-check

echo "🎨 Auto-formatting code with Trunk..."
trunk fmt --filter=ruff

echo "✅ Code quality checks complete!"
echo ""
echo "💡 To run individual tools manually:"
echo "   trunk check --filter=ruff    # Linting only"
echo "   trunk check --filter=bandit  # Security scanning only"
echo "   trunk fmt                    # Format all files"
echo "   # Note: mypy disabled in local/CI for performance"
