module TreesSurfaces

using HTTP
using JSON3

export serve_app, read_json_path

const REPO_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
const DATA_DIR = joinpath(REPO_ROOT, "prototypes", "trees-surfaces", "data")
const PUBLIC_DIR = joinpath(@__DIR__, "..", "public")
const APP_STATE = Ref{Any}(nothing)

text(value) = value === nothing ? "" : string(value)
number(value) = value isa Number ? Float64(value) : parse(Float64, text(value))

function read_json_path(path)
    JSON3.read(read(path, String), Dict{String, Any})
end

function read_json(filename)
    read_json_path(joinpath(DATA_DIR, filename))
end

function records(payload)
    get(payload, "records", Any[])
end

function scenario_by_name(scenarios, name)
    for scenario in scenarios
        text(get(scenario, "name", "")) == name && return scenario
    end
    return Dict{String, Any}()
end

function ranked_sites(points, heat_percentage, proximity_percentage)
    heat = max(0.0, Float64(heat_percentage))
    proximity = max(0.0, Float64(proximity_percentage))
    total = heat + proximity
    total = total == 0.0 ? 1.0 : total
    heat_weight = heat / total
    proximity_weight = proximity / total
    ranked = [
        begin
            result = copy(point)
            result["signal"] = point["heatScore"] * heat_weight + point["proximityScore"] * proximity_weight
            result
        end
        for point in points
    ]
    sort!(ranked, by = point -> point["signal"], rev = true)
    return Dict{String, Any}(
        "heatWeight" => heat_weight,
        "proximityWeight" => proximity_weight,
        "sites" => ranked,
    )
end

function query_number(query, key, fallback)
    query === nothing && return fallback
    for pair in split(String(query), '&')
        parts = split(pair, '='; limit = 2)
        length(parts) == 2 || continue
        parts[1] == key || continue
        parsed = tryparse(Float64, parts[2])
        parsed === nothing || return parsed
    end
    return fallback
end

