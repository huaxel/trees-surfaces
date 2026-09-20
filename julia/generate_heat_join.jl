#!/usr/bin/env julia

using Pkg
Pkg.activate(@__DIR__)
Pkg.instantiate()

include(joinpath(@__DIR__, "src", "Projection.jl"))
using .Projection
include(joinpath(@__DIR__, "src", "Heat.jl"))
using .Heat

length(ARGS) == 3 || error("usage: julia --project=julia julia/generate_heat_join.jl RASTER TREES_JSON OUTPUT_JSON")
records = generate_heat_join(ARGS[1], ARGS[2], ARGS[3])
println("Joined $(length(records)) tree points to heat pixels")
