# Measurement audit: Brussels trees, heat and cycling

**Scope:** deepen measurement validity, not enlarge the sample or change the operational ranking. Review date: 2026-10-17. This audit distinguishes a reproducible computation from a valid measurement of the intended phenomenon.

## Conclusion

The current evidence supports **descriptive mapped canopy overlap and proximity along current cycling-street reference lines**, and **product-specific modelled heat context**. It does not yet support cyclist heat exposure, observed shade continuity, tree cooling effects, or planting priorities.

The most consequential new measurement result is that segment 266's direct overlap changes from **31.4%** at the source line to **6.2–54.1%** under four fixed 2 m cardinal translations. Those translations are uncalibrated scenarios, not estimates of actual coordinate error. Nevertheless, reporting 31.4% as a robust lane-level canopy measurement would exceed the evidence.

## 1. What is measured, and what is not

| Candidate indicator | Actual measurement and support | Defensible use now | Unsupported promotion |
|---|---|---|---|
| Managed-tree point/count | Records in an administrative inventory; original feasibility sample has 100 selected points | Traceable locations of recorded trees | All trees, canopy area, maintenance need, or planting capacity |
| Detailed WBGT indicator | Source-normalized 0–100 indicator for a modelled all-hours mean on 2016-08-24; detailed 2 m radiation/shade treatment | Relative modelled hot-day context at sampled locations | Degrees Celsius, measured personal exposure, or observed tree cooling |
| VITO daily archive | Modelled 100 m daily-maximum WBGT in °C, 2008–2017 | Within-product period comparisons and regional/local climate context at its support | Independent fine-scale validation of the detailed indicator; tree-specific shade |
| ERA5 context | 0.25° source sampling; 100 tree points occupy four cells; apparent-temperature statistics | Broad temporal context | Street-level contrasts or an interchangeable WBGT measure |
| Counter distance | Straight-line distance to a monitoring location | Monitoring-location proximity | Route choice, trip volume, travel distance, or cyclist exposure |
| Assigned counter counts | Five counters, 2024-01-01 through 2024-01-07; 97 tree rows inherit five values | Activity at those counters in that week | 97 independent mobility observations or summertime flow at those trees |
| Direct canopy overlap | Line-length fraction intersecting height-classified VUB tree polygons from 2021 imagery | Exact geometric overlap under stated source/alignment assumptions | Surveyed cyclist-path canopy or actual shade |
| Within-2/5 m canopy | Line-length fraction inside a positive buffer of mapped tree polygons | Proximity to mapped canopy; sensitivity to indicator definition | Positional-accuracy bound, corrected canopy, or shaded distance |
| Longest non-overlap run | Complement of selected mapped polygons along a specified line | Descriptive interruption in that mapped indicator | Confirmed treeless or unshaded stretch, especially with unresolved source omissions |

**Important denominator distinction:** the canopy study in Gallez et al. measures tree-canopy *area* within street service areas. Our pilot measures intersected *line length*. Reusing its vegetation dataset does not transfer the validity of its area-based indicator to our line-based one. See the paper's Table 1 and §2.3 [S2].

## 2. Heat-product alignment: a substantive documentation correction

Two older project documents described the detailed WBGT layer and daily archive as having matching 100 m grids. The official Brussels Environment methodology explicitly distinguishes a **100 m summer air-temperature map** from a **2 m detailed WBGT scenario**, with radiation exposure modelled from vegetation and building heights [S1]. The detailed scenario averages all hours of 24 August 2016; the VITO archive used here reports daily maxima. The stale wording has been corrected in:

- `docs/heat-season-stakeholder-brief.md`
- `docs/heat-season-method.md`

This matters scientifically: cross-product disagreement cannot isolate time-window choice. It simultaneously changes spatial support, radiation treatment, daily statistic and scale/units. Conversely, agreement would not establish validity, since the products share model lineage. A canopy association with the detailed WBGT product is also not independent evidence of cooling when vegetation already enters its radiation model.

Existing diagnostics already support these boundaries: the 100 points occupy 39 archive cells; 13 cells have only one sampled tree. An equal-cell within-cell variance fraction of 2.6% describes variation among the sampled points, not all surfaces inside those cells. A source-normalized indicator and a second sample min–max transformation are two different operations; neither creates an absolute heat or health threshold [L1].

## 3. Spatial alignment: dilation is not an error model

Let `C(b)` be the fraction of a fixed line inside the canopy polygons buffered by distance `b`. For nonnegative buffers, `C(0) ≤ C(2) ≤ C(5)` **by construction**. Thus, increasing overlap under larger buffers is not evidence that the larger-buffer value is more accurate. The informative quantity is the magnitude and spatial arrangement of the difference, conditional on the chosen geometry—not the existence of the increase.

