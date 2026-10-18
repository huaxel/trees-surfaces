# Mobility data: what exists, what the pipeline fetches, and what changes the ranking

**Scope.** The ranking's mobility input is nearest-counter distance, and its flow context uses one
winter week from five counters. The stakeholder brief asks for "broader, temporally aligned counts or
a street-level route/flow measure". This records what is available, verified against live services on
2026-10-18, and what each option would change. Nothing here changes the ranking or a committed
artifact.

## The five-counter limit is a hard-coded list, not data availability

| Fact | Measured |
| --- | --- |
| Counters published by the API | **18** (`request=devices`, live check agrees with the committed snapshot) |
| Counters whose history the pipeline fetches | **5** — `COUNTER_HISTORY_FEATURES` in `src/Refresh.jl` is a literal tuple |
| Trees with measured flow | **97 of 100** |
| History available for the other 13 | **Yes**: `CB02411`, `CJE181`, `CAT17`, `CEK31`, `CVT387` each returned 672 records (7 days × 96 intervals) for the committed week |
| Tree coverage if all 18 were fetched | **100 of 100**, at zero data cost |

The three unmatched trees are the sample's farthest from any counter (1498–1518 m), and their true
nearest counters — `CB02411` and `CJE181` — are among the unfetched thirteen. Verified end to end by
running the project's own `refresh_bikes` into a temporary directory: it writes five history files for
eighteen devices, which is the gap exactly.

**Why this was not simply fixed.** Widening the tuple cascades: the flow artifact, the nearest-counter
artifact, the balanced screening scenarios and every number published in the mobility brief would all
change, including the five-values-repeated structure and the top-ten overlaps. That is a
stakeholder-visible change to a published comparison and belongs to the stakeholder, not to a
maintenance commit.

## Seasonality: the ranking is stable, but the absolute level is not

The brief could only show within-week stability and said so. It can now show across-season stability,
using a June week in which all five counters report:

| Counter | Winter 2024-01-01–07 (committed) | Summer 2024-06-24–30 | Ratio |
| --- | ---: | ---: | ---: |
| CB1101 | 17.9 | 59.7 | 3.3 |
| CB1142 | 11.2 | 39.2 | 3.5 |
| CJM90 | 23.9 | 73.0 | 3.1 |
| CB1143 | 8.8 | 34.4 | 3.9 |
| CB2105 | 11.2 | 21.9 | 2.0 |

Levels roughly triple, and not by a common factor, yet the **counter ordering is unchanged** and the
resulting top ten is identical: **10 of 10** in common, Spearman 0.990 on the assigned flow values.
So a season definition changes the absolute context but not, in this sample, which trees rank highest.
The committed winter week is nevertheless the lowest-activity week sampled (mean count 11.2 against
27.0 in summer 2025 and 36.2 in October 2026), which matters for any statement about *levels*.

## A trap: outages are published as zeros

Two of the fifteen counter-weeks sampled are complete outages — `CB1142` for 2024-07-29–08-04 and
`CB1143` for 2025-07-28–08-03 — each 672 rows of `count: 0` with `average_speed: -1`, the missing
sentinel. Both counters report normally in adjacent weeks (`CB1143`: 16,173 total in summer 2024,
34,284 in October 2026). Any consumer that averages `count` without checking the sentinel reads an
outage as "no cyclists", and a flow-based ranking would then treat that counter's 9–31 trees as the
least active in the city.

The committed week is unaffected: all five counters report real variation in January 2024. The
exposure was for any *future* window, so the check now lives in the fetch rather than in a
reviewer's attention: `validate_history_payload` refuses a payload whose 672 intervals total zero
crossings, naming the sentinel in the message. Verified against the real published payloads, not
only fixtures — the actual CB1143 July 2025 outage is refused, while the June 2024 week (total
40,133) and the committed week (CB2105, 7,520) are accepted.

Two limits of that guard, both worth knowing before another window is adopted. It catches **total
silence only**: a partial outage is indistinguishable from empty night intervals, because the
sentinel also marks ordinary intervals with no cyclists. And the validator pins the committed
period (`2024/01/01`–`2024/01/07`) in a literal comparison, so adopting any other window is a code
change, not a parameter change.

## Correcting the brief: flow-only is degenerate; the weighted alternative is not

The brief states that "a flow-based alternative had **0 of 10** points in common with the current
60/40 balanced top ten". Recomputing both candidate readings from committed artifacts:

