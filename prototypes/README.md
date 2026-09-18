# Mini prototypes

These are two deliberately small, dependency-free feasibility spikes for the two BAP candidates.

They use **illustrative sample data**, not research results. The purpose is to test the product shape and make the differences between the subjects tangible.

## Run locally

From this directory:

```bash
python3 -m http.server 8000
```

Then open:

- http://localhost:8000/trees-surfaces/
- http://localhost:8000/three-ages/

## Prototype A — Trees & Surfaces

A small intervention explorer. Adjust the relative importance of heat reduction, greenery and street-use preservation. The prototype ranks sample tree sites and displays a simple map-like grid.

Next feasibility step: replace the sample records with one city's tree-register data, a real heat layer and a documented mobility proxy.

## Prototype B — Three Ages

A building-history explorer. Select a sample building and compare its registered year, facade-style period and structural period, together with confidence and evidence notes.

Next feasibility step: create a permitted, manually curated pilot set from the Buildings of Brussels archive and historical imagery.
