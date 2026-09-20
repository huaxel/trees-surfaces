FROM julia:1.10-bookworm@sha256:bcffd12cc4683df07fed56e226b29affda931599862a9e0e9971a1de87e80107

WORKDIR /app

# Install dependencies before copying source so rebuilds can use Docker cache.
COPY julia/Project.toml julia/Manifest.toml /app/julia/
COPY julia/src /app/julia/src
RUN julia --project=/app/julia -e 'using Pkg; Pkg.instantiate()'

COPY julia /app/julia
COPY prototypes/trees-surfaces/data /app/prototypes/trees-surfaces/data

ENV JULIA_UI_HOST=0.0.0.0
ENV JULIA_UI_PORT=8080
EXPOSE 8080

CMD ["julia", "--project=/app/julia", "/app/julia/run.jl"]
