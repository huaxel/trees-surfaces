module HeatDiagnostics

using JSON3
using Statistics
include(joinpath(@__DIR__, "IOUtils.jl"))
using .IOUtils

export analyze, generate, top_set, midranks, variance_partition

const METRICS = ("reference_date_wbgt_c", "seasonal_mean_wbgt_c", "seasonal_p90_wbgt_c", "hot_days_per_season")
const INPUTS = ("brussels-trees-sample.json", "brussels-tree-heat-sample.json", "brussels-heat-wbgt-sample.json")

# Exact ties refer to the rounded values actually committed, not unobserved precision.
function midranks(values)
    [count(x -> x > v, values) + (count(==(v), values) + 1) / 2 for v in values]
end

function top_set(values, ids, k)
    length(values) == length(ids) || error("values and IDs differ in length")
    1 <= k <= length(values) || error("invalid top-k")
    order = sortperm(eachindex(values); by=i -> (-values[i], ids[i]))
    cutoff = values[order[k]]
    Dict("k" => k, "cutoff" => cutoff,
        "exact_ids" => ids[order[1:k]],
        "inclusive_ids" => sort(ids[findall(v -> v >= cutoff, values)]),
        "cutoff_ties" => count(==(cutoff), values))
end

function comparison(a, b, ids, k)
    left, right = top_set(a, ids, k), top_set(b, ids, k)
    l, r = Set(left["inclusive_ids"]), Set(right["inclusive_ids"])
    ra, rb = midranks(a), midranks(b)
    rho = length(unique(a)) < 2 || length(unique(b)) < 2 ? nothing : cor(ra, rb)
    Dict("spearman" => rho, "left" => left, "right" => right,
        "exact_overlap" => length(intersect(Set(left["exact_ids"]), Set(right["exact_ids"]))),
        "inclusive_overlap" => length(intersect(l, r)),
        "inclusive_jaccard" => length(intersect(l, r)) / length(union(l, r)))
end

# Population variance identity, not a fitted random-effects model or uncertainty estimate.
function variance_partition(values, cells; equal_cells=false)
    keys = sort(unique(cells))
    groups = [findall(==(key), cells) for key in keys]
    weights = equal_cells ? fill(1 / length(groups), length(groups)) : length.(groups) ./ length(values)
    means = [mean(values[g]) for g in groups]
    grand = sum(weights .* means)
    within = sum(weights[i] * mean((values[g] .- means[i]).^2) for (i, g) in enumerate(groups))
    between = sum(weights .* (means .- grand).^2)
    total = within + between
    Dict("within" => within, "between" => between, "total" => total,
        "within_fraction" => total == 0 ? nothing : within / total)
end

const SELECTION_PERCENTAGES = (10, 20, 25, 33, 50)
selection_k(n, percentage) = max(1, cld(n * percentage, 100))

function threshold_sweep(fine, reference, seasonal, ids)
    [Dict("percentage" => p, "units" => length(ids), "k" => selection_k(length(ids), p),
        "fine_vs_seasonal" => comparison(fine, seasonal, ids, selection_k(length(ids), p)),
        "reference_vs_seasonal" => comparison(reference, seasonal, ids, selection_k(length(ids), p)))
        for p in SELECTION_PERCENTAGES]
end

# Coarsening is a deterministic loss-of-precision scenario, not a stochastic
# error model. Apply once per archive cell, never independently per tree.
function rounding_sweep(cell_fine, reference, seasonal, cell_ids)
    k = selection_k(length(cell_ids), 25)
    [Dict("decimal_places" => digits, "k" => k,
        "reference_distinct_values" => length(unique(round.(reference; digits=digits))),
        "seasonal_distinct_values" => length(unique(round.(seasonal; digits=digits))),
        "fine_vs_seasonal" => comparison(cell_fine, round.(seasonal; digits=digits), cell_ids, k),
        "reference_vs_seasonal" => comparison(round.(reference; digits=digits), round.(seasonal; digits=digits), cell_ids, k))
        for digits in (2, 1, 0)]
