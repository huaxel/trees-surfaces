#!/usr/bin/env julia

using Pkg
Pkg.activate(@__DIR__)
get(ENV, "JULIA_INSTANTIATE", "1") == "1" && Pkg.instantiate()

include(joinpath(@__DIR__, "src", "TreesSurfaces.jl"))
using .TreesSurfaces

port = isempty(ARGS) ? parse(Int, get(ENV, "JULIA_UI_PORT", "8080")) : parse(Int, first(ARGS))
host = get(ENV, "JULIA_UI_HOST", "127.0.0.1")
serve_app(host = host, port = port)
