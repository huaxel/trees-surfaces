#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

CHECK_CLEAN=false
if [[ ${1:-} == "--check-clean" ]]; then
  CHECK_CLEAN=true
  shift
fi
if (($#)); then
  printf 'usage: %s [--check-clean]\n' "$0" >&2
  exit 2
fi

python3 prototypes/trees-surfaces/analyze_signal.py
python3 prototypes/trees-surfaces/export_stakeholder_review.py
python3 prototypes/three-ages/generate_structural_crops.py
python3 prototypes/three-ages/export_pilot.py
python3 prototypes/validate_snapshots.py
python3 prototypes/test_review_workflows.py
python3 -m compileall -q prototypes
node prototypes/smoke_ui.js
python3 - <<'PY'
import json
import stat
from pathlib import Path

for path in Path("prototypes").rglob("*.json"):
    with path.open(encoding="utf-8") as handle:
        json.load(
            handle,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"{path}: non-standard JSON constant {value}")
            ),
        )
print("strict JSON parsing passed")

private = [
    path
    for path in Path("prototypes").rglob("*")
    if path.is_file()
    and "__pycache__" not in path.parts
    and path.suffix != ".pyc"
    and stat.S_IMODE(path.stat().st_mode) & 0o044 != 0o044
]
if private:
    raise SystemExit(f"prototype artifacts must be group/other-readable: {private}")
private_directories = [
    path
    for path in Path("prototypes").rglob("*")
    if path.is_dir()
    and "__pycache__" not in path.parts
    and stat.S_IMODE(path.stat().st_mode) & 0o055 != 0o055
]
if private_directories:
    raise SystemExit(f"prototype directories must be group/other-readable and traversable: {private_directories}")
print("prototype artifact permissions passed")
PY

git diff --check
if [[ $CHECK_CLEAN == true ]]; then
  status=$(git status --porcelain)
  if [[ -n $status ]]; then
    printf 'validation changed tracked or generated files:\n%s\n' "$status" >&2
    exit 1
  fi
fi
printf 'prototype validation passed\n'
