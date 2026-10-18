"""Fixed registration stress tests, not calibrated error bounds or cyclist paths."""
import argparse
import hashlib
import json
import math
import tempfile
from pathlib import Path

import fiona
import shapely
from shapely.affinity import translate
from shapely.geometry import shape
from shapely.ops import unary_union

from inputs import STEM, digest, load_selection, verified_extract, verify_inputs
from metrics import parts, profile, require
from pipeline import code_identity, encoded, rename_no_replace

SCENARIOS = [('original', 0, 0)] + [
    (f'{direction}_{distance}m', dx*distance, dy*distance)
    for distance in (2, 5)
    for direction, dx, dy in [('east', 1, 0), ('west', -1, 0), ('north', 0, 1), ('south', 0, -1)]
]


def shifted_profiles(route, cover):
    rows = []
    for name, dx, dy in SCENARIOS:
        moved = translate(route, xoff=dx, yoff=dy)
        require(math.isclose(moved.length, route.length, rel_tol=0, abs_tol=1e-6),
                'Translation changed length')
        result = profile(moved, cover)
        rows.append(dict(scenario=name, dx_m=dx, dy_m=dy,
                         overlap_percent=result['overlap_percent'],
                         longest_nonoverlap_m=result['longest_nonoverlap_m']))
    return rows


def audit(manifest, cache):
    manifest = Path(manifest)
    identity = verify_inputs(manifest, cache)
    code = code_identity()
    own_hash = digest(__file__)
    selected, selection = load_selection(manifest.parent)
    a, b, c, d = unary_union([r for _, r in selected]).bounds
    bounds = (a-10, b-10, c+10, d+10)
    require(max(math.hypot(dx, dy) for _, dx, dy in SCENARIOS) < 10,
            'Extraction margin does not cover displacement scenarios')
    features, scanned = verified_extract(Path(cache)/f'{STEM}.shp', bounds)
    trees, alternatives = [], []
    for feature in features:
        if int(feature.properties['gridcode']) != 4:
            continue
        geometry = shape(feature.geometry)
        trees.extend(parts(shapely.make_valid(geometry), 'Polygon'))
        alternatives.append(geometry if geometry.is_valid else geometry.buffer(0))
    cover, alternate = unary_union(trees), unary_union(alternatives)
    rows, summary = [], []
    for feature, route in selected:
        gid = feature['properties']['gid']
        values, other = shifted_profiles(route, cover), shifted_profiles(route, alternate)
        for row, alternative in zip(values, other):
            row.update(gid=gid, length_m=route.length,
                       alternative_repair_overlap_delta_pp=alternative['overlap_percent']-row['overlap_percent'],
                       alternative_repair_longest_nonoverlap_delta_m=alternative['longest_nonoverlap_m']-row['longest_nonoverlap_m'])
        rows.extend(values)
        summary.append(dict(gid=gid, original_overlap_percent=values[0]['overlap_percent'],
                            ranges={str(distance): [min(v['overlap_percent'] for v in values if math.hypot(v['dx_m'], v['dy_m']) == distance),
                                                    max(v['overlap_percent'] for v in values if math.hypot(v['dx_m'], v['dy_m']) == distance)]
                                    for distance in (2, 5)}))
    require(verify_inputs(manifest, cache) == identity, 'Inputs changed during audit')
    require(code_identity() == code and digest(__file__) == own_hash, 'Code changed during audit')
    return dict(schema_version=1, manifest_sha256=identity, code_sha256=code,
                audit_code_sha256=own_hash, selection=selection,
                environment=dict(fiona=fiona.__version__, shapely=shapely.__version__, geos=shapely.geos_version_string),
                source_records_scanned=scanned, index_matches_full_scan=True,
                scenarios=SCENARIOS, results=rows, summary=summary,
                limitations=['Fixed cardinal translations of each complete reference line; not observed bicycle positions',
                             '2 m and 5 m are uncalibrated stress magnitudes, not confidence bounds or measured error',
                             'Range excludes the original position and is not exhaustive over directions or offsets',
                             'Translated lines can leave the carriageway; do not interpret these as exposure estimates',
                             'No correction selected from these scenarios; original results and operational ranking unchanged',
                             'Other canopy sample, classification, temporal, and shade limitations remain'])


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=root/'data/research/canopy-inputs/manifest.json')
    parser.add_argument('--cache', type=Path, default=root/'.cache/vub-canopy-2021')
    parser.add_argument('--output', type=Path, required=True, help='New JSON file, never overwritten')
    args = parser.parse_args()
    require(not args.output.exists(), 'Output already exists')
    report = audit(args.manifest, args.cache)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.alignment-', dir=args.output.parent) as temp:
        staged = Path(temp)/'report.json'
        staged.write_bytes(encoded(report))
        rename_no_replace(staged, args.output)
    print(json.dumps(report['summary'], indent=2))


if __name__ == '__main__':
    main()
