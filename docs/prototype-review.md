# Prototype review

## Trees & Surfaces

The interaction now frames a narrower descriptive question: where do sampled managed trees combine higher WBGT pixels with closer bicycle counters? The exploratory signal is calculated from the real heat and nearest-counter joins, with both inputs labelled as proxies. It is not an intervention recommendation. A BAP would still need a stakeholder-defined objective, a defensible heat measure and a validated mobility measure before optimisation is appropriate.

**Evidence now available:** reproducible 100-record snapshots from Brussels' managed-tree register (31,643 records reported by the API) and remarkable-tree register (582 records), plus 18 current Brussels bicycle-counter locations. A first spatial join now links each sampled tree to its nearest counter by great-circle distance. A seven-day sample from one counter adds 672 fifteen-minute observations. A real Brussels WBGT raster is also available and is represented in the prototype by a downsampled visual preview. The interface now ranks observed tree points using the joined raster pixel and nearest-counter distance, and positions the visible points in a relative geographic preview without implying a basemap. A pure-Python/Pillow join samples the raster at all 100 tree points after transforming WGS84 coordinates to Belgian Lambert 72; sampled values range from 50 to 95 with no NoData points in this snapshot. The managed-tree sample has coordinates, street and district fields, and the remarkable-tree source adds species, circumference, crown diameter, status and heritage links. Nearest-counter proximity is only an integration feature, not a measure of street use; the counter history is a local flow signal, not city-wide usage. **Still needed:** a stakeholder-defined objective and a proper multi-date/statistical analysis.

## Three Ages of a Brussels Building

The interaction makes the candidate's identity clear: the product is an evidence-led building-history explorer. The important design choice is to show disagreement and uncertainty rather than collapse all information into one “true” construction year.

A first public source is now available: the City of Brussels dataset describing 34 Grand Place buildings, including restoration/history and facade-description fields. The committed snapshot now preserves its public dataset endpoint. The main unresolved issues remain image licensing, annotation effort and whether historical aerial imagery can support structural-age claims at the required scale.

The 34 source records all contain history text and 32 contain facade-description text. A six-record source-linked pilot now makes the evidence gap explicit: it separates source-described facade style, documented reconstruction dates and the still-missing register/image annotations. **Still needed:** a permitted pilot image set, two or more historical image epochs and reviewed labels.

## Current conclusion

Both concepts survive a first product-shape test, but they have different feasibility bottlenecks:

- **Trees & Surfaces:** data integration and causal/interpretive validity.
- **Three Ages:** imagery access and label validity.

The next prototype iteration should use real data for only one narrowly defined question per candidate, rather than adding more interface features.
