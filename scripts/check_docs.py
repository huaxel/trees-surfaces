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

    def __init__(self, doc, pattern, artifact, selector, tolerance=0.0, rationale='', word=False):
        self.doc, self.pattern, self.artifact = doc, re.compile(pattern), artifact
        self.selector, self.tolerance, self.rationale = selector, tolerance, rationale
        self.word = word

    def check(self, texts, artifacts):
        text = texts.get(self.doc)
        require(text is not None, f'ledger names a missing document: {self.doc}')
        match = self.pattern.search(text)
        require(match is not None,
                f'claim pattern no longer matches {self.doc}: {self.pattern.pattern!r}'
                + (f' ({self.rationale})' if self.rationale else ''))
        data = artifacts.get(self.artifact)
        require(data is not None, f'ledger names a missing artifact: {self.artifact}')
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
PLAN = 'docs/canopy-accuracy-sampling-plan.md'
PIPELINE = 'docs/cycling-canopy-pipeline.md'
WBGT = 'docs/wbgt-mean-max-method.md'
BRIEF = 'docs/heat-season-stakeholder-brief.md'


def _stratum(name):
    return lambda data: sum(segment[name] for segment in data['segments'])


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
            # `../bin/x.jl` is written from the document's own directory.
            base = (root/name).parent if token.startswith(('.', '../')) else root
            found = token in paths or (base/token).resolve().exists()
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


def check_claims(root, texts):
    artifacts, problems, checked = {}, [], []
    for item in LEDGER:
        if item.artifact not in artifacts:
            path = root/item.artifact
            require(path.is_file(), f'missing artifact: {item.artifact}')
            artifacts[item.artifact] = json.loads(path.read_text())
        checked.append(item)
    results = []
    for item in LEDGER:
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

        import unittest.mock as mock
        with mock.patch('check_docs.LEDGER', ledger):
            artifacts = {'frame.json': json.loads(artifact.read_text())}
            results = [item.check(texts, artifacts) for item in ledger]
            require(results == ['7 == frame.json'], f'claim check misread a correct claim: {results}')
            stale = dict(texts); stale['docs/good.md'] = texts['docs/broken.md']
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
