# Tree signal descriptive analysis

This report answers the working screening question using the committed 100-record feasibility sample.

> Which observed tree areas combine relatively high heat-stress values with proximity to bicycle counters, and therefore merit more detailed field or mobility analysis?

## Sample summary

- Records analyzed: 100
- WBGT pixel: min 50, median 71.5, max 95
- Counter distance: min 8.1 m, median 490.5 m, max 1518.3 m
- Counter history context: 672 fifteen-minute observations from 2024/01/01 to 2024/01/07; mean count 11.2, maximum 44
- High-heat/high-proximity quadrant: 6 points at or above the sample's third quartile on both normalized components

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

## Interpretation boundary

- The WBGT layer represents one representative hot day in 2016.
- Counter distance is a spatial context proxy, not bicycle flow, pedestrian use or street occupancy.
- Min–max normalization is sample-relative; rankings change with the weights and sample.
- These points are candidates for follow-up analysis, not planting recommendations or causal findings.
