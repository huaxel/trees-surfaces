module WbgtComparison

using JSON3
using Statistics
include(joinpath(@__DIR__, "Wbgt.jl"))
include(joinpath(@__DIR__, "HeatDiagnostics.jl"))
using .Wbgt
using .HeatDiagnostics

export sample_archive, compare_samples, generate

# Materialize only sampled series in the returned object; the full cube can be
# released before the second annual file is read.
function sample_archive(path, statistic, trees)
    ids = [get(tree, "id", nothing) for tree in trees]
    !isempty(ids) && all(id -> id isa AbstractString && !isempty(id), ids) || error("trees require nonempty string IDs")
    length(unique(ids)) == length(ids) || error("duplicate tree IDs")
    identity_before = Wbgt.IOUtils.file_identity(path)
    archive = Wbgt.read_wbgt_year(path; expected_statistic=statistic)
    archive.year == 2016 || error("this bounded comparison requires 2016 archives")
    sampled = Wbgt.sample_tree_points(archive, trees)
    cell_ids = sort(unique("$(row["column"]):$(row["row"])" for row in sampled))
    rows = Any[]
    series = Matrix{Float64}(undef, length(archive.dates), length(cell_ids))
    for (position, id) in enumerate(cell_ids)
        members = filter(row -> "$(row["column"]):$(row["row"])" == id, sampled)
        cell = first(members)
        series[:, position] = archive.wbgt[cell["column"], cell["row"], :]
        push!(rows, Dict("id" => id, "x" => cell["cell_x"], "y" => cell["cell_y"],
            "tree_ids" => sort([row["id"] for row in members])))
    end
    # The digest must describe the bytes that were parsed, not a later state of the file.
    identity_after = Wbgt.IOUtils.file_identity(path)
    identity_before == identity_after || error("input changed while being read: $(basename(path))")
    (statistic=archive.statistic, title=archive.title, year=archive.year,
        dates=archive.dates, time_units=archive.time_units, calendar=archive.calendar,
        crs=archive.crs, x=archive.x, y=archive.y, cells=rows, values=series,
        filename=basename(path), scale_factor=archive.scale_factor, add_offset=archive.add_offset,
        units=archive.units, path=identity_after.path, bytes=identity_after.bytes,
        sha256=identity_after.sha256)
end