function build_state()
    managed = read_json("brussels-trees-sample.json")
    remarkable = read_json("brussels-remarkable-trees-sample.json")
    bikes = read_json("brussels-bike-counters.json")
    history = read_json("brussels-bike-history-CB2105-2024-01.json")
    joined = read_json("brussels-tree-bike-nearest.json")
    heat = read_json("brussels-tree-heat-sample.json")
    inventory = read_json("source-inventory.json")
    sensitivity = read_json("tree-signal-sensitivity.json")
    flow = read_json("brussels-tree-counter-flow.json")
    proposal = read_json("tree-stakeholder-proposal.json")
    reviews = read_json("tree-stakeholder-reviews.json")

    heat_by_id = Dict(text(get(row, "id", "")) => number(get(row, "heat_pixel", 0)) for row in records(heat))
    flow_by_id = Dict(
        text(get(row, "id", "")) => number(get(row, "counter_flow_mean", 0))
        for row in records(flow)
        if get(row, "has_measured_flow", false) == true
    )

    raw_points = Any[]
    for row in records(joined)
        id = text(get(row, "id", ""))
        haskey(heat_by_id, id) || continue
        push!(raw_points, Dict{String, Any}(
            "id" => id,
            "name" => text(get(row, "street", "")) == "" ? "Unnamed street" : text(get(row, "street", "")),
            "heatPixel" => heat_by_id[id],
            "distanceM" => number(get(row, "nearest_counter_distance_m", 0)),
            "counter" => text(get(row, "nearest_counter", "")),
            "longitude" => number(get(row, "longitude", 0)),
            "latitude" => number(get(row, "latitude", 0)),
            "flowMean" => get(flow_by_id, id, nothing),
        ))
    end

    heat_values = [point["heatPixel"] for point in raw_points]
    distances = [point["distanceM"] for point in raw_points]
    longitudes = [point["longitude"] for point in raw_points]
    latitudes = [point["latitude"] for point in raw_points]
    min_heat, max_heat = extrema(heat_values)
    min_distance, max_distance = extrema(distances)
    min_longitude, max_longitude = extrema(longitudes)
    min_latitude, max_latitude = extrema(latitudes)

    scale(value, low, high) = high == low ? 50.0 : (value - low) / (high - low) * 100
    position(value, low, high) = high == low ? 50.0 : 1 + (value - low) / (high - low) * 82

    for point in raw_points
        point["heatScore"] = scale(point["heatPixel"], min_heat, max_heat)
        point["proximityScore"] = 100 - scale(point["distanceM"], min_distance, max_distance)
        point["mapX"] = position(point["longitude"], min_longitude, max_longitude)
        point["mapY"] = 1 + 82 - position(point["latitude"], min_latitude, max_latitude)
        delete!(point, "longitude")
        delete!(point, "latitude")
    end

    audit = get(sensitivity, "data_completeness", Dict{String, Any}())
    heat_only = scenario_by_name(get(sensitivity, "scenarios", Any[]), "heat_only")
    proximity_only = scenario_by_name(get(sensitivity, "scenarios", Any[]), "proximity_only")
    review_records = records(reviews)
    review = isempty(review_records) ? nothing : first(review_records)

    quality = Dict{String, Any}(
        "validCoordinates" => get(audit, "valid_coordinate_records", 0),
        "managedRecords" => get(audit, "managed_records", 0),
        "heatJoined" => get(audit, "heat_joined_records", 0),
        "heatNoData" => length(get(audit, "heat_nodata_ids", Any[])),
        "mobilityJoined" => get(audit, "mobility_joined_records", 0),
        "flowContext" => get(audit, "measured_flow_context_records", 0),
        "flowGaps" => get(audit, "measured_flow_unmatched_ids", Any[]),
        "minDistance" => min_distance,
        "maxDistance" => max_distance,
    )

    Dict{String, Any}(
        "sites" => raw_points,
        "screen" => ranked_sites(raw_points, 60.0, 40.0),
        "quality" => quality,
        "sensitivity" => Dict{String, Any}(
            "heatOverlap" => get(heat_only, "top_10_overlap_with_balanced", 0),
            "proximityOverlap" => get(proximity_only, "top_10_overlap_with_balanced", 0),
        ),
        "sources" => Dict{String, Any}(
            "managed" => Dict("count" => get(managed, "source", 0), "credit" => get(inventory["managed_trees"], "credit", ""), "licence" => get(inventory["managed_trees"], "licence", ""), "metadata" => get(inventory["managed_trees"], "metadata", "")),
            "remarkable" => Dict("count" => get(remarkable, "source", 0), "credit" => get(inventory["remarkable_trees"], "credit", ""), "licence" => get(inventory["remarkable_trees"], "licence", ""), "metadata" => get(inventory["remarkable_trees"], "metadata", "")),
            "bikes" => Dict("count" => get(bikes, "source", 0), "credit" => get(inventory["mobility"], "credit", ""), "licence" => get(inventory["mobility"], "licence", ""), "metadata" => get(inventory["mobility"], "metadata", "")),
            "heat" => Dict("credit" => get(inventory["heat"], "credit", ""), "licence" => get(inventory["heat"], "licence", ""), "metadata" => get(inventory["heat"], "metadata", "")),
        ),
        "history" => Dict("records" => length(records(history)), "start" => get(history, "start_date", ""), "end" => get(history, "end_date", "")),
        "proposal" => Dict("stakeholder" => get(proposal, "proposed_stakeholder", ""), "question" => get(proposal, "decision_question", ""), "boundary" => get(proposal, "output_boundary", "")),
        "review" => review,
    )
end

function app_state()
    APP_STATE[] === nothing && (APP_STATE[] = build_state())
    return APP_STATE[]
end

function render_index()
    template = read(joinpath(PUBLIC_DIR, "index.html"), String)
    serialized = JSON3.write(app_state())
    # Prevent a data value from terminating the inline script element.
    serialized = replace(serialized, "<" => "\\u003c")
    replace(template, "__INITIAL_STATE__" => serialized)
end

function static_response(path, content_type)
    isfile(path) || return HTTP.Response(404, "Not found")
    HTTP.Response(200, ["Content-Type" => content_type], read(path))
end

function json_response(payload)
    HTTP.Response(200, ["Content-Type" => "application/json; charset=utf-8"], JSON3.write(payload))
end

function handler(request)
    uri = HTTP.URI(request.target)
    path = uri.path
    if path == "/" || path == "/index.html"
        return HTTP.Response(200, ["Content-Type" => "text/html; charset=utf-8"], render_index())
    elseif path == "/api/screen"
        state = app_state()
        heat = query_number(uri.query, "heat", 60.0)
        proximity = query_number(uri.query, "proximity", 40.0)
        return json_response(ranked_sites(state["sites"], heat, proximity))
    elseif path == "/heat-preview.png"
        return static_response(joinpath(DATA_DIR, "heat-preview.png"), "image/png")
    elseif path == "/stakeholder-review.csv"
        return static_response(joinpath(DATA_DIR, "tree-stakeholder-review.csv"), "text/csv; charset=utf-8")
    elseif path == "/health"
        return HTTP.Response(200, ["Content-Type" => "text/plain"], "ok\n")
    end
    HTTP.Response(404, "Not found\n")
end

function serve_app(; host = "127.0.0.1", port = 8080)
    println("Trees & Surfaces Julia UI: http://$(host):$(port)/")
    HTTP.serve(handler, host, port)
end

end
