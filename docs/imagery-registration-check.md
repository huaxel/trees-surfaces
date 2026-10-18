# What displacement relates the two 2021 Brussels flight products?

**Question.** Can agreement between the two 2021 UrbIS orthophoto products supply the
positional-alignment evidence that the canopy audit could not? The audit's 2 m
translations are uncalibrated stress tests; co-registering two independently flown
products looks like an obvious source of a real bound.

**Answer.** Within each of 15 fixed windows the two products are related by a **single
offset**: across the finest-resolving bands the measured offset is stable to a median of
**0.09 m**, an order of magnitude smaller than the offsets themselves. That offset is not
the same everywhere. It ranges from **0.55 m to 5.43 m (median 1.92 m)** and changes
systematically by street and along a street, so the difference is **local**, not a global
displacement. Agreement between these products therefore cannot supply a sub-metre
lane-level alignment claim. **No alignment bound for either product is derived here**, and
no canopy figure or ranking was changed.

This report was revised after three independent read-only reviews, each of which found a
real problem: a verdict resting on a band that could not resolve the tolerance; a verdict
still hinging on one eligibility constant, with the luminance path missing the taper the
phase path used; and then taper ordering, an unquantified "precision" claim, and a wrong
table cell. All four are fixed below, and the correction is itself informative: the taper
change moved the median offset magnitude from 1.20 m to 1.92 m, so these offsets are
**method-dependent at the ~0.5 m level**, which the limits state.

## What was compared

| | Product |
|---|---|
| Reference | `Ortho2021Eo` |
| Moving | `Ortho2021Ns` |
| Service | UrbIS WMS 1.1.1, `EPSG:31370`, JPEG, 0.1 m pixels, 120 m windows |

Both are RGB+NI products of the same 2021 acquisition programme, same camera and same
orthorectification chain. They are **CC BY 4.0, with citation of the source required**:
each publisher record states "No limitations to public access" and "Creative Commons
Attribution (CC-BY) - required citation of data source", with the CC BY 4.0 licence text
(Paradigm / CIRB, BE.CIRB).

The axis attribution is documentary rather than inferred. The two records are titled
*Orthophoto – 2021 (axe Est-Ouest)* and *Orthophoto – 2021 (axe Nord-Sud)*, and the
statement they share dates the east–west flights to 22 and 25 September and the
north–south flight to 9 October. What the records do **not** separate is the acquisition
period: both carry 2021-09-17 to 2021-10-09, which is why an earlier version of this
report treated the axis mapping as an inference from layer names. Record bytes are pinned
and their fields re-extracted on verification, so all of this is re-checkable offline.

Windows are the same five routes and three chainage fractions (10%, 50%, 90%) used by the
alignment audit, re-derived from the frozen cycling frame and cross-checked against the
published `data/research/canopy-verified/comparison.json` selection: same gids, same count-only probe,
same segment lengths. The window plan is a versioned file; verification checks its digest
**and** that the copy embedded in the manifest, which the analysis actually reads, is equal
to it. The WMS grid is north-up, so image rows run north to south and east/north are computed
for that orientation.

All 30 image responses and the two metadata records are versioned in
`data/research/imagery-inputs/` with digests, request URLs and response headers, so the
result re-checks offline without network access.

## Method, and the two limits that govern it

**Resolution.** An offset cannot be measured more precisely than its correlation peak is
wide. A band-pass restricted to wavelengths above `W` has a correlation lobe of roughly
`W/2` metres, so a band above 20 m has a ~10 m lobe and cannot distinguish a 0.5 m
difference from a 2 m one, whatever number its peak position reports. Each band therefore
carries its own lobe width, and only bands whose lobe is **no wider than the 0.5 m
tolerance** decide the per-window verdict:

| Band | Lobe width | Decides the verdict |
|---|---:|---|
| full (0.1 m) | 0.05 m | yes |
| above 1 m | 0.5 m | yes |
| above 2 m | 1.0 m | no, reported only |
| above 5 m | 2.5 m | no, reported only |
| above 20 m | 10.0 m | no, reported only |

