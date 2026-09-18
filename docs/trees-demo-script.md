# Trees & Surfaces — stakeholder demo script

## Goal

Use the prototype to test whether a Brussels urban-greening or heat-adaptation team finds the screening question useful. This is a requirements conversation, not a results presentation.

## Five-minute flow

1. **State the question**
   > Which observed tree areas combine relatively high heat-stress values with proximity to bicycle counters, and therefore merit more detailed field or mobility analysis?

2. **Set the boundary**
   Explain that the prototype uses 100 sampled managed-tree records, one 2016 WBGT raster, and nearest-counter distance. Counter proximity is context only; it is not street use or bicycle flow.

3. **Show the relative spatial preview**
   Select a visible point and explain its raw WBGT pixel, nearest counter and distance. Emphasize that the preview has no basemap and does not recommend planting.

4. **Change the weights**
   Move from balanced weights toward heat-only and proximity-only. Ask whether the changing top points is useful for screening or confusing without a stronger mobility measure.

5. **Show sensitivity evidence**
   Point out that the balanced top ten overlaps 7/10 with heat-only and 3/10 with proximity-only. Open the JSON report or CSV export if the stakeholder wants to inspect individual records.

6. **Close with the decision**
   Ask what follow-up action a high-signal point should trigger: field survey, extra temperature measurement, mobility analysis, maintenance review or nothing.

## Questions to capture

- Is the proposed screening question relevant to an actual decision?
- Is the tree point the right unit, or should results aggregate to streets or blocks?
- Is nearest-counter distance useful context?
- Which heat period matters operationally?
- What evidence would justify adding a point to a follow-up shortlist?
- What would make the output misleading or unsafe to use?

## Success signal

The demo succeeds if the stakeholder can name a concrete follow-up decision and accepts the limitations of the current proxies. If they ask for a planting recommendation or city-wide ranking immediately, freeze the interface and resolve the measurement problem first.
