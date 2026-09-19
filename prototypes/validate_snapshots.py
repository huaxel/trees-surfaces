#!/usr/bin/env python3
"""Validate the small committed snapshots used by both prototypes."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read_json(relative: str) -> dict:
    path = ROOT / relative
    return json.loads(path.read_text())


def _png_has_content(path: Path) -> bool:
    """Return True when the PNG carries non-trivial imagery, not a blank tile.

    GeoServer 1.3.0 requests for the BruCiel 1996 layer return fully
    transparent, single-colour tiles; 1.1.1 requests return real imagery.
    The guard is intentionally dependency-free: parse the IDAT with zlib,
    then require spread in the decoded grey values.
    """
    import struct
    import zlib

    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    pos, idat = 8, bytearray()
    width = height = None
    while pos < len(data):
        length, typ = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + length]
        if typ == b"IHDR":
            width, height, _depth, _ctype = struct.unpack(">IIBB", chunk[:10])
        elif typ == b"IDAT":
            idat += chunk
        elif typ == b"IEND":
            break
        pos += 12 + length
    if not width or not height or not idat:
        return False
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error:
        return False
    bpp = 4 if data[25] == 6 else 3  # colortype byte within IHDR payload
    stride = width * bpp
    if len(raw) < (height * (stride + 1)):
        return False
    # unfiltered scanlines are enough for a blank-vs-content spread check
    pixels = bytearray()
    off = 0
    for _ in range(height):
        filter_type = raw[off]
        off += 1
        line = raw[off:off + stride]
        off += stride
        if filter_type != 0:
            return True  # filtered data implies real image processing
        pixels += line[::bpp]
    if not pixels:
        return False
    seen = set(pixels)
    return len(seen) > 50 and (max(seen) - min(seen)) > 40


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"validation failed: {message}")


def main() -> None:
    trees = read_json("trees-surfaces/data/brussels-trees-sample.json")
    remarkable = read_json("trees-surfaces/data/brussels-remarkable-trees-sample.json")
    heat = read_json("trees-surfaces/data/brussels-tree-heat-sample.json")
    mobility = read_json("trees-surfaces/data/brussels-tree-bike-nearest.json")
    history = read_json("trees-surfaces/data/brussels-bike-history-CB2105-2024-01.json")
    inventory = read_json("trees-surfaces/data/source-inventory.json")
    sensitivity = read_json("trees-surfaces/data/tree-signal-sensitivity.json")
    balanced_csv = (ROOT / "trees-surfaces/data/tree-signal-balanced-screen.csv").read_text().splitlines()
    analysis_report = (ROOT / "trees-surfaces/data/tree-signal-analysis.md").read_text()
    buildings = read_json("three-ages/data/grand-place-buildings.json")
    pilot = read_json("three-ages/data/three-ages-pilot.json")
    three_ages_inventory = read_json("three-ages/data/source-inventory.json")
    preview_path = ROOT / "three-ages/data/bruciel-1996-grand-place.png"
    preview_2022_path = ROOT / "three-ages/data/urbisgrid-2022-grand-place.png"
    pilot_csv = (ROOT / "three-ages/data/three-ages-pilot-export.csv").read_text().splitlines()

    tree_ids = {record["id"] for record in trees["records"]}
    heat_ids = {record["id"] for record in heat["records"]}
    mobility_ids = {record["id"] for record in mobility["records"]}
    require(len(trees["records"]) == 100, "expected 100 managed-tree records")
    require(trees.get("sampling", "").startswith("first 100"), "managed-tree sampling metadata is missing")
    require(len(remarkable["records"]) == 100 and remarkable.get("sampling", "").startswith("first 100"), "remarkable-tree sampling metadata is missing")
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
    require(analysis_report.startswith("# Tree signal descriptive analysis") and "High-heat/high-proximity quadrant" in analysis_report, "descriptive analysis report is incomplete")
    require({scenario["name"] for scenario in sensitivity.get("scenarios", [])} == {"heat_only", "balanced", "proximity_only"}, "sensitivity scenarios are incomplete")
    require(all(len(scenario["top_records"]) == 10 for scenario in sensitivity["scenarios"]), "sensitivity report must contain ten top records per scenario")

    building_ids = {str(record["id"]) for record in buildings["records"]}
    pilot_ids = {record["source_id"] for record in pilot["records"]}
    require(len(buildings["records"]) == 34, "expected 34 Grand Place records")
    require(buildings.get("dataset_url", "").startswith("https://"), "building snapshot is missing dataset URL")
    require(len(pilot["records"]) == 6, "expected six curated pilot records")
    require(pilot.get("review_status") == "source-grounded pilot", "pilot review status is missing")
    require({"bruciel_app", "grand_place_dataset", "bruciel_1996", "bruciel_1944", "brussels_archives", "urbisgrid_2022"} <= set(three_ages_inventory), "Three Ages source inventory is incomplete")
    require(all(entry.get("url", "").startswith("https://") for entry in three_ages_inventory.values()), "Three Ages source inventory has an invalid URL")
    require(three_ages_inventory["bruciel_1996"].get("licence", "").startswith("CC0"), "1996 BruCiel licence metadata is missing")
    require(three_ages_inventory["bruciel_1996"].get("status", "").startswith("WMS extract verified"), "1996 BruCiel test status is missing")
    require(three_ages_inventory["bruciel_1996"].get("preview") == "data/bruciel-1996-grand-place.png", "1996 BruCiel preview metadata is missing")
    require(preview_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), "1996 BruCiel preview is not a PNG")
    require(_png_has_content(preview_path), "1996 BruCiel preview is blank")
    require(three_ages_inventory["urbisgrid_2022"].get("preview") == "data/urbisgrid-2022-grand-place.png", "2022 urbisgrid preview metadata is missing")
    require(preview_2022_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), "2022 urbisgrid preview is not a PNG")
    require(_png_has_content(preview_2022_path), "2022 urbisgrid preview is blank")
    require(three_ages_inventory["bruciel_1944"].get("licence", "").startswith("CC0"), "1944 BruCiel licence metadata is missing")
    require(three_ages_inventory["bruciel_1944"].get("status", "").startswith("WMS layer unavailable"), "1944 BruCiel failure status is missing")
    require(pilot_ids <= building_ids, "pilot contains an unknown building source ID")
    required_pilot_fields = {"source_id", "selection_reason", "register", "facade", "structure", "image_evidence", "next_step"}
    require(all(required_pilot_fields <= set(record) for record in pilot["records"]), "pilot record schema is incomplete")
    require(all(all(field in record[claim] for field in ("status", "value", "note")) for record in pilot["records"] for claim in ("register", "facade", "structure")), "pilot claim schema is incomplete")
    require(all(record["register"]["status"] in ("pending", "proxy", "reviewed") for record in pilot["records"]), "pilot register status is not in the agreed vocabulary")
    register_sources = {record["source_id"]: record["register"].get("source") for record in pilot["records"]}
    require(all(source.get("kind") == "wikidata-inception" and source.get("qid", "").startswith("Q") and source.get("claim_url", "").startswith("https://www.wikidata.org/") and source.get("heritage_id") and source.get("heritage_url", "").startswith("https://heritage.toolforge.org/") for source in register_sources.values() if source), "register proxy source chain is incomplete")
    require(all((record["register"]["status"] == "proxy") == (record["register"].get("source") is not None) for record in pilot["records"]), "register proxy status and source do not match")
    require(all(not record["image_evidence"] for record in pilot["records"]), "pilot image evidence should remain explicitly empty")
    require(len(pilot_csv) == 7 and pilot_csv[0].startswith("source_id,name,address"), "Three Ages pilot CSV export is incomplete")

    print("snapshot validation passed")
    print(f"tree points: {len(tree_ids)}; heat joins: {len(heat_ids)}; mobility joins: {len(mobility_ids)}")
    print(f"counter observations: {len(history['records'])}; building records: {len(building_ids)}; pilot cases: {len(pilot_ids)}")


if __name__ == "__main__":
    main()
