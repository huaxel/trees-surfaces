module HeatSeason

using Dates
using HTTP
using JSON3
using Statistics

include(joinpath(@__DIR__, "IOUtils.jl"))
using .IOUtils

export era5_grid_point, era5_grid_key, validate_era5_daily_payload, validate_grid_probe_payload, season_metrics,
    build_heat_season_payload, generate_heat_season, season_context, archive_request_url, grid_probe_request_url,
    HEAT_SEASON_FILENAME, DAILY_VARIABLES

# The `era5` model is requested explicitly. The archive API's default product is a finer but
# spatially interpolated series whose values differ from this reanalysis by more than a
# degree, and ERA5-Land omits apparent temperature, radiation, and wind entirely, so an
# implicit default would silently change the committed measure.
const ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
const MODEL = "era5"
const GRID_STEP_DEGREES = 0.25
const DAILY_VARIABLES = ("temperature_2m_max", "temperature_2m_min", "apparent_temperature_max", "relative_humidity_2m_mean", "shortwave_radiation_sum", "wind_speed_10m_mean")
const DAILY_UNITS = Dict(
    "temperature_2m_max" => "°C",
    "temperature_2m_min" => "°C",
    "apparent_temperature_max" => "°C",
    "relative_humidity_2m_mean" => "%",
    "shortwave_radiation_sum" => "MJ/m²",
    "wind_speed_10m_mean" => "km/h",
)
const TEMPERATURE_VARIABLES = ("temperature_2m_max", "temperature_2m_min", "apparent_temperature_max")
const PLAUSIBLE_TEMPERATURE_RANGE_C = (-40.0, 45.0)
const SEASON_MONTHS = ("06", "07", "08")
const WINDOW_START_DATE = "2015-01-01"
const WINDOW_END_DATE = "2024-12-31"
const WINDOW_START_YEAR = 2015
const WINDOW_END_YEAR = 2024
const SEASON_DAYS_PER_YEAR = 92
const REFERENCE_DATE = "2016-08-24"
const HOT_DAY_APPARENT_TMAX_C = 30.0
const TROPICAL_NIGHT_TMIN_C = 20.0
const HEAT_SEASON_FILENAME = "brussels-heat-season-sample.json"
const MAX_RESPONSE_BYTES = 20 * 1024 * 1024
const MAX_ATTEMPTS = 4
const RETRY_DELAY_SECONDS = 15
const GRID_NOTE = "ERA5 publishes a $(GRID_STEP_DEGREES)° regular grid (about 28 km north-south and 18 km east-west at Brussels' latitude). Committed tree coordinates are snapped to the nearest grid step, so every point in one cell shares one value and this source cannot resolve intra-urban variation."

require(condition, message) = condition || throw(ErrorException(message))
text(value) = value === nothing ? "" : string(value)
finite_number(value) = value isa Number && !(value isa Bool) && isfinite(Float64(value))

function era5_grid_point(latitude, longitude)
    require(finite_number(latitude) && finite_number(longitude), "ERA5 grid point needs finite coordinates")
    return (
        round(Float64(latitude) / GRID_STEP_DEGREES) * GRID_STEP_DEGREES,
        round(Float64(longitude) / GRID_STEP_DEGREES) * GRID_STEP_DEGREES,
    )
end

era5_grid_key(latitude, longitude) = "$(latitude)/$(longitude)"

function archive_request_url(cells)
    query = join([
        "latitude=" * join([string(cell[1]) for cell in cells], ","),
        "longitude=" * join([string(cell[2]) for cell in cells], ","),
        "start_date=" * WINDOW_START_DATE,
        "end_date=" * WINDOW_END_DATE,
        "daily=" * join(collect(DAILY_VARIABLES), ","),
        "timezone=UTC",
        "models=" * MODEL,
    ], "&")
    return ARCHIVE_URL * "?" * query
end

function grid_probe_request_url(points)
    query = join([
        "latitude=" * join([string(point[1]) for point in points], ","),
        "longitude=" * join([string(point[2]) for point in points], ","),
        "start_date=" * REFERENCE_DATE,
        "end_date=" * REFERENCE_DATE,
        "daily=temperature_2m_max",
        "timezone=UTC",
        "models=" * MODEL,
    ], "&")
    return ARCHIVE_URL * "?" * query
end

