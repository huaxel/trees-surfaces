# Trees & Surfaces — Julia UI

This is a Julia-backed version of the browser prototype. Julia loads the committed snapshots, computes the normalized point fields and provenance summary, injects the initial state into the page, and serves the UI. Slider changes call `/api/screen`, so the exploratory ranking is recalculated by Julia rather than duplicated in browser code.

The browser still uses a small amount of plain JavaScript for slider and point-selection interactions; no frontend framework is required.

The Julia layer owns the UI server, weighted screening, sensitivity artifacts, measured-flow join, stakeholder review workflow, snapshot validation, and public API refresh. `bin/refresh_open_data.jl` preserves committed sample IDs and validates source metadata/history shape before atomic writes. Add `--with-derived` to regenerate the native nearest-counter and measured-flow artifacts; add `--with-analysis` to also regenerate sensitivity JSON/CSV/Markdown artifacts. Derived artifacts are generated in a temporary directory and published atomically. Existing stakeholder review data is left untouched. Combine these with `--check` to validate the complete live refresh pipeline in temporary storage without modifying committed snapshots.

## Requirements

- Julia 1.10+
- Internet access on first launch to install `HTTP.jl` and `JSON3.jl`

## Run

From the repository root:

```bash
julia --project=. bin/run.jl
```

Then open <http://127.0.0.1:8080/>.

Use a different port with:

```bash
julia --project=. bin/run.jl 9090
```

For deployment, configure the listener with `JULIA_UI_HOST` and `JULIA_UI_PORT` environment variables. A container image is also provided:

```bash
docker build -f Dockerfile -t trees-surfaces-julia .
docker run --rm -p 8080:8080 trees-surfaces-julia
```

The server reads the canonical snapshots under `data/`, caches the derived state for the process, and recalculates only the requested weights.

Run the Julia tests with:

```bash
julia --project=. -e 'using Pkg; Pkg.test()'
```

Validate the committed snapshot invariants directly:

```bash
julia --project=. bin/validate_snapshots.jl
```

Validate the WGS84-to-Belgian-Lambert72 heat projection against all committed pixels:

```bash
julia --project=. bin/validate_projection.jl
```

Join an available 10,000 × 9,000 grayscale GeoTIFF natively in Julia:

```bash
julia --project=. bin/generate_heat_join.jl RASTER.tif trees.json output.json
```

`TiffImages.jl` supports uncompressed, PackBits, and Deflate TIFFs. Unsupported compression formats must be converted before ingestion.

Print the current Julia-computed sensitivity summary:

```bash
julia --project=. bin/analyze.jl
```

Generate Julia-owned sensitivity JSON and CSV artifacts into a separate directory:

```bash
julia --project=. bin/generate_signal.jl /tmp/trees-surfaces-julia-output
```

This writes only to the requested output directory and does not overwrite the Julia-owned snapshots.

Generate the nearest-counter spatial join:

```bash
julia --project=. bin/generate_tree_mobility_join.jl /tmp/trees-surfaces-julia-output
```

Generate the measured counter-flow context similarly:

```bash
julia --project=. bin/generate_counter_flow.jl /tmp/trees-surfaces-julia-output
```

Generate the provenance-safe stakeholder review worksheet and compiled payload:

```bash
julia --project=. bin/generate_stakeholder_review.jl
```

Pass `--reset-review` explicitly when deliberately clearing review fields.

Run unit tests plus the live HTTP smoke test from the repository root:

```bash
scripts/validate-julia.sh
```

To also validate the current public endpoints without modifying snapshots:

```bash
JULIA_REFRESH_CHECK=1 scripts/validate-julia.sh
```

The GitHub Actions workflow runs this network-dependent check only when manually dispatched; regular pull requests keep the deterministic offline gate.
