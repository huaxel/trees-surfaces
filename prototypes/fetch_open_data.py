#!/usr/bin/env python3
"""Fetch small public-data snapshots used to assess both BAP candidates.

The prototype UI still uses illustrative analytical values. These snapshots only
prove that the underlying public source shapes are accessible and inspectable.
"""
from __future__ import annotations

import gzip
import io
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
MANAGED_TREE_METADATA_URL = "https://bruxellesdata.opendatasoft.com/api/explore/v2.1/catalog/datasets/arbres-bomen-vbx-be-bm"
MANAGED_TREE_RECORDS_URL = f"{MANAGED_TREE_METADATA_URL}/records"
REMARKABLE_TREE_METADATA_URL = "https://opendata.brussels.be/api/explore/v2.1/catalog/datasets/bruxelles_arbres_remarquables"
REMARKABLE_TREE_RECORDS_URL = f"{REMARKABLE_TREE_METADATA_URL}/records"
GRAND_PLACE_DATASET_URL = "https://opendata.brussels.be/api/explore/v2.1/catalog/datasets/description-des-batiments-de-la-grand-place/records"
GRAND_PLACE_METADATA_URL = "https://opendata.brussels.be/api/explore/v2.1/catalog/datasets/description-des-batiments-de-la-grand-place"
MOBILITY_METADATA_URL = "https://data.mobility.brussels/en/info/rt_counting/"
MOBILITY_LICENCE = "CC0 1.0"
MOBILITY_CREDIT = "Brussels Mobility"
MAX_RESPONSE_BYTES = 20 * 1024 * 1024


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.chmod(0o644)
    os.replace(temporary, path)


def get_body(url: str) -> bytes:
    request = Request(url, headers={"Accept-Encoding": "identity", "User-Agent": "final-work-feasibility-spike/1.0"})
    with urlopen(request, timeout=30) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    require(len(body) <= MAX_RESPONSE_BYTES, f"response exceeds {MAX_RESPONSE_BYTES:,} bytes: {url}")
    if body[:2] == b"\x1f\x8b":
        with gzip.GzipFile(fileobj=io.BytesIO(body)) as compressed:
            body = compressed.read(MAX_RESPONSE_BYTES + 1)
        require(len(body) <= MAX_RESPONSE_BYTES, f"decompressed response exceeds {MAX_RESPONSE_BYTES:,} bytes: {url}")
    return body


def get_json(base: str, **params):
    url = f"{base}?{urlencode(params)}"
    payload = json.loads(get_body(url))
    require(isinstance(payload, dict), f"expected JSON object from {url}")
    return payload


def get_text(url: str) -> str:
    return get_body(url).decode("utf-8")


def validate_history_payload(payload: dict, feature: str) -> list[dict]:
    records = payload.get("data")
    require(payload.get("feature") == feature, f"counter API returned unexpected feature for {feature}")
    require(payload.get("startDate") == "2024/01/01" and payload.get("endDate") == "2024/01/07", f"counter API returned unexpected period for {feature}")
    require(isinstance(records, list) and len(records) == 672, f"counter history for {feature} must contain 672 observations")
    by_day = {}
    for record in records:
        require(isinstance(record.get("count"), (int, float)) and record["count"] >= 0, f"counter history for {feature} contains an invalid count")
        by_day.setdefault(record.get("count_date"), []).append(record)
    expected_days = {f"2024/01/{day:02d}" for day in range(1, 8)}
    require(set(by_day) == expected_days, f"counter history for {feature} must cover 2024/01/01 through 2024/01/07")
    require(all(len(day_records) == 96 for day_records in by_day.values()), f"counter history for {feature} must contain 96 observations per day")
    expected_slots = set(range(1, 97))
    require(
        all({record.get("time_gap") for record in day_records} == expected_slots for day_records in by_day.values()),
        f"counter history for {feature} must contain each 15-minute slot exactly once per day",
    )
    return records


def committed_sample_ids(path: Path) -> list[str] | None:
    if not path.exists():
        return None
    previous = json.loads(path.read_text()).get("records", [])
    previous_ids = [str(record.get("id")) for record in previous]
    require(len(previous_ids) == 100 and all(identifier not in {"", "None"} for identifier in previous_ids), f"committed sample IDs are invalid in {path.name}")
    require(len(set(previous_ids)) == len(previous_ids), f"committed sample IDs are duplicated in {path.name}")
    return previous_ids