# Bounded chunked read, matching the refresh reader: the size limit is enforced while the
# body is streamed rather than after it is buffered. HTTP 429 and 5xx responses are retried,
# because the free archive endpoint throttles bursts of requests.
function get_body(url; attempts = MAX_ATTEMPTS)
    for attempt in 1:attempts
        body = IOBuffer()
        status = 0
        headers = ["Accept-Encoding" => "identity", "User-Agent" => "trees-surfaces-julia-heat-season/1.0"]
        HTTP.open("GET", url, headers; connect_timeout=10, response_header_timeout=30, read_idle_timeout=30) do stream
            response = HTTP.startread(stream)
            status = Int(response.status)
            200 <= status < 300 || return
            buffer = Vector{UInt8}(undef, 64 * 1024)
            total = 0
            while true
                count = readbytes!(stream, buffer)
                count == 0 && break
                total += count
                require(total <= MAX_RESPONSE_BYTES, "response exceeds $(MAX_RESPONSE_BYTES) bytes: $url")
                write(body, @view buffer[1:count])
            end
        end
        200 <= status < 300 && return take!(body)
        retryable = status == 429 || 500 <= status < 600
        if retryable && attempt < attempts
            sleep(RETRY_DELAY_SECONDS)
            continue
        end
        error("HTTP $(status) from $url")
    end
end

function response_payloads(url, expected_points)
    payload = JSON3.read(String(get_body(url)), Any)
    payloads = payload isa AbstractVector ? collect(payload) : Any[payload]
    require(length(payloads) == expected_points, "ERA5 returned $(length(payloads)) point(s) where $(expected_points) were expected")
    return payloads
end

fetch_archive_payloads(cells) = response_payloads(archive_request_url(cells), length(cells))
fetch_archive_grid_probes(points) = response_payloads(grid_probe_request_url(points), length(points))

function validate_grid_probe_payload(payload, latitude, longitude)
    require(payload isa AbstractDict, "ERA5 grid probe response is not a JSON object")
    returned_latitude = get(payload, "latitude", nothing)
    returned_longitude = get(payload, "longitude", nothing)
    require(finite_number(returned_latitude) && finite_number(returned_longitude), "ERA5 grid probe response lacks grid coordinates")
    expected = era5_grid_point(latitude, longitude)
    require(
        isapprox(Float64(returned_latitude), expected[1]; atol = 0.01) && isapprox(Float64(returned_longitude), expected[2]; atol = 0.01),
        "ERA5 snapped tree point $(latitude)/$(longitude) to $(returned_latitude)/$(returned_longitude), not the expected nearest grid cell $(expected)",
    )
    units = get(payload, "daily_units", nothing)
    daily = get(payload, "daily", nothing)
    require(units isa AbstractDict && get(units, "temperature_2m_max", nothing) == "°C", "ERA5 grid probe returned unexpected temperature units")
    require(daily isa AbstractDict && get(daily, "time", Any[]) == [REFERENCE_DATE], "ERA5 grid probe returned an unexpected reference date")
    temperatures = get(daily, "temperature_2m_max", Any[])
    require(temperatures isa AbstractVector && length(temperatures) == 1 && finite_number(first(temperatures)), "ERA5 grid probe lacks a finite reference-day temperature")
    return expected
end

