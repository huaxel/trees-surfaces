#!/usr/bin/env julia

using Pkg
Pkg.activate(@__DIR__)
using JSON3
Pkg.instantiate()

include(joinpath(@__DIR__, "src", "TreesSurfaces.jl"))
using .TreesSurfaces
include(joinpath(@__DIR__, "src", "Analysis.jl"))
using .Analysis

println(JSON3.write(signal_summary()))
