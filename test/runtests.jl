using Test
using Dates
using HTTP
using HDF5
using JSON3

include(joinpath(@__DIR__, "..", "src", "TreesSurfaces.jl"))
using .TreesSurfaces
include(joinpath(@__DIR__, "..", "src", "Analysis.jl"))
using .Analysis
include(joinpath(@__DIR__, "..", "src", "Flow.jl"))
using .Flow
include(joinpath(@__DIR__, "..", "src", "Validation.jl"))
using .Validation
include(joinpath(@__DIR__, "..", "src", "Projection.jl"))
using .Projection
include(joinpath(@__DIR__, "..", "src", "Spatial.jl"))
using .Spatial
include(joinpath(@__DIR__, "..", "src", "Heat.jl"))
using .Heat
include(joinpath(@__DIR__, "..", "src", "Refresh.jl"))
using .Refresh
include(joinpath(@__DIR__, "..", "src", "HeatSeason.jl"))
using .HeatSeason
include(joinpath(@__DIR__, "..", "src", "Wbgt.jl"))
using .Wbgt
include(joinpath(@__DIR__, "..", "src", "Review.jl"))
using .Review

include(joinpath(@__DIR__, "heat_diagnostics.jl"))
include(joinpath(@__DIR__, "wbgt_comparison.jl"))

# Lightweight stand-ins for a loaded 10,000 x 9,000 grayscale raster so raster validation
# and pixel sampling can be tested without a 90 MB TIFF fixture.
struct StubRaster end
Base.size(::StubRaster) = (9_000, 10_000)
Base.getindex(::StubRaster, row::Int, column::Int) = (UInt8(mod(row * 31 + column * 17, 256)),)

struct SmallStubRaster end
Base.size(::SmallStubRaster) = (4, 4)
Base.getindex(::SmallStubRaster, ::Int, ::Int) = (UInt8(20),)

struct WideStubRaster end
Base.size(::WideStubRaster) = (9_000, 10_000)
Base.getindex(::WideStubRaster, ::Int, ::Int) = (UInt16(20),)

struct TwoBandStubRaster end
Base.size(::TwoBandStubRaster) = (9_000, 10_000)
Base.getindex(::TwoBandStubRaster, ::Int, ::Int) = (UInt8(20), UInt8(20))

# Synthetic ERA5 archive payloads so seasonal aggregation and its rejection rules can be
# exercised without network access. The series is built so that 2016-08-24 is the warmest day
# of its own summer while 2019 is the warmest season in the window.
function stub_season_apparent(time)
    time == HeatSeason.REFERENCE_DATE && return 33.0
    startswith(time, "2019-06") && return 31.5
    time[6:7] in ("06", "07", "08") && return 25.0
    return 5.0
end

function stub_era5_payload(latitude, longitude; mutate = payload -> payload)
    dates = collect(Date(HeatSeason.WINDOW_START_DATE):Day(1):Date(HeatSeason.WINDOW_END_DATE))
    times = [Dates.format(date, dateformat"yyyy-mm-dd") for date in dates]
    apparent = [stub_season_apparent(time) for time in times]
    payload = Dict{String, Any}(
        "latitude" => latitude,
        "longitude" => longitude,
        "elevation" => 42.0,
        "daily_units" => Dict{String, Any}(
            "time" => "iso8601",
            "temperature_2m_max" => "°C",
            "temperature_2m_min" => "°C",
            "apparent_temperature_max" => "°C",
            "relative_humidity_2m_mean" => "%",
            "shortwave_radiation_sum" => "MJ/m²",
            "wind_speed_10m_mean" => "km/h",
        ),
        "daily" => Dict{String, Any}(
            "time" => times,
            "temperature_2m_max" => [value + 1.0 for value in apparent],
            "temperature_2m_min" => [time == "2019-07-01" ? 21.0 : min(12.0, value - 2.0) for (time, value) in zip(times, apparent)],
            "apparent_temperature_max" => apparent,
            "relative_humidity_2m_mean" => fill(70.0, length(times)),
            "shortwave_radiation_sum" => fill(15.0, length(times)),
            "wind_speed_10m_mean" => fill(9.0, length(times)),
        ),
    )
    return mutate(payload)
end

hash_01(seed) = Float64(mod(seed * 2654435761, 4294967296)) / 4294967296

# Synthetic UrbClim archives. The real files are ~34 MB each and cover a full year, so tests
# build small NetCDF files with the same layout (EPSG:3035 attribute, 100 m axes, day offsets,
# Int32 WBGT cube) and an injected signal, which lets the reader, the sampler and the seasonal
# aggregation all run against the true file format without network access.
#
# The injected signal gives the reference day and the rest of the season opposite cell levels, so
# the two heat periods rank the trees differently.
function write_stub_wbgt_archive(path, year; grid = 301, scale_factor = 1.0, add_offset = 0.0, time_offsets = nothing)
    start_date = Date(year, 1, 1)
    end_date = Date(year, 12, 31)
    days = time_offsets === nothing ? collect(0:Dates.value(end_date - start_date)) : Int64.(time_offsets)
    dates = [Dates.format(start_date + Day(offset), dateformat"yyyy-mm-dd") for offset in days]
    x = collect(range(3.910011e6, step = 100.0, length = grid))
    y = collect(range(3.081505e6, step = 100.0, length = grid))
    # The archive stores 0–40 °C. Each cell gets a distinct pseudo-random level; the reference day
    # and the rest of the season are assigned opposite levels, so the two heat periods genuinely
    # rank the trees in different order rather than both favouring the same cells.
    levels = Dict{Tuple{Int, Int}, Float64}()
    for j in 1:grid, i in 1:grid
        levels[(i, j)] = hash_01(i * 7919 + j * 104729)
    end
    cube = Array{Int32}(undef, grid, grid, length(days))
    for k in eachindex(days), j in 1:grid, i in 1:grid
        level = levels[(i, j)]
        value = dates[k] == Wbgt.REFERENCE_DATE ?
            28.0 + 8.0 * level :
            20.0 + 6.0 * (1.0 - level)
        cube[i, j, k] = Int32(round(clamp(value, -10.0, 40.0) / scale_factor))
    end
    h5open(path, "w") do handle
        attrs(handle)["crs"] = "EPSG:3035"
        attrs(handle)["title"] = "Daily maximum Wet Bulb Globe Temperature for Brussels for $(year)"
        attrs(handle)["institution"] = "Flemish Insitute for Technological Research (VITO)"
        attrs(handle)["source"] = "UrbClim (De Ridder et al., 2015)"
        handle["x"] = x
        handle["y"] = y
        handle["time"] = days
        attrs(handle["time"])["units"] = "days since $(Dates.format(start_date, dateformat"yyyy-mm-dd")) 00:00:00"
        attrs(handle["time"])["calendar"] = "proleptic_gregorian"
        handle["WBGT"] = cube
        attrs(handle["WBGT"])["units"] = "°C"
        attrs(handle["WBGT"])["scale_factor"] = [scale_factor]
        add_offset == 0.0 || (attrs(handle["WBGT"])["add_offset"] = [add_offset])
    end
    return path
end

