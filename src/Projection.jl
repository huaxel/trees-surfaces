module Projection

export wgs84_to_lambert72, raster_pixel

const WGS84_A = 6378137.0
const WGS84_F = 1 / 298.257223563
const A = 6378388.0
const F_LOCAL = 1 / 297.0
const E = sqrt(F_LOCAL * (2 - F_LOCAL))
const DATUM_TRANSLATION = (-106.8686, 52.2978, -103.7239)
const DATUM_ROTATION = deg2rad.((0.3366 / 3600, -0.457 / 3600, 1.8422 / 3600))
const DATUM_SCALE = -1.2747e-6
const LAT_0 = deg2rad(90.0)
const LON_0 = deg2rad(4.367486666666666)
const LAT_1 = deg2rad(49.8333339)
const LAT_2 = deg2rad(51.16666723333333)
const X_0 = 150000.013
const Y_0 = 5400088.438
const PIXEL_SIZE = 2.0
const ORIGIN_X = 140000.0
const ORIGIN_Y = 178000.0

m(latitude) = cos(latitude) / sqrt(1 - E^2 * sin(latitude)^2)
t(latitude) = tan(pi / 4 - latitude / 2) / ((1 - E * sin(latitude)) / (1 + E * sin(latitude)))^(E / 2)
const N = log(m(LAT_1) / m(LAT_2)) / log(t(LAT_1) / t(LAT_2))
const F = m(LAT_1) / (N * t(LAT_1)^N)
const RHO_0 = A * F * t(LAT_0)^N

function geodetic_to_ecef(latitude, longitude, semi_major, flattening)
    eccentricity_squared = flattening * (2 - flattening)
    radius = semi_major / sqrt(1 - eccentricity_squared * sin(latitude)^2)
    return (
        radius * cos(latitude) * cos(longitude),
        radius * cos(latitude) * sin(longitude),
        radius * (1 - eccentricity_squared) * sin(latitude),
    )
end

function solve_3x3(matrix, values)
    rows = [Float64[matrix[index, 1], matrix[index, 2], matrix[index, 3], values[index]] for index in 1:3]
    for column in 1:3
        pivot_offset = findmax(abs.(getindex.(rows[column:3], column)))[2]
        pivot = column + pivot_offset - 1
        rows[column], rows[pivot] = rows[pivot], rows[column]
        divisor = rows[column][column]
        rows[column] ./= divisor
        for index in 1:3
            index == column && continue
            factor = rows[index][column]
            rows[index] .-= factor .* rows[column]
        end
    end
    return (rows[1][4], rows[2][4], rows[3][4])
end

function ecef_to_geodetic(x, y, z, semi_major, flattening)
    eccentricity_squared = flattening * (2 - flattening)
    longitude = atan(y, x)
    horizontal = hypot(x, y)
    latitude = atan(z, horizontal * (1 - eccentricity_squared))
    for _ in 1:10
        radius = semi_major / sqrt(1 - eccentricity_squared * sin(latitude)^2)
        updated = atan(z + eccentricity_squared * radius * sin(latitude), horizontal)
        if abs(updated - latitude) < 1e-14
            latitude = updated
            break
        end
        latitude = updated
    end
    return latitude, longitude
end

function wgs84_to_belgian72(latitude, longitude)
    wgs84 = geodetic_to_ecef(deg2rad(latitude), deg2rad(longitude), WGS84_A, WGS84_F)
    translated = ntuple(index -> wgs84[index] - DATUM_TRANSLATION[index], 3)
    rotation_x, rotation_y, rotation_z = DATUM_ROTATION
    scale = 1 + DATUM_SCALE
    matrix = [
        scale -rotation_z rotation_y
        rotation_z scale -rotation_x
        -rotation_y rotation_x scale
    ]
    local_ecef = solve_3x3(matrix, translated)
    return ecef_to_geodetic(local_ecef[1], local_ecef[2], local_ecef[3], A, F_LOCAL)
end

function wgs84_to_lambert72(latitude, longitude)
    local_latitude, local_longitude = wgs84_to_belgian72(latitude, longitude)
    rho = A * F * t(local_latitude)^N
    theta = N * (local_longitude - LON_0)
    return X_0 + rho * sin(theta), Y_0 + RHO_0 - rho * cos(theta)
end

function raster_pixel(latitude, longitude, width, height)
    x, y = wgs84_to_lambert72(latitude, longitude)
    column = floor(Int, (x - ORIGIN_X) / PIXEL_SIZE)
    row = floor(Int, (ORIGIN_Y - y) / PIXEL_SIZE)
    0 <= column < width && 0 <= row < height || error("point outside raster: $(latitude),$(longitude) -> $(x),$(y)")
    return column, row
end

end