end

function coverage_sweep(fine, cells, reference, seasonal)
    cell_ids = sort(unique(cells))
    groups = [findall(==(cell), cells) for cell in cell_ids]
    scenarios = Any[]
    for minimum_trees in (1, 2, 3)
        selected = findall(g -> length(g) >= minimum_trees, groups)
        kept = sort([i for j in selected for i in groups[j]])
        result = Dict{String,Any}("minimum_trees" => minimum_trees,
            "trees" => length(kept), "cells" => length(selected),
            "excluded_trees" => length(fine) - length(kept),
            "excluded_cells" => length(cell_ids) - length(selected),
            "cell_ids" => cell_ids[selected], "k" => nothing,
            "variance_equal_cell" => nothing, "variance_tree_weighted" => nothing,
            "fine_vs_seasonal" => nothing, "reference_vs_seasonal" => nothing)
        if !isempty(selected)
            gs = groups[selected]
            k = selection_k(length(gs), 25)
            result["k"] = k
            a = [mean(fine[g]) for g in gs]
            b = [seasonal[first(g)] for g in gs]
            c = [reference[first(g)] for g in gs]
            result["variance_equal_cell"] = variance_partition(fine[kept], cells[kept]; equal_cells=true)
            result["variance_tree_weighted"] = variance_partition(fine[kept], cells[kept])
            result["fine_vs_seasonal"] = comparison(a, b, cell_ids[selected], k)
            result["reference_vs_seasonal"] = comparison(c, b, cell_ids[selected], k)
        end
        push!(scenarios, result)
    end
    scenarios
end

function indexed(payload, label)
    rows = payload["records"]
    isempty(rows) && error("$(label) has no records")
    ids = [string(r["id"]) for r in rows]
    all(!isempty, ids) && length(unique(ids)) == length(ids) || error("$(label) has empty or duplicate IDs")
    Dict(string(r["id"]) => r for r in rows)
end

function finite_number(value, label)
    value isa Real && !(value isa Bool) && isfinite(value) || error("invalid $(label)")
    Float64(value)
end

# Publication precision only; rank ordering and membership use unrounded calculations.
# Avoid last-bit variation between normal execution and Pkg.test check-bounds mode.
publication_value(x::AbstractFloat) = round(x; digits=12)
publication_value(x::AbstractDict) = Dict(k => publication_value(v) for (k,v) in x)
publication_value(x::AbstractVector) = publication_value.(x)
publication_value(x) = x

function validate_metadata(heat, wbgt)
    expected_heat = Dict(
        "source" => "urban_heat_islands_WBGT_MEAN_24082016_0-1_byte.tif",
        "source_metadata_id" => "BRU_ENVI_73b4f29a-cff0-4d6a-a239-cb99d3140531",
        "crs" => "EPSG:31370",
        "value_semantics" => "source-normalized 0–100 WBGT indicator; value 0 is source NoData, not degrees Celsius")
    expected_wbgt = Dict(
        "reference_date" => "2016-08-24", "crs" => "EPSG:3035",
        "value_semantics" => "UrbClim 2 m Wet Bulb Globe Temperature, degrees Celsius, daily maximum, on a 100 m grid in EPSG:3035; computed with the Liljegren et al. (2008) method following ISO 7243")
    for (payload, expected) in ((heat, expected_heat), (wbgt, expected_wbgt)), (key, value) in expected
        get(payload, key, nothing) == value || error("unsupported source metadata: $(key); revisit the research design")
    end
    window = Dict("start_year" => 2008, "end_year" => 2017, "seasons" => 10,
        "years" => collect(2008:2017), "months" => ["06", "07", "08"])
    get(wbgt, "window", nothing) == window || error("unsupported WBGT seasonal window")
    grid = get(wbgt, "grid", Dict())
    all(get(grid, k, nothing) == v for (k,v) in ("step_metres" => 100, "columns" => 301, "rows" => 301)) || error("unsupported archive grid")
    licence_review = get(wbgt, "licence_review", Dict())
    get(licence_review, "status", nothing) == "unresolved" || error("licence status changed; review report wording")
    related = get(licence_review, "related_records", Any[])
    isempty(related) && error("licence review must record the related records whose terms do not transfer")
    all(get(record, "applies_to_this_archive", true) == false for record in related) ||
        error("a related record is being presented as licensing this archive")
    Dict("heat" => expected_heat, "wbgt" => expected_wbgt, "window" => window,
        "archive_grid_step_metres" => 100, "licence_status" => "unresolved")
