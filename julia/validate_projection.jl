#!/usr/bin/env julia

using Pkg
Pkg.activate(@__DIR__)
Pkg.instantiate()

include(joinpath(@__DIR__, "src", "TreesSurfaces.jl"))
using .TreesSurfaces
include(joinpath(@__DIR__, "src", "Projection.jl"))
using .Projection

function validate_projection()
    heat = TreesSurfaces.read_json("brussels-tree-heat-sample.json")
    matched = 0
    for row in TreesSurfaces.records(heat)
        column, pixel_row = raster_pixel(
            TreesSurfaces.number(row["latitude"]),
            TreesSurfaces.number(row["longitude"]),
            10_000,
            9_000,
        )
        column == row["heat_pixel_column"] || error("column mismatch for $(row["id"])")
        pixel_row == row["heat_pixel_row"] || error("row mismatch for $(row["id"])")
        matched += 1
    end
    println("Julia heat projection validation passed for $(matched) points")
end

validate_projection()
