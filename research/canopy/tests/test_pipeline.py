import hashlib
import json
import pathlib
import random
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
from validation_frame import STEP_M, classify_points
from design_effect import (allocate, distinct_realisations, lag_autocorrelation, measure,
                           segment_series, systematic_proportion)
from selection import allocate_cells, build, select, systematic_indices
from sampling_plan import (largest_remainder, plan, required_sample_size, strata_from_published,
                           stratum_totals, wilson_interval)

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



class SamplingPlanTests(unittest.TestCase):
    """Planning arithmetic only: these check the design, not any measured accuracy."""

    def test_required_sample_size_matches_the_normal_approximation(self):
        # z^2 * p(1-p) / e^2 with z = 1.95996
        self.assertEqual(required_sample_size(0.05, 0.5), 385)
        self.assertEqual(required_sample_size(0.10, 0.5), 97)
        self.assertEqual(required_sample_size(0.10, 0.1), 35)
        self.assertEqual(required_sample_size(0.075, 0.25), 129)
        # Clustering can only increase the requirement.
        self.assertEqual(required_sample_size(0.075, 0.25, design_effect=3), 385)
        for bad in (0.0, 1.0, -0.1):
            with self.subTest(prevalence=bad), self.assertRaises(ValueError):
                required_sample_size(0.05, bad)
        with self.assertRaises(ValueError):
            required_sample_size(0.05, 0.25, design_effect=0.5)

    def test_wilson_interval_is_bounded_and_reaches_the_target(self):
        low, high = wilson_interval(192, 385)
        self.assertGreaterEqual(low, 0.0)
        self.assertLessEqual(high, 1.0)
        self.assertAlmostEqual((high - low) / 2, 0.05, delta=0.002)
        for successes, total in ((0, 40), (40, 40)):
            with self.subTest(successes=successes):
                low, high = wilson_interval(successes, total)
                self.assertGreaterEqual(low, 0.0)
                self.assertLessEqual(high, 1.0)
        with self.assertRaises(ValueError):
            wilson_interval(5, 0)

    def test_largest_remainder_is_deterministic_and_exact(self):
        self.assertEqual(largest_remainder([1, 1, 1], 10), [4, 3, 3])
        self.assertEqual(largest_remainder([0, 5, 5], 3), [0, 2, 1])
        self.assertEqual(sum(largest_remainder([694.8, 419.6, 181.0], 385)), 385)
        self.assertEqual(largest_remainder([694.8, 419.6, 181.0], 385),
                         largest_remainder([694.8, 419.6, 181.0], 385))
        with self.assertRaises(ValueError):
            largest_remainder([0, 0], 5)

    def test_strata_come_from_the_published_artifact_and_reconcile(self):
        path = ROOT/'data/research/canopy-verified/comparison.json'
        rows = strata_from_published(path)
        self.assertEqual([row['gid'] for row in rows], [266, 5630, 5634, 5642, 5643])
        self.assertAlmostEqual(sum(row['length_m'] for row in rows), 1295.5, delta=0.05)
        totals = stratum_totals(rows)
        self.assertAlmostEqual(sum(totals.values()), 1295.5, delta=0.05)
        self.assertAlmostEqual(totals['mapped_overlap'], 181.0, delta=0.5)
        for row in rows:
            self.assertGreaterEqual(row['proximity_only_m'], 0)
            self.assertGreaterEqual(row['non_overlap_m'], 0)
            self.assertAlmostEqual(row['overlap_m'] + row['proximity_only_m'] + row['non_overlap_m'],
                                   row['length_m'], delta=1e-6)

    def test_plan_allocates_the_whole_sample(self):
        result = plan(ROOT/'data/research/canopy-verified/comparison.json',
                      half_width=0.075, prevalence=0.25, design_effect=3, step_m=2.0)
        self.assertEqual(result['segments'], 5)
        self.assertAlmostEqual(result['frame_m'], 1295.5, delta=0.05)
        self.assertEqual(result['candidates'], 644)
        self.assertEqual(result['assessed_m'], 1288.0)
        self.assertAlmostEqual(result['excluded_remainder_m'], 7.45, delta=0.05)
        self.assertEqual(result['precision']['clustered_points'], 385)
        self.assertEqual(sum(values['points'] for values in result['strata'].values()), 385)
        for name, values in result['strata'].items():
            with self.subTest(stratum=name):
                self.assertGreater(values['points'], 0)
                self.assertGreater(values['systematic_step_m'], 0)
                self.assertAlmostEqual(values['share'] * result['frame_m'], values['length_m'], places=6)
        # A strata file whose buffers go backwards must be rejected rather than planned from.
        with tempfile.TemporaryDirectory() as temp:
            broken = json.loads(pathlib.Path(ROOT/'data/research/canopy-verified/comparison.json').read_text())
            for row in broken['results']:
                if row['vegetation'] == 'trees' and row['gid'] == 266 and row['buffer_m'] == 5:
                    row['overlap_m'] = 0.0
            bad = pathlib.Path(temp)/'comparison.json'
            bad.write_text(json.dumps(broken))
            with self.assertRaisesRegex(ValueError, 'monotone'):
                strata_from_published(bad)


