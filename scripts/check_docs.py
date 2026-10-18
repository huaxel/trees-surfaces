"""Check that documentation references resolve and quoted numbers match their artifacts.

Two failure modes motivated this. A doc kept claiming that no real mean/maximum run had
happened after one had, and a doc named the open UrbIS DSM as an independent check of a
class that was defined by that very product. Both were prose defects that no test
covered: the gates check code and artifacts, not the sentences describing them.

So this script checks two things, both mechanical:

1. every repository path named in `docs/*.md` and `README.md` exists, and every relative
   Markdown link resolves;
2. a ledger of load-bearing numbers quoted in those documents still equals the value in
   the committed artifact that backs it.

The ledger is deliberately explicit. A regex that stops matching is a failure, not a
silent pass, so a sentence cannot drift away from its artifact unnoticed: either the
number is corrected or the claim is moved out of the ledger on purpose. Claims about
values that exist only in a local, uncommitted run are *not* listed, because a check that
cannot fail in CI is not a check.
"""
import argparse
import json
import math
import os
import re
import statistics
import subprocess
import sys
from pathlib import Path

DOCS = ('README.md',)
# Repository paths named in prose that are not repository paths: Julia package names.
EXTERNAL_REFERENCES = frozenset({'HDF5.jl', 'HTTP.jl', 'JSON3.jl', 'TiffImages.jl'})
# Name patterns and served routes are not repository paths: `WBGT_year_daily_max_YYYY.nc`
# names a family of files, and `/stakeholder-review.csv` is a URL the UI serves.
PLACEHOLDER_MARKERS = ('YYYY', '<', '>', '{', '}')
# Inputs that only ever live in the git-ignored cache, so they cannot be required in a
# clean checkout. Named individually rather than pattern-matched, so adding one is a
# deliberate act.
CACHE_ONLY_REFERENCES = frozenset({'CHM_BCR_EG_2022_complete.shp', 'WBGT_year_daily_mean_2016.nc'})
# Prefixes that are never resolvable in a clean checkout.
SKIP_PREFIXES = ('.cache/', '/tmp/', 'http://', 'https://', 'file://')
NUMBER_WORDS = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five'}

# Backticked tokens that look like file names, and Markdown link targets.
TOKEN = re.compile(r'`([A-Za-z0-9_./-]+\.(?:json|md|py|jl|sh|geojson|csv|tif|nc|png|svg|yml|yaml|xml|txt|dbf|shp|cpg|prj|lock|toml))`')
LINK = re.compile(r'\]\(([^)\s]+)\)')


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Claim:
    """One number quoted in a document, and the artifact value it must equal."""

    def __init__(self, doc, pattern, artifact, selector, tolerance=0.0, rationale='', word=False,
                 also=()):
        self.doc, self.pattern, self.artifact = doc, re.compile(pattern), artifact
        self.selector, self.tolerance, self.rationale = selector, tolerance, rationale
        self.word = word
        # Claims that need more than one artifact receive a mapping keyed by path instead.
        self.also = tuple(also)

    def inputs(self, artifacts):
        names = (self.artifact,) + self.also
        if len(names) == 1:
            return artifacts[self.artifact]
        return {name: artifacts[name] for name in names}

    def check(self, texts, artifacts):
        text = texts.get(self.doc)
        require(text is not None, f'ledger names a missing document: {self.doc}')
        match = self.pattern.search(text)
        require(match is not None,
                f'claim pattern no longer matches {self.doc}: {self.pattern.pattern!r}'
                + (f' ({self.rationale})' if self.rationale else ''))
        require(all(name in artifacts for name in (self.artifact,)+self.also),
                f'ledger names a missing artifact for {self.doc}: {self.artifact}')
        data = self.inputs(artifacts)
        if self.word:
            quoted, actual = match.group(1), str(self.selector(data))
            require(quoted == actual,
                    f'{self.doc} says {quoted!r} but {self.artifact} holds {actual!r}'
                    + (f' ({self.rationale})' if self.rationale else ''))
            return f"{quoted} == {self.artifact}"
        quoted = float(match.group(1).replace(',', ''))
        actual = float(self.selector(data))
        require(abs(quoted - actual) <= self.tolerance,
                f'{self.doc} quotes {quoted:g} but {self.artifact} holds {actual:g}'
                + (f' ({self.rationale})' if self.rationale else ''))
        return f'{quoted:g} == {self.artifact}'


def claim(doc, pattern, artifact, selector, **kwargs):
    return Claim(doc, pattern, artifact, selector, **kwargs)


FRAME = 'data/research/canopy-validation-frame.json'
WINDOWS = 'data/research/canopy-verified/windows.json'
COMPARISON = 'data/research/canopy-verified/comparison.json'
TREES = 'data/brussels-trees-sample.json'
TREE_HEAT = 'data/brussels-tree-heat-sample.json'
SEASON = 'data/brussels-heat-season-sample.json'
EFFECT = 'data/research/canopy-design-effect.json'
HEAT = 'data/brussels-heat-wbgt-sample.json'
SENSITIVITY = 'data/tree-signal-sensitivity.json'
SPEC = 'docs/trees-stakeholder-spec.md'
BRIEF_MOBILITY = 'docs/mobility-measure-stakeholder-brief.md'
COUNTER_IDS = ('CB1101', 'CB1142', 'CJM90', 'CB1143', 'CB2105')
HISTORIES = tuple(f'data/brussels-bike-history-{c}-2024-01.json' for c in COUNTER_IDS)
FLOW = 'data/brussels-tree-counter-flow.json'
NEAREST = 'data/brussels-tree-bike-nearest.json'
ANALYSIS = 'data/tree-signal-analysis.md'
DOCS_REVIEW = 'docs/prototype-review.md'
DIAGNOSTICS = 'data/research/heat-support-diagnostics.md'
DIAGNOSTICS_JSON = 'data/research/heat-support-diagnostics.json'
PLAN = 'docs/canopy-accuracy-sampling-plan.md'
PIPELINE = 'docs/cycling-canopy-pipeline.md'
WBGT = 'docs/wbgt-mean-max-method.md'
BRIEF = 'docs/heat-season-stakeholder-brief.md'
ORTHO = 'data/research/cycling-canopy-ortho-consistency.json'
IMAGERY = 'docs/imagery-registration-check.md'
AUDIT_JSON = 'data/research/cycling-canopy-alignment-audit.json'
AUDIT = 'docs/trees-measurement-audit.md'
CHECKPOINT = 'data/research/cycling-canopy-checkpoint.md'
CANDIDATES = 'docs/open-data-candidates.md'
ZENODO = 'data/research/canopy-inputs/zenodo-record.json'
LOCAL = 'data/research/cycling-canopy-local-comparison.json'
LOCALMD = 'data/research/cycling-canopy-local-comparison.md'
HMETHOD = 'docs/heat-season-method.md'
WIN100 = 'data/research/cycling-canopy-100m-windows.json'
WIN100MD = 'data/research/cycling-canopy-100m-windows.md'
PROTO = 'docs/prototype-next-iteration.md'
GEOJSON = 'data/research/canopy-inputs/cycling-frame.geojson'
DEMO = 'docs/trees-demo-script.md'
JULIA = 'docs/julia.md'
FRAME05 = 'data/research/canopy-validation-frame-0m5.json'
_AUDIT_2M = ('east_2m', 'west_2m', 'north_2m', 'south_2m')
_AUDIT_5M = ('east_5m', 'west_5m', 'north_5m', 'south_5m')


def _ortho_band(data, key, field):
    return data['summary']['band_set_sensitivity'][key][field]


def _audit_scenarios(data, gid, scenarios):
    return [r['overlap_percent'] for r in data['results']
            if r['gid'] == gid and r['scenario'] in scenarios]


def _audit_original(data, gid):
    return next(r['overlap_percent'] for r in data['results']
                if r['gid'] == gid and r['scenario'] == 'original')


def _pooled_overlap(data, vegetation, buffer_m):
    """Length-weighted overlap share across the five published segments."""
    sel = [r for r in data['results']
           if r['vegetation'] == vegetation and r['buffer_m'] == buffer_m]
    return sum(r['overlap_m'] for r in sel)/sum(r['length_m'] for r in sel)*100


def _comparison_gid(data, gid):
    return next(r['overlap_percent'] for r in data['results']
                if r['gid'] == gid and r['vegetation'] == 'trees' and r['buffer_m'] == 0)


def _date_share(data, prefix):
    """Share of analysed reference-line length whose segment start matches prefix."""
    segs = {}
    for r in data['results']:
        segs.setdefault(r['gid'], (r['begin_date'], r['length_m']))
    total = sum(length for _, length in segs.values())
    return sum(length for (begin, length) in segs.values()
               if begin.startswith(prefix))/total*100


def _ortho_window(data, gid, frac):
    return next(r for r in data['results'] if r['window_id'] == f'gid{gid}-{frac}')


def _ortho_ratio_bound(data, which):
    """Min/max over per-band median peak ratios for the four bands the audit range covers."""
    medians = [statistics.median(b['peak_separation_ratio'] for r in data['results']
                                 for b in r['bands'] if b['band'] == band)
               for band in ('full', 'above_1m', 'above_2m', 'above_5m')]
    return min(medians) if which == 'min' else max(medians)


def _gid_values(data, gid, key):
    """Per-window magnitude, resolving-band spread, or full-band NCC for one gid."""
    out = []
    for r in data['results']:
        if r['gid'] != gid:
            continue
        if key == 'magnitude':
            out.append(r['offset_m']['full_band_magnitude_m'])
        elif key == 'spread':
            out.append(r['resolving_band_spread_m'])
        else:
            out.append(r['offset_m']['full_band_ncc'])
    return out


def _zenodo_class_bound(data, which):
    """The gridcode-4 tree-class height bounds as the source record states them."""
    match = re.search(r'From ([\d.]+) to ([\d.]+) m \(nDSM value\): gridcode 4',
                      data['metadata']['description'])
    return float(match.group(1) if which == 'min' else match.group(2))


def _zenodo_ndvi(data):
    """The NDVI selection threshold as the source record states it."""
    return float(re.search(r'NDVI values of ([\d.]+) and higher',
                           data['metadata']['description']).group(1))


def _local_cell(data, gid, buffer_m, key='overlap_percent'):
    """One trees-only comparison cell for one gid and buffer."""
    return next(r[key] for r in data['results']
                if r['gid'] == gid and r['vegetation'] == 'trees'
                and r['buffer_m'] == buffer_m)


def _grid_note(data, which):
    """The coarse-grid footprint as the artifact's grid note states it."""
    match = re.search(r'about (\d+) km north-south and (\d+) km east-west',
                      data['grid']['note'])
    return float(match.group(1) if which == 'ns' else match.group(2))


def _season_threshold(data, which):
    """Hot-day (30) then tropical-night (20) thresholds, in method-text order."""
    vals = re.findall(r'at or above ([\d.]+) \u00b0C', data['method'])
    return float(vals[0] if which == 'hot' else vals[1])


def _window_summary(data, gid, buffer_m):
    """The per-gid, per-buffer window summary (ranges span both endpoint choices)."""
    return next(s for s in data['summaries']
                if s['gid'] == gid and s['buffer_m'] == buffer_m)


def _exact_overlap(block):
    """Size of the intersection of the two exact top-k ID sets."""
    return len(set(block['left']['exact_ids']) & set(block['right']['exact_ids']))


def _geo_length(data, gid):
    """Planar length of one selected route straight from the committed frame."""
    feat = next(f for f in data['features'] if f['properties'].get('gid') == gid)
    geom = feat['geometry']
    lines = geom['coordinates'] if geom['type'] == 'MultiLineString' else [geom['coordinates']]
    return sum(math.dist(line[i], line[i + 1])
               for line in lines for i in range(len(line) - 1))


def _heat_overlap(data, key):
    """One named top-ten overlap from the WBGT period-sensitivity block."""
    return data['period_sensitivity']['top_ten_overlap'][key]


def _frame_share(data, stratum):
    """Length-weighted share of one mapped stratum in a validation frame."""
    return 100*data['stratum_lengths_m'][stratum]/data['assessed_length_m']


def _frame_seg_share(data, gid):
    """Point-grid direct-overlap share of one segment in a validation frame."""
    seg = next(s for s in data['segments'] if s['gid'] == gid)
    return 100*seg['mapped_overlap']/seg['candidates']


def _max_point_gap(frame, comparison):
    """Worst segment-level gap between the point grid and the interval measurement."""
    gaps = []
    for seg in frame['segments']:
        point = 100*seg['mapped_overlap']/seg['candidates']
        interval = next(r['overlap_percent'] for r in comparison['results']
                        if r['gid'] == seg['gid'] and r['vegetation'] == 'trees'
                        and r['buffer_m'] == 0)
        gaps.append(abs(point - interval))
    return max(gaps)


def _stratum(name):
    return lambda data: sum(segment[name] for segment in data['segments'])


def _mobility_overlap(inputs, mode):
    """Recompute the flow-only and weighted top tens against the committed balanced top ten."""
    sensitivity, flow = inputs[SENSITIVITY], inputs['data/brussels-tree-counter-flow.json']
    matched = {row['id']: row['counter_flow_mean'] for row in flow['records']
               if row.get('has_measured_flow')}
    ranked = [row for row in sensitivity['balanced_screening'] if row['id'] in matched]
    require(ranked, 'no matched trees to rank')
    values = [matched[row['id']] for row in ranked]
    low, high = min(values), max(values)

    def score(row):
        flow_value = matched[row['id']]
        if mode == 'flow_only':
            return flow_value
        scaled = 0.0 if high == low else (flow_value-low)/(high-low)
        return 0.6*row['heat_score'] + 0.4*scaled

    top = {row['id'] for row in sorted(ranked, key=lambda r: (-score(r), r['id']))[:10]}
    balanced = set(sensitivity['weight_sensitivity']['balanced_top_10_ids'])
    return len(top & balanced)


