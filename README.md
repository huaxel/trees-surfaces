# Trees & Surfaces

An exploratory data-integration prototype investigating where sampled managed trees in Brussels combine relatively high urban heat stress with proximity to bicycle infrastructure.

The project evaluates open data feasibility for urban greening and climate adaptation, integrating municipal tree inventories, regional heat modeling, and transport monitoring datasets into an interactive screening tool with traceable provenance.

> **Interpretation boundary:** The prototype calculates an exploratory descriptive signal from real spatial joins. Proximity is a spatial context proxy, not cyclist volume; the heat layer models a single representative hot day in 2016; and rankings are sample-relative. The tool is designed for candidate screening and requirements elicitation with stakeholders, **not** automated planting recommendations or causal findings.

## Repository structure

- [`docs/`](docs/) — project planning, review findings, stakeholder specification, and demo guides:
  - [`docs/prototype-review.md`](docs/prototype-review.md) — assessment of current data integration and feasibility bottlenecks.
  - [`docs/prototype-next-iteration.md`](docs/prototype-next-iteration.md) — definition of done for subsequent analytical MVP iterations.
  - [`docs/trees-stakeholder-spec.md`](docs/trees-stakeholder-spec.md) — stakeholder decision question, metric definitions, and interview protocol.
  - [`docs/trees-demo-script.md`](docs/trees-demo-script.md) — 5-minute stakeholder walkthrough script.
- [`prototypes/`](prototypes/) — dependency-free browser interface, data snapshots, and processing scripts:
  - [`prototypes/trees-surfaces/`](prototypes/trees-surfaces/) — interactive browser application, analytical scripts, and data directory.
  - [`prototypes/README.md`](prototypes/README.md) — detailed pipeline execution, script options, and snapshot documentation.
- [`scripts/validate-prototypes.sh`](scripts/validate-prototypes.sh) — end-to-end regeneration, snapshot validation, and test runner.
- [`.github/workflows/validate-prototypes.yml`](.github/workflows/validate-prototypes.yml) — continuous integration matrix testing clean-state artifact generation.

## Quick start

### Prerequisites

- Python 3.10+
- Pillow (`pip install -r prototypes/requirements.txt`)
- Node.js 22+ (for browser UI smoke testing)

### Installation and local serve

1. Install Python dependencies:

   ```bash
   python3 -m pip install -r prototypes/requirements.txt
   ```

2. Start the local server:

   ```bash
   cd prototypes && python3 -m http.server 8000
   ```

3. Open <http://localhost:8000/trees-surfaces/> in your browser (or <http://localhost:8000/> to use the landing redirect).

The browser application runs completely in client-side standard HTML5/CSS/JavaScript with zero third-party runtime dependencies.

## Data pipeline and regeneration

All data processing scripts can be run independently or verified via the comprehensive validation script:

### 1. Validation gate

From the repository root:

```bash
scripts/validate-prototypes.sh
```

With strict clean-checkout validation:

```bash
scripts/validate-prototypes.sh --check-clean
```

The validation suite executes:
- Multi-scenario weight sensitivity analysis (`prototypes/trees-surfaces/analyze_signal.py`)
- Stakeholder review worksheet generation and provenance validation (`prototypes/trees-surfaces/export_stakeholder_review.py`)
- Invariant and schema validation across all committed snapshots (`prototypes/validate_snapshots.py`)
- Review preservation, stale-evidence refusal, and reset integration tests (`prototypes/test_review_workflows.py`)
- Python bytecode compilation (`python3 -m compileall`)
- Headless DOM smoke tests (`prototypes/smoke_ui.js`)
- Strict JSON syntax validation (disallowing non-standard tokens like `NaN` or `Infinity`)
- Group- and other-readability permission checks for all data artifacts
- Git diff whitespace and conflict checks (`git diff --check`)

### 2. Analytical signal generation

```bash
python3 prototypes/trees-surfaces/analyze_signal.py
```

