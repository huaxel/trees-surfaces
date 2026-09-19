# Trees & Surfaces — prototype review

## Overview

The interaction frames a narrow descriptive question: where do sampled managed trees combine higher WBGT pixels with closer bicycle counters? The exploratory signal is calculated from the real heat and nearest-counter joins, with both inputs labelled as proxies. It is not an intervention recommendation. A BAP would still need a stakeholder-defined objective, a defensible heat measure and a validated mobility measure before optimisation is appropriate.

## Evidence now available

Reproducible 100-record snapshots from Brussels' managed-tree register (31,643 records reported by the API) and remarkable-tree register (582 records), plus 18 current Brussels bicycle-counter locations. The two tree catalogues state CC BY 4.0 with their publisher/catalogue attributions, while Brussels Mobility states CC0 1.0 for the counter source; those terms are recorded in the source inventory and displayed in the prototype.

A first spatial join links each sampled tree to its nearest counter by great-circle distance. Five seven-day counter snapshots add 672 fifteen-minute observations each, providing measured nearest-counter flow context for 97/100 trees. A committed completeness audit reports 100/100 valid coordinates, heat joins, non-NoData pixels and nearest-counter joins; it names the three optional flow-context gaps and their two uncovered counters (`CB02411`, `CJE181`).

A real Brussels WBGT raster is also available and is represented in the prototype by a downsampled visual preview. Its authoritative Brussels Environment metadata defines normalized 0–100 WBGT indicator pixels for 24 August 2016 and records CC BY 4.0 reuse with source attribution. The interface ranks observed tree points using the joined raster pixel and nearest-counter distance, positions the visible points in a relative geographic preview without implying a basemap, and links each displayed point to its source tree record.

A committed descriptive report justifies the single 2016 WBGT scenario, records normalization and missingness, and finds 1 point in the sample's high-heat/high-proximity quadrant. The sensitivity report shows that the balanced top ten shares 9 points with heat-only and 1 with proximity-only, confirming that the ranking is dominated by heat under the current 60/40 weights.

A pure-Python/Pillow join samples the raster at all 100 tree points after an EPSG seven-parameter WGS84-to-Belgian-1972 datum transform and Belgian Lambert 72 projection; sampled values range from 51 to 88 with no NoData points in this snapshot. The managed-tree sample has coordinates, street and district fields, and the remarkable-tree source adds species, circumference, crown diameter, status and heritage links. Counter flow is measured at counters, not trees, and is one winter week rather than city-wide or seasonal usage. A versioned one-row worksheet now binds the proposed decision question to the completeness and sensitivity evidence, but no stakeholder response is recorded.

## Current conclusion and next steps

The prototype demonstrates data integration, spatial join feasibility, and an explicit interpretation boundary, but its feasibility bottleneck remains data integration and causal/interpretive validity:

- Counter distance is a context proxy, not pedestrian or cycling volume.
- The WBGT layer is a single representative hot-day model from 2016, not a seasonal or multi-year temperature series.
- Min-max normalization is sample-relative; rankings shift with sample composition and weighting.

**Still needed:** stakeholder acceptance or revision of the objective and mobility context, followed by a proper multi-date/statistical analysis. Do not add more interface features until the analytical definition of done is met.
