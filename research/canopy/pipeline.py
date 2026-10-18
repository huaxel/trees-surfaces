"""One offline execution; windows cannot silently load different source files."""
import hashlib
import json
import math
import platform
import statistics
from pathlib import Path

import fiona
import shapely
from shapely.geometry import shape
from shapely.ops import substring, unary_union
from shapely.validation import explain_validity

from inputs import STEM, digest, load_selection, verified_extract, verify_inputs
from metrics import parts, profile, require

LIMITS = [
    'Local convenience-centred frame; adjacent segments are not independent observations',
    'Current reference-line geometry over 2021 vegetation, not historical cyclist exposure',
    'Mapped polygon overlap/proximity is not shade, cooling, or validated vegetation absence',
    'Source coverage, classification and positional uncertainty remain unresolved',
    'The record scan checks the spatial index; feature reads still share the SHX/Fiona path',
    'The sample includes a recorded 2022 start; start dates are approximate',
]


def encoded(value):
    return (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()


def code_identity():
    root = Path(__file__).parent
    names = ('metrics.py', 'inputs.py', 'pipeline.py', 'run.py', 'pyproject.toml', 'uv.lock', '.python-version')
    return {name: digest(root/name) for name in names}


def execute(manifest, cache):
    manifest = Path(manifest)
    identity = verify_inputs(manifest, cache)
    sources = json.loads(manifest.read_text())
    code = code_identity()
    selected, request = load_selection(manifest.parent)
    a, b, c, d = unary_union([route for _, route in selected]).bounds
    bounds = (a-10, b-10, c+10, d+10)
    features, records = verified_extract(Path(cache)/f'{STEM}.shp', bounds)
    groups, alternatives, repairs = {3: [], 4: []}, {3: [], 4: []}, []
    for feature in features:
        category = int(feature.properties['gridcode'])
        require(category in (1, 2, 3, 4), 'Unexpected vegetation class')
        if category not in groups:
            continue
        geometry = shape(feature.geometry)
        repaired = geometry if geometry.is_valid else shapely.make_valid(geometry)
        polygons = unary_union(parts(repaired, 'Polygon'))
        require(polygons.is_valid, 'Repair did not produce valid polygonal cover')
        alternative = geometry if geometry.is_valid else geometry.buffer(0)
        if not geometry.is_valid:
            repairs.append(dict(id=feature.id, category=category,
                                reason=explain_validity(geometry),
                                original_area_m2=geometry.area, repaired_area_m2=polygons.area,
                                repair_type=repaired.geom_type,
                                polygon_parts=len(parts(repaired, 'Polygon')),
                                discarded_linear_length_m=sum(p.length for p in parts(repaired, 'LineString')),
                                discarded_point_count=len(parts(repaired, 'Point')),
                                alternative_symmetric_difference_m2=polygons.symmetric_difference(alternative).area))
        groups[category].append(polygons)
        alternatives[category].append(alternative)
    rows, tree_covers = [], {}
    for name, categories in [('trees', [4]), ('trees_and_high_shrubs', [3, 4])]:
        cover = unary_union([g for category in categories for g in groups[category]])
        alternate = unary_union([g for category in categories for g in alternatives[category]])
        for distance in (0, 2, 5):
            buffered = cover if distance == 0 else cover.buffer(distance)
            other = alternate if distance == 0 else alternate.buffer(distance)
            if name == 'trees':
                tree_covers[distance] = buffered
            for feature, route in selected:
                result, check = profile(route, buffered), profile(route, other)
                rows.append(dict(gid=feature['properties']['gid'],
                                 begin_date=feature['properties']['begin_date'], length_m=route.length,
                                 vegetation=name, buffer_m=distance,
                                 overlap_m=result['overlap_m'], overlap_percent=result['overlap_percent'],
                                 longest_nonoverlap_m=result['longest_nonoverlap_m'],
                                 repair_sensitivity_overlap_m=check['overlap_m']-result['overlap_m'],
                                 repair_sensitivity_longest_nonoverlap_m=check['longest_nonoverlap_m']-result['longest_nonoverlap_m']))
    provenance = dict(manifest_sha256=identity, inputs=sources['files'],
                      source_provenance=sources['provenance'], code_sha256=code,
                      environment=dict(python=platform.python_version(), fiona=fiona.__version__,
                                       gdal=fiona.__gdal_version__, shapely=shapely.__version__,
                                       geos=shapely.geos_version_string, platform=platform.platform()),
                      parameters=dict(crs='EPSG:31370', margin_m=10, buffers_m=[0, 2, 5],
                                      window_m=100, min_segment_m=100, type_code=12, status_code=1))
    comparison = dict(schema_version=1, provenance=provenance, selection=request,
                      selected_gids=[f['properties']['gid'] for f, _ in selected],
                      sample_size=len(selected), extraction_bounds=bounds,
                      source_records_scanned=records, extraction_polygon_count=len(features),
                      index_matches_full_scan=True, repair_audit=repairs, results=rows, limits=LIMITS)
    windows, summaries = [], []
    for feature, route in selected:
        gid = feature['properties']['gid']
        count, segment_rows = math.floor(route.length/100), []
        for anchor in ('source_start', 'source_end'):
            oriented = route if anchor == 'source_start' else shapely.reverse(route)
            for i in range(count):
                window = substring(oriented, 100*i, 100*(i+1))
                require(math.isclose(window.length, 100, abs_tol=1e-7, rel_tol=0),
                        'Window length differs from 100 m')
                for distance in (0, 5):
                    result = profile(window, tree_covers[distance])
                    row = dict(gid=gid, anchor=anchor, window_index=i, start_m=100*i,
                               end_m=100*(i+1), buffer_m=distance,
                               overlap_percent=result['overlap_percent'],
                               longest_nonoverlap_m=result['longest_nonoverlap_m'])
                    windows.append(row)
                    segment_rows.append(row)
        for distance in (0, 5):
            values = [r for r in segment_rows if r['buffer_m'] == distance]
            summaries.append(dict(gid=gid, buffer_m=distance, windows_per_anchor=count,
                                  excluded_remainder_m=route.length-count*100,
                                  overlap_percent_range=[min(r['overlap_percent'] for r in values), max(r['overlap_percent'] for r in values)],
                                  median_overlap_by_anchor={anchor: statistics.median(r['overlap_percent'] for r in values if r['anchor'] == anchor)
                                                            for anchor in ('source_start', 'source_end')},
                                  longest_nonoverlap_range_m=[min(r['longest_nonoverlap_m'] for r in values), max(r['longest_nonoverlap_m'] for r in values)]))
    window_report = dict(schema_version=1, provenance=provenance,
                         comparison_sha256=hashlib.sha256(encoded(comparison)).hexdigest(),
                         window_length_m=100,
                         method='Nonoverlapping full windows from each endpoint separately; incomplete remainders excluded; anchor schemes overlap and are not independent samples',
                         windows_per_anchor=sum(math.floor(r.length/100) for _, r in selected),
                         total_segment_length_m=sum(r.length for _, r in selected),
                         analysed_length_per_anchor_m=100*sum(math.floor(r.length/100) for _, r in selected),
                         summaries=summaries, windows=windows,
                         limits=LIMITS+['Remainders excluded; not every possible window placement tested'])
    # Detect modifications during the run before publishing either result.
    require(verify_inputs(manifest, cache) == identity, 'Inputs or manifest changed during execution')
    require(code_identity() == code, 'Pipeline code changed during execution')
    return comparison, window_report


def rename_no_replace(source, destination):
    """Linux renameat2: publish the pair atomically, never replace even an empty dir."""
    import ctypes
    import os
    require(platform.system() == 'Linux', 'Atomic no-replace publication currently requires Linux')
    libc = ctypes.CDLL(None, use_errno=True)
    require(hasattr(libc, 'renameat2'), 'libc renameat2 is required for safe publication')
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))


def publish(directory, comparison, windows):
    require(windows['comparison_sha256'] == hashlib.sha256(encoded(comparison)).hexdigest(),
            'Window report does not match comparison')
    require(windows['provenance'] == comparison['provenance'], 'Stage provenance differs')
    directory = Path(directory)
    require(not directory.exists(), 'Output directory already exists; use a fresh directory')
    directory.parent.mkdir(parents=True, exist_ok=True)
    # Both result files become visible together, after all validation succeeds.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='.canopy-', dir=directory.parent) as temp:
        root = Path(temp)/'result'
        root.mkdir()
        (root/'comparison.json').write_bytes(encoded(comparison))
        (root/'windows.json').write_bytes(encoded(windows))
        rename_no_replace(root, directory)
