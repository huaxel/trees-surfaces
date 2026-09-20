#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

if ! command -v julia >/dev/null 2>&1; then
  printf 'Julia is required for this validation script\n' >&2
  exit 2
fi

generated=$(mktemp -d)
review_dir=$(mktemp -d)
julia --project=julia -e 'using Pkg; Pkg.instantiate()'
julia --project=julia -e 'using Pkg; Pkg.test()'
if [[ "${JULIA_REFRESH_CHECK:-0}" == "1" ]]; then
  julia --project=julia julia/refresh_open_data.jl --check
fi
julia --project=julia julia/validate_snapshots.jl >/dev/null
julia --project=julia julia/validate_projection.jl >/dev/null
summary=$(julia --project=julia julia/analyze.jl)
python3 -c 'import json, sys; p = json.loads(sys.argv[1]); assert p["record_count"] == 100; assert p["scenarios"]["heat_only"]["top_10_overlap_with_balanced"] == 9; assert p["scenarios"]["proximity_only"]["top_10_overlap_with_balanced"] == 1' "$summary"
julia --project=julia julia/generate_signal.jl "$generated" >/dev/null
julia --project=julia julia/generate_counter_flow.jl "$generated" >/dev/null
julia --project=julia julia/generate_tree_mobility_join.jl "$generated" >/dev/null
python3 - "$generated" <<'PY'
import csv
import json
import pathlib
import sys

out = pathlib.Path(sys.argv[1])
generated = json.loads((out / "tree-signal-sensitivity.json").read_text())
canonical = json.loads(pathlib.Path("prototypes/trees-surfaces/data/tree-signal-sensitivity.json").read_text())
assert generated["record_count"] == 100
assert [row["id"] for row in generated["balanced_screening"][:10]] == [row["id"] for row in canonical["balanced_screening"][:10]]
assert generated["weight_sensitivity"]["heat_only_top_10_overlap"] == 9
assert generated["weight_sensitivity"]["proximity_only_top_10_overlap"] == 1
with (out / "tree-signal-balanced-screen.csv").open(newline="") as handle:
    assert sum(1 for _ in csv.DictReader(handle)) == 100
assert (out / "tree-signal-analysis.md").read_text().startswith("# Tree signal descriptive analysis")
flow = json.loads((out / "brussels-tree-counter-flow.json").read_text())
canonical_flow = json.loads(pathlib.Path("prototypes/trees-surfaces/data/brussels-tree-counter-flow.json").read_text())
assert flow["record_count"] == canonical_flow["record_count"] == 100
assert flow["trees_with_measured_flow"] == canonical_flow["trees_with_measured_flow"] == 97
assert flow["counter_flow"].keys() == canonical_flow["counter_flow"].keys()
join = json.loads((out / "brussels-tree-bike-nearest.json").read_text())
canonical_join = json.loads(pathlib.Path("prototypes/trees-surfaces/data/brussels-tree-bike-nearest.json").read_text())
assert len(join["records"]) == len(canonical_join["records"]) == 100
for actual, expected in zip(join["records"], canonical_join["records"]):
    assert actual["id"] == expected["id"]
    assert actual["nearest_counter"] == expected["nearest_counter"]
    assert actual["nearest_counter_distance_m"] == expected["nearest_counter_distance_m"]
PY

cp prototypes/trees-surfaces/data/tree-stakeholder-proposal.json "$review_dir/"
cp "$generated/tree-signal-sensitivity.json" "$review_dir/"
julia --project=julia julia/generate_stakeholder_review.jl "$review_dir" >/dev/null
python3 - "$review_dir/tree-stakeholder-review.csv" <<'PY'
import csv
import sys

path = sys.argv[1]
with open(path, newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
rows[0].update({
    "review_status": "needs more evidence",
    "reviewer_name": "Julia smoke test",
    "reviewer_role": "validator",
    "reviewed_at": "2025-01-01T00:00:00",
    "false_positive_preference": "prefer recall",
    "evidence_threshold": "manual review",
    "review_notes": "preservation test",
})
with open(path, "w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
PY
julia --project=julia julia/generate_stakeholder_review.jl "$review_dir" >/dev/null
python3 - "$review_dir/tree-stakeholder-reviews.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
assert payload["record_count"] == 1
assert payload["records"][0]["review_status"] == "needs more evidence"
PY
python3 - "$review_dir/tree-signal-sensitivity.json" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    payload = json.load(handle)
payload["data_completeness"]["analyzed_records"] = 99
with open(path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle)
PY
if julia --project=julia julia/generate_stakeholder_review.jl "$review_dir" >/dev/null 2>&1; then
  echo "Julia review stale-evidence refusal failed" >&2
  exit 1
fi

port=${JULIA_UI_PORT:-8093}
log=$(mktemp)
response=$(mktemp)
pid=''
cleanup() {
  if [[ -n "$pid" ]]; then
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  fi
  rm -f "$log" "$response"
  rm -rf "$generated" "$review_dir"
}
trap cleanup EXIT

julia --project=julia julia/run.jl "$port" >"$log" 2>&1 &
pid=$!
ready=false
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "$ready" != true ]]; then
  cat "$log" >&2
  exit 1
fi

curl -fsS "http://127.0.0.1:${port}/api/screen?heat=0&proximity=100" >"$response"
python3 - "$response" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

assert payload["heatWeight"] == 0
assert payload["proximityWeight"] == 1
assert payload["sites"][0]["id"] == "vbx_56876"
print("Julia HTTP smoke test passed")
PY

page=$(curl -fsS "http://127.0.0.1:${port}/")
printf '%s' "$page" | grep -F 'Julia-served exploratory view' >/dev/null
printf '%s' "$page" | grep -F 'Open source tree record' >/dev/null
curl -fsS "http://127.0.0.1:${port}/stakeholder-review.csv" | grep -F 'review_status' >/dev/null
printf 'Julia validation passed\n'
