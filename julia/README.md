# Trees & Surfaces — Julia UI

This is a Julia-backed version of the browser prototype. Julia loads the committed snapshots, computes the normalized point fields and provenance summary, injects the initial state into the page, and serves the UI. Slider changes call `/api/screen`, so the exploratory ranking is recalculated by Julia rather than duplicated in browser code.

The browser still uses a small amount of plain JavaScript for slider and point-selection interactions; no frontend framework is required.

The Julia layer currently owns the UI server, weighted screening, sensitivity artifacts, measured-flow join, stakeholder review workflow, and snapshot validation. Public API snapshots can now be refreshed with `julia/refresh_open_data.jl`; it preserves committed sample IDs and validates source metadata/history shape before atomic writes. Add `--with-derived` to regenerate the native nearest-counter and measured-flow artifacts as well; add `--with-analysis` to also regenerate sensitivity JSON/CSV/Markdown artifacts. Derived artifacts are generated in a temporary directory and published atomically. Existing stakeholder review data is left untouched. Combine these with `--check` to validate the complete live refresh pipeline in temporary storage without modifying committed snapshots. Python remains an explicit fallback for derived joins and unsupported LZW TIFF ingestion.

## Requirements

- Julia 1.10+
- Internet access on first launch to install `HTTP.jl` and `JSON3.jl`

## Run

From the repository root:

```bash
julia --project=julia julia/run.jl
```

Then open <http://127.0.0.1:8080/>.

Use a different port with:

```bash
julia --project=julia julia/run.jl 9090
```

For deployment, configure the listener with `JULIA_UI_HOST` and `JULIA_UI_PORT` environment variables. A container image is also provided:

```bash
docker build -f julia/Dockerfile -t trees-surfaces-julia .
docker run --rm -p 8080:8080 trees-surfaces-julia
```

The server reads the existing snapshots under `prototypes/trees-surfaces/data/`, caches the derived state for the process, and recalculates only the requested weights. Run the normal prototype regeneration/validation workflow before launch if those artifacts need refreshing; restart the server after refreshing snapshots.

Run the Julia tests with:

```bash
julia --project=julia -e 'using Pkg; Pkg.test()'
```

Validate the committed snapshot invariants directly:

```bash
julia --project=julia julia/validate_snapshots.jl
```

Validate the WGS84-to-Belgian-Lambert72 heat projection against all committed pixels:

```bash
julia --project=julia julia/validate_projection.jl
```

Join an available 10,000 × 9,000 grayscale GeoTIFF natively in Julia:

```bash
julia --project=julia julia/generate_heat_join.jl RASTER.tif trees.json output.json
```

`TiffImages.jl` currently supports uncompressed, PackBits, and Deflate TIFFs; the existing Python/Pillow command remains the fallback for other source compression formats.

Print the current Julia-computed sensitivity summary:

```bash
julia --project=julia julia/analyze.jl
```

Generate Julia-owned sensitivity JSON and CSV artifacts into a separate directory:

```bash
julia --project=julia julia/generate_signal.jl /tmp/trees-surfaces-julia-output
```

This does not overwrite the canonical prototype snapshots.

Generate the nearest-counter spatial join:

```bash
julia --project=julia julia/generate_tree_mobility_join.jl /tmp/trees-surfaces-julia-output
```

Generate the measured counter-flow context similarly:

```bash
julia --project=julia julia/generate_counter_flow.jl /tmp/trees-surfaces-julia-output
```

Generate the provenance-safe stakeholder review worksheet and compiled payload:

```bash
julia --project=julia julia/generate_stakeholder_review.jl
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
