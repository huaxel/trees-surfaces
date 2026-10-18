#!/usr/bin/env julia

# Run with julia --project=. bin/analyze_heat_support.jl [output-directory]
# No package installation, network access, or operational snapshot mutation.
include(joinpath(@__DIR__, "..", "src", "HeatDiagnostics.jl"))
using .HeatDiagnostics

length(ARGS) <= 1 || error("usage: julia --project=. bin/analyze_heat_support.jl [output-directory]")
root = normpath(joinpath(@__DIR__, ".."))
output = isempty(ARGS) ? joinpath(root, "research-generated") : abspath(first(ARGS))
report = generate(joinpath(root, "data"), output)
println("Wrote heat-support diagnostics for $(report["trees"]) trees / $(report["cells"]) cells to $(output)")
