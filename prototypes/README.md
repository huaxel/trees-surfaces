# Mini prototypes

These are two deliberately small, dependency-free feasibility spikes for the two BAP candidates.

Trees & Surfaces now uses an **exploratory** signal from real joins, not a validated research result. Three Ages uses source-linked records, while its register and image-derived annotations remain explicitly pending. Each spike includes a small reproducible snapshot from a real public source to test data availability and schema shape. See [`docs/prototype-next-iteration.md`](../docs/prototype-next-iteration.md) for the next definition of done.

## Run locally

From this directory:

```bash
python3 -m http.server 8000
```

Then open:

- http://localhost:8000/
- http://localhost:8000/trees-surfaces/
- http://localhost:8000/three-ages/

To validate the committed snapshots:

```bash
python3 validate_snapshots.py
```

To regenerate the tree signal sensitivity report, descriptive analysis and balanced CSV export:

```bash
python3 trees-surfaces/analyze_signal.py
```

To regenerate the Three Ages annotation worksheet:

```bash
python3 three-ages/export_pilot.py
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

The spike includes 100 records from Brussels' managed-tree register, 100 records from its remarkable-tree register, the current 18 bicycle-counter locations and 672 fifteen-minute observations from counter CB2105 over 1–7 January 2024. It also includes a downsampled preview of the real Brussels WBGT heat raster and a descriptive report with district context plus sensitivity comparisons of heat-only, balanced and proximity-only rankings, including the complete balanced screen for export. Each sampled tree is linked to its nearest bicycle counter and to a WBGT raster pixel. These are feasibility joins, not causal findings: proximity is not street use, and one hot-day WBGT raster is not a long-term temperature series.

## Prototype B — Three Ages

A building-history evidence explorer. Select a real Grand Place source record and compare the registered-year, facade-style and structural evidence fields without presenting pending annotations as facts.

The spike includes the 34-building City of Brussels Grand Place dataset and a six-record source-linked pilot. The pilot distinguishes source-described style, documented reconstruction dates and fields still awaiting a register lookup or permitted historical imagery.
