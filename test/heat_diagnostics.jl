using Test
include(joinpath(@__DIR__, "..", "src", "HeatDiagnostics.jl"))
using .HeatDiagnostics

@testset "Offline heat-support diagnostics" begin
    @test midranks([4., 4., 2., 1.]) == [1.5, 1.5, 3., 4.]
    top = top_set([4., 4., 2.], ["b", "a", "c"], 1)
    @test top["exact_ids"] == ["a"]
    @test top["inclusive_ids"] == ["a", "b"]
    @test top["cutoff_ties"] == 2
    @test_throws ErrorException top_set([1.], ["a"], 0)
    @test_throws ErrorException top_set([1.], ["a", "b"], 1)
    v = variance_partition([0., 2., 8.], ["a", "a", "b"])
    @test v["within"] ≈ 2/3
    @test v["between"] ≈ 98/9
    @test v["total"] ≈ 104/9
    equal = variance_partition([0., 2., 8.], ["a", "a", "b"]; equal_cells=true)
    @test equal["within"] == 0.5
    @test equal["between"] == 12.25
    @test variance_partition([2., 2.], ["a", "b"])["within_fraction"] === nothing
    @test HeatDiagnostics.comparison([1., 1.], [2., 3.], ["a", "b"], 1)["spearman"] === nothing
    tied = HeatDiagnostics.comparison([4., 4., 2.], [4., 2., 2.], ["a", "b", "c"], 1)
    @test tied["spearman"] ≈ 0.5
    @test tied["inclusive_jaccard"] == 0.5
    # Rank diagnostics are invariant under monotone min-max scaling.
    @test midranks([10., 30., 30., 50.]) == midranks([0., 50., 50., 100.])

    @test [HeatDiagnostics.selection_k(39, p) for p in HeatDiagnostics.SELECTION_PERCENTAGES] == [4, 8, 10, 13, 20]
    sweep = HeatDiagnostics.threshold_sweep([4., 3., 2., 1.], [4., 3., 2., 1.], [1., 2., 3., 4.], ["a", "b", "c", "d"])
    @test [s["k"] for s in sweep] == [1, 1, 1, 2, 2]
    @test all(s["reference_vs_seasonal"]["inclusive_jaccard"] == 0 for s in sweep)
    rounded = HeatDiagnostics.rounding_sweep([1., 2., 3.], [20.01, 20.02, 20.03], [20.01, 20.02, 20.03], ["a", "b", "c"])
    @test rounded[1]["fine_vs_seasonal"]["spearman"] ≈ 1
    @test rounded[1]["seasonal_distinct_values"] == 3
    @test rounded[end]["seasonal_distinct_values"] == 1
    @test rounded[end]["reference_vs_seasonal"]["spearman"] === nothing
    @test rounded[end]["reference_vs_seasonal"]["inclusive_jaccard"] == 1
    @test rounded[end]["fine_vs_seasonal"]["inclusive_jaccard"] == 1/3
    @test length(rounded[end]["fine_vs_seasonal"]["right"]["inclusive_ids"]) == 3
    covered = HeatDiagnostics.coverage_sweep([0., 2., 8.], ["a", "a", "b"], [1., 1., 2.], [1., 1., 2.])
    @test covered[1]["variance_equal_cell"] == equal
    @test covered[2]["cells"] == 1
    @test covered[2]["trees"] == 2
    @test covered[2]["excluded_cells"] == 1
    @test covered[2]["variance_equal_cell"]["within_fraction"] == 1
    @test covered[2]["fine_vs_seasonal"]["spearman"] === nothing
    @test covered[3]["cells"] == covered[3]["trees"] == 0
    @test covered[3]["k"] === nothing
    @test covered[3]["variance_equal_cell"] === nothing
    @test covered[3]["fine_vs_seasonal"] === nothing

    data = joinpath(@__DIR__, "..", "data")
    load() = [HeatDiagnostics.JSON3.read(read(joinpath(data, f), String), Dict{String,Any}) for f in HeatDiagnostics.INPUTS]
    inputs = load()
    report = analyze(inputs...)
    @test report["trees"] == 100
    @test report["cells"] == 39
    @test report["reference_vs_seasonal"]["tree"]["exact_overlap"] == 7
    @test report["tree_top_distinct_cells"]["reference_date_wbgt_c"] == 3
    @test report["tree_top_distinct_cells"]["seasonal_mean_wbgt_c"] == 3
    @test sum(r["trees"] for r in report["cell_records"]) == 100
    @test 0 <= report["variance_equal_cell"]["within_fraction"] <= 1
    @test length(report["leave_one_district_out"]) == 7
    @test report["schema_version"] == 2
    robust = report["robustness"]
    @test robust["rounding_cell"][1]["fine_vs_seasonal"] == report["fine_vs_archive_cell"]["seasonal_mean_wbgt_c"]
    @test robust["threshold_cell"][3]["reference_vs_seasonal"] == report["reference_vs_seasonal"]["cell"]
    @test robust["minimum_cell_coverage"][1]["variance_equal_cell"] == report["variance_equal_cell"]
    @test robust["minimum_cell_coverage"][2]["excluded_cells"] == report["singleton_cells"]
    @test robust["minimum_cell_coverage"][2]["trees"] == report["trees"] - report["singleton_cells"]
    for input in inputs
        reverse!(input["records"])
    end
    @test analyze(inputs...) == report

    inputs = load(); pop!(inputs[2]["records"])
    @test_throws ErrorException analyze(inputs...)
    inputs = load(); push!(inputs[1]["records"], copy(first(inputs[1]["records"])))
    @test_throws ErrorException analyze(inputs...)
    inputs = load(); inputs[2]["records"][1]["heat_pixel"] = 0
    @test_throws ErrorException analyze(inputs...)
    inputs = load(); inputs[2]["records"][1]["latitude"] += 0.0001
    @test_throws ErrorException analyze(inputs...)
    inputs = load(); inputs[3]["records"][1]["seasonal_mean_wbgt_c"] = NaN
    @test_throws ErrorException analyze(inputs...)
    inputs = load(); inputs[3]["records"][1]["column"] = true
    @test_throws ErrorException analyze(inputs...)
    inputs = load()
    group = first(r for r in report["cell_records"] if r["trees"] > 1)
    changed = first(r for r in inputs[3]["records"] if r["id"] == first(group["tree_ids"]))
    changed["seasonal_mean_wbgt_c"] += 0.5
    @test_throws ErrorException analyze(inputs...)
    for mutate in (
        p -> (p[2]["crs"] = "EPSG:4326"),
        p -> (p[3]["reference_date"] = "2017-08-24"),
        p -> (p[3]["value_semantics"] = "daily mean Celsius"),
        p -> (p[3]["grid"]["step_metres"] = 200),
        p -> (p[3]["window"]["start_year"] = 2010),
        p -> (p[3]["records"][1]["reference_date"] = "2017-08-24"))
        inputs = load(); mutate(inputs)
        @test_throws ErrorException analyze(inputs...)
    end
    # A cell straddles districts: dropping A must recompute its fine mean from B.
    inputs = load()
    selected_ids = [r["id"] for r in inputs[1]["records"][1:4]]
    for payload in inputs
        index = Dict(r["id"] => r for r in payload["records"])
        payload["records"] = [index[id] for id in selected_ids]
    end
    for i in 1:4
        inputs[1]["records"][i]["district"] = isodd(i) ? "A" : "B"
        inputs[2]["records"][i]["heat_pixel"] = [10, 30, 25, 25][i]
        row = inputs[3]["records"][i]
        row["column"] = i <= 2 ? 1 : i
        row["row"] = 1
        for metric in HeatDiagnostics.METRICS
            row[metric] = i <= 2 ? 20.0 : 20.0 + i
        end
    end
    synthetic = analyze(inputs...)
    @test synthetic["cell_records"][1]["sampled_fine_mean"] == 20
    dropped = synthetic["leave_one_district_out"]["A"]["comparison"]
    @test dropped["left"]["cutoff"] == 30
    @test dropped["left"]["exact_ids"] == ["1:1"]
    @test dropped["spearman"] == -1
    @test synthetic["leave_one_district_out"]["A"]["trees"] == 2
    mktempdir() do output
        generated = generate(data, output)
        @test generated == report
        @test sort(readdir(output)) == ["heat-support-diagnostics.json", "heat-support-diagnostics.md", "heat-support-ranks.svg", "heat-support-robustness.svg"]
        @test occursin("not an area mean", read(joinpath(output, "heat-support-diagnostics.md"), String))
        @test occursin("<svg", read(joinpath(output, "heat-support-ranks.svg"), String))
        parsed = HeatDiagnostics.JSON3.read(read(joinpath(output, "heat-support-diagnostics.json"), String), Dict{String,Any})
        @test parsed == report
        # Committed results are regenerated, not manually maintained claims.
        committed = joinpath(data, "research", "heat-support-diagnostics.json")
        @test isfile(committed)
        @test parsed == HeatDiagnostics.JSON3.read(read(committed, String), Dict{String,Any})
        for name in ("heat-support-diagnostics.md", "heat-support-ranks.svg", "heat-support-robustness.svg")
            @test isfile(joinpath(data, "research", name))
            @test read(joinpath(output, name), String) == read(joinpath(data, "research", name), String)
        end
        # The same three aggregations are compared with the reference day by two independent
        # generators: this one and the WBGT context artifact. They read the same archive through
        # different code paths, so their tree-level overlaps must agree, and a disagreement means
        # one of them is wrong rather than that the answer changed.
        context = HeatDiagnostics.JSON3.read(
            read(joinpath(data, "brussels-heat-wbgt-sample.json"), String), Dict{String,Any})
        overlaps = context["period_sensitivity"]["top_ten_overlap"]
        @test report["reference_vs_seasonal"]["tree"]["exact_overlap"] ==
              overlaps["seasonal_mean_vs_reference_day"]
        @test report["reference_vs_other_aggregations"]["seasonal_p90_wbgt_c"]["tree"]["exact_overlap"] ==
              overlaps["seasonal_p90_vs_reference_day"]
        @test report["reference_vs_other_aggregations"]["hot_days_per_season"]["tree"]["exact_overlap"] ==
              overlaps["hot_days_vs_reference_day"]
        # Cell-level overlap is a different unit and is expected to be at least as high, since
        # 39 cells give ties more room than 100 trees.
        for metric in ("seasonal_p90_wbgt_c", "hot_days_per_season")
            tree = report["reference_vs_other_aggregations"][metric]["tree"]["exact_overlap"]
            cell = report["reference_vs_other_aggregations"][metric]["cell"]["exact_overlap"]
            @test cell >= tree
        end
    end

