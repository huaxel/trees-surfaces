# Stakeholder brief: what should seasonal heat evidence change?

## Decision needed

Should the 2015–2024 ERA5 seasonal heat measure remain **temporal context** beside the current spatial WBGT screen, or should the project hold any ranking change until it has a higher-resolution, multi-date heat surface?

The existing ranking uses the Brussels Environment WBGT indicator raster for 24 August 2016. The new ERA5 artifact adds a ten-summer comparison; it does not change the ranking.

## Evidence from the feasibility sample

- The ERA5 archive provides a consistent daily series for June–August (JJA), 2015–2024. For this sample, 100 trees map to four ERA5 grid cells.
- The 24 August 2016 reference day falls among the 88th–90th warmest JJA days in its own summer across those cells (94.6–96.7% of that summer's days were below it).
- The 2016 summer's mean daily apparent-temperature maximum was about 21.75 °C across the sample cells; 2018 was the warmest season in the ten-year window at about 23.93 °C.
- The artifact counts about 7.3–8.5 JJA days per year with apparent-temperature maximum at or above 30 °C. This is a descriptive threshold, **not** a health-warning threshold.

## Higher-resolution source feasibility (exploratory)

A point-coverage audit sampled the 100 tree coordinates against Planetary Computer `landsat-c2-l2` scenes for JJA 2015–2024. It selected the surface-temperature asset by its STAC `temperature` role, covering sensor-specific keys such as Landsat 7 `lwir` and Landsat 8/9 `lwir11`, and read `qa_pixel`, `qa` (ST_QA), and `cdist` using temporary anonymous SAS tokens. All 361 intersecting scene items were readable. Scene overlaps were deduplicated by tree and acquisition date; eligible pairs are tree-dates covered by at least one scene with a surface-temperature product.

**Correction:** an earlier version of this exploratory audit assumed the `lwir11` asset name and omitted Landsat 7 scenes. The sensor-complete counts below supersede that earlier summary.

The baseline screen requires a nonzero temperature DN and clear QA_PIXEL bits 0–5 (fill, dilated cloud, cirrus where applicable, cloud, cloud shadow, snow). The stricter tests additionally apply the ST_QA uncertainty band (scale 0.01 K) and/or ST_CDIST cloud-distance band (scale 0.01 km). USGS describes these bands but does not prescribe the cutoffs below; they are sensitivity scenarios, not official pass/fail thresholds.

| Summer | ST scenes | Eligible tree-date pairs | Baseline QA | ST_QA ≤ 3 K | ST_CDIST ≥ 1 km |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2015 | 30 | 2,000 | 778 (38.9%) | 291 (14.5%) | 392 (19.6%) |
| 2016 | 33 | 2,200 | 351 (16.0%) | 178 (8.1%) | 242 (11.0%) |
| 2017 | 35 | 2,300 | 499 (21.7%) | 74 (3.2%) | 133 (5.8%) |
| 2018 | 33 | 2,200 | 670 (30.5%) | 378 (17.2%) | 455 (20.7%) |
| 2019 | 36 | 2,400 | 899 (37.5%) | 215 (9.0%) | 333 (13.9%) |
| 2020 | 35 | 2,300 | 796 (34.6%) | 239 (10.4%) | 368 (16.0%) |
| 2021 | 33 | 2,200 | 538 (24.5%) | 234 (10.6%) | 385 (17.5%) |
| 2022 | 38 | 2,399 | 1,105 (46.1%) | 151 (6.3%) | 347 (14.5%) |
| 2023 | 49 | 3,000 | 845 (28.2%) | 550 (18.3%) | 655 (21.8%) |
| 2024 | 39 | 2,200 | 803 (36.5%) | 191 (8.7%) | 337 (15.3%) |
| **Total** | **361** | **23,199** | **7,284 (31.4%)** | **2,501 (10.8%)** | **3,647 (15.7%)** |

Across all years, ST_QA cutoffs of ≤1 K and ≤2 K retained 0% and 0.9% of eligible pairs, respectively; ≤5 K retained 26.6%. Cloud-distance cutoffs of ≥0.5 km and ≥2 km retained 21.3% and 9.7%, respectively. Combining ST_QA ≤5 K with cloud distance ≥1 km retained the same 15.7% as the cloud-distance filter alone. Coverage is sensitive to quality policy, and no threshold here is stakeholder-approved.

The original WBGT reference date, 2016-08-24, has no Landsat scene item intersecting the Brussels sample area, so the satellite source cannot provide a same-date comparison for that event. Even the basic QA screen leaves a median of only three valid dates per tree in 2016; stricter screens reduce coverage further. This is not yet a validated seasonal heat measure.

The audit did not apply additional product-specific quality checks. The sample thermal asset has 100 m ground sampling even though it is delivered on a 30 m grid; the grid spacing is not independent 30 m thermal detail. Satellite land-surface temperature is also not WBGT, air temperature, tree shade, or a direct measure of human exposure. Any follow-up needs a documented quality policy and stakeholder agreement. Do not blend it into the ranking.

Sources: [USGS Landsat Collection 2 Surface Temperature](https://www.usgs.gov/landsat-missions/landsat-collection-2-surface-temperature), [USGS Collection 2 Quality Assessment Bands](https://www.usgs.gov/landsat-missions/landsat-collection-2-quality-assessment-bands), [Landsat 8/9 Level-2 Product Guide](https://www.usgs.gov/media/files/landsat-8-9-collection-2-level-2-science-product-guide), [Planetary Computer Landsat STAC quickstart](https://planetarycomputer.microsoft.com/docs/quickstarts/reading-stac-r/), and [Planetary Computer data-access tokens](https://planetarycomputer.microsoft.com/docs/concepts/sas/). Catalog reads were exploratory on 2026-10-16; no satellite snapshot was committed.

## Important limits

ERA5's grid step is about 28 km north–south and 18 km east–west at Brussels' latitude. Trees in the same cell share the same seasonal values, and all 100 points fall into only four cells. This can contextualize whether the single raster day was unusual and describe broad temporal exposure; it cannot distinguish streets, blocks, tree shade, or neighborhood-scale heat.

Apparent temperature is not WBGT. The ERA5 metrics and the normalized raster values have different units and meanings; do not combine or compare them as if they were the same scale. The ERA5 artifact therefore remains separate from the current ranking unless a stakeholder defines a suitable, spatially defensible way to use it.

## Questions for the review

1. Is broad, coarse-grid seasonal context useful alongside the current intra-urban WBGT screen, or is neighborhood-scale multi-date heat evidence required before changing the screen?
2. Which heat period should guide the eventual decision: a representative hot day, JJA average, frequency of hot days, or another locally meaningful period?
3. Should this seasonal measure remain descriptive context, or should a future heat measure enter the ranking? If it should enter, what spatial resolution and validation would make that defensible?
4. Is the round-number 30 °C apparent-temperature threshold useful for discussion, or should recurrence be reported without a threshold until the stakeholder specifies one?

## Suggested decision record

Use the existing stakeholder worksheet to record one of these outcomes, or an alternative:

- **Keep separate:** retain the single-day WBGT raster for the spatial screen and show ERA5 only as temporal context.
- **Require better spatial coverage:** do not revise the heat ranking until a validated multi-date neighborhood-scale source (for example, satellite land-surface temperature) is available.
- **Change the measure:** specify the operational heat metric, period, spatial unit, and validation needed before implementation.

This brief is a discussion aid, not a proposal to change the current ranking. See [`heat-season-method.md`](heat-season-method.md) and [`brussels-heat-season-sample.json`](../data/brussels-heat-season-sample.json) for the method and full snapshot. Record any accepted heat period in `tree-stakeholder-review.csv`; do not infer approval from this brief.
