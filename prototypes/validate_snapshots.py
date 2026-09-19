#!/usr/bin/env python3
"""Validate the small committed snapshots used by both prototypes."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import runpy
import statistics
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent


def read_json(relative: str) -> dict:
    path = ROOT / relative

    def reject_nonstandard_constant(value: str) -> None:
        raise ValueError(f"non-standard JSON constant {value} in {path}")

    return json.loads(path.read_text(), parse_constant=reject_nonstandard_constant)


def _decode_png(path: Path) -> tuple[int, int, str, bytes] | None:
    """Decode the small non-interlaced 8-bit PNG variants used by previews."""
    import struct
    import zlib

    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    pos, idat, header = 8, bytearray(), None
    while pos < len(data):
        length, typ = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + length]
        if typ == b"IHDR":
            header = struct.unpack(">IIBBBBB", chunk[:13])
        elif typ == b"IDAT":
            idat += chunk
        elif typ == b"IEND":
            break
        pos += 12 + length
    if not header or not idat:
        return None
    width, height, depth, colour_type, compression, filtering, interlace = header
    modes = {0: ("L", 1), 2: ("RGB", 3), 4: ("LA", 2), 6: ("RGBA", 4)}
    if depth != 8 or colour_type not in modes or compression or filtering or interlace:
        return None
    mode, channels = modes[colour_type]
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error:
        return None
    stride = width * channels
    if len(raw) != height * (stride + 1):
        return None

    def paeth(left: int, up: int, upper_left: int) -> int:
        estimate = left + up - upper_left
        distances = (abs(estimate - left), abs(estimate - up), abs(estimate - upper_left))
        return (left, up, upper_left)[distances.index(min(distances))]

    pixels = bytearray()
    previous = bytearray(stride)
    off = 0
    for _ in range(height):
        filter_type = raw[off]
        off += 1
        encoded = raw[off:off + stride]
        off += stride
        decoded = bytearray(stride)
        for index, value in enumerate(encoded):
            left = decoded[index - channels] if index >= channels else 0
            up = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            predictor = {0: 0, 1: left, 2: up, 3: (left + up) // 2, 4: paeth(left, up, upper_left)}.get(filter_type)
            if predictor is None:
                return None
            decoded[index] = (value + predictor) & 0xFF
        pixels += decoded
        previous = decoded
    return width, height, mode, bytes(pixels)


def _png_pixel_sha256(path: Path) -> str:
    import hashlib

    decoded = _decode_png(path)
    if not decoded:
        return ""
    width, height, mode, pixels = decoded
    return hashlib.sha256(f"{mode}:{width}x{height}:".encode("ascii") + pixels).hexdigest()


def _png_has_content(path: Path) -> bool:
    """Return True when the PNG carries non-trivial visible imagery."""
    decoded = _decode_png(path)
    if not decoded:
        return False
    _width, _height, mode, pixels = decoded
    channels = len(mode)
    intensities = bytearray()
    for index in range(0, len(pixels), channels):
        values = pixels[index:index + channels]
        alpha = values[-1] if mode.endswith("A") else 255
        colour = values[:-1] if mode.endswith("A") else values
        if alpha:
            intensities.append(sum(colour) // len(colour))
    if not intensities:
        return False
    seen = set(intensities)
    return len(seen) > 50 and (max(seen) - min(seen)) > 40


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"validation failed: {message}")


def require_unique_ids(records: list[dict], label: str, field: str = "id") -> set[object]:
    identifiers = [record.get(field) for record in records]
    require(all(identifier not in (None, "") for identifier in identifiers), f"{label} contains a missing {field}")
    require(len(set(identifiers)) == len(identifiers), f"{label} contains duplicate {field} values")
    return set(identifiers)


def main() -> None:
    trees = read_json("trees-surfaces/data/brussels-trees-sample.json")
    remarkable = read_json("trees-surfaces/data/brussels-remarkable-trees-sample.json")
    heat = read_json("trees-surfaces/data/brussels-tree-heat-sample.json")
    mobility = read_json("trees-surfaces/data/brussels-tree-bike-nearest.json")
    bikes = read_json("trees-surfaces/data/brussels-bike-counters.json")
    history = read_json("trees-surfaces/data/brussels-bike-history-CB2105-2024-01.json")
    history_flows = {feature: read_json(f"trees-surfaces/data/brussels-bike-history-{feature}-2024-01.json") for feature in ("CB1101", "CB1142", "CJM90", "CB1143", "CB2105")}
    flow_context = read_json("trees-surfaces/data/brussels-tree-counter-flow.json")
    inventory = read_json("trees-surfaces/data/source-inventory.json")
    sensitivity = read_json("trees-surfaces/data/tree-signal-sensitivity.json")
    stakeholder_proposal = read_json("trees-surfaces/data/tree-stakeholder-proposal.json")
    stakeholder_review_csv = (ROOT / "trees-surfaces/data/tree-stakeholder-review.csv").read_text().splitlines()
    stakeholder_review_rows = list(csv.DictReader(stakeholder_review_csv))
    compiled_stakeholder_reviews = read_json("trees-surfaces/data/tree-stakeholder-reviews.json")
    balanced_csv = (ROOT / "trees-surfaces/data/tree-signal-balanced-screen.csv").read_text().splitlines()
    balanced_rows = list(csv.DictReader(balanced_csv))
    analysis_report = (ROOT / "trees-surfaces/data/tree-signal-analysis.md").read_text()
    buildings = read_json("three-ages/data/grand-place-buildings.json")
    pilot = read_json("three-ages/data/three-ages-pilot.json")
    structural_crops = read_json("three-ages/data/three-ages-structural-crops.json")
    three_ages_inventory = read_json("three-ages/data/source-inventory.json")
    preview_1935_path = ROOT / "three-ages/data/bruciel-1935-grand-place.png"
    preview_path = ROOT / "three-ages/data/bruciel-1996-grand-place.png"
    preview_2022_path = ROOT / "three-ages/data/urbisgrid-2022-grand-place.png"
    pilot_csv = (ROOT / "three-ages/data/three-ages-pilot-export.csv").read_text().splitlines()
    image_review_csv = (ROOT / "three-ages/data/three-ages-image-review.csv").read_text().splitlines()
    image_review_rows = list(csv.DictReader(image_review_csv))
    compiled_reviews = read_json("three-ages/data/three-ages-image-reviews.json")
    structural_review_csv = (ROOT / "three-ages/data/three-ages-structural-review.csv").read_text().splitlines()
    structural_review_rows = list(csv.DictReader(structural_review_csv))
    compiled_structural_reviews = read_json("three-ages/data/three-ages-structural-reviews.json")
    register_review_csv = (ROOT / "three-ages/data/three-ages-register-review.csv").read_text().splitlines()
    register_review_rows = list(csv.DictReader(register_review_csv))
    compiled_register_reviews = read_json("three-ages/data/three-ages-register-reviews.json")

    tree_ids = require_unique_ids(trees["records"], "managed-tree snapshot")
    require_unique_ids(remarkable["records"], "remarkable-tree snapshot")
    heat_ids = require_unique_ids(heat["records"], "heat join")
    mobility_ids = require_unique_ids(mobility["records"], "mobility join")
    bike_ids = require_unique_ids(bikes["records"], "bicycle-counter snapshot")
    flow_ids = require_unique_ids(flow_context["records"], "counter-flow join")
    require(len(trees["records"]) == 100, "expected 100 managed-tree records")
    require(trees.get("sampling", "").startswith("first 100"), "managed-tree sampling metadata is missing")
    require(len(remarkable["records"]) == 100 and remarkable.get("sampling", "").startswith("first 100"), "remarkable-tree sampling metadata is missing")
    require(trees.get("dataset_metadata_url") == inventory["managed_trees"]["metadata"] and trees.get("source_licence") == inventory["managed_trees"]["licence"] and trees.get("source_credit") == inventory["managed_trees"]["credit"], "managed-tree snapshot provenance disagrees with the source inventory")
    require(remarkable.get("dataset_metadata_url") == inventory["remarkable_trees"]["metadata"] and remarkable.get("source_licence") == inventory["remarkable_trees"]["licence"] and remarkable.get("source_credit") == inventory["remarkable_trees"]["credit"], "remarkable-tree snapshot provenance disagrees with the source inventory")
    mobility_snapshots = [bikes, *history_flows.values()]
    require(all(payload.get("dataset_metadata_url") == inventory["mobility"]["metadata"] and payload.get("source_licence") == inventory["mobility"]["licence"] and payload.get("source_credit") == inventory["mobility"]["credit"] for payload in mobility_snapshots), "mobility snapshot provenance disagrees with the source inventory")
    require(heat_ids == tree_ids, "heat join IDs do not match tree snapshot IDs")
    require(mobility_ids == tree_ids, "mobility join IDs do not match tree snapshot IDs")
    require(mobility.get("source", "").startswith("Derived from the committed"), "mobility join source metadata is missing")
    require(mobility.get("inputs") == ["brussels-trees-sample.json", "brussels-bike-counters.json"], "mobility join input metadata is missing")
    require(mobility.get("method", "").startswith("Haversine great-circle"), "mobility join distance method metadata is missing")
    tree_by_id = {record["id"]: record for record in trees["records"]}
    require(all(record["latitude"] == tree_by_id[record["id"]]["latitude"] and record["longitude"] == tree_by_id[record["id"]]["longitude"] for record in heat["records"]), "heat join coordinates are stale")
    require(heat.get("coordinate_transform", "").startswith("WGS84 to Belgian 1972 datum"), "heat join datum-transform metadata is missing")
    heat_join = runpy.run_path(str(ROOT / "trees-surfaces" / "join_heat.py"))
    require(heat_join.get("EXPECTED_RASTER_SIZE") == (10_000, 9_000) and heat_join.get("EXPECTED_RASTER_MODE") == "L", "heat join source-shape safeguards are stale")
    require(heat.get("source_metadata_id") == heat_join.get("SOURCE_METADATA_ID"), "heat join metadata identifier is stale")
    require(heat.get("source_licence") == heat_join.get("SOURCE_LICENCE") == "CC BY 4.0", "heat join licence provenance is stale")
    require(heat.get("value_semantics") == heat_join.get("VALUE_SEMANTICS"), "heat join value semantics are stale")
    control_x, control_y = heat_join["wgs84_to_lambert72"](50.85, 4.35)
    require(abs(control_x - 148679.4474) < 0.01 and abs(control_y - 171066.8103) < 0.01, "Belgian Lambert 72 transform fails the EPSG control point")
    require(all((record["heat_pixel_column"], record["heat_pixel_row"]) == heat_join["raster_pixel"](record["latitude"], record["longitude"], 100_000, 100_000) for record in heat["records"]), "heat raster cells are stale relative to the coordinate transform")
    require(all(record["latitude"] == tree_by_id[record["id"]]["latitude"] and record["longitude"] == tree_by_id[record["id"]]["longitude"] for record in mobility["records"]), "mobility join coordinates are stale")
    require(len(history["records"]) == 672, "expected 672 counter observations")
    require(all(len(payload["records"]) == 672 for payload in history_flows.values()), "counter history snapshots must hold 672 observations")
    for feature, payload in history_flows.items():
        days = {}
        for record in payload["records"]:
            days.setdefault(record["count_date"], []).append(record)
        require(payload.get("feature") == feature, f"history feature metadata disagrees for {feature}")
        require(payload.get("start_date") == "2024/01/01" and payload.get("end_date") == "2024/01/07", f"history period metadata disagrees for {feature}")
        expected_days = {f"2024/01/{day:02d}" for day in range(1, 8)}
        require(set(days) == expected_days, f"history observations do not cover the expected seven dates for {feature}")
        require(all(len(records) == 96 for records in days.values()), f"history observations are not 96 per day for {feature}")
        expected_slots = set(range(1, 97))
        require(all({record.get("time_gap") for record in records} == expected_slots for records in days.values()), f"history observations do not contain each 15-minute slot exactly once per day for {feature}")
        require(all(record["count"] >= 0 for record in payload["records"]), f"negative counter count for {feature}")
    require(flow_context.get("record_count") == 100 and flow_context.get("trees_with_measured_flow") == 97, "counter-flow context is incomplete")
    require(flow_context.get("source") == "Brussels Mobility bicycle counter API (five committed counter snapshots sharing one 7-day period)", "counter-flow source provenance is stale")
    require(flow_context.get("source_metadata_url") == inventory["mobility"]["metadata"] and flow_context.get("source_licence") == inventory["mobility"]["licence"] and flow_context.get("source_credit") == inventory["mobility"]["credit"], "counter-flow licence provenance is stale")
    require(flow_context.get("caveat", "").startswith("Flow is measured at the nearest counter"), "counter-flow context caveat is missing")
    flow_means = {feature: statistics.mean(record["count"] for record in payload["records"]) for feature, payload in history_flows.items()}
    require(all(abs(flow_context["counter_flow"][feature]["mean_all"] - mean) < 0.001 for feature, mean in flow_means.items()), "counter-flow means are stale")
    require(all(flow_context["counter_flow"][feature]["days"] == 7 for feature in history_flows), "counter-flow day coverage is stale")
    mobility_by_id = {record["id"]: record for record in mobility["records"]}
    require(flow_ids == tree_ids, "counter-flow IDs do not match tree snapshot IDs")
    require(all(entry["nearest_counter"] == mobility_by_id[entry["id"]]["nearest_counter"] and entry["distance_m"] == mobility_by_id[entry["id"]]["nearest_counter_distance_m"] for entry in flow_context["records"]), "counter-flow join is stale relative to nearest-counter join")
    require(all(entry["has_measured_flow"] == (entry["nearest_counter"] in history_flows) for entry in flow_context["records"]), "counter-flow context flags are inconsistent")
    require(all((entry["counter_flow_mean"] is not None) == entry["has_measured_flow"] for entry in flow_context["records"]), "missing counter-flow means must be JSON null")
    require(all((not entry["has_measured_flow"]) or abs(entry["counter_flow_mean"] - flow_means[entry["nearest_counter"]]) < 0.001 for entry in flow_context["records"]), "per-tree counter-flow means are stale")
    require(all(isinstance(record["heat_pixel"], int) and 0 < record["heat_pixel"] <= 100 for record in heat["records"]), "heat join contains NoData or out-of-range indicator values")
    require(all(record["nearest_counter_distance_m"] >= 0 for record in mobility["records"]), "negative counter distance")
    require(all(entry.get("licence") and entry.get("credit") for entry in inventory.values()), "Trees source inventory contains an unresolved licence or credit field")
    require(inventory.get("canopy", {}).get("licence") == "CC BY 4.0" and inventory.get("canopy", {}).get("doi") == "10.5281/zenodo.13869065" and "Elsa Gallez" in inventory.get("canopy", {}).get("credit", ""), "canopy source-lead provenance is missing or stale")
    require(all(inventory.get(key, {}).get("records", "").startswith("https://") for key in ("managed_trees", "remarkable_trees")), "tree source inventory is missing record URLs")
    require(all(inventory.get(key, {}).get("metadata", "").startswith("https://") for key in ("managed_trees", "remarkable_trees")), "tree source inventory is missing metadata URLs")
    require(all(inventory.get(key, {}).get("licence") == "CC BY 4.0" for key in ("managed_trees", "remarkable_trees")), "tree-register licences are missing or stale")
    require(inventory.get("managed_trees", {}).get("credit") == "City of Brussels/Data Management; catalogue attributions: Bruxelles Mobilité, Bruxelles Environnement, Google Maps, Ville de Bruxelles/Espaces publics et verts", "managed-tree catalogue attribution is incomplete or paraphrased")
    require(inventory.get("remarkable_trees", {}).get("credit") == "heritage.brussels; catalogue attribution: National Geographic Institute (NGI-IGN, ngi.be)", "remarkable-tree catalogue attribution is incomplete or paraphrased")
    require(inventory.get("heat", {}).get("download", "").startswith("https://"), "heat source inventory is missing download URL")
    require(inventory.get("heat", {}).get("raster_size_pixels") == {"width": 10_000, "height": 9_000}, "heat source raster dimensions are missing or stale")
    require(inventory.get("heat", {}).get("metadata_id") == "BRU_ENVI_73b4f29a-cff0-4d6a-a239-cb99d3140531", "heat metadata identifier is missing or stale")
    require("73b4f29a-cff0-4d6a-a239-cb99d3140531" in inventory.get("heat", {}).get("metadata", ""), "heat metadata URL is missing or stale")
    require(inventory.get("heat", {}).get("licence") == "CC BY 4.0" and "Brussels Environment" in inventory.get("heat", {}).get("credit", ""), "heat licence or attribution is missing")
    require("normalized 0–100 WBGT indicator values" in inventory.get("heat", {}).get("note", ""), "heat raster value semantics are missing")
    require(inventory.get("mobility", {}).get("devices", "").startswith("https://"), "mobility source inventory is missing device URL")
    require(inventory.get("mobility", {}).get("metadata") == "https://data.mobility.brussels/en/info/rt_counting/", "mobility metadata URL is missing or stale")
    require(inventory.get("mobility", {}).get("licence") == "CC0 1.0" and inventory.get("mobility", {}).get("credit") == "Brussels Mobility", "mobility licence or source credit is missing")
    refresh_script = runpy.run_path(str(ROOT / "fetch_open_data.py"))
    require(refresh_script.get("MOBILITY_METADATA_URL") == inventory["mobility"]["metadata"] and refresh_script.get("MOBILITY_LICENCE") == inventory["mobility"]["licence"] and refresh_script.get("MOBILITY_CREDIT") == inventory["mobility"]["credit"], "mobility refresh expectations disagree with the source inventory")
    history_url = inventory.get("mobility", {}).get("history", "")
    require(history_url.startswith("https://data.mobility.brussels/bike/api/counts/"), "mobility source inventory is missing history URL")
    require(parse_qs(urlparse(history_url).query) == {
        "request": ["history"],
        "featureID": ["CB2105"],
        "startDate": ["20240101"],
        "endDate": ["20240107"],
    }, "mobility history inventory URL disagrees with the committed seven-day period")
    require(sensitivity.get("record_count") == 100, "sensitivity report has unexpected record count")
    require(sensitivity.get("heat_value_semantics") == heat["value_semantics"], "sensitivity report heat semantics are stale")
    require(sensitivity.get("heat_source_metadata_id") == heat["source_metadata_id"] and sensitivity.get("heat_source_licence") == heat["source_licence"], "sensitivity report heat provenance is stale")
    flow_missing_ids = [entry["id"] for entry in flow_context["records"] if not entry["has_measured_flow"]]
    expected_completeness = {
        "managed_records": len(trees["records"]),
        "valid_coordinate_records": sum(all(isinstance(record.get(field), (int, float)) and math.isfinite(record[field]) for field in ("latitude", "longitude")) for record in trees["records"]),
        "missing_coordinate_ids": [record["id"] for record in trees["records"] if not all(isinstance(record.get(field), (int, float)) and math.isfinite(record[field]) for field in ("latitude", "longitude"))],
        "heat_joined_records": len(heat_ids),
        "heat_unmatched_ids": [record["id"] for record in trees["records"] if record["id"] not in heat_ids],
        "heat_nodata_ids": [record["id"] for record in heat["records"] if float(record["heat_pixel"]) == 0],
        "mobility_joined_records": len(mobility_ids),
        "mobility_unmatched_ids": [record["id"] for record in trees["records"] if record["id"] not in mobility_ids],
        "analyzed_records": len(heat_ids & mobility_ids),
        "analysis_unmatched_ids": [record["id"] for record in trees["records"] if record["id"] not in (heat_ids & mobility_ids)],
        "flow_context_joined_records": len(flow_context["records"]),
        "flow_context_unmatched_ids": [record["id"] for record in trees["records"] if record["id"] not in {entry["id"] for entry in flow_context["records"]}],
        "measured_flow_context_records": flow_context["trees_with_measured_flow"],
        "measured_flow_unmatched_ids": flow_missing_ids,
        "measured_flow_unmatched_counters": sorted({entry["nearest_counter"] for entry in flow_context["records"] if not entry["has_measured_flow"]}),
    }
    require(sensitivity.get("data_completeness") == expected_completeness, "sensitivity data-completeness audit is stale")
    require(len(sensitivity.get("balanced_screening", [])) == 100, "balanced screening export is incomplete")
    require(len(balanced_csv) == 101 and balanced_csv[0].startswith("rank,id,street"), "balanced CSV export is incomplete")
    require(analysis_report.startswith("# Tree signal descriptive analysis") and "High-heat/high-proximity quadrant" in analysis_report and "## Mobility context" in analysis_report and "not a seasonal or street-level estimate" in analysis_report and "## Heat data and normalization" in analysis_report and "## Traceability" in analysis_report and "## Data completeness" in analysis_report and "## Weight sensitivity" in analysis_report and all(record_id in analysis_report for record_id in flow_missing_ids), "descriptive analysis report is incomplete")
    require("normalized 0–100 WBGT indicator, not degrees Celsius" in analysis_report and "CC BY 4.0" in analysis_report and heat["source_metadata_id"] in analysis_report, "descriptive analysis lacks authoritative heat semantics or licence")
    require({scenario["name"] for scenario in sensitivity.get("scenarios", [])} == {"heat_only", "balanced", "proximity_only"}, "sensitivity scenarios are incomplete")
    require(all(len(scenario["top_records"]) == 10 for scenario in sensitivity["scenarios"]), "sensitivity report must contain ten top records per scenario")
    require(all(record["nearest_counter"] in bike_ids for record in mobility["records"]), "mobility join references an unknown counter")

    def distance_m(a, b):
        radius = 6_371_000
        lat1, lon1, lat2, lon2 = map(math.radians, [a["latitude"], a["longitude"], b["latitude"], b["longitude"]])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 2 * radius * math.asin(math.sqrt(h))

    bikes_by_id = {record["id"]: record for record in bikes["records"]}
    for tree in trees["records"]:
        nearest = min(bikes["records"], key=lambda bike: distance_m(tree, bike))
        joined = next(record for record in mobility["records"] if record["id"] == tree["id"])
        require(joined["nearest_counter"] == nearest["id"], f"nearest counter is stale for {tree['id']}")
        require(abs(float(joined["nearest_counter_distance_m"]) - round(distance_m(tree, bikes_by_id[nearest["id"]]), 1)) < 0.051, f"nearest counter distance is stale for {tree['id']}")
    heat_by_id = {record["id"]: float(record["heat_pixel"]) for record in heat["records"]}
    distances = [float(record["nearest_counter_distance_m"]) for record in mobility["records"]]
    heat_values = list(heat_by_id.values())
    min_distance, max_distance = min(distances), max(distances)
    min_heat, max_heat = min(heat_values), max(heat_values)

    def normalize(value: float, lower: float, upper: float) -> float:
        return 50.0 if upper == lower else (value - lower) / (upper - lower) * 100

    analysis_rows = []
    for record in mobility["records"]:
        heat_value = heat_by_id[record["id"]]
        distance = float(record["nearest_counter_distance_m"])
        analysis_rows.append({
            "id": record["id"],
            "street": record.get("street"),
            "district": record.get("district") or "Unknown",
            "heat_pixel": heat_value,
            "nearest_counter": record["nearest_counter"],
            "distance_m": distance,
            "heat_score": round(normalize(heat_value, min_heat, max_heat), 3),
            "proximity_score": round(100 - normalize(distance, min_distance, max_distance), 3),
        })

    scenario_weights = {
        "heat_only": {"heat": 1.0, "proximity": 0.0},
        "balanced": {"heat": 0.6, "proximity": 0.4},
        "proximity_only": {"heat": 0.0, "proximity": 1.0},
    }
    expected_rankings = {}
    for name, weights in scenario_weights.items():
        ranked = sorted(analysis_rows, key=lambda row: row["heat_score"] * weights["heat"] + row["proximity_score"] * weights["proximity"], reverse=True)
        expected_rankings[name] = [{**row, "signal": round(row["heat_score"] * weights["heat"] + row["proximity_score"] * weights["proximity"], 3)} for row in ranked]

    def compare_ranked(actual_rows, expected_rows, label):
        require([row["id"] for row in actual_rows] == [row["id"] for row in expected_rows], f"{label} ranking order is stale")
        for actual, expected in zip(actual_rows, expected_rows):
            for field in ("heat_pixel", "distance_m", "heat_score", "proximity_score", "signal"):
                require(math.isclose(float(actual[field]), float(expected[field]), rel_tol=0, abs_tol=0.001), f"{label} {field} is stale for {actual['id']}")
            require(actual["nearest_counter"] == expected["nearest_counter"], f"{label} counter is stale for {actual['id']}")

    compare_ranked(sensitivity["balanced_screening"], expected_rankings["balanced"], "balanced screening")
    require(len(balanced_rows) == 100 and [int(row["rank"]) for row in balanced_rows] == list(range(1, 101)), "balanced CSV ranks are incomplete")
    compare_ranked([{**row, **{"heat_pixel": float(row["heat_pixel"]), "distance_m": float(row["distance_m"]), "heat_score": float(row["heat_score"]), "proximity_score": float(row["proximity_score"]), "signal": float(row["signal"]), "nearest_counter": row["nearest_counter"]}} for row in balanced_rows], expected_rankings["balanced"], "balanced CSV")
    for scenario in sensitivity["scenarios"]:
        compare_ranked(scenario["top_records"], expected_rankings[scenario["name"]][:10], f"{scenario['name']} top ten")
    expected_balanced_top = [row["id"] for row in expected_rankings["balanced"][:10]]
    expected_balanced_ids = set(expected_balanced_top)
    expected_heat_overlap = len({row["id"] for row in expected_rankings["heat_only"][:10]} & expected_balanced_ids)
    expected_proximity_overlap = len({row["id"] for row in expected_rankings["proximity_only"][:10]} & expected_balanced_ids)
    sensitivity_summary = sensitivity.get("weight_sensitivity", {})
    require(sensitivity_summary.get("balanced_top_10_ids") == expected_balanced_top, "weight-sensitivity balanced top ten is stale")
    require(sensitivity_summary.get("heat_only_top_10_overlap") == expected_heat_overlap and sensitivity_summary.get("proximity_only_top_10_overlap") == expected_proximity_overlap, "weight-sensitivity overlap counts are stale")
    require(sensitivity_summary.get("material_change") == (expected_proximity_overlap < 5) and "strongly heat-led" in sensitivity_summary.get("interpretation", ""), "weight-sensitivity conclusion is stale")

    required_proposal_fields = {"proposal_id", "status", "proposed_stakeholder", "decision_question", "spatial_unit", "heat_measure", "mobility_measure", "measured_flow_context", "output_boundary", "review_topics", "allowed_review_statuses"}
    require(required_proposal_fields <= set(stakeholder_proposal), "Trees stakeholder proposal schema is incomplete")
    require(stakeholder_proposal["proposal_id"] == "trees-screening-v1" and stakeholder_proposal["status"].endswith("pending"), "Trees stakeholder proposal identity or status is stale")
    require(set(stakeholder_proposal["allowed_review_statuses"]) == {"accepted", "accepted with changes", "needs more evidence", "rejected"}, "stakeholder review status vocabulary is stale")
    require(len(stakeholder_review_csv) == 2 and len(stakeholder_review_rows) == 1, "stakeholder review worksheet must contain one proposal row")
    stakeholder_row = stakeholder_review_rows[0]
    expected_stakeholder_provenance = {
        "proposal_id": stakeholder_proposal["proposal_id"],
        "proposal_status": stakeholder_proposal["status"],
        "proposed_stakeholder": stakeholder_proposal["proposed_stakeholder"],
        "decision_question": stakeholder_proposal["decision_question"],
        "spatial_unit": stakeholder_proposal["spatial_unit"],
        "heat_measure": stakeholder_proposal["heat_measure"],
        "mobility_measure": stakeholder_proposal["mobility_measure"],
        "measured_flow_context": stakeholder_proposal["measured_flow_context"],
        "output_boundary": stakeholder_proposal["output_boundary"],
        "core_join_summary": f"{expected_completeness['analyzed_records']}/{expected_completeness['managed_records']} records analyzed; {len(expected_completeness['missing_coordinate_ids'])} missing coordinates; {len(expected_completeness['heat_nodata_ids'])} NoData heat pixels; {len(expected_completeness['analysis_unmatched_ids'])} unmatched core joins; {expected_completeness['measured_flow_context_records']}/{expected_completeness['managed_records']} with measured-flow history",
        "sensitivity_summary": f"balanced top ten overlaps {expected_heat_overlap}/10 with heat-only and {expected_proximity_overlap}/10 with proximity-only; {sensitivity_summary['interpretation']}",
    }
    require(all(stakeholder_row[field] == value for field, value in expected_stakeholder_provenance.items()), "stakeholder review proposal provenance is stale")
    stakeholder_review_fields = ("review_status", "reviewer_name", "reviewer_role", "reviewed_at", "accepted_decision_question", "accepted_spatial_unit", "accepted_mobility_measure", "accepted_heat_period", "false_positive_preference", "evidence_threshold", "review_notes")
    common_stakeholder_fields = ("review_status", "reviewer_name", "reviewer_role", "reviewed_at", "false_positive_preference", "evidence_threshold", "review_notes")
    accepted_stakeholder_fields = ("accepted_decision_question", "accepted_spatial_unit", "accepted_mobility_measure", "accepted_heat_period")
    has_stakeholder_review = any(stakeholder_row[field].strip() for field in stakeholder_review_fields)
    if has_stakeholder_review:
        require(all(stakeholder_row[field].strip() for field in common_stakeholder_fields), "stakeholder review is incomplete")
        require(stakeholder_row["review_status"] in stakeholder_proposal["allowed_review_statuses"], "stakeholder review status is invalid")
        if stakeholder_row["review_status"] in {"accepted", "accepted with changes"}:
            require(all(stakeholder_row[field].strip() for field in accepted_stakeholder_fields), "accepted stakeholder decision fields are incomplete")
        try:
            datetime.fromisoformat(stakeholder_row["reviewed_at"].replace("Z", "+00:00"))
        except ValueError:
            require(False, "stakeholder review date is not ISO 8601")
    require(compiled_stakeholder_reviews.get("source") == "tree-stakeholder-review.csv" and compiled_stakeholder_reviews.get("proposal_id") == stakeholder_proposal["proposal_id"], "compiled stakeholder-review metadata is stale")
    require(compiled_stakeholder_reviews.get("record_count") == (1 if has_stakeholder_review else 0), "compiled stakeholder-review count is stale")
    require(compiled_stakeholder_reviews.get("records") == ([stakeholder_row] if has_stakeholder_review else []), "compiled stakeholder review does not match the worksheet")

    stakeholder_export = runpy.run_path(str(ROOT / "trees-surfaces" / "export_stakeholder_review.py"))
    generated_stakeholder = {field: "" for field in stakeholder_export["FIELDS"]}
    generated_stakeholder.update({"proposal_id": "test-proposal", "sensitivity_summary": "test evidence"})
    existing_stakeholder = {field: str(generated_stakeholder[field]) for field in stakeholder_export["FIELDS"]}
    existing_stakeholder.update({
        "review_status": "accepted with changes",
        "reviewer_name": "Test reviewer",
        "reviewer_role": "Test role",
        "reviewed_at": "2026-09-20",
        "accepted_decision_question": "Test question",
        "accepted_spatial_unit": "Test unit",
        "accepted_mobility_measure": "Test mobility measure",
        "accepted_heat_period": "Test period",
        "false_positive_preference": "Test preference",
        "evidence_threshold": "Test threshold",
        "review_notes": "Test notes",
    })
    allowed_stakeholder_statuses = {"accepted", "accepted with changes", "needs more evidence", "rejected"}
    preserved_stakeholder = stakeholder_export["preserve_review"](dict(generated_stakeholder), existing_stakeholder, allowed_stakeholder_statuses)
    require(preserved_stakeholder["reviewer_name"] == "Test reviewer", "completed stakeholder reviews are not preserved")
    rejected_stakeholder = dict(existing_stakeholder)
    rejected_stakeholder["review_status"] = "rejected"
    for field in stakeholder_export["ACCEPTED_DECISION_FIELDS"]:
        rejected_stakeholder[field] = ""
    stakeholder_export["validate_review"](rejected_stakeholder, allowed_stakeholder_statuses)
    changed_stakeholder = dict(generated_stakeholder)
    changed_stakeholder["sensitivity_summary"] = "changed evidence"
    try:
        stakeholder_export["preserve_review"](changed_stakeholder, existing_stakeholder, allowed_stakeholder_statuses)
    except RuntimeError:
        pass
    else:
        require(False, "stakeholder reviews can drift onto changed proposal evidence")

    building_ids = require_unique_ids(buildings["records"], "Grand Place building snapshot")
    pilot_ids = require_unique_ids(pilot["records"], "Three Ages pilot", "source_id")
    buildings_by_id = {str(record["id"]): record for record in buildings["records"]}
    require(len(buildings["records"]) == 34, "expected 34 Grand Place records")
    require(buildings.get("dataset_url", "").startswith("https://"), "building snapshot is missing dataset URL")
    require(buildings.get("dataset_metadata_url") == "https://opendata.brussels.be/api/explore/v2.1/catalog/datasets/description-des-batiments-de-la-grand-place", "building snapshot metadata URL is missing or stale")
    require(buildings.get("source_licence") == "CC BY 4.0", "building snapshot licence is missing or stale")
    require(buildings.get("source_credit") == "Ville de Bruxelles/Data Management; catalogue attributions: Behind Brussels, Google Maps", "building snapshot attribution is missing or stale")
    require(len(pilot["records"]) == 6, "expected six curated pilot records")
    require(pilot.get("review_status") == "source-grounded pilot", "pilot review status is missing")
    require({"bruciel_app", "grand_place_dataset", "brussels_heritage_inventory", "wikidata_register_proxies", "heritage_collection_1749", "kik_irpa_historical", "wikimedia_commons_balance", "balance_engraving_1878", "bruciel_1935", "bruciel_1996", "bruciel_1944", "brussels_archives", "urbisgrid_2022"} <= set(three_ages_inventory), "Three Ages source inventory is incomplete")
    area_images = pilot.get("area_image_evidence", [])
    require(
        [(asset.get("asset_id"), asset.get("epoch"), asset.get("preview")) for asset in area_images] == [
            ("bruciel-grand-place-1935", "1930–1935", "data/bruciel-1935-grand-place.png"),
            ("bruciel-grand-place-1996", 1996, "data/bruciel-1996-grand-place.png"),
            ("urbisgrid-grand-place-2022", 2022, "data/urbisgrid-2022-grand-place.png"),
        ],
        "area-level structural evidence is incomplete or out of order",
    )
    area_required = {"asset_id", "epoch", "scope", "source_url", "image_url", "preview", "preview_sha256", "licence", "credit", "observation", "annotation_status"}
    require(all(area_required <= set(asset) for asset in area_images), "area-level structural evidence schema is incomplete")
    require(all(asset["scope"] == "Grand Place pilot area" and asset["annotation_status"].startswith("area source preview") for asset in area_images), "area-level structural evidence scope or review status is stale")
    require(all("bbox=4.348%2C50.845%2C4.357%2C50.849" in asset["image_url"] for asset in area_images), "area-level structural evidence bounds are not aligned")
    require(all(hashlib.sha256((ROOT / "three-ages" / asset["preview"]).read_bytes()).hexdigest() == asset["preview_sha256"] for asset in area_images), "area-level source preview checksum is stale")

    require(structural_crops.get("review_status") == "derived review aids; no structural observations", "structural crop review boundary is missing")
    require(structural_crops.get("crs") == "EPSG:4326", "structural crop CRS is stale")
    require(structural_crops.get("bounds") == {"west": 4.348, "south": 50.845, "east": 4.357, "north": 50.849}, "structural crop bounds are stale")
    require(structural_crops.get("source_size_pixels") == {"width": 640, "height": 480}, "structural crop source dimensions are stale")
    crop_size = structural_crops.get("crop_size_pixels")
    require(crop_size == 160 and structural_crops.get("record_count") == 6, "structural crop size or record count is stale")
    crop_records = structural_crops.get("records", [])
    require_unique_ids(crop_records, "structural crop manifest", "source_id")
    require([record.get("source_id") for record in crop_records] == [record["source_id"] for record in pilot["records"]], "structural crops do not follow the pilot case order")
    area_by_id = {asset["asset_id"]: asset for asset in area_images}
    crop_paths = set()
    for crop_record in crop_records:
        source_id = crop_record["source_id"]
        building = buildings_by_id[source_id]
        require(crop_record["latitude"] == building["latitude"] and crop_record["longitude"] == building["longitude"], f"structural crop coordinate is stale for {source_id}")
        expected_x = round((building["longitude"] - 4.348) / (4.357 - 4.348) * 640)
        expected_y = round((50.849 - building["latitude"]) / (50.849 - 50.845) * 480)
        require(crop_record["source_center_pixels"] == {"x": expected_x, "y": expected_y}, f"structural crop centre is stale for {source_id}")
        half = crop_size // 2
        require(crop_record["crop_box_pixels"] == {"left": expected_x - half, "top": expected_y - half, "right": expected_x + half, "bottom": expected_y + half}, f"structural crop box is stale for {source_id}")
        crop_assets = crop_record.get("assets", [])
        require([asset.get("asset_id") for asset in crop_assets] == list(area_by_id), f"structural crop epochs are stale for {source_id}")
        for crop_asset in crop_assets:
            source_asset = area_by_id[crop_asset["asset_id"]]
            require(crop_asset["epoch"] == source_asset["epoch"] and crop_asset["source_preview"] == source_asset["preview"] and crop_asset["source_preview_sha256"] == source_asset["preview_sha256"], f"structural crop source metadata is stale for {source_id}/{crop_asset['asset_id']}")
            crop_path = ROOT / "three-ages" / crop_asset["crop_preview"]
            crop_paths.add(crop_path.resolve())
            decoded = _decode_png(crop_path) if crop_path.is_file() else None
            require(decoded is not None and decoded[:2] == (crop_size, crop_size), f"structural crop is missing or has wrong dimensions for {source_id}/{crop_asset['asset_id']}")
            require(_png_has_content(crop_path), f"structural crop is blank for {source_id}/{crop_asset['asset_id']}")
            require(_png_pixel_sha256(crop_path) == crop_asset["pixel_sha256"], f"structural crop pixel hash is stale for {source_id}/{crop_asset['asset_id']}")
    actual_crop_paths = {path.resolve() for path in (ROOT / "three-ages/data/structural").glob("*.png")}
    require(actual_crop_paths == crop_paths, "structural crop directory contains missing or stale files")

    require(all(entry.get("url", "").startswith("https://") for entry in three_ages_inventory.values()), "Three Ages source inventory has an invalid URL")
    require(all(entry.get("licence") and entry.get("credit") for entry in three_ages_inventory.values()), "Three Ages source inventory contains an unresolved licence or credit field")
    require(three_ages_inventory["urbis_buildings"].get("licence", "").startswith("Open Data licence stated by provider") and three_ages_inventory["urbis_buildings"].get("credit") == "Paradigm", "UrbIS source-lead reuse status is missing")
    require(three_ages_inventory["planning_permits"].get("licence") == "CC0 1.0" and "Ville de Bruxelles" in three_ages_inventory["planning_permits"].get("credit", ""), "planning-permit source-lead provenance is missing")
    require(three_ages_inventory["grand_place_dataset"].get("metadata") == buildings["dataset_metadata_url"] and three_ages_inventory["grand_place_dataset"].get("licence") == buildings["source_licence"] and three_ages_inventory["grand_place_dataset"].get("credit") == buildings["source_credit"], "Grand Place inventory provenance disagrees with the snapshot")
    require(three_ages_inventory["brussels_heritage_inventory"].get("terms") == "https://monument.heritage.brussels/fr/legal/", "architectural-inventory terms URL is missing")
    require(three_ages_inventory["brussels_heritage_inventory"].get("licence") == "text quotations and reused information permitted with explicit source attribution" and "urban.brussels" in three_ages_inventory["brussels_heritage_inventory"].get("credit", ""), "architectural-inventory text reuse terms or credit are missing")
    require(three_ages_inventory["wikidata_register_proxies"].get("licence") == "CC0 1.0 for structured data" and three_ages_inventory["wikidata_register_proxies"].get("credit", "").startswith("Wikidata contributors"), "Wikidata register-proxy licence or credit is missing")
    require(three_ages_inventory["kik_irpa_historical"].get("licence", "").startswith("CC BY 4.0") and three_ages_inventory["kik_irpa_historical"].get("credit", "").startswith("KIK-IRPA"), "KIK-IRPA licence or credit metadata is missing")
    require(three_ages_inventory["kik_irpa_historical"].get("status", "").startswith("five 1941-1942"), "KIK-IRPA verification status is missing")
    require(three_ages_inventory["wikimedia_commons_balance"].get("licence") == "CC BY-SA 3.0" and three_ages_inventory["wikimedia_commons_balance"].get("credit") == "EmDee, via Wikimedia Commons", "Wikimedia Commons licence or credit metadata is missing")
    require(three_ages_inventory["wikimedia_commons_balance"].get("status", "").startswith("exact-case 2011"), "Wikimedia Commons verification status is missing")
    require("2043-0177/0" in three_ages_inventory["wikimedia_commons_balance"].get("note", "") and "does not state Rue de la Colline 24" in three_ages_inventory["wikimedia_commons_balance"]["note"], "Wikimedia Commons identity metadata is inaccurate")
    require(three_ages_inventory["balance_engraving_1878"].get("licence") == "No known copyright restrictions" and "British Library" in three_ages_inventory["balance_engraving_1878"].get("credit", "") and "Victor Dedoncker" in three_ages_inventory["balance_engraving_1878"]["credit"], "1878 engraving rights or credit metadata is missing")
    require(three_ages_inventory["balance_engraving_1878"].get("status", "").startswith("exact-case 1878 institutional scan verified"), "1878 engraving verification status is missing")
    require(three_ages_inventory["balance_engraving_1878"].get("preview") == "data/historical/british-library-maison-balance-1878.jpg", "1878 engraving preview metadata is missing")
    require(three_ages_inventory["bruciel_1935"].get("licence", "").startswith("CC0") and three_ages_inventory["bruciel_1935"].get("credit") == area_by_id["bruciel-grand-place-1935"]["credit"], "1930–1935 BruCiel licence or credit metadata is missing")
    require(three_ages_inventory["bruciel_1935"].get("status", "").startswith("historical WMS extract verified"), "1930–1935 BruCiel test status is missing")
    require(three_ages_inventory["bruciel_1935"].get("layer") == "URBAN_DCC_ER:Orthophotoplans_1935", "1930–1935 BruCiel layer metadata is stale")
    require(three_ages_inventory["bruciel_1935"].get("preview") == "data/bruciel-1935-grand-place.png", "1930–1935 BruCiel preview metadata is missing")
    require(preview_1935_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), "1930–1935 BruCiel preview is not a PNG")
    require(_png_has_content(preview_1935_path), "1930–1935 BruCiel preview is blank")
    require(three_ages_inventory["bruciel_1996"].get("licence", "").startswith("CC0") and three_ages_inventory["bruciel_1996"].get("credit") == area_by_id["bruciel-grand-place-1996"]["credit"], "1996 BruCiel licence or credit metadata is missing")
    require(three_ages_inventory["bruciel_1996"].get("status", "").startswith("WMS extract verified"), "1996 BruCiel test status is missing")
    require(three_ages_inventory["bruciel_1996"].get("preview") == "data/bruciel-1996-grand-place.png", "1996 BruCiel preview metadata is missing")
    require(preview_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), "1996 BruCiel preview is not a PNG")
    require(_png_has_content(preview_path), "1996 BruCiel preview is blank")
    require(three_ages_inventory["urbisgrid_2022"].get("licence", "").startswith("open data") and three_ages_inventory["urbisgrid_2022"].get("credit") == area_by_id["urbisgrid-grand-place-2022"]["credit"], "2022 urbisgrid licence or credit metadata is missing")
    require(three_ages_inventory["urbisgrid_2022"].get("preview") == "data/urbisgrid-2022-grand-place.png", "2022 urbisgrid preview metadata is missing")
    require(preview_2022_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), "2022 urbisgrid preview is not a PNG")
    require(_png_has_content(preview_2022_path), "2022 urbisgrid preview is blank")
    require(three_ages_inventory["bruciel_1944"].get("licence", "").startswith("CC0"), "1944 BruCiel licence metadata is missing")
    require(three_ages_inventory["bruciel_1944"].get("status", "").startswith("WMS layer unavailable"), "1944 BruCiel failure status is missing")
    require(pilot_ids <= building_ids, "pilot contains an unknown building source ID")
    required_pilot_fields = {"source_id", "selection_reason", "register", "facade", "structure", "image_evidence", "next_step"}
    require(all(required_pilot_fields <= set(record) for record in pilot["records"]), "pilot record schema is incomplete")
    require(all(all(field in record[claim] for field in ("status", "value", "note")) for record in pilot["records"] for claim in ("register", "facade", "structure")), "pilot claim schema is incomplete")
    require(all(all(field in record["register"] for field in ("date_semantics", "source_comparison")) for record in pilot["records"]), "pilot register semantics are not explicit")
    require(all(record["register"]["status"] in ("pending", "proxy", "reviewed") for record in pilot["records"]), "pilot register status is not in the agreed vocabulary")
    register_sources = {record["source_id"]: record["register"].get("source") for record in pilot["records"]}
    wikidata_sources = [source for source in register_sources.values() if source and source.get("kind") == "wikidata-inception"]
    inventory_sources = [source for source in register_sources.values() if source and source.get("kind") == "brussels-architectural-inventory"]
    require({source.get("qid") for source in wikidata_sources} == {"Q3279995", "Q3279408", "Q3279633"}, "Wikidata register proxy claim set is incomplete or stale")
    require(all(source.get("qid", "").startswith("Q") and source.get("claim_url", "").startswith("https://www.wikidata.org/") and source.get("heritage_id") and source.get("heritage_url", "").startswith("https://heritage.toolforge.org/") for source in wikidata_sources), "Wikidata register proxy source chain is incomplete")
    require(all(source.get("inventory_id", "").isdigit() and source.get("url", "").startswith("https://monument.heritage.brussels/") for source in inventory_sources), "official heritage inventory source chain is incomplete")
    expected_inventory_proxies = {"005": 1697, "024": 1704, "026": 1697}
    require(all(pilot_record["register"]["value"] == value and register_sources[source_id]["kind"] == "brussels-architectural-inventory" for source_id, value in expected_inventory_proxies.items() for pilot_record in pilot["records"] if pilot_record["source_id"] == source_id), "official inventory proxy values are stale")
    require(all((record["register"]["status"] == "proxy") == (record["register"].get("source") is not None) for record in pilot["records"]), "register proxy status and source do not match")
    require(all(record["register"]["date_semantics"] == ("Wikidata inception claim referenced to heritage register" if record["register"]["source"]["kind"] == "wikidata-inception" else "heritage-inventory reconstruction date") for record in pilot["records"]), "register date semantics do not match source kinds")
    comparison_by_id = {record["source_id"]: record["register"]["source_comparison"] for record in pilot["records"]}
    require(comparison_by_id["023"].startswith("disagrees") and comparison_by_id["022"].startswith("compatible") and all(comparison_by_id[source_id].startswith("agrees") for source_id in {"005", "009", "024", "026"}), "register source comparisons are stale")
    balance_case = next(record for record in pilot["records"] if record["source_id"] == "024")
    require("Rue de la Colline 24" in balance_case.get("identity_note", "") and "street-address mapping" in balance_case["identity_note"], "La Balance identity discrepancy is not explicit")
    identity_evidence = balance_case.get("identity_evidence", [])
    require(
        [(item.get("source_kind"), item.get("record_id")) for item in identity_evidence] == [
            ("city-open-data", "024"),
            ("brussels-architectural-inventory", "30991"),
            ("wikimedia-commons", "2043-0177/0"),
            ("british-library-flickr-commons", "11271682895"),
        ],
        "La Balance identity crosswalk identifiers are incomplete",
    )
    require(all(all(item.get(field) for field in ("label", "address", "source_url", "observation")) for item in identity_evidence), "La Balance identity crosswalk schema is incomplete")
    commons_identity = next(item for item in identity_evidence if item["source_kind"] == "wikimedia-commons")
    require(commons_identity["address"].startswith("Grand-Place") and "Rue de la Colline" not in commons_identity["address"], "Commons identity evidence overstates its street address")
    heritage_identity = next(item for item in identity_evidence if item["source_kind"] == "brussels-architectural-inventory")
    require(heritage_identity["address"] == "Rue de la Colline 24" and "Grand-Place ensemble" in heritage_identity["observation"], "heritage identity evidence is incomplete")
    require(all("identity_evidence" not in record for record in pilot["records"] if record["source_id"] != "024"), "identity crosswalk is attached to an unrelated pilot case")
    expected_images = {
        "005": [("T084580", 1942)],
        "009": [("B031587", 1942)],
        "022": [("A102887", 1941)],
        "023": [("B024641", 1941)],
        "024": [("british-library-balance-1878", 1878), ("commons-balance-2011-01", 2011)],
        "026": [("B031502", 1942)],
    }
    for record in pilot["records"]:
        evidence = record["image_evidence"]
        require([(asset.get("asset_id"), asset.get("epoch")) for asset in evidence] == expected_images[record["source_id"]], f"historical image evidence is unexpected for {record['source_id']}")
        for asset in evidence:
            require(all(asset.get(field) for field in ("asset_id", "epoch", "source_url", "image_url", "preview", "preview_sha256", "licence", "credit", "observation", "annotation_status")), f"historical image evidence schema is incomplete for {record['source_id']}")
            if asset["asset_id"].startswith("commons-"):
                require(asset["source_url"].startswith("https://commons.wikimedia.org/wiki/File:"), f"Commons source URL is invalid for {asset['asset_id']}")
                require(asset["image_url"].startswith("https://upload.wikimedia.org/wikipedia/commons/"), f"Commons image URL is invalid for {asset['asset_id']}")
                require(asset["licence"] == "CC BY-SA 3.0" and "EmDee" in asset["credit"], f"Commons image rights or credit is missing for {asset['asset_id']}")
            elif asset["asset_id"].startswith("british-library-"):
                require(asset["source_url"] == "https://www.flickr.com/photos/britishlibrary/11271682895/", f"British Library source URL is invalid for {asset['asset_id']}")
                require(asset["image_url"] == "https://live.staticflickr.com/2815/11271682895_1aeeecbddd_o.jpg", f"British Library image URL is stale for {asset['asset_id']}")
                require(asset["licence"] == "No known copyright restrictions" and "British Library" in asset["credit"], f"British Library image rights or credit is missing for {asset['asset_id']}")
            else:
                require(asset["source_url"].startswith("https://balat.kikirpa.be/en/photo/"), f"historical image source URL is invalid for {asset['asset_id']}")
                require(asset["image_url"].startswith("https://iiif.kikirpa.be/iiif/2/"), f"historical image IIIF URL is invalid for {asset['asset_id']}")
                require(asset["licence"] == "CC BY 4.0", f"historical image rights are missing for {asset['asset_id']}")
            require(asset["annotation_status"].startswith("source preview"), f"historical image review status is missing for {asset['asset_id']}")
            preview = ROOT / "three-ages" / asset["preview"]
            preview_bytes = preview.read_bytes() if preview.is_file() else b""
            require(preview_bytes.startswith(b"\xff\xd8\xff"), f"historical image preview is missing for {asset['asset_id']}")
            require(hashlib.sha256(preview_bytes).hexdigest() == asset["preview_sha256"], f"historical image preview checksum is stale for {asset['asset_id']}")
    evidence_by_asset = {
        asset["asset_id"]: asset
        for case in pilot["records"]
        for asset in case["image_evidence"]
    }
    kik_downloader = runpy.run_path(str(ROOT / "three-ages" / "download_kik_previews.py"))
    require(all(evidence_by_asset[asset_id]["preview_sha256"] == digest for asset_id, digest in kik_downloader["EXPECTED_SHA256"].items()), "KIK downloader checksums disagree with pilot provenance")
    commons_downloader = runpy.run_path(str(ROOT / "three-ages" / "download_commons_previews.py"))
    require(evidence_by_asset["commons-balance-2011-01"]["preview_sha256"] == commons_downloader["EXPECTED_SHA256"], "Commons downloader checksum disagrees with pilot provenance")
    british_downloader = runpy.run_path(str(ROOT / "three-ages" / "download_british_library_preview.py"))
    require(evidence_by_asset["british-library-balance-1878"]["preview_sha256"] == british_downloader["EXPECTED_SHA256"], "British Library downloader checksum disagrees with pilot provenance")
    area_checksum_scripts = {
        "bruciel-grand-place-1935": "download_bruciel_1935_preview.py",
        "bruciel-grand-place-1996": "download_bruciel_preview.py",
        "urbisgrid-grand-place-2022": "download_urbisgrid_preview.py",
    }
    for asset_id, script in area_checksum_scripts.items():
        downloader = runpy.run_path(str(ROOT / "three-ages" / script))
        require(area_by_id[asset_id]["preview_sha256"] == downloader["EXPECTED_SHA256"], f"{asset_id} downloader checksum disagrees with pilot provenance")

    require(len(pilot_csv) == 7 and pilot_csv[0].startswith("source_id,name,address"), "Three Ages pilot CSV export is incomplete")
    require(all(field in pilot_csv[0] for field in ("register_source_kind", "register_source_url", "identity_note", "identity_evidence_count", "identity_evidence_ids", "identity_evidence_urls", "image_evidence_ids", "image_evidence_epochs", "image_evidence_urls")), "Three Ages pilot CSV is missing provenance columns")
    require(len(image_review_csv) == 8 and image_review_csv[0].startswith("source_id,name,address,asset_id,epoch"), "historical-image review worksheet is incomplete")
    require(all(field in image_review_csv[0] for field in ("source_observation", "annotation_status", "identity_note", "facade_observation", "structural_observation", "reviewer", "reviewed_at", "confidence")), "historical-image review worksheet is missing review columns")
    require({row["source_id"] for row in image_review_rows} == set(expected_images), "historical-image review worksheet does not cover every pilot case")
    require(all(asset_id in "\n".join(image_review_csv) for asset_id in ("T084580", "B031587", "A102887", "B024641", "british-library-balance-1878", "commons-balance-2011-01", "B031502")), "historical-image review worksheet is missing an asset")
    expected_review_rows = {}
    for case in pilot["records"]:
        assets = case["image_evidence"] or [None]
        for asset in assets:
            asset = asset or {}
            key = (case["source_id"], asset.get("asset_id", ""))
            expected_review_rows[key] = {
                "epoch": str(asset.get("epoch", "")),
                "source_url": asset.get("source_url", ""),
                "image_url": asset.get("image_url", ""),
                "preview": asset.get("preview", ""),
                "preview_sha256": asset.get("preview_sha256", ""),
                "licence": asset.get("licence", ""),
                "credit": asset.get("credit", ""),
                "source_observation": asset.get("observation", "No permitted historical preview is attached."),
                "identity_note": case.get("identity_note", ""),
                "_source_annotation_status": asset.get("annotation_status", "pending historical source"),
            }
    require(len(image_review_rows) == len(expected_review_rows), "historical-image review worksheet has unexpected rows")
    review_fields = ("facade_observation", "structural_observation", "reviewer", "reviewed_at", "confidence")
    for row in image_review_rows:
        key = (row["source_id"], row["asset_id"])
        require(key in expected_review_rows, f"historical-image review worksheet has an unexpected case or asset: {key}")
        expected = expected_review_rows[key]
        require(all(row[field] == value for field, value in expected.items() if field != "_source_annotation_status"), f"historical-image review worksheet is stale for {key}")
        has_review = any(row[field].strip() for field in review_fields)
        if has_review:
            require(bool(row["asset_id"]), f"historical-image review cannot annotate missing evidence for {key}")
            require(bool(row["facade_observation"].strip() or row["structural_observation"].strip()), f"historical-image review needs an observation for {key}")
            require(bool(row["reviewer"].strip() and row["reviewed_at"].strip() and row["confidence"].strip()), f"historical-image review metadata is incomplete for {key}")
            require(row["confidence"] in {"low", "medium", "high"}, f"historical-image review confidence is invalid for {key}")
            try:
                datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
            except ValueError:
                require(False, f"historical-image review date is not ISO 8601 for {key}")
            require(row["annotation_status"] == "reviewed image annotation", f"historical-image review status is stale for {key}")
        else:
            require(row["annotation_status"] == expected["_source_annotation_status"], f"unreviewed historical-image status is stale for {key}")
    completed_review_rows = [row for row in image_review_rows if any(row[field].strip() for field in review_fields)]
    require(compiled_reviews.get("source") == "three-ages-image-review.csv", "compiled image-review source metadata is missing")
    require(compiled_reviews.get("record_count") == len(completed_review_rows), "compiled image-review count is stale")
    require(compiled_reviews.get("records") == completed_review_rows, "compiled image reviews do not match the completed worksheet rows")
    balance_image_rows = [row for row in image_review_rows if row["source_id"] == "024"]
    require({(row["asset_id"], row["epoch"]) for row in balance_image_rows} == {("british-library-balance-1878", "1878"), ("commons-balance-2011-01", "2011")}, "La Balance comparison epochs are missing from the review worksheet")

    structural_fields = ("structural_observation", "reviewer", "reviewed_at", "confidence")
    require(len(structural_review_csv) == 7 and structural_review_csv[0].startswith("source_id,name,address,comparison_id"), "structural review worksheet is incomplete")
    require({row["source_id"] for row in structural_review_rows} == pilot_ids, "structural review worksheet does not cover every pilot case")
    area_joined = {
        "area_asset_ids": ";".join(str(asset["asset_id"]) for asset in area_images),
        "area_epochs": ";".join(str(asset["epoch"]) for asset in area_images),
        "area_source_urls": ";".join(asset["source_url"] for asset in area_images),
        "area_image_urls": ";".join(asset["image_url"] for asset in area_images),
        "area_previews": ";".join(asset["preview"] for asset in area_images),
        "area_preview_sha256": ";".join(asset["preview_sha256"] for asset in area_images),
        "area_licences": ";".join(asset["licence"] for asset in area_images),
        "area_credits": ";".join(asset["credit"] for asset in area_images),
    }
    case_by_id = {case["source_id"]: case for case in pilot["records"]}
    crop_by_id = {record["source_id"]: record for record in crop_records}
    for row in structural_review_rows:
        key = (row["source_id"], row["comparison_id"])
        require(row["comparison_id"] == "grand-place-1930-1935-to-2022", f"structural comparison id is stale for {key}")
        require(all(row[field] == value for field, value in area_joined.items()), f"structural comparison provenance is stale for {key}")
        crop_record = crop_by_id[row["source_id"]]
        center, box, assets = crop_record["source_center_pixels"], crop_record["crop_box_pixels"], crop_record["assets"]
        crop_joined = {
            "case_latitude": str(crop_record["latitude"]),
            "case_longitude": str(crop_record["longitude"]),
            "crop_source_center_pixels": f"{center['x']},{center['y']}",
            "crop_box_pixels": f"{box['left']},{box['top']},{box['right']},{box['bottom']}",
            "crop_size_pixels": str(crop_size),
            "case_crop_previews": ";".join(asset["crop_preview"] for asset in assets),
            "case_crop_pixel_sha256": ";".join(asset["pixel_sha256"] for asset in assets),
        }
        require(all(row[field] == value for field, value in crop_joined.items()), f"structural crop provenance is stale for {key}")
        identity_items = case_by_id[row["source_id"]].get("identity_evidence", [])
        identity_joined = {
            "identity_evidence_ids": ";".join(f"{item.get('source_kind', '')}:{item.get('record_id', '')}" for item in identity_items),
            "identity_evidence_urls": ";".join(item.get("source_url", "") for item in identity_items),
            "identity_evidence_observations": ";".join(item.get("observation", "") for item in identity_items),
        }
        require(all(row[field] == value for field, value in identity_joined.items()), f"structural identity provenance is stale for {key}")
        require(row["identity_note"] == case_by_id[row["source_id"]].get("identity_note", ""), f"structural comparison identity note is stale for {key}")
        has_review = any(row[field].strip() for field in structural_fields)
        if has_review:
            require(all(row[field].strip() for field in structural_fields), f"structural review metadata is incomplete for {key}")
            require(row["confidence"] in {"low", "medium", "high"}, f"structural review confidence is invalid for {key}")
            try:
                datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
            except ValueError:
                require(False, f"structural review date is not ISO 8601 for {key}")
            require(row["annotation_status"] == "reviewed structural comparison", f"completed structural review status is stale for {key}")
        else:
            require(row["annotation_status"] == "area comparison; no reviewer annotation", f"pending structural review status is stale for {key}")
    completed_structural_rows = [row for row in structural_review_rows if any(row[field].strip() for field in structural_fields)]
    require(compiled_structural_reviews.get("source") == "three-ages-structural-review.csv", "compiled structural-review source metadata is missing")
    require(compiled_structural_reviews.get("record_count") == len(completed_structural_rows), "compiled structural-review count is stale")
    require(compiled_structural_reviews.get("records") == completed_structural_rows, "compiled structural reviews do not match the completed worksheet rows")

    register_fields = ("register_decision", "register_observation", "reviewer", "reviewed_at", "confidence")
    register_decisions = {"accept proxy for MVP", "retain as reconstruction evidence", "reject source mapping"}
    require(len(register_review_csv) == 7 and register_review_csv[0].startswith("source_id,name,address,claim_id"), "register review worksheet is incomplete")
    require({row["source_id"] for row in register_review_rows} == pilot_ids, "register review worksheet does not cover every pilot case")
    for row in register_review_rows:
        source_id = row["source_id"]
        case = case_by_id[source_id]
        claim = case["register"]
        claim_source = claim["source"]
        key = (source_id, row["claim_id"])
        expected_register = {
            "claim_id": f"register-{source_id}",
            "reported_value": str(claim["value"]),
            "claim_status": claim["status"],
            "date_semantics": claim["date_semantics"],
            "source_comparison": claim["source_comparison"],
            "source_kind": claim_source["kind"],
            "source_record_id": claim_source.get("qid") or claim_source.get("inventory_id", ""),
            "source_url": claim_source.get("url") or claim_source.get("claim_url", ""),
            "source_note": claim["note"],
            "city_history": buildings_by_id[source_id]["history"],
            "identity_note": case.get("identity_note", ""),
        }
        require(all(row[field] == value for field, value in expected_register.items()), f"register review provenance is stale for {key}")
        has_review = any(row[field].strip() for field in register_fields)
        if has_review:
            require(all(row[field].strip() for field in register_fields), f"register review metadata is incomplete for {key}")
            require(row["register_decision"] in register_decisions, f"register review decision is invalid for {key}")
            require(row["confidence"] in {"low", "medium", "high"}, f"register review confidence is invalid for {key}")
            try:
                datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
            except ValueError:
                require(False, f"register review date is not ISO 8601 for {key}")
            require(row["annotation_status"] == "reviewed register semantics", f"completed register review status is stale for {key}")
        else:
            require(row["annotation_status"] == "proxy semantics; no reviewer decision", f"pending register review status is stale for {key}")
    completed_register_rows = [row for row in register_review_rows if any(row[field].strip() for field in register_fields)]
    require(compiled_register_reviews.get("source") == "three-ages-register-review.csv", "compiled register-review source metadata is missing")
    require(compiled_register_reviews.get("record_count") == len(completed_register_rows), "compiled register-review count is stale")
    require(compiled_register_reviews.get("records") == completed_register_rows, "compiled register reviews do not match the completed worksheet rows")

    review_export = runpy.run_path(str(ROOT / "three-ages" / "export_pilot.py"))
    generated_review = {field: "" for field in review_export["IMAGE_FIELDS"]}
    generated_review.update({"source_id": "test-case", "asset_id": "test-asset", "source_url": "https://example.test/evidence", "annotation_status": "source preview; no reviewer annotation"})
    existing_review = {field: str(generated_review[field]) for field in review_export["IMAGE_FIELDS"]}
    existing_review.update({"facade_observation": "Test observation", "reviewer": "Test reviewer", "reviewed_at": "2026-09-20", "confidence": "medium"})
    preserved_review = review_export["preserve_review"](dict(generated_review), existing_review)
    require(preserved_review["facade_observation"] == "Test observation" and preserved_review["annotation_status"] == "reviewed image annotation", "completed historical-image reviews are not preserved")
    changed_review = dict(generated_review)
    changed_review["source_url"] = "https://example.test/changed"
    try:
        review_export["preserve_review"](changed_review, existing_review)
    except RuntimeError:
        pass
    else:
        require(False, "historical-image reviews can drift onto changed provenance")

    generated_structural = {field: "" for field in review_export["STRUCTURAL_FIELDS"]}
    generated_structural.update({
        "source_id": "test-case",
        "comparison_id": "test-comparison",
        "area_asset_ids": "historical;modern",
        "case_crop_pixel_sha256": "historical-hash;modern-hash",
        "annotation_status": "area comparison; no reviewer annotation",
    })
    existing_structural = {field: str(generated_structural[field]) for field in review_export["STRUCTURAL_FIELDS"]}
    existing_structural.update({
        "structural_observation": "Test structural observation",
        "reviewer": "Test reviewer",
        "reviewed_at": "2026-09-20",
        "confidence": "medium",
    })
    preserved_structural = review_export["preserve_structural_review"](dict(generated_structural), existing_structural)
    require(preserved_structural["structural_observation"] == "Test structural observation" and preserved_structural["annotation_status"] == "reviewed structural comparison", "completed structural reviews are not preserved")
    changed_structural = dict(generated_structural)
    changed_structural["case_crop_pixel_sha256"] = "changed-hash;modern-hash"
    try:
        review_export["preserve_structural_review"](changed_structural, existing_structural)
    except RuntimeError:
        pass
    else:
        require(False, "structural reviews can drift onto changed crop pixels")

    generated_register = {field: "" for field in review_export["REGISTER_FIELDS"]}
    generated_register.update({
        "source_id": "test-case",
        "claim_id": "register-test-case",
        "reported_value": "1700",
        "date_semantics": "test semantics",
        "source_comparison": "test comparison",
        "annotation_status": "proxy semantics; no reviewer decision",
    })
    existing_register = {field: str(generated_register[field]) for field in review_export["REGISTER_FIELDS"]}
    existing_register.update({
        "register_decision": "retain as reconstruction evidence",
        "register_observation": "Test semantics observation",
        "reviewer": "Test reviewer",
        "reviewed_at": "2026-09-20",
        "confidence": "medium",
    })
    preserved_register = review_export["preserve_register_review"](dict(generated_register), existing_register)
    require(preserved_register["register_decision"] == "retain as reconstruction evidence" and preserved_register["annotation_status"] == "reviewed register semantics", "completed register reviews are not preserved")
    changed_register = dict(generated_register)
    changed_register["source_comparison"] = "changed comparison"
    try:
        review_export["preserve_register_review"](changed_register, existing_register)
    except RuntimeError:
        pass
    else:
        require(False, "register reviews can drift onto changed source semantics")

    print("snapshot validation passed")
    print(f"tree points: {len(tree_ids)}; heat joins: {len(heat_ids)}; mobility joins: {len(mobility_ids)}")
    print(f"counter observations: {len(history['records'])}; building records: {len(building_ids)}; pilot cases: {len(pilot_ids)}")


if __name__ == "__main__":
    main()
