module Analysis

using Statistics
using ..TreesSurfaces

include(joinpath(@__DIR__, "HeatSeason.jl"))
using .HeatSeason
include(joinpath(@__DIR__, "Wbgt.jl"))
using .Wbgt

export signal_summary, generate_signal_artifacts

const csv_escape = TreesSurfaces.csv_escape

function signal_summary()
    state = TreesSurfaces.build_state()
    scenarios = Dict(
        "heat_only" => (100.0, 0.0),
        "balanced" => (60.0, 40.0),
        "proximity_only" => (0.0, 100.0),
    )
    screens = Dict(name => TreesSurfaces.ranked_sites(state["sites"], weights[1], weights[2]) for (name, weights) in scenarios)
    balanced_ids = Set(site["id"] for site in screens["balanced"]["sites"][1:10])
    scenario_summary = Dict{String, Any}()
    for (name, screen) in screens
        top = screen["sites"][1:10]
        scenario_summary[name] = Dict{String, Any}(
            "heat_weight" => screen["heatWeight"],
            "proximity_weight" => screen["proximityWeight"],
            "top_10_ids" => [site["id"] for site in top],
            "top_signal" => first(top)["signal"],
            "top_10_overlap_with_balanced" => length(intersect(Set(site["id"] for site in top), balanced_ids)),
        )
    end
    return Dict{String, Any}(
        "record_count" => length(state["sites"]),
        "scenarios" => scenario_summary,
        "data_completeness" => state["quality"],
    )
end

function analysis_rows(data_dir=TreesSurfaces.DATA_DIR)
    managed_payload = TreesSurfaces.read_json_path(joinpath(data_dir, "brussels-trees-sample.json"))
    heat_payload = TreesSurfaces.read_json_path(joinpath(data_dir, "brussels-tree-heat-sample.json"))
    joined_payload = TreesSurfaces.read_json_path(joinpath(data_dir, "brussels-tree-bike-nearest.json"))
    heat_by_id = Dict(TreesSurfaces.text(get(row, "id", "")) => TreesSurfaces.number(get(row, "heat_pixel", 0)) for row in TreesSurfaces.records(heat_payload))
    points = Any[]
    for row in TreesSurfaces.records(joined_payload)
        id = TreesSurfaces.text(get(row, "id", ""))
        haskey(heat_by_id, id) || continue
        push!(points, Dict{String, Any}(
            "id" => id,
            "street" => get(row, "street", nothing),
            "district" => get(row, "district", nothing) === nothing ? "Unknown" : get(row, "district", "Unknown"),
            "heatPixel" => heat_by_id[id],
            "distanceM" => TreesSurfaces.number(get(row, "nearest_counter_distance_m", 0)),
            "counter" => TreesSurfaces.text(get(row, "nearest_counter", "")),
        ))
    end
    scored = TreesSurfaces.score_heat_proximity!(points)
    return points, managed_payload, heat_payload, scored.min_heat, scored.max_heat, scored.min_distance, scored.max_distance
end

function artifact_row(site)
    Dict{String, Any}(
        "id" => site["id"],
        "street" => site["street"],
        "district" => site["district"],
        "heat_pixel" => site["heatPixel"],
        "nearest_counter" => site["counter"],
        "distance_m" => site["distanceM"],
        "heat_score" => site["heatScore"],
        "proximity_score" => site["proximityScore"],
        "signal" => round(site["signal"]; digits = 3),
    )
end

function markdown_value(value; fallback="")
    string_value = value === nothing ? fallback : string(value)
    replace(string_value, "\\" => "\\\\", "|" => "\\|", "\r" => " ", "\n" => " ")
end

function format_thousands(value)
    digits = string(round(Int, value))
    sign = startswith(digits, "-") ? "-" : ""
    sign == "-" && (digits = digits[2:end])
    groups = String[]
    while length(digits) > 3
        push!(groups, digits[(end - 2):end])
        digits = digits[1:(end - 3)]
    end
    push!(groups, digits)
    return sign * join(reverse(groups), ",")
