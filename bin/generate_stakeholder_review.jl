#!/usr/bin/env julia

using Pkg
Pkg.activate(joinpath(@__DIR__, ".."))
Pkg.instantiate()
using JSON3

include(joinpath(@__DIR__, "..", "src", "TreesSurfaces.jl"))
using .TreesSurfaces
include(joinpath(@__DIR__, "..", "src", "Review.jl"))
using .Review

if "--help" in ARGS || "-h" in ARGS
    println("Usage: julia --project=. bin/generate_stakeholder_review.jl [DATA_DIR] [--reset-review]")
    println("  DATA_DIR        directory holding tree-stakeholder-proposal.json and tree-signal-sensitivity.json (default: data/)")
    println("  --reset-review  clear review fields while preserving source-derived provenance columns")
    exit()
end

parsed = Review.parse_stakeholder_review_args(ARGS)
row, compiled = generate_stakeholder_review_artifacts(parsed.dir; reset_review = parsed.reset_review)
println("wrote Julia stakeholder review artifacts to $(parsed.dir)")
println(JSON3.write(Dict("record_count" => compiled["record_count"], "review_status" => get(row, "review_status", ""))))
