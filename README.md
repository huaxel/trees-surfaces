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
- [`src/`](src/) and [`bin/`](bin/) — Julia package modules, server entry point, analytical pipeline, refresh workflow, and CLI tools.
- [`data/`](data/) — canonical committed snapshots and generated review/analysis artifacts.
- [`docs/julia.md`](docs/julia.md) — Julia runtime, refresh, generation, and validation commands.
- [`Dockerfile`](Dockerfile) — containerized Julia application.
- [`scripts/validate-julia.sh`](scripts/validate-julia.sh) — Julia unit tests and UI/API smoke test.
- [`scripts/validate-all.sh`](scripts/validate-all.sh) — the repository-wide Julia validation entry point.
- [`.github/workflows/validate.yml`](.github/workflows/validate.yml) — Julia unit, refresh, and container validation.

## Quick start

### Prerequisites

- Julia 1.10+
- Python 3.10+ (used by the validation script for JSON and HTTP smoke-test assertions)

### Installation and local serve

1. Start the canonical Julia server:

   ```bash
   julia --project=. bin/run.jl
   ```

2. Open <http://127.0.0.1:8080/>.

See [`docs/julia.md`](docs/julia.md) for refresh, artifact generation, container, and validation commands.

The Julia server is the only supported application entry point.

Validate current public API contracts without changing committed snapshots:

```bash
julia --project=. bin/refresh_open_data.jl --check
```

## Data pipeline and regeneration

All data processing scripts can be run independently or verified via the comprehensive validation script.

### 1. Canonical Julia validation gate

From the repository root:

```bash
scripts/validate-julia.sh
```

This covers Julia snapshot validation, spatial joins, sensitivity artifacts, stakeholder review preservation, the HTTP UI, and container-facing behavior. Add `JULIA_REFRESH_CHECK=1` to validate the live public API contracts without modifying `data/`.

Run the repository-wide Julia gate with:

```bash
scripts/validate-all.sh
```

It covers snapshot validation, spatial joins, artifact generation, stakeholder review preservation, the HTTP UI, and container-facing behavior.

### 2. Analytical signal generation

Generate canonical Julia artifacts directly into `data/`:

```bash
julia --project=. bin/generate_signal.jl data
```

Or include source refresh, derived joins, and analysis in one atomic workflow:

```bash
julia --project=. bin/refresh_open_data.jl --with-derived --with-analysis
```

Generates:
- `tree-signal-sensitivity.json`: sensitivity scenarios (heat-only 100/0, balanced 60/40, proximity-only 0/100) and data completeness audit.
- `tree-signal-balanced-screen.csv`: complete ranking under the balanced screening lens.
- `tree-signal-analysis.md`: comprehensive markdown analysis report including district summaries and method explanations.

### 3. Stakeholder review workflow

```bash
julia --project=. bin/generate_stakeholder_review.jl
```

Maintains the two-way contract between analytical evidence and decision-maker feedback:
- Generates `tree-stakeholder-review.csv` bound to the exact findings in `tree-signal-sensitivity.json` and `tree-stakeholder-proposal.json`.
- Compiles completed reviews into `tree-stakeholder-reviews.json`.
- Refuses to write if proposal evidence changed (preventing review drift).
- Supports `--reset-review` to clear decision inputs while preserving source-derived provenance columns.

### 4. Fetching open data snapshots

```bash
julia --project=. bin/refresh_open_data.jl --with-derived
```

Refreshes municipal open-data snapshots from official Brussels APIs while preserving committed sample IDs:
- Managed trees from City of Brussels Open Data
- Remarkable trees from Brussels Heritage Open Data
- Bicycle counter devices and 7-day 15-minute history counts from Brussels Mobility
- Derives nearest-counter Haversine distances and measured counter flow context in Julia.

### 5. Heat raster sampling

For supported uncompressed, PackBits, or Deflate TIFFs, use the native Julia join:

```bash
julia --project=. bin/generate_heat_join.jl /path/to/WBGT_MEAN_24082016_0-1_byte.tif data/brussels-trees-sample.json data/brussels-tree-heat-sample.json
```

Unsupported TIFF compression formats must be converted before ingestion; the native Julia join supports uncompressed, PackBits, and Deflate TIFFs.

Implements an exact EPSG 7-parameter datum shift from WGS84 to BD72 and Belgian Lambert 72 projection (EPSG:31370) without external CRS libraries, extracting nearest raster pixel values from the 10,000 × 9,000 regional urban-heat-island model.

## Sources and provenance

| Dataset | Provider | Terms / Licence | Role in Prototype |
|---|---|---|---|
| Arbres (City of Brussels) | City of Brussels / Data Management | CC BY 4.0 | Sample of 100 managed public trees with coordinates, street, and district. |
| Arbres remarquables | heritage.brussels | CC BY 4.0 | Sample of 100 heritage trees with species, circumference, and protection status. |
| RT Counting (Devices & History) | Brussels Mobility | CC0 1.0 | 18 counter locations and 7-day (672 observation) 15-minute count series for 5 counters. |
| Mean WBGT 24/08/2016 | Brussels Environment | CC BY 4.0 | Regional urban-heat-island model; 0–100 indicator pixels (ISO `BRU_ENVI_73b4f29a-cff0-4d6a-a239-cb99d3140531`). |
| Canopy Layer (Lead) | Elsa Gallez | CC BY 4.0 | Documented source lead for canopy model integration (Zenodo DOI `10.5281/zenodo.13869065`). |
| Road accidents 2017–2024 | Statbel / Federal Police | CC BY 4.0 | 30,022 Brussels-region geolocated injury/fatal accident records; bicycle involvement is derived from road-user types. |

Full metadata, URLs, and attribution terms are maintained in [`data/source-inventory.json`](data/source-inventory.json).

## Limitations and caveats

- **Exploratory metric:** The signal combines min-max normalized heat indicator pixels with inverse normalized counter distance. Rankings shift when weights change or if evaluated on a different sample.
- **Single-day heat model:** The available open regional heat raster models a single representative hot day (24 August 2016). Multi-date or seasonal satellite land-surface temperature (LST) remains future work.
- **Contextual mobility:** Counter proximity is a geographic context proxy, not a direct measurement of cyclist or pedestrian volume at the tree location. Measured counter flow covers a single winter week at 5 counters.
- **No causal claim:** High signal indicates a candidate point for site inspection and further analytical study, not an automated recommendation to plant or fell trees.
