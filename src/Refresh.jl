module Refresh

using HTTP
using JSON3

export refresh_open_data, validate_history_payload, preserve_sample, fetch_json, generate_managed_tree_crosswalk

const DATA_DIR = joinpath(@__DIR__, "..", "data")
const MANAGED_TREE_METADATA_URL = "https://bruxellesdata.opendatasoft.com/api/explore/v2.1/catalog/datasets/arbres-bomen-vbx-be-bm"
const REMARKABLE_TREE_METADATA_URL = "https://opendata.brussels.be/api/explore/v2.1/catalog/datasets/bruxelles_arbres_remarquables"
const MOBILITY_METADATA_URL = "https://data.mobility.brussels/en/info/rt_counting/"
const MOBILITY_API_URL = "https://data.mobility.brussels/bike/api/counts/"
const COUNTER_HISTORY_FEATURES = ("CB1101", "CB1142", "CJM90", "CB1143", "CB2105")
const REFRESH_FILENAMES = (
    "brussels-trees-sample.json",
    "brussels-remarkable-trees-sample.json",
    "brussels-bike-counters.json",
    ("brussels-bike-history-$(feature)-2024-01.json" for feature in COUNTER_HISTORY_FEATURES)...,
)
const MAX_RESPONSE_BYTES = 20 * 1024 * 1024

# The upstream managed-tree catalogue re-keyed its primary key from numeric suffixes
# (`vbx_56544`) to UUIDs between 2026-09-21 and 2026-10-13. `id` in the committed
# sample is a project-stable identifier, so refreshes resolve it through this
# crosswalk instead of matching the live key directly.
const MANAGED_TREE_CROSSWALK_FILENAME = "managed-tree-id-crosswalk.json"
const MANAGED_TREE_CROSSWALK_RADIUS_M = 2.0

require(condition, message) = condition || throw(ErrorException(message))
text(value) = value === nothing ? "" : string(value)
finite_number(value) = value isa Number && !(value isa Bool) && isfinite(Float64(value))
valid_brussels_coordinates(latitude, longitude) = finite_number(latitude) && finite_number(longitude) && 50.7 <= latitude <= 51.0 && 4.1 <= longitude <= 4.7

function encode_query(value)
    io = IOBuffer()
    for byte in codeunits(string(value))
        if (byte >= UInt8('a') && byte <= UInt8('z')) || (byte >= UInt8('A') && byte <= UInt8('Z')) || (byte >= UInt8('0') && byte <= UInt8('9')) || byte in (UInt8('-'), UInt8('_'), UInt8('.'), UInt8('~'))
            write(io, byte)
        else
            print(io, "%", uppercase(string(byte, base=16, pad=2)))
        end
    end
    String(take!(io))
end

function get_body(url)
    body = IOBuffer()
    headers = ["Accept-Encoding" => "identity", "User-Agent" => "trees-surfaces-julia-refresh/1.0"]
    HTTP.open("GET", url, headers; connect_timeout=10, response_header_timeout=30, read_idle_timeout=30) do stream
        response = HTTP.startread(stream)
        require(200 <= response.status < 300, "HTTP $(response.status) from $url")
        buffer = Vector{UInt8}(undef, 64 * 1024)
        total = 0
        while true
            count = readbytes!(stream, buffer)
            count == 0 && break
            total += count
            require(total <= MAX_RESPONSE_BYTES, "response exceeds $(MAX_RESPONSE_BYTES) bytes: $url")
            write(body, @view buffer[1:count])
        end
    end
    take!(body)
end

function fetch_json(base; params=Pair{String,String}[])
    query = isempty(params) ? "" : "?" * join(["$(encode_query(k))=$(encode_query(v))" for (k, v) in params], "&")
    payload = JSON3.read(String(get_body(base * query)), Dict{String,Any})
    require(payload isa Dict, "expected JSON object from $(base * query)")
    payload
end

function fetch_text(url)
    String(get_body(url))
end

function atomic_write_json(path, payload)
    mkpath(dirname(path))
    temporary, io = mktemp(dirname(path))
    try
        JSON3.write(io, payload)
        write(io, UInt8('\n'))
        close(io)
        chmod(temporary, 0o644)
        mv(temporary, path; force=true)
    catch
        close(io)
        rm(temporary; force=true)
        rethrow()
    end
end

