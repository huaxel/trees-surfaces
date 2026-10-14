#!/usr/bin/env julia

using Pkg
Pkg.activate(joinpath(@__DIR__, ".."))
Pkg.instantiate()
using JSON3

include(joinpath(@__DIR__, "..", "src", "Refresh.jl"))
using .Refresh

output_path = isempty(ARGS) ? joinpath(Refresh.DATA_DIR, Refresh.MANAGED_TREE_CROSSWALK_FILENAME) : first(ARGS)
payload = Refresh.generate_managed_tree_crosswalk(output_path)
println("wrote managed-tree id crosswalk to $(output_path)")
println(JSON3.write(Dict(
    "record_count" => length(payload["records"]),
    "match_radius_m" => payload["match_radius_m"],
)))
