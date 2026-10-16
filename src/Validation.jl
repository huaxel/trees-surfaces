module Validation

using ..TreesSurfaces

export validate_snapshots

finite_snapshot_number(value) = value isa Number && !(value isa Bool) && isfinite(Float64(value))

function validate_snapshots(data_dir=TreesSurfaces.DATA_DIR)
    read_snapshot(filename) = TreesSurfaces.read_json_path(joinpath(data_dir, filename))
    managed = read_snapshot("brussels-trees-sample.json")
    heat = read_snapshot("brussels-tree-heat-sample.json")
    joined = read_snapshot("brussels-tree-bike-nearest.json")
    flow = read_snapshot("brussels-tree-counter-flow.json")
    inventory = read_snapshot("source-inventory.json")
    crosswalk = read_snapshot("managed-tree-id-crosswalk.json")
    accidents = read_snapshot("brussels-counter-accident-context.json")
    season = read_snapshot("brussels-heat-season-sample.json")

    managed_records = TreesSurfaces.records(managed)
    heat_records = TreesSurfaces.records(heat)
    joined_records = TreesSurfaces.records(joined)
    flow_records = TreesSurfaces.records(flow)
    length(managed_records) == 100 || error("expected 100 managed-tree records")
    length(heat_records) == 100 || error("expected 100 heat records")
    length(joined_records) == 100 || error("expected 100 nearest-counter records")
    length(flow_records) == 100 || error("expected 100 counter-flow records")

    managed_ids = Set(TreesSurfaces.text(get(row, "id", "")) for row in managed_records)
    heat_ids = Set(TreesSurfaces.text(get(row, "id", "")) for row in heat_records)
    joined_ids = Set(TreesSurfaces.text(get(row, "id", "")) for row in joined_records)
    managed_ids == heat_ids || error("managed and heat IDs differ")
    managed_ids == joined_ids || error("managed and nearest-counter IDs differ")
    length(managed_ids) == 100 || error("managed IDs are not unique")

    valid_coordinates = 0
    for row in managed_records
        latitude = get(row, "latitude", nothing)
        longitude = get(row, "longitude", nothing)
        if latitude isa Number && longitude isa Number && isfinite(Float64(latitude)) && isfinite(Float64(longitude))
            valid_coordinates += 1
        end
    end
    valid_coordinates == 100 || error("not all managed records have valid coordinates")
    all(TreesSurfaces.number(get(row, "heat_pixel", 0)) > 0 for row in heat_records) || error("heat snapshot contains NoData pixels")
    all(TreesSurfaces.number(get(row, "nearest_counter_distance_m", -1)) >= 0 for row in joined_records) || error("nearest-counter distance is negative")

    measured_flow = count(get(row, "has_measured_flow", false) == true for row in flow_records)
    measured_flow == 97 || error("expected 97 measured-flow records")
    all(haskey(inventory, key) for key in ("managed_trees", "remarkable_trees", "heat", "heat_season", "mobility")) || error("source inventory is incomplete")

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
    length(unique(season_ids)) == 100 || error("seasonal heat record IDs are not unique")
    get(season, "model", nothing) == "era5" || error("seasonal heat snapshot is not sourced from the ERA5 model")
    get(season, "source_licence", nothing) == "CC BY 4.0" || error("seasonal heat source licence is missing or changed")
    occursin("Open-Meteo", TreesSurfaces.text(get(season, "source_credit", ""))) && occursin("Copernicus", TreesSurfaces.text(get(season, "source_credit", ""))) || error("seasonal heat attribution must credit Open-Meteo and Copernicus")
    occursin("open-meteo.com/en/docs/historical-weather-api", TreesSurfaces.text(get(season, "dataset_metadata_url", ""))) || error("seasonal heat metadata URL is missing")
    occursin("models=era5", TreesSurfaces.text(get(season, "request_url", ""))) || error("seasonal heat request does not explicitly select ERA5")
    occursin("models=era5", TreesSurfaces.text(get(season, "grid_probe_url", ""))) || error("seasonal heat snapshot lacks its ERA5 grid-probe request")
    TreesSurfaces.text(get(season, "reference_date", "")) == "2016-08-24" || error("seasonal heat record date differs from the committed WBGT date")
    get(year, "months", Any[]) == ["06", "07", "08"] || error("seasonal heat months differ from the documented June-August season")
    get(year, "window_start_year", 0) == 2015 && get(year, "window_end_year", 0) == 2024 || error("seasonal heat window differs from the documented 2015-2024 window")
    get(year, "season_days", 0) == 920 || error("seasonal heat season must cover 920 days")
    cell_by_key = Dict{String, Any}()
    for cell in season_cells
        latitude = TreesSurfaces.number(get(cell, "grid_latitude", NaN))
        longitude = TreesSurfaces.number(get(cell, "grid_longitude", NaN))
        (isfinite(latitude) && isfinite(longitude) && 50.6 <= latitude <= 51.1 && 4.0 <= longitude <= 4.8) || error("seasonal heat cell is outside the Brussels envelope")
        key = TreesSurfaces.text(get(cell, "grid_key", ""))
        !isempty(key) || error("seasonal heat cell lacks a grid key")
        haskey(cell_by_key, key) && error("seasonal heat grid key $(key) is duplicated")
        cell_by_key[key] = cell
        get(cell, "season_days", 0) == 920 || error("seasonal heat cell $(key) covers $(get(cell, "season_days", 0)) season days")
        get(cell, "season_year_count", 0) == 10 || error("seasonal heat cell $(key) covers $(get(cell, "season_year_count", 0)) seasons")
        metric_keys = ("seasonal_mean_apparent_tmax_c", "seasonal_mean_tmax_c", "seasonal_mean_tmin_c", "hot_days_per_season", "tropical_nights_per_season", "hottest_season_apparent_tmax_mean_c", "warmest_season_apparent_tmax_c", "reference_date_apparent_tmax_c", "reference_date_tmax_c", "reference_date_season_mean_apparent_tmax_c", "reference_date_season_percentile", "reference_date_window_percentile", "seasonal_mean_apparent_tmax_spread_across_years_c")
        all(finite_snapshot_number(get(cell, metric, nothing)) for metric in metric_keys) || error("seasonal heat cell $(key) contains a missing or non-finite metric")
        0.0 <= TreesSurfaces.number(get(cell, "seasonal_mean_apparent_tmax_c", -99.0)) <= 45.0 || error("seasonal heat cell $(key) has an implausible seasonal mean")
        0.0 <= TreesSurfaces.number(get(cell, "hot_days_per_season", -1.0)) <= 92.0 || error("seasonal heat cell $(key) has an implausible hot-day count")
        0.0 <= TreesSurfaces.number(get(cell, "tropical_nights_per_season", -1.0)) <= 92.0 || error("seasonal heat cell $(key) has an implausible tropical-night count")
        0.0 <= TreesSurfaces.number(get(cell, "reference_date_season_percentile", -1.0)) <= 100.0 || error("seasonal heat cell $(key) has an implausible reference-date percentile")
        rank = get(cell, "reference_date_rank_within_season", nothing)
        rank isa Integer && !(rank isa Bool) && 1 <= rank <= 92 || error("seasonal heat cell $(key) has an implausible reference-date rank")
    end
    summary = get(season, "region_summary", Dict{String, Any}())
    get(summary, "cells", 0) == length(season_cells) || error("seasonal heat region summary counts $(get(summary, "cells", 0)) cells where the snapshot contains $(length(season_cells))")
    seasonal_cell_means = [TreesSurfaces.number(cell["seasonal_mean_apparent_tmax_c"]) for cell in season_cells]
    abs(TreesSurfaces.number(get(summary, "seasonal_mean_apparent_tmax_spread_c", NaN)) - (maximum(seasonal_cell_means) - minimum(seasonal_cell_means))) <= 0.01 || error("seasonal heat region spread disagrees with its cells")
    for row in season_records
        id = TreesSurfaces.text(get(row, "id", ""))
        cell = get(cell_by_key, TreesSurfaces.text(get(row, "grid_key", "")), nothing)
        cell === nothing && error("seasonal heat record $(id) references an undeclared ERA5 cell")
        for (record_key, cell_key) in (("seasonal_mean_apparent_tmax_c", "seasonal_mean_apparent_tmax_c"), ("reference_date_apparent_tmax_c", "reference_date_apparent_tmax_c"), ("reference_date_season_percentile", "reference_date_season_percentile"))
            TreesSurfaces.number(get(row, record_key, -1.0)) == TreesSurfaces.number(get(cell, cell_key, -2.0)) || error("seasonal heat record $(id) disagrees with its ERA5 cell on $(record_key)")
        end
    end

    crosswalk_records = TreesSurfaces.records(crosswalk)
    crosswalk_legacy = [TreesSurfaces.text(get(row, "legacy_id", "")) for row in crosswalk_records]
    crosswalk_live = [TreesSurfaces.text(get(row, "live_id", "")) for row in crosswalk_records]
    length(crosswalk_records) == 100 || error("expected 100 managed-tree crosswalk records")
    all(!isempty(id) for id in crosswalk_legacy) || error("managed-tree crosswalk contains empty legacy IDs")
    all(!isempty(id) for id in crosswalk_live) || error("managed-tree crosswalk contains empty live IDs")
    length(unique(crosswalk_legacy)) == 100 || error("managed-tree crosswalk legacy IDs are not unique")
    length(unique(crosswalk_live)) == 100 || error("managed-tree crosswalk live IDs are not unique")
    Set(crosswalk_legacy) == managed_ids || error("managed-tree crosswalk does not cover the committed managed-tree sample IDs")

    accident_records = get(accidents, "counters", Any[])
    TreesSurfaces.number(get(accidents, "record_count", 0)) > 0 || error("accident-context record count must be positive")
    !isempty(accident_records) || error("accident-context snapshot contains no counters")
    accident_ids = [TreesSurfaces.text(get(row, "id", "")) for row in accident_records]
    all(!isempty(id) for id in accident_ids) || error("accident-context contains empty counter IDs")
    length(unique(accident_ids)) == length(accident_ids) || error("accident-context counter IDs are not unique")
    accident_count_keys = ("accidents_within_250m", "bicycle_accidents_within_250m", "accidents_within_500m", "bicycle_accidents_within_500m")
    for row in accident_records
        for key in accident_count_keys
            value = get(row, key, nothing)
            value isa Integer && !(value isa Bool) && value >= 0 || error("accident-context $(key) must be a non-negative integer for $(TreesSurfaces.text(get(row, "id", "")))")
        end
        row["bicycle_accidents_within_250m"] <= row["accidents_within_250m"] || error("accident-context bicycle accidents exceed all accidents within 250 m for $(row["id"])")
        row["bicycle_accidents_within_500m"] <= row["accidents_within_500m"] || error("accident-context bicycle accidents exceed all accidents within 500 m for $(row["id"])")
        row["accidents_within_250m"] <= row["accidents_within_500m"] || error("accident-context 250 m count exceeds 500 m count for $(row["id"])")
        row["bicycle_accidents_within_250m"] <= row["bicycle_accidents_within_500m"] || error("accident-context bicycle 250 m count exceeds 500 m count for $(row["id"])")
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
    )
end

end
