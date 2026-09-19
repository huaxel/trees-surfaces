#!/usr/bin/env python3
"""Fetch small public-data snapshots used to assess both BAP candidates.

The prototype UI still uses illustrative analytical values. These snapshots only
prove that the underlying public source shapes are accessible and inspectable.
"""
from __future__ import annotations

import gzip
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlencode, urlparse, parse_qs
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
GRAND_PLACE_DATASET_URL = "https://opendata.brussels.be/api/explore/v2.1/catalog/datasets/description-des-batiments-de-la-grand-place/records"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    os.replace(temporary, path)


def get_json(base: str, **params):
    url = f"{base}?{urlencode(params)}"
    request = Request(url, headers={"Accept-Encoding": "identity", "User-Agent": "final-work-feasibility-spike/1.0"})
    with urlopen(request, timeout=30) as response:
        body = response.read()
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    payload = json.loads(body)
    require(isinstance(payload, dict), f"expected JSON object from {url}")
    return payload


def validate_history_payload(payload: dict, feature: str) -> list[dict]:
    records = payload.get("data")
    require(payload.get("feature") == feature, f"counter API returned unexpected feature for {feature}")
    require(payload.get("startDate") == "2024/01/01" and payload.get("endDate") == "2024/01/07", f"counter API returned unexpected period for {feature}")
    require(isinstance(records, list) and len(records) == 672, f"counter history for {feature} must contain 672 observations")
    by_day = {}
    for record in records:
        require(isinstance(record.get("count"), (int, float)) and record["count"] >= 0, f"counter history for {feature} contains an invalid count")
        by_day.setdefault(record.get("count_date"), []).append(record)
    require(len(by_day) == 7 and all(len(day_records) == 96 for day_records in by_day.values()), f"counter history for {feature} must contain 96 observations per day")
    return records


def fetch_trees() -> None:
    payload = get_json(
        "https://bruxellesdata.opendatasoft.com/api/explore/v2.1/catalog/datasets/arbres-bomen-vbx-be-bm/records",
        limit=100,
    )
    require(payload.get("total_count", 0) >= 100 and len(payload.get("results", [])) == 100, "managed-tree API returned fewer than 100 records")
    rows = []
    for item in payload["results"]:
        point = item.get("geo_point_2d") or {}
        rows.append(
            {
                "id": item.get("id"),
                "street": item.get("address_fr") or item.get("adress_nl"),
                "district": item.get("district_fr") or item.get("district_nl"),
                "latitude": point.get("lat"),
                "longitude": point.get("lon"),
                "species": item.get("species"),
                "source": item.get("source_fr") or item.get("source_nl"),
            }
        )
    completeness = {
        field: sum(row.get(field) is not None for row in rows)
        for field in ("latitude", "longitude", "street", "district", "species")
    }
    out = ROOT / "trees-surfaces" / "data" / "brussels-trees-sample.json"
    write_json(out, {"source": payload["total_count"], "sampling": "first 100 records in API response order; not a probability sample", "completeness": completeness, "records": rows})

    remarkable = get_json(
        "https://opendata.brussels.be/api/explore/v2.1/catalog/datasets/bruxelles_arbres_remarquables/records",
        limit=100,
    )
    require(remarkable.get("total_count", 0) >= 100 and len(remarkable.get("results", [])) == 100, "remarkable-tree API returned fewer than 100 records")
    remarkable_rows = []
    for item in remarkable["results"]:
        point = item.get("geo_point_2d") or {}
        remarkable_rows.append(
            {
                "id": item.get("id_arbres_cms"),
                "species": item.get("nom_la"),
                "status": item.get("statuts_fr") or item.get("statuts_nl"),
                "circumference": item.get("circonference"),
                "crown_diameter": item.get("diametre_cime"),
                "latitude": point.get("lat"),
                "longitude": point.get("lon"),
                "url": item.get("url_fr") or item.get("url_nl"),
            }
        )
    remarkable_out = ROOT / "trees-surfaces" / "data" / "brussels-remarkable-trees-sample.json"
    write_json(remarkable_out, {"source": remarkable["total_count"], "sampling": "first 100 records in API response order; not a probability sample", "records": remarkable_rows})


