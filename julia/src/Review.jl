module Review

using Dates
using JSON3
using ..TreesSurfaces

export generate_stakeholder_review_artifacts

const FIELDS = [
    "proposal_id", "proposal_status", "proposed_stakeholder", "decision_question", "spatial_unit",
    "heat_measure", "mobility_measure", "measured_flow_context", "output_boundary", "core_join_summary",
    "sensitivity_summary", "review_status", "reviewer_name", "reviewer_role", "reviewed_at",
    "accepted_decision_question", "accepted_spatial_unit", "accepted_mobility_measure", "accepted_heat_period",
    "false_positive_preference", "evidence_threshold", "review_notes",
]
const REVIEW_FIELDS = [
    "review_status", "reviewer_name", "reviewer_role", "reviewed_at", "accepted_decision_question",
    "accepted_spatial_unit", "accepted_mobility_measure", "accepted_heat_period", "false_positive_preference",
    "evidence_threshold", "review_notes",
]
const COMMON_REQUIRED = ["review_status", "reviewer_name", "reviewer_role", "reviewed_at", "false_positive_preference", "evidence_threshold", "review_notes"]
const ACCEPTED_DECISION = ["accepted_decision_question", "accepted_spatial_unit", "accepted_mobility_measure", "accepted_heat_period"]
const ACCEPTED_STATUSES = Set(["accepted", "accepted with changes"])
const PROVENANCE_FIELDS = [field for field in FIELDS if !(field in REVIEW_FIELDS)]

text(value) = value === nothing ? "" : string(value)

function parse_csv_line(line)
    fields = String[]
    buffer = IOBuffer()
    quoted = false
    index = firstindex(line)
    while index <= lastindex(line)
        character = line[index]
        if character == '"'
            if quoted && index < lastindex(line) && line[nextind(line, index)] == '"'
                print(buffer, '"')
                index = nextind(line, index)
            else
                quoted = !quoted
            end
        elseif character == ',' && !quoted
            push!(fields, String(take!(buffer)))
        else
            print(buffer, character)
        end
        index = nextind(line, index)
    end
    push!(fields, String(take!(buffer)))
    fields
end

function read_existing(path)
    isfile(path) || return nothing
    lines = split(chomp(replace(read(path, String), "\r\n" => "\n")), '\n')
    length(lines) == 2 || error("stakeholder worksheet must contain exactly one proposal row")
    header = parse_csv_line(lines[1])
    values = parse_csv_line(lines[2])
    length(header) == length(values) || error("stakeholder worksheet has mismatched CSV columns")
    row = Dict(header[index] => values[index] for index in eachindex(header))
    required = Set(["proposal_id", REVIEW_FIELDS...])
    setdiff(required, Set(header)) |> isempty || error("existing stakeholder worksheet is missing required columns")
    return row
end

function validate_review(row, allowed_statuses)
    review_values = Dict(field => strip(text(get(row, field, ""))) for field in REVIEW_FIELDS)
    any(!isempty(value) for value in values(review_values)) || return
    for field in COMMON_REQUIRED
        isempty(review_values[field]) && error("stakeholder review is missing $(field)")
    end
    review_values["review_status"] in allowed_statuses || error("invalid stakeholder review status: $(review_values["review_status"])")
    if review_values["review_status"] in ACCEPTED_STATUSES
        for field in ACCEPTED_DECISION
            isempty(review_values[field]) && error("accepted stakeholder review is missing $(field)")
        end
    end
    timestamp = replace(review_values["reviewed_at"], "Z" => "")
    try
        DateTime(timestamp)
    catch
        error("stakeholder reviewed_at must be ISO 8601")
    end
end

function csv_escape(value)
    value === nothing && return ""
    value = string(value)
    (occursin(',', value) || occursin('"', value) || occursin('\n', value) || occursin('\r', value)) || return value
    "\"" * replace(value, "\"" => "\"\"") * "\""
end

function write_csv(path, row)
    temporary = path * ".tmp"
    open(temporary, "w") do io
        println(io, join(csv_escape.(FIELDS), ","))
        println(io, join((csv_escape(get(row, field, "")) for field in FIELDS), ","))
    end
    chmod(temporary, 0o644)
    mv(temporary, path; force = true)
end

function write_json(path, payload)
    temporary = path * ".tmp"
    open(temporary, "w") do io
        write(io, JSON3.write(payload))
        write(io, "\n")
    end
    chmod(temporary, 0o644)
    mv(temporary, path; force = true)
end

function generate_stakeholder_review_artifacts(data_dir; reset_review = false)
    mkpath(data_dir)
    proposal = TreesSurfaces.read_json(joinpath(data_dir, "tree-stakeholder-proposal.json"))
    sensitivity = TreesSurfaces.read_json(joinpath(data_dir, "tree-signal-sensitivity.json"))
    audit = sensitivity["data_completeness"]
    weights = sensitivity["weight_sensitivity"]
    allowed_statuses = Set(string(status) for status in proposal["allowed_review_statuses"])
    row = Dict{String, Any}(
        "proposal_id" => proposal["proposal_id"],
        "proposal_status" => proposal["status"],
        "proposed_stakeholder" => proposal["proposed_stakeholder"],
        "decision_question" => proposal["decision_question"],
        "spatial_unit" => proposal["spatial_unit"],
        "heat_measure" => proposal["heat_measure"],
        "mobility_measure" => proposal["mobility_measure"],
        "measured_flow_context" => proposal["measured_flow_context"],
        "output_boundary" => proposal["output_boundary"],
        "core_join_summary" => "$(audit["analyzed_records"])/$(audit["managed_records"]) records analyzed; $(length(audit["missing_coordinate_ids"])) missing coordinates; $(length(audit["heat_nodata_ids"])) NoData heat pixels; $(length(audit["analysis_unmatched_ids"])) unmatched core joins; $(audit["measured_flow_context_records"])/$(audit["managed_records"]) with measured-flow history",
        "sensitivity_summary" => "balanced top ten overlaps $(weights["heat_only_top_10_overlap"])/10 with heat-only and $(weights["proximity_only_top_10_overlap"])/10 with proximity-only; $(weights["interpretation"])",
    )
    for field in REVIEW_FIELDS
        row[field] = ""
    end

    output = joinpath(data_dir, "tree-stakeholder-review.csv")
    existing = reset_review ? nothing : read_existing(output)
    if existing !== nothing && any(!isempty(strip(get(existing, field, ""))) for field in REVIEW_FIELDS)
        get(existing, "proposal_id", "") == text(row["proposal_id"]) || error("refusing to move stakeholder review onto a different proposal")
        mismatches = [field for field in PROVENANCE_FIELDS if get(existing, field, "") != text(get(row, field, ""))]
        isempty(mismatches) || error("refusing to attach stakeholder review after proposal evidence changed: $(mismatches)")
        for field in REVIEW_FIELDS
            row[field] = get(existing, field, "")
        end
    end
    validate_review(row, allowed_statuses)
    write_csv(output, row)
    completed = any(!isempty(strip(text(get(row, field, "")))) for field in REVIEW_FIELDS)
    compiled = Dict{String, Any}(
        "source" => basename(output),
        "proposal_id" => proposal["proposal_id"],
        "status" => completed ? "completed stakeholder review" : "stakeholder review pending",
        "record_count" => completed ? 1 : 0,
        "records" => completed ? [Dict(field => text(get(row, field, "")) for field in FIELDS)] : Any[],
    )
    write_json(joinpath(data_dir, "tree-stakeholder-reviews.json"), compiled)
    return row, compiled
end

end
