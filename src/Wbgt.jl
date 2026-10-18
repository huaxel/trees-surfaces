module Wbgt

# Multi-date, 100 m heat context from the VITO UrbClim daily archive.
#
# The committed ranking input is a single-day Brussels Environment WBGT indicator raster that
# VITO produced with the same urban climate model (UrbClim) at the same 100 m resolution. VITO
# publishes the multi-date upstream of that product as daily NetCDF series for 2008–2017, which
# is what makes the "one representative hot day" claim testable rather than a limitation.
#
# This module reads those NetCDF files, samples the committed tree points, and reports how the
# committed reference day sits inside a multi-year distribution. It never changes the ranking.

using Dates
using HDF5
using JSON3
using Statistics

include(joinpath(@__DIR__, "IOUtils.jl"))
using .IOUtils

export wgs84_to_laea_europe, archive_filename, archive_url, read_wbgt_year, sample_tree_points,
    season_indices, tree_season_metrics, build_wbgt_payload, generate_wbgt_context,
    load_wbgt_years, balanced_screen_top_ids, context_summary, WBGT_FILENAME, ARCHIVE_BASE_URL, REFERENCE_DATE, SEASON_MONTHS

const ARCHIVE_BASE_URL = "https://provide.marvin.vito.be/ftp/compressed_daily/Brussels"
const ARCHIVE_START_YEAR = 2008
const ARCHIVE_END_YEAR = 2017
const REFERENCE_DATE = "2016-08-24"
const SEASON_MONTHS = ("06", "07", "08")
const WBGT_FILENAME = "brussels-heat-wbgt-sample.json"
const EXPECTED_SIZE = (301, 301)
const GRID_STEP_METRES = 100.0
const HOT_DAY_WBGT_C = 26.0
const PLAUSIBLE_WBGT_RANGE_C = (-20.0, 45.0)
const MIN_ARCHIVE_BYTES = 1024 * 1024
const MAX_RESPONSE_BYTES = 128 * 1024 * 1024

# --- EPSG:3035 (ETRS89-extended / LAEA Europe) -------------------------------------------------
#
# The archive declares EPSG:3035. This mirrors PROJ's oblique ellipsoidal LAEA exactly: PROJ
# scales by the semi-major axis outside the projection step and, in the oblique case, uses
# distinct x/y scale constants. Using a single shared constant places points up to ~169 m off,
# which is more than one 100 m cell.

const LAEA_A = 6378137.0
const LAEA_E2 = 0.00669438002290
const LAEA_E = sqrt(LAEA_E2)
const LAEA_LAT0 = deg2rad(52.0)
const LAEA_LON0 = 10.0
const LAEA_FALSE_EASTING = 4321000.0
const LAEA_FALSE_NORTHING = 3210000.0

function authalic_q(latitude)
    sine = sin(latitude)
    return (1 - LAEA_E2) * (sine / (1 - LAEA_E2 * sine^2) - (1 / (2 * LAEA_E)) * log((1 - LAEA_E * sine) / (1 + LAEA_E * sine)))
end

const LAEA_QP = authalic_q(pi / 2)
const LAEA_Q0 = authalic_q(LAEA_LAT0)
const LAEA_RQ = sqrt(0.5 * LAEA_QP)
const LAEA_BETA0 = asin(LAEA_Q0 / LAEA_QP)
const LAEA_SINB1 = sin(LAEA_BETA0)
const LAEA_COSB1 = cos(LAEA_BETA0)
const LAEA_DD = cos(LAEA_LAT0) / (sqrt(1 - LAEA_E2 * sin(LAEA_LAT0)^2) * LAEA_RQ * LAEA_COSB1)
const LAEA_XMF = LAEA_RQ * LAEA_DD
const LAEA_YMF = LAEA_RQ / LAEA_DD

