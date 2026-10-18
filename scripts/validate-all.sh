#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

scripts/validate-canopy.sh
scripts/validate-imagery.sh
scripts/validate-julia.sh
scripts/validate-docs.sh
printf 'Trees & Surfaces canopy, imagery, Julia and documentation validation passed\n'
