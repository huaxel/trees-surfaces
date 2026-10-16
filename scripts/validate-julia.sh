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
julia --project=. -e 'using Pkg; Pkg.instantiate()'
julia --project=. -e 'using Pkg; Pkg.test()'
if [[ "${JULIA_REFRESH_CHECK:-0}" == "1" ]]; then
  julia --project=. bin/refresh_open_data.jl --check
fi
julia --project=. bin/validate_snapshots.jl >/dev/null
julia --project=. bin/validate_projection.jl >/dev/null
summary=$(julia --project=. bin/analyze.jl)
python3 -c 'import json, sys; p = json.loads(sys.argv[1]); assert p["record_count"] == 100; assert p["scenarios"]["heat_only"]["top_10_overlap_with_balanced"] == 9; assert p["scenarios"]["proximity_only"]["top_10_overlap_with_balanced"] == 1' "$summary"
julia --project=. bin/generate_signal.jl "$generated" >/dev/null
julia --project=. bin/generate_counter_flow.jl "$generated" >/dev/null
julia --project=. bin/generate_tree_mobility_join.jl "$generated" >/dev/null
julia --project=. bin/generate_accident_context.jl "$generated" >/dev/null
python3 - "$generated" <<'PY'
import csv
import json
import pathlib
import sys

def committed(name):
    return json.loads((pathlib.Path("data") / name).read_text())

def generated(out, name):
    return json.loads((pathlib.Path(out) / name).read_text())

out = sys.argv[1]
# Every derived JSON artifact is a pure function of the committed snapshots, so the generator
# must reproduce the committed artifacts exactly (semantic equality; committed JSON is pretty
# printed while the generator emits compact JSON).
for name in ("tree-signal-sensitivity.json", "brussels-tree-bike-nearest.json", "brussels-tree-counter-flow.json", "brussels-counter-accident-context.json"):
    assert generated(out, name) == committed(name), f"generated {name} differs from the committed artifact"

sensitivity = committed("tree-signal-sensitivity.json")
assert sensitivity["record_count"] == 100
assert sensitivity["weight_sensitivity"]["heat_only_top_10_overlap"] == 9
assert sensitivity["weight_sensitivity"]["proximity_only_top_10_overlap"] == 1
with (pathlib.Path(out) / "tree-signal-balanced-screen.csv").open(newline="") as handle:
    assert sum(1 for _ in csv.DictReader(handle)) == 100
assert (pathlib.Path(out) / "tree-signal-analysis.md").read_text().startswith("# Tree signal descriptive analysis")
assert committed("brussels-tree-counter-flow.json")["trees_with_measured_flow"] == 97
season = committed("brussels-heat-season-sample.json")
assert season["model"] == "era5"
assert "models=era5" in season["grid_probe_url"]
assert season["season"]["window_start_year"] == 2015
assert season["season"]["window_end_year"] == 2024
assert season["season"]["season_days"] == 920
assert len(season["cells"]) == 4
assert len(season["records"]) == 100
assert season["region_summary"]["reference_date_season_percentile_min"] > 90
PY

# The Markdown report and the ranking CSV are fully derived from committed snapshots, so the
# generator must reproduce the committed artifacts byte for byte.
for artifact in tree-signal-analysis.md tree-signal-balanced-screen.csv; do
  if ! diff -q "$generated/$artifact" "data/$artifact" >/dev/null; then
    echo "Generated $artifact does not match the committed artifact:" >&2
    diff "$generated/$artifact" "data/$artifact" >&2 || true
    exit 1
  fi
done

cp data/tree-stakeholder-proposal.json "$review_dir/"
cp "$generated/tree-signal-sensitivity.json" "$review_dir/"
julia --project=. bin/generate_stakeholder_review.jl "$review_dir" >/dev/null
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
julia --project=. bin/generate_stakeholder_review.jl "$review_dir" >/dev/null
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
if julia --project=. bin/generate_stakeholder_review.jl "$review_dir" >/dev/null 2>&1; then
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

julia --project=. bin/run.jl "$port" >"$log" 2>&1 &
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
curl -fsS "http://127.0.0.1:${port}/api/screen?heat=0&proximity=0" >"$response"
python3 - "$response" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

assert payload["heatWeight"] == payload["proximityWeight"] == 0.5
assert len({site["signal"] for site in payload["sites"]}) > 1
print("Julia zero-sum weight HTTP smoke test passed")
PY
curl -fsS "http://127.0.0.1:${port}/api/screen?heat=NaN&proximity=Inf" >"$response"
python3 - "$response" <<'PY'
import json
import math
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

assert payload["heatWeight"] == 0.6
assert payload["proximityWeight"] == 0.4
assert all(math.isfinite(site["signal"]) for site in payload["sites"])
print("Julia malformed-weight HTTP smoke test passed")
PY
curl -fsS "http://127.0.0.1:${port}/api/screen?heat=1e308&proximity=1e308" >"$response"
python3 - "$response" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

assert payload["heatWeight"] == payload["proximityWeight"] == 0.5
assert len({site["signal"] for site in payload["sites"]}) > 1
print("Julia extreme-weight HTTP smoke test passed")
PY

page=$(curl -fsS "http://127.0.0.1:${port}/")
printf '%s' "$page" | grep -F 'Julia-served exploratory view' >/dev/null
printf '%s' "$page" | grep -F 'Open source tree record' >/dev/null
curl -fsS "http://127.0.0.1:${port}/stakeholder-review.csv" | grep -F 'review_status' >/dev/null
printf 'Julia validation passed\n'