function committed_sample_ids(path)
    isfile(path) || return nothing
    previous = JSON3.read(read(path, String), Dict{String,Any})
    ids = [text(get(row, "id", nothing)) for row in get(previous, "records", Any[])]
    require(length(ids) == 100 && all(!isempty(id) for id in ids), "committed sample IDs are invalid in $(basename(path))")
    require(length(unique(ids)) == length(ids), "committed sample IDs are duplicated in $(basename(path))")
    ids
end

function preserve_sample(rows, path, raw_id_field)
    ids = [text(get(row, raw_id_field, nothing)) for row in rows]
    require(all(!isempty(id) for id in ids), "source returned missing IDs for $(basename(path))")
    require(length(unique(ids)) == length(ids), "source returned duplicate IDs for $(basename(path))")
    previous = committed_sample_ids(path)
    previous === nothing && (require(length(rows) >= 100, "source returned fewer than 100 records for $(basename(path))"); return rows[1:100])
    by_id = Dict(text(get(row, raw_id_field, nothing)) => row for row in rows)
    missing = [id for id in previous if !haskey(by_id, id)]
    require(isempty(missing), "source no longer returns committed sample IDs for $(basename(path)): $(missing[1:min(3, length(missing))])")
    [by_id[id] for id in previous]
end

function coordinate(value)
    value isa Number && return Float64(value)
    parsed = tryparse(Float64, text(value))
    parsed === nothing ? NaN : parsed
end

function managed_tree_crosswalk(data_dir=DATA_DIR)
    path = joinpath(data_dir, MANAGED_TREE_CROSSWALK_FILENAME)
    isfile(path) || return Dict{String, String}()
    payload = JSON3.read(read(path, String), Dict{String, Any})
    mapping = Dict{String, String}()
    for row in get(payload, "records", Any[])
        legacy = text(get(row, "legacy_id", nothing))
        live = text(get(row, "live_id", nothing))
        (!isempty(legacy) && !isempty(live)) && (mapping[legacy] = live)
    end
    return mapping
end

function managed_tree_live_ids(crosswalk, previous)
    missing = [id for id in previous if !haskey(crosswalk, id)]
    require(
        isempty(missing),
        "$(MANAGED_TREE_CROSSWALK_FILENAME) is missing $(length(missing)) committed managed-tree id(s), e.g. $(join(missing[1:min(3, length(missing))], ", ")); regenerate it with bin/generate_managed_tree_crosswalk.jl",
    )
    return [crosswalk[id] for id in previous]
end

function localize_managed_ids(rows, crosswalk)
    reverse = Dict(live => legacy for (legacy, live) in crosswalk)
    for row in rows
        live = text(get(row, "id", nothing))
        legacy = get(reverse, live, nothing)
        require(legacy !== nothing, "$(MANAGED_TREE_CROSSWALK_FILENAME) has no entry for live managed-tree record $(live); regenerate it with bin/generate_managed_tree_crosswalk.jl")
        row["id"] = legacy
    end
    return rows
end

function validate_history_payload(payload, feature)
    rows = get(payload, "data", Any[])
    require(get(payload, "feature", nothing) == feature, "counter API returned unexpected feature for $feature")
    require(get(payload, "startDate", nothing) == "2024/01/01" && get(payload, "endDate", nothing) == "2024/01/07", "counter API returned unexpected period for $feature")
    require(rows isa AbstractVector && length(rows) == 672, "counter history for $feature must contain 672 observations")
    by_day = Dict{String,Vector{Any}}()
    for row in rows
        count = get(row, "count", nothing)
        require(finite_number(count) && count >= 0, "counter history for $feature contains an invalid count")
        day = text(get(row, "count_date", nothing))
        push!(get!(by_day, day, Any[]), row)
    end
    expected_days = Set("2024/01/$(lpad(day, 2, '0'))" for day in 1:7)
    require(Set(keys(by_day)) == expected_days, "counter history for $feature must cover 2024/01/01 through 2024/01/07")
    require(all(length(day_rows) == 96 for day_rows in values(by_day)), "counter history for $feature must contain 96 observations per day")
    require(
        all(
            all((slot = get(row, "time_gap", nothing); slot isa Integer && !(slot isa Bool) && 1 <= slot <= 96) for row in day_rows) &&
            Set(get(row, "time_gap", nothing) for row in day_rows) == Set(1:96)
            for day_rows in values(by_day)
        ),
        "counter history for $feature must contain each integer 15-minute slot exactly once per day",
    )
    rows
end

