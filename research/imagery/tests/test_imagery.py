import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image

import consistency
from consistency import (BAND_AGREEMENT_M, DEGRADED_SHIFT_M, analyse, band_sets, bands_for,
                         code_identity, lowpass)
from registration import (_refine, estimate_shift, gradient_energy, interpret, luminance,
                          shifted, whitened_spectrum, window)
from support import digest, encoded
from wms import LAYERS, pinned_array, plan, record_fields, verify

ROOT = Path(__file__).resolve().parents[3]
FROZEN = ROOT/'data/research/imagery-inputs'


def texture(size=120, seed=11, cutoff=12):
    """Deterministic band-limited field: broadband enough to localise a shift."""
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal((size, size))
    spectrum = np.fft.fft2(noise)
    v = np.fft.fftfreq(size)[:, None]
    u = np.fft.fftfreq(size)[None, :]
    keep = np.hypot(v, u) <= cutoff/size
    field = np.real(np.fft.ifft2(spectrum*keep))
    return 128.0 + 100.0*(field-field.mean())/(field.std()+1e-12)


def rgb(array):
    return np.repeat(np.clip(array, 0, 255).astype(np.uint8)[:, :, None], 3, axis=2)


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.field = texture()

    def assertClose(self, value, expected, tolerance):
        self.assertAlmostEqual(value, expected, delta=tolerance)

    def test_known_answer_shifts(self):
        for row, column in [(0, 0), (1, 0), (0, 1), (-3, 0), (2, -2), (0.4, -0.6), (5, 0)]:
            with self.subTest(shift=(row, column)):
                result = estimate_shift(self.field, shifted(self.field, row, column), max_shift=8)
                self.assertClose(result['row_shift'], row, 0.25)
                self.assertClose(result['column_shift'], column, 0.25)
                self.assertAlmostEqual(result['magnitude'], float(np.hypot(row, column)), delta=0.25)

    def test_fractional_shift_accuracy_is_bounded(self):
        # A parabola on whole-pixel samples is biased by up to one pixel; the exact
        # band-limited refinement must stay well inside a quarter pixel.
        errors = []
        for step in np.arange(-2, 2.001, 0.125):
            reference = texture(seed=29, cutoff=45)
            result = estimate_shift(reference, shifted(reference, float(step), float(-step)), max_shift=8)
            errors.append(float(np.hypot(result['row_shift']-step, result['column_shift']+step)))
        self.assertLess(max(errors), 0.25)

    def test_refined_surface_is_real_and_local(self):
        spectrum = whitened_spectrum(np.fft.fft2(self.field))
        for row, column in [(3.0, 0.0), (3.5, -0.25), (0.0, 1.75)]:
            with self.subTest(offset=(row, column)):
                refined_row, refined_column, value = _refine(spectrum, row, column)
                self.assertLessEqual(abs(refined_row-row), 1.6)
                self.assertLessEqual(abs(refined_column-column), 1.6)
                self.assertTrue(np.isfinite(value))

    def test_interpret_maps_to_compass_for_north_up_raster(self):
        # Content that appears 3 pixels lower and 2 to the right is south-east of the reference.
        result = estimate_shift(self.field, shifted(self.field, 3, 2), max_shift=8)
        answer = interpret(result, 0.1)
        self.assertClose(answer['east_m'], 0.2, 0.005)
        self.assertClose(answer['north_m'], -0.3, 0.005)
        self.assertClose(answer['magnitude_m'], float(np.hypot(0.2, 0.3)), 0.005)

    def test_identity_and_gain_changes(self):
        zero = estimate_shift(self.field, self.field, max_shift=5)
        self.assertClose(zero['row_shift'], 0.0, 1e-9)
        self.assertClose(zero['column_shift'], 0.0, 1e-9)
        for modification in (2.5*self.field+30, 30-0.4*self.field):
            result = estimate_shift(self.field, modification, max_shift=5)
            self.assertClose(result['column_shift'], 0.0, 0.02)
        # A shifted survey with a large brightness and colour offset must still register.
        moved = shifted(self.field, 0, 2.5)
        coloured = np.stack([np.clip(0.6*moved+10, 0, 255), np.clip(1.4*moved+5, 0, 255),
                             np.clip(0.3*moved, 0, 255)], axis=2).astype(np.uint8)
        result = interpret(estimate_shift(luminance(rgb(self.field)), luminance(coloured), max_shift=8), 0.05)
        self.assertClose(result['east_m'], 0.125, 0.02)

    def test_noise_robustness(self):
        rng = np.random.default_rng(3)
        noisy = shifted(self.field, 1.5, -2.25) + rng.normal(0, 12, self.field.shape)
        result = estimate_shift(self.field, noisy, max_shift=8)
        self.assertClose(result['row_shift'], 1.5, 0.25)
        self.assertClose(result['column_shift'], -2.25, 0.25)

    def test_rejects_unusable_inputs(self):
        bad = [(self.field, self.field[:10], 5),
               (self.field, np.full_like(self.field, 128.0), 5),
               (self.field, self.field + np.nan, 5)]
        for reference, moving, radius in bad:
            with self.subTest(radius=radius), self.assertRaises(ValueError):
                estimate_shift(reference, moving, max_shift=radius)
        # A true shift far outside the searched radius must be reported as unconvincing.
        outside = estimate_shift(self.field, shifted(self.field, 40, 0), max_shift=10)
        self.assertLess(outside['peak_ratio'], 2.0)
        inside = estimate_shift(self.field, shifted(self.field, 2, 0), max_shift=10)
        self.assertGreater(inside['peak_ratio'], 10.0)
        with self.assertRaisesRegex(ValueError, 'max_shift'):
            estimate_shift(self.field, self.field, max_shift=0)
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            # A two-row periodic field matches at several offsets equally well.
            periodic = np.tile(np.arange(6.0)[:, None].repeat(20, axis=1), (8, 1))
            estimate_shift(periodic, np.roll(periodic, 3, axis=0), max_shift=4, min_rival_ratio=1.05)

    def test_gradient_and_window_guards(self):
        with self.assertRaises(ValueError):
            luminance(np.zeros((4, 4)))
        with self.assertRaises(ValueError):
            gradient_energy(np.zeros((4, 4)))
        with self.assertRaises(ValueError):
            window((4, 4))
        self.assertEqual(gradient_energy(np.zeros((9, 9))).shape, (7, 7))
        with self.assertRaisesRegex(ValueError, 'too small'):
            estimate_shift(np.zeros((10, 10)), np.zeros((10, 10)), max_shift=1)