Because the bands are nested, agreement across a wider set is not an independent
confirmation: the fine band contains every coarser one. Spreads are therefore reported for
**every** nested set, so no single eligibility constant decides the story:

| Bands compared | Windows agreeing within 0.5 m | Median spread | Worst spread |
|---|---:|---:|---:|
| 2 (full, above 1 m) | **15 of 15** | 0.09 m | 0.29 m |
| 3 (+ above 2 m) | 13 of 15 | 0.30 m | 0.74 m |
| 4 (+ above 5 m) | 5 of 15 | 0.73 m | 1.38 m |
| 5 (+ above 20 m) | 0 of 15 | 1.34 m | 7.60 m |

The disagreement grows monotonically with the coarsest band admitted, which is what bands
that cannot resolve the tolerance predict. Because the per-window requirement is only two
bands, the verdict is one scale-stability check: whether including the sub-metre content
changes the answer.

**Peak sharpness.** The offset is also close to one definition of a *precision*: the
recorded correlation maximum is broad, not a spike. Comparing each peak with the best value
outside its own measured lobe gives median ratios of 1.00 (full band), 1.01 (above 1 m),
1.04 (above 2 m), 1.10 (above 5 m) and 1.39 (above 20 m). A ratio near one means the surface
just outside the lobe is as high as the peak, so what is being located is a **broad
maximum**, whose position is well defined but easily nudged by any change of weighting. That
is why the 0.09 m band-to-band agreement is reported as **scale stability, not a standard
error**, and why the 1.20 → 1.92 m change under a different taper is disclosed rather than
smoothed over.

Both band-limited paths apply the same Hann taper, and the taper is applied **before** the
band-limit, to images whose taper-weighted mean has been removed: otherwise the rectangle's
wrap seam, turned into ringing by the band-limit, would survive inside the taper. The
phase-only correlation of gradient energy is reported as a **diagnostic only**; it weights
every frequency equally, so broadband content differences flatten its peak, and it is never
used to decide agreement.

## Controls

| Control | Worst error observed |
|---|---:|
| Identical image against itself | exact zero |
| Synthetic band-limited shift of the window | 0.00034 px |
| Cubic resampling of a padded window, including a shifted footprint so the two images do not share edges | 0.00035 px |
| **Degraded control**: known 1.5 m shift, shifted footprint, JPEG quality 45, a 60% illumination ramp and 3 LSB noise — resolving bands | **0.003 m** |
| Same degraded control — wide bands (5 m, 20 m) | **0.872 m** |

The degraded control runs through the band path, not only the estimator, so it exercises the
code that produces the verdict; its per-band errors are 0.0003, 0.003, 0.010, 0.045 and
0.330 m from fine to coarse for a representative window. A resolving band that drifted
beyond the tolerance fails the run instead of being reported, and that guard has its own
test. The degradation is illustrative, not calibrated to the real radiometric difference
between the flights: it demonstrates a mechanism and its direction, not its true size.

## Results

| gid | Offset (east / north) at 10 / 50 / 90% | Magnitude | 2-band spread | Full-band NCC |
|---|---|---|---:|---:|
| 266 | +3.11/−1.13 m · +1.31/+0.53 m · +0.85/−0.51 m | 0.99–3.30 m | ≤0.15 m | 0.49–0.68 |
| 5630 | +1.80/−0.48 m · +1.71/−0.48 m · +1.82/−0.53 m | 1.78–1.90 m | ≤0.12 m | 0.62–0.75 |
| 5634 | −2.62/+4.54 m · −2.86/+4.62 m · −2.33/+4.04 m | 4.66–5.43 m | ≤0.09 m | 0.45–0.50 |
| 5642 | −0.07/+0.55 m · +0.06/−0.67 m · −1.84/+0.78 m | 0.55–2.00 m | ≤0.29 m | 0.40–0.73 |
| 5643 | +1.74/−0.82 m · +1.93/−0.87 m · +3.21/−1.12 m | 1.92–3.40 m | ≤0.13 m | 0.56–0.67 |

