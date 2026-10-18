import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fiona
from shapely.geometry import LineString, MultiLineString, Polygon, box, mapping
from shapely.ops import unary_union

from inputs import (EXTENSIONS, SNAPSHOTS, STEM, digest, full_scan_candidates,
                    load_selection, verified_extract, verify_inputs)
from metrics import merge_intervals, profile, route_line
from pipeline import encoded, execute, publish, rename_no_replace
from alignment_audit import shifted_profiles

ROOT = Path(__file__).resolve().parents[3]


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.route = LineString([(0, 0), (10, 0)])

    def test_empty_full_disjoint(self):
        for cover, length, gap in [(Polygon(), 0, 10), (box(-1, -1, 11, 1), 10, 0),
                                   (unary_union([box(1, -1, 3, 1), box(7, -1, 9, 1)]), 4, 4)]:
            result = profile(self.route, cover)
            self.assertAlmostEqual(result['overlap_m'], length)
            self.assertAlmostEqual(result['longest_nonoverlap_m'], gap)

    def test_directional_displacement_is_not_dilation(self):
        cover = box(2, -0.5, 8, 0.5)
        values = {v['scenario']: v for v in shifted_profiles(self.route, cover)}
        self.assertEqual(values['original']['overlap_percent'], 60)
        self.assertEqual(values['north_2m']['overlap_percent'], 0)
        offset = LineString([(0, 2), (10, 2)])
        other = {v['scenario']: v for v in shifted_profiles(offset, cover)}
        self.assertEqual(other['original']['overlap_percent'], 0)
        self.assertEqual(other['south_2m']['overlap_percent'], 60)
        self.assertEqual(profile(self.route, cover.buffer(2))['overlap_percent'], 100)

    def test_bend_and_reverse(self):
        line = LineString([(0, 0), (10, 0), (10, 10)])
        cover = box(5, -1, 11, 5)
        self.assertEqual(profile(line, cover)['overlap_m'], 10)
        self.assertEqual(profile(LineString(list(line.coords)[::-1]), cover)['overlap_m'], 10)

    def test_boundary_and_point_contact(self):
        self.assertEqual(profile(self.route, box(2, 0, 4, 1))['overlap_m'], 2)
        triangle = Polygon([(5, 0), (4, 2), (6, 2)])
        self.assertEqual(profile(self.route, triangle)['overlap_m'], 0)

    def test_reject_bad_routes(self):
        bad = [LineString(), LineString([(0, 0), (0, 0)]),
               LineString([(0, 0), (2, 2), (0, 2), (2, 0)]),
               LineString([(0, 0), (2, 0), (2, 2), (0, 0)]),
               LineString([(0, 0, 1), (2, 2, 1)]),
               MultiLineString([[(0, 0), (1, 0)], [(2, 0), (3, 0)]])]
        for geometry in bad:
            with self.subTest(geometry=geometry), self.assertRaises(ValueError):
                route_line(geometry)

    def test_merge_and_reject_reversed_interval(self):
        self.assertEqual(merge_intervals([[1, 2], [0, 1], [4, 5]]), [[0, 2], [4, 5]])
        with self.assertRaises(ValueError):
            merge_intervals([[2, 1]])


class InputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def test_manifest_tamper_and_exact_set(self):
        files = []
        for location, names in [('cache', [f'{STEM}.{ext}' for ext in EXTENSIONS]), ('snapshot', SNAPSHOTS)]:
            for name in names:
                (self.root/name).write_bytes(b'original')
                files.append(dict(location=location, name=name, bytes=8, sha256=digest(self.root/name)))
        manifest = self.root/'manifest.json'
        manifest.write_text(json.dumps(dict(schema_version=1, files=files)))
        verify_inputs(manifest, self.root)
        (self.root/f'{STEM}.shp').write_bytes(b'modified')  # Same length: size alone cannot detect it.
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            verify_inputs(manifest, self.root)
        manifest.write_text(json.dumps(dict(schema_version=1, files=files[:-1])))
        with self.assertRaisesRegex(ValueError, 'exactly'):
            verify_inputs(manifest, self.root)

    def copy_snapshots(self):
        for name in SNAPSHOTS:
            shutil.copy(ROOT/'data/research/canopy-inputs'/name, self.root/name)

    def test_frozen_small_snapshots_match_manifest(self):
        root = ROOT/'data/research/canopy-inputs'
        manifest = json.loads((root/'manifest.json').read_text())
        entries = [e for e in manifest['files'] if e['location'] == 'snapshot']
        self.assertEqual({e['name'] for e in entries}, set(SNAPSHOTS))
        for entry in entries:
            p = root/entry['name']
            self.assertEqual(p.stat().st_size, entry['bytes'])
            self.assertEqual(digest(p), entry['sha256'])

    def test_selection_preserves_count_and_ids(self):
        self.copy_snapshots()
        selected, request = load_selection(self.root)
        self.assertEqual([f['properties']['gid'] for f, _ in selected], [266, 5630, 5634, 5642, 5643])
        self.assertEqual(request['count_only_number_matched'], 82)

    def test_bad_crs_count_and_duplicate_rejected(self):
        for kind in ('crs', 'count', 'duplicate'):
            self.copy_snapshots()
            p = self.root/'cycling-frame.geojson'
            frame = json.loads(p.read_text())
            if kind == 'crs':
                frame['crs']['properties']['name'] = 'EPSG:4326'
            elif kind == 'count':
                frame['features'].pop()
            else:
                frame['features'][0]['properties']['gid'] = frame['features'][1]['properties']['gid']
            p.write_text(json.dumps(frame))
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                load_selection(self.root)

    def make_shp(self, crs='EPSG:31370'):
        path = self.root/'fixture.shp'
        with fiona.open(path, 'w', driver='ESRI Shapefile', crs=crs,
                        schema={'geometry': 'Polygon', 'properties': {'gridcode': 'int'}}) as dst:
            for geometry in (box(0, 0, 2, 2), box(10, 10, 12, 12)):
                dst.write(dict(geometry=mapping(geometry), properties={'gridcode': 4}))
        return path

    def test_full_scan_and_index_match(self):
        path = self.make_shp()
        candidates, count = full_scan_candidates(path, (-1, -1, 3, 3))
        self.assertEqual((candidates, count), ([0], 2))
        extracted, count = verified_extract(path, (-1, -1, 3, 3))
        self.assertEqual((len(extracted), count), (1, 2))

    def test_index_mismatch_is_rejected(self):
        path = self.make_shp()
        with patch('inputs.full_scan_candidates', return_value=([], 2)):
            with self.assertRaisesRegex(ValueError, 'Spatial index differs'):
                verified_extract(path, (-1, -1, 3, 3))

    def test_unmanifested_index_is_rejected(self):
        files = []
        for location, names in [('cache', [f'{STEM}.{ext}' for ext in ('cpg','prj','shp','shx','dbf')]),
                                ('snapshot', SNAPSHOTS)]:
            for name in names:
                p = self.root/name
                p.write_bytes(b'x')
                files.append(dict(location=location, name=name, bytes=1, sha256=digest(p)))
        manifest = self.root/'manifest.json'
        manifest.write_text(json.dumps(dict(schema_version=1, files=files)))
        (self.root/f'{STEM}.sbn').write_bytes(b'untrusted index')
        with self.assertRaisesRegex(ValueError, 'Unmanifested spatial index'):
            verify_inputs(manifest, self.root)

    def test_wrong_source_crs(self):
        path = self.make_shp('EPSG:4326')
        with self.assertRaisesRegex(ValueError, 'CRS'):
            verified_extract(path, (-1, -1, 3, 3))

    def test_complete_pipeline_and_midrun_identity_change(self):
        self.copy_snapshots()
        manifest = self.root/'fixture-manifest.json'
        with fiona.open(self.root/f'{STEM}.shp', 'w', driver='ESRI Shapefile', crs='EPSG:31370',
                        schema={'geometry': 'Polygon', 'properties': {'gridcode': 'int'}}) as dst:
            dst.write(dict(geometry=mapping(box(151970, 169145, 152990, 170165)),
                           properties={'gridcode': 4}))
            dst.write(dict(geometry=mapping(Polygon([(152200,169600), (152202,169602),
                                                    (152200,169602), (152202,169600)])),
                           properties={'gridcode': 3}))
        entries = []
        for location, names in [('cache', [f'{STEM}.{ext}' for ext in ('cpg','prj','shp','shx','dbf')]),
                                ('snapshot', SNAPSHOTS)]:
            for name in names:
                p = self.root/name
                entries.append(dict(location=location, name=name, bytes=p.stat().st_size, sha256=digest(p)))
        manifest.write_text(json.dumps({'schema_version': 1, 'files': entries, 'provenance': {'fixture': True}}))
        comparison, windows = execute(manifest, self.root)
        again, again_windows = execute(manifest, self.root)
        self.assertEqual(encoded(comparison), encoded(again))
        self.assertEqual(encoded(windows), encoded(again_windows))
        self.assertEqual(len(comparison['repair_audit']), 1)
        self.assertGreater(comparison['repair_audit'][0]['alternative_symmetric_difference_m2'], 0)
        self.assertGreater(windows['total_segment_length_m']-windows['analysed_length_per_anchor_m'], 0)
        self.assertEqual(len(comparison['results']), 30)
        self.assertEqual(len(windows['windows']), 40)
        self.assertTrue(all(abs(r['overlap_percent']-100) < 1e-7 for r in comparison['results']))
        self.assertTrue(all(abs(r['overlap_percent']-100) < 1e-7 for r in windows['windows']))
        self.assertEqual(windows['comparison_sha256'], hashlib.sha256(encoded(comparison)).hexdigest())
        original_verify = verify_inputs
        calls = []
        def change_after_first_check(path, cache):
            if calls:
                snapshot = self.root/'frame-request.json'
                snapshot.write_text(snapshot.read_text()+' ')
            calls.append(True)
            return original_verify(path, cache)
        with patch('pipeline.verify_inputs', side_effect=change_after_first_check):
            with self.assertRaisesRegex(ValueError, 'Input size changed'):
                execute(manifest, self.root)

    def test_truncated_shp_rejected(self):
        path = self.make_shp()
        path.write_bytes(path.read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError, 'length'):
            full_scan_candidates(path, (-1, -1, 3, 3))

    def test_publication_binds_outputs_and_refuses_overwrite(self):
        comparison = {'provenance': {'manifest_sha256': 'fixture'}, 'results': []}
        windows = {'provenance': comparison['provenance'],
                   'comparison_sha256': hashlib.sha256(encoded(comparison)).hexdigest()}
        output = self.root/'output'
        publish(output, comparison, windows)
        self.assertEqual(hashlib.sha256((output/'comparison.json').read_bytes()).hexdigest(),
                         json.loads((output/'windows.json').read_text())['comparison_sha256'])
        with self.assertRaises(ValueError):
            publish(output, comparison, windows)
        windows['comparison_sha256'] = 'wrong'
        with self.assertRaises(ValueError):
            publish(self.root/'wrong', comparison, windows)
        self.assertFalse((self.root/'wrong').exists())
        windows['comparison_sha256'] = hashlib.sha256(encoded(comparison)).hexdigest()
        def racing_destination(source, destination):
            destination.mkdir()
            return rename_no_replace(source, destination)
        with patch('pipeline.rename_no_replace', side_effect=racing_destination):
            with self.assertRaises(FileExistsError):
                publish(self.root/'race', comparison, windows)
        self.assertTrue((self.root/'race').is_dir())
        self.assertEqual(list((self.root/'race').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
