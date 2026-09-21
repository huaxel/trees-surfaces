#!/usr/bin/env julia

using Pkg
Pkg.activate(joinpath(@__DIR__, ".."))
using JSON3
Pkg.instantiate()

include(joinpath(@__DIR__, "..", "src", "Refresh.jl"))
using .Refresh
include(joinpath(@__DIR__, "..", "src", "TreesSurfaces.jl"))
using .TreesSurfaces
include(joinpath(@__DIR__, "..", "src", "Spatial.jl"))
using .Spatial
include(joinpath(@__DIR__, "..", "src", "Flow.jl"))
using .Flow
include(joinpath(@__DIR__, "..", "src", "Analysis.jl"))
using .Analysis
include(joinpath(@__DIR__, "..", "src", "Validation.jl"))
using .Validation

if "--help" in ARGS || "-h" in ARGS
    println("Usage: julia --project=. bin/refresh_open_data.jl [--check] [--with-derived] [--with-analysis]")
    println("  --check          validate live APIs and derived snapshots in a temporary directory")
    println("  --with-derived   regenerate derived artifacts (also enables analysis with --with-analysis)")
    println("  --with-analysis  regenerate sensitivity artifacts (requires --with-derived)")
    exit()
end
allowed = Set(["--check", "--with-derived", "--with-analysis"])
unknown = [arg for arg in ARGS if !(arg in allowed)]
isempty(unknown) || error("unknown option(s): $(join(unknown, ", "))")
("--with-analysis" in ARGS && !("--with-derived" in ARGS)) && error("--with-analysis requires --with-derived")

if "--check" in ARGS
    mktempdir() do directory
        filenames = filter(filename -> isfile(joinpath(Refresh.DATA_DIR, filename)), readdir(Refresh.DATA_DIR))
        originals = Dict(filename => read(joinpath(Refresh.DATA_DIR, filename)) for filename in filenames)
        for filename in filenames
            cp(joinpath(Refresh.DATA_DIR, filename), joinpath(directory, filename))
        end
        Refresh.refresh_open_data(output_dir=directory)
        Spatial.generate_tree_mobility_join(directory; data_dir=directory)
        Flow.generate_counter_flow_artifact(directory; data_dir=directory)
        if "--with-analysis" in ARGS
            Analysis.generate_signal_artifacts(directory; data_dir=directory)
        end
        Validation.validate_snapshots(directory)
        println("Julia refreshed public-data snapshots and derived artifacts validated in the temporary directory.")
        all(read(joinpath(Refresh.DATA_DIR, filename)) == content for (filename, content) in originals) || error("--check modified a committed snapshot")
        println("Julia public API check passed; committed snapshots were not modified.")
    end
else
    mktempdir() do directory
        for filename in readdir(Refresh.DATA_DIR)
            source = joinpath(Refresh.DATA_DIR, filename)
            isfile(source) && cp(source, joinpath(directory, filename))
        end
        Refresh.refresh_open_data(output_dir=directory)
        generated = String[Refresh.REFRESH_FILENAMES...]
        if "--with-derived" in ARGS
            Spatial.generate_tree_mobility_join(directory; data_dir=directory)
            Flow.generate_counter_flow_artifact(directory; data_dir=directory)
            append!(generated, ["brussels-tree-bike-nearest.json", "brussels-tree-counter-flow.json"])
            if "--with-analysis" in ARGS
                Analysis.generate_signal_artifacts(directory; data_dir=directory)
                append!(generated, ["tree-signal-sensitivity.json", "tree-signal-balanced-screen.csv", "tree-signal-analysis.md"])
                println("Julia regenerated sensitivity artifacts; existing stakeholder review remains untouched.")
            end
        end
        Refresh.promote_files(directory, TreesSurfaces.DATA_DIR, generated)
    end
    if "--with-derived" in ARGS
        println("Julia promoted refreshed source and derived artifacts after successful generation.")
    else
        println("Derived joins unchanged; use --with-derived to regenerate them.")
    end
end