Sample: median magnitude **1.92 m**, range 0.55–5.43 m; median 2-band spread **0.09 m**, worst
0.29 m; normalised correlation 0.40–0.75; phase-diagnostic peak ratios 1.02–2.90 with 2 of 15
windows at ≥90% of the per-axis search limit.

What the numbers support:

- **One offset describes each window.** Across the two finest bands, whose content differs by
  everything between 0.1 m and 1 m, the measured offset moves by a median of 0.09 m — far less
  than the offsets themselves, so the estimates are not scale-sensitive noise. They are
  broad-maximum positions, so this is stability, not uncertainty.
- **The difference is local, not a global shift.** The east component changes by metres over
  ~100 m of route: gid 5642 runs −0.07 → +0.06 → −1.84 m across its three windows, gid 266
  3.30 → 1.42 → 0.99 m, gid 5643 1.92 → 2.12 → 3.40 m. No single translation, rotation or
  scale of one mosaic relative to the other produces swings of that size over that distance.
  The residual therefore sits per tile or per feature — mosaic/resection difference or relief
  displacement — rather than in one global georeferencing constant.
- **Coarse-band disagreement is not evidence about the products.** It appears only once bands
  with lobes of metres are admitted, and the degradation control moves exactly those bands by
  ~0.9 m under ordinary radiometric difference. The earlier draft's "scale-dependent
  disagreement up to 3.0 m" is withdrawn for that reason.
- **Consistency is not validation.** Every window above is labelled consistent because its
  bands located the same maximum. Nothing here checks that maximum against a reference, so
  the largest values — gid 5634 at 4.66–5.43 m — are self-consistent and still unchecked
  locally; they are the clearest candidate for the control-point work in the follow-up.
- **The offsets are method-dependent at the half-metre level.** Applying the taper correctly
  changed the median magnitude from 1.20 m to 1.92 m, and the estimand is a
  Hann-weighted (centre-dominant) displacement rather than a rectangle-weighted one. Treat
  these as metre-scale magnitudes, not precise constants.

## What this does and does not establish

- An offset of 0.55–5.43 m between two mosaics of the same city is a statement about the
  **pair**. Both can be accurate and still differ, or share a common error this comparison
  cannot see. It is **not** an accuracy assessment of either product, and **not** a substitute
  for documented positional metadata or surveyed control points.
- Local mosaicking and relief effects are now the leading explanation, but the apportionment
  between them, and any residual global georeferencing difference, is not identified here.
- For canopy work the practical reading is: any judgement that overlays canopy polygons from
  one product's lineage on imagery from the other, or that needs sub-metre positional
  agreement at lane level, inherits local disagreement of order 1–5 m between products alone
  on this sample. The audit's conclusion therefore stands unchanged, and its 2 m stress
  scenarios are of the same order as, and in places smaller than, an independently observed
  product-to-product difference — context for treating them as relevant stress magnitudes,
  not evidence that 2 m is the canopy layer's own error.
- A real alignment claim still needs surveyed control points, or the publishers' documented
  positional-accuracy metadata, with reported residuals and reference uncertainty.

## Reproduction

The plan, both metadata records and all 30 image responses are versioned, so verification and
analysis re-run offline. The analysis refuses to overwrite an existing report:

```sh
# verification only: re-checks the plan digest and embedded copy, every pinned file
# digest, every metadata record field and every image size
uv run --locked --python 3.12.12 --project research/imagery python research/imagery/wms.py

# offline analysis into a new path
uv run --locked --python 3.12.12 --project research/imagery python research/imagery/consistency.py \
  --output .cache/ortho-consistency-new.json
```

Rebuilding from upstream requires the fetch path, which writes a new plan first and refuses
to replace any existing file or manifest:

```sh
uv run --locked --python 3.12.12 --project research/imagery python research/imagery/wms.py --fetch
```

`scripts/validate-imagery.sh` is the regression gate: the estimator, the band resolution rule,
the nested-cut reporting, the manifest/plan/record binding, the degraded-control guard and the
whole analysis on synthetic fixtures, plus an offline verification pass over the versioned
package. The committed report is `data/research/cycling-canopy-ortho-consistency.json` —
per-window, per-band, per-control detail, with request URLs and hashes.
