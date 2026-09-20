module Refresh

using HTTP
using JSON3

export refresh_open_data, validate_history_payload, preserve_sample, fetch_json

const REPO_ROOT = normpath(joinpath(@__DIR__, "..", ".."))
const DATA_DIR = joinpath(REPO_ROOT, "prototypes", "trees-surfaces", "data")
const MANAGED_TREE_METADATA_URL = "https://bruxellesdata.opendatasoft.com/api/explore/v2.1/catalog/datasets/arbres-bomen-vbx-be-bm"
const REMARKABLE_TREE_METADATA_URL = "https://opendata.brussels.be/api/explore/v2.1/catalog/datasets/bruxelles_arbres_remarquables"
const MOBILITY_METADATA_URL = "https://data.mobility.brussels/en/info/rt_counting/"
const MOBILITY_API_URL = "https://data.mobility.brussels/bike/api/counts/"
const COUNTER_HISTORY_FEATURES = ("CB1101", "CB1142", "CJM90", "CB1143", "CB2105")
const MAX_RESPONSE_BYTES = 20 * 1024 * 1024

require(condition, message) = condition || throw(ErrorException(message))
text(value) = value === nothing ? "" : string(value)

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
    response = HTTP.request("GET", url, ["Accept-Encoding" => "identity", "User-Agent" => "trees-surfaces-julia-refresh/1.0"]; status_exception=false)
    require(200 <= response.status < 300, "HTTP $(response.status) from $url")
    body = Vector{UInt8}(response.body)
    require(length(body) <= MAX_RESPONSE_BYTES, "response exceeds $(MAX_RESPONSE_BYTES) bytes: $url")
    body
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

function validate_history_payload(payload, feature)
    rows = get(payload, "data", Any[])
    require(get(payload, "feature", nothing) == feature, "counter API returned unexpected feature for $feature")
    require(get(payload, "startDate", nothing) == "2024/01/01" && get(payload, "endDate", nothing) == "2024/01/07", "counter API returned unexpected period for $feature")
    require(rows isa AbstractVector && length(rows) == 672, "counter history for $feature must contain 672 observations")
    by_day = Dict{String,Vector{Any}}()
    for row in rows
        count = get(row, "count", nothing)
        require(count isa Number && count >= 0, "counter history for $feature contains an invalid count")
        day = text(get(row, "count_date", nothing))
        push!(get!(by_day, day, Any[]), row)
    end
    expected_days = Set("2024/01/$(lpad(day, 2, '0'))" for day in 1:7)
    require(Set(keys(by_day)) == expected_days, "counter history for $feature must cover 2024/01/01 through 2024/01/07")
    require(all(length(day_rows) == 96 for day_rows in values(by_day)), "counter history for $feature must contain 96 observations per day")
    require(all(Set(get(row, "time_gap", nothing) for row in day_rows) == Set(1:96) for day_rows in values(by_day)), "counter history for $feature must contain each 15-minute slot exactly once per day")
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

function tree_row(item, fields)
    point = get(item, "geo_point_2d", Dict{String,Any}())
    Dict{String,Any}("id"=>get(item, fields[1], nothing), "street"=>coalesce(get(item, fields[2], nothing), get(item, fields[3], nothing)), "district"=>coalesce(get(item, fields[4], nothing), get(item, fields[5], nothing)), "latitude"=>get(point, "lat", nothing), "longitude"=>get(point, "lon", nothing), "species"=>get(item, fields[6], nothing), "source"=>coalesce(get(item, fields[7], nothing), get(item, fields[8], nothing)))
end

