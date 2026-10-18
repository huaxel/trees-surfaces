"""Estimate a proportion from the validation sample, with unequal inclusion probabilities.

The selection gives cells different inclusion probabilities — a cell with few candidates is
sampled at or near certainty — so a plain count of labelled points is not a design-consistent
estimate of the frame proportion, and a Wilson interval on the labelled count is not a
design-consistent interval. This module supplies the estimator the plan's protocol needs,
before any labels exist, so that the arithmetic is tested when they do.

Estimand: the proportion of the frame's candidate points whose reference label is canopy.
Weights are inverse inclusion probabilities, which the selection records per point.

Three things the protocol requires are implemented here rather than left to prose:

- **unknown is a category.** Labels are `canopy`, `not_canopy` or `unknown`. Unknown points
  are excluded from the estimate and reported separately as a weighted share, with bounds
  that treat them all as canopy and all as not-canopy, so a reader sees how far the unknown
  group could move the result.
- **variance without joint inclusion probabilities.** A single systematic draw per cell
  supplies no replicate, so joint inclusion probabilities are not available. The
  with-replacement approximation treats sampled points as if drawn independently with
  replacement proportions 1/pi, which overstates variance by ignoring the stratification gain
  from the equal spread. Reported as an approximation, never as a design-based interval.
- **intervals on the effective sample size.** Wilson assumes equal weights and independence.
  With unequal weights the honest sample size is Kish's effective size, (sum w)^2 / sum w^2,
  which is smaller than the number of points whenever weights vary.
"""
import math

from metrics import require
from sampling_plan import wilson_interval

CANOPY = 'canopy'
NOT_CANOPY = 'not_canopy'
UNKNOWN = 'unknown'
LABELS = (CANOPY, NOT_CANOPY, UNKNOWN)


def _weights(points):
    """Inverse inclusion probabilities, validating the recorded field."""
    require(bool(points), 'no sampled points')
    weights = []
    for point in points:
        weight = point.get('inverse_inclusion_probability')
        require(weight is not None, 'point is missing inverse_inclusion_probability')
        require(weight >= 1.0, f'inverse inclusion probability below 1: {weight}')
        weights.append(float(weight))
    return weights


def effective_sample_size(weights):
    """Kish's effective sample size: how many equal-weight points these weights are worth."""
    require(bool(weights), 'no weights')
    require(all(weight > 0 for weight in weights), 'weights must be positive')
    return sum(weights)**2/sum(weight**2 for weight in weights)


def estimate(points, labels, frame_size):
    """Hajek estimate of the frame proportion, with unknown shares and crude bounds.

    `labels` maps a point identity (gid, chainage_m) to one of `LABELS`. Points without a
    label are refused rather than silently treated as not-canopy, because an unfinished
    labelling pass must not look like a measured result.
    """
    weights = _weights(points)
    require(len(weights) == len(points), 'weight count disagrees with the points')
    require(frame_size >= len(points), 'frame cannot be smaller than the sample')
    labelled, unknown = [], []
    for weight, point in zip(weights, points):
        key = (point['gid'], point['chainage_m'])
        require(key in labels, f'point {key} has no label')
        label = labels[key]
        require(label in LABELS, f'unrecognised label {label!r} for {key}')
        (unknown if label == UNKNOWN else labelled).append((weight, label))
    require(bool(labelled), 'no labelled points: every sample is unknown')

    total_weight = sum(weight for weight, _ in labelled)
    canopy_weight = sum(weight for weight, label in labelled if label == CANOPY)
    proportion = canopy_weight/total_weight
    # Hajek is a ratio estimator, so this is the weighted share among all sampled points.
    all_weight = total_weight + sum(weight for weight, _ in unknown)
    low = canopy_weight/all_weight
    high = (canopy_weight + sum(weight for weight, _ in unknown))/all_weight
    return dict(
        estimator='Hajek ratio estimation with inverse inclusion probability weights',
        labelled_points=len(labelled), unknown_points=len(unknown),
        canopy_points=sum(1 for _, label in labelled if label == CANOPY),
        proportion=round(proportion, 6),
        frame_size=frame_size, sample_size=len(points),
        unknown_share=round(sum(weight for weight, _ in unknown)/all_weight, 6),
        bounds_unknown_all_not_canopy=round(low, 6),
        bounds_unknown_all_canopy=round(high, 6),
        effective_sample_size=round(effective_sample_size([weight for weight, _ in labelled]), 3),
        horvitz_thompson=round(
            sum(weight for weight, label in labelled if label == CANOPY)/frame_size, 6),
        limits=[
            'Unknown points are excluded from the estimate and reported as a weighted share',
            'Bounds treat every unknown point as not-canopy and as canopy, not as a distribution',
            'The variance approximation treats points as drawn with replacement and ignores the equal-spread gain',
            'Hajek and the bounds estimate the frame; they say nothing about other streets or years',
        ],
    )


def with_replacement_variance(points, labels):
    """Crude variance of the Hajek proportion, valid only as an approximation.

    Sarndal's with-replacement form for a ratio estimator: the weighted squared deviations
    over the squared total weight, times the usual n/(n-1) sample correction. It requires no
    joint inclusion probabilities, which a single systematic draw cannot supply.
    """
    weights = _weights(points)
    labelled = []
    for weight, point in zip(weights, points):
        label = labels.get((point['gid'], point['chainage_m']))
        require(label in LABELS, f'missing or invalid label for {(point["gid"], point["chainage_m"])}')
        if label != UNKNOWN:
            labelled.append((weight, 1.0 if label == CANOPY else 0.0))
    require(len(labelled) >= 2, 'variance needs at least two labelled points')
    total = sum(weight for weight, _ in labelled)
    proportion = sum(weight*value for weight, value in labelled)/total
    numerator = sum((weight**2)*(value-proportion)**2 for weight, value in labelled)
    count = len(labelled)
    return numerator/(total**2)*count/(count-1)


def wilson_on_effective(proportion, size):
    """Wilson interval evaluated at the effective sample size, not the point count."""
    require(0.0 <= proportion <= 1.0, 'proportion must lie in [0, 1]')
    require(size >= 2, 'effective sample size must be at least 2')
    total = int(round(size))
    successes = int(round(proportion*total))
    return wilson_interval(successes, total)


def report(points, labels, frame_size):
    """Convenience wrapper: estimate, approximate variance and an effective-size interval."""
    estimate_ = estimate(points, labels, frame_size)
    variance = with_replacement_variance(points, labels)
    size = estimate_['effective_sample_size']
    low, high = wilson_on_effective(estimate_['proportion'], size)
    estimate_['variance_approximation'] = round(variance, 8)
    estimate_['standard_error'] = round(math.sqrt(variance), 6)
    estimate_['interval_effective_size'] = [round(low, 6), round(high, 6)]
    estimate_['interval_half_width_pp'] = round((high-low)/2*100, 3)
    estimate_['interval_note'] = (
        f'Wilson at the effective sample size ({size:.1f}) rather than {estimate_["sample_size"]} '
        'points; the with-replacement variance makes this approximate, not design-based')
    return estimate_
