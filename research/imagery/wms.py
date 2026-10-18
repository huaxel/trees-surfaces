"""Fetch and pin the two 2021 UrbIS orthophoto products for fixed diagnostic windows.

Two separate steps, deliberately: `fetch` uses the network once and writes new
files plus a manifest that pins them; `verify` is offline and is the only way the
analysis is allowed to read imagery. Neither step replaces an existing file, so a
check either re-verifies the pinned bytes or fails.

The pinned record files are the publisher's own metadata for the two products.
Their statements describe the dataset's flights; they do NOT attribute a specific
flight date to `Ortho2021Eo` or `Ortho2021Ns`, and the analysis does not assume
that they do.
"""
import argparse
import datetime
import json
import math
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image
from shapely.geometry import box, shape

from geometry import route_line
from support import digest, digest_bytes, encoded, require

SERVICE = 'https://geoservices-urbis.irisnet.be/geoserver/urbisgrid/ows'
LAYERS = {'east_west_2021_09_22_or_25': 'Ortho2021Eo',
          'north_south_2021_10_09': 'Ortho2021Ns'}
RECORDS = {'east_west_2021_09_22_or_25': 'fed5671a-e61a-4972-9eb9-fc5e8cdc6dbd',
           'north_south_2021_10_09': 'fec72767-d6b6-41b9-a767-616df2779aae'}
RECORD_URL = 'https://geobru.irisnet.be/geonetwork/srv/api/records/{}/formatters/xml'
WINDOW_M, PIXEL_M, CHAINAGES = 120, 0.1, (0.1, 0.5, 0.9)
SRS = 'EPSG:31370'
IMAGE_CAP = 8_000_000
RECORD_CAP = 1_000_000
IMAGE_DIR, RECORD_DIR = 'images', 'records'


def selected_routes(frame_path, request_path, hits_path):
    """The published sample, re-derived from the frozen request, frame and hits snapshot."""
    frame = json.loads(Path(frame_path).read_text())
    request = json.loads(Path(request_path).read_text())
    hits = ET.parse(hits_path).getroot()
    require(frame['crs']['properties']['name'] == 'urn:ogc:def:crs:EPSG::31370',
            'Cycling source CRS must be EPSG:31370')
    matched = int(hits.attrib['numberMatched'])
    require(matched == request['response_count'] == len(frame['features']),
            'Frozen count-only probe disagrees with the retrieval')
    covered = box(*request['bbox'])
    routes = []
    for feature in frame['features']:
        properties = feature['properties']
        if properties['status_code'] != 1 or properties['type_code'] != 12:
            continue
        route = route_line(shape(feature['geometry']))
        # Same two conditions as the published canopy sample; anything else is excluded.
        if route.length >= 100 and covered.covers(route):
            routes.append((properties['gid'], route))
    routes.sort()
    require(bool(routes), 'Empty sample')
    return routes, matched


def plan(snapshot_root, published_comparison):
    """Fixed windows, declared before any imagery is fetched."""
    snapshot_root = Path(snapshot_root)
    routes, matched = selected_routes(snapshot_root/'cycling-frame.geojson',
                                      snapshot_root/'frame-request.json',
                                      snapshot_root/'frame-hits.xml')
    published = json.loads(Path(published_comparison).read_text())
    require([gid for gid, _ in routes] == published['selected_gids'],
            'Re-derived sample differs from the published canopy selection')
    require(published['selection']['count_only_number_matched'] == matched
            and published['selection']['response_count'] == matched,
            'Published selection used another frame request')
    lengths = {row['gid']: row['length_m'] for row in published['results']}
    for gid, route in routes:
        require(math.isclose(route.length, lengths[gid], rel_tol=0, abs_tol=1e-9),
                f'Re-derived length differs from the published segment length for gid {gid}')
    half = WINDOW_M/2
    windows = []
    for gid, route in routes:
        for fraction in CHAINAGES:
            point = route.interpolate(route.length*fraction)
            bounds = (point.x-half, point.y-half, point.x+half, point.y+half)
            windows.append(dict(window_id=f'gid{gid}-at{int(fraction*100):02d}', gid=gid,
                                fraction=fraction, chainage_m=route.length*fraction,
                                segment_length_m=route.length, bounds=bounds))
    return dict(schema_version=1, pixel_m=PIXEL_M, window_m=WINDOW_M,
                width=int(round(WINDOW_M/PIXEL_M)), height=int(round(WINDOW_M/PIXEL_M)),
                srs=SRS, service=SERVICE, layers=LAYERS, records=RECORDS,
                chainage_fractions=list(CHAINAGES), windows=windows,
                frozen_inputs={name: digest(snapshot_root/name)
                               for name in ('cycling-frame.geojson', 'frame-request.json',
                                            'frame-hits.xml')},
                published_comparison_sha256=digest(published_comparison))


