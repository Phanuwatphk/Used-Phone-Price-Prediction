"""Private V2 experiment: paired two/five-window validation on the same listings.

Reuses the project's fit/feature/metric implementations. Components are fitted
once per window because only the final averaging weight differs across trials.
Published two-window scores must reproduce before five-window conclusions.
"""
import copy
import csv
from datetime import date, timedelta
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np
from threadpoolctl import threadpool_limits
from script.modeling.common import metrics
from script.modeling.model_v2.train_improved import fit, get_frame
from script.modeling.predict import load_model
from script.modeling.split_dataset import read_dataset, sha, dump, write_csv

OUTPUT = Path(__file__).with_suffix('')


def canonical(spec):
    return {key: value for key, value in spec.items() if key != 'name'}


def component_predictions(models, components, rows, catalog, threads):
    with threadpool_limits(limits=threads):
        predictions = np.asarray([model.predict(get_frame(spec, rows, catalog))
                                  for model, spec in zip(models, components)])
    if not np.isfinite(predictions).all():
        raise ValueError('Nonfinite component prediction')
    return predictions


def blend(predictions, spec):
    return np.maximum(1., np.average(predictions, axis=0, weights=spec['blend_weights']))


def run():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if (OUTPUT / 'summary.json').exists():
        raise ValueError('Completed experiment exists; preserve it before rerunning')
    started = time.monotonic()
    config_path = ROOT / 'config/modeling/current.json'
    config = json.loads(config_path.read_text())
    report = ROOT / 'docs/assets/modeling'
    published = json.loads((report / 'metadata.json').read_text())
    android = set(published['summary']['platform_evaluation']['android_brands'])
    protected = [config_path, ROOT / 'data/final/dataset.csv', ROOT / config['condition_features'],
                 ROOT / config['dataset'], ROOT / 'models/asking_price_v2/model.joblib',
                 ROOT / 'models/asking_price_v2/evaluation.joblib',
                 ROOT / 'models/asking_price_v2/metadata.json', report / 'metadata.json']
    hashes = {str(path.relative_to(ROOT)): sha(path) for path in protected}
    rows = sorted([row for row in read_dataset(ROOT / config['dataset'], config['dataset_sha256'])
                   if row['condition'] == 'used'], key=lambda row: (row['published_at'], row['listing_id']))
    assert len(rows) == config['expected_training_rows'] == 9100
    catalog = json.loads((ROOT / config['catalog']).read_text())['release_years']
    specs = [copy.deepcopy(spec) for spec in config['candidates'] if spec.get('eligible_for_selection', True)]
    components = specs[0]['components']
    assert len(specs) == 3
    for spec in specs:
        assert spec['half_life'] == 2
        assert [canonical(component) for component in spec['components']] == [canonical(c) for c in components]
    start = config['folds'][0]['start']
    cutoff = config['retrospective_test_start']
    validation = [row for row in rows if start <= row['published_at'] < cutoff]
    assert len(validation) == 955
    boundaries = [start] + [validation[len(validation) * index // 5]['published_at'] for index in range(1, 5)] + [cutoff]
    assert len(set(boundaries)) == 6
    five = [{'start': lower, 'end': (date.fromisoformat(upper) - timedelta(days=1)).isoformat()}
            for lower, upper in zip(boundaries, boundaries[1:])]
    designs = {'two_windows': config['folds'], 'five_windows': five}
    dump(OUTPUT / 'plan.json', {'model_version': 2, 'designs': designs, 'candidates': specs,
                              'validation_rows': len(validation), 'test_cutoff': cutoff,
                              'five_window_policy': 'Date-only row quantiles; all listings on a day stay together; same validation IDs and horizon as two windows.',
                              'selection': 'Pooled validation MAE; test not used for selecting either weight.',
                              'input_hashes': hashes, 'script_sha256': sha(Path(__file__))})
    with (report / 'tables/validation_comparison.csv').open() as handle:
        expected = {row['name']: float(row['mae_thb']) for row in csv.DictReader(handle)}
    folds, pooled, grouped, per_row = [], [], [], []
    selections = {}
    for design, intervals in designs.items():
        oof_rows, actuals = [], []
        oof_predictions = {spec['name']: [] for spec in specs}
        for index, interval in enumerate(intervals, 1):
            train = [row for row in rows if row['published_at'] < interval['start']]
            valid = [row for row in rows if interval['start'] <= row['published_at'] <= interval['end']]
            assert train and valid and train[-1]['published_at'] < valid[0]['published_at']
            assert valid[-1]['published_at'] < cutoff
            print(f'{design} fold {index}/{len(intervals)} train={len(train)} validation={len(valid)}', flush=True)
            clock = time.monotonic()
            models = [fit(component, train, catalog, config) for component in components]
            valid_components = component_predictions(models, components, valid, catalog, config['threads'])
            train_components = component_predictions(models, components, train, catalog, config['threads'])
            actual = np.asarray([float(row['price_thb']) for row in valid])
            train_actual = np.asarray([float(row['price_thb']) for row in train])
            oof_rows.extend(valid)
            actuals.extend(actual)
            for spec in specs:
                pred = blend(valid_components, spec)
                score = metrics(actual, pred)
                oof_predictions[spec['name']].extend(pred)
                folds.append({'design': design, 'fold': index, 'candidate': spec['name'],
                              'cat_share': spec['blend_weights'][1], 'train_rows': len(train),
                              'train_max': train[-1]['published_at'], 'validation_min': valid[0]['published_at'],
                              'validation_max': valid[-1]['published_at'],
                              'android_rows': sum(row['brand'] in android for row in valid),
                              'train_mae_thb': metrics(train_actual, blend(train_components, spec))['mae_thb'], **score})
                per_row.extend({'design': design, 'fold': index, 'candidate': spec['name'],
                                'listing_id': row['listing_id'], 'brand': row['brand'], 'model': row['model'],
                                'actual_thb': float(y), 'predicted_thb': float(p)} for row, y, p in zip(valid, actual, pred))
            write_csv(OUTPUT / 'fold_metrics.csv', folds)
            print(f'  component fitting/prediction {time.monotonic()-clock:.1f}s', flush=True)
        assert len(oof_rows) == len({row['listing_id'] for row in oof_rows}) == len(validation)
        assert {row['listing_id'] for row in oof_rows} == {row['listing_id'] for row in validation}
        for spec in specs:
            name = spec['name']
            pred = np.asarray(oof_predictions[name])
            actual = np.asarray(actuals)
            score = {'design': design, 'candidate': name, 'cat_share': spec['blend_weights'][1], **metrics(actual, pred)}
            pooled.append(score)
            if design == 'two_windows':
                assert abs(score['mae_thb'] - expected[name]) < 1e-6, (name, score['mae_thb'], expected[name])
            for platform in ['iPhone', 'Android', 'other']:
                indices = [i for i, row in enumerate(oof_rows) if
                           ('iPhone' if row['brand'] == 'Apple' else 'Android' if row['brand'] in android else 'other') == platform]
                grouped.append({'design': design, 'candidate': name, 'platform': platform,
                                **metrics(actual[indices], pred[indices])})
            print(f'  POOLED {name}: MAE {score["mae_thb"]:.2f}', flush=True)
        best = min([score for score in pooled if score['design'] == design], key=lambda score: (score['mae_thb'], score['candidate']))
        selections[design] = {'candidate': best['candidate'], 'cat_share': best['cat_share'], 'validation_mae_thb': best['mae_thb']}
        write_csv(OUTPUT / 'pooled_metrics.csv', pooled)
        dump(OUTPUT / 'selection.json', {'selected_before_retrospective_scoring': True, 'selection_metric': 'pooled_validation_mae', 'designs': selections})
    # Fitting a different final blend weight cannot change its component fits:
    # each member was independently trained on the same 8,418 rows. Reuse the
    # checked evaluation artifact's members after validation selection is frozen.
    artifact = load_model(ROOT / 'models/asking_price_v2/evaluation.joblib')
    assert artifact['candidate_name'] == published['summary']['selected_model']
    evaluation_models = artifact['model'].named_steps['regressor'].estimators_
    test = [row for row in rows if row['published_at'] >= cutoff]
    assert len(test) == 682
    test_components = component_predictions(evaluation_models, components, test, catalog, config['threads'])
    actual = np.asarray([float(row['price_thb']) for row in test])
    retrospective = []
    for design, selection in selections.items():
        spec = next(spec for spec in specs if spec['name'] == selection['candidate'])
        pred = blend(test_components, spec)
        for platform in ['all', 'iPhone', 'Android', 'other']:
            indices = [i for i, row in enumerate(test) if platform == 'all' or
                       ('iPhone' if row['brand'] == 'Apple' else 'Android' if row['brand'] in android else 'other') == platform]
            retrospective.append({'design': design, 'candidate': spec['name'], 'platform': platform,
                                  **metrics(actual[indices], pred[indices])})
    reference = next(row for row in retrospective if row['design'] == 'two_windows' and row['platform'] == 'all')
    assert abs(reference['mae_thb'] - published['summary']['retrospective']['mae_thb']) < 1e-6
    assert hashes == {str(path.relative_to(ROOT)): sha(path) for path in protected}
    write_csv(OUTPUT / 'validation_group_metrics.csv', grouped)
    write_csv(OUTPUT / 'validation_predictions.csv', per_row)
    write_csv(OUTPUT / 'retrospective_metrics.csv', retrospective)
    summary = {'model_version': 2, 'selections': selections, 'pooled_metrics': pooled,
               'retrospective': retrospective, 'validation_ids_identical': True,
               'published_two_window_results_reproduced': True, 'production_files_unchanged': True,
               'fresh_independent_holdout': False, 'duration_seconds': time.monotonic()-started,
               'interpretation': 'More windows update training more frequently; score changes are not proof of improved deployment accuracy. Windows overlap in training and are not independent replications.'}
    dump(OUTPUT / 'summary.json', summary)
    print('COMPLETE', json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    run()
