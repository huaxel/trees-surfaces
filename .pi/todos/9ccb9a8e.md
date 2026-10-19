{
  "id": "9ccb9a8e",
  "title": "Probe canopy×heat overlap (idea #4): tree points vs canopy windows from committed files",
  "tags": [
    "exploration",
    "canopy",
    "heat"
  ],
  "status": "closed",
  "created_at": "2026-10-19T05:57:57.879Z",
  "updated_at": "2026-10-19T05:58:23.420Z"
}

PROBE COMPLETE 2026-10-19 — idea #4 REJECTED for the current pilot frame. Read-only; repo untouched.\n\nMethod: windowed gids {266, 5630, 5634, 5642, 5643} from cycling-canopy-100m-windows.json (40 windows, 1,295.5 m); geometries from canopy-inputs/cycling-frame.geojson (EPSG:31370); 200 tree points projected WGS84→31370 via pyproj; exact point-to-segment minimum distances.\n\nFalsifier result: CONFIRMED (no overlap). Managed: nearest tree 896 m from any windowed segment, 0% within 500 m. Remarkable: nearest 470 m, 2% within 500 m. The pilot frame and the tree samples are different parts of the city.\n\nResurrection condition (precise): #4 revives if canopy analysis scales beyond the five-segment pilot to tree neighborhoods, or a new window set is cut around tree points with the existing methods. Both are new-work decisions, not probes. The pilot's 'local frame' limit already records this; now quantified.
