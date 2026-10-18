# Planning a canopy-class validation sample

**Status: a plan, not a result.** No reference labels exist. Nothing here estimates
accuracy, changes a canopy number, or affects the operational ranking. This document makes
one audit recommendation concrete — *derive a precision target and sampling plan before
estimating accuracy* — so that the decision about whether to fund validation can be made
against numbers rather than adjectives.

## What would be estimated

The estimand is the **line-length-weighted proportion of reference line that intersects
mapped tree-class canopy** — the same quantity the pipeline reports as direct overlap —
together with class-specific omission and commission at that support. The unit is a point
on the line with a stated footprint, not a polygon: polygons inherit their boundaries from
the classifier, so sampling polygons cannot measure omission.

Two consequences follow and are built into the plan:

- The frame is line length, and weights are measured mapped lengths, so a balanced sample of
  strata is **not** an estimate of canopy prevalence.
- Locations are clustered along streets. Precision must be quoted for the effective sample
  size, not the number of labelled points.

## What a given precision costs

Required independent points for a 95% interval half-width on a proportion, normal
approximation (z = 1.96), from `research/canopy/sampling_plan.py`:

| Assumed prevalence | ±5 pp | ±7.5 pp | ±10 pp | ±7.5 pp with design effect 3 |
|---|---:|---:|---:|---:|
| 0.10 | 139 | 62 | 35 | 185 |
| 0.25 | 289 | 129 | 73 | 385 |
| 0.50 | 385 | 171 | 97 | 513 |

The realised interval should be reported with the Wilson score interval, which stays inside
[0, 1] near the extremes where overlap is small: at n = 385 and p = 0.5 the Wilson
half-width is 4.97 pp, and at n = 97 it is 9.76 pp. The `design_effect` column exists
because adjacent locations on one street are not independent; the audit's translation
results (segment 266 moving from 31.4% to 6.2–54.1% under 2 m shifts) are a direct warning
that overlap is spatially autocorrelated. **The design effect must be estimated from the
pilot labels themselves**, as an intra-cluster correlation over street segments; 3 is a
planning placeholder, not a measured value.

Part of that placeholder can be measured without labels, and has been:
`research/canopy/design_effect.py` writes `data/research/canopy-design-effect.json` from the
committed frame, and the result splits the single number into two different things.

- **The mapped class is strongly clustered at short range.** The canopy indicator's
  within-segment autocorrelation is 0.63 at 2 m, 0.31 at 4 m, 0.21 at 6 m, and the frame
  holds 20 canopy runs averaging **9.0 m** (longest 26 m).
- **Randomly placed points would therefore face an inflation near 3.7** — one plus mean run
  over step, at this plan's **3.35 m** step. So 3 is not an arbitrary placeholder: it is
  about what random placement on this patch structure costs.
- **But the plan places points systematically, and even spreading removes most of that
  cost.** Across 4,000 random starting points the estimate moves between **12.99%** and
  **15.06%** (2.5th to 97.5th percentile) around the frame's **13.98%** — roughly ±1 pp,
  inside the binomial band, at a sampling fraction of **0.60**.
- **What the placeholder must still cover is label error.** Clustering of reference-label
  errors is invisible in mapped geometry and remains unmeasurable until labels exist.

One limitation is recorded with the artifact and should travel with the numbers: the variance
across starting points is a diagnostic, and a segment whose step is a fraction with a small
denominator repeats the same few samples, which makes that variance **unreliable rather than
systematically low** — forty synthetic i.i.d. frames with an integral step spanned 0.14 to 3.2
around a true 1.0. On the committed frame, segments 5630 and 5643 have a step of exactly 5/3
and only five distinct realisations, but neither contains any mapped canopy, so they
contribute no variance and the reported spread is driven by segment 266 with 215 distinct
realisations. The artifact records each segment's count. The spread is not a design-effect
estimate and must not be quoted as one.

## Frame and strata

