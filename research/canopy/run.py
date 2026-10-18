"""Run with uv run --locked --project research/canopy python research/canopy/run.py."""
import argparse
from pathlib import Path

from pipeline import execute, publish


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description='Verified offline mapped-canopy comparison (not shade)')
    parser.add_argument('--cache', type=Path, default=root/'.cache/vub-canopy-2021')
    parser.add_argument('--manifest', type=Path, default=root/'data/research/canopy-inputs/manifest.json')
    parser.add_argument('--output', type=Path, required=True, help='New directory; never overwrite existing results')
    args = parser.parse_args()
    parser.error('output already exists; choose a new directory') if args.output.exists() else None
    comparison, windows = execute(args.manifest, args.cache)
    publish(args.output, comparison, windows)
    print(f'Validated {comparison["sample_size"]} segments, {len(comparison["results"])} conditions, '
          f'{windows["windows_per_anchor"]} windows per anchor; wrote {args.output}')


if __name__ == '__main__':
    main()
