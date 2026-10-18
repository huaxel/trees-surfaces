# VITO licence and convention enquiry — ready to send, not sent

**Status: a draft. No contact has been sent.** Sending is a human action; nothing in this
repository has been communicated to VITO, and no reply exists.

**Why it matters.** Two things are blocked on it, and neither can be settled by analysis:

1. **Licence.** Whether the derived values already committed under `data/` may be published
   and reused externally. The archive page states no licence and the NetCDF files carry no
   licence attribute, so derived values stay exploratory by our own rule.
2. **A convention, not a permission.** Whether the archive's daily values use UTC or local
   day boundaries. Every within-archive comparison this project publishes inherits that
   convention, and matching date labels and the proleptic-Gregorian calendar do not
   establish it. This is a factual question with a factual answer.

**Send to:** `urbclim@vito.be` — the contact recorded in the project's own licence review.

## Draft

**Subject:** Licence terms and day-boundary convention for the daily WBGT archive (Brussels)

Dear UrbClim team,

We are running a non-commercial feasibility study on urban greening and heat exposure in the
Brussels-Capital Region, using open data only. We have used your daily WBGT archive at 100 m
for Brussels — the ten annual daily-maximum files for 2008–2017 at
`provide.marvin.vito.be/ftp/compressed_daily/Brussels/`, and the corresponding
`WBGT_year_daily_mean_2016.nc`. We cite De Ridder et al. (2015) and Souverijns et al. (2026)
as the archive page requests.

We would be grateful for answers to two questions.

**1. Licence and reuse.** The archive page states no licence terms and the files carry no
licence attribute, so we have treated everything derived from them as exploratory and have
not claimed reuse rights. Two related records do not transfer their terms: the Souverijns et
al. (2026) decadal indicator set is CC BY 4.0, and the Copernicus Climate Data Store record
`sis-urban-climate-cities` (deprecated 2024-05-10) is CC-BY-4.0 but contains no WBGT.

Specifically, may we:

- publish small **derived** results from the daily files — for example WBGT sampled at 100
  fixed points in Brussels, and descriptive comparisons between aggregations of the same
  series (daily mean versus daily maximum, and the reference day versus a ten-summer
  seasonal mean, 90th percentile and hot-day count);
- state those results under a permissive licence in a public repository, with attribution to
  VITO and the citations above;
- redistribute the **NetCDF files themselves**? We assume not and have never redistributed
  them — they are cached locally and git-ignored — but we would like to confirm that.

**2. Day-boundary convention.** The archive gives one value per day. Could you confirm
whether the daily aggregation uses UTC or local (CET/CEST) day boundaries, and whether the
same convention applies to both the daily-mean and daily-maximum files? We compare your
daily values with seasonal aggregations of our own, so a difference in day boundary would
change what our seasonal statistics mean, and matching date labels do not reveal it.

If it is easier, a short reply to the two points is entirely sufficient, and we are happy to
share the derived results we hold if that helps you assess the request.

With thanks for maintaining the archive,

[Name, role, organisation, contact]

## What would change once answered

| Question | Effect on this repository |
| --- | --- |
| Derived-value licence | The mean/maximum comparison already computed locally (`.cache/wbgt-mean-max/`) could be published, and the existing committed derived values could be labelled with terms rather than as exploratory |
| Redistribution | Would decide whether NetCDF files could ever be committed; today they never are |
| Day boundary | Would let the seasonal statistics be described as UTC or local, and would either confirm the current comparison or require it to be recomputed |

Until a reply arrives, the recorded status stays "unresolved" and the derived values stay
exploratory. See [`wbgt-mean-max-method.md`](wbgt-mean-max-method.md) and
[`heat-season-method.md`](heat-season-method.md) for the licence review in full.
