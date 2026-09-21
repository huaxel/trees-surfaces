#!/usr/bin/env julia

using Pkg
Pkg.activate(joinpath(@__DIR__, ".."))
Pkg.instantiate()
using JSON3

include(joinpath(@__DIR__, "..", "src", "TreesSurfaces.jl"))
using .TreesSurfaces
include(joinpath(@__DIR__, "..", "src", "Analysis.jl"))
using .Analysis

output_dir = isempty(ARGS) ? joinpath(pwd(), "julia-generated") : first(ARGS)
report = generate_signal_artifacts(output_dir)
println("wrote Julia signal artifacts to $(output_dir)")
println(JSON3.write(Dict("record_count" => report["record_count"], "output_dir" => output_dir)))
