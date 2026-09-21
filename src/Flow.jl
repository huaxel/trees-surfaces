module Flow

using JSON3
using Statistics
using ..TreesSurfaces

export generate_counter_flow_artifact

const COUNTERS = ("CB1101", "CB1142", "CJM90", "CB1143", "CB2105")

function history_payload(feature, data_dir=TreesSurfaces.DATA_DIR)
    TreesSurfaces.read_json_path(joinpath(data_dir, "brussels-bike-history-$(feature)-2024-01.json"))
end

function generate_counter_flow_artifact(output_dir; data_dir=TreesSurfaces.DATA_DIR)
    mkpath(output_dir)
    joined = TreesSurfaces.read_json_path(joinpath(data_dir, "brussels-tree-bike-nearest.json"))
    histories = Dict(feature => history_payload(feature, data_dir) for feature in COUNTERS)
    provenance = Set(
        (
            string(get(payload, "dataset_metadata_url", "")),
            string(get(payload, "source_licence", "")),
            string(get(payload, "source_credit", "")),
        )
        for payload in values(histories)
    )
    length(provenance) == 1 || error("counter history provenance differs across snapshots")
    metadata_url, licence, credit = first(provenance)

    counter_flow = Dict{String, Any}()
    for feature in COUNTERS
        payload = histories[feature]
        count_values = [TreesSurfaces.number(get(row, "count", 0)) for row in TreesSurfaces.records(payload)]
        by_day = Dict{String, Vector{Float64}}()
        for row in TreesSurfaces.records(payload)
            day = first(TreesSurfaces.text(get(row, "count_date", "")), 10)
            push!(get!(by_day, day, Float64[]), TreesSurfaces.number(get(row, "count", 0)))
        end
        day_means = [mean(day_values) for day_values in values(by_day)]
        counter_flow[feature] = Dict{String, Any}(
            "mean_all" => round(mean(count_values); digits = 3),
            "days" => length(by_day),
            "min_day_mean" => round(minimum(day_means); digits = 3),
            "max_day_mean" => round(maximum(day_means); digits = 3),
        )
    end

    records = Any[]
    covered = 0
    for row in TreesSurfaces.records(joined)
        counter = TreesSurfaces.text(get(row, "nearest_counter", ""))
        has_flow = haskey(counter_flow, counter)
        has_flow && (covered += 1)
        push!(records, Dict{String, Any}(
            "id" => TreesSurfaces.text(get(row, "id", "")),
            "street" => get(row, "street", nothing),
            "nearest_counter" => counter,
            "distance_m" => TreesSurfaces.number(get(row, "nearest_counter_distance_m", 0)),
            "counter_flow_mean" => has_flow ? counter_flow[counter]["mean_all"] : nothing,
            "has_measured_flow" => has_flow,
        ))
    end

    payload = Dict{String, Any}(
        "source" => "Brussels Mobility bicycle counter API (five committed counter snapshots sharing one 7-day period)",
        "source_metadata_url" => metadata_url,
        "source_licence" => licence,
        "source_credit" => credit,
        "period" => "2024/01/01 - 2024/01/07",
        "record_count" => length(records),
        "trees_with_measured_flow" => covered,
        "counter_flow" => counter_flow,
        "caveat" => "Flow is measured at the nearest counter, not at the tree; the period is a single winter week, so it is not a seasonal mobility estimate.",
        "records" => records,
    )
    open(joinpath(output_dir, "brussels-tree-counter-flow.json"), "w") do io
        write(io, JSON3.write(payload))
        write(io, "\n")
    end
    return payload
end

end
