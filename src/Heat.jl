module Heat

using JSON3
using TiffImages
using ..Projection

include(joinpath(@__DIR__, "IOUtils.jl"))
using .IOUtils

export generate_heat_join, validate_raster, heat_join_records

const EXPECTED_WIDTH = 10_000
const EXPECTED_HEIGHT = 9_000
const SOURCE_METADATA_ID = "BRU_ENVI_73b4f29a-cff0-4d6a-a239-cb99d3140531"
const SOURCE_LICENCE = "CC BY 4.0"
const VALUE_SEMANTICS = "source-normalized 0–100 WBGT indicator; value 0 is source NoData, not degrees Celsius"

function gray_byte(pixel)
    round(Int, 255 * Float64(getfield(pixel, 1)))
end

function validate_raster(image)
    height, width = size(image)
    (width, height) == (EXPECTED_WIDTH, EXPECTED_HEIGHT) || error("unexpected raster size $(width)x$(height); expected $(EXPECTED_WIDTH)x$(EXPECTED_HEIGHT)")
    pixel = image[1, 1]
    fieldcount(typeof(pixel)) == 1 || error("expected a grayscale raster")
    sizeof(getfield(pixel, 1)) == 1 || error("expected an 8-bit grayscale raster")
    return width, height
end

function heat_join_records(image, source)
    width, height = validate_raster(image)
    records = Any[]
    for tree in get(source, "records", Any[])
        latitude = Float64(get(tree, "latitude", NaN))
        longitude = Float64(get(tree, "longitude", NaN))
        column, row = Projection.raster_pixel(latitude, longitude, width, height)
        output = Dict{String, Any}(string(key) => value for (key, value) in pairs(tree))
        output["heat_pixel"] = gray_byte(image[row + 1, column + 1])
        output["heat_pixel_column"] = column
        output["heat_pixel_row"] = row
        push!(records, output)
    end
    return records
end

function generate_heat_join(raster_path, trees_path, output_path)
    image = TiffImages.load(raster_path)
    source = JSON3.read(read(trees_path, String), Dict{String, Any})
    records = heat_join_records(image, source)
    IOUtils.atomic_write_json(output_path, Dict(
        "source" => basename(raster_path),
        "source_metadata_id" => SOURCE_METADATA_ID,
        "source_licence" => SOURCE_LICENCE,
        "value_semantics" => VALUE_SEMANTICS,
        "crs" => "EPSG:31370",
        "coordinate_transform" => "WGS84 to Belgian 1972 datum using the EPSG seven-parameter transform, then Belgian Lambert 72 projection",
        "sampling" => "nearest raster pixel at tree point",
        "records" => records,
    ))
    return records
end

end
