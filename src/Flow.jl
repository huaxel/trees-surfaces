module Flow

using Dates
using Statistics
using ..TreesSurfaces

export generate_counter_flow_artifact, build_counter_flow_artifact

const COUNTERS = ("CB1101", "CB1142", "CJM90", "CB1143", "CB2105")

# The counter API reports outages as an unbroken run of zero counts, which is indistinguishable
# from a genuinely unused street if only the mean is inspected. That matters here: CB1101 was
# offline from 2019-01 to 2022-11 and CB1143 stopped reporting in 2025-10, yet both are the
# nearest counter for a large share of the sample. A window with no observed movement is treated
# as unmeasured rather than as zero flow.
MINIMUM_OBSERVED_TOTAL = 1.0
MINIMUM_EXPECTED_ROWS_PER_DAY = 96
const HISTORY_START_DATE = Date(2024, 1, 1)
const HISTORY_END_DATE = Date(2024, 1, 7)
const HISTORY_PERIOD = "2024/01/01 - 2024/01/07"

function parse_history_date(value, feature, field)
    raw = first(TreesSurfaces.text(value), 10)
    normalized = replace(raw, "/" => "-")
    try
        return Date(normalized, dateformat"yyyy-mm-dd")
    catch
        error("counter $(feature) has an invalid $(field) date: $(value)")
    end
end

function validate_history_window(payload, feature)
    TreesSurfaces.text(get(payload, "feature", "")) == feature || error("counter history file for $(feature) declares a different counter ID")
    start_date = parse_history_date(get(payload, "start_date", ""), feature, "start")
    end_date = parse_history_date(get(payload, "end_date", ""), feature, "end")
    start_date == HISTORY_START_DATE && end_date == HISTORY_END_DATE || error(
        "counter $(feature) history covers $(start_date) to $(end_date); expected $(HISTORY_START_DATE) to $(HISTORY_END_DATE)",
    )
    return Set(HISTORY_START_DATE + Day(offset) for offset in 0:Dates.value(HISTORY_END_DATE - HISTORY_START_DATE))
end

function history_payload(feature, data_dir=TreesSurfaces.DATA_DIR)
    TreesSurfaces.read_json_path(joinpath(data_dir, "brussels-bike-history-$(feature)-2024-01.json"))
end

function build_counter_flow_artifact(; data_dir=TreesSurfaces.DATA_DIR)
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
        expected_days = validate_history_window(payload, feature)
        rows = TreesSurfaces.records(payload)
        count_values = Float64[]
        by_day = Dict{String, Vector{Float64}}()
        slots_by_day = Dict{String, Set{Int}}()
        for row in rows
            day = parse_history_date(get(row, "count_date", ""), feature, "record")
            day in expected_days || error("counter $(feature) has a record outside its declared history window: $(day)")
            day_key = Dates.format(day, dateformat"yyyy-mm-dd")
            raw_count = get(row, "count", nothing)
            raw_count isa Real && !(raw_count isa Bool) && isfinite(Float64(raw_count)) && raw_count >= 0 || error("counter $(feature) has an invalid count on $(day)")
            count = Float64(raw_count)
            push!(count_values, count)
            push!(get!(by_day, day_key, Float64[]), count)
            raw_slot = get(row, "time_gap", nothing)
            raw_slot isa Integer && !(raw_slot isa Bool) && 1 <= raw_slot <= MINIMUM_EXPECTED_ROWS_PER_DAY || error("counter $(feature) has an invalid time slot on $(day)")
            push!(get!(slots_by_day, day_key, Set{Int}()), Int(raw_slot))
        end
        day_means = [mean(day_values) for day_values in values(by_day)]
        # Guard the ways a snapshot can look valid while carrying no usable measurement: an all-zero
        # window (outage, or a counter that was not yet installed), missing or duplicated slots, and
        # duplicate rows that leave every slot present while inflating the totals.
        observed_total = sum(count_values)
        expected_rows = length(expected_days) * MINIMUM_EXPECTED_ROWS_PER_DAY
        expected_slots = Set(1:MINIMUM_EXPECTED_ROWS_PER_DAY)
        expected_day_keys = Set(Dates.format(day, dateformat"yyyy-mm-dd") for day in expected_days)
        complete_slots = Set(keys(by_day)) == expected_day_keys && all(get(slots_by_day, day, Set{Int}()) == expected_slots for day in expected_day_keys)
        unexpected_rows = length(rows) != expected_rows
        if observed_total < MINIMUM_OBSERVED_TOTAL || unexpected_rows || !complete_slots
            counter_flow[feature] = Dict{String, Any}(
                "mean_all" => nothing,
                "days" => length(by_day),
                "min_day_mean" => nothing,
                "max_day_mean" => nothing,
                "measured" => false,
                "observed_total" => observed_total,
                "reason" => observed_total < MINIMUM_OBSERVED_TOTAL ?
                    "the committed window records no movement, so this counter is treated as unmeasured rather than as zero flow" :
                    unexpected_rows ? "the committed window has $(length(rows)) slots where $(expected_rows) were expected" :
                    "the committed window has missing or duplicate time slots",
            )
            continue
        end
        counter_flow[feature] = Dict{String, Any}(
            "mean_all" => round(mean(count_values); digits = 3),
            "days" => length(by_day),
            "min_day_mean" => round(minimum(day_means); digits = 3),
            "max_day_mean" => round(maximum(day_means); digits = 3),
            "measured" => true,
            "observed_total" => observed_total,
        )
    end

    records = Any[]
    covered = 0
    unmeasured = String[]
    for row in TreesSurfaces.records(joined)
        counter = TreesSurfaces.text(get(row, "nearest_counter", ""))
        measured = haskey(counter_flow, counter) && get(counter_flow[counter], "measured", false) == true
        if measured
            covered += 1
        elseif !isempty(counter) && !(counter in unmeasured)
            # Include nearest counters without an archived history as well as counters whose
            # archived window was rejected as unmeasured.
            push!(unmeasured, counter)
        end
        push!(records, Dict{String, Any}(
            "id" => TreesSurfaces.text(get(row, "id", "")),
            "street" => get(row, "street", nothing),
            "nearest_counter" => counter,
            "distance_m" => TreesSurfaces.number(get(row, "nearest_counter_distance_m", 0)),
            "counter_flow_mean" => measured ? counter_flow[counter]["mean_all"] : nothing,
            "has_measured_flow" => measured,
        ))
    end
    sort!(unmeasured)

    payload = Dict{String, Any}(
        "source" => "Brussels Mobility bicycle counter API (five committed counter snapshots sharing one 7-day period)",
        "source_metadata_url" => metadata_url,
        "source_licence" => licence,
        "source_credit" => credit,
        "period" => HISTORY_PERIOD,
        "record_count" => length(records),
        "trees_with_measured_flow" => covered,
        "counters_without_measured_flow" => unmeasured,
        "counter_flow" => counter_flow,
        "caveat" => "Flow is measured at the nearest counter, not at the tree; the period is a single winter week, so it is not a seasonal mobility estimate. Counters whose committed window records no movement are reported as unmeasured rather than as zero flow, because the source API returns outages as continuous zero counts.",
        "records" => records,
    )
    return payload
end

function generate_counter_flow_artifact(output_dir; data_dir=TreesSurfaces.DATA_DIR)
    mkpath(output_dir)
    payload = build_counter_flow_artifact(; data_dir=data_dir)
    TreesSurfaces.atomic_write_json(joinpath(output_dir, "brussels-tree-counter-flow.json"), payload)
    return payload
end

end
