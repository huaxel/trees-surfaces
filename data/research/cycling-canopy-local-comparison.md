# Local cycling-street canopy comparison

Exploratory, not representative. Selection was fixed before inspecting canopy: existing cycling-street records (type 12, status 1), at least 100 m long, entirely within the EPSG:31370 square [151980,169155,152980,170155]. All 82 cycling records in the frame were retrieved; a separate WFS count confirmed 82. Five met the rules. No outcome-based exclusions.

| gid | Length (m) | Direct tree overlap (%) | Within 2 m (%) | Within 5 m (%) | Longest direct non-overlap (m) |
|---|---:|---:|---:|---:|---:|
| 266 | 563.6 | 31.4 | 66.3 | 89.6 | 158.1 |
| 5630 | 121.9 | 0.0 | 0.9 | 16.9 | 121.9 |
| 5634 | 189.8 | 0.0 | 0.0 | 1.6 | 189.8 |
| 5642 | 268.5 | 1.6 | 10.9 | 26.8 | 262.0 |
| 5643 | 151.7 | 0.0 | 0.0 | 0.0 | 151.7 |

## Findings and boundaries

- Segment 266 contrasts with the original pilot: substantially more mapped tree overlap, but direct overlap is still much lower than proximity within 5 m.
- Do not compare absolute longest gaps without considering segment length. Segments are database units, not independent matched corridors.
- Segment 5634 has an approximate 2022 start date: this analysis overlays current infrastructure geometry on 2021 vegetation, not vegetation observed during cycling-street operation.
- These values describe overhead polygon intersection and proximity, not shade, heat, cooling, or observed cyclist paths. Class 4 is a height-based tree category. Unmapped space is not validated absence.
- All 14,210 intersecting vegetation polygons were cross-checked against a scan of 5,790,723 source records. The 82 invalid tree/high-shrub polygons were repaired with no area change; alternate repair yielded identical reported overlap and longest-gap values for all 30 conditions.
- The original 73 m segment 5644 is excluded by the preselected length rule, not its canopy result.

Sources: [VUB / Gallez et al. 2024, Zenodo 13869065](https://zenodo.org/records/13869065), CC BY 4.0; Brussels Mobility WFS bm_bike:ac. Exact request, raw precision, limitations and verification are in `cycling-canopy-local-comparison.json`. Reproduction script and downloaded inputs remain in ignored `.cache/vub-canopy-2021/`; this is not yet an integrated project pipeline.
