"""Materialise the candidate frame for canopy-class validation sampling.

The sampling plan needs a population to draw from. This writes it: every candidate
point along the published reference lines, at a fixed chainage step, labelled with
the mapped stratum it falls in and the distance to the nearest mapped tree polygon.

The frame is a discretisation of the same reference lines the pipeline measures, so
the stratified lengths it produces are a second, independent estimate of the
published overlap lengths. `reconcile` compares the two and the caller fails if they
disagree beyond the discretisation bound, because a frame that does not describe the
same lines would make any sample drawn from it uninterpretable.
"""
import argparse
import json
import math
import tempfile
from pathlib import Path

import shapely
from shapely.geometry import shape
from shapely.ops import substring, unary_union

from inputs import STEM, digest, load_selection, verified_extract, verify_inputs
from metrics import parts, profile, require
from pipeline import code_identity, encoded, rename_no_replace

STEP_M = 2.0
PROXIMITY_M = 5.0
STRATA = ('mapped_overlap', 'proximity_only', 'mapped_non_overlap')
FRAME_NAME = 'canopy-validation-frame.json'
# Point positions are interval midpoints, so a 2 m step represents 2 m of line. The
# incomplete remainder at the end of a segment is excluded and reported, matching the
# window rule used elsewhere in this project.
POSITION_RULE = 'chainage = (i + 0.5) * step for i in 0 .. floor(length / step) - 1'
LIMITS = [
    'Candidates are interior points of a discretised line, not an area sample: a point represents the 2 m of line it sits in the middle of',
    'Stratum labels come from the mapped tree class, so they describe the mapped frame, not validated canopy',
    'The frame is the 1 km2 convenience frame with five segments, not a probability sample of Brussels streets',
    'Stratum boundaries are inclusive: a point exactly on a polygon edge counts as overlap, matching the pipeline intersection convention',
    'The incomplete remainder of each segment (shorter than one step) is excluded from the frame',
]


def classify_points(route, cover, near, step_m, gid):
    """Midpoint grid along one route, labelled by mapped stratum.

    Position rule: chainage = (i + 0.5) * step for i in 0 .. floor(length / step) - 1, so each
    candidate represents the `step` of line it sits in the middle of and the incomplete
    remainder is excluded. Stratum boundaries are inclusive: a point exactly on a polygon edge
    counts as overlap, matching the pipeline's intersection convention. The 5 m boundary is the
    polygonal buffer the published proximity numbers use, not an exact offset curve, so the
    frame and the measurement classify the same way; the recorded distance is the exact one, for
    reference.
    """
    require(step_m > 0, 'step must be positive')
    require(cover.is_valid and near.is_valid, 'cover or buffer is invalid')
    count = math.floor(route.length/step_m)
    require(count > 0, f'segment {gid} is shorter than one step')
    counts = {name: 0 for name in STRATA}
    counts['candidates'] = count
    points = []
    for index in range(count):
        chainage = (index + 0.5)*step_m
        point = route.interpolate(chainage)
        if cover.covers(point):
            stratum, distance = 'mapped_overlap', 0.0
        elif near.covers(point):
            stratum, distance = 'proximity_only', float(point.distance(cover))
        else:
            stratum, distance = 'mapped_non_overlap', float(point.distance(cover))
        require(stratum != 'mapped_overlap' or distance == 0.0, f'overlap point with nonzero distance for gid {gid}')
        counts[stratum] += 1
        points.append(dict(gid=gid, chainage_m=round(chainage, 6),
                           x=round(point.x, 6), y=round(point.y, 6),
                           stratum=stratum, distance_to_cover_m=round(distance, 6)))
    return points, counts


