# Trees & Surfaces — stakeholder specification

This is a working specification for the next conversation with a Brussels urban-greening or spatial-planning stakeholder. The final decision question and external stakeholder confirmation still remain open.

## Confirmed working direction

- **Stakeholder:** urban greening / heat adaptation team.
- **Use of mobility data:** retain nearest bicycle-counter distance as a clearly labelled context proxy.
- **Boundary:** the team needs a screening view for follow-up analysis, not an automated planting recommendation.

This is a project-level working decision; it should still be validated with the eventual coach or stakeholder.

## Conservative interim recommendation (not accepted)

The project-owner review is recorded as **needs more evidence**. The following direction is a recommendation for discussion, not stakeholder acceptance or a change to the ranking:

- Keep the existing 24 August 2016 WBGT input as the ranking's heat measure for now; show the ten-summer ERA5 result and the 100 m daily WBGT result only as separate context. In the VITO daily-maximum series, the reference-day and ten-year seasonal-mean heat-only top tens share 7/10 trees. Their cross-screen overlaps with the current balanced ranking are 3/10 and 0/10 respectively, but those comparisons also differ in WBGT output semantics and scoring, so do not attribute them to heat period alone. The exploratory Landsat audit remains rejected (no scene on the reference date, only 31.4% of eligible tree-date pairs passing basic QA, 10.8% passing the illustrative ST_QA ≤3 K filter).
- Keep nearest-counter distance explicitly labelled as proximity context; show measured flow separately. The flow snapshot covers five counters for one winter week, assigns only five distinct values across 97 trees, and its alternative 60/40 top ten has no overlap with the current balanced top ten.
- Retain individual tree records as the traceable analysis unit, not as an intervention unit. A stakeholder still needs to decide whether follow-up should target trees, street segments, blocks, or another unit.
- Leave false-positive preference and evidence threshold undecided. Do not use the current screen to automate site selection or recommend planting.

The recommendation is deliberately conservative because both candidate replacements have substantial temporal or spatial limitations. External stakeholder review is still required before accepting any measure or changing the model.

## Working MVP decision question

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
- **Current range:** 51–88 in the committed sample.
- **Displayed score:** min–max normalization within the sample to 0–100.
- **Interpretation:** relative heat-stress signal for one representative hot day, not a continuous temperature series.

### Mobility context

- **Raw measure:** great-circle distance to the nearest bicycle counter.
- **Displayed score:** inverse min–max normalization within the sample to 0–100.
- **Interpretation:** spatial proximity to observed cycling infrastructure, not bicycle flow, pedestrian use or street occupancy.
- **Measured-flow supplement:** a new context snapshot (`brussels-tree-counter-flow.json`) attaches each tree's nearest-counter mean measured flow over the same one-week period (1–7 January 2024, 15-minute counts) for five counters, covering 97 of 100 trees. It is stored as contextual evidence next to distance, not folded into the ranking, and is explicitly not a seasonal or street-level estimate.
- **Current MVP decision:** retain distance as a context proxy and never label it as street usage, bicycle flow or occupancy; use the measured-flow supplement to inform the stakeholder question about a stronger mobility measure.

### Exploratory signal

`signal = heat_score × heat_weight + proximity_score × proximity_weight`

Weights are normalized to sum to 1. The interface exposes the weights, displays the normalized values, and must label the result as exploratory.

The current descriptive report finds 1 of 100 points at or above the sample's third quartile on both normalized heat and proximity scores. The sensitivity artifact compares three scenarios: the heat-only top ten shares 9 of 10 points with the balanced top ten, while the proximity-only top ten shares 1 of 10. It also stores all 100 points ranked under the balanced 60/40 weights so each displayed point can be traced and exported. This shows that the current balanced ranking is strongly heat-led and should not be presented as a stable priority list.

## Acceptance criteria for the next MVP

- [x] Working stakeholder and decision direction are recorded in writing.
- [x] Working MVP screening question is recorded in writing.
- [x] Retention of nearest-counter distance as a clearly labelled context proxy is documented.
- [x] Heat-date choice and normalization are justified (single regional WBGT scenario documented, min-max sample normalization, no heat missingness; multi-date options measured rather than deferred — see [`heat-season-stakeholder-brief.md`](heat-season-stakeholder-brief.md)).
- [x] Every displayed point can be traced to its source records and join method (per-point source-record links in the interface; heat and mobility join methods documented in the analysis report).
- [x] Weight sensitivity is reported, including material top-ten membership change under proximity-only weighting.
- [x] Missing coordinates, NoData pixels and unmatched joins are reported; all core joins are complete and the three measured-flow gaps are named.
- [x] The interface explicitly negates unsupported street-use and intervention interpretations and does not present points as priorities, optima or planting locations.
- [x] Results are described as screening or follow-up candidates, not causal findings.

## Review handoff

The exact working proposal is versioned in `tree-stakeholder-proposal.json`. `tree-stakeholder-review.csv` binds one stakeholder response to that proposal, the current completeness audit and the 9/10 versus 1/10 sensitivity result. A completed review must identify the reviewer and role, use an allowed status (`accepted`, `accepted with changes`, `needs more evidence`, or `rejected`), and record false-positive preference, evidence threshold and notes. Accepted statuses must also state the agreed decision question, unit, mobility measure and heat period; negative statuses may leave those accepted-value fields blank and explain the outcome in notes. Regeneration refuses to carry the response onto changed proposal evidence; completed responses compile to `tree-stakeholder-reviews.json` for the Julia application.

## Draft outreach invitation (not sent)

**Subject:** Review request: Brussels tree heat and mobility screening prototype

Hello [name],

We have an exploratory screening prototype that joins a 100-tree feasibility sample to one Brussels WBGT raster day and nearby bicycle counters. It is intended to identify candidates for follow-up analysis, not to recommend planting or rank intervention sites. The project-owner review is recorded as **needs more evidence**; the current ranking is unchanged, and we are seeking your guidance before deciding what the screen should represent.

Would you be available for a short review? The main questions are:

- What decision should this screen support, and should its analysis unit be an individual tree, street segment, block, or another area?
- Should the single-day WBGT remain the ranking input, with ERA5 and the 100 m WBGT archive shown only as context, or is a specific multi-date heat period required first — and if so, is it a seasonal mean, a hot-day count, or the hottest day?
- Is nearest-counter distance useful context, should measured counter activity remain separate, or is another mobility measure needed?
- What trade-off between missed sites and false alarms is acceptable, and what evidence should trigger manual follow-up?

For context, see [`heat-season-stakeholder-brief.md`](heat-season-stakeholder-brief.md), [`mobility-measure-stakeholder-brief.md`](mobility-measure-stakeholder-brief.md), and the [`conservative interim recommendation`](#conservative-interim-recommendation-not-accepted). The briefs describe the limitations and do not ask you to approve an automated intervention.

If you are willing to review, please suggest a time and identify the appropriate reviewer role. We will record your response in the stakeholder worksheet; no ranking change will be made without an agreed decision.

Thank you,
[project owner]

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

Use [`heat-season-stakeholder-brief.md`](heat-season-stakeholder-brief.md) to discuss whether ERA5 remains separate context or a higher-resolution multi-date heat source is required, and [`mobility-measure-stakeholder-brief.md`](mobility-measure-stakeholder-brief.md) to compare nearest-counter distance with measured counter activity. Conduct one stakeholder or coach review using the questions above and record it in `tree-stakeholder-review.csv`. Regenerate with `julia --project=. bin/generate_stakeholder_review.jl` and verify the decision appears in the Julia application. Do not expand the model or add canopy/optimization features until the decision question and mobility measure are accepted.
