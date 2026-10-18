"""Sub-pixel registration between two rasters of the same area.

The estimator is a windowed, phase-whitened cross-correlation of gradient energy.
Gradient energy is used because two flights of the same city differ strongly in
brightness, colour and shadow direction while still sharing the geometry of
building edges, kerbs and façades.

Sign convention: a returned positive row shift means features appear lower in the
moving image's array (towards larger row index) than in the reference, and a
positive column shift means they appear further right. Callers map that to metres
and compass directions themselves; `interpret` does it for a north-up raster.
"""
import numpy as np

from support import require

MAX_ZERO_EVIDENCE = 1e-12


def luminance(rgb):
    """Rec. 601 luma of an (rows, columns, 3) uint8 array as float64 in 0-255."""
    array = np.asarray(rgb)
    require(array.ndim == 3 and array.shape[2] == 3, 'Expected an (rows, columns, 3) image')
    weights = np.array([0.299, 0.587, 0.114])
    return array.astype(np.float64) @ weights


def gradient_energy(image):
    """Central-difference gradient magnitude, edge-safe (no wrap, no padding fill)."""
    array = np.asarray(image, dtype=np.float64)
    require(array.ndim == 2 and min(array.shape) >= 8, 'Expected a 2-D image of at least 8x8')
    require(np.isfinite(array).all(), 'Image contains non-finite values')
    rows = (array[2:, 1:-1] - array[:-2, 1:-1]) / 2
    columns = (array[1:-1, 2:] - array[1:-1, :-2]) / 2
    return np.hypot(rows, columns)


def window(shape):
    """Separable Hann window; reduces the implicit periodicity of the FFT."""
    rows, columns = shape
    require(min(shape) >= 8, 'Window too small')
    r = np.hanning(rows)[:, None]
    c = np.hanning(columns)[None, :]
    return r * c


def shifted(image, row_shift, column_shift):
    """Band-limited translation for known-answer controls: content moves by (+row, +column)."""
    array = np.asarray(image, dtype=np.float64)
    require(array.ndim == 2, 'Expected a 2-D image')
    rows, columns = array.shape
    spectrum = np.fft.fft2(array)
    v = np.fft.fftfreq(rows)[:, None]
    u = np.fft.fftfreq(columns)[None, :]
    ramp = np.exp(-2j * np.pi * (v * row_shift + u * column_shift))
    return np.real(np.fft.ifft2(spectrum * ramp))


def _peak(values, zero_evidence):
    require(values.size > 0, 'Empty correlation surface')
    require(float(np.max(np.abs(values))) > zero_evidence, 'Correlation surface is flat')
    index = int(np.argmax(values))
    coordinates = np.unravel_index(index, values.shape)
    return coordinates, float(values[coordinates])


UPSAMPLE = 100
REFINE_RADIUS_PX = 1.5


def whitened_spectrum(cross):
    """Phase-only normalisation, leaving negligible magnitudes at zero.

    A band-limited or locally flat image has exact spectral zeros; dividing by
    them would produce non-finite values that poison the whole surface.
    """
    magnitude = np.abs(cross)
    require(float(magnitude.max()) > MAX_ZERO_EVIDENCE,
            'No usable gradient texture: at least one image is featureless')
    usable = magnitude > MAX_ZERO_EVIDENCE*magnitude.max()
    return np.where(usable, cross/np.where(usable, magnitude, 1.0), 0.0)


