# Trees & Surfaces Prototype

This directory contains the standalone feasibility prototype and reproducible data pipeline for **Trees & Surfaces**, exploring where sampled managed trees in Brussels combine higher heat exposure (WBGT raster indicator) with closer bicycle counters.

The browser prototype uses no third-party runtime libraries. Offline geospatial raster extraction requires Pillow.

## Setup and validation

The tooling requires Python 3.10+, Pillow, and Node.js (for the dependency-free UI smoke harness).

From the repository root:

```bash
python3 -m pip install -r prototypes/requirements.txt
scripts/validate-prototypes.sh
```

The validation gate:
1. Regenerates the sensitivity analysis and descriptive markdown report (`analyze_signal.py`).
2. Regenerates the stakeholder review worksheet and compiled review payload (`export_stakeholder_review.py`).
3. Validates snapshot schemas, coordinate transforms, flow statistics, and source inventory provenance (`validate_snapshots.py`).
4. Verifies stakeholder review preservation, provenance-change refusal, and explicit reset in an isolated sandbox (`test_review_workflows.py`).
5. Compiles Python source files (`python3 -m compileall`).
6. Executes the browser DOM smoke test (`smoke_ui.js`).
7. Enforces strict standard JSON parsing (no `NaN`, `Infinity`, or comments).
8. Enforces group/other-readable artifact and directory permissions.
9. Runs `git diff --check`.
10. With `--check-clean`, fails if any committed or generated files were modified or left untracked.

## Run locally

Start a static HTTP server from this directory:

```bash
python3 -m http.server 8000
```

Then navigate to:
- <http://localhost:8000/> (redirects to the prototype)
- <http://localhost:8000/trees-surfaces/> (interactive prototype)

## Pipeline scripts and data generation

All commands below assume execution from the `prototypes/` directory.

### 1. Regenerate sensitivity analysis and balanced screen

```bash
python3 trees-surfaces/analyze_signal.py
```

Outputs:
- `trees-surfaces/data/tree-signal-sensitivity.json` — multi-scenario weight sensitivity and completeness audit.
- `trees-surfaces/data/tree-signal-balanced-screen.csv` — full 100-record ranking under balanced weights (60% heat / 40% proximity).
- `trees-surfaces/data/tree-signal-analysis.md` — comprehensive descriptive analysis report with methodology, district breakdown, and interpretation boundaries.

### 2. Export and preserve stakeholder reviews

```bash
python3 trees-surfaces/export_stakeholder_review.py
```

Outputs:
- `trees-surfaces/data/tree-stakeholder-review.csv` — one-row review worksheet for decision-maker sign-off.
- `trees-surfaces/data/tree-stakeholder-reviews.json` — compiled review JSON consumed by the browser UI.

Options:
- `--reset-review` — deliberately clears completed review fields while strictly preserving source-derived provenance columns.

### 3. Regenerate measured counter-flow context

```bash
python3 trees-surfaces/join_counter_flow.py
```

Outputs:
- `trees-surfaces/data/brussels-tree-counter-flow.json` — joins each sampled tree to measured flow statistics from its nearest bicycle counter (1–7 January 2024, 15-minute counts, covering 97/100 trees across 5 active counters).

### 4. Fetch open data snapshots

```bash
python3 fetch_open_data.py
```

The equivalent Julia source-refresh command is:

```bash
julia --project=../../julia ../../julia/refresh_open_data.jl [--check|--with-derived|--with-analysis]
```

It preserves committed sample IDs, validates source metadata and counter-history shape, and writes snapshots atomically. `--check` performs the live validation in a temporary directory without changing committed files; `--with-derived` also regenerates Julia's derived joins; `--with-analysis` additionally regenerates sensitivity artifacts and requires `--with-derived`. The Python command remains the fallback for the derived nearest-counter/flow joins and unsupported source formats.

Refreshes:
- `trees-surfaces/data/brussels-trees-sample.json` (City of Brussels managed trees sample)
- `trees-surfaces/data/brussels-remarkable-trees-sample.json` (heritage.brussels remarkable trees sample)
- `trees-surfaces/data/brussels-bike-counters.json` (Brussels Mobility counter locations)
- `trees-surfaces/data/brussels-bike-history-*-2024-01.json` (7-day 15-minute count histories for 5 counters)
- `trees-surfaces/data/brussels-tree-bike-nearest.json` (Haversine nearest-counter spatial join)
- Runs `join_counter_flow.py` to update the counter flow join.

