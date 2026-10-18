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
import os
import re
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
PLAN = 'docs/canopy-accuracy-sampling-plan.md'
PIPELINE = 'docs/cycling-canopy-pipeline.md'
WBGT = 'docs/wbgt-mean-max-method.md'
BRIEF = 'docs/heat-season-stakeholder-brief.md'


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
    claim(SPEC, r'finds (\d+) of 100 points at or above', SENSITIVITY,
          lambda d: _quadrant(d['balanced_screening']),
          rationale='third-quartile quadrant count, recomputed from the committed scores'),
    claim(ANALYSIS, r'quadrant: (\d+) point at or above', SENSITIVITY,
          lambda d: _quadrant(d['balanced_screening']),
          rationale='the analysis document and the spec must agree with the scores'),
    claim(WBGT, r'(\d+) distinct 100 m cells', HEAT,
          lambda d: min(d['region_summary']['distinct_cells'], len(d['records'])),
          rationale='the effective sample the method doc relies on'),
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
