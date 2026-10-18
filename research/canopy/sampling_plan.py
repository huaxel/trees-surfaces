"""Arithmetic for planning a canopy-class validation sample.

This module computes sample sizes and a stratified allocation for validating the
mapped tree-canopy class along the published reference lines. It is planning
arithmetic only: no reference labels exist yet, and nothing here estimates
accuracy. Standard library only, so the canopy lockfile and the published
artifact's recorded code identity do not change.

The estimand is the line-length-weighted proportion of reference line that
intersects mapped tree-class canopy at buffer 0, with omission and commission
reported separately. Because the unit is a point on a line, the required sample
size is driven by the precision target chosen for that proportion, not by the
number of polygons.
"""
import json
import math
from pathlib import Path

Z_95 = 1.959963984540054


def required_sample_size(half_width, prevalence, design_effect=1.0, z=Z_95):
    """Independent point samples for a 95% interval half-width on a proportion.

    Uses the normal approximation for planning, then callers should report Wilson
    intervals on the realised sample. `design_effect` inflates the requirement for
    clustering along a street: n_effective = n / design_effect.
    """
    require(0 < prevalence < 1, 'prevalence must be a proportion strictly between 0 and 1')
    require(0 < half_width < 1, 'half_width must be a proportion strictly between 0 and 1')
    require(design_effect >= 1, 'design_effect cannot be below 1; clustering cannot reduce the requirement')
    independent = (z * z) * prevalence * (1 - prevalence) / (half_width * half_width)
    return math.ceil(design_effect * independent)


def wilson_interval(successes, total, z=Z_95):
    """Wilson score interval, which stays inside [0, 1] near 0 and 1."""
    require(total > 0, 'total must be positive')
    require(0 <= successes <= total, 'successes must lie within the sample')
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    spread = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - spread), min(1.0, centre + spread)


def largest_remainder(weights, total):
    """Allocate `total` units proportionally to `weights`, deterministically.

    Ties break by descending weight then by position, so the allocation is
    reproducible rather than dependent on dictionary order.
    """
    require(total > 0, 'total must be positive')
    require(all(weight >= 0 for weight in weights), 'weights must be nonnegative')
    size = sum(weights)
    require(size > 0, 'weights must not all be zero')
    exact = [weight * total / size for weight in weights]
    floors = [math.floor(value) for value in exact]
    remainder = total - sum(floors)
    order = sorted(range(len(weights)), key=lambda index: (-(exact[index] - floors[index]), -weights[index], index))
    for index in order[:remainder]:
        floors[index] += 1
    return floors


def strata_from_published(path):
    """Measured stratum lengths along the reference lines, from the verified artifact.

    Overlap is the mapped tree-class buffer-0 intersection; proximity-only is the
    additional length inside the 5 m buffer; non-overlap is the rest. These are
    mapped lengths, not validated ones: they define the frame and its weights.
    """
    report = json.loads(Path(path).read_text())
    trees = [row for row in report['results'] if row['vegetation'] == 'trees']
    require(bool(trees), 'published artifact has no tree rows')
    per_gid = {}
    for row in trees:
        entry = per_gid.setdefault(row['gid'], dict(gid=row['gid'], length_m=row['length_m'], buffers={}))
        require(entry['length_m'] == row['length_m'], f'inconsistent length for gid {row["gid"]}')
        entry['buffers'][row['buffer_m']] = row['overlap_m']
    rows = []
    for gid in sorted(per_gid):
        entry = per_gid[gid]
        buffers = entry['buffers']
        require(0 in buffers and 5 in buffers, f'gid {gid} lacks the 0 m or 5 m buffer row')
        ordered = [buffers[key] for key in sorted(buffers)]
        require(all(later >= earlier - 1e-9 for earlier, later in zip(ordered, ordered[1:])),
                f'overlap is not monotone in the buffer for gid {gid}')
        row = dict(gid=gid, length_m=entry['length_m'], overlap_m=buffers[0],
                   within_5m_m=buffers[5])
        row['proximity_only_m'] = row['within_5m_m'] - row['overlap_m']
        row['non_overlap_m'] = row['length_m'] - row['within_5m_m']
        require(row['proximity_only_m'] >= -1e-9 and row['non_overlap_m'] >= -1e-9,
                f'negative stratum length for gid {gid}')
        for key in ('overlap_m', 'proximity_only_m', 'non_overlap_m'):
            row[key] = max(0.0, row[key])
        rows.append(row)
    return rows