@testset "Top-k chance reference" begin
    # Read quoted top-ten overlaps against what independence would give, so a 7/10 or 9/10
    # overlap is not mistaken for evidence beyond what the shared inputs already imply.
    hundred = HeatDiagnostics.chance_top_k(100, 10, 7)
    @test hundred.expected == 1.0
    @test isapprox(hundred.probability_at_least, 8.249e-7, rtol = 1e-3)
    @test isapprox(1 - hundred.probability_observed_or_less, hundred.probability_at_least, rtol = 1e-9)
    @test isapprox(HeatDiagnostics.chance_top_k(100, 10, 2).probability_at_least, 0.2615, atol = 5e-4)
    @test isapprox(HeatDiagnostics.chance_top_k(100, 10, 10).probability_at_least, 5.777e-14, rtol = 1e-3)
    cells = HeatDiagnostics.chance_top_k(39, 10, 7)
    @test isapprox(cells.expected, 2.5641, atol = 5e-4)
    @test isapprox(cells.probability_at_least, 7.189e-4, rtol = 1e-3)
    @test HeatDiagnostics.chance_top_k(5, 5, 5).probability_at_least == 1.0
    @test HeatDiagnostics.chance_top_k(5, 5, 0).probability_at_least == 1.0
    for bad in ((100, 10, 11), (100, 101, 1), (100, 10, -1), (100, 2.5, 1))
        @test_throws ErrorException HeatDiagnostics.chance_top_k(bad...)
    end
end

end
