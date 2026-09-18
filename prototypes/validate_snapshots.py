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
    buildings = read_json("three-ages/data/grand-place-buildings.json")
    pilot = read_json("three-ages/data/three-ages-pilot.json")

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

    building_ids = {str(record["id"]) for record in buildings["records"]}
    pilot_ids = {record["source_id"] for record in pilot["records"]}
    require(len(buildings["records"]) == 34, "expected 34 Grand Place records")
    require(buildings.get("dataset_url", "").startswith("https://"), "building snapshot is missing dataset URL")
    require(len(pilot["records"]) == 6, "expected six curated pilot records")
    require(pilot_ids <= building_ids, "pilot contains an unknown building source ID")
    require(all(not record["image_evidence"] for record in pilot["records"]), "pilot image evidence should remain explicitly empty")

    print("snapshot validation passed")
    print(f"tree points: {len(tree_ids)}; heat joins: {len(heat_ids)}; mobility joins: {len(mobility_ids)}")
    print(f"counter observations: {len(history['records'])}; building records: {len(building_ids)}; pilot cases: {len(pilot_ids)}")


if __name__ == "__main__":
    main()
