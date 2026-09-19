#!/usr/bin/env python3
"""Generate a small weight-sensitivity report for the tree-point signal."""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUTPUT = DATA / "tree-signal-sensitivity.json"
CSV_OUTPUT = DATA / "tree-signal-balanced-screen.csv"
MARKDOWN_OUTPUT = DATA / "tree-signal-analysis.md"


def normalize(value: float, lower: float, upper: float) -> float:
    return 50.0 if upper == lower else (value - lower) / (upper - lower) * 100


def main() -> None:
    managed_payload = json.loads((DATA / "brussels-trees-sample.json").read_text())
    heat = json.loads((DATA / "brussels-tree-heat-sample.json").read_text())["records"]
    joined = json.loads((DATA / "brussels-tree-bike-nearest.json").read_text())["records"]
    flow_payload = json.loads((DATA / "brussels-tree-counter-flow.json").read_text())
    history_payload = json.loads((DATA / "brussels-bike-history-CB2105-2024-01.json").read_text())
    history = history_payload["records"]
    heat_by_id = {record["id"]: float(record["heat_pixel"]) for record in heat}
    points = [record for record in joined if record["id"] in heat_by_id]
    distances = [float(record["nearest_counter_distance_m"]) for record in points]
    heats = [heat_by_id[record["id"]] for record in points]
    min_distance, max_distance = min(distances), max(distances)
    min_heat, max_heat = min(heats), max(heats)

    rows = []
    for record in points:
        distance = float(record["nearest_counter_distance_m"])
        heat_value = heat_by_id[record["id"]]
        rows.append({
            "id": record["id"],
            "street": record.get("street"),
            "district": record.get("district") or "Unknown",
            "heat_pixel": heat_value,
            "nearest_counter": record["nearest_counter"],
            "distance_m": distance,
            "heat_score": round(normalize(heat_value, min_heat, max_heat), 3),
            "proximity_score": round(100 - normalize(distance, min_distance, max_distance), 3),
        })

    scenarios = {
        "heat_only": {"heat": 1.0, "proximity": 0.0},
        "balanced": {"heat": 0.6, "proximity": 0.4},
        "proximity_only": {"heat": 0.0, "proximity": 1.0},
    }
    ranked = {}
    for name, weights in scenarios.items():
        ordered = sorted(
            rows,
            key=lambda row: row["heat_score"] * weights["heat"] + row["proximity_score"] * weights["proximity"],
            reverse=True,
        )
        ranked[name] = [
            {**row, "signal": round(row["heat_score"] * weights["heat"] + row["proximity_score"] * weights["proximity"], 3)}
            for row in ordered
        ]

    balanced_ids = {row["id"] for row in ranked["balanced"][:10]}
    report = {
        "method": "min-max normalization within the 100-record feasibility sample",
        "record_count": len(rows),
        "heat_range": [min_heat, max_heat],
        "distance_range_m": [min_distance, max_distance],
        "balanced_screening": ranked["balanced"],
        "scenarios": [
            {
                "name": name,
                "weights": weights,
                "top_10_overlap_with_balanced": len({row["id"] for row in ranked[name][:10]} & balanced_ids),
                "top_records": ranked[name][:10],
            }
            for name, weights in scenarios.items()
        ],
        "caveat": "Rankings are exploratory and depend on sample-relative normalization; proximity is not a mobility measure.",
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    with CSV_OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["rank", "id", "street", "district", "heat_pixel", "nearest_counter", "distance_m", "heat_score", "proximity_score", "signal"], lineterminator="\n")
        writer.writeheader()
        for rank, row in enumerate(ranked["balanced"], start=1):
            writer.writerow({"rank": rank, **{field: row[field] for field in writer.fieldnames if field != "rank"}})

    heat_scores = [row["heat_score"] for row in rows]
    proximity_scores = [row["proximity_score"] for row in rows]
    heat_q3 = statistics.quantiles(heat_scores, n=4, method="inclusive")[2]
    proximity_q3 = statistics.quantiles(proximity_scores, n=4, method="inclusive")[2]
    high_high = [row for row in ranked["balanced"] if row["heat_score"] >= heat_q3 and row["proximity_score"] >= proximity_q3]
    high_high_ids = {row["id"] for row in high_high}
    district_groups = {}
    for row in rows:
        district_groups.setdefault(row["district"], []).append(row)
    district_summary = []
    for district, district_rows in district_groups.items():
        district_summary.append({
            "district": district,
            "count": len(district_rows),
            "mean_heat": statistics.mean(row["heat_pixel"] for row in district_rows),
            "median_distance": statistics.median(row["distance_m"] for row in district_rows),
            "high_high_count": sum(row["id"] in high_high_ids for row in district_rows),
        })
    district_summary.sort(key=lambda row: (-row["high_high_count"], -row["count"], row["district"]))
    lines = [
        "# Tree signal descriptive analysis",
        "",
        "This report answers the working screening question using the committed 100-record feasibility sample.",
        "",
        "> Which observed tree areas combine relatively high heat-stress values with proximity to bicycle counters, and therefore merit more detailed field or mobility analysis?",
        "",
        "## Heat data and normalization",
        "",
        "- The heat input is the regional urban-heat-island model published by Brussels Environment: mean 24-hour Wet Bulb Globe Temperature for one representative hot day (2016-08-24). The public WMS exposes this single scenario layer; no multi-date or seasonal open layer exists for the region.",
        "- Normalization is min-max within the committed 100-record sample (0-100), which makes scores sample-relative; rankings shift with the weights and with a different sample.",
        "- Missing data: all 100 joined points have non-NoData WBGT pixels, so there is no heat missingness to impute in this snapshot.",
        "- Multi-date alternatives (ERA5 2 m temperature, satellite land-surface temperature) are documented as future options and are out of scope for this feasibility sample.",
        "",
        "## Traceability",
        "",
        "Every displayed point can be traced to its source record and join method:",
        "- Source record: the managed-tree register entry, reachable by id, e.g. `https://bruxellesdata.opendatasoft.com/api/explore/v2.1/catalog/datasets/arbres-bomen-vbx-be-bm/records?where=id%3D%27vbx_56544%27`.",
        "- Heat join: WBGT raster pixel value extracted at the tree's coordinates from the regional layer (see `join_heat.py`).",
        "- Mobility join: great-circle distance to the nearest bicycle counter (see the committed `brussels-tree-bike-nearest.json`); measured-flow context for the nearest counter is in `brussels-tree-counter-flow.json`.",
        "- Ranking: signal = heat_score × weight + proximity_score × weight, min-max scores, weights exposed in the interface.",
        "",
        "## Sample summary",
        "",
        f"- Records analyzed: {len(rows)} of {managed_payload['source']:,} managed-tree records reported by the source ({len(rows) / managed_payload['source'] * 100:.2f}% of the reported register)",
        "- Sampling note: the committed records are a feasibility snapshot, not a probability sample or city-wide estimate",
        f"- WBGT pixel: min {min(heats):.0f}, median {statistics.median(heats):.1f}, max {max(heats):.0f}",
        f"- Counter distance: min {min(distances):.1f} m, median {statistics.median(distances):.1f} m, max {max(distances):.1f} m",
        f"- Counter history context: {len(history)} fifteen-minute observations from {history_payload['start_date']} to {history_payload['end_date']}; mean count {statistics.mean(record['count'] for record in history):.1f}, maximum {max(record['count'] for record in history)}",
        f"- High-heat/high-proximity quadrant: {len(high_high)} points at or above the sample's third quartile on both normalized components",
        "",
        "## District context",
        "",
        "District counts describe this 100-record sample only; they are not district prevalence estimates.",
        "",
        "| District | Points | Mean WBGT pixel | Median counter distance | High-high points |",
        "|---|---:|---:|---:|---:|",
    ]
    for summary in district_summary:
        lines.append(f"| {summary['district']} | {summary['count']} | {summary['mean_heat']:.1f} | {summary['median_distance']:.1f} m | {summary['high_high_count']} |")
    lines.extend([
        "",
        "## Balanced screen",
        "",
        "The balanced screen uses heat weight 0.6 and proximity weight 0.4. The table shows the ten highest exploratory signals.",
        "",
        "| Rank | ID | Street | WBGT pixel | Counter distance | Signal |",
        "|---:|---|---|---:|---:|---:|",
    ])
    for rank, row in enumerate(ranked["balanced"][:10], start=1):
        lines.append(f"| {rank} | {row['id']} | {row.get('street') or 'Unnamed street'} | {row['heat_pixel']:.0f} | {row['distance_m']:.1f} m | {row['signal']:.1f} |")
    lines.extend([
        "",
        "## Mobility context",
        "",
        f"A measured-flow context now supplements nearest-counter distance: {flow_payload['trees_with_measured_flow']} of {flow_payload['record_count']} sampled trees have their nearest counter covered by the same {flow_payload['period']} week of 15-minute counts. The three remaining trees are nearest to counters without committed history.",
        "",
        "| Counter | Mean 15-min count | Day-mean range |",
        "|---|---:|---:|",
    ])
    for feature, meta in sorted(flow_payload["counter_flow"].items(), key=lambda item: -item[1]["mean_all"]):
        lines.append(f"| {feature} | {meta['mean_all']:.1f} | {meta['min_day_mean']:.1f} - {meta['max_day_mean']:.1f} |")
    lines.extend([
        "",
        "Flow is measured at the nearest counter, not at the tree, and covers a single winter week; it is contextual mobility evidence, not a seasonal or street-level estimate. See `brussels-tree-counter-flow.json` for per-tree values.",
        "",
        "## Interpretation boundary",
        "",
        "- The WBGT layer represents one representative hot day in 2016.",
        "- Counter distance is a spatial context proxy, not bicycle flow, pedestrian use or street occupancy.",
        "- Min–max normalization is sample-relative; rankings change with the weights and sample.",
        "- These points are candidates for follow-up analysis, not planting recommendations or causal findings.",
        "",
    ])
    MARKDOWN_OUTPUT.write_text("\n".join(lines))
    print(f"wrote {OUTPUT.relative_to(ROOT)}, {CSV_OUTPUT.relative_to(ROOT)} and {MARKDOWN_OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
