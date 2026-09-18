#!/usr/bin/env python3
"""Fetch small public-data snapshots used to assess both BAP candidates.

The prototype UI still uses illustrative analytical values. These snapshots only
prove that the underlying public source shapes are accessible and inspectable.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlencode, urlparse, parse_qs
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent


def get_json(base: str, **params):
    url = f"{base}?{urlencode(params)}"
    with urlopen(url, timeout=30) as response:
        return json.load(response)


def fetch_trees() -> None:
    payload = get_json(
        "https://bruxellesdata.opendatasoft.com/api/explore/v2.1/catalog/datasets/arbres-bomen-vbx-be-bm/records",
        limit=100,
    )
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
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"source": payload["total_count"], "completeness": completeness, "records": rows}, ensure_ascii=False, indent=2) + "\n")

    remarkable = get_json(
        "https://opendata.brussels.be/api/explore/v2.1/catalog/datasets/bruxelles_arbres_remarquables/records",
        limit=100,
    )
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
    remarkable_out.write_text(json.dumps({"source": remarkable["total_count"], "records": remarkable_rows}, ensure_ascii=False, indent=2) + "\n")


def fetch_grand_place() -> None:
    payload = get_json(
        "https://opendata.brussels.be/api/explore/v2.1/catalog/datasets/description-des-batiments-de-la-grand-place/records",
        limit=100,
    )
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
    out.write_text(json.dumps({"source": payload["total_count"], "completeness": completeness, "records": rows}, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    fetch_trees()
    fetch_grand_place()
    print("Fetched public-data snapshots for both prototype spikes.")
