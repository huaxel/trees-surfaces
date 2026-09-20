module Spatial

using JSON3
using ..TreesSurfaces

export generate_tree_mobility_join, haversine_distance_m

const EARTH_RADIUS_M = 6_371_000.0

function haversine_distance_m(latitude_a, longitude_a, latitude_b, longitude_b)
    lat_a = deg2rad(latitude_a)
    lon_a = deg2rad(longitude_a)
    lat_b = deg2rad(latitude_b)
    lon_b = deg2rad(longitude_b)
    delta_latitude = lat_b - lat_a
    delta_longitude = lon_b - lon_a
    haversine = sin(delta_latitude / 2)^2 + cos(lat_a) * cos(lat_b) * sin(delta_longitude / 2)^2
    return 2 * EARTH_RADIUS_M * asin(sqrt(haversine))
end

function copy_record(row)
    Dict{String, Any}(string(key) => value for (key, value) in pairs(row))
end

function generate_tree_mobility_join(output_dir; data_dir=TreesSurfaces.DATA_DIR)
    mkpath(output_dir)
    trees_payload = TreesSurfaces.read_json_path(joinpath(data_dir, "brussels-trees-sample.json"))
    bikes_payload = TreesSurfaces.read_json_path(joinpath(data_dir, "brussels-bike-counters.json"))
    trees = TreesSurfaces.records(trees_payload)
    bikes = TreesSurfaces.records(bikes_payload)
    rows = Any[]
    for tree in trees
        latitude = get(tree, "latitude", nothing)
        longitude = get(tree, "longitude", nothing)
        latitude isa Number && longitude isa Number || continue
        nearest = nothing
        nearest_distance = Inf
        for bike in bikes
            bike_latitude = TreesSurfaces.number(get(bike, "latitude", 0))
            bike_longitude = TreesSurfaces.number(get(bike, "longitude", 0))
            distance = haversine_distance_m(Float64(latitude), Float64(longitude), bike_latitude, bike_longitude)
            if distance < nearest_distance
                nearest = bike
                nearest_distance = distance
            end
        end
        nearest === nothing && error("no bicycle counters available")
        row = copy_record(tree)
        row["nearest_counter"] = TreesSurfaces.text(get(nearest, "id", ""))
        row["nearest_counter_distance_m"] = round(nearest_distance; digits = 1)
        push!(rows, row)
    end
    length(rows) == length(trees) || error("nearest-counter join dropped tree records")
    payload = Dict{String, Any}(
        "source" => "Derived from the committed managed-tree and bicycle-counter snapshots",
        "inputs" => ["brussels-trees-sample.json", "brussels-bike-counters.json"],
        "method" => "Haversine great-circle nearest-counter distance using Earth radius 6371000 m; no causal interpretation",
        "records" => rows,
    )
    open(joinpath(output_dir, "brussels-tree-bike-nearest.json"), "w") do io
        write(io, JSON3.write(payload))
        write(io, "\n")
    end
    return payload
end

end