Generates:
- `tree-signal-sensitivity.json`: sensitivity scenarios (heat-only 100/0, balanced 60/40, proximity-only 0/100) and data completeness audit.
- `tree-signal-balanced-screen.csv`: complete ranking under the balanced screening lens.
- `tree-signal-analysis.md`: comprehensive markdown analysis report including district summaries and method explanations.

### 3. Stakeholder review workflow

```bash
python3 prototypes/trees-surfaces/export_stakeholder_review.py
```

Maintains the two-way contract between analytical evidence and decision-maker feedback:
- Generates `tree-stakeholder-review.csv` bound to the exact findings in `tree-signal-sensitivity.json` and `tree-stakeholder-proposal.json`.
- Compiles completed reviews into `tree-stakeholder-reviews.json`.
- Refuses to write if proposal evidence changed (preventing review drift).
- Supports `--reset-review` to clear decision inputs while preserving source-derived provenance columns.

### 4. Fetching open data snapshots

```bash
python3 prototypes/fetch_open_data.py
```

Refreshes municipal open-data snapshots from official Brussels APIs while preserving committed sample IDs:
- Managed trees from City of Brussels Open Data
- Remarkable trees from Brussels Heritage Open Data
- Bicycle counter devices and 7-day 15-minute history counts from Brussels Mobility
- Derives nearest-counter Haversine distances and measured counter flow context (`prototypes/trees-surfaces/join_counter_flow.py`).

### 5. Heat raster sampling

```bash
python3 prototypes/trees-surfaces/join_heat.py /path/to/WBGT_MEAN_24082016_0-1_byte.tif prototypes/trees-surfaces/data/brussels-trees-sample.json prototypes/trees-surfaces/data/brussels-tree-heat-sample.json
```

Implements an exact EPSG 7-parameter datum shift from WGS84 to BD72 and Belgian Lambert 72 projection (EPSG:31370) without external CRS libraries, extracting nearest raster pixel values from the 10,000 × 9,000 regional urban-heat-island model.

## Sources and provenance

| Dataset | Provider | Terms / Licence | Role in Prototype |
|---|---|---|---|
| Arbres (City of Brussels) | City of Brussels / Data Management | CC BY 4.0 | Sample of 100 managed public trees with coordinates, street, and district. |
| Arbres remarquables | heritage.brussels | CC BY 4.0 | Sample of 100 heritage trees with species, circumference, and protection status. |
| RT Counting (Devices & History) | Brussels Mobility | CC0 1.0 | 18 counter locations and 7-day (672 observation) 15-minute count series for 5 counters. |
| Mean WBGT 24/08/2016 | Brussels Environment | CC BY 4.0 | Regional urban-heat-island model; 0–100 indicator pixels (ISO `BRU_ENVI_73b4f29a-cff0-4d6a-a239-cb99d3140531`). |
| Canopy Layer (Lead) | Elsa Gallez | CC BY 4.0 | Documented source lead for canopy model integration (Zenodo DOI `10.5281/zenodo.13869065`). |

Full metadata, URLs, and attribution terms are maintained in [`prototypes/trees-surfaces/data/source-inventory.json`](prototypes/trees-surfaces/data/source-inventory.json).

## Limitations and caveats

- **Exploratory metric:** The signal combines min-max normalized heat indicator pixels with inverse normalized counter distance. Rankings shift when weights change or if evaluated on a different sample.
- **Single-day heat model:** The available open regional heat raster models a single representative hot day (24 August 2016). Multi-date or seasonal satellite land-surface temperature (LST) remains future work.
- **Contextual mobility:** Counter proximity is a geographic context proxy, not a direct measurement of cyclist or pedestrian volume at the tree location. Measured counter flow covers a single winter week at 5 counters.
- **No causal claim:** High signal indicates a candidate point for site inspection and further analytical study, not an automated recommendation to plant or fell trees.
