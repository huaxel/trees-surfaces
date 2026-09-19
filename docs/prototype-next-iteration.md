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
- replace the single heat date with a justified multi-date or seasonal measure (progress: the 2016 regional WBGT choice, normalization and missingness are documented; the WMS exposes no multi-date layer, so ERA5 or satellite LST remains future work);
- use a validated mobility measure rather than nearest-counter distance alone (progress: a measured-flow context — nearest-counter mean flow for one week, five counters, 97/100 trees — is committed as `brussels-tree-counter-flow.json` and reported in the analysis; distance still drives the ranking until the stakeholder question accepts a flow-based alternative);
- document normalization, missing data and sensitivity to the weights (complete for the feasibility snapshot in the JSON artifact, Markdown report and interface);
- keep the output descriptive unless a causal design is established.

## Decision boundary

Do not add more interface features until the prototype satisfies its analytical definition of done. The next work depends on stakeholder clarification of the decision question and mobility measure.
