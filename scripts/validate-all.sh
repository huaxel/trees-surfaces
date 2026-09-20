#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

scripts/validate-prototypes.sh
scripts/validate-julia.sh
printf 'All Trees & Surfaces validation passed\n'
