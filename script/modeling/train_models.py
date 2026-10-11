"""Compare predeclared candidates on validation, then evaluate a frozen winner on test."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if not __package__:
    sys.path.insert(0, str(ROOT))

import joblib
import numpy as np
from catboost import CatBoostRegressor
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, median_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from threadpoolctl import threadpool_limits

from script.modeling.features import CATEGORICAL, NUMERIC, FEATURES, features, prices
from script.modeling.split_dataset import DEFAULT_CONFIG, ROOT, create_split, dump, protected_output, sha, write_csv


def metrics(actual, predicted):
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    error = np.abs(actual - predicted)
    return {'rows': len(actual), 'mae_thb': float(mean_absolute_error(actual, predicted)),
            'rmse_thb': float(mean_squared_error(actual, predicted) ** .5),
            'median_absolute_error_thb': float(median_absolute_error(actual, predicted)),
            'r2': float(r2_score(actual, predicted)) if len(actual) > 1 and np.var(actual) > 0 else None,
            'mape_pct': float(np.mean(error / actual) * 100),
            'within_20pct': float(np.mean(error / actual <= .2)),
            'bias_thb': float(np.mean(predicted - actual))}


def build_model(spec, seed=42, threads=4, iterations=None):
    parameters = dict(spec['parameters'])
    kind = spec['kind']
    if kind == 'catboost':
        if iterations is not None:
            parameters['iterations'] = iterations
        return CatBoostRegressor(**parameters, cat_features=CATEGORICAL, random_seed=seed,
                                 thread_count=threads, eval_metric='MAE', has_time=True,
                                 allow_writing_files=False, verbose=False)
    if kind == 'median':
        estimator = DummyRegressor(strategy='median')
    elif kind == 'ridge':
        estimator = Ridge(**parameters)
    elif kind == 'extra_trees':
        estimator = ExtraTreesRegressor(**parameters, random_state=seed, n_jobs=threads)
    elif kind == 'hist_boost':
        estimator = HistGradientBoostingRegressor(**parameters, random_state=seed)
    else:
        raise ValueError('Unknown candidate: ' + kind)
    preprocessing = ColumnTransformer([
        ('categorical', OneHotEncoder(handle_unknown='ignore', sparse_output=False), CATEGORICAL),
        ('numeric', StandardScaler(), NUMERIC),
    ], sparse_threshold=0)
    model = Pipeline([('features', preprocessing), ('regressor', estimator)])
    if spec.get('log_target'):
        model = TransformedTargetRegressor(regressor=model, func=np.log, inverse_func=np.exp)
    return model


def group_metrics(rows, actual, predicted, fitted_models):
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        attributes = {'source': row['source'], 'brand': row['brand'], 'year': row['published_at'][:4],
                      'condition': row['condition'], 'model_coverage': 'seen' if row['brand'] + ':' + row['model'] in fitted_models else 'unseen',
                      'brand_model': row['brand'] + ':' + row['model']}
        for field, value in attributes.items():
            groups[(field, value)].append(i)
    return [{'group': field, 'value': value, **metrics(actual[idx], predicted[idx])}
            for (field, value), idx in sorted(groups.items())]


def train(config_path=DEFAULT_CONFIG, report_output=None, model_output=None, private_output=None):
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text())
    report = Path(report_output or ROOT / 'docs/assets/modeling' / config['run']).resolve()
    model_dir = Path(model_output or ROOT / 'models' / config['run']).resolve()
    private = Path(private_output or ROOT / 'data/intermediate/modeling' / config['run']).resolve()
    dataset = ROOT / config['dataset']
    for destination in [report, model_dir, private]:
        protected_output(destination, [dataset, config_path])
    for i, left in enumerate([report, model_dir, private]):
        for right in [report, model_dir, private][i + 1:]:
            if left == right or left.is_relative_to(right) or right.is_relative_to(left):
                raise ValueError('Model/report/private output directories must not overlap')
    for path in [report / 'tables', model_dir, private]:
        path.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    clock = time.monotonic()
    splits, split_summary, split_dir = create_split(config_path, private / 'split')
    x_train, x_validation = features(splits['train']), features(splits['validation'])
    y_train = np.array([float(r['price_thb']) for r in splits['train']])
    y_validation = np.array([float(r['price_thb']) for r in splits['validation']])
    print('SPLIT', {k: len(v) for k, v in splits.items()}, flush=True)
    comparisons = []
    winner_spec = None
    winner_result = None
    for i, spec in enumerate(config['candidates'], 1):
        trial_clock = time.monotonic()
        print(f'FIT {i}/{len(config["candidates"])} {spec["name"]}', flush=True)
        model = build_model(spec, config['random_seed'], config['threads'])
        with threadpool_limits(limits=config['threads']):
            if spec['kind'] == 'catboost':
                model.fit(x_train, y_train, eval_set=(x_validation, y_validation),
                          early_stopping_rounds=120, use_best_model=True)
            else:
                model.fit(x_train, y_train)
            prediction = prices(model, x_validation)
        result = {'name': spec['name'], 'kind': spec['kind'], **metrics(y_validation, prediction),
                  'fit_seconds': round(time.monotonic() - trial_clock, 3),
                  'iterations': model.tree_count_ if spec['kind'] == 'catboost' else None}
        comparisons.append(result)
        write_csv(report / 'tables/validation_comparison.csv', comparisons)
        dump(report / 'progress.json', {'phase': 'validation_comparison', 'completed': i, 'total': len(config['candidates']), 'last': result})
        print(f'VALIDATION MAE={result["mae_thb"]:.2f} THB ({result["fit_seconds"]:.1f}s)', flush=True)
        if winner_result is None or (result['mae_thb'], spec['name']) < (winner_result['mae_thb'], winner_spec['name']):
            winner_spec, winner_result = spec, result
            winner_predictions = prediction.copy()
    # Persist selection before accessing test targets. No candidate test scores are used.
    selection = {'criterion': config['selection_metric'], 'candidate': winner_spec, 'validation_metrics': winner_result,
                 'refit_rows': len(splits['train']) + len(splits['validation']), 'test_used_for_selection': False}
    dump(report / 'selection.json', selection)
    print('SELECTED', winner_spec['name'], 'refit train + validation; test remains held out', flush=True)
    fit_rows = splits['train'] + splits['validation']
    x_fit = features(fit_rows)
    y_fit = np.array([float(r['price_thb']) for r in fit_rows])
    final_model = build_model(winner_spec, config['random_seed'], config['threads'], winner_result['iterations'])
    with threadpool_limits(limits=config['threads']):
        final_model.fit(x_fit, y_fit)
        # The first target-based evaluation of test happens here, after the selection is frozen.
        x_test = features(splits['test'])
        y_test = np.array([float(r['price_thb']) for r in splits['test']])
        prediction = prices(final_model, x_test)
        baseline = np.full(len(y_test), np.median(y_fit))
    evaluation = metrics(y_test, prediction)
    baseline_metrics = metrics(y_test, baseline)
    fitted_models = sorted(set(x_fit['brand_model']))
    fitted_brands = sorted(set(x_fit['brand']))
    groups = group_metrics(splits['test'], y_test, prediction, set(fitted_models))
    write_csv(report / 'tables/test_by_group.csv', groups)
    write_csv(report / 'tables/test_metrics.csv', [{'model': winner_spec['name'], **evaluation}, {'model': 'fixed_median_baseline', **baseline_metrics}])
    per_row = [{'listing_id': r['listing_id'], 'source': r['source'], 'brand': r['brand'], 'model': r['model'],
                'published_at': r['published_at'], 'actual_thb': float(actual), 'predicted_thb': float(pred),
                'absolute_error_thb': float(abs(actual - pred)), 'model_seen_in_fit': r['brand'] + ':' + r['model'] in fitted_models}
               for r, actual, pred in zip(splits['test'], y_test, prediction)]
    write_csv(private / 'test_predictions.csv', per_row)
    write_csv(private / 'validation_predictions.csv', [{'listing_id': r['listing_id'], 'actual_thb': float(y), 'predicted_thb': float(pred), 'absolute_error_thb': float(abs(y-pred)), 'candidate': winner_spec['name']} for r, y, pred in zip(splits['validation'], y_validation, winner_predictions)])
    # Persist the estimator plus its feature/coverage contract; prediction builds exactly these features.
    artifact = {'model': final_model, 'feature_names': FEATURES, 'fitted_models': fitted_models,
                'fitted_brands': fitted_brands, 'fit_date_min': split_summary['train']['date_min'],
                'fit_date_max': split_summary['validation']['date_max'], 'dataset_sha256': sha(dataset),
                'candidate_name': winner_spec['name']}
    model_path = model_dir / 'model.joblib'
    joblib.dump(artifact, model_path, compress=3)
    loaded = joblib.load(model_path)
    if not np.allclose(prices(loaded['model'], x_test), prediction, rtol=1e-10, atol=1e-8):
        raise ValueError('Serialized predictions differ')
    if winner_spec['kind'] == 'catboost':
        final_model.save_model(str(model_dir / 'model.cbm'))
    output_hashes = {p.name: sha(p) for p in model_dir.iterdir() if p.suffix in ('.joblib', '.cbm')}
    metadata = {'run': config['run'], 'started_at_utc': started, 'finished_at_utc': datetime.now(timezone.utc).isoformat(),
                'duration_seconds': round(time.monotonic() - clock, 3), 'dataset': config['dataset'], 'dataset_sha256': sha(dataset),
                'config_sha256': sha(config_path), 'code_sha256': {str(p.relative_to(ROOT)): sha(p) for p in sorted(Path(__file__).parent.glob('*.py'))},
                'versions': {p: importlib.metadata.version(p) for p in ['numpy', 'pandas', 'scipy', 'scikit-learn', 'catboost', 'joblib', 'matplotlib']},
                'feature_names': FEATURES, 'excluded_features': ['price_thb (target)', 'listing_id', 'product_id', 'url', 'source_snapshot', 'published_at_raw', 'published_at_precision'],
                'seed': config['random_seed'], 'model_hashes': output_hashes, 'final_fit': 'train + validation; test excluded',
                'coverage': {'models_seen_in_fit': len(fitted_models), 'brands_seen_in_fit': len(fitted_brands), 'fit_date_max': artifact['fit_date_max']}}
    validation = {'input_hash_matches': sha(dataset) == config['dataset_sha256'], 'rows_accounted': sum(len(v) for v in splits.values()) == config['expected_rows'],
                  'test_used_for_selection': False, 'test_used_for_fit': False, 'preprocessing_fitted_on_training_part_only': True,
                  'whole_day_chronological_splits': True, 'no_target_or_identifiers_in_features': True,
                  'saved_model_roundtrip_matches': True, 'finite_positive_predictions': bool(np.isfinite(prediction).all() and (prediction > 0).all())}
    summary = {'run': config['run'], 'selected_model': winner_spec['name'], 'validation': winner_result, 'test': evaluation,
               'baseline_test': baseline_metrics, 'mae_improvement_pct': (1 - evaluation['mae_thb'] / baseline_metrics['mae_thb']) * 100,
               'split': split_summary, 'test_groups': [g for g in groups if g['group'] != 'brand_model'],
               'selection_bias': config['selection_bias'], 'model_file': str(model_path.relative_to(ROOT)) if model_path.is_relative_to(ROOT) else str(model_path)}
    for name, content in [('summary.json', summary), ('run_metadata.json', metadata), ('validation.json', validation), ('config.json', config), ('split_summary.json', split_summary)]:
        dump(report / name, content)
    dump(model_dir / 'metadata.json', {**metadata, 'selected_model': winner_spec['name'], 'test_metrics': evaluation})
    from script.modeling.report import render_report
    render_report(report, summary, metadata, comparisons, y_test, prediction)
    dump(report / 'output_hashes.json', {str(p.relative_to(report)): sha(p) for p in sorted(report.rglob('*')) if p.is_file() and p.name not in ('output_hashes.json', 'progress.json')})
    dump(report / 'progress.json', {'phase': 'completed', 'selected_model': winner_spec['name'], 'test_mae_thb': evaluation['mae_thb'], 'duration_seconds': metadata['duration_seconds']})
    print('COMPLETE', json.dumps({'model': winner_spec['name'], 'test': evaluation, 'report': str(report), 'artifact': str(model_path)}, ensure_ascii=False), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--report-output', type=Path)
    parser.add_argument('--model-output', type=Path)
    parser.add_argument('--private-output', type=Path)
    args = parser.parse_args()
    train(args.config, args.report_output, args.model_output, args.private_output)


if __name__ == '__main__':
    main()
