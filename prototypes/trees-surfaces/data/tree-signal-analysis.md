# Tree signal descriptive analysis

This report answers the working screening question using the committed 100-record feasibility sample.

> Which observed tree areas combine relatively high heat-stress values with proximity to bicycle counters, and therefore merit more detailed field or mobility analysis?

## Heat data and normalization

- The heat input is the regional urban-heat-island model published by Brussels Environment: mean 24-hour Wet Bulb Globe Temperature for one representative hot day (2016-08-24). The public WMS exposes this single scenario layer; no multi-date or seasonal open layer exists for the region.
- The source raster stores a normalized 0–100 WBGT indicator, not degrees Celsius. The prototype then min-max normalizes those source values again within the committed 100-record sample to calculate heat scores; rankings therefore shift with the weights and with a different sample.
- The authoritative ISO metadata identifies the dataset as `BRU_ENVI_73b4f29a-cff0-4d6a-a239-cb99d3140531`, published by Brussels Environment / Leefmilieu Brussel under CC BY 4.0 with source attribution.
- Missing data: all 100 joined points have non-NoData WBGT pixels, so there is no heat missingness to impute in this snapshot.
- Multi-date alternatives (ERA5 2 m temperature, satellite land-surface temperature) are documented as future options and are out of scope for this feasibility sample.

## Traceability

Every displayed point can be traced to its source record and join method:
- Source record: the managed-tree register entry, reachable by id, e.g. `https://bruxellesdata.opendatasoft.com/api/explore/v2.1/catalog/datasets/arbres-bomen-vbx-be-bm/records?where=id%3D%27vbx_56544%27`.
- Heat join: WBGT raster pixel value extracted after the EPSG seven-parameter WGS84-to-Belgian-1972 datum transform and Belgian Lambert 72 projection (see `join_heat.py`).
- Mobility join: great-circle distance to the nearest bicycle counter (see the committed `brussels-tree-bike-nearest.json`); measured-flow context for the nearest counter is in `brussels-tree-counter-flow.json`.
- Ranking: signal = heat_score × weight + proximity_score × weight, min-max scores, weights exposed in the interface.

## Sample summary

- Records analyzed: 100 of 31,643 managed-tree records reported by the source (0.32% of the reported register)
- Sampling note: the committed records are a feasibility snapshot, not a probability sample or city-wide estimate
- Source-normalized WBGT indicator pixel (0–100, not °C): min 51, median 68.0, max 88
- Counter distance: min 8.1 m, median 490.5 m, max 1518.3 m
- Counter history context: 672 fifteen-minute observations from 2024/01/01 to 2024/01/07; mean count 11.2, maximum 44
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

Measured-flow context is unavailable for IDs vbx_58411, vbx_58413, vbx_58589; the affected nearest counter set is CB02411, CJE181, with no committed history snapshot. All core heat and nearest-counter joins are complete.

## District context

District counts describe this 100-record sample only; they are not district prevalence estimates.

| District | Points | Mean WBGT indicator (0–100) | Median counter distance | High-high points |
|---|---:|---:|---:|---:|
| STALINGRAD | 9 | 84.0 | 489.9 m | 1 |
| SQUARES | 35 | 72.8 | 559.3 m | 0 |
| QUARTIER ROYAL | 33 | 56.1 | 285.5 m | 0 |
| BEGUINAGE - DIXMUDE | 15 | 68.4 | 564.6 m | 0 |
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

A measured-flow context now supplements nearest-counter distance: 97 of 100 sampled trees have their nearest counter covered by the same 2024/01/01 - 2024/01/07 week of 15-minute counts. The three remaining trees are nearest to counters without committed history.

| Counter | Mean 15-min count | Day-mean range |
|---|---:|---:|
| CJM90 | 23.9 | 16.0 - 35.0 |
| CB1101 | 17.9 | 10.8 - 27.9 |
| CB1142 | 11.2 | 6.4 - 19.4 |
| CB2105 | 11.2 | 8.3 - 14.8 |
| CB1143 | 8.8 | 5.0 - 14.9 |

Flow is measured at the nearest counter, not at the tree, and covers a single winter week; it is contextual mobility evidence, not a seasonal or street-level estimate. See `brussels-tree-counter-flow.json` for per-tree values.

## Interpretation boundary

- The WBGT layer represents one representative hot day in 2016.
- Counter distance is a spatial context proxy, not bicycle flow, pedestrian use or street occupancy.
- Min–max normalization is sample-relative; rankings change with the weights and sample.
- These points are candidates for follow-up analysis, not planting recommendations or causal findings.