function refresh_trees(output_dir=DATA_DIR)
    managed_metadata = fetch_json(MANAGED_TREE_METADATA_URL)
    default_terms = get(get(managed_metadata, "metas", Dict()), "default", Dict())
    terms = get(default_terms, "license", nothing)
    require(terms == "CC BY 4.0" && get(default_terms, "publisher_en", nothing) == "City of Brussels/Data Management" && get(default_terms, "attributions", Any[]) == ["Bruxelles Mobilité", "Bruxelles Environnement", "Google Maps", "Ville de Bruxelles/Espaces publics et verts"], "managed-tree catalogue provenance changed")
    out = joinpath(output_dir, "brussels-trees-sample.json")
    previous = committed_sample_ids(out)
    params = Pair{String,String}["limit"=>"100"]
    if previous !== nothing
        quoted = join(["'" * replace(id, "'"=>"''") * "'" for id in previous], ",")
        params = ["limit"=>"100", "where"=>"id IN ($quoted)"]
    end
    payload = fetch_json(MANAGED_TREE_METADATA_URL * "/records"; params=params)
    source = Int(get(payload, "total_count", 0))
    require(source >= 100 && length(get(payload, "results", Any[])) == 100, "managed-tree API returned fewer than 100 records")
    rows = [tree_row(item, ("id", "address_fr", "adress_nl", "district_fr", "district_nl", "species", "source_fr", "source_nl")) for item in preserve_sample(get(payload, "results", Any[]), out, "id")]
    completeness = Dict(field => count(get(row, field, nothing) !== nothing for row in rows) for field in ("latitude", "longitude", "street", "district", "species"))
    atomic_write_json(out, Dict("source"=>source, "dataset_metadata_url"=>MANAGED_TREE_METADATA_URL, "source_licence"=>"CC BY 4.0", "source_credit"=>"City of Brussels/Data Management; catalogue attributions: Bruxelles Mobilité, Bruxelles Environnement, Google Maps, Ville de Bruxelles/Espaces publics et verts", "sampling"=>"first 100 records in initial API response order; refreshes preserve committed IDs; not a probability sample", "completeness"=>completeness, "records"=>rows))

    remarkable_metadata = fetch_json(REMARKABLE_TREE_METADATA_URL)
    remarkable_default = get(get(remarkable_metadata, "metas", Dict()), "default", Dict())
    remarkable_terms = get(remarkable_default, "license", nothing)
    require(remarkable_terms == "CC BY 4.0" && get(remarkable_default, "publisher_en", nothing) == "heritage.brussels" && get(remarkable_default, "attributions", Any[]) == ["National Geographic Institute (NGI-IGN, ngi.be)"], "remarkable-tree catalogue provenance changed")
    metadata, all_rows = fetch_all_records(REMARKABLE_TREE_METADATA_URL * "/records")
    require(Int(get(metadata, "total_count", 0)) >= 100 && length(all_rows) >= 100, "remarkable-tree API returned fewer than 100 records")
    remarkable_out = joinpath(output_dir, "brussels-remarkable-trees-sample.json")
    rows = [Dict("id"=>get(item, "id_arbres_cms", nothing), "species"=>get(item, "nom_la", nothing), "status"=>coalesce(get(item, "statuts_fr", nothing), get(item, "statuts_nl", nothing)), "circumference"=>get(item, "circonference", nothing), "crown_diameter"=>get(item, "diametre_cime", nothing), "latitude"=>get(get(item, "geo_point_2d", Dict()), "lat", nothing), "longitude"=>get(get(item, "geo_point_2d", Dict()), "lon", nothing), "url"=>coalesce(get(item, "url_fr", nothing), get(item, "url_nl", nothing))) for item in preserve_sample(all_rows, remarkable_out, "id_arbres_cms")]
    atomic_write_json(remarkable_out, Dict("source"=>get(metadata, "total_count", 0), "dataset_metadata_url"=>REMARKABLE_TREE_METADATA_URL, "source_licence"=>"CC BY 4.0", "source_credit"=>"heritage.brussels; catalogue attribution: National Geographic Institute (NGI-IGN, ngi.be)", "sampling"=>"first 100 records in initial API response order; refreshes preserve committed IDs; not a probability sample", "records"=>rows))
end

function counter_row(feature)
    properties = get(feature, "properties", Dict())
    geometry = get(feature, "geometry", Dict())
    coords = geometry isa Dict ? get(geometry, "coordinates", Any[]) : Any[]
    require(coords isa AbstractVector && length(coords) >= 2, "bicycle-counter API returned invalid geometry")
    Dict("id"=>get(properties, "device_name", nothing), "street"=>coalesce(get(properties, "road_en", nothing), get(properties, "road_fr", nothing)), "active"=>get(properties, "active", nothing), "longitude"=>coords[1], "latitude"=>coords[2])
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

function refresh_open_data(; output_dir=DATA_DIR)
    refresh_trees(output_dir)
    refresh_bikes(output_dir)
    println("Julia refreshed public-data snapshots; Python remains the derived-join fallback.")
end

end
