#!/usr/bin/env python3
"""Validate the small committed snapshots used by both prototypes."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read_json(relative: str) -> dict:
    path = ROOT / relative
    return json.loads(path.read_text())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"validation failed: {message}")


def main() -> None:
    trees = read_json("trees-surfaces/data/brussels-trees-sample.json")
    heat = read_json("trees-surfaces/data/brussels-tree-heat-sample.json")
    mobility = read_json("trees-surfaces/data/brussels-tree-bike-nearest.json")
    history = read_json("trees-surfaces/data/brussels-bike-history-CB2105-2024-01.json")
    inventory = read_json("trees-surfaces/data/source-inventory.json")
    sensitivity = read_json("trees-surfaces/data/tree-signal-sensitivity.json")
    balanced_csv = (ROOT / "trees-surfaces/data/tree-signal-balanced-screen.csv").read_text().splitlines()
    buildings = read_json("three-ages/data/grand-place-buildings.json")
    pilot = read_json("three-ages/data/three-ages-pilot.json")
    pilot_csv = (ROOT / "three-ages/data/three-ages-pilot-export.csv").read_text().splitlines()

    tree_ids = {record["id"] for record in trees["records"]}
    heat_ids = {record["id"] for record in heat["records"]}
    mobility_ids = {record["id"] for record in mobility["records"]}
    require(len(trees["records"]) == 100, "expected 100 managed-tree records")
    require(heat_ids == tree_ids, "heat join IDs do not match tree snapshot IDs")
    require(mobility_ids == tree_ids, "mobility join IDs do not match tree snapshot IDs")
    require(len(history["records"]) == 672, "expected 672 counter observations")
    require(all(0 < record["heat_pixel"] for record in heat["records"]), "heat join contains NoData values")
    require(all(record["nearest_counter_distance_m"] >= 0 for record in mobility["records"]), "negative counter distance")
    require(all(inventory.get(key, {}).get("records", "").startswith("https://") for key in ("managed_trees", "remarkable_trees")), "tree source inventory is missing record URLs")
    require(inventory.get("heat", {}).get("download", "").startswith("https://"), "heat source inventory is missing download URL")
    require(inventory.get("mobility", {}).get("devices", "").startswith("https://"), "mobility source inventory is missing device URL")
    require(sensitivity.get("record_count") == 100, "sensitivity report has unexpected record count")
    require(len(sensitivity.get("balanced_screening", [])) == 100, "balanced screening export is incomplete")
    require(len(balanced_csv) == 101 and balanced_csv[0].startswith("rank,id,street"), "balanced CSV export is incomplete")
    require({scenario["name"] for scenario in sensitivity.get("scenarios", [])} == {"heat_only", "balanced", "proximity_only"}, "sensitivity scenarios are incomplete")
    require(all(len(scenario["top_records"]) == 10 for scenario in sensitivity["scenarios"]), "sensitivity report must contain ten top records per scenario")

    building_ids = {str(record["id"]) for record in buildings["records"]}
    pilot_ids = {record["source_id"] for record in pilot["records"]}
    require(len(buildings["records"]) == 34, "expected 34 Grand Place records")
    require(buildings.get("dataset_url", "").startswith("https://"), "building snapshot is missing dataset URL")
    require(len(pilot["records"]) == 6, "expected six curated pilot records")
    require(pilot.get("review_status") == "source-grounded pilot", "pilot review status is missing")
    require(pilot_ids <= building_ids, "pilot contains an unknown building source ID")
    required_pilot_fields = {"source_id", "selection_reason", "register", "facade", "structure", "image_evidence", "next_step"}
    require(all(required_pilot_fields <= set(record) for record in pilot["records"]), "pilot record schema is incomplete")
    require(all(all(field in record[claim] for field in ("status", "value", "note")) for record in pilot["records"] for claim in ("register", "facade", "structure")), "pilot claim schema is incomplete")
    require(all(not record["image_evidence"] for record in pilot["records"]), "pilot image evidence should remain explicitly empty")
    require(len(pilot_csv) == 7 and pilot_csv[0].startswith("source_id,name,address"), "Three Ages pilot CSV export is incomplete")

    print("snapshot validation passed")
    print(f"tree points: {len(tree_ids)}; heat joins: {len(heat_ids)}; mobility joins: {len(mobility_ids)}")
    print(f"counter observations: {len(history['records'])}; building records: {len(building_ids)}; pilot cases: {len(pilot_ids)}")


if __name__ == "__main__":
    main()