The existing 0/2/5 m results therefore do not calibrate route registration error. To examine a different failure mode, the audit translates each complete reference line east, west, north and south by exactly 2 m, then by 5 m, leaving the polygons unchanged. These scenarios were fixed before computing the audit. Directions refer to the projected EPSG:31370 coordinate axes. They preserve line length and can increase or decrease overlap.

### New deterministic stress test

| gid | Original direct overlap | Four 2 m translations: min–max | Four 5 m translations: min–max |
|---|---:|---:|---:|
| 266 | 31.4% | 6.2–54.1% | 1.7–63.6% |
| 5630 | 0.0% | 0.0–0.0% | 0.0–4.1% |
| 5634 | 0.0% | 0.0–0.0% | 0.0–0.0% |
| 5642 | 1.6% | 1.8–7.3% | 0.0–10.4% |
| 5643 | 0.0% | 0.0–0.0% | 0.0–0.0% |

Ranges exclude the original position, are not confidence intervals and are not exhaustive over directions or displacements. A whole-line translation is a registration stress test, not a model of road-relative cyclist movement; translated lines may leave the carriageway. Without surveyed errors or appropriate positional metadata, neither 2 m nor 5 m can be called a plausible error bound. Local bends, systematic bias and spatially varying errors are not covered by these eight scenarios.

The strong sensitivity at 266 is an actionable reason to audit its physical reference line and canopy edges before treating it as a precise overhead-canopy contrast. Zero in tested scenarios for 5643 is still only a mapped result, not proof of no trees or shade. Do not select whichever translation gives the preferred result, or claim a ranking reversal by choosing different errors for different streets.

### Independent check: the two flight products differ by metres, locally, window by window

The two 2021 UrbIS orthophoto products (CC BY 4.0, citation required; their records name the east–west and north–south axes and the shared statement dates the passes) were co-registered on 15 fixed windows over the same five routes. Each spatial band carries the resolution its own correlation lobe allows, because a band above 20 m has a ~10 m lobe and cannot resolve a 0.5 m difference; only bands whose lobe is no wider than the tolerance decide the per-window verdict, and spreads are reported for every nested set so no single cut decides the story. Three independent read-only reviews shaped this method, each finding a real defect: an earlier verdict rested on an unresolvable band; the next still hinged on one eligibility constant and omitted the taper the phase path used; then taper ordering, an unquantified precision claim and a wrong table cell ([L4]).

Result: within a window one offset describes the pair, stable to a median of **0.09 m** across the two finest bands (worst 0.29 m; 15 of 15 windows within 0.5 m). The offset itself is **0.55–5.43 m (median 1.92 m)**, and it changes along a street: gid 5642 runs −0.07 → +0.06 → −1.84 m east over about 130 m, gid 266 3.30 → 1.42 → 0.99 m. No single translation, rotation or scale of one mosaic relative to the other produces such swings over that distance, so the difference is **local** — per-tile mosaic/resection difference or relief displacement — not one global georeferencing constant. Full-band correlation 0.40–0.75. Three caveats are stated in the source: the correlation maximum is broad (peak-to-shoulder ratios 1.00–1.10), so 0.09 m is scale stability rather than a standard error; the estimand is Hann-weighted; and a correct taper change moved the median magnitude from 1.20 m to 1.92 m, so these offsets are method-dependent at the ~0.5 m level. A degraded control (known 1.5 m shift with a shifted footprint, JPEG quality 45, a 60% illumination ramp and 3 LSB noise) holds the resolving bands within 3 mm but moves the wide bands by 0.872 m, which is why coarse-band disagreement is treated as an artefact rather than evidence.

This bounds nothing about either product's accuracy: two products can be displaced relative to each other while both are accurate, and the residual global georeferencing component is not identified. It does establish that these products are **not interchangeable at sub-metre level** and that metre-scale local differences exist between them on this sample, so overlay-style positional judgements at lane level inherit that before any canopy question is asked. The 2 m stress scenarios above are of the same order as, and in places smaller than, an independently observed product-to-product difference — context for treating them as relevant stress magnitudes, not evidence that 2 m is the canopy layer's error. A real alignment claim still needs surveyed control points or documented positional-accuracy metadata with reported residuals [L4]. Methodology, controls and reproduction: `docs/imagery-registration-check.md`, `data/research/cycling-canopy-ortho-consistency.json`. No canopy figure or ranking was changed.

Reproduction:

```sh
uv run --locked --python 3.12.12 --project research/canopy \
  python research/canopy/alignment_audit.py \
  --output .cache/alignment-audit-new.json
```

