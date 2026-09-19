#!/usr/bin/env python3
"""Join measured bicycle-counter flow to the sampled trees.

Builds a mobility-context snapshot: for every tree in the committed sample,
record the nearest counter, the distance, and that counter's measured mean
flow over the same one-week period (1-7 January 2024, 15-minute counts).
This replaces bare distance with a measured-flow context where history
exists, without re-ranking the exploratory signal.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUTPUT = DATA / "brussels-tree-counter-flow.json"

COUNTERS = ("CB1101", "CB1142", "CJM90", "CB1143", "CB2105")


def load_history_payload(feature: str) -> dict:
    return json.loads((DATA / f"brussels-bike-history-{feature}-2024-01.json").read_text())


def load_history(feature: str) -> list:
    return load_history_payload(feature)["records"]


def main() -> None:
    joined = json.loads((DATA / "brussels-tree-bike-nearest.json").read_text())["records"]
    flow = {feature: statistics.mean(record["count"] for record in load_history(feature)) for feature in COUNTERS}
    weekday = {}
    for feature in COUNTERS:
        records = load_history(feature)
        by_day = {}
        for record in records:
            day = record["count_date"][:10]
            by_day.setdefault(day, []).append(record["count"])
        means = {day: statistics.mean(counts) for day, counts in by_day.items()}
        weekday[feature] = {
            "mean_all": flow[feature],
            "days": len(by_day),
            "min_day_mean": min(means.values()),
            "max_day_mean": max(means.values()),
        }

    source_terms = set()
    for feature in COUNTERS:
        history_payload = load_history_payload(feature)
        source_terms.add((
            history_payload.get("dataset_metadata_url"),
            history_payload.get("source_licence"),
            history_payload.get("source_credit"),
        ))
    if len(source_terms) != 1:
        raise RuntimeError(f"counter history provenance differs across snapshots: {source_terms}")
    metadata_url, source_licence, source_credit = source_terms.pop()

    records = []
    covered = 0
    for row in joined:
        counter = row["nearest_counter"]
        distance = float(row["nearest_counter_distance_m"])
        entry = {
            "id": row["id"],
            "street": row.get("street"),
            "nearest_counter": counter,
            "distance_m": distance,
            "counter_flow_mean": round(flow[counter], 3) if counter in flow else None,
            "has_measured_flow": counter in flow,
        }
        records.append(entry)
        covered += entry["has_measured_flow"]

    payload = {
        "source": "Brussels Mobility bicycle counter API (five committed counter snapshots sharing one 7-day period)",
        "source_metadata_url": metadata_url,
        "source_licence": source_licence,
        "source_credit": source_credit,
        "period": "2024/01/01 - 2024/01/07",
        "record_count": len(records),
        "trees_with_measured_flow": covered,
        "counter_flow": {feature: {k: round(v, 3) if isinstance(v, float) else v for k, v in meta.items()} for feature, meta in weekday.items()},
        "caveat": "Flow is measured at the nearest counter, not at the tree; the period is a single winter week, so it is not a seasonal mobility estimate.",
        "records": records,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    OUTPUT.chmod(0o644)
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    print(f"trees with measured flow at nearest counter: {covered}/{len(records)}")
    print(f"counter mean flows: { {k: v['mean_all'] for k, v in weekday.items()} }")


if __name__ == "__main__":
    main()