def preserve_sample(records: list[dict], path: Path, raw_id_field: str) -> list[dict]:
    record_ids = [str(record.get(raw_id_field)) for record in records]
    require(all(identifier not in {"", "None"} for identifier in record_ids), f"source returned missing IDs for {path.name}")
    require(len(set(record_ids)) == len(record_ids), f"source returned duplicate IDs for {path.name}")
    previous_ids = committed_sample_ids(path)
    if previous_ids is None:
        require(len(records) >= 100, f"source returned fewer than 100 records for {path.name}")
        return records[:100]

    by_id = {str(record.get(raw_id_field)): record for record in records}
    missing = [identifier for identifier in previous_ids if identifier not in by_id]
    require(not missing, f"source no longer returns committed sample IDs for {path.name}: {missing[:3]}")
    return [by_id[identifier] for identifier in previous_ids]


def fetch_all_records(base: str, **params) -> tuple[dict, list[dict]]:
    page_size = 100
    first = get_json(base, limit=page_size, offset=0, **params)
    records = list(first.get("results", []))
    total = first.get("total_count", len(records))
    for offset in range(page_size, total, page_size):
        page = get_json(base, limit=page_size, offset=offset, **params)
        require(page.get("total_count") == total, f"source total changed while paging {base}")
        records.extend(page.get("results", []))
    require(len(records) == total, f"source paging returned {len(records)} records for declared total {total}: {base}")
    return first, records


def fetch_trees() -> None:
    managed_metadata = get_json(MANAGED_TREE_METADATA_URL)
    managed_terms = managed_metadata.get("metas", {}).get("default", {})
    require(managed_terms.get("license") == "CC BY 4.0", "managed-tree catalogue licence changed")
    require(managed_terms.get("publisher_en") == "City of Brussels/Data Management", "managed-tree catalogue publisher changed")
    managed_attributions = managed_terms.get("attributions", [])
    require(managed_attributions == ["Bruxelles Mobilité", "Bruxelles Environnement", "Google Maps", "Ville de Bruxelles/Espaces publics et verts"], "managed-tree catalogue attributions changed")
    out = ROOT / "trees-surfaces" / "data" / "brussels-trees-sample.json"
    previous_ids = committed_sample_ids(out)
    params = {"limit": 100}
    if previous_ids:
        source_summary = get_json(MANAGED_TREE_RECORDS_URL, limit=1)
        source_count = source_summary.get("total_count", 0)
        quoted_ids = ",".join(f"'{identifier.replace(chr(39), chr(39) * 2)}'" for identifier in previous_ids)
        params["where"] = f"id IN ({quoted_ids})"
    else:
        source_count = None
    payload = get_json(MANAGED_TREE_RECORDS_URL, **params)
    source_count = source_count or payload.get("total_count", 0)
    require(source_count >= 100 and len(payload.get("results", [])) == 100, "managed-tree API returned fewer than 100 records")
    rows = []
    for item in preserve_sample(payload["results"], out, "id"):
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
    write_json(out, {
        "source": source_count,
        "dataset_metadata_url": MANAGED_TREE_METADATA_URL,
        "source_licence": managed_terms["license"],
        "source_credit": "City of Brussels/Data Management; catalogue attributions: Bruxelles Mobilité, Bruxelles Environnement, Google Maps, Ville de Bruxelles/Espaces publics et verts",
        "sampling": "first 100 records in initial API response order; refreshes preserve committed IDs; not a probability sample",
        "completeness": completeness,
        "records": rows,
    })

    remarkable_metadata = get_json(REMARKABLE_TREE_METADATA_URL)
    remarkable_terms = remarkable_metadata.get("metas", {}).get("default", {})
    require(remarkable_terms.get("license") == "CC BY 4.0", "remarkable-tree catalogue licence changed")
    require(remarkable_terms.get("publisher_en") == "heritage.brussels", "remarkable-tree catalogue publisher changed")
    require(remarkable_terms.get("attributions") == ["National Geographic Institute (NGI-IGN, ngi.be)"], "remarkable-tree catalogue attribution changed")
    remarkable, remarkable_results = fetch_all_records(REMARKABLE_TREE_RECORDS_URL)
    require(remarkable.get("total_count", 0) >= 100 and len(remarkable_results) >= 100, "remarkable-tree API returned fewer than 100 records")
    remarkable_out = ROOT / "trees-surfaces" / "data" / "brussels-remarkable-trees-sample.json"
    remarkable_rows = []
    for item in preserve_sample(remarkable_results, remarkable_out, "id_arbres_cms"):
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
    write_json(remarkable_out, {
        "source": remarkable["total_count"],
        "dataset_metadata_url": REMARKABLE_TREE_METADATA_URL,
        "source_licence": remarkable_terms["license"],
        "source_credit": "heritage.brussels; catalogue attribution: National Geographic Institute (NGI-IGN, ngi.be)",
        "sampling": "first 100 records in initial API response order; refreshes preserve committed IDs; not a probability sample",
        "records": remarkable_rows,
    })