def get(url, cap):
    with urllib.request.urlopen(url, timeout=60) as response:
        body = response.read(cap+1)
        headers = dict(response.headers)
    require(len(body) <= cap, f'Response larger than {cap} bytes: {url}')
    return body, headers


def record_fields(body):
    """Acquisition period and statement text as published, without interpreting them."""
    root = ET.fromstring(body)
    values = {'begin': [], 'end': [], 'statement': []}
    for element in root.iter():
        tag = element.tag.split('}')[-1]
        text = ' '.join(' '.join(element.itertext()).split())
        if tag in ('beginPosition', 'endPosition') and text:
            values[tag[:-8].lower()].append(text)
        elif tag == 'statement' and text:
            values['statement'].append(text)
    require(values['begin'] and values['end'], 'No acquisition period in the source record')
    require(values['statement'], 'No source statement in the record')
    require(len(set(values['statement'])) == 1, 'Conflicting source statements')
    return dict(begin_position=sorted(set(values['begin']))[0],
                end_position=sorted(set(values['end']))[0],
                statement=values['statement'][0])


def flight_dates(record_id):
    url = RECORD_URL.format(record_id)
    body, _ = get(url, RECORD_CAP)
    return body, dict(record_url=url, record_sha256=digest_bytes(body), **record_fields(body))


