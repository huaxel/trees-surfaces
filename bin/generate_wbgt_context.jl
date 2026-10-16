#!/usr/bin/env julia

using Pkg
Pkg.activate(joinpath(@__DIR__, ".."))
Pkg.instantiate()
using JSON3
using HTTP

include(joinpath(@__DIR__, "..", "src", "IOUtils.jl"))
using .IOUtils
include(joinpath(@__DIR__, "..", "src", "Wbgt.jl"))
using .Wbgt

# Download one archive file to a temporary sibling and rename it into place, so an interrupted
# transfer can never leave a truncated file that later reads would treat as a valid archive. The
# body is streamed to disk because each annual file is ~34 MB.
function download(url, path)
    directory = dirname(abspath(path))
    mkpath(directory)
    temporary, io = mktemp(directory)
    closed = false
    try
        HTTP.open("GET", url; connect_timeout = 30, response_header_timeout = 60, read_idle_timeout = 300, redirect = true) do stream
            response = HTTP.startread(stream)
            response.status == 200 || error("HTTP $(response.status) from $(url)")
            written = 0
            buffer = Vector{UInt8}(undef, 64 * 1024)
            while true
                count = readbytes!(stream, buffer)
                count == 0 && break
                written += count
                # Enforce the cap while streaming so a runaway response cannot fill the disk before
                # the post-transfer check runs.
                written <= Wbgt.MAX_RESPONSE_BYTES || error("downloaded archive exceeds $(Wbgt.MAX_RESPONSE_BYTES) bytes from $(url)")
                write(io, @view buffer[1:count])
            end
        end
        close(io)
        closed = true
        Wbgt.validate_archive_download(temporary, url)
        mv(temporary, path; force = true)
    catch
        closed || close(io)
        rm(temporary; force = true)
        rethrow()
    end
    return path
end

function main(arguments)
    if "--help" in arguments || "-h" in arguments
        println("Usage: julia --project=. bin/generate_wbgt_context.jl [--cache DIR] [--data DIR] [--download]")
        println("  --cache DIR   directory holding (or receiving) the annual NetCDF archives")
        println("  --data DIR    data directory containing brussels-trees-sample.json")
        println("  --download    fetch any missing annual archive from VITO before reading")
        println()
        println("The archive is ~34 MB per year across $(Wbgt.ARCHIVE_START_YEAR)–$(Wbgt.ARCHIVE_END_YEAR).")
        println("Files are cached outside git; only derived values are written.")
        return
    end

    index = 1
    cache_dir = joinpath(@__DIR__, "..", ".cache", "urbclim")
    data_dir = joinpath(@__DIR__, "..", "data")
    should_download = false
    while index <= length(arguments)
        argument = arguments[index]
        if argument == "--download"
            should_download = true
            index += 1
        elseif argument in ("--cache", "--data")
            index < length(arguments) || error("$(argument) requires a value")
            argument == "--cache" ? (cache_dir = abspath(arguments[index + 1])) : (data_dir = abspath(arguments[index + 1]))
            index += 2
        else
            error("unknown option: $(argument)")
        end
    end

    trees_path = joinpath(data_dir, "brussels-trees-sample.json")
    isfile(trees_path) || error("committed tree sample not found: $(trees_path)")

    # Carry the balanced-screen top ten into the payload so the artifact can report how the heat
    # period alone changes the screen's membership.
    tree_payload = JSON3.read(read(trees_path, String), Dict{String, Any})
    tree_ids = Set(string(get(tree, "id", "")) for tree in get(tree_payload, "records", Any[]))
    screen_path = joinpath(data_dir, "tree-signal-balanced-screen.csv")
    balanced = Wbgt.balanced_screen_top_ids(screen_path, tree_ids)

    output_path = joinpath(data_dir, Wbgt.WBGT_FILENAME)
    payload = Wbgt.generate_wbgt_context(
        trees_path,
        output_path;
        cache_dir = cache_dir,
        fetch = should_download ? download : nothing,
        extra = Dict{String, Any}("balanced_top_ids" => balanced),
    )

    summary = payload["region_summary"]
    sensitivity = payload["period_sensitivity"]["top_ten_overlap"]
    println("Wrote $(output_path)")
    println("  trees: $(summary["trees"]) in $(summary["distinct_cells"]) distinct 100 m cells")
    println("  reference day $(Wbgt.REFERENCE_DATE) WBGT $(summary["reference_date_wbgt_min_c"])–$(summary["reference_date_wbgt_max_c"]) °C")
    println("  season mean WBGT $(summary["seasonal_mean_wbgt_min_c"])–$(summary["seasonal_mean_wbgt_max_c"]) °C")
    println("  reference day sits at the $(summary["reference_percentile_min"])–$(summary["reference_percentile_max"])th percentile of pooled June–August days")
    println("  top-ten overlap vs balanced screen: reference day $(sensitivity["reference_day_vs_balanced"]), seasonal mean $(sensitivity["seasonal_mean_vs_balanced"]), hot-day count $(sensitivity["hot_days_vs_balanced"])")
end

main(ARGS)
