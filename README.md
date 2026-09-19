# Final Work planning and feasibility prototypes

This repository contains planning material and two small, evidence-led feasibility prototypes for a Bachelorproef (BAP) topic decision. It also preserves examples from previous students and separate Future Proof Project (FPP) notes.

The BAP subject is **not formally selected or approved yet**. The two current candidates are:

- **Trees & Surfaces** — explores where sampled managed trees combine higher WBGT raster values with closer bicycle counters. Its ranking is descriptive and is not a planting recommendation or causal mobility result.
- **Three Ages of a Brussels Building** — compares register/source dates, facade evidence and structural imagery while keeping provenance, disagreement and pending human review visible.

The selected FPP direction, *De Vier Prijzen van Brussel*, is a separate project. See [`docs/brainstorming-status.md`](docs/brainstorming-status.md) for that distinction and the remaining decisions.

## Repository map

- [`docs/`](docs/) — decision briefs, project status, review findings, source notes and demo scripts
- [`prototypes/`](prototypes/) — dependency-free browser prototypes, public-data snapshots and regeneration scripts
- [`examples/`](examples/) — previous students' submissions, included only as reference material
- [`.github/workflows/validate-prototypes.yml`](.github/workflows/validate-prototypes.yml) — continuous validation and generated-artifact drift check

Start with [`docs/README.md`](docs/README.md) for the documentation index and [`prototypes/README.md`](prototypes/README.md) for data provenance, limitations and regeneration details.

## Run the prototypes

Requirements: Python 3.10+, Node.js and Pillow.

```bash
python3 -m pip install -r prototypes/requirements.txt
cd prototypes
python3 -m http.server 8000
```

Open <http://localhost:8000/>. The browser prototypes use no third-party runtime libraries.

## Validate

From the repository root:

```bash
scripts/validate-prototypes.sh
```

The gate regenerates derived artifacts, preserves provenance-compatible human reviews, validates snapshot invariants, compiles Python, exercises both browser interfaces, strictly parses JSON and checks diff formatting. CI uses `--check-clean` to reject stale or missing generated artifacts.

## Evidence status

Both prototypes demonstrate source access and a narrow product shape; neither presents a finished research result. The principal open steps are stakeholder acceptance of the Trees decision question and controlled human review of the Three Ages identity, register, facade and structural evidence. The current assessment is maintained in [`docs/prototype-review.md`](docs/prototype-review.md).

## Licensing

Asset-specific source, credit and reuse terms are recorded in the prototype inventories and supporting documentation. No repository-wide software or documentation licence has been declared; do not assume that one asset's terms apply to the rest of the repository.
