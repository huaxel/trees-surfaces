#!/usr/bin/env julia

using Pkg
Pkg.activate(joinpath(@__DIR__, ".."))
Pkg.instantiate()
using JSON3

include(joinpath(@__DIR__, "..", "src", "HeatSeason.jl"))
using .HeatSeason

length(ARGS) <= 1 || error("usage: julia --project=. bin/generate_heat_season.jl [OUTPUT_DIR_OR_JSON]")
data_dir = joinpath(@__DIR__, "..", "data")
source = joinpath(data_dir, "brussels-trees-sample.json")
argument = isempty(ARGS) ? data_dir : first(ARGS)
output = isdir(argument) ? joinpath(argument, HEAT_SEASON_FILENAME) : argument

payload = generate_heat_season(source, output)
summary = payload["region_summary"]
println("Wrote $(length(payload["records"])) tree records over $(summary["cells"]) ERA5 cells to $(output)")
println(JSON3.write(Dict(
    "records" => length(payload["records"]),
    "cells" => summary["cells"],
    "reference_date_season_percentile_min" => summary["reference_date_season_percentile_min"],
    "reference_date_season_percentile_max" => summary["reference_date_season_percentile_max"],
)))