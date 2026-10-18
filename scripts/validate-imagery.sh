#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
command -v uv >/dev/null 2>&1 || { echo 'uv is required; tested with uv 0.13.0' >&2; exit 2; }
uv run --locked --python 3.12.12 --project research/imagery python -m unittest discover -s research/imagery/tests -v
# Validation must not depend on Python assertions surviving optimisation.
uv run --locked --python 3.12.12 --project research/imagery python -O -m unittest discover -s research/imagery/tests
printf 'Imagery registration validation passed (synthetic fixtures plus offline verification of the versioned package; no downloads)\n'