end

function analyze(trees_payload, heat_payload, wbgt_payload)
    metadata = validate_metadata(heat_payload, wbgt_payload)
    trees, heat, wbgt = indexed(trees_payload, "trees"), indexed(heat_payload, "heat"), indexed(wbgt_payload, "WBGT")
    Set(keys(trees)) == Set(keys(heat)) == Set(keys(wbgt)) || error("input ID sets differ; missing values must not be silently dropped")
    ids = sort(collect(keys(trees)))
    cells = String[]
    for id in ids
        for axis in ("column", "row")
            v = wbgt[id][axis]
            v isa Integer && !(v isa Bool) && 1 <= v <= 301 || error("invalid WBGT cell index")
        end
        get(wbgt[id], "reference_date", nothing) == "2016-08-24" || error("WBGT row reference date differs")
        push!(cells, "$(wbgt[id]["column"]):$(wbgt[id]["row"])")
        # Point artifacts must still describe the same locations as the managed snapshot.
        for axis in ("latitude", "longitude")
            a = finite_number(trees[id][axis], axis)
            b = finite_number(heat[id][axis], axis)
            a == b || error("heat coordinates differ for $(id)")
        end
    end
    fine = [finite_number(heat[id]["heat_pixel"], "heat pixel") for id in ids]
    all(v -> 0 < v <= 100, fine) || error("heat has NoData or out-of-range indicator")
    values = Dict(metric => [finite_number(wbgt[id][metric], metric) for id in ids] for metric in METRICS)
    cell_ids = sort(unique(cells))
    groups = [findall(==(cell), cells) for cell in cell_ids]
    for metric in METRICS, group in groups
        length(unique(values[metric][group])) == 1 || error("WBGT values disagree within a cell for $(metric)")
    end
    cell_fine = [mean(fine[g]) for g in groups]
    cell_values = Dict(metric => [values[metric][first(g)] for g in groups] for metric in METRICS)
    tree_k, cell_k = min(10, length(ids)), max(1, ceil(Int, length(cell_ids) / 4))
    tree_comparisons = Dict(metric => comparison(fine, values[metric], ids, tree_k) for metric in METRICS)
    cell_comparisons = Dict(metric => comparison(cell_fine, cell_values[metric], cell_ids, cell_k) for metric in METRICS)
    temporal = Dict(
        "tree" => comparison(values[first(METRICS)], values["seasonal_mean_wbgt_c"], ids, tree_k),
        "cell" => comparison(cell_values[first(METRICS)], cell_values["seasonal_mean_wbgt_c"], cell_ids, cell_k))
    top_cells = Dict{String, Any}()
    for metric in METRICS
        selected = Set(tree_comparisons[metric]["right"]["exact_ids"])
        top_cells[metric] = length(unique(cells[i] for i in eachindex(ids) if ids[i] in selected))
    end
    districts = [get(trees[id], "district", nothing) === nothing ? "Unknown" : string(trees[id]["district"]) for id in ids]
    leave_out = Dict{String, Any}()
    for district in sort(unique(districts))
        keep = findall(!=(district), districts)
        isempty(keep) && continue
        # Re-aggregate retained points: a cell may straddle district labels.
        retained_cells = sort(unique(cells[keep]))
        gs = [[i for i in keep if cells[i] == cell] for cell in retained_cells]
        a = [mean(fine[g]) for g in gs]
        b = [values["seasonal_mean_wbgt_c"][first(g)] for g in gs]
        leave_out[district] = Dict("trees" => length(keep), "cells" => length(gs),
            "comparison" => comparison(a, b, retained_cells, max(1, ceil(Int, length(gs) / 4))))
    end
    publication_value(Dict("schema_version" => 2, "inputs" => collect(INPUTS), "source_contract" => metadata, "trees" => length(ids), "cells" => length(cell_ids),
        "tree_top_k" => tree_k, "cell_top_k" => cell_k,
        "singleton_cells" => count(g -> length(g) == 1, groups),
        "cell_records" => [Dict("id" => cell_ids[i], "trees" => length(g), "tree_ids" => ids[g],
            "sampled_fine_mean" => cell_fine[i], "sampled_fine_min" => minimum(fine[g]),
            "sampled_fine_max" => maximum(fine[g]),
            "wbgt" => Dict(metric => cell_values[metric][i] for metric in METRICS)) for (i,g) in enumerate(groups)],
        "variance_tree_weighted" => variance_partition(fine, cells),
        "variance_equal_cell" => variance_partition(fine, cells; equal_cells=true),
        "fine_vs_archive_tree" => tree_comparisons, "fine_vs_archive_cell" => cell_comparisons,
        "reference_vs_seasonal" => temporal, "tree_top_distinct_cells" => top_cells,
        "leave_one_district_out" => leave_out,
        "robustness" => Dict(
            "selection_percentages" => collect(SELECTION_PERCENTAGES),
            "threshold_tree" => threshold_sweep(fine, values[first(METRICS)], values["seasonal_mean_wbgt_c"], ids),
            "threshold_cell" => threshold_sweep(cell_fine, cell_values[first(METRICS)], cell_values["seasonal_mean_wbgt_c"], cell_ids),
            "rounding_cell" => rounding_sweep(cell_fine, cell_values[first(METRICS)], cell_values["seasonal_mean_wbgt_c"], cell_ids),
            "minimum_cell_coverage" => coverage_sweep(fine, cells, values[first(METRICS)], values["seasonal_mean_wbgt_c"]))))
