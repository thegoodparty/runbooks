#!/usr/bin/env bash
# Install system dependencies for runbooks scripts on macOS.
# Safe to run multiple times — brew install is a no-op if already installed.
#
# Required tools: brew (https://brew.sh)

set -euo pipefail

echo "==> Checking for Homebrew..."
if ! command -v brew &>/dev/null; then
  echo "ERROR: Homebrew not found. Install it first: https://brew.sh"
  exit 1
fi

echo "==> Installing pandoc..."
brew install pandoc

echo "==> Installing texlive (provides xelatex for PDF generation)..."
brew install texlive

echo "==> Installing uv (Python package manager)..."
if command -v uv &>/dev/null; then
  echo "    uv already installed at $(which uv)"
else
  curl -LsSf https://astral.sh/uv/install.sh | sh
  echo "    Restart your shell or run: source \$HOME/.local/bin/env"
fi

echo "==> Installing Python dependencies..."
cd "$(git rev-parse --show-toplevel)/scripts/python" && uv sync

echo ""
echo "Setup complete. All runbook scripts should now be runnable."
