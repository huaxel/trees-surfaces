"""Offline agreement check between the two 2021 UrbIS flight products.

The question is narrow: what displacement relates the two products on fixed windows
of the published cycling sample, and is it precise enough to say anything at lane
level?

Three measurements are taken, each with the resolution it actually has:

* a resolving-band comparison of normalised luminance cross-correlation, used to
  decide whether one rigid offset describes the pair. A band whose correlation lobe
  is wide cannot locate an offset as precisely as a fine band, so its width is
  reported and wide bands are excluded from the verdict;
* the full-band offset itself, which is the magnitude of interest;
* a phase-only correlation of gradient energy, reported as a diagnostic only. It
  weights every frequency equally, so any broadband content difference suppresses
  its peak; that is a property of the estimator, not evidence about the products.

Controls run on the same windows and include one with an independent degradation
(JPEG re-encode, illumination ramp, additive noise), which is what the band
comparison must survive.
"""
import argparse
import json
import os
import platform
import statistics
import tempfile
from pathlib import Path

import numpy as np
import PIL
from PIL import Image

from registration import _refine, _peak, estimate_shift, interpret, luminance, shifted, window
from support import digest, encoded, require
from wms import LAYERS, pinned_array, verify

MAX_SHIFT_M = 6.0
BAND_AGREEMENT_M = 0.5
BAND_WAVELENGTHS_M = (1.0, 2.0, 5.0, 20.0)
MIN_CYCLES_ACROSS_WINDOW = 4
MIN_WAVELENGTH_PX = 4
KNOWN_ANSWERS_M = ((1.0, 0.0), (2.0, 0.0), (0.0, 2.0), (2.0, 2.0), (4.0, 0.0))
KNOWN_ANSWER_TOLERANCE_PX = 0.25
DEGRADED_SHIFT_M = (1.5, 0.0)
DEGRADED_TOLERANCE_M = BAND_AGREEMENT_M
DEGRADED_NOISE_LSB = 3.0
DEGRADED_ILLUMINATION = 0.6
DEGRADED_JPEG_QUALITY = 45
DEGRADED_FOOTPRINT_PX = (9, -6)
REFERENCE = 'east_west_2021_09_22_or_25'
MOVING = 'north_south_2021_10_09'
CODE_FILES = ('registration.py', 'wms.py', 'consistency.py', 'geometry.py', 'support.py',
              'pyproject.toml', 'uv.lock')
VERDICT_LABELS = {'consistent': 'bands agree within the tolerance',
                  'inconsistent': 'bands disagree beyond the tolerance'}

LIMITS = [
    'The two products are one 2021 programme, same camera and orthorectification chain, and both are CC BY 4.0 with required source citation; their records name the flight axes and the shared statement dates the passes, while the acquisition period alone (2021-09-17 to 2021-10-09) is identical in both',
    'A measured offset mixes georeferencing difference, relief displacement at building height, sun-angle and seasonal change that this method cannot separate',
    'Two products can be displaced relative to each other and both be accurate, or both be wrong in the same way; this is not an accuracy assessment of either product',
    'Agreement across bands shows only that they located the same maximum; it does not validate that maximum against any reference, so a consistent window is not a verified offset',
    'Fixed 120 m windows at three chainages per route are a diagnostic subset, not a probability sample; the window geometry was declared before fetching, the agreement thresholds were not',
    'Bands whose correlation lobe is wider than the tolerance cannot resolve it; they are reported but excluded from the verdict',
    'The phase-only estimator weights all frequencies equally and is not a test of the products; its failure to peak is reported separately and never used as evidence of disagreement',
    'Estimator sensitivity is about 0.25 px on hard synthetic texture and far better on these windows; the controls resample the imagery itself, so they test the estimator, not the products',
    'Nothing here validates canopy classification, tree presence, or the positional accuracy of the vegetation polygons',
    'No result from this check was used to adjust canopy figures or the operational ranking',
]


def code_identity():
    root = Path(__file__).parent
    return {name: digest(root/name) for name in CODE_FILES}