def fetch_bike_devices() -> None:
    metadata_html = get_text(MOBILITY_METADATA_URL)
    require('href="https://creativecommons.org/publicdomain/zero/1.0">CC0</a>' in metadata_html, "bicycle-counter metadata licence changed")
    require("Bruxelles Mobilité" in metadata_html, "bicycle-counter metadata source changed")
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
    identifiers = [row["id"] for row in rows]
    require(all(identifier not in (None, "") for identifier in identifiers), "bicycle-counter API returned a device without an ID")
    require(len(set(identifiers)) == len(identifiers), "bicycle-counter API returned duplicate device IDs")
    out = ROOT / "trees-surfaces" / "data" / "brussels-bike-counters.json"
    write_json(out, {
        "source": payload.get("totalFeatures"),
        "dataset_metadata_url": MOBILITY_METADATA_URL,
        "source_licence": MOBILITY_LICENCE,
        "source_credit": MOBILITY_CREDIT,
        "records": rows,
    })


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
            "dataset_metadata_url": MOBILITY_METADATA_URL,
            "source_licence": MOBILITY_LICENCE,
            "source_credit": MOBILITY_CREDIT,
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
    write_json(out, {
        "source": "Derived from the committed managed-tree and bicycle-counter snapshots",
        "inputs": ["brussels-trees-sample.json", "brussels-bike-counters.json"],
        "method": "Haversine great-circle nearest-counter distance using Earth radius 6371000 m; no causal interpretation",
        "records": rows,
    })


def fetch_grand_place() -> None:
    payload = get_json(
        GRAND_PLACE_DATASET_URL,
        limit=100,
    )
    metadata = get_json(GRAND_PLACE_METADATA_URL)
    metadata_default = metadata.get("metas", {}).get("default", {})
    require(metadata_default.get("license") == "CC BY 4.0", "Grand Place catalogue licence changed")
    require(metadata_default.get("publisher") == "Ville de Bruxelles/Data Management", "Grand Place catalogue publisher changed")
    attributions = metadata_default.get("attributions", [])
    require(attributions == ["Behind Brussels", "Google Maps"], "Grand Place catalogue attributions changed")
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
    identifiers = [row["id"] for row in rows]
    require(all(identifier not in (None, "") for identifier in identifiers), "Grand Place API returned a building without an ID")
    require(len(set(identifiers)) == len(identifiers), "Grand Place API returned duplicate building IDs")
    completeness = {
        field: sum(bool(row.get(field)) for row in rows)
        for field in ("history", "history_years", "facade", "original_function")
    }
    out = ROOT / "three-ages" / "data" / "grand-place-buildings.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, {
        "source": payload["total_count"],
        "dataset_url": GRAND_PLACE_DATASET_URL,
        "dataset_metadata_url": GRAND_PLACE_METADATA_URL,
        "source_licence": metadata_default["license"],
        "source_credit": f"{metadata_default['publisher']}; catalogue attributions: {', '.join(attributions)}",
        "completeness": completeness,
        "records": rows,
    })


if __name__ == "__main__":
    fetch_trees()
    fetch_bike_devices()
    fetch_bike_history()
    build_tree_mobility_join()
    subprocess.run([sys.executable, str(ROOT / "trees-surfaces" / "join_counter_flow.py")], check=True)
    fetch_grand_place()
    print("Fetched public-data snapshots for both prototype spikes.")
