# Mini prototypes

These are two deliberately small feasibility spikes for the two BAP candidates. The browser prototypes use no third-party runtime libraries; offline image-processing scripts require Pillow.

Trees & Surfaces now uses an **exploratory** signal from real joins, not a validated research result. Three Ages uses source-linked records, with six explicit register-date proxies (three Wikidata/heritage-linked and three official architectural-inventory reconstruction dates), three aligned ortho previews (1930–1935, 1996 and 2022), five licensed 1941–1942 KIK-IRPA facade previews and an exact-case La Balance pair: an 1878 British Library engraving and a 2011 Wikimedia Commons photograph. Image-derived annotations remain pending. Each spike includes reproducible snapshots from real public sources to test data availability and schema shape. See [`docs/prototype-next-iteration.md`](../docs/prototype-next-iteration.md) for the next definition of done.

## Setup and validation

The regeneration scripts require Python 3.10+, Pillow and Node.js for the dependency-free UI smoke harness. From the repository root:

```bash
python3 -m pip install -r prototypes/requirements.txt
scripts/validate-prototypes.sh
```

The validation script regenerates all derived local artifacts, verifies completed-review preservation, provenance-change refusal and explicit reset behavior in isolated copies, validates snapshots, compiles Python, exercises both browser UIs, strictly parses every JSON file and runs `git diff --check`. GitHub Actions runs the same command with `--check-clean` on Python 3.10 and 3.13, which also fails when committed generated artifacts are stale, missing or version-dependent.

## Run locally

From this directory:

```bash
python3 -m http.server 8000
```

Then open:

- http://localhost:8000/
- http://localhost:8000/trees-surfaces/
- http://localhost:8000/three-ages/

To validate only the committed snapshot invariants from this directory:

```bash
python3 validate_snapshots.py
```

Use `../scripts/validate-prototypes.sh` for the complete repository gate.

To regenerate the tree signal sensitivity report, descriptive analysis, balanced CSV export and stakeholder-review worksheet:

```bash
python3 trees-surfaces/analyze_signal.py
python3 trees-surfaces/export_stakeholder_review.py
```

The stakeholder exporter preserves a completed review only while the exact proposal, core-join audit and sensitivity evidence remain unchanged. Every completed row requires reviewer metadata, false-positive preference, evidence threshold and notes plus an allowed status (`accepted`, `accepted with changes`, `needs more evidence`, or `rejected`). Accepted statuses additionally require the agreed question, unit, mobility measure and heat period; negative statuses do not require fabricated accepted values. Use `--reset-review` only to deliberately clear that decision.

To regenerate the aligned building-centred structural crops, then the Three Ages building, facade-image, structural-comparison and register-semantics worksheets:

```bash
python3 three-ages/generate_structural_crops.py  # requires Pillow
python3 three-ages/export_pilot.py
```

The crop generator projects each building coordinate into the shared WMS bounds, applies the same 160 px box to all three epochs and records stable pixel hashes; the crops are review aids, not structural observations. The export preserves completed human review fields only while their source provenance still matches. A facade-image row needs a facade or structural observation; a structural-comparison row needs a structural observation. A register row requires one controlled decision: `accept proxy for MVP`, `retain as reconstruction evidence`, or `reject source mapping`. Every completed row also requires reviewer, ISO-8601 review date and `low`, `medium` or `high` confidence. Completed rows compile to the corresponding `three-ages-*-reviews.json` artifact and appear beside the evidence in the explorer. The command refuses to carry reviews onto changed or removed assets, comparison epochs, bounds, crop pixels, identity notes, source semantics or source comparisons. Use `--reset-reviews` only to deliberately clear all three review worksheets.

To refresh the verified 1930–1935 and 1996 BruCiel previews, 2022 urbisgrid preview, KIK-IRPA historical previews and exact-case Wikimedia Commons preview:

