#!/usr/bin/env bash
# Conductor workspace setup — runs once when a new workspace (git worktree) is created.
# Conductor sets: CONDUCTOR_ROOT_PATH (original clone), CONDUCTOR_WORKSPACE_PATH, CONDUCTOR_WORKSPACE_NAME.
set -euo pipefail

echo "==> Setting up workspace: ${CONDUCTOR_WORKSPACE_NAME:-$(basename "$PWD")}"

# 1. Python deps (incl. pytest/ruff)
if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv not found on PATH. Install: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi
uv sync --extra dev

# 2. Secrets — .env is gitignored, copy from the root repo if it exists there
ROOT="${CONDUCTOR_ROOT_PATH:-}"
if [[ -n "$ROOT" && -f "$ROOT/.env" && ! -f .env ]]; then
    cp "$ROOT/.env" .env
    echo "==> Copied .env from root repo"
fi
if [[ -n "$ROOT" && -f "$ROOT/config/secrets.yaml" && ! -f config/secrets.yaml ]]; then
    cp "$ROOT/config/secrets.yaml" config/secrets.yaml
    echo "==> Copied config/secrets.yaml from root repo"
fi

# 3. Market-data cache — gitignored Parquet bars; symlink to the root repo's cache
#    so each worktree doesn't re-download history. Cache is read-mostly (keyed by
#    symbol/timeframe/range), so sharing across parallel workspaces is safe.
mkdir -p data
if [[ -n "$ROOT" && -d "$ROOT/data/cache" && ! -e data/cache ]]; then
    ln -s "$ROOT/data/cache" data/cache
    echo "==> Symlinked data/cache -> $ROOT/data/cache"
else
    mkdir -p data/cache
fi

# 4. Sanity check
uv run python -c "import pandas, numpy, pyarrow; print('==> Core deps OK')"
echo "==> Workspace ready"
