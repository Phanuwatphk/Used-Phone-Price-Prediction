"""Freeze chronological train/validation/test by whole publication days."""
import argparse
from collections import Counter
import csv
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if not __package__:
    sys.path.insert(0, str(ROOT))
from script.modeling.features import validate_listing

RUN = 'asking_price_v1'
DEFAULT_CONFIG = ROOT / 'config/modeling/training.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def protected_output(output, inputs):
    output = Path(output).resolve()
    for protected in [ROOT / 'data/raw', ROOT / 'data/final', ROOT / 'config', ROOT / 'script', *map(Path, inputs)]:
        protected = protected.resolve()
        if output == protected or output.is_relative_to(protected) or protected.is_relative_to(output):
            raise ValueError(f'Output overlaps protected input: {protected}')


def read_dataset(path, expected_hash=None):
    if expected_hash and sha(path) != expected_hash:
        raise ValueError('Dataset checksum differs from the frozen training input')
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    if not rows or len({r['listing_id'] for r in rows}) != len(rows):
        raise ValueError('Empty dataset or duplicate listing_id')
    if len({r['url'] for r in rows}) != len(rows):
        raise ValueError('Duplicate listing URL')
    for row in rows:
        validate_listing(row)
        price = float(row['price_thb'])
        if not math.isfinite(price) or price <= 0:
            raise ValueError('Invalid target price')
        if row['listing_id'] != row['source'] + ':' + row['product_id']:
            raise ValueError('Listing identity differs from source/product_id')
    return rows


def split_rows(rows, train_fraction=.85, validation_fraction=.075):
    if not 0 < train_fraction < 1 or not 0 < validation_fraction < 1 - train_fraction:
        raise ValueError('Invalid split fractions')
    ordered = sorted(rows, key=lambda r: (r['published_at'], r['listing_id']))
    n = len(ordered)
    validation_start = ordered[min(int(n * train_fraction), n - 1)]['published_at']
    test_start = ordered[min(int(n * (train_fraction + validation_fraction)), n - 1)]['published_at']
    splits = {'train': [], 'validation': [], 'test': []}
    for row in ordered:
        name = 'train' if row['published_at'] < validation_start else 'validation' if row['published_at'] < test_start else 'test'
        splits[name].append(row)
    if any(not part for part in splits.values()):
        raise ValueError('Too few distinct dates to create three nonempty chronological splits')
    for left, right in [('train', 'validation'), ('validation', 'test')]:
        if max(r['published_at'] for r in splits[left]) >= min(r['published_at'] for r in splits[right]):
            raise ValueError('Chronological overlap')
    return splits


def describe_splits(splits):
    training_models = {(r['brand'], r['model']) for r in splits['train']}
    fitted_models = training_models | {(r['brand'], r['model']) for r in splits['validation']}
    return {name: {
        'rows': len(rows), 'date_min': rows[0]['published_at'], 'date_max': rows[-1]['published_at'],
        'source_counts': dict(Counter(r['source'] for r in rows)),
        'brand_counts': dict(Counter(r['brand'] for r in rows)),
        'unseen_model_rows_vs_training': sum((r['brand'], r['model']) not in training_models for r in rows),
        'unseen_model_rows_vs_final_fit': sum((r['brand'], r['model']) not in fitted_models for r in rows),
    } for name, rows in splits.items()}


def create_split(config_path=DEFAULT_CONFIG, output=None):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text())
    dataset = ROOT / config['dataset']
    output = Path(output or ROOT / 'data/intermediate/modeling' / config['run'] / 'split').resolve()
    protected_output(output, [dataset, config_path])
    rows = read_dataset(dataset, config['dataset_sha256'])
    if len(rows) != config['expected_rows']:
        raise ValueError('Dataset row count differs')
    splits = split_rows(rows, **config['split'])
    if any(set(config['required_training_sources']) - {r['source'] for r in part} for part in splits.values()):
        raise ValueError('Each split must cover both sources')
    summary = describe_splits(splits)
    summary['policy'] = 'Whole-day chronological split; no random shuffle; exact IDs/URLs disjoint. Physical-device identity is unavailable.'
    summary['dataset_sha256'] = sha(dataset)
    summary['config_sha256'] = sha(config_path)
    assignments = []
    for name, part in splits.items():
        write_csv(output / f'{name}.csv', part)
        assignments.extend({'listing_id': r['listing_id'], 'published_at': r['published_at'], 'split': name} for r in part)
    write_csv(output / 'assignments.csv', assignments)
    dump(output / 'summary.json', summary)
    dump(output / 'validation.json', {'all_rows_accounted': len(assignments) == len(rows), 'listing_ids_disjoint': len({r['listing_id'] for r in assignments}) == len(rows), 'publication_days_disjoint': True, 'strict_chronological_order': True, 'dataset_unchanged': sha(dataset) == config['dataset_sha256']})
    dump(output / 'hashes.json', {p.name: sha(p) for p in sorted(output.glob('*.csv'))})
    return splits, summary, output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    _, summary, output = create_split(args.config, args.output)
    print(json.dumps({'output': str(output), 'split': summary}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
