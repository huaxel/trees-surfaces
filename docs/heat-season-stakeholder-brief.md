# Stakeholder brief: what should seasonal heat evidence change?

## Decision needed

Should the 2015–2024 ERA5 seasonal heat measure remain **temporal context** beside the current spatial WBGT screen, should the screen move to the **100 m multi-date WBGT archive**, or should the project hold any ranking change until a stakeholder approves a heat period?

The existing ranking uses the Brussels Environment WBGT indicator raster for 24 August 2016. Two multi-date context artifacts now exist and neither changes the ranking.

## Higher-resolution source: multi-date evidence exists (exploratory comparison)

An earlier version of this brief treated the single-day raster as unavoidable because the regional WMS publishes one scenario. That was incomplete. VITO publishes a multi-date daily **100 m** WBGT archive for **2008–2017**, as `WBGT_year_daily_max_YYYY.nc` under `https://provide.marvin.vito.be/ftp/compressed_daily/Brussels/`. The archive reports daily-maximum WBGT in °C.

**Spatial-support correction:** the [official detailed-layer methodology](https://environnement.brussels/citoyen/documentation-et-outils/etat-des-lieux-de-lenvironnement/ilot-de-chaleur) describes the Brussels Environment WBGT scenario at **2 m × 2 m**, using UrbClim meteorological inputs and radiation simulated from vegetation and building heights. Its reported temporal quantity is the mean over all hours of 24 August 2016; the committed layer is a 0–100 indicator. The earlier claim here of matching 100 m grids was wrong. Common model lineage does not make the two products spatially or physically interchangeable.

`brussels-heat-wbgt-sample.json` samples the daily archive at the 100 committed tree points. Within that archive, holding product, spatial support and aggregation semantics fixed permits a descriptive reference-day versus seasonal-period comparison. Comparing the archive with the detailed indicator additionally changes spatial support, radiation treatment, units and daily statistic; it cannot isolate the effect of heat period. See [heat-support diagnostics](../data/research/heat-support-diagnostics.md).

Pooling ten June–August seasons and ranking the same trees by seasonal-mean WBGT produces a top ten that shares **7/10** members with the heat-only top ten from 24 August 2016, using the same VITO daily-maximum series. The other two same-series aggregations agree by exactly the same margin: the seasonal 90th percentile shares **7/10**, and the count of June–August days at or above 26 °C shares **7/10**. Spearman agreement with the reference day is 0.922 for the seasonal mean, 0.862 for hot-day count and 0.841 for the 90th percentile.

That is the decision-relevant reading of this section: within the same source, grid and spatial support, **the choice of period does not reorder the sample much** — three different period definitions give the same 7 of 10. What does reorder it is the cross-screen comparison, where resolution, radiation treatment, units and scoring all change together (0–3 of 10). So the sensitivity that matters here is the product, not the period, and a period can be chosen on grounds of meaning — which question the screen should answer — rather than on the expectation that it changes which trees rank highest. Against the current balanced top ten, the VITO reference-day-only ranking overlaps **3/10**, while the ten-year seasonal-mean and hot-day-count rankings each overlap **0/10**. Those cross-screen comparisons also differ in WBGT output semantics and scoring, so they cannot attribute the changes to heat period alone. The two same-series heat-only rankings are substantially, but not completely, different.

Two further measurements matter for interpretation:

- The 100 m archive assigns the 100 trees to **39 distinct cells**, compared with four ERA5 cells. Reference-day WBGT spans **26.13–27.52 °C** (1.39 °C across the sample); the ten-summer seasonal mean spans **19.10–20.51 °C** (1.41 °C). It resolves more intra-urban variation than ERA5, but the values still form a narrow band.
- The reference day ranks between the **96.7th and 97.6th percentiles of pooled June–August daily WBGT values** across the 2008–2017 window. An earlier 2016-only check placed it near the 94th percentile of that summer; those are different comparison populations, so do not conflate them. The reference day is genuinely extreme, which is evidence for using it — but its hot-day score is not the same decision as a ten-year seasonal mean.

This is why the brief does not simply recommend switching. "Seasonal mean" and "worst day" are different decisions, and the project cannot choose between them without a stakeholder saying what the screen is for.

**Day-boundary caveat.** The ERA5 seasonal series is requested as UTC-day aggregates, and that convention is recorded and tested. The VITO daily archive states no such convention, so a daily maximum from each context need not aggregate the same hours; the comparison treats that as unresolved rather than assumed common.

**Licence caveat.** The [VITO archive page](https://provide.marvin.vito.be/ftp/compressed_daily/) asks users to cite De Ridder et al. (2015) and Souverijns et al. (2026), but states no licence or redistribution terms. The related Souverijns et al. CC BY 4.0 dataset is the decadal 2010–2100 indicator set, not this daily archive. The committed artifact records terms as unresolved. A 2026-10-17 primary-source check found no licence attribute in the annual NetCDF files either, and the Copernicus Climate Data Store sibling record `sis-urban-climate-cities` (CC-BY-4.0, deprecated on the CDS on 2024-05-10) covers hourly temperature, humidity and wind for 100 cities and contains no WBGT, so it does not license this daily WBGT archive (see [`heat-season-method.md`](heat-season-method.md), *Licence and lineage*). Confirm reuse terms with VITO (`urbclim@vito.be`) before external redistribution or relying on derived values beyond exploratory analysis; do not redistribute the NetCDF files.

## Coarse ERA5 context (independent check)

- The ERA5 archive provides a consistent daily series for June–August (JJA), 2015–2024. For this sample, 100 trees map to four ERA5 grid cells.
- The 24 August 2016 reference day falls among the 88th–90th warmest JJA days in its own summer across those cells (94.6–96.7% of that summer's days were below it).
- The 2016 summer's mean daily apparent-temperature maximum was about 21.75 °C across the sample cells; 2018 was the warmest season in the ten-year window at about 23.93 °C.
- The artifact counts about 7.3–8.5 JJA days per year with apparent-temperature maximum at or above 30 °C. This is a descriptive threshold, **not** a health-warning threshold.

## Higher-resolution source feasibility (superseded)

An earlier version of this section audited Landsat land-surface temperature as the only candidate high-resolution source, and reported that no scene intersects the reference date. That audit remains accurate as far as it goes, but it is no longer the decisive comparison, because a 100 m **WBGT** archive from the same model as the committed raster is available and measures heat stress rather than surface temperature. Read the section above first; the Landsat numbers below are retained as a record of a rejected alternative.

A point-coverage audit sampled the 100 tree coordinates against Planetary Computer `landsat-c2-l2` scenes for JJA 2015–2024. It selected the surface-temperature asset by its STAC `temperature` role, covering sensor-specific keys such as Landsat 7 `lwir` and Landsat 8/9 `lwir11`, and read `qa_pixel`, `qa` (ST_QA), and `cdist` using temporary anonymous SAS tokens. All 361 intersecting scene items were readable. Scene overlaps were deduplicated by tree and acquisition date; eligible pairs are tree-dates covered by at least one scene with a surface-temperature product.

**Correction:** an earlier version of this exploratory audit assumed the `lwir11` asset name and omitted Landsat 7 scenes. The sensor-complete counts below supersede that earlier summary.

The baseline screen requires a nonzero temperature DN and clear QA_PIXEL bits 0–5 (fill, dilated cloud, cirrus where applicable, cloud, cloud shadow, snow). The stricter tests additionally apply the ST_QA uncertainty band (scale 0.01 K) and/or ST_CDIST cloud-distance band (scale 0.01 km). USGS describes these bands but does not prescribe the cutoffs below; they are sensitivity scenarios, not official pass/fail thresholds.

**Not reproducible from this repository.** These counts were produced by querying Planetary Computer in an earlier session, and no committed artifact holds them; the tooling that would re-derive them (rasterio, pystac-client, planetary-computer) is deliberately not part of the locked research environments. They are the only numbers in this brief that the documentation checker cannot verify, and they should be read as exploratory context rather than as a checked result. Re-deriving them would mean adding those dependencies and re-running the scene and QA-band queries over the 100 tree coordinates.

| Summer | ST scenes | Eligible tree-date pairs | Baseline QA | ST_QA ≤ 3 K | ST_CDIST ≥ 1 km |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2015 | 30 | 2,000 | 778 (38.9%) | 291 (14.5%) | 392 (19.6%) |
| 2016 | 33 | 2,200 | 351 (16.0%) | 178 (8.1%) | 242 (11.0%) |
| 2017 | 35 | 2,300 | 499 (21.7%) | 74 (3.2%) | 133 (5.8%) |
| 2018 | 33 | 2,200 | 670 (30.5%) | 378 (17.2%) | 455 (20.7%) |
| 2019 | 36 | 2,400 | 899 (37.5%) | 215 (9.0%) | 333 (13.9%) |
| 2020 | 35 | 2,300 | 796 (34.6%) | 239 (10.4%) | 368 (16.0%) |
| 2021 | 33 | 2,200 | 538 (24.5%) | 234 (10.6%) | 385 (17.5%) |
| 2022 | 38 | 2,399 | 1,105 (46.1%) | 151 (6.3%) | 347 (14.5%) |
| 2023 | 49 | 3,000 | 845 (28.2%) | 550 (18.3%) | 655 (21.8%) |
| 2024 | 39 | 2,200 | 803 (36.5%) | 191 (8.7%) | 337 (15.3%) |
| **Total** | **361** | **23,199** | **7,284 (31.4%)** | **2,501 (10.8%)** | **3,647 (15.7%)** |

Across all years, ST_QA cutoffs of ≤1 K and ≤2 K retained 0% and 0.9% of eligible pairs, respectively; ≤5 K retained 26.6%. Cloud-distance cutoffs of ≥0.5 km and ≥2 km retained 21.3% and 9.7%, respectively. Combining ST_QA ≤5 K with cloud distance ≥1 km retained the same 15.7% as the cloud-distance filter alone. Coverage is sensitive to quality policy, and no threshold here is stakeholder-approved.

The original WBGT reference date, 2016-08-24, has no Landsat scene item intersecting the Brussels sample area, so the satellite source cannot provide a same-date comparison for that event. Even the basic QA screen leaves a median of only three valid dates per tree in 2016; stricter screens reduce coverage further. This is not yet a validated seasonal heat measure.

The audit did not apply additional product-specific quality checks. The sample thermal asset has 100 m ground sampling even though it is delivered on a 30 m grid; the grid spacing is not independent 30 m thermal detail. Satellite land-surface temperature is also not WBGT, air temperature, tree shade, or a direct measure of human exposure. Any follow-up needs a documented quality policy and stakeholder agreement. Do not blend it into the ranking.

Sources: [USGS Landsat Collection 2 Surface Temperature](https://www.usgs.gov/landsat-missions/landsat-collection-2-surface-temperature), [USGS Collection 2 Quality Assessment Bands](https://www.usgs.gov/landsat-missions/landsat-collection-2-quality-assessment-bands), [Landsat 8/9 Level-2 Product Guide](https://www.usgs.gov/media/files/landsat-8-9-collection-2-level-2-science-product-guide), [Planetary Computer Landsat STAC quickstart](https://planetarycomputer.microsoft.com/docs/quickstarts/reading-stac-r/), and [Planetary Computer data-access tokens](https://planetarycomputer.microsoft.com/docs/concepts/sas/). Catalog reads were exploratory on 2026-10-16; no satellite snapshot was committed.

## Important limits

ERA5's grid step is about 28 km north–south and 18 km east–west at Brussels' latitude. Trees in the same cell share the same seasonal values, and all 100 points fall into only four cells. This can contextualize whether the single raster day was unusual and describe broad temporal exposure; it cannot distinguish streets, blocks, tree shade, or neighborhood-scale heat.

Apparent temperature is not WBGT. The ERA5 metrics and the normalized raster values have different units and meanings; do not combine or compare them as if they were the same scale. The ERA5 artifact therefore remains separate from the current ranking unless a stakeholder defines a suitable, spatially defensible way to use it.

## Questions for the review

1. Is the current single-day WBGT screen preferable to the available ten-year 100 m WBGT seasonal mean, or should the screen use a different heat period (for example a hot-day frequency or high percentile)?
2. Which heat period should guide the eventual decision: a representative hot day, JJA average, frequency of hot days, or another locally meaningful period?
3. Should this seasonal measure remain descriptive context, or should a future heat measure enter the ranking? If it should enter, what spatial resolution and validation would make that defensible?
4. Is the round-number 30 °C apparent-temperature threshold useful for discussion, or should recurrence be reported without a threshold until the stakeholder specifies one?

## Suggested decision record

Use the existing stakeholder worksheet to record one of these outcomes, or an alternative:

- **Keep the reference day:** retain the 24 August 2016 raster for the spatial screen; show ERA5 and the multi-date WBGT archive as context.
- **Use a multi-date WBGT period:** specify whether the operational measure is a seasonal mean, percentile, hot-day frequency, or another aggregation of the VITO 100 m archive, then validate it before changing the ranking.
- **Change the measure:** specify the operational heat metric, period, spatial unit, and validation needed before implementation.

This brief is a discussion aid, not a proposal to change the current ranking. See [`heat-season-method.md`](heat-season-method.md) and [`brussels-heat-season-sample.json`](../data/brussels-heat-season-sample.json) for the method and full snapshot. Record any accepted heat period in `tree-stakeholder-review.csv`; do not infer approval from this brief.
