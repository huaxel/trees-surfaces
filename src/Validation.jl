module Validation

using ..TreesSurfaces

export validate_snapshots

function validate_snapshots(data_dir=TreesSurfaces.DATA_DIR)
    read_snapshot(filename) = TreesSurfaces.read_json_path(joinpath(data_dir, filename))
    managed = read_snapshot("brussels-trees-sample.json")
    heat = read_snapshot("brussels-tree-heat-sample.json")
    joined = read_snapshot("brussels-tree-bike-nearest.json")
    flow = read_snapshot("brussels-tree-counter-flow.json")
    inventory = read_snapshot("source-inventory.json")
    crosswalk = read_snapshot("managed-tree-id-crosswalk.json")
    accidents = read_snapshot("brussels-counter-accident-context.json")

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
    all(haskey(inventory, key) for key in ("managed_trees", "remarkable_trees", "heat", "mobility")) || error("source inventory is incomplete")

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
    )
end

end
