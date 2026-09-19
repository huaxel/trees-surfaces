# Prototype next iteration

The current spikes are ready for review as **evidence-shaped prototypes**, not finished analyses.

## Trees & Surfaces

**Question tested:** where do sampled managed trees combine higher WBGT pixels with closer bicycle counters?

**Now demonstrated:**

- 100 managed-tree points joined to a WBGT raster pixel;
- 100 points joined to their nearest bicycle counter;
- a transparent, normalized exploratory signal;
- relative geographic positioning and source links;
- explicit warnings that proximity is not street use.

**Definition of done for an analytical MVP:**

- choose one stakeholder and one intervention or descriptive decision;
- replace the single heat date with a justified multi-date or seasonal measure (progress: the 2016 regional WBGT choice, normalization and missingness are documented; the WMS exposes no multi-date layer, so ERA5 or satellite LST remains future work);
- use a validated mobility measure rather than nearest-counter distance alone (progress: a measured-flow context — nearest-counter mean flow for one week, five counters, 97/100 trees — is committed as `brussels-tree-counter-flow.json` and reported in the analysis; distance still drives the ranking until the stakeholder question accepts a flow-based alternative);
- document normalization, missing data and sensitivity to the weights;
- keep the output descriptive unless a causal design is established.

## Three Ages

**Question tested:** can a building record show separate register, facade and structural evidence without collapsing uncertainty into one date?

**Now demonstrated:**

- 34 real Grand Place source records;
- six source-linked pilot cases;
- explicit separation between source description and image-derived annotation;
- a visible annotation protocol and next-step evidence notes;
- public dataset provenance links.

**Definition of done for a curated MVP:**

- obtain permission for at least two historical image epochs (partial: two modern epochs — 1996 CC0 and 2022 open data — are committed and legally reusable; the historical 1940s epoch remains pending on the archives request and the retired 1944 WMS);
- add an official register-year source for each pilot case (progress: three cases now carry sourced `proxy` years via Wikidata inception claims referenced to Brussels heritage register records, with agreement/disagreement recorded; three remain pending);
- annotate facade period and structural change with source, epoch, rationale and reviewer;
- record inter-annotator disagreement before assigning confidence;
- publish the image licence and a reproducible annotation export.

## Decision boundary

Do not add more interface features until one candidate satisfies its analytical or annotation definition of done. The next work depends on stakeholder clarification for Trees & Surfaces and data/licensing access for Three Ages.
