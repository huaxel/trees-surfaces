# Stakeholder brief: counter proximity or measured bicycle flow?

## Decision needed

Should the screening view retain nearest-counter distance as a **proximity context**, use the nearest counter's measured count as an **activity context**, or keep both descriptive and outside the ranking until a street-level mobility measure is available?

The current ranking uses distance. This comparison is exploratory and does not change it.

## Evidence in the feasibility sample

- The committed flow snapshot covers **97 of 100 trees** through their nearest counter. It represents five counters and one winter week, **2024-01-01 to 2024-01-07**, using 15-minute counts.
- Each tree inherits its nearest counter's one-week mean, so the matched tree sample has only **five distinct flow values**, repeated across trees.
- Across the 97 matched trees, raw nearest-counter distance and assigned counter flow have a weak negative association (Pearson *r* = −0.20; Spearman *rho* = −0.23). This is descriptive only: the 97 tree rows do not represent 97 independent flow measurements.
- A **flow-only** top ten shared **0 of 10** points with the current 60/40 balanced top ten (restricted to the 97 matched trees), because all ten sit on the single highest-flow counter: the matched sample has only five distinct flow values, so a flow-only ranking is really a counter ranking. The proximity-only top ten also shared **0 of 10**.
- A **60/40 heat-plus-min–max-flow** alternative — the comparison the sentence above used to describe — shares **9 of 10** with the current balanced top ten. An earlier version of this brief attributed the 0 of 10 to that weighted alternative; it does not reproduce, and the difference matters. The reading is not "any flow input reshuffles the top ten" but "the current screen is heat-led and already agrees with a weighted flow input, while a flow-only ranking cannot be formed from five counters at all".

  Both figures are recomputed from committed artifacts and pinned in the canopy test suite. The evidence, the counter network and the season and outage findings are in [`mobility-data-candidates.md`](mobility-data-candidates.md).

| Nearest counter | Sample trees | Mean 15-minute count | Range of daily means |
| --- | ---: | ---: | ---: |
| CB1101 | 33 | 17.872 | 10.760–27.875 |
| CB1142 | 31 | 11.226 | 6.385–19.417 |
| CJM90 | 15 | 23.906 | 16.042–35.021 |
| CB1143 | 9 | 8.769 | 5.021–14.875 |
| CB2105 | 9 | 11.190 | 8.333–14.844 |

The alternative score uses the same heat scores as the current 100-tree sample, min–max normalizes flow across the 97 matched trees, and applies 60/40 weights. The three trees without measured flow are excluded, not imputed; the current balanced top ten happens to be fully inside the matched set. Score ties use the existing ID tie-break.

Within the sampled week, each counter has 96 observations on each of seven days. Daily means vary, as shown by the table's ranges, but recomputing the flow-based 60/40 top ten separately for each day yields 7–10 points in common with the weekly-mean top ten (10/10 on Tuesday–Friday; 7/10 on January 1 and 7; 8/10 on January 6). This is only within-week stability; it does not show that a January week represents summer or annual mobility.

## Limits

Counter flow is measured at five counter locations, not at the trees, streets, or walking paths. The single January week is not a seasonal mobility estimate and is not temporally aligned with the 24 August 2016 WBGT raster. The 97 matched points are a feasibility sample, not a representative city sample. Min–max scores and top-ten membership depend on this sample and the chosen weights. Neither measure establishes street use or exposure.

## Suggested discussion

- Keep distance as an explicitly labelled spatial-proximity context, with measured flow shown separately as counter activity.
- If the decision requires cycling exposure, specify the relevant season and seek broader, temporally aligned counts or a street-level route/flow measure before ranking by mobility.
- Record whether any mobility measure should enter the screening score only after the stakeholder defines the decision, spatial unit, period, and acceptable evidence.

## Sources and reproducibility

The source is [Brussels Mobility's real-time bicycle-counter data](https://data.mobility.brussels/en/info/rt_counting/), credited to Brussels Mobility and licensed CC0 in the committed snapshot. The comparison uses `brussels-tree-counter-flow.json`, `brussels-tree-bike-nearest.json`, `brussels-tree-heat-sample.json`, and the balanced scenario in `tree-signal-sensitivity.json`. This is a discussion aid, not a recommendation to change the ranking or a claim of causal effect.
