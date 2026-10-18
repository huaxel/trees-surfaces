"""Offline input validation. No download or automatic manifest acceptance."""
import hashlib
import json
import mmap
import struct
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import fiona
from shapely.geometry import box, shape

from metrics import require, route_line

STEM = 'CHM_BCR_EG_2022_complete'
EXTENSIONS = ('cpg', 'prj', 'sbn', 'sbx', 'shp', 'shx', 'dbf')
SNAPSHOTS = ('zenodo-record.json', 'cycling-frame.geojson', 'frame-request.json', 'frame-hits.xml')
FRAME = (151980, 169155, 152980, 170155)


def digest(path, algorithm='sha256'):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def verify_inputs(manifest_path, cache):
    manifest_path, cache = Path(manifest_path), Path(cache)
    manifest = json.loads(manifest_path.read_text())
    require(manifest['schema_version'] == 1, 'Unsupported manifest')
    entries = manifest['files']
    expected = {('cache', f'{STEM}.{ext}') for ext in ('cpg', 'prj', 'shp', 'shx', 'dbf')}
    expected |= {('snapshot', name) for name in SNAPSHOTS}
    indices = {('cache', f'{STEM}.{ext}') for ext in ('sbn', 'sbx')}
    actual = {(e['location'], e['name']) for e in entries}
    require(len(entries) == len(actual) and actual in (expected, expected | indices),
            'Manifest must identify exactly the required inputs and optional index pair')
    for location, name in indices - actual:
        require(not (cache/name).exists(), f'Unmanifested spatial index: {name}')
    for entry in entries:
        root = cache if entry['location'] == 'cache' else manifest_path.parent
        path = root / entry['name']
        require(path.stat().st_size == entry['bytes'], f'Input size changed: {path.name}')
        require(digest(path) == entry['sha256'], f'Input SHA-256 changed: {path.name}')
    return digest(manifest_path)


def load_selection(snapshot_root):
    root = Path(snapshot_root)
    request = json.loads((root/'frame-request.json').read_text())
    frame = json.loads((root/'cycling-frame.geojson').read_text())
    hits = ET.parse(root/'frame-hits.xml').getroot()
    require(frame['crs']['properties']['name'] == 'urn:ogc:def:crs:EPSG::31370',
            'Cycling source CRS must be EPSG:31370')
    require(tuple(request['bbox']) == FRAME, 'Comparison frame changed')
    query = parse_qs(urlsplit(request['url']).query)
    require(query.get('bbox') == [','.join(map(str, FRAME))+',EPSG:31370'],
            'Request bbox differs from selection frame')
    require(query.get('srsName') == ['EPSG:31370'], 'Requested CRS differs')
    count = int(hits.attrib['numberMatched'])
    features = frame['features']
    require(count == len(features) == frame['numberReturned'] == request['response_count'],
            'Count-only response and feature retrieval disagree')
    require(len(features) < request['response_cap'], 'Possibly truncated frame')
    require(len({f['properties']['gid'] for f in features}) == len(features),
            'Duplicate cycling IDs')
    selected = []
    for feature in features:
        properties = feature['properties']
        if properties['status_code'] != 1 or properties['type_code'] != 12:
            continue
        route = route_line(shape(feature['geometry']))
        if route.length >= 100 and box(*FRAME).covers(route):
            selected.append((feature, route))
    require(bool(selected), 'Empty selected sample')
    selected.sort(key=lambda pair: pair[0]['properties']['gid'])
    request['count_only_number_matched'] = count
    return selected, request


def full_scan_candidates(path, bounds):
    """Read every SHP record envelope without using SHX/SBN/SBX."""
    candidates, records = [], 0
    with Path(path).open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        require(len(data) >= 100, 'Truncated SHP header')
        require(struct.unpack_from('>i', data, 0)[0] == 9994, 'Invalid SHP header')
        require(struct.unpack_from('>i', data, 24)[0]*2 == len(data), 'SHP length mismatch')
        pos = 100
        while pos < len(data):
            require(pos+12 <= len(data), 'Truncated SHP record')
            number, words = struct.unpack_from('>2i', data, pos)
            end = pos+8+words*2
            require(number == records+1 and words >= 2 and end <= len(data),
                    'Invalid SHP record header')
            kind = struct.unpack_from('<i', data, pos+8)[0]
            require(kind in (0, 5), 'Expected Polygon or Null shape')
            if kind == 5:
                require(words >= 22, 'Truncated polygon')
                a, b, c, d = struct.unpack_from('<4d', data, pos+12)
                if c >= bounds[0] and a <= bounds[2] and d >= bounds[1] and b <= bounds[3]:
                    candidates.append(records)
            pos, records = end, records+1
        require(pos == len(data), 'SHP record boundaries do not reconcile')
    with Path(path).with_suffix('.dbf').open('rb') as dbf:
        header = dbf.read(32)
    require(len(header) == 32 and records == struct.unpack_from('<I', header, 4)[0],
            'SHP/DBF record counts disagree')
    return candidates, records


def verified_extract(path, bounds):
    window = box(*bounds)
    with fiona.open(path) as source:
        require(source.crs.to_epsg() == 31370, 'Vegetation CRS must be EPSG:31370')
        indexed = {int(f.id): f for f in source.filter(bbox=bounds)
                   if shape(f.geometry).intersects(window)}
        candidates, records = full_scan_candidates(path, bounds)
        scanned = set()
        for fid in candidates:
            feature = source[fid]
            require(feature is not None, 'Missing SHX feature')
            if shape(feature.geometry).intersects(window):
                scanned.add(fid)
        require(scanned == set(indexed), 'Spatial index differs from full record scan')
    return list(indexed.values()), records
