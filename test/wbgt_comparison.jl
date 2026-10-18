using Test
using Dates
using HDF5
include(joinpath(@__DIR__, "..", "src", "WbgtComparison.jl"))

function paired_stub()
    dates = string.(collect(Date(2016,1,1):Day(1):Date(2016,12,31)))
    cells = [Dict("id" => "$(i):1", "x" => 100.0i, "y" => 100.0, "tree_ids" => ["t$(i)"]) for i in 1:3]
    a = repeat(reshape([10.,12.,14.], 1, 3), 366, 1)
    b = repeat(reshape([20.,18.,16.], 1, 3), 366, 1)
    ref = findfirst(==("2016-08-24"), dates)
    a[ref,:] .+= 1; b[ref,:] .+= 1
    common = (year=2016, dates=dates, time_units="days since 2016-01-01 00:00:00", calendar="proleptic_gregorian",
        x=[100.,200.,300.], y=[100.], cells=cells, scale_factor=0.01, add_offset=0.0, units="°C",
        crs="EPSG:3035")
    merge(common, (statistic=:mean, title="synthetic mean", values=a, filename="mean.nc",
                   path="/synthetic/mean.nc", bytes=1, sha256=repeat("a", 64))),
    merge(common, (statistic=:maximum, title="synthetic maximum", values=b, filename="max.nc",
                   path="/synthetic/max.nc", bytes=2, sha256=repeat("b", 64)))
end

function write_paired_archive(path, statistic, trees)
    W = WbgtComparison.Wbgt
    x = collect(3910011.:100.:3940011.)
    y = collect(3081505.:100.:3111505.)
    samples = W.sample_tree_points((x=x,y=y), trees)
    h5open(path, "w") do f
        attrs(f)["title"] = "Daily $(statistic == :mean ? "average" : "maximum") Wet Bulb Globe Temperature for Brussels for 2016"
        attrs(f)["crs"] = "EPSG:3035"
        f["x"] = x; f["y"] = y; f["time"] = Int64.(0:365)
        attrs(f["time"])["units"] = "days since 2016-01-01 00:00:00"
        attrs(f["time"])["calendar"] = "proleptic_gregorian"
        ds = create_dataset(f, "WBGT", Int16, (301,301,366); chunk=(1,1,366), deflate=1)
        attrs(ds)["units"] = "°C"
        attrs(ds)["scale_factor"] = [0.01]
        for row in samples
            ds[row["column"], row["row"], :] = fill(Int16(statistic == :mean ? 1500 : 2000), 366)
        end
    end
end