end

fmt(x) = x === nothing ? "undefined (constant values)" : string(round(x; digits=3))

function robustness_markdown(report)
    robust = report["robustness"]
    sizes(c) = "$(length(c["left"]["inclusive_ids"]))/$(length(c["right"]["inclusive_ids"]))"
    lines = ["## Offline robustness stress tests", "",
        "These fixed sensitivity scenarios are not confidence intervals, measurement-error bounds, or a search for the best-looking cutoff. No scenario changes the operational score.", "",
        "### Selection fractions", "",
        "Use the same nominal fraction within each analysis unit: k = ceiling(n × percentage / 100). Ties can expand the selected sets beyond k; L/R sizes below count the two inclusive sets. Equal fractions do not make trees and cells equivalent populations. Larger selections often overlap more mechanically, which does not establish validity.", "",
        "| Unit | Nominal % | k / n | Temporal L/R sizes | Temporal Jaccard | Fine/seasonal L/R sizes | Fine/seasonal Jaccard |",
        "|---|---:|---:|---:|---:|---:|---:|"]
    for unit in ("tree", "cell"), s in robust["threshold_$(unit)"]
        temporal, cross = s["reference_vs_seasonal"], s["fine_vs_seasonal"]
        push!(lines, "| $(unit) | $(s["percentage"]) | $(s["k"]) / $(s["units"]) | $(sizes(temporal)) | $(fmt(temporal["inclusive_jaccard"])) | $(sizes(cross)) | $(fmt(cross["inclusive_jaccard"])) |")
    end
    append!(lines, ["", "![Threshold robustness profiles](heat-support-robustness.svg)", "",
        "Two panels keep tree and cell populations separate. X = nominal selected percentage; Y = tie-inclusive Jaccard. Solid teal compares reference-day with seasonal-mean archive WBGT; dashed orange compares the fine indicator with seasonal-mean archive WBGT. Markers are the tested thresholds, not interpolated evidence. Tooltips include k, n and tie-expanded sizes. All observations are present; no confidence bands are implied.", "",
        "### Archive-temperature coarsening (cells only)", "",
        "Round both reference-day and seasonal-mean WBGT from the committed two decimals to one decimal or whole degrees Celsius (nearest, ties-to-even). Keep the fine indicator unchanged. One value per cell preserves shared observations. This tests deliberate coarsening only: it cannot recover unrounded data or bound hidden rounding error. A high inclusive Jaccard can result from tie expansion rather than robust discrimination. Spearman is undefined for a constant input.", "",
        "| Decimals | Distinct reference/seasonal | Temporal L/R sizes | Temporal Jaccard | Temporal Spearman | Fine/seasonal L/R sizes | Fine/seasonal Jaccard | Fine/seasonal Spearman |",
        "|---|---:|---:|---:|---:|---:|---:|---:|"])
    for s in robust["rounding_cell"]
        temporal, cross = s["reference_vs_seasonal"], s["fine_vs_seasonal"]
        push!(lines, "| $(s["decimal_places"]) | $(s["reference_distinct_values"])/$(s["seasonal_distinct_values"]) | $(sizes(temporal)) | $(fmt(temporal["inclusive_jaccard"])) | $(fmt(temporal["spearman"])) | $(sizes(cross)) | $(fmt(cross["inclusive_jaccard"])) | $(fmt(cross["spearman"])) |")
    end
    append!(lines, ["", "### Minimum sampled trees per cell", "",
        "Recompute variance partitions and rank comparisons on cells with at least 1, 2 or 3 sampled trees, weighting retained cells equally. The threshold selects a different population; it does not correct singleton variance or recover missing locations. Rank comparisons select the top quarter of retained cells (ceiling). Empty retained populations are explicitly unavailable. Even multiple-tree cells sample trees, not all surfaces.", "",
        "| Minimum trees/cell | Retained trees/cells | Excluded trees/cells | k | Within variance fraction | Fine/seasonal Spearman | Temporal Spearman |",
        "|---|---:|---:|---:|---:|---:|---:|"])
    for s in robust["minimum_cell_coverage"]
        if s["cells"] == 0
            push!(lines, "| $(s["minimum_trees"]) | 0/0 | $(s["excluded_trees"])/$(s["excluded_cells"]) | unavailable | unavailable | unavailable | unavailable |")
        else
            push!(lines, "| $(s["minimum_trees"]) | $(s["trees"])/$(s["cells"]) | $(s["excluded_trees"])/$(s["excluded_cells"]) | $(s["k"]) | $(fmt(s["variance_equal_cell"]["within_fraction"])) | $(fmt(s["fine_vs_seasonal"]["spearman"])) | $(fmt(s["reference_vs_seasonal"]["spearman"])) |")
        end
    end
    lines
