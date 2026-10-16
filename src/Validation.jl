module Validation

using Dates
using Statistics
using ..TreesSurfaces

include(joinpath(@__DIR__, "Wbgt.jl"))
using .Wbgt
include(joinpath(@__DIR__, "Projection.jl"))
include(joinpath(@__DIR__, "Spatial.jl"))
using .Spatial: haversine_distance_m, build_accident_context
include(joinpath(@__DIR__, "HeatSeason.jl"))
using .HeatSeason: era5_grid_point, era5_grid_key, DAILY_VARIABLES, GRID_STEP_DEGREES, REFERENCE_DATE, HOT_DAY_APPARENT_TMAX_C, TROPICAL_NIGHT_TMIN_C, WINDOW_START_YEAR, WINDOW_END_YEAR, SEASON_DAYS_PER_YEAR
include(joinpath(@__DIR__, "Flow.jl"))
using .Flow: build_counter_flow_artifact, HISTORY_START_DATE, HISTORY_END_DATE, HISTORY_PERIOD
include(joinpath(@__DIR__, "Review.jl"))
using .Review: validate_review, review_summary_fields, REVIEW_FIELDS

export validate_snapshots

finite_snapshot_number(value) = value isa Number && !(value isa Bool) && isfinite(Float64(value))

# Lambert coordinates arrive as numbers or numeric strings; unparseable values are
# treated as missing rather than raising a parse error, so the validator names the
# failing invariant instead of throwing.
function finite_lambert_coordinate(value)
    value isa Number && return isfinite(Float64(value))
    parsed = tryparse(Float64, TreesSurfaces.text(value))
    parsed !== nothing && isfinite(parsed)
end