The frame is the 1,295.5 m of reference line in the frozen comparison frame (five segments),
discretised at **2 m chainage**, and it is now materialised rather than described:
`data/research/canopy-validation-frame.json` holds **644 candidate points** covering
**1,288.0 m**, built by `research/canopy/validation_frame.py`. Candidates sit at the midpoint
of each 2 m interval (`chainage = (i + 0.5) × 2`), so a point represents the 2 m of line it
sits in the middle of; each segment's incomplete remainder, **7.451 m in total**, is excluded
and reported, matching the remainder rule used for the window analysis.

Stratum lengths below are measured from the published artifact
(`data/research/canopy-verified/comparison.json`, tree class at buffer 0 and 5 m) and are the
weights the allocation uses:

| Stratum | Length | Share | Points at n = 385 | Systematic step |
|---|---:|---:|---:|---:|
| Mapped non-overlap (beyond 5 m of any mapped tree) | 694.8 m | 53.6% | 206 | every 3.4 m |
| Proximity-only (inside the 5 m buffer, not overlapping) | 419.6 m | 32.4% | 125 | every 3.4 m |
| Mapped overlap | 181.0 m | 14.0% | 54 | every 3.4 m |

Mapped overlap is only 14% of the frame, so an unstratified sample would spend most of its
budget confirming absence. Allocation is proportional to measured stratum length, with the
largest-remainder rule applied deterministically, so the three counts sum exactly to the
requested total. A fourth stratum, **difficult or obscured locations** (for example where
the reference imagery is shadowed or the line is occluded by buildings), cannot be sized
from existing artifacts: it must be identified by a declared rule during sampling, kept as
its own stratum with its own reported results, and **never reweighted into the primary
estimate**, because its location rule is a judgement rather than a mapped length.

The frame reproduces the same geometry through a different method, which is why it can be
trusted as the population for a sample: point lengths at 2 m spacing against an interval
measurement of exactly the same range agree to within boundary discretisation —
overlap 180.0 vs 181.0 m, proximity-only 418.0 vs 419.1 m, non-overlap 690.0 vs 687.8 m
(worst absolute difference 2.2 m for non-overlap; every stratum within 51% of its tolerance of one step or 1% of the stratum
length). The artifact records that reconciliation, its bound and the generating script's
hash; `validation_frame.py` fails rather than publishing if it drifts.

Selection is executed by `research/canopy/selection.py`. Allocation is a single
proportional largest-remainder pass over the fifteen **(stratum, segment)** cells, weighted by
each cell's candidate count, with **at least one point per non-empty cell** so that no sampled
street is left unvisited. Strata therefore receive points in proportion to their frame
candidate counts (90 overlap, 209 proximity-only, 345 non-overlap) to within 1%, not exactly.
Within a cell the draw is systematic with a random start, so every candidate in that cell has
the same inclusion probability, `allocated / candidates`.

**Inclusion probability is not constant within a stratum**, because the minimum-one rule gives
small cells a larger share: inverse probabilities range from 1.0 to 1.69 at the 385-point
target. Proportions must therefore be weighted by each point's **inverse inclusion
probability**, which is recorded per point and sums to the frame size (644) over the sample.
The stratum-level `design_weight` (frame share ÷ sample share) does come out within 1% of 1,
but it is a diagnostic, not an estimator weight: the artifact records
`design_weight_valid: false` for every stratum, with the range it averages over. Using it at
stratum level would under-weight the certainty cells by up to 1.69×.

That balance across streets is a survey choice, not a prevalence estimate.

Run it with an explicit total and seed, neither of which is defaulted:

```sh
uv run --locked --python 3.12.12 --project research/canopy python research/canopy/selection.py \
  --total 385 --seed 20261017 --output .cache/canopy-validation-sample.json
```

## Reference labels

This is the hardest part, and the plan cannot paper over it: **the 2021 UrbIS orthophotos
are the same acquisition programme the mapped class was derived from**, so interpreting them
again is a consistency check, not independent validation. A label that can support an
accuracy claim needs one of:

- a field visit at leaf-on, recording canopy presence over the reference line and, for
  edges, the height class and approximate extent;
- a genuinely different source — a later or earlier orthophoto with its acquisition metadata
  verified, or a structural dataset not derived from the same classification.