def stratum_totals(rows):
    totals = {'mapped_overlap': 0.0, 'proximity_only': 0.0, 'mapped_non_overlap': 0.0}
    for row in rows:
        totals['mapped_overlap'] += row['overlap_m']
        totals['proximity_only'] += row['proximity_only_m']
        totals['mapped_non_overlap'] += row['non_overlap_m']
    return totals


def require(condition, message):
    if not condition:
        raise ValueError(message)


def plan(artifact, half_width, prevalence, design_effect, step_m):
    """Full planning output: precision requirement, frame, strata and allocation."""
    rows = strata_from_published(artifact)
    totals = stratum_totals(rows)
    frame_m = sum(row['length_m'] for row in rows)
    independent = required_sample_size(half_width, prevalence, design_effect=1.0)
    clustered = required_sample_size(half_width, prevalence, design_effect=design_effect)
    names = sorted(totals, key=lambda name: -totals[name])
    allocation = largest_remainder([totals[name] for name in names], clustered)
    per_stratum = {}
    for name, count in zip(names, allocation):
        length = totals[name]
        step = length / count if count else None
        per_stratum[name] = dict(length_m=length, share=length / frame_m, points=count,
                                 systematic_step_m=step)
    return dict(
        frame_m=frame_m, segments=len(rows), step_m=step_m,
        candidates=math.floor(frame_m / step_m) + 1,
        precision=dict(half_width=half_width, prevalence=prevalence, design_effect=design_effect,
                       independent_points=independent, clustered_points=clustered),
        strata=per_stratum, segments_detail=rows,
    )


def main():
    root = Path(__file__).resolve().parents[2]
    artifact = root/'data/research/canopy-verified/comparison.json'
    print('Precision requirement: independent points for a 95% half-width on a proportion')
    print(f"  {'prevalence':>11} {'±5 pp':>7} {'±7.5 pp':>9} {'±10 pp':>8} {'deff=3 @ ±7.5 pp':>18}")
    for prevalence in (0.1, 0.25, 0.5):
        cells = [required_sample_size(half_width, prevalence) for half_width in (0.05, 0.075, 0.10)]
        clustered = required_sample_size(0.075, prevalence, design_effect=3)
        print(f'  {prevalence:>11.2f} {cells[0]:>7} {cells[1]:>9} {cells[2]:>8} {clustered:>18}')
    print('\nWilson check at the largest of those sizes (p=0.5):')
    for total in (97, 153, 384):
        low, high = wilson_interval(total//2, total)
        print(f'  n={total:>3} -> 95% interval {(high - low) / 2 * 100:.2f} pp half-width')
    print('\nFrame and strata (measured mapped lengths in the published artifact)')
    result = plan(artifact, half_width=0.075, prevalence=0.25, design_effect=3, step_m=2.0)
    print(f"  frame {result['frame_m']:.1f} m over {result['segments']} segments; "
          f"{result['candidates']} candidate {result['step_m']:.0f} m chainage points")
    for name, values in sorted(result['strata'].items(), key=lambda item: -item[1]['length_m']):
        step = values['systematic_step_m']
        print(f"  {name:>20}: {values['length_m']:7.1f} m ({100 * values['share']:5.1f}%), "
              f"{values['points']:3d} points"
              + (f", every {step:.1f} m" if step else ''))
    print(f"  total requested: {result['precision']['clustered_points']} points "
          f"(design effect {result['precision']['design_effect']})")


if __name__ == '__main__':
    main()