function validate_snapshots(data_dir=TreesSurfaces.DATA_DIR)
    read_snapshot(filename) = TreesSurfaces.read_json_path(joinpath(data_dir, filename))
    managed = read_snapshot("brussels-trees-sample.json")
    heat = read_snapshot("brussels-tree-heat-sample.json")
    joined = read_snapshot("brussels-tree-bike-nearest.json")
    bikes_payload = read_snapshot("brussels-bike-counters.json")
    flow = read_snapshot("brussels-tree-counter-flow.json")
    inventory = read_snapshot("source-inventory.json")
    crosswalk = read_snapshot("managed-tree-id-crosswalk.json")
    accidents = read_snapshot("brussels-counter-accident-context.json")
    accident_source = read_snapshot("brussels-road-accidents-2017-2024.json")
    season = read_snapshot("brussels-heat-season-sample.json")

    managed_records = TreesSurfaces.records(managed)
    heat_records = TreesSurfaces.records(heat)
    joined_records = TreesSurfaces.records(joined)
    flow_records = TreesSurfaces.records(flow)
    length(managed_records) == 100 || error("expected 100 managed-tree records")
    length(heat_records) == 100 || error("expected 100 heat records")
    length(joined_records) == 100 || error("expected 100 nearest-counter records")
    length(flow_records) == 100 || error("expected 100 counter-flow records")
    managed_source_total = get(managed, "source", nothing)
    managed_source_total isa Integer && !(managed_source_total isa Bool) && managed_source_total >= length(managed_records) || error("managed-tree source total is invalid or smaller than the committed sample")
    completeness = get(managed, "completeness", nothing)
    completeness isa AbstractDict || error("managed-tree snapshot lacks its completeness block")
    for field in ("latitude", "longitude", "street", "district", "species")
        expected = count(row -> get(row, field, nothing) !== nothing, managed_records)
        get(completeness, field, nothing) == expected || error("managed-tree completeness for $(field) disagrees with its records")
    end

    managed_ids = Set(TreesSurfaces.text(get(row, "id", "")) for row in managed_records)
    heat_ids = Set(TreesSurfaces.text(get(row, "id", "")) for row in heat_records)
    joined_by_id = Dict(TreesSurfaces.text(get(row, "id", "")) => row for row in joined_records)
    joined_ids = Set(keys(joined_by_id))
    managed_ids == heat_ids || error("managed and heat IDs differ")
    managed_ids == joined_ids || error("managed and nearest-counter IDs differ")
    flow_ids = [TreesSurfaces.text(get(row, "id", "")) for row in flow_records]
    Set(flow_ids) == managed_ids || error("managed and counter-flow IDs differ")
    length(unique(flow_ids)) == length(flow_records) || error("counter-flow IDs are not unique")
    length(managed_ids) == 100 || error("managed IDs are not unique")
    managed_by_id = Dict(TreesSurfaces.text(get(row, "id", "")) => row for row in managed_records)
    for (kind, rows) in (("heat", heat_records), ("nearest-counter", joined_records))
        for row in rows
            id = TreesSurfaces.text(get(row, "id", ""))
            source_row = managed_by_id[id]
            for key in ("street", "latitude", "longitude")
                get(row, key, nothing) == get(source_row, key, nothing) || error("$(kind) record $(id) disagrees with managed tree on $(key)")
            end
        end
    end

    valid_coordinates = 0
    for row in managed_records
        latitude = get(row, "latitude", nothing)
        longitude = get(row, "longitude", nothing)
        if latitude isa Number && longitude isa Number && isfinite(Float64(latitude)) && isfinite(Float64(longitude))
            valid_coordinates += 1
        end
    end
    valid_coordinates == 100 || error("not all managed records have valid coordinates")
    all(begin
        value = get(row, "heat_pixel", nothing)
        value isa Integer && !(value isa Bool) && 1 <= value <= 100
    end for row in heat_records) || error("heat snapshot must contain non-NoData integer pixels in the declared 1–100 WBGT indicator range")
    for row in heat_records
        id = TreesSurfaces.text(get(row, "id", ""))
        tree = managed_by_id[id]
        expected_column, expected_row = Projection.raster_pixel(Float64(tree["latitude"]), Float64(tree["longitude"]), 10_000, 9_000)
        get(row, "heat_pixel_column", nothing) == expected_column || error("heat record $(id) column disagrees with its tree coordinates")
        get(row, "heat_pixel_row", nothing) == expected_row || error("heat record $(id) row disagrees with its tree coordinates")
    end
    all(begin
        distance = get(row, "nearest_counter_distance_m", nothing)
        finite_snapshot_number(distance) && TreesSurfaces.number(distance) >= 0
    end for row in joined_records) || error("nearest-counter distance is negative or invalid")
    bikes = TreesSurfaces.records(bikes_payload)
    !isempty(bikes) || error("bicycle-counter snapshot contains no counters")
    assert_counter_source = get(bikes_payload, "source", nothing)
    assert_counter_source isa Integer && !(assert_counter_source isa Bool) && assert_counter_source == length(bikes) || error("bicycle-counter snapshot source total disagrees with its records")
    bike_ids = [TreesSurfaces.text(get(bike, "id", "")) for bike in bikes]
    all(!isempty(id) for id in bike_ids) || error("bicycle-counter snapshot contains an empty ID")
    length(unique(bike_ids)) == length(bike_ids) || error("bicycle-counter snapshot IDs are not unique")
    for bike in bikes
        latitude = get(bike, "latitude", nothing)
        longitude = get(bike, "longitude", nothing)
        finite_snapshot_number(latitude) && 50.7 <= TreesSurfaces.number(latitude) <= 51.0 || error("bicycle counter $(get(bike, "id", "")) is outside the Brussels latitude envelope")
        finite_snapshot_number(longitude) && 4.1 <= TreesSurfaces.number(longitude) <= 4.7 || error("bicycle counter $(get(bike, "id", "")) is outside the Brussels longitude envelope")
    end
    for row in joined_records
        id = TreesSurfaces.text(get(row, "id", ""))
        latitude = Float64(managed_by_id[id]["latitude"])
        longitude = Float64(managed_by_id[id]["longitude"])
        nearest_id = ""
        nearest_distance = Inf
        for bike in bikes
            bike_id = TreesSurfaces.text(get(bike, "id", ""))
            bike_latitude = TreesSurfaces.number(get(bike, "latitude", NaN))
            bike_longitude = TreesSurfaces.number(get(bike, "longitude", NaN))
            distance = haversine_distance_m(latitude, longitude, bike_latitude, bike_longitude)
            if distance < nearest_distance
                nearest_id = bike_id
                nearest_distance = distance
            end
        end
        TreesSurfaces.text(get(row, "nearest_counter", "")) == nearest_id || error("nearest-counter assignment disagrees with source counter coordinates for tree $(id)")
        TreesSurfaces.number(get(row, "nearest_counter_distance_m", NaN)) == round(nearest_distance; digits = 1) || error("nearest-counter distance disagrees with source coordinates for tree $(id)")
    end

    expected_flow = build_counter_flow_artifact(; data_dir=data_dir)
    flow_counters = get(flow, "counter_flow", nothing)
    flow_counters isa AbstractDict || error("counter-flow artifact lacks counter summaries")
    flow_counters == expected_flow["counter_flow"] || error("counter-flow summaries disagree with committed counter histories")
    for key in ("source_metadata_url", "source_licence", "source_credit")
        get(flow, key, nothing) == get(expected_flow, key, nothing) || error("counter-flow $(key) disagrees with committed counter histories")
    end
    for (counter, summary) in flow_counters
        summary isa AbstractDict || error("counter-flow summary is not an object for $(counter)")
        get(summary, "measured", nothing) isa Bool || error("counter-flow measured status is not boolean for $(counter)")
        observed_total = get(summary, "observed_total", nothing)
        finite_snapshot_number(observed_total) && TreesSurfaces.number(observed_total) >= 0 || error("counter $(counter) lacks a finite non-negative observed total")
        if summary["measured"]
            days = get(summary, "days", nothing)
            days isa Integer && !(days isa Bool) && days == Dates.value(HISTORY_END_DATE - HISTORY_START_DATE) + 1 || error("measured counter $(counter) does not cover seven days")
            for key in ("mean_all", "min_day_mean", "max_day_mean")
                value = get(summary, key, nothing)
                finite_snapshot_number(value) && TreesSurfaces.number(value) >= 0 || error("measured counter $(counter) lacks a finite non-negative $(key)")
            end
            mean_all = TreesSurfaces.number(summary["mean_all"])
            min_day_mean = TreesSurfaces.number(summary["min_day_mean"])
            max_day_mean = TreesSurfaces.number(summary["max_day_mean"])
            min_day_mean <= mean_all + 0.001 && mean_all <= max_day_mean + 0.001 || error("counter $(counter) mean falls outside its daily-mean range")
            TreesSurfaces.number(observed_total) >= 1 || error("measured counter $(counter) has no observed movement")
            expected_mean = round(TreesSurfaces.number(observed_total) / (days * 96); digits = 3)
            isapprox(mean_all, expected_mean; atol = 1e-9) || error("counter $(counter) mean disagrees with its observed total and seven-day window")
        else
            all(get(summary, key, nothing) === nothing for key in ("mean_all", "min_day_mean", "max_day_mean")) || error("unmeasured counter $(counter) has measured statistics")
        end
    end
    for row in flow_records
        id = TreesSurfaces.text(get(row, "id", ""))
        counter = TreesSurfaces.text(get(row, "nearest_counter", ""))
        !isempty(counter) || error("counter-flow record $(id) lacks a nearest-counter ID")
        joined_row = get(joined_by_id, id, nothing)
        joined_row !== nothing || error("counter-flow record $(id) has no nearest-counter join")
        counter == TreesSurfaces.text(get(joined_row, "nearest_counter", "")) || error("counter-flow record $(id) disagrees with its nearest-counter join")
        finite_snapshot_number(get(row, "distance_m", nothing)) && TreesSurfaces.number(row["distance_m"]) >= 0 || error("counter-flow record $(id) has an invalid counter distance")
        TreesSurfaces.number(row["distance_m"]) == TreesSurfaces.number(get(joined_row, "nearest_counter_distance_m", NaN)) || error("counter-flow record $(id) distance disagrees with its nearest-counter join")
        get(row, "street", nothing) == get(joined_row, "street", nothing) || error("counter-flow record $(id) street disagrees with its nearest-counter join")
        measured = get(row, "has_measured_flow", nothing)
        measured isa Bool || error("counter-flow measured status is not boolean for tree $(id)")
        haskey(row, "counter_flow_mean") || error("counter-flow record $(id) lacks its mean field")
        summary = get(flow_counters, counter, nothing)
        if measured
            summary !== nothing && get(summary, "measured", false) == true || error("tree $(id) claims measured flow for counter $(counter) without a measured summary")
            finite_snapshot_number(row["counter_flow_mean"]) || error("measured-flow tree $(id) lacks a finite counter mean")
            TreesSurfaces.number(row["counter_flow_mean"]) == TreesSurfaces.number(summary["mean_all"]) || error("tree $(id) counter mean disagrees with counter $(counter)")
        else
            row["counter_flow_mean"] === nothing || error("unmeasured-flow tree $(id) has a counter mean")
            summary === nothing || get(summary, "measured", false) == false || error("tree $(id) lacks measured flow despite counter $(counter) being measured")
        end
    end
    get(flow, "period", nothing) == HISTORY_PERIOD || error("counter-flow artifact declares an unexpected period")
    get(flow, "record_count", nothing) == length(flow_records) || error("counter-flow record count disagrees with its records")
    measured_flow = count(get(row, "has_measured_flow", false) == true for row in flow_records)
    measured_flow == 97 || error("expected 97 measured-flow records")
    get(flow, "trees_with_measured_flow", nothing) == measured_flow || error("counter-flow measured-tree count disagrees with its records")
    unmeasured_counters = sort!(collect(Set(
        TreesSurfaces.text(get(row, "nearest_counter", ""))
        for row in flow_records
        if get(row, "has_measured_flow", false) != true && !isempty(TreesSurfaces.text(get(row, "nearest_counter", "")))
    )))
    get(flow, "counters_without_measured_flow", Any[]) == unmeasured_counters || error("counter-flow summary does not match its unmeasured tree records")
    all(haskey(inventory, key) for key in ("managed_trees", "remarkable_trees", "heat", "heat_season", "heat_wbgt", "mobility")) || error("source inventory is incomplete")
    heat_inventory = get(inventory, "heat", Dict{String, Any}())
    heat_inventory isa AbstractDict && get(heat_inventory, "metadata_id", nothing) == get(heat, "source_metadata_id", nothing) || error("source inventory heat metadata ID disagrees with the heat snapshot")
    get(heat_inventory, "licence", nothing) == get(heat, "source_licence", nothing) || error("source inventory heat licence disagrees with the heat snapshot")
    season_inventory = get(inventory, "heat_season", Dict{String, Any}())
    season_inventory isa AbstractDict && get(season_inventory, "licence", nothing) == get(season, "source_licence", nothing) || error("source inventory seasonal-heat licence disagrees with the seasonal heat snapshot")
    lowercase(TreesSurfaces.text(get(season_inventory, "model", ""))) == lowercase(TreesSurfaces.text(get(season, "model", ""))) || error("source inventory seasonal-heat model disagrees with the seasonal heat snapshot")
    mobility_inventory = get(inventory, "mobility", Dict{String, Any}())
    mobility_inventory isa AbstractDict && get(mobility_inventory, "licence", nothing) == get(bikes_payload, "source_licence", nothing) || error("source inventory mobility licence disagrees with the bicycle-counter snapshot")
    mobility_inventory isa AbstractDict && get(mobility_inventory, "credit", nothing) == get(bikes_payload, "source_credit", nothing) && get(mobility_inventory, "metadata", nothing) == get(bikes_payload, "dataset_metadata_url", nothing) || error("source inventory mobility attribution disagrees with the bicycle-counter snapshot")
    crosswalk_inventory = get(inventory, "managed_tree_crosswalk", Dict{String, Any}())
    crosswalk_inventory isa AbstractDict && get(crosswalk_inventory, "source", nothing) == get(crosswalk, "dataset_metadata_url", nothing) && get(crosswalk_inventory, "inputs", nothing) == ["brussels-trees-sample.json"] || error("source inventory crosswalk entry disagrees with the crosswalk artifact")
    accident_inventory = get(inventory, "road_accidents", Dict{String, Any}())
    accident_inventory isa AbstractDict && get(accident_inventory, "licence", nothing) == TreesSurfaces.text(get(accident_source, "source_licence", "")) || error("source inventory road-accident licence disagrees with the accident snapshot")
    accident_inventory isa AbstractDict && get(accident_inventory, "credit", nothing) == TreesSurfaces.text(get(accident_source, "source", "")) || error("source inventory road-accident credit disagrees with the accident snapshot")
    accident_inventory isa AbstractDict && get(accident_inventory, "source", nothing) == TreesSurfaces.text(get(accident_source, "source_url", "")) && get(accident_inventory, "download", nothing) == TreesSurfaces.text(get(accident_source, "download_url", "")) || error("source inventory road-accident URLs disagree with the accident snapshot")
    accident_inventory isa AbstractDict && get(accident_inventory, "coordinate_reference_system", nothing) == TreesSurfaces.text(get(accident_source, "coordinate_reference_system", "")) || error("source inventory road-accident CRS disagrees with the accident snapshot")
    context_inventory = get(inventory, "accident_context", Dict{String, Any}())
    context_inventory isa AbstractDict && get(context_inventory, "inputs", nothing) == get(accidents, "inputs", nothing) || error("source inventory accident-context inputs disagree with the accident-context artifact")
    managed_inventory = get(inventory, "managed_trees", Dict{String, Any}())
    managed_inventory isa AbstractDict && get(managed_inventory, "licence", nothing) == get(managed, "source_licence", nothing) && get(managed_inventory, "credit", nothing) == get(managed, "source_credit", nothing) || error("source inventory managed-tree attribution disagrees with the managed-tree snapshot")
    managed_inventory isa AbstractDict && get(managed_inventory, "metadata", nothing) == get(managed, "dataset_metadata_url", nothing) || error("source inventory managed-tree metadata URL disagrees with the managed-tree snapshot")
    remarkable_snapshot = read_snapshot("brussels-remarkable-trees-sample.json")
    remarkable_records = TreesSurfaces.records(remarkable_snapshot)
    length(remarkable_records) == 100 || error("expected 100 remarkable-tree records")
    remarkable_ids = [TreesSurfaces.text(get(row, "id", "")) for row in remarkable_records]
    all(!isempty(id) for id in remarkable_ids) || error("remarkable-tree sample contains empty IDs")
    length(unique(remarkable_ids)) == 100 || error("remarkable-tree sample IDs are not unique")
    remarkable_total = get(remarkable_snapshot, "source", nothing)
    remarkable_total isa Integer && !(remarkable_total isa Bool) && remarkable_total >= length(remarkable_records) || error("remarkable-tree source total is invalid or smaller than the committed sample")
    for row in remarkable_records
        latitude = get(row, "latitude", nothing)
        longitude = get(row, "longitude", nothing)
        finite_snapshot_number(latitude) && finite_snapshot_number(longitude) && 50.7 <= TreesSurfaces.number(latitude) <= 51.0 && 4.1 <= TreesSurfaces.number(longitude) <= 4.7 || error("remarkable tree $(TreesSurfaces.text(get(row, "id", ""))) is outside the Brussels envelope")
    end
    remarkable_inventory = get(inventory, "remarkable_trees", Dict{String, Any}())
    remarkable_inventory isa AbstractDict && get(remarkable_inventory, "licence", nothing) == get(remarkable_snapshot, "source_licence", nothing) && get(remarkable_inventory, "credit", nothing) == get(remarkable_snapshot, "source_credit", nothing) || error("source inventory remarkable-tree attribution disagrees with the remarkable-tree snapshot")
    remarkable_inventory isa AbstractDict && get(remarkable_inventory, "metadata", nothing) == get(remarkable_snapshot, "dataset_metadata_url", nothing) || error("source inventory remarkable-tree metadata URL disagrees with the remarkable-tree snapshot")

    # The committed stakeholder review is bound to the proposal and audit evidence it was
    # generated from, so a drifted provenance field would misrepresent which evidence was seen.
    proposal = read_snapshot("tree-stakeholder-proposal.json")
    reviews = read_snapshot("tree-stakeholder-reviews.json")
    sensitivity = read_snapshot("tree-signal-sensitivity.json")
    review_records = TreesSurfaces.records(reviews)
    review_count = get(reviews, "record_count", nothing)
    review_count isa Integer && !(review_count isa Bool) && review_count == length(review_records) || error("stakeholder review record count disagrees with its records")
    expected_review_status = review_count >= 1 ? "completed stakeholder review" : "stakeholder review pending"
    get(reviews, "status", nothing) == expected_review_status || error("stakeholder review status disagrees with its record count")
    # A compiled review is only meaningful if the reviewer actually supplied input; otherwise the
    # artifact claims a completed review that carries no response.
    review_input_fields = REVIEW_FIELDS
    allowed_review_statuses = Set(TreesSurfaces.text(status) for status in get(proposal, "allowed_review_statuses", Any[]))
    !isempty(allowed_review_statuses) || error("tree proposal declares no allowed review statuses")
    for row in review_records
        any(!isempty(strip(TreesSurfaces.text(get(row, field, "")))) for field in review_input_fields) || error("stakeholder review record carries no reviewer input")
        validate_review(row, allowed_review_statuses)
    end
    get(reviews, "proposal_id", nothing) == get(proposal, "proposal_id", nothing) || error("stakeholder review is bound to a different proposal")
    audit = get(sensitivity, "data_completeness", Dict{String, Any}())
    weights = get(sensitivity, "weight_sensitivity", Dict{String, Any}())
    # The audit and sensitivity artifact feed the review text and the report, so recompute their
    # record-derived counts from the committed snapshots rather than trusting the artifact.
    heat_joined_ids = Set(TreesSurfaces.text(get(row, "id", "")) for row in heat_records)
    mobility_joined_ids = Set(TreesSurfaces.text(get(row, "id", "")) for row in joined_records)
    flow_context_ids = Set(TreesSurfaces.text(get(row, "id", "")) for row in flow_records)
    measured_flow_ids = Set(TreesSurfaces.text(get(row, "id", "")) for row in flow_records if get(row, "has_measured_flow", false) == true)
    nodata_ids = [TreesSurfaces.text(get(row, "id", "")) for row in heat_records if get(row, "heat_pixel", nothing) == 0]
    ordered_ids = [TreesSurfaces.text(get(row, "id", "")) for row in managed_records]
    audit_checks = (
        ("managed_records", length(ordered_ids)),
        ("valid_coordinate_records", valid_coordinates),
        ("heat_joined_records", length(heat_joined_ids)),
        ("mobility_joined_records", length(mobility_joined_ids)),
        ("analyzed_records", count(id -> id in heat_joined_ids && id in mobility_joined_ids, ordered_ids)),
        ("flow_context_joined_records", length(flow_context_ids)),
        ("measured_flow_context_records", length(measured_flow_ids)),
    )
    for (key, expected) in audit_checks
        get(audit, key, nothing) == expected || error("sensitivity audit $(key) disagrees with the committed snapshots")
    end
    expected_audit_ids = Dict(
        "missing_coordinate_ids" => [id for id in ordered_ids if get(managed_by_id[id], "latitude", nothing) === nothing || get(managed_by_id[id], "longitude", nothing) === nothing],
        "heat_unmatched_ids" => [id for id in ordered_ids if !(id in heat_joined_ids)],
        "mobility_unmatched_ids" => [id for id in ordered_ids if !(id in mobility_joined_ids)],
        "analysis_unmatched_ids" => [id for id in ordered_ids if !(id in heat_joined_ids) || !(id in mobility_joined_ids)],
        "flow_context_unmatched_ids" => [id for id in ordered_ids if !(id in flow_context_ids)],
        "measured_flow_unmatched_ids" => [id for id in ordered_ids if !(id in measured_flow_ids)],
        "heat_nodata_ids" => nodata_ids,
    )
    for (key, expected) in expected_audit_ids
        get(audit, key, nothing) == expected || error("sensitivity audit $(key) disagrees with the committed snapshots")
    end
    expected_unmatched_counters = sort!(collect(Set(TreesSurfaces.text(get(row, "nearest_counter", "")) for row in flow_records if get(row, "has_measured_flow", false) != true && !isempty(TreesSurfaces.text(get(row, "nearest_counter", ""))))))
    get(audit, "measured_flow_unmatched_counters", nothing) == expected_unmatched_counters || error("sensitivity audit unmatched counters disagree with the committed flow snapshot")
    summaries = review_summary_fields(audit, weights)
    expected_core = summaries.core_join_summary
    expected_sensitivity = summaries.sensitivity_summary
    for row in review_records
        id = TreesSurfaces.text(get(row, "proposal_id", ""))
        id == TreesSurfaces.text(get(proposal, "proposal_id", "")) || error("stakeholder review record is bound to a different proposal")
        for (field, source_field) in (("proposal_status", "status"), ("proposed_stakeholder", "proposed_stakeholder"), ("decision_question", "decision_question"), ("spatial_unit", "spatial_unit"), ("heat_measure", "heat_measure"), ("mobility_measure", "mobility_measure"), ("measured_flow_context", "measured_flow_context"), ("output_boundary", "output_boundary"))
            TreesSurfaces.text(get(row, field, "")) == TreesSurfaces.text(get(proposal, source_field, "")) || error("stakeholder review provenance $(field) disagrees with the current proposal")
        end
        TreesSurfaces.text(get(row, "core_join_summary", "")) == expected_core || error("stakeholder review core-join summary disagrees with the current audit")
        TreesSurfaces.text(get(row, "sensitivity_summary", "")) == expected_sensitivity || error("stakeholder review sensitivity summary disagrees with the current sensitivity artifact")
    end
    wbgt_inventory = get(inventory, "heat_wbgt", Dict{String, Any}())
    if isfile(joinpath(data_dir, Wbgt.WBGT_FILENAME))
        wbgt_snapshot = read_snapshot(Wbgt.WBGT_FILENAME)
        wbgt_inventory isa AbstractDict && get(wbgt_inventory, "crs", nothing) == get(wbgt_snapshot, "crs", nothing) || error("source inventory WBGT CRS disagrees with the WBGT snapshot")
        get(wbgt_inventory, "resolution_metres", nothing) == get(get(wbgt_snapshot, "grid", Dict{String, Any}()), "step_metres", nothing) || error("source inventory WBGT resolution disagrees with the WBGT snapshot")
        wbgt_status = get(get(wbgt_snapshot, "licence_review", Dict{String, Any}()), "status", "")
        startswith(lowercase(TreesSurfaces.text(get(wbgt_inventory, "licence", ""))), lowercase(wbgt_status)) || error("source inventory WBGT licence disagrees with the WBGT snapshot")
    end

    # The seasonal heat context is a committed source snapshot: it must cover the same trees,
    # resolve every tree to a declared ERA5 cell, and carry per-tree values identical to that
    # cell, so the report cannot quote a number the artifact does not contain.
    season_records = TreesSurfaces.records(season)
    season_cells = get(season, "cells", Any[])
    year = get(season, "season", Dict{String, Any}())
    length(season_records) == 100 || error("expected 100 seasonal heat records")
    !isempty(season_cells) || error("seasonal heat snapshot contains no ERA5 cells")
    season_ids = [TreesSurfaces.text(get(row, "id", "")) for row in season_records]
    Set(season_ids) == managed_ids || error("seasonal heat record IDs differ from the managed-tree sample")
    get(season, "model", nothing) == "era5" || error("seasonal heat snapshot is not sourced from the ERA5 model")
    get(season, "source_licence", nothing) == "CC BY 4.0" || error("seasonal heat source licence is missing or changed")
    occursin("Open-Meteo", TreesSurfaces.text(get(season, "source_credit", ""))) && occursin("Copernicus", TreesSurfaces.text(get(season, "source_credit", ""))) || error("seasonal heat attribution must credit Open-Meteo and Copernicus")
    occursin("open-meteo.com/en/docs/historical-weather-api", TreesSurfaces.text(get(season, "dataset_metadata_url", ""))) || error("seasonal heat metadata URL is missing")
    occursin("models=era5", TreesSurfaces.text(get(season, "request_url", ""))) || error("seasonal heat request does not explicitly select ERA5")
    occursin("models=era5", TreesSurfaces.text(get(season, "grid_probe_url", ""))) || error("seasonal heat snapshot lacks its ERA5 grid-probe request")
    TreesSurfaces.text(get(season, "reference_date", "")) == REFERENCE_DATE || error("seasonal heat record date differs from the committed WBGT date")
    get(year, "months", Any[]) == ["06", "07", "08"] || error("seasonal heat months differ from the documented June-August season")
    expected_window_years = WINDOW_END_YEAR - WINDOW_START_YEAR + 1
    get(year, "window_start_year", 0) == WINDOW_START_YEAR && get(year, "window_end_year", 0) == WINDOW_END_YEAR || error("seasonal heat window differs from the documented ERA5 window")
    get(year, "season_days", 0) == expected_window_years * SEASON_DAYS_PER_YEAR || error("seasonal heat season must cover $(expected_window_years * SEASON_DAYS_PER_YEAR) days")
    season_days_per_year = get(year, "season_days_per_year", nothing)
    season_days_per_year isa Integer && !(season_days_per_year isa Bool) && season_days_per_year == SEASON_DAYS_PER_YEAR || error("seasonal heat season days per year must be $(SEASON_DAYS_PER_YEAR)")
    requested_step = TreesSurfaces.number(get(get(season, "grid", Dict{String, Any}()), "requested_step_degrees", 0.0))
    requested_step == GRID_STEP_DEGREES || error("seasonal heat requested grid step disagrees with the configured ERA5 grid")
    request_url = TreesSurfaces.text(get(season, "request_url", ""))
    season_method = TreesSurfaces.text(get(season, "method", ""))
    occursin("$(HOT_DAY_APPARENT_TMAX_C) °C", season_method) || error("seasonal heat method text disagrees with the configured hot-day threshold")
    occursin("$(TROPICAL_NIGHT_TMIN_C) °C", season_method) || error("seasonal heat method text disagrees with the configured tropical-night threshold")
    occursin("start_date=$(get(year, "window_start_year", 0))-01-01", request_url) && occursin("end_date=$(get(year, "window_end_year", 0))-12-31", request_url) || error("seasonal heat request URL does not match the declared window")
    for variable in DAILY_VARIABLES
        occursin(variable, request_url) || error("seasonal heat request URL omits the $(variable) variable")
    end
    cell_by_key = Dict{String, Any}()
    for cell in season_cells
        latitude = TreesSurfaces.number(get(cell, "grid_latitude", NaN))
        longitude = TreesSurfaces.number(get(cell, "grid_longitude", NaN))
        (isfinite(latitude) && isfinite(longitude) && 50.6 <= latitude <= 51.1 && 4.0 <= longitude <= 4.8) || error("seasonal heat cell is outside the Brussels envelope")
        key = TreesSurfaces.text(get(cell, "grid_key", ""))
        !isempty(key) || error("seasonal heat cell lacks a grid key")
        haskey(cell_by_key, key) && error("seasonal heat grid key $(key) is duplicated")
        cell_by_key[key] = cell
        get(cell, "season_days", 0) == expected_window_years * SEASON_DAYS_PER_YEAR || error("seasonal heat cell $(key) covers $(get(cell, "season_days", 0)) season days")
        get(cell, "season_year_count", 0) == expected_window_years || error("seasonal heat cell $(key) covers $(get(cell, "season_year_count", 0)) seasons")
        metric_keys = ("seasonal_mean_apparent_tmax_c", "seasonal_mean_tmax_c", "seasonal_mean_tmin_c", "hot_days_per_season", "tropical_nights_per_season", "hottest_season_apparent_tmax_mean_c", "warmest_season_apparent_tmax_c", "reference_date_apparent_tmax_c", "reference_date_tmax_c", "reference_date_season_mean_apparent_tmax_c", "reference_date_season_percentile", "reference_date_window_percentile", "seasonal_mean_apparent_tmax_spread_across_years_c")
        all(finite_snapshot_number(get(cell, metric, nothing)) for metric in metric_keys) || error("seasonal heat cell $(key) contains a missing or non-finite metric")
        0.0 <= TreesSurfaces.number(get(cell, "seasonal_mean_apparent_tmax_c", -99.0)) <= 45.0 || error("seasonal heat cell $(key) has an implausible seasonal mean")
        0.0 <= TreesSurfaces.number(get(cell, "hot_days_per_season", -1.0)) <= 92.0 || error("seasonal heat cell $(key) has an implausible hot-day count")
        0.0 <= TreesSurfaces.number(get(cell, "tropical_nights_per_season", -1.0)) <= 92.0 || error("seasonal heat cell $(key) has an implausible tropical-night count")
        0.0 <= TreesSurfaces.number(get(cell, "reference_date_season_percentile", -1.0)) <= 100.0 || error("seasonal heat cell $(key) has an implausible reference-date percentile")
        0.0 <= TreesSurfaces.number(get(cell, "reference_date_window_percentile", -1.0)) <= 100.0 || error("seasonal heat cell $(key) has an implausible full-window reference-date percentile")
        TreesSurfaces.number(get(cell, "seasonal_mean_apparent_tmax_spread_across_years_c", -1.0)) >= 0.0 || error("seasonal heat cell $(key) has a negative interannual spread")
        hottest_year = tryparse(Int, TreesSurfaces.text(get(cell, "hottest_season_year", "")))
        hottest_year !== nothing && year["window_start_year"] <= hottest_year <= year["window_end_year"] || error("seasonal heat cell $(key) has a hottest-season year outside its window")
        hottest_mean = TreesSurfaces.number(get(cell, "hottest_season_apparent_tmax_mean_c", NaN))
        seasonal_mean = TreesSurfaces.number(get(cell, "seasonal_mean_apparent_tmax_c", NaN))
        warmest_day = TreesSurfaces.number(get(cell, "warmest_season_apparent_tmax_c", NaN))
        hottest_mean + 0.01 >= seasonal_mean || error("seasonal heat cell $(key) hottest-season mean is below its pooled mean")
        warmest_day + 0.01 >= hottest_mean || error("seasonal heat cell $(key) hottest-season mean exceeds its warmest day")
        rank = get(cell, "reference_date_rank_within_season", nothing)
        rank isa Integer && !(rank isa Bool) && 1 <= rank <= 92 || error("seasonal heat cell $(key) has an implausible reference-date rank")
        expected_percentile = round(100 * (rank - 1) / 92; digits = 1)
        isapprox(TreesSurfaces.number(get(cell, "reference_date_season_percentile", NaN)), expected_percentile; atol = 0.05) || error("seasonal heat cell $(key) percentile disagrees with its reference-date rank")
    end
    summary = get(season, "region_summary", Dict{String, Any}())
    get(summary, "cells", 0) == length(season_cells) || error("seasonal heat region summary counts $(get(summary, "cells", 0)) cells where the snapshot contains $(length(season_cells))")
    seasonal_cell_means = [TreesSurfaces.number(cell["seasonal_mean_apparent_tmax_c"]) for cell in season_cells]
    reference_temperatures = [TreesSurfaces.number(cell["reference_date_apparent_tmax_c"]) for cell in season_cells]
    seasonal_percentiles = [TreesSurfaces.number(cell["reference_date_season_percentile"]) for cell in season_cells]
    cell_hot_days = [TreesSurfaces.number(cell["hot_days_per_season"]) for cell in season_cells]
    summary_checks = (
        ("seasonal_mean_apparent_tmax_min_c", minimum(seasonal_cell_means)),
        ("seasonal_mean_apparent_tmax_max_c", maximum(seasonal_cell_means)),
        ("seasonal_mean_apparent_tmax_spread_c", maximum(seasonal_cell_means) - minimum(seasonal_cell_means)),
        ("reference_date_apparent_tmax_min_c", minimum(reference_temperatures)),
        ("reference_date_apparent_tmax_max_c", maximum(reference_temperatures)),
        ("reference_date_season_percentile_min", minimum(seasonal_percentiles)),
        ("reference_date_season_percentile_max", maximum(seasonal_percentiles)),
        ("hot_days_per_season_min", minimum(cell_hot_days)),
        ("hot_days_per_season_max", maximum(cell_hot_days)),
    )
    for (key, expected) in summary_checks
        isapprox(TreesSurfaces.number(get(summary, key, NaN)), expected; atol = 0.01) || error("seasonal heat region summary $(key) disagrees with its cells")
    end
    for row in season_records
        id = TreesSurfaces.text(get(row, "id", ""))
        tree = managed_by_id[id]
        expected_grid = era5_grid_point(tree["latitude"], tree["longitude"])
        expected_key = era5_grid_key(expected_grid...)
        record_key = TreesSurfaces.text(get(row, "grid_key", ""))
        record_key == expected_key || error("seasonal heat record $(id) is assigned to the wrong ERA5 grid cell")
        isapprox(TreesSurfaces.number(get(row, "grid_latitude", NaN)), expected_grid[1]; atol = 1e-9) || error("seasonal heat record $(id) latitude disagrees with tree snapping")
        isapprox(TreesSurfaces.number(get(row, "grid_longitude", NaN)), expected_grid[2]; atol = 1e-9) || error("seasonal heat record $(id) longitude disagrees with tree snapping")
        cell = get(cell_by_key, record_key, nothing)
        cell === nothing && error("seasonal heat record $(id) references an undeclared ERA5 cell")
        isapprox(TreesSurfaces.number(get(cell, "grid_latitude", NaN)), expected_grid[1]; atol = 1e-9) || error("seasonal heat cell $(record_key) latitude disagrees with tree snapping")
        isapprox(TreesSurfaces.number(get(cell, "grid_longitude", NaN)), expected_grid[2]; atol = 1e-9) || error("seasonal heat cell $(record_key) longitude disagrees with tree snapping")
        for (record_key, cell_key) in (("seasonal_mean_apparent_tmax_c", "seasonal_mean_apparent_tmax_c"), ("reference_date_apparent_tmax_c", "reference_date_apparent_tmax_c"), ("reference_date_season_percentile", "reference_date_season_percentile"))
            TreesSurfaces.number(get(row, record_key, -1.0)) == TreesSurfaces.number(get(cell, cell_key, -2.0)) || error("seasonal heat record $(id) disagrees with its ERA5 cell on $(record_key)")
        end
    end
    record_grid_keys = Set(TreesSurfaces.text(get(row, "grid_key", "")) for row in season_records)
    record_grid_keys == Set(keys(cell_by_key)) || error("seasonal heat cells do not exactly cover the tree-assigned ERA5 grid cells")

    crosswalk_records = TreesSurfaces.records(crosswalk)
    crosswalk_legacy = [TreesSurfaces.text(get(row, "legacy_id", "")) for row in crosswalk_records]
    crosswalk_live = [TreesSurfaces.text(get(row, "live_id", "")) for row in crosswalk_records]
    length(crosswalk_records) == 100 || error("expected 100 managed-tree crosswalk records")
    all(!isempty(id) for id in crosswalk_legacy) || error("managed-tree crosswalk contains empty legacy IDs")
    all(!isempty(id) for id in crosswalk_live) || error("managed-tree crosswalk contains empty live IDs")
    length(unique(crosswalk_legacy)) == 100 || error("managed-tree crosswalk legacy IDs are not unique")
    length(unique(crosswalk_live)) == 100 || error("managed-tree crosswalk live IDs are not unique")
    Set(crosswalk_legacy) == managed_ids || error("managed-tree crosswalk does not cover the committed managed-tree sample IDs")
    for row in crosswalk_records
        legacy_id = TreesSurfaces.text(get(row, "legacy_id", ""))
        managed = managed_by_id[legacy_id]
        for key in ("latitude", "longitude")
            get(row, key, nothing) == get(managed, key, nothing) || error("managed-tree crosswalk coordinates disagree for $(legacy_id)")
        end
    end

    accident_records = get(accidents, "counters", Any[])
    accident_rows = TreesSurfaces.records(accident_source)
    accident_summary = get(accident_source, "summary", nothing)
    accident_summary isa AbstractDict || error("accident source snapshot lacks its summary block")
    get(accident_summary, "record_count", nothing) == length(accident_rows) || error("accident source summary record count disagrees with its records")
    get(accident_summary, "bicycle_involved_count", nothing) == count(get(row, "bicycle_involved", false) == true for row in accident_rows) || error("accident source summary bicycle count disagrees with its records")
    source_years = sort!(collect(Set(TreesSurfaces.text(get(row, "year", "")) for row in accident_rows)))
    get(accident_summary, "years", nothing) == source_years || error("accident source summary years disagree with its records")
    expected_accidents = build_accident_context(; data_dir=data_dir)
    # The builder skips source rows with missing or non-finite Lambert coordinates
    # before counting; recount those skips here so a builder defect that dropped
    # valid rows could not hide behind its own record count.
    skipped_accidents = count(accident_rows) do row
        raw_x = get(row, "x_lambert72", nothing)
        raw_y = get(row, "y_lambert72", nothing)
        raw_x === nothing || raw_y === nothing || isempty(TreesSurfaces.text(raw_x)) || isempty(TreesSurfaces.text(raw_y)) || !finite_lambert_coordinate(raw_x) || !finite_lambert_coordinate(raw_y)
    end
    committed_accident_count = get(accidents, "record_count", nothing)
    committed_accident_count isa Integer && !(committed_accident_count isa Bool) && committed_accident_count + skipped_accidents == length(accident_rows) || error("accident-context record count and skipped rows do not cover the source snapshot")
    get(accidents, "record_count", nothing) == expected_accidents["record_count"] || error("accident-context record count disagrees with source coordinates")
    for key in ("accidents_by_year", "bicycle_accidents_by_year")
        get(accidents, key, nothing) == expected_accidents[key] || error("accident-context $(key) disagrees with source records")
    end
    !isempty(accident_records) || error("accident-context snapshot contains no counters")
    accident_ids = [TreesSurfaces.text(get(row, "id", "")) for row in accident_records]
    all(!isempty(id) for id in accident_ids) || error("accident-context contains empty counter IDs")
    length(unique(accident_ids)) == length(accident_ids) || error("accident-context counter IDs are not unique")
    Set(accident_ids) == Set(bike_ids) || error("accident-context counters differ from the bicycle-counter snapshot")
    bikes_by_id = Dict(bike_ids[index] => bikes[index] for index in eachindex(bikes))
    for row in accident_records
        id = TreesSurfaces.text(get(row, "id", ""))
        bike = bikes_by_id[id]
        for key in ("street", "latitude", "longitude")
            get(row, key, nothing) == get(bike, key, nothing) || error("accident-context counter $(id) disagrees with the bicycle-counter snapshot on $(key)")
        end
    end
    accident_count_keys = ("accidents_within_250m", "bicycle_accidents_within_250m", "accidents_within_500m", "bicycle_accidents_within_500m")
    expected_accident_counters = Dict(TreesSurfaces.text(get(row, "id", "")) => row for row in expected_accidents["counters"])
    for row in accident_records
        for key in accident_count_keys
            value = get(row, key, nothing)
            value isa Integer && !(value isa Bool) && value >= 0 || error("accident-context $(key) must be a non-negative integer for $(TreesSurfaces.text(get(row, "id", "")))")
            value == expected_accident_counters[TreesSurfaces.text(get(row, "id", ""))][key] || error("accident-context $(key) disagrees with source geometry for $(TreesSurfaces.text(get(row, "id", "")))")
        end
        row["bicycle_accidents_within_250m"] <= row["accidents_within_250m"] || error("accident-context bicycle accidents exceed all accidents within 250 m for $(row["id"])")
        row["bicycle_accidents_within_500m"] <= row["accidents_within_500m"] || error("accident-context bicycle accidents exceed all accidents within 500 m for $(row["id"])")
        row["accidents_within_250m"] <= row["accidents_within_500m"] || error("accident-context 250 m count exceeds 500 m count for $(row["id"])")
        row["bicycle_accidents_within_250m"] <= row["bicycle_accidents_within_500m"] || error("accident-context bicycle 250 m count exceeds 500 m count for $(row["id"])")
    end

    # The multi-date 100 m WBGT context is optional: it is produced by a separate opt-in command
    # because the upstream archive is ~34 MB per year. When present it must agree with the tree
    # sample and with its own summary, because report text quotes both.
    wbgt_record_count = 0
    wbgt_path = joinpath(data_dir, Wbgt.WBGT_FILENAME)
    if isfile(wbgt_path)
        wbgt = read_snapshot(Wbgt.WBGT_FILENAME)
        wbgt_records = TreesSurfaces.records(wbgt)
        wbgt_record_count = length(wbgt_records)
        length(wbgt_records) == length(managed_ids) || error("WBGT context covers $(length(wbgt_records)) trees where $(length(managed_ids)) were expected")
        wbgt_ids = [TreesSurfaces.text(get(row, "id", "")) for row in wbgt_records]
        Set(wbgt_ids) == managed_ids || error("WBGT context IDs differ from the managed-tree sample")
        get(wbgt, "crs", nothing) == "EPSG:3035" || error("WBGT context does not declare EPSG:3035")
        get(wbgt, "reference_date", nothing) == Wbgt.REFERENCE_DATE || error("WBGT context reference date differs from the committed raster date")
        occursin("UrbClim", TreesSurfaces.text(get(wbgt, "source", ""))) || error("WBGT context source does not name UrbClim")
        get(get(wbgt, "licence_review", Dict{String, Any}()), "status", "") == "unresolved" || error("WBGT context licence review must stay explicitly unresolved until VITO confirms terms")
        window = get(wbgt, "window", Dict{String, Any}())
        start_year = get(window, "start_year", 0)
        end_year = get(window, "end_year", 0)
        (start_year isa Integer && !(start_year isa Bool) && end_year isa Integer && !(end_year isa Bool) && start_year >= 2000 && end_year >= start_year && end_year - start_year + 1 <= 15) || error("WBGT context window $(start_year)-$(end_year) is outside the supported span")
        expected_years = collect(start_year:end_year)
        years = get(window, "years", nothing)
        years isa AbstractVector && length(years) == length(expected_years) && all(value -> value isa Integer && !(value isa Bool), years) && Int.(years) == expected_years || error("WBGT context year list disagrees with its start/end years")
        seasons = get(window, "seasons", nothing)
        seasons isa Integer && !(seasons isa Bool) && seasons == length(expected_years) || error("WBGT context season count disagrees with its year list")
        window_phrase = "$(start_year)–$(end_year)"
        occursin("at or above $(Wbgt.HOT_DAY_WBGT_C) °C", TreesSurfaces.text(get(wbgt, "method", ""))) || error("WBGT context method text disagrees with the configured hot-day threshold")
        occursin(window_phrase, TreesSurfaces.text(get(wbgt, "method", ""))) && occursin(window_phrase, TreesSurfaces.text(get(wbgt, "interpretation_boundary", ""))) || error("WBGT context narrative text disagrees with the declared window")
        get(window, "months", nothing) == collect(Wbgt.SEASON_MONTHS) || error("WBGT context months are not June–August")
        get(wbgt, "archive_base_url", nothing) == Wbgt.ARCHIVE_BASE_URL || error("WBGT context archive base URL disagrees with the configured archive")
        expected_urls = [Wbgt.archive_url(year) for year in expected_years]
        get(wbgt, "archive_urls", nothing) == expected_urls || error("WBGT context archive URLs disagree with the declared window years")
        occursin("Celsius", TreesSurfaces.text(get(wbgt, "value_semantics", ""))) || error("WBGT context value semantics do not declare degrees Celsius")
        grid = get(wbgt, "grid", Dict{String, Any}())
        grid_rows = get(grid, "rows", 0)
        grid_columns = get(grid, "columns", 0)
        (grid_rows isa Integer && !(grid_rows isa Bool) && grid_columns isa Integer && !(grid_columns isa Bool) && grid_rows == Wbgt.EXPECTED_SIZE[2] && grid_columns == Wbgt.EXPECTED_SIZE[1]) || error("WBGT context grid dimensions disagree with the archive")
        TreesSurfaces.number(get(grid, "step_metres", 0)) == Wbgt.GRID_STEP_METRES || error("WBGT context grid step disagrees with the archive")
        cell_centres = Dict{Tuple{Int, Int}, Tuple{Float64, Float64}}()
        for row in wbgt_records
            id = TreesSurfaces.text(get(row, "id", ""))
            column = get(row, "column", nothing)
            grid_row = get(row, "row", nothing)
            column isa Integer && !(column isa Bool) && 1 <= column <= grid_columns || error("WBGT record $(id) has an out-of-range column")
            grid_row isa Integer && !(grid_row isa Bool) && 1 <= grid_row <= grid_rows || error("WBGT record $(id) has an out-of-range row")
            cell_x = TreesSurfaces.number(get(row, "cell_x", NaN))
            cell_y = TreesSurfaces.number(get(row, "cell_y", NaN))
            isfinite(cell_x) && isfinite(cell_y) || error("WBGT record $(id) lacks finite cell coordinates")
            key = (column, grid_row)
            stored = get(cell_centres, key, nothing)
            if stored === nothing
                push!(cell_centres, key => (cell_x, cell_y))
            else
                stored == (cell_x, cell_y) || error("WBGT records sharing a cell disagree on its coordinates")
            end
            tree = managed_by_id[id]
            projected_x, projected_y = Wbgt.wgs84_to_laea_europe(Float64(tree["latitude"]), Float64(tree["longitude"]))
            abs(projected_x - cell_x) <= Wbgt.GRID_STEP_METRES / 2 + 1e-6 || error("WBGT record $(id) cell_x disagrees with its tree coordinates")
            abs(projected_y - cell_y) <= Wbgt.GRID_STEP_METRES / 2 + 1e-6 || error("WBGT record $(id) cell_y disagrees with its tree coordinates")
        end
        get(get(wbgt, "region_summary", Dict{String, Any}()), "distinct_cells", 0) == length(cell_centres) || error("WBGT region summary cell count disagrees with its sampled cells")
        for row in wbgt_records
            get(row, "reference_date", nothing) == Wbgt.REFERENCE_DATE || error("WBGT record $(get(row, "id", "")) has an unexpected reference date")
            for key in ("reference_date_wbgt_c", "seasonal_mean_wbgt_c", "seasonal_max_wbgt_c", "seasonal_min_wbgt_c", "seasonal_p90_wbgt_c", "hottest_season_mean_wbgt_c", "hot_days_per_season", "reference_percentile_in_season")
                finite_snapshot_number(get(row, key, nothing)) || error("WBGT record $(get(row, "id", "")) has a missing or non-finite $(key)")
            end
            TreesSurfaces.number(get(row, "seasonal_min_wbgt_c", -99.0)) >= -40.0 || error("WBGT record $(get(row, "id", "")) has an implausible minimum")
            TreesSurfaces.number(get(row, "seasonal_max_wbgt_c", 99.0)) <= 45.0 || error("WBGT record $(get(row, "id", "")) has an implausible maximum")
            TreesSurfaces.number(get(row, "seasonal_min_wbgt_c", 99.0)) <= TreesSurfaces.number(get(row, "seasonal_mean_wbgt_c", -99.0)) || error("WBGT record $(get(row, "id", "")) has a seasonal mean below its minimum")
            seasonal_max = TreesSurfaces.number(get(row, "seasonal_max_wbgt_c", -99.0))
            seasonal_min = TreesSurfaces.number(get(row, "seasonal_min_wbgt_c", 99.0))
            TreesSurfaces.number(get(row, "seasonal_mean_wbgt_c", 99.0)) <= seasonal_max || error("WBGT record $(get(row, "id", "")) has a seasonal mean above its maximum")
            seasonal_min <= TreesSurfaces.number(get(row, "reference_date_wbgt_c", -99.0)) <= seasonal_max || error("WBGT record $(get(row, "id", "")) has a reference-day value outside its seasonal range")
            seasonal_min <= TreesSurfaces.number(get(row, "seasonal_p90_wbgt_c", -99.0)) <= seasonal_max || error("WBGT record $(get(row, "id", "")) has a seasonal 90th percentile outside its range")
            seasonal_min <= TreesSurfaces.number(get(row, "hottest_season_mean_wbgt_c", -99.0)) <= seasonal_max || error("WBGT record $(get(row, "id", "")) has a hottest-season mean outside its range")
            percentile = TreesSurfaces.number(get(row, "reference_percentile_in_season", -1.0))
            0.0 <= percentile <= 100.0 || error("WBGT record $(get(row, "id", "")) has an implausible percentile")
            rank = get(row, "reference_rank_in_season", nothing)
            pooled_days = get(window, "seasons", 0) * 92
            rank isa Integer && !(rank isa Bool) && 1 <= rank <= pooled_days || error("WBGT record $(get(row, "id", "")) has an implausible pooled reference rank")
            expected_percentile = round(100 * (rank - 1) / pooled_days; digits = 1)
            isapprox(percentile, expected_percentile; atol = 0.05) || error("WBGT record $(get(row, "id", "")) percentile disagrees with its pooled rank")
            hottest_year = tryparse(Int, TreesSurfaces.text(get(row, "hottest_season_year", "")))
            hottest_year !== nothing && start_year <= hottest_year <= end_year || error("WBGT record $(get(row, "id", "")) hottest season lies outside the declared window")
            0.0 <= TreesSurfaces.number(get(row, "hot_days_per_season", -1.0)) <= 92.0 || error("WBGT record $(get(row, "id", "")) has an implausible hot-day count")
        end
        summary = get(wbgt, "region_summary", Dict{String, Any}())
        get(summary, "trees", 0) == length(wbgt_records) || error("WBGT region summary disagrees with its records on the tree count")
        # The generated analysis report quotes these summary figures verbatim, so each one must be
        # reproducible from the per-tree records rather than trusted on its own.
        summary_value(key) = TreesSurfaces.number(get(summary, key, NaN))
        record_values(key) = [TreesSurfaces.number(get(row, key, NaN)) for row in wbgt_records]
        reference_values = record_values("reference_date_wbgt_c")
        isapprox(summary_value("reference_date_wbgt_min_c"), minimum(reference_values); atol = 0.01) || error("WBGT region summary minimum disagrees with its records")
        isapprox(summary_value("reference_date_wbgt_max_c"), maximum(reference_values); atol = 0.01) || error("WBGT region summary maximum disagrees with its records")
        isapprox(summary_value("reference_date_wbgt_spread_c"), maximum(reference_values) - minimum(reference_values); atol = 0.01) || error("WBGT region summary spread disagrees with its records")
        seasonal_values = record_values("seasonal_mean_wbgt_c")
        isapprox(summary_value("seasonal_mean_wbgt_min_c"), minimum(seasonal_values); atol = 0.01) || error("WBGT region summary seasonal-mean minimum disagrees with its records")
        isapprox(summary_value("seasonal_mean_wbgt_max_c"), maximum(seasonal_values); atol = 0.01) || error("WBGT region summary seasonal-mean maximum disagrees with its records")
        isapprox(summary_value("seasonal_mean_wbgt_spread_c"), maximum(seasonal_values) - minimum(seasonal_values); atol = 0.01) || error("WBGT region summary seasonal-mean spread disagrees with its records")
        percentile_values = record_values("reference_percentile_in_season")
        isapprox(summary_value("reference_percentile_min"), minimum(percentile_values); atol = 0.05) || error("WBGT region summary percentile minimum disagrees with its records")
        isapprox(summary_value("reference_percentile_max"), maximum(percentile_values); atol = 0.05) || error("WBGT region summary percentile maximum disagrees with its records")
        isapprox(summary_value("reference_percentile_mean"), Statistics.mean(percentile_values); atol = 0.05) || error("WBGT region summary percentile mean disagrees with its records")
        hot_day_values = record_values("hot_days_per_season")
        isapprox(summary_value("hot_days_per_season_min"), minimum(hot_day_values); atol = 0.01) || error("WBGT region summary hot-day minimum disagrees with its records")
        isapprox(summary_value("hot_days_per_season_max"), maximum(hot_day_values); atol = 0.01) || error("WBGT region summary hot-day maximum disagrees with its records")
        # The top-ten comparison must be internally consistent, otherwise report text could quote
        # an overlap the data does not support.
        period_sensitivity = get(wbgt, "period_sensitivity", Dict{String, Any}())
        wbgt_overlaps = get(period_sensitivity, "top_ten_overlap", Dict{String, Any}())
        balanced_ids = get(period_sensitivity, "balanced_top_ten_ids", nothing)
        balanced_ids isa AbstractVector && length(balanced_ids) == 10 || error("WBGT balanced comparison must contain ten tree IDs")
        balanced_ids = TreesSurfaces.text.(balanced_ids)
        length(unique(balanced_ids)) == 10 && all(id -> id in managed_ids, balanced_ids) || error("WBGT balanced comparison has duplicate or unknown tree IDs")
        balanced_path = joinpath(data_dir, "tree-signal-balanced-screen.csv")
        expected_balanced_ids = Wbgt.balanced_screen_top_ids(balanced_path, managed_ids)
        balanced_ids == expected_balanced_ids || error("WBGT balanced comparison IDs disagree with the committed balanced screen")
        function top_ten_ids(key)
            ordered = sort(wbgt_records, by = row -> (-TreesSurfaces.number(row[key]), TreesSurfaces.text(row["id"])))
            return Set(TreesSurfaces.text(row["id"]) for row in ordered[1:10])
        end
        expected_overlaps = Dict(
            "reference_day_vs_balanced" => length(intersect(top_ten_ids("reference_date_wbgt_c"), Set(balanced_ids))),
            "seasonal_mean_vs_balanced" => length(intersect(top_ten_ids("seasonal_mean_wbgt_c"), Set(balanced_ids))),
            "seasonal_p90_vs_balanced" => length(intersect(top_ten_ids("seasonal_p90_wbgt_c"), Set(balanced_ids))),
            "hot_days_vs_balanced" => length(intersect(top_ten_ids("hot_days_per_season"), Set(balanced_ids))),
            "seasonal_mean_vs_reference_day" => length(intersect(top_ten_ids("seasonal_mean_wbgt_c"), top_ten_ids("reference_date_wbgt_c"))),
        )
        for (key, expected) in expected_overlaps
            value = get(wbgt_overlaps, key, nothing)
            value isa Integer && !(value isa Bool) && value == expected || error("WBGT top-ten overlap $(key) disagrees with its records")
        end
    end

    return Dict{String, Any}(
        "managed_records" => length(managed_records),
        "valid_coordinates" => valid_coordinates,
        "heat_records" => length(heat_records),
        "nearest_counter_records" => length(joined_records),
        "measured_flow_records" => measured_flow,
        "managed_tree_crosswalk_records" => length(crosswalk_records),
        "accident_context_counters" => length(accident_records),
        "heat_season_records" => length(season_records),
        "heat_season_cells" => length(season_cells),
        "heat_wbgt_records" => wbgt_record_count,
    )
end

end