class BandTests(unittest.TestCase):
    def test_resolving_bands_carry_their_own_lobe_width(self):
        bands = bands_for(0.1, 120)
        self.assertEqual([b['band'] for b in bands],
                         ['full', 'above_1m', 'above_2m', 'above_5m', 'above_20m'])
        self.assertEqual([b['lobe_width_m'] for b in bands], [0.05, 0.5, 1.0, 2.5, 10.0])
        # A lobe wider than the tolerance cannot resolve the tolerance.
        self.assertEqual([b['can_resolve_tolerance'] for b in bands], [True, True, False, False, False])
        self.assertTrue(all(abs(b['wavelength_m']/2 - b['lobe_width_m']) < 1e-9 for b in bands[1:]))
        self.assertEqual(list(band_sets(bands)),
                         ['2_bands_through_1m', '3_bands_through_2m', '4_bands_through_5m',
                          '5_bands_through_20m'])
        for index, name in enumerate(band_sets(bands), start=2):
            self.assertEqual([band['band'] for band in band_sets(bands)[name]],
                             [band['band'] for band in bands[:index]])

    def test_bands_shrink_with_the_window(self):
        self.assertEqual([b['band'] for b in bands_for(0.25, 60)],
                         ['full', 'above_1m', 'above_2m', 'above_5m'])
        self.assertEqual([b['can_resolve_tolerance'] for b in bands_for(0.25, 60)],
                         [True, True, False, False])
        # Coarse pixels or a small window leave too little resolving power to judge.
        for pixel_m, window_m, message in [(1.0, 120, 'fewer than two'), (5.0, 30, 'too small')]:
            with self.subTest(pixel_m=pixel_m), self.assertRaisesRegex(ValueError, message):
                bands_for(pixel_m, window_m)

    def test_lowpass_keeps_only_coarse_structure(self):
        image = texture(120, cutoff=45)
        coarse = lowpass(image, 0.02)
        self.assertAlmostEqual(float(coarse.mean()), float(image.mean()), delta=1e-6)
        self.assertLess(float(gradient_energy(coarse).std()), float(gradient_energy(image).std()))


