# Cycling canopy: exploratory checkpoint

## Question and estimand

**Does nearby mapped tree canopy conceal interruptions in overhead canopy along cycling-street reference lines?**

Two different quantities are reported:

1. **Direct mapped overlap:** fraction of reference-line length intersecting VUB tree-class polygons (gridcode 4, height-based classification).
2. **Mapped proximity:** fraction of reference-line length within 2 or 5 m of those polygons. Buffering polygons is a proximity sensitivity analysis, not a claim that canopy expands or that cyclists ride at an observed offset.

Non-overlap is the complement of the selected mapped polygons, NOT independently verified absence of vegetation, and NOT unshaded distance. The images show that streets without overhead canopy can be shadowed. The reference line is not an observed cyclist trajectory or a surveyed lane footprint.

## Data and provenance

- [VUB / Gallez et al., 2024, Zenodo 13869065](https://zenodo.org/records/13869065): 2021 imagery-derived vegetation; CC BY 4.0. The 25 cm grid is resampled and is not a positional-accuracy guarantee. All seven published shapefile components passed the published MD5 checksums before local extraction. Source file names include `2022`, but the documented imagery is 2021.
- Brussels Mobility `bm_bike:ac` WFS: current retrieval, type 12 (cycling street), status 1 (existing). Start dates are approximate; current geometry does not establish 2021 cycling operation or alignment.
- Paradigm `Ortho2021Ns`: visual consistency check only. This is the imagery product underlying VUB's classification, not independent validation imagery. Exact crop request is cached.

## Fixed local comparison frame

A 1 km square around the initial convenience-selected pilot, EPSG:31370 bounds `[151980,169155,152980,170155]`. Select every existing cycling-street segment at least 100 m long whose entire geometry lies in the square. Rules were set before evaluating the new segments' canopy outcomes.

All 82 cycling-infrastructure records matching the bounding box were retrieved; a separate WFS hits response confirmed 82. Five records met the rules. The original 73 m segment 5644 is excluded by the length rule, not its outcome. This local, convenience-centred frame is not representative of Brussels. Adjacent road records are not independent samples or matched corridors.

## What the results support

See `cycling-canopy-local-comparison.md` and `cycling-canopy-100m-windows.md` for the tables and corresponding JSON for full precision.

- Mapped canopy proximity differs substantially within this small area: whole-segment overlap within 5 m ranges from 0% to about 90%.
- Segment 266 has about 31% direct overlap versus 90% proximity within 5 m. Its tested 100 m windows span 0–61% direct overlap despite 68–100% proximity. A high nearby-canopy value does not guarantee overhead continuity in this sample.
- Segment 5643 has no selected tree-polygon overlap even within 5 m. This is a mapped result, not a validated absence claim.
- These findings motivate a larger design. They do not establish heat exposure, cooling, actual shade, causal effects, citywide rankings, or demographic inequalities.

## Verification completed

- Local extraction was compared with an independent scan of all 5,790,723 SHP record bounding rectangles plus exact candidate intersections: the indexed result matched all 14,210 intersecting polygons in the comparison footprint. This verifies retrieval, not source classification or coverage.
- Invalid tree/high-shrub polygons were repaired with `make_valid`, retaining polygonal components. The comparison contained 82 such invalid polygons; repaired area was unchanged. Alternative `buffer(0)` repair produced identical reported overlap and longest non-overlap values across the 30 segment/class/buffer conditions.
- Interval measurements use per-line-segment projection to avoid projection ambiguity near bends. Covered lengths agree with direct geometry intersection lengths; overlap plus non-overlap reconciles to line length. Analytical checks cover empty/full coverage, multiple intervals, merging, and a bend.
- The original three-segment pilot's 18 condition totals match direct geometry intersections and reconcile to full-route totals.
- Equal-length analysis uses non-overlapping complete 100 m windows from either endpoint separately: 10 windows, 1,000 of 1,295.5 m, per anchoring scheme. The two schemes overlap and are not independent observations. Remainders are excluded; this is not an exhaustive sliding-window analysis or a confidence interval.

## Imagery agreement check (closed)

Asked whether the two 2021 UrbIS flight products could supply the positional-alignment evidence the audit lacked, on the same five routes and the same pre-declared chainages. Plan, both publisher metadata records and all 30 image responses are versioned with digests in `data/research/imagery-inputs/`, so the check verifies and re-runs offline.

Result: within each window one offset describes the pair, stable to a **median of 0.09 m** across the two finest-resolving bands (worst 0.29 m; 15 of 15 windows within 0.5 m). The offset itself is **0.55-5.43 m (median 1.92 m)** and varies along a street (-0.07 -> +0.06 -> -1.84 m east on gid 5642 over ~130 m), which no global translation, rotation or scale explains: the difference is **local** (per-tile mosaic/resection or relief), not one georeferencing constant. Full-band correlation 0.40-0.75. A degraded control (known 1.5 m shift with shifted footprint + JPEG q45 + 60% illumination ramp + 3 LSB noise) holds resolving bands within 3 mm but moves wide bands by 0.872 m; per-band errors rise monotonically 0.0003 -> 0.330 m from fine to coarse.

Three independent read-only reviews each found a real defect: a verdict resting on a band with a ~10 m lobe; then one eligibility constant deciding the verdict plus a missing taper on the luminance path; then taper ordering, an unquantified "precision" claim and a wrong table cell. Fixes: lobe-width reporting with only resolving bands deciding; nested spreads for every band cut (15/13/5/0 windows agreeing as coarser bands come in); identical taper applied before the band-limit on both paths; a peak-separation diagnostic, which shows the maximum is broad (1.00-1.10) and therefore that 0.09 m is stability, not a standard error; phase estimator demoted to a diagnostic; embedded plan, record bytes and record fields all bound and tested; shifted-footprint and degradation controls with a test that the guard fires. **Withdrawn**: the earlier "scale-dependent disagreement up to 3.0 m" and the "~1 m rigid global offset" framing. The per-layer axis attribution is no longer an inference: the pinned records are titled by axis and both are CC BY 4.0 with citation required (see `data/research/imagery-inputs/README.md`).

Consequence: these products are **not interchangeable at sub-metre level**, and metre-scale local differences exist between them on this sample. The offsets are method-dependent at the ~0.5 m level (a correct taper change moved the median 1.20 -> 1.92 m), so they are metre-scale magnitudes, not precise constants. Causes remain confounded (mosaic/resection, relief displacement, seasonal and shadow change, any residual global georeferencing), so this is not an accuracy bound for either product; the audit's 2 m scenarios remain uncalibrated stress tests, now with independent context that they are of the right order. No canopy figure or ranking was changed. Method and reproduction: `docs/imagery-registration-check.md`; numbers: `data/research/cycling-canopy-ortho-consistency.json`; gate: `scripts/validate-imagery.sh`.

## Before expansion

1. **Reproducibility implemented.** The canonical comparison/window pipeline now lives in `research/canopy/`, with a dependency lock, frozen input identities and small source snapshots, environment/parameter provenance, repair audits, and regression tests. See `docs/cycling-canopy-pipeline.md`. Source files remain ignored (~2 GB). Historical exact receipt timestamps were not retained and remain explicitly unknown.
2. **Specify the spatial unit before sampling.** Database segments differ in length and segmentation. Prefer a justified connected-route or fixed-distance design, with a predeclared sampling frame and inclusion rules. Do not rank longest gaps without accounting for route length.
3. **Resolve temporal scope.** Either explicitly study 2021 canopy along current cycling streets, or reconstruct historical infrastructure geometry/status. Weighted by analysed reference-line length, 43.5% of the sample (gid 266) has a recorded 2017 start, 41.8% (gid 5630, 5642, 5643) a June 2021 start — the same year as the imagery, which was flown in late September and early October 2021 — and 14.6% (gid 5634) a June 2022 start, after the imagery. So only gid 266 predates the canopy year: four of five segments, covering 56.4% of analysed length, are contemporaneous with or postdate the canopy they are compared against, and gid 5634 (14.6%) cannot be treated as confirmed 2021 cycling infrastructure. Segment 266 is also the segment whose direct overlap is most sensitive to translation (6.2-54.1% under four 2 m shifts), so being closest to historical does not make it a precise measurement. Start dates are approximate and describe designation records rather than travel.
4. **Validate source omission and alignment separately.** Use a preselected set of covered/non-covered locations, an independent source where possible, and an explicit unknown category where coverage is unresolved. Checking only striking gaps is not an accuracy assessment.
5. **Keep shade a separate research question.** Actual shade requires solar/time geometry and buildings, vegetation structure, or observations. It cannot be inferred from the canopy complement alone.

## Verification completed: independent geometry path (2026-10-17)

The published proportions come from exact line-interval intersection. An independent recomputation classified points at 2 m and 0.5 m chainage by point-in-polygon against the same tree cover (`cover.covers`, then the 5 m buffer), which is a different geometric path and a discretised one:

| Quantity | Published (interval) | 2 m points | 0.5 m points |
|---|---:|---:|---:|
| Direct overlap | 13.97% | 13.98% | 13.87% |
| Proximity-only (0-5 m, not overlapping) | 32.39% | 32.45% | 32.46% |
| Mapped non-overlap | 53.64% | 53.57% | 53.67% |

Per segment at 0.5 m: gid 266 31.06% vs 31.38%; gid 5642 1.68% vs 1.55%; gid 5630, 5634 and 5643 0.00% both ways. Agreement is therefore at the level of discretisation (about 0.1 pp in aggregate, at most 0.35 pp on one segment, where a grazed boundary contributes a few sample points). The exact interval value stands; the point check confirms the geometry rather than replacing it. `alignment_audit.py` was also re-executed and reproduces `data/research/cycling-canopy-alignment-audit.json` byte for byte, and both the pipeline outputs and this audit match their recorded code identities.

## Verification completed: legacy versus canonical artifacts (2026-10-17)

The exploratory artifacts kept under `data/research/` were compared against the canonical pipeline outputs. Where they overlap the numbers are identical: 30 of 30 comparison rows match on overlap and longest non-overlap, and 40 of 40 window rows plus 10 of 10 summaries match on every shared value field. The differences are metadata only — the canonical files replace the exploratory `method`/`limits` wording and add provenance, `schema_version` and the comparison digest. The legacy files are left byte-unchanged as the exploratory record; `docs/cycling-canopy-pipeline.md` now names them as superseded so new work reads the canonical outputs.

## Independent review

An independent read-only reviewer found **no important calculation errors in static review**. The reviewer did not execute scripts, verify source bytes, or independently inspect imagery. The review accepted the mapped-overlap/proximity interpretation and identified two reproducibility blockers before expansion:

- Scripts remain in ignored cache; comparison and window outputs lack enforced input identities and sufficient environment provenance. A concrete metadata-drift bug would have discarded the separately verified WFS count on regeneration. This bug was fixed by making `compare_local.py` read and assert the saved count response. A rerun produced a byte-identical published comparison JSON (SHA-256 check passed).
- The exploratory window script reread source files without proving identity. The replacement pipeline now computes both stages from the same validated in-memory routes and canopy, checks input hashes before and after execution, validates CRS/simple routes, and links window output to the comparison checksum. Shared helpers are ordinary imports with no report-writing side effects. Use the tracked pipeline rather than the historical cache scripts.

A second independent static review of the replacement pipeline identified missing end-to-end tests and a check-then-rename publication race. Both were fixed: manifest-backed synthetic execution now tests repairs, remainders, byte determinism, input mutation and index mismatch; Linux atomic no-replace publication is race-tested. Follow-up review found no remaining important issues, with the explicit limitation that the reviewer did not execute tests.

Executed verification: all 16 canopy tests passed normally and under optimized Python; the full repository gate passed with Julia 1.10.12 (1,258 Julia checks plus HTTP smoke tests). Two full-data pipeline runs produced byte-identical outputs and exactly reproduced the previous 30 comparison rows, 40 window-condition rows and 10 summaries. Provenance-bound outputs are in `data/research/canopy-verified/`. CI configuration was added but remote CI has not been run in this session.

The record scan cross-checks the spatial index; subsequent feature geometry retrieval still uses the same reader/SHX path. It is not a fully independent parser validation. No new quantitative heat or shade conclusion follows from this checkpoint.
