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
# The semantics above say 0 is NoData. Recording it as a value would place the tree at the
# coolest end of the sample, which is the opposite of what missing heat data means.
const NODATA_PIXEL = 0

function gray_byte(pixel)
    round(Int, 255 * Float64(getfield(pixel, 1)))
end

function validate_raster(image)
    height, width = size(image)
    (width, height) == (EXPECTED_WIDTH, EXPECTED_HEIGHT) || error("unexpected raster size $(width)x$(height); expected $(EXPECTED_WIDTH)x$(EXPECTED_HEIGHT)")
    pixel = image[1, 1]
    fieldcount(typeof(pixel)) == 1 || error("expected a grayscale raster")
    sizeof(getfield(pixel, 1)) == 1 || error("expected an 8-bit grayscale raster")
    # Substance, not just shape: a blank or error image of the right size and type passes the
    # checks above and would assign one identical value to every tree, which reads as a sample
    # with no spatial variation rather than as a failed input. Sampled on a stride, so this
    # catches a uniform image without scanning all ninety million pixels. It cannot tell a real
    # Belgium raster from a real raster of somewhere else.
    samples = Int[]
    for row in 1:997:height, column in 1:991:width
        push!(samples, gray_byte(image[row, column]))
    end
    length(unique(samples)) > 1 || error(
        "raster is uniform: every sampled pixel is $(first(samples)), so it cannot supply spatial " *
        "heat variation. A blank or error image of the correct size and type is refused here.",
    )
    return width, height
end

function heat_join_records(image, source)
    width, height = validate_raster(image)
    records = Any[]
    for tree in get(source, "records", Any[])
        latitude = Float64(get(tree, "latitude", NaN))
        longitude = Float64(get(tree, "longitude", NaN))
        column, row = Projection.raster_pixel(latitude, longitude, width, height)
        value = gray_byte(image[row + 1, column + 1])
        value == NODATA_PIXEL && error(
            "tree $(string(get(tree, "id", "?"))) samples source NoData at column $(column), row $(row): " *
            "this raster uses 0 for NoData, and recording it would rank the tree as the coolest " *
            "point in the sample instead of as unmeasured.",
        )
        output = Dict{String, Any}(string(key) => value for (key, value) in pairs(tree))
        output["heat_pixel"] = value
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