def fetch_bike_devices() -> None:
    payload = get_json("https://data.mobility.brussels/bike/api/counts/", request="devices")
    require(payload.get("totalFeatures", 0) >= 1 and payload.get("features"), "bicycle-counter API returned no devices")
    rows = []
    for feature in payload.get("features", []):
        properties = feature.get("properties", {})
        coordinates = feature.get("geometry", {}).get("coordinates", [None, None])
        rows.append(
            {
                "id": properties.get("device_name"),
                "street": properties.get("road_en") or properties.get("road_fr"),
                "active": properties.get("active"),
                "longitude": coordinates[0],
                "latitude": coordinates[1],
            }
        )
    out = ROOT / "trees-surfaces" / "data" / "brussels-bike-counters.json"
    write_json(out, {"source": payload.get("totalFeatures"), "records": rows})


COUNTER_HISTORY_FEATURES = ("CB1101", "CB1142", "CJM90", "CB1143", "CB2105")


def fetch_bike_history() -> None:
    for feature in COUNTER_HISTORY_FEATURES:
        payload = get_json(
            "https://data.mobility.brussels/bike/api/counts/",
            request="history",
            featureID=feature,
            startDate="20240101",
            endDate="20240107",
        )
        out = ROOT / "trees-surfaces" / "data" / f"brussels-bike-history-{feature}-2024-01.json"
        records = validate_history_payload(payload, feature)
        write_json(out, {
            "source": "Brussels Mobility bicycle counter API",
            "feature": payload.get("feature"),
            "start_date": payload.get("startDate"),
            "end_date": payload.get("endDate"),
            "records": records,
        })


def build_tree_mobility_join() -> None:
    trees_path = ROOT / "trees-surfaces" / "data" / "brussels-trees-sample.json"
    bikes_path = ROOT / "trees-surfaces" / "data" / "brussels-bike-counters.json"
    trees = json.loads(trees_path.read_text())["records"]
    bikes = json.loads(bikes_path.read_text())["records"]

    def distance_m(a, b):
        radius = 6_371_000
        lat1, lon1, lat2, lon2 = map(math.radians, [a["latitude"], a["longitude"], b["latitude"], b["longitude"]])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 2 * radius * math.asin(math.sqrt(h))

    rows = []
    for tree in trees:
        if tree["latitude"] is None or tree["longitude"] is None:
            continue
        nearest = min(bikes, key=lambda bike: distance_m(tree, bike))
        rows.append({**tree, "nearest_counter": nearest["id"], "nearest_counter_distance_m": round(distance_m(tree, nearest), 1)})
    out = ROOT / "trees-surfaces" / "data" / "brussels-tree-bike-nearest.json"
    require(len(rows) == len(trees), "nearest-counter join dropped tree records")
    write_json(out, {"records": rows, "method": "great-circle nearest-counter distance; no causal interpretation"})


def fetch_grand_place() -> None:
    payload = get_json(
        GRAND_PLACE_DATASET_URL,
        limit=100,
    )
    require(payload.get("total_count", 0) >= 34 and len(payload.get("results", [])) == 34, "Grand Place API returned fewer than 34 records")
    rows = []
    for item in payload["results"]:
        maps_url = item.get("google_maps") or ""
        query = parse_qs(urlparse(maps_url).query).get("query", [""])[0]
        query = unquote(query)
        coords = query.split(",", 1) if "," in query else [None, None]
        history = item.get("history_and_successive_restorations") or ""
        history_years = [int(year) for year in re.findall(r"\b(1[5-9]\d{2}|20\d{2})\b", history)]
        rows.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "address": item.get("adresse"),
                "latitude": float(coords[0]) if coords[0] else None,
                "longitude": float(coords[1]) if coords[1] else None,
                "history": history,
                "history_years": sorted(set(history_years)),
                "facade": item.get("composition_of_the_facade_and_decorative_program"),
                "original_function": item.get("original_main_function"),
                "source_url": maps_url,
            }
        )
    completeness = {
        field: sum(bool(row.get(field)) for row in rows)
        for field in ("history", "history_years", "facade", "original_function")
    }
    out = ROOT / "three-ages" / "data" / "grand-place-buildings.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, {"source": payload["total_count"], "dataset_url": GRAND_PLACE_DATASET_URL, "completeness": completeness, "records": rows})


if __name__ == "__main__":
    fetch_trees()
    fetch_bike_devices()
    fetch_bike_history()
    build_tree_mobility_join()
    subprocess.run([sys.executable, str(ROOT / "trees-surfaces" / "join_counter_flow.py")], check=True)
    fetch_grand_place()
    print("Fetched public-data snapshots for both prototype spikes.")
