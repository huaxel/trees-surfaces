# Tree signal descriptive analysis

This report answers the working screening question using the committed 100-record feasibility sample.

> Which observed tree areas combine relatively high heat-stress values with proximity to bicycle counters, and therefore merit more detailed field or mobility analysis?

## Heat data and normalization

- The ranking heat input is the regional urban-heat-island model published by Brussels Environment: mean 24-hour Wet Bulb Globe Temperature for one representative hot day (2016-08-24). The public regional WMS exposes this single scenario layer.
- The source raster stores a normalized 0–100 WBGT indicator, not degrees Celsius. The prototype then min-max normalizes those source values again within the committed 100-record sample to calculate heat scores; rankings therefore shift with the weights and with a different sample.
- The authoritative ISO metadata identifies the dataset as `BRU_ENVI_73b4f29a-cff0-4d6a-a239-cb99d3140531`, published by Brussels Environment / Leefmilieu Brussel under CC BY 4.0 with source attribution.
- Missing data: all 100 joined points have non-NoData WBGT pixels, so there is no heat missingness to impute in this snapshot.
- A separate multi-date 100 m WBGT context was evaluated; its data-derived comparisons and interpretive limits are summarized below. It remains context only and does not replace the raster as ranking input.

## Seasonal heat context

- A multi-year seasonal context is committed as `brussels-heat-season-sample.json`: pooled June–August seasons for 2015–2024 on the ERA5 reanalysis grid, where 4 cells cover the committed sample, retrieved from the Open-Meteo archive API with Copernicus attribution.
- The committed WBGT date, 2016-08-24, was an extreme day inside its own summer: apparent-temperature maxima were 32.4–33.2 °C across those cells, ranking 88th–90th warmest of that season's 92 days (94.6–96.7% of the seasonal days were below it).
- The 2016 seasonal mean apparent maximum was about 21.75 °C across the sample cells; 2018 was the warmest season across all sampled cells, at about 23.93 °C on average.
- Recurrence context: about 7.3–8.5 days per season reach an apparent maximum of 30 °C or more in these cells, so a one-day snapshot says nothing about how often the condition repeats.
- Boundary: the ERA5 grid step is about 28 km north-south and 18 km east-west at Brussels' latitude; the 4 cells spanning the sample differ by only 0.63 °C in seasonal mean apparent maximum. This source documents temporal representativeness; it cannot reproduce or replace the intra-urban pattern of the 10,000 × 9,000 WBGT raster that drives the ranking.

## Multi-date 100 m WBGT context

- VITO publishes daily maximum WBGT at 100 m in EPSG:3035 for 2008–2017 (10 summers), sampled as `brussels-heat-wbgt-sample.json` to the same 100 trees across 39 cells. It is the same UrbClim model family and spatial resolution as the Brussels Environment raster, but its °C daily maxima are not interchangeable with the raster's 0–100 indicator for a 24-hour mean scenario. The archive page requests citation to De Ridder et al. (2015) and Souverijns et al. (2026).
- The 24 August 2016 raster date falls at the 96.7–97.6th percentile of the pooled June–August daily WBGT distribution; its sampled point values are 26.13–27.52 °C. The seasonal-mean WBGT ranges from 19.1 to 20.51 °C across the sample.
- In the VITO daily-maximum series, the reference-day and pooled seasonal-mean heat-only top tens share 7/10. Against the current balanced screen, the VITO reference-day, seasonal-mean and hot-day-count top tens overlap at 3/10, 0/10 and 0/10. The latter comparisons also change WBGT output semantics and scoring; they do not isolate heat-period effects. No alternative is adopted pending stakeholder choice.
- Licence review for the VITO 2008–2017 (10 summers) daily archive is unresolved: the source page requests both citations but states no reuse terms, and the annual NetCDF files themselves carry no licence attribute. Two related records do not transfer theirs — the Souverijns et al. (2026) decadal indicator set is CC BY 4.0, and the CC-BY-4.0 Copernicus CDS record `sis-urban-climate-cities` covers hourly temperature, humidity and wind without WBGT. Confirm terms with VITO before external redistribution or relying on derived values beyond exploratory analysis; see `docs/heat-season-method.md`, *Licence and lineage*.

## Traceability

Every displayed point can be traced to its source record and join method:
- Source record: the managed-tree register entry, reachable by id, e.g. `https://bruxellesdata.opendatasoft.com/api/explore/v2.1/catalog/datasets/arbres-bomen-vbx-be-bm/records?where=id%3D%27vbx_56544%27`.
- Heat join: WBGT raster pixel value extracted after the EPSG seven-parameter WGS84-to-Belgian-1972 datum transform and Belgian Lambert 72 projection (see `src/Heat.jl` and `src/Projection.jl`, exposed as `bin/generate_heat_join.jl`).
- Mobility join: great-circle distance to the nearest bicycle counter (see the committed `brussels-tree-bike-nearest.json`); measured-flow context for the nearest counter is in `brussels-tree-counter-flow.json`.
- Ranking: signal = heat_score × weight + proximity_score × weight, min-max scores, weights exposed in the interface.

## Sample summary

