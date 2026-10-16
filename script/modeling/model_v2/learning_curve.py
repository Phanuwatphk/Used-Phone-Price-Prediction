"""Fit chronological learning curves for the five frozen V2 validation windows.

Execute with the project Python environment; the report refresh runs afterward.
Each point is a fresh fit. Evaluation/deployment artifacts are never replaced.
"""
import csv
from datetime import datetime, timezone
import importlib.metadata
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if not __package__:
    sys.path.insert(0, str(ROOT))

import numpy as np
from script.artifacts import metadata_sha, read_metadata, write_metadata
from script.modeling.model_v2.train_improved import fit, validate_validation_scheme
from script.modeling.model_v2.train_validation_errors import fold_errors
from script.modeling.split_dataset import read_dataset, sha, write_csv

FRACTIONS = (.10, .25, .50, .75, 1.)


def temporal_prefix(rows, fraction):
    """Take the earliest fraction, rounding upward to include the entire cutoff day."""
    if not rows or not 0 < fraction <= 1:
        raise ValueError('A nonempty training set and fraction in (0, 1] are required')
    ordered = sorted(rows, key=lambda row: (row['published_at'], row['listing_id']))
    cutoff = ordered[math.ceil(len(ordered) * fraction) - 1]['published_at']
    return [row for row in ordered if row['published_at'] <= cutoff]


def run():
    report = ROOT / 'docs/assets/modeling'
    config = read_metadata(report, 'config')
    validate_validation_scheme(config)
    spec = read_metadata(report, 'selection')['candidate']
    if spec != next(item for item in config['candidates'] if item['name'] == spec['name']):
        raise ValueError('Selected candidate differs from recorded configuration')
    dataset, catalog_path = ROOT / config['dataset'], ROOT / config['catalog']
    rows = read_dataset(dataset, config['dataset_sha256'])
    if len(rows) != config['expected_rows']:
        raise ValueError('Enriched row count mismatch')
    if config.get('training_conditions'):
        rows = [row for row in rows if row['condition'] in config['training_conditions']]
        if len(rows) != config['expected_training_rows']:
            raise ValueError('Training scope row count mismatch')
    if sha(catalog_path) != config['catalog_sha256']:
        raise ValueError('Catalog checksum mismatch')
    catalog = json.loads(catalog_path.read_text())['release_years']
    reference_path = report / 'tables/train_validation_errors.csv'
    reference_meta = read_metadata(report, 'train_validation_diagnostic')
    if (reference_meta['config_sha256'] != metadata_sha(report, 'config') or
            reference_meta['output_sha256'] != sha(reference_path)):
        raise ValueError('Refresh train_validation_errors.py before computing learning curves')
    with reference_path.open() as handle:
        reference = {int(row['fold']): row for row in csv.DictReader(handle)}
    folds = read_metadata(report, 'folds')
    results = []
    for index, interval in enumerate(config['folds'], 1):
        training = [row for row in rows if row['published_at'] < interval['start']]
        validation = [row for row in rows if interval['start'] <= row['published_at'] <= interval['end']]
        if (len(training), len(validation)) != (folds[index-1]['train_rows'], folds[index-1]['validation_rows']):
            raise ValueError('Fold sizes differ from recorded training')
        for fraction in FRACTIONS:
            subset = temporal_prefix(training, fraction)
            print(f'FIT learning curve fold {index}/{len(folds)}, {fraction:.0%}: '
                  f'{len(subset)} train, {len(validation)} fixed validation', flush=True)
            model = fit(spec, subset, catalog, config)
            scores = fold_errors(model, spec, subset, validation, catalog, config['threads'])
            if fraction == 1.:
                for key, value in scores.items():
                    expected = reference[index][key]
                    if not ((value is None and expected == '') or
                            (value is not None and np.isclose(value, float(expected), rtol=1e-9, atol=1e-6))):
                        raise ValueError(f'Full-size fold {index} differs from recorded {key}')
            results.append({'candidate': spec['name'], 'fold': index, 'requested_fraction': fraction,
                            'actual_fraction': len(subset) / len(training), 'full_train_rows': len(training),
                            'train_min': subset[0]['published_at'], 'train_max': subset[-1]['published_at'],
                            'window_start': interval['start'], 'window_end': interval['end'], **scores})
            print(f"MAE train={scores['train_mae_thb']:.2f}, validation={scores['validation_mae_thb']:.2f}", flush=True)
    output = report / 'tables/learning_curve.csv'
    write_csv(output, results)
    write_metadata(report, 'learning_curve', {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'candidate': spec['name'], 'fractions': list(FRACTIONS), 'fresh_fits': len(results),
        'config_sha256': metadata_sha(report, 'config'), 'dataset_sha256': sha(dataset),
        'catalog_sha256': sha(catalog_path), 'reference_sha256': sha(reference_path),
        'output_sha256': sha(output), 'full_size_matches_recorded': True,
        'code_sha256': {str(path.relative_to(ROOT)): sha(path)
                        for path in sorted((ROOT / 'script/modeling').rglob('*.py'))},
        'versions': {name: importlib.metadata.version(name)
                     for name in ['scikit-learn', 'catboost', 'pandas', 'numpy', 'joblib']},
        'policy': 'Fresh fits of frozen selected candidate on nested earliest-date training prefixes, '
                  'rounded up to whole days. Same validation rows at every size within a fold. '
                  'Preprocessing and recency weights fitted on each prefix only. Unweighted THB errors. '
                  'No retrospective test scoring, tuning, or model artifact replacement.'})
    return results


if __name__ == '__main__':
    run()
    from script.modeling.model_v2.report_improved import main
    main()