def lowpass(image, cutoff):
    """Keep frequencies up to `cutoff` cycles per pixel (0.5 is the full band)."""
    spectrum = np.fft.fft2(image)
    rows, columns = image.shape
    u = np.fft.fftfreq(rows)[:, None]
    v = np.fft.fftfreq(columns)[None, :]
    return np.real(np.fft.ifft2(spectrum*(np.hypot(u, v) <= cutoff)))


def centred(image, taper):
    """Remove the taper-weighted mean, then taper: the sequence that leaves no
    rectangle discontinuity for the band-limit to ring on."""
    weight = taper/taper.sum()
    return (image - float((image*weight).sum()))*taper


def bands_for(pixel_m, window_m):
    """Comparison bands this window can resolve, coarsest last.

    Each band carries the width of its correlation lobe in metres (about half its
    shortest wavelength, or half a pixel for the full band), because that width
    bounds how precisely the band can place an offset at all.
    """
    require(pixel_m > 0 and window_m > 0, 'Window geometry must be positive')
    bands = [dict(band='full', cutoff=0.5, wavelength_m=pixel_m*2, lobe_width_m=pixel_m/2)]
    for wavelength in BAND_WAVELENGTHS_M:
        pixels = wavelength/pixel_m
        if pixels >= MIN_WAVELENGTH_PX and wavelength <= window_m/MIN_CYCLES_ACROSS_WINDOW:
            bands.append(dict(band=f'above_{wavelength:g}m', cutoff=1/pixels,
                              wavelength_m=wavelength, lobe_width_m=wavelength/2))
    require(len(bands) > 1, 'Window is too small to resolve any comparison band')
    for entry in bands:
        entry['can_resolve_tolerance'] = entry['lobe_width_m'] <= BAND_AGREEMENT_M
    require(sum(entry['can_resolve_tolerance'] for entry in bands) >= 2,
            'Window has fewer than two bands able to resolve the tolerance')
    return bands


def band_sets(bands):
    """Nested band sets, coarsest band last, so sensitivity to the cut is visible.

    The bands are nested by construction (the fine band contains every coarser one),
    so agreement across a wider set is one check on subsets, not independent
    confirmations.
    """
    require(len(bands) >= 2, 'Need at least two bands')
    sets = {}
    for count in range(2, len(bands)+1):
        chosen = bands[:count]
        coarsest = chosen[-1]['band'].replace('above_', '').replace('full', 'full')
        sets[f'{count}_bands_through_{coarsest}'] = chosen
    return sets


def lobe_px(cutoff):
    """The band's correlation lobe width in pixels, for peak-separation exclusion."""
    return 0.5/max(cutoff, 1e-9)


def cross_correlation(reference, moving, cutoff, pixel_m):
    """Normalised correlation surface and its best offset, in metres.

    The normalisation puts a perfect match at 1.0, so the peak is directly
    interpretable. Both images get the same taper as the phase estimator, so a hard
    window edge shared by both cannot contribute a common-lag component.
    """
    taper = window(reference.shape)
    a = lowpass(centred(reference, taper), cutoff)
    b = lowpass(centred(moving, taper), cutoff)
    sigma = np.sqrt(float((a*a).mean())*float((b*b).mean()))
    require(sigma > 0, 'Band-limited window is featureless')
    # conj(reference) * moving puts the displacement of the moving content at +d.
    spectrum = np.conj(np.fft.fft2(a))*np.fft.fft2(b)/(len(a.ravel())*sigma)
    surface = np.real(np.fft.ifft2(spectrum))
    rows, columns = surface.shape
    max_shift = int(round(MAX_SHIFT_M/pixel_m))
    require(max_shift*2 < min(rows, columns), 'Search radius does not fit the window')
    mask = np.zeros_like(surface, dtype=bool)
    mask[:max_shift + 1, :max_shift + 1] = mask[:max_shift + 1, -max_shift:] = True
    mask[-max_shift:, :max_shift + 1] = mask[-max_shift:, -max_shift:] = True
    (peak_row, peak_column), peak = _peak(np.where(mask, surface, -np.inf), 1e-12)
    # Peak separation: the best value outside the band's own lobe. A ratio near one
    # means the band cannot separate this offset from its neighbour, whatever its
    # nominal lobe width; a large ratio means a distinct peak.
    reach = max(1, int(np.ceil(lobe_px(cutoff))))
    exclusion = np.zeros_like(surface, dtype=bool)
    for dr in range(-reach, reach+1):
        for dc in range(-reach, reach+1):
            exclusion[(peak_row + dr) % rows, (peak_column + dc) % columns] = True
    rival = float(np.abs(np.where(exclusion, 0.0, surface)).max())
    return surface, spectrum, (peak_row, peak_column), float(peak), peak/max(rival, 1e-12)


