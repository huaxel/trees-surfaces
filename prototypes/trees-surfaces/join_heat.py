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

# EPSG:31370 / Belgian Lambert 72. Projection is on the Belgian 1972
# datum (International 1924 ellipsoid), so WGS84 coordinates must first
# undergo the inverse of the EPSG seven-parameter datum transformation.
WGS84_A = 6378137.0
WGS84_F = 1 / 298.257223563
A = 6378388.0
F_LOCAL = 1 / 297.0
E = math.sqrt(F_LOCAL * (2 - F_LOCAL))
# EPSG operation “BD72 to WGS 84 (3)”, expressed in position-vector convention.
DATUM_TRANSLATION = (-106.8686, 52.2978, -103.7239)
DATUM_ROTATION = tuple(math.radians(value / 3600) for value in (0.3366, -0.457, 1.8422))
DATUM_SCALE = -1.2747e-6
LAT_0 = math.radians(90.0)
LON_0 = math.radians(4.367486666666666)
LAT_1 = math.radians(49.8333339)
LAT_2 = math.radians(51.16666723333333)
X_0 = 150000.013
Y_0 = 5400088.438
PIXEL_SIZE = 2.0
ORIGIN_X = 140000.0
ORIGIN_Y = 178000.0
EXPECTED_RASTER_SIZE = (10_000, 9_000)
EXPECTED_RASTER_MODE = "L"
SOURCE_METADATA_ID = "BRU_ENVI_73b4f29a-cff0-4d6a-a239-cb99d3140531"
SOURCE_LICENCE = "CC BY 4.0"
VALUE_SEMANTICS = "source-normalized 0–100 WBGT indicator; value 0 is source NoData, not degrees Celsius"


def m(lat: float) -> float:
    return math.cos(lat) / math.sqrt(1 - E * E * math.sin(lat) ** 2)


def t(lat: float) -> float:
    return math.tan(math.pi / 4 - lat / 2) / ((1 - E * math.sin(lat)) / (1 + E * math.sin(lat))) ** (E / 2)


N = math.log(m(LAT_1) / m(LAT_2)) / math.log(t(LAT_1) / t(LAT_2))
F = m(LAT_1) / (N * t(LAT_1) ** N)
RHO_0 = A * F * t(LAT_0) ** N


def geodetic_to_ecef(latitude: float, longitude: float, semi_major: float, flattening: float) -> tuple[float, float, float]:
    eccentricity_squared = flattening * (2 - flattening)
    radius = semi_major / math.sqrt(1 - eccentricity_squared * math.sin(latitude) ** 2)
    return (
        radius * math.cos(latitude) * math.cos(longitude),
        radius * math.cos(latitude) * math.sin(longitude),
        radius * (1 - eccentricity_squared) * math.sin(latitude),
    )


def solve_3x3(matrix: tuple[tuple[float, ...], ...], values: tuple[float, ...]) -> tuple[float, float, float]:
    """Solve the inverse Helmert matrix without an external CRS dependency."""
    rows = [list(matrix[index]) + [values[index]] for index in range(3)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda index: abs(rows[index][column]))
        rows[column], rows[pivot] = rows[pivot], rows[column]
        divisor = rows[column][column]
        rows[column] = [value / divisor for value in rows[column]]
        for index in range(3):
            if index == column:
                continue
            factor = rows[index][column]
            rows[index] = [rows[index][offset] - factor * rows[column][offset] for offset in range(4)]
    return tuple(rows[index][3] for index in range(3))


def ecef_to_geodetic(x: float, y: float, z: float, semi_major: float, flattening: float) -> tuple[float, float]:
    eccentricity_squared = flattening * (2 - flattening)
    longitude = math.atan2(y, x)
    horizontal = math.hypot(x, y)
    latitude = math.atan2(z, horizontal * (1 - eccentricity_squared))
    for _ in range(10):
        radius = semi_major / math.sqrt(1 - eccentricity_squared * math.sin(latitude) ** 2)
        updated = math.atan2(z + eccentricity_squared * radius * math.sin(latitude), horizontal)
        if abs(updated - latitude) < 1e-14:
            latitude = updated
            break
        latitude = updated
    return latitude, longitude


def wgs84_to_belgian72(latitude: float, longitude: float) -> tuple[float, float]:
    wgs84 = geodetic_to_ecef(math.radians(latitude), math.radians(longitude), WGS84_A, WGS84_F)
    translated = tuple(value - offset for value, offset in zip(wgs84, DATUM_TRANSLATION))
    rotation_x, rotation_y, rotation_z = DATUM_ROTATION
    scale = 1 + DATUM_SCALE
    # DATUM_* describes Belgian 1972 -> WGS84, so solve its matrix in reverse.
    matrix = (
        (scale, -rotation_z, rotation_y),
        (rotation_z, scale, -rotation_x),
        (-rotation_y, rotation_x, scale),
    )
    local_ecef = solve_3x3(matrix, translated)
    return ecef_to_geodetic(*local_ecef, A, F_LOCAL)


def wgs84_to_lambert72(latitude: float, longitude: float) -> tuple[float, float]:
    lat, lon = wgs84_to_belgian72(latitude, longitude)
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

    # The official source is exactly 10,000 × 9,000 pixels. Keep Pillow's
    # decompression-bomb protection enabled, with that verified size as the
    # maximum, and reject changed raster geometry before decoding all pixels.
    Image.MAX_IMAGE_PIXELS = math.prod(EXPECTED_RASTER_SIZE)
    with Image.open(args.raster) as source_image:
        if source_image.size != EXPECTED_RASTER_SIZE:
            raise RuntimeError(f"unexpected raster size {source_image.size}; expected {EXPECTED_RASTER_SIZE}")
        if source_image.mode != EXPECTED_RASTER_MODE:
            raise RuntimeError(f"unexpected raster mode {source_image.mode!r}; expected {EXPECTED_RASTER_MODE!r}")
        image = source_image.copy()

    source = json.loads(args.trees.read_text())
    records = []
    for tree in source["records"]:
        col, row = raster_pixel(tree["latitude"], tree["longitude"], *image.size)
        value = image.getpixel((col, row))
        records.append({**tree, "heat_pixel": value, "heat_pixel_column": col, "heat_pixel_row": row})

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "source": "urban_heat_islands_WBGT_MEAN_24082016_0-1_byte.tif",
        "source_metadata_id": SOURCE_METADATA_ID,
        "source_licence": SOURCE_LICENCE,
        "value_semantics": VALUE_SEMANTICS,
        "crs": "EPSG:31370",
        "coordinate_transform": "WGS84 to Belgian 1972 datum using the EPSG seven-parameter transform, then Belgian Lambert 72 projection",
        "sampling": "nearest raster pixel at tree point",
        "records": records,
    }, ensure_ascii=False, indent=2) + "\n")
    args.output.chmod(0o644)
    print(f"Joined {len(records)} tree points to heat pixels")


if __name__ == "__main__":
    main()