function fetch_all_records(base)
    page_size = 100
    first = fetch_json(base; params=["limit"=>"$page_size", "offset"=>"0"])
    rows = Any[get(first, "results", Any[])...]
    total = Int(get(first, "total_count", length(rows)))
    for offset in page_size:page_size:(total - 1)
        page = fetch_json(base; params=["limit"=>"$page_size", "offset"=>"$offset"])
        require(get(page, "total_count", total) == total, "source total changed while paging $base")
        append!(rows, get(page, "results", Any[]))
    end
    require(length(rows) == total, "source paging returned $(length(rows)) records for declared total $total: $base")
    first, rows
end

function first_present(values...)
    for value in values
        if value !== nothing && value !== missing && !isempty(strip(string(value)))
            return value
        end
    end
    nothing
end

function tree_row(item, fields)
    point = get(item, "geo_point_2d", Dict{String,Any}())
    Dict{String,Any}("id"=>get(item, fields[1], nothing), "street"=>first_present(get(item, fields[2], nothing), get(item, fields[3], nothing)), "district"=>first_present(get(item, fields[4], nothing), get(item, fields[5], nothing)), "latitude"=>get(point, "lat", nothing), "longitude"=>get(point, "lon", nothing), "species"=>get(item, fields[6], nothing), "source"=>first_present(get(item, fields[7], nothing), get(item, fields[8], nothing)))
end

function refresh_trees(output_dir=DATA_DIR)
    managed_metadata = fetch_json(MANAGED_TREE_METADATA_URL)
    default_terms = get(get(managed_metadata, "metas", Dict()), "default", Dict())
    terms = get(default_terms, "license", nothing)
    require(terms == "CC BY 4.0" && get(default_terms, "publisher_en", nothing) == "City of Brussels/Data Management" && get(default_terms, "attributions", Any[]) == ["Bruxelles Mobilité", "Bruxelles Environnement", "Google Maps", "Ville de Bruxelles/Espaces publics et verts"], "managed-tree catalogue provenance changed")
    out = joinpath(output_dir, "brussels-trees-sample.json")
    previous = committed_sample_ids(out)
    source_summary = fetch_json(MANAGED_TREE_METADATA_URL * "/records"; params=["limit"=>"1", "offset"=>"0"])
    source = Int(get(source_summary, "total_count", 0))
    params = Pair{String,String}["limit"=>"100"]
    crosswalk = Dict{String, String}()
    if previous !== nothing
        crosswalk = managed_tree_crosswalk(output_dir)
        live_ids = managed_tree_live_ids(crosswalk, previous)
        quoted = join(["'" * replace(id, "'"=>"''") * "'" for id in live_ids], ",")
        params = ["limit"=>"100", "where"=>"id IN ($quoted)"]
    end
    payload = fetch_json(MANAGED_TREE_METADATA_URL * "/records"; params=params)
    fetched = get(payload, "results", Any[])
    expected = previous === nothing ? 100 : length(previous)
    require(source >= 100 && length(fetched) == expected, "managed-tree API returned $(length(fetched)) record(s) where $(expected) were expected (live total_count $(source))")
    rows = [tree_row(item, ("id", "address_fr", "adress_nl", "district_fr", "district_nl", "species", "source_fr", "source_nl")) for item in fetched]
    previous !== nothing && localize_managed_ids(rows, crosswalk)
    rows = preserve_sample(rows, out, "id")
    require(all(valid_brussels_coordinates(get(row, "latitude", nothing), get(row, "longitude", nothing)) for row in rows), "managed-tree sample contains coordinates outside the Brussels region")
    completeness = Dict(field => count(get(row, field, nothing) !== nothing for row in rows) for field in ("latitude", "longitude", "street", "district", "species"))
    atomic_write_json(out, Dict("source"=>source, "dataset_metadata_url"=>MANAGED_TREE_METADATA_URL, "source_licence"=>"CC BY 4.0", "source_credit"=>"City of Brussels/Data Management; catalogue attributions: Bruxelles Mobilité, Bruxelles Environnement, Google Maps, Ville de Bruxelles/Espaces publics et verts", "sampling"=>"first 100 records in initial API response order; refreshes preserve committed IDs; not a probability sample", "completeness"=>completeness, "records"=>rows))

    remarkable_metadata = fetch_json(REMARKABLE_TREE_METADATA_URL)
    remarkable_default = get(get(remarkable_metadata, "metas", Dict()), "default", Dict())
    remarkable_terms = get(remarkable_default, "license", nothing)
    require(remarkable_terms == "CC BY 4.0" && get(remarkable_default, "publisher_en", nothing) == "heritage.brussels" && get(remarkable_default, "attributions", Any[]) == ["National Geographic Institute (NGI-IGN, ngi.be)"], "remarkable-tree catalogue provenance changed")
    metadata, all_rows = fetch_all_records(REMARKABLE_TREE_METADATA_URL * "/records")
    require(Int(get(metadata, "total_count", 0)) >= 100 && length(all_rows) >= 100, "remarkable-tree API returned fewer than 100 records")
    remarkable_out = joinpath(output_dir, "brussels-remarkable-trees-sample.json")
    rows = [Dict("id"=>get(item, "id_arbres_cms", nothing), "species"=>get(item, "nom_la", nothing), "status"=>first_present(get(item, "statuts_fr", nothing), get(item, "statuts_nl", nothing)), "circumference"=>get(item, "circonference", nothing), "crown_diameter"=>get(item, "diametre_cime", nothing), "latitude"=>get(get(item, "geo_point_2d", Dict()), "lat", nothing), "longitude"=>get(get(item, "geo_point_2d", Dict()), "lon", nothing), "url"=>first_present(get(item, "url_fr", nothing), get(item, "url_nl", nothing))) for item in preserve_sample(all_rows, remarkable_out, "id_arbres_cms")]
    require(all(valid_brussels_coordinates(get(row, "latitude", nothing), get(row, "longitude", nothing)) for row in rows), "remarkable-tree sample contains coordinates outside the Brussels region")
    atomic_write_json(remarkable_out, Dict("source"=>get(metadata, "total_count", 0), "dataset_metadata_url"=>REMARKABLE_TREE_METADATA_URL, "source_licence"=>"CC BY 4.0", "source_credit"=>"heritage.brussels; catalogue attribution: National Geographic Institute (NGI-IGN, ngi.be)", "sampling"=>"first 100 records in initial API response order; refreshes preserve committed IDs; not a probability sample", "records"=>rows))
