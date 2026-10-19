# Trees & Surfaces

An exploratory data-integration prototype investigating where sampled managed trees in Brussels combine relatively high urban heat stress with proximity to bicycle infrastructure.

The project evaluates open data feasibility for urban greening and climate adaptation, integrating municipal tree inventories, regional heat modeling, and transport monitoring datasets into an interactive screening tool with traceable provenance.

> **Interpretation boundary:** The prototype calculates an exploratory descriptive signal from real spatial joins. Proximity is a spatial context proxy, not cyclist volume; the ranking uses a single-day WBGT raster from 2016, while two multi-date heat contexts — a coarse ERA5 seasonal series and a 100 m daily WBGT archive from the same UrbClim model — are reported as context only; and rankings are sample-relative. The 100 m comparison shows substantial membership sensitivity across heat summaries; its cross-screen comparisons also differ in WBGT output semantics and scoring, so they do not isolate the heat-period effect. The more direct VITO reference-day versus seasonal-mean heat-only comparison shares 7/10 trees. The ranking has not been switched to a multi-date measure because that choice belongs to stakeholders. The tool is designed for candidate screening and requirements elicitation with stakeholders, **not** automated planting recommendations or causal findings.

## Offline heat-support research

Run the separate research diagnostic without downloads or changing the operational screen:

```bash
julia --project=. bin/analyze_heat_support.jl /tmp/heat-support
```

The [generated research report](data/research/heat-support-diagnostics.md),
[JSON measurements](data/research/heat-support-diagnostics.json), and
[rank visualization](data/research/heat-support-ranks.svg) examine duplicate archive
cells, cutoff ties, within/between-cell variation, and leave-one-district-out
sensitivity. The [robustness profiles](data/research/heat-support-robustness.svg)
compare 10–50% selection fractions; the report also tests archive-temperature
coarsening and cells with at least two or three sampled trees. These are
descriptive stress tests, not confidence intervals or corrections for sampling bias.
Regenerate committed research outputs by passing `data/research`.
The standard test suite checks their reproducibility.