function validate_era5_daily_payload(payload, latitude, longitude)
    require(payload isa AbstractDict, "ERA5 response is not a JSON object")
    returned_latitude = get(payload, "latitude", nothing)
    returned_longitude = get(payload, "longitude", nothing)
    require(finite_number(returned_latitude) && finite_number(returned_longitude), "ERA5 response lacks grid coordinates")
    require(
        isapprox(Float64(returned_latitude), Float64(latitude); atol = 0.01) && isapprox(Float64(returned_longitude), Float64(longitude); atol = 0.01),
        "ERA5 returned grid point $(returned_latitude)/$(returned_longitude) where $(latitude)/$(longitude) was requested",
    )
    units = get(payload, "daily_units", nothing)
    require(units isa AbstractDict, "ERA5 response lacks daily units")
    for variable in DAILY_VARIABLES
        returned = get(units, variable, nothing)
        require(text(returned) == DAILY_UNITS[variable], "ERA5 unit for $variable changed to $(returned); expected $(DAILY_UNITS[variable])")
    end
    daily = get(payload, "daily", nothing)
    require(daily isa AbstractDict, "ERA5 response lacks a daily block")
    times = get(daily, "time", nothing)
    require(times isa AbstractVector && !isempty(times), "ERA5 response lacks daily timestamps")
    expected_days = Dates.value(Date(WINDOW_END_DATE) - Date(WINDOW_START_DATE)) + 1
    require(length(times) == expected_days, "ERA5 window covers $(length(times)) days where $(expected_days) were expected")
    require(text(first(times)) == WINDOW_START_DATE && text(last(times)) == WINDOW_END_DATE, "ERA5 window is $(first(times)) to $(last(times))")

    values = Dict{String, Vector{Float64}}()
    for variable in DAILY_VARIABLES
        column = get(daily, variable, nothing)
        require(column isa AbstractVector && length(column) == length(times), "ERA5 column $variable has an unexpected length")
        numbers = Vector{Float64}(undef, length(times))
        for (index, value) in enumerate(column)
            finite_number(value) || error("ERA5 column $variable contains a missing or non-finite value at $(times[index])")
            numbers[index] = Float64(value)
        end
        values[variable] = numbers
    end

    minimum_temperature, maximum_temperature = PLAUSIBLE_TEMPERATURE_RANGE_C
    for variable in TEMPERATURE_VARIABLES
        for (index, value) in enumerate(values[variable])
            require(
                minimum_temperature <= value <= maximum_temperature,
                "ERA5 column $variable contains an implausible value $(value) °C at $(times[index])",
            )
        end
    end
    require(all(0.0 <= value <= 100.0 for value in values["relative_humidity_2m_mean"]), "ERA5 relative humidity is outside 0-100 %")
    require(all(0.0 <= value <= 40.0 for value in values["shortwave_radiation_sum"]), "ERA5 radiation sum is outside 0-40 MJ/m²")
    require(all(0.0 <= value <= 300.0 for value in values["wind_speed_10m_mean"]), "ERA5 wind speed is outside 0-300 km/h")
    for index in eachindex(times)
        require(
            values["temperature_2m_min"][index] <= values["temperature_2m_max"][index],
            "ERA5 daily minimum exceeds the daily maximum at $(times[index])",
        )
    end
    return (times = [text(time) for time in times], values = values, elevation = get(payload, "elevation", nothing))
end

function season_indices(times)
    indices = [index for (index, time) in enumerate(times) if time[6:7] in SEASON_MONTHS]
    expected = (WINDOW_END_YEAR - WINDOW_START_YEAR + 1) * SEASON_DAYS_PER_YEAR
    require(length(indices) == expected, "ERA5 season covers $(length(indices)) days where $(expected) were expected")
    return indices
end

percentile_below(values, reference) = round(100 * count(value -> value < reference, values) / length(values); digits = 1)

# Use the minimum/competition-rank convention: tied observations share the rank immediately
# after all strictly cooler days (1 + the count below the reference value).

