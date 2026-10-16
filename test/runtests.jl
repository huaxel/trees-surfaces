using Test
using HTTP

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
include(joinpath(@__DIR__, "..", "src", "Review.jl"))
using .Review

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
    history = Dict{String,Any}("feature"=>"CB2105", "startDate"=>"2024/01/01", "endDate"=>"2024/01/07", "data"=>Any[Dict("count"=>1, "count_date"=>"2024/01/$(lpad(day, 2, '0'))", "time_gap"=>slot) for day in 1:7 for slot in 1:96])
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
        for heading in ("## Heat data and normalization", "## Traceability", "## Sample summary", "## Data completeness", "## District context", "## Weight sensitivity", "## Balanced screen", "## Mobility context", "## Interpretation boundary")
            @test occursin(heading, report_text)
        end
        @test !occursin("join_heat.py", report_text)
        @test occursin("| STALINGRAD | 9 | 84.0 | 489.9 m | 1 |", report_text)
        @test report_text == read(joinpath(TreesSurfaces.DATA_DIR, "tree-signal-analysis.md"), String)
        @test read(joinpath(directory, "tree-signal-balanced-screen.csv"), String) == read(joinpath(TreesSurfaces.DATA_DIR, "tree-signal-balanced-screen.csv"), String)
    end
    mktempdir() do directory
        flow = Flow.generate_counter_flow_artifact(directory)
        @test flow["record_count"] == 100
        @test flow["trees_with_measured_flow"] == 97
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