function compare_samples(average, maximum)
    average.statistic == :mean && maximum.statistic == :maximum || error("expected mean then maximum samples")
    average.year == maximum.year == 2016 || error("comparison requires matching 2016 archives")
    average.calendar == maximum.calendar == "proleptic_gregorian" || error("calendar mismatch")
    average.time_units == maximum.time_units || error("time origins/day labels differ")
    average.dates == maximum.dates || error("dates differ")
    Wbgt.validate_calendar_year_coverage(average.dates, 2016, "paired samples")
    # The result is a temperature difference, so the two files must be packed identically;
    # ranking comparisons hide a mismatched scale, while the printed °C differences would be wrong.
    average.scale_factor == maximum.scale_factor || error("packing mismatch: scale_factor differs between the mean and maximum files")
    average.add_offset == maximum.add_offset || error("packing mismatch: add_offset differs between the mean and maximum files")
    average.units == maximum.units == "°C" || error("units differ between the mean and maximum files")
    average.crs == maximum.crs || error("declared CRS differs between the mean and maximum files")
    average.sha256 == maximum.sha256 && error("the two inputs are the same file; a mean/maximum comparison needs two distinct archives")
    average.path != maximum.path || error("the two inputs are the same path")
    average.x == maximum.x && average.y == maximum.y || error("coordinate grids differ")
    average.cells == maximum.cells || error("sampled cells or tree membership differ")
    !isempty(average.cells) || error("no sampled cells")
    expected_shape = (length(average.dates), length(average.cells))
    size(average.values) == size(maximum.values) == expected_shape || error("sample matrix shape mismatch")
    for values in (average.values, maximum.values)
        all(isfinite, values) || error("missing or nonfinite sampled WBGT; no imputation")
        all(v -> -20 <= v <= 45, values) || error("sampled WBGT outside plausible range")
    end
    delta = maximum.values - average.values
    minimum(delta) >= -1e-8 || error("daily maximum is below daily mean at a sampled cell/date")
    # A series identical in every sampled cell and day is a duplicate or mislabelled file, not a
    # measured null. Report the zero-difference count so near-degenerate inputs stay visible.
    zero_fraction = count(==(0.0), delta) / length(delta)
    zero_fraction < 1 || error("every sampled cell-day has zero maximum-minus-mean; check for a duplicated input")
    reference = Wbgt.reference_index(average.dates)
    season = Wbgt.season_indices(average.dates, 2016)
    length(season) == 92 || error("expected 92 JJA days")
    avg_ref, max_ref = average.values[reference, :], maximum.values[reference, :]
    avg_jja = vec(mean(average.values[season, :]; dims=1))
    max_jja = vec(mean(maximum.values[season, :]; dims=1))
    ids = [row["id"] for row in average.cells]
    k = HeatDiagnostics.selection_k(length(ids), 25)
    comparisons = Dict(
        "reference_mean_vs_maximum" => HeatDiagnostics.comparison(avg_ref, max_ref, ids, k),
        "jja_mean_vs_maximum" => HeatDiagnostics.comparison(avg_jja, max_jja, ids, k),
        "mean_reference_vs_jja" => HeatDiagnostics.comparison(avg_ref, avg_jja, ids, k),
        "maximum_reference_vs_jja" => HeatDiagnostics.comparison(max_ref, max_jja, ids, k))
    records = [merge(average.cells[i], Dict(
        "reference_daily_mean_c" => avg_ref[i], "reference_daily_maximum_c" => max_ref[i],
        "reference_max_minus_mean_c" => max_ref[i] - avg_ref[i],
        "jja_mean_of_daily_means_c" => avg_jja[i], "jja_mean_of_daily_maxima_c" => max_jja[i],
        "jja_mean_max_minus_mean_c" => max_jja[i] - avg_jja[i])) for i in eachindex(ids)]
    provenance(s) = Dict("filename" => s.filename, "path" => s.path, "bytes" => s.bytes,
        "sha256" => s.sha256, "declared_title" => s.title,
        "statistic" => string(s.statistic), "scale_factor" => s.scale_factor,
        "add_offset" => s.add_offset, "units" => s.units, "crs" => s.crs,
        "calendar" => s.calendar, "time_units" => s.time_units)
    HeatDiagnostics.publication_value(Dict(
        "schema_version" => 1, "year" => 2016, "reference_date" => Wbgt.REFERENCE_DATE,
        "season_days" => 92, "cells" => length(ids), "tree_count" => sum(length(row["tree_ids"]) for row in average.cells),
        "selection_k" => k, "selection_percentage" => 25,
        "inputs" => Dict("mean" => provenance(average), "maximum" => provenance(maximum)),
        "validation" => Dict("paired_cell_days" => length(delta), "grid_and_dates_match" => true,
            "packing_matches" => true, "distinct_input_files" => true,
            "minimum_max_minus_mean_c" => minimum(delta),
            "zero_difference_fraction" => zero_fraction,
            "max_below_mean_tolerance_c" => 1e-8,
            "day_boundary" => "Time labels match; actual timezone and daily aggregation convention are not independently verified"),
        "licence_status" => "unresolved; local exploratory comparison is not permission to redistribute",
        "interpretation" => "Equal-cell comparison within the 100 m archive; no 2 m raster, mobility score, hot-day threshold or tree-cooling inference. JJA means summarize daily means or daily maxima separately, not the same statistic. No confidence intervals or independent physical validation.",
        "comparisons" => comparisons, "records" => records))
end