The script verifies the frozen input identities before/after analysis, recomputes the full-scan-checked extraction with 10 m margin, and tests alternative repairs for every scenario. All 45 segment/scenario combinations had zero reported overlap and longest-nonoverlap differences between the two repair methods. Results and source/code identities: `data/research/cycling-canopy-alignment-audit.json`. The original comparison outputs are unchanged.

## 4. Source classification: geometry quality is not thematic accuracy

The VUB description selects vegetation by NDVI and classifies it by modelled height; its tree class is a height category, not a field census of botanical trees. It combines 2021 imagery and terrain/surface models, resampled to 25 cm, and excludes green roofs [S3]. Consequences:

- A 25 cm grid does not establish 25 cm horizontal or vertical accuracy.
- Trees below the class threshold may be classified among shrubs. A botanical-tree claim needs a different reference definition.
- A height-threshold crossing and a small canopy-edge error can alter a narrow line intersection substantially.
- Valid polygons, matching checksums, complete retrieval and unchanged repaired area do not measure omission/commission error. The alternative-repair test checks one numerical failure mode, not source truth.
- Green roofs are deliberately excluded, so the complement cannot be interpreted as all non-vegetation.
- No local confusion matrix or independent positional-error estimate has been established for these five streets. The main paper directs detailed methods to supplementary material; no numerical local classification-accuracy result was established from the main text or dataset record inspected here. That is a limit of this audit, not a claim that no validation exists anywhere.

The original visual check uses the same north–south orthophoto product underlying VUB. It can expose gross inconsistencies but is not independent validation. A 2021 east–west product is a candidate cross-check, but its acquisition timing and processing dependence have not yet been verified; no independent imagery validation is claimed.

## 5. Temporal alignment is a question of target, not just dates

The sources span a 2016 modelled heat scenario, a 2008–2017 daily archive, 2021 canopy imagery, one January 2024 counter week, and current infrastructure retrieval. Segment 5634 has an approximate recorded 2022 cycling-street start.

Three different questions must not be blended:

1. **Historical 2021 canopy along current road-reference lines:** feasible as a clearly labelled geometric comparison. It makes no claim that cycling designation or travel occurred in 2021.
2. **Conditions experienced by cyclists in a specified season/year:** requires appropriate route/path geometry, infrastructure status, travel timing, and environmental data for that target period. The existing sources do not jointly establish this.
3. **A causal effect of trees on heat or cycling:** needs a causal design and relevant observations, not a cross-sectional overlay. Land use, street width/orientation, building shade, traffic, morphology and management can confound associations.

A recent field visit cannot directly validate 2021 vegetation absence. Apparent disagreement may be growth, removal or planting. Record acquisition/observation time and land-cover change separately from classification error. Likewise, data publication/retrieval time is not the date the physical condition was observed.

## 6. Statistical support and novelty

- Five local administrative segments are not five random, independent samples. One segment contributes half of the 10 complete 100 m windows per anchoring scheme. Adjacent windows share context and source errors; reversing the anchor does not create new observations.
- Equal-length windows improve comparability of run lengths but exclude about 295.5 m per scheme. Their results are not exhaustive sliding-window extrema. Database splitting and frame-edge exclusions can change the sample.
- Whole-segment percentages and pooled window averages answer different questions. A network description should state whether it weights equal streets, equal length, trips, or people; none is a neutral default for exposure.
- The five-segment study demonstrates that these two mapped indicators can differ locally. Since buffer nesting guarantees an increase, that alone is not a novel environmental finding. A useful next contribution would quantify *where and how often* high canopy proximity coexists with low overhead continuity under a justified frame, then test whether the distinction matters for an externally observed outcome.
- The primary school study's temperature-regulation indicator is based on vegetation fractions and literature supply rates; its authors call these rough estimates (§4.3). It is not observed local cooling and does not validate our cyclist-exposure indicator [S2]. School-neighbourhood demographics also cannot identify the demographics of cyclists using a road.

## 7. Validation plan and stop/go gates

No numerical acceptance threshold or sample size below is represented as stakeholder-approved. Both should follow a declared decision and desired precision, not be chosen after seeing outcomes.

### A. Define the intended measurement first

Keep the default target as **mapped canopy continuity along specified reference lines**. If the target is physical overhead cover along usable cycling space, obtain lane/path geometry or a justified road-surface representation. If the target is shade or thermal exposure, use a separate protocol. Resolve the spatial unit, target year/season and acceptable false positives with the stakeholder; do not modify the operational tree screen without that decision [L2].

### B. Audit alignment and classification separately

