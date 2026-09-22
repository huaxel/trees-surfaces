# Choose an interesting implementation language — 2026-07-15

## Task
Recommend an interesting programming language for this project.

## Human notes
<!-- goals, constraints, or requested direction -->

## Todos
- [x] Inspect the project shape and constraints
- [x] Recommend a language with concrete tradeoffs
- [x] Add a Julia-backed UI prototype
- [x] Run the Julia server smoke test when Julia is available
- [x] Add a repeatable Julia validation script
- [x] Run Julia validation in GitHub Actions
- [x] Cache immutable snapshot state for interactive Julia requests
- [x] Add a Julia analytical summary command
- [x] Add non-destructive Julia signal artifact generation
- [x] Add Julia-generated Markdown analysis report
- [x] Add Julia measured-counter-flow artifact generation
- [x] Add Julia stakeholder review workflow
- [x] Add Julia snapshot invariant validation
- [x] Add Julia nearest-counter spatial join
- [x] Add Julia heat projection parity validation
- [x] Add Julia container CI smoke test

## Progress
- Started analysis
- Reviewed the README, prototype architecture, stakeholder specification, and validation gate.
- Recommended Julia as the most interesting fit, with Rust as the stronger systems-oriented alternative.
- Added a Julia package/server under `julia/` that loads the existing snapshots, computes the UI state, and serves an interactive page.
- The existing Python/Node validation gate passes.
- Installed Julia 1.10.12 locally, corrected the JSON3 UUID, ran the Julia unit tests (12/12), and smoke-tested the server, health route, rendered state, and heat preview.
- Added `/api/screen?heat=...&proximity=...`; slider recalculation now runs in Julia, with the browser limited to rendering the returned ranking.
- Added `scripts/validate-julia.sh` for unit tests plus live HTTP smoke checks; it passes locally.
- Added a pinned Julia 1.10 GitHub Actions job and made the validation script install its project dependencies on clean runners.
- Restored source-record links and the stakeholder-review CSV download in the Julia UI, with both covered by the smoke test.
- Completed the Julia analytical, spatial, heat-projection, TIFF, stakeholder-review, validation, Docker, and CI layers; the unified gate passes with 226 Julia tests.

## Findings
- The project is primarily reproducible spatial/data analysis: API snapshots, raster sampling, coordinate transforms, joins, normalization, provenance, and sensitivity analysis.
- The UI is a dependency-free browser app, so a language choice mainly affects the data pipeline and could optionally add a typed service later.
- The next iteration needs multi-date heat data and stronger mobility measures, making analytical ergonomics more important than novelty alone.
- Julia can power the UI too, either through server-rendered HTML/HTMX, a Julia dashboard framework, or compiled browser code; the first option is the least risky for this prototype.

## Decisions
- Prefer Julia for an exploratory rewrite: it keeps numerical/data work expressive while offering a path to typed geospatial processing and notebooks/visualizations.
- Julia can own the UI, but start with a small server-rendered app rather than forcing a compiled browser frontend.
- Keep the current static JavaScript UI initially only as a migration fallback; a full Julia UI is feasible if the goal is a single-language prototype.
- Consider Rust if the goal shifts toward a durable production pipeline or WebAssembly frontend rather than research iteration.
- Practicality currently dominates novelty: Julia is the chosen exploratory implementation, with Python retained only for external API refresh and unsupported TIFF compression.
- The Julia UI is a verified parallel prototype; the existing static UI remains available as fallback.
- Keep server-side score calculation as the source of truth so analytical logic is not silently forked between Python, Julia, and browser JavaScript.
- The Julia validation gate is separate from the existing Python/Node gate because Julia is an optional runtime for the parallel UI prototype.
- The Julia UI can now run locally or as a container with the same committed snapshots.
- Julia now owns the analytical and review workflows; public API refreshes remain Python, while a native Julia GeoTIFF join is now available for supported grayscale TIFF compression.
- Julia-generated sensitivity artifacts now include the full completeness and interpretation metadata required by the stakeholder review workflow, so the Julia pipeline can feed review generation directly.
- Added direct `Dates` and `Statistics` dependencies plus standard `[extras]`/`[targets]` configuration; `Pkg.test()` now runs the full 226-test suite successfully.
- Native heat sampling was smoke-tested on a correctly sized 10,000 × 9,000 fixture; TiffImages does not support LZW, so Python/Pillow remains the fallback for that compression.
- Added a Julia launch card to the prototype landing page and documented the separate Julia validation gate in the root README.
- Added `scripts/validate-all.sh`; one command now runs both the original and Julia validation gates.
- The unified gate passes after switching Julia validation to standard `Pkg.test()` execution.
- CI now verifies both gates independently; the Julia workflow action is pinned to `julia-actions/setup-julia` v2.7.0.
- The parallel Julia UI now retains the prototype's key provenance and stakeholder handoff affordances rather than being a reduced demo.
- Snapshot-derived state is cached once per Julia process; slider requests only recompute weighted rankings.
- Julia tests now compare the balanced top ten and rounded top score against the committed sensitivity artifact, guarding against analytical drift.
- Added `julia/analyze.jl` and `src/Analysis.jl`; the Julia side now exposes the 100-record sensitivity summary as a CLI as well as powering the UI.
- Added Julia compat bounds and configurable `JULIA_UI_HOST` / `JULIA_UI_PORT` launcher settings; the resolved environment and validation gate pass.
- Added `julia/generate_signal.jl`, which writes Julia-computed sensitivity JSON/CSV to a chosen output directory; CI compares its top-ten and overlap invariants with the canonical artifacts.
- The generator now also emits a concise Markdown analysis report, with CI checking its structure.
- Added `julia/generate_counter_flow.jl`; Julia now reproduces the 100-record, 97-covered-tree measured-flow context and CI compares its provenance-shaped invariants.
- Added `julia/generate_stakeholder_review.jl`; CI exercises pending generation, completed-review preservation, and stale-evidence refusal.
- Added `julia/validate_snapshots.jl`; Julia now validates record counts, ID alignment, coordinates, heat NoData, distances, flow coverage, and source inventory completeness.
- Added a Julia Haversine nearest-counter join; its 100 IDs, counter assignments, and rounded distances match the canonical snapshot.
- Added Julia WGS84 → Belgian Lambert 72 projection math; all 100 committed heat pixel coordinates match exactly, covering the transformation before TIFF decoding.
- Added a GitHub Actions container job that builds `julia/Dockerfile` and smoke-tests `/health` plus proximity-only ranking.
- Pinned the Julia container base image by digest; the image still builds successfully.
- Added and built `julia/Dockerfile`; the packaged container passes health and API smoke tests.
- Added `julia/src/Refresh.jl` and `julia/refresh_open_data.jl`: Julia now refreshes managed-tree, remarkable-tree, counter-device, and five counter-history snapshots with metadata/history validation, committed-ID preservation, URL-safe queries, and atomic writes. Python remains the documented fallback for derived joins and unsupported LZW TIFF ingestion.