def _refine(spectrum, coarse_row, coarse_column, upsample=UPSAMPLE,
            radius_px=REFINE_RADIUS_PX):
    """Sample the exact band-limited correlation surface on a fine grid.

    A parabola fitted to three whole-pixel samples is biased by up to a pixel,
    which would swamp the sub-metre differences this check is meant to resolve.
    Instead the Fourier series of the correlation surface is evaluated directly,
    as a product of two DFT matrices, which is exact for the sampled data.
    """
    rows, columns = spectrum.shape
    require(radius_px >= 0.5, 'Refinement must span at least one whole pixel')
    # Drop the Nyquist row and column. Their phase labels are ambiguous under
    # negation, which leaves an imaginary residue for fractional offsets; the
    # remaining band is the standard real band-limited interpolant of the grid.
    band = np.ones_like(spectrum, dtype=bool)
    band[rows//2, :] = band[:, columns//2] = False
    spectrum = spectrum*band
    offsets = np.arange(-radius_px, radius_px + 1/upsample, 1/upsample)
    row_offsets, column_offsets = coarse_row + offsets, coarse_column + offsets
    # fftfreq keeps the signed frequency of the wrapped FFT index; using the raw
    # index would alias the shifted frequencies for fractional offsets.
    row_basis = np.exp(2j*np.pi*np.fft.fftfreq(rows)[:, None]*row_offsets[None, :])
    column_basis = np.exp(2j*np.pi*np.fft.fftfreq(columns)[:, None]*column_offsets[None, :])
    fine = (row_basis.T @ (spectrum @ column_basis))/(rows*columns)
    require(float(np.abs(fine.imag).max()) <= 1e-9*max(float(np.abs(fine.real).max()), 1e-30),
            'Refined surface is not real-valued')
    values = fine.real
    index = int(np.argmax(values))
    row, column = np.unravel_index(index, values.shape)
    # Residual parabolic step on the fine grid: the spacing is 1/upsample pixels.
    step = 1/upsample
    def adjust(centre, forward, backward):
        denominator = forward - 2*centre + backward
        return 0.0 if denominator == 0 else float(np.clip(0.5*(forward-backward)/denominator, -1, 1))
    dr = adjust(values[row, column], values[min(row+1, values.shape[0]-1), column],
                values[max(row-1, 0), column])
    dc = adjust(values[row, column], values[row, min(column+1, values.shape[1]-1)],
                values[row, max(column-1, 0)])
    return (float(row_offsets[row] + dr*step), float(column_offsets[column] + dc*step),
            float(values[row, column]))


def estimate_shift(reference, moving, max_shift, min_rival_ratio=0.0):
    """Displacement of `moving` relative to `reference`, in pixel units.

    `max_shift` bounds the search in whole pixels, so the result never silently
    wraps around the array. `min_rival_ratio` compares the correlation peak with
    the best peak outside a one-pixel neighbourhood; a low ratio means the match
    is ambiguous rather than precise. Both images must already be co-gridded.
    """
    reference, moving = np.asarray(reference, dtype=np.float64), np.asarray(moving, dtype=np.float64)
    require(reference.shape == moving.shape, 'Images differ in shape')
    require(min(reference.shape) >= 12, 'Images too small for a gradient-based estimate')
    require(reference.ndim == 2, 'Expected 2-D images')
    require(1 <= max_shift < min(reference.shape) // 4, 'max_shift outside usable radius')
    reference_energy, moving_energy = gradient_energy(reference), gradient_energy(moving)
    # The window follows the gradient support, which is one pixel smaller on each side.
    windowed = window(reference_energy.shape)
    a, b = np.fft.fft2(reference_energy * windowed), np.fft.fft2(moving_energy * windowed)
    # conj(reference) * moving puts the displacement of the moving content at +d.
    cross = np.conj(a) * b
    spectrum = whitened_spectrum(cross)
    surface = np.real(np.fft.ifft2(spectrum))
    rows, columns = surface.shape
    # The aligning displacement can sit at either end of the circular axis.
    mask = np.zeros_like(surface, dtype=bool)
    mask[:max_shift + 1, :max_shift + 1] = mask[:max_shift + 1, -max_shift:] = True
    mask[-max_shift:, :max_shift + 1] = mask[-max_shift:, -max_shift:] = True
    require(bool(mask.any()), 'Empty search region')
    searched = np.where(mask, surface, -np.inf)
    (peak_row, peak_column), peak = _peak(searched, MAX_ZERO_EVIDENCE)
    neighbourhood = np.zeros_like(surface, dtype=bool)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            neighbourhood[(peak_row + dr) % rows, (peak_column + dc) % columns] = True
    rivals = np.where(neighbourhood | ~mask, -np.inf, surface)
    rival = float(rivals.max())
    ratio = float('inf') if rival == -np.inf else peak / max(abs(rival), MAX_ZERO_EVIDENCE)
    row_shift, column_shift, refined = _refine(spectrum, float(peak_row), float(peak_column))
    tolerance = REFINE_RADIUS_PX + 1/UPSAMPLE + 1e-9
    require(abs(row_shift - peak_row) <= tolerance and abs(column_shift - peak_column) <= tolerance,
            'Refinement disagreed with the searched peak location')
    if row_shift > rows / 2:
        row_shift -= rows
    if column_shift > columns / 2:
        column_shift -= columns
    require(abs(row_shift) <= max_shift + 1 and abs(column_shift) <= max_shift + 1,
            'Shift escaped the searched radius')
    require(ratio + 1e-9 >= min_rival_ratio,
            f'Ambiguous match: peak/rival {ratio:.3f} below {min_rival_ratio:.3f}')
    return dict(row_shift=row_shift, column_shift=column_shift,
                magnitude=float(np.hypot(row_shift, column_shift)),
                peak=peak, peak_ratio=ratio)


def interpret(result, pixel_size_m):
    """Convert row/column pixels to east/north metres for a north-up raster."""
    require(pixel_size_m > 0, 'Pixel size must be positive')
    return dict(east_m=result['column_shift'] * pixel_size_m,
                north_m=-result['row_shift'] * pixel_size_m,
                magnitude_m=result['magnitude'] * pixel_size_m,
                peak_ratio=result['peak_ratio'])
