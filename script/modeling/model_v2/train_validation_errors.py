"""Reproduce selected V2 folds and compare in-sample training/forward validation errors.

Run after train_improved.py, then report_improved.py to refresh the report.
This diagnostic never replaces evaluation or deployment model artifacts.
"""
import csv
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if not __package__:
    sys.path.insert(0, str(ROOT))

import numpy as np
from script.artifacts import metadata_sha, read_metadata, write_metadata
from script.modeling.common import metrics
from script.modeling.model_v2.train_improved import fit, forecast, validate_validation_scheme
from script.modeling.split_dataset import read_dataset, sha, write_csv


def fold_errors(model, spec, training, validation, catalog, threads):
    """Score both partitions with the same train-only fitted estimator in THB."""
    result = {}
    for partition, rows in [('train', training), ('validation', validation)]:
        scores = metrics([float(row['price_thb']) for row in rows],
                         forecast(model, spec, rows, catalog, threads))
        result.update({partition + '_' + key: value for key, value in scores.items()})
    for metric in ['mae_thb', 'rmse_thb']:
        result[metric + '_gap'] = result['validation_' + metric] - result['train_' + metric]
    return result


def run():
    report = ROOT / 'docs/assets/modeling'
    config = read_metadata(report, 'config')
    validate_validation_scheme(config)
    spec = read_metadata(report, 'selection')['candidate']
    if spec != next(item for item in config['candidates'] if item['name'] == spec['name']):
        raise ValueError('Selected candidate differs from recorded configuration')
    dataset, catalog_path = ROOT / config['dataset'], ROOT / config['catalog']
    rows = sorted(read_dataset(dataset, config['dataset_sha256']),
                  key=lambda row: (row['published_at'], row['listing_id']))
    if len(rows) != config['expected_rows']:
        raise ValueError('Enriched row count mismatch')
    if config.get('training_conditions'):
        rows = [row for row in rows if row['condition'] in config['training_conditions']]
        if len(rows) != config['expected_training_rows']:
            raise ValueError('Training scope row count mismatch')
    if sha(catalog_path) != config['catalog_sha256']:
        raise ValueError('Catalog checksum mismatch')
    catalog = json.loads(catalog_path.read_text())['release_years']
    stored_path = report / 'tables/fold_metrics.csv'
    with stored_path.open() as handle:
        stored = {int(row['fold']): row for row in csv.DictReader(handle)
                  if row['candidate'] == spec['name']}
    folds = read_metadata(report, 'folds')
    if len(stored) != len(config['folds']) or len(folds) != len(config['folds']):
        raise ValueError('Incomplete recorded folds')
    results = []
    for index, interval in enumerate(config['folds'], 1):
        training = [row for row in rows if row['published_at'] < interval['start']]
        validation = [row for row in rows if interval['start'] <= row['published_at'] <= interval['end']]
        if not training or not validation:
            raise ValueError('Empty fold')
        if (len(training), len(validation)) != (folds[index-1]['train_rows'], folds[index-1]['validation_rows']):
            raise ValueError('Fold sizes differ from recorded training')
        print(f'FIT diagnostic fold {index}/{len(folds)}: {len(training)} train, {len(validation)} validation', flush=True)
        model = fit(spec, training, catalog, config)
        scores = fold_errors(model, spec, training, validation, catalog, config['threads'])
        for key in stored[index]:
            if key in ('candidate', 'fold'):
                continue
            expected = stored[index][key]
            actual = scores['validation_' + key]
            if not ((actual is None and expected == '') or
                    (actual is not None and np.isclose(actual, float(expected), rtol=1e-9, atol=1e-6))):
                raise ValueError(f'Fold {index} validation differs from recorded {key}')
        results.append({'candidate': spec['name'], 'fold': index,
                        'window_start': interval['start'], 'window_end': interval['end'], **scores})
        print(f"MAE train={scores['train_mae_thb']:.2f}, validation={scores['validation_mae_thb']:.2f}", flush=True)
    output = report / 'tables/train_validation_errors.csv'
    write_csv(output, results)
    write_metadata(report, 'train_validation_diagnostic', {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'candidate': spec['name'], 'folds': len(results),
        'config_sha256': metadata_sha(report, 'config'),
        'dataset_sha256': sha(dataset), 'catalog_sha256': sha(catalog_path),
        'recorded_fold_metrics_sha256': sha(stored_path), 'output_sha256': sha(output),
        'code_sha256': {str(path.relative_to(ROOT)): sha(path)
                        for path in sorted((ROOT / 'script/modeling').rglob('*.py'))},
        'versions': {name: importlib.metadata.version(name)
                     for name in ['scikit-learn', 'catboost', 'pandas', 'numpy', 'joblib']},
        'validation_matches_recorded': True,
        'policy': 'Selected candidate refitted on each original train-only fold. Both errors are unweighted, in THB, after inverse log transform and blending. Training errors are in-sample. No model artifacts replaced; no new selection or retrospective scoring.'})
    return results


if __name__ == '__main__':
    run()
    from script.modeling.model_v2.report_improved import main
    main()