def fetch(plan_path, root, manifest_path):
    """Network step. Writes new files and a new manifest, never replacing either."""
    plan_path, root, manifest_path = Path(plan_path), Path(root), Path(manifest_path)
    spec = json.loads(plan_path.read_text())
    require(not manifest_path.exists(), 'Manifest already exists; refusing to replace it')
    images, records = root/IMAGE_DIR, root/RECORD_DIR
    for directory in (images, records):
        require(not directory.exists() or not any(directory.iterdir()),
                f'Output directory is not empty: {directory}')
        directory.mkdir(parents=True, exist_ok=True)
    entries, requests, source = [], [], {}
    for name, record_id in sorted(spec['records'].items()):
        body, fields = flight_dates(record_id)
        path = records/f'{name}.xml'
        require(not path.exists(), f'Record already exists: {path.name}')
        path.write_bytes(body)
        entries.append(dict(location='record', name=f'{RECORD_DIR}/{path.name}',
                            bytes=path.stat().st_size, sha256=digest(path)))
        source[name] = fields
    for window in spec['windows']:
        bounds = window['bounds']
        for name, layer in sorted(spec['layers'].items()):
            query = dict(service='WMS', version='1.1.1', request='GetMap', layers=layer, styles='',
                         srs=spec['srs'], bbox=','.join(str(float(v)) for v in bounds),
                         width=spec['width'], height=spec['height'], format='image/jpeg')
            url = spec['service']+'?'+urllib.parse.urlencode(query)
            body, headers = get(url, IMAGE_CAP)
            require(body[:2] == b'\xff\xd8', f'Not a JPEG response: {url}')
            file_name = f"{window['window_id']}-{layer}.jpg"
            path = images/file_name
            require(not path.exists(), f'Image already exists: {path.name}')
            path.write_bytes(body)
            with Image.open(path) as image:
                require(image.size == (spec['width'], spec['height']),
                        f'Unexpected image size for {file_name}: {image.size}')
                require(image.mode in ('RGB', 'L'), f'Unexpected image mode for {file_name}: {image.mode}')
            entries.append(dict(location='image', name=f'{IMAGE_DIR}/{file_name}',
                                bytes=path.stat().st_size, sha256=digest(path)))
            requests.append(dict(window_id=window['window_id'], layer=layer, product=name,
                                 file=f'{IMAGE_DIR}/{file_name}', url=url,
                                 bbox=list(bounds), width=spec['width'], height=spec['height'],
                                 srs=spec['srs'], format='image/jpeg',
                                 retrieved_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                 response_headers={k.lower(): v for k, v in headers.items()},
                                 bytes=path.stat().st_size, sha256=digest(path)))
    manifest = dict(schema_version=1, plan_sha256=digest(plan_path), plan=spec,
                    source_records=source, requests=requests, files=entries,
                    retrieved_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(encoded(manifest))
    return manifest


def verify(manifest_path, root, plan_path=None):
    """Offline. Returns the manifest after checking every pinned input and the plan."""
    manifest_path, root = Path(manifest_path), Path(root)
    manifest = json.loads(manifest_path.read_text())
    require(manifest['schema_version'] == 1, 'Unsupported imagery manifest')
    if plan_path is not None:
        require(digest(plan_path) == manifest['plan_sha256'],
                'Frozen plan does not match the manifest; the windows are not the declared ones')
        # The analysis reads the embedded copy, so that copy must be the frozen plan.
        require(manifest['plan'] == json.loads(plan_path.read_text()),
                'Manifest plan differs from the frozen plan; the analysed windows are not the declared ones')
    entries = manifest['files']
    require(len(entries) == len({e['name'] for e in entries}), 'Duplicate entries in imagery manifest')
    expected = {(w['window_id'], name) for w in manifest['plan']['windows']
                for name in manifest['plan']['layers']}
    require(expected == {(r['window_id'], r['product']) for r in manifest['requests']},
            'Requests do not cover every planned window and product exactly once')
    require({r['file'] for r in manifest['requests']} ==
            {e['name'] for e in entries if e['location'] == 'image'}, 'Requests and images disagree')
    require({f"{RECORD_DIR}/{name}.xml" for name in manifest['plan']['records']} ==
            {e['name'] for e in entries if e['location'] == 'record'}, 'Requests and records disagree')
    planned = {w['window_id']: list(w['bounds']) for w in manifest['plan']['windows']}
    for request in manifest['requests']:
        require(request['bbox'] == planned[request['window_id']],
                'Request bbox differs from the plan: '+request['window_id'])
        require(request['layer'] == manifest['plan']['layers'][request['product']],
                'Request layer differs from the plan: '+request['window_id'])
        require(request['format'] == 'image/jpeg' and request['srs'] == manifest['plan']['srs'],
                'Request parameters differ from the plan: '+request['window_id'])
    for entry in entries:
        path = root/entry['name']
        require(path.exists(), f'Pinned input is missing: {entry["name"]}')
        require(path.stat().st_size == entry['bytes'], f'Pinned input size changed: {path.name}')
        require(digest(path) == entry['sha256'], f'Pinned input SHA-256 changed: {path.name}')
    for name, fields in manifest['source_records'].items():
        stored = root/RECORD_DIR/f'{name}.xml'
        require(digest_bytes(stored.read_bytes()) == fields['record_sha256'],
                f'Stored record does not match its own digest: {name}')
        require(record_fields(stored.read_bytes()) == {key: fields[key] for key in
                                                       ('begin_position', 'end_position', 'statement')},
                f'Record fields differ from the stored file: {name}')
    for request in manifest['requests']:
        path = root/request['file']
        with Image.open(path) as image:
            require(image.size == (request['width'], request['height']),
                    f'Pinned image changed size: {path.name}')
            require(image.mode in ('RGB', 'L'), f'Pinned image changed mode: {path.name}')
    return manifest


def pinned_array(manifest, root, window_id, layer):
    """Decode one pinned image and check it still matches its manifest entry."""
    request = next((r for r in manifest['requests']
                    if (r['window_id'], r['layer']) == (window_id, layer)), None)
    require(request is not None, f'No pinned request for {window_id} {layer}')
    entry = next((e for e in manifest['files'] if e['name'] == request['file']), None)
    require(entry is not None, f'No pinned image for {window_id} {layer}')
    path = Path(root)/entry['name']
    require(digest(path) == entry['sha256'], f'Imagery SHA-256 changed: {path.name}')
    with Image.open(path) as image:
        return np.asarray(image.convert('RGB'))


def main():
    repository = Path(__file__).resolve().parents[2]
    frozen = repository/'data/research/canopy-inputs'
    published = repository/'data/research/canopy-verified/comparison.json'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, default=frozen)
    parser.add_argument('--comparison', type=Path, default=published)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent.parent
                        /'data/research/imagery-inputs')
    parser.add_argument('--fetch', action='store_true',
                        help='Fetch from upstream into --root; refused if the plan or files already exist')
    args = parser.parse_args()
    manifest_path = args.root/'manifest.json'
    plan_path = args.root/'plan.json'
    if args.fetch:
        require(not plan_path.exists(), 'Plan already exists; the fetch step writes a new plan first')
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_bytes(encoded(plan(args.snapshot, args.comparison)))
        manifest = fetch(plan_path, args.root, manifest_path)
        print(json.dumps(dict(plan_sha256=manifest['plan_sha256'], files=len(manifest['files']),
                              windows=len(manifest['plan']['windows'])), indent=2))
        return
    manifest = verify(manifest_path, args.root, plan_path)
    print(json.dumps(dict(plan_sha256=manifest['plan_sha256'],
                          files=len(manifest['files']),
                          windows=len(manifest['plan']['windows'])), indent=2))


if __name__ == '__main__':
    main()
