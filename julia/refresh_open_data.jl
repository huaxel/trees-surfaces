#!/usr/bin/env julia

using Pkg
Pkg.activate(@__DIR__)
using JSON3
Pkg.instantiate()

include(joinpath(@__DIR__, "src", "Refresh.jl"))
using .Refresh
include(joinpath(@__DIR__, "src", "TreesSurfaces.jl"))
using .TreesSurfaces
include(joinpath(@__DIR__, "src", "Spatial.jl"))
using .Spatial
include(joinpath(@__DIR__, "src", "Flow.jl"))
using .Flow
include(joinpath(@__DIR__, "src", "Analysis.jl"))
using .Analysis

if "--help" in ARGS || "-h" in ARGS
    println("Usage: julia --project=julia julia/refresh_open_data.jl [--check] [--with-derived] [--with-analysis]")
    println("  --check          validate live APIs in a temporary directory")
    println("  --with-derived   regenerate nearest-counter and measured-flow artifacts")
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
        if "--with-derived" in ARGS
            Spatial.generate_tree_mobility_join(directory; data_dir=directory)
            Flow.generate_counter_flow_artifact(directory; data_dir=directory)
            if "--with-analysis" in ARGS
                Analysis.generate_signal_artifacts(directory; data_dir=directory)
            end
            println("Julia derived refresh check passed in the temporary directory.")
        end
        all(read(joinpath(Refresh.DATA_DIR, filename)) == content for (filename, content) in originals) || error("--check modified a committed snapshot")
        println("Julia public API check passed; committed snapshots were not modified.")
    end
else
    Refresh.refresh_open_data()
end

if "--with-derived" in ARGS && !("--check" in ARGS)
    mktempdir() do directory
        Spatial.generate_tree_mobility_join(directory)
        Flow.generate_counter_flow_artifact(directory)
        generated = ["brussels-tree-bike-nearest.json", "brussels-tree-counter-flow.json"]
        if "--with-analysis" in ARGS
            Analysis.generate_signal_artifacts(directory)
            append!(generated, ["tree-signal-sensitivity.json", "tree-signal-balanced-screen.csv", "tree-signal-analysis.md"])
            println("Julia regenerated sensitivity artifacts; existing stakeholder review remains untouched.")
        end
        for filename in generated
            cp(joinpath(directory, filename), joinpath(TreesSurfaces.DATA_DIR, filename); force=true)
        end
    end
    println("Julia regenerated derived artifacts atomically.")
elseif !("--check" in ARGS)
    println("Derived joins unchanged; use --with-derived or the Python refresh fallback.")
end
