#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
command -v uv >/dev/null 2>&1 || { echo 'uv is required; tested with uv 0.13.0' >&2; exit 2; }

# The checker proves it can fail before it is trusted to pass.
uv run --locked --python 3.12.12 --project research/canopy python scripts/check_docs.py --self-test
uv run --locked --python 3.12.12 --project research/canopy python scripts/check_docs.py
printf 'Documentation reference and pinned-claim validation passed\n'