**Spatial-support clarification:** older descriptions in this repository call the
ranking raster and daily archive matching 100 m products. [Brussels Environment's
methodology](https://environnement.brussels/citoyen/documentation-et-outils/etat-des-lieux-de-lenvironnement/ilot-de-chaleur)
distinguishes 100 m UrbClim meteorology from the detailed **2 m radiation/shade WBGT
simulation**, consistent with `src/Projection.jl::PIXEL_SIZE`. The archive contains
100 m daily maxima; the detailed raster is a normalized indicator of a 24-hour
mean. Their disagreement cannot isolate heat-period effects. The research report
supersedes the older same-resolution claim, without changing the existing ranking.
VITO daily-archive reuse terms remain unresolved; generated diagnostics are
exploratory and are not a licence clearance.

### Prepared mean/maximum comparison (local inputs only)

The [comparison protocol](docs/wbgt-mean-max-method.md) and
`bin/compare_wbgt_mean_max.jl` are ready for two local 2016 annual files. The reader
now checks the declared statistic explicitly; a daily-mean file cannot silently
enter the maximum-only workflow. The separate output compares equal-weight cells
on the reference day and over JJA, with paired-value and missingness checks.
**A real paired run has since been made on the cached 2016 files, and its outputs stay in
the git-ignored cache rather than this repository:** publishing a mean/maximum comparison
is a stakeholder decision and VITO's reuse terms are unresolved, so the method document
records that the run happened and what it validated, not the measured values. The command
has no download capability, and VITO reuse terms and daily aggregation conventions still
require confirmation.

## Repository structure

- [`docs/`](docs/) — project planning, review findings, stakeholder specification, and demo guides:
  - [`docs/prototype-review.md`](docs/prototype-review.md) — assessment of current data integration and feasibility bottlenecks.
  - [`docs/prototype-next-iteration.md`](docs/prototype-next-iteration.md) — definition of done for subsequent analytical MVP iterations.
  - [`docs/trees-stakeholder-spec.md`](docs/trees-stakeholder-spec.md) — stakeholder decision question, metric definitions, and interview protocol.
  - [`docs/trees-demo-script.md`](docs/trees-demo-script.md) — 5-minute stakeholder walkthrough script.
  - [`docs/mobility-measure-stakeholder-brief.md`](docs/mobility-measure-stakeholder-brief.md) — the mobility-measure decision brief, including how counter data is and is not used.
- [`docs/heat-season-stakeholder-brief.md`](docs/heat-season-stakeholder-brief.md) — decision brief comparing coarse ERA5 and 100 m multi-date WBGT context, with explicit limits on ranking comparisons.
  - [`docs/heat-season-method.md`](docs/heat-season-method.md) — method and limits for the committed seasonal and 100 m WBGT context artifacts.
- [`src/`](src/) and [`bin/`](bin/) — Julia package modules, server entry point, analytical pipeline, refresh workflow, and CLI tools.
- [`data/`](data/) — canonical committed snapshots and generated review/analysis artifacts.
- [`docs/julia.md`](docs/julia.md) — Julia runtime, refresh, generation, and validation commands.
- [`Dockerfile`](Dockerfile) — containerized Julia application.
- [`scripts/validate-julia.sh`](scripts/validate-julia.sh) — Julia unit tests and UI/API smoke test.
- [`scripts/validate-all.sh`](scripts/validate-all.sh) — the repository-wide canopy, imagery and Julia validation entry point.
- [`docs/cycling-canopy-pipeline.md`](docs/cycling-canopy-pipeline.md) — locked, checksum-verified offline canopy comparison and 100 m window analysis.
- [`docs/canopy-accuracy-sampling-plan.md`](docs/canopy-accuracy-sampling-plan.md) — planning arithmetic for validating the mapped canopy class: frame, strata, sample sizes, label protocol and limits. A plan, not a result.
- [`docs/trees-measurement-audit.md`](docs/trees-measurement-audit.md) — data quality, spatial/temporal alignment, indicator validity, and directional registration stress tests.
- [`docs/imagery-registration-check.md`](docs/imagery-registration-check.md) — pixel-level comparison of the two 2021 flight products, why co-registering them cannot bound lane-level alignment, and the per-window controls behind that negative result.
- [`docs/vito-licence-enquiry.md`](docs/vito-licence-enquiry.md) — ready-to-send draft of the licence and day-boundary enquiry to VITO, the one action that unblocks publishing the mean/maximum comparison.
- [`docs/tailnet-datastore.md`](docs/tailnet-datastore.md) — sharing machine-local caches and exploration outputs across the operator's tailnet machines (per-project store, read-only, no redistribution).
- [`docs/open-data-candidates.md`](docs/open-data-candidates.md) — what a deliberate search for other open data found: LiDAR candidates that can support a structural check, the Street Tree Layer measured as not covering these streets, and the licences that forbid reuse.
- [`scripts/validate-canopy.sh`](scripts/validate-canopy.sh) — canopy geometry/provenance regressions using synthetic data and small versioned snapshots (requires uv).
- [`scripts/validate-imagery.sh`](scripts/validate-imagery.sh) — registration-estimator and imagery-manifest regressions on synthetic fixtures, with no downloads (requires uv).
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

Or include source refresh, derived joins, analysis, and seasonal heat context in one atomic workflow:

```bash
julia --project=. bin/refresh_open_data.jl --with-derived --with-analysis --with-heat-season
```

To regenerate only the ERA5 seasonal heat context (this makes two batched live requests to Open-Meteo: a grid-snapping probe and the seasonal series):

```bash
julia --project=. bin/generate_heat_season.jl data
```

To regenerate the 100 m multi-date WBGT context, which samples the VITO UrbClim daily archive at the committed tree points:

```bash
julia --project=. bin/generate_wbgt_context.jl --download
```

That command caches about 340 MB of NetCDF under `.cache/urbclim/` (git-ignored, never redistributed) and writes `data/brussels-heat-wbgt-sample.json`. Omit `--download` to reuse an existing cache offline. The archive's redistribution terms are unresolved, so the artifact records that and only derived values are committed.

Regeneration is **deterministic**: repeated runs from the same cache produce byte-identical output, and a Julia test pins that along with the number convention (integer-valued fields as JSON integers, computed `Float64` fields as JSON floats). The artifact is a single line, so a type or serializer change rewrites that whole line; the committed file was regenerated deliberately on 2026-10-17 for exactly that reason, with no change to any value. Check both before treating a large diff as a data change.

Generates:
- `tree-signal-sensitivity.json`: sensitivity scenarios (heat-only 100/0, balanced 60/40, proximity-only 0/100) and data completeness audit.
- `tree-signal-balanced-screen.csv`: complete ranking under the balanced screening lens.
- `tree-signal-analysis.md`: comprehensive markdown analysis report including district summaries and method explanations.

The one-command workflow above also regenerates `brussels-counter-accident-context.json` (counter-level all-accident and bicycle-involved accident counts within 250 m and 500 m). Regenerate it on its own with:

```bash
julia --project=. bin/generate_accident_context.jl data
```

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
- Derives nearest-counter Haversine distances, measured counter flow context, and national road-accident context in Julia.

The upstream managed-tree catalogue re-keyed its primary key from numeric suffixes (`vbx_56544`) to UUIDs. [`data/managed-tree-id-crosswalk.json`](data/managed-tree-id-crosswalk.json) maps each committed sample ID to the current live identifier so refreshes stay stable; regenerate it after an upstream re-key:

```bash
julia --project=. bin/generate_managed_tree_crosswalk.jl
```

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
| ERA5 seasonal heat context | ECMWF / Copernicus via Open-Meteo | CC BY 4.0 | Daily apparent-temperature maxima and temperature minima for June–August, 2015–2024; coarse ~28 km grid used to contextualize the reference date, not rank intra-urban locations. |
| UrbClim daily 100 m WBGT | VITO (UrbClim; source page requests De Ridder et al. 2015 and Souverijns et al. 2026 citations) | **Unresolved** | Daily-maximum WBGT in °C for 2008–2017 at 100 m in EPSG:3035 from the same UrbClim model family; the committed raster is a 0–100 indicator for a 24-hour mean scenario, so these are not identical outputs. Only derived per-tree values are committed. Neither the archive page nor the NetCDF attributes state terms, and the two related records do not transfer theirs: the Souverijns et al. (2026) decadal set is CC BY 4.0, and the Copernicus CDS record `sis-urban-climate-cities` (deprecated 2024-05-10) is CC-BY-4.0 but covers hourly temperature, humidity and wind for 100 cities and contains no WBGT. Unresolved pending VITO. |
| Canopy Layer (Lead) | Elsa Gallez | CC BY 4.0 | Documented source lead for canopy model integration (Zenodo DOI `10.5281/zenodo.13869065`). |
| Road accidents 2017–2024 | Statbel / Federal Police | CC BY 4.0 | 30,022 Brussels-region geolocated injury/fatal accident records; bicycle involvement is derived from road-user types. |
| Counter accident context | Derived | Source licences inherited | Counter-level all/bicycle-involved accident counts within 250 m and 500 m. |

Full metadata, URLs, and attribution terms are maintained in [`data/source-inventory.json`](data/source-inventory.json).

## Licence

The source code in this repository is released under the [MIT Licence](LICENSE). The committed snapshots and generated artifacts under [`data/`](data/) retain their source-specific terms — including CC BY 4.0 and CC0 1.0 sources, and Open-Meteo's ERA5-derived data under CC BY 4.0 — with attribution recorded in [`data/source-inventory.json`](data/source-inventory.json). **Reuse or redistribution terms for the VITO 2008–2017 daily UrbClim archive and its derived `brussels-heat-wbgt-sample.json` values are unresolved; the MIT licence is not a grant of rights to those data.** Checked 2026-10-17: the archive page states no licence, the annual NetCDF files carry no licence attribute, and neither the CC BY 4.0 Souverijns et al. (2026) decadal set nor the CC-BY-4.0 Copernicus CDS record `sis-urban-climate-cities` (hourly temperature, humidity and wind for 100 cities, no WBGT, deprecated on the CDS 2024-05-10) covers this daily WBGT archive. Confirm applicable terms with VITO before external reuse. The MIT licence does not override source-specific data terms.

## Limitations and caveats

- **Exploratory metric:** The signal combines min-max normalized heat indicator pixels with inverse normalized counter distance. Rankings shift when weights change or if evaluated on a different sample.
- **Heat measures are not interchangeable:** The ranking still uses the Brussels Environment 24 August 2016 WBGT indicator. The ERA5 artifact pools June–August seasons from 2015–2024 and shows how unusual that day was, but its ~28 km grid cannot resolve intra-urban heat patterns and its apparent temperature is not WBGT. The 100 m WBGT archive removes that resolution objection because it uses the same UrbClim model family and grid spacing, but its daily-maximum °C values differ from the committed raster's 24-hour 0–100 indicator. Within the archive, the reference-day and seasonal-mean heat-only top tens share 7/10; comparisons to the balanced screen also change the scoring and measure, so they cannot attribute differences to period alone. Multi-date heat evidence therefore exists; choosing a heat period is an open stakeholder decision, not a data gap.
- **Counter outages look like low traffic:** The source API returns sensor outages as continuous zero counts. The project now refuses to treat an all-zero or incomplete counter window as measured flow, but counter coverage is still uneven over time (CB1101 was offline for nearly four years) and the committed snapshot is a single week.
- **Contextual mobility:** Counter proximity is a geographic context proxy, not a direct measurement of cyclist or pedestrian volume at the tree location. Measured counter flow covers a single winter week at 5 counters.
- **No causal claim:** High signal indicates a candidate point for site inspection and further analytical study, not an automated recommendation to plant or fell trees.
- **Personal review data:** The interactive view and `/stakeholder-review.csv` expose the stakeholder worksheet, including reviewer name, role and notes. The app has no access control of its own, so keep it on a trusted network (or behind an authenticated proxy) once a review is recorded; the shipped container binds to all interfaces.