@testset "Offline mean/maximum WBGT comparison" begin
    C = WbgtComparison
    W = C.Wbgt
    average, maximum = paired_stub()
    report = C.compare_samples(average, maximum)
    @test report["cells"] == 3
    @test report["season_days"] == 92
    @test report["validation"]["paired_cell_days"] == 1098
    @test report["validation"]["minimum_max_minus_mean_c"] == 2
    @test report["comparisons"]["reference_mean_vs_maximum"]["spearman"] == -1
    @test report["comparisons"]["reference_mean_vs_maximum"]["exact_overlap"] == 0
    @test report["comparisons"]["mean_reference_vs_jja"]["spearman"] == 1
    @test report["records"][1]["jja_mean_of_daily_means_c"] ≈ 10 + 1/92
    @test report["records"][1]["jja_mean_max_minus_mean_c"] == 10
    @test !haskey(report["records"][1], "hot_days_per_season")
    for (key,value) in ((:statistic,:mean), (:year,2017), (:calendar,"standard"),
        (:time_units,"days since 2016-01-01 01:00:00"), (:dates,maximum.dates[1:end-1]),
        (:x,[101.,201.,301.]), (:values,maximum.values[1:end-1,:]), (:cells,reverse(maximum.cells)))
        changed = merge(maximum, NamedTuple{(key,)}((value,)))
        @test_throws ErrorException C.compare_samples(average, changed)
    end
    for bad in (NaN, Inf, 46., -21., 9.)
        values = copy(maximum.values); values[1,1] = bad
        @test_throws ErrorException C.compare_samples(average, merge(maximum, (values=values,)))
    end
    # A mismatched packing (scale or offset) changes the printed °C differences while leaving
    # ranks intact, so it must be refused rather than silently reported.
    for changed in ((scale_factor=0.001,), (add_offset=5.0,), (units="K",), (crs="urn:ogc:def:crs:EPSG::3035",))
        @test_throws ErrorException C.compare_samples(merge(average, changed), maximum)
    end
    # Two inputs with identical content are a duplication or mislabelling, not a comparison.
    @test_throws ErrorException C.compare_samples(average, merge(maximum, (sha256=average.sha256,)))
    @test_throws ErrorException C.compare_samples(average, merge(maximum, (path=average.path,)))
    @test_throws ErrorException C.compare_samples(average, merge(maximum, (values=average.values,)))
    # The paired-order tolerance is inclusive at 1e-8 and must not accept a larger violation.
    tolerated = copy(maximum.values); tolerated[1,1] = average.values[1,1] - 1e-9
    @test C.compare_samples(average, merge(maximum, (values=tolerated,)))["validation"]["paired_cell_days"] == 1098
    violated = copy(maximum.values); violated[1,1] = average.values[1,1] - 2e-8
    @test_throws ErrorException C.compare_samples(average, merge(maximum, (values=violated,)))
    # Hand-computed tie case: with four cells and k=1, the maximum side has two cells tied at the
    # cutoff (20 °C), so the exact top-1 keeps one by ID while the inclusive set keeps both, the
    # mean side keeps one, and the sets do not intersect. Values chosen to be exactly anti-ranked
    # so the midrank Spearman is -1.
    four = [Dict("id" => "$(i):1", "x" => 100.0i, "y" => 100.0, "tree_ids" => ["u$(i)"]) for i in 1:4]
    four_common = (year=2016, dates=average.dates, time_units=average.time_units,
        calendar=average.calendar, crs=average.crs, x=[100.,200.,300.,400.], y=[100.], cells=four,
        scale_factor=0.01, add_offset=0.0, units="°C")
    means = repeat(reshape([10.,10.,12.,14.], 1, 4), 366, 1)
    maxima = repeat(reshape([20.,20.,18.,16.], 1, 4), 366, 1)
    tied = C.compare_samples(
        merge(four_common, (statistic=:mean, title="synthetic mean", values=means,
                            filename="m.nc", path="/m.nc", bytes=1, sha256=repeat("c", 64))),
        merge(four_common, (statistic=:maximum, title="synthetic maximum", values=maxima,
                            filename="x.nc", path="/x.nc", bytes=2, sha256=repeat("d", 64))))
    tied_comparison = tied["comparisons"]["reference_mean_vs_maximum"]
    @test tied["selection_k"] == 1
    @test tied_comparison["spearman"] == -1
    @test tied_comparison["exact_overlap"] == 0
    @test length(tied_comparison["left"]["inclusive_ids"]) == 1
    @test length(tied_comparison["right"]["inclusive_ids"]) == 2
    @test tied_comparison["inclusive_jaccard"] == 0.0
    # Constant-but-equal ranks are undefined, not zero, and stay distinguishable from a duplicate.
    flat = C.compare_samples(merge(average, (values=fill(10.0, size(average.values)),)),
                             merge(maximum, (values=fill(12.0, size(maximum.values)),)))
    @test flat["comparisons"]["reference_mean_vs_maximum"]["spearman"] === nothing
    @test flat["validation"]["zero_difference_fraction"] == 0.0
    @test occursin("not redistribution permission", C.markdown(report))
    @test occursin("timezone/day-boundary", C.markdown(report))
    # Argument handling is testable without loading packages: both cases exit before the
    # command includes any project module.
    cli = joinpath(@__DIR__, "..", "bin", "compare_wbgt_mean_max.jl")
    function cli_exit(args)
        process = run(pipeline(`$(Base.julia_cmd()) $cli $args`, stdout=devnull, stderr=devnull); wait=false)
        wait(process)
        return process.exitcode
    end
    @test cli_exit(["--help"]) == 0
    @test cli_exit(String[]) != 0
    mktempdir() do dir
        mean_path, max_path = joinpath(dir,"mean.nc"), joinpath(dir,"maximum.nc")
        trees = [Dict("id"=>"a", "latitude"=>50.839932, "longitude"=>4.342365),
                 Dict("id"=>"b", "latitude"=>50.839932, "longitude"=>4.342365),
                 Dict("id"=>"c", "latitude"=>50.85, "longitude"=>4.35)]
        write_paired_archive(mean_path, :mean, trees)
        write_paired_archive(max_path, :maximum, trees)
        @test_throws ErrorException W.read_wbgt_year(mean_path) # defaults to maximum
        @test_throws ErrorException W.read_wbgt_year(max_path; expected_statistic=:mean)
        @test_throws ErrorException W.read_wbgt_year(max_path; expected_statistic=:minimum)
        for title in ("", "Daily average Wet Bulb Globe Temperature for Brussels for 2016")
            h5open(max_path,"r+") do f; attrs(f)["title"] = title; end
            @test_throws ErrorException W.read_wbgt_year(max_path)
        end
        h5open(max_path,"r+") do f
            attrs(f)["title"] = "Daily maximum Wet Bulb Globe Temperature for Brussels for 2016"
            attrs(f["time"])["calendar"] = "360_day"
        end
        @test_throws ErrorException W.read_wbgt_year(max_path)
        h5open(max_path,"r+") do f; attrs(f["time"])["calendar"] = "proleptic_gregorian"; end
        tree_path = joinpath(dir,"trees.json")
        write(tree_path,C.JSON3.write(Dict("records"=>trees)))
        out = joinpath(dir,"result")
        actual = C.generate(mean_path, max_path, tree_path, out)
        @test actual["cells"] == 2
        @test actual["tree_count"] == 3
        @test actual["validation"]["minimum_max_minus_mean_c"] == 5
        @test actual["comparisons"]["reference_mean_vs_maximum"]["spearman"] === nothing
        @test actual["inputs"]["mean"]["statistic"] == "mean"
        # Provenance must identify the exact bytes: name-only provenance cannot distinguish two
        # files with the same name or detect a changed upstream file.
        @test actual["inputs"]["mean"]["sha256"] != actual["inputs"]["maximum"]["sha256"]
        @test all(haskey(actual["inputs"][key], field) for key in ("mean","maximum")
                  for field in ("path","bytes","sha256","add_offset","units","scale_factor"))
        @test actual["inputs"]["mean"]["bytes"] == filesize(mean_path)
        @test actual["validation"]["packing_matches"] && actual["validation"]["distinct_input_files"]
        @test actual["validation"]["zero_difference_fraction"] == 0.0
        # Rerunning from the same inputs reproduces both files byte for byte.
        repeat_out = joinpath(dir,"result-repeat")
        C.generate(mean_path, max_path, tree_path, repeat_out)
        @test all(read(joinpath(out,name)) == read(joinpath(repeat_out,name))
                  for name in readdir(out))
        @test_throws ErrorException C.generate(mean_path, max_path, tree_path, out)
        @test sort(readdir(out)) == ["wbgt-mean-max-comparison.json", "wbgt-mean-max-comparison.md"]
        @test C.JSON3.read(read(joinpath(out,"wbgt-mean-max-comparison.json"),String), Dict{String,Any}) == actual
        @test read(joinpath(out,"wbgt-mean-max-comparison.md"),String) == C.markdown(actual)
        @test_throws ErrorException C.generate(joinpath(dir,"missing.nc"),max_path,tree_path,joinpath(dir,"absent"))
        @test !ispath(joinpath(dir,"absent"))
        alias = joinpath(dir,"wbgt-mean-max-comparison.json")
        symlink(tree_path,alias)
        @test_throws ErrorException C.generate(mean_path,max_path,tree_path,dir)
        @test_throws ErrorException C.sample_archive(mean_path,:mean,[trees[1],trees[1]])
        # Scalar and vector missing codes must not survive as plausible temperatures.
        # The second vector code decodes to 15 C, so range/paired-order checks alone
        # cannot detect it. Both modes must fail without writing results.
        # A file whose declared packing differs from its pair must fail before any output.
        h5open(mean_path,"r+") do f; attrs(f["WBGT"])["scale_factor"] = [0.001]; end
        mismatched = joinpath(dir,"bad-packing")
        @test_throws ErrorException C.generate(mean_path,max_path,tree_path,mismatched)
        @test !ispath(mismatched)
        h5open(mean_path,"r+") do f; attrs(f["WBGT"])["scale_factor"] = [0.01]; attrs(f["WBGT"])["add_offset"] = 5.0; end
        offset_mismatch = joinpath(dir,"bad-offset")
        @test_throws ErrorException C.generate(mean_path,max_path,tree_path,offset_mismatch)
        @test !ispath(offset_mismatch)
        # HDF5.jl deletes attributes from the dataset object, not from its attribute dict.
        h5open(mean_path,"r+") do f; delete_attribute(f["WBGT"], "add_offset"); end
        h5open(mean_path,"r+") do f; attrs(f["WBGT"])["units"] = "K"; end
        units_mismatch = joinpath(dir,"bad-units")
        @test_throws ErrorException C.generate(mean_path,max_path,tree_path,units_mismatch)
        @test !ispath(units_mismatch)
        h5open(mean_path,"r+") do f; attrs(f["WBGT"])["units"] = "°C"; end

        # A real retitled copy on disk: it passes the reader as a mean file, has a different digest
        # from the maximum file, and is caught only by the all-zero paired difference.
        duplicate = joinpath(dir,"duplicate-mean.nc")
        cp(max_path, duplicate; force = true)
        h5open(duplicate,"r+") do f
            attrs(f)["title"] = "Daily average Wet Bulb Globe Temperature for Brussels for 2016"
        end
        @test C.sample_archive(duplicate, :mean, trees).sha256 != C.sample_archive(max_path, :maximum, trees).sha256
        duplicate_out = joinpath(dir,"bad-duplicate")
        @test_throws ErrorException C.generate(duplicate, max_path, tree_path, duplicate_out)
        @test !ispath(duplicate_out)

        for (i, sentinel) in enumerate((Int16(1500), Int16[1400,1500]))
            h5open(mean_path,"r+") do f
                attrs(f["WBGT"])["missing_value"] = sentinel
            end
            bad_output = joinpath(dir,"bad-$(i)")
            @test_throws ErrorException C.generate(mean_path,max_path,tree_path,bad_output)
            @test !ispath(bad_output)
        end
    end
end
