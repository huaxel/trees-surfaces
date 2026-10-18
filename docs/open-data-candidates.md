# Open data candidates for the canopy check (searched 2026-10-17)

**Purpose.** Record what a deliberate search for *other* open data found, separate what is
genuinely new from what the project already uses, and state for each candidate what it can and
cannot support. Nothing here is fetched, cleared, integrated or committed as data; the numbers
below are observations of live services and catalogue records on the search date.

**Method.** Catalogue abstracts were not treated as evidence. Licences, dates and resolutions
come from the catalogue records' own XML (`catalog.datastore.brussels/geonetwork/srv/api/records/
<id>/formatters/xml`) and, for Copernicus Street Tree Layer, from queries against the published
service covering this project's own five route segments.

## Already in use, not new

The search surfaced four sources the project already depends on, so they are not candidates:
the 2021 UrbIS orthophotos, VITO UrbClim WBGT, ERA5 via Open-Meteo, and the City of Brussels
managed-tree and remarkable-tree registries. It also surfaced the VUB/Zenodo
**canopy height model from Gallez et al.** (DOI 10.5281/zenodo.13869065) — which this project
**already fetches, hashes and analyses** (`data/research/canopy-inputs/manifest.json`,
cached as `CHM_BCR_EG_2022_complete.shp`). It is listed below only for the independence
question, not as a discovery.

## New candidates

| Candidate | Provider | Coverage and resolution | Terms | Access | What it could support |
| --- | --- | --- | --- | --- | --- |
| **Airborne LiDAR point cloud, 2021** | Paradigm / UrbIS | Brussels region, LAS point cloud; flight date **2021-10-09** | CC BY 4.0 (as recorded on the data.gov.be entry) | Open, direct download | Echo and surface **structure** for telling a crown from a roof at the same height — a different property from height, so not circular for the class mapped here. Heights from it are circular, see below |
| **DTM / DSM, 2021** | Paradigm / UrbIS | Region-wide, 50 cm grid (record states `Distance: 0.5`) | Same open UrbIS download | Open, direct download | **Not usable as a check of this project's canopy class**: the class boundary is a height threshold computed from this very product |
| **LiDAR tree models, Brussels 2021** | IOER FDZ (Münzinger et al.), DOI 10.71830/AIEEPB | CHM 0.5 m, parameterised tree positions, crown convex hulls, CityGML LoD2 crowns | CC BY 4.0 | **File access restricted — request access**; metadata and README public | Per-tree crowns and heights, the closest thing to a tree inventory of the region, from the same October 2021 LiDAR |
| **Urban Atlas Street Tree Layer 2018** | Copernicus Land Monitoring Service / EEA | Brussels FUA `be001l2`, vector, MMU 500 m², MMW 10 m | CLMS terms, free of charge with citation | Open (service queried directly; prepackaged per-FUA download) | A 2018 satellite-interpreted street-tree extent, independent of our imagery — **measured below as unusable on four of the five streets** |
| **HRL Tree Cover Density, 2018–2023** | Copernicus Land Monitoring Service | Europe, 10 m raster, yearly | CLMS terms, free of charge | Open via WeKeo / Copernicus Data Space | A year-matched (2021) crown-cover fraction, but at 10 m it cannot resolve 2 m canopy pixels |
| **UrbIS Land cover** | Paradigm / UrbIS | Brussels region; four classes including **street surfaces** and blocks with parks and water | Open UrbIS download | Open | A survey-based street-surface mask for the area-versus-line denominator question, independent of our OSM-derived buffer |
| **Brussels street-level imagery** | Mapillary, plus Panoramax; one contributor's bicycle capture | Entire region and Forêt de Soignes, ~4,500–5,000 km and ~600,000 images, complete by September 2023 | CC BY-SA | Open, per-image | Field-adjacent inspection of individual street trees and shade — with share-alike terms that differ from every other input here |
| **DSM 1 m, national** | National Geographic Institute | Belgium, 1 m, Brussels source is the 2021 regional data | **Internal use only; commercial use strictly forbidden** | No public reuse | Nothing for this project. Listed so the restriction is on record rather than rediscovered later. |

## The independence question, which decides their value

The point of a structural reference is to be independent of the thing being checked. On that
test the candidates split cleanly, and the split is not the one the descriptions suggest:

- **For the class this project maps, a height check is circular.** The mapped tree class is
  `gridcode == 4` (`research/canopy/pipeline.py`, `alignment_audit.py`, `validation_frame.py`),
  which the source record defines as normalised height **5–113.96 m** — and that record states
  the model was built from the UrbIS north–south 2021 orthophotos *and from the 50 cm DSM/DTM
  captured 2021-09-22*, which is the same product offered on the open portal. A nDSM check
  against that surface model would recover the threshold that defined the class. It verifies
  arithmetic, not canopy. Height can check a class derived from **imagery alone**; it cannot
  check one whose boundary *is* a height.
- **What the point cloud can still add is structure, not height.** Whether a polygon is a crown
  or a roof at the same elevation is a question of echo and surface roughness, a property the
  DSM/DTM interpolation discards and the CHM never used. That use needs the point cloud, not
  the raster, and it is a weaker check than field labels because it shares the flight.
- **LiDAR is a different instrument, but not a different occasion.** Both 2021 orthophoto
  products carry the acquisition period 2021-09-17 to 2021-10-09
  (`docs/imagery-registration-check.md`) and the LiDAR flight is dated 2021-10-09, inside that
  window. So agreement between a LiDAR height mask and our classification is **not** correlated
  through the imagery — different sensor, different failure modes — but it *is* correlated
  through date and weather, hence through leaf-on state and canopy condition. It is an
  independent-*modality* check, not a temporally independent one, and it cannot validate
  anything about years other than 2021.
- **The Gallez CHM is not an independent reference at all.** Its own record states it was built
  from the UrbIS **north–south 2021** orthophotos (RGB and NIR) and from DSM/DTM captured
  2021-09-22, using NDVI ≥ 0.2 with height bands (< 0.5 m grass, 0.5–2 m low shrub, 2–5 m high
  shrub, > 5 m trees). Agreement with it measures whether two analysts, with different methods
  and thresholds, read the *same imagery* to the same answer. That is a useful
  inter-analyst reproducibility check — the same class of evidence as the east–west versus
  north–south comparison — and it must not be reported as validation.
- **Consequence for the sampling plan.** The "structural dataset" it called the hardest gap is
  partially closable with an open, same-window LiDAR product, and no candidate removes the need
  for field labels. Nothing found here is independent of the 2021 acquisition window.

## Measured: Copernicus Street Tree Layer does not reach these streets

The layer's own definition (contiguous tree patches of 500 m² or more, minimum width 10 m)
predicts it holds parks and blocks rather than street trees. Queried over the bounding box of
the five published segments (plus 200 m), through
`image.discomap.eea.europa.eu/arcgis/rest/services/UrbanAtlas/UA_StreetTreeLayer_2018/MapServer/0/query`,
with the envelope transformed from EPSG:31370 to the service's EPSG:3857 using GDAL via `fiona`
(no pyproj is available in the canopy environment):

| Segment | Nearest STL polygon | Centreline inside STL | Share of the 10 m half-width buffer covered |
| --- | --- | --- | --- |
| 266 | 0.0 m | 29.6 m | 9.5% |
| 5630 | 5.2 m | 0.0 m | 1.4% |
| 5634 | 44.6 m | 0.0 m | 0.0% |
| 5642 | 22.9 m | 0.0 m | 0.0% |
| 5643 | 101.6 m | 0.0 m | 0.0% |

46 polygons intersect the route bounding box, with a union area of 157,647 m² — enough to
matter as a region-scale extent, and concentrated away from four of the five streets. On this
evidence STL 2018 cannot serve as a street-tree reference for the sample.

**Limits of that measurement.** One query, one bounding box, one edition, one date. It is not a
statement about STL's quality elsewhere, not a licence opinion, and not a substitute for
checking the 2012 edition or a per-segment extraction. It is enough to stop treating STL as the
obvious candidate.

## What this changes

1. The sampling plan's structural-reference gap is **narrower than it looked, and still open**.
   The open UrbIS LiDAR can check surface structure, and can check a height *class* derived from
   imagery alone — but not this project's tree class, whose definition is a height threshold
   taken from the same DSM/DTM. No candidate found removes the need for field labels.
2. One door is closed with a measurement rather than an assumption: **STL 2018 does not cover
   these streets**.
3. A licensing trap is on record: the national 1 m DSM is **not openly reusable**.
4. Nothing is integrated, and no fetch script is committed — the canopy pipeline's rule is that
   it never fetches upstream research datasets. Using the LiDAR requires a human decision to
   spend a multi-GB download and to choose a height threshold, which is a method choice, not a
   data-sourcing question.
