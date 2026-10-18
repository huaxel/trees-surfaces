"""Measure the design effect the sampling plan currently assumes.

The plan prices a ±7.5 pp interval at 385 points *given a design effect of 3*, and says in
the same breath that the design effect must be estimated rather than assumed. This
estimates the part of it that can be estimated without labels: the variance inflation
caused by clustering along the street, computed from the committed 2 m frame.

What is measured: the class indicator along each published segment, sampled systematically
with a common step and an independent random start per segment, which is the field design's
spatial structure with the class strata removed. The variance of the proportion across
random starts is compared with the simple-random-sample variance for the same n. Removing
the strata is deliberate — stratifying on the mapped class would make the *mapped*
proportion nearly variance-free and flatter the estimate, while the estimand is the
*reference* proportion, whose relationship to the mapped class is exactly what labels would
establish.

What this cannot measure: the stratification gain for the reference proportion, the
clustering of reference-class *errors* (omission and commission are spatially structured
too, and are not visible here), or anything about a class other than the mapped one at
these five segments. A measured design effect above 3 does not prove the plan is wrong; it
shows that its cost figure rests on an assumption smaller than the clustering in the data.
"""
import argparse
import json
import math
import random
from pathlib import Path

from metrics import require
from sampling_plan import largest_remainder, required_sample_size
from selection import systematic_indices

FRAME_NAME = 'canopy-validation-frame.json'
CANOPY_STRATUM = 'mapped_overlap'


def segment_series(frame):
    """Per-segment binary canopy indicator in chainage order."""
    series = {}
    for point in sorted(frame['points'], key=lambda p: (p['gid'], p['chainage_m'])):
        series.setdefault(point['gid'], []).append(1 if point['stratum'] == CANOPY_STRATUM else 0)
    return series


def allocate(series, total):
    """Split `total` draws across segments in proportion to candidate counts."""
    keys = sorted(series)
    counts = [len(series[key]) for key in keys]
    require(total <= sum(counts), 'cannot draw more points than the frame holds')
    base = [max(1, int(round(total*count/sum(counts)))) for count in counts]
    while sum(base) > total:
        index = max(range(len(base)), key=lambda i: base[i])
        base[index] -= 1
    if sum(base) < total:
        for index, extra in enumerate(largest_remainder(counts, total - sum(base))):
            base[index] += extra
    require(sum(base) == total, 'segment allocation does not sum to the requested total')
    return dict(zip(keys, base))


def systematic_proportion(series, total, rng):
    """One draw of the design: a systematic sample with a random start per segment."""
    allocation = allocate(series, total)
    covered = drawn = 0
    for key in sorted(series):
        values = series[key]
        count = allocation[key]
        for position in systematic_indices(len(values), count, rng):
            covered += values[position]
            drawn += 1
    require(drawn == total, f'design drew {drawn} points for a total of {total}')
    return covered/drawn


def lag_autocorrelation(series, max_lag):
    """Autocorrelation of the indicator at lags 1..max_lag, computed within segments.

    Pooling the segments first would mix their very different canopy proportions and hold
    the correlation near a large constant value at every lag — an earlier version did
    exactly that and produced an absurd design effect. Each segment's correlation is
    therefore computed about its own mean and averaged weighted by available pairs.
    """
    totals, counts = {}, {}
    for values in series.values():
        mean = sum(values)/len(values)
        variance = sum((value-mean)**2 for value in values)/len(values)
        if variance == 0:
            continue     # a segment with no variation carries no information about lag
        for lag in range(1, max_lag+1):
            pairs = len(values)-lag
            if pairs < 8:
                break
            covariance = sum((values[i]-mean)*(values[i+lag]-mean)
                             for i in range(pairs))/pairs
            totals[lag] = totals.get(lag, 0.0)+(covariance/variance)*pairs
            counts[lag] = counts.get(lag, 0)+pairs
    require(bool(counts), 'no segment varies; autocorrelation is undefined')
    return [totals[lag]/counts[lag] for lag in sorted(counts)]