def _mobility_panel(inputs):
    """Matched trees, their assigned flow, distance and heat score, from committed artifacts."""
    flow = inputs[FLOW]['records']
    nearest = {row['id']: row for row in inputs[NEAREST]['records']}
    heat = {row['id']: row['heat_score'] for row in inputs[SENSITIVITY]['balanced_screening']}
    trees = [row for row in flow if row.get('has_measured_flow') and row['id'] in nearest]
    return trees, nearest, heat


def _mobility_statistic(inputs, which):
    trees, nearest, heat = _mobility_panel(inputs)
    pairs = [(nearest[row['id']]['nearest_counter_distance_m'], row['counter_flow_mean'])
             for row in trees]

    def pearson(x, y):
        count = len(x)
        mx, my = sum(x)/count, sum(y)/count
        numerator = sum((a-mx)*(b-my) for a, b in zip(x, y))
        denominator = (sum((a-mx)**2 for a in x)*sum((b-my)**2 for b in y))**0.5
        return numerator/denominator

    def ranks(values):
        order = sorted(range(len(values)), key=lambda index: values[index])
        out = [0.0]*len(values)
        index = 0
        while index < len(order):
            end = index
            while end+1 < len(order) and values[order[end+1]] == values[order[index]]:
                end += 1
            for position in range(index, end+1):
                out[order[position]] = (index+end)/2 + 1
            index = end+1
        return out

    if which == 'matched':
        return len(trees)
    if which == 'distinct_flow_values':
        return len({round(row['counter_flow_mean'], 6) for row in trees})
    if which == 'pearson':
        return abs(pearson([p[0] for p in pairs], [p[1] for p in pairs]))
    if which == 'spearman':
        return abs(pearson(ranks([p[0] for p in pairs]), ranks([p[1] for p in pairs])))
    if which.startswith('trees_of_'):
        counter = which.split('trees_of_')[1]
        return sum(1 for row in trees if nearest[row['id']]['nearest_counter'] == counter)
    if which.startswith('mean_of_'):
        counter = which.split('mean_of_')[1]
        rows = inputs[f'data/brussels-bike-history-{counter}-2024-01.json']['records']
        return round(sum(row['count'] for row in rows)/len(rows), 3)
    if which == 'daily_overlap_min':
        return min(_daily_overlaps(inputs))
    if which == 'daily_overlap_max':
        return max(_daily_overlaps(inputs))
    raise ValueError(f'unknown mobility statistic {which}')


def _daily_overlaps(inputs):
    """Per-day flow ranking against the weekly-mean flow ranking, both at 60/40."""
    trees, nearest, heat = _mobility_panel(inputs)
    weekly, daily = {}, {}
    for counter in COUNTER_IDS:
        rows = inputs[f'data/brussels-bike-history-{counter}-2024-01.json']['records']
        per_day = {}
        for row in rows:
            per_day.setdefault(row['count_date'], []).append(row['count'])
        for day, counts in per_day.items():
            daily.setdefault(day, {})[counter] = sum(counts)/len(counts)
        weekly[counter] = sum(row['count'] for row in rows)/len(rows)

    def top_ten(flows):
        values = {row['id']: flows[nearest[row['id']]['nearest_counter']] for row in trees}
        low, high = min(values.values()), max(values.values())
        scored = sorted(((0.6*heat[key] + 0.4*(0.0 if high == low else (value-low)/(high-low)), key)
                         for key, value in values.items()), key=lambda pair: (-pair[0], pair[1]))
        return {key for _, key in scored[:10]}

    baseline = top_ten(weekly)
    return [len(top_ten(daily[day]) & baseline) for day in sorted(daily)]


def _temporal_block(data, metric):
    """The seasonal mean sits in its own block; the other aggregations share one."""
    if metric == 'seasonal_mean_wbgt_c':
        return data['reference_vs_seasonal']
    return data['reference_vs_other_aggregations'][metric]


def _temporal_overlap(data, metric, unit):
    return _temporal_block(data, metric)[unit]['exact_overlap']


def _temporal_spearman(data, metric, unit):
    return _temporal_block(data, metric)[unit]['spearman']


def _quadrant(records):
    """Recompute the high-heat/high-proximity count rather than trust the quoted one."""
    import statistics
    heat = statistics.quantiles([record['heat_score'] for record in records], n=4)[2]
    proximity = statistics.quantiles([record['proximity_score'] for record in records], n=4)[2]
    return sum(1 for record in records
               if record['heat_score'] >= heat and record['proximity_score'] >= proximity)


