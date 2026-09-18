# Prototype review

## Trees & Surfaces

The interaction makes the candidate's identity clear: it is a decision-support tool about trade-offs, not merely a tree map. The main unresolved issue is that the current priority score is illustrative. The BAP would need one defined intervention question, a defensible heat measure and a clearly labelled mobility proxy before the score could be interpreted.

**Evidence now available:** reproducible 100-record snapshots from Brussels' managed-tree register (31,643 records reported by the API) and remarkable-tree register (582 records). The managed-tree sample has coordinates, street and district fields, and the remarkable-tree source adds species, circumference, crown diameter, status and heritage links. **Still needed:** one heat/canopy layer, one mobility dataset and a stakeholder-defined objective.

## Three Ages of a Brussels Building

The interaction makes the candidate's identity clear: the product is an evidence-led building-history explorer. The important design choice is to show disagreement and uncertainty rather than collapse all information into one “true” construction year.

A first public source is now available: the City of Brussels dataset describing 34 Grand Place buildings, including restoration/history and facade-description fields. The main unresolved issues remain image licensing, annotation effort and whether historical aerial imagery can support structural-age claims at the required scale.

The 34 source records all contain history text and 32 contain facade-description text, which is promising for a manually curated pilot. **Still needed:** a small permitted pilot set, a labelling protocol, two or more historical image epochs and a confidence/evidence model.

## Current conclusion

Both concepts survive a first product-shape test, but they have different feasibility bottlenecks:

- **Trees & Surfaces:** data integration and causal/interpretive validity.
- **Three Ages:** imagery access and label validity.

The next prototype iteration should use real data for only one narrowly defined question per candidate, rather than adding more interface features.
