# Trees & Surfaces — next iteration

The prototype is ready for review as an **evidence-shaped prototype**, not a finished analysis.

## Question tested

Where do sampled managed trees combine higher WBGT pixels with closer bicycle counters?

## Now demonstrated

- 100 managed-tree points joined to a WBGT raster pixel;
- 100 points joined to their nearest bicycle counter;
- a transparent, normalized exploratory signal;
- relative geographic positioning and source links;
- explicit warnings that proximity is not street use;
- a machine-readable completeness audit with complete core joins and three named optional flow-context gaps;
- weight sensitivity showing the 60/40 top ten overlaps 9/10 with heat-only but only 1/10 with proximity-only;
- a versioned stakeholder proposal and provenance-safe one-row review handoff, still awaiting a real response.

## Definition of done for an analytical MVP

- choose one stakeholder and one intervention or descriptive decision;
- replace the single heat date with a justified multi-date or seasonal measure (progress: **multi-date heat data was found and measured, so this is now a choice rather than a gap.** VITO publishes daily 100 m WBGT for 2008–2017 from the UrbClim model family used by the committed raster. On the same tree sample, the 2016-08-24 and ten-year seasonal-mean heat-only top tens from the VITO daily-max series share 7/10. Their overlaps with the current balanced screen are 3/10 and 0/10 (hot-day count also 0/10), but those cross-screen comparisons differ in WBGT semantics and scoring and do not isolate heat-period effects. ERA5 supplies an independent coarse temporal context; a sensor-complete Landsat audit was also run and rejected (no scene on the reference date, 31.4% of eligible tree-date pairs passing basic QA, 10.8% at ST_QA ≤3 K). All alternatives remain context until a stakeholder chooses the heat period. See [`heat-season-stakeholder-brief.md`](heat-season-stakeholder-brief.md));
- use a validated mobility measure rather than nearest-counter distance alone (progress: a one-week winter flow context for five counters covers 97/100 trees; only five distinct flow values are assigned across them. An exploratory 60/40 flow alternative shares 0/10 points with the current balanced top ten, while daily top tens within that week share 7–10/10 with the weekly mean. This shows metric sensitivity, not which measure is valid. See [`mobility-measure-stakeholder-brief.md`](mobility-measure-stakeholder-brief.md); distance still drives the ranking pending stakeholder agreement);
- document normalization, missing data and sensitivity to the weights (complete for the feasibility snapshot in the JSON artifact, Markdown report and interface);
- keep the output descriptive unless a causal design is established.

## Decision boundary

Do not add more interface features until the prototype satisfies its analytical definition of done. The next work depends on stakeholder clarification of the decision question and mobility measure.
