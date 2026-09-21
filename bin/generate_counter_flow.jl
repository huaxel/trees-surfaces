#!/usr/bin/env julia

using Pkg
Pkg.activate(joinpath(@__DIR__, ".."))
Pkg.instantiate()
using JSON3

include(joinpath(@__DIR__, "..", "src", "TreesSurfaces.jl"))
using .TreesSurfaces
include(joinpath(@__DIR__, "..", "src", "Flow.jl"))
using .Flow

output_dir = isempty(ARGS) ? joinpath(pwd(), "julia-generated") : first(ARGS)
payload = generate_counter_flow_artifact(output_dir)
println("wrote Julia counter-flow artifact to $(output_dir)")
println(JSON3.write(Dict("record_count" => payload["record_count"], "trees_with_measured_flow" => payload["trees_with_measured_flow"])))