Of the structural options, one is now named and one is closed, both on evidence recorded in
[`open-data-candidates.md`](open-data-candidates.md):

- **Usable candidate, with one condition that rules out the obvious use:** the open **UrbIS
  airborne LiDAR point cloud and 50 cm DTM/DSM from the 2021 campaign** (CC BY 4.0, flight dated
  2021-10-09). It is a different instrument from the orthophoto camera, so it does not share the
  imagery's failure modes — but it sits inside the same acquisition window as both orthophotos
  (2021-09-17 to 2021-10-09), so it is an independent-**modality** check, not a temporally
  independent one, and it says nothing about any year but 2021. **A height check against its
  DSM/DTM cannot validate the class this project maps**, because that class is the 5–113.96 m
  height band of a model built from the same 50 cm DSM/DTM; it would recover the defining
  threshold. The legitimate use is surface **structure** from the raw point cloud — crown versus
  planar roof at the same height — which is a different property from height.
- **Closed door:** **Copernicus Urban Atlas Street Tree Layer 2018** was queried against these
  five segments and does not reach four of them (nearest polygon 22.9 m, 44.6 m and 101.6 m from
  the centreline). Its 500 m² minimum mapping unit excludes street trees, so it cannot be the
  street reference.

Two things the plan must not accept as validation: the **VUB/Zenodo canopy height model already
in use** is derived from the UrbIS north–south 2021 orthophotos, so agreement with it is an
inter-analyst reproducibility check; and the national 1 m DSM is **internal use only**, so it is
not available for this purpose at all.

Protocol requirements taken from the audit, to be fixed before any labelling:

1. Interpreters work **blinded** to the mapped class and to the pipeline's scores.
2. The reference definition is declared in advance — canopy over the reference line, at the
   point's footprint — and distinguishes a botanical tree from a height-class vegetation
   polygon.
3. **Unknown is a category.** Obscured or ambiguous locations are labelled unknown, not
   forced into positive or negative, and the unknown fraction is reported.
4. Observed disagreement is adjudicated against a documented source hierarchy, with
   disagreements preserved rather than resolved silently.
5. Temporal change is coded **separately** from classification error: growth, planting or
   removal between the reference observation and the 2021 imagery is not a classifier error,
   and a single "disagreement" rate would conflate the two.
6. No point used for positional registration is reused for class validation.

## Analysis rules

- Report omission, commission and unknown as proportions with Wilson intervals, at
  line-length weights for the frame and separately by stratum.
- Report the interval at the **effective** sample size, using the design effect estimated
  from the pilot (segment-level clustering), and state the estimator used.
- Report bounds with unknowns treated as all-positive and all-negative, so a reader sees how
  much the unknown category could move the result. Do not silently treat unknown as negative.
- Report positional/edge discrepancies alongside class error, since a boundary shift and a
  class error can produce the same disagreement at the line support.

## Limits of this plan

- The frame is a 1 km² convenience frame with five segments, not a probability sample of
  Brussels streets. Precision statements apply to these lines, not the city, and the stratum
  shares are mapped lengths rather than validated canopy.
- The arithmetic assumes the normal approximation for planning and a design effect that is
  still unknown; both must be revisited once labels exist.
- A balanced or oversampled design changes what can be reported: it estimates stratum
  accuracy, not prevalence.
- Nothing here is a licence or redistribution clearance; reference imagery or field data
  would carry their own terms.

## Reproduction

```sh
# materialise the candidate frame (reads the frozen inputs, writes a new file)
uv run --locked --python 3.12.12 --project research/canopy python research/canopy/validation_frame.py \
  --output .cache/canopy-validation-frame.json

# precision table, Wilson check, and the strata and allocation
uv run --locked --python 3.12.12 --project research/canopy python research/canopy/sampling_plan.py
```

The committed frame is `data/research/canopy-validation-frame.json`; the command above writes a
new file rather than replacing it, as every generator in this project does.
`research/canopy/tests/test_pipeline.py` asserts the arithmetic, the deterministic
allocation, and that strata reconcile to the published artifact's lengths; the canopy gate
runs them.
