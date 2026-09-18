# Trees & Surfaces — stakeholder specification

This is a working specification for the next conversation with a Brussels urban-greening or spatial-planning stakeholder. The stakeholder identity and final decision question still require confirmation.

## Proposed stakeholder

A Brussels team responsible for urban trees, heat adaptation or public-space planning.

**Assumption to confirm:** the team needs a screening view that identifies locations for follow-up analysis, not an automated planting recommendation.

## Proposed decision question

> Which observed tree areas combine relatively high heat-stress values with proximity to bicycle counters, and therefore merit more detailed field or mobility analysis?

This is deliberately narrower than “where should the city plant trees?” The current data does not support a planting recommendation.

## Unit of analysis

One managed-tree record from the Brussels register:

- point coordinates in WGS84;
- street and district fields;
- one sampled WBGT raster pixel;
- nearest bicycle-counter identifier;
- great-circle distance to that counter.

The committed feasibility snapshot contains 100 records.

## Metrics

### Heat exposure

- **Raw measure:** pixel value from the Brussels WBGT mean raster for 24 August 2016.
- **Current range:** 50–95 in the committed sample.
- **Displayed score:** min–max normalization within the sample to 0–100.
- **Interpretation:** relative heat-stress signal for one representative hot day, not a continuous temperature series.

### Mobility context

- **Raw measure:** great-circle distance to the nearest bicycle counter.
- **Displayed score:** inverse min–max normalization within the sample to 0–100.
- **Interpretation:** spatial proximity to observed cycling infrastructure, not bicycle flow, pedestrian use or street occupancy.
- **Required decision:** stakeholder must accept this as a context proxy or provide a stronger mobility measure.

### Exploratory signal

`signal = heat_score × heat_weight + proximity_score × proximity_weight`

Weights are normalized to sum to 1. The interface exposes the weights, displays the normalized values, and must label the result as exploratory.

The current sensitivity artifact compares three scenarios: the heat-only top ten shares 7 of 10 points with the balanced top ten, while the proximity-only top ten shares 3 of 10. This demonstrates that the ranking is weight-sensitive and should not be presented as a stable priority list.

## Acceptance criteria for the next MVP

- [ ] Stakeholder and decision question are confirmed in writing.
- [ ] A replacement or explicit acceptance of nearest-counter distance is documented.
- [ ] Heat-date choice and normalization are justified.
- [ ] Every displayed point can be traced to its source records and join method.
- [ ] Weight sensitivity is reported, including whether the top points change materially.
- [ ] Missing coordinates, NoData pixels and unmatched joins are reported.
- [ ] The interface does not use “street use”, “priority”, “optimal” or “plant here” unless supported by validated measures.
- [ ] Results are described as screening or follow-up candidates, not causal findings.

## Stakeholder interview questions

1. What decision would this screening view change?
2. Is the relevant concern heat exposure, tree maintenance, cycling conflict, pedestrian comfort or another outcome?
3. What spatial unit should decisions use: individual trees, street segments, blocks or cells?
4. Is bicycle-counter proximity useful context, or is another mobility/occupancy source required?
5. Which heat period matters operationally: one hot day, summer average, daily maximum or seasonal exposure?
6. What false positive is more costly: missing a hot location or flagging too many locations?
7. What evidence is required before a location enters a site survey or intervention shortlist?
8. What geographic area and update frequency should the MVP cover?

## Immediate next action

Conduct one stakeholder or coach review using the questions above. Do not expand the model or add canopy/optimization features until the decision question and mobility measure are accepted.
