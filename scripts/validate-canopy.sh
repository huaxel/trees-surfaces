#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
command -v uv >/dev/null 2>&1 || { echo 'uv is required; tested with uv 0.13.0' >&2; exit 2; }
uv run --locked --python 3.12.12 --project research/canopy python -m unittest discover -s research/canopy/tests -v
# Validation must not depend on Python assertions surviving optimisation.
uv run --locked --python 3.12.12 --project research/canopy python -O -m unittest discover -s research/canopy/tests
printf 'Canopy geometry and provenance validation passed (no upstream data downloads)\n'