LEDGER = (
    claim(PLAN, r'\*\*(\d+) candidate points\*\*', FRAME, lambda d: d['candidate_count'],
          rationale='the frame is what the plan draws from'),
    claim(PLAN, r'\*\*([\d,.]+) m\*\*, built by', FRAME, lambda d: d['assessed_length_m']),
    claim(PLAN, r'\*\*([\d.]+) m in total\*\*', FRAME, lambda d: d['excluded_remainder_m'],
          rationale='excluded incomplete remainders'),
    claim(PLAN, r'\((\d+) overlap', FRAME, _stratum('mapped_overlap')),
    claim(PLAN, r'(\d+) proximity-only', FRAME, _stratum('proximity_only')),
    claim(PLAN, r'(\d+) non-overlap\)', FRAME, _stratum('mapped_non_overlap')),
    claim(PLAN, r'The frame is the ([\d,.]+) m of reference line', WINDOWS,
          lambda d: d['total_segment_length_m'], tolerance=0.05),
    claim(PIPELINE, r'([\d,]+) of 1,295\.5 m', WINDOWS, lambda d: d['analysed_length_per_anchor_m']),
    claim(PIPELINE, r'all (\d+) window rows', WINDOWS, lambda d: len(d['windows'])),
    claim(PIPELINE, r'(\d+) summaries', WINDOWS, lambda d: len(d['summaries'])),
    claim(PIPELINE, r'([\d,]+) comparison rows', COMPARISON, lambda d: len(d['results'])),
    claim(PIPELINE, r'frame contains (\w+) segments', FRAME,
          lambda d: NUMBER_WORDS[len(d['segments'])], word=True,
          rationale='the frame is five published segments, not a sample'),
    claim(BRIEF, r'the (\d+) committed tree points', TREES, lambda d: len(d['records'])),
    claim(WBGT, r'The (\d+) committed tree points', TREES, lambda d: len(d['records'])),
    claim(PLAN, r'\*\*([\d.]+) m\*\* step', EFFECT, lambda d: d['sampling_step_m'], tolerance=0.01),
    claim(PLAN, r'averaging \*\*([\d.]+) m\*\*', EFFECT, lambda d: d['canopy_runs']['mean_length_m'],
          tolerance=0.01, rationale='mean mapped-canopy run length'),
    claim(PLAN, r'between \*\*([\d.]+)%\*\* and', EFFECT,
          lambda d: d['estimate_quantiles']['2.5']*100, tolerance=0.01),
    claim(PLAN, r'and\s+\*\*([\d.]+)%\*\* \(2\.5th', EFFECT,
          lambda d: d['estimate_quantiles']['97.5']*100, tolerance=0.01),
    claim(PLAN, r'around the frame.s \*\*([\d.]+)%\*\*', EFFECT,
          lambda d: d['frame_prevalence']*100, tolerance=0.01),
    claim(PLAN, r'sampling fraction of \*\*([\d.]+)\*\*', EFFECT,
          lambda d: d['sampling_fraction'], tolerance=0.005),
    claim(PLAN, r'inflation near ([\d.]+)\*\*', EFFECT,
          lambda d: d['inflation_for_random_placement'], tolerance=0.05),
    # Stakeholder-facing numbers: the ones a reader acts on, so they are pinned too.
    claim('README.md', r'comparison shares (\d+)/10 trees', HEAT,
          lambda d: d['period_sensitivity']['top_ten_overlap']['seasonal_mean_vs_reference_day'],
          rationale='the second README statement of the same overlap'),
    claim('README.md', r'top tens share (\d+)/10', HEAT,
          lambda d: d['period_sensitivity']['top_ten_overlap']['seasonal_mean_vs_reference_day'],
          rationale='the README quotes the same overlap as the brief'),
    claim(BRIEF, r'shares \*\*(\d+)/10\*\* members', HEAT,
          lambda d: d['period_sensitivity']['top_ten_overlap']['seasonal_mean_vs_reference_day'],
          rationale='reference-day versus seasonal-mean top ten'),
    claim(BRIEF, r'assigns the 100 trees to \*\*(\d+) distinct cells\*\*', HEAT,
          lambda d: min(d['region_summary']['distinct_cells'], len(d['records'])),
          rationale='distinct 100 m cells, never more than the tree count'),
    claim(BRIEF, r'between the \*\*([\d.]+)th and', HEAT,
          lambda d: min(r['reference_percentile_in_season'] for r in d['records']), tolerance=0.01),
    claim(BRIEF, r'and ([\d.]+)th percentiles', HEAT,
          lambda d: max(r['reference_percentile_in_season'] for r in d['records']), tolerance=0.01),

    claim(BRIEF_MOBILITY, r'covers \*\*(\d+) of 100 trees\*\*', FLOW,
          lambda inputs: _mobility_statistic(inputs, 'matched'),
          also=(NEAREST, SENSITIVITY), rationale='trees with a measured counter'),
    claim(BRIEF_MOBILITY, r'only \*\*(five) distinct flow values\*\*', FLOW,
          lambda inputs: NUMBER_WORDS[_mobility_statistic(inputs, 'distinct_flow_values')],
          word=True, also=(NEAREST, SENSITIVITY),
          rationale='five counters means five distinct values'),
    claim(BRIEF_MOBILITY, r'Pearson \*r\* = [−-]([\d.]+)', FLOW,
          lambda inputs: _mobility_statistic(inputs, 'pearson'),
          tolerance=0.005, also=(NEAREST, SENSITIVITY),
          rationale='distance against assigned flow, recomputed'),
    claim(BRIEF_MOBILITY, r'Spearman \*rho\* = [−-]([\d.]+)', FLOW,
          lambda inputs: _mobility_statistic(inputs, 'spearman'),
          tolerance=0.005, also=(NEAREST, SENSITIVITY),
          rationale='rank association, recomputed'),
    claim(BRIEF_MOBILITY, r'gives \*\*(\d+) of 10\*\* in common', FLOW,
          lambda inputs: _mobility_statistic(inputs, 'daily_overlap_min'),
          also=(NEAREST, SENSITIVITY) + HISTORIES,
          rationale='per-day flow ranking against the weekly one'),
    claim(BRIEF_MOBILITY, r'\| CB1101 \| (\d+) \|', FLOW,
          lambda inputs, c='CB1101': _mobility_statistic(inputs, 'trees_of_'+c),
          also=(NEAREST, SENSITIVITY), rationale='sample trees served by CB1101'),
    claim(BRIEF_MOBILITY, r'\| CB1101 \| \d+ \| ([\d.]+) \|', FLOW,
          lambda inputs, c='CB1101': _mobility_statistic(inputs, 'mean_of_'+c),
          tolerance=0.001, also=(NEAREST, SENSITIVITY, 'data/brussels-bike-history-CB1101-2024-01.json'),
          rationale='mean 15-minute count at CB1101'),
    claim(BRIEF_MOBILITY, r'\| CB1142 \| (\d+) \|', FLOW,
          lambda inputs, c='CB1142': _mobility_statistic(inputs, 'trees_of_'+c),
          also=(NEAREST, SENSITIVITY), rationale='sample trees served by CB1142'),
    claim(BRIEF_MOBILITY, r'\| CB1142 \| \d+ \| ([\d.]+) \|', FLOW,
          lambda inputs, c='CB1142': _mobility_statistic(inputs, 'mean_of_'+c),
          tolerance=0.001, also=(NEAREST, SENSITIVITY, 'data/brussels-bike-history-CB1142-2024-01.json'),
          rationale='mean 15-minute count at CB1142'),
    claim(BRIEF_MOBILITY, r'\| CJM90 \| (\d+) \|', FLOW,
          lambda inputs, c='CJM90': _mobility_statistic(inputs, 'trees_of_'+c),
          also=(NEAREST, SENSITIVITY), rationale='sample trees served by CJM90'),
    claim(BRIEF_MOBILITY, r'\| CJM90 \| \d+ \| ([\d.]+) \|', FLOW,
          lambda inputs, c='CJM90': _mobility_statistic(inputs, 'mean_of_'+c),
          tolerance=0.001, also=(NEAREST, SENSITIVITY, 'data/brussels-bike-history-CJM90-2024-01.json'),
          rationale='mean 15-minute count at CJM90'),
    claim(BRIEF_MOBILITY, r'\| CB1143 \| (\d+) \|', FLOW,
          lambda inputs, c='CB1143': _mobility_statistic(inputs, 'trees_of_'+c),
          also=(NEAREST, SENSITIVITY), rationale='sample trees served by CB1143'),
    claim(BRIEF_MOBILITY, r'\| CB1143 \| \d+ \| ([\d.]+) \|', FLOW,
          lambda inputs, c='CB1143': _mobility_statistic(inputs, 'mean_of_'+c),
          tolerance=0.001, also=(NEAREST, SENSITIVITY, 'data/brussels-bike-history-CB1143-2024-01.json'),
          rationale='mean 15-minute count at CB1143'),
    claim(BRIEF_MOBILITY, r'\| CB2105 \| (\d+) \|', FLOW,
          lambda inputs, c='CB2105': _mobility_statistic(inputs, 'trees_of_'+c),
          also=(NEAREST, SENSITIVITY), rationale='sample trees served by CB2105'),
    claim(BRIEF_MOBILITY, r'\| CB2105 \| \d+ \| ([\d.]+) \|', FLOW,
          lambda inputs, c='CB2105': _mobility_statistic(inputs, 'mean_of_'+c),
          tolerance=0.001, also=(NEAREST, SENSITIVITY, 'data/brussels-bike-history-CB2105-2024-01.json'),
          rationale='mean 15-minute count at CB2105'),
    # Verified by recomputation this session; the table above them is deliberately not pinned
    # because no committed artifact holds it, and the brief now says so.
    claim(BRIEF, r'seasonal 90th percentile shares \*\*(\d+)/10\*\*', HEAT,
          lambda d: d['period_sensitivity']['top_ten_overlap']['seasonal_p90_vs_reference_day'],
          rationale='same-series aggregation, computed by the generator'),
    claim(BRIEF, r'at or above 26 °C shares \*\*(\d+)/10\*\*', HEAT,
          lambda d: d['period_sensitivity']['top_ten_overlap']['hot_days_vs_reference_day'],
          rationale='same-series aggregation, computed by the generator'),
    claim(BRIEF, r'compared with (four) ERA5 cells', SEASON,
          lambda d: NUMBER_WORDS[len(d['cells'])], word=True,
          rationale='ERA5 grid cells covering the tree sample'),
    claim(BRIEF, r'WBGT spans \*\*([\d.]+)–', HEAT, lambda d: d['region_summary']['reference_date_wbgt_min_c']),
    claim(BRIEF, r'–([\d.]+) °C\*\* \(1\.39', HEAT,
          lambda d: d['region_summary']['reference_date_wbgt_max_c']),
    claim(BRIEF, r'\(([\d.]+) °C across the sample\)', HEAT,
          lambda d: d['region_summary']['reference_date_wbgt_spread_c']),
    claim(BRIEF, r'is ([\d.]+) for the seasonal mean', DIAGNOSTICS_JSON,
          lambda d, m='seasonal_mean_wbgt_c': _temporal_spearman(d, m, 'tree'),
          tolerance=0.001, rationale='the rank agreement the heat-period choice rests on'),
    claim(BRIEF, r'([\d.]+) for hot-day count', DIAGNOSTICS_JSON,
          lambda d, m='hot_days_per_season': _temporal_spearman(d, m, 'tree'),
          tolerance=0.001),
    claim(BRIEF, r'and ([\d.]+) for the 90th percentile', DIAGNOSTICS_JSON,
          lambda d, m='seasonal_p90_wbgt_c': _temporal_spearman(d, m, 'tree'),
          tolerance=0.001),
    claim(BRIEF, r'counts about ([\d.]+)[\u2013-]', SEASON,
          lambda d: d['region_summary']['hot_days_per_season_min'], tolerance=0.05,
          rationale='the threshold statistic the brief asks stakeholders about'),
    claim(BRIEF, r'counts about [\d.]+[\u2013-]([\d.]+) JJA days', SEASON,
          lambda d: d['region_summary']['hot_days_per_season_max'], tolerance=0.05),
    claim(BRIEF, r'step is about (\d+) km north', SEASON,
          lambda d, w='ns': _grid_note(d, w)),
    claim(BRIEF, r'and (\d+) km east\u2013west', SEASON,
          lambda d, w='ew': _grid_note(d, w)),
    claim(BRIEF, r'daily \*\*(\d+) m\*\* WBGT archive', HEAT,
          lambda d: d['grid']['step_metres']),
    claim(BRIEF, r'archive for \*\*(\d+)[\u2013-]', HEAT,
          lambda d: d['window']['start_year']),
    claim(BRIEF, r'archive for \*\*\d+[\u2013-](\d+)\*\*', HEAT,
          lambda d: d['window']['end_year']),
    claim(BRIEF, r'round-number (\d+) \u00b0C apparent-temperature threshold', SEASON,
          lambda d, w='hot': _season_threshold(d, w)),
    claim(BRIEF, r'seasonal mean spans \*\*([\d.]+)–', HEAT,
          lambda d: d['region_summary']['seasonal_mean_wbgt_min_c']),
    claim(BRIEF, r'–([\d.]+) °C\*\* \(1\.41', HEAT,
          lambda d: d['region_summary']['seasonal_mean_wbgt_max_c']),
    claim(BRIEF, r'\(([\d.]+) °C\)\. It resolves', HEAT,
          lambda d: d['region_summary']['seasonal_mean_wbgt_spread_c']),
    claim(ANALYSIS, r'Records analyzed: (\d+) of', TREES, lambda d: len(d['records'])),
    claim(ANALYSIS, r'of ([\d,]+) managed-tree records', TREES, lambda d: d['source']),
    claim(DOCS_REVIEW, r'sampled values range from (\d+) to 88', TREE_HEAT,
          lambda d: min(r['heat_pixel'] for r in d['records']),
          rationale='the same sampled range the review quotes'),
    claim(DOCS_REVIEW, r'sampled values range from 51 to (\d+)', TREE_HEAT,
          lambda d: max(r['heat_pixel'] for r in d['records'])),
    claim(ANALYSIS, r'not °C\): min (\d+)', TREE_HEAT, lambda d: min(r['heat_pixel'] for r in d['records'])),
    claim(ANALYSIS, r'median ([\d.]+), max', TREE_HEAT,
          lambda d: statistics.median(r['heat_pixel'] for r in d['records']), tolerance=0.05),
    claim(ANALYSIS, r'median [\d.]+, max (\d+)', TREE_HEAT,
          lambda d: max(r['heat_pixel'] for r in d['records'])),
    claim(ANALYSIS, r'Counter distance: min ([\d.]+) m', NEAREST,
          lambda d: min(r['nearest_counter_distance_m'] for r in d['records'])),
    claim(ANALYSIS, r'min [\d.]+ m, median ([\d.]+) m', NEAREST,
          lambda d: statistics.median(r['nearest_counter_distance_m'] for r in d['records']),
          tolerance=0.06, rationale='a mid-pair median of 490.55, so 490.5 and 490.6 are both fair'),
    claim(ANALYSIS, r'median [\d.]+ m, max ([\d.]+) m', NEAREST,
          lambda d: max(r['nearest_counter_distance_m'] for r in d['records'])),
    claim(ANALYSIS, r'([\d,]+) fifteen-minute observations', HISTORIES[0],
          lambda inputs: sum(len(inputs[path]['records']) for path in HISTORIES), also=HISTORIES[1:]),
    claim(ANALYSIS, r'mean count ([\d.]+), maximum', HISTORIES[0],
          lambda inputs: round(sum(row['count'] for path in HISTORIES for row in inputs[path]['records'])
                               /sum(len(inputs[path]['records']) for path in HISTORIES), 1),
          tolerance=0.05, also=HISTORIES[1:]),
    claim(ANALYSIS, r'mean count [\d.]+, maximum (\d+)', HISTORIES[0],
          lambda inputs: max(row['count'] for path in HISTORIES for row in inputs[path]['records']),
          also=HISTORIES[1:]),
    claim(DIAGNOSTICS, r'\| seasonal_mean_wbgt_c \| tree \| (\d+)/10', DIAGNOSTICS_JSON,
          lambda d, m='seasonal_mean_wbgt_c': _temporal_overlap(d, m, 'tree'),
          rationale='tree-level overlap, also recorded by the WBGT context generator'),
    claim(DIAGNOSTICS, r'\| seasonal_mean_wbgt_c \| cell \| (\d+)/10', DIAGNOSTICS_JSON,
          lambda d, m='seasonal_mean_wbgt_c': _temporal_overlap(d, m, 'cell'),
          rationale='cell-level overlap at the top quarter of cells'),
    claim(DIAGNOSTICS, rf'\| seasonal_mean_wbgt_c \| tree \| \d+/10 \| [\d, ]+ \| \d+ \| [\d.]+ \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, m='seasonal_mean_wbgt_c': _temporal_spearman(d, m, 'tree'),
          tolerance=0.001, rationale='tree-level Spearman for seasonal_mean_wbgt_c'),
    claim(DIAGNOSTICS, r'\| seasonal_p90_wbgt_c \| tree \| (\d+)/10', DIAGNOSTICS_JSON,
          lambda d, m='seasonal_p90_wbgt_c': _temporal_overlap(d, m, 'tree'),
          rationale='tree-level overlap, also recorded by the WBGT context generator'),
    claim(DIAGNOSTICS, r'\| seasonal_p90_wbgt_c \| cell \| (\d+)/10', DIAGNOSTICS_JSON,
          lambda d, m='seasonal_p90_wbgt_c': _temporal_overlap(d, m, 'cell'),
          rationale='cell-level overlap at the top quarter of cells'),
    claim(DIAGNOSTICS, rf'\| seasonal_p90_wbgt_c \| tree \| \d+/10 \| [\d, ]+ \| \d+ \| [\d.]+ \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, m='seasonal_p90_wbgt_c': _temporal_spearman(d, m, 'tree'),
          tolerance=0.001, rationale='tree-level Spearman for seasonal_p90_wbgt_c'),
    claim(DIAGNOSTICS, r'\| hot_days_per_season \| tree \| (\d+)/10', DIAGNOSTICS_JSON,
          lambda d, m='hot_days_per_season': _temporal_overlap(d, m, 'tree'),
          rationale='tree-level overlap, also recorded by the WBGT context generator'),
    claim(DIAGNOSTICS, r'\| hot_days_per_season \| cell \| (\d+)/10', DIAGNOSTICS_JSON,
          lambda d, m='hot_days_per_season': _temporal_overlap(d, m, 'cell'),
          rationale='cell-level overlap at the top quarter of cells'),
    claim(DIAGNOSTICS, rf'\| hot_days_per_season \| tree \| \d+/10 \| [\d, ]+ \| \d+ \| [\d.]+ \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, m='hot_days_per_season': _temporal_spearman(d, m, 'tree'),
          tolerance=0.001, rationale='tree-level Spearman for hot_days_per_season'),
    claim(SPEC, r'finds (\d+) of 100 points at or above', SENSITIVITY,
          lambda d: _quadrant(d['balanced_screening']),
          rationale='third-quartile quadrant count, recomputed from the committed scores'),
    claim(ANALYSIS, r'quadrant: (\d+) point at or above', SENSITIVITY,
          lambda d: _quadrant(d['balanced_screening']),
          rationale='the analysis document and the spec must agree with the scores'),
    claim(WBGT, r'(\d+) distinct 100 m cells', HEAT,
          lambda d: min(d['region_summary']['distinct_cells'], len(d['records'])),
          rationale='the effective sample the method doc relies on'),
    # The ortho-consistency check is the only alignment evidence that survived review, so
    # its verdict numbers are pinned like the heat and canopy ones.
    claim(IMAGERY, r'Within each of (\d+) fixed windows', ORTHO,
          lambda d: d['summary']['windows']),
    claim(IMAGERY, r'stable to a median of\s+\*\*([\d.]+) m\*\*', ORTHO,
          lambda d: d['summary']['median_resolving_band_spread_m'], tolerance=0.005,
          rationale='resolving-band spread, not a standard error'),
    claim(IMAGERY, r'ranges from \*\*([\d.]+) m to 5\.43 m', ORTHO,
          lambda d: d['summary']['full_band_offset_m_range'][0], tolerance=0.005),
    claim(IMAGERY, r'ranges from \*\*0\.55 m to ([\d.]+) m', ORTHO,
          lambda d: d['summary']['full_band_offset_m_range'][1], tolerance=0.005),
    claim(IMAGERY, r'ranges from \*\*0\.55 m to 5\.43 m \(median ([\d.]+) m\)\*\*', ORTHO,
          lambda d: d['summary']['median_full_band_offset_m'], tolerance=0.005),
    claim(IMAGERY, r'\| 2 \(full, above 1 m\) \| \*\*(\d+) of 15\*\*', ORTHO,
          lambda d, k='2_bands_through_1m': _ortho_band(d, k, 'consistent_windows')),
    claim(IMAGERY, r'\| 3 \(\+ above 2 m\) \| (\d+) of 15', ORTHO,
          lambda d, k='3_bands_through_2m': _ortho_band(d, k, 'consistent_windows')),
    claim(IMAGERY, r'\| 4 \(\+ above 5 m\) \| (\d+) of 15', ORTHO,
          lambda d, k='4_bands_through_5m': _ortho_band(d, k, 'consistent_windows')),
    claim(IMAGERY, r'\| 5 \(\+ above 20 m\) \| (\d+) of 15', ORTHO,
          lambda d, k='5_bands_through_20m': _ortho_band(d, k, 'consistent_windows')),
    claim(IMAGERY, r'\| 2 \(full, above 1 m\) \| \*\*15 of 15\*\* \| ([\d.]+) m \|', ORTHO,
          lambda d, k='2_bands_through_1m': _ortho_band(d, k, 'median_spread_m'),
          tolerance=0.005),
    claim(IMAGERY, r'\| 3 \(\+ above 2 m\) \| 13 of 15 \| ([\d.]+) m \|', ORTHO,
          lambda d, k='3_bands_through_2m': _ortho_band(d, k, 'median_spread_m'),
          tolerance=0.005),
    claim(IMAGERY, r'\| 4 \(\+ above 5 m\) \| 5 of 15 \| ([\d.]+) m \|', ORTHO,
          lambda d, k='4_bands_through_5m': _ortho_band(d, k, 'median_spread_m'),
          tolerance=0.005),
    claim(IMAGERY, r'\| 5 \(\+ above 20 m\) \| 0 of 15 \| ([\d.]+) m \|', ORTHO,
          lambda d, k='5_bands_through_20m': _ortho_band(d, k, 'median_spread_m'),
          tolerance=0.01),
    claim(IMAGERY, r'\| 2 \(full, above 1 m\) \| \*\*15 of 15\*\* \| [\d.]+ m \| ([\d.]+) m \|',
          ORTHO, lambda d, k='2_bands_through_1m': _ortho_band(d, k, 'max_spread_m'),
          tolerance=0.005),
    claim(IMAGERY, r'\| 3 \(\+ above 2 m\) \| 13 of 15 \| [\d.]+ m \| ([\d.]+) m \|',
          ORTHO, lambda d, k='3_bands_through_2m': _ortho_band(d, k, 'max_spread_m'),
          tolerance=0.005),
    claim(IMAGERY, r'\| 4 \(\+ above 5 m\) \| 5 of 15 \| [\d.]+ m \| ([\d.]+) m \|',
          ORTHO, lambda d, k='4_bands_through_5m': _ortho_band(d, k, 'max_spread_m'),
          tolerance=0.005),
    claim(IMAGERY, r'\| 5 \(\+ above 20 m\) \| 0 of 15 \| [\d.]+ m \| ([\d.]+) m \|',
          ORTHO, lambda d, k='5_bands_through_20m': _ortho_band(d, k, 'max_spread_m'),
          tolerance=0.01),
    claim(IMAGERY, r'resolving bands \| \*\*([\d.]+) m\*\*', ORTHO,
          lambda d: d['degraded_max_error_resolving_band_m'], tolerance=0.0005,
          rationale='degraded control through the band path, not only the estimator'),
    claim(IMAGERY, r'wide bands \(5 m, 20 m\) \| \*\*([\d.]+) m\*\*', ORTHO,
          lambda d: d['degraded_max_error_wide_band_m'], tolerance=0.001),
    claim(IMAGERY, r'normalised correlation ([\d.]+)[\u2013-]', ORTHO,
          lambda d: d['summary']['full_band_ncc_range'][0], tolerance=0.005),
    claim(IMAGERY, r'normalised correlation [\d.]+[\u2013-]([\d.]+)', ORTHO,
          lambda d: d['summary']['full_band_ncc_range'][1], tolerance=0.005),
    claim(IMAGERY, r'peak ratios ([\d.]+)[\u2013-]', ORTHO,
          lambda d: d['summary']['phase_peak_ratio_range'][0], tolerance=0.005),
    claim(IMAGERY, r'peak ratios [\d.]+[\u2013-]([\d.]+) with', ORTHO,
          lambda d: d['summary']['phase_peak_ratio_range'][1], tolerance=0.005),
    claim(IMAGERY, r'with (\d+) of 15\nwindows at', ORTHO,
          lambda d: d['summary']['phase_at_search_bound']),
    # The stress-test table is the audit's consequential result: segment 266's overlap
    # moves by tens of points under fixed 2 m translations, and the zeros elsewhere are
    # load-bearing too -- a drift to non-zero would change the sensitivity story.
    claim(AUDIT, r'\| 266 \| ([\d.]+)%', AUDIT_JSON,
          lambda d, g=266: _audit_original(d, g), tolerance=0.05),
    claim(AUDIT, r'\| 266 \| [\d.]+% \| ([\d.]+)[\u2013-]', AUDIT_JSON,
          lambda d, g=266, s=_AUDIT_2M: min(_audit_scenarios(d, g, s)), tolerance=0.05),
    claim(AUDIT, r'\| 266 \| [\d.]+% \| [\d.]+[\u2013-]([\d.]+)%', AUDIT_JSON,
          lambda d, g=266, s=_AUDIT_2M: max(_audit_scenarios(d, g, s)), tolerance=0.05),
    claim(AUDIT, r'\| 266 \| [\d.]+% \| [\d.]+[\u2013-][\d.]+% \| ([\d.]+)[\u2013-]',
          AUDIT_JSON, lambda d, g=266, s=_AUDIT_5M: min(_audit_scenarios(d, g, s)),
          tolerance=0.05),
    claim(AUDIT, r'\| 266 \| [\d.]+% \| [\d.]+[\u2013-][\d.]+% \| [\d.]+[\u2013-]([\d.]+)%',
          AUDIT_JSON, lambda d, g=266, s=_AUDIT_5M: max(_audit_scenarios(d, g, s)),
          tolerance=0.05),
    claim(AUDIT, r'\| 5630 \| ([\d.]+)%', AUDIT_JSON,
          lambda d, g=5630: _audit_original(d, g), tolerance=0.05),
    claim(AUDIT, r'\| 5630 \| [\d.]+% \| ([\d.]+)[\u2013-]', AUDIT_JSON,
          lambda d, g=5630, s=_AUDIT_2M: min(_audit_scenarios(d, g, s)), tolerance=0.05),
    claim(AUDIT, r'\| 5630 \| [\d.]+% \| [\d.]+[\u2013-]([\d.]+)%', AUDIT_JSON,
          lambda d, g=5630, s=_AUDIT_2M: max(_audit_scenarios(d, g, s)), tolerance=0.05),
    claim(AUDIT, r'\| 5630 \| [\d.]+% \| [\d.]+[\u2013-][\d.]+% \| ([\d.]+)[\u2013-]',
          AUDIT_JSON, lambda d, g=5630, s=_AUDIT_5M: min(_audit_scenarios(d, g, s)),
          tolerance=0.05),
    claim(AUDIT, r'\| 5630 \| [\d.]+% \| [\d.]+[\u2013-][\d.]+% \| [\d.]+[\u2013-]([\d.]+)%',
          AUDIT_JSON, lambda d, g=5630, s=_AUDIT_5M: max(_audit_scenarios(d, g, s)),
          tolerance=0.05),
    claim(AUDIT, r'\| 5634 \| ([\d.]+)%', AUDIT_JSON,
          lambda d, g=5634: _audit_original(d, g), tolerance=0.05),
    claim(AUDIT, r'\| 5634 \| [\d.]+% \| ([\d.]+)[\u2013-]', AUDIT_JSON,
          lambda d, g=5634, s=_AUDIT_2M: min(_audit_scenarios(d, g, s)), tolerance=0.05),
    claim(AUDIT, r'\| 5634 \| [\d.]+% \| [\d.]+[\u2013-]([\d.]+)%', AUDIT_JSON,
          lambda d, g=5634, s=_AUDIT_2M: max(_audit_scenarios(d, g, s)), tolerance=0.05),
    claim(AUDIT, r'\| 5634 \| [\d.]+% \| [\d.]+[\u2013-][\d.]+% \| ([\d.]+)[\u2013-]',
          AUDIT_JSON, lambda d, g=5634, s=_AUDIT_5M: min(_audit_scenarios(d, g, s)),
          tolerance=0.05),
    claim(AUDIT, r'\| 5634 \| [\d.]+% \| [\d.]+[\u2013-][\d.]+% \| [\d.]+[\u2013-]([\d.]+)%',
          AUDIT_JSON, lambda d, g=5634, s=_AUDIT_5M: max(_audit_scenarios(d, g, s)),
          tolerance=0.05),
    claim(AUDIT, r'\| 5642 \| ([\d.]+)%', AUDIT_JSON,
          lambda d, g=5642: _audit_original(d, g), tolerance=0.05),
    claim(AUDIT, r'\| 5642 \| [\d.]+% \| ([\d.]+)[\u2013-]', AUDIT_JSON,
          lambda d, g=5642, s=_AUDIT_2M: min(_audit_scenarios(d, g, s)), tolerance=0.05),
    claim(AUDIT, r'\| 5642 \| [\d.]+% \| [\d.]+[\u2013-]([\d.]+)%', AUDIT_JSON,
          lambda d, g=5642, s=_AUDIT_2M: max(_audit_scenarios(d, g, s)), tolerance=0.05),
    claim(AUDIT, r'\| 5642 \| [\d.]+% \| [\d.]+[\u2013-][\d.]+% \| ([\d.]+)[\u2013-]',
          AUDIT_JSON, lambda d, g=5642, s=_AUDIT_5M: min(_audit_scenarios(d, g, s)),
          tolerance=0.05),
    claim(AUDIT, r'\| 5642 \| [\d.]+% \| [\d.]+[\u2013-][\d.]+% \| [\d.]+[\u2013-]([\d.]+)%',
          AUDIT_JSON, lambda d, g=5642, s=_AUDIT_5M: max(_audit_scenarios(d, g, s)),
          tolerance=0.05),
    claim(AUDIT, r'\| 5643 \| ([\d.]+)%', AUDIT_JSON,
          lambda d, g=5643: _audit_original(d, g), tolerance=0.05),
    claim(AUDIT, r'\| 5643 \| [\d.]+% \| ([\d.]+)[\u2013-]', AUDIT_JSON,
          lambda d, g=5643, s=_AUDIT_2M: min(_audit_scenarios(d, g, s)), tolerance=0.05),
    claim(AUDIT, r'\| 5643 \| [\d.]+% \| [\d.]+[\u2013-]([\d.]+)%', AUDIT_JSON,
          lambda d, g=5643, s=_AUDIT_2M: max(_audit_scenarios(d, g, s)), tolerance=0.05),
    claim(AUDIT, r'\| 5643 \| [\d.]+% \| [\d.]+[\u2013-][\d.]+% \| ([\d.]+)[\u2013-]',
          AUDIT_JSON, lambda d, g=5643, s=_AUDIT_5M: min(_audit_scenarios(d, g, s)),
          tolerance=0.05),
    claim(AUDIT, r'\| 5643 \| [\d.]+% \| [\d.]+[\u2013-][\d.]+% \| [\d.]+[\u2013-]([\d.]+)%',
          AUDIT_JSON, lambda d, g=5643, s=_AUDIT_5M: max(_audit_scenarios(d, g, s)),
          tolerance=0.05),
    # The conclusion restates 266's row; pin it where the stop/go reasoning leans on it.
    claim(AUDIT, r'overlap changes from \*\*([\d.]+)%\*\*', AUDIT_JSON,
          lambda d, g=266: _audit_original(d, g), tolerance=0.05,
          rationale='the sentence that rules out reporting 31.4% as robust'),
    claim(AUDIT, r'source line to \*\*([\d.]+)[\u2013-]', AUDIT_JSON,
          lambda d, g=266, s=_AUDIT_2M: min(_audit_scenarios(d, g, s)), tolerance=0.05),
    claim(AUDIT, r'source line to \*\*[\d.]+[\u2013-]([\d.]+)%\*\*', AUDIT_JSON,
          lambda d, g=266, s=_AUDIT_2M: max(_audit_scenarios(d, g, s)), tolerance=0.05),
    # The recomputation sentence: only the published interval values have JSON backing.
    # The point-method columns (13.98/13.87, 0.35 pp) live only in checkpoint prose.
    claim(CHECKPOINT, r'\| Direct overlap \| ([\d.]+)%', COMPARISON,
          lambda d: _pooled_overlap(d, 'trees', 0), tolerance=0.005,
          rationale='length-weighted trees-only buffer-0 share over 1,295.5 m'),
    claim(CHECKPOINT, r'Proximity-only \(0-5 m, not overlapping\) \| ([\d.]+)%', COMPARISON,
          lambda d: _pooled_overlap(d, 'trees', 5) - _pooled_overlap(d, 'trees', 0),
          tolerance=0.005, rationale='within-5m-but-not-overlapping is buffer 5 minus buffer 0'),
    claim(CHECKPOINT, r'\| Mapped non-overlap \| ([\d.]+)%', COMPARISON,
          lambda d: 100 - _pooled_overlap(d, 'trees', 5), tolerance=0.01,
          rationale='exact value 53.6329 rounds to 53.63; the record says 53.64'),
    claim(CHECKPOINT, r'gid 266 [\d.]+% vs ([\d.]+)%', COMPARISON,
          lambda d, g=266: _comparison_gid(d, g), tolerance=0.005),
    claim(CHECKPOINT, r'gid 5642 [\d.]+% vs ([\d.]+)%', COMPARISON,
          lambda d, g=5642: _comparison_gid(d, g), tolerance=0.005),
    claim(AUDIT, r'against the published ([\d.]+)%', COMPARISON,
          lambda d: _pooled_overlap(d, 'trees', 0), tolerance=0.005,
          rationale='the published figure is the trees-only buffer-0 pool, not all classes'),
    # The audit restates the ortho verdict and the segment-date weights; pin the repeats so
    # the two documents cannot drift apart unnoticed. The 3 mm resolving-band figure is
    # skipped: the claim ledger compares quoted floats, and millimetres need a unit the
    # ledger does not have. The 1.20 m end of the taper history has no JSON backing.
    claim(AUDIT, r'stable to a median of \*\*([\d.]+) m\*\* across', ORTHO,
          lambda d: d['summary']['median_resolving_band_spread_m'], tolerance=0.005),
    claim(AUDIT, r'\(worst ([\d.]+) m; \d+ of 15 windows within', ORTHO,
          lambda d: d['summary']['max_resolving_band_spread_m'], tolerance=0.005),
    claim(AUDIT, r'\(worst [\d.]+ m; (\d+) of 15 windows within', ORTHO,
          lambda d: d['summary']['consistent_windows']),
    claim(AUDIT, r'The offset itself is \*\*([\d.]+)[\u2013-]', ORTHO,
          lambda d: d['summary']['full_band_offset_m_range'][0], tolerance=0.005),
    claim(AUDIT, r'The offset itself is \*\*[\d.]+[\u2013-]([\d.]+) m', ORTHO,
          lambda d: d['summary']['full_band_offset_m_range'][1], tolerance=0.005),
    claim(AUDIT, r'The offset itself is \*\*[\d.]+[\u2013-][\d.]+ m \(median ([\d.]+) m\)\*\*',
          ORTHO, lambda d: d['summary']['median_full_band_offset_m'], tolerance=0.005),
    claim(AUDIT, r'Full-band correlation ([\d.]+)[\u2013-]', ORTHO,
          lambda d: d['summary']['full_band_ncc_range'][0], tolerance=0.005),
    claim(AUDIT, r'Full-band correlation [\d.]+[\u2013-]([\d.]*\d)\.', ORTHO,
          lambda d: d['summary']['full_band_ncc_range'][1], tolerance=0.005),
    claim(AUDIT, r'peak-to-shoulder ratios ([\d.]+)[\u2013-]', ORTHO,
          lambda d, w='min': _ortho_ratio_bound(d, w), tolerance=0.005,
          rationale='least-sharp of the four per-band medians'),
    claim(AUDIT, r'peak-to-shoulder ratios [\d.]+[\u2013-]([\d.]+)', ORTHO,
          lambda d, w='max': _ortho_ratio_bound(d, w), tolerance=0.005,
          rationale='sharpest of the four per-band medians'),
    claim(AUDIT, r'moved the median magnitude from 1\.20 m to ([\d.]+) m', ORTHO,
          lambda d: d['summary']['median_full_band_offset_m'], tolerance=0.005),
    claim(AUDIT, r'moves the wide bands by ([\d.]+) m', ORTHO,
          lambda d: d['degraded_max_error_wide_band_m'], tolerance=0.001),
    claim(AUDIT, r'gid 5642 runs [\u2212-]([\d.]+) \u2192', ORTHO,
          lambda d, g=5642: abs(_ortho_window(d, g, 'at10')['offset_m']['full_band_east_m']),
          tolerance=0.005, rationale='magnitude pinned here; the sign lives in the glyph'),
    claim(AUDIT, r'\u2192 \+([\d.]+) \u2192', ORTHO,
          lambda d, g=5642: _ortho_window(d, g, 'at50')['offset_m']['full_band_east_m'],
          tolerance=0.005),
    claim(AUDIT, r'\u2192 [\u2212-]([\d.]+) m east over', ORTHO,
          lambda d, g=5642: abs(_ortho_window(d, g, 'at90')['offset_m']['full_band_east_m']),
          tolerance=0.005, rationale='magnitude pinned here; the sign lives in the glyph'),
    claim(AUDIT, r'gid 266 ([\d.]+) \u2192', ORTHO,
          lambda d, g=266: _ortho_window(d, g, 'at10')['offset_m']['full_band_magnitude_m'],
          tolerance=0.005),
    claim(AUDIT, r'gid 266 [\d.]+ \u2192 ([\d.]+) \u2192', ORTHO,
          lambda d, g=266: _ortho_window(d, g, 'at50')['offset_m']['full_band_magnitude_m'],
          tolerance=0.005),
    claim(AUDIT, r'gid 266 [\d.]+ \u2192 [\d.]+ \u2192 ([\d.]+) m\.', ORTHO,
          lambda d, g=266: _ortho_window(d, g, 'at90')['offset_m']['full_band_magnitude_m'],
          tolerance=0.005),
    # The temporal weights behind "only gid 266 predates the canopy year".
    claim(AUDIT, r'\(1,295\.5 m\): ([\d.]+)% \(gid 266\) starts in 2017', COMPARISON,
          lambda d: _date_share(d, '2017'), tolerance=0.05),
    claim(AUDIT, r'\*\*([\d.]+)% \(gid 5630, 5642, 5643\) starts in June 2021', COMPARISON,
          lambda d: _date_share(d, '2021-06'), tolerance=0.05),
    claim(AUDIT, r'and ([\d.]+)% \(gid 5634\) starts in June 2022', COMPARISON,
          lambda d: _date_share(d, '2022'), tolerance=0.05),
    claim(AUDIT, r'the other four segments \u2014 ([\d.]+)% of analysed length', COMPARISON,
          lambda d: 100 - _date_share(d, '2017'), tolerance=0.1,
          rationale='sums the rounded published components 41.8+14.6; the exact pool is 56.4951'),
    # The per-gid results table: magnitude ranges, worst resolving-band spreads, NCC ranges.
    claim(IMAGERY, r'\| 266 \| [^|]*\| ([\d.]+)[\u2013-]', ORTHO,
          lambda d, g=266: min(_gid_values(d, g, 'magnitude')), tolerance=0.005),
    claim(IMAGERY, r'\| 266 \| [^|]*\| [\d.]+[\u2013-]([\d.]+) m \|', ORTHO,
          lambda d, g=266: max(_gid_values(d, g, 'magnitude')), tolerance=0.005),
    claim(IMAGERY, r'\| 266 \| [^|]*\| [^|]*\| \u2264([\d.]+) m \|', ORTHO,
          lambda d, g=266: max(_gid_values(d, g, 'spread')), tolerance=0.005),
    claim(IMAGERY, r'\| 266 \| [^|]*\| [^|]*\| [^|]*\| ([\d.]+)[\u2013-]', ORTHO,
          lambda d, g=266: min(_gid_values(d, g, 'ncc')), tolerance=0.005),
    claim(IMAGERY, r'\| 266 \| [^|]*\| [^|]*\| [^|]*\| [\d.]+[\u2013-]([\d.]+) \|',
          ORTHO, lambda d, g=266: max(_gid_values(d, g, 'ncc')), tolerance=0.005),
    claim(IMAGERY, r'\| 5630 \| [^|]*\| ([\d.]+)[\u2013-]', ORTHO,
          lambda d, g=5630: min(_gid_values(d, g, 'magnitude')), tolerance=0.005),
    claim(IMAGERY, r'\| 5630 \| [^|]*\| [\d.]+[\u2013-]([\d.]+) m \|', ORTHO,
          lambda d, g=5630: max(_gid_values(d, g, 'magnitude')), tolerance=0.005),
    claim(IMAGERY, r'\| 5630 \| [^|]*\| [^|]*\| \u2264([\d.]+) m \|', ORTHO,
          lambda d, g=5630: max(_gid_values(d, g, 'spread')), tolerance=0.005),
    claim(IMAGERY, r'\| 5630 \| [^|]*\| [^|]*\| [^|]*\| ([\d.]+)[\u2013-]', ORTHO,
          lambda d, g=5630: min(_gid_values(d, g, 'ncc')), tolerance=0.005),
    claim(IMAGERY, r'\| 5630 \| [^|]*\| [^|]*\| [^|]*\| [\d.]+[\u2013-]([\d.]+) \|',
          ORTHO, lambda d, g=5630: max(_gid_values(d, g, 'ncc')), tolerance=0.005),
    claim(IMAGERY, r'\| 5634 \| [^|]*\| ([\d.]+)[\u2013-]', ORTHO,
          lambda d, g=5634: min(_gid_values(d, g, 'magnitude')), tolerance=0.005),
    claim(IMAGERY, r'\| 5634 \| [^|]*\| [\d.]+[\u2013-]([\d.]+) m \|', ORTHO,
          lambda d, g=5634: max(_gid_values(d, g, 'magnitude')), tolerance=0.005),
    claim(IMAGERY, r'\| 5634 \| [^|]*\| [^|]*\| \u2264([\d.]+) m \|', ORTHO,
          lambda d, g=5634: max(_gid_values(d, g, 'spread')), tolerance=0.005),
    claim(IMAGERY, r'\| 5634 \| [^|]*\| [^|]*\| [^|]*\| ([\d.]+)[\u2013-]', ORTHO,
          lambda d, g=5634: min(_gid_values(d, g, 'ncc')), tolerance=0.005),
    claim(IMAGERY, r'\| 5634 \| [^|]*\| [^|]*\| [^|]*\| [\d.]+[\u2013-]([\d.]+) \|',
          ORTHO, lambda d, g=5634: max(_gid_values(d, g, 'ncc')), tolerance=0.005),
    claim(IMAGERY, r'\| 5642 \| [^|]*\| ([\d.]+)[\u2013-]', ORTHO,
          lambda d, g=5642: min(_gid_values(d, g, 'magnitude')), tolerance=0.005),
    claim(IMAGERY, r'\| 5642 \| [^|]*\| [\d.]+[\u2013-]([\d.]+) m \|', ORTHO,
          lambda d, g=5642: max(_gid_values(d, g, 'magnitude')), tolerance=0.005),
    claim(IMAGERY, r'\| 5642 \| [^|]*\| [^|]*\| \u2264([\d.]+) m \|', ORTHO,
          lambda d, g=5642: max(_gid_values(d, g, 'spread')), tolerance=0.005),
    claim(IMAGERY, r'\| 5642 \| [^|]*\| [^|]*\| [^|]*\| ([\d.]+)[\u2013-]', ORTHO,
          lambda d, g=5642: min(_gid_values(d, g, 'ncc')), tolerance=0.005),
    claim(IMAGERY, r'\| 5642 \| [^|]*\| [^|]*\| [^|]*\| [\d.]+[\u2013-]([\d.]+) \|',
          ORTHO, lambda d, g=5642: max(_gid_values(d, g, 'ncc')), tolerance=0.005),
    claim(IMAGERY, r'\| 5643 \| [^|]*\| ([\d.]+)[\u2013-]', ORTHO,
          lambda d, g=5643: min(_gid_values(d, g, 'magnitude')), tolerance=0.005),
    claim(IMAGERY, r'\| 5643 \| [^|]*\| [\d.]+[\u2013-]([\d.]+) m \|', ORTHO,
          lambda d, g=5643: max(_gid_values(d, g, 'magnitude')), tolerance=0.005),
    claim(IMAGERY, r'\| 5643 \| [^|]*\| [^|]*\| \u2264([\d.]+) m \|', ORTHO,
          lambda d, g=5643: max(_gid_values(d, g, 'spread')), tolerance=0.005),
    claim(IMAGERY, r'\| 5643 \| [^|]*\| [^|]*\| [^|]*\| ([\d.]+)[\u2013-]', ORTHO,
          lambda d, g=5643: min(_gid_values(d, g, 'ncc')), tolerance=0.005),
    claim(IMAGERY, r'\| 5643 \| [^|]*\| [^|]*\| [^|]*\| [\d.]+[\u2013-]([\d.]+) \|',
          ORTHO, lambda d, g=5643: max(_gid_values(d, g, 'ncc')), tolerance=0.005),
    # The Sample line restates the headline values in distinct phrasing; pin those.
    # Its NCC, phase-ratio and search-bound repeats are word-identical to the intro pins,
    # so the existing claims already cover the values if not their second occurrence.
    claim(IMAGERY, r'Sample: median magnitude \*\*([\d.]+) m\*\*', ORTHO,
          lambda d: d['summary']['median_full_band_offset_m'], tolerance=0.005),
    claim(IMAGERY, r'range ([\d.]+)[\u2013-][\d.]+ m; median', ORTHO,
          lambda d: d['summary']['full_band_offset_m_range'][0], tolerance=0.005),
    claim(IMAGERY, r'range [\d.]+[\u2013-]([\d.]+) m; median', ORTHO,
          lambda d: d['summary']['full_band_offset_m_range'][1], tolerance=0.005),
    claim(IMAGERY, r'median 2-band spread \*\*([\d.]+) m\*\*, worst', ORTHO,
          lambda d: d['summary']['median_resolving_band_spread_m'], tolerance=0.005),
    claim(IMAGERY, r'2-band spread \*\*[\d.]+ m\*\*, worst\s+([\d.]+) m', ORTHO,
          lambda d: d['summary']['max_resolving_band_spread_m'], tolerance=0.005),
    # The class definition the circularity argument stands on, as the source record states it.
    claim(CANDIDATES, r'normalised height \*\*([\d.]+)[\u2013-]', ZENODO,
          lambda d, w='min': _zenodo_class_bound(d, w)),
    claim(CANDIDATES, r'normalised height \*\*[\d.]+[\u2013-]([\d.]+) m\*\*', ZENODO,
          lambda d, w='max': _zenodo_class_bound(d, w)),
    claim(CANDIDATES, r'using NDVI \u2265 ([\d.]+)', ZENODO, _zenodo_ndvi),
    # The exploratory comparison record: per-gid cells plus the frame counts it states.
    claim(LOCALMD, r'\| 266 \| ([\d.]+) \|', LOCAL,
          lambda d, g=266: _local_cell(d, g, 0, 'length_m'), tolerance=0.05),
    claim(LOCALMD, r'\| 266 \| [\d.]+ \| ([\d.]+) \|', LOCAL,
          lambda d, g=266: _local_cell(d, g, 0), tolerance=0.05),
    claim(LOCALMD, r'\| 266 \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|', LOCAL,
          lambda d, g=266: _local_cell(d, g, 2), tolerance=0.05),
    claim(LOCALMD, r'\| 266 \| [\d.]+ \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|', LOCAL,
          lambda d, g=266: _local_cell(d, g, 5), tolerance=0.05),
    claim(LOCALMD, r'\| 266 \| [\d.]+ \| [\d.]+ \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|',
          LOCAL, lambda d, g=266: _local_cell(d, g, 0, 'longest_nonoverlap_m'),
          tolerance=0.05),
    claim(LOCALMD, r'\| 5630 \| ([\d.]+) \|', LOCAL,
          lambda d, g=5630: _local_cell(d, g, 0, 'length_m'), tolerance=0.05),
    claim(LOCALMD, r'\| 5630 \| [\d.]+ \| ([\d.]+) \|', LOCAL,
          lambda d, g=5630: _local_cell(d, g, 0), tolerance=0.05),
    claim(LOCALMD, r'\| 5630 \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|', LOCAL,
          lambda d, g=5630: _local_cell(d, g, 2), tolerance=0.05),
    claim(LOCALMD, r'\| 5630 \| [\d.]+ \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|', LOCAL,
          lambda d, g=5630: _local_cell(d, g, 5), tolerance=0.05),
    claim(LOCALMD, r'\| 5630 \| [\d.]+ \| [\d.]+ \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|',
          LOCAL, lambda d, g=5630: _local_cell(d, g, 0, 'longest_nonoverlap_m'),
          tolerance=0.05),
    claim(LOCALMD, r'\| 5634 \| ([\d.]+) \|', LOCAL,
          lambda d, g=5634: _local_cell(d, g, 0, 'length_m'), tolerance=0.05),
    claim(LOCALMD, r'\| 5634 \| [\d.]+ \| ([\d.]+) \|', LOCAL,
          lambda d, g=5634: _local_cell(d, g, 0), tolerance=0.05),
    claim(LOCALMD, r'\| 5634 \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|', LOCAL,
          lambda d, g=5634: _local_cell(d, g, 2), tolerance=0.05),
    claim(LOCALMD, r'\| 5634 \| [\d.]+ \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|', LOCAL,
          lambda d, g=5634: _local_cell(d, g, 5), tolerance=0.05),
    claim(LOCALMD, r'\| 5634 \| [\d.]+ \| [\d.]+ \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|',
          LOCAL, lambda d, g=5634: _local_cell(d, g, 0, 'longest_nonoverlap_m'),
          tolerance=0.05),
    claim(LOCALMD, r'\| 5642 \| ([\d.]+) \|', LOCAL,
          lambda d, g=5642: _local_cell(d, g, 0, 'length_m'), tolerance=0.05),
    claim(LOCALMD, r'\| 5642 \| [\d.]+ \| ([\d.]+) \|', LOCAL,
          lambda d, g=5642: _local_cell(d, g, 0), tolerance=0.05),
    claim(LOCALMD, r'\| 5642 \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|', LOCAL,
          lambda d, g=5642: _local_cell(d, g, 2), tolerance=0.05),
    claim(LOCALMD, r'\| 5642 \| [\d.]+ \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|', LOCAL,
          lambda d, g=5642: _local_cell(d, g, 5), tolerance=0.05),
    claim(LOCALMD, r'\| 5642 \| [\d.]+ \| [\d.]+ \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|',
          LOCAL, lambda d, g=5642: _local_cell(d, g, 0, 'longest_nonoverlap_m'),
          tolerance=0.05),
    claim(LOCALMD, r'\| 5643 \| ([\d.]+) \|', LOCAL,
          lambda d, g=5643: _local_cell(d, g, 0, 'length_m'), tolerance=0.05),
    claim(LOCALMD, r'\| 5643 \| [\d.]+ \| ([\d.]+) \|', LOCAL,
          lambda d, g=5643: _local_cell(d, g, 0), tolerance=0.05),
    claim(LOCALMD, r'\| 5643 \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|', LOCAL,
          lambda d, g=5643: _local_cell(d, g, 2), tolerance=0.05),
    claim(LOCALMD, r'\| 5643 \| [\d.]+ \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|', LOCAL,
          lambda d, g=5643: _local_cell(d, g, 5), tolerance=0.05),
    claim(LOCALMD, r'\| 5643 \| [\d.]+ \| [\d.]+ \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|',
          LOCAL, lambda d, g=5643: _local_cell(d, g, 0, 'longest_nonoverlap_m'),
          tolerance=0.05),
    claim(LOCALMD, r'All (\d+) cycling records in the frame were retrieved', LOCAL,
          lambda d: d['selection']['response_count']),
    claim(LOCALMD, r'separate WFS count confirmed (\d+)', LOCAL,
          lambda d: d['selection']['count_only_number_matched']),
    claim(LOCALMD, r'(\w+) met the rules', LOCAL,
          lambda d: NUMBER_WORDS[d['sample_size']].capitalize(), word=True,
          rationale='sentence-initial capital; five published segments, not a sample'),
    claim(LOCALMD, r'([\d,]+) intersecting vegetation polygons were cross-checked', LOCAL,
          lambda d: d['extraction_polygon_count']),
    claim(LOCALMD, r'scan of ([\d,]+) source records', LOCAL,
          lambda d: d['source_records_scanned']),
    claim(LOCALMD, r'The (\d+) invalid tree/high-shrub polygons', LOCAL,
          lambda d: sum(d['invalid_selected_classes'].values()),
          rationale='41 class-4 plus 41 class-3 repairs, no area change'),
    # The method doc's parameters, as the season artifact records them.
    claim(HMETHOD, r'giving (\d+) days per year and \d+ seasonal days', SEASON,
          lambda d: d['season']['season_days_per_year']),
    claim(HMETHOD, r'giving \d+ days per year and (\d+) seasonal days per grid cell', SEASON,
          lambda d: d['season']['season_days']),
    claim(HMETHOD, r'window is 1 January (\d+)[\u2013-]', SEASON,
          lambda d: d['season']['window_start_year']),
    claim(HMETHOD, r'January \d+[\u2013-]\d+ December (\d+)', SEASON,
          lambda d: d['season']['window_end_year']),
    claim(HMETHOD, r'nearest ([\d.]+)\u00b0 ERA5 grid step', SEASON,
          lambda d: d['grid']['requested_step_degrees']),
    claim(HMETHOD, r'approximately (\d+) km north-south', SEASON,
          lambda d, w='ns': _grid_note(d, w)),
    claim(HMETHOD, r'and (\d+) km east-west', SEASON,
          lambda d, w='ew': _grid_note(d, w)),
    claim(HMETHOD, r'models=(\w+)', SEASON, lambda d: d['model'], word=True,
          rationale='the reanalysis the context is actually drawn from'),
    claim(HMETHOD, r'timezone=([A-Z]+)', SEASON,
          lambda d: re.search(r'timezone=(\w+)', d['request_url']).group(1), word=True,
          rationale='a dropped timezone would silently shift the series'),
    claim(HMETHOD, r'maximum \u2265([\d.]+) \u00b0C \(a descriptive', SEASON,
          lambda d, w='hot': _season_threshold(d, w)),
    claim(HMETHOD, r'minimum temperature \u2265([\d.]+) \u00b0C', SEASON,
          lambda d, w='tropical': _season_threshold(d, w)),
    claim(HMETHOD, r'probe for the (\d+) committed tree points', SEASON,
          lambda d: len(d['records'])),
    # The equal-length window check: per-gid ranges plus the analysed-length statement.
    claim(WIN100MD, r'\| 266 \| (\d+) \|', WIN100,
          lambda d, g=266: _window_summary(d, g, 0)['windows_per_anchor']),
    claim(WIN100MD, r'\| 266 \| \d+ \| ([\d.]+)[\u2013-]', WIN100,
          lambda d, g=266: _window_summary(d, g, 0)['overlap_percent_range'][0],
          tolerance=0.05),
    claim(WIN100MD, r'\| 266 \| \d+ \| [\d.]+[\u2013-]([\d.]+) \|', WIN100,
          lambda d, g=266: _window_summary(d, g, 0)['overlap_percent_range'][1],
          tolerance=0.05),
    claim(WIN100MD, r'\| 266 \| \d+ \| [\d.]+[\u2013-][\d.]+ \| ([\d.]+)[\u2013-]',
          WIN100, lambda d, g=266: _window_summary(d, g, 5)['overlap_percent_range'][0],
          tolerance=0.05),
    claim(WIN100MD, r'\| 266 \| \d+ \| [\d.]+[\u2013-][\d.]+ \| [\d.]+[\u2013-]([\d.]+) \|',
          WIN100, lambda d, g=266: _window_summary(d, g, 5)['overlap_percent_range'][1],
          tolerance=0.05),
    claim(WIN100MD, r'\| 5630 \| (\d+) \|', WIN100,
          lambda d, g=5630: _window_summary(d, g, 0)['windows_per_anchor']),
    claim(WIN100MD, r'\| 5630 \| \d+ \| ([\d.]+)[\u2013-]', WIN100,
          lambda d, g=5630: _window_summary(d, g, 0)['overlap_percent_range'][0],
          tolerance=0.05),
    claim(WIN100MD, r'\| 5630 \| \d+ \| [\d.]+[\u2013-]([\d.]+) \|', WIN100,
          lambda d, g=5630: _window_summary(d, g, 0)['overlap_percent_range'][1],
          tolerance=0.05),
    claim(WIN100MD, r'\| 5630 \| \d+ \| [\d.]+[\u2013-][\d.]+ \| ([\d.]+)[\u2013-]',
          WIN100, lambda d, g=5630: _window_summary(d, g, 5)['overlap_percent_range'][0],
          tolerance=0.05),
    claim(WIN100MD, r'\| 5630 \| \d+ \| [\d.]+[\u2013-][\d.]+ \| [\d.]+[\u2013-]([\d.]+) \|',
          WIN100, lambda d, g=5630: _window_summary(d, g, 5)['overlap_percent_range'][1],
          tolerance=0.05),
    claim(WIN100MD, r'\| 5634 \| (\d+) \|', WIN100,
          lambda d, g=5634: _window_summary(d, g, 0)['windows_per_anchor']),
    claim(WIN100MD, r'\| 5634 \| \d+ \| ([\d.]+)[\u2013-]', WIN100,
          lambda d, g=5634: _window_summary(d, g, 0)['overlap_percent_range'][0],
          tolerance=0.05),
    claim(WIN100MD, r'\| 5634 \| \d+ \| [\d.]+[\u2013-]([\d.]+) \|', WIN100,
          lambda d, g=5634: _window_summary(d, g, 0)['overlap_percent_range'][1],
          tolerance=0.05),
    claim(WIN100MD, r'\| 5634 \| \d+ \| [\d.]+[\u2013-][\d.]+ \| ([\d.]+)[\u2013-]',
          WIN100, lambda d, g=5634: _window_summary(d, g, 5)['overlap_percent_range'][0],
          tolerance=0.05),
    claim(WIN100MD, r'\| 5634 \| \d+ \| [\d.]+[\u2013-][\d.]+ \| [\d.]+[\u2013-]([\d.]+) \|',
          WIN100, lambda d, g=5634: _window_summary(d, g, 5)['overlap_percent_range'][1],
          tolerance=0.05),
    claim(WIN100MD, r'\| 5642 \| (\d+) \|', WIN100,
          lambda d, g=5642: _window_summary(d, g, 0)['windows_per_anchor']),
    claim(WIN100MD, r'\| 5642 \| \d+ \| ([\d.]+)[\u2013-]', WIN100,
          lambda d, g=5642: _window_summary(d, g, 0)['overlap_percent_range'][0],
          tolerance=0.05),
    claim(WIN100MD, r'\| 5642 \| \d+ \| [\d.]+[\u2013-]([\d.]+) \|', WIN100,
          lambda d, g=5642: _window_summary(d, g, 0)['overlap_percent_range'][1],
          tolerance=0.05),
    claim(WIN100MD, r'\| 5642 \| \d+ \| [\d.]+[\u2013-][\d.]+ \| ([\d.]+)[\u2013-]',
          WIN100, lambda d, g=5642: _window_summary(d, g, 5)['overlap_percent_range'][0],
          tolerance=0.05),
    claim(WIN100MD, r'\| 5642 \| \d+ \| [\d.]+[\u2013-][\d.]+ \| [\d.]+[\u2013-]([\d.]+) \|',
          WIN100, lambda d, g=5642: _window_summary(d, g, 5)['overlap_percent_range'][1],
          tolerance=0.05),
    claim(WIN100MD, r'\| 5643 \| (\d+) \|', WIN100,
          lambda d, g=5643: _window_summary(d, g, 0)['windows_per_anchor']),
    claim(WIN100MD, r'\| 5643 \| \d+ \| ([\d.]+)[\u2013-]', WIN100,
          lambda d, g=5643: _window_summary(d, g, 0)['overlap_percent_range'][0],
          tolerance=0.05),
    claim(WIN100MD, r'\| 5643 \| \d+ \| [\d.]+[\u2013-]([\d.]+) \|', WIN100,
          lambda d, g=5643: _window_summary(d, g, 0)['overlap_percent_range'][1],
          tolerance=0.05),
    claim(WIN100MD, r'\| 5643 \| \d+ \| [\d.]+[\u2013-][\d.]+ \| ([\d.]+)[\u2013-]',
          WIN100, lambda d, g=5643: _window_summary(d, g, 5)['overlap_percent_range'][0],
          tolerance=0.05),
    claim(WIN100MD, r'\| 5643 \| \d+ \| [\d.]+[\u2013-][\d.]+ \| [\d.]+[\u2013-]([\d.]+) \|',
          WIN100, lambda d, g=5643: _window_summary(d, g, 5)['overlap_percent_range'][1],
          tolerance=0.05),
    claim(WIN100MD, r'(\d+) windows per anchoring scheme', WIN100,
          lambda d: d['windows_per_anchor']),
    claim(WIN100MD, r'(\d+) m of [\d,.]+ m analysed per scheme', WIN100,
          lambda d: d['analysed_length_per_anchor_m']),
    claim(WIN100MD, r'\d+ m of ([\d,.]+) m analysed per scheme', WIN100,
          lambda d: d['total_segment_length_m'], tolerance=0.05),
    # The cross-screen overlaps: what isolates heat period from shared-input agreement.
    claim(PROTO, r'seasonal-mean heat-only top tens from the VITO daily-max series share (\d+)/10',
          HEAT, lambda d, k='seasonal_mean_vs_reference_day': _heat_overlap(d, k),
          rationale='same-series aggregation; the cross-screen zeros below are the contrast'),
    claim(PROTO, r'overlaps with the current balanced screen are (\d+)/10 and \d+/10',
          HEAT, lambda d, k='reference_day_vs_balanced': _heat_overlap(d, k),
          rationale='reference-day heat versus the operational screen'),
    claim(PROTO, r'overlaps with the current balanced screen are \d+/10 and (\d+)/10',
          HEAT, lambda d, k='seasonal_mean_vs_balanced': _heat_overlap(d, k)),
    claim(PROTO, r'\(hot-day count also (\d+)/10\)',
          HEAT, lambda d, k='hot_days_vs_balanced': _heat_overlap(d, k)),
    claim(PROTO, r'top ten overlaps (\d+)/10 with heat-only but only \d+/10 with proximity-only',
          SENSITIVITY, lambda d: d['weight_sensitivity']['heat_only_top_10_overlap']),
    claim(PROTO, r'top ten overlaps \d+/10 with heat-only but only (\d+)/10 with proximity-only',
          SENSITIVITY, lambda d: d['weight_sensitivity']['proximity_only_top_10_overlap']),
    # Corrected 2026-10-18: the prose carried a stale 7-10 range and the old weighted-0/10
    # error the mobility brief already corrected. Both now match the checked artifacts.
    claim(PROTO, r'flow-only ranking shares (\d+)/10', FLOW,
          lambda inputs, m='flow_only': _mobility_overlap(inputs, m),
          also=(NEAREST, SENSITIVITY),
          rationale='five counters cannot form a flow ranking'),
    claim(PROTO, r'heat-plus-flow alternative shares (\d+)/10', FLOW,
          lambda inputs, m='weighted': _mobility_overlap(inputs, m),
          also=(NEAREST, SENSITIVITY)),
    claim(PROTO, r'daily top tens share (\d+)/10 with the weekly mean on every day', FLOW,
          lambda inputs: _mobility_statistic(inputs, 'daily_overlap_min'),
          also=(NEAREST, SENSITIVITY) + HISTORIES,
          rationale='a 10 minimum over top-ten overlaps implies every day is 10 of 10'),
    claim(BRIEF_MOBILITY, r'flow-only\*\* top ten shared \*\*(\d+) of 10\*\* points', FLOW,
          lambda inputs, m='flow_only': _mobility_overlap(inputs, m),
          also=(NEAREST, SENSITIVITY)),
    claim(BRIEF_MOBILITY, r'shares \*\*(\d+) of 10\*\* with the current balanced top ten', FLOW,
          lambda inputs, m='weighted': _mobility_overlap(inputs, m),
          also=(NEAREST, SENSITIVITY),
          rationale='the corrected reading: heat-led agreement, not any-flow reshuffle'),
    claim(SPEC, r'seasonal-mean heat-only top tens share (\d+)/10 trees',
          HEAT, lambda d, k='seasonal_mean_vs_reference_day': _heat_overlap(d, k)),
    claim(SPEC, r'balanced ranking are (\d+)/10 and \d+/10 respectively',
          HEAT, lambda d, k='reference_day_vs_balanced': _heat_overlap(d, k)),
    claim(SPEC, r'balanced ranking are \d+/10 and (\d+)/10 respectively',
          HEAT, lambda d, k='seasonal_mean_vs_balanced': _heat_overlap(d, k)),
    claim(SPEC, r'the (\d+)/10 versus \d+/10 sensitivity result',
          SENSITIVITY, lambda d: d['weight_sensitivity']['heat_only_top_10_overlap']),
    claim(SPEC, r'the \d+/10 versus (\d+)/10 sensitivity result',
          SENSITIVITY, lambda d: d['weight_sensitivity']['proximity_only_top_10_overlap']),
    claim(DIAGNOSTICS, r'\| seasonal_mean_wbgt_c \| cell \| \d+/10 \| [\d, ]+ \| \d+ \| [\d.]+ \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, m='seasonal_mean_wbgt_c': _temporal_spearman(d, m, 'cell'),
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| seasonal_p90_wbgt_c \| cell \| \d+/10 \| [\d, ]+ \| \d+ \| [\d.]+ \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, m='seasonal_p90_wbgt_c': _temporal_spearman(d, m, 'cell'),
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| hot_days_per_season \| cell \| \d+/10 \| [\d, ]+ \| \d+ \| [\d.]+ \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, m='hot_days_per_season': _temporal_spearman(d, m, 'cell'),
          tolerance=0.001),
    claim(DIAGNOSTICS, r'cell-level Spearman ([\d.]+) and exact top-cell overlap',
          DIAGNOSTICS_JSON, lambda d: d['reference_vs_seasonal']['cell']['spearman'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'exact top-cell overlap (\d+)/10',
          DIAGNOSTICS_JSON, lambda d: _exact_overlap(d['reference_vs_seasonal']['cell'])),
    claim(DIAGNOSTICS, r'Only ([\d.]+)% of the fine',
          DIAGNOSTICS_JSON, lambda d: 100*d['variance_equal_cell']['within_fraction'],
          tolerance=0.01,
          rationale='percentage of a fraction; the table below rounds the same value to 0.026'),
    claim(DIAGNOSTICS, r'ranks have cell-level Spearman ([\d.]+) after aggregation',
          DIAGNOSTICS_JSON, lambda d, m='seasonal_mean_wbgt_c': d['fine_vs_archive_cell'][m]['spearman'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| reference_date_wbgt_c \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, m='reference_date_wbgt_c': d['fine_vs_archive_tree'][m]['spearman'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| reference_date_wbgt_c \| [\d.]+ \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, m='reference_date_wbgt_c': d['fine_vs_archive_cell'][m]['spearman'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| reference_date_wbgt_c \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, m='reference_date_wbgt_c': d['fine_vs_archive_cell'][m]['inclusive_jaccard'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| reference_date_wbgt_c \| [\d.]+ \| [\d.]+ \| [\d.]+ \| (\d+) \|',
          DIAGNOSTICS_JSON, lambda d, m='reference_date_wbgt_c': d['tree_top_distinct_cells'][m]),
    claim(DIAGNOSTICS, r'\| seasonal_mean_wbgt_c \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, m='seasonal_mean_wbgt_c': d['fine_vs_archive_tree'][m]['spearman'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| seasonal_mean_wbgt_c \| [\d.]+ \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, m='seasonal_mean_wbgt_c': d['fine_vs_archive_cell'][m]['spearman'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| seasonal_mean_wbgt_c \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, m='seasonal_mean_wbgt_c': d['fine_vs_archive_cell'][m]['inclusive_jaccard'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| seasonal_mean_wbgt_c \| [\d.]+ \| [\d.]+ \| [\d.]+ \| (\d+) \|',
          DIAGNOSTICS_JSON, lambda d, m='seasonal_mean_wbgt_c': d['tree_top_distinct_cells'][m]),
    claim(DIAGNOSTICS, r'\| seasonal_p90_wbgt_c \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, m='seasonal_p90_wbgt_c': d['fine_vs_archive_tree'][m]['spearman'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| seasonal_p90_wbgt_c \| [\d.]+ \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, m='seasonal_p90_wbgt_c': d['fine_vs_archive_cell'][m]['spearman'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| seasonal_p90_wbgt_c \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, m='seasonal_p90_wbgt_c': d['fine_vs_archive_cell'][m]['inclusive_jaccard'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| seasonal_p90_wbgt_c \| [\d.]+ \| [\d.]+ \| [\d.]+ \| (\d+) \|',
          DIAGNOSTICS_JSON, lambda d, m='seasonal_p90_wbgt_c': d['tree_top_distinct_cells'][m]),
    claim(DIAGNOSTICS, r'\| hot_days_per_season \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, m='hot_days_per_season': d['fine_vs_archive_tree'][m]['spearman'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| hot_days_per_season \| [\d.]+ \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, m='hot_days_per_season': d['fine_vs_archive_cell'][m]['spearman'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| hot_days_per_season \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, m='hot_days_per_season': d['fine_vs_archive_cell'][m]['inclusive_jaccard'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| hot_days_per_season \| [\d.]+ \| [\d.]+ \| [\d.]+ \| (\d+) \|',
          DIAGNOSTICS_JSON, lambda d, m='hot_days_per_season': d['tree_top_distinct_cells'][m]),
    claim(DIAGNOSTICS, r'\| variance_tree_weighted \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d: d['variance_tree_weighted']['within'], tolerance=0.005),
    claim(DIAGNOSTICS, r'\| variance_tree_weighted \| [\d.]+ \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d: d['variance_tree_weighted']['between'], tolerance=0.005),
    claim(DIAGNOSTICS, r'\| variance_tree_weighted \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d: d['variance_tree_weighted']['within_fraction'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| variance_equal_cell \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d: d['variance_equal_cell']['within'], tolerance=0.005),
    claim(DIAGNOSTICS, r'\| variance_equal_cell \| [\d.]+ \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d: d['variance_equal_cell']['between'], tolerance=0.005),
    claim(DIAGNOSTICS, r'\| variance_equal_cell \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d: d['variance_equal_cell']['within_fraction'], tolerance=0.001),
    claim(CHECKPOINT, r'(\d+) of \d+ comparison rows match', COMPARISON,
          lambda d: len(d['results'])),
    claim(CHECKPOINT, r'\d+ of (\d+) comparison rows match', COMPARISON,
          lambda d: len(d['results'])),
    claim(CHECKPOINT, r'(\d+) of \d+ window rows', WIN100,
          lambda d: len(d['windows'])),
    claim(CHECKPOINT, r'\d+ of (\d+) window rows', WIN100,
          lambda d: len(d['windows'])),
    claim(CHECKPOINT, r'(\d+) of \d+ summaries match', WIN100,
          lambda d: len(d['summaries'])),
    claim(CHECKPOINT, r'\d+ of (\d+) summaries match', WIN100,
          lambda d: len(d['summaries'])),
    claim(CHECKPOINT, r'All (\d+) cycling-infrastructure records matching', LOCAL,
          lambda d: d['selection']['response_count']),
    claim(CHECKPOINT, r'response confirmed (\d+)', LOCAL,
          lambda d: d['selection']['count_only_number_matched']),
    claim(CHECKPOINT, r'(\w+) records met the rules', LOCAL,
          lambda d: NUMBER_WORDS[d['sample_size']].capitalize(), word=True,
          rationale='sentence-initial capital, as in the local record'),
    claim(CHECKPOINT, r'original (\d+) m segment 5644', GEOJSON,
          lambda d, g=5644: _geo_length(d, g), tolerance=0.05,
          rationale='planar length straight from the committed frame'),
    claim(DIAGNOSTICS, r'\| BEGUINAGE - DIXMUDE \| (\d+) \|',
          DIAGNOSTICS_JSON, lambda d, k='BEGUINAGE - DIXMUDE': d['leave_one_district_out'][k]['trees']),
    claim(DIAGNOSTICS, r'\| BEGUINAGE - DIXMUDE \| \d+ \| (\d+) \|',
          DIAGNOSTICS_JSON, lambda d, k='BEGUINAGE - DIXMUDE': d['leave_one_district_out'][k]['cells']),
    claim(DIAGNOSTICS, r'\| BEGUINAGE - DIXMUDE \| \d+ \| \d+ \| ([-\u2212\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, k='BEGUINAGE - DIXMUDE': d['leave_one_district_out'][k]['comparison']['spearman'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| HEEMBEEK \| (\d+) \|',
          DIAGNOSTICS_JSON, lambda d, k='HEEMBEEK': d['leave_one_district_out'][k]['trees']),
    claim(DIAGNOSTICS, r'\| HEEMBEEK \| \d+ \| (\d+) \|',
          DIAGNOSTICS_JSON, lambda d, k='HEEMBEEK': d['leave_one_district_out'][k]['cells']),
    claim(DIAGNOSTICS, r'\| HEEMBEEK \| \d+ \| \d+ \| ([-\u2212\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, k='HEEMBEEK': d['leave_one_district_out'][k]['comparison']['spearman'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| HEYSEL \| (\d+) \|',
          DIAGNOSTICS_JSON, lambda d, k='HEYSEL': d['leave_one_district_out'][k]['trees']),
    claim(DIAGNOSTICS, r'\| HEYSEL \| \d+ \| (\d+) \|',
          DIAGNOSTICS_JSON, lambda d, k='HEYSEL': d['leave_one_district_out'][k]['cells']),
    claim(DIAGNOSTICS, r'\| HEYSEL \| \d+ \| \d+ \| ([-\u2212\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, k='HEYSEL': d['leave_one_district_out'][k]['comparison']['spearman'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| QUARTIER EUROPEEN \| (\d+) \|',
          DIAGNOSTICS_JSON, lambda d, k='QUARTIER EUROPEEN': d['leave_one_district_out'][k]['trees']),
    claim(DIAGNOSTICS, r'\| QUARTIER EUROPEEN \| \d+ \| (\d+) \|',
          DIAGNOSTICS_JSON, lambda d, k='QUARTIER EUROPEEN': d['leave_one_district_out'][k]['cells']),
    claim(DIAGNOSTICS, r'\| QUARTIER EUROPEEN \| \d+ \| \d+ \| ([-\u2212\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, k='QUARTIER EUROPEEN': d['leave_one_district_out'][k]['comparison']['spearman'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| QUARTIER ROYAL \| (\d+) \|',
          DIAGNOSTICS_JSON, lambda d, k='QUARTIER ROYAL': d['leave_one_district_out'][k]['trees']),
    claim(DIAGNOSTICS, r'\| QUARTIER ROYAL \| \d+ \| (\d+) \|',
          DIAGNOSTICS_JSON, lambda d, k='QUARTIER ROYAL': d['leave_one_district_out'][k]['cells']),
    claim(DIAGNOSTICS, r'\| QUARTIER ROYAL \| \d+ \| \d+ \| ([-\u2212\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, k='QUARTIER ROYAL': d['leave_one_district_out'][k]['comparison']['spearman'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| SQUARES \| (\d+) \|',
          DIAGNOSTICS_JSON, lambda d, k='SQUARES': d['leave_one_district_out'][k]['trees']),
    claim(DIAGNOSTICS, r'\| SQUARES \| \d+ \| (\d+) \|',
          DIAGNOSTICS_JSON, lambda d, k='SQUARES': d['leave_one_district_out'][k]['cells']),
    claim(DIAGNOSTICS, r'\| SQUARES \| \d+ \| \d+ \| ([-\u2212\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, k='SQUARES': d['leave_one_district_out'][k]['comparison']['spearman'],
          tolerance=0.001),
    claim(DIAGNOSTICS, r'\| STALINGRAD \| (\d+) \|',
          DIAGNOSTICS_JSON, lambda d, k='STALINGRAD': d['leave_one_district_out'][k]['trees']),
    claim(DIAGNOSTICS, r'\| STALINGRAD \| \d+ \| (\d+) \|',
          DIAGNOSTICS_JSON, lambda d, k='STALINGRAD': d['leave_one_district_out'][k]['cells']),
    claim(DIAGNOSTICS, r'\| STALINGRAD \| \d+ \| \d+ \| ([-\u2212\d.]+) \|',
          DIAGNOSTICS_JSON, lambda d, k='STALINGRAD': d['leave_one_district_out'][k]['comparison']['spearman'],
          tolerance=0.001),

    claim(DEMO, r'uses (\d+) sampled managed-tree records', TREES,
          lambda d: len(d['records']),
          rationale='the sample the demo walks stakeholders through'),
    claim(DEMO, r'overlaps (\d+)/10 with heat-only and', SENSITIVITY,
          lambda d: d['weight_sensitivity']['heat_only_top_10_overlap']),
    claim(DEMO, r'with heat-only and (\d+)/10 with proximity-only', SENSITIVITY,
          lambda d: d['weight_sensitivity']['proximity_only_top_10_overlap']),
    claim(WBGT, r'maximum WBGT at (\d+) m for \d+', HEAT,
          lambda d: d['grid']['step_metres']),
    claim(WBGT, r'at \d+ m for (\d+)[\u2013-]', HEAT,
          lambda d: d['window']['start_year']),
    claim(WBGT, r'at \d+ m for \d+[\u2013-](\d+)', HEAT,
          lambda d: d['window']['end_year']),
    claim(WBGT, r'No (\d+) °C hot-day threshold', HEAT,
          lambda d: float(re.search(r'at or above ([\d.]+) °C', d['method']).group(1)),
          rationale='the threshold the mean product must not inherit'),
    claim(JULIA, r'seasons from (\d+) through \d+', SEASON,
          lambda d: d['season']['window_start_year']),
    claim(JULIA, r'seasons from \d+ through (\d+)', SEASON,
          lambda d: d['season']['window_end_year']),
    # The point-grid recomputation: the 2 m column is the committed frame, the 0.5 m
    # column the new 0.5 m frame built from committed code under the same midpoint rule.
    claim(CHECKPOINT, r'\| Direct overlap \| [\d.]+% \| ([\d.]+)%', FRAME,
          lambda d, s='mapped_overlap': _frame_share(d, s), tolerance=0.005,
          rationale='the 2 m column is the validation frame itself'),
    claim(CHECKPOINT, r'Proximity-only \(0-5 m, not overlapping\) \| [\d.]+% \| ([\d.]+)%',
          FRAME, lambda d, s='proximity_only': _frame_share(d, s), tolerance=0.005),
    claim(CHECKPOINT, r'\| Mapped non-overlap \| [\d.]+% \| ([\d.]+)%', FRAME,
          lambda d, s='mapped_non_overlap': _frame_share(d, s), tolerance=0.005),
    claim(CHECKPOINT, r'\| Direct overlap \| [\d.]+% \| [\d.]+% \| ([\d.]+)%', FRAME05,
          lambda d, s='mapped_overlap': _frame_share(d, s), tolerance=0.005),
    claim(CHECKPOINT, r'Proximity-only \(0-5 m, not overlapping\) \| [\d.]+% \| [\d.]+% \| ([\d.]+)%',
          FRAME05, lambda d, s='proximity_only': _frame_share(d, s), tolerance=0.005),
    claim(CHECKPOINT, r'\| Mapped non-overlap \| [\d.]+% \| [\d.]+% \| ([\d.]+)%', FRAME05,
          lambda d, s='mapped_non_overlap': _frame_share(d, s), tolerance=0.005),
    claim(CHECKPOINT, r'gid 266 ([\d.]+)% vs [\d.]+%', FRAME05,
          lambda d, g=266: _frame_seg_share(d, g), tolerance=0.005),
    claim(CHECKPOINT, r'gid 5642 ([\d.]+)% vs [\d.]+%', FRAME05,
          lambda d, g=5642: _frame_seg_share(d, g), tolerance=0.005),
    claim(CHECKPOINT, r'gid 5630, 5634 and 5643 ([\d.]+)% both ways', FRAME05,
          lambda d: max(_frame_seg_share(d, g) for g in (5630, 5634, 5643)),
          rationale='three zero-share segments; a drift in any one breaks the bound'),
    claim(AUDIT, r': ([\d.]+)-[\d.]+% overlap against', FRAME05,
          lambda d, s='mapped_overlap': _frame_share(d, s), tolerance=0.005),
    claim(AUDIT, r': [\d.]+-([\d.]+)% overlap against', FRAME,
          lambda d, s='mapped_overlap': _frame_share(d, s), tolerance=0.005),
    claim(AUDIT, r'at most ([\d.]+) pp difference on a single segment', FRAME05,
          lambda inputs: _max_point_gap(inputs[FRAME05], inputs[COMPARISON]),
          also=(COMPARISON,), tolerance=0.05,
          rationale='an upper bound; the recomputed worst gap is 0.32 on gid 266'),
)


def load_texts(root, docs):
    require(docs, 'no documents to check')
    texts = {}
    for name in docs:
        path = root/name
        require(path.is_file(), f'missing document: {name}')
        texts[name] = path.read_text()
    return texts


def tracked_files(root):
    """Repository-relative paths git knows about, plus local cache files."""
    out = subprocess.run(['git', 'ls-files'], cwd=root, check=True,
                         capture_output=True, text=True).stdout.split()
    paths = set(out)
    cache = root/'.cache'
    if cache.is_dir():
        paths |= {str(p.relative_to(root)) for p in cache.rglob('*') if p.is_file()}
    return paths


def references(text):
    """Repository-looking tokens in one document, ignoring shells and served routes."""
    found = set()
    for match in TOKEN.finditer(text):
        before = text[match.start(1)-1] if match.start(1) else ''
        if before in '$_' or before.isalnum():
            continue    # a suffix of a shell variable or of a longer word, not a path
        found.add(match.group(1))
    for link in LINK.finditer(text):
        found.add(link.group(1).split('#')[0])
    found.discard('')
    return sorted(found)


def unresolved(root, text, name, paths, basenames):
    """Repository paths named in one document that do not exist."""
    problems = []
    for token in references(text):
        if token.startswith(SKIP_PREFIXES) or token in EXTERNAL_REFERENCES:
            continue
        if token in CACHE_ONLY_REFERENCES or token.startswith('/'):
            continue
        if any(marker in token for marker in PLACEHOLDER_MARKERS):
            continue
        if '/' in token:
            # Written from the document's own directory when it starts with ./ or ../.
            normalised = (os.path.normpath(os.path.join(os.path.dirname(name), token))
                          if token.startswith(('.', '../')) else token)
            # Tracked files only, so an untracked working-tree file cannot pass here and then
            # fail in a clean checkout. A directory counts when something tracked lives in it.
            found = (normalised in paths
                     or any(path.startswith(normalised.rstrip('/') + '/') for path in paths))
        else:
            found = token in basenames
        if not found:
            problems.append(f'{name}: unresolved reference `{token}`')
    return problems


def check_references(root, texts, paths):
    basenames = {p.rsplit('/', 1)[-1] for p in paths}
    problems = []
    for name, text in texts.items():
        problems.extend(unresolved(root, text, name, paths, basenames))
    return problems, basenames


def check_claims(root, texts, ledger=None):
    """Verify every claim, optionally against a supplied ledger rather than the module one."""
    ledger = LEDGER if ledger is None else ledger
    artifacts, problems, checked = {}, [], []
    for item in ledger:
        for name in (item.artifact,) + item.also:
            if name not in artifacts:
                path = root/name
                require(path.is_file(), f'missing artifact: {name}')
                artifacts[name] = json.loads(path.read_text())
        checked.append(item)
    results = []
    for item in ledger:
        try:
            results.append(item.check(texts, artifacts))
        except ValueError as error:
            problems.append(str(error))
    return problems, results


def self_test():
    """Prove both checks detect injected errors; a check that cannot fail is not a check."""
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root/'docs').mkdir()
        good = root/'docs/good.md'
        good.write_text('See `scripts/validate-all.sh` and the **7 candidate points** here.\n')
        broken = root/'docs/broken.md'
        broken.write_text('See `docs/does-not-exist.md` and the **9 candidate points** here.\n')
        artifact = root/'frame.json'
        artifact.write_text(json.dumps({'candidate_count': 7}))
        ledger = (claim('docs/good.md', r'\*\*(\d+) candidate points\*\*', 'frame.json',
                        lambda d: d['candidate_count']),)
        paths = {'scripts/validate-all.sh'}
        texts = {'docs/good.md': good.read_text(), 'docs/broken.md': broken.read_text()}

        problems, _ = check_references(root, {'docs/broken.md': texts['docs/broken.md']}, paths)
        require(any('does-not-exist' in p for p in problems),
                'path check did not detect a missing reference')
        accepted = check_references(root, {'docs/good.md': texts['docs/good.md']}, paths)[0]
        require(accepted == [], f'path check rejected a good reference: {accepted}')

        # A claim whose pattern no longer matches must fail rather than pass silently.
        drifted = dict(texts)
        drifted['docs/good.md'] = 'The sentence was reworded and the number is gone.\n'
        try:
            ledger[0].check(drifted, {'frame.json': json.loads(artifact.read_text())})
        except ValueError as error:
            require('no longer matches' in str(error), f'unexpected failure: {error}')
        else:
            raise ValueError('claim check did not notice a vanished claim')

        artifacts = {'frame.json': json.loads(artifact.read_text())}
        results = [item.check(texts, artifacts) for item in ledger]
        require(results == ['7 == frame.json'], f'claim check misread a correct claim: {results}')
        # Exercise the loader the gate actually calls, not only Claim.check directly.
        problems, checked = check_claims(root, texts, ledger)
        require(problems == [] and checked == ['7 == frame.json'],
                f'the claim loader disagreed: {problems} {checked}')
        # The loader's failure path, not only Claim.check's: a stale document must be
        # reported by the function the gate actually calls.
        broken_claims, _ = check_claims(root, stale_for_loader := dict(texts, **{'docs/good.md': texts['docs/broken.md']}), ledger)
        require(any('quotes 9' in problem for problem in broken_claims),
                f'the claim loader did not aggregate the failure: {broken_claims}')
        stale = dict(texts)
        stale['docs/good.md'] = texts['docs/broken.md']
        try:
            ledger[0].check(stale, artifacts)
        except ValueError as error:
            require('quotes 9' in str(error), f'claim check reported the wrong problem: {error}')
        else:
            raise ValueError('claim check did not detect a mismatched number')
    print('self-test passed: the path check and the claim check each detected an injected error, '
          'and neither rejected the correct pair')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0

    root = args.root
    docs = DOCS + tuple(sorted(str(p.relative_to(root)) for p in (root/'docs').glob('*.md')))
    docs += tuple(sorted(str(p.relative_to(root)) for p in (root/'data').glob('*.md')))
    docs += tuple(sorted(str(p.relative_to(root)) for p in (root/'data/research').glob('*.md')))
    texts = load_texts(root, docs)
    paths = tracked_files(root)
    problems, _ = check_references(root, texts, paths)
    claim_problems, results = check_claims(root, texts)
    problems += claim_problems

    print(f'{len(docs)} documents, {len(paths)} known paths, '
          f'{len(LEDGER)} pinned claims ({len(results)} verified)')
    for item in results:
        print(f'  pinned: {item}')
    if problems:
        print(f'\n{len(problems)} documentation problem(s):')
        for problem in problems:
            print(f'  {problem}')
        return 1
    print('documentation references and pinned claims all hold')
    return 0


if __name__ == '__main__':
    sys.exit(main())
