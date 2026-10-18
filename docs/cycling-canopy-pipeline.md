# Reproduce the local cycling-canopy comparison

This is an **offline mapped-overlap/proximity analysis**, not a shade model. The
canonical implementation is `research/canopy/`; it replaces the exploratory
scripts in ignored `.cache/vub-canopy-2021/`. Do not use cached scripts to regenerate
new research results.

## Superseded artifacts

Three committed files come from the exploratory phase and are kept only as history. Their
numbers were verified against the canonical outputs on 2026-10-17 and agree exactly where
they overlap, so nothing is lost by using the canonical files instead:

| Superseded | Canonical | Agreement |
|---|---|---|
| `data/research/cycling-canopy-local-comparison.json` | `data/research/canopy-verified/comparison.json` | all 30 rows identical on overlap and longest non-overlap; differs only in the `limits` text and two legacy-only fields |
| `data/research/cycling-canopy-100m-windows.json` | `data/research/canopy-verified/windows.json` | all 40 window rows and 10 summaries identical; differs only in `method`/`limits` wording and in the canonical file's added provenance fields |
| `data/research/cycling-canopy-pilot-segments.json` | covered by the canonical selection | kept as the original three-segment pilot record |

The legacy files are deliberately left byte-unchanged rather than annotated in place, so the
exploratory record stays as produced. New work must read the canonical outputs, which carry
input identity, code identity and environment provenance; the legacy files do not.

## Environment and tests

Linux is currently required for atomic no-replace output publication. Use
Python 3.12.12 and uv (tested with 0.13.0). Direct and transitive dependencies are
locked in `research/canopy/uv.lock`; Fiona and Shapely are pinned in `pyproject.toml`.
Dependency/Python installation can need network access, but analysis and tests
never fetch upstream research datasets. Python, Fiona, GDAL, Shapely, GEOS and
platform versions are recorded in every output.

```sh
scripts/validate-canopy.sh
scripts/validate-imagery.sh
scripts/validate-all.sh
```

The canopy gate runs synthetic/small-snapshot tests both normally and under
`python -O`. It does not require the 2 GB source. CI runs this gate separately from
Julia. `scripts/validate-imagery.sh` is the same shape of gate for the sibling
`research/imagery/` project, which compares the two 2021 flight products and needs no
downloads to test; see `docs/imagery-registration-check.md`. `validate-all.sh` runs both gates; Julia must be configured locally. For the
current mise installation, a per-command `MISE_JULIA_VERSION=1.10.12` suffices and
does not alter global configuration.

## Frozen inputs

`data/research/canopy-inputs/manifest.json` identifies the exact bytes used:

- Seven VUB shapefile components remain ignored in `.cache/vub-canopy-2021/`.
  Their public URLs, sizes, published MD5s and locally computed SHA-256s are in the
  manifest. All seven published MD5s were reverified when freezing the manifest.
- Small Zenodo metadata, cycling-frame, request and count-only response snapshots
  are versioned alongside the manifest. The complete cycling frame is retained;
  selection is recomputed, not read from a mutable selected-feature cache.
- Response timestamps are preserved. The VUB download date was recovered from the
  session, but exact HTTP receipt timestamps were not retained; these are explicitly
  unknown, not inferred from file mtimes. The manifest also preserves the exact
  count-only request URL reconstructed from the recorded request parameters.

If the large inputs are absent, download the seven **full files** from the URLs in
the manifest into a local cache, preserving their names. This is about 2 GB.
Do not use range-heavy remote spatial queries (the exploratory attempt hit rate
limits); stop on HTTP 429 and respect the server's backoff. The offline runner
will reject missing, resized, or checksum-mismatched files. It never downloads,
repairs a manifest, or automatically accepts changed upstream data.

A new upstream snapshot requires an explicit new manifest and reviewed sampling
parameters. Editing the trusted manifest deliberately changes the accepted input
identity; checksums protect reproducibility, not against a malicious manifest
editor or errors in the publisher's classification. Preserve the old experiment.

## One run, two linked outputs

From the repository root, choose an output directory that does not exist:

```sh
uv run --locked --python 3.12.12 --project research/canopy \
  python research/canopy/run.py \
  --cache .cache/vub-canopy-2021 \
  --output .cache/canopy-reproduction-001
```

The default manifest is the versioned one. `--manifest PATH` permits an explicitly
reviewed alternative manifest; the selected frame and measurement parameters
remain fixed in code. Publication uses Linux `renameat2(RENAME_NOREPLACE)`; even
an empty destination created concurrently is not replaced. A platform without
this primitive fails rather than weakening that guarantee.

The run:

1. Verifies the exact declared input set, sizes and SHA-256s. A synthetic fixture
   may omit the SBN/SBX pair, but an unmanifested index pair is rejected. The real
   frozen source includes both. Rechecks source identities before publication.
2. Validates EPSG:31370, unique cycling IDs, request bounds, retrieved feature
   count and the separately saved count-only response. Recomputes all type 12,
   status 1, wholly-contained segments of at least 100 m in the predefined 1 km
   square. Rejects disconnected, non-simple, closed, zero-length or non-2D routes.
3. Extracts vegetation with a 10 m margin (maximum proximity buffer is 5 m).
   Cross-checks the spatial index by scanning every SHP record envelope and exact
   candidate intersections; checks SHP/DBF record counts. Subsequent candidate
   geometry reads still share Fiona/SHX: this is not an independent parser audit.
4. Repairs invalid polygon cover with `make_valid`, keeps polygon components,
   records discarded lower-dimensional components, areas and validity reasons,
   and compares reported metrics against `buffer(0)` repairs.
5. Computes both comparison and window metrics from the **same in-memory validated
   routes and canopy geometries**. There is no separate window-stage input path,
   no `runpy`, no AST loading, and no report-writing import side effect.
6. Writes `comparison.json` and `windows.json` atomically as a pair. Both carry the
   manifest identity, source identities/provenance, code/lockfile hashes,
   environment and parameters. The window report includes the exact SHA-256 of
   the encoded comparison file. Output directories are never overwritten.

The JSON files include scientific limitations and full-precision values. The
older human-readable comparison/window Markdown reports remain exploratory
summaries; original numbers were retained for numerical regression. The pipeline
does not regenerate the historical imagery panels or pilot strip plot.

## Checks and scope

Regression tests cover empty/full/boundary/disjoint cover, bends and reversal,
invalid routes, tampering with same-sized files, counts/CRS/duplicates, optional
index identity, full-scan mismatch, invalid polygon repairs, complete manifest-backed
execution, endpoint windows with remainders, deterministic repeat execution,
mid-run input changes, report linkage, and concurrent publication refusal.

A full-source run reproduced the previous 30 comparison rows, 40 window-condition
rows and 10 summaries exactly. The frame contains five segments and is not a
representative or independent sample. Two endpoint window schemes each cover
1,000 of 1,295.5 m; they overlap each other and exclude incomplete remainders.

All interpretations in `data/research/cycling-canopy-checkpoint.md` still apply:
2021 vegetation is intersected with current road-reference geometry (including
one recorded 2022 cycling-street start); class 4 is height-based; absence of a
mapped polygon is not validated absence, and neither direct overlap nor 5 m
proximity measures actual shade, cooling, or cyclist exposure. This pipeline
improves reproducibility, not the underlying observational evidence.