def band_measurement(reference, moving, band, pixel_m):
    surface, spectrum, (peak_row, peak_column), peak, separation = cross_correlation(
        reference, moving, band['cutoff'], pixel_m)
    row, column, _ = _refine(spectrum, float(peak_row), float(peak_column))
    if row > surface.shape[0]/2:
        row -= surface.shape[0]
    if column > surface.shape[1]/2:
        column -= surface.shape[1]
    return dict(band=band['band'], cutoff=band['cutoff'], wavelength_m=band['wavelength_m'],
                lobe_width_m=band['lobe_width_m'],
                can_resolve_tolerance=band['can_resolve_tolerance'],
                best_ncc=peak, peak_separation_ratio=separation,
                east_m=float(column*pixel_m), north_m=float(-row*pixel_m))


def known_answers(reference, pixel_m, max_shift_px):
    """Control: the estimator must recover a synthetic displacement of this window."""
    rows = []
    for east_m, north_m in KNOWN_ANSWERS_M:
        synthetic = shifted(reference, -north_m/pixel_m, east_m/pixel_m)
        measured = interpret(estimate_shift(reference, synthetic, max_shift=max_shift_px,
                                            min_rival_ratio=0), pixel_m)
        error_m = float(np.hypot(measured['east_m']-east_m, measured['north_m']-north_m))
        rows.append(dict(asked_east_m=east_m, asked_north_m=north_m, east_m=measured['east_m'],
                         north_m=measured['north_m'], error_m=error_m, error_px=error_m/pixel_m))
    return rows


def resampled_answers(reference, pixel_m, max_shift_px):
    """Controls with cubic resampling: the source is padded so no filled edge is analysed.

    The last case also crops a shifted footprint, so the two compared images do not
    share their edges; a common edge or wraparound component cannot hide in it.
    """
    pad = int(round(len(reference)/8))
    padded = np.pad(reference, pad, mode='edge')
    image = Image.fromarray(np.clip(padded, 0, 255).astype(np.uint8))
    cases = [(east, north, 0, 0) for east, north in KNOWN_ANSWERS_M[:3]]
    cases.append((2.0, -1.0, 7, -4))
    rows = []
    for east_m, north_m, row_crop, column_crop in cases:
        moved = image.transform(image.size, Image.AFFINE,
                                (1, 0, -east_m/pixel_m, 0, 1, north_m/pixel_m),
                                resample=Image.BICUBIC)
        array = np.asarray(moved)
        crop = array[pad+row_crop:pad+row_crop+len(reference),
                     pad+column_crop:pad+column_crop+len(reference)].astype(np.float64)
        # Cropping at an offset removes that offset from the content's displacement.
        expected = (east_m - column_crop*pixel_m, north_m + row_crop*pixel_m)
        measured = interpret(estimate_shift(reference, crop, max_shift=max_shift_px,
                                            min_rival_ratio=0), pixel_m)
        error_m = float(np.hypot(measured['east_m']-expected[0], measured['north_m']-expected[1]))
        rows.append(dict(asked_east_m=east_m, asked_north_m=north_m,
                         footprint_rows=row_crop, footprint_columns=column_crop,
                         expected_east_m=expected[0], expected_north_m=expected[1],
                         east_m=measured['east_m'], north_m=measured['north_m'],
                         error_m=error_m, error_px=error_m/pixel_m))
    return rows


