#!/usr/bin/env julia

using Pkg
Pkg.activate(joinpath(@__DIR__, ".."))
Pkg.instantiate()
using JSON3

include(joinpath(@__DIR__, "..", "src", "TreesSurfaces.jl"))
using .TreesSurfaces
include(joinpath(@__DIR__, "..", "src", "Validation.jl"))
using .Validation

summary = validate_snapshots()
println(JSON3.write(summary))
println("Julia snapshot validation passed")