end

function generate_managed_tree_crosswalk(output_path=joinpath(DATA_DIR, MANAGED_TREE_CROSSWALK_FILENAME); data_dir=DATA_DIR)
    sample = JSON3.read(read(joinpath(data_dir, "brussels-trees-sample.json"), String), Dict{String, Any})
    records = Any[]
    for tree in get(sample, "records", Any[])
        legacy = text(get(tree, "id", nothing))
        latitude = coordinate(get(tree, "latitude", nothing))
        longitude = coordinate(get(tree, "longitude", nothing))
        require(!isempty(legacy) && isfinite(latitude) && isfinite(longitude), "committed managed tree $(legacy) lacks usable coordinates")
        payload = fetch_json(
            MANAGED_TREE_METADATA_URL * "/records";
            params=[
                "limit" => "5",
                "select" => "id",
                "where" => "within_distance(geo_point_2d, GEOM'POINT($(longitude) $(latitude))', $(MANAGED_TREE_CROSSWALK_RADIUS_M)m)",
            ],
        )
        matches = [text(get(item, "id", nothing)) for item in get(payload, "results", Any[])]
        require(length(matches) == 1, "expected exactly one live managed tree within $(MANAGED_TREE_CROSSWALK_RADIUS_M) m of $(legacy) ($(latitude), $(longitude)); found $(length(matches))")
        push!(records, Dict{String, Any}("legacy_id"=>legacy, "live_id"=>matches[1], "latitude"=>latitude, "longitude"=>longitude))
    end
    require(length(records) == 100, "expected 100 committed managed trees, found $(length(records))")
    require(length(unique(text(get(row, "live_id", nothing)) for row in records)) == length(records), "crosswalk maps multiple committed ids to the same live id")
    payload = Dict{String, Any}(
        "source" => "Legacy numeric managed-tree identifiers mapped to current live dataset identifiers",
        "dataset_metadata_url" => MANAGED_TREE_METADATA_URL,
        "reason" => "The upstream catalogue re-keyed its primary key from numeric suffixes (for example vbx_56544) to UUIDs; this mapping keeps the committed sample identifiers stable across refreshes.",
        "method" => "Exact one-to-one match by coordinates within $(MANAGED_TREE_CROSSWALK_RADIUS_M) m of each committed managed-tree location",
        "match_radius_m" => MANAGED_TREE_CROSSWALK_RADIUS_M,
        "records" => records,
    )
    atomic_write_json(output_path, payload)
    return payload