function season_metrics(validated)
    times = validated.times
    daily_values = validated.values
    indices = season_indices(times)
    apparent = daily_values["apparent_temperature_max"]
    seasonal_apparent = apparent[indices]

    year_means = Dict{String, Float64}()
    hot_days = Dict{String, Int}()
    tropical_nights = Dict{String, Int}()
    for year in WINDOW_START_YEAR:WINDOW_END_YEAR
        year_indices = [index for index in indices if times[index][1:4] == string(year)]
        require(length(year_indices) == SEASON_DAYS_PER_YEAR, "ERA5 season year $year covers $(length(year_indices)) days where $(SEASON_DAYS_PER_YEAR) were expected")
        year_means[string(year)] = Statistics.mean(apparent[year_indices])
        hot_days[string(year)] = count(index -> apparent[index] >= HOT_DAY_APPARENT_TMAX_C, year_indices)
        tropical_nights[string(year)] = count(index -> daily_values["temperature_2m_min"][index] >= TROPICAL_NIGHT_TMIN_C, year_indices)
    end

    reference_index = findfirst(==(REFERENCE_DATE), times)
    require(reference_index !== nothing, "ERA5 window does not contain $(REFERENCE_DATE)")
    reference_apparent = apparent[reference_index]
    reference_year = REFERENCE_DATE[1:4]
    reference_season = [apparent[index] for index in indices if times[index][1:4] == reference_year]
    require(length(reference_season) == SEASON_DAYS_PER_YEAR, "ERA5 reference season $(reference_year) is incomplete")
    hottest_season_year = first(sort(collect(keys(year_means)), by = year -> (-year_means[year], year)))

    return Dict{String, Any}(
        "season_days_per_year" => SEASON_DAYS_PER_YEAR,
        "season_days" => length(indices),
        "season_year_count" => length(year_means),
        "seasonal_mean_apparent_tmax_c" => round(Statistics.mean(seasonal_apparent); digits = 2),
        "seasonal_mean_tmax_c" => round(Statistics.mean(daily_values["temperature_2m_max"][indices]); digits = 2),
        "seasonal_mean_tmin_c" => round(Statistics.mean(daily_values["temperature_2m_min"][indices]); digits = 2),
        "seasonal_mean_apparent_tmax_spread_across_years_c" => round(maximum(values(year_means)) - minimum(values(year_means)); digits = 2),
        "hottest_season_year" => hottest_season_year,
        "hottest_season_apparent_tmax_mean_c" => round(year_means[hottest_season_year]; digits = 2),
        "warmest_season_apparent_tmax_c" => round(maximum(seasonal_apparent); digits = 1),
        "hot_days_per_season" => round(Statistics.mean(collect(values(hot_days))); digits = 1),
        "tropical_nights_per_season" => round(Statistics.mean(collect(values(tropical_nights))); digits = 1),
        "reference_date" => REFERENCE_DATE,
        "reference_date_apparent_tmax_c" => round(reference_apparent; digits = 1),
        "reference_date_tmax_c" => round(daily_values["temperature_2m_max"][reference_index]; digits = 1),
        "reference_date_season_mean_apparent_tmax_c" => round(Statistics.mean(reference_season); digits = 2),
        "reference_date_rank_within_season" => count(value -> value < reference_apparent, reference_season) + 1,
        "reference_date_season_percentile" => percentile_below(reference_season, reference_apparent),
        "reference_date_window_percentile" => percentile_below(seasonal_apparent, reference_apparent),
    )
end

function tree_cells(source)
    cells = Dict{String, Tuple{Float64, Float64}}()
    for row in get(source, "records", Any[])
        latitude = get(row, "latitude", nothing)
        longitude = get(row, "longitude", nothing)
        require(finite_number(latitude) && finite_number(longitude), "committed tree $(text(get(row, "id", nothing))) lacks usable coordinates")
        grid = era5_grid_point(latitude, longitude)
        cells[era5_grid_key(grid[1], grid[2])] = grid
    end
    require(!isempty(cells), "committed tree sample is empty")
    return cells
end

function cell_record(key, grid, validated)
    payload = Dict{String, Any}("grid_key" => key, "grid_latitude" => grid[1], "grid_longitude" => grid[2])
    finite_number(validated.elevation) && (payload["elevation_m"] = round(Float64(validated.elevation); digits = 1))
    for (name, value) in season_metrics(validated)
        payload[name] = value
    end
    return payload
end