## Questions / Next steps
- Julia public API source refresh is now available; validate it locally against the live Brussels endpoints when credentials/network access are available. Keep Python fallback for derived joins and unsupported LZW TIFF ingestion.
- Julia test suite passes 229 tests, and `scripts/validate-all.sh` passes both the original Python/Node gate and the Julia gate after the refresh milestone.
- Extended `julia/refresh_open_data.jl` with optional `--with-derived`: source refresh remains isolated by default, while Julia can regenerate the native nearest-counter and measured-flow artifacts without requiring Python. Added `--check`, which validates live Brussels endpoints in a temporary directory without modifying committed snapshots. Python remains the fallback path.
- Live `--check` passed against the current public endpoints; committed snapshots were unchanged.
- Added `JULIA_REFRESH_CHECK=1 scripts/validate-julia.sh` as an opt-in repeatable gate for live API contract checks; the default offline validation remains unchanged for CI stability.
- Added a manually dispatched GitHub Actions job for the live refresh check; pull-request CI remains deterministic and offline.
- Extended explicit refresh modes with `--with-analysis`, which requires `--with-derived`, regenerates sensitivity JSON/CSV/Markdown artifacts, and deliberately leaves stakeholder review data untouched.
- Hardened the refresh CLI with `--help` and unknown-option rejection; Julia tests remain 229/229.
- Derived refresh outputs are now generated in a temporary directory and published only after all requested joins/artifacts succeed, preventing partial derived updates.
- `--check` now snapshots source bytes before live validation and asserts they are unchanged afterward; fixed conditional module imports so all refresh modes parse correctly. Live check passed.
- Added isolated sensitivity-artifact generation coverage; the Julia suite now passes 233 tests, and the unified validation gate remains green.
- Added the safe Julia public-API check command to the root README quickstart.
- Added regression tests for negative counts and incomplete seven-day counter histories; Julia now passes 235 tests. `git diff --check` is clean.
- Hardened bicycle-counter refresh parsing to reject missing or malformed coordinate arrays; extracted and directly tested the parser. Julia now passes 237 tests; the full unified validation gate remains green.
- Parameterized Julia spatial, flow, and sensitivity generators over a data directory. `--check --with-derived --with-analysis` now validates the complete live refresh pipeline in temporary storage; it passed without changing committed snapshots.
- Reviewed `public/index.html` and `src/TreesSurfaces.jl`: the UI has strong provenance, interpretation boundaries, CSP nonce handling, escaping, keyboard-usable map buttons, and server-authoritative ranking. Julia tests pass 500/500.
- UI review found no release-blocking correctness or security defect. Follow-ups: show a visible error state when `/api/screen` fails, add a responsive overflow treatment for the wide ranking table, and consider a stronger focus style/selection announcement for map buttons.
- Implemented all three UI follow-ups in `public/index.html`: API failures now show an alert, the ranking table scrolls horizontally on small screens, and map buttons have visible focus styling with polite selection announcements. Julia tests pass 500/500 and `scripts/validate-julia.sh` passes.