fmt(v) = v === nothing ? "undefined (constant ranks)" : string(round(v; digits=3))
function markdown(report)
    lines = ["# Local paired WBGT mean/maximum comparison", "",
        "Generated only from supplied local 2016 annual archives. This is not the operational screen. Reuse terms remain unresolved; this output is not redistribution permission.", "",
        "$(report["tree_count"]) tree points map to $(report["cells"]) distinct cells, weighted equally. Reference date: 2016-08-24; season: 92 JJA days. Units: °C. Positive differences below mean daily maximum minus daily mean, not tree cooling.", "",
        "Validation covers all $(report["validation"]["paired_cell_days"]) sampled cell-days: identical grid, calendar, dates and declared CRS; identical packing (scale factor, offset, units); distinct input digests; complete finite sampled values; maximum ≥ mean (floating tolerance 1e-8 °C). The fraction of sampled cell-days with an exactly zero difference is $(fmt(report["validation"]["zero_difference_fraction"])); a value near 1 means the two inputs are effectively the same series, and a value of exactly 1 is refused rather than reported. Matching date labels do not independently establish identical timezone/day-boundary conventions. Confirm these with the provider before interpreting differences as purely aggregation effects.", "",
        "## Comparisons", "",
        "k=$(report["selection_k"]) is the ceiling of the top quarter of cells. Spearman uses midranks; inclusive sets retain all cutoff ties; exact overlap breaks ties by cell ID. Jaccard divides inclusive intersection by union. Ties can inflate overlap. No intervals are estimated from these dependent cell/day observations.", "",
        "| Comparison | Spearman | Exact overlap | Inclusive set sizes | Inclusive Jaccard |", "|---|---:|---:|---:|---:|"]
    for key in sort(collect(keys(report["comparisons"])))
        c = report["comparisons"][key]
        push!(lines, "| $(key) | $(fmt(c["spearman"])) | $(c["exact_overlap"])/$(report["selection_k"]) | $(length(c["left"]["inclusive_ids"]))/$(length(c["right"]["inclusive_ids"])) | $(fmt(c["inclusive_jaccard"])) |")
    end
    append!(lines, ["", "## Paired cell measurements", "",
        "JJA mean of daily means and JJA mean of daily maxima are distinct summaries. The differences are computed before rounding. Cell ID = archive column:row; tree memberships and physical cell centers are recorded in JSON.", "",
        "| Cell | Trees | Reference mean | Reference maximum | Difference | JJA daily-mean average | JJA daily-maximum average | Difference |", "|---|---:|---:|---:|---:|---:|---:|---:|"])
    for r in report["records"]
        push!(lines, "| $(r["id"]) | $(length(r["tree_ids"])) | $(fmt(r["reference_daily_mean_c"])) | $(fmt(r["reference_daily_maximum_c"])) | $(fmt(r["reference_max_minus_mean_c"])) | $(fmt(r["jja_mean_of_daily_means_c"])) | $(fmt(r["jja_mean_of_daily_maxima_c"])) | $(fmt(r["jja_mean_max_minus_mean_c"])) |")
    end
    append!(lines, ["", "## Limits", "",
        report["interpretation"], "",
        "The existing detailed 2 m normalized WBGT indicator has different radiation treatment and units; it is intentionally absent. A 26 °C threshold calibrated or chosen for daily maxima must not be transferred silently to daily means. Convenience-sampled cells do not represent Brussels, and one year cannot establish multi-year stability.", "",
        "Source: [VITO daily archive](https://provide.marvin.vito.be/ftp/compressed_daily/). File declarations and calendar are recorded in JSON; no download or licence confirmation is performed by this command.", ""])
    join(lines, "\n")
end

function generate(mean_path, maximum_path, trees_path, output_dir)
    for path in (mean_path, maximum_path, trees_path)
        isfile(path) || error("local input missing: $(path); this command never downloads files")
    end
    # Never overwrite any input, even if an input has one of our output names.
    outputs = [joinpath(output_dir, name) for name in ("wbgt-mean-max-comparison.json", "wbgt-mean-max-comparison.md")]
    for out in outputs, input in (mean_path, maximum_path, trees_path)
        abspath(out) == abspath(input) && error("output would overwrite input")
        ispath(out) && realpath(out) == realpath(input) && error("output aliases input")
    end
    trees = JSON3.read(read(trees_path, String), Dict{String,Any})["records"]
    average = sample_archive(mean_path, :mean, trees)
    maximum = sample_archive(maximum_path, :maximum, trees)
    report = compare_samples(average, maximum)
    # Stage both outputs, then move the pair into place, so a failure cannot leave a JSON
    # without its Markdown. The final move is two renames, not one atomic operation: a crash
    # between them leaves either nothing or a complete, self-consistent pair only if the
    # second rename succeeds, so the directory is built first and moved as a unit.
    mkpath(output_dir)
    isempty(readdir(output_dir)) || error("output directory is not empty: $(output_dir)")
    # Stage beside the target when the parent allows it, so both moves stay on one filesystem,
    # and fall back to the system temporary directory when it does not (as IOUtils does for
    # other workflows). Publish the pair only after both staged files exist, and undo a partial
    # publication, so a failure leaves either both files or neither.
    staging = try
        mktempdir(dirname(abspath(output_dir)); prefix = ".wbgt-mean-max-")
    catch
        mktempdir()
    end
    published = String[]
    try
        Wbgt.IOUtils.atomic_write_json(joinpath(staging, basename(outputs[1])), report)
        Wbgt.IOUtils.atomic_write(joinpath(staging, basename(outputs[2])), markdown(report))
        for name in basename.(outputs)
            target = joinpath(output_dir, name)
            # rename is atomic when the staging directory is a sibling, which is the normal case.
            mv(joinpath(staging, name), target)
            push!(published, target)
        end
    catch
        for target in published
            rm(target; force = true)
        end
        rethrow()
    finally
        isdir(staging) && rm(staging; force = true, recursive = true)
    end
    report
end

end
