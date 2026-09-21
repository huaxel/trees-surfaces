#!/usr/bin/env julia

using Pkg
Pkg.activate(joinpath(@__DIR__, ".."))
Pkg.instantiate()
using JSON3

include(joinpath(@__DIR__, "..", "src", "TreesSurfaces.jl"))
using .TreesSurfaces
include(joinpath(@__DIR__, "..", "src", "Spatial.jl"))
using .Spatial

output_dir = isempty(ARGS) ? joinpath(pwd(), "julia-generated") : first(ARGS)
payload = generate_tree_mobility_join(output_dir)
println("wrote Julia nearest-counter artifact to $(output_dir)")
println(JSON3.write(Dict("record_count" => length(payload["records"]))))