def degraded_answers(reference, bands, pixel_m):
    """Positive control: a known offset under degradation the products really show.

    Applies JPEG re-encoding, a smooth illumination ramp and additive noise to a
    known displacement of the window, then asks every band for the offset. A band
    whose answer drifts beyond the tolerance is not measuring the displacement.
    """
    east_m, north_m = DEGRADED_SHIFT_M
    row_crop, column_crop = DEGRADED_FOOTPRINT_PX
    pad = int(round(len(reference)/8))
    padded = np.pad(reference, pad, mode='edge')
    image = Image.fromarray(np.clip(padded, 0, 255).astype(np.uint8))
    moved = np.asarray(image.transform(image.size, Image.AFFINE,
                                       (1, 0, -east_m/pixel_m, 0, 1, north_m/pixel_m),
                                       resample=Image.BICUBIC))[
        pad+row_crop:pad+row_crop+len(reference),
        pad+column_crop:pad+column_crop+len(reference)]
    ramp = 1.0+DEGRADED_ILLUMINATION*(np.arange(moved.shape[1])[None, :]/moved.shape[1]-0.5)
    rng = np.random.default_rng(20261017)
    noisy = moved*ramp + rng.normal(0, DEGRADED_NOISE_LSB, moved.shape)
    buffer = tempfile.TemporaryDirectory(prefix='.degraded-')
    try:
        path = Path(buffer.name)/'moving.jpg'
        Image.fromarray(np.clip(noisy, 0, 255).astype(np.uint8)).save(path, format='JPEG',
                                                                     quality=DEGRADED_JPEG_QUALITY)
        with Image.open(path) as reloaded:
            degraded = luminance(np.asarray(reloaded.convert('RGB')))
    finally:
        buffer.cleanup()
    # Cropping at an offset removes that offset from the content's displacement.
    expected = (east_m - column_crop*pixel_m, north_m + row_crop*pixel_m)
    measured = []
    for band in bands:
        values = band_measurement(reference, degraded, band, pixel_m)
        error_m = float(np.hypot(values['east_m']-expected[0], values['north_m']-expected[1]))
        measured.append(dict(band=band['band'], east_m=values['east_m'], north_m=values['north_m'],
                             error_m=error_m, can_resolve_tolerance=band['can_resolve_tolerance']))
    return dict(asked_east_m=east_m, asked_north_m=north_m,
                footprint_pixels=list(DEGRADED_FOOTPRINT_PX),
                expected_east_m=expected[0], expected_north_m=expected[1], bands=measured,
                max_error_resolving_m=max(row['error_m'] for row in measured
                                          if row['can_resolve_tolerance']),
                max_error_wide_band_m=max([row['error_m'] for row in measured
                                           if not row['can_resolve_tolerance']] or [0.0]))


