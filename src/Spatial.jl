module Spatial

using ..TreesSurfaces
using ..Projection

export generate_tree_mobility_join, generate_accident_context, haversine_distance_m

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

function generate_accident_context(output_dir; data_dir=TreesSurfaces.DATA_DIR)
    mkpath(output_dir)
    accidents_payload = TreesSurfaces.read_json_path(joinpath(data_dir, "brussels-road-accidents-2017-2024.json"))
    bikes_payload = TreesSurfaces.read_json_path(joinpath(data_dir, "brussels-bike-counters.json"))
    accidents = TreesSurfaces.records(accidents_payload)
    bikes = TreesSurfaces.records(bikes_payload)
    summaries = Dict{String, Dict{String, Any}}()
    for bike in bikes
        id = TreesSurfaces.text(get(bike, "id", ""))
        summaries[id] = Dict{String, Any}(
            "id" => id,
            "street" => TreesSurfaces.text(get(bike, "street", "")),
            "latitude" => TreesSurfaces.number(get(bike, "latitude", 0)),
            "longitude" => TreesSurfaces.number(get(bike, "longitude", 0)),
            "accidents_within_250m" => 0,
            "bicycle_accidents_within_250m" => 0,
            "accidents_within_500m" => 0,
            "bicycle_accidents_within_500m" => 0,
        )
    end
    valid_records = 0
    years = Dict{String, Int}()
    bicycle_years = Dict{String, Int}()
    for accident in accidents
        raw_x = get(accident, "x_lambert72", nothing)
        raw_y = get(accident, "y_lambert72", nothing)
        raw_x === nothing || raw_y === nothing || isempty(TreesSurfaces.text(raw_x)) || isempty(TreesSurfaces.text(raw_y)) ? continue : nothing
        x = TreesSurfaces.number(raw_x)
        y = TreesSurfaces.number(raw_y)
        isfinite(x) && isfinite(y) || continue
        latitude, longitude = Projection.lambert72_to_wgs84(x, y)
        valid_records += 1
        year = TreesSurfaces.text(get(accident, "year", ""))
        years[year] = get(years, year, 0) + 1
        bicycle = get(accident, "bicycle_involved", false) == true
        bicycle && (bicycle_years[year] = get(bicycle_years, year, 0) + 1)
        for bike in bikes
            distance = haversine_distance_m(latitude, longitude, TreesSurfaces.number(get(bike, "latitude", 0)), TreesSurfaces.number(get(bike, "longitude", 0)))
            if distance > 500
                continue
            end
            bike_id = TreesSurfaces.text(get(bike, "id", ""))
            summary = summaries[bike_id]
            if distance <= 250
                summary["accidents_within_250m"] += 1
                bicycle && (summary["bicycle_accidents_within_250m"] += 1)
            end
            summary["accidents_within_500m"] += 1
            bicycle && (summary["bicycle_accidents_within_500m"] += 1)
        end
    end
    rows = collect(values(summaries))
    sort!(rows, by = row -> (-row["bicycle_accidents_within_500m"], row["id"]))
    payload = Dict{String, Any}(
        "source" => "Derived from Statbel/Federal Police road accidents and Brussels Mobility bicycle-counter snapshots",
        "inputs" => ["brussels-road-accidents-2017-2024.json", "brussels-bike-counters.json"],
        "method" => "Convert Belgian Lambert 72 accident coordinates to WGS84 and count all and bicycle-involved accidents within 250 m and 500 m of each bicycle counter by Haversine distance; an accident is added to every counter whose buffer it falls inside. This is contextual proximity, not exposure-adjusted risk.",
        "coordinate_transform" => "EPSG:31370 to WGS84 using the repository's Belgian 1972 seven-parameter transformation",
        "record_count" => valid_records,
        "accidents_by_year" => years,
        "bicycle_accidents_by_year" => bicycle_years,
        "counters" => rows,
    )
    TreesSurfaces.atomic_write_json(joinpath(output_dir, "brussels-counter-accident-context.json"), payload)
    return payload
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
    TreesSurfaces.atomic_write_json(joinpath(output_dir, "brussels-tree-bike-nearest.json"), payload)
    return payload
end

end