end

function write_analysis_report(report, context, output_dir)
    balanced = report["balanced_screening"]
    quality = report["data_completeness"]
    weights = report["weight_sensitivity"]
    heat_season = context["heat_season"]
    wbgt = context["heat_wbgt"]
    wbgt_lines = wbgt["available"] ? [
        "- VITO publishes daily maximum WBGT at 100 m in EPSG:3035 for $(wbgt["window_phrase"]), sampled as `brussels-heat-wbgt-sample.json` to the same $(report["record_count"]) trees across $(wbgt["distinct_cells"]) cells. It is the same UrbClim model family and spatial resolution as the Brussels Environment raster, but its °C daily maxima are not interchangeable with the raster's 0–100 indicator for a 24-hour mean scenario. The archive page requests citation to De Ridder et al. (2015) and Souverijns et al. (2026).",
        "- The 24 August 2016 raster date falls at the $(wbgt["reference_percentile_min"])–$(wbgt["reference_percentile_max"])th percentile of the pooled June–August daily WBGT distribution; its sampled point values are $(wbgt["reference_min"])–$(wbgt["reference_max"]) °C. The seasonal-mean WBGT ranges from $(wbgt["seasonal_mean_min"]) to $(wbgt["seasonal_mean_max"]) °C across the sample.",
        "- In the VITO daily-maximum series, the reference-day and pooled seasonal-mean heat-only top tens share $(wbgt["seasonal_mean_vs_reference_day"])/10. Against the current balanced screen, the VITO reference-day, seasonal-mean and hot-day-count top tens overlap at $(wbgt["reference_day_vs_balanced"])/10, $(wbgt["seasonal_mean_vs_balanced"])/10 and $(wbgt["hot_days_vs_balanced"])/10. The latter comparisons also change WBGT output semantics and scoring; they do not isolate heat-period effects. No alternative is adopted pending stakeholder choice.",
        "- Licence review for the VITO $(wbgt["window_phrase"]) daily archive is $(wbgt["licence_status"]): the source page requests both citations but states no reuse terms, and the annual NetCDF files themselves carry no licence attribute. Two related records do not transfer theirs — the Souverijns et al. (2026) decadal indicator set is CC BY 4.0, and the CC-BY-4.0 Copernicus CDS record `sis-urban-climate-cities` covers hourly temperature, humidity and wind without WBGT. Confirm terms with VITO before external redistribution or relying on derived values beyond exploratory analysis; see `docs/heat-season-method.md`, *Licence and lineage*.",

    ] : [
        "- No multi-date 100 m WBGT snapshot is present; VITO publishes daily UrbClim WBGT for Brussels for 2008–2017. Use `julia --project=. bin/generate_wbgt_context.jl --download` to build it from the upstream archive.",
    ]
    hottest_years = heat_season["available"] ? heat_season["hottest_season_years"] : String[]
    hottest_season_line = length(hottest_years) == 1 ?
        "- The 2016 seasonal mean apparent maximum was about $(heat_season["reference_season_mean"]) °C across the sample cells; $(first(hottest_years)) was the warmest season across all sampled cells, at about $(heat_season["hottest_season_mean"]) °C on average." :
        "- The 2016 seasonal mean apparent maximum was about $(heat_season["reference_season_mean"]) °C across the sample cells; cell-specific warmest seasons differ ($(join(hottest_years, ", "))), and their hottest-season means average $(heat_season["hottest_season_mean"]) °C."
    season_lines = heat_season["available"] ? [
        "- A multi-year seasonal context is committed as `brussels-heat-season-sample.json`: pooled June–August seasons for $(heat_season["window_phrase"]) on the ERA5 reanalysis grid, where $(heat_season["cells"]) cells cover the committed sample, retrieved from the Open-Meteo archive API with Copernicus attribution.",
        "- The committed WBGT date, $(heat_season["reference_date"]), was an extreme day inside its own summer: apparent-temperature maxima were $(heat_season["reference_apparent_min"])–$(heat_season["reference_apparent_max"]) °C across those cells, ranking $(heat_season["reference_rank_min"])th–$(heat_season["reference_rank_max"])th warmest of that season's 92 days ($(heat_season["reference_percentile_min"])–$(heat_season["reference_percentile_max"])% of the seasonal days were below it).",
        hottest_season_line,
        "- Recurrence context: about $(heat_season["hot_days_per_season_min"])–$(heat_season["hot_days_per_season_max"]) days per season reach an apparent maximum of $(Int(HeatSeason.HOT_DAY_APPARENT_TMAX_C)) °C or more in these cells, so a one-day snapshot says nothing about how often the condition repeats.",
        "- Boundary: the ERA5 grid step is about 28 km north-south and 18 km east-west at Brussels' latitude; the $(heat_season["cells"]) cells spanning the sample differ by only $(heat_season["seasonal_mean_spread"]) °C in seasonal mean apparent maximum. This source documents temporal representativeness; it cannot reproduce or replace the intra-urban pattern of the 10,000 × 9,000 WBGT raster that drives the ranking.",
    ] : [
        "- No seasonal heat context snapshot is present in this data directory; the committed snapshot is `brussels-heat-season-sample.json`.",
    ]
    heat_missing = length(quality["heat_nodata_ids"])
    heat_missing_line = heat_missing == 0 ?
        "- Missing data: all $(report["record_count"]) joined points have non-NoData WBGT pixels, so there is no heat missingness to impute in this snapshot." :
        "- Missing data: $(heat_missing) of $(report["record_count"]) joined points have NoData WBGT pixels; they are excluded from the heat component and named in the completeness section."
    history_line = "- Counter history context: $(format_thousands(context["history_observations"])) fifteen-minute observations ($(context["history_counters"]) counters × 672) from $(context["history_period_phrase"]); $(context["history_statistics"])"
    lines = [
        "# Tree signal descriptive analysis",
        "",
        "This report answers the working screening question using the committed $(report["record_count"])-record feasibility sample.",
        "",
        "> Which observed tree areas combine relatively high heat-stress values with proximity to bicycle counters, and therefore merit more detailed field or mobility analysis?",
        "",
        "## Heat data and normalization",
        "",
        "- The ranking heat input is the regional urban-heat-island model published by Brussels Environment: mean 24-hour Wet Bulb Globe Temperature for one representative hot day (2016-08-24). The public regional WMS exposes this single scenario layer.",
        "- The source raster stores a normalized 0–100 WBGT indicator, not degrees Celsius. The prototype then min-max normalizes those source values again within the committed $(report["record_count"])-record sample to calculate heat scores; rankings therefore shift with the weights and with a different sample.",
        "- The authoritative ISO metadata identifies the dataset as `$(report["heat_source_metadata_id"])`, published by Brussels Environment / Leefmilieu Brussel under $(report["heat_source_licence"]) with source attribution.",
        heat_missing_line,
        "- A separate multi-date 100 m WBGT context was evaluated; its data-derived comparisons and interpretive limits are summarized below. It remains context only and does not replace the raster as ranking input.",
        "",
        "## Seasonal heat context",
        "",
        season_lines...,
        "",
        "## Multi-date 100 m WBGT context",
        "",
        wbgt_lines...,
        "",
        "## Traceability",
        "",
        "Every displayed point can be traced to its source record and join method:",
        "- Source record: the managed-tree register entry, reachable by id, e.g. `https://bruxellesdata.opendatasoft.com/api/explore/v2.1/catalog/datasets/arbres-bomen-vbx-be-bm/records?where=id%3D%27$(context["example_id"])%27`.",
        "- Heat join: WBGT raster pixel value extracted after the EPSG seven-parameter WGS84-to-Belgian-1972 datum transform and Belgian Lambert 72 projection (see `src/Heat.jl` and `src/Projection.jl`, exposed as `bin/generate_heat_join.jl`).",
        "- Mobility join: great-circle distance to the nearest bicycle counter (see the committed `brussels-tree-bike-nearest.json`); measured-flow context for the nearest counter is in `brussels-tree-counter-flow.json`.",
        "- Ranking: signal = heat_score × weight + proximity_score × weight, min-max scores, weights exposed in the interface.",
        "",
        "## Sample summary",
        "",
        "- Records analyzed: $(report["record_count"]) of $(format_thousands(context["managed_source_total"])) managed-tree records reported by the source ($(context["share_of_register"])% of the reported register)",
        "- Sampling note: the committed records are a feasibility snapshot, not a probability sample or city-wide estimate",
        "- Source-normalized WBGT indicator pixel (0–100, not °C): min $(context["heat_min"]), median $(context["heat_median"]), max $(context["heat_max"])",
        "- Counter distance: min $(context["distance_min"]) m, median $(context["distance_median"]) m, max $(context["distance_max"]) m",
        history_line,
        "- High-heat/high-proximity quadrant: $(context["quadrant_count"]) $(context["quadrant_label"]) at or above the sample's third quartile on both normalized components",
        "",
        "## Data completeness",
        "",
        "Completeness is reported against the $(quality["managed_records"]) committed managed-tree records. Missing measured-flow context does not remove a point from the heat/proximity analysis.",
        "",
        "| Stage | Expected | Available | Missing |",
        "|---|---:|---:|---:|",
        "| Valid coordinates | $(quality["managed_records"]) | $(quality["valid_coordinate_records"]) | $(length(quality["missing_coordinate_ids"])) |",
        "| Heat join | $(quality["managed_records"]) | $(quality["heat_joined_records"]) | $(length(quality["heat_unmatched_ids"])) |",
        "| Non-NoData heat pixels | $(quality["managed_records"]) | $(context["heat_usable_records"]) | $(heat_missing) |",
        "| Nearest-counter join | $(quality["managed_records"]) | $(quality["mobility_joined_records"]) | $(length(quality["mobility_unmatched_ids"])) |",
        "| Analyzed records | $(quality["managed_records"]) | $(quality["analyzed_records"]) | $(length(quality["analysis_unmatched_ids"])) |",
        "| Counter-flow context join | $(quality["managed_records"]) | $(quality["flow_context_joined_records"]) | $(length(quality["flow_context_unmatched_ids"])) |",
        "| Measured-flow history available | $(quality["managed_records"]) | $(quality["measured_flow_context_records"]) | $(length(quality["measured_flow_unmatched_ids"])) |",
        "",
        context["flow_gap_sentence"],
        "",
        "## District context",
        "",
        "District counts describe this $(report["record_count"])-record sample only; they are not district prevalence estimates.",
        "",
        "| District | Points | Mean WBGT indicator (0–100) | Median counter distance | High-high points |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in context["district_rows"]
        push!(lines, "| $(markdown_value(row["district"])) | $(row["points"]) | $(round(row["mean_heat"]; digits = 1)) | $(round(row["median_distance"]; digits = 1)) m | $(row["high_high"]) |")
    end
    push!(lines, "")
    push!(lines, "## Weight sensitivity")
    push!(lines, "")
    push!(lines, "| Scenario | Heat weight | Proximity weight | Top-ten overlap with 60/40 |")
    push!(lines, "|---|---:|---:|---:|")
    for (label, name) in (("Heat only", "heat_only"), ("Balanced", "balanced"), ("Proximity only", "proximity_only"))
        scenario = context["scenario_weights"][name]
        push!(lines, "| $(label) | $(round(Int, scenario["heat"] * 100))% | $(round(Int, scenario["proximity"] * 100))% | $(scenario["overlap"])/10 |")
    end
    push!(lines, "")
    push!(lines, "The balanced top ten shares $(weights["heat_only_top_10_overlap"])/10 points with heat-only but only $(weights["proximity_only_top_10_overlap"])/10 with proximity-only. The 60/40 screen is therefore strongly heat-led, and emphasizing proximity materially changes membership; it is not a stable priority ordering.")
    push!(lines, "")
    push!(lines, "## Balanced screen")
    push!(lines, "")
    push!(lines, "The balanced screen uses heat weight 0.6 and proximity weight 0.4. The table shows the ten highest exploratory signals.")
    push!(lines, "")
    push!(lines, "| Rank | ID | Street | WBGT indicator (0–100) | Counter distance | Signal |")
    push!(lines, "|---:|---|---|---:|---:|---:|")
    for (rank, row) in enumerate(balanced[1:10])
        push!(lines, "| $(rank) | $(markdown_value(row["id"])) | $(markdown_value(row["street"]; fallback = "Unnamed street")) | $(round(Int, row["heat_pixel"])) | $(round(row["distance_m"]; digits = 1)) m | $(round(row["signal"]; digits = 1)) |")
    end
    push!(lines, "")
    push!(lines, "## Mobility context")
    push!(lines, "")
    push!(lines, "A measured-flow context supplements nearest-counter distance: $(quality["measured_flow_context_records"]) of $(quality["managed_records"]) sampled trees have their nearest counter covered by the same $(context["history_period"]) week of 15-minute counts. The remaining $(length(quality["measured_flow_unmatched_ids"])) trees are nearest to counters without usable measured history.")
    push!(lines, "")
    push!(lines, "| Counter | Mean 15-min count | Day-mean range |")
    push!(lines, "|---|---:|---:|")
    for row in context["counter_rows"]
        push!(lines, "| $(markdown_value(row["counter"])) | $(round(row["mean"]; digits = 1)) | $(round(row["min_day_mean"]; digits = 1)) - $(round(row["max_day_mean"]; digits = 1)) |")
    end
    push!(lines, "")
    push!(lines, "Flow is measured at the nearest counter, not at the tree, and covers a single winter week; it is contextual mobility evidence, not a seasonal or street-level estimate. See `brussels-tree-counter-flow.json` for per-tree values.")
    push!(lines, "")
    push!(lines, "## Interpretation boundary")
    push!(lines, "")
    push!(lines, "- The WBGT layer represents one representative hot day in 2016; the seasonal context shows that day was an extreme day inside a comparatively mild summer, so exposure frequency is not represented.")
    push!(lines, "- Counter distance is a spatial context proxy, not bicycle flow, pedestrian use or street occupancy.")
    push!(lines, "- Min–max normalization is sample-relative; rankings change with the weights and sample.")
    push!(lines, "- These points are candidates for follow-up analysis, not planting recommendations or causal findings.")
    TreesSurfaces.atomic_write(joinpath(output_dir, "tree-signal-analysis.md"), join(lines, "\n") * "\n")
end

function generate_signal_artifacts(output_dir; data_dir=TreesSurfaces.DATA_DIR)
    mkpath(output_dir)
    points, managed_payload, heat_payload, min_heat, max_heat, min_distance, max_distance = analysis_rows(data_dir)
    scenarios = Dict(
        "heat_only" => (100.0, 0.0),
        "balanced" => (60.0, 40.0),
        "proximity_only" => (0.0, 100.0),
    )
    screens = Dict(name => TreesSurfaces.ranked_sites(points, weights[1], weights[2]) for (name, weights) in scenarios)
    balanced_ids = Set(site["id"] for site in screens["balanced"]["sites"][1:10])
    scenario_rows = Any[]
    for name in ("heat_only", "balanced", "proximity_only")
        screen = screens[name]
        rows = [artifact_row(site) for site in screen["sites"]]
        push!(scenario_rows, Dict{String, Any}(
            "name" => name,
            "weights" => Dict("heat" => screen["heatWeight"], "proximity" => screen["proximityWeight"]),
            "top_10_overlap_with_balanced" => length(intersect(Set(row["id"] for row in rows[1:10]), balanced_ids)),
            "top_records" => rows[1:10],
        ))
    end
    joined_ids = Set(point["id"] for point in points)
    managed_records = TreesSurfaces.records(managed_payload)
    managed_ids = [TreesSurfaces.text(get(row, "id", "")) for row in managed_records]
    heat_records = TreesSurfaces.records(heat_payload)
    heat_ids = Set(TreesSurfaces.text(get(row, "id", "")) for row in heat_records)
    valid_coordinate_ids = Set(
        TreesSurfaces.text(get(row, "id", ""))
        for row in managed_records
        if get(row, "latitude", nothing) isa Number && get(row, "longitude", nothing) isa Number && isfinite(Float64(get(row, "latitude", 0))) && isfinite(Float64(get(row, "longitude", 0)))
    )
    flow_payload = TreesSurfaces.read_json_path(joinpath(data_dir, "brussels-tree-counter-flow.json"))
    flow_records = TreesSurfaces.records(flow_payload)
    flow_record_ids = Set(TreesSurfaces.text(get(row, "id", "")) for row in flow_records)
    measured_flow_records = [row for row in flow_records if get(row, "has_measured_flow", false) == true]
    measured_flow_ids = Set(TreesSurfaces.text(get(row, "id", "")) for row in measured_flow_records)
    missing_coordinate_ids = [id for id in managed_ids if !(id in valid_coordinate_ids)]
    heat_unmatched_ids = [id for id in managed_ids if !(id in heat_ids)]
    mobility_unmatched_ids = [id for id in managed_ids if !(id in joined_ids)]
    analysis_unmatched_ids = [id for id in managed_ids if !(id in joined_ids)]
    flow_context_unmatched_ids = [id for id in managed_ids if !(id in flow_record_ids)]
    measured_flow_unmatched_ids = [id for id in managed_ids if !(id in measured_flow_ids)]
    measured_flow_unmatched_counters = sort(unique(TreesSurfaces.text(get(row, "nearest_counter", "")) for row in flow_records if TreesSurfaces.text(get(row, "id", "")) in measured_flow_unmatched_ids))
    data_completeness = Dict{String, Any}(
        "managed_records" => length(managed_ids),
        "valid_coordinate_records" => length(valid_coordinate_ids),
        "missing_coordinate_ids" => missing_coordinate_ids,
        "heat_joined_records" => length(heat_ids),
        "heat_unmatched_ids" => heat_unmatched_ids,
        "heat_nodata_ids" => [TreesSurfaces.text(get(row, "id", "")) for row in heat_records if TreesSurfaces.number(get(row, "heat_pixel", 0)) == 0],
        "mobility_joined_records" => length(joined_ids),
        "mobility_unmatched_ids" => mobility_unmatched_ids,
        "analyzed_records" => length(joined_ids),
        "analysis_unmatched_ids" => analysis_unmatched_ids,
        "flow_context_joined_records" => length(flow_record_ids),
        "flow_context_unmatched_ids" => flow_context_unmatched_ids,
        "measured_flow_context_records" => length(measured_flow_ids),
        "measured_flow_unmatched_ids" => measured_flow_unmatched_ids,
        "measured_flow_unmatched_counters" => measured_flow_unmatched_counters,
    )
    context = report_context(points, managed_payload, managed_ids, flow_payload, data_completeness, scenario_rows; data_dir = data_dir)
    report = Dict{String, Any}(
        "method" => "min-max normalization within the 100-record feasibility sample",
        "heat_value_semantics" => get(heat_payload, "value_semantics", ""),
        "heat_source_metadata_id" => get(heat_payload, "source_metadata_id", ""),
        "heat_source_licence" => get(heat_payload, "source_licence", ""),
        "record_count" => length(points),
        "heat_range" => [min_heat, max_heat],
        "distance_range_m" => [min_distance, max_distance],
        "balanced_screening" => [artifact_row(site) for site in screens["balanced"]["sites"]],
        "data_completeness" => data_completeness,
        "weight_sensitivity" => Dict(
            "balanced_top_10_ids" => [site["id"] for site in screens["balanced"]["sites"][1:10]],
            "heat_only_top_10_overlap" => scenario_rows[1]["top_10_overlap_with_balanced"],
            "proximity_only_top_10_overlap" => scenario_rows[3]["top_10_overlap_with_balanced"],
            "material_change" => scenario_rows[3]["top_10_overlap_with_balanced"] < 5,
            "interpretation" => "The 60/40 top ten is strongly heat-led; emphasizing proximity materially changes its membership.",
        ),
        "scenarios" => scenario_rows,
        "heat_season_context" => context["heat_season"],
        "heat_wbgt_context" => context["heat_wbgt"],
        "caveat" => "Rankings are exploratory and depend on sample-relative normalization; proximity is not a mobility measure.",
    )
    TreesSurfaces.atomic_write_json(joinpath(output_dir, "tree-signal-sensitivity.json"), report)
    fields = ["rank", "id", "street", "district", "heat_pixel", "nearest_counter", "distance_m", "heat_score", "proximity_score", "signal"]
    csv_lines = String[join(csv_escape.(fields), ",")]
    for (rank, site) in enumerate(screens["balanced"]["sites"])
        row = artifact_row(site)
        values = Any[rank, row["id"], row["street"], row["district"], row["heat_pixel"], row["nearest_counter"], row["distance_m"], row["heat_score"], row["proximity_score"], row["signal"]]
        push!(csv_lines, join(csv_escape.(values), ","))
    end
    TreesSurfaces.atomic_write(joinpath(output_dir, "tree-signal-balanced-screen.csv"), join(csv_lines, "\n") * "\n")
    write_analysis_report(report, context, output_dir)
    return report
end

function report_context(points, managed_payload, managed_ids, flow_payload, data_completeness, scenario_rows; data_dir = TreesSurfaces.DATA_DIR)
    heat_values = [point["heatPixel"] for point in points]
    distances = [point["distanceM"] for point in points]
    heat_scores = [point["heatScore"] for point in points]
    proximity_scores = [point["proximityScore"] for point in points]
    third_quartile_heat = Statistics.quantile(heat_scores, 0.75)
    third_quartile_proximity = Statistics.quantile(proximity_scores, 0.75)
    in_quadrant = point -> point["heatScore"] >= third_quartile_heat && point["proximityScore"] >= third_quartile_proximity
    quadrant_count = count(in_quadrant, points)

    # Per-district sample aggregates; sorted so the report is reproducible.
    point_by_id = Dict(point["id"] => point for point in points)
    district_ids = Dict{String, Vector{String}}()
    for point in points
        district = TreesSurfaces.text(get(point, "district", nothing))
        isempty(district) && (district = "Unknown")
        push!(get!(district_ids, district, String[]), point["id"])
    end
    district_rows = Any[]
    for (district, ids) in district_ids
        push!(district_rows, Dict{String, Any}(
            "district" => district,
            "points" => length(ids),
            "mean_heat" => Statistics.mean(point_by_id[id]["heatPixel"] for id in ids),
            "median_distance" => Statistics.median(point_by_id[id]["distanceM"] for id in ids),
            "high_high" => count(id -> in_quadrant(point_by_id[id]), ids),
        ))
    end
    sort!(district_rows, by = row -> (-row["points"], row["district"]))

    # Aggregate the committed counter-history series for the sample summary.
    counter_flow = Dict{String, Any}(string(counter) => values for (counter, values) in pairs(flow_payload["counter_flow"]))
    history_counts = Float64[]
    for counter in sort(collect(keys(counter_flow)))
        get(counter_flow[counter], "measured", true) == true || continue
        payload = TreesSurfaces.read_json_path(joinpath(data_dir, "brussels-bike-history-$(counter)-2024-01.json"))
        append!(history_counts, [TreesSurfaces.number(get(row, "count", 0)) for row in TreesSurfaces.records(payload)])
    end
    counter_rows = Any[]
    unmeasured_counters = String[]
    for (counter, values) in counter_flow
        # An outage window carries no measurement, so it must not enter report statistics or
        # sorting as if it were an observed mean of zero.
        if get(values, "measured", true) != true
            push!(unmeasured_counters, counter)
            continue
        end
        push!(counter_rows, Dict{String, Any}(
            "counter" => counter,
            "mean" => values["mean_all"],
            "min_day_mean" => values["min_day_mean"],
            "max_day_mean" => values["max_day_mean"],
        ))
    end
    sort!(counter_rows, by = row -> (-row["mean"], row["counter"]))
    sort!(unmeasured_counters)
    history_mean = isempty(history_counts) ? nothing : round(Statistics.mean(history_counts); digits = 1)
    history_max = isempty(history_counts) ? nothing : round(Int, maximum(history_counts))
    history_statistics = history_mean === nothing ? "no measured count statistics are available" : "mean count $(history_mean), maximum $(history_max)"

    flow_gap_ids = data_completeness["measured_flow_unmatched_ids"]
    flow_gap_counters = data_completeness["measured_flow_unmatched_counters"]
    flow_gap_sentence = isempty(flow_gap_ids) ?
        "Every sampled tree has measured-flow history for its nearest counter; all core heat and nearest-counter joins are complete." :
        "Measured-flow context is unavailable for IDs $(join(flow_gap_ids, ", ")); the affected nearest counter set is $(join(flow_gap_counters, ", ")), whose archived windows are absent or did not qualify as measured. All core heat and nearest-counter joins are complete."

    managed_source_total = Int(TreesSurfaces.number(get(managed_payload, "source", length(points))))
    return Dict{String, Any}(
        "managed_source_total" => managed_source_total,
        "share_of_register" => round(100 * length(points) / max(managed_source_total, 1); digits = 2),
        "heat_min" => round(Int, minimum(heat_values)),
        "heat_median" => round(Statistics.median(heat_values); digits = 1),
        "heat_max" => round(Int, maximum(heat_values)),
        "heat_usable_records" => data_completeness["heat_joined_records"] - length(data_completeness["heat_nodata_ids"]),
        "distance_min" => round(minimum(distances); digits = 1),
        "distance_median" => round(Statistics.median(distances); digits = 1),
        "distance_max" => round(maximum(distances); digits = 1),
        "history_observations" => length(history_counts),
        "history_counters" => length(counter_rows),
        "history_measured_counters" => length(counter_rows),
        "history_unmeasured_counters" => unmeasured_counters,
        "history_period" => TreesSurfaces.text(get(flow_payload, "period", "")),
        "history_period_phrase" => replace(TreesSurfaces.text(get(flow_payload, "period", "")), " - " => " to "),
        "history_mean" => history_mean,
        "history_max" => history_max,
        "history_statistics" => history_statistics,
        "quadrant_count" => quadrant_count,
        "quadrant_label" => quadrant_count == 1 ? "point" : "points",
        "example_id" => first(managed_ids),
        "flow_gap_sentence" => flow_gap_sentence,
        "district_rows" => district_rows,
        "counter_rows" => counter_rows,
        "scenario_weights" => Dict{String, Any}(
            row["name"] => Dict{String, Any}(
                "heat" => row["weights"]["heat"],
                "proximity" => row["weights"]["proximity"],
                "overlap" => row["top_10_overlap_with_balanced"],
            )
            for row in scenario_rows
        ),
        "heat_season" => HeatSeason.season_context(data_dir),
        "heat_wbgt" => Wbgt.context_summary(data_dir),
    )
end

end