```bash
python3 three-ages/download_bruciel_1935_preview.py
python3 three-ages/download_bruciel_preview.py
python3 three-ages/download_urbisgrid_preview.py
python3 three-ages/download_kik_previews.py
python3 three-ages/download_commons_previews.py
```

All ten committed source previews are SHA-256 pinned in `three-ages-pilot.json`; the downloaders verify those bytes before overwriting evidence, and the worksheets carry the hashes as review provenance. A checksum change therefore requires source inspection and a deliberate provenance update rather than silent acceptance.

To refresh the exact 1878 La Balance engraving from the British Library Flickr Commons record:

```bash
python3 three-ages/download_british_library_preview.py
```

The downloader verifies the source's rights label, scan page, book identifier and publication year before accepting the checksum-pinned original JPEG.

To regenerate the measured counter-flow context:

```bash
python3 trees-surfaces/join_counter_flow.py
```

To refresh the public-data snapshots:

```bash
python3 fetch_open_data.py
```

To regenerate the heat join, download the source GeoTIFF from `data/source-inventory.json` and run:

```bash
python3 trees-surfaces/join_heat.py /path/to/WBGT_MEAN_24082016_0-1_byte.tif trees-surfaces/data/brussels-trees-sample.json trees-surfaces/data/brussels-tree-heat-sample.json
```

## Prototype A — Trees & Surfaces

An exploratory tree-point view. Adjust the relative importance of a sampled WBGT pixel and nearest bicycle-counter proximity. The prototype ranks the top 20 observed points and positions them in a relative geographic preview; it does not recommend planting locations.

The spike includes 100 records from Brussels' managed-tree register, 100 records from its remarkable-tree register, the current 18 bicycle-counter locations and five seven-day counter-history snapshots (672 fifteen-minute observations each) covering measured-flow context for 97/100 trees. The authoritative catalogues license both tree registers under CC BY 4.0 and the Brussels Mobility counter source under CC0 1.0; their required publisher and catalogue attributions are recorded in `trees-surfaces/data/source-inventory.json` and displayed in the interface. It also includes a downsampled preview of the real Brussels WBGT heat raster and a descriptive report with heat-date justification, traceability, district context, sensitivity comparisons and the complete balanced screen for export. The authoritative Brussels Environment metadata identifies that raster as normalized 0–100 WBGT indicator values for 24 August 2016 and licenses it under CC BY 4.0 with source attribution. Each sampled tree is linked to its nearest bicycle counter, measured counter-flow context where available, and a WBGT raster pixel. These are feasibility joins, not causal findings: counter flow is measured at the counter, not the tree; proximity is not street use; and one hot-day WBGT raster is not a long-term temperature series.

## Prototype B — Three Ages

A building-history evidence explorer. Select a real Grand Place source record and compare the registered-year, facade-style and structural evidence fields without presenting pending annotations as facts.

The spike includes the 34-building City of Brussels Grand Place dataset and a six-record source-linked pilot. The dataset catalogue states CC BY 4.0 and requires the City publisher plus `Behind Brussels` and `Google Maps` attributions. The architectural-inventory terms permit text quotations and reused information with explicit source attribution; they do not grant a general image licence. The three Wikidata structured inception claims are CC0 1.0 and acknowledged to Wikidata contributors, but remain crowd-sourced proxies rather than official register dates. The pilot distinguishes source-described style, documented reconstruction proxies, six explicitly labelled register-date proxies, three reusable aligned ortho previews and seven reusable case-level facade previews. Five facade photographs date to 1941–1942; La Balance has a 1878 British Library engraving and a 2011 Commons photograph. Historical facade and structural source access is now demonstrated; case-level observations and reviewed labels remain open. The La Balance crosswalk remains visible for review: the City dataset uses `Grand-Place 24`; heritage inventory Urban 30991 uses `Rue de la Colline 24`; the British Library caption says `rue de la Colline`; and Commons says `Grand-Place` with monument id `2043-0177/0`.
