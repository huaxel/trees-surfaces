#!/usr/bin/env python3
"""Sample Brussels WBGT raster values at the sampled Brussels tree points.

The raster uses Belgian Lambert 72 (EPSG:31370), while the tree source uses
WGS84 coordinates. The output is a small derived artifact; the large source
GeoTIFF is intentionally not stored in this repository.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image

# EPSG:31370 / Belgian Lambert 72, International 1924 ellipsoid.
A = 6378388.0
E = math.sqrt(0.0067226700223333)
LAT_0 = math.radians(90.0)
LON_0 = math.radians(4.367486666666666)
LAT_1 = math.radians(49.8333339)
LAT_2 = math.radians(51.16666723333333)
X_0 = 150000.013
Y_0 = 5400088.438
PIXEL_SIZE = 2.0
ORIGIN_X = 140000.0
ORIGIN_Y = 178000.0


def m(lat: float) -> float:
    return math.cos(lat) / math.sqrt(1 - E * E * math.sin(lat) ** 2)


def t(lat: float) -> float:
    return math.tan(math.pi / 4 - lat / 2) / ((1 - E * math.sin(lat)) / (1 + E * math.sin(lat))) ** (E / 2)


N = math.log(m(LAT_1) / m(LAT_2)) / math.log(t(LAT_1) / t(LAT_2))
F = m(LAT_1) / (N * t(LAT_1) ** N)
RHO_0 = A * F * t(LAT_0) ** N


def wgs84_to_lambert72(latitude: float, longitude: float) -> tuple[float, float]:
    lat, lon = math.radians(latitude), math.radians(longitude)
    rho = A * F * t(lat) ** N
    theta = N * (lon - LON_0)
    return X_0 + rho * math.sin(theta), Y_0 + RHO_0 - rho * math.cos(theta)


def raster_pixel(latitude: float, longitude: float, width: int, height: int) -> tuple[int, int]:
    x, y = wgs84_to_lambert72(latitude, longitude)
    col = int((x - ORIGIN_X) / PIXEL_SIZE)
    row = int((ORIGIN_Y - y) / PIXEL_SIZE)
    if not (0 <= col < width and 0 <= row < height):
        raise ValueError(f"point outside raster: {latitude},{longitude} -> {x:.1f},{y:.1f}")
    return col, row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("raster", type=Path, help="WBGT GeoTIFF downloaded from the source URL")
    parser.add_argument("trees", type=Path, help="brussels-trees-sample.json")
    parser.add_argument("output", type=Path, help="derived joined JSON output")
    args = parser.parse_args()

    Image.MAX_IMAGE_PIXELS = None
    image = Image.open(args.raster).convert("L")
    source = json.loads(args.trees.read_text())
    records = []
    for tree in source["records"]:
        col, row = raster_pixel(tree["latitude"], tree["longitude"], *image.size)
        value = image.getpixel((col, row))
        records.append({**tree, "heat_pixel": value, "heat_pixel_column": col, "heat_pixel_row": row})

    args.output.write_text(json.dumps({
        "source": "urban_heat_islands_WBGT_MEAN_24082016_0-1_byte.tif",
        "crs": "EPSG:31370",
        "sampling": "nearest raster pixel at tree point; value 0 is source NoData",
        "records": records,
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"Joined {len(records)} tree points to heat pixels")


if __name__ == "__main__":
    main()