class ValidationFrameTests(unittest.TestCase):
    """The candidate frame is geometry only: synthetic routes, no upstream download."""

    def setUp(self):
        # A 30 m straight route along y = 0 with a tree square covering x in [2, 5]. A point at
        # chainage c has distance 0 inside, 2 - c on the near side, c - 5 on the far side.
        self.route = LineString([(0, 0), (30, 0)])
        self.cover = box(2, -1, 5, 1)
        self.near = self.cover.buffer(5)

    @staticmethod
    def expected_stratum(x):
        if 2 <= x <= 5:
            return 'mapped_overlap'
        if abs(x - 3.5) <= 6.5:                 # within 5 m of the box, either side
            return 'proximity_only'
        return 'mapped_non_overlap'

    def test_strata_follow_the_mapped_cover(self):
        step = 1.0
        points, counts = classify_points(self.route, self.cover, self.near, step, 7)
        self.assertEqual([p['chainage_m'] for p in points], [i + 0.5 for i in range(30)])
        expected = [self.expected_stratum(point['chainage_m']) for point in points]
        self.assertEqual([p['stratum'] for p in points], expected)
        self.assertEqual(counts['candidates'], 30)
        for name in ('mapped_overlap', 'proximity_only', 'mapped_non_overlap'):
            self.assertEqual(counts[name], expected.count(name))
        # 3 m of overlap, a 5 m proximity band on each side (7 whole-metre candidates), rest absent.
        self.assertEqual((counts['mapped_overlap'], counts['proximity_only'], counts['mapped_non_overlap']),
                         (3, 7, 20))
        self.assertTrue(all(point['gid'] == 7 for point in points))
        self.assertEqual(points[2]['distance_to_cover_m'], 0.0)
        self.assertAlmostEqual(points[0]['distance_to_cover_m'], 1.5, places=6)
        self.assertAlmostEqual(points[-1]['distance_to_cover_m'], 24.5, places=6)

    def test_grid_represents_the_step_and_excludes_the_remainder(self):
        points, counts = classify_points(self.route, self.cover, self.near, 2.0, 7)
        self.assertEqual([p['chainage_m'] for p in points], [1.0, 3.0, 5.0, 7.0, 9.0,
                                                             11.0, 13.0, 15.0, 17.0, 19.0,
                                                             21.0, 23.0, 25.0, 27.0, 29.0])
        self.assertEqual(counts['candidates'], 15)
        self.assertAlmostEqual(self.route.length - counts['candidates']*2.0, 0.0)
        short = LineString([(0, 0), (3.5, 0)])
        _, short_counts = classify_points(short, self.cover, self.near, 2.0, 7)
        self.assertEqual(short_counts['candidates'], 1)          # 3.5 m route, 2 m step
        with self.assertRaises(ValueError):
            classify_points(LineString([(0, 0), (1.0, 0)]), self.cover, self.near, 2.0, 7)

    def test_boundary_is_inclusive_and_output_is_deterministic(self):
        # A point exactly 5 m from the cover edge sits on the polygonal buffer boundary the
        # published proximity numbers use, and must count as proximity rather than absence.
        route = LineString([(9.0, 0), (11.0, 0)])
        points, _ = classify_points(route, self.cover, self.near, 2.0, 11)
        self.assertEqual([p['chainage_m'] for p in points], [1.0])
        self.assertAlmostEqual(points[0]['distance_to_cover_m'], 5.0, places=6)
        self.assertEqual(points[0]['stratum'], 'proximity_only')
        first = classify_points(self.route, self.cover, self.near, 1.0, 7)
        again = classify_points(LineString([(0, 0), (30, 0)]), box(2, -1, 5, 1),
                                box(2, -1, 5, 1).buffer(5), 1.0, 7)
        self.assertEqual(first, again)
        with self.assertRaises(ValueError):
            classify_points(self.route, self.cover, self.near, 0.0, 7)



