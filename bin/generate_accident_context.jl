#!/usr/bin/env julia

using Pkg
Pkg.activate(joinpath(@__DIR__, ".."))
Pkg.instantiate()
using JSON3

include(joinpath(@__DIR__, "..", "src", "TreesSurfaces.jl"))
using .TreesSurfaces
include(joinpath(@__DIR__, "..", "src", "Projection.jl"))
using .Projection
include(joinpath(@__DIR__, "..", "src", "Spatial.jl"))
using .Spatial

output_dir = isempty(ARGS) ? joinpath(pwd(), "julia-generated") : first(ARGS)
payload = generate_accident_context(output_dir)
println("wrote Julia counter accident-context artifact to $(output_dir)")
println(JSON3.write(Dict(
    "record_count" => payload["record_count"],
    "bicycle_accidents_by_year" => payload["bicycle_accidents_by_year"],
)))
