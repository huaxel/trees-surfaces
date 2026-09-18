#!/usr/bin/env python3
"""Generate a small weight-sensitivity report for the tree-point signal."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUTPUT = DATA / "tree-signal-sensitivity.json"
CSV_OUTPUT = DATA / "tree-signal-balanced-screen.csv"


def normalize(value: float, lower: float, upper: float) -> float:
    return 50.0 if upper == lower else (value - lower) / (upper - lower) * 100


def main() -> None:
    heat = json.loads((DATA / "brussels-tree-heat-sample.json").read_text())["records"]
    joined = json.loads((DATA / "brussels-tree-bike-nearest.json").read_text())["records"]
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
    print(f"wrote {OUTPUT.relative_to(ROOT)} and {CSV_OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
