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
    heat = json.loads((DATA / "brussels-tree-heat-sample.json").read_text())["records"]
    joined = json.loads((DATA / "brussels-tree-bike-nearest.json").read_text())["records"]
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
        writer = csv.DictWriter(handle, fieldnames=["rank", "id", "street", "heat_pixel", "nearest_counter", "distance_m", "heat_score", "proximity_score", "signal"], lineterminator="\n")
        writer.writeheader()
        for rank, row in enumerate(ranked["balanced"], start=1):
            writer.writerow({"rank": rank, **{field: row[field] for field in writer.fieldnames if field != "rank"}})

    heat_scores = [row["heat_score"] for row in rows]
    proximity_scores = [row["proximity_score"] for row in rows]
    heat_q3 = statistics.quantiles(heat_scores, n=4, method="inclusive")[2]
    proximity_q3 = statistics.quantiles(proximity_scores, n=4, method="inclusive")[2]
    high_high = [row for row in ranked["balanced"] if row["heat_score"] >= heat_q3 and row["proximity_score"] >= proximity_q3]
    lines = [
        "# Tree signal descriptive analysis",
        "",
        "This report answers the working screening question using the committed 100-record feasibility sample.",
        "",
        "> Which observed tree areas combine relatively high heat-stress values with proximity to bicycle counters, and therefore merit more detailed field or mobility analysis?",
        "",
        "## Sample summary",
        "",
        f"- Records analyzed: {len(rows)}",
        f"- WBGT pixel: min {min(heats):.0f}, median {statistics.median(heats):.1f}, max {max(heats):.0f}",
        f"- Counter distance: min {min(distances):.1f} m, median {statistics.median(distances):.1f} m, max {max(distances):.1f} m",
        f"- Counter history context: {len(history)} fifteen-minute observations from {history_payload['start_date']} to {history_payload['end_date']}; mean count {statistics.mean(record['count'] for record in history):.1f}, maximum {max(record['count'] for record in history)}",
        f"- High-heat/high-proximity quadrant: {len(high_high)} points at or above the sample's third quartile on both normalized components",
        "",
        "## Balanced screen",
        "",
        "The balanced screen uses heat weight 0.6 and proximity weight 0.4. The table shows the ten highest exploratory signals.",
        "",
        "| Rank | ID | Street | WBGT pixel | Counter distance | Signal |",
        "|---:|---|---|---:|---:|---:|",
    ]
    for rank, row in enumerate(ranked["balanced"][:10], start=1):
        lines.append(f"| {rank} | {row['id']} | {row.get('street') or 'Unnamed street'} | {row['heat_pixel']:.0f} | {row['distance_m']:.1f} m | {row['signal']:.1f} |")
    lines.extend([
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
