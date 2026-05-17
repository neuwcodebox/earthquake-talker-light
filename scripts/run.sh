#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

git fetch --prune
git pull --ff-only
uv sync
exec uv run python main.py