### 5. Regenerate heat join (GeoTIFF extraction)

To re-extract the heat indicator values from the official Brussels Environment WBGT GeoTIFF:

```bash
python3 trees-surfaces/join_heat.py /path/to/urban_heat_islands_WBGT_MEAN_24082016_0-1_byte.tif trees-surfaces/data/brussels-trees-sample.json trees-surfaces/data/brussels-tree-heat-sample.json
```

This performs an EPSG 7-parameter datum transformation from WGS84 to the Belgian 1972 datum (BD72), followed by a Belgian Lambert 72 projection (EPSG:31370) and pixel sampling on the 10,000 × 9,000 raster.

## Review workflow and provenance safety

The stakeholder review mechanism connects the analytical model to operational decision-making:

- **Proposal contract:** `trees-surfaces/data/tree-stakeholder-proposal.json` defines the proposed screening question, spatial unit, measures, and allowed statuses (`accepted`, `accepted with changes`, `needs more evidence`, `rejected`).
- **Worksheet:** `trees-surfaces/data/tree-stakeholder-review.csv` contains one row. Completed reviews require `reviewer_name`, `reviewer_role`, `reviewed_at` (ISO 8601), `false_positive_preference`, `evidence_threshold`, and `review_notes`.
- **Accepted decisions:** Statuses `accepted` and `accepted with changes` require explicit entries for `accepted_decision_question`, `accepted_spatial_unit`, `accepted_mobility_measure`, and `accepted_heat_period`.
- **Stale-evidence refusal:** `export_stakeholder_review.py` compares the existing worksheet's provenance columns (proposal ID, core join audit summary, sensitivity summary) against regenerated values. If any input evidence changed, the script **refuses to write** and raises a `RuntimeError` to prevent attaching an obsolete stakeholder approval to changed findings.
- **Compiled artifact:** Valid completed reviews compile to `trees-surfaces/data/tree-stakeholder-reviews.json` and are presented in the prototype interface.

## Sources and provenance

All source licences, access points, and mandatory attribution strings are formally documented in [`trees-surfaces/data/source-inventory.json`](trees-surfaces/data/source-inventory.json):

| Dataset | Publisher | Licence | Attributions / Notes |
|---|---|---|---|
| Managed Trees | City of Brussels / Data Management | CC BY 4.0 | Bruxelles Mobilité, Bruxelles Environnement, Google Maps, Ville de Bruxelles/Espaces publics et verts |
| Remarkable Trees | heritage.brussels | CC BY 4.0 | National Geographic Institute (NGI-IGN, ngi.be) |
| Bicycle Counters & History | Brussels Mobility | CC0 1.0 | Real-time counting API; 15-minute observations |
| Heat Island Raster (WBGT) | Brussels Environment / Leefmilieu Brussel | CC BY 4.0 | Metadata ID `BRU_ENVI_73b4f29a-cff0-4d6a-a239-cb99d3140531`; normalized 0–100 WBGT indicator for 2016-08-24 |
| Canopy Layer Lead | Elsa Gallez | CC BY 4.0 | Zenodo DOI `10.5281/zenodo.13869065` |

## Caveats and interpretation boundaries

1. **Screening only:** The output signal is descriptive exploratory screening. It is **not** a planting recommendation or intervention priority list.
2. **Mobility proxy:** Great-circle distance to the nearest bicycle counter is a spatial context proxy. It does not measure cyclist volume, pedestrian activity, or street use.
3. **Measured flow context:** The counter-flow data represents measured flow at the counter (not at the tree) during one winter week (1–7 January 2024); it is not a seasonal or annual mobility metric.
4. **Heat model scope:** The heat raster models mean 24-hour WBGT on a single representative hot day (24 August 2016). It is an indicator of relative heat stress, not a real-time air temperature measurement.
5. **Sample-relative normalization:** Min-max normalization is performed within the 100-record feasibility sample. Rankings shift if the sample changes or if different weights are applied.