class SelectionTests(unittest.TestCase):
    """The draw is deterministic given a seed and balanced across streets by construction."""

    def synthetic_frame(self, sizes=((266, 40), (5630, 10), (5634, 12), (5642, 20), (5643, 8))):
        points = []
        for gid, count in sizes:
            for index in range(count):
                stratum = ('mapped_overlap' if index % 5 == 0 else
                           'proximity_only' if index % 3 == 0 else 'mapped_non_overlap')
                points.append(dict(gid=gid, chainage_m=float(2*index + 1), x=float(index), y=float(gid % 100),
                                   stratum=stratum, distance_to_cover_m=float(index % 7)))
        return dict(schema_version=1, candidate_count=len(points), step_m=2.0, points=points,
                    manifest_sha256='fixture', frame_code_sha256='fixture')

    def test_cell_allocation_is_exact_and_covers_every_cell(self):
        cells = {('a', 1): 100, ('a', 2): 50, ('b', 1): 1}
        allocation = allocate_cells(cells, 30)
        self.assertEqual(sum(allocation.values()), 30)
        self.assertTrue(all(value >= 1 for value in allocation.values()))
        self.assertGreater(allocation[('a', 1)], allocation[('a', 2)])
        self.assertGreater(allocation[('a', 2)], allocation[('b', 1)])
        with self.assertRaises(ValueError):
            allocate_cells(cells, 2)

    def test_systematic_positions_are_distinct_and_spread(self):
        positions = systematic_indices(100, 10, random.Random(7))
        self.assertEqual(len(positions), 10)
        self.assertEqual(len(set(positions)), 10)
        self.assertEqual(positions, sorted(positions))
        self.assertTrue(all(0 <= position < 100 for position in positions))
        self.assertTrue(all(b - a >= 8 for a, b in zip(positions, positions[1:])))
        self.assertEqual(systematic_indices(5, 5, random.Random(1)), [0, 1, 2, 3, 4])
        for bad in ((5, 6), (5, 0)):
            with self.assertRaises(ValueError):
                systematic_indices(bad[0], bad[1], random.Random(1))

    def test_selection_is_reproducible_and_complete(self):
        frame = self.synthetic_frame()
        first = select(frame, 60, 20261017)
        self.assertEqual(first, select(frame, 60, 20261017))
        self.assertNotEqual(first, select(frame, 60, 999))
        self.assertEqual(len(first), 60)
        self.assertEqual(len({(row['gid'], row['chainage_m']) for row in first}), 60)
        self.assertEqual({row['gid'] for row in first}, {266, 5630, 5634, 5642, 5643})
        for row in first:
            self.assertEqual(row['cell'], f"{row['stratum']}:{row['gid']}")
            self.assertAlmostEqual(row['inclusion_probability'],
                                   row['cell_allocated']/row['cell_candidates'], places=8)
            self.assertLessEqual(row['cell_allocated'], row['cell_candidates'])
        self.assertEqual(sorted(row['gid'] for row in first),
                         [row['gid'] for row in first])   # ordered by segment then chainage
        with self.assertRaises(ValueError):
            select(frame, 60, 'seed')

    def test_committed_frame_accepts_the_planned_sample(self):
        frame_path = ROOT/'data/research/canopy-validation-frame.json'
        frame = json.loads(frame_path.read_text())
        selected = select(frame, 385, 20261017)
        self.assertEqual(len(selected), 385)
        self.assertEqual({row['gid'] for row in selected}, {266, 5630, 5634, 5642, 5643})
        counts = {name: 0 for name in ('mapped_overlap', 'proximity_only', 'mapped_non_overlap')}
        frame_counts = dict(counts)
        for row in selected:
            counts[row['stratum']] += 1
        for point in frame['points']:
            frame_counts[point['stratum']] += 1
        for name, count in counts.items():
            # Proportional allocation keeps each stratum's sample share within a point or two.
            self.assertLess(abs(count/385 - frame_counts[name]/frame['candidate_count']), 0.01)
        report = build(frame_path, 385, 20261017)
        self.assertEqual(report['selected'], 385)
        # Inverse inclusion probability is the estimator weight, and it expands to the frame.
        self.assertAlmostEqual(sum(row['inverse_inclusion_probability'] for row in report['points']),
                               frame['candidate_count'], delta=0.001)
        for row in report['points']:
            self.assertAlmostEqual(row['inverse_inclusion_probability'],
                                   1/row['inclusion_probability'], places=6)
        # The stratum ratio is a diagnostic only, because cell probabilities differ.
        self.assertTrue(all(not entry['design_weight_valid'] for entry in report['strata'].values()))
        self.assertTrue(all('design_weight_note' in entry for entry in report['strata'].values()))
        self.assertEqual(sum(report['points_by_segment'].values()), 385)
        self.assertTrue(all(abs(entry['design_weight'] - 1) < 0.02 for entry in report['strata'].values()))


