#!/usr/bin/env julia

using Pkg
Pkg.activate(joinpath(@__DIR__, ".."))
Pkg.instantiate()
using JSON3

include(joinpath(@__DIR__, "..", "src", "TreesSurfaces.jl"))
using .TreesSurfaces
include(joinpath(@__DIR__, "..", "src", "Review.jl"))
using .Review

output_dir = isempty(ARGS) ? TreesSurfaces.DATA_DIR : first(ARGS)
reset_review = "--reset-review" in ARGS
row, compiled = generate_stakeholder_review_artifacts(output_dir; reset_review = reset_review)
println("wrote Julia stakeholder review artifacts to $(output_dir)")
println(JSON3.write(Dict("record_count" => compiled["record_count"], "review_status" => get(row, "review_status", ""))))