function build_heat_season_payload(source, cells, request_url; grid_probe_url = "")
    require(!isempty(cells), "cannot build seasonal heat context without ERA5 cells")
    require(!isempty(request_url), "seasonal heat context requires its archive request URL")
    cell_by_key = Dict(text(get(cell, "grid_key", "")) => cell for cell in cells)
    require(length(cell_by_key) == length(cells), "seasonal heat cells contain duplicate grid keys")
    required_cell_keys = ("season_days", "season_year_count", "seasonal_mean_apparent_tmax_c", "seasonal_mean_tmax_c", "seasonal_mean_tmin_c", "hot_days_per_season", "tropical_nights_per_season", "hottest_season_year", "hottest_season_apparent_tmax_mean_c", "warmest_season_apparent_tmax_c", "reference_date_apparent_tmax_c", "reference_date_tmax_c", "reference_date_season_mean_apparent_tmax_c", "reference_date_rank_within_season", "reference_date_season_percentile", "reference_date_window_percentile", "seasonal_mean_apparent_tmax_spread_across_years_c")
    all(all(haskey(cell, name) for name in required_cell_keys) for cell in cells) || error("seasonal heat cell is missing required metrics")
    all(cell["season_days"] == first(cells)["season_days"] && cell["season_year_count"] == first(cells)["season_year_count"] for cell in cells) || error("seasonal heat cells disagree on their season window")
    all(cell["season_year_count"] == WINDOW_END_YEAR - WINDOW_START_YEAR + 1 && cell["season_days"] == cell["season_year_count"] * SEASON_DAYS_PER_YEAR for cell in cells) || error("seasonal heat cells do not match the configured ten-season JJA window")
    records = Any[]
    for tree in get(source, "records", Any[])
        id = text(get(tree, "id", nothing))
        grid = era5_grid_point(get(tree, "latitude", nothing), get(tree, "longitude", nothing))
        key = era5_grid_key(grid[1], grid[2])
        cell = get(cell_by_key, key, nothing)
        require(cell !== nothing, "no ERA5 cell for committed tree $(id)")
        push!(records, Dict{String, Any}(
            "id" => id,
            "grid_key" => key,
            "grid_latitude" => cell["grid_latitude"],
            "grid_longitude" => cell["grid_longitude"],
            "seasonal_mean_apparent_tmax_c" => cell["seasonal_mean_apparent_tmax_c"],
            "reference_date_apparent_tmax_c" => cell["reference_date_apparent_tmax_c"],
            "reference_date_season_percentile" => cell["reference_date_season_percentile"],
        ))
    end
    require(length(records) == 100, "expected 100 committed trees, found $(length(records))")
    require(length(unique(record["id"] for record in records)) == length(records), "committed tree IDs are not unique")

    seasonal_means = [cell["seasonal_mean_apparent_tmax_c"] for cell in cells]
    percentiles = [cell["reference_date_season_percentile"] for cell in cells]
    reference_temperatures = [cell["reference_date_apparent_tmax_c"] for cell in cells]
    hot_days = [cell["hot_days_per_season"] for cell in cells]
    return Dict{String, Any}(
        "source" => "Open-Meteo archive API (ERA5 reanalysis)",
        "dataset_metadata_url" => "https://open-meteo.com/en/docs/historical-weather-api",
        "model" => MODEL,
        "request_url" => request_url,
        "grid_probe_url" => grid_probe_url,
        "source_licence" => "CC BY 4.0",
        "source_credit" => "Weather data by Open-Meteo.com (CC BY 4.0). Contains modified Copernicus Climate Change Service information (ERA5 reanalysis, ECMWF); retrieved through the Open-Meteo archive API.",
        "value_semantics" => "ERA5 reanalysis daily air-temperature and apparent-temperature maxima in degrees Celsius on a $(GRID_STEP_DEGREES)° grid; not a WBGT measurement and not comparable pixel by pixel with the 0–100 WBGT indicator raster",
        "season" => Dict{String, Any}(
            "months" => collect(SEASON_MONTHS),
            "window_start_year" => WINDOW_START_YEAR,
            "window_end_year" => WINDOW_END_YEAR,
            "season_days" => first(cells)["season_days"],
            "season_days_per_year" => SEASON_DAYS_PER_YEAR,
        ),
        "grid" => Dict{String, Any}("requested_step_degrees" => GRID_STEP_DEGREES, "note" => GRID_NOTE),
        "reference_date" => REFERENCE_DATE,
        "method" => "June-August (JJA) is the season, consistent with the committed WBGT reference date. Seasons for $(WINDOW_START_YEAR)-$(WINDOW_END_YEAR) are pooled per ERA5 grid cell: seasonal mean of daily apparent-temperature maxima, mean number of days per season with an apparent-temperature maximum at or above $(HOT_DAY_APPARENT_TMAX_C) °C (a descriptive, not health-warning, threshold), mean number of tropical nights with a daily minimum at or above $(TROPICAL_NIGHT_TMIN_C) °C, and the percentile of the committed WBGT reference date $(REFERENCE_DATE) within its own $(REFERENCE_DATE[1:4]) season.",
        "interpretation_boundary" => "This artifact states how representative the committed single-day WBGT raster is and adds multi-year air-temperature exposure context. It is not an intra-urban heat map, does not replace the raster in the ranking, and is not a health or comfort measurement.",
        "region_summary" => Dict{String, Any}(
            "cells" => length(cells),
            "seasonal_mean_apparent_tmax_min_c" => minimum(seasonal_means),
            "seasonal_mean_apparent_tmax_max_c" => maximum(seasonal_means),
            "seasonal_mean_apparent_tmax_spread_c" => round(maximum(seasonal_means) - minimum(seasonal_means); digits = 2),
            "hot_days_per_season_min" => minimum(hot_days),
            "hot_days_per_season_max" => maximum(hot_days),
            "reference_date_apparent_tmax_min_c" => minimum(reference_temperatures),
            "reference_date_apparent_tmax_max_c" => maximum(reference_temperatures),
            "reference_date_season_percentile_min" => minimum(percentiles),
            "reference_date_season_percentile_max" => maximum(percentiles),
        ),
        "cells" => cells,
        "records" => records,
    )
