#!/usr/bin/env python3
"""Validate the small committed snapshots used by Trees & Surfaces."""
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

    heat_preview_path = ROOT / "trees-surfaces/data/heat-preview.png"
    require(heat_preview_path.is_file(), "heat preview image is missing")
    require(_png_has_content(heat_preview_path), "heat preview image is blank")

    print("snapshot validation passed")
    print(f"tree points: {len(tree_ids)}; heat joins: {len(heat_ids)}; mobility joins: {len(mobility_ids)}")
    print(f"counter observations: {len(history['records'])}; bicycle counters: {len(bike_ids)}")


if __name__ == "__main__":
    main()