def distinct_realisations(series, total, seed, trials=400):
    """How many distinct systematic samples each segment produced in `trials` seeded draws.

    This is a lower bound on what the segment can produce, not the exhaustive count: segment
    266 allows 281 samples and shows 215 at 400 trials. It is enough for its purpose, which is
    to spot a step whose small denominator, such as 5/3, repeats five samples forever and so
    makes a variance across random starts say little about that segment.
    """
    allocation = allocate(series, total)
    rng = random.Random(seed)
    seen = {key: set() for key in series}
    for _ in range(trials):
        for key in sorted(series):
            positions = systematic_indices(len(series[key]), allocation[key], rng)
            seen[key].add(tuple(positions))
    return {key: dict(allocated=allocation[key], candidates=len(series[key]),
                      step=round(len(series[key])/allocation[key], 4),
                      distinct=len(seen[key]),
                      varies=len(set(series[key])) > 1)
            for key in sorted(series)}


def measure(frame, total, draws, seed):
    series = segment_series(frame)
    points = frame['points']
    canopy = sum(1 for point in points if point['stratum'] == CANOPY_STRATUM)
    prevalence = canopy/len(points)
    rng = random.Random(seed)
    estimates = [systematic_proportion(series, total, rng) for _ in range(draws)]
    mean = sum(estimates)/len(estimates)
    variance = sum((value-mean)**2 for value in estimates)/(len(estimates)-1)
    # Two distinct baselines, because they answer different questions and differ by the
    # sampling fraction, which is large here: 385 of 644 candidates is 60%.
    srswr_variance = prevalence*(1-prevalence)/total
    fraction = total/len(points)
    srswor_variance = srswr_variance*(len(points)-total)/(len(points)-1)
    step = frame['assessed_length_m']/total
    spacing_lags = step/frame['step_m']
    realisations = distinct_realisations(series, total, seed)
    rhos = lag_autocorrelation(series, max_lag=min(200, max(len(v) for v in series.values()))-8)
    runs = []
    for key in sorted(series):
        values = series[key]
        length = run = 1
        for previous, current in zip(values, values[1:]):
            if current == previous:
                run += 1
            else:
                runs.append((previous, run))
                run = 1
        runs.append((values[-1], run))
    canopy_runs = [run for label, run in runs if label == 1]
    mean_run = sum(canopy_runs)/len(canopy_runs) if canopy_runs else 0.0
    return dict(
        schema_version=2,
        frame_manifest_sha256=frame['manifest_sha256'],
        frame_code_sha256=frame['frame_code_sha256'],
        candidate_count=len(points), assessed_length_m=frame['assessed_length_m'],
        step_m=frame['step_m'], canopy_candidates=canopy,
        frame_prevalence=round(prevalence, 6),
        sample_size=total, sampling_fraction=round(fraction, 6),
        sampling_step_m=round(step, 4), spacing_lags=round(spacing_lags, 4),
        draws=draws, seed=seed,
        design='systematic with a common step and an independent random start per segment, '
               'segment allocations proportional to candidate counts, no class strata',
        mean_estimate=round(mean, 6),
        variance=round(variance, 10),
        srswr_variance=round(srswr_variance, 10),
        srswor_variance=round(srswor_variance, 10),
        # Diagnostics, not headlines. A segment whose step has a small denominator yields few
        # distinct systematic samples, and across-start variance is then unreliable rather than
        # systematically low: forty synthetic i.i.d. frames with an integral step spanned
        # 0.14-3.2 around a true 1.0. `distinct_realisations` measures this directly instead of
        # guessing from the step, because the step is per segment and the global ratio hides it.
        distinct_realisations=realisations,
        few_distinct_realisations=any(entry['distinct'] < 20 and entry['varies']
                                      for entry in realisations.values()),
        design_effect=round(variance/srswr_variance, 4),
        design_effect_finite=round(variance/srswor_variance, 4),
        # A crude bound, not an estimate: for an infinite population, systematic sampling
        # from an autocorrelated series inflates variance by roughly patch length / step.
        # It is reported because it reproduces the magnitude the plan assumes; it is not
        # used for the cost tables.
        inflation_for_random_placement=round(1 + mean_run*frame['step_m']/step, 4),
        variance_mc_standard_error=round(variance*math.sqrt(2/(len(estimates)-1)), 12),
        estimate_range=[round(min(estimates), 6), round(max(estimates), 6)],
        estimate_quantiles={q: round(sorted(estimates)[int(q/100*(len(estimates)-1))], 6)
                            for q in (2.5, 25, 50, 75, 97.5)},
        lag_autocorrelation={f'lag_{i}': round(rho, 4) for i, rho in enumerate(rhos[:24], start=1)},
        canopy_runs=dict(count=len(canopy_runs),
                         mean_length_frames=round(mean_run, 2),
                         longest_frames=max(canopy_runs) if canopy_runs else 0,
                         mean_length_m=round(mean_run*frame['step_m'], 2)),
        limits=[
            'Measures clustering of the mapped class along these five segments, not of reference labels',
            'Removes the class strata, so it cannot measure stratification gain for the reference proportion',
            'Reference omission and commission are spatially structured too and are invisible here',
            'The finite-population reading treats the frame itself as the population; the infinite reading treats these streets as a sample from a broader population, and only the second matches the plan',
            'Five convenience segments are not a sample of Brussels streets',
            'The variance across starting points is a diagnostic: a segment with few distinct realisations makes it unreliable, not biased (synthetic i.i.d. frames spanned 0.14-3.2 around a true 1.0)',
            'inflation_for_random_placement applies to randomly placed points, which is the implicit model of the plan, not to its systematic design',
            'Monte-Carlo precision is reported; it is not a sampling-theory confidence interval',
            'A lag-sum (spectral) estimator was implemented and dropped: these segments are too',
            'short for stable long-lag autocorrelation and it returned impossible negative inflation',
        ],
    )