def analyse_window(manifest, root, window, pixel_m):
    span = (window['bounds'][2]-window['bounds'][0], window['bounds'][3]-window['bounds'][1])
    require(all(abs(value - manifest['plan']['window_m']) < 1e-6 for value in span),
            'Window does not match the planned size')
    reference = luminance(pinned_array(manifest, root, window['window_id'], LAYERS[REFERENCE]))
    moving = luminance(pinned_array(manifest, root, window['window_id'], LAYERS[MOVING]))
    max_shift_px = int(round(MAX_SHIFT_M/pixel_m))
    bands = bands_for(pixel_m, manifest['plan']['window_m'])
    identity = interpret(estimate_shift(reference, reference, max_shift=max_shift_px,
                                        min_rival_ratio=0), pixel_m)
    require(abs(identity['east_m']) < 1e-6 and abs(identity['north_m']) < 1e-6,
            'Identical imagery did not register at zero')
    phase = interpret(estimate_shift(reference, moving, max_shift=max_shift_px,
                                     min_rival_ratio=0), pixel_m)
    values = [band_measurement(reference, moving, band, pixel_m) for band in bands]
    controls = known_answers(reference, pixel_m, max_shift_px)
    cubic = resampled_answers(reference, pixel_m, max_shift_px)
    degraded = degraded_answers(reference, bands, pixel_m)
    control_error_px = max(row['error_px'] for row in controls)
    cubic_error_px = max(row['error_px'] for row in cubic)
    require(control_error_px <= KNOWN_ANSWER_TOLERANCE_PX,
            'Known-answer control failed; the estimator cannot resolve this scale')
    require(cubic_error_px <= KNOWN_ANSWER_TOLERANCE_PX,
            'Resampled control failed; the estimator cannot resolve this scale')
    require(degraded['max_error_resolving_m'] <= DEGRADED_TOLERANCE_M,
            'A resolving band failed the degraded control; it is not measuring the offset')
    def spread_of(rows):
        offsets = np.array([[row['east_m'], row['north_m']] for row in rows])
        return float(max(np.hypot(*(a-b)) for a in offsets for b in offsets))
    resolving = [row for row in values if row['can_resolve_tolerance']]
    spreads = {name: spread_of(chosen) for name, chosen in band_sets(values).items()}
    require(len(resolving) >= 2, 'Fewer than two bands can resolve the tolerance')
    spread = spread_of(resolving)
    verdict = 'consistent' if spread <= BAND_AGREEMENT_M else 'inconsistent'
    return dict(window_id=window['window_id'], gid=window['gid'], chainage_m=window['chainage_m'],
                segment_length_m=window['segment_length_m'], bounds=list(window['bounds']),
                offset_m=dict(full_band_east_m=values[0]['east_m'],
                              full_band_north_m=values[0]['north_m'],
                              full_band_magnitude_m=float(np.hypot(values[0]['east_m'],
                                                                   values[0]['north_m'])),
                              full_band_ncc=values[0]['best_ncc']),
                phase=dict(east_m=phase['east_m'], north_m=phase['north_m'],
                           magnitude_m=phase['magnitude_m'], peak_ratio=phase['peak_ratio'],
                           at_search_bound=bool(phase['magnitude_m'] >= MAX_SHIFT_M*0.9)),
                bands=values, resolving_band_spread_m=spread, spread_by_band_set_m=spreads,
                verdict=verdict, verdict_rule=VERDICT_LABELS[verdict],
                known_answers=controls, known_answer_max_error_px=control_error_px,
                resampled_answers=cubic, resampled_max_error_px=cubic_error_px,
                degraded_control=degraded)