| Ranking variant | Overlap with the current balanced top ten |
| --- | ---: |
| **Flow-only** top ten | **0 of 10** — all ten sit on the single highest-flow counter (`CJM90`) |
| **60/40 heat + min–max flow** | **9 of 10** |

The 0 of 10 belongs to the flow-only variant, which is degenerate because the matched sample has only
five distinct flow values: a flow-only ranking is a counter ranking, and one counter supplies the
whole top ten. The weighted alternative, which is what the brief's sentence describes, is 9 of 10.
The distinction is not pedantic: it changes the reading from "any flow input reshuffles the top ten"
to "the current screen is heat-led and already agrees with a weighted flow input, while a flow-only
ranking cannot be formed from five counters at all".

## Street-level alternatives

| Candidate | What it offers | Terms and access | Assessment |
| --- | --- | --- | --- |
| Bike counts API `live` request | Last hour, day and year counts per device | CC0 1.0, same source | Adds a recency view; still counter locations, not streets |
| API archive from **2018-12-05** | Full history for any window since then | CC0 1.0 | Makes a season-aligned window available at zero cost; early windows are partial (the 2018-12-05 week returned 88 of 672 rows) |
| `bm_bike` GeoServer layers | Cycle highways, junctions, Villo stations, red-light crossings, slopes | Same portal | Infrastructure context, not flow |
| **Strava Metro** | Street-segment ("edge") counts on OpenStreetMap ways, hourly, with people counts and OSM way IDs | No cost, with conditions; see the eligibility and obligations below | The only credible street-level flow candidate. Aggregated and de-identified, matched to OSM edges, which is the spatial unit this project already uses |
| BRUBIKE (2019) | 193 days of bike counts with weather, plus average speed | Public repository, licence to verify | Superseded by the API for counts; its speed variable is available directly from the API as `average_speed` |

The API's own `average_speed` field per 15-minute interval was not used in the committed snapshot. It
is `-1` when missing, so it shares the sentinel trap above, and its interpretability at 15-minute
resolution over a 15–40 m counting loop is unverified. Recorded as available, not recommended.

## Strava Metro: which path applies, and what it obliges

An earlier version of this document said the candidate was "free for cities and for accepted academic
researchers" and flagged the academic cohort's closing date as the gate. That framing was wrong in a
way that could misdirect: the two paths have different eligibility, and only one is deadline-bound.

- **General licensee path.** Strava's terms make Metro available to organisations that "plan, own, or
  maintain active transportation or outdoor recreation infrastructure, or that seek to positively
  influence active transportation or outdoor recreation planning processes", by application, with no
  closing date stated. This is the path that fits a municipality, agency or advocacy stakeholder.
- **Academic program.** Restricted to researchers "affiliated with an accredited institution of higher
  education", for non-commercial academic research. Its 2027 cohort closed **2026-10-23**, which matters
  only if the applicant is an accredited academic. Nothing in this repository establishes that.
- **Consultants.** A consulting or engineering firm may only use Metro when retained under a formal
  contract by an organisation that already holds access. Informal collaborations and volunteer
  arrangements explicitly do not qualify, so access cannot be obtained on a stakeholder's behalf.

Three obligations bear on how this project works, and they are the reason a decision is needed before
any request:

1. **No redistribution.** The underlying data may not be shared or posted. Our practice is to commit
   every artifact publicly, so a Strava-derived artifact could not be committed as our others are.
2. **Thirty days' prior review** of any report intended for external publication, with mandatory
   attribution wording in every copy.
3. **No machine-learning use.** The data may not be used to train, fine-tune, evaluate or benchmark any
   AI or machine-learning system. That constrains how the data could be combined with the rest of this
   project's tooling.

Access is granted for one year and is renewable at Strava's discretion, and each user applies
individually: logins may not be shared, including with colleagues.

## What would change a decision

1. **Widen the history fetch to all 18 counters** — 100 of 100 trees matched for free, but it changes
   every published flow number, so it needs the stakeholder's agreement.
2. **Adopt a season-aligned window** — the ranking is stable across seasons in this sample, so this is
   about honest levels and alignment with the heat period, not about reordering trees.
3. **Add the outage check** before any other window is used, since outages are indistinguishable from
   zero traffic in the published fields.
4. **Apply for street-level flow** (Strava Metro) if cycling exposure is what the measure must mean;
   that is the only path in this list from counter locations to streets.