end

function generate_heat_season(source_path, output_path; fetch_cells = fetch_archive_payloads, fetch_grid_probes = fetch_archive_grid_probes)
    source = JSON3.read(read(source_path, String), Dict{String, Any})
    cells = tree_cells(source)
    records = get(source, "records", Any[])
    probe_points = [(Float64(row["latitude"]), Float64(row["longitude"])) for row in records]
    probe_url = grid_probe_request_url(probe_points)
    probe_payloads = fetch_grid_probes(probe_points)
    require(length(probe_payloads) == length(probe_points), "ERA5 returned $(length(probe_payloads)) grid probe(s) where $(length(probe_points)) were expected")
    for (point, payload) in zip(probe_points, probe_payloads)
        validate_grid_probe_payload(payload, point[1], point[2])
    end
    requested = [cells[key] for key in sort(collect(keys(cells)))]
    payloads = fetch_cells(requested)
    require(length(payloads) == length(requested), "ERA5 returned $(length(payloads)) point(s) where $(length(requested)) were expected")
    cell_records = Any[]
    for (grid, payload) in zip(requested, payloads)
        validated = validate_era5_daily_payload(payload, grid[1], grid[2])
        push!(cell_records, cell_record(era5_grid_key(grid[1], grid[2]), grid, validated))
    end
    payload = build_heat_season_payload(source, cell_records, archive_request_url(requested); grid_probe_url = probe_url)
    atomic_write_json(output_path, payload)
    return payload
end

function season_context(data_dir)
    path = joinpath(data_dir, HEAT_SEASON_FILENAME)
    isfile(path) || return Dict{String, Any}("available" => false)
    payload = JSON3.read(read(path, String), Dict{String, Any})
    cells = get(payload, "cells", Any[])
    require(!isempty(cells), "$(HEAT_SEASON_FILENAME) contains no ERA5 cells")
    summary = get(payload, "region_summary", Dict{String, Any}())
    season = get(payload, "season", Dict{String, Any}())
    return Dict{String, Any}(
        "available" => true,
        "cells" => Int(get(summary, "cells", length(cells))),
        "season_year_count" => Int(get(season, "season_year_count", first(cells)["season_year_count"])),
        "season_days" => Int(get(season, "season_days", first(cells)["season_days"])),
        "window_phrase" => "$(get(season, "window_start_year", WINDOW_START_YEAR))–$(get(season, "window_end_year", WINDOW_END_YEAR))",
        "reference_date" => text(get(payload, "reference_date", "")),
        "reference_percentile_min" => get(summary, "reference_date_season_percentile_min", 0.0),
        "reference_percentile_max" => get(summary, "reference_date_season_percentile_max", 0.0),
        "reference_apparent_min" => get(summary, "reference_date_apparent_tmax_min_c", 0.0),
        "reference_apparent_max" => get(summary, "reference_date_apparent_tmax_max_c", 0.0),
        "seasonal_mean_min" => get(summary, "seasonal_mean_apparent_tmax_min_c", 0.0),
        "seasonal_mean_max" => get(summary, "seasonal_mean_apparent_tmax_max_c", 0.0),
        "seasonal_mean_spread" => get(summary, "seasonal_mean_apparent_tmax_spread_c", 0.0),
        "hot_days_per_season_min" => minimum(cell["hot_days_per_season"] for cell in cells),
        "hot_days_per_season_max" => maximum(cell["hot_days_per_season"] for cell in cells),
        "hottest_season_year" => text(first(cells)["hottest_season_year"]),
        "hottest_season_mean" => round(Statistics.mean(cell["hottest_season_apparent_tmax_mean_c"] for cell in cells); digits = 2),
        "reference_season_mean" => round(Statistics.mean(cell["reference_date_season_mean_apparent_tmax_c"] for cell in cells); digits = 2),
        "reference_rank_min" => minimum(cell["reference_date_rank_within_season"] for cell in cells),
        "reference_rank_max" => maximum(cell["reference_date_rank_within_season"] for cell in cells),
    )
end

end