function wgs84_to_laea_europe(latitude, longitude)
    (isfinite(latitude) && isfinite(longitude)) || error("LAEA conversion needs finite coordinates")
    beta = asin(authalic_q(deg2rad(latitude)) / LAEA_QP)
    delta = longitude - LAEA_LON0
    while delta > 180.0
        delta -= 360.0
    end
    while delta < -180.0
        delta += 360.0
    end
    radians_delta = deg2rad(delta)
    cosine_beta = cos(beta)
    sine_beta = sin(beta)
    denominator = 1.0 + LAEA_SINB1 * sine_beta + LAEA_COSB1 * cosine_beta * cos(radians_delta)
    denominator > 0 || error("point falls outside the LAEA projection domain: $(latitude),$(longitude)")
    scale = sqrt(2.0 / denominator)
    x = LAEA_FALSE_EASTING + LAEA_A * LAEA_XMF * scale * cosine_beta * sin(radians_delta)
    y = LAEA_FALSE_NORTHING + LAEA_A * LAEA_YMF * scale * (LAEA_COSB1 * sine_beta - LAEA_SINB1 * cosine_beta * cos(radians_delta))
    return x, y
end

# --- archive access ---------------------------------------------------------------------------

archive_filename(year) = "WBGT_year_daily_max_$(year).nc"
archive_url(year; base = ARCHIVE_BASE_URL) = "$(base)/$(archive_filename(year))"

# A downloaded archive must look like a real annual NetCDF file: each is ~34 MB, so a tiny file
# means a truncated or error response, and an oversized one means the transfer ran away. The
# upper bound is also enforced while streaming in `bin/generate_wbgt_context.jl` so an unlimited
# response cannot fill the disk before this final check runs.
function validate_archive_download(path, source)
    bytes = filesize(path)
    bytes >= MIN_ARCHIVE_BYTES || error("downloaded archive $(source) is implausibly small: $(bytes) bytes")
    bytes <= MAX_RESPONSE_BYTES || error("downloaded archive $(source) exceeds $(MAX_RESPONSE_BYTES) bytes: $(bytes)")
    return bytes
end

function validate_daily_time_offsets(raw_time, filename)
    all(value -> value isa Real && isfinite(Float64(value)) && isinteger(value), raw_time) || error("$(filename) has non-integer or non-finite daily time coordinates")
    time = Int64.(raw_time)
    isempty(time) && error("$(filename) contains no daily time coordinates")
    time == collect(first(time):last(time)) || error("$(filename) has missing, duplicate, or unordered daily time coordinates")
    return time
end

function validate_calendar_year_coverage(dates, year, filename)
    expected_dates = [Dates.format(date, dateformat"yyyy-mm-dd") for date in Date(year, 1, 1):Day(1):Date(year, 12, 31)]
    dates == expected_dates || error("$(filename) does not contain complete daily coverage for $(year)")
    return nothing
end

function validate_grid_axis(axis, name, filename)
    length(axis) >= 2 || error("$(filename) has too few coordinates on the $(name) axis")
    all(isfinite, axis) || error("$(filename) has non-finite coordinates on the $(name) axis")
    all(step -> isapprox(step, GRID_STEP_METRES; atol = 1e-6), diff(axis)) || error("$(filename) $(name) axis is not a regular increasing $(GRID_STEP_METRES) m grid")
    return nothing
end