def cost_table(design_effect, prevalences=(0.10, 0.14, 0.25, 0.50),
               half_widths=(0.05, 0.075, 0.10)):
    """Required independent points, with inflation clamped at 1 as the planner requires."""
    design_effect = max(1.0, design_effect)
    return {f'{prevalence:.2f}': {f'{int(hw*100)} pp': required_sample_size(hw, prevalence, design_effect)
                                  for hw in half_widths}
            for prevalence in prevalences}


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frame', type=Path, default=root/'data/research'/FRAME_NAME)
    parser.add_argument('--total', type=int, default=385, help='points the plan prices')
    parser.add_argument('--draws', type=int, default=4000)
    parser.add_argument('--seed', type=int, default=20261018)
    parser.add_argument('--output', type=Path, help='new JSON file, never overwritten')
    args = parser.parse_args()
    require(args.draws >= 100, 'need at least 100 draws for a usable variance')
    frame = json.loads(args.frame.read_text())
    require(frame['candidate_count'] == len(frame['points']), 'frame count disagrees with its points')
    report = measure(frame, args.total, args.draws, args.seed)
    report['cost_at_assumed_design_effect_3'] = cost_table(3.0)
    report['cost_at_measured_inflation_for_random_placement'] = cost_table(
        report['inflation_for_random_placement'])
    # The finite-frame effect is below 1, so this table is the no-inflation column; the key
    # says so rather than implying an estimate at 0.27 was computed.
    report['cost_at_finite_design_effect_clamped_to_1'] = cost_table(report['design_effect_finite'])
    report['finite_design_effect_note'] = (
        f"design_effect_finite {report['design_effect_finite']} is below 1, so the clamped cost "
        'table equals the no-inflation column; the planner cannot price a sub-unit effect')
    if args.output:
        require(not args.output.exists(), 'output already exists')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2)+'\n')
        print(f'wrote {args.output}')
    else:
        print(json.dumps(report, indent=2)[:4000])


if __name__ == '__main__':
    main()