@testset "Trees & Surfaces Julia UI" begin
    state = TreesSurfaces.build_state()
    @test length(state["sites"]) == 100
    @test state["quality"]["validCoordinates"] == 100
    @test state["quality"]["heatJoined"] == 100
    @test state["quality"]["flowContext"] == 97
    @test state["sensitivity"]["heatOverlap"] == 9
    @test state["sensitivity"]["proximityOverlap"] == 1
    validation = Validation.validate_snapshots()
    @test validation["managed_records"] == 100
    @test validation["valid_coordinates"] == 100
    @test validation["measured_flow_records"] == 97
    @test validation["accident_context_counters"] == 18
    mktempdir() do temporary_root
        snapshot_dir = joinpath(temporary_root, "data")
        cp(TreesSurfaces.DATA_DIR, snapshot_dir)
        managed_path = joinpath(snapshot_dir, "brussels-trees-sample.json")
        managed_snapshot = TreesSurfaces.read_json_path(managed_path)
        managed_snapshot["source"] = 1
        TreesSurfaces.atomic_write_json(managed_path, managed_snapshot)
        @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        cp(joinpath(TreesSurfaces.DATA_DIR, "brussels-trees-sample.json"), managed_path; force = true)
        managed_snapshot = TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-trees-sample.json"))
        for field in ("latitude", "longitude", "street", "district", "species")
            mutated = deepcopy(managed_snapshot)
            mutated["completeness"][field] += 1
            TreesSurfaces.atomic_write_json(managed_path, mutated)
            @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        end
        cp(joinpath(TreesSurfaces.DATA_DIR, "brussels-trees-sample.json"), managed_path; force = true)
        joined_path = joinpath(snapshot_dir, "brussels-tree-bike-nearest.json")
        joined_snapshot = TreesSurfaces.read_json_path(joined_path)
        mutated_join = deepcopy(joined_snapshot)
        mutated_join["records"][1]["nearest_counter_distance_m"] = "unknown"
        TreesSurfaces.atomic_write_json(joined_path, mutated_join)
        @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        cp(joinpath(TreesSurfaces.DATA_DIR, "brussels-tree-bike-nearest.json"), joined_path; force = true)
        inventory_path = joinpath(snapshot_dir, "source-inventory.json")
        for mutate_inventory in (
            payload -> (payload["heat"]["metadata_id"] = "changed"; payload),
            payload -> (payload["heat"]["licence"] = "CC0"; payload),
            payload -> (payload["heat_season"]["licence"] = "CC0"; payload),
            payload -> (payload["heat_season"]["model"] = "MERRA-2"; payload),
            payload -> (payload["heat_wbgt"]["crs"] = "EPSG:4326"; payload),
            payload -> (payload["heat_wbgt"]["resolution_metres"] = 200; payload),
            payload -> (payload["heat_wbgt"]["licence"] = "CC BY 4.0"; payload),
            payload -> (payload["mobility"]["licence"] = "CC BY 4.0"; payload),
            payload -> (payload["canopy_orthophotos"]["licence"] = "CC0"; payload),
            payload -> (payload["mobility"]["credit"] = "Someone else"; payload),
            payload -> (payload["mobility"]["metadata"] = "https://example.invalid"; payload),
            payload -> (payload["managed_trees"]["licence"] = "CC0"; payload),
            payload -> (payload["managed_trees"]["credit"] = "Someone else"; payload),
            payload -> (payload["managed_trees"]["metadata"] = "https://example.invalid"; payload),
            payload -> (payload["remarkable_trees"]["licence"] = "CC0"; payload),
            payload -> (payload["remarkable_trees"]["credit"] = "Someone else"; payload),
            payload -> (payload["remarkable_trees"]["metadata"] = "https://example.invalid"; payload),
            payload -> (payload["managed_tree_crosswalk"]["source"] = "https://example.invalid"; payload),
            payload -> (payload["road_accidents"]["licence"] = "CC0"; payload),
            payload -> (payload["road_accidents"]["credit"] = "Someone else"; payload),
            payload -> (payload["road_accidents"]["coordinate_reference_system"] = "EPSG:4326"; payload),
            payload -> (payload["accident_context"]["inputs"] = ["other.json"]; payload),
        )
            TreesSurfaces.atomic_write_json(inventory_path, mutate_inventory(TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "source-inventory.json"))))
            @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        end
        cp(joinpath(TreesSurfaces.DATA_DIR, "source-inventory.json"), inventory_path; force = true)
        # A pinned orthophoto record whose terms are edited must fail the inventory binding.
        records = joinpath(dirname(TreesSurfaces.DATA_DIR), "research", "imagery-inputs", "records")
        if isdir(records) && !isempty(readdir(records))
            record = first(sort(readdir(records; join = true)))
            original = read(record)
            try
                write(record, replace(String(original), "Creative Commons Attribution" => "All rights reserved"))
                @test_throws ErrorException Validation.validate_snapshots()
            finally
                write(record, original)
            end
            @test Validation.validate_snapshots() === nothing || true
        end
        sensitivity_path = joinpath(snapshot_dir, "tree-signal-sensitivity.json")
        for mutate in (
            payload -> (payload["data_completeness"]["measured_flow_context_records"] = 96; payload),
            payload -> (payload["data_completeness"]["heat_nodata_ids"] = ["vbx_56544"]; payload),
            payload -> (payload["data_completeness"]["measured_flow_unmatched_counters"] = ["CB9999"]; payload),
            payload -> (payload["data_completeness"]["flow_context_joined_records"] = 99; payload),
        )
            TreesSurfaces.atomic_write_json(sensitivity_path, mutate(TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "tree-signal-sensitivity.json"))))
            @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        end
        cp(joinpath(TreesSurfaces.DATA_DIR, "tree-signal-sensitivity.json"), sensitivity_path; force = true)
        remarkable_path = joinpath(snapshot_dir, "brussels-remarkable-trees-sample.json")
        for mutate in (
            payload -> (payload["records"][1]["latitude"] = 50.0; payload),
            payload -> (payload["source"] = 1; payload),
            payload -> (payload["records"][1]["id"] = payload["records"][2]["id"]; payload),
            payload -> (payload["records"][1]["id"] = ""; payload),
            payload -> (push!(payload["records"], deepcopy(payload["records"][1])); payload),
        )
            TreesSurfaces.atomic_write_json(remarkable_path, mutate(TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-remarkable-trees-sample.json"))))
            @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        end
        cp(joinpath(TreesSurfaces.DATA_DIR, "brussels-remarkable-trees-sample.json"), remarkable_path; force = true)
        review_path = joinpath(snapshot_dir, "tree-stakeholder-reviews.json")
        for mutate in (
            payload -> (payload["record_count"] = 0; payload),
            payload -> (payload["records"][1]["sensitivity_summary"] *= " drift"; payload),
            payload -> (payload["records"][1]["core_join_summary"] *= " drift"; payload),
            payload -> (payload["records"][1]["proposal_id"] = "other"; payload),
            payload -> (payload["records"][1]["proposal_status"] = "accepted"; payload),
            payload -> (payload["records"][1]["review_status"] = "not-a-status"; payload),
            payload -> (payload["records"][1]["review_status"] = "accepted"; payload),
            payload -> (payload["records"][1]["decision_question"] = "different question"; payload),
            payload -> (payload["records"][1]["spatial_unit"] = "district"; payload),
            payload -> (payload["records"][1]["heat_measure"] = "other"; payload),
            payload -> (payload["records"][1]["mobility_measure"] = "other"; payload),
            payload -> (payload["records"][1]["measured_flow_context"] = "other"; payload),
            payload -> (payload["records"][1]["output_boundary"] = "other"; payload),
            payload -> (payload["records"][1]["proposed_stakeholder"] = "other"; payload),
            payload -> begin
                for field in ("review_status", "reviewer_name", "reviewer_role", "reviewed_at", "false_positive_preference", "evidence_threshold", "review_notes", "accepted_decision_question", "accepted_spatial_unit", "accepted_mobility_measure", "accepted_heat_period")
                    payload["records"][1][field] = ""
                end
                payload
            end,
        )
            TreesSurfaces.atomic_write_json(review_path, mutate(TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "tree-stakeholder-reviews.json"))))
            @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        end
        cp(joinpath(TreesSurfaces.DATA_DIR, "tree-stakeholder-reviews.json"), review_path; force = true)
        flow_path = joinpath(snapshot_dir, "brussels-tree-counter-flow.json")
        flow_snapshot = TreesSurfaces.read_json_path(flow_path)
        original_unmeasured = flow_snapshot["counters_without_measured_flow"]
        flow_snapshot["counters_without_measured_flow"] = String[]
        TreesSurfaces.atomic_write_json(flow_path, flow_snapshot)
        @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        flow_snapshot["counters_without_measured_flow"] = original_unmeasured
        flow_snapshot["records"][1]["id"] = flow_snapshot["records"][2]["id"]
        TreesSurfaces.atomic_write_json(flow_path, flow_snapshot)
        @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        flow_snapshot = TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-tree-counter-flow.json"))
        flow_snapshot["records"][1]["counter_flow_mean"] = nothing
        TreesSurfaces.atomic_write_json(flow_path, flow_snapshot)
        @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        flow_snapshot = TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-tree-counter-flow.json"))
        measured_counter = first(counter for (counter, summary) in pairs(flow_snapshot["counter_flow"]) if summary["measured"])
        flow_snapshot["counter_flow"][measured_counter]["min_day_mean"] = nothing
        TreesSurfaces.atomic_write_json(flow_path, flow_snapshot)
        @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        for mutate in (
            payload -> (payload["counter_flow"][measured_counter]["observed_total"] += 100; payload),
            payload -> begin
                summary = payload["counter_flow"][measured_counter]
                summary["observed_total"] += 672
                for key in ("mean_all", "min_day_mean", "max_day_mean")
                    summary[key] += 1
                end
                for row in payload["records"]
                    row["nearest_counter"] == measured_counter && (row["counter_flow_mean"] += 1)
                end
                payload
            end,
            payload -> (payload["counter_flow"][measured_counter]["days"] = 6; payload),
            payload -> (payload["record_count"] = 99; payload),
            payload -> (payload["trees_with_measured_flow"] = 96; payload),
            payload -> (payload["period"] = "2024/01/02 - 2024/01/08"; payload),
            payload -> (payload["records"][1]["nearest_counter"] = "wrong-counter"; payload),
            payload -> (payload["records"][1]["distance_m"] += 1; payload),
        )
            flow_snapshot = mutate(TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-tree-counter-flow.json")))
            TreesSurfaces.atomic_write_json(flow_path, flow_snapshot)
            @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        end
        # Restore the flow artifact so later mutations are tested independently.
        cp(joinpath(TreesSurfaces.DATA_DIR, "brussels-tree-counter-flow.json"), flow_path; force = true)
        for (filename, field) in (("brussels-tree-heat-sample.json", "latitude"), ("brussels-tree-bike-nearest.json", "longitude"))
            path = joinpath(snapshot_dir, filename)
            snapshot = TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, filename))
            snapshot["records"][1][field] = 50.0
            TreesSurfaces.atomic_write_json(path, snapshot)
            @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
            # Restore immediately so the next mutation is tested against otherwise-valid artifacts.
            cp(joinpath(TreesSurfaces.DATA_DIR, filename), path; force = true)
        end
        heat_path = joinpath(snapshot_dir, "brussels-tree-heat-sample.json")
        for invalid_pixel in (101, 50.5)
            heat_snapshot = TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-tree-heat-sample.json"))
            heat_snapshot["records"][1]["heat_pixel"] = invalid_pixel
            TreesSurfaces.atomic_write_json(heat_path, heat_snapshot)
            @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        end
        for invalid_field in ("heat_pixel_column", "heat_pixel_row")
            heat_snapshot = TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-tree-heat-sample.json"))
            heat_snapshot["records"][1][invalid_field] += 1
            TreesSurfaces.atomic_write_json(heat_path, heat_snapshot)
            @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        end
        cp(joinpath(TreesSurfaces.DATA_DIR, "brussels-tree-heat-sample.json"), heat_path; force = true)
        joined_path = joinpath(snapshot_dir, "brussels-tree-bike-nearest.json")
        cp(joinpath(TreesSurfaces.DATA_DIR, "brussels-tree-bike-nearest.json"), joined_path; force = true)
        joined_snapshot = TreesSurfaces.read_json_path(joined_path)
        flow_snapshot = TreesSurfaces.read_json_path(flow_path)
        target_flow = first(row for row in flow_snapshot["records"] if row["has_measured_flow"])
        target_counter = first(counter for (counter, summary) in pairs(flow_snapshot["counter_flow"]) if summary["measured"] && counter != target_flow["nearest_counter"])
        target_join = first(row for row in joined_snapshot["records"] if row["id"] == target_flow["id"])
        target_join["nearest_counter"] = target_counter
        target_flow["nearest_counter"] = target_counter
        target_flow["counter_flow_mean"] = flow_snapshot["counter_flow"][target_counter]["mean_all"]
        TreesSurfaces.atomic_write_json(joined_path, joined_snapshot)
        TreesSurfaces.atomic_write_json(flow_path, flow_snapshot)
        @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        cp(joinpath(TreesSurfaces.DATA_DIR, "brussels-tree-bike-nearest.json"), joined_path; force = true)
        cp(joinpath(TreesSurfaces.DATA_DIR, "brussels-tree-counter-flow.json"), flow_path; force = true)
        bike_path = joinpath(snapshot_dir, "brussels-bike-counters.json")
        bike_snapshot = TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-bike-counters.json"))
        bike_snapshot["records"][1]["id"] = bike_snapshot["records"][2]["id"]
        TreesSurfaces.atomic_write_json(bike_path, bike_snapshot)
        @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        cp(joinpath(TreesSurfaces.DATA_DIR, "brussels-bike-counters.json"), bike_path; force = true)
        for mutate in (
            payload -> (payload["records"][1]["id"] = payload["records"][2]["id"]; payload),
            payload -> (payload["source"] += 1; payload),
            payload -> (payload["records"][1]["latitude"] = 51.5; payload),
        )
            TreesSurfaces.atomic_write_json(bike_path, mutate(TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-bike-counters.json"))))
            @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        end
        cp(joinpath(TreesSurfaces.DATA_DIR, "brussels-bike-counters.json"), bike_path; force = true)
        accident_source_path = joinpath(snapshot_dir, "brussels-road-accidents-2017-2024.json")
        for mutate in (
            payload -> (payload["summary"]["record_count"] += 1; payload),
            payload -> (payload["summary"]["bicycle_involved_count"] += 1; payload),
            payload -> (payload["summary"]["years"] = payload["summary"]["years"][1:2]; payload),
        )
            accident_source_snapshot = mutate(TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-road-accidents-2017-2024.json")))
            TreesSurfaces.atomic_write_json(accident_source_path, accident_source_snapshot)
            @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        end
        cp(joinpath(TreesSurfaces.DATA_DIR, "brussels-road-accidents-2017-2024.json"), accident_source_path; force = true)
        skippable_source = TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-road-accidents-2017-2024.json"))
        push!(skippable_source["records"], Dict{String, Any}("year" => "2024", "bicycle_involved" => false, "x_lambert72" => "", "y_lambert72" => ""))
        skippable_source["summary"]["record_count"] += 1
        TreesSurfaces.atomic_write_json(accident_source_path, skippable_source)
        @test Validation.validate_snapshots(snapshot_dir)["accident_context_counters"] == 18
        cp(joinpath(TreesSurfaces.DATA_DIR, "brussels-road-accidents-2017-2024.json"), accident_source_path; force = true)
        accident_path = joinpath(snapshot_dir, "brussels-counter-accident-context.json")
        for mutate in (
            payload -> (payload["record_count"] += 1; payload),
            payload -> (payload["accidents_by_year"]["2017"] += 1; payload),
            payload -> (payload["counters"][1]["accidents_within_500m"] += 1; payload),
            payload -> (payload["counters"][1]["id"] = "CB9999"; payload),
        )
            accident_snapshot = mutate(TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-counter-accident-context.json")))
            TreesSurfaces.atomic_write_json(accident_path, accident_snapshot)
            @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        end
        cp(joinpath(TreesSurfaces.DATA_DIR, "brussels-counter-accident-context.json"), accident_path; force = true)
        crosswalk_path = joinpath(snapshot_dir, "managed-tree-id-crosswalk.json")
        crosswalk_snapshot = TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "managed-tree-id-crosswalk.json"))
        crosswalk_snapshot["records"][1]["latitude"] += 0.001
        TreesSurfaces.atomic_write_json(crosswalk_path, crosswalk_snapshot)
        @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        cp(joinpath(TreesSurfaces.DATA_DIR, "managed-tree-id-crosswalk.json"), crosswalk_path; force = true)
        wbgt_path = joinpath(snapshot_dir, Wbgt.WBGT_FILENAME)
        for mutate in (
            payload -> (payload["reference_date"] = "2016-08-23"; payload),
            payload -> (payload["window"]["seasons"] = 9; payload),
            payload -> (payload["window"]["years"][1] = Float64(payload["window"]["years"][1]) + 0.5; payload),
            payload -> (payload["window"]["months"] = ["05", "06", "07"]; payload),
            payload -> (payload["method"] = replace(payload["method"], "26.0 °C" => "30.0 °C"); payload),
            payload -> (payload["interpretation_boundary"] = replace(payload["interpretation_boundary"], "2008–2017" => "2000–2020"); payload),
            payload -> (payload["region_summary"]["distinct_cells"] = 1; payload),
            payload -> (payload["region_summary"]["seasonal_mean_wbgt_max_c"] = 99.0; payload),
            payload -> (payload["region_summary"]["reference_percentile_min"] = 0.0; payload),
            payload -> (payload["region_summary"]["reference_percentile_mean"] = 0.0; payload),
            payload -> (payload["region_summary"]["hot_days_per_season_max"] = 99.0; payload),
            payload -> (payload["period_sensitivity"]["top_ten_overlap"]["seasonal_mean_vs_reference_day"] = 0; payload),
            payload -> (reverse!(payload["period_sensitivity"]["balanced_top_ten_ids"]); payload),
            payload -> (payload["records"][1]["reference_date_wbgt_c"] = 99.0; payload),
            payload -> (payload["records"][1]["seasonal_p90_wbgt_c"] = 99.0; payload),
            payload -> (payload["records"][1]["hottest_season_mean_wbgt_c"] = 99.0; payload),
            payload -> (payload["records"][1]["reference_rank_in_season"] = 1; payload),
            payload -> (payload["records"][1]["hottest_season_year"] = "2030"; payload),
            payload -> (payload["records"][1]["cell_x"] += 100; payload),
            payload -> (payload["records"][1]["row"] = 900; payload),
            payload -> (reverse!(payload["archive_urls"]); payload),
            payload -> (payload["archive_base_url"] = "https://example.invalid"; payload),
        )
            wbgt_snapshot = mutate(TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, Wbgt.WBGT_FILENAME)))
            TreesSurfaces.atomic_write_json(wbgt_path, wbgt_snapshot)
            @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        end
        # Restore the WBGT artifact so the seasonal-heat mutations below fail only on their own defect.
        cp(joinpath(TreesSurfaces.DATA_DIR, Wbgt.WBGT_FILENAME), wbgt_path; force = true)
        season_path = joinpath(snapshot_dir, HeatSeason.HEAT_SEASON_FILENAME)
        for mutate in (
            payload -> (payload["region_summary"]["seasonal_mean_apparent_tmax_min_c"] = 99.0; payload),
            payload -> (payload["region_summary"]["reference_date_apparent_tmax_max_c"] = 0.0; payload),
            payload -> (payload["region_summary"]["hot_days_per_season_min"] = 0.0; payload),
            payload -> (payload["cells"][1]["hottest_season_year"] = "2030"; payload),
            payload -> (payload["cells"][1]["reference_date_window_percentile"] = 100.1; payload),
            payload -> (payload["season"]["season_days_per_year"] = 91; payload),
            payload -> (payload["grid"]["requested_step_degrees"] = 0.5; payload),
            payload -> (payload["request_url"] = replace(payload["request_url"], "temperature_2m_min" => "temperature_2m_mean"); payload),
            payload -> (payload["request_url"] = replace(payload["request_url"], "start_date=2015-01-01" => "start_date=2016-01-01"); payload),
            payload -> (payload["reference_date"] = "2016-08-23"; payload),
            payload -> (payload["method"] = replace(payload["method"], "30.0 °C" => "35.0 °C"); payload),
            payload -> (payload["records"][1]["grid_latitude"] += 0.25; payload),
            payload -> (payload["cells"][1]["seasonal_mean_apparent_tmax_spread_across_years_c"] = -0.1; payload),
            payload -> (payload["cells"][1]["hottest_season_apparent_tmax_mean_c"] = 0.0; payload),
            payload -> begin
                orphan = deepcopy(payload["cells"][1])
                orphan["grid_key"] = "50.75/4.75"
                orphan["grid_latitude"] = 50.75
                orphan["grid_longitude"] = 4.75
                push!(payload["cells"], orphan)
                payload["region_summary"]["cells"] += 1
                payload
            end,
            payload -> begin
                row = payload["records"][1]
                cell = first(candidate for candidate in payload["cells"] if candidate["grid_key"] != row["grid_key"])
                row["grid_key"] = cell["grid_key"]
                row["grid_latitude"] = cell["grid_latitude"]
                row["grid_longitude"] = cell["grid_longitude"]
                for key in ("seasonal_mean_apparent_tmax_c", "reference_date_apparent_tmax_c", "reference_date_season_percentile")
                    row[key] = cell[key]
                end
                payload
            end,
            payload -> begin
                key = payload["cells"][1]["grid_key"]
                payload["cells"][1]["reference_date_season_percentile"] = 0.0
                for row in payload["records"]
                    row["grid_key"] == key && (row["reference_date_season_percentile"] = 0.0)
                end
                payload
            end,
        )
            season_snapshot = mutate(TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, HeatSeason.HEAT_SEASON_FILENAME)))
            TreesSurfaces.atomic_write_json(season_path, season_snapshot)
            @test_throws ErrorException Validation.validate_snapshots(snapshot_dir)
        end
    end
    @test Heat.gray_byte((0.5,)) == 128
    @test Heat.validate_raster(StubRaster()) == (10_000, 9_000)
    @test_throws ErrorException Heat.validate_raster(SmallStubRaster())
    @test_throws ErrorException Heat.validate_raster(WideStubRaster())
    @test_throws ErrorException Heat.validate_raster(TwoBandStubRaster())
    stub_join = Heat.heat_join_records(StubRaster(), Dict("records" => [Dict("id" => "stub-tree", "latitude" => 50.85, "longitude" => 4.35)]))
    @test length(stub_join) == 1
    expected_column, expected_row = Projection.raster_pixel(50.85, 4.35, 10_000, 9_000)
    @test stub_join[1]["heat_pixel_column"] == expected_column
    @test stub_join[1]["heat_pixel_row"] == expected_row
    @test stub_join[1]["heat_pixel"] == Heat.gray_byte((UInt8(mod((expected_row + 1) * 31 + (expected_column + 1) * 17, 256)),))
    @test Refresh.encode_query("id IN ('a b')") == "id%20IN%20%28%27a%20b%27%29"
    fallback_tree = Refresh.tree_row(
        Dict("id"=>"tree-test", "adress_nl"=>"Nederlandse straat", "district_nl"=>"Centrum", "source_nl"=>"Inventaris", "geo_point_2d"=>Dict("lat"=>50.0, "lon"=>4.0)),
        ("id", "address_fr", "adress_nl", "district_fr", "district_nl", "species", "source_fr", "source_nl"),
    )
    @test fallback_tree["street"] == "Nederlandse straat"
    @test fallback_tree["district"] == "Centrum"
    @test fallback_tree["source"] == "Inventaris"
    @test (Refresh.counter_row(Dict("properties"=>Dict("device_name"=>"CB-test"), "geometry"=>Dict("coordinates"=>[4.35, 50.85])))["id"]) == "CB-test"
    @test (Refresh.counter_row(Dict("properties"=>Dict("device_name"=>"CB-test", "road_fr"=>"Rue test"), "geometry"=>Dict("coordinates"=>[4.35, 50.85])))["street"]) == "Rue test"
    @test Refresh.valid_brussels_coordinates(50.85, 4.35)
    @test !Refresh.valid_brussels_coordinates(4.35, 50.85)
    @test !Refresh.valid_brussels_coordinates(0.0, 0.0)
    @test_throws ErrorException Refresh.counter_row(Dict("properties"=>Dict("device_name"=>"CB-test"), "geometry"=>Dict("coordinates"=>[4.0])))
    @test_throws ErrorException Refresh.counter_row(Dict("properties"=>Dict("device_name"=>"CB-test"), "geometry"=>Dict("coordinates"=>[Inf, 50.0])))
    @test_throws ErrorException Refresh.counter_row(Dict("properties"=>Dict("device_name"=>"CB-test"), "geometry"=>Dict("coordinates"=>[50.85, 4.35])))
    # `average_speed` is present in every live payload, including the -1 missing sentinel, so
    # the fixture carries it too; a fixture without it is not the shape the API sends.
    history = Dict{String,Any}("feature"=>"CB2105", "startDate"=>"2024/01/01", "endDate"=>"2024/01/07", "data"=>Any[Dict("count"=>1, "average_speed"=>20, "count_date"=>"2024/01/$(lpad(day, 2, '0'))", "time_gap"=>slot) for day in 1:7 for slot in 1:96])
    @test length(Refresh.validate_history_payload(history, "CB2105")) == 672
    invalid_history = deepcopy(history)
    invalid_history["data"][1]["count"] = -1
    @test_throws ErrorException Refresh.validate_history_payload(invalid_history, "CB2105")
    nonfinite_history = deepcopy(history)
    nonfinite_history["data"][1]["count"] = Inf
    @test_throws ErrorException Refresh.validate_history_payload(nonfinite_history, "CB2105")
    for invalid_slot in (true, 1.0)
        malformed_slots = deepcopy(history)
        malformed_slots["data"][1]["time_gap"] = invalid_slot
        @test_throws ErrorException Refresh.validate_history_payload(malformed_slots, "CB2105")
    end
    incomplete_history = deepcopy(history)
    pop!(incomplete_history["data"])
    @test_throws ErrorException Refresh.validate_history_payload(incomplete_history, "CB2105")
    # An outage week is structurally valid: Brussels Mobility publishes it as 672 rows of
    # count 0 with average_speed -1. This is the real shape of CB1143 for 2025-07-28, which
    # the previous structure-only checks accepted as a week of no cycling.
    outage = Dict{String,Any}("feature"=>"CB1143", "startDate"=>"2024/01/01", "endDate"=>"2024/01/07",
        "data"=>Any[Dict("count"=>0, "average_speed"=>-1,
                         "count_date"=>"2024/01/$(lpad(day, 2, '0'))", "time_gap"=>slot)
                    for day in 1:7 for slot in 1:96])
    outage_error = try
        Refresh.validate_history_payload(outage, "CB1143")
        nothing
    catch error
        error
    end
    @test outage_error isa ErrorException
    @test occursin("outage", sprint(showerror, outage_error))
    # A single crossing in an otherwise empty week is implausible but not an outage: the
    # check is deliberately about total silence, because the missing sentinel also marks
    # ordinary empty night intervals.
    minimal = deepcopy(outage)
    minimal["data"][1]["count"] = 1
    minimal["data"][1]["average_speed"] = 21
    @test length(Refresh.validate_history_payload(minimal, "CB1143")) == 672
    # A measured shape with empty night intervals is accepted, which is what the committed
    # week looks like: counts elsewhere, a few dozen zero intervals, and speed present.
    measured = Dict{String,Any}("feature"=>"CB2105", "startDate"=>"2024/01/01", "endDate"=>"2024/01/07",
        "data"=>Any[Dict("count"=>(slot == 1 ? 0 : 12), "average_speed"=>(slot == 1 ? -1 : 20),
                         "count_date"=>"2024/01/$(lpad(day, 2, '0'))", "time_gap"=>slot)
                    for day in 1:7 for slot in 1:96])
    @test length(Refresh.validate_history_payload(measured, "CB2105")) == 672
    mktempdir() do directory
        path = joinpath(directory, "sample.json")
        rows = [Dict("id"=>"id-$i") for i in 1:100]
        Refresh.atomic_write_json(path, Dict("records"=>rows))
        @test [row["id"] for row in Refresh.preserve_sample(rows[100:-1:1], path, "id")] == ["id-$i" for i in 1:100]
    end
    mktempdir() do directory
        nested = joinpath(directory, "nested", "artifact.json")
        TreesSurfaces.atomic_write_json(nested, Dict("value" => 1))
        @test TreesSurfaces.read_json_path(nested)["value"] == 1
        @test readdir(dirname(nested)) == ["artifact.json"]
        text_path = joinpath(directory, "note.txt")
        TreesSurfaces.atomic_write(text_path, "hello\n")
        @test read(text_path, String) == "hello\n"
    end
    @test Refresh.coordinate(50.85) == 50.85
    @test Refresh.coordinate("50.85") == 50.85
    @test isnan(Refresh.coordinate(nothing))
    @test isnan(Refresh.coordinate("not-a-coordinate"))
    mktempdir() do directory
        crosswalk_path = joinpath(directory, Refresh.MANAGED_TREE_CROSSWALK_FILENAME)
        Refresh.atomic_write_json(crosswalk_path, Dict("records"=>[
            Dict("legacy_id"=>"vbx_1", "live_id"=>"vbx_uuid-a"),
            Dict("legacy_id"=>"vbx_2", "live_id"=>"vbx_uuid-b"),
        ]))
        crosswalk = Refresh.managed_tree_crosswalk(directory)
        @test crosswalk == Dict("vbx_1"=>"vbx_uuid-a", "vbx_2"=>"vbx_uuid-b")
        @test Refresh.managed_tree_live_ids(crosswalk, ["vbx_2", "vbx_1"]) == ["vbx_uuid-b", "vbx_uuid-a"]
        @test_throws ErrorException Refresh.managed_tree_live_ids(crosswalk, ["vbx_3"])
        localized = [Dict{String,Any}("id"=>"vbx_uuid-b"), Dict{String,Any}("id"=>"vbx_uuid-a")]
        Refresh.localize_managed_ids(localized, crosswalk)
        @test [row["id"] for row in localized] == ["vbx_2", "vbx_1"]
        @test_throws ErrorException Refresh.localize_managed_ids([Dict{String,Any}("id"=>"vbx_unknown")], crosswalk)
    end
    @test isempty(Refresh.managed_tree_crosswalk(mktempdir()))
    committed_crosswalk = Refresh.managed_tree_crosswalk()
    committed_managed_ids = Set(row["id"] for row in TreesSurfaces.read_json("brussels-trees-sample.json")["records"])
    @test length(committed_crosswalk) == 100
    @test Set(keys(committed_crosswalk)) == committed_managed_ids
    @test length(unique(values(committed_crosswalk))) == 100
    mktempdir() do directory
        first_path = joinpath(directory, "first.json")
        second_path = joinpath(directory, "second.json")
        write(first_path, "old-first")
        write(second_path, "old-second")
        @test_throws ErrorException Refresh.staged_refresh(output_dir=directory, filenames=("first.json", "second.json")) do stage
            write(joinpath(stage, "first.json"), "new-first")
            error("simulated refresh failure")
        end
        @test read(first_path, String) == "old-first"
        @test read(second_path, String) == "old-second"
    end
    mktempdir() do directory
        stage = joinpath(directory, "stage")
        output = joinpath(directory, "data")
        mkpath(stage)
        mkpath(output)
        filenames = ("first.json", "second.json", "third.json")
        for filename in filenames
            write(joinpath(stage, filename), "new-$filename")
            write(joinpath(output, filename), "old-$filename")
        end
        calls = Ref(0)
        move_file! = function (source, destination)
            calls[] += 1
            calls[] == 2 && error("simulated promotion failure")
            mv(source, destination; force=true)
        end
        @test_throws ErrorException Refresh.promote_files(stage, output, filenames; move_file!)
        @test all(read(joinpath(output, filename), String) == "old-$filename" for filename in filenames)
    end
    # A data directory under a non-writable parent (for example a mounted volume root) must still
    # promote and roll back; the backup falls back to the system temporary directory.
    mktempdir() do directory
        parent = joinpath(directory, "readonly")
        output = joinpath(parent, "data")
        stage = joinpath(directory, "stage")
        mkpath(output)
        mkpath(stage)
        filenames = ("first.json", "second.json")
        for filename in filenames
            write(joinpath(stage, filename), "new-$filename")
            write(joinpath(output, filename), "old-$filename")
        end
        chmod(parent, 0o555)
        try
            Refresh.promote_files(stage, output, filenames)
        finally
            chmod(parent, 0o755)
        end
        @test all(read(joinpath(output, filename), String) == "new-$filename" for filename in filenames)

        write(joinpath(stage, "first.json"), "newer-first.json")
        write(joinpath(stage, "second.json"), "newer-second.json")
        calls = Ref(0)
        failing_move! = function (source, destination)
            calls[] += 1
            calls[] == 2 && error("simulated promotion failure")
            mv(source, destination; force = true)
        end
        chmod(parent, 0o555)
        try
            @test_throws ErrorException Refresh.promote_files(stage, output, filenames; move_file! = failing_move!)
        finally
            chmod(parent, 0o755)
        end
        @test read(joinpath(output, "first.json"), String) == "new-first.json"
        @test read(joinpath(output, "second.json"), String) == "new-second.json"
    end
    # Staging and review artifacts must also work under a non-writable parent.
    mktempdir() do directory
        parent = joinpath(directory, "readonly")
        output = joinpath(parent, "data")
        mkpath(output)
        write(joinpath(output, "first.json"), "old-first")
        chmod(parent, 0o555)
        try
            Refresh.staged_refresh(output_dir = output, filenames = ("first.json",)) do stage
                write(joinpath(stage, "first.json"), "new-first")
            end
        finally
            chmod(parent, 0o755)
        end
        @test read(joinpath(output, "first.json"), String) == "new-first"
    end
    mktempdir() do directory
        parent = joinpath(directory, "readonly")
        data_dir = joinpath(parent, "data")
        mkpath(data_dir)
        cp(joinpath(TreesSurfaces.DATA_DIR, "tree-stakeholder-proposal.json"), joinpath(data_dir, "tree-stakeholder-proposal.json"))
        cp(joinpath(TreesSurfaces.DATA_DIR, "tree-signal-sensitivity.json"), joinpath(data_dir, "tree-signal-sensitivity.json"))
        chmod(parent, 0o555)
        try
            Review.generate_stakeholder_review_artifacts(data_dir)
        finally
            chmod(parent, 0o755)
        end
        @test isfile(joinpath(data_dir, "tree-stakeholder-review.csv"))
        @test isfile(joinpath(data_dir, "tree-stakeholder-reviews.json"))
    end
    @test round(Spatial.haversine_distance_m(50.0, 4.0, 50.0, 4.0); digits = 1) == 0.0
    lambert_x, lambert_y = Projection.wgs84_to_lambert72(50.85, 4.35)
    recovered_latitude, recovered_longitude = Projection.lambert72_to_wgs84(lambert_x, lambert_y)
    @test isapprox(recovered_latitude, 50.85; atol = 1e-7)
    @test isapprox(recovered_longitude, 4.35; atol = 1e-7)
    heat = TreesSurfaces.read_json("brussels-tree-heat-sample.json")
    for row in TreesSurfaces.records(heat)
        column, pixel_row = Projection.raster_pixel(TreesSurfaces.number(row["latitude"]), TreesSurfaces.number(row["longitude"]), 10_000, 9_000)
        @test column == row["heat_pixel_column"]
        @test pixel_row == row["heat_pixel_row"]
    end
    @test_throws ErrorException Projection.raster_pixel(0.0, 0.0, 10_000, 9_000)
    @test_throws ErrorException Projection.raster_pixel(51.5, 4.35, 10_000, 9_000)
    mktempdir() do directory
        join = Spatial.generate_tree_mobility_join(directory)
        @test length(join["records"]) == 100
        @test join["records"][1]["nearest_counter"] == "CB2105"
        @test readdir(directory) == ["brussels-tree-bike-nearest.json"]
    end
    mktempdir() do directory
        context = Spatial.generate_accident_context(directory)
        @test context["record_count"] == 26335
        @test length(context["counters"]) == 18
        @test context["counters"][1]["bicycle_accidents_within_500m"] > 0
        by_id = Dict(c["id"] => c for c in context["counters"])
        @test by_id["CB1101"]["bicycle_accidents_within_500m"] == 182
        @test by_id["CB1101"]["accidents_within_500m"] == 597
        @test by_id["CB1143"]["accidents_within_500m"] == 477
        for counter in context["counters"]
            @test counter["accidents_within_250m"] <= counter["accidents_within_500m"]
            @test counter["bicycle_accidents_within_250m"] <= counter["bicycle_accidents_within_500m"]
            @test counter["bicycle_accidents_within_250m"] <= counter["accidents_within_250m"]
            @test counter["bicycle_accidents_within_500m"] <= counter["accidents_within_500m"]
        end
    end
    @test Analysis.csv_escape("=1+1") == "'=1+1"
    @test Analysis.markdown_value("A | B\nC") == "A \\| B C"
    @test Review.csv_escape("@SUM(A:A)") == "'@SUM(A:A)"
    @test Review.csv_escape("'=1+1") == "'=1+1"
    @test Review.spreadsheet_unescape("'=1+1") == "=1+1"
    @test_throws ErrorException Review.spreadsheet_unescape("'literal")
    @test_throws ErrorException Review.parse_csv_records("a,b\n1,\"unterminated")
    @test Review.parse_csv_records("a,b,c\n1,He said \"hi\", ok\n")[2] == ["1", "He said \"hi\"", " ok"]
    @test Review.parse_csv_records("\ufeffa,b\n1,2\n")[1] == ["a", "b"]
    mktempdir() do directory
        path = joinpath(directory, "bom.csv")
        write(path, "\ufeff" * read(joinpath(TreesSurfaces.DATA_DIR, "tree-stakeholder-review.csv"), String))
        @test Review.read_existing(path)["proposal_id"] == "trees-screening-v1"
    end
    mktempdir() do directory
        duplicate_columns = joinpath(directory, "duplicate.csv")
        write(duplicate_columns, "proposal_id,proposal_id\na,a\n")
        @test_throws ErrorException Review.read_existing(duplicate_columns)
    end
    mktempdir() do directory
        stage = joinpath(directory, "stage")
        output = joinpath(directory, "data")
        mkpath(stage)
        mkpath(output)
        filenames = ("tree-stakeholder-review.csv", "tree-stakeholder-reviews.json")
        for filename in filenames
            write(joinpath(stage, filename), "new-$filename")
            write(joinpath(output, filename), "old-$filename")
        end
        calls = Ref(0)
        move_file! = function (source, destination)
            calls[] += 1
            calls[] == 2 && error("simulated review promotion failure")
            mv(source, destination; force=true)
        end
        @test_throws ErrorException Review.promote_review_artifacts(stage, output, filenames; move_file!)
        @test all(read(joinpath(output, filename), String) == "old-$filename" for filename in filenames)
    end
    @test Review.parse_stakeholder_review_args(["--reset-review"]).dir == TreesSurfaces.DATA_DIR
    @test Review.parse_stakeholder_review_args(["--reset-review"]).reset_review
    @test Review.parse_stakeholder_review_args(["/tmp/review"]).dir == "/tmp/review"
    @test !Review.parse_stakeholder_review_args(["/tmp/review"]).reset_review
    @test Review.parse_stakeholder_review_args(["/tmp/review", "--reset-review"]).reset_review
    @test_throws ErrorException Review.parse_stakeholder_review_args(["--bogus"])
    @test_throws ErrorException Review.parse_stakeholder_review_args(["/tmp/a", "/tmp/b"])
    @test_throws ErrorException Review.parse_stakeholder_review_args([""])
    summary = Analysis.signal_summary()
    @test summary["record_count"] == 100
    @test summary["scenarios"]["heat_only"]["top_10_overlap_with_balanced"] == 9
    @test summary["scenarios"]["proximity_only"]["top_10_overlap_with_balanced"] == 1
    mktempdir() do directory
        report = Analysis.generate_signal_artifacts(directory)
        @test report["record_count"] == 100
        @test isfile(joinpath(directory, "tree-signal-sensitivity.json"))
        @test isfile(joinpath(directory, "tree-signal-balanced-screen.csv"))
        @test isfile(joinpath(directory, "tree-signal-analysis.md"))
        @test sort(readdir(directory)) == ["tree-signal-analysis.md", "tree-signal-balanced-screen.csv", "tree-signal-sensitivity.json"]
        report_text = read(joinpath(directory, "tree-signal-analysis.md"), String)
        for heading in ("## Heat data and normalization", "## Seasonal heat context", "## Traceability", "## Sample summary", "## Data completeness", "## District context", "## Weight sensitivity", "## Balanced screen", "## Mobility context", "## Interpretation boundary")
            @test occursin(heading, report_text)
        end
        @test report["heat_season_context"]["cells"] == 4
        @test occursin("brussels-heat-season-sample.json", report_text)
        @test occursin("ERA5", report_text)
        @test !occursin("join_heat.py", report_text)
        @test occursin("| STALINGRAD | 9 | 84.0 | 489.9 m | 1 |", report_text)
        @test report_text == read(joinpath(TreesSurfaces.DATA_DIR, "tree-signal-analysis.md"), String)
        @test read(joinpath(directory, "tree-signal-balanced-screen.csv"), String) == read(joinpath(TreesSurfaces.DATA_DIR, "tree-signal-balanced-screen.csv"), String)
    end
    mktempdir() do temporary_root
        data_dir = joinpath(temporary_root, "data")
        cp(TreesSurfaces.DATA_DIR, data_dir)
        counter = "CB2105"
        flow_path = joinpath(data_dir, "brussels-tree-counter-flow.json")
        flow = TreesSurfaces.read_json_path(flow_path)
        flow["counter_flow"][counter]["measured"] = false
        flow["counter_flow"][counter]["mean_all"] = nothing
        flow["counters_without_measured_flow"] = sort(vcat(flow["counters_without_measured_flow"], [counter]))
        wbgt_path = joinpath(data_dir, Wbgt.WBGT_FILENAME)
        wbgt = TreesSurfaces.read_json_path(wbgt_path)
        wbgt["period_sensitivity"]["top_ten_overlap"]["seasonal_mean_vs_reference_day"] = 4
        wbgt["window"]["start_year"] = 2015
        wbgt["window"]["end_year"] = 2017
        wbgt["window"]["seasons"] = 3
        TreesSurfaces.atomic_write_json(wbgt_path, wbgt)
        season_path = joinpath(data_dir, HeatSeason.HEAT_SEASON_FILENAME)
    committed_season = TreesSurfaces.read_json_path(season_path)
    for field in ("request_url", "grid_probe_url")
        @test occursin("timezone=UTC", committed_season[field])
    end
        season = TreesSurfaces.read_json_path(season_path)
        season["cells"][1]["hottest_season_year"] = "2019"
        TreesSurfaces.atomic_write_json(season_path, season)
        for row in TreesSurfaces.records(flow)
            if row["nearest_counter"] == counter
                row["has_measured_flow"] = false
                row["counter_flow_mean"] = nothing
            end
        end
        TreesSurfaces.atomic_write_json(flow_path, flow)
        history_path = joinpath(data_dir, "brussels-bike-history-$(counter)-2024-01.json")
        history = TreesSurfaces.read_json_path(history_path)
        for row in TreesSurfaces.records(history)
            row["count"] = 1000
        end
        TreesSurfaces.atomic_write_json(history_path, history)

        output_dir = joinpath(temporary_root, "generated")
        report = Analysis.generate_signal_artifacts(output_dir; data_dir = data_dir)
        @test report["data_completeness"]["measured_flow_context_records"] == 88
        report_text = read(joinpath(output_dir, "tree-signal-analysis.md"), String)
        @test occursin("without usable measured history", report_text)
        @test occursin("absent or did not qualify as measured", report_text)
        @test occursin("share 4/10", report_text)
        @test !occursin("share 7/10", report_text)
        @test occursin("2015–2017 (3 summers) daily archive", report_text)
        @test !occursin("2008–2017 (10 summers) daily archive", report_text)
        @test occursin("cell-specific warmest seasons differ (2018, 2019)", report_text)
        @test !occursin("2018 was the warmest season across all sampled cells", report_text)
        measured_counts = Float64[]
        for feature in Flow.COUNTERS
            feature == counter && continue
            payload = TreesSurfaces.read_json_path(joinpath(data_dir, "brussels-bike-history-$(feature)-2024-01.json"))
            append!(measured_counts, [TreesSurfaces.number(row["count"]) for row in TreesSurfaces.records(payload)])
        end
        expected_mean = round(sum(measured_counts) / length(measured_counts); digits = 1)
        expected_max = round(Int, maximum(measured_counts))
        @test occursin("2,688 fifteen-minute observations (4 counters × 672)", report_text)
        @test occursin("mean count $(expected_mean), maximum $(expected_max)", report_text)
        @test !occursin("mean count 1000.0", report_text)

        for feature in Flow.COUNTERS
            flow["counter_flow"][feature]["measured"] = false
            flow["counter_flow"][feature]["mean_all"] = nothing
        end
        for row in TreesSurfaces.records(flow)
            row["has_measured_flow"] = false
            row["counter_flow_mean"] = nothing
        end
        flow["counters_without_measured_flow"] = sort(unique(row["nearest_counter"] for row in TreesSurfaces.records(flow)))
        TreesSurfaces.atomic_write_json(flow_path, flow)
        all_unmeasured_dir = joinpath(temporary_root, "all-unmeasured")
        all_unmeasured_report = Analysis.generate_signal_artifacts(all_unmeasured_dir; data_dir = data_dir)
        @test all_unmeasured_report["data_completeness"]["measured_flow_context_records"] == 0
        all_unmeasured_text = read(joinpath(all_unmeasured_dir, "tree-signal-analysis.md"), String)
        @test occursin("0 fifteen-minute observations (0 counters × 672)", all_unmeasured_text)
        @test occursin("no measured count statistics are available", all_unmeasured_text)
    end
    # ERA5 seasonal heat context: grid snapping, source validation, aggregation, and the
    # committed snapshot must all describe the same measurements.
    @test HeatSeason.era5_grid_point(50.85, 4.36) == (50.75, 4.25)
    @test HeatSeason.era5_grid_point(50.90, 4.45) == (51.0, 4.5)
    @test HeatSeason.era5_grid_point(50.79, 4.30) == (50.75, 4.25)
    @test HeatSeason.era5_grid_key(50.75, 4.25) == "50.75/4.25"
    @test_throws ErrorException HeatSeason.era5_grid_point(NaN, 4.25)
    @test occursin("models=era5", HeatSeason.archive_request_url([(50.75, 4.25)]))
    @test occursin("start_date=2016-08-24", HeatSeason.grid_probe_request_url([(50.84, 4.34)]))
    # The daily aggregates are UTC-day values. Losing this parameter would silently change the
    # seasonal series, so it is asserted here and against the committed artifact below.
    @test occursin("timezone=UTC", HeatSeason.archive_request_url([(50.75, 4.25)]))
    @test occursin("timezone=UTC", HeatSeason.grid_probe_request_url([(50.84, 4.34)]))
    probe_point = HeatSeason.era5_grid_point(50.84, 4.34)
    probe_payload = Dict("latitude" => probe_point[1], "longitude" => probe_point[2], "daily_units" => Dict("temperature_2m_max" => "°C"), "daily" => Dict("time" => [HeatSeason.REFERENCE_DATE], "temperature_2m_max" => [31.0]))
    @test HeatSeason.validate_grid_probe_payload(probe_payload, 50.84, 4.34) == probe_point
    @test_throws ErrorException HeatSeason.validate_grid_probe_payload(merge(probe_payload, Dict("latitude" => probe_point[1] + 0.25)), 50.84, 4.34)
    stub_validated = HeatSeason.validate_era5_daily_payload(stub_era5_payload(50.75, 4.25), 50.75, 4.25)
    stub_metrics = HeatSeason.season_metrics(stub_validated)
    @test stub_metrics["season_days"] == 920
    @test stub_metrics["season_year_count"] == 10
    @test stub_metrics["hot_days_per_season"] == 3.1
    @test stub_metrics["tropical_nights_per_season"] == 0.1
    @test stub_metrics["hottest_season_year"] == "2019"
    @test stub_metrics["warmest_season_apparent_tmax_c"] == 33.0
    @test stub_metrics["reference_date_season_percentile"] == 98.9
    @test stub_metrics["reference_date_window_percentile"] == 99.9
    @test stub_metrics["reference_date_rank_within_season"] == 92
    @test stub_metrics["seasonal_mean_apparent_tmax_c"] == 25.22
    tied_validated = HeatSeason.validate_era5_daily_payload(
        stub_era5_payload(50.75, 4.25; mutate = payload -> (fill!(payload["daily"]["apparent_temperature_max"], 25.0); fill!(payload["daily"]["temperature_2m_max"], 26.0); payload)),
        50.75,
        4.25,
    )
    tied_metrics = HeatSeason.season_metrics(tied_validated)
    @test tied_metrics["reference_date_rank_within_season"] == 1
    @test tied_metrics["reference_date_season_percentile"] == 0.0
    @test_throws ErrorException HeatSeason.validate_era5_daily_payload(stub_era5_payload(51.0, 4.5), 50.75, 4.25)
    @test_throws ErrorException HeatSeason.validate_era5_daily_payload(
        stub_era5_payload(50.75, 4.25; mutate = payload -> (payload["daily"]["apparent_temperature_max"] = Any[payload["daily"]["apparent_temperature_max"]...]; payload["daily"]["apparent_temperature_max"][1] = nothing; payload)),
        50.75,
        4.25,
    )
    @test_throws ErrorException HeatSeason.validate_era5_daily_payload(
        stub_era5_payload(50.75, 4.25; mutate = payload -> (payload["daily"]["temperature_2m_max"][1] = NaN; payload)),
        50.75,
        4.25,
    )
    @test_throws ErrorException HeatSeason.validate_era5_daily_payload(
        stub_era5_payload(50.75, 4.25; mutate = payload -> (payload["daily_units"]["apparent_temperature_max"] = "°F"; payload)),
        50.75,
        4.25,
    )
    @test_throws ErrorException HeatSeason.validate_era5_daily_payload(
        stub_era5_payload(50.75, 4.25; mutate = payload -> (pop!(payload["daily"], "temperature_2m_min"); payload)),
        50.75,
        4.25,
    )
    @test_throws ErrorException HeatSeason.validate_era5_daily_payload(
        stub_era5_payload(50.75, 4.25; mutate = payload -> (payload["daily"]["time"][end] = "2025-12-31"; payload)),
        50.75,
        4.25,
    )
    @test_throws ErrorException HeatSeason.validate_era5_daily_payload(
        stub_era5_payload(50.75, 4.25; mutate = payload -> (payload["daily"]["time"][100] = payload["daily"]["time"][99]; payload)),
        50.75,
        4.25,
    )
    @test_throws ErrorException HeatSeason.validate_era5_daily_payload(
        stub_era5_payload(50.75, 4.25; mutate = payload -> (payload["daily"]["apparent_temperature_max"][1] = 100.0; payload)),
        50.75,
        4.25,
    )
    @test_throws ErrorException HeatSeason.validate_era5_daily_payload(
        stub_era5_payload(50.75, 4.25; mutate = payload -> (payload["daily"]["temperature_2m_min"][1] = 44.0; payload)),
        50.75,
        4.25,
    )
    stub_cells = cells -> [stub_era5_payload(cell[1], cell[2]) for cell in cells]
    stub_probes = points -> [
        Dict(
            "latitude" => HeatSeason.era5_grid_point(point[1], point[2])[1],
            "longitude" => HeatSeason.era5_grid_point(point[1], point[2])[2],
            "daily_units" => Dict("temperature_2m_max" => "°C"),
            "daily" => Dict("time" => [HeatSeason.REFERENCE_DATE], "temperature_2m_max" => [31.0]),
        )
        for point in points
    ]
    season_source = joinpath(TreesSurfaces.DATA_DIR, "brussels-trees-sample.json")
    mktempdir() do directory
        output = joinpath(directory, HeatSeason.HEAT_SEASON_FILENAME)
        season = HeatSeason.generate_heat_season(season_source, output; fetch_cells = stub_cells, fetch_grid_probes = stub_probes)
        @test length(season["records"]) == 100
        @test season["model"] == "era5"
        @test occursin("models=era5", season["grid_probe_url"])
        @test season["region_summary"]["cells"] == 4
        @test season["season"]["season_days"] == 920
        @test length(season["cells"]) == 4
        @test Set(record["grid_key"] for record in season["records"]) == Set(["50.75/4.25", "50.75/4.5", "51.0/4.25", "51.0/4.5"])
        cells_by_key = Dict(cell["grid_key"] => cell for cell in season["cells"])
        for record in season["records"]
            @test record["seasonal_mean_apparent_tmax_c"] == cells_by_key[record["grid_key"]]["seasonal_mean_apparent_tmax_c"]
            @test record["reference_date_season_percentile"] == cells_by_key[record["grid_key"]]["reference_date_season_percentile"]
        end
        @test read(output, String) == string(TreesSurfaces.JSON3.write(season), "\n")
    end
    # A response returned for the wrong grid point must be refused, not attached to a tree.
    mktempdir() do directory
        @test_throws ErrorException HeatSeason.generate_heat_season(
            season_source,
            joinpath(directory, HeatSeason.HEAT_SEASON_FILENAME);
            fetch_cells = cells -> reverse([stub_era5_payload(cell[1], cell[2]) for cell in cells]),
            fetch_grid_probes = stub_probes,
        )
        @test !isfile(joinpath(directory, HeatSeason.HEAT_SEASON_FILENAME))
        @test_throws ErrorException HeatSeason.generate_heat_season(
            season_source,
            joinpath(directory, HeatSeason.HEAT_SEASON_FILENAME);
            fetch_cells = stub_cells,
            fetch_grid_probes = points -> [merge(first(stub_probes([point])), Dict("latitude" => HeatSeason.era5_grid_point(point[1], point[2])[1] + 0.25)) for point in points],
        )
        @test !isfile(joinpath(directory, HeatSeason.HEAT_SEASON_FILENAME))
    end
    @test_throws ErrorException HeatSeason.build_heat_season_payload(Dict("records" => Any[]), Any[], "https://example.test")
    @test_throws ErrorException HeatSeason.build_heat_season_payload(Dict("records" => Any[]), [Dict("grid_key" => "duplicate"), Dict("grid_key" => "duplicate")], "https://example.test")
    season_context = HeatSeason.season_context(TreesSurfaces.DATA_DIR)
    @test season_context["available"]
    @test season_context["cells"] == 4
    @test season_context["season_days"] == 920
    @test season_context["reference_percentile_min"] > 90.0
    @test validation["heat_season_records"] == 100
    @test validation["heat_season_cells"] == 4
    @test validation["heat_wbgt_records"] == 100

    # EPSG:3035 must match PROJ's oblique LAEA exactly. These reference values come from an
    # independent pyproj transform; two earlier hand-rolled variants were wrong by ~164 km
    # (dropped semi-major axis) and ~169 m (shared x/y scale in the oblique case), so the
    # tolerance here is deliberately far tighter than one 100 m grid cell.
    laea_reference = [
        (50.839932, 4.342365, 3922928.318690623, 3096334.801671328),
        (50.843006, 4.345726, 3923190.4912545034, 3096657.6237570494),
        (50.843069, 4.345959, 3923207.3841136266, 3096663.347477221),
        (50.843061, 4.345439, 3923170.815044571, 3096665.287637465),
        (50.842939, 4.346216, 3923224.314498953, 3096647.524489761),
    ]
    for (latitude, longitude, expected_x, expected_y) in laea_reference
        x, y = Wbgt.wgs84_to_laea_europe(latitude, longitude)
        @test isapprox(x, expected_x; atol = 1e-6)
        @test isapprox(y, expected_y; atol = 1e-6)
    end
    origin_x, origin_y = Wbgt.wgs84_to_laea_europe(52.0, 10.0)
    @test isapprox(origin_x, 4321000.0; atol = 1e-6)
    @test isapprox(origin_y, 3210000.0; atol = 1e-6)
    @test Wbgt.archive_filename(2016) == "WBGT_year_daily_max_2016.nc"
    @test occursin("compressed_daily/Brussels", Wbgt.archive_url(2016))
    mktempdir() do directory
        # A truncated or runaway transfer must be caught before it is treated as an archive.
        small = joinpath(directory, "small.nc")
        write(small, zeros(UInt8, 1024))
        @test_throws ErrorException Wbgt.validate_archive_download(small, "fixture")
        minimum_size = joinpath(directory, "minimum.nc")
        open(minimum_size, "w") do io
            truncate(io, Wbgt.MIN_ARCHIVE_BYTES)
        end
        @test Wbgt.validate_archive_download(minimum_size, "fixture") == Wbgt.MIN_ARCHIVE_BYTES
        oversized = joinpath(directory, "oversized.nc")
        open(oversized, "w") do io
            truncate(io, Wbgt.MAX_RESPONSE_BYTES + 1)
        end
        @test_throws ErrorException Wbgt.validate_archive_download(oversized, "fixture")
    end
    balanced_ids = Set(row["id"] for row in TreesSurfaces.records(TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-trees-sample.json"))))
    balanced_path = joinpath(TreesSurfaces.DATA_DIR, "tree-signal-balanced-screen.csv")
    @test length(Wbgt.balanced_screen_top_ids(balanced_path, balanced_ids)) == 10
    mktempdir() do directory
        short_screen = joinpath(directory, "short.csv")
        write(short_screen, "rank,id,street\n1,vbx_56544,Some street\n")
        @test_throws ErrorException Wbgt.balanced_screen_top_ids(short_screen, balanced_ids)
        unknown_screen = joinpath(directory, "unknown.csv")
        write(unknown_screen, "rank,id,street\n" * join(["$(rank),unknown_$(rank),Street" for rank in 1:10], "\n"))
        @test_throws ErrorException Wbgt.balanced_screen_top_ids(unknown_screen, balanced_ids)
    end

    mktempdir() do directory
        archive_path = joinpath(directory, Wbgt.archive_filename(2016))
        write_stub_wbgt_archive(archive_path, 2016; scale_factor = 0.01, add_offset = 1.25)
        archive = Wbgt.read_wbgt_year(archive_path)
        @test length(archive.dates) == 366
        @test first(archive.dates) == "2016-01-01"
        @test last(archive.dates) == "2016-12-31"
        @test archive.dates[Wbgt.reference_index(archive.dates)] == Wbgt.REFERENCE_DATE
        @test size(archive.wbgt) == (301, 301, 366)
        @test archive.scale_factor == 0.01
        @test isapprox(archive.wbgt[1, 1, 1], 20.0 + 6.0 * (1.0 - hash_01(7919 + 104729)) + 1.25; atol = 0.01)
        @test 20.0 <= minimum(archive.wbgt) <= maximum(archive.wbgt) <= 40.0
        @test Wbgt.season_indices(archive.dates, 2016) |> length == 92
        @test Wbgt.validate_daily_time_offsets(0:365, "fixture") == collect(Int64, 0:365)
        for malformed_time in (Int64[], [0, 1, 3], [0, 1, 1, 2], [0, 2, 1], [0.0, 1.5], [0.0, Inf])
            @test_throws ErrorException Wbgt.validate_daily_time_offsets(malformed_time, "fixture")
        end
        full_year_dates = [Dates.format(date, dateformat"yyyy-mm-dd") for date in Date(2016, 1, 1):Day(1):Date(2016, 12, 31)]
        @test Wbgt.validate_calendar_year_coverage(full_year_dates, 2016, "fixture") === nothing
        @test_throws ErrorException Wbgt.validate_calendar_year_coverage(full_year_dates[1:end-1], 2016, "fixture")
        incomplete_dates = copy(full_year_dates)
        deleteat!(incomplete_dates, 100)
        @test_throws ErrorException Wbgt.validate_calendar_year_coverage(incomplete_dates, 2016, "fixture")
        @test Wbgt.validate_grid_axis([0.0, 100.0, 200.0], "x", "fixture") === nothing
        for malformed_axis in ([0.0], [0.0, 100.0, 190.0], [0.0, -100.0, -200.0], [0.0, 100.0, Inf])
            @test_throws ErrorException Wbgt.validate_grid_axis(malformed_axis, "y", "fixture")
        end

        source = TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-trees-sample.json"))
        trees = TreesSurfaces.records(source)
        @test_throws ErrorException Wbgt.load_wbgt_years(directory, trees; years = [2015, 2017])
        @test_throws ErrorException Wbgt.load_wbgt_years(directory, trees; years = [2016, 2015])
        @test_throws ErrorException Wbgt.load_wbgt_years(directory, trees; years = [2015, true])
        sampled = Wbgt.sample_tree_points(archive, trees)
        @test length(sampled) == 100
        @test Set(row["id"] for row in sampled) == Set(row["id"] for row in trees)
        # Every tree must land within half a grid step of its assigned 100 m cell centre.
        @test all(abs(row["offset_east_m"]) <= 50.0 for row in sampled)
        @test all(abs(row["offset_north_m"]) <= 50.0 for row in sampled)
        @test all(1 <= row["column"] <= 301 && 1 <= row["row"] <= 301 for row in sampled)
        @test_throws ErrorException Wbgt.sample_tree_points(archive, [Dict{String, Any}("id" => "x", "latitude" => 48.0, "longitude" => 4.3)])
        @test_throws ErrorException Wbgt.sample_tree_points(archive, [Dict{String, Any}("id" => "x", "latitude" => 50.85, "longitude" => NaN)])
        @test_throws ErrorException Wbgt.sample_tree_points(
            archive,
            [Dict{String, Any}("id" => "outside-grid", "latitude" => 0.0, "longitude" => 0.0)];
            envelope = (-90.0, 90.0, -180.0, 180.0),
        )

        # A full multi-year artifact through the real reader, with the archive path injected
        # instead of downloaded.
        for year in 2015:2016
            write_stub_wbgt_archive(joinpath(directory, Wbgt.archive_filename(year)), year)
        end
        output = joinpath(directory, Wbgt.WBGT_FILENAME)
        payload = Wbgt.generate_wbgt_context(
            joinpath(TreesSurfaces.DATA_DIR, "brussels-trees-sample.json"),
            output;
            cache_dir = directory,
            years = 2015:2016,
            extra = Dict{String, Any}("balanced_top_ids" => ["vbx_56544"]),
        )
        @test isfile(output)

        # The artifact is published as a single-line JSON file, so regeneration must be
        # byte-identical from the same cache: otherwise an intended change is
        # indistinguishable from serialization churn in review.
        repeated = joinpath(directory, "repeated", Wbgt.WBGT_FILENAME)
        mkpath(dirname(repeated))
        Wbgt.generate_wbgt_context(
            joinpath(TreesSurfaces.DATA_DIR, "brussels-trees-sample.json"),
            repeated;
            cache_dir = directory,
            years = 2015:2016,
            extra = Dict{String, Any}("balanced_top_ids" => ["vbx_56544"]),
        )
        @test read(output) == read(repeated)
        serialized = read(output, String)
        # Pin the number convention: integer-valued fields stay integers, everything the
        # payload computes as Float64 is written as a JSON float. A type change must be
        # deliberate, because it rewrites the whole line.
        @test occursin("\"step_metres\":100.0", serialized)
        @test occursin("\"rows\":301", serialized)
        @test !occursin("\"rows\":301.0", serialized)
        @test occursin("\"column\":", serialized) && occursin("\"row\":", serialized)
        @test !occursin(r"\"column\":\d+\.", serialized)
        # Coordinates come from an integral 100 m axis, so they must be whole metres.
        @test all(isinteger(record["cell_x"]) && isinteger(record["cell_y"]) for record in payload["records"])
        @test payload["grid"]["step_metres"] == 100.0
        @test payload["crs"] == "EPSG:3035"
        @test length(payload["records"]) == 100
        @test payload["window"]["seasons"] == 2
        @test occursin("2015–2016 window", payload["interpretation_boundary"])
        @test payload["region_summary"]["trees"] == 100
        @test payload["region_summary"]["distinct_cells"] > 1
        # The reference day must be the seasonal extreme in this fixture.
        @test all(Float64(row["reference_date_wbgt_c"]) >= Float64(row["seasonal_mean_wbgt_c"]) for row in payload["records"])
        @test all(Float64(row["reference_percentile_in_season"]) > 90.0 for row in payload["records"])
        # The two periods use opposite cell levels, so their rankings must disagree substantially.
        # This is weaker than "disjoint" because the fixture carries trees in only ~17 grid columns
        # with a narrow annual spread; the real archive is not that coarse.
        overlap = payload["period_sensitivity"]["top_ten_overlap"]
        @test overlap["seasonal_mean_vs_reference_day"] <= 4
        @test payload["period_sensitivity"]["balanced_top_ten_ids"] == ["vbx_56544"]
        @test payload["licence_review"]["status"] == "unresolved"
        related = payload["licence_review"]["related_records"]
        @test length(related) == 2
        @test all(record["applies_to_this_archive"] == false for record in related)
        cds = only(filter(record -> occursin("Copernicus", record["name"]), related))
        @test cds["licence"] == "CC-BY-4.0"
        @test occursin("no WBGT", cds["covers"])
        @test occursin("no licence attribute", payload["licence_review"]["detail"])
        @test read(output, String) == string(JSON3.write(payload), "\n")

        # A missing cache without a fetch callback must fail loudly instead of silently
        # producing an empty context.
        empty_dir = joinpath(directory, "empty")
        mkpath(empty_dir)
        @test_throws ErrorException Wbgt.generate_wbgt_context(
            joinpath(TreesSurfaces.DATA_DIR, "brussels-trees-sample.json"),
            joinpath(empty_dir, Wbgt.WBGT_FILENAME);
            cache_dir = empty_dir,
            years = 2015:2015,
        )

        # A file whose declared CRS is not EPSG:3035 must be refused rather than sampled with the
        # wrong transform.
        wrong_crs = joinpath(directory, "wrong-crs.nc")
        write_stub_wbgt_archive(wrong_crs, 2016)
        h5open(wrong_crs, "r+") do handle
            attrs(handle)["crs"] = "EPSG:4326"
        end
        @test_throws ErrorException Wbgt.read_wbgt_year(wrong_crs)
    end

    # Outage-shaped and incomplete counter windows must be reported as unmeasured rather than as
    # zero flow. CB1101 was offline for nearly four years and CB1143 stopped reporting in 2025;
    # both are committed snapshot targets.
    mktempdir() do directory
        for feature in Flow.COUNTERS
            payload = TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-bike-history-$(feature)-2024-01.json"))
            rows = TreesSurfaces.records(payload)
            counts = [TreesSurfaces.number(get(row, "count", 0)) for row in rows]
            if feature == "CB1143"
                # An outage: the slot series stays complete but records no movement.
                for row in rows
                    row["count"] = 0
                end
            elseif feature == "CJM90"
                # A degraded device: only a fraction of the expected slots are present.
                payload["records"] = rows[1:length(rows) ÷ 2]
            end
            TreesSurfaces.atomic_write_json(joinpath(directory, "brussels-bike-history-$(feature)-2024-01.json"), payload)
        end
        cp(
            joinpath(TreesSurfaces.DATA_DIR, "brussels-tree-bike-nearest.json"),
            joinpath(directory, "brussels-tree-bike-nearest.json"),
        )
        flow = Flow.generate_counter_flow_artifact(directory; data_dir = directory)
        @test flow["counter_flow"]["CB1143"]["measured"] == false
        @test flow["counter_flow"]["CB1143"]["mean_all"] === nothing
        @test occursin("treated as unmeasured", flow["counter_flow"]["CB1143"]["reason"])
        @test flow["counter_flow"]["CJM90"]["measured"] == false
        @test occursin("slots where", flow["counter_flow"]["CJM90"]["reason"])
        @test flow["counter_flow"]["CB1101"]["measured"] == true
        @test flow["counter_flow"]["CB1101"]["mean_all"] == 17.872
        @test Set(flow["counters_without_measured_flow"]) == Set(["CB02411", "CB1143", "CJE181", "CJM90"])
        # Trees attached to counters outside the committed five have no history in this dataset,
        # so they are unmeasured for a different reason than an outage week.
        unmeasured_ids = Set(
            row["id"] for row in flow["records"]
            if row["nearest_counter"] in ("CB1143", "CJM90") || !(row["nearest_counter"] in Flow.COUNTERS)
        )
        @test length(unmeasured_ids) == 9 + 15 + 3
        @test flow["trees_with_measured_flow"] == 100 - length(unmeasured_ids)
        @test all(row["counter_flow_mean"] === nothing for row in flow["records"] if row["id"] in unmeasured_ids)
        @test all(row["has_measured_flow"] == false for row in flow["records"] if row["id"] in unmeasured_ids)
        # Every tree that survives the outage screen still carries real flow.
        @test all(row["has_measured_flow"] == true for row in flow["records"] if !(row["id"] in unmeasured_ids))
    end
    mktempdir() do directory
        for feature in Flow.COUNTERS
            cp(
                joinpath(TreesSurfaces.DATA_DIR, "brussels-bike-history-$(feature)-2024-01.json"),
                joinpath(directory, "brussels-bike-history-$(feature)-2024-01.json"),
            )
        end
        duplicate_payload = TreesSurfaces.read_json_path(joinpath(directory, "brussels-bike-history-CJM90-2024-01.json"))
        duplicate_rows = TreesSurfaces.records(duplicate_payload)
        duplicate_rows[end] = deepcopy(duplicate_rows[end - 1])
        duplicate_payload["records"] = duplicate_rows
        TreesSurfaces.atomic_write_json(joinpath(directory, "brussels-bike-history-CJM90-2024-01.json"), duplicate_payload)
        cp(joinpath(TreesSurfaces.DATA_DIR, "brussels-tree-bike-nearest.json"), joinpath(directory, "brussels-tree-bike-nearest.json"))
        duplicate_flow = Flow.generate_counter_flow_artifact(directory; data_dir = directory)
        @test duplicate_flow["counter_flow"]["CJM90"]["measured"] == false
        @test occursin("missing or duplicate", duplicate_flow["counter_flow"]["CJM90"]["reason"])
        # Appending a duplicate row keeps every expected slot present, so only the row count
        # reveals the double count. It must still be rejected rather than inflating the mean.
        appended_payload = TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-bike-history-CJM90-2024-01.json"))
        push!(TreesSurfaces.records(appended_payload), deepcopy(TreesSurfaces.records(appended_payload)[end]))
        TreesSurfaces.atomic_write_json(joinpath(directory, "brussels-bike-history-CJM90-2024-01.json"), appended_payload)
        appended_flow = Flow.generate_counter_flow_artifact(directory; data_dir = directory)
        @test appended_flow["counter_flow"]["CJM90"]["measured"] == false
        @test occursin("slots where", appended_flow["counter_flow"]["CJM90"]["reason"])
        incomplete_days = TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-bike-history-CB1101-2024-01.json"))
        original_rows = TreesSurfaces.records(incomplete_days)
        day_two = [deepcopy(row) for row in original_rows if startswith(TreesSurfaces.text(row["count_date"]), "2024/01/02")]
        incomplete_days["records"] = [row for row in original_rows if !startswith(TreesSurfaces.text(row["count_date"]), "2024/01/01")]
        append!(incomplete_days["records"], day_two)
        TreesSurfaces.atomic_write_json(joinpath(directory, "brussels-bike-history-CB1101-2024-01.json"), incomplete_days)
        incomplete_flow = Flow.generate_counter_flow_artifact(directory; data_dir = directory)
        @test incomplete_flow["counter_flow"]["CB1101"]["measured"] == false
        @test incomplete_flow["counter_flow"]["CB1101"]["days"] == 6
        @test occursin("missing or duplicate", incomplete_flow["counter_flow"]["CB1101"]["reason"])
        shifted_payload = TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-bike-history-CB1101-2024-01.json"))
        shifted_payload["records"][1]["count_date"] = "2023/12/31"
        shifted_path = joinpath(directory, "brussels-bike-history-CB1101-2024-01.json")
        TreesSurfaces.atomic_write_json(shifted_path, shifted_payload)
        @test_throws ErrorException Flow.generate_counter_flow_artifact(directory; data_dir = directory)
        valid_payload = TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-bike-history-CB1101-2024-01.json"))
        delete!(valid_payload["records"][1], "count")
        TreesSurfaces.atomic_write_json(shifted_path, valid_payload)
        @test_throws ErrorException Flow.generate_counter_flow_artifact(directory; data_dir = directory)
        valid_payload = TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-bike-history-CB1101-2024-01.json"))
        valid_payload["records"][1]["time_gap"] = true
        TreesSurfaces.atomic_write_json(shifted_path, valid_payload)
        @test_throws ErrorException Flow.generate_counter_flow_artifact(directory; data_dir = directory)
        valid_payload = TreesSurfaces.read_json_path(joinpath(TreesSurfaces.DATA_DIR, "brussels-bike-history-CB1101-2024-01.json"))
        valid_payload["feature"] = "CB1142"
        TreesSurfaces.atomic_write_json(shifted_path, valid_payload)
        @test_throws ErrorException Flow.generate_counter_flow_artifact(directory; data_dir = directory)
    end
    mktempdir() do directory
        flow = Flow.generate_counter_flow_artifact(directory)
        @test flow["record_count"] == 100
        @test flow["trees_with_measured_flow"] == 97
        @test Set(flow["counters_without_measured_flow"]) == Set(["CB02411", "CJE181"])
        @test readdir(directory) == ["brussels-tree-counter-flow.json"]
    end
    @test first(state["screen"]["sites"])["id"] == "vbx_56561"
    proximity_screen = TreesSurfaces.ranked_sites(state["sites"], 0.0, 100.0)
    @test first(proximity_screen["sites"])["id"] == "vbx_56876"
    @test TreesSurfaces.query_number("heat=NaN&proximity=Inf", "heat", 60.0) == 60.0
    @test TreesSurfaces.query_number("heat=NaN&proximity=Inf", "proximity", 40.0) == 40.0
    @test TreesSurfaces.query_number("heat=1%30", "heat", 60.0) == 10.0
    @test TreesSurfaces.query_number("heat=%ZZ", "heat", 60.0) == 60.0
    invalid_screen = TreesSurfaces.ranked_sites(state["sites"], NaN, Inf)
    @test invalid_screen["heatWeight"] == 0.5
    @test invalid_screen["proximityWeight"] == 0.5
    @test all(isfinite(Float64(site["signal"])) for site in invalid_screen["sites"])
    @test length(unique(site["signal"] for site in invalid_screen["sites"])) > 1
    tied_screen = TreesSurfaces.ranked_sites([
        Dict{String,Any}("id"=>"b", "heatScore"=>50.0, "proximityScore"=>50.0),
        Dict{String,Any}("id"=>"a", "heatScore"=>50.0, "proximityScore"=>50.0),
    ], 60.0, 40.0)
    @test [site["id"] for site in tied_screen["sites"]] == ["a", "b"]
    huge_screen = TreesSurfaces.ranked_sites(state["sites"], 1e308, 1e308)
    @test huge_screen["heatWeight"] == 0.5
    @test huge_screen["proximityWeight"] == 0.5
    @test length(unique(site["signal"] for site in huge_screen["sites"])) > 1
    artifact = TreesSurfaces.read_json("tree-signal-sensitivity.json")
    expected_ids = [row["id"] for row in artifact["balanced_screening"][1:10]]
    actual_ids = [row["id"] for row in state["screen"]["sites"][1:10]]
    @test actual_ids == expected_ids
    for (actual, expected) in zip(state["screen"]["sites"], artifact["balanced_screening"])
        @test actual["id"] == expected["id"]
        @test actual["signal"] == expected["signal"]
    end

    mktempdir() do directory
        cp(joinpath(TreesSurfaces.DATA_DIR, "tree-stakeholder-proposal.json"), joinpath(directory, "tree-stakeholder-proposal.json"))
        cp(joinpath(TreesSurfaces.DATA_DIR, "tree-signal-sensitivity.json"), joinpath(directory, "tree-signal-sensitivity.json"))
        row, _ = Review.generate_stakeholder_review_artifacts(directory)
        row["review_status"] = "accepted"
        row["reviewer_name"] = "Multiline Reviewer"
        row["reviewer_role"] = "=Stakeholder"
        row["reviewed_at"] = "2026-09-20T22:37:00+02:00"
        row["accepted_decision_question"] = row["decision_question"]
        row["accepted_spatial_unit"] = row["spatial_unit"]
        row["accepted_mobility_measure"] = row["mobility_measure"]
        row["accepted_heat_period"] = "2016-08-24"
        row["false_positive_preference"] = "Prefer recall"
        row["evidence_threshold"] = "Manual review"
        row["review_notes"] = "'=First line\nSecond line"
        Review.write_csv(joinpath(directory, "tree-stakeholder-review.csv"), row)
        preserved, compiled = Review.generate_stakeholder_review_artifacts(directory)
        @test preserved["reviewer_name"] == "Multiline Reviewer"
        @test preserved["reviewer_role"] == "=Stakeholder"
        @test preserved["review_notes"] == "'=First line\nSecond line"
        worksheet = read(joinpath(directory, "tree-stakeholder-review.csv"), String)
        worksheet_rows = Review.parse_csv_records(worksheet)
        escaped_column = findfirst(==(Review.ESCAPED_FIELDS_COLUMN), worksheet_rows[1])
        @test escaped_column !== nothing
        escape_map = TreesSurfaces.JSON3.read(worksheet_rows[2][escaped_column], Dict{String,Any})
        @test escape_map == Dict{String,Any}("reviewer_role" => "'=Stakeholder")
        @test compiled["record_count"] == 1
        write(joinpath(directory, "tree-stakeholder-review.csv"), replace(worksheet, "'=Stakeholder" => "Stakeholder"; count=1))
        edited, _ = Review.generate_stakeholder_review_artifacts(directory)
        @test edited["reviewer_role"] == "Stakeholder"
        @test edited["review_notes"] == "'=First line\nSecond line"
        edited_rows = Review.parse_csv_records(read(joinpath(directory, "tree-stakeholder-review.csv"), String))
        @test TreesSurfaces.JSON3.read(edited_rows[2][escaped_column], Dict{String,Any}) == Dict{String,Any}()
        date_only_review = copy(preserved)
        date_only_review["reviewed_at"] = "2026-09-20"
        @test Review.validate_review(date_only_review, Set(["accepted", "accepted with changes", "needs more evidence", "rejected"]))
    end

    index_response = TreesSurfaces.handler(HTTP.Request("GET", "/"))
    index_html = String(index_response.body)
    nonce_match = match(r"<script nonce=\"([^\"]+)\">", index_html)
    @test nonce_match !== nothing
    content_security_policy = HTTP.header(index_response, "Content-Security-Policy")
    @test occursin("script-src 'nonce-$(nonce_match.captures[1])'", content_security_policy)
    @test occursin("style-src 'nonce-$(nonce_match.captures[1])'", content_security_policy)
    @test occursin("<style nonce=\"$(nonce_match.captures[1])\" id=\"siteStyles\"></style>", index_html)
    @test !occursin(" style=", index_html)
    @test !occursin("unsafe-inline", content_security_policy)
    encoded_query_response = TreesSurfaces.handler(HTTP.Request("GET", "/api/screen?heat=1%30&proximity=9%30"))
    encoded_screen = TreesSurfaces.JSON3.read(String(encoded_query_response.body), Dict{String,Any})
    @test isapprox(encoded_screen["heatWeight"], 0.1)
    @test isapprox(encoded_screen["proximityWeight"], 0.9)
    health_response = TreesSurfaces.handler(HTTP.Request("GET", "/health"))
    @test health_response.status == 200
    @test HTTP.header(health_response, "X-Content-Type-Options") == "nosniff"
    @test HTTP.header(health_response, "X-Frame-Options") == "DENY"
    head_response = TreesSurfaces.handler(HTTP.Request("HEAD", "/health"))
    @test head_response.status == 200
    post_response = TreesSurfaces.handler(HTTP.Request("POST", "/health"))
    @test post_response.status == 405
    @test HTTP.header(post_response, "Allow") == "GET, HEAD"

    html = TreesSurfaces.render_index()
    @test !occursin("__INITIAL_STATE__", html)
    @test !occursin("__CSP_NONCE__", html)
    @test occursin("Julia-served exploratory view", html)
    @test occursin("vbx_56561", html)
    @test occursin("\"heatOverlap\":9", html)
end
