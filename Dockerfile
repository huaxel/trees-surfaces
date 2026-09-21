FROM julia:1.10-bookworm@sha256:bcffd12cc4683df07fed56e226b29affda931599862a9e0e9971a1de87e80107

WORKDIR /app
ENV JULIA_DEPOT_PATH=/opt/julia-depot

# Install dependencies before copying source so rebuilds can use Docker cache.
COPY Project.toml Manifest.toml /app/
COPY src /app/src
RUN mkdir -p "$JULIA_DEPOT_PATH" \
    && julia --project=/app -e 'using Pkg; Pkg.instantiate()' \
    && useradd --create-home --uid 10001 --user-group app \
    && chown -R app:app "$JULIA_DEPOT_PATH"

COPY public /app/public
COPY data /app/data
COPY bin /app/bin

ENV JULIA_UI_HOST=0.0.0.0
ENV JULIA_UI_PORT=8080
ENV JULIA_INSTANTIATE=0
USER app
EXPOSE 8080

CMD ["julia", "--project=/app", "/app/bin/run.jl"]