1. Select validation locations from a declared frame, including mapped tree overlap, mapped non-overlap, proximity-only locations and difficult/obscured locations. Include both positive and negative predictions; checking only conspicuous gaps is biased.
2. Keep selection probabilities and chainage/segment IDs. Stratified oversampling is useful, but combine strata with the correct target weights if reporting overall error. Do not present a balanced validation sample as the natural prevalence of canopy.
3. For positional registration, use stable, clearly identifiable reference features and report residual vectors plus reference uncertainty; canopy crowns move/grow and are poor sole registration controls. Do not tune and validate on the same points.
4. For class/edge validation, define the reference label explicitly (height-class vegetation versus botanical tree, canopy over the reference line versus any tree nearby). Have independent interpreters blinded to scores where feasible; label obscured cases **unknown**, preserve disagreements, and adjudicate against a documented source hierarchy.
5. Match dates where possible. Where sources differ in time, code change separately; do not count all disagreement as classification error. Verify orthophoto acquisition metadata before claiming an independent reference.
6. Report class-specific omission/commission, unknown fraction, and positional/edge discrepancies at the relevant line or area support. Derive a precision target and sampling plan before estimating accuracy. Do not silently treat unknown locations as negative.

**Go:** proceed to broader mapped-canopy description once the estimand/frame are fixed and residual alignment/omission limits are reported. **Stop:** if the intended comparison is lane-level overhead cover but plausible alignment remains uncalibrated enough to change the decision, resolve it before ranking.

### C. Validate shade/heat only with relevant evidence

For shade, specify date, time, solar geometry and buildings as well as canopy; compare against independent observations or a separately validated model. For heat stress, specify the physical index, height, averaging interval, radiation/wind handling, and calibration of reference measurements. A canopy–WBGT association where vegetation is already a model input is not an independent cooling validation.

Use a separate held-out route/day design if an exposure model is fitted. Do not count shared raster cells, repeated counter assignments or overlapping windows as independent measurements. Keep licence/redistribution clearance separate from scientific validity: VITO daily-archive terms remain unresolved.

## Evidence and sources

- **[S1]** Brussels Environment, [Îlot de chaleur](https://environnement.brussels/citoyen/documentation-et-outils/etat-des-lieux-de-lenvironnement/ilot-de-chaleur), sections on the 100 m 1987–2016 summer air-temperature map and the 2 m 2016-08-24 detailed WBGT scenario; checked 2026-10-17.
- **[S2]** Gallez, Canters, Gadeyne & Baró (2024), *A multi-indicator distributive justice approach to assess school-related green infrastructure benefits in Brussels*, Ecosystem Services 70, 101677, [DOI](https://doi.org/10.1016/j.ecoser.2024.101677). Main text Table 1, §§2.3 and 4.3 inspected via [public full text](https://www.docu.vlaamserand.be/sites/default/files/2025-05/1-s2.0-S2212041624000846-main.pdf). Paper licence is CC BY-NC-ND; dataset licence is separately CC BY 4.0. No supplementary accuracy result was established in this audit.
- **[S3]** VUB, [Urban Vegetation Data, Brussels 2021](https://zenodo.org/records/13869065); exact metadata snapshot and source hashes in `data/research/canopy-inputs/`.
- **[L1]** `data/research/heat-support-diagnostics.md`; `docs/mobility-measure-stakeholder-brief.md`; `docs/heat-season-stakeholder-brief.md`. Existing computed diagnostics, not new independent measurements.
- **[L2]** `docs/trees-stakeholder-spec.md`: decision question, spatial unit and intervention criteria still require external stakeholder confirmation; current screen is not a planting recommendation.
- **[L3]** `data/research/canopy-verified/`, `data/research/cycling-canopy-alignment-audit.json`, and `docs/cycling-canopy-pipeline.md`: reproducible arithmetic and provenance, not field validation.
- **[L4]** `docs/imagery-registration-check.md`; `data/research/cycling-canopy-ortho-consistency.json`: computed cross-product offset with per-window controls and a resolution-aware band rule, revised after independent review; a statement about the pair of products, not an accuracy measurement, and a demonstration that imagery co-registration cannot supply a sub-metre lane-level bound.

## Review and execution record

Independent read-only review found no important findings in the measurement logic, numerical transcription or claim boundaries. The reviewer did not execute code or establish field accuracy. Separately, 17 canopy regression tests passed normally and under optimized Python; the full Julia/project gate passed (1,258 Julia checks plus HTTP smoke tests). The audit baseline reproduces the verified comparison exactly and uses the same frozen input manifest. No operational ranking or original canopy result was changed.