def analyse(manifest_path, root, plan_path):
    manifest_path, root, plan_path = Path(manifest_path), Path(root), Path(plan_path)
    manifest = verify(manifest_path, root, plan_path)
    code = code_identity()
    pixel_m = manifest['plan']['pixel_m']
    rows = [analyse_window(manifest, root, window, pixel_m) for window in manifest['plan']['windows']]
    require(verify(manifest_path, root, plan_path) == manifest, 'Pinned inputs changed during analysis')
    require(code_identity() == code, 'Analysis code changed during analysis')
    consistent = [row for row in rows if row['verdict'] == 'consistent']
    magnitudes = [row['offset_m']['full_band_magnitude_m'] for row in rows]
    cuts = {}
    for name in rows[0]['spread_by_band_set_m']:
        values = [row['spread_by_band_set_m'][name] for row in rows]
        cuts[name] = dict(consistent_windows=sum(1 for value in values if value <= BAND_AGREEMENT_M),
                          median_spread_m=statistics.median(values), max_spread_m=max(values))
    return dict(schema_version=2, manifest_sha256=digest(manifest_path),
                plan_sha256=digest(plan_path), code_sha256=code,
                environment=dict(python=platform.python_version(), numpy=np.__version__,
                                 pillow=PIL.__version__, platform=platform.platform()),
                method=dict(reference_product=REFERENCE, moving_product=MOVING,
                            measurements=['normalised luminance cross-correlation per spatial band',
                                          'phase-only correlation of gradient energy (diagnostic only)'],
                            band_wavelengths_m=list(BAND_WAVELENGTHS_M),
                            min_cycles_across_window=MIN_CYCLES_ACROSS_WINDOW,
                            verdict_band_set='bands whose correlation lobe is no wider than the '
                                             'agreement tolerance: a wider lobe cannot resolve the '
                                             'difference, and the sets are nested',
                            sensitivity_band_sets='spread is also reported for every wider nested set',
                            band_agreement_m=BAND_AGREEMENT_M,
                            max_shift_m=MAX_SHIFT_M,
                            window_m=manifest['plan']['window_m'], pixel_m=pixel_m,
                            search_mask='square, +/-6 m on each axis, so up to 8.5 m diagonally',
                            known_answers=list(KNOWN_ANSWERS_M),
                            known_answer_tolerance_px=KNOWN_ANSWER_TOLERANCE_PX,
                            known_answer_control='Synthetic band-limited displacement of the pinned '
                                                 'reference window: proves the estimator recovers a known '
                                                 'shift in this imagery',
                            resampled_control='Cubic resampling of a padded copy of the pinned window, so '
                                              'no filled edge is analysed',
                            degraded_control=dict(shift_m=list(DEGRADED_SHIFT_M),
                                                  jpeg_quality=DEGRADED_JPEG_QUALITY,
                                                  illumination_ramp=DEGRADED_ILLUMINATION,
                                                  noise_lsb=DEGRADED_NOISE_LSB,
                                                  requirement='every resolving band must stay within '
                                                              f'{DEGRADED_TOLERANCE_M} m of the known shift')),
                source_records=manifest['source_records'], requests=manifest['requests'],
                known_answer_max_error_px=max(row['known_answer_max_error_px'] for row in rows),
                resampled_max_error_px=max(row['resampled_max_error_px'] for row in rows),
                degraded_max_error_resolving_band_m=max(
                    row['degraded_control']['max_error_resolving_m'] for row in rows),
                degraded_max_error_wide_band_m=max(
                    row['degraded_control']['max_error_wide_band_m'] for row in rows),
                results=rows,
                summary=dict(
                    windows=len(rows), consistent_windows=len(consistent),
                    inconsistent_windows=len(rows)-len(consistent),
                    median_full_band_offset_m=statistics.median(magnitudes),
                    full_band_offset_m_range=[min(magnitudes), max(magnitudes)],
                    median_resolving_band_spread_m=statistics.median(
                        row['resolving_band_spread_m'] for row in rows),
                    max_resolving_band_spread_m=max(row['resolving_band_spread_m'] for row in rows),
                    band_set_sensitivity=cuts,
                    full_band_ncc_range=[min(row['offset_m']['full_band_ncc'] for row in rows),
                                         max(row['offset_m']['full_band_ncc'] for row in rows)],
                    phase_peak_ratio_range=[min(row['phase']['peak_ratio'] for row in rows),
                                            max(row['phase']['peak_ratio'] for row in rows)],
                    phase_at_search_bound=sum(row['phase']['at_search_bound'] for row in rows),
                    finding=('One offset per window describes the pair to a median of '
                             f'{statistics.median(row["resolving_band_spread_m"] for row in rows):.2f} m '
                             f'(range {min(row["resolving_band_spread_m"] for row in rows):.2f}-'
                             f'{max(row["resolving_band_spread_m"] for row in rows):.2f} m) across the bands '
                             'that can resolve the tolerance, while the offset itself varies by window from '
                             f'{min(magnitudes):.2f} m to {max(magnitudes):.2f} m '
                             f'(median {statistics.median(magnitudes):.2f} m); '
                             f'{len(consistent)} of {len(rows)} windows agree within '
                             f'{BAND_AGREEMENT_M} m on the resolving bands alone')),
                limitations=LIMITS)


def main():
    repository = Path(__file__).resolve().parents[2]
    frozen = repository/'data/research/imagery-inputs'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=frozen)
    parser.add_argument('--output', type=Path, required=True, help='New JSON file, never overwritten')
    args = parser.parse_args()
    require(not args.output.exists(), 'Output already exists')
    report = analyse(args.root/'manifest.json', args.root, args.root/'plan.json')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.imagery-', dir=args.output.parent) as temp:
        staged = Path(temp)/'report.json'
        staged.write_bytes(encoded(report))
        # link() refuses to replace an existing file, so a concurrent writer cannot be clobbered.
        os.link(staged, args.output)
    print(json.dumps(report['summary'], indent=2))


if __name__ == '__main__':
    main()