end

function markdown(report)
    lines = ["# Offline heat-support diagnostics", "",
        "Generated from committed summaries only. Operational ranking and stakeholder decisions are unchanged.", "",
        "## Findings", "",
        "- Same-archive reference-day versus seasonal-mean ranks have cell-level Spearman $(fmt(report["reference_vs_seasonal"]["cell"]["spearman"])) and exact top-cell overlap $(report["reference_vs_seasonal"]["cell"]["exact_overlap"])/$(report["cell_top_k"]). This is agreement among pooled summaries, not held-out summer validation.",
        "- Only $(fmt(report["variance_equal_cell"]["within_fraction"] === nothing ? nothing : 100 * report["variance_equal_cell"]["within_fraction"]))% of the fine indicator's equal-cell-weighted variance lies within sampled cells. The observed point sample therefore does not support within-cell variance dominating total variation. It does not measure all within-cell surfaces or identify the cause of cross-product disagreement.",
        "- Fine indicator versus seasonal archive ranks have cell-level Spearman $(fmt(report["fine_vs_archive_cell"]["seasonal_mean_wbgt_c"]["spearman"])) after aggregation: product disagreement remains. The district exclusions below show how sample-dependent that association is.", "",
        "## Method and interpretation", "",
        "$(report["trees"]) convenience-sampled trees occupy $(report["cells"]) archive cells. Each cell receives equal weight in cell-level comparisons. The fine-layer cell statistic is the mean **at sampled tree points**, not an area mean or a representative cell estimate.", "",
        "The detailed Brussels Environment layer is a source-normalized 0–100 indicator for a 24-hour mean on 24 August 2016, with 2 m radiation/shade modeling. VITO's archive is 100 m daily-maximum WBGT in °C. Same model family does not mean matching spatial support. Cross-product differences cannot isolate time, shade, normalization or model error.", "",
        "Sources: [Brussels Environment detailed-layer methodology](https://environnement.brussels/citoyen/documentation-et-outils/etat-des-lieux-de-lenvironnement/ilot-de-chaleur); [VITO archive](https://provide.marvin.vito.be/ftp/compressed_daily/). VITO daily-archive reuse terms remain unresolved: the archive page states none, the NetCDF files carry no licence attribute, and neither the CC BY 4.0 Souverijns et al. (2026) decadal set nor the CC-BY-4.0 Copernicus CDS record sis-urban-climate-cities (hourly temperature, humidity and wind for 100 cities, no WBGT, deprecated on the CDS 2024-05-10) licenses this daily WBGT archive. See docs/heat-season-method.md, section 'Licence and lineage'. This is internal exploratory analysis, not a redistribution clearance.", "",
        "Published numeric diagnostics are rounded to 12 decimal places for cross-runtime reproducibility; selection uses the unrounded calculations. Ranks use average ranks for exact ties in the committed rounded values. Exact top-k uses ID tie-breaking; inclusive top-k retains every cutoff tie. Jaccard = inclusive intersection / inclusive union. Tree k=$(report["tree_top_k"]); cell k=$(report["cell_top_k"]) (ceiling of one quarter of cells). These are different selection policies, not a controlled estimate of aggregation's effect.", "",
        "## Fine indicator versus archive", "",
        "| Archive metric | Tree Spearman | Cell Spearman | Cell inclusive Jaccard | Cells in exact tree top ten |", "|---|---:|---:|---:|---:|"]
    for metric in METRICS
        t, c = report["fine_vs_archive_tree"][metric], report["fine_vs_archive_cell"][metric]
        push!(lines, "| $(metric) | $(fmt(t["spearman"])) | $(fmt(c["spearman"])) | $(fmt(c["inclusive_jaccard"])) | $(report["tree_top_distinct_cells"][metric]) |")
    end
    append!(lines, ["", "## Same-series temporal comparison", "",
        "| Unit | Exact overlap | Tie-inclusive set sizes | Inclusive overlap | Jaccard | Spearman |", "|---|---:|---:|---:|---:|---:|"])
    for unit in ("tree", "cell")
        c = report["reference_vs_seasonal"][unit]
        push!(lines, "| $(unit) | $(c["exact_overlap"])/$(c["left"]["k"]) | $(length(c["left"]["inclusive_ids"])), $(length(c["right"]["inclusive_ids"])) | $(c["inclusive_overlap"]) | $(fmt(c["inclusive_jaccard"])) | $(fmt(c["spearman"])) |")
    end
    append!(lines, ["", "## Within-cell variation", "",
        "Population variance is partitioned into within-cell and between-cell components using the sampled indicator values, in indicator-squared units. It is not a causal effect or a random-effects estimate. $(report["singleton_cells"]) cells contain only one sampled tree and contribute zero observed within-cell variance by construction; this does not establish spatial uniformity.", "",
        "| Weighting | Within | Between | Within fraction |", "|---|---:|---:|---:|"])
    for name in ("variance_tree_weighted", "variance_equal_cell")
        v = report[name]
        push!(lines, "| $(name) | $(fmt(v["within"])) | $(fmt(v["between"])) | $(fmt(v["within_fraction"])) |")
    end
    append!(lines, ["", "## Leave-one-district-out sensitivity", "",
        "Recompute sampled cell means after excluding each district. This checks dependence on sample composition; it is not a confidence interval or out-of-sample validation.", "",
        "| Omitted district | Retained trees | Cells | Fine versus seasonal-mean Spearman |", "|---|---:|---:|---:|"])
    for district in sort(collect(keys(report["leave_one_district_out"])))
        row = report["leave_one_district_out"][district]
        safe = replace(district, "|" => "\\|", "\n" => " ")
        push!(lines, "| $(safe) | $(row["trees"]) | $(row["cells"]) | $(fmt(row["comparison"]["spearman"])) |")
    end
    append!(lines, [""; robustness_markdown(report)])
    append!(lines, ["", "## Rank visualization", "", "![Equal-cell rank comparison](heat-support-ranks.svg)", "",
        "Each circle is one archive cell with equal visual weight. X = descending rank of mean fine indicator at sampled trees; Y = descending rank of seasonal-mean daily-maximum WBGT. Rank 1 is hottest. The diagonal denotes identical ranks. Exact ties share midranks and may overlap. Tooltips give cell ID and sample multiplicity. No uncertainty bands: these are deterministic summaries, not estimates with validated error models. Input gaps cause generation to fail rather than disappear silently.", "",
        "## What remains unresolved", "",
        "Min–max scaling is monotone and cannot change pure-heat ranks; this analysis does not endorse normalization or mobility weights in a composite score. Cell duplication, rounding, tree-coordinate error and selective sampling limit inference. Point-level within-cell variation does not identify tree cooling.", "",
        "No daily series, raster neighborhoods or measured thermal observations are committed here. Therefore this analysis cannot bootstrap summers, perturb raster sampling coordinates, compare daily mean versus maximum, or validate physical heat. The archive's daily-mean files are a verified follow-up source, not analyzed evidence. Reuse permission and source/model compatibility must be resolved first.", ""])
    join(lines, "\n")