# Read one annual NetCDF file. Only the pieces this module needs are pulled out: the declared
# CRS, the projected grid axes, the day offsets and the WBGT cube. HDF5 presents the NetCDF
# datasets in reversed axis order, so WBGT arrives as (x, y, time).
function read_wbgt_year(path)
    isfile(path) || error("WBGT archive file is missing: $(path)")
    h5open(path, "r") do handle
        crs = haskey(attrs(handle), "crs") ? string(attrs(handle)["crs"]) : ""
        occursin("3035", crs) || error("$(basename(path)) declares CRS $(crs); EPSG:3035 was expected")
        for dataset in ("x", "y", "time", "WBGT")
            haskey(handle, dataset) || error("$(basename(path)) is missing the $(dataset) dataset")
        end
        x = Float64.(read(handle["x"]))
        y = Float64.(read(handle["y"]))
        time = validate_daily_time_offsets(read(handle["time"]), basename(path))
        wbgt_dataset = handle["WBGT"]
        cube = Float64.(read(wbgt_dataset))
        wbgt_attributes = attrs(wbgt_dataset)
        scalar_attribute(value) = value isa AbstractArray ? first(value) : value
        units = string(scalar_attribute(wbgt_attributes["units"]))
        units == "°C" || error("$(basename(path)) declares WBGT units $(units); °C was expected")
        scale_factor = haskey(wbgt_attributes, "scale_factor") ? Float64(scalar_attribute(wbgt_attributes["scale_factor"])) : 1.0
        add_offset = haskey(wbgt_attributes, "add_offset") ? Float64(scalar_attribute(wbgt_attributes["add_offset"])) : 0.0
        isfinite(scale_factor) && scale_factor > 0 || error("$(basename(path)) has an invalid WBGT scale_factor")
        isfinite(add_offset) || error("$(basename(path)) has an invalid WBGT add_offset")
        cube .= cube .* scale_factor .+ add_offset
        # Day offsets are relative to a base declared in the variable attribute, so read the base
        # rather than assuming 1 January of the file's nominal year.
        time_units = string(attrs(handle["time"])["units"])
        matched = match(r"days since (\d{4}-\d{2}-\d{2})", time_units)
        matched === nothing && error("$(basename(path)) declares an unsupported time unit: $(time_units)")
        base_date = Date(matched.captures[1])
        size(cube) == (length(x), length(y), length(time)) || error(
            "$(basename(path)) has WBGT shape $(size(cube)) inconsistent with x=$(length(x)), y=$(length(y)), time=$(length(time))",
        )
        (length(x), length(y)) == EXPECTED_SIZE || error(
            "$(basename(path)) grid is $(length(x))x$(length(y)); expected $(EXPECTED_SIZE[1])x$(EXPECTED_SIZE[2])",
        )
        validate_grid_axis(x, "x", basename(path))
        validate_grid_axis(y, "y", basename(path))
        dates = [Dates.format(base_date + Day(offset), dateformat"yyyy-mm-dd") for offset in time]
        return (x = x, y = y, dates = dates, wbgt = cube, time_units = time_units, units = units, scale_factor = scale_factor)
    end
end

function grid_index(axis, value)
    # Coordinate axes are monotonically increasing, so a binary search gives the exact cell.
    index = searchsortedfirst(axis, value)
    index = clamp(index, 1, length(axis))
    # Pick whichever neighbouring cell centre is actually closer, so points between centres are
    # assigned to the nearest 100 m cell rather than always rounding one way.
    if index > 1
        previous = index - 1
        if abs(axis[previous] - value) <= abs(axis[index] - value)
            index = previous
        end
    end
    return index
end

function sample_tree_points(archive, trees; envelope = (50.7, 51.0, 4.1, 4.7))
    minimum_latitude, maximum_latitude, minimum_longitude, maximum_longitude = envelope
    records = Any[]
    for tree in trees
        id = string(get(tree, "id", ""))
        isempty(id) && error("tree record is missing an id")
        latitude = Float64(get(tree, "latitude", NaN))
        longitude = Float64(get(tree, "longitude", NaN))
        (isfinite(latitude) && isfinite(longitude)) || error("tree $(id) lacks finite coordinates")
        minimum_latitude <= latitude <= maximum_latitude || error("tree $(id) latitude $(latitude) is outside the Brussels envelope")
        minimum_longitude <= longitude <= maximum_longitude || error("tree $(id) longitude $(longitude) is outside the Brussels envelope")
        x, y = wgs84_to_laea_europe(latitude, longitude)
        column = grid_index(archive.x, x)
        row = grid_index(archive.y, y)
        offset_east = x - archive.x[column]
        offset_north = y - archive.y[row]
        half_step = GRID_STEP_METRES / 2
        abs(offset_east) <= half_step + 1e-6 || error("tree $(id) falls outside the WBGT grid on the x axis")
        abs(offset_north) <= half_step + 1e-6 || error("tree $(id) falls outside the WBGT grid on the y axis")
        push!(records, Dict{String, Any}(
            "id" => id,
            "column" => column,
            "row" => row,
            "cell_x" => archive.x[column],
            "cell_y" => archive.y[row],
            "offset_east_m" => round(offset_east; digits = 1),
            "offset_north_m" => round(offset_north; digits = 1),
        ))
    end
    return records
end

season_indices(dates, year) = [index for (index, date) in enumerate(dates) if date[1:4] == string(year) && date[6:7] in SEASON_MONTHS]

