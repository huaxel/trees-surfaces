# Seasonal heat context

## Purpose

The committed Brussels Environment WBGT raster describes one modeled hot day, 24 August 2016. The public regional WMS exposes that scenario rather than a multi-date series. This artifact tests how that reference day sits within a repeatable multi-year summer distribution. It **does not** change the heat input used by the ranking.

**This is not the only multi-date option.** The committed raster is a VITO UrbClim product (the study was commissioned by Brussels Environment and executed by VITO at 100 m), and VITO publishes a multi-date daily 100 m WBGT archive for 2008–2017 on a matching grid. The archive reports WBGT in °C as daily maxima; the committed raster is a 0–100 indicator for a 24-hour mean scenario, so their values and temporal summaries are not interchangeable. `brussels-heat-wbgt-sample.json`, produced by [`bin/generate_wbgt_context.jl`](../bin/generate_wbgt_context.jl), samples the archive at the committed tree points. The ERA5 context here is a coarse cross-check on temporal representativeness, not the project's only route to multi-date heat evidence. See [`heat-season-stakeholder-brief.md`](heat-season-stakeholder-brief.md) for the comparison between the two.

## Source and period

The generator requests `models=era5` explicitly from the Open-Meteo Historical Weather API (`https://archive-api.open-meteo.com/v1/archive`). The window is 1 January 2015–31 December 2024; the season is June–August (JJA), giving 92 days per year and 920 seasonal days per grid cell. JJA contains the committed 24 August reference date and is a conventional meteorological summer window. The ten-season span reduces dependence on a single year's weather while remaining a bounded, reproducible context for the 2016 raster.

Daily variables are `temperature_2m_max`, `temperature_2m_min`, `apparent_temperature_max`, `relative_humidity_2m_mean`, `shortwave_radiation_sum`, and `wind_speed_10m_mean`. The artifact reports the pooled JJA mean of daily apparent-temperature maxima, mean days per season with apparent-temperature maximum ≥30 °C (a descriptive threshold, not a health-warning threshold), mean tropical nights with minimum temperature ≥20 °C, and the reference date's rank/percentile within its own 2016 JJA season. It also records the reference day's ERA5 apparent-temperature maximum and the ten-season context. Apparent temperature is a humidity-aware air-temperature index, **not WBGT**.

## Spatial assignment and limitations

Each managed-tree coordinate is assigned to the nearest 0.25° ERA5 grid step. The request is batched across the distinct cells represented in the 100-tree sample. All trees assigned to one cell receive the same values. A 0.25° grid step is approximately 28 km north-south and 18 km east-west at Brussels' latitude: this is too coarse to represent neighborhood, street, shade, or canopy differences. It supplies temporal context only; the Brussels Environment raster remains the ranking's spatial heat input. The two measures have different units and semantics and must not be compared pixel by pixel.

## Validation and reproduction

`bin/generate_heat_season.jl data` makes two batched live requests: a one-day coordinate probe for the 100 committed tree points verifies Open-Meteo's actual native-grid snapping, then a full-period request fetches each distinct grid cell. It atomically writes `data/brussels-heat-season-sample.json`. The generator checks returned grid coordinates, exact date coverage, units, complete finite daily values, plausible value ranges, and minimum/maximum temperature ordering. Unit tests use synthetic payloads; the regular validation gate reads the committed snapshot offline. `JULIA_REFRESH_CHECK=1 scripts/validate-julia.sh` additionally checks the current archive response without changing committed snapshots.

The output records both request URLs (the coordinate probe and full-period series), model, variables' value semantics, period, and source attribution. The API data are CC BY 4.0; attribute Open-Meteo and Copernicus/ECMWF, and note that the data were modified through aggregation. Consult the current source terms before redistributing updated data.
