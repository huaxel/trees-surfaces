# Prototype next iteration

The current spikes are ready for review as **evidence-shaped prototypes**, not finished analyses.

## Trees & Surfaces

**Question tested:** where do sampled managed trees combine higher WBGT pixels with closer bicycle counters?

**Now demonstrated:**

- 100 managed-tree points joined to a WBGT raster pixel;
- 100 points joined to their nearest bicycle counter;
- a transparent, normalized exploratory signal;
- relative geographic positioning and source links;
- explicit warnings that proximity is not street use;
- a machine-readable completeness audit with complete core joins and three named optional flow-context gaps;
- weight sensitivity showing the 60/40 top ten overlaps 9/10 with heat-only but only 1/10 with proximity-only;
- a versioned stakeholder proposal and provenance-safe one-row review handoff, still awaiting a real response.

**Definition of done for an analytical MVP:**

- choose one stakeholder and one intervention or descriptive decision;
- replace the single heat date with a justified multi-date or seasonal measure (progress: the 2016 regional WBGT choice, normalization and missingness are documented; the WMS exposes no multi-date layer, so ERA5 or satellite LST remains future work);
- use a validated mobility measure rather than nearest-counter distance alone (progress: a measured-flow context — nearest-counter mean flow for one week, five counters, 97/100 trees — is committed as `brussels-tree-counter-flow.json` and reported in the analysis; distance still drives the ranking until the stakeholder question accepts a flow-based alternative);
- document normalization, missing data and sensitivity to the weights (complete for the feasibility snapshot in the JSON artifact, Markdown report and interface);
- keep the output descriptive unless a causal design is established.

## Three Ages

**Question tested:** can a building record show separate register, facade and structural evidence without collapsing uncertainty into one date?

**Now demonstrated:**

- 34 real Grand Place source records;
- six source-linked pilot cases;
- explicit separation between source description and image-derived annotation;
- a visible annotation protocol and next-step evidence notes;
- three aligned area-level structural epochs (1930–1935, 1996 and 2022);
- public dataset provenance links.

**Definition of done for a curated MVP:**

- obtain permission for at least two historical image epochs (source access complete for the curated pilot: aligned BruCiel 1930–1935 and 1996 CC0 orthos plus the 2022 open-data ortho are committed; five cases have 1941–1942 KIK-IRPA facade previews under CC BY 4.0. La Balance has an exact-case 1878 British Library engraving with no known copyright restrictions and a 2011 Wikimedia Commons photograph under CC BY-SA 3.0. Exact capture-year interpretation and visible-change review remain pending);
- add an official register-year source for each pilot case (progress: all six source claims now expose their actual date semantics and City-history comparison in a provenance-safe register worksheet. The reviewer must choose whether each date is an acceptable MVP proxy, reconstruction evidence only, or a rejected mapping);
- annotate facade period and structural change with source, epoch, rationale and reviewer (progress: seven facade rows and six case-level structural-comparison rows now have separate provenance-safe worksheets and compiled JSON outputs; eighteen aligned building-centred crops make the three structural epochs reviewable, while observations and reviewer metadata remain pending);
- record inter-annotator disagreement before assigning confidence;
- publish the image licence and a reproducible annotation export.

## Decision boundary

Do not add more interface features until one candidate satisfies its analytical or annotation definition of done. The next work depends on stakeholder clarification for Trees & Surfaces and data/licensing access for Three Ages.