function reference_index(dates, reference_date = REFERENCE_DATE)
    index = findfirst(==(reference_date), dates)
    index === nothing && error("WBGT archive does not contain the reference date $(reference_date)")
    return index
end

# --- aggregation ------------------------------------------------------------------------------

# Per-tree metrics over the pooled archive. `days` is (day, tree) WBGT in °C, in archive order.
function tree_season_metrics(records, days, dates)
    minimum_temperature, maximum_temperature = PLAUSIBLE_WBGT_RANGE_C
    for value in days
        isfinite(value) || error("WBGT archive contains a non-finite value")
        minimum_temperature <= value <= maximum_temperature || error("WBGT value $(value) °C is outside the plausible range")
    end
    isempty(dates) && error("WBGT archive contains no days")
    reference_row = reference_index(dates)
    season_rows = [index for (index, date) in enumerate(dates) if date[6:7] in SEASON_MONTHS]
    isempty(season_rows) && error("WBGT archive contains no June–August days")
    seasonal = days[season_rows, :]
    years = sort(unique(date[1:4] for date in dates[season_rows]))

    metrics = Any[]
    for (position, record) in enumerate(records)
        column = seasonal[:, position]
        # Reference-day value and where that day sits in the pooled distribution.
        reference_value = Float64(days[reference_row, position])
        ranked = sort(column)
        below = count(value -> value < reference_value, column)
        year_means = Dict{String, Float64}()
        for year in years
            # `season_rows` holds absolute day indices, while `seasonal` is the June–August
            # submatrix, so translate through the seasonal position rather than indexing directly.
            rows = [position_in_season for (position_in_season, day) in enumerate(season_rows) if dates[day][1:4] == year]
            year_means[year] = mean(seasonal[rows, position])
        end
        hottest_year = first(sort(collect(keys(year_means)), by = year -> (-year_means[year], year)))
        push!(metrics, Dict{String, Any}(
            "id" => record["id"],
            "column" => record["column"],
            "row" => record["row"],
            "cell_x" => record["cell_x"],
            "cell_y" => record["cell_y"],
            "reference_date" => REFERENCE_DATE,
            "reference_date_wbgt_c" => round(reference_value; digits = 2),
            "seasonal_mean_wbgt_c" => round(mean(column); digits = 2),
            "seasonal_max_wbgt_c" => round(maximum(column); digits = 2),
            "seasonal_p90_wbgt_c" => round(ranked[clamp(ceil(Int, 0.9 * length(ranked)), 1, length(ranked))]; digits = 2),
            "seasonal_min_wbgt_c" => round(minimum(column); digits = 2),
            "hot_days_per_season" => round(count(value -> value >= HOT_DAY_WBGT_C, column) / length(years); digits = 2),
            "reference_rank_in_season" => below + 1,
            "reference_percentile_in_season" => round(100 * below / length(column); digits = 1),
            "hottest_season_year" => hottest_year,
            "hottest_season_mean_wbgt_c" => round(year_means[hottest_year]; digits = 2),
        ))
    end
    return metrics
end

function top_ids(metrics, key, count = 10)
    ordered = sort(metrics, by = row -> (-Float64(row[key]), row["id"]))
    return [row["id"] for row in ordered[1:min(count, length(ordered))]]
end

function overlap(left, right)
    return length(intersect(Set(left), Set(right)))
end