- Records analyzed: 100 of 31,643 managed-tree records reported by the source (0.32% of the reported register)
- Sampling note: the committed records are a feasibility snapshot, not a probability sample or city-wide estimate
- Source-normalized WBGT indicator pixel (0–100, not °C): min 51, median 68.0, max 88
- Counter distance: min 8.1 m, median 490.6 m, max 1518.3 m
- Counter history context: 3,360 fifteen-minute observations (5 counters × 672) from 2024/01/01 to 2024/01/07; mean count 14.6, maximum 100
- High-heat/high-proximity quadrant: 1 point at or above the sample's third quartile on both normalized components

## Data completeness

Completeness is reported against the 100 committed managed-tree records. Missing measured-flow context does not remove a point from the heat/proximity analysis.

| Stage | Expected | Available | Missing |
|---|---:|---:|---:|
| Valid coordinates | 100 | 100 | 0 |
| Heat join | 100 | 100 | 0 |
| Non-NoData heat pixels | 100 | 100 | 0 |
| Nearest-counter join | 100 | 100 | 0 |
| Analyzed records | 100 | 100 | 0 |
| Counter-flow context join | 100 | 100 | 0 |
| Measured-flow history available | 100 | 97 | 3 |

Measured-flow context is unavailable for IDs vbx_58411, vbx_58413, vbx_58589; the affected nearest counter set is CB02411, CJE181, whose archived windows are absent or did not qualify as measured. All core heat and nearest-counter joins are complete.

## District context

District counts describe this 100-record sample only; they are not district prevalence estimates.

| District | Points | Mean WBGT indicator (0–100) | Median counter distance | High-high points |
|---|---:|---:|---:|---:|
| SQUARES | 35 | 72.8 | 559.3 m | 0 |
| QUARTIER ROYAL | 33 | 56.1 | 285.5 m | 0 |
| BEGUINAGE - DIXMUDE | 15 | 68.4 | 564.6 m | 0 |
| STALINGRAD | 9 | 84.0 | 489.9 m | 1 |
| QUARTIER EUROPEEN | 5 | 61.2 | 33.8 m | 0 |
| HEEMBEEK | 2 | 73.5 | 1509.0 m | 0 |
| HEYSEL | 1 | 59.0 | 1498.2 m | 0 |

## Weight sensitivity

| Scenario | Heat weight | Proximity weight | Top-ten overlap with 60/40 |
|---|---:|---:|---:|
| Heat only | 100% | 0% | 9/10 |
| Balanced | 60% | 40% | 10/10 |
| Proximity only | 0% | 100% | 1/10 |

The balanced top ten shares 9/10 points with heat-only but only 1/10 with proximity-only. The 60/40 screen is therefore strongly heat-led, and emphasizing proximity materially changes membership; it is not a stable priority ordering.

## Balanced screen

The balanced screen uses heat weight 0.6 and proximity weight 0.4. The table shows the ten highest exploratory signals.

| Rank | ID | Street | WBGT indicator (0–100) | Counter distance | Signal |
|---:|---|---|---:|---:|---:|
| 1 | vbx_56561 | Place Rouppe 11 | 88 | 509.8 m | 86.7 |
| 2 | vbx_56558 | Place Rouppe 10 | 87 | 514.4 m | 85.0 |
| 3 | vbx_56544 | Avenue de Stalingrad 106 | 81 | 176.2 m | 84.2 |
| 4 | vbx_56550 | Rue du Midi 177 | 86 | 489.9 m | 84.0 |
| 5 | vbx_56554 | Rue du Midi 177 | 86 | 507.3 m | 83.5 |
| 6 | vbx_56557 | Place Rouppe 1 | 84 | 477.2 m | 81.1 |
| 7 | vbx_56567 | Place Rouppe 4 | 84 | 500.1 m | 80.5 |
| 8 | vbx_56573 | Place Rouppe 18 | 81 | 471.5 m | 76.4 |
| 9 | vbx_56571 | Place Rouppe 17 | 79 | 484.7 m | 72.8 |
| 10 | vbx_56818 | Rue Franklin 68 | 78 | 640.2 m | 67.0 |

## Mobility context

A measured-flow context supplements nearest-counter distance: 97 of 100 sampled trees have their nearest counter covered by the same 2024/01/01 - 2024/01/07 week of 15-minute counts. The remaining 3 trees are nearest to counters without usable measured history.

| Counter | Mean 15-min count | Day-mean range |
|---|---:|---:|
| CJM90 | 23.9 | 16.0 - 35.0 |
| CB1101 | 17.9 | 10.8 - 27.9 |
| CB1142 | 11.2 | 6.4 - 19.4 |
| CB2105 | 11.2 | 8.3 - 14.8 |
| CB1143 | 8.8 | 5.0 - 14.9 |

Flow is measured at the nearest counter, not at the tree, and covers a single winter week; it is contextual mobility evidence, not a seasonal or street-level estimate. See `brussels-tree-counter-flow.json` for per-tree values.

## Interpretation boundary

- The WBGT layer represents one representative hot day in 2016; the seasonal context shows that day was an extreme day inside a comparatively mild summer, so exposure frequency is not represented.
- Counter distance is a spatial context proxy, not bicycle flow, pedestrian use or street occupancy.
- Min–max normalization is sample-relative; rankings change with the weights and sample.
- These points are candidates for follow-up analysis, not planting recommendations or causal findings.