end

function svg(report)
    rows = report["cell_records"]
    a = midranks([r["sampled_fine_mean"] for r in rows])
    b = midranks([r["wbgt"]["seasonal_mean_wbgt_c"] for r in rows])
    n = length(rows)
    pos(v) = 60 + 420 * (v - 1) / max(1, n - 1)
    lines = ["<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 560 560\" role=\"img\" aria-labelledby=\"title desc\">",
        "<title id=\"title\">Equal-cell heat ranks</title><desc id=\"desc\">Fine-layer sampled tree mean versus seasonal-mean archive WBGT; rank one hottest, ties use average ranks. Descriptive, no uncertainty estimate.</desc>",
        "<rect width=\"560\" height=\"560\" fill=\"white\"/>",
        "<path d=\"M60 60V480H480 M60 60L480 480\" fill=\"none\" stroke=\"#999\"/>",
        "<g font-family=\"sans-serif\" font-size=\"13\" fill=\"#222\"><text x=\"65\" y=\"35\">Rank 1 = hottest; each circle = one cell</text><text x=\"130\" y=\"530\">Fine indicator sampled-mean rank →</text><text transform=\"translate(20 440) rotate(-90)\">Seasonal-mean WBGT rank →</text><text x=\"55\" y=\"500\">1</text><text x=\"470\" y=\"500\">$(n)</text><text x=\"40\" y=\"65\">1</text><text x=\"35\" y=\"480\">$(n)</text></g>"]
    for i in eachindex(rows)
        r = rows[i]
        push!(lines, "<circle cx=\"$(pos(a[i]))\" cy=\"$(pos(b[i]))\" r=\"5\" fill=\"#176b87\" fill-opacity=\"0.65\"><title>Cell $(r["id"]); $(r["trees"]) trees; ranks $(a[i]), $(b[i])</title></circle>")
    end
    join([lines; "</svg>"], "\n")
