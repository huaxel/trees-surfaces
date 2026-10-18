# Pinned imagery inputs

Frozen inputs for the cross-product registration check described in
`docs/imagery-registration-check.md`. Nothing here is regenerated in place: the tools
write a new plan and new files, and refuse to replace anything that already exists.

| Path | Contents |
|---|---|
| `plan.json` | The declared windows: 5 routes × 3 chainages, 120 m at 0.1 m pixels, `EPSG:31370`, with the digests of the frozen cycling-frame snapshots it was derived from |
| `manifest.json` | Digest, size, request URL and response headers for every pinned file, plus the publisher's acquisition period and statement for each product and the plan digest |
| `images/` | 30 WMS responses: both products for every window (about 6.5 MB) |
| `records/` | The two UrbIS/GeoNetwork metadata records the acquisition period and statement are read from |

Licence: **CC BY 4.0**, citation of the source required. Each record states "No
limitations to public access" and "Creative Commons Attribution (CC-BY) - required
citation of data source" (Paradigm / CIRB, BE.CIRB), with the CC BY 4.0 licence text.
The records are titled by flight axis — *Orthophoto – 2021 (axe Est-Ouest)* and
*Orthophoto – 2021 (axe Nord-Sud)* — and the shared statement dates the east–west
flights to 22 and 25 September and the north–south flight to 9 October; the acquisition
period (2021-09-17 to 2021-10-09) is identical in both and does not separate them.

Verify everything offline:

```sh
uv run --locked --python 3.12.12 --project research/imagery python research/imagery/wms.py
```

`scripts/validate-imagery.sh` also runs that verification as part of the repository gate.
