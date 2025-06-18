#!/bin/bash
# Fallback when Trunk has issues - installs tools temporarily via uv
# Note: Primary workflow should use Trunk for tool management

set -e

echo "🔍 Fallback: Installing and running tools via uv (temporary)..."

# Install tools temporarily (mypy excluded for performance)
echo "📦 Installing ruff, bandit temporarily..."
uv add --dev ruff bandit

# Format code with ruff
echo "🎨 Formatting code with ruff..."
uv run ruff format .

# Lint code with ruff
echo "📋 Linting code with ruff..."
uv run ruff check --fix .

# Type checking with mypy (disabled for performance)
# echo "🔍 Type checking with mypy..."
# uv run mypy cryptofeed --ignore-missing-imports || echo "⚠️  Some mypy errors found (non-blocking)"

# Security scanning with bandit
echo "🔒 Security scanning with bandit..."
uv run bandit -r cryptofeed/ -q || echo "⚠️  Some security issues found (non-blocking)"

# Clean up - remove temporary tools
echo "🧹 Removing temporary tools..."
uv remove --dev ruff bandit

echo "✅ Fallback code quality checks complete!"
echo ""
echo "💡 Note: This is a fallback script. Use 'trunk check' for normal workflow."