class DesignEffectTests(unittest.TestCase):
    """The design effect is measured on the frame, so the machinery must be able to fail."""

    def frame_from_series(self, series, step=2.0):
        points = []
        for gid, values in series.items():
            for index, value in enumerate(values):
                points.append(dict(gid=gid, chainage_m=float(index*step+step/2), x=0.0, y=0.0,
                                   stratum='mapped_overlap' if value else 'mapped_non_overlap',
                                   distance_to_cover_m=0.0))
        return dict(candidate_count=len(points), step_m=step, points=points,
                    assessed_length_m=len(points)*step, manifest_sha256='fixture',
                    frame_code_sha256='fixture')

    def test_a_periodic_pattern_is_sampled_exactly(self):
        # Every fourth frame is canopy and the step advances the phase by two, so every
        # systematic draw intercepts the pattern identically: zero variance, and a design
        # effect of exactly zero. Worth pinning because it shows how strong even spreading is.
        series = {1: [1 if index % 4 == 0 else 0 for index in range(600)]}
        report = measure(self.frame_from_series(series), 120, 1500, 7)
        self.assertEqual(report['variance'], 0.0)
        self.assertEqual(report['design_effect_finite'], 0.0)

    def test_few_distinct_realisations_are_reported(self):
        # A step of exactly five frame steps repeats the same five samples, so the
        # across-start variance says little. The report must measure that rather than infer
        # it from the step, and must only flag segments that also vary.
        import random as random_module
        rng = random_module.Random(20261018)
        series = {1: [1 if rng.random() < 0.25 else 0 for _ in range(600)]}
        report = measure(self.frame_from_series(series), 120, 1200, 7)
        entry = report['distinct_realisations'][1]
        self.assertEqual(entry['step'], 5.0)
        self.assertLessEqual(entry['distinct'], 5)
        self.assertTrue(report['few_distinct_realisations'])
        # A segment with no variation contributes no variance, so it never triggers the flag
        # however degenerate its step is. `measure` refuses a frame with no variation at all,
        # which is why the diagnostic is exercised directly here.
        flat = distinct_realisations({1: [0]*600}, 120, 7, trials=200)
        self.assertFalse(flat[1]['varies'])
        self.assertLessEqual(flat[1]['distinct'], 5)

    def test_aliasing_inflates_the_design_effect(self):
        # Strict alternation with a step of exactly two frames: every draw lands on the same
        # phase, so the estimate is either all-canopy or none. This is the case the frame is
        # NOT in, which is why the measured effect can sit below 1 without the check being
        # vacuous.
        series = {1: [index % 2 for index in range(600)]}
        frame = self.frame_from_series(series)
        report = measure(frame, 100, 2000, 11)   # step = 1200/100 = 12 frames: an even phase 2
        self.assertGreater(report['design_effect_finite'], 5.0,
                           f"aliased sampling should inflate; got {report['design_effect_finite']}")
        estimates = {report['estimate_range'][0], report['estimate_range'][1]}
        self.assertTrue(any(value in (0.0, 1.0) for value in estimates),
                        f'aliased draws should collapse to a constant; got {estimates}')

    def test_allocation_covers_every_segment(self):
        series = {1: [0]*300, 2: [0]*100, 3: [0]*20}
        allocation = allocate(series, 60)
        self.assertEqual(sum(allocation.values()), 60)
        self.assertTrue(all(count >= 1 for count in allocation.values()))
        self.assertGreater(allocation[1], allocation[2])
        with self.assertRaises(ValueError):
            allocate(series, 500)

    def test_within_segment_autocorrelation(self):
        # Alternating within each segment gives rho_1 near -1 whatever the segment means are;
        # pooling first would give a different, mean-driven answer.
        series = {1: [index % 2 for index in range(60)], 2: [1 - index % 2 for index in range(60)]}
        rhos = lag_autocorrelation(series, 4)
        self.assertAlmostEqual(rhos[0], -1.0, delta=0.05)
        with self.assertRaises(ValueError):
            lag_autocorrelation({1: [0]*50}, 4)   # a constant segment carries no lag information

    def test_measurement_is_reproducible_and_unbiased(self):
        import random as random_module
        rng = random_module.Random(11)
        series = {1: [1 if rng.random() < 0.25 else 0 for _ in range(600)]}
        frame = self.frame_from_series(series)
        report = measure(frame, 120, 1500, 3)
        self.assertEqual(report, measure(frame, 120, 1500, 3))
        self.assertAlmostEqual(report['mean_estimate'], report['frame_prevalence'], delta=0.01)
        self.assertLess(report['variance_mc_standard_error'], report['variance']/10)
        self.assertGreater(report['canopy_runs']['count'], 50)
        self.assertGreater(report['canopy_runs']['mean_length_m'], 1.0)
        self.assertLess(report['canopy_runs']['mean_length_m'], 4.0)

    def test_committed_frame_reports_the_plan_reading(self):
        frame = json.loads((ROOT/'data/research/canopy-validation-frame.json').read_text())
        report = measure(frame, 385, 1500, 20261018)
        self.assertEqual(report['candidate_count'], 644)
        self.assertAlmostEqual(report['sampling_fraction'], 385/644, places=6)
        self.assertAlmostEqual(report['mean_estimate'], report['frame_prevalence'], delta=0.01)
        # The design spreads evenly, so on a finite frame it beats random selection at the same n.
        self.assertLess(report['design_effect_finite'], 1.0)
        # And the patch-length bound lands in the same order of magnitude as the plan's 3.
        self.assertGreater(report['inflation_for_random_placement'], 2.0)
        self.assertLess(report['inflation_for_random_placement'], 6.0)
        # Two segments have a step of exactly 5/3 and only five distinct realisations, but
        # neither contains any canopy, so the spread is still driven by segments 266 and 5642.
        realisations = report['distinct_realisations']
        self.assertEqual(realisations[5630]['distinct'], 5)
        self.assertEqual(realisations[5643]['distinct'], 5)
        self.assertFalse(realisations[5630]['varies'])
        self.assertGreaterEqual(realisations[266]['distinct'], 50)
        self.assertFalse(report['few_distinct_realisations'])
        # Across starting points the estimate moves by roughly a percentage point, which is
        # the model-free statement the plan can lean on.
        low, high = report['estimate_quantiles'][2.5], report['estimate_quantiles'][97.5]
        self.assertLess(high-low, 0.03)


