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

    return Dict{String, Any}(
        "managed_records" => length(managed_records),
        "valid_coordinates" => valid_coordinates,
        "heat_records" => length(heat_records),
        "nearest_counter_records" => length(joined_records),
        "measured_flow_records" => measured_flow,
    )
end

end
