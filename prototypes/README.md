# Mini prototypes

These are two deliberately small, dependency-free feasibility spikes for the two BAP candidates.

The analytical values in the interface remain **illustrative**, not research results. Each spike also includes a small reproducible snapshot from a real public source to test data availability and schema shape.

## Run locally

From this directory:

```bash
python3 -m http.server 8000
```

Then open:

- http://localhost:8000/
- http://localhost:8000/trees-surfaces/
- http://localhost:8000/three-ages/

To refresh the public-data snapshots:

```bash
python3 fetch_open_data.py
```

## Prototype A — Trees & Surfaces

A small intervention explorer. Adjust the relative importance of heat reduction, greenery and street-use preservation. The prototype ranks sample tree sites and displays a simple map-like grid.

The spike includes 100 records from Brussels' managed-tree register and 100 records from its remarkable-tree register. Next step: join one real heat layer and one documented mobility proxy; the prototype deliberately does not invent those joins yet.

## Prototype B — Three Ages

A building-history explorer. Select a sample building and compare its registered year, facade-style period and structural period, together with confidence and evidence notes.

The spike includes the 34-building City of Brussels Grand Place dataset, including restoration/history and facade-description fields. Next step: create a permitted, manually curated pilot set with historical imagery and three-age annotations.