function build_wbgt_payload(metrics, years; archive_urls = String[], extra = Dict{String, Any}())
    isempty(metrics) && error("cannot build a WBGT context without tree metrics")
    length(unique(row["id"] for row in metrics)) == length(metrics) || error("WBGT metrics contain duplicate tree IDs")

    reference_values = [Float64(row["reference_date_wbgt_c"]) for row in metrics]
    seasonal_means = [Float64(row["seasonal_mean_wbgt_c"]) for row in metrics]
    hot_days = [Float64(row["hot_days_per_season"]) for row in metrics]
    percentiles = [Float64(row["reference_percentile_in_season"]) for row in metrics]
    cells = Set((row["column"], row["row"]) for row in metrics)

    balanced = get(extra, "balanced_top_ids", String[])
    payload = Dict{String, Any}(
        "source" => "VITO UrbClim daily 100 m WBGT archive for Brussels",
        "source_organisation" => "VITO (Flemish Institute for Technological Research), UrbClim model (De Ridder et al., 2015)",
        "related_publication" => "Souverijns et al. 2026, Data in Brief 65, 112497, doi 10.1016/j.dib.2026.112497",
        "archive_base_url" => ARCHIVE_BASE_URL,
        "source_page" => "https://provide.marvin.vito.be/ftp/compressed_daily/",
        "archive_urls" => archive_urls,
        "recommended_citations" => [
            "De Ridder, K., Lauwaet, D., Maiheu, B. (2015). UrbClim - A fast urban boundary layer climate model. Urban Climate 12, 21–48. doi:10.1016/j.uclim.2015.01.001",
            "Souverijns, N. et al. (2026). 100m climate and heat stress data up to 2100 for 142 cities around the globe. Data in Brief 65, 112497. doi:10.1016/j.dib.2026.112497",
        ],
        "value_semantics" => "UrbClim 2 m Wet Bulb Globe Temperature, degrees Celsius, daily maximum, on a 100 m grid in EPSG:3035; computed with the Liljegren et al. (2008) method following ISO 7243",
        "crs" => "EPSG:3035",
        "grid" => Dict{String, Any}(
            "columns" => EXPECTED_SIZE[1],
            "rows" => EXPECTED_SIZE[2],
            "step_metres" => GRID_STEP_METRES,
            "note" => "Nearest 100 m cell at each tree point; the sampled trees fall into $(length(cells)) distinct cells.",
        ),
        "reference_date" => REFERENCE_DATE,
        "window" => Dict{String, Any}(
            "start_year" => minimum(years),
            "end_year" => maximum(years),
            "years" => collect(years),
            "months" => collect(SEASON_MONTHS),
            "seasons" => length(years),
        ),
        "method" => "Daily maximum WBGT is pooled across June–August seasons for $(minimum(years))–$(maximum(years)). Reported per tree: the committed reference day's value, the seasonal mean, maximum and 90th percentile, the mean number of June–August days per season at or above $(HOT_DAY_WBGT_C) °C, and where the reference day ranks inside the pooled June–August distribution.",
        "interpretation_boundary" => "This daily-maximum WBGT archive is from the same UrbClim model family and 100 m grid as the committed ranking raster, but it reports °C daily maxima while that raster is a normalized 0–100 indicator for a 24-hour mean scenario. It can test sensitivity to heat-period choice, but its values are not interchangeable with the raster and it does not replace the ranking input. The $(minimum(years))–$(maximum(years)) window cannot show future climate change.",
        "region_summary" => Dict{String, Any}(
            "trees" => length(metrics),
            "distinct_cells" => length(cells),
            "reference_date_wbgt_min_c" => minimum(reference_values),
            "reference_date_wbgt_max_c" => maximum(reference_values),
            "reference_date_wbgt_spread_c" => round(maximum(reference_values) - minimum(reference_values); digits = 2),
            "seasonal_mean_wbgt_min_c" => minimum(seasonal_means),
            "seasonal_mean_wbgt_max_c" => maximum(seasonal_means),
            "seasonal_mean_wbgt_spread_c" => round(maximum(seasonal_means) - minimum(seasonal_means); digits = 2),
            "hot_days_per_season_min" => minimum(hot_days),
            "hot_days_per_season_max" => maximum(hot_days),
            "reference_percentile_min" => minimum(percentiles),
            "reference_percentile_max" => maximum(percentiles),
            "reference_percentile_mean" => round(mean(percentiles); digits = 1),
        ),
        "period_sensitivity" => Dict{String, Any}(
            "balanced_top_ten_ids" => balanced,
            "note" => "Cross-screen overlaps compare each VITO heat-only alternative with the current balanced raster-plus-proximity screen; they are descriptive and combine differences in WBGT output semantics, heat period and scoring. The reference-day versus seasonal-mean overlap compares two aggregations of the same VITO daily-maximum series and more directly describes temporal sensitivity. None of these comparisons selects a ranking.",
            "top_ten_overlap" => Dict{String, Any}(
                "reference_day_vs_balanced" => overlap(top_ids(metrics, "reference_date_wbgt_c"), balanced),
                "seasonal_mean_vs_balanced" => overlap(top_ids(metrics, "seasonal_mean_wbgt_c"), balanced),
                "seasonal_p90_vs_balanced" => overlap(top_ids(metrics, "seasonal_p90_wbgt_c"), balanced),
                "hot_days_vs_balanced" => overlap(top_ids(metrics, "hot_days_per_season"), balanced),
                "seasonal_mean_vs_reference_day" => overlap(top_ids(metrics, "seasonal_mean_wbgt_c"), top_ids(metrics, "reference_date_wbgt_c")),
            ),
        ),
        "licence_review" => Dict{String, Any}(
            "status" => "unresolved",
            "detail" => "The archive page asks users to cite both De Ridder et al. (2015) and Souverijns et al. (2026), but states no licence or redistribution terms, and the annual NetCDF files carry no licence attribute: their global attributes are only crs, title, institution (VITO), creator and source (UrbClim). Two related records do not transfer their terms to this archive. The Souverijns et al. (2026) decadal 2010–2100 indicator set is CC BY 4.0, and the Copernicus Climate Data Store record 'Climate variables for cities in Europe from 2008 to 2017' (sis-urban-climate-cities, deprecated 2024-05-10) is CC-BY-4.0 with Brussels among its 100 cities and 2008–2017 coverage — but that record contains hourly air temperature, specific humidity, relative humidity and wind speed, and no WBGT, while this archive adds WBGT, daily aggregation and further cities. Confirm the daily-file and derived-value terms with VITO (urbclim@vito.be) before external reuse.",
            "related_records" => Any[
                Dict{String, Any}(
                    "name" => "Copernicus Climate Data Store: Climate variables for cities in Europe from 2008 to 2017",
                    "catalogue_record" => "https://cds.climate.copernicus.eu/api/catalogue/v1/collections/sis-urban-climate-cities",
                    "licence" => "CC-BY-4.0",
                    "covers" => "Hourly air temperature, specific humidity, relative humidity and wind speed for 100 European cities including Brussels, 2008–2017; contains no WBGT",
                    "status" => "Deprecated on the CDS on 2024-05-10; VITO now serves the historical 2008–2017 archive itself",
                    "applies_to_this_archive" => false,
                ),
                Dict{String, Any}(
                    "name" => "Souverijns et al. (2026) decadal climate and heat-stress indicator set",
                    "doi" => "10.5281/zenodo.13361538",
                    "licence" => "CC BY 4.0",
                    "covers" => "Decadal 2010–2100 indicators (GeoTIFF and NetCDF) for 142 cities, not the daily 2008–2017 files",
                    "status" => "Separate record",
                    "applies_to_this_archive" => false,
                ),
            ],
        ),
        "records" => metrics,
    )
    for (key, value) in extra
        key == "balanced_top_ids" && continue
        payload[key] = value
    end
    return payload