class Fixture:
    """Minimal pinned package built the same way the fetch step builds one."""

    def __init__(self, root, east_m=1.5, north_m=0.0, window_m=120, pixel_m=0.2, band_split=None):
        self.root, self.window_m, self.pixel_m = Path(root), window_m, pixel_m
        size = int(window_m/pixel_m)
        reference = texture(size, seed=5, cutoff=size*0.4)
        if band_split is None:
            moving = shifted(reference, -north_m/pixel_m, east_m/pixel_m)
        else:
            # Coarse and fine structure displaced by different amounts, split between
            # two bands that both resolve the tolerance.
            (coarse_east, coarse_north), (fine_east, fine_north) = band_split['offsets']
            coarse = lowpass(reference, band_split['cutoff'])
            fine = reference - coarse
            moving = (shifted(coarse, -coarse_north/pixel_m, coarse_east/pixel_m)
                      + shifted(fine, -fine_north/pixel_m, fine_east/pixel_m))
        bounds = (0.0, 0.0, float(window_m), float(window_m))
        window_row = dict(window_id='gid1-at50', gid=1, fraction=0.5, chainage_m=50.0,
                          segment_length_m=100.0, bounds=bounds)
        self.plan = dict(schema_version=1, pixel_m=pixel_m, window_m=window_m, width=size, height=size,
                         srs='EPSG:31370', service='https://example.invalid/ows',
                         layers=dict(LAYERS), records={'example': 'record-id'},
                         chainage_fractions=[0.5], windows=[window_row],
                         frozen_inputs={'cycling-frame.geojson': 'frozen', 'frame-request.json': 'frozen'},
                         published_comparison_sha256='published')
        (self.root/'images').mkdir(parents=True, exist_ok=True)
        (self.root/'records').mkdir(parents=True, exist_ok=True)
        files, requests = [], []
        for name, layer, array in sorted([('east_west_2021_09_22_or_25', LAYERS['east_west_2021_09_22_or_25'], reference),
                                          ('north_south_2021_10_09', LAYERS['north_south_2021_10_09'], moving)]):
            file_name = f'{window_row["window_id"]}-{layer}.jpg'
            path = self.root/'images'/file_name
            Image.fromarray(rgb(array)).save(path, format='JPEG', quality=88)
            files.append(dict(location='image', name=f'images/{file_name}', bytes=path.stat().st_size,
                              sha256=digest(path)))
            requests.append(dict(window_id=window_row['window_id'], layer=layer, product=name,
                                 file=f'images/{file_name}', url='https://example.invalid/ows?request=GetMap',
                                 bbox=list(bounds), width=size, height=size, srs='EPSG:31370',
                                 format='image/jpeg', retrieved_at_utc='2000-01-01T00:00:00+00:00',
                                 response_headers={}, bytes=path.stat().st_size, sha256=digest(path)))
        record = (b'<record><beginPosition>2021-09-17T00:00:00</beginPosition>'
                  b'<endPosition>2021-10-09T00:00:00</endPosition><statement>two flights</statement></record>')
        (self.root/'records'/'example.xml').write_bytes(record)
        files.append(dict(location='record', name='records/example.xml', bytes=len(record),
                          sha256=digest(self.root/'records'/'example.xml')))
        from support import digest_bytes
        self.manifest = dict(schema_version=1, plan_sha256=digest(self.root/'plan.json')
                             if (self.root/'plan.json').exists() else 'plan',
                             plan=self.plan,
                             source_records={'example': dict(record_url='https://example.invalid/record',
                                                             record_sha256=digest_bytes(record),
                                                             **record_fields(record))},
                             requests=requests, files=files, retrieved_at_utc='2000-01-01T00:00:00+00:00')
        self.plan_path = self.root/'plan.json'
        self.plan_path.write_bytes(encoded(self.plan))
        self.manifest['plan_sha256'] = digest(self.plan_path)
        self.manifest_path = self.root/'manifest.json'
        self.write()

    def write(self):
        self.manifest_path.write_bytes(encoded(self.manifest))

    def rewrite(self, mutate):
        mutate(self.manifest)
        self.write()


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.fixture = Fixture(self.root)

    def test_verify_accepts_pinned_package(self):
        manifest = verify(self.fixture.manifest_path, self.root, self.fixture.plan_path)
        self.assertEqual(len(manifest['files']), 3)
        self.assertEqual(pinned_array(manifest, self.root, 'gid1-at50',
                                      LAYERS['east_west_2021_09_22_or_25']).shape, (600, 600, 3))

    def test_embedded_plan_must_equal_the_frozen_plan(self):
        # Editing the copy the analysis actually reads must fail, even if the plan
        # file and its digest are left untouched.
        def edit(manifest):
            manifest['plan']['pixel_m'] = 0.05
            manifest['plan']['window_m'] = 60.0
            for entry in manifest['plan']['windows']:
                entry['bounds'] = [0.0, 0.0, 60.0, 60.0]
            for request in manifest['requests']:
                request['bbox'] = [0.0, 0.0, 60.0, 60.0]
        self.fixture.rewrite(edit)
        with self.assertRaisesRegex(ValueError, 'Manifest plan differs'):
            verify(self.fixture.manifest_path, self.root, self.fixture.plan_path)

    def test_plan_must_match_the_declared_windows(self):
        self.fixture.plan['windows'][0]['bounds'] = [0.0, 0.0, 10.0, 10.0]
        self.fixture.plan_path.write_bytes(encoded(self.fixture.plan))
        with self.assertRaisesRegex(ValueError, 'Frozen plan'):
            verify(self.fixture.manifest_path, self.root, self.fixture.plan_path)

    def test_verify_rejects_tampering_gaps_and_record_edits(self):
        def tamper_image(manifest):
            path = self.root/manifest['files'][0]['name']
            path.write_bytes(path.read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError, 'SHA-256|size'):
            self.fixture.rewrite(tamper_image)
            verify(self.fixture.manifest_path, self.root, self.fixture.plan_path)
        self.fixture = Fixture(self.root/'second')
        with self.assertRaisesRegex(ValueError, 'exactly once'):
            self.fixture.rewrite(lambda manifest: manifest['requests'].pop())
            verify(self.fixture.manifest_path, self.root/'second', self.fixture.plan_path)
        self.fixture = Fixture(self.root/'third')
        with self.assertRaisesRegex(ValueError, 'bbox'):
            self.fixture.rewrite(lambda manifest: manifest['requests'][0].update(bbox=[0, 0, 1, 1]))
            verify(self.fixture.manifest_path, self.root/'third', self.fixture.plan_path)
        self.fixture = Fixture(self.root/'fourth')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.fixture.rewrite(lambda manifest: manifest['files'].append(manifest['files'][0]))
            verify(self.fixture.manifest_path, self.root/'fourth', self.fixture.plan_path)
        # Editing the stored record must fail on its digest first.
        self.fixture = Fixture(self.root/'fifth')
        record = self.root/'fifth'/'records'/'example.xml'
        record.write_bytes(record.read_bytes().replace(b'2021-10-09', b'2021-11-09'))
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            verify(self.fixture.manifest_path, self.root/'fifth', self.fixture.plan_path)
        # A manifest edited to accept tampered bytes must still fail the field check,
        # so the published dates in the report are bound to the stored file.
        from support import digest_bytes
        tampered = record.read_bytes()
        edited = json.loads(self.fixture.manifest_path.read_text())
        entry = next(e for e in edited['files'] if e['location'] == 'record')
        entry['bytes'], entry['sha256'] = len(tampered), digest_bytes(tampered)
        edited['source_records']['example']['record_sha256'] = digest_bytes(tampered)
        self.fixture.manifest_path.write_bytes(encoded(edited))
        with self.assertRaisesRegex(ValueError, 'Record fields differ'):
            verify(self.fixture.manifest_path, self.root/'fifth', self.fixture.plan_path)

    def test_missing_pinned_input_is_reported(self):
        (self.root/'images'/'gid1-at50-Ortho2021Ns.jpg').unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            verify(self.fixture.manifest_path, self.root, self.fixture.plan_path)


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def report(self, east_m=1.5, north_m=0.0, band_split=None, name=None):
        fixture = Fixture(self.root/(name or f'{east_m}_{north_m}'), east_m=east_m, north_m=north_m,
                          band_split=band_split)
        report = analyse(fixture.manifest_path, self.root/(name or f'{east_m}_{north_m}'),
                         fixture.plan_path)
        return fixture, report

    def test_recovers_known_offset_in_resolving_bands(self):
        for east_m, north_m in [(1.5, 0.0), (0.0, -2.0), (2.0, 2.0), (0.3, 0.0)]:
            with self.subTest(displacement=(east_m, north_m)):
                fixture, report = self.report(east_m, north_m)
                row = report['results'][0]
                self.assertAlmostEqual(row['offset_m']['full_band_east_m'], east_m, delta=0.2)
                self.assertAlmostEqual(row['offset_m']['full_band_north_m'], north_m, delta=0.2)
                self.assertEqual(row['verdict'], 'consistent')
                for band in row['bands']:
                    if band['can_resolve_tolerance']:
                        self.assertAlmostEqual(band['east_m'], east_m, delta=0.4)
                        self.assertAlmostEqual(band['north_m'], north_m, delta=0.4)
                self.assertLessEqual(row['known_answer_max_error_px'], 0.25)
                self.assertLessEqual(row['resampled_max_error_px'], 0.25)
                self.assertLessEqual(report['degraded_max_error_resolving_band_m'], BAND_AGREEMENT_M)

    def test_wide_bands_are_reported_but_never_decide(self):
        fixture, report = self.report()
        row = report['results'][0]
        eligible = [band for band in row['bands'] if band['can_resolve_tolerance']]
        wide = [band for band in row['bands'] if not band['can_resolve_tolerance']]
        self.assertGreaterEqual(len(eligible), 2)
        self.assertTrue(all(band['lobe_width_m'] <= BAND_AGREEMENT_M for band in eligible))
        self.assertTrue(wide, 'fixture should contain at least one unresolvable band')
        for band in wide:
            self.assertGreater(band['lobe_width_m'], BAND_AGREEMENT_M)
        self.assertEqual(report['summary']['consistent_windows'], 1)
        # Every nested cut is reported, so the verdict never rests on one constant.
        sensitivity = report['summary']['band_set_sensitivity']
        self.assertEqual(sorted(sensitivity), ['2_bands_through_1m', '3_bands_through_2m',
                                               '4_bands_through_5m', '5_bands_through_20m'])
        self.assertEqual(sensitivity['2_bands_through_1m']['consistent_windows'], 1)
        # Nested sets can only widen the spread, never narrow it.
        self.assertGreaterEqual(sensitivity['5_bands_through_20m']['max_spread_m'],
                                sensitivity['2_bands_through_1m']['max_spread_m'] - 1e-9)

    def test_band_dependent_displacement_is_called_inconsistent(self):
        fixture, report = self.report(band_split=dict(offsets=((3.0, 0.0), (0.0, 0.0)), cutoff=0.2),
                                      name='split')
        row = report['results'][0]
        self.assertEqual(row['verdict'], 'inconsistent')
        self.assertGreater(row['resolving_band_spread_m'], BAND_AGREEMENT_M)
        self.assertEqual(report['summary']['inconsistent_windows'], 1)

    def test_degraded_guard_fires_when_a_resolving_band_is_biased(self):
        # Noise and JPEG alone do not move the resolving bands (that is the point of
        # the control), so drive the guard with a deliberately biased band.
        fixture = Fixture(self.root/'biased')
        original = consistency.band_measurement

        def biased(reference, moving, band, pixel_m):
            values = original(reference, moving, band, pixel_m)
            if band['can_resolve_tolerance'] and band['band'] == 'full':
                values['east_m'] += 2.0
            return values

        with patch('consistency.band_measurement', side_effect=biased):
            with self.assertRaisesRegex(ValueError, 'degraded control'):
                analyse(fixture.manifest_path, self.root/'biased', fixture.plan_path)

    def test_degradation_control_covers_every_resolving_band(self):
        fixture, report = self.report()
        control = report['results'][0]['degraded_control']
        self.assertEqual(control['asked_east_m'], DEGRADED_SHIFT_M[0])
        self.assertEqual([row['band'] for row in control['bands']],
                         [band['band'] for band in report['results'][0]['bands']])
        self.assertTrue(any(row['can_resolve_tolerance'] for row in control['bands']))
        self.assertLessEqual(control['max_error_resolving_m'], BAND_AGREEMENT_M)

    def test_report_is_deterministic_and_labelled(self):
        fixture, report = self.report(name='stable')
        again = analyse(fixture.manifest_path, self.root/'stable', fixture.plan_path)
        self.assertEqual(encoded(report), encoded(again))
        self.assertEqual(report['code_sha256'], code_identity())
        self.assertEqual(report['summary']['windows'], 1)
        self.assertLessEqual(report['known_answer_max_error_px'], 0.25)
        self.assertEqual(len(report['method']['measurements']), 2)
        self.assertTrue(all(row['verdict'] in ('consistent', 'inconsistent') for row in report['results']))
        self.assertTrue(any('cannot separate' in limit for limit in report['limitations']))
        self.assertTrue(any('not an accuracy assessment' in limit for limit in report['limitations']))
        self.assertIn('diagnostic only', report['method']['measurements'][1])
        self.assertIn('phase_peak_ratio_range', report['summary'])

    def test_featureless_pinned_window_is_rejected(self):
        fixture = Fixture(self.root/'flat')
        flat = self.root/'flat'/'images'
        path = flat/f'gid1-at50-{LAYERS["north_south_2021_10_09"]}.jpg'
        Image.fromarray(np.zeros((600, 600, 3), dtype=np.uint8)).save(path, format='JPEG', quality=88)
        fixture.rewrite(lambda manifest: manifest['files'][1].update(bytes=path.stat().st_size,
                                                                    sha256=digest(path)))
        with self.assertRaisesRegex(ValueError, 'texture'):
            analyse(fixture.manifest_path, self.root/'flat', fixture.plan_path)


class FrozenDataTests(unittest.TestCase):
    """The versioned package must verify offline, so the report is re-checkable."""

    def test_versioned_manifest_matches_versioned_inputs(self):
        manifest = verify(FROZEN/'manifest.json', FROZEN, FROZEN/'plan.json')
        self.assertEqual(len(manifest['files']), 32)
        self.assertEqual(len(manifest['requests']), 30)
        self.assertEqual(len(manifest['plan']['windows']), 15)

    def test_plan_rejects_another_sample(self):
        comparison = json.loads((ROOT/'data/research/canopy-verified/comparison.json').read_text())
        snapshot = ROOT/'data/research/canopy-inputs'
        spec = plan(snapshot, ROOT/'data/research/canopy-verified/comparison.json')
        self.assertEqual(len(spec['windows']), 15)
        self.assertEqual(spec['width'], 1200)
        with tempfile.TemporaryDirectory() as temp:
            broken = Path(temp)/'comparison.json'
            broken.write_bytes(encoded(dict(comparison, selected_gids=comparison['selected_gids'][:-1])))
            with self.assertRaisesRegex(ValueError, 'differs from the published canopy selection'):
                plan(snapshot, broken)


if __name__ == '__main__':
    unittest.main()
