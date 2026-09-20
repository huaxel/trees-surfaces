FROM julia:1.10-bookworm@sha256:bcffd12cc4683df07fed56e226b29affda931599862a9e0e9971a1de87e80107

WORKDIR /app
ENV JULIA_DEPOT_PATH=/opt/julia-depot

# Install dependencies before copying source so rebuilds can use Docker cache.
COPY julia/Project.toml julia/Manifest.toml /app/julia/
COPY julia/src /app/julia/src
RUN mkdir -p "$JULIA_DEPOT_PATH" \
    && julia --project=/app/julia -e 'using Pkg; Pkg.instantiate()' \
    && useradd --create-home --uid 10001 --user-group app \
    && chown -R app:app "$JULIA_DEPOT_PATH"

COPY julia /app/julia
COPY prototypes/trees-surfaces/data /app/prototypes/trees-surfaces/data

ENV JULIA_UI_HOST=0.0.0.0
ENV JULIA_UI_PORT=8080
ENV JULIA_INSTANTIATE=0
USER app
EXPOSE 8080

CMD ["julia", "--project=/app/julia", "/app/julia/run.jl"]
