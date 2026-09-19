# Tree signal descriptive analysis

This report answers the working screening question using the committed 100-record feasibility sample.

> Which observed tree areas combine relatively high heat-stress values with proximity to bicycle counters, and therefore merit more detailed field or mobility analysis?

## Heat data and normalization

- The heat input is the regional urban-heat-island model published by Brussels Environment: mean 24-hour Wet Bulb Globe Temperature for one representative hot day (2016-08-24). The public WMS exposes this single scenario layer; no multi-date or seasonal open layer exists for the region.
- Normalization is min-max within the committed 100-record sample (0-100), which makes scores sample-relative; rankings shift with the weights and with a different sample.
- Missing data: all 100 joined points have non-NoData WBGT pixels, so there is no heat missingness to impute in this snapshot.
- Multi-date alternatives (ERA5 2 m temperature, satellite land-surface temperature) are documented as future options and are out of scope for this feasibility sample.

## Traceability

Every displayed point can be traced to its source record and join method:
- Source record: the managed-tree register entry, reachable by id, e.g. `https://bruxellesdata.opendatasoft.com/api/explore/v2.1/catalog/datasets/arbres-bomen-vbx-be-bm/records?where=id%3D%27vbx_56544%27`.
- Heat join: WBGT raster pixel value extracted at the tree's coordinates from the regional layer (see `join_heat.py`).
- Mobility join: great-circle distance to the nearest bicycle counter (see the committed `brussels-tree-bike-nearest.json`); measured-flow context for the nearest counter is in `brussels-tree-counter-flow.json`.
- Ranking: signal = heat_score × weight + proximity_score × weight, min-max scores, weights exposed in the interface.

## Sample summary

- Records analyzed: 100 of 31,643 managed-tree records reported by the source (0.32% of the reported register)
- Sampling note: the committed records are a feasibility snapshot, not a probability sample or city-wide estimate
- WBGT pixel: min 50, median 71.5, max 95
- Counter distance: min 8.1 m, median 490.5 m, max 1518.3 m
- Counter history context: 672 fifteen-minute observations from 2024/01/01 to 2024/01/07; mean count 11.2, maximum 44
- High-heat/high-proximity quadrant: 6 points at or above the sample's third quartile on both normalized components

## District context

District counts describe this 100-record sample only; they are not district prevalence estimates.

| District | Points | Mean WBGT pixel | Median counter distance | High-high points |
|---|---:|---:|---:|---:|
| QUARTIER ROYAL | 33 | 65.2 | 285.5 m | 4 |
| STALINGRAD | 9 | 86.9 | 489.9 m | 1 |
| QUARTIER EUROPEEN | 5 | 75.8 | 33.8 m | 1 |
| SQUARES | 35 | 65.0 | 559.3 m | 0 |
| BEGUINAGE - DIXMUDE | 15 | 84.5 | 564.6 m | 0 |
| HEEMBEEK | 2 | 79.0 | 1509.0 m | 0 |
| HEYSEL | 1 | 61.0 | 1498.2 m | 0 |

## Balanced screen

The balanced screen uses heat weight 0.6 and proximity weight 0.4. The table shows the ten highest exploratory signals.

| Rank | ID | Street | WBGT pixel | Counter distance | Signal |
|---:|---|---|---:|---:|---:|
| 1 | vbx_56544 | Avenue de Stalingrad 106 | 89 | 176.2 m | 87.5 |
| 2 | vbx_56635 | Boulevard de Dixmude 8 | 95 | 491.2 m | 87.2 |
| 3 | vbx_56870 | Rue de la Loi 170 | 83 | 33.8 m | 83.3 |
| 4 | vbx_56587 | Boulevard de Dixmude 9 | 90 | 411.3 m | 82.7 |
| 5 | vbx_58580 | Rue de la Loi 16 | 84 | 174.3 m | 80.9 |
| 6 | vbx_56637 | Boulevard de Dixmude 6 | 90 | 485.3 m | 80.7 |
| 7 | vbx_56573 | Place Rouppe 18 | 89 | 471.5 m | 79.7 |
| 8 | vbx_58582 | Rue de la Loi 3 | 83 | 197.2 m | 79.0 |
| 9 | vbx_56554 | Rue du Midi 177 | 89 | 507.3 m | 78.8 |
| 10 | vbx_56604 | Boulevard de Dixmude 65 | 91 | 608.6 m | 78.8 |

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