class PlanCostTableTests(unittest.TestCase):
    """The plan's cost table is the decision input, so its numbers are recomputed."""

    def test_published_cost_table_matches_the_code(self):
        import re as regex
        text = (ROOT/'docs/canopy-accuracy-sampling-plan.md').read_text()
        rows = regex.findall(r'^\| (0\.\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$', text, regex.M)
        self.assertEqual(len(rows), 3, f'expected three published rows, parsed {len(rows)}')
        columns = ((0.05, 1.0), (0.075, 1.0), (0.10, 1.0), (0.075, 3.0))
        checked = 0
        for prevalence, *published in rows:
            for (half_width, design_effect), quoted in zip(columns, published):
                expected = required_sample_size(half_width, float(prevalence), design_effect)
                self.assertEqual(int(quoted), expected,
                                 f'plan quotes {quoted} for prevalence {prevalence}, '
                                 f'{half_width*100:g} pp, design effect {design_effect:g}; '
                                 f'code gives {expected}')
                checked += 1
        self.assertEqual(checked, 12, f'expected twelve published cells, checked {checked}')

    def test_published_wilson_half_widths_match_the_code(self):
        text = (ROOT/'docs/canopy-accuracy-sampling-plan.md').read_text()
        import re as regex
        quoted = regex.search(r'at n = (\d+) and p = ([\d.]+) the Wilson\s+half-width is ([\d.]+) pp', text)
        self.assertIsNotNone(quoted, 'the Wilson sentence no longer parses')
        n, prevalence, stated = quoted.groups()
        low, high = wilson_interval(int(round(float(prevalence)*int(n))), int(n))
        half_width_pp = (high-low)/2*100
        self.assertAlmostEqual(half_width_pp, float(stated), delta=0.01,
                               msg=f'plan states {stated} pp for n={n}; code gives {half_width_pp:.3f}')

if __name__ == '__main__':
    unittest.main()