end

function robustness_svg(report)
    lines = ["<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 840 390\" role=\"img\" aria-labelledby=\"title desc\">",
        "<title id=\"title\">Selection-threshold sensitivity</title><desc id=\"desc\">Separate tree and cell panels plot inclusive Jaccard versus nominal selection percentage. Teal solid: reference versus seasonal archive. Orange dashed: fine indicator versus seasonal archive. Deterministic stress tests, no confidence bands.</desc>",
        "<rect width=\"840\" height=\"390\" fill=\"white\"/>",
        "<g font-family=\"sans-serif\" font-size=\"13\" fill=\"#222\"><text x=\"55\" y=\"24\">Tie-inclusive Jaccard (0–1); larger selections can inflate overlap</text>",
        "<text x=\"55\" y=\"365\" fill=\"#176b87\">Solid teal: reference / seasonal</text><text x=\"410\" y=\"365\" fill=\"#a64b00\">Dashed orange: fine / seasonal</text></g>"]
    for (panel, unit) in enumerate(("tree", "cell"))
        origin = 65 + (panel - 1) * 410
        x(p) = origin + 300 * (p - 10) / 40
        y(v) = 290 - 220 * v
        push!(lines, "<path d=\"M$(origin) 70V290H$(origin + 300)\" fill=\"none\" stroke=\"#888\"/>")
        push!(lines, "<g font-family=\"sans-serif\" font-size=\"13\" fill=\"#222\"><text x=\"$(origin)\" y=\"52\">$(unit) units</text><text x=\"$(origin - 22)\" y=\"75\">1</text><text x=\"$(origin - 22)\" y=\"295\">0</text><text x=\"$(origin + 30)\" y=\"338\">Nominal selected percentage</text></g>")
        scenarios = report["robustness"]["threshold_$(unit)"]
        for p in SELECTION_PERCENTAGES
            push!(lines, "<text x=\"$(x(p))\" y=\"310\" text-anchor=\"middle\" font-family=\"sans-serif\" font-size=\"12\">$(p)</text>")
        end
        for (key, color, dash) in (("reference_vs_seasonal", "#176b87", ""), ("fine_vs_seasonal", "#a64b00", "6 4"))
            points = join(["$(x(s["percentage"])),$(y(s[key]["inclusive_jaccard"]))" for s in scenarios], " ")
            push!(lines, "<polyline points=\"$(points)\" fill=\"none\" stroke=\"$(color)\" stroke-width=\"2\" stroke-dasharray=\"$(dash)\"/>")
            for s in scenarios
                c = s[key]
                tip = "$(unit) $(key): $(s["percentage"])%; k=$(s["k"])/$(s["units"]); inclusive sizes $(length(c["left"]["inclusive_ids"]))/$(length(c["right"]["inclusive_ids"])); Jaccard $(fmt(c["inclusive_jaccard"]))"
                push!(lines, "<circle cx=\"$(x(s["percentage"]))\" cy=\"$(y(c["inclusive_jaccard"]))\" r=\"4\" fill=\"$(color)\"><title>$(tip)</title></circle>")
            end
        end
    end
    join([lines; "</svg>"], "\n")
end

function generate(data_dir, output_dir)
    payloads = [JSON3.read(read(joinpath(data_dir, f), String), Dict{String,Any}) for f in INPUTS]
    report = analyze(payloads...)
    mkpath(output_dir)
    IOUtils.atomic_write_json(joinpath(output_dir, "heat-support-diagnostics.json"), report)
    write(joinpath(output_dir, "heat-support-diagnostics.md"), markdown(report))
    write(joinpath(output_dir, "heat-support-ranks.svg"), svg(report))
    write(joinpath(output_dir, "heat-support-robustness.svg"), robustness_svg(report))
    report
end

end
