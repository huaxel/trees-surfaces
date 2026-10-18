"""Draw a reproducible validation sample from the candidate frame.

The plan fixes a stratified, proportional, systematic design; this executes it. Two
stages, both deterministic given a seed:

1. strata receive points in proportion to their candidate counts in the frame (the
   population actually sampled, not the interval lengths the plan quotes as weights);
2. within a stratum, its points are split across the segments in proportion to each
   segment's candidate count, with every non-empty cell receiving at least one point so
   that no sampled street is left unvisited;
3. within a (stratum, segment) cell the draw is systematic with a random start, so every
   candidate in that cell has the same inclusion probability, equal to
   allocated / candidates, which is recorded per selected point.

The sample is therefore balanced across streets by construction, which is a survey
choice, not an estimate of canopy prevalence; stratum weights must be applied when
reporting frame-level proportions.
"""
import argparse
import json
import random
import tempfile
from pathlib import Path

from sampling_plan import largest_remainder
from metrics import require
from pipeline import encoded, rename_no_replace

FRAME_NAME = 'canopy-validation-frame.json'
SAMPLE_NAME = 'canopy-validation-sample.json'
MIN_PER_CELL = 1


def allocate_cells(candidates_by_cell, total):
    """Split `total` points across cells in proportion to candidates, at least one each.

    `candidates_by_cell` maps a (stratum, gid) cell to its candidate count. Returns a dict
    with the same keys. Proportionality is approximate when `total` is small relative to
    the number of cells, which is why the smallest cells are guaranteed a point first and
    the inclusion probability of every selected point is recorded.
    """
    require(total >= len(candidates_by_cell), 'total must cover at least one point per non-empty cell')
    keys = sorted(candidates_by_cell)
    counts = [candidates_by_cell[key] for key in keys]
    require(all(count > 0 for count in counts), 'cells must have candidates')
    allocation = {key: MIN_PER_CELL for key in keys}
    remaining = total - len(keys)
    if remaining:
        weights = [count - MIN_PER_CELL for count in counts]
        if sum(weights) == 0:
            weights = counts
        for key, extra in zip(keys, largest_remainder(weights, remaining)):
            allocation[key] += extra
    require(sum(allocation.values()) == total, 'cell allocation does not sum to the requested total')
    return allocation


def systematic_indices(candidates, count, rng):
    """`count` evenly spaced positions out of `candidates`, with a random start.

    The step can be fractional: the returned positions are the rounded multiples of the
    step plus a start drawn uniformly from [0, step), so each position is distinct while
    the sample stays spread across the cell.
    """
    require(0 < count <= candidates, 'count must lie within the cell')
    step = candidates / count
    start = rng.random() * step
    positions = []
    for index in range(count):
        position = min(candidates - 1, int(start + index * step))
        positions.append(position)
    require(len(set(positions)) == count, 'systematic draw produced duplicate positions')
    return sorted(positions)


def select(frame, total, seed):
    """Draw the sample. Returns selected points with their inclusion probability."""
    require(isinstance(seed, int), 'a seed is required so the draw is reproducible')
    points = frame['points']
    require(bool(points), 'frame has no candidates')
    cells = {}
    for index, point in enumerate(points):
        cells.setdefault((point['stratum'], point['gid']), []).append(index)
    candidates_by_cell = {key: len(value) for key, value in cells.items()}
    allocation = allocate_cells(candidates_by_cell, total)
    rng = random.Random(seed)
    selected = []
    for key in sorted(cells):
        indices = cells[key]
        count = allocation[key]
        require(count <= len(indices), f'cell {key} over-allocated')
        for position in systematic_indices(len(indices), count, rng):
            point = points[indices[position]]
            require((point['stratum'], point['gid']) == key, 'cell membership disagrees with the frame')
            selected.append(dict(point,
                                 cell=f'{key[0]}:{key[1]}',
                                 cell_candidates=len(indices),
                                 cell_allocated=count,
                                 inclusion_probability=round(count/len(indices), 8)))
    require(len({(row['gid'], row['chainage_m']) for row in selected}) == len(selected),
            'sample contains duplicate candidates')
    return sorted(selected, key=lambda row: (row['gid'], row['chainage_m']))


def build(frame_path, total, seed):
    frame = json.loads(Path(frame_path).read_text())
    require(frame['candidate_count'] == len(frame['points']), 'frame count disagrees with its points')
    selected = select(frame, total, seed)
    require(len(selected) == total, f'expected {total} points, selected {len(selected)}')
    strata = {}
    for row in selected:
        entry = strata.setdefault(row['stratum'], dict(points=0, frame_points=0))
        entry['points'] += 1
    for point in frame['points']:
        strata[point['stratum']]['frame_points'] += 1
    for name, entry in strata.items():
        entry['share_of_sample'] = round(entry['points']/total, 6)
        entry['share_of_frame'] = round(entry['frame_points']/frame['candidate_count'], 6)
        entry['design_weight'] = round(entry['share_of_frame']/entry['share_of_sample'], 6)
    by_segment = {}
    for row in selected:
        by_segment[row['gid']] = by_segment.get(row['gid'], 0) + 1
    return dict(schema_version=1, frame_sha256=__import__('hashlib').sha256(Path(frame_path).read_bytes()).hexdigest(),
                frame_manifest_sha256=frame['manifest_sha256'], frame_code_sha256=frame['frame_code_sha256'],
                seed=seed, requested=total, selected=len(selected), step_m=frame['step_m'],
                design='strata proportional to frame candidates; cells proportional across segments with at '
                       'least one point each; systematic with a random start within each cell',
                strata=strata, points_by_segment=by_segment, points=selected,
                limits=[
                    'The sample is balanced across streets by construction; it is not an estimate of canopy prevalence',
                    'Frame-level proportions need the recorded design weights, not the sample shares',
                    'Cells with few candidates receive a proportionally larger inclusion probability, which is recorded per point',
                    'A validation sample of positions is not a field protocol: access, safety and permission are separate',
                    'Labels do not exist yet; this artifact selects candidates to visit, nothing more',
                ])


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frame', type=Path, default=root/'data/research'/FRAME_NAME)
    parser.add_argument('--total', type=int, required=True, help='points to select')
    parser.add_argument('--seed', type=int, required=True, help='random start seed')
    parser.add_argument('--output', type=Path, required=True, help='New JSON file, never overwritten')
    args = parser.parse_args()
    require(not args.output.exists(), 'Output already exists')
    report = build(args.frame, args.total, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.sample-', dir=args.output.parent) as temp:
        staged = Path(temp)/SAMPLE_NAME
        staged.write_bytes(encoded(report))
        rename_no_replace(staged, args.output)
    print(json.dumps(dict(requested=report['requested'], selected=report['selected'],
                          seed=report['seed'], strata=report['strata'],
                          points_by_segment=report['points_by_segment']), indent=2))


if __name__ == '__main__':
    main()