end

function counter_row(feature)
    properties = get(feature, "properties", Dict())
    geometry = get(feature, "geometry", Dict())
    coords = geometry isa Dict ? get(geometry, "coordinates", Any[]) : Any[]
    require(coords isa AbstractVector && length(coords) >= 2, "bicycle-counter API returned invalid geometry")
    require(valid_brussels_coordinates(coords[2], coords[1]), "bicycle-counter API returned coordinates outside the Brussels region")
    Dict("id"=>get(properties, "device_name", nothing), "street"=>first_present(get(properties, "road_en", nothing), get(properties, "road_fr", nothing)), "active"=>get(properties, "active", nothing), "longitude"=>coords[1], "latitude"=>coords[2])
end

function refresh_bikes(output_dir=DATA_DIR)
    metadata = fetch_text(MOBILITY_METADATA_URL)
    require(occursin("href=\"https://creativecommons.org/publicdomain/zero/1.0\">CC0</a>", metadata) && occursin("Bruxelles Mobilité", metadata), "bicycle-counter metadata changed")
    payload = fetch_json(MOBILITY_API_URL; params=["request"=>"devices"])
    features = get(payload, "features", Any[])
    require(Int(get(payload, "totalFeatures", 0)) >= 1 && !isempty(features), "bicycle-counter API returned no devices")
    rows = [counter_row(feature) for feature in features]
    ids = [text(get(row, "id", nothing)) for row in rows]
    require(all(!isempty(id) for id in ids) && length(unique(ids)) == length(ids), "bicycle-counter API returned missing or duplicate device IDs")
    atomic_write_json(joinpath(output_dir, "brussels-bike-counters.json"), Dict("source"=>get(payload, "totalFeatures", 0), "dataset_metadata_url"=>MOBILITY_METADATA_URL, "source_licence"=>"CC0 1.0", "source_credit"=>"Brussels Mobility", "records"=>rows))
    for feature in COUNTER_HISTORY_FEATURES
        payload = fetch_json(MOBILITY_API_URL; params=["request"=>"history", "featureID"=>feature, "startDate"=>"20240101", "endDate"=>"20240107"])
        rows = validate_history_payload(payload, feature)
        atomic_write_json(joinpath(output_dir, "brussels-bike-history-$feature-2024-01.json"), Dict("source"=>"Brussels Mobility bicycle counter API", "dataset_metadata_url"=>MOBILITY_METADATA_URL, "source_licence"=>"CC0 1.0", "source_credit"=>"Brussels Mobility", "feature"=>get(payload, "feature", nothing), "start_date"=>get(payload, "startDate", nothing), "end_date"=>get(payload, "endDate", nothing), "records"=>rows))
    end
end

function promote_files(stage, output_dir, filenames; move_file! = (source, destination) -> mv(source, destination; force=true))
    mktempdir(dirname(output_dir)) do backup
        existing = Set{String}()
        for filename in filenames
            destination = joinpath(output_dir, filename)
            if isfile(destination)
                cp(destination, joinpath(backup, filename))
                push!(existing, filename)
            end
        end

        promoted = String[]
        try
            for filename in filenames
                move_file!(joinpath(stage, filename), joinpath(output_dir, filename))
                push!(promoted, filename)
            end
        catch
            for filename in reverse(promoted)
                destination = joinpath(output_dir, filename)
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

function staged_refresh(update!; output_dir=DATA_DIR, filenames=REFRESH_FILENAMES)
    mkpath(output_dir)
    mktempdir(dirname(output_dir)) do temporary
        stage = joinpath(temporary, "data")
        mkpath(stage)
        for filename in readdir(output_dir)
            source = joinpath(output_dir, filename)
            isfile(source) && cp(source, joinpath(stage, filename))
        end
        update!(stage)
        missing = [filename for filename in filenames if !isfile(joinpath(stage, filename))]
        isempty(missing) || error("staged refresh did not produce required outputs: $(missing)")
        promote_files(stage, output_dir, filenames)
    end
end

function refresh_open_data(; output_dir=DATA_DIR)
    staged_refresh(output_dir=output_dir) do stage
        refresh_trees(stage)
        refresh_bikes(stage)
    end
    println("Julia refreshed public-data snapshots; use --with-derived to regenerate derived joins.")
end

end
