#!/usr/bin/env julia

if ARGS == ["--help"] || ARGS == ["-h"]
    println("Usage: julia --project=. bin/compare_wbgt_mean_max.jl MEAN_2016.nc MAXIMUM_2016.nc OUTPUT_DIR")
    println("Local inputs only; no downloads, package installation, licence clearance or operational ranking changes.")
    exit(0)
end
length(ARGS) == 3 || error("expected MEAN_2016.nc MAXIMUM_2016.nc OUTPUT_DIR; use --help")
include(joinpath(@__DIR__, "..", "src", "WbgtComparison.jl"))
using .WbgtComparison
report = generate(abspath(ARGS[1]), abspath(ARGS[2]),
    joinpath(@__DIR__, "..", "data", "brussels-trees-sample.json"), abspath(ARGS[3]))
println("Wrote local-only mean/maximum comparison for $(report["cells"]) cells to $(abspath(ARGS[3]))")
println("VITO reuse terms remain unresolved; this output does not establish redistribution permission.")
