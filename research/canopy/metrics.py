"""Mapped line overlap, not shade or observed cyclist exposure."""
import math

from shapely.geometry import LineString, Point
from shapely.ops import linemerge


def require(condition, message):
    if not condition:
        raise ValueError(message)


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


def parts(geometry, kind):
    if geometry.is_empty:
        return []
    if geometry.geom_type == kind:
        return [geometry]
    return [p for g in getattr(geometry, 'geoms', ()) for p in parts(g, kind)]


def merge_intervals(intervals):
    merged = []
    for a, b in sorted(intervals):
        require(math.isfinite(a) and math.isfinite(b) and b >= a, 'Invalid interval')
        if b - a <= 1e-9:
            continue
        if merged and a <= merged[-1][1] + 1e-8:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged


def profile(route, cover):
    route = route_line(route)
    require(cover.is_valid, 'Cover must be repaired before intersection')
    intervals = []
    offset = 0.0
    coordinates = list(route.coords)
    for a, b in zip(coordinates, coordinates[1:]):
        segment = LineString([a, b])
        if segment.length == 0:
            continue
        for part in parts(segment.intersection(cover), 'LineString'):
            distances = [segment.project(Point(c)) for c in part.coords]
            intervals.append([offset + min(distances), offset + max(distances)])
        offset += segment.length
    intervals = merge_intervals(intervals)
    gaps, at = [], 0.0
    for a, b in intervals:
        if a > at + 1e-8:
            gaps.append([at, a])
        at = b
    if at < route.length - 1e-8:
        gaps.append([at, route.length])
    overlap = sum(b - a for a, b in intervals)
    direct = route.intersection(cover).length
    require(math.isclose(overlap, direct, abs_tol=1e-6, rel_tol=0),
            'Interval length differs from direct intersection')
    require(math.isclose(overlap + sum(b-a for a, b in gaps), route.length,
                         abs_tol=1e-6, rel_tol=0), 'Length partition does not reconcile')
    return dict(overlap_m=overlap, overlap_percent=100*overlap/route.length,
                longest_nonoverlap_m=max((b-a for a, b in gaps), default=0.0),
                overlap_intervals_m=intervals, nonoverlap_intervals_m=gaps)
