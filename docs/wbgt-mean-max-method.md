# Preparing the daily-mean versus daily-maximum WBGT comparison

## Status

The offline comparison command and synthetic tests are implemented, and a **real
paired run has been performed** on the cached 2016 files. The daily-mean file is
now present in the git-ignored cache: `WBGT_year_daily_mean_2016.nc`,
34,658,563 bytes — exactly the size the earlier remote probe recorded — with
SHA-256 `621b0fc7…7257ca`. The run validated all 14,274 sampled cell-days
(*Validations and measurements*) and wrote its outputs to `.cache/wbgt-mean-max/`,
where they are **deliberately not committed**: whether to publish a mean/maximum
comparison at all is still a stakeholder decision, separate from whether the
arithmetic is right, and VITO's reuse terms remain unresolved. The measured rank
and value comparisons are therefore available to that decision without being
reproduced in this repository. Nothing here changes the operational heat/proximity
ranking or grants reuse rights.

The [VITO archive page](https://provide.marvin.vito.be/ftp/compressed_daily/)
lists daily mean and maximum WBGT at 100 m for 2008–2017. On 17 October 2026,
HEAD and two bounded 64 KiB range probes of
[`WBGT_year_daily_mean_2016.nc`](https://provide.marvin.vito.be/ftp/compressed_daily/Brussels/WBGT_year_daily_mean_2016.nc)
confirmed availability (34,658,563 bytes), title “Daily average Wet Bulb Globe
Temperature for Brussels for 2016”, EPSG:3035, °C with scale factor 0.01, and
366 × 301 × 301 dimensions. Coordinates and daily offsets matched the local
maximum file exactly. Only metadata/coordinate arrays were inspected; the
mean thermal variable and full file integrity remain unverified. Temporary
incomplete metadata files were removed, never placed in the archive cache.

A second ranged read (same file, one 64 KiB block, no bulk download) checked the
declarations the comparison now requires to match, and they do:

| Declaration | Mean file (remote) | Maximum file (local) |
|---|---|---|
| Title statistic | "Daily average … for 2016" | "Daily maximum … for 2016" |
| CRS | EPSG:3035 | EPSG:3035 |
| `WBGT` dtype | int32 | int32 |
| `WBGT` units / scale | °C / 0.01 | °C / 0.01 |
| `add_offset` | absent (0.0) | absent (0.0) |
| `_FillValue` / `missing_value` | absent | absent |
| Grid `x`, `y` first values, step | 3910011, 3081505, step 100 | identical |
| Time length, units, calendar | 366, days since 2016-01-01, proleptic_gregorian | identical |

So the cross-file packing requirement added after independent review should be satisfied
by the real pair rather than failing on it. What remains unverified is everything about
the **values**: whether daily maximum ≥ daily mean holds, whether any sampled cell is
missing, and whether both products share timezone/day-boundary conventions.

Two traps for the independent-extraction check below, both hit while carrying it out on
this pair — each produced a large, entirely spurious disagreement:

1. **Dimension order differs by library.** `h5py` and `netCDF4` report `WBGT` as
   `(366, 301, 301)` with declared dimensions `('time', 'y', 'x')`, while `HDF5.jl`
   reports `(301, 301, 366)` for the same dataset, and the reader's `(x, y, time)`
   assertion passes on it. Index by dimension *name*, never by position. Getting this
   wrong mis-paired cells and produced an apparent 27 °C disagreement.
2. **`netCDF4` applies `scale_factor` and `add_offset` automatically by default.** Reading
   the variable and then multiplying by the declared scale applies it twice: values came
   out 100× too small. Call `set_auto_maskandscale(False)` and apply the declarations
   explicitly, which also tests that they are what the tool assumes. `HDF5.jl` does no
   scaling, so the reader applies the scale itself.

With both handled, an independent extraction of the 2016 pair reproduced this tool's
reference-day and JJA values for all 39 sampled cells to within 5e-5 °C (the tool's
rounding limit), and independently found the same minimum daily maximum-minus-mean. That
verification used the local cache and wrote only to a temporary directory: no derived
heat values were committed, because whether to publish a mean/max comparison at all is
still a stakeholder decision, separate from whether the arithmetic is right.

The page and inspected attributes do not establish reuse terms: the archive page
states none and the annual NetCDF files carry no licence attribute. Two related
records do not transfer theirs — the Souverijns et al. (2026) decadal set is
CC BY 4.0, and the Copernicus CDS record `sis-urban-climate-cities` is CC-BY-4.0
but covers hourly temperature, humidity and wind without WBGT. Confirm daily-file
use and redistribution of derived results with VITO before external reuse; see
[`heat-season-method.md`](heat-season-method.md), *Licence and lineage*.
The open licence follow-up remains unresolved. No contact has been sent.

## Research question

On the **same 100 m cells and dates in 2016**, how much does using daily mean
rather than daily maximum WBGT change spatial ranks and selected-cell membership?

This controls date and grid *within the archive*. It does not make either archive
variable equivalent to Brussels Environment's detailed 2 m radiation/shade
simulation or explain the cause of cross-product differences.

The bounded design compares:

1. 24 August 2016 daily mean versus daily maximum;
2. the average of 92 JJA daily means versus the average of 92 JJA daily maxima;
3. reference date versus JJA within each statistic separately.

The second comparison is **not** a summer maximum or a mean computed from daily
maxima that reconstructs the daily-mean series. No 26 °C hot-day threshold is
transferred to the mean product.

Note the overlap in the third and fourth comparisons: the reference day 2016-08-24 is
itself one of the 92 JJA days, so "reference day versus JJA" relates a day to a
summary that contains it. It is a consistency view, not held-out summer validation, in
the same sense as the archive diagnostics.

## Run when valid local inputs are available

```bash
julia --project=. bin/compare_wbgt_mean_max.jl --help
julia --project=. bin/compare_wbgt_mean_max.jl \
  .cache/urbclim/WBGT_year_daily_mean_2016.nc \
  .cache/urbclim/WBGT_year_daily_max_2016.nc \
  .cache/wbgt-mean-max
```

The paths above are the real cached pair, so this reproduces the held-local result
exactly; the command refuses an output directory that already exists.

The command performs no network calls or package installation. Both files must
already exist. It samples `data/brussels-trees-sample.json` and writes only:

- `wbgt-mean-max-comparison.json`: provenance, validation results, paired cell
  measurements and rank comparisons;
- `wbgt-mean-max-comparison.md`: readable method, comparisons and cell table.

There is no implicit fallback, imputation, licence confirmation or incorporation
into existing artifacts. Missing or invalid inputs fail before results are written.
The output directory must be empty or absent; both files are staged first — in a
sibling directory when the parent is writable, otherwise the system temporary
directory — and then moved into place one at a time with the first move undone if the
second fails, so a failure leaves either both files or neither. Rerunning into a fresh
directory from the same inputs reproduces both files byte for byte; rerunning into the
same directory is refused rather than overwriting. Do not use synthetic test files as
evidence about Brussels.

## Validations and measurements

`src/Wbgt.jl::read_wbgt_year` defaults to `expected_statistic=:maximum`, requiring
an explicit `:mean` for average data. A declared statistic/year title is checked
rather than trusting the filename. The reader validates the supported calendar,
complete year, grid spacing, units and scaling, and converts declared missing
sentinels to NaN before scaling. The existing maximum workflow stays maximum-only.

`src/WbgtComparison.jl` requires two **distinct** 2016 files with identical full
coordinate axes, calendar, time origin, dates, sampled cell memberships and
**identical packing**: `scale_factor`, `add_offset` and units must match, because the
result is a temperature difference and a mismatched scale or offset would change the
printed °C values while leaving rank statistics intact. The reader checks that each
declared `scale_factor` is finite and positive and that `add_offset` is finite; it
does not infer that any two files share a convention. Identity is enforced and
recorded: each input's resolved path, byte size and SHA-256 are written to the
output, the two digests must differ, and a pair whose sampled differences are all
exactly zero is refused as a duplicated or mislabelled input rather than reported as
a measured null. `zero_difference_fraction` is recorded so near-degenerate inputs stay
visible.

It rejects nonfinite or implausible sampled values and a sampled daily maximum below
the paired mean (floating arithmetic tolerance 1e-8 °C, inclusive at the boundary and
covered by tests on both sides). It tests every sampled cell-day in the year, not just
JJA. This does not validate unsampled temperatures, and it cannot detect two files that
are genuinely different but share a packing and a plausible difference.

Matching date labels and the proleptic-Gregorian calendar do **not** independently
verify the underlying timezone or daily aggregation boundaries. Confirm those
conventions with the provider; the result explicitly records this unresolved
assumption. Maximum ≥ mean is necessary, not sufficient, evidence of compatibility.

Distinct cells receive equal weight; multiple tree records in one cell are kept
as provenance, not extra heat observations. The 100 committed tree points occupy about
39 distinct 100 m cells, so the effective sample is those cells and the top-quarter
cutoff is roughly ten cells: the rank statistics here are coarse by construction, and
`validation.minimum_max_minus_mean_c` is one global minimum over all sampled cell-days
(366 × cells), not a per-cell or per-day attribution. The output records mean, maximum and
paired maximum-minus-mean in °C for the reference day and JJA averages. Spearman
uses midranks. Top-quarter k is rounded upward; exact top-k uses cell-ID tie breaks,
while inclusive membership retains all cutoff ties and reports set sizes and
Jaccard. Constant ranks yield an undefined correlation, not zero.

## Interpretation and independent checks

The pilot is descriptive: no p-values or confidence intervals treat correlated
cells/days as independent. No tree-cooling, individual exposure or city-wide
representativeness claim follows from the selected cells.

Once real mean data are available, independently extract a few paired cells and
dates with another NetCDF/GIS implementation. Check axis order, scale factor and
missing sentinels before interpreting ranks. Agreement of metadata alone does not
replace that check. A negative paired difference, incompatible day convention or
unexplained independent-extraction mismatch blocks interpretation.

On the real pair, none of those three blockers fired. Every listed validation
passed across all 14,274 sampled cell-days, including that each sampled daily
maximum is greater than its paired daily mean, and a second run into a fresh
directory reproduced both output files byte for byte — so the determinism claimed
for synthetic inputs holds on the real ones. The smallest paired difference and
every rank statistic sit in the local output rather than here, for the reason given
under *Status*.

A useful follow-up graphic would pair mean/max ranks per cell, showing cutoff
rank ties explicitly and keeping reference-day and JJA panels separate. Do not
present a synthetic demonstration as measured results. Multi-year validation and
physical field validation remain subsequent work, not claims of this pilot.

## Verification

An independent read-only review of this module (2026-10-17) found that cross-file packing was
never compared, that provenance recorded filenames only, and that degenerate or duplicated
inputs were accepted; a verification pass on the fixes then found the staging, identity-during-
read, declared-CRS and tie-coverage gaps. All are closed above and covered by the tests below.
The reviewer did not have the real mean archive, so nothing here has been checked against
VITO's actual mean file.

`test/wbgt_comparison.jl` supplies hand-computable paired series and temporary
synthetic HDF5 archives. It checks statistic/calendar rejection, alignment,
missingness, maximum-below-mean failures at and beyond the tolerance boundary,
equal-cell deduplication, separate outputs and no-output-on-invalid-input behavior, and
now also cross-file `scale_factor`/`add_offset`/units mismatch, identical-file and
all-zero-difference refusal, provenance fields, byte-identical reruns into fresh
directories, the undefined correlation of constant ranks, a hand-computed cutoff tie
(two cells tied at 20 °C with k = 1 keep one cell exactly and both inclusively, giving
Jaccard 0), and the command-line argument handling (both cases exit before any project
module is loaded). Packing mismatches and an on-disk retitled duplicate are exercised
end to end through `generate`, not only through `compare_samples`. It runs in the
normal project gate:

```bash
mise exec julia@1.10.12 -- scripts/validate-all.sh
```
