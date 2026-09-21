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
const SPREADSHEET_FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')
const ESCAPED_FIELDS_COLUMN = "_spreadsheet_escaped_fields"

text(value) = value === nothing ? "" : string(value)

spreadsheet_formula_payload(value) = !isempty(value) && first(value) in SPREADSHEET_FORMULA_PREFIXES

function spreadsheet_safe(value)
    string_value = text(value)
    spreadsheet_formula_payload(string_value) ? "'" * string_value : string_value
end

function spreadsheet_unescape(value)
    startswith(value, "'") && length(value) > 1 || error("stakeholder worksheet escape metadata does not match its cell value")
    remainder = value[nextind(value, firstindex(value)):end]
    spreadsheet_formula_payload(remainder) || error("stakeholder worksheet escape metadata does not match its cell value")
    remainder
end

function parse_csv_records(content)
    rows = Vector{Vector{String}}()
    fields = String[]
    buffer = IOBuffer()
    quoted = false
    index = firstindex(content)
    while index <= lastindex(content)
        character = content[index]
        if character == '"'
            if quoted && index < lastindex(content) && content[nextind(content, index)] == '"'
                print(buffer, '"')
                index = nextind(content, index)
            else
                quoted = !quoted
            end
        elseif character == ',' && !quoted
            push!(fields, String(take!(buffer)))
        elseif (character == '\n' || character == '\r') && !quoted
            push!(fields, String(take!(buffer)))
            push!(rows, fields)
            fields = String[]
            if character == '\r' && index < lastindex(content) && content[nextind(content, index)] == '\n'
                index = nextind(content, index)
            end
        else
            print(buffer, character)
        end
        index = nextind(content, index)
    end
    quoted && error("stakeholder worksheet contains an unterminated quoted field")
    if !isempty(fields) || position(buffer) > 0
        push!(fields, String(take!(buffer)))
        push!(rows, fields)
    end
    rows
end

function read_existing(path)
    isfile(path) || return nothing
    rows = parse_csv_records(read(path, String))
    length(rows) == 2 || error("stakeholder worksheet must contain exactly one proposal row")
    header, values = rows
    length(unique(header)) == length(header) || error("stakeholder worksheet contains duplicate columns")
    length(header) == length(values) || error("stakeholder worksheet has mismatched CSV columns")
    row = Dict(header[index] => values[index] for index in eachindex(header))
    required = Set(["proposal_id", REVIEW_FIELDS...])
    setdiff(required, Set(header)) |> isempty || error("existing stakeholder worksheet is missing required columns")
    serialized_escape_map = pop!(row, ESCAPED_FIELDS_COLUMN, "")
    escape_map = if isempty(serialized_escape_map)
        Dict{String,Any}()
    else
        try
            JSON3.read(serialized_escape_map, Dict{String,Any})
        catch
            error("stakeholder worksheet contains malformed spreadsheet escape metadata")
        end
    end
    all(value isa AbstractString for value in Base.values(escape_map)) || error("stakeholder worksheet spreadsheet escape metadata must be a string map")
    unknown_escaped_fields = setdiff(Set(keys(escape_map)), Set(FIELDS))
    isempty(unknown_escaped_fields) || error("stakeholder worksheet has escape metadata for unknown columns: $(collect(unknown_escaped_fields))")
    for (field, escaped_value) in escape_map
        get(row, field, "") == escaped_value && (row[field] = spreadsheet_unescape(escaped_value))
    end
    return row
end

function valid_iso8601(value)
    tryparse(Date, value) !== nothing && return true
    match_result = match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)(Z|[+-]\d{2}:?\d{2})?$", value)
    match_result === nothing && return false
    tryparse(DateTime, match_result.captures[1]) !== nothing
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
    valid_iso8601(review_values["reviewed_at"]) || error("stakeholder reviewed_at must be ISO 8601")
end

function csv_escape(value)
    value = spreadsheet_safe(value)
    (occursin(',', value) || occursin('"', value) || occursin('\n', value) || occursin('\r', value)) || return value
    "\"" * replace(value, "\"" => "\"\"") * "\""
end

function write_csv(path, row)
    temporary = path * ".tmp"
    open(temporary, "w") do io
        println(io, join(csv_escape.([FIELDS..., ESCAPED_FIELDS_COLUMN]), ","))
        escaped_fields = [field for field in FIELDS if spreadsheet_formula_payload(text(get(row, field, "")))]
        values = [csv_escape(get(row, field, "")) for field in FIELDS]
        escape_map = Dict(field => spreadsheet_safe(get(row, field, "")) for field in escaped_fields)
        push!(values, csv_escape(JSON3.write(escape_map)))
        println(io, join(values, ","))
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

function promote_review_artifacts(stage, data_dir, filenames; move_file! = (source, destination) -> mv(source, destination; force=true))
    mktempdir(dirname(data_dir)) do backup
        existing = Set{String}()
        for filename in filenames
            destination = joinpath(data_dir, filename)
            if isfile(destination)
                cp(destination, joinpath(backup, filename))
                push!(existing, filename)
            end
        end

        promoted = String[]
        try
            for filename in filenames
                move_file!(joinpath(stage, filename), joinpath(data_dir, filename))
                push!(promoted, filename)
            end
        catch
            for filename in reverse(promoted)
                destination = joinpath(data_dir, filename)
                if filename in existing
                    mv(joinpath(backup, filename), destination; force=true)
                else
                    rm(destination; force=true)
                end
            end
            rethrow()
        end
    end
end

function generate_stakeholder_review_artifacts(data_dir; reset_review = false)
    mkpath(data_dir)
    proposal = TreesSurfaces.read_json_path(joinpath(data_dir, "tree-stakeholder-proposal.json"))
    sensitivity = TreesSurfaces.read_json_path(joinpath(data_dir, "tree-signal-sensitivity.json"))
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
    completed = any(!isempty(strip(text(get(row, field, "")))) for field in REVIEW_FIELDS)
    compiled = Dict{String, Any}(
        "source" => basename(output),
        "proposal_id" => proposal["proposal_id"],
        "status" => completed ? "completed stakeholder review" : "stakeholder review pending",
        "record_count" => completed ? 1 : 0,
        "records" => completed ? [Dict(field => text(get(row, field, "")) for field in FIELDS)] : Any[],
    )
    artifact_names = (basename(output), "tree-stakeholder-reviews.json")
    mktempdir(dirname(data_dir)) do stage
        write_csv(joinpath(stage, artifact_names[1]), row)
        write_json(joinpath(stage, artifact_names[2]), compiled)
        promote_review_artifacts(stage, data_dir, artifact_names)
    end
    return row, compiled
end

end