end

# --- orchestration ----------------------------------------------------------------------------

# Load the annual files. Tree points are sampled once against the first year's grid and the
# indices are reused, because the archive grid is identical across years. Annual day counts vary
# (365 or 366), so years are pooled onto one ordered date axis rather than compared for equal
# length.
function load_wbgt_years(cache_dir, trees; years = ARCHIVE_START_YEAR:ARCHIVE_END_YEAR, fetch = nothing)
    year_list = collect(years)
    !isempty(year_list) && all(year -> year isa Integer && !(year isa Bool), year_list) || error("WBGT years must be non-empty integer values")
    year_list == collect(first(year_list):last(year_list)) || error("WBGT years must be a contiguous ascending range")
    indices = nothing
    first_year_x = nothing
    first_year_y = nothing
    dates = String[]
    values = Matrix{Float64}(undef, 0, length(trees))
    for year in year_list
        path = joinpath(cache_dir, archive_filename(year))
        if !isfile(path)
            fetch === nothing && error("missing cached archive $(path); pass fetch or run the download step")
            mkpath(cache_dir)
            fetch(archive_url(year), path)
        end
        archive = read_wbgt_year(path)
        validate_calendar_year_coverage(archive.dates, year, archive_filename(year))
        if indices === nothing
            indices = sample_tree_points(archive, trees)
            first_year_x = archive.x
            first_year_y = archive.y
        else
            # The grid must match across years, otherwise a cached index would silently address a
            # different cell in a later file.
            archive.x == first_year_x || error("$(archive_filename(year)) has a different x grid from $(archive_filename(first(year_list)))")
            archive.y == first_year_y || error("$(archive_filename(year)) has a different y grid from $(archive_filename(first(year_list)))")
        end
        annual = Matrix{Float64}(undef, length(archive.dates), length(trees))
        for (position, record) in enumerate(indices)
            annual[:, position] = Float64.(archive.wbgt[record["column"], record["row"], :])
        end
        startswith(archive.dates[1], "$(year)-") || error("$(archive_filename(year)) does not start in $(year)")
        append!(dates, archive.dates)
        values = vcat(values, annual)
    end
    isempty(dates) && error("no WBGT years were loaded")
    length(unique(dates)) == length(dates) || error("pooled WBGT years contain a duplicated date")
    return (dates = dates, years = year_list, values = values, indices = indices)