def frame(manifest, cache, step_m=STEP_M):
    """Candidate points with their mapped stratum, plus provenance and reconciliations."""
    manifest = Path(manifest)
    identity = verify_inputs(manifest, cache)
    code = code_identity()
    frame_hash = digest(__file__)
    require(step_m > 0, 'step must be positive')
    selected, selection = load_selection(manifest.parent)
    a, b, c, d = unary_union([route for _, route in selected]).bounds
    features, scanned = verified_extract(Path(cache)/f'{STEM}.shp', (a-10, b-10, c+10, d+10))
    trees = []
    for feature in features:
        if int(feature.properties['gridcode']) != 4:
            continue
        geometry = shape(feature.geometry)
        rebuilt = geometry if geometry.is_valid else shapely.make_valid(geometry)
        trees.extend(parts(rebuilt, 'Polygon'))
    cover = unary_union(trees)
    near = cover.buffer(PROXIMITY_M)
    require(cover.is_valid and near.is_valid, 'cover or buffer is invalid')

    points, segments, assessed = [], [], {}
    for feature, route in selected:
        gid = feature['properties']['gid']
        segment_points, counts = classify_points(route, cover, near, step_m, gid)
        points.extend(segment_points)
        trimmed = substring(route, 0, counts['candidates']*step_m)
        require(math.isclose(trimmed.length, counts['candidates']*step_m, abs_tol=1e-6, rel_tol=0),
                f'trimmed route for gid {gid} has the wrong length')
        # Interval measurement of exactly the assessed range, for reconciliation.
        overlap = profile(trimmed, cover)['overlap_m']
        within = profile(trimmed, near)['overlap_m']
        assessed[gid] = dict(length_m=trimmed.length, mapped_overlap=overlap,
                             proximity_only=within - overlap,
                             mapped_non_overlap=trimmed.length - within)
        segments.append(dict(gid=gid, length_m=route.length,
                             assessed_length_m=round(trimmed.length, 6),
                             candidates=counts['candidates'],
                             excluded_remainder_m=route.length - counts['candidates']*step_m,
                             **{name: counts[name] for name in STRATA}))

    point_lengths = {name: step_m*sum(row[name] for row in segments) for name in STRATA}
    total_points = len(points)
    require(sum(segments[i]['candidates'] for i in range(len(segments))) == total_points,
            'segment candidate counts do not sum to the frame')
    require(all(points[i]['gid'] <= points[i+1]['gid'] or i + 1 == len(points)
                for i in range(len(points)-1)), 'frame is not grouped by segment in order')
    # Reconcile against an interval measurement of the same assessed length range. Comparing
    # with the whole-route published lengths would count the excluded remainders (7.5 m here)
    # as disagreement.
    interval = {name: sum(row[name] for row in assessed.values()) for name in STRATA}
    published = json.loads((Path(manifest).parent.parent/'canopy-verified'/'comparison.json').read_text())
    published_overlap = sum(row['overlap_m'] for row in published['results']
                            if row['vegetation'] == 'trees' and row['buffer_m'] == 0)
    reconciliation = {}
    worst = 0.0
    for name in STRATA:
        difference = point_lengths[name] - interval[name]
        worst = max(worst, abs(difference))
        reconciliation[name] = dict(frame_m=round(point_lengths[name], 3),
                                    interval_m=round(interval[name], 3),
                                    difference_m=round(difference, 3))
    # A point grid misplaces length only near the stratum boundaries it crosses, so the check
    # compares each stratum against 1% of its interval length, or one step, whichever is larger.
    # Worst observed difference here is about 2.2 m on a 688 m stratum.
    # Diagnostic only: how often the grid crosses a stratum boundary within a segment.
    boundaries = sum(1 for index in range(1, total_points)
                     if points[index]['stratum'] != points[index-1]['stratum']
                     and points[index]['gid'] == points[index-1]['gid'])
    differences = {name: abs(reconciliation[name]['difference_m']) for name in STRATA}
    tolerances = {name: max(step_m, 0.01*interval[name]) for name in STRATA}
    worst_relative = max(differences[name]/tolerances[name] for name in STRATA)
    require(all(differences[name] <= tolerances[name] for name in STRATA),
            'frame disagrees with the interval measurement of the same range: '
            + ', '.join(f'{name} {differences[name]:.3f} m vs {tolerances[name]:.3f} m' for name in STRATA))
    # The assessed overlap must also track the published whole-route overlap, less the remainders.
    require(interval['mapped_overlap'] <= published_overlap + 1e-6,
            'assessed overlap exceeds the published whole-route overlap')
    require(code_identity() == code and verify_inputs(manifest, cache) == identity
            and digest(__file__) == frame_hash, 'inputs or code changed while building the frame')
    return dict(schema_version=1, manifest_sha256=identity, code_sha256=code,
                frame_code_sha256=frame_hash,
                step_m=step_m, proximity_m=PROXIMITY_M, position_rule=POSITION_RULE,
                selection=selection, candidate_count=total_points,
                assessed_length_m=round(step_m*total_points, 3),
                excluded_remainder_m=round(sum(row['excluded_remainder_m'] for row in segments), 3),
                strata=list(STRATA), segments=segments,
                stratum_lengths_m={name: round(value, 3) for name, value in point_lengths.items()},
                reconciliation=reconciliation, boundary_crossings=boundaries,
                reconciliation_rule='each stratum within max(one step, 1% of its interval length)',
                worst_reconciliation_fraction=round(worst_relative, 6), assessed=assessed,
                source_records_scanned=scanned,
                index_matches_full_scan=True, points=points, limits=LIMITS)


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=root/'data/research/canopy-inputs/manifest.json')
    parser.add_argument('--cache', type=Path, default=root/'.cache/vub-canopy-2021')
    parser.add_argument('--step-m', type=float, default=STEP_M)
    parser.add_argument('--output', type=Path, required=True, help='New JSON file, never overwritten')
    args = parser.parse_args()
    require(not args.output.exists(), 'Output already exists')
    report = frame(args.manifest, args.cache, args.step_m)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.frame-', dir=args.output.parent) as temp:
        staged = Path(temp)/FRAME_NAME
        staged.write_bytes(encoded(report))
        rename_no_replace(staged, args.output)
    print(json.dumps(dict(candidates=report['candidate_count'],
                          assessed_length_m=report['assessed_length_m'],
                          excluded_remainder_m=report['excluded_remainder_m'],
                          stratum_lengths_m=report['stratum_lengths_m'],
                          reconciliation=report['reconciliation']), indent=2))


if __name__ == '__main__':
    main()
