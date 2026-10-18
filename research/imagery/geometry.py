"""Route validation for the imagery check.

Deliberately a small copy of the canopy project's `route_line`: importing across
projects would couple their dependency sets, and `plan` binds the re-derived
geometry back to the published segment lengths, so any divergence fails loudly.
"""
import math

from shapely.ops import linemerge

from support import require


def route_line(geometry):
    route = linemerge(geometry) if geometry.geom_type == 'MultiLineString' else geometry
    require(route.geom_type == 'LineString', 'Route must be a single connected line')
    require(not route.is_empty and route.is_valid and route.is_simple,
            'Route must be nonempty, valid and simple')
    require(math.isfinite(route.length) and route.length > 0, 'Invalid route length')
    require(not route.is_ring, 'Closed routes need an explicit origin')
    require(all(len(c) == 2 and all(math.isfinite(v) for v in c) for c in route.coords),
            'Route coordinates must be finite 2D values')
    return route