end

function balanced_screen_top_ids(path, tree_ids)
    isfile(path) || error("balanced-screen CSV is missing: $(path)")
    lines = readlines(path)
    isempty(lines) && error("balanced-screen CSV is empty: $(path)")
    ids = String[]
    for line in Iterators.take(lines[2:end], 10)
        isempty(strip(line)) && continue
        fields = split(line, ','; limit = 3)
        length(fields) >= 2 || error("malformed balanced-screen CSV row: $(line)")
        push!(ids, strip(fields[2]))
    end
    length(ids) == 10 || error("balanced-screen CSV contains $(length(ids)) top-ten rows; expected 10")
    length(unique(ids)) == 10 || error("balanced-screen top ten contains duplicate IDs")
    all(id -> id in tree_ids, ids) || error("balanced-screen top ten contains IDs outside the committed tree sample")
    return ids
end

function context_summary(data_dir)
    path = joinpath(data_dir, WBGT_FILENAME)
    isfile(path) || return Dict{String, Any}("available" => false)
    payload = JSON3.read(read(path, String), Dict{String, Any})
    summary = payload["region_summary"]
    window = payload["window"]
    overlap = payload["period_sensitivity"]["top_ten_overlap"]
    return Dict{String, Any}(
        "available" => true,
        "window_phrase" => "$(window["start_year"])–$(window["end_year"]) ($(window["seasons"]) summers)",
        "distinct_cells" => summary["distinct_cells"],
        "reference_min" => summary["reference_date_wbgt_min_c"],
        "reference_max" => summary["reference_date_wbgt_max_c"],
        "reference_percentile_min" => summary["reference_percentile_min"],
        "reference_percentile_max" => summary["reference_percentile_max"],
        "seasonal_mean_min" => summary["seasonal_mean_wbgt_min_c"],
        "seasonal_mean_max" => summary["seasonal_mean_wbgt_max_c"],
        "seasonal_mean_spread" => summary["seasonal_mean_wbgt_spread_c"],
        "reference_day_vs_balanced" => overlap["reference_day_vs_balanced"],
        "seasonal_mean_vs_balanced" => overlap["seasonal_mean_vs_balanced"],
        "hot_days_vs_balanced" => overlap["hot_days_vs_balanced"],
        "seasonal_mean_vs_reference_day" => overlap["seasonal_mean_vs_reference_day"],
        "licence_status" => payload["licence_review"]["status"],
    )
end

function generate_wbgt_context(trees_path, output_path; cache_dir = nothing, years = ARCHIVE_START_YEAR:ARCHIVE_END_YEAR, fetch = nothing, extra = Dict{String, Any}())
    source = JSON3.read(read(trees_path, String), Dict{String, Any})
    trees = get(source, "records", Any[])
    isempty(trees) && error("committed tree sample is empty")
    directory = cache_dir === nothing ? dirname(abspath(output_path)) : cache_dir
    loaded = load_wbgt_years(directory, trees; years = years, fetch = fetch)
    metrics = tree_season_metrics(loaded.indices, loaded.values, loaded.dates)
    payload = build_wbgt_payload(metrics, loaded.years; archive_urls = [archive_url(year) for year in loaded.years], extra = extra)
    IOUtils.atomic_write_json(output_path, payload)
    return payload
end

end
